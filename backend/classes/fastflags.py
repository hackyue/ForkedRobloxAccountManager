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
        self.version_path = version_path
        self.roblox_versions_path = os.path.join(self.app_data, "Roblox", "Versions")
    
    def get_version_sources(self):
        """Get all possible Roblox version sources (including bootstrappers)"""
        sources = []
        known_bases = set()

        def add_source(name, base_path):
            if not base_path:
                return
            normalized = os.path.normcase(os.path.normpath(base_path))
            if normalized in known_bases:
                return
            known_bases.add(normalized)
            sources.append({"name": name, "base": base_path})

        roblox_dir = os.path.join(self.app_data, "Roblox", "Versions")
        if os.path.exists(roblox_dir) or os.path.exists(os.path.join(self.app_data, "Roblox")):
            add_source("Roblox", roblox_dir)

        for prog_dir in [os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)')]:
            if prog_dir:
                p_path = os.path.join(prog_dir, 'Roblox', 'Versions')
                if os.path.isdir(p_path):
                    add_source("Roblox", p_path)

        bootstrapper_configs = [
            ("Bloxstrap", os.path.join(self.app_data, "Bloxstrap"), "Bloxstrap.exe", ["Versions"]),
            ("Fishstrap", os.path.join(self.app_data, "Fishstrap"), "Fishstrap.exe", ["Versions"]),
            ("Voidstrap", os.path.join(self.app_data, "Voidstrap"), "Voidstrap.exe", ["RblxVersions", "Versions"]),
            ("FrostStrap", os.path.join(self.app_data, "FrostStrap"), "FrostStrap.exe", ["Versions"]),
            ("ExploitStrap", os.path.join(self.app_data, "ExploitStrap"), "ExploitStrap.exe", ["Versions"]),
        ]

        for name, root, launcher, v_dirs in bootstrapper_configs:
            launcher_path = os.path.join(root, launcher) if launcher and root else ""
            has_versions_dir = any(os.path.isdir(os.path.join(root, vd)) for vd in v_dirs)
            has_launcher = bool(launcher_path and os.path.isfile(launcher_path))
            has_root = bool(root and os.path.isdir(root))

            if has_versions_dir or has_launcher or has_root:
                for vd in v_dirs:
                    add_source(name, os.path.join(root, vd))

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
                    for v_sub in ("Versions", "RblxVersions", "versions", "rblxversions"):
                        v_full = os.path.join(entry.path, v_sub)
                        norm_v = os.path.normcase(os.path.normpath(v_full))
                        if os.path.isdir(v_full) and norm_v not in known_bases:
                            is_roblox = False
                            try:
                                for sub in os.scandir(v_full):
                                    if sub.is_dir():
                                        if sub.name.startswith("version-"):
                                            is_roblox = True
                                            break
                                        if os.path.isfile(os.path.join(sub.path, 'RobloxPlayerBeta.exe')) or os.path.isfile(os.path.join(sub.path, 'RobloxPlayerLauncher.exe')):
                                            is_roblox = True
                                            break
                                if not is_roblox:
                                    for root_file in os.scandir(entry.path):
                                        if root_file.is_file():
                                            fname_lower = root_file.name.lower()
                                            if fname_lower.endswith('.exe') and any(kw in fname_lower for kw in ('strap', 'bootstrapper', 'launcher', 'roblox')):
                                                is_roblox = True
                                                break
                            except Exception:
                                pass
                            if is_roblox:
                                add_source(entry.name, v_full)
            except Exception:
                pass

        if not sources:
            add_source("Roblox", roblox_dir)

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
        
        latest_version = max(all_versions, key=lambda x: x[1])
        return latest_version[0]
    
    def get_fast_flags_file(self):
        """Find the FastFlags file in the version-specific ClientSettings folder"""
        latest_version = self.get_latest_version_path()
        if latest_version:
            client_settings_path = os.path.join(latest_version, "ClientSettings")
            os.makedirs(client_settings_path, exist_ok=True)
            return os.path.join(client_settings_path, "ClientAppSettings.json")
        
        fallback_location = os.path.join(self.app_data, "Roblox", "PlayerSettings")
        os.makedirs(fallback_location, exist_ok=True)
        return os.path.join(fallback_location, "ClientAppSettings.json")

    def get_all_target_settings_files(self):
        """Get all target ClientAppSettings.json paths across versions and bootstrappers"""
        target_files = []
        primary_file = self.get_fast_flags_file()
        if primary_file:
            target_files.append(primary_file)
        
        sources = self.get_version_sources()
        for source in sources:
            base_path = source.get("base")
            if not base_path or not os.path.exists(base_path):
                continue
            try:
                for entry in os.scandir(base_path):
                    if entry.is_dir() and entry.name.startswith("version-"):
                        settings_dir = os.path.join(entry.path, "ClientSettings")
                        settings_file = os.path.join(settings_dir, "ClientAppSettings.json")
                        if settings_file not in target_files:
                            target_files.append(settings_file)
            except Exception:
                pass
        
        bloxstrap_mod_dir = os.path.join(self.app_data, "Bloxstrap", "Modifications", "ClientSettings")
        if os.path.exists(os.path.dirname(os.path.dirname(bloxstrap_mod_dir))):
            bloxstrap_mod_file = os.path.join(bloxstrap_mod_dir, "ClientAppSettings.json")
            if bloxstrap_mod_file not in target_files:
                target_files.append(bloxstrap_mod_file)
        
        return target_files
    
    def load_fast_flags(self):
        """Load current FastFlags from file"""
        file_path = self.get_fast_flags_file()
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "variables" in data and isinstance(data["variables"], dict):
                        return data["variables"]
                    return data
                return {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load FastFlags from {file_path}: {e}")
            return {}
    
    def save_fast_flags(self, flags):
        """Save FastFlags to file"""
        target_files = self.get_all_target_settings_files()
        if not target_files:
            target_files = [self.get_fast_flags_file()]
        
        clean_flags = {}
        for k, v in flags.items():
            if v is not None and str(v).strip() != "":
                clean_flags[str(k)] = v
        
        saved_any = False
        for file_path in target_files:
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(clean_flags, f, indent=2)
                saved_any = True
                print(f"[SUCCESS] FastFlags saved to {file_path}")
            except IOError as e:
                print(f"[ERROR] Failed to save FastFlags to {file_path}: {e}")
        
        return saved_any
    
    def reset_to_default(self):
        """Reset all FastFlags to default (clear file)"""
        target_files = self.get_all_target_settings_files()
        if not target_files:
            target_files = [self.get_fast_flags_file()]
        
        for file_path in target_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                print(f"[SUCCESS] FastFlags reset to default for {file_path}")
            except IOError as e:
                print(f"[ERROR] Failed to reset FastFlags at {file_path}: {e}")
        return True
    
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
    
    def validate_flag_name(self, flag_name):
        """Validate FastFlag name format"""
        if not flag_name or not str(flag_name).strip():
            return False, "Flag name cannot be empty"
        
        name = str(flag_name).strip()
        if len(name) < 4:
            return False, "Flag name is too short (minimum 4 characters)"
        
        pattern = r'^(DF|FF|F|SF|SFF|FLog|DFLog)(Int|Float|lag|String|Log)?[A-Z0-9_][a-zA-Z0-9_]*$'
        
        if not re.match(pattern, name) and not re.match(r'^[A-Za-z0-9_]{4,100}$', name):
            return False, (
                "Invalid flag name format. Expected format:\n"
                "• FFlagSomething / DFlagSomething (for boolean flags)\n"
                "• FIntSomething / DFIntSomething (for integer flags)\n"
                "• FFloatSomething / DFFloatSomething (for float flags)\n"
                "• FStringSomething / DFStringSomething (for string flags)\n\n"
                "Examples:\n"
                "• FFlagEnableNewRendering\n"
                "• FIntTaskSchedulerTargetFps\n"
                "• DFIntTaskSchedulerTargetFps\n"
                "• DFStringCrashUploadToBacktraceBaseUrl"
            )
        
        return True, "Valid flag name format"
