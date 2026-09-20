import os
import json
import winreg
from typing import Dict, Any, Optional

THEME_TITLE_TO_ID = {
    "Default": "default",
    "Classic": "classic",
    "Cosmic Dust": "cosmic_dust",
    "Polar Freeze": "polar_freeze",
    "Super Charge": "super_charge",
    "Electric Lime": "electric_lime",
    "Lava Glow": "lava_glow",
    "Star Burst": "star_burst",
    "Pixel Pop": "pixel_pop",
    "Midnight Wave": "midnight_wave",
    "Ocean Breeze": "ocean_breeze",
    "Forest Mist": "forest_mist",
    "Sunset Bloom": "sunset_bloom",
    "Lavender Soft": "lavender_soft"
}

THEME_ID_TO_TITLE = {v: k for k, v in THEME_TITLE_TO_ID.items()}

class RobloxAppStorageManager:
    def __init__(self):
        self.app_storage_path = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\LocalStorage\appStorage.json")
        self.versions_dir = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\Versions")

    def get_latest_roblox_exe(self) -> Optional[str]:
        if not os.path.isdir(self.versions_dir):
            return None
        candidates = []
        try:
            for item in os.listdir(self.versions_dir):
                full_dir = os.path.join(self.versions_dir, item)
                if os.path.isdir(full_dir):
                    exe = os.path.join(full_dir, "RobloxPlayerBeta.exe")
                    if os.path.isfile(exe):
                        mtime = os.path.getmtime(exe)
                        candidates.append((mtime, exe))
        except Exception:
            pass
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None

    def read_startup_registry(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "RobloxPlayerBeta")
                return bool(val and "--launch-to-tray" in str(val))
        except Exception:
            return False

    def write_startup_registry(self, enabled: bool) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    exe = self.get_latest_roblox_exe()
                    if exe:
                        cmd = f'"{exe}" --launch-to-tray'
                        winreg.SetValueEx(key, "RobloxPlayerBeta", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, "RobloxPlayerBeta")
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    def load_app_storage_dict(self) -> Dict[str, Any]:
        if not os.path.exists(self.app_storage_path):
            return {}
        try:
            with open(self.app_storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_app_storage_dict(self, data: Dict[str, Any]) -> bool:
        try:
            os.makedirs(os.path.dirname(self.app_storage_path), exist_ok=True)
            with open(self.app_storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except Exception:
            return False

    def read_device_preferences(self) -> Dict[str, Any]:
        storage = self.load_app_storage_dict()
        user_id = str(storage.get("UserId") or "0")

        auth_theme = str(storage.get("AuthenticatedTheme") or "").strip().lower()
        dev_theme_raw = str(storage.get("DeviceLevelTheme") or "").strip()

        detected_theme = auth_theme
        if dev_theme_raw:
            try:
                parsed_map = json.loads(dev_theme_raw)
                if isinstance(parsed_map, dict):
                    if user_id in parsed_map:
                        detected_theme = str(parsed_map[user_id]).strip().lower()
                    elif parsed_map:
                        detected_theme = str(next(iter(parsed_map.values()))).strip().lower()
            except Exception:
                pass

        app_mode = "System Default"
        app_theme = "Default"

        if detected_theme == "light":
            app_mode = "Light"
            app_theme = "Default"
        elif detected_theme == "dark":
            app_mode = "Dark"
            app_theme = "Default"
        elif detected_theme == "default" or detected_theme == "":
            app_mode = "System Default"
            app_theme = "Default"
        elif detected_theme in THEME_ID_TO_TITLE:
            app_mode = "System Default"
            app_theme = THEME_ID_TO_TITLE[detected_theme]

        launch_startup = self.read_startup_registry()
        if "LaunchAtStartup" in storage:
            val = storage.get("LaunchAtStartup")
            if isinstance(val, bool):
                launch_startup = val
            elif isinstance(val, str):
                launch_startup = val.lower() == "true"

        minimize_tray = True
        if "MinimizeToTray" in storage:
            val = storage.get("MinimizeToTray")
            if isinstance(val, bool):
                minimize_tray = val
            elif isinstance(val, str):
                minimize_tray = val.lower() == "true"

        return {
            "AppMode": app_mode,
            "AppTheme": app_theme,
            "LaunchAtStartup": launch_startup,
            "MinimizeToTray": minimize_tray
        }

    def save_device_preferences(self, prefs: Dict[str, Any]) -> bool:
        storage = self.load_app_storage_dict()
        user_id = str(storage.get("UserId") or "0")

        app_mode = prefs.get("AppMode")
        app_theme = prefs.get("AppTheme")

        if app_theme is not None or app_mode is not None:
            theme_val = "default"
            theme_choice = str(app_theme or "Default")
            mode_choice = str(app_mode or "System Default")

            if theme_choice != "Default" and theme_choice in THEME_TITLE_TO_ID:
                theme_val = THEME_TITLE_TO_ID[theme_choice]
            else:
                if mode_choice == "Light":
                    theme_val = "light"
                elif mode_choice == "Dark":
                    theme_val = "dark"
                else:
                    theme_val = "default"

            storage["AuthenticatedTheme"] = theme_val

            dev_theme_raw = str(storage.get("DeviceLevelTheme") or "").strip()
            dev_theme_map = {}
            if dev_theme_raw:
                try:
                    parsed = json.loads(dev_theme_raw)
                    if isinstance(parsed, dict):
                        dev_theme_map = parsed
                except Exception:
                    dev_theme_map = {}

            dev_theme_map[user_id] = theme_val
            for uid in list(dev_theme_map.keys()):
                dev_theme_map[uid] = theme_val

            storage["DeviceLevelTheme"] = json.dumps(dev_theme_map)

        if "LaunchAtStartup" in prefs:
            val = bool(prefs["LaunchAtStartup"])
            self.write_startup_registry(val)
            storage["LaunchAtStartup"] = "true" if val else "false"

        if "MinimizeToTray" in prefs:
            val = bool(prefs["MinimizeToTray"])
            storage["MinimizeToTray"] = "true" if val else "false"
            storage["MinimizeToTrayWhenClose"] = "true" if val else "false"

        return self.save_app_storage_dict(storage)

roblox_app_storage_manager = RobloxAppStorageManager()
