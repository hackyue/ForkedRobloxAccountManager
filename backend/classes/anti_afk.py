import os
import sys
import time
import platform
import threading
import re
import ctypes
from typing import Dict, List, Set, Any, Optional, Tuple, Callable

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = win32con = win32process = None


ROBLOX_CLIENT_EXECUTABLES: Set[str] = {
    "robloxplayerbeta.exe",
    "robloxplayer.exe",
}

BOOTSTRAPPER_EXECUTABLES: Set[str] = {
    "robloxplayerlauncher.exe",
    "bloxstrap.exe",
    "fishstrap.exe",
    "voidstrap.exe",
    "froststrap.exe",
    "exploitstrap.exe",
}

ALL_TARGET_EXECUTABLES: Set[str] = ROBLOX_CLIENT_EXECUTABLES | BOOTSTRAPPER_EXECUTABLES


class AntiAfkManager:
    """Manages periodic background input injection into active Roblox client windows to prevent idle timeouts."""

    TARGET_EXECUTABLES: Set[str] = ROBLOX_CLIENT_EXECUTABLES
    DEFAULT_INTERVAL_MINUTES: int = 10
    MIN_INTERVAL_MINUTES: int = 1
    MAX_INTERVAL_MINUTES: int = 19
    DEFAULT_KEY_NAME: str = "M1"
    LOOP_SLEEP_SECONDS: float = 2.0
    INPUT_PRESS_DURATION: float = 1.0
    PID_CACHE_TTL_SECONDS: float = 2.0
    STAGGER_DELAY_SECONDS: float = 0.08

    MOUSE_ALIASES: Dict[str, str] = {
        "m1": "M1",
        "mouse1": "M1",
        "left click": "M1",
        "button 1": "M1",
        "m2": "M2",
        "mouse2": "M2",
        "right click": "M2",
        "button 3": "M2",
        "m3": "M3",
        "mouse3": "M3",
        "middle click": "M3",
        "button 2": "M3",
    }

    KEY_ALIASES: Dict[str, str] = {
        "space": "Space",
        "spacebar": "Space",
        "up": "Up Arrow",
        "up arrow": "Up Arrow",
        "down": "Down Arrow",
        "down arrow": "Down Arrow",
        "left": "Left Arrow",
        "left arrow": "Left Arrow",
        "right": "Right Arrow",
        "right arrow": "Right Arrow",
        "w": "W",
        "a": "A",
        "s": "S",
        "d": "D",
        "e": "E",
        "f": "F",
        "shift": "Shift",
        "control": "Control",
        "ctrl": "Control",
    }

    def __init__(
        self,
        settings_getter=None,
        accounts_getter=None,
        launch_info_getter=None,
        headless_manager=None,
        auto_rejoin_monitor=None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.settings_getter = settings_getter
        self.accounts_getter = accounts_getter
        self.launch_info_getter = launch_info_getter
        self.headless_manager = headless_manager
        self.auto_rejoin_monitor = auto_rejoin_monitor
        self.log_callback = log_callback
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.running: bool = False
        self.last_run_ts: Optional[float] = None
        self.next_run_ts: Optional[float] = None
        self.last_pass_summary: Optional[Dict[str, int]] = None
        self.in_progress: bool = False
        self._pids_cache: Set[int] = set()
        self._pids_cache_ts: float = 0.0
        self._suppressed_hwnds: Dict[int, float] = {}
        self._overlay_manager: Optional[_AntiAfkOverlayManager] = None

    def _log(self, message: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(message)
            except Exception:
                pass

    def get_settings(self) -> Dict[str, Any]:
        if callable(self.settings_getter):
            try:
                res = self.settings_getter()
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {}

    def get_accounts(self) -> List[Dict[str, Any]]:
        if callable(self.accounts_getter):
            try:
                res = self.accounts_getter()
                if isinstance(res, list):
                    return res
            except Exception:
                pass
        return []

    def is_enabled(self) -> bool:
        settings = self.get_settings()
        if bool(settings.get("antiAfkEnabled", False) or settings.get("anti_afk_enabled", False)):
            return True
        accounts = self.get_accounts()
        return any(bool(acc.get("anti_afk_enabled", False)) for acc in accounts if isinstance(acc, dict))

    def is_overlay_enabled(self) -> bool:
        settings = self.get_settings()
        if not self.is_enabled():
            return False
        return bool(settings.get("antiAfkShowNextLabel", False))

    def is_window_afk_enabled(self, hwnd: int, pid: int, title: str) -> bool:
        settings = self.get_settings()
        if bool(settings.get("antiAfkEnabled", False) or settings.get("anti_afk_enabled", False)):
            return True

        accounts = self.get_accounts()
        afk_usernames = {
            str(acc.get("username", "")).lower()
            for acc in accounts
            if isinstance(acc, dict) and bool(acc.get("anti_afk_enabled", False)) and acc.get("username")
        }
        if not afk_usernames:
            return False

        title_lower = str(title or "").lower()
        for uname in afk_usernames:
            if uname in title_lower:
                return True

        if callable(self.launch_info_getter):
            try:
                info_map = self.launch_info_getter()
                if isinstance(info_map, dict):
                    for uname, info in info_map.items():
                        if str(uname).lower() in afk_usernames:
                            if isinstance(info, dict) and info.get("pid") == pid:
                                return True
            except Exception:
                pass

        if self.auto_rejoin_monitor is not None:
            try:
                sessions = getattr(self.auto_rejoin_monitor, "active_sessions", None)
                lock = getattr(self.auto_rejoin_monitor, "_lock", None)
                if isinstance(sessions, dict):
                    if lock is not None:
                        with lock:
                            for uname, session in sessions.items():
                                if str(uname).lower() in afk_usernames:
                                    if getattr(session, "pid", None) == pid:
                                        return True
                    else:
                        for uname, session in sessions.items():
                            if str(uname).lower() in afk_usernames:
                                if getattr(session, "pid", None) == pid:
                                    return True
            except Exception:
                pass

        try:
            import psutil
            proc = psutil.Process(pid)
            cmdline_str = " ".join(proc.cmdline()).lower()
            for uname in afk_usernames:
                if uname in cmdline_str:
                    return True
        except Exception:
            pass

        return False

    def get_interval_minutes(self) -> int:
        settings = self.get_settings()
        raw_val = settings.get("antiAfkIntervalMinutes", settings.get("anti_afk_interval_minutes", self.DEFAULT_INTERVAL_MINUTES))
        try:
            val = int(raw_val or self.DEFAULT_INTERVAL_MINUTES)
            return max(self.MIN_INTERVAL_MINUTES, min(self.MAX_INTERVAL_MINUTES, val))
        except (TypeError, ValueError):
            return self.DEFAULT_INTERVAL_MINUTES

    def get_press_duration(self) -> float:
        settings = self.get_settings()
        raw_val = settings.get("antiAfkDuration", settings.get("anti_afk_duration", self.INPUT_PRESS_DURATION))
        try:
            val = float(raw_val if raw_val is not None else self.INPUT_PRESS_DURATION)
            return max(0.05, min(10.0, val))
        except (TypeError, ValueError):
            return float(self.INPUT_PRESS_DURATION)

    def get_key_name(self) -> str:
        settings = self.get_settings()
        raw_name = str(settings.get("antiAfkKeyName", settings.get("anti_afk_key_name", self.DEFAULT_KEY_NAME)) or self.DEFAULT_KEY_NAME).strip()
        if not raw_name:
            return self.DEFAULT_KEY_NAME

        lookup = raw_name.replace("_", " ").casefold()
        if lookup in self.MOUSE_ALIASES:
            return self.MOUSE_ALIASES[lookup]
        if lookup in self.KEY_ALIASES:
            return self.KEY_ALIASES[lookup]

        if len(raw_name) == 1:
            return raw_name.upper()

        fn_match = re.fullmatch(r"(?i)f([1-9]|1[0-9]|2[0-4])", raw_name)
        if fn_match:
            return f"F{fn_match.group(1)}"

        return raw_name

    def get_key_code(self, key_name: str) -> int:
        if key_name in {"M1", "M2", "M3"}:
            return 0

        special = {
            "Space": 0x20,
            "Left Arrow": 0x25,
            "Up Arrow": 0x26,
            "Right Arrow": 0x27,
            "Down Arrow": 0x28,
            "Shift": 0x10,
            "Control": 0x11,
        }
        if key_name in special:
            return special[key_name]

        if len(key_name) == 1:
            ch = key_name.upper()
            if "A" <= ch <= "Z" or "0" <= ch <= "9":
                return ord(ch)

        fn_match = re.fullmatch(r"(?i)f([1-9]|1[0-9]|2[0-4])", key_name)
        if fn_match:
            return 0x70 + int(fn_match.group(1)) - 1

        return 0x20

    def _is_bootstrapper_window(self, hwnd: int, proc_name: str) -> bool:
        """Detect bootstrapper/launcher windows that should not receive anti-AFK input."""
        name_lower = str(proc_name or "").lower()
        if name_lower in BOOTSTRAPPER_EXECUTABLES:
            return True
        for token in ("bloxstrap", "fishstrap", "voidstrap", "froststrap", "exploitstrap", "launcher", "installer", "crashhandler"):
            if token in name_lower:
                return True
        if win32gui:
            try:
                title = (win32gui.GetWindowText(hwnd) or "").lower()
                cls_name = (win32gui.GetClassName(hwnd) or "").lower()
                for kw in ("bloxstrap", "fishstrap", "voidstrap", "froststrap", "exploitstrap", "launcher", "installer", "crash handler"):
                    if kw in title or kw in cls_name:
                        return True
            except Exception:
                pass
        return False

    def _is_session_mid_rejoin(self, pid: int, title: str) -> bool:
        """Check if the auto-rejoin monitor considers this window's session to be mid-rejoin."""
        monitor = self.auto_rejoin_monitor
        if monitor is None:
            return False
        try:
            lock = getattr(monitor, "_lock", None)
            sessions = getattr(monitor, "active_sessions", None)
            if lock is None or sessions is None:
                return False
            with lock:
                for _uname, session in sessions.items():
                    if getattr(session, "rejoin_in_progress", False) or getattr(session, "intentionally_stopped", False):
                        session_pid = int(getattr(session, "pid", 0) or 0)
                        if session_pid == pid:
                            return True
                        session_username = str(getattr(session, "username", "") or "").lower()
                        if session_username and session_username in str(title or "").lower():
                            return True
        except Exception:
            pass
        return False

    def _is_process_alive(self, pid: int) -> bool:
        """Quick check whether a PID still exists."""
        if pid <= 0:
            return False
        try:
            import psutil
            return psutil.pid_exists(pid)
        except Exception:
            return True

    def suppress_hwnd(self, hwnd: int, duration_seconds: float = 30.0) -> None:
        """Temporarily suppress anti-AFK input for a specific window handle."""
        with self.lock:
            self._suppressed_hwnds[hwnd] = time.time() + duration_seconds

    def unsuppress_hwnd(self, hwnd: int) -> None:
        """Remove a suppression on a specific window handle."""
        with self.lock:
            self._suppressed_hwnds.pop(hwnd, None)

    def _is_hwnd_suppressed(self, hwnd: int) -> bool:
        """Check if a window handle is temporarily suppressed."""
        with self.lock:
            expires_at = self._suppressed_hwnds.get(hwnd)
            if expires_at is None:
                return False
            if time.time() >= expires_at:
                self._suppressed_hwnds.pop(hwnd, None)
                return False
            return True

    def _cleanup_suppressed(self) -> None:
        """Remove expired suppressions."""
        now = time.time()
        with self.lock:
            expired = [h for h, t in self._suppressed_hwnds.items() if now >= t]
            for h in expired:
                self._suppressed_hwnds.pop(h, None)

    def get_roblox_windows(self, include_hidden: bool = False) -> List[Tuple[int, int, str]]:
        if platform.system() != "Windows" or not win32gui or not win32process:
            return []

        now = time.time()
        pids: Set[int] = set()
        pid_names: Dict[int, str] = {}

        if (now - self._pids_cache_ts) < self.PID_CACHE_TTL_SECONDS and self._pids_cache:
            pids = set(self._pids_cache)
        else:
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        name = str(proc.info.get('name') or '').lower()
                        if name in self.TARGET_EXECUTABLES:
                            p = int(proc.info['pid'])
                            pids.add(p)
                            pid_names[p] = name
                    except Exception:
                        continue
                self._pids_cache = set(pids)
                self._pids_cache_ts = now
            except Exception:
                pass

        if not pids:
            return []

        headless_hidden_hwnds: Set[int] = set()
        if self.headless_manager is not None:
            try:
                hidden = getattr(self.headless_manager, "hidden_hwnds", None)
                if isinstance(hidden, set):
                    headless_hidden_hwnds = set(hidden)
            except Exception:
                pass

        candidates_by_pid: Dict[int, List[Tuple[int, int, str, str, int, int, bool]]] = {}

        def enum_win_cb(hwnd, _):
            if not win32gui.IsWindow(hwnd):
                return True
            try:
                if win32gui.GetParent(hwnd) != 0:
                    return True

                rect = win32gui.GetWindowRect(hwnd)
                width = int(rect[2] - rect[0])
                height = int(rect[3] - rect[1])
                if width < 100 or height < 100:
                    return True

                is_vis = bool(win32gui.IsWindowVisible(hwnd))
                is_headless = hwnd in headless_hidden_hwnds

                if not is_vis and not is_headless and not include_hidden:
                    return True

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in pids:
                    return True

                proc_name = pid_names.get(pid, "")
                if not proc_name:
                    try:
                        import psutil
                        proc_name = psutil.Process(pid).name().lower()
                    except Exception:
                        proc_name = ""

                if proc_name in BOOTSTRAPPER_EXECUTABLES or self._is_bootstrapper_window(hwnd, proc_name):
                    return True

                raw_title = str(win32gui.GetWindowText(hwnd) or "").strip()
                cls = str(win32gui.GetClassName(hwnd) or "").strip()

                is_roblox_window = (
                    cls in ("WINDOWSCLIENT", "RobloxPlayerBeta", "RobloxPlayer", "ApplicationFrameWindow", "Win32Window0")
                    or "roblox" in raw_title.lower()
                    or "roblox" in cls.lower()
                )

                if is_roblox_window:
                    title = raw_title if raw_title else "Roblox"
                    candidates_by_pid.setdefault(pid, []).append((hwnd, pid, title, cls, width, height, is_vis))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_win_cb, None)
        except Exception:
            pass

        windows: List[Tuple[int, int, str]] = []
        for pid, candidate_list in candidates_by_pid.items():
            if not candidate_list:
                continue

            def candidate_score(c):
                chwnd, _cpid, ctitle, ccls, cw, ch, cvis = c
                score = 0
                if ccls == "WINDOWSCLIENT":
                    score += 1000
                elif ccls in ("RobloxPlayerBeta", "RobloxPlayer", "ApplicationFrameWindow", "Win32Window0"):
                    score += 500
                if ctitle.lower().startswith("roblox"):
                    score += 200
                elif "roblox" in ctitle.lower():
                    score += 100
                if cvis or chwnd in headless_hidden_hwnds:
                    score += 150
                score += min(100, (cw * ch) // 10000)
                return score

            best = max(candidate_list, key=candidate_score)
            windows.append((best[0], best[1], best[2]))

        windows.sort(key=lambda item: item[0])
        return windows

    def _activate_window(self, hwnd: int) -> bool:
        if platform.system() != "Windows" or not win32gui or not win32process:
            return False
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not win32gui.IsWindow(hwnd):
                return False

            if user32.IsIconic(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return False

            if user32.GetForegroundWindow() == hwnd:
                return True

            our_tid = kernel32.GetCurrentThreadId()
            fg_hwnd = user32.GetForegroundWindow()
            fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0
            target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

            attached_fg = False
            attached_target = False
            if fg_tid and fg_tid != our_tid:
                try:
                    attached_fg = bool(user32.AttachThreadInput(our_tid, fg_tid, True))
                except Exception:
                    attached_fg = False

            if target_tid and target_tid != our_tid:
                try:
                    attached_target = bool(user32.AttachThreadInput(our_tid, target_tid, True))
                except Exception:
                    attached_target = False

            try:
                user32.LockSetForegroundWindow(2)
            except Exception:
                pass

            try:
                user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)

            if user32.GetForegroundWindow() != hwnd:
                try:
                    user32.keybd_event(0x12, 0, 0, 0)
                    user32.keybd_event(0x12, 0, 2, 0)
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            if attached_target:
                try:
                    user32.AttachThreadInput(our_tid, target_tid, False)
                except Exception:
                    pass

            if attached_fg:
                try:
                    user32.AttachThreadInput(our_tid, fg_tid, False)
                except Exception:
                    pass

            return user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _send_hardware_key(self, code: int, scan_code: int, is_extended: bool, duration: float = 0.0) -> None:
        user32 = ctypes.windll.user32
        ULONG_PTR = ctypes.c_ulonglong

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("union", INPUT_UNION),
            ]

        press_time = duration if duration > 0 else self.get_press_duration()

        flags_down = 0x0008 if scan_code > 0 else 0
        if is_extended:
            flags_down |= 0x0001
        flags_up = flags_down | 0x0002

        inp_down = INPUT()
        inp_down.type = 1
        inp_down.union.ki.wVk = 0 if scan_code > 0 else code
        inp_down.union.ki.wScan = scan_code
        inp_down.union.ki.dwFlags = flags_down

        inp_up = INPUT()
        inp_up.type = 1
        inp_up.union.ki.wVk = 0 if scan_code > 0 else code
        inp_up.union.ki.wScan = scan_code
        inp_up.union.ki.dwFlags = flags_up

        user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        try:
            user32.keybd_event(code, scan_code, 0 if not is_extended else 1, 0)
        except Exception:
            pass

        time.sleep(press_time)

        user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
        try:
            user32.keybd_event(code, scan_code, 2 if not is_extended else 3, 0)
        except Exception:
            pass

    def _send_hardware_mouse(self, key_name: str, duration: float = 0.0) -> None:
        user32 = ctypes.windll.user32
        ULONG_PTR = ctypes.c_ulonglong

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [
                ("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [
                ("mi", MOUSEINPUT),
                ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_ulong),
                ("union", INPUT_UNION),
            ]

        press_time = duration if duration > 0 else self.get_press_duration()
        down_flag = 0x0002 if key_name == "M1" else (0x0008 if key_name == "M2" else 0x0020)
        up_flag = 0x0004 if key_name == "M1" else (0x0010 if key_name == "M2" else 0x0040)

        inp_down = INPUT()
        inp_down.type = 0
        inp_down.union.mi.dwFlags = down_flag

        inp_up = INPUT()
        inp_up.type = 0
        inp_up.union.mi.dwFlags = up_flag

        user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        time.sleep(press_time)
        user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))

    def post_window_input(self, hwnd: int, key_name: str, restore_focus: bool = True) -> bool:
        if platform.system() != "Windows" or not win32gui or not win32con:
            return False
        try:
            if not win32gui.IsWindow(hwnd):
                return False

            rect = win32gui.GetClientRect(hwnd)
            w_raw = int(rect[2] - rect[0])
            h_raw = int(rect[3] - rect[1])
            width = w_raw if w_raw > 0 else 800
            height = h_raw if h_raw > 0 else 600

            x_val = max(0, min(width - 1, int(width / 2)))
            y_val = max(0, min(height - 1, int(height / 2)))
            lparam = (y_val << 16) | x_val

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            is_headless = False
            if self.headless_manager is not None:
                try:
                    hidden = getattr(self.headless_manager, "hidden_hwnds", None)
                    if isinstance(hidden, set) and hwnd in hidden:
                        is_headless = True
                except Exception:
                    pass

            prev_fg = 0
            try:
                prev_fg = user32.GetForegroundWindow()
            except Exception:
                prev_fg = 0

            is_visible = bool(win32gui.IsWindowVisible(hwnd))
            was_already_foreground = (prev_fg == hwnd)
            if not is_headless and is_visible and not user32.IsIconic(hwnd) and not was_already_foreground:
                self._activate_window(hwnd)
                time.sleep(0.04)

            is_foreground = False
            try:
                is_foreground = (user32.GetForegroundWindow() == hwnd)
            except Exception:
                pass

            duration = self.get_press_duration()

            if key_name in {"M1", "M2", "M3"}:
                mouse_map = {
                    "M1": (0x0201, 0x0202, 0x0001),
                    "M2": (0x0204, 0x0205, 0x0002),
                    "M3": (0x0207, 0x0208, 0x0010),
                }
                msg_down, msg_up, wparam = mouse_map[key_name]

                if is_foreground:
                    try:
                        self._send_hardware_mouse(key_name, duration)
                    except Exception:
                        pass

                win32gui.PostMessage(hwnd, getattr(win32con, "WM_MOUSEMOVE", 0x0200), 0, lparam)
                win32gui.PostMessage(hwnd, msg_down, wparam, lparam)
                if key_name == "M2":
                    nudge_lparam = (y_val << 16) | ((x_val + 4) & 0xFFFF)
                    win32gui.PostMessage(hwnd, getattr(win32con, "WM_MOUSEMOVE", 0x0200), wparam, nudge_lparam)
                time.sleep(duration)
                win32gui.PostMessage(hwnd, msg_up, 0, lparam)
            else:
                code = self.get_key_code(key_name)
                if code > 0:
                    scan_code = user32.MapVirtualKeyW(code, 0)
                    is_extended = code in (0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22)

                    lparam_down = 1 | (scan_code << 16)
                    lparam_up = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
                    if is_extended:
                        lparam_down |= (1 << 24)
                        lparam_up |= (1 << 24)

                    our_tid = kernel32.GetCurrentThreadId()
                    target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
                    attached = False
                    if target_tid and target_tid != our_tid:
                        try:
                            attached = bool(user32.AttachThreadInput(our_tid, target_tid, True))
                        except Exception:
                            attached = False

                    try:
                        win32gui.PostMessage(hwnd, 0x0006, 1, 0)
                        win32gui.PostMessage(hwnd, 0x0007, 0, 0)
                        win32gui.PostMessage(hwnd, getattr(win32con, "WM_KEYDOWN", 0x0100), code, lparam_down)

                        char_code = user32.MapVirtualKeyW(code, 2)
                        if char_code > 0:
                            win32gui.PostMessage(hwnd, 0x0102, char_code, lparam_down)

                        if is_foreground:
                            try:
                                self._send_hardware_key(code, scan_code, is_extended, duration)
                            except Exception:
                                time.sleep(duration)
                        else:
                            time.sleep(duration)

                        win32gui.PostMessage(hwnd, getattr(win32con, "WM_KEYUP", 0x0101), code, lparam_up)
                    finally:
                        if attached:
                            try:
                                user32.AttachThreadInput(our_tid, target_tid, False)
                            except Exception:
                                pass

            if restore_focus and prev_fg and prev_fg != hwnd and not was_already_foreground:
                try:
                    if win32gui.IsWindow(prev_fg):
                        self._activate_window(prev_fg)
                except Exception:
                    pass

            return True
        except Exception as e:
            self._log(f"AntiAFK PostMessage error for hwnd {hwnd}: {e}")

        return False

    def trigger_pass(self) -> Dict[str, Any]:
        with self.lock:
            if self.in_progress:
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "pass_already_in_progress",
                    "total_windows": 0,
                    "successful_windows": 0,
                    "failed_windows": 0,
                    "key_used": self.get_key_name(),
                    "timestamp": time.time(),
                }
            self.in_progress = True

        try:
            self._cleanup_suppressed()
            windows = self.get_roblox_windows()
            key_name = self.get_key_name()
            total = len(windows)
            success = 0
            failed = 0
            skipped = 0

            original_fg = 0
            if platform.system() == "Windows":
                try:
                    original_fg = ctypes.windll.user32.GetForegroundWindow()
                except Exception:
                    original_fg = 0

            for i, (hwnd, pid, title) in enumerate(windows):
                if self._stop_event.is_set():
                    break

                if not self.is_window_afk_enabled(hwnd, pid, title):
                    skipped += 1
                    continue

                if self._is_hwnd_suppressed(hwnd):
                    skipped += 1
                    continue

                if self._is_session_mid_rejoin(pid, title):
                    skipped += 1
                    continue

                if not self._is_process_alive(pid):
                    skipped += 1
                    continue

                try:
                    if not win32gui or not win32gui.IsWindow(hwnd):
                        skipped += 1
                        continue
                except Exception:
                    skipped += 1
                    continue

                if self.post_window_input(hwnd, key_name, restore_focus=False):
                    success += 1
                else:
                    failed += 1

                if i < len(windows) - 1:
                    time.sleep(self.STAGGER_DELAY_SECONDS)

            if original_fg and platform.system() == "Windows":
                try:
                    if win32gui and win32gui.IsWindow(original_fg) and ctypes.windll.user32.GetForegroundWindow() != original_fg:
                        self._activate_window(original_fg)
                except Exception:
                    pass

            now = time.time()

            with self.lock:
                self.last_run_ts = now
                self.last_pass_summary = {
                    "total_windows": total,
                    "successful_windows": success,
                    "failed_windows": failed,
                    "skipped_windows": skipped,
                }
                interval_sec = self.get_interval_minutes() * 60
                self.next_run_ts = now + interval_sec

            return {
                "success": True,
                "total_windows": total,
                "successful_windows": success,
                "failed_windows": failed,
                "skipped_windows": skipped,
                "key_used": key_name,
                "timestamp": now,
            }
        finally:
            with self.lock:
                self.in_progress = False

    def start_loop(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self._stop_event.clear()
            self.worker_thread = threading.Thread(target=self._loop, daemon=True, name="anti-afk-worker")
            self.worker_thread.start()
            self._sync_overlay()

    def stop_loop(self, timeout: float = 5.0):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self._stop_event.set()
            thread = self.worker_thread
            self.worker_thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))

        self._destroy_overlay()

    def sync_overlay(self) -> None:
        self._sync_overlay()

    def _sync_overlay(self) -> None:
        """Start or stop the overlay manager based on the current setting."""
        if platform.system() != "Windows":
            return
        try:
            should_show = self.is_overlay_enabled()
            if should_show:
                if self._overlay_manager is None:
                    self._overlay_manager = _AntiAfkOverlayManager(self)
                    self._overlay_manager.start()
            else:
                self._destroy_overlay()
        except Exception as e:
            self._log(f"AntiAFK overlay sync error: {e}")

    def _destroy_overlay(self) -> None:
        """Tear down the overlay manager."""
        mgr = self._overlay_manager
        self._overlay_manager = None
        if mgr is not None:
            try:
                mgr.stop()
            except Exception:
                pass

    def _loop(self):
        overlay_check_counter = 0
        while not self._stop_event.is_set():
            try:
                if self.is_enabled():
                    now = time.time()
                    with self.lock:
                        interval_sec = self.get_interval_minutes() * 60
                        if self.next_run_ts is None:
                            self.next_run_ts = now + interval_sec
                        due = now >= self.next_run_ts

                    if due:
                        self.trigger_pass()

                overlay_check_counter += 1
                if overlay_check_counter >= 3:
                    overlay_check_counter = 0
                    self._sync_overlay()

                self._stop_event.wait(self.LOOP_SLEEP_SECONDS)
            except Exception as e:
                self._log(f"AntiAFK worker error: {e}")
                self._stop_event.wait(5.0)

    def get_status(self) -> Dict[str, Any]:
        windows = self.get_roblox_windows()
        key_name = self.get_key_name()
        interval_min = self.get_interval_minutes()
        enabled = self.is_enabled()
        now = time.time()

        with self.lock:
            last_run = self.last_run_ts
            next_run = self.next_run_ts
            summary = dict(self.last_pass_summary) if self.last_pass_summary else None
            currently_in_progress = self.in_progress

        remaining_sec = 0
        if enabled and next_run:
            remaining_sec = max(0, int(next_run - now))

        headless_active = False
        if self.headless_manager is not None:
            try:
                headless_active = bool(getattr(self.headless_manager, "watchdog_running", False))
            except Exception:
                pass

        return {
            "success": True,
            "enabled": enabled,
            "interval_minutes": interval_min,
            "key_name": key_name,
            "key_code": self.get_key_code(key_name),
            "duration_seconds": self.get_press_duration(),
            "roblox_instance_count": len(windows),
            "last_run_ts": last_run,
            "next_run_ts": next_run,
            "seconds_until_next_run": remaining_sec,
            "last_pass_summary": summary,
            "in_progress": currently_in_progress,
            "headless_mode_active": headless_active,
            "overlay_active": self._overlay_manager is not None,
        }


