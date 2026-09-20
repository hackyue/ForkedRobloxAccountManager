"""
Encryption utilities for Roblox Account Manager
Handles hardware-based and password-based encryption
"""

import os
import json
import base64
import hashlib
import platform
import subprocess
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2


class HardwareEncryption:
    """Hardware-based encryption using machine-specific identifiers"""
    
    def __init__(self, data_folder=None, config=None):
        self.data_folder = data_folder or self._resolve_data_folder()
        self.config = config or self._resolve_config()
        self.candidate_keys = []
        self.machine_id = self._get_machine_id()
        self.key = self._derive_key_from_machine_id(self.machine_id)
        if self.key not in self.candidate_keys:
            self.candidate_keys.insert(0, self.key)

    def _resolve_data_folder(self):
        try:
            from utils.paths import get_data_folder
            return get_data_folder()
        except Exception:
            return None

    def _resolve_config(self):
        try:
            if self.data_folder:
                cfg_path = os.path.join(self.data_folder, "encryption_config.json")
                return EncryptionConfig(cfg_path)
        except Exception:
            pass
        return None
    
    def _get_machine_id(self):
        """Generate unique machine ID from hardware identifiers and anchor stable keys"""
        def no_window_kwargs():
            if platform.system() != "Windows":
                return {}
            kwargs = {}
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if creation_flags:
                kwargs["creationflags"] = creation_flags
            startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
            if startupinfo_cls is not None:
                startupinfo = startupinfo_cls()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
                startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
                kwargs["startupinfo"] = startupinfo
            return kwargs
        
        hardware_parts = []
        anchored_guid = None
        backup_guid = None
        registry_guid = None

        if self.config and hasattr(self.config, 'get_hardware_guid'):
            anchored_guid = self.config.get_hardware_guid()

        if self.data_folder:
            b_path = os.path.join(self.data_folder, "rblxswap_backup.json")
            if os.path.exists(b_path):
                try:
                    with open(b_path, "r", encoding="utf-8-sig") as bf:
                        b_data = json.load(bf)
                        raw_guid = b_data.get("identifiers", {}).get("machineGuid")
                        if raw_guid and isinstance(raw_guid, str):
                            backup_guid = raw_guid.strip()
                except Exception:
                    pass

        try:
            if platform.system() == "Windows":
                try:
                    ps_cmd = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_ComputerSystemProduct).UUID']
                    res = subprocess.check_output(ps_cmd, **no_window_kwargs()).decode().strip()
                    if res:
                        hardware_parts.append(res)
                except Exception:
                    pass

                try:
                    ps_cmd = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_Processor).ProcessorId']
                    res = subprocess.check_output(ps_cmd, **no_window_kwargs()).decode().strip()
                    if res:
                        hardware_parts.append(res)
                except Exception:
                    pass

                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    if guid:
                        registry_guid = str(guid).strip()
                except Exception:
                    pass

            if not hardware_parts:
                hardware_parts.append(platform.node())
                hardware_parts.append(str(os.getuid()) if hasattr(os, 'getuid') else "0")
        except Exception:
            hardware_parts.append(platform.node())
            hardware_parts.append(platform.machine())

        chosen_guid = anchored_guid or backup_guid or registry_guid
        if chosen_guid and self.config and hasattr(self.config, 'set_hardware_guid') and not anchored_guid:
            try:
                self.config.set_hardware_guid(chosen_guid)
            except Exception:
                pass

        if chosen_guid:
            primary_identifiers = list(hardware_parts) + [chosen_guid]
        else:
            primary_identifiers = list(hardware_parts)

        primary_string = "-".join(primary_identifiers)

        candidate_strings = [primary_string]
        if backup_guid and backup_guid != chosen_guid:
            candidate_strings.append("-".join(list(hardware_parts) + [backup_guid]))
        if registry_guid and registry_guid != chosen_guid:
            candidate_strings.append("-".join(list(hardware_parts) + [registry_guid]))
        candidate_strings.append("-".join(hardware_parts))
        candidate_strings.append(f"{platform.node()}-{platform.machine()}")
        candidate_strings.append(platform.node())

        self.candidate_keys = []
        for ms in candidate_strings:
            mid = hashlib.sha256(ms.encode()).hexdigest()
            k1 = self._derive_key_from_machine_id(mid)
            if k1 not in self.candidate_keys:
                self.candidate_keys.append(k1)
            k2 = PBKDF2(mid, b'roblox_account_manager_salt_v1', dkLen=32, count=100000)
            if k2 not in self.candidate_keys:
                self.candidate_keys.append(k2)

        return hashlib.sha256(primary_string.encode()).hexdigest()
    
    def _derive_key_from_machine_id(self, machine_id=None):
        """Derive encryption key from machine ID"""
        mid = machine_id or self.machine_id
        salt = hashlib.sha256(b'roblox_account_manager_salt_v1_' + mid.encode()).digest()
        key = PBKDF2(mid, salt, dkLen=32, count=100000)
        return key
    
    def encrypt_data(self, data):
        """Encrypt data using hardware-based key"""
        if isinstance(data, dict):
            data = json.dumps(data, indent=2, ensure_ascii=False)
        
        data_bytes = data.encode('utf-8')
        
        cipher = AES.new(self.key, AES.MODE_GCM)
        nonce = cipher.nonce
        
        ciphertext, tag = cipher.encrypt_and_digest(data_bytes)
        
        encrypted_package = {
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'tag': base64.b64encode(tag).decode('utf-8'),
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8')
        }
        
        return encrypted_package
    
    def decrypt_data(self, encrypted_package):
        """Decrypt data using hardware-based key with candidate fallbacks"""
        try:
            nonce = base64.b64decode(encrypted_package['nonce'])
            tag = base64.b64decode(encrypted_package['tag'])
            ciphertext = base64.b64decode(encrypted_package['ciphertext'])
        except Exception as e:
            raise Exception(f"Decryption package invalid: {str(e)}")

        keys_to_try = [self.key] + [k for k in self.candidate_keys if k != self.key]

        for k in keys_to_try:
            try:
                cipher = AES.new(k, AES.MODE_GCM, nonce=nonce)
                data_bytes = cipher.decrypt_and_verify(ciphertext, tag)
                data_string = data_bytes.decode('utf-8')
                if k != self.key:
                    self.key = k
                try:
                    return json.loads(data_string)
                except (json.JSONDecodeError, ValueError):
                    return data_string
            except Exception:
                continue

        raise Exception("Decryption failed. This program may have been encrypted on a different machine.")


