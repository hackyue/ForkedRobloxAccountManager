import os
import sys
import re
import json
import uuid
import ctypes
import hashlib
import subprocess
import time
import tempfile
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional

class RobloxSwapManager:
    def __init__(self, data_folder: str):
        self.data_folder = data_folder
        self.backup_path = os.path.join(self.data_folder, "rblxswap_backup.json")
        self.clean_status = {
            "active": False,
            "progress": 0,
            "step": "",
            "logs": []
        }
        self.identifiers = {
            "machineGuid": {
                "hive": "HKLM",
                "key": "SOFTWARE\\Microsoft\\Cryptography",
                "value": "MachineGuid",
                "braces": False,
                "upper": False
            },
            "hwProfileGuid": {
                "hive": "HKLM",
                "key": "SYSTEM\\CurrentControlSet\\Control\\IDConfigDB\\Hardware Profiles\\0001",
                "value": "HwProfileGuid",
                "braces": True,
                "upper": True
            },
            "machineId": {
                "hive": "HKLM",
                "key": "SOFTWARE\\Microsoft\\SQMClient",
                "value": "MachineId",
                "braces": True,
                "upper": True
            }
        }
        self.anticheats = [
            {
                "name": "Riot Vanguard",
                "services": ["vgc", "vgk"],
                "processes": ["vgc", "vgtray"],
                "steps": [
                    "Open Command Prompt as Administrator and run: sc stop vgc",
                    "Disable driver: sc config vgk start= disabled",
                    "Reboot your computer. The vgk kernel driver only unloads on restart",
                    "To play Valorant again later, run: sc config vgk start= system and reboot"
                ]
            },
            {
                "name": "FACEIT AC",
                "services": ["faceit", "faceitac"],
                "processes": ["faceitclient", "faceit"],
                "steps": [
                    "Right-click the FACEIT AC tray icon and choose Exit",
                    "Or run Command Prompt as Admin: sc stop faceit",
                    "Reboot if it remains running"
                ]
            },
            {
                "name": "EasyAntiCheat",
                "services": ["easyanticheat", "easyanticheat_eos"],
                "processes": ["easyanticheat"],
                "steps": [
                    "Run Command Prompt as Administrator: sc stop EasyAntiCheat",
                    "It normally terminates once the game is closed"
                ]
            },
            {
                "name": "BattlEye",
                "services": ["beservice", "bedaisy"],
                "processes": ["beservice"],
                "steps": [
                    "Run Command Prompt as Administrator: sc stop BEService",
                    "It normally terminates once the game is closed"
                ]
            },
            {
                "name": "ESEA",
                "services": ["eseaclient"],
                "processes": ["eseaclient"],
                "steps": [
                    "Exit the ESEA client from the system tray",
                    "Or run Command Prompt as Admin: sc stop ESEAClient"
                ]
            }
        ]

    def _no_window_kwargs(self) -> Dict[str, Any]:
        kwargs = {}
        if sys.platform != "win32":
            return kwargs
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        kwargs["creationflags"] = flags
        startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
        if startupinfo_cls is not None:
            startupinfo = startupinfo_cls()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            kwargs["startupinfo"] = startupinfo
        return kwargs

    def is_elevated(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            try:
                res = subprocess.run(["net", "session"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **self._no_window_kwargs())
                return res.returncode == 0
            except Exception:
                return False

    def _ps_escape(self, val: Any) -> str:
        if val is None:
            return ""
        return str(val).replace("'", "''")

    def _safe_json_loads(self, text: str) -> Any:
        if not text:
            return None
        cleaned = str(text).strip().lstrip('\ufeff')
        if not cleaned:
            return None
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def _run_ps(self, script: str) -> str:
        res = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8-sig",
            errors="replace",
            **self._no_window_kwargs()
        )
        return (res.stdout or "").strip().lstrip('\ufeff')

    def _run_elevated_ps(self, script: str, timeout: int = 120) -> tuple:
        if self.is_elevated():
            out = self._run_ps(script)
            return True, out

        tmp_id = uuid.uuid4().hex
        tmp_out = os.path.join(tempfile.gettempdir(), f"fram_out_{tmp_id}.txt")
        tmp_err = os.path.join(tempfile.gettempdir(), f"fram_err_{tmp_id}.txt")
        esc_out = self._ps_escape(tmp_out)
        esc_err = self._ps_escape(tmp_err)

        child_ps = f"""
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
try {{
    $res = & {{
{script}
    }}
    if ($res -ne $null) {{
        $res | Out-File -FilePath '{esc_out}' -Encoding utf8
    }} else {{
        'OK' | Out-File -FilePath '{esc_out}' -Encoding utf8
    }}
}} catch {{
    ('ERR: ' + $_.Exception.Message) | Out-File -FilePath '{esc_out}' -Encoding utf8
}}
"""
        enc_child = base64.b64encode(child_ps.encode('utf-16le')).decode('ascii')
        parent_ps = f"""
try {{
    Start-Process powershell -ArgumentList '-WindowStyle Hidden -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc_child}' -Verb RunAs -Wait -WindowStyle Hidden
}} catch {{
    ('UAC_ERROR: ' + $_.Exception.Message) | Out-File -FilePath '{esc_err}' -Encoding utf8
}}
"""
        enc_parent = base64.b64encode(parent_ps.encode('utf-16le')).decode('ascii')

        try:
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc_parent],
                capture_output=True,
                text=True,
                timeout=timeout,
                **self._no_window_kwargs()
            )
        except Exception as e:
            self._cleanup_temp_files([tmp_out, tmp_err])
            return False, f"Elevation execution failed: {e}"

        if os.path.exists(tmp_err):
            try:
                with open(tmp_err, "r", encoding="utf-8-sig", errors="replace") as f:
                    err_content = f.read().strip().lstrip('\ufeff')
                self._cleanup_temp_files([tmp_out, tmp_err])
                if "canceled by the user" in err_content.lower() or "operation was canceled" in err_content.lower():
                    return False, "Administrator permissions were denied."
                return False, err_content
            except Exception:
                pass

        if os.path.exists(tmp_out):
            try:
                with open(tmp_out, "r", encoding="utf-8-sig", errors="replace") as f:
                    out_content = f.read().strip().lstrip('\ufeff')
                self._cleanup_temp_files([tmp_out, tmp_err])
                if out_content.startswith("ERR:"):
                    return False, out_content[4:].strip().lstrip('\ufeff')
                return True, out_content
            except Exception:
                pass

        self._cleanup_temp_files([tmp_out, tmp_err])
        return False, "Elevated process did not produce output (UAC prompt may have been canceled)."

    def _cleanup_temp_files(self, paths: List[str]) -> None:
        for p in paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def _reg_read(self, hive: str, key: str, value: str) -> Optional[str]:
        hive_upper = (hive or "").upper()
        if sys.platform == "win32":
            try:
                import winreg
                hive_const = None
                if hive_upper in ("HKLM", "HKEY_LOCAL_MACHINE"):
                    hive_const = winreg.HKEY_LOCAL_MACHINE
                elif hive_upper in ("HKCU", "HKEY_CURRENT_USER"):
                    hive_const = winreg.HKEY_CURRENT_USER
                elif hive_upper in ("HKCR", "HKEY_CLASSES_ROOT"):
                    hive_const = winreg.HKEY_CLASSES_ROOT
                elif hive_upper in ("HKU", "HKEY_USERS"):
                    hive_const = winreg.HKEY_USERS

                if hive_const is not None:
                    try:
                        access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
                        with winreg.OpenKey(hive_const, key, 0, access) as k:
                            val, _ = winreg.QueryValueEx(k, value)
                            if isinstance(val, (list, tuple)):
                                return " ".join(str(v) for v in val)
                            return str(val)
                    except Exception:
                        with winreg.OpenKey(hive_const, key, 0, winreg.KEY_READ) as k:
                            val, _ = winreg.QueryValueEx(k, value)
                            if isinstance(val, (list, tuple)):
                                return " ".join(str(v) for v in val)
                            return str(val)
            except Exception:
                pass

        try:
            res = subprocess.run(
                ["reg", "query", f"{hive}\\{key}", "/v", value],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **self._no_window_kwargs()
            )
            if res.returncode != 0:
                return None
            m = re.search(rf"{re.escape(value)}\s+REG_\w+\s+(.+)", res.stdout or "", re.IGNORECASE)
            return m.group(1).strip() if m else None
        except Exception:
            return None

    def _reg_write(self, hive: str, key: str, value: str, data: str) -> bool:
        res = subprocess.run(
            ["reg", "add", f"{hive}\\{key}", "/v", value, "/t", "REG_SZ", "/d", data, "/f"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self._no_window_kwargs()
        )
        if res.returncode == 0:
            return True
        if hive.upper() in ("HKCU", "HKEY_CURRENT_USER"):
            return False

        script = f"""
reg add "{hive}\\{key}" /v "{value}" /t REG_SZ /d "{data}" /f | Out-Null
if ($LASTEXITCODE -eq 0) {{ 'OK' }} else {{ throw 'Failed reg add' }}
"""
        ok, out = self._run_elevated_ps(script)
        return ok and "OK" in out

    def _reg_delete_key(self, hive: str, key: str) -> bool:
        res = subprocess.run(
            ["reg", "delete", f"{hive}\\{key}", "/f"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self._no_window_kwargs()
        )
        if res.returncode == 0:
            return True
        if hive.upper() in ("HKCU", "HKEY_CURRENT_USER"):
            return False
        if not self.is_elevated():
            script = f"""
reg delete "{hive}\\{key}" /f | Out-Null
if ($LASTEXITCODE -eq 0) {{ 'OK' }} else {{ 'NOT_FOUND' }}
"""
            ok, out = self._run_elevated_ps(script)
            return ok and "OK" in out
        return False

    def generate_guid(self, braces: bool = False, upper: bool = False) -> str:
        g = str(uuid.uuid4())
        if upper:
            g = g.upper()
        return f"{{{g}}}" if braces else g

    def is_valid_guid(self, val: Any) -> bool:
        if not isinstance(val, str):
            return False
        pattern = r"^(\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?)$"
        stripped = val.strip()
        if not re.match(pattern, stripped):
            return False
        if (stripped.startswith("{") and not stripped.endswith("}")) or (stripped.endswith("}") and not stripped.startswith("{")):
            return False
        return True

    def backup_exists(self) -> bool:
        return os.path.exists(self.backup_path)

    def read_backup(self) -> Optional[Dict[str, Any]]:
        if not self.backup_exists():
            return None
        try:
            with open(self.backup_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return None

    def write_backup(self, data: Dict[str, Any]) -> bool:
        try:
            os.makedirs(os.path.dirname(self.backup_path), exist_ok=True)
            with open(self.backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def get_backup_info(self) -> Dict[str, Any]:
        b = self.read_backup()
        if not b:
            return {"exists": False}
        identifiers = b.get("identifiers", {})
        adapters = b.get("adapters", [])
        vol = b.get("volume", {})
        return {
            "exists": True,
            "saved_at": b.get("saved_at"),
            "has": {
                "guids": any(self.is_valid_guid(v) for v in identifiers.values()),
                "mac": len(adapters) > 0,
                "volume": bool(vol and vol.get("sector"))
            },
            "serials": {
                "machine_guid": identifiers.get("machineGuid"),
                "volume": vol.get("serial") if vol else None
            }
        }

    def detect_anticheats(self) -> List[Dict[str, Any]]:
        running = {"services": [], "processes": []}
        script = """
        $svc = @(Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Running' } | Select-Object -ExpandProperty Name)
        $proc = @(Get-Process -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
        ConvertTo-Json -Compress @{ services = @($svc); processes = @($proc) }
        """
        try:
            out = self._run_ps(script)
            if out:
                parsed = self._safe_json_loads(out)
                if isinstance(parsed, dict):
                    raw_services = parsed.get("services", [])
                    if isinstance(raw_services, str):
                        raw_services = [raw_services]
                    elif not isinstance(raw_services, list):
                        raw_services = []

                    raw_processes = parsed.get("processes", [])
                    if isinstance(raw_processes, str):
                        raw_processes = [raw_processes]
                    elif not isinstance(raw_processes, list):
                        raw_processes = []

                    running["services"] = [str(s).lower() for s in raw_services if s]
                    running["processes"] = [str(p).lower() for p in raw_processes if p]
        except Exception:
            pass

        detected = []
        for ac in self.anticheats:
            hit_svc = next((s for s in ac["services"] if s in running["services"]), None)
            hit_proc = next((p for p in ac["processes"] if p in running["processes"]), None)
            if hit_svc or hit_proc:
                detected.append({
                    "name": ac["name"],
                    "service": hit_svc,
                    "process": hit_proc,
                    "steps": ac["steps"]
                })
        return detected

    def get_system_drive(self) -> str:
        return os.environ.get("SystemDrive", "C:").rstrip("\\/")

    def read_volume_serial(self, drive: Optional[str] = None) -> Optional[str]:
        drv = drive or self.get_system_drive()
        if sys.platform == "win32":
            try:
                root_path = f"{drv}\\" if not drv.endswith("\\") else drv
                serial_num = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetVolumeInformationW(
                    root_path, None, 0, ctypes.byref(serial_num), None, None, None, 0
                ):
                    raw_hex = f"{serial_num.value:08X}"
                    return f"{raw_hex[0:4]}-{raw_hex[4:8]}"
            except Exception:
                pass

        script = f"(Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='{self._ps_escape(drv)}'\").VolumeSerialNumber"
        try:
            out = self._run_ps(script).strip().upper()
            if re.match(r"^[0-9A-F]{8}$", out):
                return f"{out[0:4]}-{out[4:8]}"
        except Exception:
            pass
        return None

    def _vsn_offset(self, sector_bytes: bytes) -> Optional[int]:
        if len(sector_bytes) < 512:
            return None
        if sector_bytes[3:7] == b"NTFS":
            return 0x48
        if sector_bytes[0x52:0x57] == b"FAT32":
            return 0x43
        if sector_bytes[0x36:0x39] == b"FAT":
            return 0x27
        return None

    def _is_boot_sector(self, sector_bytes: bytes) -> bool:
        return len(sector_bytes) == 512 and sector_bytes[510] == 0x55 and sector_bytes[511] == 0xAA and self._vsn_offset(sector_bytes) is not None

    def _read_sector(self, drive: Optional[str] = None) -> Optional[bytes]:
        drv = drive or self.get_system_drive()
        script = f"""
        $targetPath = '\\\\.\\{self._ps_escape(drv)}'
        $fs = $null
        try {{
            $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::Read), ([IO.FileShare]::ReadWrite)
            $buf = New-Object byte[] 512
            $total = 0
            while ($total -lt 512) {{
                $n = $fs.Read($buf, $total, 512 - $total)
                if ($n -le 0) {{ break }}
                $total += $n
            }}
            if ($total -lt 512) {{ '' }} else {{ [Convert]::ToBase64String($buf) }}
        }} catch {{
            ''
        }} finally {{
            if ($fs -ne $null) {{ $fs.Dispose() }}
        }}
        """
        try:
            b64 = re.sub(r"\s+", "", self._run_ps(script))
            if not b64:
                return None
            data = base64.b64decode(b64)
            return data if len(data) == 512 else None
        except Exception:
            return None

    def _write_sector(self, sector_bytes: bytes, drive: Optional[str] = None) -> bool:
        if len(sector_bytes) != 512:
            return False
        b64 = base64.b64encode(sector_bytes).decode("ascii")
        drv = drive or self.get_system_drive()
        script = f"""
        $bytes = [Convert]::FromBase64String('{b64}')
        if ($bytes.Length -ne 512) {{ throw 'Invalid length' }}
        $targetPath = '\\\\.\\{self._ps_escape(drv)}'
        $fs = $null
        try {{
            $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::ReadWrite), ([IO.FileShare]::ReadWrite)
            $fs.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
            $fs.Write($bytes, 0, 512)
            $fs.Flush()
            Write-Output 'OK'
        }} finally {{
            if ($fs -ne $null) {{ $fs.Dispose() }}
        }}
        """
        if self.is_elevated():
            out = self._run_ps(script)
            return "OK" in out
        ok, out = self._run_elevated_ps(script)
        return ok and "OK" in out

    def _update_backup_volume_sector(self, drive: str, orig_b64: str, offset: Optional[int] = None) -> None:
        try:
            buf = base64.b64decode(orig_b64)
            b = self.read_backup() or {}
            vol = b.get("volume") or {}
            if not vol.get("sector"):
                vol["drive"] = drive
                vol["serial"] = vol.get("serial") or self.read_volume_serial(drive)
                vol["sector"] = orig_b64
                vol["sector_hash"] = hashlib.sha256(buf).hexdigest()
                vol["offset"] = offset or self._vsn_offset(buf)
                b["volume"] = vol
                self.write_backup(b)
        except Exception:
            pass

    def read_volume_backup(self, drive: Optional[str] = None) -> Dict[str, Any]:
        drv = drive or self.get_system_drive()
        entry = {
            "drive": drv,
            "serial": self.read_volume_serial(drv),
            "sector": None,
            "sector_hash": None,
            "offset": None
        }
        buf = self._read_sector(drv)
        if buf and self._is_boot_sector(buf):
            entry["sector"] = base64.b64encode(buf).decode("ascii")
            entry["sector_hash"] = hashlib.sha256(buf).hexdigest()
            entry["offset"] = self._vsn_offset(buf)
        return entry

    def spoof_volume_serial(self, drive: Optional[str] = None) -> Dict[str, Any]:
        drv = drive or self.get_system_drive()
        raw_hex = os.urandom(4).hex().upper()
        formatted_serial = f"{raw_hex[0:4]}-{raw_hex[4:8]}"
        int_val = int(raw_hex, 16)
        patch_bytes = list(int_val.to_bytes(4, byteorder="little"))

        if self.is_elevated():
            buf = self._read_sector(drv)
            if not buf or not self._is_boot_sector(buf):
                return {"drive": drv, "ok": False, "error": "Not a valid boot sector"}
            offset = self._vsn_offset(buf)
            if offset is None:
                return {"drive": drv, "ok": False, "error": "Unknown volume filesystem"}

            orig_b64 = base64.b64encode(buf).decode("ascii")
            mutable = bytearray(buf)
            mutable[offset:offset+4] = bytes(patch_bytes)
            ok = self._write_sector(bytes(mutable), drv)
            if ok:
                self._update_backup_volume_sector(drv, orig_b64, offset)
                return {"drive": drv, "ok": True, "serial": formatted_serial, "reboot": True}
            return {"drive": drv, "ok": False, "error": "Failed to write raw boot sector"}

        patch_str = ",".join(str(b) for b in patch_bytes)
        script = f"""
$fs = $null
try {{
    $drv = '{self._ps_escape(drv)}'
    $targetPath = '\\\\.\\' + $drv
    $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::ReadWrite), ([IO.FileShare]::ReadWrite)
    $buf = New-Object byte[] 512
    $total = 0
    while ($total -lt 512) {{
        $n = $fs.Read($buf, $total, 512 - $total)
        if ($n -le 0) {{ break }}
        $total += $n
    }}
    if ($total -ne 512 -or $buf[510] -ne 0x55 -or $buf[511] -ne 0xAA) {{
        throw 'Invalid boot sector'
    }}
    $origB64 = [Convert]::ToBase64String($buf)
    $offset = -1
    if ($buf[3] -eq 78 -and $buf[4] -eq 84 -and $buf[5] -eq 70 -and $buf[6] -eq 83) {{
        $offset = 72
    }} elseif ($buf[82] -eq 70 -and $buf[83] -eq 65 -and $buf[84] -eq 84 -and $buf[85] -eq 51 -and $buf[86] -eq 50) {{
        $offset = 67
    }} elseif ($buf[54] -eq 70 -and $buf[55] -eq 65 -and $buf[56] -eq 84) {{
        $offset = 39
    }}
    if ($offset -lt 0) {{
        throw 'Unknown filesystem'
    }}
    $patch = [byte[]]@({patch_str})
    for ($i = 0; $i -lt 4; $i++) {{
        $buf[$offset + $i] = $patch[$i]
    }}
    $fs.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
    $fs.Write($buf, 0, 512)
    $fs.Flush()
    ConvertTo-Json -Compress @{{ ok = $true; orig_b64 = $origB64; offset = $offset }}
}} catch {{
    ConvertTo-Json -Compress @{{ ok = $false; error = $_.Exception.Message }}
}} finally {{
    if ($fs -ne $null) {{ $fs.Dispose() }}
}}
"""
        ok, out = self._run_elevated_ps(script)
        if not ok:
            return {"drive": drv, "ok": False, "error": out}
        try:
            parsed = self._safe_json_loads(out)
            if isinstance(parsed, dict) and parsed.get("ok"):
                if parsed.get("orig_b64"):
                    self._update_backup_volume_sector(drv, parsed["orig_b64"], parsed.get("offset"))
                return {"drive": drv, "ok": True, "serial": formatted_serial, "reboot": True}
            err_msg = parsed.get("error") if isinstance(parsed, dict) else "Sector write failed"
            return {"drive": drv, "ok": False, "error": err_msg or "Sector write failed"}
        except Exception as e:
            return {"drive": drv, "ok": False, "error": str(e)}

    def restore_volume_serial(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        if not entry or not entry.get("sector"):
            return {"drive": entry.get("drive") if entry else None, "restored": False, "reboot": False, "reason": "no-sector"}
        try:
            sector_bytes = base64.b64decode(re.sub(r"\s+", "", entry["sector"]))
        except Exception as e:
            return {"drive": entry.get("drive"), "restored": False, "reboot": False, "reason": f"Corrupt base64: {e}"}

        if not self._is_boot_sector(sector_bytes):
            return {"drive": entry.get("drive"), "restored": False, "reboot": False, "reason": "Backup data is not a valid boot sector"}

        if entry.get("sector_hash") and hashlib.sha256(sector_bytes).hexdigest() != entry["sector_hash"]:
            return {"drive": entry.get("drive"), "restored": False, "reboot": False, "reason": "Integrity hash mismatch"}

        drv = entry.get("drive") or self.get_system_drive()
        ok = self._write_sector(sector_bytes, drv)
        return {"drive": drv, "restored": ok, "reboot": ok, "reason": None if ok else "Write failed"}

    def get_adapters(self) -> List[Dict[str, Any]]:
        script = """
        $ErrorActionPreference = 'SilentlyContinue'
        $a = @(Get-NetAdapter -Physical | Where-Object { $_.MacAddress })
        if ($a.Count -eq 0) {
            $a = @(Get-NetAdapter | Where-Object { $_.MacAddress -and $_.InterfaceDescription -notmatch 'Loopback|Teredo|ISATAP|Tunnel|WAN Miniport|Kernel Debug' })
        }
        ConvertTo-Json -InputObject @($a | Select-Object Name, InterfaceDescription, MacAddress, Status) -Compress
        """
        try:
            out = self._run_ps(script)
            if not out:
                return []
            parsed = self._safe_json_loads(out)
            items = parsed if isinstance(parsed, list) else ([parsed] if isinstance(parsed, dict) else [])
            class_key = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e972-e325-11ce-bfc1-08002be10318}"
            sub_script = f"""
            Get-ChildItem '{class_key}' -ErrorAction SilentlyContinue | ForEach-Object {{
                $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
                if ($p -and $p.DriverDesc) {{
                    [pscustomobject]@{{ DriverDesc = $p.DriverDesc; NetworkAddress = $p.NetworkAddress }}
                }}
            }} | ConvertTo-Json -Compress
            """
            sub_out = self._run_ps(sub_script)
            reg_map = {}
            if sub_out:
                reg_parsed = self._safe_json_loads(sub_out)
                reg_items = reg_parsed if isinstance(reg_parsed, list) else ([reg_parsed] if isinstance(reg_parsed, dict) else [])
                for ri in reg_items:
                    if isinstance(ri, dict):
                        desc = ri.get("DriverDesc")
                        na = ri.get("NetworkAddress")
                        if desc:
                            reg_map[desc] = na

            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                desc = item.get("InterfaceDescription", "")
                result.append({
                    "name": item.get("Name", ""),
                    "description": desc,
                    "mac": item.get("MacAddress", ""),
                    "status": item.get("Status", ""),
                    "spoofed": bool(reg_map.get(desc)),
                    "network_address": reg_map.get(desc)
                })
            return result
        except Exception:
            return []

    def set_network_address(self, adapter_desc: str, mac: str) -> bool:
        if not adapter_desc or not mac:
            return False
        clean_mac = re.sub(r"[-:]", "", mac).upper()
        if not re.match(r"^[0-9A-F]{12}$", clean_mac):
            return False

        script = f"""
        $adapters = Get-ChildItem "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}" -ErrorAction SilentlyContinue | ForEach-Object {{ Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue }} | Where-Object {{ $_.DriverDesc -eq '{self._ps_escape(adapter_desc)}' }}
        if ($adapters) {{
            $target = if ($adapters -is [array]) {{ $adapters[0] }} else {{ $adapters }}
            Set-ItemProperty -Path $target.PSPath -Name "NetworkAddress" -Value "{clean_mac}" -ErrorAction Stop
            Write-Output "SUCCESS"
        }} else {{
            Write-Output "NOT_FOUND"
        }}
        """
        if self.is_elevated():
            out = self._run_ps(script)
        else:
            ok, out = self._run_elevated_ps(script)
            if not ok:
                return False
        return "SUCCESS" in out

    def clear_network_address(self, adapter_desc: str) -> bool:
        if not adapter_desc:
            return False
        script = f"""
        $adapters = Get-ChildItem "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}" -ErrorAction SilentlyContinue | ForEach-Object {{ Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue }} | Where-Object {{ $_.DriverDesc -eq '{self._ps_escape(adapter_desc)}' }}
        if ($adapters) {{
            $target = if ($adapters -is [array]) {{ $adapters[0] }} else {{ $adapters }}
            Remove-ItemProperty -Path $target.PSPath -Name "NetworkAddress" -ErrorAction SilentlyContinue
            Write-Output "SUCCESS"
        }} else {{
            Write-Output "NOT_FOUND"
        }}
        """
        if self.is_elevated():
            out = self._run_ps(script)
        else:
            ok, out = self._run_elevated_ps(script)
            if not ok:
                return False
        return "SUCCESS" in out

    def cycle_adapter(self, adapter_name: str) -> bool:
        if not adapter_name:
            return False
        script = f"""
        Disable-NetAdapter -Name '{self._ps_escape(adapter_name)}' -Confirm:$false -ErrorAction Continue
        Start-Sleep -Milliseconds 800
        Enable-NetAdapter -Name '{self._ps_escape(adapter_name)}' -Confirm:$false -ErrorAction Continue
        Write-Output "SUCCESS"
        """
        if self.is_elevated():
            out = self._run_ps(script)
        else:
            ok, out = self._run_elevated_ps(script)
            if not ok:
                return False
        return "SUCCESS" in out

    def refresh_dhcp(self) -> bool:
        try:
            subprocess.run(["ipconfig", "/release"], capture_output=True, check=False, **self._no_window_kwargs())
            subprocess.run(["ipconfig", "/renew"], capture_output=True, check=False, **self._no_window_kwargs())
            return True
        except Exception:
            return False

    def generate_mac(self, base_mac: Optional[str] = None, mirror_oui: bool = False) -> str:
        if mirror_oui and base_mac:
            clean = re.sub(r"[-:]", "", base_mac).upper()
            if len(clean) >= 6 and re.match(r"^[0-9A-F]{6,12}$", clean):
                first_byte_int = (int(clean[0:2], 16) | 0x02) & 0xFE
                oui_byte0 = f"{first_byte_int:02X}"
                oui = [oui_byte0, clean[2:4], clean[4:6]]
                tail = [f"{b:02X}" for b in os.urandom(3)]
                return "-".join(oui + tail)

        b0 = (os.urandom(1)[0] | 0x02) & 0xFE
        tail = [f"{b:02X}" for b in os.urandom(5)]
        return "-".join([f"{b0:02X}"] + tail)

    def create_system_restore_point(self, desc: str = "FRAM RblxSwap Pre-Spoof") -> Dict[str, Any]:
        clean_desc = desc or "FRAM RblxSwap Pre-Spoof"
        script = f"""
        try {{
            Enable-ComputerRestore -Drive "$env:SystemDrive\\" -ErrorAction SilentlyContinue
            New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore" -Name "SystemRestorePointCreationFrequency" -Value 0 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
            Checkpoint-Computer -Description '{self._ps_escape(clean_desc)}' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop
            Write-Output 'OK'
        }} catch {{
            Write-Output ('ERR: ' + $_.Exception.Message)
        }}
        """
        if self.is_elevated():
            out = self._run_ps(script)
        else:
            ok, out = self._run_elevated_ps(script)
            if not ok:
                return {"ok": False, "message": out or "Administrator permissions denied"}
        if out.startswith("OK"):
            return {"ok": True}
        return {"ok": False, "message": out.replace("ERR:", "").strip() or "System Restore unavailable"}

    def create_backup(self) -> Dict[str, Any]:
        if self.backup_exists():
            return {"created": False, "snapshot": self.read_backup()}

        adapters = self.get_adapters()
        raw_adapters = []
        for a in adapters:
            raw_adapters.append({
                "name": a.get("name"),
                "desc": a.get("description"),
                "mac": a.get("mac"),
                "network_address": a.get("network_address")
            })

        ident_data = {}
        for name, spec in self.identifiers.items():
            ident_data[name] = self._reg_read(spec["hive"], spec["key"], spec["value"])

        snapshot = {
            "saved_at": datetime.now().isoformat(),
            "identifiers": ident_data,
            "adapters": raw_adapters,
            "volume": self.read_volume_backup()
        }
        self.write_backup(snapshot)
        self._anchor_hardware_encryption_guid(ident_data.get("machineGuid"))
        return {"created": True, "snapshot": snapshot}

    def _anchor_hardware_encryption_guid(self, machine_guid: Optional[str] = None):
        if not machine_guid:
            return
        try:
            from classes.encryption import EncryptionConfig
            cfg_path = os.path.join(self.data_folder, "encryption_config.json")
            if os.path.exists(cfg_path):
                enc_cfg = EncryptionConfig(cfg_path)
                if enc_cfg.is_encryption_enabled() and enc_cfg.get_encryption_method() == 'hardware':
                    if not enc_cfg.get_hardware_guid():
                        enc_cfg.set_hardware_guid(machine_guid)
        except Exception:
            pass

    def spoof_identifiers(self, guids: bool = True, volume: bool = False) -> List[Dict[str, Any]]:
        self.create_backup()
        current_guid = self._reg_read("HKLM", "SOFTWARE\\Microsoft\\Cryptography", "MachineGuid")
        if current_guid:
            self._anchor_hardware_encryption_guid(current_guid)
        if self.is_elevated():
            results = []
            if guids:
                for name, spec in self.identifiers.items():
                    val = self.generate_guid(braces=spec["braces"], upper=spec["upper"])
                    ok = self._reg_write(spec["hive"], spec["key"], spec["value"], val)
                    results.append({"name": name, "value": val, "ok": ok})

            if volume:
                vol_res = self.spoof_volume_serial()
                results.append({
                    "name": "volumeSerial",
                    "value": vol_res.get("serial"),
                    "ok": vol_res.get("ok", False),
                    "error": vol_res.get("error"),
                    "reboot": vol_res.get("reboot", False)
                })
            return results

        guid_items = []
        if guids:
            for name, spec in self.identifiers.items():
                val = self.generate_guid(braces=spec["braces"], upper=spec["upper"])
                guid_items.append({
                    "name": name,
                    "hive": spec["hive"],
                    "key": spec["key"],
                    "val_name": spec["value"],
                    "data": val
                })

        vol_data = None
        if volume:
            raw_hex = os.urandom(4).hex().upper()
            formatted_serial = f"{raw_hex[0:4]}-{raw_hex[4:8]}"
            int_val = int(raw_hex, 16)
            patch_bytes = list(int_val.to_bytes(4, byteorder="little"))
            vol_data = {
                "drive": self.get_system_drive(),
                "serial": formatted_serial,
                "patch_bytes": patch_bytes
            }

        ps_lines = [
            "$guidOut = @()",
            "$volOut = $null"
        ]
        for g in guid_items:
            ps_lines.append(f"""
reg add "{g['hive']}\\{g['key']}" /v "{g['val_name']}" /t REG_SZ /d "{g['data']}" /f | Out-Null
$guidOut += [PSCustomObject]@{{ name = '{g['name']}'; value = '{g['data']}'; ok = ($LASTEXITCODE -eq 0) }}
""")
        if vol_data:
            patch_str = ",".join(str(b) for b in vol_data["patch_bytes"])
            ps_lines.append(f"""
$fs = $null
try {{
    $drv = '{self._ps_escape(vol_data['drive'])}'
    $targetPath = '\\\\.\\' + $drv
    $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::ReadWrite), ([IO.FileShare]::ReadWrite)
    $buf = New-Object byte[] 512
    $total = 0
    while ($total -lt 512) {{
        $n = $fs.Read($buf, $total, 512 - $total)
        if ($n -le 0) {{ break }}
        $total += $n
    }}
    if ($total -ne 512 -or $buf[510] -ne 0x55 -or $buf[511] -ne 0xAA) {{
        throw 'Invalid boot sector'
    }}
    $origB64 = [Convert]::ToBase64String($buf)
    $offset = -1
    if ($buf[3] -eq 78 -and $buf[4] -eq 84 -and $buf[5] -eq 70 -and $buf[6] -eq 83) {{
        $offset = 72
    }} elseif ($buf[82] -eq 70 -and $buf[83] -eq 65 -and $buf[84] -eq 84 -and $buf[85] -eq 51 -and $buf[86] -eq 50) {{
        $offset = 67
    }} elseif ($buf[54] -eq 70 -and $buf[55] -eq 65 -and $buf[56] -eq 84) {{
        $offset = 39
    }}
    if ($offset -lt 0) {{
        throw 'Unknown filesystem'
    }}
    $patch = [byte[]]@({patch_str})
    for ($i = 0; $i -lt 4; $i++) {{
        $buf[$offset + $i] = $patch[$i]
    }}
    $fs.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
    $fs.Write($buf, 0, 512)
    $fs.Flush()
    $volOut = [PSCustomObject]@{{ ok = $true; orig_b64 = $origB64; offset = $offset }}
}} catch {{
    $volOut = [PSCustomObject]@{{ ok = $false; error = $_.Exception.Message }}
}} finally {{
    if ($fs -ne $null) {{ $fs.Dispose() }}
}}
""")
        ps_lines.append("""
ConvertTo-Json -Compress @{
    guids = @($guidOut)
    volume = $volOut
}
""")
        ok, out = self._run_elevated_ps("\n".join(ps_lines))
        if not ok:
            err_msg = out or "Elevation denied"
            results = []
            for g in guid_items:
                results.append({"name": g["name"], "value": g["data"], "ok": False, "error": err_msg})
            if vol_data:
                results.append({"name": "volumeSerial", "value": vol_data["serial"], "ok": False, "error": err_msg, "reboot": False})
            return results

        try:
            parsed = self._safe_json_loads(out)
            results = []
            if isinstance(parsed, dict):
                raw_guids = parsed.get("guids", [])
                guid_list = raw_guids if isinstance(raw_guids, list) else ([raw_guids] if isinstance(raw_guids, dict) else [])
                for rg in guid_list:
                    if isinstance(rg, dict):
                        results.append({"name": rg.get("name"), "value": rg.get("value"), "ok": bool(rg.get("ok"))})
                v_info = parsed.get("volume")
                if v_info and isinstance(v_info, dict) and vol_data:
                    if v_info.get("ok"):
                        if v_info.get("orig_b64"):
                            self._update_backup_volume_sector(vol_data["drive"], v_info["orig_b64"], v_info.get("offset"))
                        results.append({"name": "volumeSerial", "value": vol_data["serial"], "ok": True, "reboot": True})
                    else:
                        results.append({"name": "volumeSerial", "value": vol_data["serial"], "ok": False, "error": v_info.get("error") or "Failed sector write", "reboot": False})
            return results
        except Exception as e:
            return [{"name": "spoof", "ok": False, "error": f"Failed parsing elevated output: {e}"}]

    def restore_identifiers(self, guids: bool = True, mac: bool = True, volume: bool = True) -> Dict[str, Any]:
        backup = self.read_backup()
        if not backup:
            return {"ok": False, "reason": "No backup snapshot exists", "errors": ["No backup snapshot exists"]}

        info = self.get_backup_info()
        results = {"identifiers": [], "adapters": [], "volume": None, "errors": []}

        if self.is_elevated():
            if guids:
                for name, spec in self.identifiers.items():
                    orig = backup.get("identifiers", {}).get(name)
                    if not orig or not self.is_valid_guid(orig):
                        results["identifiers"].append({"name": name, "restored": False, "reason": "invalid-or-missing"})
                        continue
                    ok = self._reg_write(spec["hive"], spec["key"], spec["value"], orig)
                    results["identifiers"].append({"name": name, "restored": ok})
                    if not ok:
                        results["errors"].append(f"{name}: failed to write original value")

            if mac:
                for a in backup.get("adapters", []):
                    desc = a.get("desc")
                    name = a.get("name")
                    na = a.get("network_address")
                    try:
                        if na:
                            self.set_network_address(desc, na)
                        else:
                            self.clear_network_address(desc)
                        if name:
                            self.cycle_adapter(name)
                        results["adapters"].append({"name": name or desc, "restored": True})
                    except Exception as e:
                        results["adapters"].append({"name": name or desc, "restored": False, "reason": str(e)})
                        results["errors"].append(f"{name or desc}: {e}")

            if volume and backup.get("volume"):
                vol_res = self.restore_volume_serial(backup["volume"])
                results["volume"] = vol_res
                if not vol_res.get("restored") and vol_res.get("reason") != "no-sector":
                    results["errors"].append(f"Volume: {vol_res.get('reason')}")

            all_clean = len(results["errors"]) == 0
            covered_everything = (
                (guids or not info["has"]["guids"]) and
                (mac or not info["has"]["mac"]) and
                (volume or not info["has"]["volume"])
            )
            if all_clean and covered_everything:
                try:
                    if os.path.exists(self.backup_path):
                        os.remove(self.backup_path)
                except Exception:
                    pass
            return {"ok": all_clean, **results}

        ps_lines = [
            "$guidOut = @()",
            "$adapterOut = @()",
            "$volOut = $null"
        ]

        if guids:
            for name, spec in self.identifiers.items():
                orig = backup.get("identifiers", {}).get(name)
                if orig and self.is_valid_guid(orig):
                    ps_lines.append(f"""
reg add "{spec['hive']}\\{spec['key']}" /v "{spec['value']}" /t REG_SZ /d "{orig}" /f | Out-Null
$guidOut += [PSCustomObject]@{{ name = '{name}'; restored = ($LASTEXITCODE -eq 0) }}
""")
                else:
                    ps_lines.append(f"""
$guidOut += [PSCustomObject]@{{ name = '{name}'; restored = $false; reason = 'invalid-or-missing' }}
""")

        if mac:
            for a in backup.get("adapters", []):
                desc = a.get("desc")
                name = a.get("name")
                na = a.get("network_address")
                if desc:
                    esc_desc = self._ps_escape(desc)
                    if na:
                        clean_na = re.sub(r"[-:]", "", na).upper()
                        act = f'Set-ItemProperty -Path $target.PSPath -Name "NetworkAddress" -Value "{clean_na}" -ErrorAction SilentlyContinue'
                    else:
                        act = 'Remove-ItemProperty -Path $target.PSPath -Name "NetworkAddress" -ErrorAction SilentlyContinue'
                    cyc = f"Disable-NetAdapter -Name '{self._ps_escape(name)}' -Confirm:$false -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800; Enable-NetAdapter -Name '{self._ps_escape(name)}' -Confirm:$false -ErrorAction SilentlyContinue" if name else ""
                    ps_lines.append(f"""
try {{
    $ad = Get-ChildItem "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}" -ErrorAction SilentlyContinue | ForEach-Object {{ Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue }} | Where-Object {{ $_.DriverDesc -eq '{esc_desc}' }}
    if ($ad) {{
        $target = if ($ad -is [array]) {{ $ad[0] }} else {{ $ad }}
        {act}
        {cyc}
        $adapterOut += [PSCustomObject]@{{ name = '{self._ps_escape(name or desc)}'; restored = $true }}
    }} else {{
        $adapterOut += [PSCustomObject]@{{ name = '{self._ps_escape(name or desc)}'; restored = $false; reason = 'not-found' }}
    }}
}} catch {{
    $adapterOut += [PSCustomObject]@{{ name = '{self._ps_escape(name or desc)}'; restored = $false; reason = $_.Exception.Message }}
}}
""")

        if volume and backup.get("volume") and backup["volume"].get("sector"):
            b64_sec = re.sub(r"\s+", "", backup["volume"]["sector"])
            vol_drv = backup["volume"].get("drive") or self.get_system_drive()
            ps_lines.append(f"""
$fs = $null
try {{
    $bytes = [Convert]::FromBase64String('{b64_sec}')
    $targetPath = '\\\\.\\{self._ps_escape(vol_drv)}'
    $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::ReadWrite), ([IO.FileShare]::ReadWrite)
    $fs.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
    $fs.Write($bytes, 0, 512)
    $fs.Flush()
    $volOut = [PSCustomObject]@{{ drive = '{self._ps_escape(vol_drv)}'; restored = $true; reboot = $true }}
}} catch {{
    $volOut = [PSCustomObject]@{{ drive = '{self._ps_escape(vol_drv)}'; restored = $false; reboot = $false; reason = $_.Exception.Message }}
}} finally {{
    if ($fs -ne $null) {{ $fs.Dispose() }}
}}
""")

        ps_lines.append("""
ConvertTo-Json -Compress @{
    identifiers = @($guidOut)
    adapters = @($adapterOut)
    volume = $volOut
}
""")
        ok, out = self._run_elevated_ps("\n".join(ps_lines))
        if not ok:
            return {"ok": False, "reason": out or "Administrator permissions denied", "errors": [out or "Elevation denied"]}

        try:
            parsed = self._safe_json_loads(out)
            if isinstance(parsed, dict):
                raw_guids = parsed.get("identifiers", [])
                guid_list = raw_guids if isinstance(raw_guids, list) else ([raw_guids] if isinstance(raw_guids, dict) else [])
                for g in guid_list:
                    if isinstance(g, dict):
                        r_ok = bool(g.get("restored"))
                        results["identifiers"].append({"name": g.get("name"), "restored": r_ok})
                        if not r_ok:
                            results["errors"].append(f"{g.get('name')}: failed to restore")

                raw_ad = parsed.get("adapters", [])
                ad_list = raw_ad if isinstance(raw_ad, list) else ([raw_ad] if isinstance(raw_ad, dict) else [])
                for a in ad_list:
                    if isinstance(a, dict):
                        a_ok = bool(a.get("restored"))
                        results["adapters"].append({"name": a.get("name"), "restored": a_ok})
                        if not a_ok:
                            results["errors"].append(f"{a.get('name')}: failed to restore adapter")

                if volume and backup.get("volume"):
                    vol_res = parsed.get("volume")
                    if isinstance(vol_res, dict):
                        results["volume"] = vol_res
                        if not vol_res.get("restored") and vol_res.get("reason") != "no-sector":
                            results["errors"].append(f"Volume: {vol_res.get('reason')}")
                    else:
                        results["volume"] = {"drive": backup["volume"].get("drive"), "restored": False, "reboot": False, "reason": "no-sector"}

            all_clean = len(results["errors"]) == 0
            covered_everything = (
                (guids or not info["has"]["guids"]) and
                (mac or not info["has"]["mac"]) and
                (volume or not info["has"]["volume"])
            )
            if all_clean and covered_everything:
                try:
                    if os.path.exists(self.backup_path):
                        os.remove(self.backup_path)
                except Exception:
                    pass
            return {"ok": all_clean, **results}
        except Exception as e:
            return {"ok": False, "reason": f"Failed parsing restore output: {e}", "errors": [str(e)]}

    def spoof_all(
        self,
        guids: bool = True,
        volume: bool = False,
        mac: bool = False,
        all_adapters: bool = False,
        adapter_desc: Optional[str] = None,
        adapter_name: Optional[str] = None,
        custom_mac: Optional[str] = None,
        mirror_oui: bool = True,
        restart: bool = True,
        create_restore_point: bool = False,
        restore_point_desc: str = "FRAM RblxSwap Pre-Spoof"
    ) -> Dict[str, Any]:
        self.create_backup()
        current_guid = self._reg_read("HKLM", "SOFTWARE\\Microsoft\\Cryptography", "MachineGuid")
        if current_guid:
            self._anchor_hardware_encryption_guid(current_guid)
        restore_point_res = None
        if create_restore_point and self.is_elevated():
            restore_point_res = self.create_system_restore_point(restore_point_desc)

        if self.is_elevated():
            h_results = self.spoof_identifiers(guids=guids, volume=volume) if (guids or volume) else []
            m_results = []
            single_mac = None
            if mac:
                if all_adapters:
                    adapters = self.get_adapters()
                    for a in adapters:
                        d = a.get("description")
                        om = a.get("mac")
                        n = a.get("name")
                        nm = custom_mac if (custom_mac and len(adapters) == 1) else self.generate_mac(base_mac=om, mirror_oui=mirror_oui)
                        ok = self.set_network_address(d, nm)
                        if ok and restart and n:
                            self.cycle_adapter(n)
                        m_results.append({"name": n, "desc": d, "mac": nm, "ok": ok})
                else:
                    if adapter_desc:
                        existing_adapters = self.get_adapters()
                        target_a = next((a for a in existing_adapters if a.get("description") == adapter_desc), None)
                        base_m = target_a.get("mac") if target_a else None
                        single_mac = custom_mac or self.generate_mac(base_mac=base_m, mirror_oui=mirror_oui)
                        ok = self.set_network_address(adapter_desc, single_mac)
                        if ok and restart and adapter_name:
                            self.cycle_adapter(adapter_name)
                        m_results.append({"name": adapter_name, "desc": adapter_desc, "mac": single_mac, "ok": ok})
            return {
                "success": True,
                "restore_point": restore_point_res,
                "hwid": h_results,
                "mac": m_results,
                "single_mac": single_mac
            }

        guid_items = []
        if guids:
            for name, spec in self.identifiers.items():
                val = self.generate_guid(braces=spec["braces"], upper=spec["upper"])
                guid_items.append({
                    "name": name,
                    "hive": spec["hive"],
                    "key": spec["key"],
                    "val_name": spec["value"],
                    "data": val
                })

        vol_data = None
        if volume:
            raw_hex = os.urandom(4).hex().upper()
            formatted_serial = f"{raw_hex[0:4]}-{raw_hex[4:8]}"
            int_val = int(raw_hex, 16)
            patch_bytes = list(int_val.to_bytes(4, byteorder="little"))
            vol_data = {
                "drive": self.get_system_drive(),
                "serial": formatted_serial,
                "patch_bytes": patch_bytes
            }

        mac_plan = []
        if mac:
            if all_adapters:
                adapters = self.get_adapters()
                for a in adapters:
                    d = a.get("description")
                    om = a.get("mac")
                    n = a.get("name")
                    nm = custom_mac if (custom_mac and len(adapters) == 1) else self.generate_mac(base_mac=om, mirror_oui=mirror_oui)
                    clean = re.sub(r"[-:]", "", nm).upper()
                    mac_plan.append({"name": n, "desc": d, "mac": nm, "clean_mac": clean})
            elif adapter_desc:
                existing_adapters = self.get_adapters()
                target_a = next((a for a in existing_adapters if a.get("description") == adapter_desc), None)
                base_m = target_a.get("mac") if target_a else None
                nm = custom_mac or self.generate_mac(base_mac=base_m, mirror_oui=mirror_oui)
                clean = re.sub(r"[-:]", "", nm).upper()
                mac_plan.append({"name": adapter_name, "desc": adapter_desc, "mac": nm, "clean_mac": clean})

        ps_lines = [
            "$rpOut = $null",
            "$guidOut = @()",
            "$volOut = $null",
            "$macOut = @()"
        ]

        if create_restore_point:
            ps_lines.append(f"""
try {{
    Enable-ComputerRestore -Drive "$env:SystemDrive\\" -ErrorAction SilentlyContinue
    New-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore" -Name "SystemRestorePointCreationFrequency" -Value 0 -PropertyType DWord -Force -ErrorAction SilentlyContinue | Out-Null
    Checkpoint-Computer -Description '{self._ps_escape(restore_point_desc)}' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop
    $rpOut = [PSCustomObject]@{{ ok = $true }}
}} catch {{
    $rpOut = [PSCustomObject]@{{ ok = $false; message = $_.Exception.Message }}
}}
""")

        for g in guid_items:
            ps_lines.append(f"""
reg add "{g['hive']}\\{g['key']}" /v "{g['val_name']}" /t REG_SZ /d "{g['data']}" /f | Out-Null
$guidOut += [PSCustomObject]@{{ name = '{g['name']}'; value = '{g['data']}'; ok = ($LASTEXITCODE -eq 0) }}
""")

        if vol_data:
            patch_str = ",".join(str(b) for b in vol_data["patch_bytes"])
            ps_lines.append(f"""
$fs = $null
try {{
    $drv = '{self._ps_escape(vol_data['drive'])}'
    $targetPath = '\\\\.\\' + $drv
    $fs = New-Object System.IO.FileStream -ArgumentList $targetPath, ([IO.FileMode]::Open), ([IO.FileAccess]::ReadWrite), ([IO.FileShare]::ReadWrite)
    $buf = New-Object byte[] 512
    $total = 0
    while ($total -lt 512) {{
        $n = $fs.Read($buf, $total, 512 - $total)
        if ($n -le 0) {{ break }}
        $total += $n
    }}
    if ($total -ne 512 -or $buf[510] -ne 0x55 -or $buf[511] -ne 0xAA) {{
        throw 'Invalid boot sector'
    }}
    $origB64 = [Convert]::ToBase64String($buf)
    $offset = -1
    if ($buf[3] -eq 78 -and $buf[4] -eq 84 -and $buf[5] -eq 70 -and $buf[6] -eq 83) {{
        $offset = 72
    }} elseif ($buf[82] -eq 70 -and $buf[83] -eq 65 -and $buf[84] -eq 84 -and $buf[85] -eq 51 -and $buf[86] -eq 50) {{
        $offset = 67
    }} elseif ($buf[54] -eq 70 -and $buf[55] -eq 65 -and $buf[56] -eq 84) {{
        $offset = 39
    }}
    if ($offset -lt 0) {{
        throw 'Unknown filesystem'
    }}
    $patch = [byte[]]@({patch_str})
    for ($i = 0; $i -lt 4; $i++) {{
        $buf[$offset + $i] = $patch[$i]
    }}
    $fs.Seek(0, [IO.SeekOrigin]::Begin) | Out-Null
    $fs.Write($buf, 0, 512)
    $fs.Flush()
    $volOut = [PSCustomObject]@{{ ok = $true; orig_b64 = $origB64; offset = $offset }}
}} catch {{
    $volOut = [PSCustomObject]@{{ ok = $false; error = $_.Exception.Message }}
}} finally {{
    if ($fs -ne $null) {{ $fs.Dispose() }}
}}
""")

        for mp in mac_plan:
            esc_d = self._ps_escape(mp["desc"])
            esc_n = self._ps_escape(mp["name"] or "")
            clean_m = mp["clean_mac"]
            cyc = f"Disable-NetAdapter -Name '{esc_n}' -Confirm:$false -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800; Enable-NetAdapter -Name '{esc_n}' -Confirm:$false -ErrorAction SilentlyContinue" if (restart and mp["name"]) else ""
            ps_lines.append(f"""
try {{
    $ad = Get-ChildItem "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{{4d36e972-e325-11ce-bfc1-08002be10318}}" -ErrorAction SilentlyContinue | ForEach-Object {{ Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue }} | Where-Object {{ $_.DriverDesc -eq '{esc_d}' }}
    if ($ad) {{
        $target = if ($ad -is [array]) {{ $ad[0] }} else {{ $ad }}
        Set-ItemProperty -Path $target.PSPath -Name "NetworkAddress" -Value "{clean_m}" -ErrorAction Stop
        {cyc}
        $macOut += [PSCustomObject]@{{ name = '{esc_n}'; desc = '{esc_d}'; mac = '{mp['mac']}'; ok = $true }}
    }} else {{
        $macOut += [PSCustomObject]@{{ name = '{esc_n}'; desc = '{esc_d}'; mac = '{mp['mac']}'; ok = $false; error = 'not-found' }}
    }}
}} catch {{
    $macOut += [PSCustomObject]@{{ name = '{esc_n}'; desc = '{esc_d}'; mac = '{mp['mac']}'; ok = $false; error = $_.Exception.Message }}
}}
""")

        ps_lines.append("""
ConvertTo-Json -Compress @{
    restore_point = $rpOut
    guids = @($guidOut)
    volume = $volOut
    mac = @($macOut)
}
""")
        ok, out = self._run_elevated_ps("\n".join(ps_lines))
        if not ok:
            return {"success": False, "error": out or "Administrator permissions denied"}

        try:
            parsed = self._safe_json_loads(out)
            h_results = []
            if isinstance(parsed, dict):
                raw_guids = parsed.get("guids", [])
                guid_list = raw_guids if isinstance(raw_guids, list) else ([raw_guids] if isinstance(raw_guids, dict) else [])
                for rg in guid_list:
                    if isinstance(rg, dict):
                        h_results.append({"name": rg.get("name"), "value": rg.get("value"), "ok": bool(rg.get("ok"))})
                v_info = parsed.get("volume")
                if v_info and isinstance(v_info, dict) and vol_data:
                    if v_info.get("ok"):
                        if v_info.get("orig_b64"):
                            self._update_backup_volume_sector(vol_data["drive"], v_info["orig_b64"], v_info.get("offset"))
                        h_results.append({"name": "volumeSerial", "value": vol_data["serial"], "ok": True, "reboot": True})
                    else:
                        h_results.append({"name": "volumeSerial", "value": vol_data["serial"], "ok": False, "error": v_info.get("error") or "Failed sector write", "reboot": False})

                m_results = []
                raw_mac = parsed.get("mac", [])
                mac_list = raw_mac if isinstance(raw_mac, list) else ([raw_mac] if isinstance(raw_mac, dict) else [])
                for rm in mac_list:
                    if isinstance(rm, dict):
                        m_results.append({
                            "name": rm.get("name"),
                            "desc": rm.get("desc"),
                            "mac": rm.get("mac"),
                            "ok": bool(rm.get("ok")),
                            "error": rm.get("error")
                        })

                single_mac = m_results[0].get("mac") if len(m_results) == 1 else None
                return {
                    "success": True,
                    "restore_point": parsed.get("restore_point"),
                    "hwid": h_results,
                    "mac": m_results,
                    "single_mac": single_mac
                }
            return {"success": False, "error": "Invalid response format from elevated script"}
        except Exception as e:
            return {"success": False, "error": f"Failed parsing elevated output: {e}"}

    def _discover_all_bootstrappers(self, local_app_data: Optional[str] = None, app_data: Optional[str] = None) -> List[Dict[str, Any]]:
        bootstrappers = []
        seen_roots = set()

        def add_bootstrapper(name: str, root_dir: str, version_dirs: List[str]):
            if not root_dir or not os.path.isdir(root_dir):
                return
            norm = os.path.normcase(os.path.normpath(root_dir))
            if norm in seen_roots:
                return
            seen_roots.add(norm)
            bootstrappers.append({
                "name": name,
                "root": root_dir,
                "version_dirs": version_dirs
            })

        known_configs = [
            ("Bloxstrap", ["Versions"]),
            ("Fishstrap", ["Versions"]),
            ("Voidstrap", ["RblxVersions", "Versions"]),
            ("FrostStrap", ["Versions"]),
            ("ExploitStrap", ["Versions"]),
            ("NovaStrap", ["Versions"]),
        ]

        if local_app_data:
            for b_name, v_dirs in known_configs:
                target_p = os.path.join(local_app_data, b_name)
                if os.path.isdir(target_p):
                    add_bootstrapper(b_name, target_p, v_dirs)

        if app_data:
            for b_name, v_dirs in known_configs:
                target_p = os.path.join(app_data, b_name)
                if os.path.isdir(target_p):
                    add_bootstrapper(b_name, target_p, v_dirs)

        search_roots = []
        for env_key in ('LOCALAPPDATA', 'APPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
            path_val = os.getenv(env_key)
            if path_val and os.path.isdir(path_val):
                search_roots.append(path_val)

        for s_root in search_roots:
            try:
                for entry in os.scandir(s_root):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    low_name = entry.name.lower()
                    if low_name in ('roblox', 'temp', 'microsoft', 'windows', 'system32', 'common files', 'packages'):
                        continue

                    v_dirs_found = []
                    for v_sub in ('Versions', 'RblxVersions', 'versions', 'rblxversions'):
                        v_full = os.path.join(entry.path, v_sub)
                        if os.path.isdir(v_full):
                            v_dirs_found.append(v_sub)

                    is_roblox_strap = False
                    if v_dirs_found:
                        for vd in v_dirs_found:
                            v_full = os.path.join(entry.path, vd)
                            try:
                                for sub_item in os.scandir(v_full):
                                    if sub_item.is_dir(follow_symlinks=False):
                                        if sub_item.name.startswith("version-"):
                                            is_roblox_strap = True
                                            break
                                        if os.path.isfile(os.path.join(sub_item.path, 'RobloxPlayerBeta.exe')) or os.path.isfile(os.path.join(sub_item.path, 'RobloxPlayerLauncher.exe')):
                                            is_roblox_strap = True
                                            break
                            except Exception:
                                pass
                            if is_roblox_strap:
                                break

                    if not is_roblox_strap and (low_name.endswith("strap") or "blox" in low_name):
                        try:
                            for root_file in os.scandir(entry.path):
                                if root_file.is_file(follow_symlinks=False):
                                    fn = root_file.name.lower()
                                    if fn.endswith('.exe') and ('blox' in fn or 'roblox' in fn or fn.startswith('fish') or fn.startswith('void') or fn.startswith('frost')):
                                        is_roblox_strap = True
                                        break
                        except Exception:
                            pass

                    if is_roblox_strap:
                        add_bootstrapper(
                            entry.name,
                            entry.path,
                            v_dirs_found if v_dirs_found else ["Versions", "RblxVersions"]
                        )
            except Exception:
                pass

        return bootstrappers

    def terminate_roblox_processes(self) -> List[str]:
        terminated = []
        process_names = [
            "RobloxPlayerBeta.exe",
            "RobloxPlayerLauncher.exe",
            "RobloxStudioBeta.exe",
            "RobloxCrashHandler.exe",
            "Bloxstrap.exe",
            "Fishstrap.exe",
            "Voidstrap.exe",
            "FrostStrap.exe",
            "ExploitStrap.exe",
            "NovaStrap.exe"
        ]

        local_app_data = os.environ.get("LOCALAPPDATA")
        discovered = self._discover_all_bootstrappers(local_app_data)
        for b in discovered:
            b_name = b["name"]
            process_names.append(f"{b_name}.exe")
            if os.path.isdir(b.get("root", "")):
                try:
                    for f in os.scandir(b["root"]):
                        if f.is_file(follow_symlinks=False) and f.name.lower().endswith(".exe"):
                            process_names.append(f.name)
                except Exception:
                    pass

        target_names = {name.lower() for name in process_names}
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    if pname in target_names or (pname.startswith('roblox') and pname.endswith('.exe')):
                        proc.kill()
                        terminated.append(proc.info.get('name') or pname)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            if terminated:
                return list(dict.fromkeys(terminated))
        except Exception:
            pass

        for name in dict.fromkeys(process_names):
            try:
                res = subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, text=True, **self._no_window_kwargs())
                if res.returncode == 0:
                    terminated.append(name)
            except Exception:
                pass
        return list(dict.fromkeys(terminated))

    def _collect_files(self, root_dir: str, regex_pattern: str, max_depth: int = 5, current_depth: int = 0) -> List[str]:
        if current_depth > max_depth or not os.path.exists(root_dir):
            return []
        matches = []
        matcher = re.compile(regex_pattern, re.IGNORECASE)
        try:
            with os.scandir(root_dir) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            if matcher.match(entry.name):
                                matches.append(entry.path)
                        elif entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                            matches.extend(self._collect_files(entry.path, regex_pattern, max_depth, current_depth + 1))
                    except Exception:
                        pass
        except Exception:
            pass
        return matches

    def _remove_path(self, target_path: str) -> bool:
        if not target_path or not os.path.exists(target_path):
            return False
        try:
            if os.path.isdir(target_path):
                import shutil
                shutil.rmtree(target_path, ignore_errors=True)
            else:
                os.remove(target_path)
            return True
        except Exception:
            return False

    def clean_traces(
        self,
        preserve_settings: bool = True,
        preserve_fastflags: bool = False,
        preserve_app_settings: bool = True,
        delete_studio: bool = False,
        purge_auth: bool = True,
        weblauncher_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        logs = []
        def set_progress(pct: int, msg: str):
            self.clean_status = {
                "active": pct < 100,
                "progress": pct,
                "step": msg,
                "logs": list(logs)
            }

        try:
            set_progress(5, "Scanning and safeguarding settings...")
            local_app_data = os.environ.get("LOCALAPPDATA")
            app_data = os.environ.get("APPDATA")
            temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
            program_data = os.environ.get("PROGRAMDATA")
            user_profile = os.environ.get("USERPROFILE")

            logs.append({"level": "info", "msg": "Initiating Roblox trace cleanup and session purge"})

            preserved_settings = []
            if preserve_settings and local_app_data:
                roots = [os.path.join(local_app_data, "Roblox")]
                if app_data:
                    roots.append(os.path.join(app_data, "Roblox"))
                all_paths = []
                for r in roots:
                    all_paths.extend(self._collect_files(r, r"^Global(Basic)?Settings(_\d+)?\.xml$", 6))
                direct_gbs = os.path.join(local_app_data, "Roblox", "GlobalBasicSettings_13.xml")
                if os.path.exists(direct_gbs) and direct_gbs not in all_paths:
                    all_paths.append(direct_gbs)
                for p in set(all_paths):
                    try:
                        with open(p, "rb") as f:
                            preserved_settings.append({"path": p, "data": f.read()})
                    except Exception:
                        pass
                if preserved_settings:
                    logs.append({"level": "info", "msg": f"Safeguarded {len(preserved_settings)} Global Client Settings file(s)"})
            elif not preserve_settings and local_app_data:
                roots = [os.path.join(local_app_data, "Roblox")]
                if app_data:
                    roots.append(os.path.join(app_data, "Roblox"))
                for r in roots:
                    if os.path.exists(r):
                        for p in self._collect_files(r, r"^Global(Basic)?Settings(_\d+)?\.xml$", 6):
                            if self._remove_path(p):
                                logs.append({"level": "success", "msg": f"Cleaned Global Client Settings: {os.path.basename(p)}"})

            discovered_bootstrappers = self._discover_all_bootstrappers(local_app_data, app_data)

            preserved_fflags = []
            if preserve_fastflags and local_app_data:
                launcher_roots = [b["root"] for b in discovered_bootstrappers if os.path.isdir(b.get("root", ""))]
                if weblauncher_dir and os.path.isdir(weblauncher_dir):
                    launcher_roots.append(weblauncher_dir)
                all_ff = []
                for r in launcher_roots:
                    all_ff.extend(self._collect_files(r, r"^Client(Settings|AppSettings)\.json$", 6))
                for p in set(all_ff):
                    try:
                        with open(p, "rb") as f:
                            preserved_fflags.append({"path": p, "data": f.read()})
                    except Exception:
                        pass
                if preserved_fflags:
                    logs.append({"level": "info", "msg": f"Safeguarded {len(preserved_fflags)} FastFlags configuration file(s)"})

            preserved_app_settings = []
            if preserve_app_settings and local_app_data:
                app_storage_path = os.path.join(local_app_data, "Roblox", "LocalStorage", "appStorage.json")
                if os.path.exists(app_storage_path):
                    try:
                        with open(app_storage_path, "rb") as f:
                            preserved_app_settings.append({"path": app_storage_path, "data": f.read()})
                        logs.append({"level": "info", "msg": "Safeguarded Roblox App Settings (appStorage.json)"})
                    except Exception:
                        pass

            set_progress(20, "Checking for active Roblox client processes...")
            terminated = self.terminate_roblox_processes()
            if terminated:
                logs.append({"level": "success", "msg": f"Terminated {len(terminated)} active Roblox process(es): {', '.join(terminated)}"})
                time.sleep(1.0)
            else:
                logs.append({"level": "info", "msg": "No active Roblox client processes were running"})

            set_progress(35, "Cleaning LocalAppData and launcher versions...")
            for b in discovered_bootstrappers:
                b_name = b["name"]
                b_root = b.get("root", "")
                if b_root and os.path.exists(b_root):
                    for sub in ["Logs", "Downloads", "Cache", "Temp", "logs", "downloads", "cache"]:
                        sp = os.path.join(b_root, sub)
                        if self._remove_path(sp):
                            logs.append({"level": "success", "msg": f"Cleaned {b_name} / {sub}"})

                    for v_dir_name in b.get("version_dirs", ["Versions", "RblxVersions"]):
                        v_dir = os.path.join(b_root, v_dir_name)
                        if os.path.exists(v_dir):
                            try:
                                for item in os.listdir(v_dir):
                                    vf = os.path.join(v_dir, item)
                                    is_studio = os.path.isdir(vf) and (os.path.exists(os.path.join(vf, "RobloxStudioBeta.exe")) or os.path.exists(os.path.join(vf, "RobloxStudioLauncherBeta.exe")))
                                    if not delete_studio and is_studio:
                                        logs.append({"level": "info", "msg": f"Preserved Studio directory in {b_name}: {item}"})
                                    else:
                                        if self._remove_path(vf):
                                            logs.append({"level": "success", "msg": f"Removed {b_name} version: {item}"})
                            except Exception:
                                pass

            if local_app_data:
                target_local_roblox = os.path.join(local_app_data, "Roblox")
                if os.path.exists(target_local_roblox):
                    v_dir = os.path.join(target_local_roblox, "Versions")
                    if os.path.exists(v_dir):
                        try:
                            for item in os.listdir(v_dir):
                                vf = os.path.join(v_dir, item)
                                is_studio = os.path.isdir(vf) and (os.path.exists(os.path.join(vf, "RobloxStudioBeta.exe")) or os.path.exists(os.path.join(vf, "RobloxStudioLauncherBeta.exe")))
                                if not delete_studio and is_studio:
                                    logs.append({"level": "info", "msg": f"Preserved Roblox Studio: {item}"})
                                else:
                                    if self._remove_path(vf):
                                        logs.append({"level": "success", "msg": f"Cleaned version: {item}"})
                        except Exception:
                            pass
                    for sub in ["Downloads", "Logs", "logs", "Analytics", "analytics", "rbxcache", "HttpCache", "httpcache", "CrashDumps", "crashdumps"]:
                        sp = os.path.join(target_local_roblox, sub)
                        if self._remove_path(sp):
                            logs.append({"level": "success", "msg": f"Cleaned LocalAppData Roblox / {sub}"})

            set_progress(55, "Cleaning Roaming AppData and caches...")
            if app_data:
                roaming_roblox = os.path.join(app_data, "Roblox")
                if os.path.exists(roaming_roblox):
                    for sub in ["logs", "http"]:
                        if self._remove_path(os.path.join(roaming_roblox, sub)):
                            logs.append({"level": "success", "msg": f"Cleaned Roaming Roblox / {sub}"})

            set_progress(70, "Purging Prefetch artifacts and registry entries...")
            system_root = os.environ.get("SystemRoot", "C:\\Windows")
            prefetch_dir = os.path.join(system_root, "Prefetch")
            prefetch_prefixes = [
                "ROBLOXPLAYERBETA.EXE-",
                "ROBLOXCRASHHANDLER.EXE-",
                "ROBLOXPLAYERLAUNCHER.EXE-",
                "BLOXSTRAP.EXE-",
                "FISHSTRAP.EXE-",
                "VOIDSTRAP.EXE-",
                "FROSTSTRAP.EXE-",
                "EXPLOITSTRAP.EXE-",
                "NOVASTRAP.EXE-"
            ]
            for b in discovered_bootstrappers:
                prefetch_prefixes.append(f"{b['name'].upper()}.EXE-")
                if os.path.isdir(b.get("root", "")):
                    try:
                        for f in os.scandir(b["root"]):
                            if f.is_file(follow_symlinks=False) and f.name.lower().endswith(".exe"):
                                prefetch_prefixes.append(f"{f.name.upper()}-")
                    except Exception:
                        pass

            prefetch_prefixes = list(dict.fromkeys(prefetch_prefixes))

            if os.path.exists(prefetch_dir):
                try:
                    for fn in os.listdir(prefetch_dir):
                        upper_fn = fn.upper()
                        if upper_fn.endswith(".PF") and any(upper_fn.startswith(pfx) for pfx in prefetch_prefixes):
                            if self._remove_path(os.path.join(prefetch_dir, fn)):
                                logs.append({"level": "success", "msg": f"Deleted Prefetch artifact: {fn}"})
                except Exception:
                    pass

            if self._reg_delete_key("HKCU", "Software\\ROBLOX Corporation"):
                logs.append({"level": "success", "msg": "Removed HKCU\\Software\\ROBLOX Corporation"})
            if self._reg_delete_key("HKCU", "Software\\Roblox"):
                logs.append({"level": "success", "msg": "Removed HKCU\\Software\\Roblox"})
            for b in discovered_bootstrappers:
                b_reg = f"Software\\{b['name']}"
                if self._reg_delete_key("HKCU", b_reg):
                    logs.append({"level": "success", "msg": f"Removed HKCU\\{b_reg}"})

            set_progress(82, "Clearing temporary files and LocalStorage session data...")
            if temp_dir and os.path.exists(temp_dir):
                self._remove_path(os.path.join(temp_dir, "Roblox"))
                self._remove_path(os.path.join(temp_dir, "RobloxLogs"))
                try:
                    for fn in os.listdir(temp_dir):
                        if fn.startswith("Roblox"):
                            self._remove_path(os.path.join(temp_dir, fn))
                except Exception:
                    pass
                logs.append({"level": "success", "msg": "Cleared Temp folder Roblox caches"})

            if program_data:
                self._remove_path(os.path.join(program_data, "Roblox"))

            if purge_auth and user_profile:
                r_local = os.path.join(user_profile, "AppData", "Local", "Roblox")
                if os.path.exists(r_local):
                    ls = os.path.join(r_local, "LocalStorage")
                    if self._remove_path(ls):
                        logs.append({"level": "success", "msg": "Purged LocalStorage authentication session data"})
                    lg = os.path.join(r_local, "logs")
                    if self._remove_path(lg):
                        logs.append({"level": "success", "msg": "Purged telemetry logs"})

            if weblauncher_dir and os.path.isdir(weblauncher_dir):
                norm_w = os.path.normpath(weblauncher_dir).lower()
                sys_drive = self.get_system_drive().lower()
                sys_root = os.environ.get("SystemRoot", "C:\\Windows").lower()
                u_prof = (user_profile or "").lower()
                is_safe_dir = (
                    norm_w not in (sys_drive, f"{sys_drive}\\", "c:", "c:\\") and
                    not norm_w.startswith(sys_root) and
                    norm_w != u_prof and
                    ("roblox" in norm_w or "version-" in norm_w or any(b["name"].lower() in norm_w for b in discovered_bootstrappers))
                )
                if is_safe_dir:
                    for d in ["content", "ExtraContent", "PlatformContent", "RobloxPlayerBeta.exe.WebView2", "shaders", "ssl", "WebView2RuntimeInstaller", "Logs", "logs", "Temp", "temp", "CrashDumps", "crashdumps", "rbxcache", "HttpCache", "httpcache"]:
                        self._remove_path(os.path.join(weblauncher_dir, d))
                    for f in ["RobloxCrashHandler.exe", "RobloxPlayerBeta.dll", "RobloxPlayerBeta.exe", "WebView2Loader.dll"]:
                        self._remove_path(os.path.join(weblauncher_dir, f))
                    logs.append({"level": "success", "msg": f"Cleaned WebLauncher directory at {weblauncher_dir}"})

            set_progress(94, "Restoring preserved user configurations...")
            for item in preserved_settings:
                try:
                    os.makedirs(os.path.dirname(item["path"]), exist_ok=True)
                    with open(item["path"], "wb") as f:
                        f.write(item["data"])
                    logs.append({"level": "success", "msg": f"Restored Global Client Settings: {os.path.basename(item['path'])}"})
                except Exception as e:
                    logs.append({"level": "warn", "msg": f"Failed restoring Global Client Settings {os.path.basename(item['path'])}: {e}"})

            for item in preserved_fflags:
                try:
                    os.makedirs(os.path.dirname(item["path"]), exist_ok=True)
                    with open(item["path"], "wb") as f:
                        f.write(item["data"])
                    logs.append({"level": "success", "msg": f"Restored FastFlags: {os.path.basename(item['path'])}"})
                except Exception as e:
                    logs.append({"level": "warn", "msg": f"Failed restoring FastFlags {os.path.basename(item['path'])}: {e}"})

            for item in preserved_app_settings:
                try:
                    os.makedirs(os.path.dirname(item["path"]), exist_ok=True)
                    with open(item["path"], "wb") as f:
                        f.write(item["data"])
                    logs.append({"level": "success", "msg": f"Restored App Settings: {os.path.basename(item['path'])}"})
                except Exception as e:
                    logs.append({"level": "warn", "msg": f"Failed restoring App Settings {os.path.basename(item['path'])}: {e}"})

            logs.append({"level": "success", "msg": "Roblox trace cleanup completed successfully"})
            set_progress(100, "Roblox trace cleanup completed")
            return {"success": True, "logs": logs}
        except Exception as e:
            logs.append({"level": "error", "msg": f"Cleanup encountered an error: {e}"})
            self.clean_status = {
                "active": False,
                "progress": 100,
                "step": f"Error: {e}",
                "logs": list(logs)
            }
            return {"success": False, "error": str(e), "logs": logs}
