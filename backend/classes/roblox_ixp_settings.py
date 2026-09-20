import os
import json
from typing import Dict, Any

class RobloxIxpSettingsManager:
    def __init__(self):
        self.file_path = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\ClientSettings\IxpSettings.json")

    def get_file_path(self) -> str:
        return self.file_path

    def load_settings(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return {
                "success": True,
                "exists": False,
                "file_path": self.file_path,
                "settings": {}
            }

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {
                        "success": True,
                        "exists": True,
                        "file_path": self.file_path,
                        "settings": data
                    }
                return {
                    "success": True,
                    "exists": True,
                    "file_path": self.file_path,
                    "settings": {}
                }
        except Exception as e:
            return {
                "success": False,
                "exists": True,
                "file_path": self.file_path,
                "settings": {},
                "error": str(e)
            }

    def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        try:
            parent_dir = os.path.dirname(self.file_path)
            os.makedirs(parent_dir, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(new_settings, f, indent=2, ensure_ascii=False)
            return {
                "success": True,
                "message": "Device Preferences (IxpSettings.json) saved successfully!"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to save IxpSettings.json: {e}"
            }

    def reset_settings(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            return {
                "success": True,
                "message": "IxpSettings.json reset successfully."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to reset IxpSettings.json: {e}"
            }

roblox_ixp_settings_manager = RobloxIxpSettingsManager()
