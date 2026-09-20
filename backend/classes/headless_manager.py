import os
import sys
import time
import ctypes
import platform
import threading
from typing import Dict, List, Tuple, Any, Optional, Set

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = win32con = win32process = None

class HeadlessManager:
    ROBLOX_HEADLESS_TARGET_EXECUTABLES: Set[str] = {
        "robloxplayerbeta.exe",
        "robloxplayer.exe",
    }
    ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS = 2
    ROBLOX_HEADLESS_MEMORY_TRIM_INTERVAL_SECONDS = 30
    _PROCESS_SET_INFORMATION = 0x0200
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _IDLE_PRIORITY_CLASS = 0x00000040
    _NORMAL_PRIORITY_CLASS = 0x00000020

    def __init__(self, settings_getter=None, auto_arranger=None):
        self.settings_getter = settings_getter
        self.auto_arranger = auto_arranger
        self.lock = threading.Lock()
        self.watchdog_thread: Optional[threading.Thread] = None
        self.watchdog_running = False
        self.last_trim_ts = 0.0
        self.seen_pids: Set[int] = set()
        self.first_seen_pids: Dict[int, float] = {}
        self.hidden_hwnds: Set[int] = set()
        self.generation = 0

    def get_settings(self) -> Dict[str, Any]:
        if callable(self.settings_getter):
            try:
                res = self.settings_getter()
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {}

    def is_enabled(self) -> bool:
        settings = self.get_settings()
        return bool(settings.get("headlessMode", False) or settings.get("roblox_headless_mode_enabled", False))

    def is_idle_priority_enabled(self) -> bool:
        settings = self.get_settings()
        return bool(settings.get("headlessIdlePriority", True) or settings.get("roblox_headless_idle_priority", True))

    def is_trim_memory_enabled(self) -> bool:
        settings = self.get_settings()
        return bool(settings.get("headlessTrimMemory", True) or settings.get("roblox_headless_trim_memory", True))

    def get_detection_delay_seconds(self) -> int:
        settings = self.get_settings()
        try:
            val = int(settings.get("headlessDetectionDelaySeconds", 0) or settings.get("roblox_headless_detection_delay_seconds", 0))
            return max(0, min(300, val))
        except Exception:
            return 0

    def get_roblox_pids(self) -> Set[int]:
        if platform.system() != "Windows":
            return set()
        pids: Set[int] = set()
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = str(proc.info.get('name') or '').lower()
                    if name in self.ROBLOX_HEADLESS_TARGET_EXECUTABLES:
                        pids.add(int(proc.info['pid']))
                except Exception:
                    continue
        except Exception:
            try:
                import subprocess
                ps_script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'robloxplayerbeta' } | Select-Object -ExpandProperty ProcessId"
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().splitlines():
                        line = line.strip()
                        if line.isdigit():
                            pids.add(int(line))
            except Exception:
                pass
        return pids

    def get_roblox_windows(self, target_pids: Optional[Set[int]] = None, include_hidden: bool = False) -> List[int]:
        if platform.system() != "Windows" or not win32gui or not win32process:
            return []

        if target_pids is None:
            target_pids = self.get_roblox_pids()
        if not target_pids:
            return []

        found_windows: List[int] = []

        def enum_window_callback(hwnd, extra):
            try:
                if not win32gui.IsWindow(hwnd):
                    return True
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in target_pids:
                    return True

                is_vis = bool(win32gui.IsWindowVisible(hwnd))
                if not include_hidden and not is_vis:
                    return True

                title = str(win32gui.GetWindowText(hwnd) or "").strip()
                class_name = str(win32gui.GetClassName(hwnd) or "").strip()

                if title or class_name == "WINDOWSCLIENT" or "Roblox" in title or "Roblox" in class_name:
                    found_windows.append(int(hwnd))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_window_callback, None)
        except Exception:
            pass

        return found_windows

    def hide_window(self, hwnd: int) -> bool:
        if not hwnd or not win32gui:
            return False
        changed = False
        try:
            if win32gui.IsWindowVisible(hwnd):
                win32gui.ShowWindow(hwnd, getattr(win32con, "SW_HIDE", 0))
                changed = True
        except Exception:
            pass

        try:
            win32gui.PostMessage(
                hwnd,
                getattr(win32con, "WM_SYSCOMMAND", 0x0112),
                getattr(win32con, "SC_MINIMIZE", 0xF020),
                0,
            )
        except Exception:
            pass

        if changed:
            self.hidden_hwnds.add(hwnd)
        return changed

    def restore_window(self, hwnd: int) -> bool:
        if not hwnd or not win32gui:
            return False
        try:
            win32gui.ShowWindow(hwnd, getattr(win32con, "SW_SHOW", 5))
            win32gui.ShowWindow(hwnd, getattr(win32con, "SW_RESTORE", 9))
            self.hidden_hwnds.discard(hwnd)
            return True
        except Exception:
            return False

    def set_process_priority(self, pid: int, priority_class: int) -> Tuple[bool, str]:
        if not pid or platform.system() != "Windows":
            return False, "invalid pid or platform"
        handle = None
        try:
            kernel32 = ctypes.windll.kernel32
            access = self._PROCESS_SET_INFORMATION | self._PROCESS_QUERY_LIMITED_INFORMATION
            handle = kernel32.OpenProcess(access, False, int(pid))
            if not handle:
                return False, "OpenProcess failed"
            ok = kernel32.SetPriorityClass(handle, int(priority_class))
            if ok:
                return True, "ok"
            return False, "SetPriorityClass failed"
        except Exception as exc:
            return False, str(exc)
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)
                except Exception:
                    pass

    def trim_process_memory(self, pid: int) -> bool:
        if not pid or platform.system() != "Windows":
            return False
        handle = None
        try:
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
            kernel32.OpenProcess.restype = ctypes.c_void_p

            kernel32.SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
            kernel32.SetProcessWorkingSetSize.restype = ctypes.c_bool

            psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
            psapi.EmptyWorkingSet.restype = ctypes.c_bool

            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool

            access = 0x0100 | 0x0400 | 0x0008 | 0x0010 | 0x1000 | 0x0200
            handle = kernel32.OpenProcess(access, False, int(pid))
            if not handle:
                return False

            size_max = ctypes.c_size_t(-1).value
            ok1 = psapi.EmptyWorkingSet(handle)
            ok2 = kernel32.SetProcessWorkingSetSize(handle, size_max, size_max)
            return bool(ok1 or ok2)
        except Exception:
            return False
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)
                except Exception:
                    pass

    def apply_pass(self, force_trim: bool = False) -> Dict[str, Any]:
        with self.lock:
            pids = self.get_roblox_pids()
            if not pids:
                self.seen_pids = set()
                self.first_seen_pids = {}
                return {
                    "pids": 0,
                    "hidden": 0,
                    "priority": 0,
                    "trimmed": 0,
                    "new_pids": []
                }

            now = time.monotonic()
            delay_seconds = 0 if force_trim else self.get_detection_delay_seconds()

            for stale_pid in set(self.first_seen_pids.keys()) - pids:
                self.first_seen_pids.pop(stale_pid, None)

            for pid in pids:
                if pid not in self.first_seen_pids:
                    self.first_seen_pids[pid] = now

            if delay_seconds > 0:
                ready_pids = {
                    pid for pid in pids
                    if (now - float(self.first_seen_pids.get(pid, now))) >= delay_seconds
                }
            else:
                ready_pids = set(pids)

            previous_pids = set(self.seen_pids)
            new_pids = sorted(pids - previous_pids)
            self.seen_pids = set(pids)

            if not ready_pids:
                return {
                    "pids": len(pids),
                    "hidden": 0,
                    "priority": 0,
                    "trimmed": 0,
                    "new_pids": new_pids
                }

            hidden_count = 0
            priority_count = 0
            trimmed_count = 0

            visible_windows = self.get_roblox_windows(target_pids=ready_pids, include_hidden=False)
            for hwnd in visible_windows:
                if self.hide_window(hwnd):
                    hidden_count += 1

            if self.is_idle_priority_enabled():
                for pid in ready_pids:
                    ok, _ = self.set_process_priority(pid, self._IDLE_PRIORITY_CLASS)
                    if ok:
                        priority_count += 1
            else:
                for pid in ready_pids:
                    self.set_process_priority(pid, self._NORMAL_PRIORITY_CLASS)

            if self.is_trim_memory_enabled():
                should_trim = force_trim or (now - self.last_trim_ts) >= self.ROBLOX_HEADLESS_MEMORY_TRIM_INTERVAL_SECONDS
                if should_trim:
                    for pid in ready_pids:
                        if self.trim_process_memory(pid):
                            trimmed_count += 1
                    self.last_trim_ts = now

            return {
                "pids": len(pids),
                "hidden": hidden_count,
                "priority": priority_count,
                "trimmed": trimmed_count,
                "new_pids": new_pids
            }

    def restore_all_windows(self) -> Dict[str, Any]:
        with self.lock:
            pids = self.get_roblox_pids()
            restored_count = 0
            priority_count = 0

            windows = self.get_roblox_windows(target_pids=pids if pids else None, include_hidden=True)
            for hwnd in windows:
                if self.restore_window(hwnd):
                    restored_count += 1

            for pid in pids:
                ok, _ = self.set_process_priority(pid, self._NORMAL_PRIORITY_CLASS)
                if ok:
                    priority_count += 1

            self.seen_pids = set()
            self.first_seen_pids = {}
            self.hidden_hwnds = set()

            if restored_count > 0 and self.auto_arranger and self.auto_arranger.is_enabled():
                try:
                    self.auto_arranger.trigger_delayed_arrange(0.5)
                except Exception:
                    pass

            return {
                "pids": len(pids),
                "restored": restored_count,
                "priority": priority_count
            }

    def trigger_delayed_headless(self, delays: Optional[List[float]] = None):
        if delays is None:
            delays = [0.8, 2.0, 4.0, 7.0]

        def runner():
            for d in delays:
                time.sleep(d)
                if self.is_enabled():
                    try:
                        self.apply_pass(force_trim=False)
                    except Exception:
                        pass

        threading.Thread(target=runner, daemon=True, name="delayed-headless-runner").start()

    def sync_watchdog(self, enabled: Optional[bool] = None):
        if enabled is None:
            enabled = self.is_enabled()

        if enabled:
            if not self.watchdog_running:
                self.watchdog_running = True
                self.generation += 1
                gen = self.generation
                self.watchdog_thread = threading.Thread(
                    target=self._watchdog_loop,
                    args=(gen,),
                    daemon=True,
                    name="headless-mode-watchdog"
                )
                self.watchdog_thread.start()
        else:
            if self.watchdog_running:
                self.watchdog_running = False
                self.generation += 1
                threading.Thread(
                    target=self.restore_all_windows,
                    daemon=True,
                    name="headless-restore-worker"
                ).start()

    def _watchdog_loop(self, generation: int):
        while self.watchdog_running and self.generation == generation:
            try:
                if self.is_enabled():
                    self.apply_pass(force_trim=False)
            except Exception:
                pass
            time.sleep(self.ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS)
