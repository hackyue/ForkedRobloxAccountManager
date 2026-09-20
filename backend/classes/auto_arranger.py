import os
import sys
import time
import math
import ctypes
import platform
import threading
from typing import Dict, List, Tuple, Any, Optional, Set

try:
    import win32gui
    import win32con
    import win32api
    import win32process
except ImportError:
    win32gui = win32con = win32api = win32process = None

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080
SWP_NOCOPYBITS = 0x0100
SWP_NOOWNERZORDER = 0x0200
SWP_NOSENDCHANGING = 0x0400

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
SW_RESTORE = 9
SW_SHOWNORMAL = 1

ROBLOX_CLIENT_EXECUTABLES: Set[str] = {
    "robloxplayerbeta.exe",
    "robloxplayer.exe",
}

ROBLOX_TARGET_EXECUTABLES: Set[str] = ROBLOX_CLIENT_EXECUTABLES

BOOTSTRAPPER_EXECUTABLES: Set[str] = {
    "bloxstrap.exe",
    "fishstrap.exe",
    "voidstrap.exe",
    "froststrap.exe",
    "exploitstrap.exe",
    "robloxplayerlauncher.exe",
    "robloxplayerinstaller.exe",
    "robloxcrashhandler.exe",
}

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]

class AutoArranger:
    def __init__(self, settings_getter=None, headless_manager=None):
        self.settings_getter = settings_getter
        self.headless_manager = headless_manager
        self.lock = threading.Lock()
        self.watchdog_thread: Optional[threading.Thread] = None
        self.watchdog_running = False
        self.last_signature: Optional[Tuple[Any, ...]] = None
        self.last_arranged_count = 0
        self.last_arranged_time = 0.0
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
        val = settings.get("keepClientsArranged", settings.get("keep_roblox_clients_arranged", False))
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes", "on", "enable", "enabled")
        return bool(val)

    def is_bootstrapper_window(self, hwnd: int, proc_name: str = "") -> bool:
        name = str(proc_name or "").lower()
        if name in BOOTSTRAPPER_EXECUTABLES:
            return True
        if any(token in name for token in ("bloxstrap", "fishstrap", "voidstrap", "froststrap", "exploitstrap", "launcher", "installer", "bootstrapper", "crashhandler")):
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

    def get_roblox_client_windows(self) -> List[int]:
        if platform.system() != "Windows":
            return []

        user32 = ctypes.windll.user32
        found_hwnds: List[int] = []

        if win32gui and win32process:
            def enum_cb(hwnd, extra):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if self.headless_manager and hasattr(self.headless_manager, 'hidden_hwnds') and hwnd in self.headless_manager.hidden_hwnds:
                    return True
                if win32gui.IsIconic(hwnd):
                    pass
                try:
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    width = right - left
                    height = bottom - top
                    if width <= 10 or height <= 10:
                        return True
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid:
                        import psutil
                        proc = psutil.Process(pid)
                        name = proc.name().lower()
                        if self.is_bootstrapper_window(hwnd, name):
                            return True
                        if name in ROBLOX_CLIENT_EXECUTABLES:
                            found_hwnds.append(hwnd)
                            return True
                except Exception:
                    pass

                try:
                    title = win32gui.GetWindowText(hwnd) or ""
                    cls_name = win32gui.GetClassName(hwnd) or ""
                    if cls_name in ("RobloxPlayer", "RobloxPlayerBeta", "WINDOWSCLIENT"):
                        if not self.is_bootstrapper_window(hwnd, ""):
                            if hwnd not in found_hwnds:
                                found_hwnds.append(hwnd)
                except Exception:
                    pass
                return True

            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception:
                pass
        else:
            def c_enum_cb(hwnd, lparam):
                if not user32.IsWindowVisible(hwnd):
                    return 1
                rect = RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w <= 10 or h <= 10:
                        return 1
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value:
                    try:
                        import psutil
                        proc = psutil.Process(pid.value)
                        name = proc.name().lower()
                        if self.is_bootstrapper_window(hwnd, name):
                            return 1
                        if name in ROBLOX_CLIENT_EXECUTABLES:
                            found_hwnds.append(hwnd)
                    except Exception:
                        pass
                return 1

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            cb = WNDENUMPROC(c_enum_cb)
            user32.EnumWindows(cb, 0)

        found_hwnds.sort()
        return found_hwnds

    def get_monitor_work_areas(self) -> List[Tuple[bool, Tuple[int, int, int, int]]]:
        if platform.system() != "Windows":
            return [(True, (0, 0, 1920, 1080))]

        monitors: List[Tuple[bool, Tuple[int, int, int, int]]] = []

        if win32api:
            try:
                enum_monitors = win32api.EnumDisplayMonitors(None, None)
                for handle, _, _ in enum_monitors:
                    try:
                        info = win32api.GetMonitorInfo(handle)
                        work = info.get("Work") or info.get("WorkArea") or info.get("Monitor")
                        if not work:
                            continue
                        flags = info.get("Flags", 0)
                        primary_flag = getattr(win32con, "MONITORINFOF_PRIMARY", 1)
                        is_primary = bool(flags & primary_flag)
                        monitors.append((is_primary, (int(work[0]), int(work[1]), int(work[2]), int(work[3]))))
                    except Exception:
                        pass
            except Exception:
                pass

        if not monitors:
            user32 = ctypes.windll.user32

            def monitor_enum_proc(hmonitor, hdc, lprect, lparam):
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
                    is_primary = bool(mi.dwFlags & 1)
                    work = (int(mi.rcWork.left), int(mi.rcWork.top), int(mi.rcWork.right), int(mi.rcWork.bottom))
                    monitors.append((is_primary, work))
                return 1

            MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_void_p)
            proc = MONITORENUMPROC(monitor_enum_proc)
            user32.EnumDisplayMonitors(0, 0, proc, 0)

        if not monitors:
            user32 = ctypes.windll.user32
            sm_cxscreen = user32.GetSystemMetrics(0)
            sm_cyscreen = user32.GetSystemMetrics(1)
            monitors.append((True, (0, 0, sm_cxscreen or 1920, sm_cyscreen or 1080)))

        monitors.sort(key=lambda item: (not item[0], item[1][0], item[1][1]))
        return monitors

    def filter_monitors_by_scope(self, monitors: List[Tuple[bool, Tuple[int, int, int, int]]], scope: str) -> List[Tuple[int, int, int, int]]:
        if not monitors:
            return []

        work_areas = [area for _, area in monitors]
        scope_str = str(scope or "both").lower().strip()

        if scope_str.startswith("monitor_"):
            try:
                idx = int(scope_str.split("_")[1]) - 1
                if 0 <= idx < len(work_areas):
                    return [work_areas[idx]]
            except Exception:
                pass
        elif scope_str.isdigit():
            idx = int(scope_str) - 1
            if 0 <= idx < len(work_areas):
                return [work_areas[idx]]

        if scope_str == "primary":
            return work_areas[:1]
        elif scope_str == "secondary":
            if len(work_areas) > 1:
                return work_areas[1:2]
            return work_areas[:1]
        elif scope_str == "both" or scope_str == "all":
            return work_areas
        return work_areas

    def sort_windows_by_position(self, hwnds: List[int]) -> List[int]:
        user32 = ctypes.windll.user32
        positioned: List[Tuple[int, int, int]] = []

        for hwnd in hwnds:
            rect = RECT()
            left = top = 0
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                left = rect.left
                top = rect.top
            positioned.append((top, left, hwnd))

        positioned.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[2] for item in positioned]

    def get_window_signature(self, hwnds: List[int]) -> Tuple[Tuple[int, int, int, int, int], ...]:
        user32 = ctypes.windll.user32
        sig = []
        for hwnd in self.sort_windows_by_position(hwnds):
            rect = RECT()
            left = top = right = bottom = 0
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                left = int(rect.left)
                top = int(rect.top)
                right = int(rect.right)
                bottom = int(rect.bottom)
            sig.append((int(hwnd), left, top, max(0, right - left), max(0, bottom - top)))
        return tuple(sig)

    def calculate_tile_layout(self, window_count: int, available_width: int, available_height: int, dimension_mode: str, target_width: int = 800, target_height: int = 600) -> Tuple[int, int, int, int]:
        if window_count <= 0:
            return (1, 1, max(1, available_width), max(1, available_height))

        mode = str(dimension_mode or "auto").lower().strip()

        if mode == "target_size":
            t_w = max(50, min(7680, int(target_width or 800)))
            t_h = max(50, min(4320, int(target_height or 600)))

            cols = max(1, min(window_count, available_width // t_w))
            rows = max(1, math.ceil(window_count / cols))

            while rows * t_h > available_height and cols < window_count:
                cols += 1
                rows = max(1, math.ceil(window_count / cols))

            tile_w = max(1, min(t_w, available_width // cols))
            tile_h = max(1, min(t_h, available_height // rows))
            return (cols, rows, tile_w, tile_h)

        aspect_ratio = available_width / available_height if available_height else 1.0
        cols = max(1, math.ceil(math.sqrt(window_count * aspect_ratio)))
        cols = min(cols, window_count)
        rows = max(1, math.ceil(window_count / cols))
        tile_w = max(1, available_width // cols)
        tile_h = max(1, available_height // rows)
        return (cols, rows, tile_w, tile_h)

    def move_resize_window_unclamped(self, hwnd: int, x: int, y: int, width: int, height: int, strip_styles: bool = False) -> bool:
        if platform.system() != "Windows":
            return False

        user32 = ctypes.windll.user32
        flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOSENDCHANGING

        original_style = None
        if strip_styles:
            try:
                original_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                stripped_style = original_style & ~(WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
                user32.SetWindowLongW(hwnd, GWL_STYLE, stripped_style)
            except Exception:
                original_style = None

        user32.SetWindowPos(hwnd, None, int(x), int(y), int(width), int(height), flags)

        if original_style is not None:
            try:
                user32.SetWindowLongW(hwnd, GWL_STYLE, original_style)
                user32.SetWindowPos(hwnd, None, int(x), int(y), int(width), int(height), flags)
            except Exception:
                pass

        time.sleep(0.04)
        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            actual_w = max(1, rect.right - rect.left)
            actual_h = max(1, rect.bottom - rect.top)
            return actual_w == int(width) and actual_h == int(height)
        return True

    def arrange_windows_within_area(self, hwnds: List[int], work_area: Tuple[int, int, int, int], dimension_mode: str = "auto", target_width: int = 800, target_height: int = 600) -> None:
        work_left, work_top, work_right, work_bottom = work_area
        available_width = max(1, work_right - work_left)
        available_height = max(1, work_bottom - work_top)
        count = len(hwnds)

        if count == 0:
            return

        columns, rows, tile_w, tile_h = self.calculate_tile_layout(
            count,
            available_width,
            available_height,
            dimension_mode=dimension_mode,
            target_width=target_width,
            target_height=target_height,
        )

        user32 = ctypes.windll.user32

        for idx, hwnd in enumerate(hwnds):
            row = idx // columns
            col = idx % columns
            if row >= rows:
                row = rows - 1

            left = work_left + (col * tile_w)
            top = work_top + (row * tile_h)
            w = max(1, tile_w)
            h = max(1, tile_h)

            left = min(left, work_right - w)
            top = min(top, work_bottom - h)

            try:
                if win32gui and not win32gui.IsWindowVisible(hwnd):
                    continue
                if self.headless_manager and hasattr(self.headless_manager, 'hidden_hwnds') and hwnd in self.headless_manager.hidden_hwnds:
                    continue
                user32.ShowWindow(hwnd, SW_RESTORE)
                ok = self.move_resize_window_unclamped(hwnd, left, top, w, h, strip_styles=False)
                if not ok:
                    ok = self.move_resize_window_unclamped(hwnd, left, top, w, h, strip_styles=True)
                if not ok and win32gui:
                    win32gui.MoveWindow(hwnd, left, top, w, h, True)
            except Exception:
                pass

    def arrange_clients(self, scope: Optional[str] = None, dimension_mode: Optional[str] = None, target_width: Optional[int] = None, target_height: Optional[int] = None) -> Dict[str, Any]:
        if platform.system() != "Windows":
            return {
                "success": False,
                "count": 0,
                "monitors": 0,
                "message": "Auto-Arrange is only supported on Windows operating systems."
            }

        with self.lock:
            settings = self.get_settings()
            effective_scope = scope if scope is not None else settings.get("autoArrangeScope", settings.get("auto_arrange_scope", "both"))
            effective_dim_mode = dimension_mode if dimension_mode is not None else settings.get("autoArrangeDimensionMode", settings.get("auto_arrange_dimension_mode", "auto"))
            effective_t_width = int(target_width if target_width is not None else settings.get("autoArrangeTargetWidth", settings.get("auto_arrange_target_width", 800)))
            effective_t_height = int(target_height if target_height is not None else settings.get("autoArrangeTargetHeight", settings.get("auto_arrange_target_height", 600)))

            hwnds = self.get_roblox_client_windows()
            if not hwnds:
                return {
                    "success": False,
                    "count": 0,
                    "monitors": 0,
                    "message": "No active Roblox client windows were detected."
                }

            all_monitors = self.get_monitor_work_areas()
            filtered_work_areas = self.filter_monitors_by_scope(all_monitors, effective_scope)

            if not filtered_work_areas:
                filtered_work_areas = [area for _, area in all_monitors]

            sorted_hwnds = self.sort_windows_by_position(hwnds)
            num_monitors = len(filtered_work_areas)
            assignments: List[List[int]] = [[] for _ in range(num_monitors)]

            for i, hwnd in enumerate(sorted_hwnds):
                assignments[i % num_monitors].append(hwnd)

            for mon_idx, assigned in enumerate(assignments):
                if not assigned:
                    continue
                self.arrange_windows_within_area(
                    assigned,
                    filtered_work_areas[mon_idx],
                    dimension_mode=effective_dim_mode,
                    target_width=effective_t_width,
                    target_height=effective_t_height
                )

            self.last_signature = self.get_window_signature(sorted_hwnds)
            self.last_arranged_count = len(sorted_hwnds)
            self.last_arranged_time = time.time()

            return {
                "success": True,
                "count": len(sorted_hwnds),
                "monitors": num_monitors,
                "message": f"Successfully arranged {len(sorted_hwnds)} Roblox client(s) across {num_monitors} monitor(s)!"
            }

    def start_watchdog(self) -> None:
        with self.lock:
            if self.watchdog_running:
                return
            self.watchdog_running = True
            self.generation += 1
            gen = self.generation
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                args=(gen,),
                daemon=True,
                name="keep-clients-arranged-watchdog"
            )
            self.watchdog_thread.start()

    def stop_watchdog(self) -> None:
        with self.lock:
            if self.watchdog_running:
                self.watchdog_running = False
                self.generation += 1
                self.watchdog_thread = None

    def sync_watchdog(self, enabled: Optional[bool] = None) -> None:
        with self.lock:
            if enabled is None:
                enabled = self.is_enabled()
            else:
                if isinstance(enabled, str):
                    enabled = enabled.strip().lower() in ("true", "1", "yes", "on", "enable", "enabled")
                else:
                    enabled = bool(enabled)

            if enabled:
                if not self.watchdog_running:
                    self.watchdog_running = True
                    self.generation += 1
                    gen = self.generation
                    self.watchdog_thread = threading.Thread(
                        target=self._watchdog_loop,
                        args=(gen,),
                        daemon=True,
                        name="keep-clients-arranged-watchdog"
                    )
                    self.watchdog_thread.start()
            else:
                if self.watchdog_running:
                    self.watchdog_running = False
                    self.generation += 1
                    self.watchdog_thread = None

    def trigger_delayed_arrange(self, delay_seconds: float = 2.5) -> None:
        if not self.is_enabled():
            return

        def delayed_worker():
            time.sleep(max(0.5, float(delay_seconds)))
            try:
                if self.is_enabled():
                    self.arrange_clients()
            except Exception:
                pass

        threading.Thread(target=delayed_worker, daemon=True, name="delayed-auto-arrange").start()

    def _watchdog_loop(self, generation: int) -> None:
        while self.watchdog_running and self.generation == generation:
            try:
                time.sleep(5)
                if not self.watchdog_running or self.generation != generation:
                    break

                if not self.is_enabled():
                    self.stop_watchdog()
                    break

                hwnds = self.get_roblox_client_windows()
                if not hwnds:
                    self.last_signature = None
                    continue

                current_sig = self.get_window_signature(hwnds)
                if current_sig != self.last_signature:
                    self.arrange_clients()
            except Exception:
                pass
