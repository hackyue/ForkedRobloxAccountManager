import os
import sys
import re
import json
import time
import shutil
import hashlib
import tempfile
import threading
import subprocess
from typing import Dict, List, Any, Optional
import requests
from utils.paths import get_data_folder

class AppUpdaterManager:
    APP_VERSION = "3.0.0"
    PRIMARY_REPO = "hackyue/ForkedRobloxAccountManager"
    DEV_REPO = "hackyue/ForkedRobloxAccountManagerv3"

    def __init__(self):
        self.lock = threading.Lock()
        self.download_thread: Optional[threading.Thread] = None
        self.last_check_time: float = 0.0
        self.cached_check: Optional[Dict[str, Any]] = None
        self.download_state: Dict[str, Any] = {
            "active": False,
            "status": "Idle",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "success": None,
            "error": None,
            "file_path": None,
            "asset_name": ""
        }

    def _parse_version_tuple(self, version_str: Any) -> tuple:
        if not version_str:
            return (0,)
        clean = str(version_str).strip()
        if clean.lower().startswith("v"):
            clean = clean[1:]
        clean = clean.split("-")[0]
        parts = []
        for segment in clean.split("."):
            nums = re.findall(r"\d+", segment)
            if nums:
                parts.append(int(nums[0]))
            else:
                parts.append(0)
        return tuple(parts) if parts else (0,)

    def check_for_updates(
        self,
        force: bool = False,
        include_prereleases: bool = False,
        include_latest: bool = True
    ) -> Dict[str, Any]:
        cache_key = (bool(include_prereleases), bool(include_latest))
        with self.lock:
            now = time.time()
            if not force and self.cached_check and getattr(self, "cached_check_key", None) == cache_key and (now - self.last_check_time < 180):
                return dict(self.cached_check)

        if not include_prereleases and not include_latest:
            result = {
                "success": True,
                "update_available": False,
                "current_version": self.APP_VERSION,
                "latest_version": self.APP_VERSION,
                "release_title": "Update checks disabled",
                "release_notes": "Both pre-release and latest release checks are disabled.",
                "published_at": "",
                "html_url": f"https://github.com/{self.PRIMARY_REPO}",
                "asset_name": "",
                "asset_size": 0,
                "download_url": "",
                "sha256": "",
                "prerelease": False
            }
            with self.lock:
                self.cached_check = result
                self.cached_check_key = cache_key
                self.last_check_time = time.time()
            return result

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "FRAM-Updater"
        }

        release_data = None
        selected_repo = self.PRIMARY_REPO

        for repo in (self.PRIMARY_REPO, self.DEV_REPO):
            if include_prereleases:
                api_url = f"https://api.github.com/repos/{repo}/releases"
                try:
                    resp = requests.get(api_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            for item in data:
                                if not isinstance(item, dict) or item.get("draft"):
                                    continue
                                is_pre = bool(item.get("prerelease", False))
                                if is_pre and include_prereleases:
                                    release_data = item
                                    selected_repo = repo
                                    break
                                elif not is_pre and include_latest:
                                    release_data = item
                                    selected_repo = repo
                                    break
                            if release_data:
                                break
                except Exception:
                    continue
            else:
                api_url = f"https://api.github.com/repos/{repo}/releases/latest"
                try:
                    resp = requests.get(api_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and data.get("tag_name"):
                            release_data = data
                            selected_repo = repo
                            break
                except Exception:
                    continue

        if not release_data:
            result = {
                "success": True,
                "update_available": False,
                "current_version": self.APP_VERSION,
                "latest_version": self.APP_VERSION,
                "release_title": "Up to date",
                "release_notes": "You are currently running the latest version of FRAM.",
                "published_at": "",
                "html_url": f"https://github.com/{self.PRIMARY_REPO}",
                "asset_name": "",
                "asset_size": 0,
                "download_url": "",
                "sha256": "",
                "prerelease": False
            }
            with self.lock:
                self.cached_check = result
                self.cached_check_key = cache_key
                self.last_check_time = time.time()
            return result

        latest_tag = str(release_data.get("tag_name") or "").strip()
        latest_version = latest_tag[1:] if latest_tag.lower().startswith("v") else latest_tag

        current_tuple = self._parse_version_tuple(self.APP_VERSION)
        latest_tuple = self._parse_version_tuple(latest_version)

        update_available = latest_tuple > current_tuple

        assets = release_data.get("assets") or []
        chosen_asset = None

        for a in assets:
            name = str(a.get("name") or "").lower()
            if name.endswith(".exe") and ("setup" in name or "installer" in name):
                chosen_asset = a
                break

        if not chosen_asset:
            for a in assets:
                name = str(a.get("name") or "").lower()
                if name.endswith(".exe"):
                    chosen_asset = a
                    break

        if not chosen_asset:
            for a in assets:
                name = str(a.get("name") or "").lower()
                if name.endswith(".msi") or name.endswith(".zip"):
                    chosen_asset = a
                    break

        asset_name = chosen_asset.get("name") if chosen_asset else ""
        asset_size = chosen_asset.get("size", 0) if chosen_asset else 0
        download_url = chosen_asset.get("browser_download_url") if chosen_asset else ""

        expected_digest = chosen_asset.get("digest") if chosen_asset else None
        expected_sha256 = ""
        if isinstance(expected_digest, str) and expected_digest.lower().startswith("sha256:"):
            expected_sha256 = expected_digest.split(":", 1)[1].strip().lower()

        result = {
            "success": True,
            "update_available": update_available,
            "current_version": self.APP_VERSION,
            "latest_version": latest_version,
            "latest_tag": latest_tag,
            "release_title": release_data.get("name") or latest_tag,
            "release_notes": release_data.get("body") or "",
            "published_at": release_data.get("published_at") or "",
            "html_url": release_data.get("html_url") or f"https://github.com/{selected_repo}",
            "asset_name": asset_name,
            "asset_size": asset_size,
            "download_url": download_url,
            "sha256": expected_sha256,
            "repo": selected_repo,
            "prerelease": bool(release_data.get("prerelease", False))
        }

        with self.lock:
            self.cached_check = result
            self.cached_check_key = cache_key
            self.last_check_time = time.time()

        return result

    def get_all_releases(self, force: bool = False) -> List[Dict[str, Any]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "FRAM-Desktop-App"
        }
        for repo in (self.PRIMARY_REPO, self.DEV_REPO):
            api_url = f"https://api.github.com/repos/{repo}/releases"
            try:
                resp = requests.get(api_url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                continue
        return []

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.download_state)

    def start_download(
        self,
        download_url: Optional[str] = None,
        asset_name: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        total_bytes: Optional[int] = 0
    ) -> Dict[str, Any]:
        with self.lock:
            if self.download_state["active"]:
                return {"success": False, "error": "Download is already in progress"}

            if not download_url:
                check = self.cached_check or self.check_for_updates()
                download_url = check.get("download_url")
                if not download_url:
                    return {"success": False, "error": "No download URL available for the latest release"}

                asset_name = check.get("asset_name") or "FRAM_Update.exe"
                expected_sha256 = check.get("sha256") or ""
                total_bytes = check.get("asset_size") or 0
            else:
                asset_name = asset_name or "FRAM_Update.exe"
                expected_sha256 = expected_sha256 or ""
                total_bytes = total_bytes or 0

            self.download_state = {
                "active": True,
                "status": "Starting download...",
                "progress": 0,
                "downloaded_bytes": 0,
                "total_bytes": total_bytes or 0,
                "success": None,
                "error": None,
                "file_path": None,
                "asset_name": asset_name
            }

        thread = threading.Thread(
            target=self._download_worker,
            args=(download_url, asset_name, expected_sha256),
            daemon=True
        )
        self.download_thread = thread
        thread.start()

        return {"success": True, "message": "Download initiated"}

    def _download_worker(self, download_url: str, asset_name: str, expected_sha256: str) -> None:
        data_dir = get_data_folder()
        suffix = os.path.splitext(asset_name)[1] or ".exe"
        fd, temp_path = tempfile.mkstemp(prefix="fram_update_", suffix=suffix, dir=data_dir)
        os.close(fd)

        headers = {
            "User-Agent": "FRAM-Updater",
            "Accept": "application/octet-stream"
        }

        hasher = hashlib.sha256()

        try:
            with requests.get(download_url, headers=headers, stream=True, timeout=60) as resp:
                resp.raise_for_status()

                total_length = None
                content_len = resp.headers.get("Content-Length")
                if content_len and content_len.isdigit():
                    total_length = int(content_len)

                with self.lock:
                    if total_length:
                        self.download_state["total_bytes"] = total_length
                    self.download_state["status"] = "Downloading update..."

                downloaded = 0
                last_update = 0.0

                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 128):
                        if not chunk:
                            continue
                        f.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_update >= 0.2 or (total_length and downloaded >= total_length):
                            last_update = now
                            with self.lock:
                                self.download_state["downloaded_bytes"] = downloaded
                                if total_length and total_length > 0:
                                    pct = min(100.0, round((downloaded / total_length) * 100, 1))
                                    self.download_state["progress"] = pct
                                    mb_curr = downloaded / (1024 * 1024)
                                    mb_tot = total_length / (1024 * 1024)
                                    self.download_state["status"] = f"Downloading... {mb_curr:.1f} / {mb_tot:.1f} MB ({pct}%)"
                                else:
                                    mb_curr = downloaded / (1024 * 1024)
                                    self.download_state["status"] = f"Downloading... {mb_curr:.1f} MB"

            if expected_sha256:
                actual_sha256 = hasher.hexdigest().lower()
                if actual_sha256 != expected_sha256.lower():
                    raise RuntimeError("Downloaded file failed checksum integrity verification")

            with self.lock:
                self.download_state["active"] = False
                self.download_state["success"] = True
                self.download_state["progress"] = 100.0
                self.download_state["status"] = "Update ready to install"
                self.download_state["file_path"] = temp_path

        except Exception as e:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

            with self.lock:
                self.download_state["active"] = False
                self.download_state["success"] = False
                self.download_state["error"] = str(e)
                self.download_state["status"] = f"Download failed: {e}"

    def apply_update(self) -> Dict[str, Any]:
        with self.lock:
            file_path = self.download_state.get("file_path")
            asset_name = self.download_state.get("asset_name") or ""

        if not file_path or not os.path.isfile(file_path):
            return {"success": False, "error": "No downloaded update file found. Please download the update first."}

        lower_asset = asset_name.lower()
        lower_path = file_path.lower()
        is_setup = (
            "setup" in lower_asset
            or "installer" in lower_asset
            or "nsis" in lower_asset
            or "bundle" in lower_asset
            or lower_path.endswith(".msi")
            or ("setup" in lower_path and lower_path.endswith(".exe"))
            or ("installer" in lower_path and lower_path.endswith(".exe"))
            or ("nsis" in lower_path and lower_path.endswith(".exe"))
        )

        try:
            if is_setup:
                if file_path.lower().endswith(".msi"):
                    subprocess.Popen(["msiexec", "/i", file_path], close_fds=True)
                else:
                    subprocess.Popen([file_path], close_fds=True)
                return {"success": True, "message": "Installer launched. Please complete the installation."}

            parent_pid = os.getppid() if hasattr(os, "getppid") else os.getpid()
            current_pid = os.getpid()

            target_exe = None
            possible_names = ["FRAM.exe", "Forked Account Manager.exe", "forked-account-manager.exe"]
            base_dir = os.path.dirname(sys.executable)
            candidate_dirs = [
                base_dir,
                os.path.dirname(base_dir),
                os.path.dirname(os.path.dirname(base_dir)),
                os.getcwd()
            ]

            for c_dir in candidate_dirs:
                if not c_dir:
                    continue
                for name in possible_names:
                    p = os.path.join(c_dir, name)
                    if os.path.isfile(p):
                        target_exe = p
                        break
                if target_exe:
                    break

            if not target_exe:
                target_exe = sys.executable

            data_dir = get_data_folder()
            bat_path = os.path.join(data_dir, "apply_update.bat")

            bat_content = f"""@echo off
setlocal
set "P1={parent_pid}"
set "P2={current_pid}"
set "SRC={file_path}"
set "TGT={target_exe}"

timeout /t 2 /nobreak >nul

:wait_p1
tasklist /fi "PID eq %P1%" 2>nul | findstr /i "%P1%" >nul
if %ERRORLEVEL% equ 0 (
    timeout /t 1 /nobreak >nul
    goto wait_p1
)

:wait_p2
tasklist /fi "PID eq %P2%" 2>nul | findstr /i "%P2%" >nul
if %ERRORLEVEL% equ 0 (
    timeout /t 1 /nobreak >nul
    goto wait_p2
)

copy /y "%SRC%" "%TGT%" >nul
del /f /q "%SRC%" >nul
start "" "%TGT%"
del /f /q "%~f0" >nul
"""

            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(["cmd.exe", "/c", bat_path], close_fds=True, creationflags=CREATE_NO_WINDOW)

            return {"success": True, "message": "Updater launched. Application will now update and restart."}

        except Exception as e:
            return {"success": False, "error": f"Failed to apply update: {e}"}

updater_manager = AppUpdaterManager()
