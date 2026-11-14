import ctypes
import ctypes.wintypes as wintypes
import platform
from typing import Any, Dict, List, Optional, Tuple
import psutil


class HyperionOffsets:
    # Hyperion
    VIOLATION_TABLE = 0x1190EB8
    VIOLATIONS_INDEX = 0x10
    ENCODED_VIOLATIONS = 0x19
    XOR_TABLE_INDEX = 0x0

    # Instance
    DATAMODEL_ARBITER = 0x8F8E968
    ARBITER_TO_DATAMODEL = 0x1F0
    CHILDREN = 0x70
    SCRIPT_CONTEXT = 0x440

    # Structs
    L_GLOBAL = 0x60
    REGISTRY_FREE = 0x630

    # Luau
    GLOBAL_STATES = 0x188
    ACTOR_STATE = 0x310
    GLOBAL_STATE = 0x18
    ENCRYPTED_STATE = 0x220


TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_wchar * 256),
        ("szExePath", ctypes.c_wchar * 260),
    ]


def _rol1(x: int, n: int) -> int:
    n &= 7
    return ((x << n) | (x >> ((8 - n) & 7))) & 0xFF


_KERNEL32_CACHE = None


def _setup_kernel32():
    global _KERNEL32_CACHE
    if _KERNEL32_CACHE is not None:
        return _KERNEL32_CACHE

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32FirstW.restype = wintypes.BOOL

    kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
    kernel32.Module32NextW.restype = wintypes.BOOL

    kernel32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    _KERNEL32_CACHE = kernel32
    return kernel32


def _get_module_base(kernel32: Any, pid: int, module_name: str) -> Optional[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, int(pid))
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return None
    try:
        me = MODULEENTRY32W()
        me.dwSize = ctypes.sizeof(MODULEENTRY32W)
        target = module_name.lower()
        if kernel32.Module32FirstW(snapshot, ctypes.byref(me)):
            while True:
                if str(me.szModule).lower() == target and me.modBaseAddr:
                    return int(me.modBaseAddr)
                if not kernel32.Module32NextW(snapshot, ctypes.byref(me)):
                    break
        return None
    finally:
        kernel32.CloseHandle(snapshot)


def _read_u8(kernel32: Any, handle: int, address: int) -> Tuple[bool, int]:
    buf = ctypes.c_uint8(0)
    bytes_read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(address),
        ctypes.byref(buf),
        1,
        ctypes.byref(bytes_read),
    )
    if not ok or bytes_read.value != 1:
        return False, 0
    return True, int(buf.value)


def _read_u32(kernel32: Any, handle: int, address: int) -> Tuple[bool, int]:
    buf = ctypes.c_uint32(0)
    bytes_read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(address),
        ctypes.byref(buf),
        4,
        ctypes.byref(bytes_read),
    )
    if not ok or bytes_read.value != 4:
        return False, 0
    return True, int(buf.value)


def _read_ptr(kernel32: Any, handle: int, address: int) -> Tuple[bool, int]:
    buf = ctypes.c_uint64(0)
    bytes_read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(address),
        ctypes.byref(buf),
        8,
        ctypes.byref(bytes_read),
    )
    if not ok or bytes_read.value != 8:
        return False, 0
    return True, int(buf.value)


def _decrypt_state(kernel32: Any, handle: int, encrypted_state: int) -> Optional[int]:
    ok_low, raw_low = _read_u32(kernel32, handle, encrypted_state)
    ok_high, raw_high = _read_u32(kernel32, handle, encrypted_state + 0x4)
    if not ok_low or not ok_high:
        return None
    addr32 = encrypted_state & 0xFFFFFFFF
    low = (raw_low - addr32) & 0xFFFFFFFF
    high = (raw_high - addr32) & 0xFFFFFFFF
    return ((high << 32) | low) & 0xFFFFFFFFFFFFFFFF


def _read_luau_violations(kernel32: Any, handle: int, roblox_base: int) -> Dict[str, Any]:
    if not roblox_base:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "RobloxPlayerBeta.exe not loaded"}

    ok, data_model = _read_ptr(kernel32, handle, roblox_base + HyperionOffsets.DATAMODEL_ARBITER)
    if not ok or not data_model:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "DataModel not active"}

    data_model += HyperionOffsets.ARBITER_TO_DATAMODEL
    ok, children_container = _read_ptr(kernel32, handle, data_model + HyperionOffsets.CHILDREN)
    if not ok or not children_container:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "DataModel children unavailable"}

    ok, children = _read_ptr(kernel32, handle, children_container)
    if not ok or not children:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "Failed to read DataModel children"}

    ok, script_context = _read_ptr(kernel32, handle, children + HyperionOffsets.SCRIPT_CONTEXT)
    if not ok or not script_context:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "ScriptContext unavailable"}

    encrypted_l1 = script_context + HyperionOffsets.GLOBAL_STATES + HyperionOffsets.GLOBAL_STATE
    encrypted_l2 = encrypted_l1 + HyperionOffsets.ACTOR_STATE

    l1 = _decrypt_state(kernel32, handle, encrypted_l1 + HyperionOffsets.ENCRYPTED_STATE)
    l2 = _decrypt_state(kernel32, handle, encrypted_l2 + HyperionOffsets.ENCRYPTED_STATE)
    if not l1 or not l2:
        return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "Failed to decrypt Luau states"}

    def _bit(ptr: int, b: int) -> Optional[int]:
        ok_g, l_global = _read_ptr(kernel32, handle, ptr + HyperionOffsets.L_GLOBAL)
        if not ok_g or not l_global:
            return None
        ok_rf, reg_free = _read_u32(kernel32, handle, l_global + HyperionOffsets.REGISTRY_FREE)
        if not ok_rf:
            return None
        return (reg_free >> b) & 1

    bits: List[int] = []
    for b in (28, 29, 30):
        b1 = _bit(l1, b)
        b2 = _bit(l2, b)
        if b1 is None or b2 is None:
            return {"luau_status": "unavailable", "luau_violations": None, "luau_hex": None, "luau_error": "Failed to read Luau registry flags"}
        bits.append(b1 & b2)

    result = bits[0] | (bits[1] << 1) | (bits[2] << 2)
    luau_status = "clean" if result == 0x7 else "detected"
    return {
        "luau_status": luau_status,
        "luau_violations": result,
        "luau_hex": hex(result),
    }


