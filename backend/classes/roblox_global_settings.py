import os
import sys
import platform
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple

class RobloxGlobalSettingsManager:
    def __init__(self):
        self.settings_path = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\GlobalBasicSettings_13.xml")

    def get_field_specs(self) -> Dict[str, Tuple[Dict[str, Any], ...]]:
        return {
            "Graphics": (
                {"key": "GraphicsQualityLevel", "label": "Graphics Quality Level", "xml_name": "GraphicsQualityLevel", "xml_type": "int", "control": "scale", "default": 21, "minimum": 1.0, "maximum": 21.0, "display": "int"},
                {"key": "GraphicsOptimizationMode", "label": "Graphics Optimization Mode", "xml_name": "GraphicsOptimizationMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Auto", 0), ("Performance", 1), ("Quality", 2))},
                {"key": "MaxQualityEnabled", "label": "Max Quality Enabled", "xml_name": "MaxQualityEnabled", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "VignetteEnabled", "label": "Vignette Enabled", "xml_name": "VignetteEnabled", "xml_type": "bool", "control": "bool", "default": True},
                {"key": "FramerateCap", "label": "Framerate Cap", "xml_name": "FramerateCap", "xml_type": "int", "control": "spinbox", "default": 120, "minimum": 0, "maximum": 999},
                {"key": "Fullscreen", "label": "Fullscreen", "xml_name": "Fullscreen", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "StartMaximized", "label": "Start Maximized", "xml_name": "StartMaximized", "xml_type": "bool", "control": "bool", "default": True},
            ),
            "Audio": (
                {"key": "MasterVolume", "label": "Master Volume", "xml_name": "MasterVolume", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                {"key": "PartyVoiceVolume", "label": "Party Voice Volume", "xml_name": "PartyVoiceVolume", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
            ),
            "Controls": (
                {"key": "ComputerMovementMode", "label": "Computer Movement Mode", "xml_name": "ComputerMovementMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Default", 0), ("Keyboard+Mouse", 1), ("Click To Move", 2))},
                {"key": "ControlMode", "label": "Control Mode", "xml_name": "ControlMode", "xml_type": "token", "control": "combo", "default": 1, "options": (("Mouse Lock", 0), ("Classic", 1), ("Dynamic", 2))},
                {"key": "MouseSensitivity", "label": "Mouse Sensitivity", "xml_name": "MouseSensitivity", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "MouseSensitivityFirstPersonX", "label": "Mouse Sensitivity First Person X", "xml_name": "MouseSensitivityFirstPerson", "xml_type": "Vector2", "component": "X", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "MouseSensitivityFirstPersonY", "label": "Mouse Sensitivity First Person Y", "xml_name": "MouseSensitivityFirstPerson", "xml_type": "Vector2", "component": "Y", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "MouseSensitivityThirdPersonX", "label": "Mouse Sensitivity Third Person X", "xml_name": "MouseSensitivityThirdPerson", "xml_type": "Vector2", "component": "X", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "MouseSensitivityThirdPersonY", "label": "Mouse Sensitivity Third Person Y", "xml_name": "MouseSensitivityThirdPerson", "xml_type": "Vector2", "component": "Y", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "GamepadCameraSensitivity", "label": "Gamepad Camera Sensitivity", "xml_name": "GamepadCameraSensitivity", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                {"key": "HapticStrength", "label": "Haptic Strength", "xml_name": "HapticStrength", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
            ),
            "Camera": (
                {"key": "CameraMode", "label": "Camera Mode", "xml_name": "CameraMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Classic", 0), ("Follow", 1))},
                {"key": "CameraYInverted", "label": "Camera Y Inverted", "xml_name": "CameraYInverted", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "ComputerCameraMovementMode", "label": "Computer Camera Movement Mode", "xml_name": "ComputerCameraMovementMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Default", 0), ("Follow", 1), ("Classic", 2), ("Orbital", 3), ("Camera Toggle", 4))},
            ),
            "Accessibility": (
                {"key": "ReducedMotion", "label": "Reduced Motion", "xml_name": "ReducedMotion", "xml_type": "bool", "control": "bool", "default": True},
                {"key": "ReadAloud", "label": "Read Aloud", "xml_name": "ReadAloud", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "AllTutorialsDisabled", "label": "All Tutorials Disabled", "xml_name": "AllTutorialsDisabled", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "PreferredTextSize", "label": "Preferred Text Size", "xml_name": "PreferredTextSize", "xml_type": "token", "control": "combo", "default": 1, "options": (("Small", 0), ("Normal", 1), ("Large", 2), ("Extra Large", 3))},
                {"key": "PreferredTransparency", "label": "Preferred Transparency", "xml_name": "PreferredTransparency", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                {"key": "PlayerNamesEnabled", "label": "Player Names Enabled", "xml_name": "PlayerNamesEnabled", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "PerformanceStatsVisible", "label": "Performance Stats Visible", "xml_name": "PerformanceStatsVisible", "xml_type": "bool", "control": "bool", "default": False},
            ),
            "Chat": (
                {"key": "ChatVisible", "label": "Chat Visible", "xml_name": "ChatVisible", "xml_type": "bool", "control": "bool", "default": True},
                {"key": "ChatTranslationEnabled", "label": "Chat Translation Enabled", "xml_name": "ChatTranslationEnabled", "xml_type": "bool", "control": "bool", "default": True},
                {"key": "ChatTranslationToggleEnabled", "label": "Chat Translation Toggle Enabled", "xml_name": "ChatTranslationToggleEnabled", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "ChatTranslationLocale", "label": "Chat Translation Locale", "xml_name": "ChatTranslationLocale", "xml_type": "string", "control": "entry", "default": "en_us"},
            ),
            "Display": (
                {"key": "PlayerListVisible", "label": "Player List Visible", "xml_name": "PlayerListVisible", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "BadgeVisible", "label": "Badge Visible", "xml_name": "BadgeVisible", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "PlayerHeight", "label": "Player Height", "xml_name": "PlayerHeight", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "float"},
            ),
            "Device Preferences": (
                {"key": "MasterVolume", "label": "Volume", "xml_name": "MasterVolume", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                {"key": "AppMode", "label": "Mode", "control": "combo", "default": "Light", "options": (("Light", "Light"), ("Dark", "Dark"), ("System Default", "System Default")), "storage": "app_storage"},
                {"key": "AppTheme", "label": "App Theme", "control": "combo", "default": "Default", "options": (("Default", "Default"), ("Classic", "Classic"), ("Cosmic Dust", "Cosmic Dust"), ("Polar Freeze", "Polar Freeze"), ("Super Charge", "Super Charge"), ("Electric Lime", "Electric Lime"), ("Lava Glow", "Lava Glow"), ("Star Burst", "Star Burst"), ("Pixel Pop", "Pixel Pop"), ("Midnight Wave", "Midnight Wave"), ("Ocean Breeze", "Ocean Breeze"), ("Forest Mist", "Forest Mist"), ("Sunset Bloom", "Sunset Bloom"), ("Lavender Soft", "Lavender Soft")), "storage": "app_storage"},
                {"key": "PreferredTransparency", "label": "Background Transparency", "xml_name": "PreferredTransparency", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                {"key": "HapticStrength", "label": "Haptics", "xml_name": "HapticStrength", "xml_type": "float", "control": "bool", "default": False},
                {"key": "ReducedMotion", "label": "Reduce Motion", "xml_name": "ReducedMotion", "xml_type": "bool", "control": "bool", "default": False},
                {"key": "PreferredTextSize", "label": "Text Size", "xml_name": "PreferredTextSize", "xml_type": "token", "control": "combo", "default": 1, "options": (("Small", 0), ("Normal (Default)", 1), ("Large", 2), ("Extra Large", 3))},
                {"key": "LaunchAtStartup", "label": "Launch at Startup", "control": "bool", "default": False, "storage": "app_storage"},
                {"key": "MinimizeToTray", "label": "Minimize to Tray When Close", "control": "bool", "default": True, "storage": "app_storage"},
            ),
        }

    def _get_properties_node(self, root_element: ET.Element) -> ET.Element:
        item_node = root_element.find(".//Item[@class='UserGameSettings']")
        if item_node is None:
            raise ValueError("UserGameSettings item not found in XML")
        properties_node = item_node.find("Properties")
        if properties_node is None:
            raise ValueError("Properties node not found in XML")
        return properties_node

    def is_roblox_running(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            cmd = ["tasklist", "/FI", "IMAGENAME eq RobloxPlayerBeta.exe"]
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags, timeout=5)
            return bool(res.returncode == 0 and "RobloxPlayerBeta.exe" in str(res.stdout or ""))
        except Exception:
            return False

    def _read_field_value(self, properties_node: ET.Element, field_spec: Dict[str, Any]) -> Any:
        xml_name = str(field_spec.get("xml_name") or "")
        xml_type = str(field_spec.get("xml_type") or "")
        default_value = field_spec.get("default")

        if xml_type == "Vector2":
            vector_node = properties_node.find(f"Vector2[@name='{xml_name}']")
            if vector_node is None:
                return default_value
            component_name = str(field_spec.get("component") or "")
            component_node = vector_node.find(component_name)
            if component_node is None or component_node.text is None:
                return default_value
            try:
                return float(component_node.text.strip() or default_value)
            except ValueError:
                return default_value

        field_node = properties_node.find(f"{xml_type}[@name='{xml_name}']")
        if field_node is None or field_node.text is None:
            return default_value

        raw_value = field_node.text.strip()
        if field_spec.get("control") == "bool" and xml_type == "float":
            try:
                return float(raw_value) > 0.0
            except ValueError:
                return default_value
        if xml_type == "bool":
            return raw_value.lower() == "true"
        if xml_type in {"int", "token"}:
            try:
                return int(raw_value)
            except ValueError:
                return default_value
        if xml_type == "float":
            try:
                return float(raw_value)
            except ValueError:
                return default_value
        return raw_value

    def _write_field_value(self, properties_node: ET.Element, field_spec: Dict[str, Any], value: Any) -> None:
        xml_name = str(field_spec.get("xml_name") or "")
        xml_type = str(field_spec.get("xml_type") or "")

        def _format_float(v: float) -> str:
            return f"{float(v):.6g}"

        if xml_type == "Vector2":
            vector_node = properties_node.find(f"Vector2[@name='{xml_name}']")
            if vector_node is None:
                vector_node = ET.SubElement(properties_node, "Vector2", {"name": xml_name})
                ET.SubElement(vector_node, "X").text = "1.0"
                ET.SubElement(vector_node, "Y").text = "1.0"
            component_name = str(field_spec.get("component") or "")
            component_node = vector_node.find(component_name)
            if component_node is None:
                component_node = ET.SubElement(vector_node, component_name)
            component_node.text = _format_float(float(value))
            return

        field_node = properties_node.find(f"{xml_type}[@name='{xml_name}']")
        if field_node is None:
            field_node = ET.SubElement(properties_node, xml_type, {"name": xml_name})

        if field_spec.get("control") == "bool" and xml_type == "float":
            field_node.text = "1" if bool(value) else "0"
            return

        if xml_type == "bool":
            field_node.text = "true" if bool(value) else "false"
        elif xml_type in {"int", "token"}:
            field_node.text = str(int(value))
        elif xml_type == "float":
            field_node.text = _format_float(float(value))
        else:
            field_node.text = str(value or "")

    def load_settings(self) -> Dict[str, Any]:
        specs = self.get_field_specs()
        all_specs_by_key = {}
        for tab_fields in specs.values():
            for spec in tab_fields:
                all_specs_by_key[spec["key"]] = spec

        values = {}
        for key, spec in all_specs_by_key.items():
            values[key] = spec.get("default")

        from classes.roblox_app_storage import roblox_app_storage_manager
        app_prefs = roblox_app_storage_manager.read_device_preferences()
        for k, v in app_prefs.items():
            if k in all_specs_by_key:
                values[k] = v

        if not os.path.exists(self.settings_path):
            return {
                "exists": False,
                "file_path": self.settings_path,
                "is_roblox_running": self.is_roblox_running(),
                "settings": values,
                "specs": specs
            }

        try:
            xml_tree = ET.parse(self.settings_path)
            properties_node = self._get_properties_node(xml_tree.getroot())
            for key, spec in all_specs_by_key.items():
                if spec.get("xml_name"):
                    values[key] = self._read_field_value(properties_node, spec)

            return {
                "exists": True,
                "file_path": self.settings_path,
                "is_roblox_running": self.is_roblox_running(),
                "settings": values,
                "specs": specs
            }
        except Exception as e:
            return {
                "exists": True,
                "file_path": self.settings_path,
                "is_roblox_running": self.is_roblox_running(),
                "settings": values,
                "specs": specs,
                "error": f"Error parsing XML: {e}"
            }

    def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        specs = self.get_field_specs()
        all_specs_by_key = {}
        for tab_fields in specs.values():
            for spec in tab_fields:
                all_specs_by_key[spec["key"]] = spec

        from classes.roblox_app_storage import roblox_app_storage_manager
        app_storage_keys = {"AppMode", "AppTheme", "LaunchAtStartup", "MinimizeToTray"}
        app_storage_subset = {k: v for k, v in new_settings.items() if k in app_storage_keys}
        if app_storage_subset:
            roblox_app_storage_manager.save_device_preferences(app_storage_subset)

        if not os.path.exists(self.settings_path):
            if app_storage_subset:
                return {"success": True, "message": "Global Roblox settings saved successfully!"}
            return {"success": False, "error": f"Settings file not found: {self.settings_path}"}

        try:
            xml_tree = ET.parse(self.settings_path)
            properties_node = self._get_properties_node(xml_tree.getroot())

            for key, val in new_settings.items():
                if key in all_specs_by_key:
                    spec = all_specs_by_key[key]
                    if spec.get("xml_name"):
                        self._write_field_value(properties_node, spec, val)

            if hasattr(ET, "indent"):
                ET.indent(xml_tree, space="\t")

            xml_tree.write(self.settings_path, encoding="unicode", xml_declaration=False)
            return {"success": True, "message": "Global Roblox settings saved successfully!"}
        except Exception as e:
            return {"success": False, "error": f"Failed to save settings: {e}"}

roblox_global_settings_manager = RobloxGlobalSettingsManager()
