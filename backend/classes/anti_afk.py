import os
import sys
import time
import platform
import threading
import re
from typing import Dict, List, Set, Any, Optional, Tuple

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = win32con = win32process = None


class AntiAfkManager:
    """Manages periodic background input injection into active Roblox client windows to prevent idle timeouts."""

    TARGET_EXECUTABLES: Set[str] = {
        "robloxplayerbeta.exe",
        "robloxplayer.exe",
        "robloxplayerlauncher.exe",
        "bloxstrap.exe",
        "fishstrap.exe",
        "voidstrap.exe",
        "froststrap.exe",
        "exploitstrap.exe",
    }
    DEFAULT_INTERVAL_MINUTES: int = 10
    MIN_INTERVAL_MINUTES: int = 1
    MAX_INTERVAL_MINUTES: int = 19
    DEFAULT_KEY_NAME: str = "M1"

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

    def __init__(self, settings_getter=None, accounts_getter=None, launch_info_getter=None):
        self.settings_getter = settings_getter
        self.accounts_getter = accounts_getter
        self.launch_info_getter = launch_info_getter
        self.lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.running: bool = False
        self.last_run_ts: Optional[float] = None
        self.next_run_ts: Optional[float] = None
        self.last_pass_summary: Optional[Dict[str, int]] = None
        self.in_progress: bool = False
        self._pids_cache: Set[int] = set()
        self._pids_cache_ts: float = 0.0

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

    def get_roblox_windows(self, include_hidden: bool = True) -> List[Tuple[int, int, str]]:
        if platform.system() != "Windows" or not win32gui or not win32process:
            return []

        now = time.time()
        pids: Set[int] = set()
        if (now - self._pids_cache_ts) < 2.0:
            pids = set(self._pids_cache)
        else:
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        name = str(proc.info.get('name') or '').lower()
                        if name in self.TARGET_EXECUTABLES:
                            pids.add(int(proc.info['pid']))
                    except Exception:
                        continue
                self._pids_cache = set(pids)
                self._pids_cache_ts = now
            except Exception:
                pass

        if not pids:
            return []

        windows: List[Tuple[int, int, str]] = []

        def enum_win_cb(hwnd, _):
            if not win32gui.IsWindow(hwnd):
                return True
            if not include_hidden and not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in pids:
                    title = win32gui.GetWindowText(hwnd) or "Roblox"
                    cls = win32gui.GetClassName(hwnd) or ""
                    if "Roblox" in title or "Roblox" in cls or "WINDOWSCLIENT" in cls or "ApplicationFrame" in cls or cls == "Win32Window0":
                        windows.append((hwnd, pid, title))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_win_cb, None)
        except Exception:
            pass

        return windows

    def post_window_input(self, hwnd: int, key_name: str) -> bool:
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

            win32gui.PostMessage(hwnd, getattr(win32con, "WM_MOUSEMOVE", 0x0200), 0, lparam)

            if key_name in {"M1", "M2", "M3"}:
                mouse_map = {
                    "M1": (0x0201, 0x0202, 0x0001),
                    "M2": (0x0204, 0x0205, 0x0002),
                    "M3": (0x0207, 0x0208, 0x0010),
                }
                msg_down, msg_up, wparam = mouse_map[key_name]
                win32gui.PostMessage(hwnd, msg_down, wparam, lparam)
                time.sleep(0.05)
                win32gui.PostMessage(hwnd, msg_up, 0, lparam)
                return True
            else:
                code = self.get_key_code(key_name)
                if code > 0:
                    win32gui.PostMessage(hwnd, getattr(win32con, "WM_KEYDOWN", 0x0100), code, 0)
                    time.sleep(0.05)
                    win32gui.PostMessage(hwnd, getattr(win32con, "WM_KEYUP", 0x0101), code, 0xC0000001)
                    return True
        except Exception as e:
            print(f"AntiAFK PostMessage error for hwnd {hwnd}: {e}")

        return False

    def trigger_pass(self) -> Dict[str, Any]:
        with self.lock:
            self.in_progress = True

        try:
            windows = self.get_roblox_windows()
            key_name = self.get_key_name()
            total = len(windows)
            success = 0
            failed = 0

            for hwnd, pid, title in windows:
                if not self.is_window_afk_enabled(hwnd, pid, title):
                    continue
                if self.post_window_input(hwnd, key_name):
                    success += 1
                else:
                    failed += 1

            now = time.time()
            self.last_run_ts = now
            self.last_pass_summary = {
                "total_windows": total,
                "successful_windows": success,
                "failed_windows": failed,
            }

            interval_sec = self.get_interval_minutes() * 60
            self.next_run_ts = now + interval_sec

            return {
                "success": True,
                "total_windows": total,
                "successful_windows": success,
                "failed_windows": failed,
                "key_used": key_name,
                "timestamp": now,
            }
        finally:
            with self.lock:
                self.in_progress = False

    def start_loop(self):
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._loop, daemon=True)
        self.worker_thread.start()

    def stop_loop(self):
        self.running = False
        self.worker_thread = None

    def _loop(self):
        while self.running:
            try:
                if self.is_enabled():
                    now = time.time()
                    interval_sec = self.get_interval_minutes() * 60
                    if self.next_run_ts is None:
                        self.next_run_ts = now + interval_sec

                    if now >= self.next_run_ts:
                        self.trigger_pass()

                time.sleep(2)
            except Exception as e:
                print(f"AntiAFK worker error: {e}")
                time.sleep(5)

    def get_status(self) -> Dict[str, Any]:
        windows = self.get_roblox_windows()
        key_name = self.get_key_name()
        interval_min = self.get_interval_minutes()
        enabled = self.is_enabled()
        now = time.time()

        remaining_sec = 0
        if enabled and self.next_run_ts:
            remaining_sec = max(0, int(self.next_run_ts - now))

        return {
            "success": True,
            "enabled": enabled,
            "interval_minutes": interval_min,
            "key_name": key_name,
            "key_code": self.get_key_code(key_name),
            "roblox_instance_count": len(windows),
            "last_run_ts": self.last_run_ts,
            "next_run_ts": self.next_run_ts,
            "seconds_until_next_run": remaining_sec,
            "last_pass_summary": self.last_pass_summary,
            "in_progress": self.in_progress,
        }