class PasswordEncryption:
    """Password-based encryption for portable account data"""
    
    def __init__(self, password, salt=None):
        if salt is None:
            self.salt = get_random_bytes(32)
        else:
            if isinstance(salt, str):
                self.salt = base64.b64decode(salt)
            else:
                self.salt = salt
        
        self.key = self._derive_key_from_password(password)
    
    def _derive_key_from_password(self, password):
        """Derive encryption key from password"""
        key = PBKDF2(password, self.salt, dkLen=32, count=100000)
        return key
    
    def get_salt_b64(self):
        """Get base64-encoded salt"""
        return base64.b64encode(self.salt).decode('utf-8')
    
    def encrypt_data(self, data):
        """Encrypt data using password-based key"""
        if isinstance(data, dict):
            data = json.dumps(data, indent=2, ensure_ascii=False)
        
        data_bytes = data.encode('utf-8')
        
        cipher = AES.new(self.key, AES.MODE_GCM)
        nonce = cipher.nonce
        
        ciphertext, tag = cipher.encrypt_and_digest(data_bytes)
        
        encrypted_package = {
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'tag': base64.b64encode(tag).decode('utf-8'),
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8')
        }
        
        return encrypted_package
    
    def decrypt_data(self, encrypted_package):
        """Decrypt data using password-based key"""
        try:
            nonce = base64.b64decode(encrypted_package['nonce'])
            tag = base64.b64decode(encrypted_package['tag'])
            ciphertext = base64.b64decode(encrypted_package['ciphertext'])
            
            cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
            
            data_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            
            data_string = data_bytes.decode('utf-8')
            
            try:
                return json.loads(data_string)
            except (json.JSONDecodeError, ValueError):
                return data_string
                
        except Exception as e:
            raise Exception(f"Decryption failed. Password may be incorrect. Error: {str(e)}")


class EncryptionConfig:
    """Manages encryption configuration and settings"""
    
    def __init__(self, config_file="encryption_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self):
        """Load encryption configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError, OSError):
                return {}
        return {}
    
    def save_config(self):
        """Save encryption configuration to file"""
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def is_encryption_enabled(self):
        """Check if encryption is enabled"""
        return self.config.get('encryption_enabled', False)
    
    def get_encryption_method(self):
        """Get current encryption method"""
        return self.config.get('encryption_method', None)
    
    def get_salt(self):
        """Get stored salt for password encryption"""
        return self.config.get('salt', None)
    
    def get_password_hash(self):
        """Get stored password hash"""
        return self.config.get('password_hash', None)
    
    def get_hardware_guid(self):
        """Get stored hardware GUID"""
        return self.config.get('hardware_guid', None)

    def set_hardware_guid(self, guid):
        """Set stored hardware GUID"""
        if guid:
            self.config['hardware_guid'] = str(guid).strip()
            self.save_config()

    def enable_hardware_encryption(self, hardware_guid=None):
        """Enable hardware-based encryption"""
        self.config['encryption_enabled'] = True
        self.config['encryption_method'] = 'hardware'
        self.config['no_encryption_chosen'] = False
        if hardware_guid:
            self.config['hardware_guid'] = str(hardware_guid).strip()
        if 'salt' in self.config:
            del self.config['salt']
        if 'password_hash' in self.config:
            del self.config['password_hash']
        if 'password_verified' in self.config:
            del self.config['password_verified']
        self.save_config()
    
    def enable_password_encryption(self, salt, password_hash):
        """Enable password-based encryption"""
        self.config['encryption_enabled'] = True
        self.config['encryption_method'] = 'password'
        self.config['salt'] = salt
        self.config['password_hash'] = password_hash
        self.config['password_verified'] = True
        self.config['no_encryption_chosen'] = False  
        if 'hardware_guid' in self.config:
            del self.config['hardware_guid']
        self.save_config()
    
    def is_no_encryption_chosen(self):
        """Check if user has explicitly chosen no encryption"""
        return self.config.get('no_encryption_chosen', False)
    
    def disable_encryption(self):
        """Disable encryption"""
        self.config['encryption_enabled'] = False
        self.config['encryption_method'] = None
        self.config['no_encryption_chosen'] = True  
        if 'salt' in self.config:
            del self.config['salt']
        if 'password_hash' in self.config:
            del self.config['password_hash']
        if 'hardware_guid' in self.config:
            del self.config['hardware_guid']
        self.save_config()

