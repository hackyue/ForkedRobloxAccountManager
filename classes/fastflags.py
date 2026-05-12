"""
FastFlags Manager for Roblox Account Manager
Handles reading, writing, and managing Roblox FastFlags
"""

import os
import json
import re
import shutil
from pathlib import Path


class FastFlagsManager:
    """Manages Roblox FastFlags for performance and graphics customization"""
    
    def __init__(self, version_path=None):
        self.app_data = os.path.expandvars("%LOCALAPPDATA%")
        self.version_path = version_path  # Specific version path to use
        self.roblox_versions_path = os.path.join(self.app_data, "Roblox", "Versions")
        
        # Common FastFlag presets
        self.presets = {
            "Performance": {
                "FFlagDebugGraphicsDisableVehicleDrawDistance": "False",
                "FFlagDebugGraphicsPreferSimpleDistanceField": "True",
                "DFIntTaskSchedulerTargetFps": "60",
                "DFIntRenderCullingGranularity": "1024",
                "FFlagDebugGraphicsDisableDecals": "True",
                "FFlagDebugGraphicsDisablePostFX": "False",
                "FFlagDebugGraphicsDisableBloom": "False",
                "FFlagDebugGraphicsDisableBlur": "False",
            },
            "Low Quality": {
                "FFlagDebugGraphicsDisableVehicleDrawDistance": "True",
                "FFlagDebugGraphicsPreferSimpleDistanceField": "True",
                "DFIntTaskSchedulerTargetFps": "30",
                "DFIntRenderCullingGranularity": "512",
                "FFlagDebugGraphicsDisableDecals": "True",
                "FFlagDebugGraphicsDisablePostFX": "True",
                "FFlagDebugGraphicsDisableBloom": "True",
                "FFlagDebugGraphicsDisableBlur": "True",
                "FFlagDebugGraphicsDisableShadows": "True",
                "FFlagDebugGraphicsDisableReflections": "True",
            },
            "High Quality": {
                "FFlagDebugGraphicsDisableVehicleDrawDistance": "False",
                "FFlagDebugGraphicsPreferSimpleDistanceField": "False",
                "DFIntTaskSchedulerTargetFps": "144",
                "DFIntRenderCullingGranularity": "2048",
                "FFlagDebugGraphicsDisableDecals": "False",
                "FFlagDebugGraphicsDisablePostFX": "False",
                "FFlagDebugGraphicsDisableBloom": "False",
                "FFlagDebugGraphicsDisableBlur": "False",
                "FFlagDebugGraphicsDisableShadows": "False",
                "FFlagDebugGraphicsDisableReflections": "False",
            },
            "FPS Cap 30": {
                "DFIntTaskSchedulerTargetFps": "30",
            },
            "FPS Cap 60": {
                "DFIntTaskSchedulerTargetFps": "60",
            },
            "FPS Cap 120": {
                "DFIntTaskSchedulerTargetFps": "120",
            },
            "FPS Cap 144": {
                "DFIntTaskSchedulerTargetFps": "144",
            },
            "FPS Cap 240": {
                "DFIntTaskSchedulerTargetFps": "240",
            },
            "Uncapped": {
                "DFIntTaskSchedulerTargetFps": "0",
            }
        }
    
    def get_version_sources(self):
        """Get all possible Roblox version sources (including bootstrappers)"""
        sources = []
        
        
        sources.append({
            "name": "Roblox",
            "base": os.path.join(self.app_data, "Roblox", "Versions")
        })
        
        
        bootstrapper_paths = [
            ("Bloxstrap", os.path.join(self.app_data, "Bloxstrap", "Versions")),
            ("Fishstrap", os.path.join(self.app_data, "Fishstrap", "Versions")),
            ("Voidstrap", os.path.join(self.app_data, "Voidstrap", "RblxVersions")),
        ]
        
        for name, path in bootstrapper_paths:
            if os.path.exists(path):
                sources.append({"name": name, "base": path})
        
        return sources
    
    def get_latest_version_path(self):
        """Get the path to the latest Roblox version from all sources"""
        if self.version_path:
            return self.version_path
        
        
        sources = self.get_version_sources()
        all_versions = []
        
        for source in sources:
            base_path = source["base"]
            if not os.path.exists(base_path):
                continue
            
            try:
                entries = [
                    os.path.join(base_path, d)
                    for d in os.listdir(base_path)
                    if os.path.isdir(os.path.join(base_path, d)) and d.startswith("version-")
                ]
                for entry in entries:
                    all_versions.append((entry, os.path.getmtime(entry)))
            except Exception:
                continue
        
        if not all_versions:
            return None
        
        # Return the most recently modified version
        latest_version = max(all_versions, key=lambda x: x[1])
        return latest_version[0]
    
    def get_fast_flags_file(self):
        """Find the FastFlags file in the version-specific ClientSettings folder"""
        latest_version = self.get_latest_version_path()
        if latest_version:
            client_settings_path = os.path.join(latest_version, "ClientSettings")
            if os.path.exists(client_settings_path):
                return os.path.join(client_settings_path, "ClientAppSettings.json")
            else:
                # Create ClientSettings folder if it doesn't exist
                os.makedirs(client_settings_path, exist_ok=True)
                return os.path.join(client_settings_path, "ClientAppSettings.json")
        
        
        fallback_location = os.path.join(self.app_data, "Roblox", "PlayerSettings")
        os.makedirs(fallback_location, exist_ok=True)
        return os.path.join(fallback_location, "ClientAppSettings.json")
    
    def load_fast_flags(self):
        """Load current FastFlags from file"""
        file_path = self.get_fast_flags_file()
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("variables", {})
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load FastFlags from {file_path}: {e}")
            return {}
    
    def save_fast_flags(self, flags):
        """Save FastFlags to file"""
        file_path = self.get_fast_flags_file()
        
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        
        data = {
            "variables": flags
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[SUCCESS] FastFlags saved to {file_path}")
            return True
        except IOError as e:
            print(f"[ERROR] Failed to save FastFlags to {file_path}: {e}")
            return False
    
    def reset_to_default(self):
        """Reset all FastFlags to default (clear file)"""
        file_path = self.get_fast_flags_file()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            print("[SUCCESS] FastFlags reset to default")
            return True
        except IOError as e:
            print(f"[ERROR] Failed to reset FastFlags: {e}")
            return False
    
    def backup_fast_flags(self):
        """Create a backup of current FastFlags"""
        file_path = self.get_fast_flags_file()
        if os.path.exists(file_path):
            backup_path = file_path + ".backup"
            try:
                shutil.copy2(file_path, backup_path)
                print(f"[SUCCESS] FastFlags backed up to {backup_path}")
                return True
            except IOError as e:
                print(f"[ERROR] Failed to backup FastFlags: {e}")
                return False
        return False
    
    def restore_fast_flags(self):
        """Restore FastFlags from backup"""
        file_path = self.get_fast_flags_file()
        backup_path = file_path + ".backup"
        
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, file_path)
                print(f"[SUCCESS] FastFlags restored from backup")
                return True
            except IOError as e:
                print(f"[ERROR] Failed to restore FastFlags: {e}")
                return False
        else:
            print("[ERROR] No backup file found")
            return False
    
    def get_available_presets(self):
        """Get list of available preset names"""
        return list(self.presets.keys())
    
    def validate_flag_name(self, flag_name):
        """Validate FastFlag name format"""
        pattern = r'^(DF|FF)(Int|Float|lag)[A-Z][a-zA-Z0-9]*$'
        
        if not flag_name:
            return False, "Flag name cannot be empty"
        
        if len(flag_name) < 5:
            return False, "Flag name is too short (minimum 5 characters)"
        
        if not re.match(pattern, flag_name):
            return False, (
                "Invalid flag name format. Expected format:\n"
                "• DFlagSomething (for boolean/string flags)\n"
                "• FFlagSomething (for boolean/string flags)\n"
                "• DFIntSomething (for integer flags)\n"
                "• DFFloatSomething (for float flags)\n\n"
                "Examples:\n"
                "• DFlagDebugGraphicsDisableDecals\n"
                "• DFIntTaskSchedulerTargetFps\n"
                "• FFlagEnableNewRendering"
            )
        
        return True, "Valid flag name format"
    