def _read_process_hyperion_violations(kernel32: Any, pid: int) -> Dict[str, Any]:
    hyperion_base = _get_module_base(kernel32, pid, "RobloxPlayerBeta.dll")
    if not hyperion_base:
        return {
            "pid": pid,
            "status": "unavailable",
            "violations": 0,
            "hex": "0x0",
            "error": "RobloxPlayerBeta.dll not loaded",
        }

    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, int(pid))
    if not handle:
        return {
            "pid": pid,
            "status": "unavailable",
            "violations": 0,
            "hex": "0x0",
            "error": "Failed to open process handle",
        }

    try:
        violation_table = hyperion_base + HyperionOffsets.VIOLATION_TABLE
        ok, index = _read_u8(kernel32, handle, violation_table + HyperionOffsets.VIOLATIONS_INDEX)
        if not ok:
            return {
                "pid": pid,
                "status": "unavailable",
                "violations": 0,
                "hex": "0x0",
                "error": "Failed to read violation index",
            }

        encoded_table = violation_table + (index * 4) + HyperionOffsets.ENCODED_VIOLATIONS
        violations = 0
        for i in range(4):
            ok, value = _read_u8(kernel32, handle, encoded_table + i)
            if not ok:
                return {
                    "pid": pid,
                    "status": "unavailable",
                    "violations": 0,
                    "hex": "0x0",
                    "error": "Failed to read violation bytes",
                }
            value = _rol1(value, 4)
            violations |= (value << (i * 8))

        violations &= 0xFFFFFFFF
        hyperion_status = "clean" if violations == 0 else "detected"
        roblox_base = _get_module_base(kernel32, pid, "RobloxPlayerBeta.exe")
        luau_info = _read_luau_violations(kernel32, handle, roblox_base or 0)
        luau_status = luau_info["luau_status"]

        if hyperion_status == "detected" or luau_status == "detected":
            overall_proc_status = "detected"
        elif hyperion_status == "clean" or luau_status == "clean":
            overall_proc_status = "clean"
        else:
            overall_proc_status = "unavailable"

        return {
            "pid": pid,
            "status": overall_proc_status,
            "violations": violations,
            "hex": hex(violations),
            "hyperion_status": hyperion_status,
            "hyperion_violations": violations,
            "hyperion_hex": hex(violations),
            **luau_info,
        }
    finally:
        kernel32.CloseHandle(handle)


def check_hyperion_violations() -> Dict[str, Any]:
    """Read Hyperion violation status from all running RobloxPlayerBeta.exe processes."""
    if platform.system() != "Windows":
        return {
            "success": True,
            "supported": False,
            "status": "unavailable",
            "violations": 0,
            "hex": "0x0",
            "processes": [],
        }

    pids: List[int] = []
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = str(proc.info.get("name") or "").lower()
                if name == "robloxplayerbeta.exe":
                    pids.append(int(proc.info["pid"]))
            except Exception:
                continue
    except Exception:
        pass

    if not pids:
        return {
            "success": True,
            "supported": True,
            "status": "idle",
            "violations": 0,
            "hex": "0x0",
            "processes": [],
        }

    try:
        kernel32 = _setup_kernel32()
    except Exception:
        return {
            "success": False,
            "supported": True,
            "status": "unavailable",
            "violations": 0,
            "hex": "0x0",
            "processes": [],
            "error": "Failed to initialize Windows API",
        }

    results: List[Dict[str, Any]] = []
    detected_violations = 0
    has_clean = False
    has_detected = False
    luau_detected_hex: Optional[str] = None
    luau_clean_hex: Optional[str] = None

    for pid in pids:
        res = _read_process_hyperion_violations(kernel32, pid)
        results.append(res)
        if res["status"] == "detected":
            has_detected = True
            if detected_violations == 0:
                detected_violations = res["violations"]
        elif res["status"] == "clean":
            has_clean = True

        if res.get("luau_status") == "detected" and luau_detected_hex is None:
            luau_detected_hex = res.get("luau_hex")
        elif res.get("luau_status") == "clean" and luau_clean_hex is None:
            luau_clean_hex = res.get("luau_hex")

    if has_detected:
        overall_status = "detected"
        overall_violations = detected_violations
    elif has_clean:
        overall_status = "clean"
        overall_violations = 0
    else:
        overall_status = "unavailable"
        overall_violations = 0

    if luau_detected_hex is not None:
        overall_luau_status = "detected"
        overall_luau_hex = luau_detected_hex
    elif luau_clean_hex is not None:
        overall_luau_status = "clean"
        overall_luau_hex = luau_clean_hex
    else:
        overall_luau_status = "unavailable"
        overall_luau_hex = None

    return {
        "success": True,
        "supported": True,
        "status": overall_status,
        "violations": overall_violations,
        "hex": hex(overall_violations),
        "luau_status": overall_luau_status,
        "luau_hex": overall_luau_hex,
        "processes": results,
    }