class _AntiAfkOverlayManager:
    """Creates and manages transparent, click-through overlay windows that display
    an anti-AFK countdown timer on the top-right of each Roblox client window."""

    OVERLAY_WIDTH: int = 130
    OVERLAY_HEIGHT: int = 24
    OVERLAY_MARGIN_X: int = 10
    OVERLAY_MARGIN_Y: int = 10
    UPDATE_INTERVAL_SECONDS: float = 0.5
    BG_COLOR_RGB: Tuple[int, int, int] = (30, 30, 40)
    TEXT_COLOR_GDI: int = 0x0070E870
    PULSE_TEXT_COLOR_GDI: int = 0x0050C0E0
    FONT_SIZE: int = 13
    FONT_NAME: str = "Segoe UI"
    WNDCLASS_NAME: str = "FRAMAntiAfkOverlay"
    WINDOW_ALPHA: int = 200

    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOPMOST = 0x00000008
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000

    LWA_ALPHA = 0x02
    HWND_TOPMOST = -1
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040

    def __init__(self, afk_manager: "AntiAfkManager"):
        self.afk_manager = afk_manager
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._overlay_hwnds: Dict[int, int] = {}
        self._wndclass_atom = 0
        self._hinstance = None
        self._bg_brush = None
        self._current_text: str = ""
        self._current_is_pulse: bool = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="anti-afk-overlay")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

    def _run(self) -> None:
        if platform.system() != "Windows":
            return

        try:
            import ctypes.wintypes as wintypes

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            kernel32 = ctypes.windll.kernel32
            self._hinstance = kernel32.GetModuleHandleW(None)

            user32.DefWindowProcW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.DefWindowProcW.restype = wintypes.LPARAM

            user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
            user32.RegisterClassExW.restype = wintypes.ATOM

            user32.UnregisterClassW.argtypes = [ctypes.c_wchar_p, wintypes.HINSTANCE]
            user32.UnregisterClassW.restype = wintypes.BOOL

            user32.CreateWindowExW.argtypes = [
                wintypes.DWORD,
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                wintypes.DWORD,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HWND,
                wintypes.HMENU,
                wintypes.HINSTANCE,
                ctypes.c_void_p,
            ]
            user32.CreateWindowExW.restype = wintypes.HWND

            user32.DestroyWindow.argtypes = [wintypes.HWND]
            user32.DestroyWindow.restype = wintypes.BOOL

            user32.IsWindow.argtypes = [wintypes.HWND]
            user32.IsWindow.restype = wintypes.BOOL

            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL

            user32.SetLayeredWindowAttributes.argtypes = [
                wintypes.HWND,
                wintypes.COLORREF,
                wintypes.BYTE,
                wintypes.DWORD,
            ]
            user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

            user32.InvalidateRect.argtypes = [
                wintypes.HWND,
                ctypes.c_void_p,
                wintypes.BOOL,
            ]
            user32.InvalidateRect.restype = wintypes.BOOL

            user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
            user32.BeginPaint.restype = wintypes.HDC

            user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
            user32.EndPaint.restype = wintypes.BOOL

            user32.FillRect.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.HBRUSH]
            user32.FillRect.restype = ctypes.c_int

            user32.DrawTextW.argtypes = [
                wintypes.HDC,
                ctypes.c_wchar_p,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.UINT,
            ]
            user32.DrawTextW.restype = ctypes.c_int

            gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
            gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

            gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
            gdi32.DeleteObject.restype = wintypes.BOOL

            gdi32.CreateFontW.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_wchar_p,
            ]
            gdi32.CreateFontW.restype = wintypes.HFONT

            gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
            gdi32.SelectObject.restype = wintypes.HGDIOBJ

            gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
            gdi32.SetTextColor.restype = wintypes.COLORREF

            gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
            gdi32.SetBkMode.restype = ctypes.c_int

            WNDPROC = ctypes.WINFUNCTYPE(
                wintypes.LPARAM,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            manager_ref = self

            def wnd_proc(hwnd, msg, wparam, lparam):
                try:
                    if msg == 0x000F:
                        manager_ref._on_paint(hwnd, user32, gdi32)
                        return 0
                    if msg == 0x0014:
                        return 1
                    if msg == 0x0010:
                        user32.DestroyWindow(hwnd)
                        return 0
                    if msg == 0x0002:
                        return 0
                    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
                except Exception:
                    return 0

            self._wnd_proc_ref = WNDPROC(wnd_proc)

            class WNDCLASSEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HCURSOR),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", ctypes.c_wchar_p),
                    ("lpszClassName", ctypes.c_wchar_p),
                    ("hIconSm", wintypes.HICON),
                ]

            bg_r, bg_g, bg_b = self.BG_COLOR_RGB
            bg_colorref = bg_r | (bg_g << 8) | (bg_b << 16)
            self._bg_brush = gdi32.CreateSolidBrush(bg_colorref)

            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.style = 0
            wc.lpfnWndProc = self._wnd_proc_ref
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = self._hinstance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = self._bg_brush
            wc.lpszMenuName = None
            wc.lpszClassName = self.WNDCLASS_NAME
            wc.hIconSm = None

            self._wndclass_atom = user32.RegisterClassExW(ctypes.byref(wc))
            if not self._wndclass_atom:
                if kernel32.GetLastError() != 1410:
                    if self._bg_brush:
                        gdi32.DeleteObject(self._bg_brush)
                        self._bg_brush = None
                    return

            while not self._stop_event.is_set():
                try:
                    self._update_overlays(user32, gdi32)
                except Exception:
                    pass

                msg = ctypes.wintypes.MSG()
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                self._stop_event.wait(self.UPDATE_INTERVAL_SECONDS)

        except Exception as e:
            try:
                self.afk_manager._log(f"AntiAFK overlay thread error: {e}")
            except Exception:
                pass
        finally:
            self._cleanup_all()

    def _on_paint(self, hwnd, user32, gdi32) -> None:
        try:
            import ctypes.wintypes as wintypes

            class PAINTSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hdc", wintypes.HDC),
                    ("fErase", wintypes.BOOL),
                    ("rcPaint_left", ctypes.c_long),
                    ("rcPaint_top", ctypes.c_long),
                    ("rcPaint_right", ctypes.c_long),
                    ("rcPaint_bottom", ctypes.c_long),
                    ("fRestore", wintypes.BOOL),
                    ("fIncUpdate", wintypes.BOOL),
                    ("rgbReserved", ctypes.c_byte * 32),
                ]

            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            if not hdc:
                return

            bg_r, bg_g, bg_b = self.BG_COLOR_RGB
            bg_colorref = bg_r | (bg_g << 8) | (bg_b << 16)
            bg_brush = gdi32.CreateSolidBrush(bg_colorref)
            rc = wintypes.RECT(0, 0, self.OVERLAY_WIDTH, self.OVERLAY_HEIGHT)
            user32.FillRect(hdc, ctypes.byref(rc), bg_brush)
            gdi32.DeleteObject(bg_brush)

            hfont = gdi32.CreateFontW(
                self.FONT_SIZE, 0, 0, 0,
                700,
                0, 0, 0,
                1,
                0, 0, 5,
                0,
                self.FONT_NAME,
            )
            old_font = gdi32.SelectObject(hdc, hfont)

            text_color = self.PULSE_TEXT_COLOR_GDI if self._current_is_pulse else self.TEXT_COLOR_GDI
            gdi32.SetTextColor(hdc, text_color)
            gdi32.SetBkMode(hdc, 1)

            text_rc = wintypes.RECT(4, 0, self.OVERLAY_WIDTH - 4, self.OVERLAY_HEIGHT)
            user32.DrawTextW(hdc, self._current_text, -1, ctypes.byref(text_rc), 0x0025)

            gdi32.SelectObject(hdc, old_font)
            gdi32.DeleteObject(hfont)

            user32.EndPaint(hwnd, ctypes.byref(ps))
        except Exception:
            pass

    def _update_overlays(self, user32, gdi32) -> None:
        if not self.afk_manager.is_overlay_enabled():
            self._cleanup_all()
            return

        try:
            roblox_windows = self.afk_manager.get_roblox_windows(include_hidden=False)
            roblox_windows = [
                w for w in roblox_windows
                if self.afk_manager.is_window_afk_enabled(w[0], w[1], w[2])
            ]
        except Exception:
            roblox_windows = []

        target_hwnds = {hwnd for hwnd, _, _ in roblox_windows}

        stale_targets = set(self._overlay_hwnds.keys()) - target_hwnds
        for target_hwnd in stale_targets:
            overlay_hwnd = self._overlay_hwnds.pop(target_hwnd, None)
            if overlay_hwnd:
                try:
                    user32.DestroyWindow(overlay_hwnd)
                except Exception:
                    pass

        now = time.time()
        with self.afk_manager.lock:
            next_run = self.afk_manager.next_run_ts
            is_in_progress = self.afk_manager.in_progress

        remaining_sec = max(0, int((next_run or now) - now))
        minutes = remaining_sec // 60
        seconds = remaining_sec % 60

        if is_in_progress:
            new_text = "\u26a1 Pulsing..."
        else:
            new_text = f"\u23f1 {minutes}:{seconds:02d}"

        text_changed = (new_text != self._current_text) or (is_in_progress != self._current_is_pulse)
        self._current_text = new_text
        self._current_is_pulse = is_in_progress

        for target_hwnd, _pid, _title in roblox_windows:
            try:
                if not win32gui or not win32gui.IsWindow(target_hwnd):
                    continue
                if not win32gui.IsWindowVisible(target_hwnd):
                    overlay = self._overlay_hwnds.pop(target_hwnd, None)
                    if overlay:
                        try:
                            user32.DestroyWindow(overlay)
                        except Exception:
                            pass
                    continue

                rect = win32gui.GetWindowRect(target_hwnd)
                win_left, win_top, win_right, win_bottom = rect
                win_width = win_right - win_left
                if win_width < 100:
                    continue

                overlay_x = win_right - self.OVERLAY_WIDTH - self.OVERLAY_MARGIN_X
                overlay_y = win_top + self.OVERLAY_MARGIN_Y

                overlay_hwnd = self._overlay_hwnds.get(target_hwnd)
                if overlay_hwnd and not user32.IsWindow(overlay_hwnd):
                    self._overlay_hwnds.pop(target_hwnd, None)
                    overlay_hwnd = None

                if overlay_hwnd is None:
                    ex_style = (
                        self.WS_EX_LAYERED
                        | self.WS_EX_TRANSPARENT
                        | self.WS_EX_TOPMOST
                        | self.WS_EX_TOOLWINDOW
                        | self.WS_EX_NOACTIVATE
                    )
                    style = self.WS_POPUP | self.WS_VISIBLE

                    overlay_hwnd = user32.CreateWindowExW(
                        ex_style,
                        self.WNDCLASS_NAME,
                        "",
                        style,
                        overlay_x, overlay_y,
                        self.OVERLAY_WIDTH, self.OVERLAY_HEIGHT,
                        None, None, self._hinstance, None,
                    )
                    if not overlay_hwnd:
                        continue
                    self._overlay_hwnds[target_hwnd] = overlay_hwnd

                    user32.SetLayeredWindowAttributes(
                        overlay_hwnd, 0, self.WINDOW_ALPHA, self.LWA_ALPHA,
                    )

                user32.SetWindowPos(
                    overlay_hwnd, self.HWND_TOPMOST,
                    overlay_x, overlay_y,
                    self.OVERLAY_WIDTH, self.OVERLAY_HEIGHT,
                    self.SWP_NOACTIVATE | self.SWP_SHOWWINDOW,
                )

                if text_changed:
                    user32.InvalidateRect(overlay_hwnd, None, 1)

            except Exception:
                continue

    def _cleanup_all(self) -> None:
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            for overlay_hwnd in list(self._overlay_hwnds.values()):
                try:
                    user32.DestroyWindow(overlay_hwnd)
                except Exception:
                    pass
            self._overlay_hwnds.clear()
            if self._wndclass_atom and self._hinstance:
                try:
                    user32.UnregisterClassW(self.WNDCLASS_NAME, self._hinstance)
                except Exception:
                    pass
                self._wndclass_atom = 0
            if self._bg_brush:
                try:
                    gdi32.DeleteObject(self._bg_brush)
                except Exception:
                    pass
                self._bg_brush = None
        except Exception:
            pass
