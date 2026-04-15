"""
Auto-rejoin session tracking and monitor logic.
"""

import ctypes
import platform
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Optional

import requests

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


@dataclass
class SessionEntry:
    username: str
    cookie: str
    place_id: str = ""
    private_server_link: str = ""
    pid: int = 0
    auto_rejoin: bool = False
    rejoin_delay: int = 5
    max_rejoin_attempts: int = 0
    user_id: str = ""
    server_job_id: str = ""
    launch_mode: str = "game"
    version_path: Optional[str] = None
    rejoin_attempts: int = 0
    intentionally_stopped: bool = False
    rejoin_in_progress: bool = False
    last_presence_type: Optional[int] = None
    last_presence_check_at: float = 0.0
    has_seen_in_game: bool = False
    has_seen_process_alive: bool = False
    has_seen_window: bool = False
    last_game_location: str = ""
    disabled_reason: str = ""


class AutoRejoinMonitor:
    POLL_INTERVAL_SECONDS = 20.0
    LOOP_INTERVAL_SECONDS = 2.0
    MANUAL_STOP_GRACE_SECONDS = 45.0

    def __init__(
        self,
        launch_callback: Callable[[SessionEntry, int], bool],
        presence_lookup: Callable[..., Dict],
        log_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str, str, int], None]] = None,
        validate_account_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.launch_callback = launch_callback
        self.presence_lookup = presence_lookup
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.validate_account_callback = validate_account_callback

        self.active_sessions: Dict[str, SessionEntry] = {}
        self._manual_stop_grace: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._presence_session = requests.Session()

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="auto-rejoin-monitor",
            )
            self._thread.start()

    def stop(self, timeout=5.0):
        self._stop_event.set()
        thread = None
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))
        with self._lock:
            self._thread = None
            self.active_sessions.clear()
            self._manual_stop_grace.clear()
        try:
            self._presence_session.close()
        except Exception:
            pass

    def register_session(
        self,
        username,
        cookie,
        place_id="",
        private_server_link="",
        pid=0,
        auto_rejoin=False,
        rejoin_delay=5,
        max_rejoin_attempts=0,
        user_id="",
        server_job_id="",
        launch_mode="game",
        version_path=None,
        preserve_rejoin_attempts=False,
    ):
        username = str(username or "").strip()
        if not username:
            return None

        normalized_mode = str(launch_mode or "game").strip().lower()
        if normalized_mode not in {"game", "join_user"}:
            normalized_mode = "game"

        normalized_pid = self._normalize_int(pid, default=0, minimum=0)
        normalized_delay = self._normalize_int(rejoin_delay, default=5, minimum=0)
        normalized_attempts = self._normalize_int(max_rejoin_attempts, default=0, minimum=0)
        normalized_place_id = str(place_id or "").strip()
        normalized_private_server = str(private_server_link or "").strip()
        normalized_server_job_id = str(server_job_id or "").strip()
        normalized_user_id = str(user_id or "").strip()
        normalized_version_path = str(version_path).strip() if version_path else None

        with self._lock:
            self._manual_stop_grace.pop(username, None)
            session = self.active_sessions.get(username)
            if session is None:
                session = SessionEntry(username=username, cookie=str(cookie or "").strip())
                self.active_sessions[username] = session

            keep_attempts = bool(preserve_rejoin_attempts) or bool(session.rejoin_in_progress)
            session.username = username
            session.cookie = str(cookie or "").strip()
            session.place_id = normalized_place_id
            session.private_server_link = normalized_private_server
            session.pid = normalized_pid
            session.auto_rejoin = bool(auto_rejoin)
            session.rejoin_delay = normalized_delay
            session.max_rejoin_attempts = normalized_attempts
            if normalized_user_id:
                session.user_id = normalized_user_id
            session.server_job_id = normalized_server_job_id
            session.launch_mode = normalized_mode
            session.version_path = normalized_version_path
            session.intentionally_stopped = False
            session.disabled_reason = ""

            if not keep_attempts:
                session.rejoin_attempts = 0
                session.rejoin_in_progress = False
            else:
                session.rejoin_in_progress = True

            session.last_presence_type = None
            session.last_presence_check_at = 0.0
            session.has_seen_in_game = False
            session.has_seen_process_alive = bool(
                normalized_pid and self._is_process_running(normalized_pid)
            )
            session.has_seen_window = bool(
                normalized_pid and self._window_exists_for_pid(normalized_pid)
            )
            return session

    def update_session_pid(self, username, pid):
        username = str(username or "").strip()
        normalized_pid = self._normalize_int(pid, default=0, minimum=0)
        if not username or normalized_pid <= 0:
            return False

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return False
            session.pid = normalized_pid
            session.intentionally_stopped = False
            session.has_seen_process_alive = bool(self._is_process_running(normalized_pid))
            session.has_seen_window = bool(self._window_exists_for_pid(normalized_pid))
            session.rejoin_in_progress = False
            return True

    def update_session_preferences(
        self,
        username,
        auto_rejoin=None,
        rejoin_delay=None,
        max_rejoin_attempts=None,
    ):
        username = str(username or "").strip()
        if not username:
            return False

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return False

            if auto_rejoin is not None:
                session.auto_rejoin = bool(auto_rejoin)
                if not session.auto_rejoin:
                    session.rejoin_in_progress = False
            if rejoin_delay is not None:
                session.rejoin_delay = self._normalize_int(rejoin_delay, default=5, minimum=0)
            if max_rejoin_attempts is not None:
                session.max_rejoin_attempts = self._normalize_int(
                    max_rejoin_attempts,
                    default=0,
                    minimum=0,
                )
            return True

    def mark_intentionally_stopped(self, username=None, pid=None):
        resolved_username = str(username or "").strip()
        normalized_pid = self._normalize_int(pid, default=0, minimum=0)

        with self._lock:
            if not resolved_username and normalized_pid > 0:
                for candidate_username, session in self.active_sessions.items():
                    if int(session.pid or 0) == normalized_pid:
                        resolved_username = candidate_username
                        break

            if not resolved_username:
                return False

            self._manual_stop_grace[resolved_username] = (
                time.monotonic() + self.MANUAL_STOP_GRACE_SECONDS
            )

            session = self.active_sessions.pop(resolved_username, None)
            if session is not None:
                session.intentionally_stopped = True
                session.auto_rejoin = False
                session.rejoin_in_progress = False
            return True

    def clear_session(self, username):
        username = str(username or "").strip()
        if not username:
            return False
        with self._lock:
            removed = self.active_sessions.pop(username, None)
        return removed is not None

    def get_session_snapshot(self, username):
        username = str(username or "").strip()
        if not username:
            return None
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return None
            return asdict(session)

    def _run(self):
        while not self._stop_event.is_set():
            self._expire_manual_stop_grace()
            usernames = self._get_usernames()
            for username in usernames:
                if self._stop_event.is_set():
                    return
                try:
                    self._monitor_session(username)
                except Exception as exc:
                    self._log(f"[AUTO REJOIN] Monitor error for {username}: {exc}")
            self._stop_event.wait(self.LOOP_INTERVAL_SECONDS)

    def _get_usernames(self):
        with self._lock:
            return list(self.active_sessions.keys())

    def _expire_manual_stop_grace(self):
        now = time.monotonic()
        with self._lock:
            expired = [
                username
                for username, expires_at in self._manual_stop_grace.items()
                if expires_at <= now
            ]
            for username in expired:
                self._manual_stop_grace.pop(username, None)

    def _monitor_session(self, username):
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            pid_value = int(session.pid or 0)
            process_seen = bool(session.has_seen_process_alive)
            window_seen = bool(session.has_seen_window)
            rejoin_in_progress = bool(session.rejoin_in_progress)
            auto_rejoin = bool(session.auto_rejoin)
            last_presence_check_at = float(session.last_presence_check_at or 0.0)
            user_id = str(session.user_id or "").strip()
            cookie = str(session.cookie or "").strip()

        process_running = bool(pid_value and self._is_process_running(pid_value))
        window_exists = bool(pid_value and self._window_exists_for_pid(pid_value))

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            if process_running:
                session.has_seen_process_alive = True
            if window_exists:
                session.has_seen_window = True

        if rejoin_in_progress:
            return

        if pid_value and process_seen and not process_running:
            if auto_rejoin and not self._is_manual_stop_active(username):
                self._queue_rejoin(username, reason="process exit")
            else:
                with self._lock:
                    self.active_sessions.pop(username, None)
            return

        if pid_value and window_seen and not window_exists and not process_running:
            if auto_rejoin and not self._is_manual_stop_active(username):
                self._queue_rejoin(username, reason="window closed")
            else:
                with self._lock:
                    self.active_sessions.pop(username, None)
            return

        if not auto_rejoin:
            return

        now = time.monotonic()
        if (now - last_presence_check_at) < self.POLL_INTERVAL_SECONDS:
            return

        if not user_id.isdigit():
            self._disable_session(
                username,
                reason="missing_user_id",
                status_text="Auto-Rejoin unavailable",
                log_message=(
                    f"[AUTO REJOIN] {username}: unable to monitor presence because no user ID was resolved."
                ),
            )
            return

        presence_result = {}
        try:
            presence_result = self.presence_lookup(
                cookie,
                [int(user_id)],
                session=self._presence_session,
            ) or {}
        except Exception as exc:
            self._log(f"[AUTO REJOIN] Presence lookup failed for {username}: {exc}")
            with self._lock:
                session = self.active_sessions.get(username)
                if session is not None:
                    session.last_presence_check_at = now
            return

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.last_presence_check_at = now

        if not presence_result.get("ok", False):
            if presence_result.get("auth_error", False) or self._account_is_invalid(username):
                self._disable_session(
                    username,
                    reason="cookie_invalid",
                    status_text="Auto-Rejoin disabled",
                    log_message=(
                        f"[AUTO REJOIN] {username}: cookie appears invalid or expired; "
                        "auto-rejoin has been disabled for this session."
                    ),
                )
            return

        user_presences = presence_result.get("user_presences") or []
        if not user_presences:
            return

        presence = user_presences[0] or {}
        current_presence_type = self._normalize_int(
            presence.get("userPresenceType"),
            default=0,
            minimum=0,
        )
        place_id = str(presence.get("placeId") or "").strip()
        game_id = str(presence.get("gameId") or "").strip()
        location = str(presence.get("lastLocation") or "").strip()

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            previous_presence_type = session.last_presence_type
            if place_id:
                session.place_id = place_id
            if game_id:
                session.server_job_id = game_id
            if location:
                session.last_game_location = location
            session.last_presence_type = current_presence_type

            if current_presence_type == 2:
                session.has_seen_in_game = True
                session.rejoin_in_progress = False
                self._set_status(username, "", ttl_seconds=0)
                return

            if session.has_seen_in_game and previous_presence_type == 2:
                should_rejoin = True
            else:
                should_rejoin = False

            should_clear = bool(session.has_seen_in_game and current_presence_type != 2 and not process_running)

        if should_rejoin:
            self._queue_rejoin(username, reason="presence transition")
            return

        if should_clear:
            with self._lock:
                self.active_sessions.pop(username, None)

    def _queue_rejoin(self, username, reason):
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return False
            if session.rejoin_in_progress or session.intentionally_stopped:
                return False
            if not session.auto_rejoin or self._is_manual_stop_active(username):
                return False
            if session.max_rejoin_attempts > 0 and session.rejoin_attempts >= session.max_rejoin_attempts:
                self._disable_session(
                    username,
                    reason="max_attempts_reached",
                    status_text="Max rejoin attempts reached",
                    log_message=(
                        f"[AUTO REJOIN] {username}: max rejoin attempts reached "
                        f"({session.max_rejoin_attempts})."
                    ),
                )
                return False

            session.rejoin_in_progress = True
            session.last_presence_type = None
            attempt_number = session.rejoin_attempts + 1
            delay_seconds = session.rejoin_delay
            place_id = str(session.place_id or "").strip() or "Unknown"

        self._set_status(username, "Kicked - Rejoining", ttl_seconds=15)
        self._log(
            f"[AUTO REJOIN] {username}: disconnect detected for place {place_id} "
            f"({reason}). Attempt {attempt_number} in {delay_seconds}s."
        )
        threading.Thread(
            target=self._rejoin_worker,
            args=(username,),
            daemon=True,
            name=f"auto-rejoin-{username}",
        ).start()
        return True

    def _rejoin_worker(self, username):
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            delay_seconds = max(0, int(session.rejoin_delay))

        if self._stop_event.wait(delay_seconds):
            self._finish_rejoin(username, keep_enabled=True)
            return

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            if session.intentionally_stopped or self._is_manual_stop_active(username):
                session.rejoin_in_progress = False
                return
            if not session.auto_rejoin:
                session.rejoin_in_progress = False
                return
            if session.max_rejoin_attempts > 0 and session.rejoin_attempts >= session.max_rejoin_attempts:
                self._disable_session(
                    username,
                    reason="max_attempts_reached",
                    status_text="Max rejoin attempts reached",
                    log_message=(
                        f"[AUTO REJOIN] {username}: max rejoin attempts reached "
                        f"({session.max_rejoin_attempts})."
                    ),
                )
                return

            if not str(session.place_id or "").strip():
                self._disable_session(
                    username,
                    reason="missing_place_id",
                    status_text="Auto-Rejoin unavailable",
                    log_message=(
                        f"[AUTO REJOIN] {username}: no place ID is available for rejoin."
                    ),
                )
                return

        if self._account_is_invalid(username):
            self._disable_session(
                username,
                reason="cookie_invalid",
                status_text="Auto-Rejoin disabled",
                log_message=(
                    f"[AUTO REJOIN] {username}: cookie appears invalid or expired; "
                    "auto-rejoin has been disabled for this session."
                ),
            )
            return

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.rejoin_attempts += 1
            attempt_number = int(session.rejoin_attempts)
            place_id = str(session.place_id or "").strip()

        self._log(
            f"[AUTO REJOIN] Attempt {attempt_number}: account={username} place_id={place_id}"
        )

        launched = False
        try:
            launched = bool(self.launch_callback(session, attempt_number))
        except Exception as exc:
            self._log(f"[AUTO REJOIN] Launch callback failed for {username}: {exc}")
            launched = False

        if not launched:
            self._finish_rejoin(username, keep_enabled=True)
            self._set_status(username, "Auto-Rejoin failed", ttl_seconds=12)
            return

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.rejoin_in_progress = True
            session.pid = 0
            session.last_presence_type = None
            session.last_presence_check_at = 0.0
            session.has_seen_in_game = False
            session.has_seen_process_alive = False
            session.has_seen_window = False

    def _finish_rejoin(self, username, keep_enabled):
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.rejoin_in_progress = False
            if not keep_enabled:
                session.auto_rejoin = False

    def _disable_session(self, username, reason, status_text="", log_message=""):
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.auto_rejoin = False
            session.rejoin_in_progress = False
            session.disabled_reason = str(reason or "").strip()

        if log_message:
            self._log(log_message)
        if status_text:
            self._set_status(username, status_text, ttl_seconds=12)

    def _account_is_invalid(self, username):
        if not callable(self.validate_account_callback):
            return False
        try:
            return not bool(self.validate_account_callback(username))
        except Exception:
            return False

    def _is_manual_stop_active(self, username):
        expires_at = 0.0
        with self._lock:
            expires_at = float(self._manual_stop_grace.get(username, 0.0) or 0.0)
        return expires_at > time.monotonic()

    def _log(self, message):
        text = str(message or "").strip()
        if not text:
            return
        if callable(self.log_callback):
            try:
                self.log_callback(text)
                return
            except Exception:
                pass
        print(text)

    def _set_status(self, username, text, ttl_seconds=0):
        if not callable(self.status_callback):
            return
        try:
            self.status_callback(str(username or "").strip(), str(text or ""), int(ttl_seconds or 0))
        except Exception:
            pass

    @staticmethod
    def _normalize_int(value, default=0, minimum=0):
        try:
            parsed = int(value)
        except Exception:
            parsed = int(default)
        return max(int(minimum), parsed)

    @staticmethod
    def _is_process_running(pid):
        pid_value = AutoRejoinMonitor._normalize_int(pid, default=0, minimum=0)
        if pid_value <= 0 or platform.system() != "Windows":
            return False

        handle = None
        try:
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                pid_value,
            )
            if not handle:
                return False

            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0:
                return False
            return int(exit_code.value) == STILL_ACTIVE
        except Exception:
            return False
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)
                except Exception:
                    pass

    @staticmethod
    def _window_exists_for_pid(pid):
        pid_value = AutoRejoinMonitor._normalize_int(pid, default=0, minimum=0)
        if (
            pid_value <= 0
            or platform.system() != "Windows"
            or win32gui is None
            or win32process is None
        ):
            return False

        found = {"value": False}

        def _enum_handler(hwnd, _):
            if found["value"]:
                return False
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if int(window_pid) != pid_value:
                return True
            title = ""
            try:
                title = str(win32gui.GetWindowText(hwnd) or "").strip()
            except Exception:
                title = ""
            if title or win32gui.GetClassName(hwnd) == "WINDOWSCLIENT":
                found["value"] = True
                return False
            return True

        try:
            win32gui.EnumWindows(_enum_handler, None)
        except Exception:
            return False
        return found["value"]
