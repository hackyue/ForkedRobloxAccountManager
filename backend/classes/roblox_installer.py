import os
import sys
import re
import json
import time
import shutil
import zipfile
import tempfile
import threading
from typing import Dict, List, Any, Optional
import requests
from classes.roblox_api import RobloxAPI

WEAO_VERSIONS_CURRENT_PATH = "/api/versions/current"
WEAO_VERSIONS_FUTURE_PATH = "/api/versions/future"
WEAO_VERSIONS_PAST_PATH = "/api/versions/past"
WEAO_API_HOSTS = ("weao.xyz", "whatexpsare.online", "weao.gg", "whatexploitsaretra.sh")
WEAO_API_USER_AGENT = "WEAO-3PService"

ROBLOX_CLIENT_SETTINGS_URL = "https://clientsettings.roblox.com/v2/client-version/WindowsPlayer"
ROBLOX_DOWNLOAD_HEADERS = {
    "User-Agent": "Roblox/WinInet",
    "Referer": "https://www.roblox.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

RDD_HOST_PATH = "https://setup-aws.rbxcdn.com"
RDD_BINARY_TYPES = {
    "WindowsPlayer": {"blob_dir": "/"},
    "WindowsStudio64": {"blob_dir": "/"}
}

RDD_EXTRACT_ROOTS = {
    "player": {
        "RobloxApp.zip": "",
        "redist.zip": "",
        "shaders.zip": "shaders/",
        "ssl.zip": "ssl/",
        "WebView2.zip": "",
        "WebView2RuntimeInstaller.zip": "WebView2RuntimeInstaller/",
        "content-avatar.zip": "content/avatar/",
        "content-configs.zip": "content/configs/",
        "content-fonts.zip": "content/fonts/",
        "content-sky.zip": "content/sky/",
        "content-sounds.zip": "content/sounds/",
        "content-textures2.zip": "content/textures/",
        "content-models.zip": "content/models/",
        "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
        "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
        "content-terrain.zip": "PlatformContent/pc/terrain/",
        "content-textures3.zip": "PlatformContent/pc/textures/",
        "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
        "extracontent-translations.zip": "ExtraContent/translations/",
        "extracontent-models.zip": "ExtraContent/models/",
        "extracontent-textures.zip": "ExtraContent/textures/",
        "extracontent-places.zip": "ExtraContent/places/",
    },
    "studio": {
        "RobloxStudio.zip": "",
        "RibbonConfig.zip": "RibbonConfig/",
        "redist.zip": "",
        "Libraries.zip": "",
        "LibrariesQt5.zip": "",
        "WebView2.zip": "",
        "WebView2RuntimeInstaller.zip": "",
        "shaders.zip": "shaders/",
        "ssl.zip": "ssl/",
        "Qml.zip": "Qml/",
        "Plugins.zip": "Plugins/",
        "StudioFonts.zip": "StudioFonts/",
        "BuiltInPlugins.zip": "BuiltInPlugins/",
        "ApplicationConfig.zip": "ApplicationConfig/",
        "BuiltInStandalonePlugins.zip": "BuiltInStandalonePlugins/",
        "content-qt_translations.zip": "content/qt_translations/",
        "content-sky.zip": "content/sky/",
        "content-fonts.zip": "content/fonts/",
        "content-avatar.zip": "content/avatar/",
        "content-models.zip": "content/models/",
        "content-sounds.zip": "content/sounds/",
        "content-configs.zip": "content/configs/",
        "content-api-docs.zip": "content/api_docs/",
        "content-textures2.zip": "content/textures/",
        "content-studio_svg_textures.zip": "content/studio_svg_textures/",
        "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
        "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
        "content-terrain.zip": "PlatformContent/pc/terrain/",
        "content-textures3.zip": "PlatformContent/pc/textures/",
        "extracontent-translations.zip": "ExtraContent/translations/",
        "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
        "extracontent-textures.zip": "ExtraContent/textures/",
        "extracontent-scripts.zip": "ExtraContent/scripts/",
        "extracontent-models.zip": "ExtraContent/models/",
        "studiocontent-models.zip": "StudioContent/models/",
        "studiocontent-textures.zip": "StudioContent/textures/",
    }
}

RDD_APP_SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Settings>
\t<ContentFolder>content</ContentFolder>
\t<BaseUrl>http://www.roblox.com</BaseUrl>
</Settings>
"""

INSTALLER_VERSION_ENTRY_LIMIT = 5

class RobloxInstallerManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.download_thread: Optional[threading.Thread] = None
        self.versions_cache: Optional[Dict[str, Any]] = None
        self.installer_state: Dict[str, Any] = {
            "active": False,
            "status": "Idle",
            "progress": 0,
            "success": None,
            "error": None,
            "version": "",
            "client_name": ""
        }
        self.exploits_cache: Optional[Dict[str, Any]] = None

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.installer_state)

    def get_weao_exploits(self) -> List[Dict[str, Any]]:
        now = time.time()
        if (
            self.exploits_cache
            and self.exploits_cache.get("exploits")
            and (now - float(self.exploits_cache.get("ts", 0))) < 60
        ):
            return self.exploits_cache.get("exploits", [])

        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {"User-Agent": WEAO_API_USER_AGENT}

        candidate_urls = [
            "https://whatexpsare.online/api/status/exploits",
            "https://weao.gg/api/status/exploits",
            "https://weao.xyz/api/status/exploits",
            "http://whatexpsare.online/api/status/exploits",
            "http://weao.xyz/api/status/exploits",
        ]

        for url in candidate_urls:
            try:
                response = session.get(url, headers=headers, timeout=6)
                if response.ok:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        self.exploits_cache = {"ts": now, "exploits": data}
                        return data
            except Exception:
                continue

        return []

    def _fetch_weao_windows_version(self, route_path: str, status: str) -> Optional[Dict[str, Any]]:
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {"User-Agent": WEAO_API_USER_AGENT}
        normalized_route_path = route_path if str(route_path).startswith("/") else f"/{route_path}"
        subdomain_route_path = normalized_route_path
        if subdomain_route_path.startswith("/api/"):
            subdomain_route_path = subdomain_route_path[4:]
        candidate_urls = []
        for host in WEAO_API_HOSTS:
            for scheme in ("https", "http"):
                candidate_urls.append(f"{scheme}://{host}{normalized_route_path}")
        candidate_urls.extend((
            f"https://api.weao.xyz{subdomain_route_path}",
            f"https://api.whatexpsare.online{subdomain_route_path}",
        ))

        for url in candidate_urls:
            try:
                response = session.get(url, headers=headers, timeout=5)
                response.raise_for_status()
                data = response.json()
            except Exception:
                continue

            if not isinstance(data, dict) or data.get("error"):
                continue

            win = data.get("Windows")
            if not win or not isinstance(win, str):
                continue
            win = win.strip()
            if not re.fullmatch(r"version-[0-9a-fA-F]+", win):
                continue
            return {
                "version": win,
                "status": status,
                "date": data.get("WindowsDate"),
                "download_channel": "LIVE",
                "source": "WEAO",
                "label": f"[{status}] {win}"
            }

        if status == "LIVE":
            try:
                response = session.get(ROBLOX_CLIENT_SETTINGS_URL, timeout=5)
                if response.ok:
                    data = response.json()
                    win = data.get("clientVersionUpload") or data.get("version")
                    if win and isinstance(win, str) and win.startswith("version-"):
                        return {
                            "version": win.strip(),
                            "status": "LIVE",
                            "date": None,
                            "download_channel": "LIVE",
                            "source": "RobloxAPI",
                            "label": f"[LIVE] {win.strip()}"
                        }
            except Exception:
                pass
        return None

    def fetch_remote_versions(self, limit=INSTALLER_VERSION_ENTRY_LIMIT) -> List[Dict[str, Any]]:
        route_specs = (
            (WEAO_VERSIONS_FUTURE_PATH, "FUTURE"),
            (WEAO_VERSIONS_CURRENT_PATH, "LIVE"),
            (WEAO_VERSIONS_PAST_PATH, "PAST"),
        )
        fetched_versions = []
        for route_path, status in route_specs:
            entry = self._fetch_weao_windows_version(route_path, status)
            if entry:
                fetched_versions.append(entry)

        display_priority = {"FUTURE": 0, "LIVE": 1, "PAST": 2}
        dedupe_priority = {"LIVE": 0, "FUTURE": 1, "PAST": 2}
        deduped_versions: Dict[str, Dict[str, Any]] = {}
        for entry in fetched_versions:
            version = entry.get("version")
            if not version:
                continue
            existing = deduped_versions.get(version)
            if existing is None or dedupe_priority.get(entry.get("status"), 99) < dedupe_priority.get(existing.get("status"), 99):
                deduped_versions[version] = entry

        ordered_versions = sorted(
            deduped_versions.values(),
            key=lambda item: display_priority.get(item.get("status"), 99)
        )
        if limit is not None:
            ordered_versions = ordered_versions[:limit]
        return ordered_versions

    def get_local_roblox_versions(self, limit=INSTALLER_VERSION_ENTRY_LIMIT) -> List[Dict[str, Any]]:
        sources = []
        for client in self.get_installed_clients():
            v_path = client.get("versions_path", "")
            if v_path:
                sources.append({
                    "name": client.get("name", ""),
                    "base": v_path
                })

        versions = []
        seen = set()
        for source in sources:
            base_path = source["base"]
            if not base_path or not os.path.exists(base_path):
                continue

            try:
                entries = []
                with os.scandir(base_path) as iterator:
                    for entry in iterator:
                        try:
                            if not entry.is_dir():
                                continue
                            stat = entry.stat()
                        except OSError:
                            continue
                        entries.append((float(getattr(stat, "st_mtime", 0.0)), entry.path, entry.name))

                entries.sort(key=lambda item: item[0], reverse=True)

                for idx, entry_item in enumerate(entries):
                    _, path, version_name = entry_item
                    if version_name in seen:
                        continue
                    seen.add(version_name)
                    label = f"[{source['name']}] {version_name}"
                    versions.append({
                        "label": label,
                        "path": path,
                        "version": version_name,
                        "status": "LIVE" if idx == 0 else "PAST",
                        "source": "Local"
                    })
            except Exception:
                continue

        if limit is not None:
            versions = versions[:limit]
        return versions

    def get_available_versions(self) -> List[Dict[str, Any]]:
        now = time.time()
        if (
            self.versions_cache
            and self.versions_cache.get("versions")
            and (now - float(self.versions_cache.get("ts", 0))) < 60
        ):
            return self.versions_cache["versions"]

        remote = self.fetch_remote_versions()
        if remote:
            self.versions_cache = {"ts": now, "versions": remote}
            return remote

        local = self.get_local_roblox_versions()
        return local

    def get_installed_clients(self) -> List[Dict[str, Any]]:
        candidates = []
        known_paths = set()

        def add_candidate(name: str, base_path: str):
            if not base_path:
                return
            normalized = os.path.normcase(os.path.normpath(base_path))
            if normalized in known_paths:
                return
            known_paths.add(normalized)
            candidates.append((name, base_path))

        default_roblox_versions = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\Versions")
        default_roblox_root = os.path.expandvars(r"%LOCALAPPDATA%\Roblox")
        if os.path.isdir(default_roblox_versions) or os.path.isdir(default_roblox_root):
            add_candidate("Roblox", default_roblox_versions)

        for prog_dir in [os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)')]:
            if prog_dir:
                p_path = os.path.join(prog_dir, 'Roblox', 'Versions')
                if os.path.isdir(p_path):
                    add_candidate("Roblox", p_path)

        for bootstrapper in RobloxAPI.BOOTSTRAPPER_CLIENTS:
            root = os.path.expandvars(bootstrapper.get("root", ""))
            launcher_name = bootstrapper.get("launcher", "")
            launcher_path = os.path.join(root, launcher_name) if launcher_name and root else ""
            version_dir_names = bootstrapper.get("version_dirs", ("Versions",))

            has_versions_dir = any(os.path.isdir(os.path.join(root, vd)) for vd in version_dir_names)
            has_launcher = bool(launcher_path and os.path.isfile(launcher_path))
            has_root = bool(root and os.path.isdir(root))

            if has_versions_dir or has_launcher or has_root:
                for vd in version_dir_names:
                    add_candidate(
                        bootstrapper.get("name", os.path.basename(root)),
                        os.path.join(root, vd)
                    )

        search_roots = []
        for env_key in ('LOCALAPPDATA', 'APPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
            path_val = os.getenv(env_key)
            if path_val and os.path.isdir(path_val):
                search_roots.append(path_val)

        for search_root in search_roots:
            try:
                for entry in os.scandir(search_root):
                    if not entry.is_dir():
                        continue
                    for v_sub in ('Versions', 'RblxVersions', 'versions', 'rblxversions'):
                        v_full = os.path.join(entry.path, v_sub)
                        norm_v = os.path.normcase(os.path.normpath(v_full))
                        if os.path.isdir(v_full) and norm_v not in known_paths:
                            is_roblox_client = False
                            try:
                                for sub in os.scandir(v_full):
                                    if sub.is_dir():
                                        if sub.name.startswith("version-"):
                                            is_roblox_client = True
                                            break
                                        if os.path.isfile(os.path.join(sub.path, 'RobloxPlayerBeta.exe')) or os.path.isfile(os.path.join(sub.path, 'RobloxPlayerLauncher.exe')):
                                            is_roblox_client = True
                                            break
                                if not is_roblox_client:
                                    for root_file in os.scandir(entry.path):
                                        if root_file.is_file():
                                            fname_lower = root_file.name.lower()
                                            if fname_lower.endswith('.exe') and any(kw in fname_lower for kw in ('strap', 'bootstrapper', 'launcher', 'roblox')):
                                                is_roblox_client = True
                                                break
                            except Exception:
                                pass

                            if is_roblox_client:
                                add_candidate(entry.name, v_full)
            except Exception:
                pass

        if not candidates:
            add_candidate("Roblox", default_roblox_versions)

        result = []
        seen = set()
        for name, base_path in candidates:
            if not base_path:
                continue
            normalized = os.path.normcase(os.path.normpath(base_path))
            if normalized in seen:
                continue
            seen.add(normalized)
            client_id = name.lower().replace(" ", "_").replace("-", "_")
            result.append({
                "id": client_id,
                "name": name,
                "versions_path": base_path,
                "installed": os.path.isdir(base_path) or os.path.isdir(os.path.dirname(base_path))
            })

        result.sort(key=lambda entry: (0 if entry["name"].lower() == "roblox" else 1, entry["name"].lower()))
        return result

    def start_installation(self, version_entry: Dict[str, Any], client_id: str, overwrite: bool = False) -> Dict[str, Any]:
        with self.lock:
            if self.installer_state["active"]:
                return {"success": False, "error": "An installation process is already running."}

        clients = self.get_installed_clients()
        selected_client = None
        for c in clients:
            if c["id"] == client_id:
                selected_client = c
                break

        if not selected_client:
            return {"success": False, "error": f"Client '{client_id}' is not recognized."}

        os.makedirs(selected_client["versions_path"], exist_ok=True)

        version = (version_entry.get("version") or "").strip()
        if not version:
            return {"success": False, "error": "Invalid version specified."}

        if not version.startswith("version-"):
            version = "version-" + version

        target_dir = os.path.join(selected_client["versions_path"], version)

        if os.path.exists(target_dir) and not overwrite:
            return {
                "success": False,
                "already_exists": True,
                "target_dir": target_dir,
                "version": version,
                "client_name": selected_client["name"],
                "error": f"Folder for {version} already exists in {selected_client['name']}."
            }

        with self.lock:
            self.installer_state = {
                "active": True,
                "status": "Starting installation...",
                "progress": 0,
                "success": None,
                "error": None,
                "version": version,
                "client_name": selected_client["name"]
            }

        thread = threading.Thread(
            target=self._installer_download_thread,
            args=(version_entry, selected_client, target_dir, overwrite),
            daemon=True
        )
        self.download_thread = thread
        thread.start()

        return {"success": True, "message": "Installation started."}

    def _installer_download_thread(self, version_entry: Dict[str, Any], client: Dict[str, Any], target_dir: str, overwrite: bool):
        version = (version_entry.get("version") or "").strip()
        if not version.startswith("version-"):
            version = "version-" + version

        def update_state(status=None, progress=None, success=None, error=None):
            with self.lock:
                if status is not None:
                    self.installer_state["status"] = status
                if progress is not None:
                    self.installer_state["progress"] = progress
                if success is not None:
                    self.installer_state["success"] = success
                    self.installer_state["active"] = False
                if error is not None:
                    self.installer_state["error"] = error

        temp_root = None
        try:
            if os.path.exists(target_dir) and overwrite:
                try:
                    shutil.rmtree(target_dir)
                except Exception as exc:
                    raise RuntimeError(f"Failed to remove existing folder {target_dir}: {exc}")

            channel = str(version_entry.get("download_channel") or "LIVE").strip().upper()
            binary_type = "WindowsPlayer"
            blob_dir = RDD_BINARY_TYPES.get(binary_type, {}).get("blob_dir", "/")

            update_state(status="Fetching version manifest...", progress=5)

            session = requests.Session()
            session.trust_env = False

            channel_path = RDD_HOST_PATH
            if channel != "LIVE":
                channel_path = f"{RDD_HOST_PATH}/channel/{channel.lower()}"

            version_path = f"{channel_path}{blob_dir}{version}-"
            manifest_url = version_path + "rbxPkgManifest.txt"

            resp = session.get(manifest_url, headers=ROBLOX_DOWNLOAD_HEADERS, timeout=15)
            resp.raise_for_status()
            manifest_body = resp.text

            lines = [line.strip() for line in manifest_body.splitlines() if line.strip()]
            if not lines or lines[0] != "v0":
                raise RuntimeError("Invalid or unsupported rbxPkgManifest format")

            packages = []
            for line in lines[1:]:
                name = (line.split() or [""])[0]
                if name.lower().endswith(".zip"):
                    packages.append(name)

            if not packages:
                raise RuntimeError("Manifest contained no packages")

            if "RobloxApp.zip" in packages:
                extract_roots = RDD_EXTRACT_ROOTS["player"]
            elif "RobloxStudio.zip" in packages:
                extract_roots = RDD_EXTRACT_ROOTS["studio"]
            else:
                raise RuntimeError("Unrecognized package manifest content")

            temp_root = tempfile.mkdtemp(prefix="fram_rdd_")
            build_dir = os.path.join(temp_root, "build")
            os.makedirs(build_dir, exist_ok=True)

            app_settings_path = os.path.join(build_dir, "AppSettings.xml")
            with open(app_settings_path, "w", encoding="utf-8") as f:
                f.write(RDD_APP_SETTINGS_XML)

            pkgs_dir = os.path.join(temp_root, "pkgs")
            os.makedirs(pkgs_dir, exist_ok=True)

            total_pkgs = len(packages)
            for idx, package_name in enumerate(packages, 1):
                pct = 10.0 + ((idx - 1) / max(1, total_pkgs)) * 65.0
                update_state(status=f"Downloading {package_name} ({idx}/{total_pkgs})...", progress=round(pct, 1))

                pkg_url = version_path + package_name
                pkg_path = os.path.join(pkgs_dir, package_name)

                with session.get(pkg_url, headers=ROBLOX_DOWNLOAD_HEADERS, stream=True, timeout=(10, 120)) as r:
                    r.raise_for_status()
                    with open(pkg_path, "wb") as out:
                        for chunk in r.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                out.write(chunk)

                extract_root = extract_roots.get(package_name)
                if extract_root is None:
                    shutil.copy2(pkg_path, os.path.join(build_dir, package_name))
                    continue

                update_state(status=f"Extracting {package_name} ({idx}/{total_pkgs})...", progress=round(pct + 2.0, 1))
                with zipfile.ZipFile(pkg_path, "r") as zf:
                    for info in zf.infolist():
                        name = info.filename
                        if not name or name.endswith("/") or name.endswith("\\"):
                            continue
                        fixed = name.replace("\\", "/").lstrip("/")
                        normalized = os.path.normpath(fixed)
                        if normalized.startswith("..") or os.path.isabs(normalized):
                            continue
                        normalized = normalized.replace("\\", "/")
                        dest_path = os.path.join(build_dir, extract_root, normalized)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with zf.open(info, "r") as src_f, open(dest_path, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

            update_state(status="Installing files...", progress=85)
            os.makedirs(target_dir, exist_ok=True)
            items = os.listdir(build_dir)
            total_items = len(items) or 1
            for idx, name in enumerate(items, 1):
                src = os.path.join(build_dir, name)
                dst = os.path.join(target_dir, name)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
                pct = 85.0 + (idx / total_items) * 14.0
                update_state(status=f"Installing {name} ({idx}/{total_items})...", progress=round(pct, 1))

            update_state(status=f"Successfully installed {version} into {client['name']}!", progress=100, success=True)
        except Exception as exc:
            update_state(status="Installation failed", progress=0, success=False, error=str(exc))
        finally:
            if temp_root and os.path.exists(temp_root):
                try:
                    shutil.rmtree(temp_root, ignore_errors=True)
                except Exception:
                    pass

roblox_installer_manager = RobloxInstallerManager()
