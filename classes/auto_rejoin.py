"""
Auto-rejoin session tracking and monitor logic.
"""

import ctypes
import platform
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import requests

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
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
    rejoin_launch_behavior: str = "rejoin_same_server"
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


@dataclass(frozen=True)
class PresenceCheckCandidate:
    username: str
    cookie: str
    user_id: int
    process_running: bool


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
        rejoin_launch_behavior="rejoin_same_server",
        version_path=None,
        preserve_rejoin_attempts=False,
    ):
        username = str(username or "").strip()
        if not username:
            return None

        normalized_mode = str(launch_mode or "game").strip().lower()
        if normalized_mode not in {"game", "join_user"}:
            normalized_mode = "game"
        normalized_rejoin_launch_behavior = self._normalize_rejoin_launch_behavior(
            rejoin_launch_behavior
        )

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
            session.rejoin_launch_behavior = normalized_rejoin_launch_behavior
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
        rejoin_launch_behavior=None,
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
            if rejoin_launch_behavior is not None:
                session.rejoin_launch_behavior = self._normalize_rejoin_launch_behavior(
                    rejoin_launch_behavior
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

    def get_session_snapshot(self, username):
        username = str(username or "").strip()
        if not username:
            return None
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return None
            return asdict(session)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._expire_manual_stop_grace()
            usernames, process_states, visible_window_pids = self._build_monitor_snapshot()
            presence_candidates: List[PresenceCheckCandidate] = []
            for username in usernames:
                if self._stop_event.is_set():
                    return
                try:
                    presence_candidate = self._monitor_session(
                        username,
                        process_states=process_states,
                        visible_window_pids=visible_window_pids,
                    )
                    if presence_candidate is not None:
                        presence_candidates.append(presence_candidate)
                except Exception as exc:
                    self._log(f"[AUTO REJOIN] Monitor error for {username}: {exc}")
            if presence_candidates and not self._stop_event.is_set():
                try:
                    self._run_presence_check_batch(presence_candidates)
                except Exception as exc:
                    self._log(f"[AUTO REJOIN] Presence batch error: {exc}")
            self._stop_event.wait(self.LOOP_INTERVAL_SECONDS)

    def _build_monitor_snapshot(self) -> Tuple[List[str], Dict[int, bool], Set[int]]:
        with self._lock:
            usernames = list(self.active_sessions.keys())
            pid_values = {
                self._normalize_int(session.pid, default=0, minimum=0)
                for session in self.active_sessions.values()
            }

        tracked_pids = {pid_value for pid_value in pid_values if pid_value > 0}
        process_states = {
            pid_value: self._is_process_running(pid_value)
            for pid_value in tracked_pids
        }
        visible_window_pids = self._get_visible_window_pids(tracked_pids)
        return usernames, process_states, visible_window_pids

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

    def _monitor_session(
        self,
        username: str,
        process_states: Optional[Dict[int, bool]] = None,
        visible_window_pids: Optional[Set[int]] = None,
    ) -> Optional[PresenceCheckCandidate]:
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return None
            pid_value = int(session.pid or 0)
            process_seen = bool(session.has_seen_process_alive)
            window_seen = bool(session.has_seen_window)
            rejoin_in_progress = bool(session.rejoin_in_progress)
            auto_rejoin = bool(session.auto_rejoin)
            last_presence_check_at = float(session.last_presence_check_at or 0.0)
            user_id = str(session.user_id or "").strip()
            cookie = str(session.cookie or "").strip()

        process_running = bool(
            pid_value and (
                process_states.get(pid_value)
                if isinstance(process_states, dict)
                else self._is_process_running(pid_value)
            )
        )
        window_exists = bool(
            pid_value and (
                pid_value in visible_window_pids
                if isinstance(visible_window_pids, set)
                else self._window_exists_for_pid(pid_value)
            )
        )

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return None
            if process_running:
                session.has_seen_process_alive = True
            if window_exists:
                session.has_seen_window = True

        if rejoin_in_progress:
            return None

        if pid_value and process_seen and not process_running:
            if auto_rejoin and not self._is_manual_stop_active(username):
                self._queue_rejoin(username, reason="process exit")
            else:
                with self._lock:
                    self.active_sessions.pop(username, None)
            return None

        if pid_value and window_seen and not window_exists and not process_running:
            if auto_rejoin and not self._is_manual_stop_active(username):
                self._queue_rejoin(username, reason="window closed")
            else:
                with self._lock:
                    self.active_sessions.pop(username, None)
            return None

        if not auto_rejoin:
            return None

        now = time.monotonic()
        if (now - last_presence_check_at) < self.POLL_INTERVAL_SECONDS:
            return None

        if not user_id.isdigit():
            self._disable_session(
                username,
                reason="missing_user_id",
                status_text="Auto-Rejoin unavailable",
                log_message=(
                    f"[AUTO REJOIN] {username}: unable to monitor presence because no user ID was resolved."
                ),
            )
            return None

        return PresenceCheckCandidate(
            username=username,
            cookie=cookie,
            user_id=int(user_id),
            process_running=process_running,
        )

    def _run_presence_check_batch(self, candidates: List[PresenceCheckCandidate]) -> None:
        grouped_candidates = self._group_presence_candidates_by_cookie(candidates)
        for cookie, cookie_candidates in grouped_candidates.items():
            if self._stop_event.is_set():
                return
            checked_at = time.monotonic()
            user_ids = list(dict.fromkeys(candidate.user_id for candidate in cookie_candidates))
            try:
                presence_result: Dict[str, object] = self.presence_lookup(
                    cookie,
                    user_ids,
                    session=self._presence_session,
                ) or {}
            except Exception as exc:
                self._handle_presence_lookup_failure(cookie_candidates, checked_at, exc)
                continue
            self._handle_presence_lookup_result(cookie_candidates, presence_result, checked_at)

    def _group_presence_candidates_by_cookie(
        self,
        candidates: List[PresenceCheckCandidate],
    ) -> Dict[str, List[PresenceCheckCandidate]]:
        grouped_candidates: Dict[str, List[PresenceCheckCandidate]] = {}
        for candidate in candidates:
            grouped_candidates.setdefault(candidate.cookie, []).append(candidate)
        return grouped_candidates

    def _handle_presence_lookup_failure(
        self,
        candidates: List[PresenceCheckCandidate],
        checked_at: float,
        error: Exception,
    ) -> None:
        usernames = ", ".join(candidate.username for candidate in candidates)
        self._log(f"[AUTO REJOIN] Presence lookup failed for {usernames}: {error}")
        self._update_presence_check_timestamps(candidates, checked_at)

    def _handle_presence_lookup_result(
        self,
        candidates: List[PresenceCheckCandidate],
        presence_result: Dict[str, object],
        checked_at: float,
    ) -> None:
        self._update_presence_check_timestamps(candidates, checked_at)

        if not presence_result.get("ok", False):
            auth_error = bool(presence_result.get("auth_error", False))
            for candidate in candidates:
                if auth_error or self._account_is_invalid(candidate.username):
                    self._disable_session(
                        candidate.username,
                        reason="cookie_invalid",
                        status_text="Auto-Rejoin disabled",
                        log_message=(
                            f"[AUTO REJOIN] {candidate.username}: cookie appears invalid or expired; "
                            "auto-rejoin has been disabled for this session."
                        ),
                    )
            return

        raw_user_presences = presence_result.get("user_presences") or []
        if not isinstance(raw_user_presences, list):
            return

        presence_by_user_id = self._build_presence_by_user_id(raw_user_presences)
        if not presence_by_user_id:
            return

        for candidate in candidates:
            presence = presence_by_user_id.get(candidate.user_id)
            if presence is not None:
                self._handle_presence_entry(candidate, presence)

    def _update_presence_check_timestamps(
        self,
        candidates: List[PresenceCheckCandidate],
        checked_at: float,
    ) -> None:
        with self._lock:
            for candidate in candidates:
                session = self.active_sessions.get(candidate.username)
                if session is not None:
                    session.last_presence_check_at = checked_at

    def _build_presence_by_user_id(
        self,
        user_presences: Iterable[object],
    ) -> Dict[int, Dict[str, object]]:
        presence_by_user_id: Dict[int, Dict[str, object]] = {}
        for presence in user_presences:
            if not isinstance(presence, dict):
                continue
            presence_user_id = self._normalize_int(
                presence.get("userId"),
                default=0,
                minimum=0,
            )
            if presence_user_id > 0:
                presence_by_user_id[presence_user_id] = presence
        return presence_by_user_id

    def _handle_presence_entry(
        self,
        candidate: PresenceCheckCandidate,
        presence: Dict[str, object],
    ) -> None:
        username = candidate.username
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
            if str(session.cookie or "").strip() != candidate.cookie:
                return
            if self._normalize_int(session.user_id, default=0, minimum=0) != candidate.user_id:
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

            should_clear = bool(
                session.has_seen_in_game
                and current_presence_type != 2
                and not candidate.process_running
            )

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
            rejoin_launch_behavior = self._normalize_rejoin_launch_behavior(
                session.rejoin_launch_behavior
            )

        if rejoin_launch_behavior == "rejoin_same_game":
            status_text = "Kicked - Rejoining Game"
            target_text = f"place {place_id}"
        else:
            status_text = "Kicked - Rejoining Server"
            target_text = f"server for place {place_id}"

        self._set_status(username, status_text, ttl_seconds=15)
        self._log(
            f"[AUTO REJOIN] {username}: disconnect detected for {target_text} "
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

            rejoin_launch_behavior = self._normalize_rejoin_launch_behavior(
                session.rejoin_launch_behavior
            )
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

        previous_pid = 0
        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            previous_pid = self._normalize_int(session.pid, default=0, minimum=0)
            if previous_pid > 0:
                session.pid = 0

        if previous_pid > 0:
            self._close_tracked_process(previous_pid, username)

        with self._lock:
            session = self.active_sessions.get(username)
            if session is None:
                return
            session.rejoin_attempts += 1
            attempt_number = int(session.rejoin_attempts)
            place_id = str(session.place_id or "").strip()
            rejoin_launch_behavior = self._normalize_rejoin_launch_behavior(
                session.rejoin_launch_behavior
            )

        action_text = (
            "rejoin same game"
            if rejoin_launch_behavior == "rejoin_same_game"
            else "rejoin same server"
        )
        self._log(
            f"[AUTO REJOIN] Attempt {attempt_number}: account={username} action={action_text} place_id={place_id}"
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

    def _close_tracked_process(self, pid, username=""):
        pid_value = self._normalize_int(pid, default=0, minimum=0)
        if pid_value <= 0 or platform.system() != "Windows":
            return False
        if not self._is_process_running(pid_value):
            return False

        handle = None
        try:
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                False,
                pid_value,
            )
            if not handle:
                self._log(
                    f"[AUTO REJOIN] {username}: failed to open previous Roblox process {pid_value} for termination."
                )
                return False

            if ctypes.windll.kernel32.TerminateProcess(handle, 1) == 0:
                self._log(
                    f"[AUTO REJOIN] {username}: failed to terminate previous Roblox process {pid_value}."
                )
                return False

            ctypes.windll.kernel32.WaitForSingleObject(handle, 5000)
            self._log(
                f"[AUTO REJOIN] {username}: closed previous Roblox process {pid_value} before rejoining."
            )
            return True
        except Exception as exc:
            self._log(
                f"[AUTO REJOIN] {username}: error while closing previous Roblox process {pid_value}: {exc}"
            )
            return False
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)
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
    def _normalize_rejoin_launch_behavior(value: object) -> str:
        normalized = str(value or "rejoin_same_server").strip().lower()
        if normalized in {"relaunch_client_same_server", "relaunch_client", "client", "app"}:
            return "rejoin_same_server"
        if normalized in {"relaunch_client_same_game", "relaunch_game_client"}:
            return "rejoin_same_game"
        if normalized in {"rejoin_same_game", "same_game"}:
            return "rejoin_same_game"
        return "rejoin_same_server"

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

    @staticmethod
    def _get_visible_window_pids(pid_values):
        normalized_pid_values = {
            AutoRejoinMonitor._normalize_int(pid_value, default=0, minimum=0)
            for pid_value in (pid_values or set())
        }
        normalized_pid_values.discard(0)
        if (
            not normalized_pid_values
            or platform.system() != "Windows"
            or win32gui is None
            or win32process is None
        ):
            return set()

        visible_pids = set()

        def _enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            normalized_window_pid = AutoRejoinMonitor._normalize_int(
                window_pid,
                default=0,
                minimum=0,
            )
            if normalized_window_pid not in normalized_pid_values:
                return True
            title = ""
            try:
                title = str(win32gui.GetWindowText(hwnd) or "").strip()
            except Exception:
                title = ""
            if title or win32gui.GetClassName(hwnd) == "WINDOWSCLIENT":
                visible_pids.add(normalized_window_pid)
                if len(visible_pids) >= len(normalized_pid_values):
                    return False
            return True

        try:
            win32gui.EnumWindows(_enum_handler, None)
        except Exception:
            return set()
        return visible_pids
