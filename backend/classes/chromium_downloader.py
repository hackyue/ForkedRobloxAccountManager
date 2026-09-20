import os
import sys
import json
import time
import shutil
import zipfile
import platform
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from utils.paths import get_data_folder

CHROME_FOR_TESTING_DOWNLOADS_URL = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"

class ChromiumDownloaderManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.download_thread: Optional[threading.Thread] = None
        self.download_state: Dict[str, Any] = {
            "active": False,
            "status": "Idle",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "success": None,
            "error": None,
            "version": ""
        }

    def get_root_path(self) -> Path:
        return Path(get_data_folder()) / "browser_automation" / "chromium"

    def get_binary_path(self) -> Optional[Path]:
        root = self.get_root_path()
        candidates = [
            root / "chrome-win64" / "chrome.exe",
            root / "chrome-win32" / "chrome.exe",
            root / "chrome-win" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        try:
            for candidate in sorted(root.glob("chrome-*/chrome.exe")):
                if candidate.is_file():
                    return candidate
        except OSError:
            return None
        return None

    def get_driver_path(self) -> Optional[Path]:
        root = self.get_root_path()
        candidates = [
            root / "chromedriver-win64" / "chromedriver.exe",
            root / "chromedriver-win32" / "chromedriver.exe",
            root / "chromedriver-win" / "chromedriver.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        try:
            for candidate in sorted(root.glob("chromedriver-*/chromedriver.exe")):
                if candidate.is_file():
                    return candidate
        except OSError:
            return None
        return None

    def get_installed_version(self) -> str:
        root = self.get_root_path()
        manifest_path = root / "managed_chromium.json"
        if not manifest_path.is_file():
            return ""
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return str(data.get("version") or "").strip()
        except (OSError, json.JSONDecodeError):
            return ""
        return ""

    def is_installed(self) -> bool:
        binary = self.get_binary_path()
        driver = self.get_driver_path()
        return binary is not None and driver is not None

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            state_copy = dict(self.download_state)
        
        installed = self.is_installed()
        version = self.get_installed_version()
        binary_path = str(self.get_binary_path()) if self.get_binary_path() else ""
        driver_path = str(self.get_driver_path()) if self.get_driver_path() else ""

        return {
            "installed": installed,
            "version": version,
            "binary_path": binary_path,
            "driver_path": driver_path,
            "downloading": state_copy.get("active", False),
            "status_text": state_copy.get("status", "Idle"),
            "progress": state_copy.get("progress", 0),
            "downloaded_bytes": state_copy.get("downloaded_bytes", 0),
            "total_bytes": state_copy.get("total_bytes", 0),
            "success": state_copy.get("success"),
            "error": state_copy.get("error")
        }

    def _get_platform_key(self) -> str:
        if platform.system() != "Windows":
            raise RuntimeError("Managed Chromium download is currently only supported on Windows.")
        arch = platform.architecture()[0]
        machine = platform.machine().lower()
        if "64" in arch or "64" in machine:
            return "win64"
        return "win32"

    def _select_download_url(self, downloads: Any, asset_name: str, platform_key: str) -> str:
        if not isinstance(downloads, dict):
            raise RuntimeError("Invalid download entries in Chromium manifest.")
        entries = downloads.get(asset_name)
        if not isinstance(entries, list):
            raise RuntimeError(f"Manifest missing download entries for {asset_name}.")
        for entry in entries:
            if isinstance(entry, dict) and entry.get("platform") == platform_key:
                url = entry.get("url")
                if url:
                    return str(url)
        raise RuntimeError(f"No {asset_name} download found for {platform_key}.")

    def _download_file(self, session: requests.Session, url: str, target_path: Path, description: str, weight: float, start_prog: float) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        last_update = 0.0

        try:
            with session.get(url, stream=True, timeout=90) as response:
                response.raise_for_status()
                total_bytes = int(response.headers.get("Content-Length") or 0)
                downloaded_bytes = 0
                with temp_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        now = time.time()
                        if now - last_update >= 0.25:
                            last_update = now
                            fraction = (downloaded_bytes / total_bytes) if total_bytes > 0 else 0
                            prog = int(start_prog + fraction * weight)
                            if total_bytes > 0:
                                status = f"Downloading {description} ({downloaded_bytes / (1024 * 1024):.1f} / {total_bytes / (1024 * 1024):.1f} MB)..."
                            else:
                                status = f"Downloading {description} ({downloaded_bytes / (1024 * 1024):.1f} MB)..."
                            with self.lock:
                                self.download_state["status"] = status
                                self.download_state["progress"] = min(prog, 95)
                                self.download_state["downloaded_bytes"] = downloaded_bytes
                                self.download_state["total_bytes"] = total_bytes
                temp_path.replace(target_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _extract_zip(self, archive_path: Path, target_dir: Path, description: str) -> None:
        resolved_target_dir = target_dir.resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                resolved_member_path = (target_dir / member.filename).resolve()
                try:
                    resolved_member_path.relative_to(resolved_target_dir)
                except ValueError as exc:
                    raise RuntimeError(f"The {description} archive contains an unsafe path.") from exc
            archive.extractall(target_dir)

    def _run_download_thread(self) -> None:
        session = requests.Session()
        session.headers.update({"User-Agent": "FRAM-ChromiumInstaller/1.0"})

        root = self.get_root_path()
        parent_dir = root.parent
        staging_dir = parent_dir / "chromium_staging"
        download_dir = parent_dir / "downloads"

        try:
            with self.lock:
                self.download_state["status"] = "Fetching Chromium manifest..."
                self.download_state["progress"] = 5

            platform_key = self._get_platform_key()
            resp = session.get(CHROME_FOR_TESTING_DOWNLOADS_URL, timeout=30)
            resp.raise_for_status()
            manifest = resp.json()

            if not isinstance(manifest, dict) or "channels" not in manifest or "Stable" not in manifest["channels"]:
                raise RuntimeError("Invalid format for Chromium download manifest.")

            stable = manifest["channels"]["Stable"]
            version = str(stable.get("version") or "").strip()
            downloads = stable.get("downloads", {})
            if not version:
                raise RuntimeError("Stable Chromium version missing in manifest.")

            chrome_url = self._select_download_url(downloads, "chrome", platform_key)
            chromedriver_url = self._select_download_url(downloads, "chromedriver", platform_key)

            parent_dir.mkdir(parents=True, exist_ok=True)
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            staging_dir.mkdir(parents=True, exist_ok=True)
            download_dir.mkdir(parents=True, exist_ok=True)

            chrome_zip = download_dir / f"chrome-{version}-{platform_key}.zip"
            driver_zip = download_dir / f"chromedriver-{version}-{platform_key}.zip"

            with self.lock:
                self.download_state["status"] = f"Downloading Chromium v{version}..."
                self.download_state["progress"] = 10
                self.download_state["version"] = version

            self._download_file(session, chrome_url, chrome_zip, "Chromium Browser", 60.0, 10.0)

            with self.lock:
                self.download_state["status"] = "Downloading ChromeDriver..."
                self.download_state["progress"] = 72

            self._download_file(session, chromedriver_url, driver_zip, "ChromeDriver", 15.0, 72.0)

            with self.lock:
                self.download_state["status"] = "Extracting Chromium Browser..."
                self.download_state["progress"] = 88

            self._extract_zip(chrome_zip, staging_dir, "Chromium")

            with self.lock:
                self.download_state["status"] = "Extracting ChromeDriver..."
                self.download_state["progress"] = 93

            self._extract_zip(driver_zip, staging_dir, "ChromeDriver")

            expected_binary = staging_dir / f"chrome-{platform_key}" / "chrome.exe"
            expected_driver = staging_dir / f"chromedriver-{platform_key}" / "chromedriver.exe"

            if not expected_binary.is_file():
                found_binaries = list(staging_dir.glob("chrome-*/chrome.exe"))
                if not found_binaries:
                    raise RuntimeError("Chromium executable not found after extraction.")
            if not expected_driver.is_file():
                found_drivers = list(staging_dir.glob("chromedriver-*/chromedriver.exe"))
                if not found_drivers:
                    raise RuntimeError("ChromeDriver executable not found after extraction.")

            meta = {
                "version": version,
                "platform": platform_key,
                "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": CHROME_FOR_TESTING_DOWNLOADS_URL
            }
            (staging_dir / "managed_chromium.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            with self.lock:
                self.download_state["status"] = "Finalizing installation..."
                self.download_state["progress"] = 98

            if root.exists():
                shutil.rmtree(root)
            staging_dir.rename(root)

            for zip_path in (chrome_zip, driver_zip):
                if zip_path.exists():
                    try:
                        zip_path.unlink()
                    except OSError:
                        pass

            with self.lock:
                self.download_state["active"] = False
                self.download_state["status"] = f"Chromium v{version} installed successfully."
                self.download_state["progress"] = 100
                self.download_state["success"] = True
                self.download_state["error"] = None
                self.download_state["version"] = version

        except Exception as exc:
            error_msg = str(exc)
            with self.lock:
                self.download_state["active"] = False
                self.download_state["status"] = f"Installation failed: {error_msg}"
                self.download_state["progress"] = 0
                self.download_state["success"] = False
                self.download_state["error"] = error_msg
        finally:
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir)
                except OSError:
                    pass

    def start_download(self) -> Dict[str, Any]:
        with self.lock:
            if self.download_state.get("active", False):
                return {"success": False, "error": "Chromium download is already running."}
            self.download_state["active"] = True
            self.download_state["status"] = "Preparing download..."
            self.download_state["progress"] = 0
            self.download_state["downloaded_bytes"] = 0
            self.download_state["total_bytes"] = 0
            self.download_state["success"] = None
            self.download_state["error"] = None
            self.download_state["version"] = ""

            self.download_thread = threading.Thread(target=self._run_download_thread, daemon=True)
            self.download_thread.start()
            return {"success": True, "message": "Chromium download started."}

    def uninstall(self) -> Dict[str, Any]:
        with self.lock:
            if self.download_state.get("active", False):
                return {"success": False, "error": "Cannot uninstall while download is in progress."}
            root = self.get_root_path()
            parent_dir = root.parent
            staging_dir = parent_dir / "chromium_staging"
            download_dir = parent_dir / "downloads"
            
            errors = []
            if root.exists():
                try:
                    shutil.rmtree(root)
                except Exception as e:
                    errors.append(f"Failed to remove chromium directory: {e}")
            
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir)
                except Exception:
                    pass

            if download_dir.exists():
                try:
                    for f in download_dir.glob("chrome*"):
                        try:
                            f.unlink()
                        except Exception:
                            pass
                except Exception:
                    pass

            self.download_state = {
                "active": False,
                "status": "Idle",
                "progress": 0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "success": None,
                "error": None,
                "version": ""
            }

            if errors:
                return {"success": False, "error": "; ".join(errors)}
            return {"success": True, "message": "Chromium uninstalled successfully."}

chromium_downloader_manager = ChromiumDownloaderManager()

