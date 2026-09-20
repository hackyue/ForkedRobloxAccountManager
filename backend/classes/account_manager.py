"""
Account Manager class
Handles account storage, browser automation, and account management
"""

import os
import sys
import json
import base64
import time
import tempfile
import hashlib
import hmac
import shutil
import subprocess
import re
import threading
import platform
from pathlib import Path
from typing import Any, Optional, Sequence
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, NoSuchWindowException
from webdriver_manager.chrome import ChromeDriverManager
try:
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from webdriver_manager.firefox import GeckoDriverManager
except Exception:
    FirefoxService = None
    FirefoxOptions = None
    GeckoDriverManager = None

try:
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
except Exception:
    EdgeService = None
    EdgeOptions = None
    EdgeChromiumDriverManager = None

from .encryption import HardwareEncryption, PasswordEncryption, EncryptionConfig
from .roblox_api import RobloxAPI
from .browser_extensions import BrowserExtension, BrowserExtensionError, BrowserExtensionManager
from utils.error_detector import log_detailed_error



class RobloxAccountManager:
    LOGIN_DETECTION_INTERVAL_SECONDS = 0.25
    SUPPORTED_BROWSER_NAMES = ("chrome", "edge", "firefox", "waterfox", "chromium")
    GECKO_BROWSER_NAMES = {"firefox", "waterfox"}
    CHROMIUM_BROWSER_NAMES = {"chrome", "edge", "msedge", "chromium"}
    BROWSER_DISPLAY_NAMES = {
        "chrome": "Chrome",
        "edge": "Microsoft Edge",
        "msedge": "Microsoft Edge",
        "firefox": "Firefox",
        "waterfox": "Waterfox",
        "chromium": "Chromium",
    }
    _SELENIUM_POPEN_KW = {
        "creation_flags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
    } if os.name == "nt" else {}
    
    def __init__(self, password=None):
        from utils.paths import get_data_folder
        self.data_folder = get_data_folder()
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        self.accounts_file = os.path.join(self.data_folder, "saved_accounts.json")
        self.encryption_config = EncryptionConfig(os.path.join(self.data_folder, "encryption_config.json"))
        self.encryptor = None
        
        if self.encryption_config.is_encryption_enabled():
            method = self.encryption_config.get_encryption_method()
            if method == 'hardware':
                self.encryptor = HardwareEncryption(data_folder=self.data_folder, config=self.encryption_config)
            elif method == 'password':
                if password is None:
                    raise ValueError("Password required for password-based encryption")
                
                stored_hash = self.encryption_config.get_password_hash()
                if stored_hash:
                    salt = self.encryption_config.get_salt()
                    if salt:
                        temp_enc = PasswordEncryption(password, salt)
                        entered_hash = hashlib.sha256(temp_enc.key).hexdigest()
                    else:
                        entered_hash = hashlib.sha256(password.encode()).hexdigest()
                    if not hmac.compare_digest(entered_hash, stored_hash):
                        raise ValueError("Invalid password")
                
                salt = self.encryption_config.get_salt()
                self.encryptor = PasswordEncryption(password, salt)
        
        self.accounts = self.load_accounts()
        self.temp_profile_dir = None
        self.temp_profile_dirs = set()
        self._temp_profile_lock = threading.Lock()
        self.auto_rejoin_monitor = None
        self.browser_extension_manager: BrowserExtensionManager = BrowserExtensionManager(Path(self.data_folder))
        self.browser_extension_manager.ensure_storage()
        self.active_browser_drivers = []
        self._active_browser_automation_count = 0
        self._browser_automation_lock = threading.Lock()
        self._last_browser_closed_by_user = False
        self._last_browser_close_reason = None

    def _is_browser_closed_exception(self, exc):
        if exc is None:
            return False
        if isinstance(exc, NoSuchWindowException):
            return True
        err_str = str(exc).lower()
        close_keywords = (
            "target window",
            "no such window",
            "web view not found",
            "chrome not reachable",
            "invalid session id",
            "session deleted",
            "disconnected",
            "devtools",
            "connection refused",
            "connection reset",
            "failed to check if window was closed",
            "window was already closed",
            "browser has closed",
            "not connected to devtools",
            "remotedisconnected",
        )
        return any(kw in err_str for kw in close_keywords)

    def is_browser_automation_running(self):
        if not hasattr(self, '_browser_automation_lock'):
            self._browser_automation_lock = threading.Lock()
        with self._browser_automation_lock:
            return getattr(self, '_active_browser_automation_count', 0) > 0

    def _inc_browser_automation(self, count=1):
        if not hasattr(self, '_browser_automation_lock'):
            self._browser_automation_lock = threading.Lock()
        with self._browser_automation_lock:
            val = getattr(self, '_active_browser_automation_count', 0)
            self._active_browser_automation_count = val + max(1, count)

    def _dec_browser_automation(self, count=1):
        if not hasattr(self, '_browser_automation_lock'):
            self._browser_automation_lock = threading.Lock()
        with self._browser_automation_lock:
            val = getattr(self, '_active_browser_automation_count', 0)
            self._active_browser_automation_count = max(0, val - max(1, count))
        
    def load_accounts(self):
        """Load saved accounts from JSON file"""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict) and data.get('encrypted'):
                    if not self.encryptor:
                        raise ValueError("Failed to decrypt account files: Account file is encrypted but no decryption key or master password was provided.")
                    try:
                        decrypted_data = self.encryptor.decrypt_data(data['data'])
                        if not isinstance(decrypted_data, (dict, list)):
                            raise ValueError("Decrypted payload is invalid format.")
                        self._migrate_accounts(decrypted_data)
                        return decrypted_data
                    except Exception as e:
                        err_str = str(e)
                        if err_str.startswith("Failed to decrypt"):
                            raise ValueError(err_str)
                        raise ValueError(f"Failed to decrypt account files: {err_str}")
                

                if isinstance(data, dict):
                    self._migrate_accounts(data)
                return data if isinstance(data, dict) else {}
            except ValueError:
                raise
            except Exception as e:
                log_detailed_error("Error loading accounts file", exc=e, extra_info={"accounts_file": self.accounts_file}, source="account_manager")
                return {}
        return {}

    
    def _migrate_accounts(self, accounts):
        """Migrate old account data to include new fields"""
        for username, account_data in accounts.items():
            if isinstance(account_data, dict):
                if 'note' not in account_data:
                    account_data['note'] = ''
                if 'group' not in account_data:
                    account_data['group'] = ''
                if 'password' not in account_data:
                    account_data['password'] = ''
                if 'vip_server' not in account_data:
                    account_data['vip_server'] = ''
                if 'auto_rejoin_enabled' not in account_data:
                    account_data['auto_rejoin_enabled'] = False
                if 'user_id' not in account_data:
                    account_data['user_id'] = ''

    def normalize_private_server(self, value, roblosecurity_cookie=None):
        text = str(value or "").strip()
        if not text:
            return ""

        if not roblosecurity_cookie and hasattr(self, 'accounts') and isinstance(self.accounts, dict):
            for acc in self.accounts.values():
                if isinstance(acc, dict) and acc.get('cookie'):
                    roblosecurity_cookie = acc['cookie']
                    break

        return RobloxAPI.normalize_private_server(text, roblosecurity_cookie)
    
    def save_accounts(self):
        if not hasattr(self, '_save_lock'):
            self._save_lock = threading.Lock()
        with self._save_lock:
            tmp_path = f"{self.accounts_file}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    if self.encryptor:
                        encrypted_package = self.encryptor.encrypt_data(self.accounts)
                        encrypted_data = {
                            'encrypted': True,
                            'data': encrypted_package
                        }
                        json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
                    else:
                        json.dump(self.accounts, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                max_retries = 10
                for attempt in range(max_retries):
                    try:
                        os.replace(tmp_path, self.accounts_file)
                        break
                    except (PermissionError, OSError):
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(0.05 * (attempt + 1))
                if hasattr(self, 'on_save_callback') and callable(self.on_save_callback):
                    try:
                        self.on_save_callback()
                    except Exception:
                        pass
            except BaseException:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def _build_account_record(self, username: str, cookie: str, password: Optional[str] = None) -> dict[str, Any]:
        """Build an account record while preserving existing per-account metadata."""
        existing_account = self.accounts.get(username)
        if isinstance(existing_account, dict):
            account_record: dict[str, Any] = dict(existing_account)
        else:
            account_record = {}

        account_record.setdefault('added_date', time.strftime('%Y-%m-%d %H:%M:%S'))
        account_record.setdefault('note', '')
        account_record.setdefault('group', '')
        account_record.setdefault('vip_server', '')
        account_record.setdefault('auto_rejoin_enabled', False)
        account_record.setdefault('user_id', '')
        if password is None:
            account_record.setdefault('password', '')
        else:
            account_record['password'] = str(password)
        account_record['username'] = str(username)
        account_record['cookie'] = str(cookie)
        return account_record

    def reorder_accounts(self, ordered_usernames):
        """Reorder accounts to match the provided username list and persist the change."""
        if ordered_usernames is None:
            return

        existing_accounts = dict(self.accounts)
        if not existing_accounts:
            return

        normalized_order = []
        seen = set()
        for username in ordered_usernames:
            if username in existing_accounts and username not in seen:
                normalized_order.append(username)
                seen.add(username)

        for username in existing_accounts:
            if username not in seen:
                normalized_order.append(username)
                seen.add(username)

        current_order = list(self.accounts.keys())
        if normalized_order == current_order:
            return

        self.accounts = {username: existing_accounts[username] for username in normalized_order}
        self.save_accounts()

    def create_temp_profile(self):
        """Create a temporary browser profile directory"""
        profile_dir = tempfile.mkdtemp(prefix="roblox_login_")
        with self._temp_profile_lock:
            self.temp_profile_dir = profile_dir
            self.temp_profile_dirs.add(profile_dir)
        return profile_dir
    
    def cleanup_temp_profile(self, profile_dir=None):
        """Clean up temporary profile directory"""
        with self._temp_profile_lock:
            if profile_dir:
                targets = [str(profile_dir)]
            elif self.temp_profile_dirs:
                targets = list(self.temp_profile_dirs)
            elif self.temp_profile_dir:
                targets = [self.temp_profile_dir]
            else:
                targets = []
        for target in targets:
            if not target:
                continue
            try:
                if os.path.exists(target):
                    shutil.rmtree(target)
            except Exception:
                pass
            finally:
                with self._temp_profile_lock:
                    self.temp_profile_dirs.discard(target)
                    if self.temp_profile_dir == target:
                        self.temp_profile_dir = None

    def get_managed_chromium_root(self) -> Path:
        return Path(self.data_folder) / "browser_automation" / "chromium"

    def get_browser_extension_manager(self) -> BrowserExtensionManager:
        return self.browser_extension_manager

    def get_enabled_browser_extensions(self, browser_name: Optional[str] = None) -> list[BrowserExtension]:
        try:
            enabled_extensions = [
                extension
                for extension in self.browser_extension_manager.list_extensions()
                if extension.enabled
            ]
        except BrowserExtensionError as exc:
            print(f"[WARNING] Browser extensions could not be loaded: {exc}")
            return []

        normalized_browser_name = str(browser_name or "").strip().lower()
        if normalized_browser_name in self.CHROMIUM_BROWSER_NAMES:
            return [
                extension
                for extension in enabled_extensions
                if extension.source not in {"firefox_addons", "xpi"}
            ]
        if normalized_browser_name in self.GECKO_BROWSER_NAMES:
            return [
                extension
                for extension in enabled_extensions
                if extension.source not in {"web_store", "crx"}
            ]
        return enabled_extensions

    def get_enabled_browser_extension_paths(self, browser_name: Optional[str] = None) -> list[Path]:
        return [extension.directory for extension in self.get_enabled_browser_extensions(browser_name)]

    def get_managed_chromium_binary_path(self) -> Optional[Path]:
        root = self.get_managed_chromium_root()
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

    def get_managed_chromium_driver_path(self) -> Optional[Path]:
        root = self.get_managed_chromium_root()
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

    def _get_browser_display_name(self, browser_name: str) -> str:
        normalized_name = str(browser_name or "").strip().lower()
        return self.BROWSER_DISPLAY_NAMES.get(normalized_name, normalized_name.capitalize() or "Browser")

    def _get_browser_binary_path(self, browser_name: str) -> Optional[Path]:
        """Find an installed browser executable for local automation."""
        name = str(browser_name or "").strip().lower()
        if name == "chromium":
            return self.get_managed_chromium_binary_path()
        if name not in {"chrome", "edge", "msedge", "firefox", "waterfox"}:
            return None

        executable_name_by_browser = {
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "msedge": "msedge.exe",
            "firefox": "firefox.exe",
            "waterfox": "waterfox.exe",
        }
        executable_name = executable_name_by_browser[name]

        for command_name in (executable_name, executable_name[:-4]):
            resolved_path = shutil.which(command_name)
            if resolved_path and Path(resolved_path).is_file():
                return Path(resolved_path)

        candidates: list[Path] = []
        pf = os.environ.get("ProgramFiles")
        pfx86 = os.environ.get("ProgramFiles(x86)")
        localapp = os.environ.get("LOCALAPPDATA")
        appdata = os.environ.get("APPDATA")

        if name in ("edge", "msedge"):
            if pf:
                candidates.append(Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
            if pfx86:
                candidates.append(Path(pfx86) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
            if localapp:
                candidates.append(Path(localapp) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
        elif name == "chrome":
            if pf:
                candidates.append(Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe")
            if pfx86:
                candidates.append(Path(pfx86) / "Google" / "Chrome" / "Application" / "chrome.exe")
            if localapp:
                candidates.append(Path(localapp) / "Google" / "Chrome" / "Application" / "chrome.exe")
        elif name == "firefox":
            if pf:
                candidates.append(Path(pf) / "Mozilla Firefox" / "firefox.exe")
            if pfx86:
                candidates.append(Path(pfx86) / "Mozilla Firefox" / "firefox.exe")
            if localapp:
                candidates.append(Path(localapp) / "Mozilla Firefox" / "firefox.exe")
            if appdata:
                candidates.append(Path(appdata) / "Mozilla" / "Firefox" / "firefox.exe")
        elif name == "waterfox":
            waterfox_folders = ("Waterfox", "Waterfox Current", "Waterfox Classic")
            for base_path in (pf, pfx86):
                if not base_path:
                    continue
                for folder_name in waterfox_folders:
                    candidates.append(Path(base_path) / folder_name / "waterfox.exe")
            if localapp:
                for folder_name in waterfox_folders:
                    candidates.append(Path(localapp) / folder_name / "waterfox.exe")
                    candidates.append(Path(localapp) / "Programs" / folder_name / "waterfox.exe")
            if appdata:
                for folder_name in waterfox_folders:
                    candidates.append(Path(appdata) / folder_name / "waterfox.exe")

        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _is_browser_installed(self, browser_name):
        """Best-effort check for local browser executable presence."""
        name = (browser_name or "").strip().lower()
        if name not in self.SUPPORTED_BROWSER_NAMES:
            return False

        now = time.time()
        if not hasattr(self, '_browser_installed_cache'):
            self._browser_installed_cache = {}
            self._browser_installed_cache_time = 0

        if now - getattr(self, '_browser_installed_cache_time', 0) < 15.0 and name in getattr(self, '_browser_installed_cache', {}):
            return self._browser_installed_cache[name]

        result = False
        if name == "chromium":
            result = self.get_managed_chromium_binary_path() is not None and self.get_managed_chromium_driver_path() is not None
        elif name in self.GECKO_BROWSER_NAMES and (FirefoxService is None or FirefoxOptions is None or GeckoDriverManager is None):
            result = False
        else:
            try:
                path = self._get_browser_binary_path(name)
                result = path is not None
            except Exception:
                result = False

        if not hasattr(self, '_browser_installed_cache'):
            self._browser_installed_cache = {}
        self._browser_installed_cache[name] = result
        self._browser_installed_cache_time = now
        return result

    def has_supported_browser(self):
        return any(self._is_browser_installed(browser_name) for browser_name in self.SUPPORTED_BROWSER_NAMES)

    def get_available_browsers(self):
        return [b for b in self.SUPPORTED_BROWSER_NAMES if self._is_browser_installed(b)]

    def _get_browser_preference_order(self, preferred_browser=None):
        preferred = (preferred_browser or "").strip().lower()
        supported_browsers = list(self.SUPPORTED_BROWSER_NAMES)
        print(f"[Browser Preference] Input: {preferred_browser}, Processed: {preferred}, Supported: {supported_browsers}")
        
        if preferred and preferred in supported_browsers:
            result = [preferred] + [browser_name for browser_name in supported_browsers if browser_name != preferred]
            print(f"[Browser Preference] Using preferred browser order: {result}")
            return result
        if self._is_browser_installed("chromium"):
            return ["chromium", "chrome", "edge", "firefox", "waterfox"]
        return ["chrome", "edge", "firefox", "waterfox"]

    def _create_chrome_options(
        self,
        profile_dir: str,
        headless: bool = False,
        binary_path: Optional[Path] = None,
        extension_paths: Optional[Sequence[Path]] = None,
    ) -> Options:
        chrome_options = Options()
        if binary_path is not None:
            chrome_options.binary_location = str(binary_path)
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("detach", True)

        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-gpu-logging")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_experimental_option('useAutomationExtension', False)

        exclude_switches = {"enable-automation", "enable-logging"}
        chrome_options.add_experimental_option("excludeSwitches", sorted(exclude_switches))

        resolved_extension_paths = [
            str(Path(extension_path).resolve())
            for extension_path in (extension_paths or [])
            if Path(extension_path).is_dir()
        ]
        if resolved_extension_paths:
            extension_arg = ",".join(resolved_extension_paths)
            chrome_options.add_argument(f"--disable-extensions-except={extension_arg}")
            chrome_options.add_argument(f"--load-extension={extension_arg}")
        else:
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-component-extensions-with-background-pages")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-prompt-on-repost")
        chrome_options.add_argument("--disable-domain-reliability")
        chrome_options.add_argument("--disable-component-update")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--aggressive-cache-discard")
        if headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=520,700")
        return chrome_options

    def _resolve_edge_driver(self) -> Optional[str]:
        """Resolve or auto-download msedgedriver.exe from Microsoft's active endpoint."""
        driver_dir = Path(self.data_folder) / "browser_automation" / "msedgedriver"
        driver_exe = driver_dir / ("msedgedriver.exe" if os.name == "nt" else "msedgedriver")
        if driver_exe.is_file():
            return str(driver_exe)

        system_driver = shutil.which("msedgedriver.exe" if os.name == "nt" else "msedgedriver")
        if system_driver and os.path.isfile(system_driver):
            return system_driver

        if EdgeChromiumDriverManager is not None:
            try:
                wdm_path = EdgeChromiumDriverManager().install()
                if wdm_path and os.path.isfile(wdm_path):
                    return wdm_path
                if wdm_path:
                    dir_path = os.path.dirname(wdm_path)
                    exe_name = "msedgedriver.exe" if os.name == "nt" else "msedgedriver"
                    exe_path = os.path.join(dir_path, exe_name)
                    if os.path.isfile(exe_path):
                        return exe_path
            except Exception:
                pass

        try:
            edge_bin = self._get_browser_binary_path("edge")
            if not edge_bin or not edge_bin.is_file():
                return None

            escaped_path = str(edge_bin).replace("'", "''")
            cmd = ["powershell", "-NoProfile", "-Command", f"(Get-Item -LiteralPath '{escaped_path}').VersionInfo.FileVersion"]
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if platform.system() == "Windows" else 0
            version = subprocess.check_output(cmd, creationflags=flags).decode().strip()
            if not version:
                return None

            arch = "win64" if sys.maxsize > 2**32 else "win32"
            url = f"https://msedgedriver.microsoft.com/{version}/edgedriver_{arch}.zip"

            import zipfile
            import requests
            driver_dir.mkdir(parents=True, exist_ok=True)
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                zip_file = driver_dir / "edgedriver.zip"
                with open(zip_file, "wb") as f:
                    f.write(resp.content)
                with zipfile.ZipFile(zip_file, "r") as z:
                    z.extractall(driver_dir)
                try:
                    os.remove(zip_file)
                except Exception:
                    pass
                if driver_exe.is_file():
                    return str(driver_exe)
        except Exception:
            pass

        return None

    def _setup_edge_driver(self, headless: bool = False) -> Any:
        """Setup Microsoft Edge driver."""
        if EdgeService is None or EdgeOptions is None:
            raise RuntimeError("Microsoft Edge Selenium support is unavailable in this environment.")

        profile_dir = self.create_temp_profile()
        try:
            edge_options = EdgeOptions()
            binary_path = self._get_browser_binary_path("edge")
            if binary_path is not None:
                edge_options.binary_location = str(binary_path)
            edge_options.add_argument(f"--user-data-dir={profile_dir}")
            edge_options.add_argument("--no-first-run")
            edge_options.add_argument("--no-default-browser-check")
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_experimental_option('useAutomationExtension', False)
            edge_options.add_experimental_option("detach", True)
            edge_options.add_argument("--log-level=3")
            edge_options.add_argument("--silent")
            edge_options.add_argument("--disable-logging")
            edge_options.add_argument("--disable-gpu-logging")
            edge_options.add_argument("--disable-dev-tools")
            edge_options.add_argument("--disable-default-apps")

            exclude_switches = {"enable-automation", "enable-logging"}
            edge_options.add_experimental_option("excludeSwitches", sorted(exclude_switches))

            extension_paths = self.get_enabled_browser_extension_paths("edge")
            resolved_extension_paths = [
                str(Path(ext_path).resolve())
                for ext_path in extension_paths
                if Path(ext_path).is_dir()
            ]
            if resolved_extension_paths:
                ext_arg = ",".join(resolved_extension_paths)
                edge_options.add_argument(f"--disable-extensions-except={ext_arg}")
                edge_options.add_argument(f"--load-extension={ext_arg}")
            else:
                edge_options.add_argument("--disable-extensions")

            if headless:
                edge_options.add_argument("--headless=new")

            driver_path = self._resolve_edge_driver()
            if driver_path and os.path.isfile(driver_path):
                service = EdgeService(
                    driver_path,
                    log_output=os.devnull,
                    popen_kw=self._SELENIUM_POPEN_KW.copy(),
                )
                driver = webdriver.Edge(service=service, options=edge_options)
            else:
                driver = webdriver.Edge(options=edge_options)

            setattr(driver, "_ram_temp_profile_dir", profile_dir)
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            return driver
        except Exception:
            self.cleanup_temp_profile(profile_dir)
            raise

    def _setup_chrome_driver(self, headless=False):
        """Setup Chrome driver with speed-oriented options."""
        profile_dir = self.create_temp_profile()
        try:
            extension_paths = self.get_enabled_browser_extension_paths("chrome")
            chrome_options = self._create_chrome_options(profile_dir, headless=headless, extension_paths=extension_paths)
            driver_path = ChromeDriverManager().install()
            if driver_path and os.path.basename(driver_path).lower() != "chromedriver.exe" and os.path.basename(driver_path).lower() != "chromedriver":
                dir_path = os.path.dirname(driver_path)
                exe_name = "chromedriver.exe" if os.name == "nt" else "chromedriver"
                exe_path = os.path.join(dir_path, exe_name)
                if os.path.isfile(exe_path):
                    driver_path = exe_path
            service = Service(
                driver_path,
                log_path=os.devnull,
                popen_kw=self._SELENIUM_POPEN_KW.copy(),
            )
            driver = webdriver.Chrome(service=service, options=chrome_options)
            setattr(driver, "_ram_temp_profile_dir", profile_dir)
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            return driver
        except Exception:
            self.cleanup_temp_profile(profile_dir)
            raise

    def _setup_chromium_driver(self, headless: bool = False) -> Any:
        """Setup downloaded Chromium with its matching bundled driver."""
        browser_binary_path = self.get_managed_chromium_binary_path()
        driver_binary_path = self.get_managed_chromium_driver_path()
        if browser_binary_path is None or driver_binary_path is None:
            raise RuntimeError("Downloaded Chromium is not installed.")

        profile_dir = self.create_temp_profile()
        try:
            chrome_options = self._create_chrome_options(
                profile_dir,
                headless=headless,
                binary_path=browser_binary_path,
                extension_paths=self.get_enabled_browser_extension_paths("chromium"),
            )
            service = Service(
                str(driver_binary_path),
                log_path=os.devnull,
                popen_kw=self._SELENIUM_POPEN_KW.copy(),
            )
            driver = webdriver.Chrome(service=service, options=chrome_options)
            setattr(driver, "_ram_temp_profile_dir", profile_dir)
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except WebDriverException:
                pass
            return driver
        except (OSError, RuntimeError, WebDriverException):
            self.cleanup_temp_profile(profile_dir)
            raise

    def _install_firefox_extensions(self, driver: Any, browser_name: str = "firefox") -> None:
        display_name = self._get_browser_display_name(browser_name)
        for extension in self.get_enabled_browser_extensions(browser_name):
            try:
                driver.install_addon(str(extension.directory.resolve()), temporary=True)
            except (AttributeError, OSError, WebDriverException) as exc:
                print(f"[WARNING] {display_name} could not load extension {extension.name}: {exc}")

    def _setup_gecko_driver(self, browser_name: str, headless: bool = False) -> Any:
        """Setup a Firefox-compatible Gecko browser driver."""
        normalized_browser_name = str(browser_name or "firefox").strip().lower()
        if normalized_browser_name not in self.GECKO_BROWSER_NAMES:
            raise RuntimeError(f"Unsupported Gecko browser: {browser_name}")

        display_name = self._get_browser_display_name(normalized_browser_name)
        if FirefoxService is None or FirefoxOptions is None or GeckoDriverManager is None:
            raise RuntimeError(f"{display_name} Selenium support is unavailable in this environment.")

        profile_dir = self.create_temp_profile()
        try:
            firefox_options = FirefoxOptions()
            browser_binary_path = self._get_browser_binary_path(normalized_browser_name)
            if normalized_browser_name == "waterfox" and browser_binary_path is None:
                raise RuntimeError("Waterfox is not installed.")
            if browser_binary_path is not None:
                firefox_options.binary_location = str(browser_binary_path)
            firefox_options.add_argument("-profile")
            firefox_options.add_argument(profile_dir)
            firefox_options.set_preference("marionette.enabled", True)
            firefox_options.set_preference("dom.webdriver.enabled", False)
            firefox_options.set_preference("useAutomationExtension", False)
            firefox_options.set_preference("toolkit.telemetry.reportingpolicy.firstRun", False)
            firefox_options.set_preference("datareporting.healthreport.uploadEnabled", False)
            firefox_options.set_preference("browser.startup.homepage_override.mstone", "ignore")
            firefox_options.set_preference("browser.shell.checkDefaultBrowser", False)
            firefox_options.set_preference("app.update.auto", False)
            firefox_options.set_preference("app.update.enabled", False)
            if headless:
                firefox_options.add_argument("-headless")

            driver_path = GeckoDriverManager().install()
            if driver_path and os.path.basename(driver_path).lower() != "geckodriver.exe" and os.path.basename(driver_path).lower() != "geckodriver":
                dir_path = os.path.dirname(driver_path)
                exe_name = "geckodriver.exe" if os.name == "nt" else "geckodriver"
                exe_path = os.path.join(dir_path, exe_name)
                if os.path.isfile(exe_path):
                    driver_path = exe_path
            service = FirefoxService(
                driver_path,
                log_output=os.devnull,
                popen_kw=self._SELENIUM_POPEN_KW.copy(),
            )
            driver = webdriver.Firefox(service=service, options=firefox_options)
            setattr(driver, "_ram_temp_profile_dir", profile_dir)
            self._install_firefox_extensions(driver, normalized_browser_name)
            return driver
        except Exception as exc:
            self.cleanup_temp_profile(profile_dir)
            raise RuntimeError(f"Failed to start {display_name} automation: {exc}") from exc

    def _setup_firefox_driver(self, headless: bool = False) -> Any:
        """Setup Firefox driver with compatible performance options."""
        return self._setup_gecko_driver("firefox", headless=headless)

    def _setup_waterfox_driver(self, headless: bool = False) -> Any:
        """Setup Waterfox driver with compatible performance options."""
        return self._setup_gecko_driver("waterfox", headless=headless)

    def setup_browser_driver(self, preferred_browser=None, headless=False):
        """
        Setup a Selenium driver using supported browsers.
        Returns (driver, browser_name) or (None, None) on failure.
        """
        original_stderr = sys.stderr
        stderr_devnull = None
        attempted = []
        try:
            stderr_devnull = open(os.devnull, "w")
            sys.stderr = stderr_devnull

            browser_order = self._get_browser_preference_order(preferred_browser)
            print(f"[Browser Driver] Browser preference order: {browser_order}")
            
            for browser_name in browser_order:
                try:
                    print(f"[Browser Driver] Trying {browser_name}...")
                    if not self._is_browser_installed(browser_name):
                        print(f"[Browser Driver] {browser_name} not installed, skipping")
                        continue
                    print(f"[Browser Driver] {browser_name} is installed, setting up driver")
                    if browser_name == "chrome":
                        driver = self._setup_chrome_driver(headless=headless)
                    elif browser_name in ("edge", "msedge"):
                        driver = self._setup_edge_driver(headless=headless)
                    elif browser_name == "chromium":
                        driver = self._setup_chromium_driver(headless=headless)
                    elif browser_name == "firefox":
                        driver = self._setup_firefox_driver(headless=headless)
                    elif browser_name == "waterfox":
                        driver = self._setup_waterfox_driver(headless=headless)
                    else:
                        continue
                    print(f"[Browser Driver] Successfully set up {browser_name}")
                    return driver, browser_name
                except Exception as exc:
                    print(f"[Browser Driver] Failed to setup {browser_name}: {exc}")
                    attempted.append((browser_name, str(exc)))
                    if browser_name == "chrome":
                        print(f"[Browser Driver] Chrome setup failed, skipping to next browser")
                        continue

            print(f"[Browser Driver] First attempt failed, trying fallback...")
            for browser_name in browser_order:
                try:
                    print(f"[Browser Driver] Fallback trying {browser_name}...")
                    if browser_name == "chrome":
                        driver = self._setup_chrome_driver(headless=headless)
                    elif browser_name in ("edge", "msedge"):
                        driver = self._setup_edge_driver(headless=headless)
                    elif browser_name == "chromium":
                        driver = self._setup_chromium_driver(headless=headless)
                    elif browser_name == "firefox":
                        driver = self._setup_firefox_driver(headless=headless)
                    elif browser_name == "waterfox":
                        driver = self._setup_waterfox_driver(headless=headless)
                    else:
                        continue
                    print(f"[Browser Driver] Fallback successfully set up {browser_name}")
                    return driver, browser_name
                except Exception as exc:
                    print(f"[Browser Driver] Fallback failed for {browser_name}: {exc}")
                    attempted.append((browser_name, str(exc)))
        finally:
            sys.stderr = original_stderr
            if stderr_devnull is not None:
                try:
                    stderr_devnull.close()
                except Exception:
                    pass

        if attempted:
            details = ", ".join([f"{name}: {err}" for name, err in attempted])
            print(f"Error setting up browser driver: {details}")
        else:
            print("Error setting up browser driver: no supported browser available.")
        print("Please make sure Google Chrome, Mozilla Firefox, Waterfox, or downloaded Chromium is installed.")
        return None, None

    def setup_chrome_driver(self):
        """
        Backward-compatible wrapper that supports fallback to Firefox, Waterfox, or downloaded Chromium.
        """
        driver, _browser = self.setup_browser_driver(preferred_browser="chrome")
        return driver
    
    def wait_for_login(self, driver, timeout=300):
        """
        Ultra-fast login detection using URL checks.
        Returns a tuple: (logged_in: bool, captured_password: str)
        """
        print("Please log into your Roblox account")
        captured_password = ""
        
        detect_interval_ms = max(50, int(self.LOGIN_DETECTION_INTERVAL_SECONDS * 1000))
        detector_script = """
        window.ultraFastDetection = {
            detected: false,
            method: null,
            debug: [],
            capturedPassword: '',
            interval: null,
            observer: null,
            eventHandlers: [],
            cleanup: function() {
                if (this.interval) {
                    clearInterval(this.interval);
                    this.interval = null;
                }
                if (this.observer) {
                    this.observer.disconnect();
                    this.observer = null;
                }
                if (Array.isArray(this.eventHandlers)) {
                    this.eventHandlers.forEach(function(item) {
                        if (item && item.event && item.handler) {
                            window.removeEventListener(item.event, item.handler);
                        }
                    });
                    this.eventHandlers = [];
                }
            }
        };
        
        function instantDetect() {
            const url = window.location.href.toLowerCase();
            try {
                const passwordField = document.querySelector(
                    "input#login-password, input[name='password'], input[type='password']"
                );
                if (passwordField && typeof passwordField.value === 'string' && passwordField.value.length > 0) {
                    window.ultraFastDetection.capturedPassword = passwordField.value;
                }
            } catch (_captureError) {}
             
            if (url.includes('/login') || url.includes('/signup') || url.includes('/createaccount')) {
                return false;
            }
            
            if (url.includes('/not-approved') || url.includes('/notapproved')) {
                window.ultraFastDetection.detected = true;
                window.ultraFastDetection.method = 'not_approved_url';
                window.ultraFastDetection.debug.push('DETECTED via NOT-APPROVED URL! Page: ' + url);
                window.ultraFastDetection.cleanup();
                return true;
            }

            if (url.includes('/home') || url.includes('/games') || 
                url.includes('/catalog') || url.includes('/avatar') ||
                url.includes('/discover') || url.includes('/friends') ||
                url.includes('/profile') || url.includes('/groups') ||
                url.includes('/develop') || url.includes('/create') ||
                url.includes('/transactions') || url.includes('/my/avatar') ||
                (url.includes('roblox.com/users/') && !url.includes('/login'))) {
                
                window.ultraFastDetection.detected = true;
                window.ultraFastDetection.method = 'url_only';
                window.ultraFastDetection.debug.push('✅ DETECTED via URL! Page: ' + url);
                window.ultraFastDetection.cleanup();
                return true;
            }
            
            return false;
        }
        
        function registerCleanupEvent(eventName, handler) {
            window.addEventListener(eventName, handler);
            window.ultraFastDetection.eventHandlers.push({ event: eventName, handler: handler });
        }
        
        instantDetect();
        
        window.ultraFastDetection.interval = setInterval(() => {
            if (instantDetect()) {
                window.ultraFastDetection.cleanup();
            }
        }, __DETECT_INTERVAL_MS__);
        
        let lastHref = location.href;
        window.ultraFastDetection.observer = new MutationObserver(() => {
            if (location.href !== lastHref) {
                lastHref = location.href;
                window.ultraFastDetection.debug.push('URL changed to: ' + location.href);
                if (window.ultraFastDetection.debug.length > 40) {
                    window.ultraFastDetection.debug = window.ultraFastDetection.debug.slice(-40);
                }
                if (instantDetect()) {
                    window.ultraFastDetection.cleanup();
                }
            }
        });
        window.ultraFastDetection.observer.observe(document, {subtree: true, childList: true});
        
        ['beforeunload', 'unload', 'pagehide'].forEach(event => {
            registerCleanupEvent(event, () => {
                window.ultraFastDetection.cleanup();
            });
        });
        """
        detector_script = detector_script.replace("__DETECT_INTERVAL_MS__", str(detect_interval_ms))
        
        try:
            driver.execute_script(detector_script)
            print("[SUCCESS] Detection script injected successfully")
        except Exception as e:
            if self._is_browser_closed_exception(e):
                print("[INFO] Browser window closed by user.")
                return False, captured_password, "user_closed"
            print(f"[WARNING] Warning: Could not inject detection script: {e}")
        
        start_time = time.time()
        last_debug_time = 0
        last_password_probe_time = 0.0

        def cleanup_detection():
            try:
                driver.execute_script(
                    "if (window.ultraFastDetection && typeof window.ultraFastDetection.cleanup === 'function') "
                    "{ window.ultraFastDetection.cleanup(); }"
                )
            except Exception:
                pass
        
        while time.time() - start_time < timeout:
            try:
                result = driver.execute_script("return window.ultraFastDetection;")
                
                if result:
                    js_password = result.get('capturedPassword')
                    if isinstance(js_password, str) and js_password:
                        captured_password = js_password

                current_time = time.time()
                if (current_time - last_password_probe_time) >= 0.75:
                    last_password_probe_time = current_time
                    try:
                        password_fields = driver.find_elements(
                            By.CSS_SELECTOR,
                            "input#login-password, input[name='password'], input[type='password']"
                        )
                        for password_field in password_fields:
                            try:
                                field_value = password_field.get_attribute("value")
                            except Exception:
                                field_value = ""
                            if isinstance(field_value, str) and field_value:
                                captured_password = field_value
                                break
                    except Exception:
                        pass

                if result and result.get('detected'):
                    method = result.get('method', 'url_only')
                    print(f"[SUCCESS] LOGIN DETECTED! Method: {method} - Closing browser instantly...")
                    cleanup_detection()
                    return True, captured_password, "success"

                if current_time - last_debug_time > 5:
                    last_debug_time = current_time
                    try:
                        current_url = driver.current_url
                        print(f"Still checking... Current URL: {current_url}")
                        
                        if result and result.get('debug'):
                            recent_debug = result.get('debug', [])[-3:]
                            for debug_msg in recent_debug:
                                print(f"Debug: {debug_msg}")
                        
                        if ('/home' in current_url or '/games' in current_url or 
                            '/catalog' in current_url or '/avatar' in current_url or
                            '/discover' in current_url or '/friends' in current_url or
                            '/profile' in current_url or '/groups' in current_url or
                            '/develop' in current_url or '/create' in current_url or
                            '/not-approved' in current_url or '/notapproved' in current_url) and '/login' not in current_url and '/createaccount' not in current_url.lower():
                            print("[SUCCESS] LOGIN DETECTED via manual URL check!")
                            cleanup_detection()
                            return True, captured_password, "success"
                                
                    except (NoSuchWindowException, WebDriverException) as window_err:
                        if self._is_browser_closed_exception(window_err):
                            print("[INFO] Browser window closed by user.")
                            cleanup_detection()
                            return False, captured_password, "user_closed"
                        print(f"Debug error: {window_err}")
                    except Exception as e:
                        if self._is_browser_closed_exception(e):
                            print("[INFO] Browser window closed by user.")
                            cleanup_detection()
                            return False, captured_password, "user_closed"
                        print(f"Debug error: {e}")
                
                time.sleep(self.LOGIN_DETECTION_INTERVAL_SECONDS)
                
            except (NoSuchWindowException, WebDriverException) as window_err:
                if self._is_browser_closed_exception(window_err):
                    print("[INFO] Browser window closed by user.")
                cleanup_detection()
                return False, captured_password, "user_closed"
            except Exception as loop_err:
                if self._is_browser_closed_exception(loop_err):
                    print("[INFO] Browser window closed by user.")
                    cleanup_detection()
                    return False, captured_password, "user_closed"
                print(f"[DEBUG] Error during login check: {loop_err}")
                cleanup_detection()
                return False, captured_password, "error"
        
        print("[WARNING] Login timeout. Please try again.")
        cleanup_detection()
        return False, captured_password, "timeout"
    
    def extract_user_info(self, driver):
        """Extract username and cookie with ultra-fast detection"""
        try:
            roblosecurity_cookie = None
            cookies = driver.get_cookies()
            
            for cookie in cookies:
                if cookie['name'] == '.ROBLOSECURITY':
                    roblosecurity_cookie = cookie['value']
                    break
            
            if not roblosecurity_cookie:
                return None, None
            
            username = None
            try:
                result = driver.execute_script("return window.ultraFastDetection;")
                if result and result.get('username'):
                    username = result.get('username')
                    print(f"[SUCCESS] Username detected from page: {username}")
            except:
                pass
            
            if not username:
                try:
                    username_selectors = [
                        "[data-testid='navigation-user-display-name']",
                        "[data-testid='user-menu-button']",
                        ".font-header-2.text-color-secondary-alt",
                        "#nav-username",
                        ".navigation-user-name"
                    ]
                    
                    for selector in username_selectors:
                        try:
                            element = driver.find_element(By.CSS_SELECTOR, selector)
                            if element and element.text.strip():
                                username = element.text.strip()
                                break
                        except:
                            continue
                            
                except Exception:
                    pass

            if not username:
                try:
                    js_meta_user = driver.execute_script(
                        """
                        try {
                            var meta = document.querySelector("meta[name='user-data']");
                            if (meta) {
                                var name = meta.getAttribute("data-name");
                                var uid = meta.getAttribute("data-userid");
                                if (name) return { username: name, userId: uid };
                            }
                            if (window.Roblox && window.Roblox.CurrentUser) {
                                return {
                                    username: window.Roblox.CurrentUser.name || window.Roblox.CurrentUser.username,
                                    userId: window.Roblox.CurrentUser.userId || window.Roblox.CurrentUser.id
                                };
                            }
                        } catch (e) {}
                        return null;
                        """
                    )
                    if js_meta_user and isinstance(js_meta_user, dict):
                        if js_meta_user.get('username'):
                            username = str(js_meta_user.get('username')).strip()
                        elif js_meta_user.get('userId'):
                            resolved = RobloxAPI.get_username_from_user_id(js_meta_user.get('userId'))
                            if resolved:
                                username = resolved
                except Exception:
                    pass

            if not username:
                try:
                    current_url = getattr(driver, "current_url", "")
                    import re
                    uid_match = re.search(r'[?&]userId=(\d+)', str(current_url), re.IGNORECASE)
                    if uid_match:
                        resolved_user = RobloxAPI.get_username_from_user_id(uid_match.group(1))
                        if resolved_user:
                            username = resolved_user
                except Exception:
                    pass
            
            if not username:
                username = RobloxAPI.get_username_from_api(roblosecurity_cookie)

            if not username or username == "Unknown":
                profile = RobloxAPI.get_user_profile_from_cookie(roblosecurity_cookie)
                if profile and profile.get('username'):
                    username = profile.get('username')
            
            if not username or username == "Unknown":
                curr_url_l = str(getattr(driver, "current_url", "")).lower()
                if "/not-approved" in curr_url_l or "/notapproved" in curr_url_l:
                    username = f"BannedUser_{abs(hash(roblosecurity_cookie)) % 100000}"
                else:
                    username = "Unknown"
            
            return username, roblosecurity_cookie
            
        except Exception as e:
            print(f"Error extracting user info: {e}")
            return None, None

    def extract_captured_password(self, driver):
        """Extract a password captured from the Roblox login page (if available)."""
        captured_password = ""
        try:
            captured_password = driver.execute_script(
                """
                try {
                    if (window.ultraFastDetection && typeof window.ultraFastDetection.capturedPassword === 'string') {
                        return window.ultraFastDetection.capturedPassword;
                    }
                } catch (_windowReadError) {}
                return "";
                """
            )
        except Exception:
            captured_password = ""

        if not isinstance(captured_password, str):
            captured_password = ""

        return captured_password

    def _extract_quick_sign_in_data(self, driver):
        try:
            script = r"""
            const response = {
                modalOpen: false,
                code: "",
                qrImageUrl: ""
            };

            const titleEl = document.querySelector([
                ".cross-device-login-display-code-modal-title-container .modal-title",
                "h4.modal-title",
                "h3.modal-title",
                "[data-testid*='cross-device']",
                ".modal-header"
            ].join(","));

            const titleText = (titleEl ? (titleEl.textContent || "") : "").toLowerCase();
            const bodyText = (document.body ? (document.body.innerText || "") : "").toLowerCase();

            const isModalDetected = titleText.includes("quick") ||
                                    titleText.includes("cross") ||
                                    titleText.includes("device") ||
                                    bodyText.includes("quick sign-in") ||
                                    bodyText.includes("quick log in") ||
                                    bodyText.includes("another device") ||
                                    bodyText.includes("enter this code on your other device");

            response.modalOpen = isModalDetected;

            const codeCandidates = [];

            const directCodeEls = document.querySelectorAll([
                ".cross-device-login-display-code-modal-title-container ~ .modal-body .font-title",
                ".modal-body .font-title",
                ".cross-device-login-code",
                "[data-testid*='code']",
                "span.font-title",
                "div.font-title",
                "h2.font-title"
            ].join(","));

            directCodeEls.forEach(el => {
                const txt = (el.textContent || "").trim();
                if (txt) codeCandidates.push(txt);
            });

            const imgEl = document.querySelector([
                "img.cross-device-login-display-qr-code-image",
                ".cross-device-login-display-qr-code-image img",
                "img[src*='auth-token-service']",
                "img[src*='qr']",
                "img[alt*='QR']",
                "img[alt*='qr']",
                "[data-testid*='qr'] img",
                "[data-testid*='qr-code'] img"
            ].join(","));

            if (imgEl) {
                let src = imgEl.getAttribute("src") || imgEl.src || "";
                if (src) {
                    try {
                        const url = new URL(src, window.location.origin);
                        src = url.href;
                        const codeFromParam = url.searchParams.get("code");
                        if (codeFromParam) codeCandidates.push(codeFromParam);
                    } catch (_) {}

                    try {
                        if (imgEl.complete && imgEl.naturalWidth > 0) {
                            const canvas = document.createElement("canvas");
                            canvas.width = imgEl.naturalWidth;
                            canvas.height = imgEl.naturalHeight;
                            const ctx = canvas.getContext("2d");
                            ctx.drawImage(imgEl, 0, 0);
                            const dataUrl = canvas.toDataURL("image/png");
                            if (dataUrl && dataUrl.startsWith("data:image")) {
                                src = dataUrl;
                            }
                        }
                    } catch (_) {}

                    response.qrImageUrl = src;
                }
            }

            if (!response.qrImageUrl) {
                const canvasEl = document.querySelector([
                    "canvas.cross-device-login-display-qr-code-image",
                    ".cross-device-login-display-qr-code-image canvas",
                    "canvas[data-testid*='qr']",
                    "[data-testid*='qr-code'] canvas",
                    ".modal-body canvas"
                ].join(","));
                if (canvasEl) {
                    try {
                        response.qrImageUrl = canvasEl.toDataURL("image/png");
                    } catch (_) {}
                }
            }

            if (!response.qrImageUrl) {
                const svgEl = document.querySelector([
                    "svg.cross-device-login-display-qr-code-image",
                    ".cross-device-login-display-qr-code-image svg",
                    "svg[data-testid*='qr']",
                    "[data-testid*='qr-code'] svg",
                    ".modal-body svg[class*='qr']"
                ].join(","));
                if (svgEl) {
                    try {
                        const svgXml = new XMLSerializer().serializeToString(svgEl);
                        response.qrImageUrl = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgXml);
                    } catch (_) {}
                }
            }

            const allElements = document.querySelectorAll("div, span, p, h1, h2, h3, h4, h5, h6");
            allElements.forEach(el => {
                if (el.children.length === 0) {
                    const text = (el.textContent || "").trim();
                    if (/^[A-Za-z0-9]{6}$/.test(text) || /^[A-Za-z0-9]{3}[\s-][A-Za-z0-9]{3}$/.test(text)) {
                        codeCandidates.push(text);
                    }
                }
            });

            for (const candidate of codeCandidates) {
                const normalized = candidate.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
                if (normalized.length === 6) {
                    response.code = normalized;
                    response.modalOpen = true;
                    break;
                }
            }

            return response;
            """
            raw_value = driver.execute_script(script)
            if isinstance(raw_value, dict):
                return raw_value
        except Exception:
            pass
        return {"modalOpen": False, "code": "", "qrImageUrl": ""}

    def _extract_quick_sign_in_code(self, driver):
        """Extract just the 6-character code string for compatibility."""
        data = self._extract_quick_sign_in_data(driver)
        return str(data.get("code") or "")

    def _quick_sign_in_button_candidates(self):
        return [
            (By.CSS_SELECTOR, "button[data-testid*='quick']"),
            (By.CSS_SELECTOR, "button[data-testid*='cross-device']"),
            (By.CSS_SELECTOR, "button[data-testid*='crossDevice']"),
            (By.CSS_SELECTOR, "button[data-testid*='another-device']"),
            (By.CSS_SELECTOR, "button[data-testid*='signin']"),
            (By.CSS_SELECTOR, "button[id*='quick']"),
            (By.CSS_SELECTOR, "button[class*='quick']"),
            (By.CSS_SELECTOR, "button[class*='cross-device']"),
            (By.CSS_SELECTOR, "a[data-testid*='quick']"),
            (By.CSS_SELECTOR, "a[data-testid*='cross-device']"),
            (By.CSS_SELECTOR, "a[id*='quick']"),
            (By.CSS_SELECTOR, "a[class*='quick']"),
            (By.CSS_SELECTOR, "a[class*='cross-device']"),
            (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'quick')]"),
            (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'another device')]"),
            (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cross-device')]"),
            (By.XPATH, "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'quick')]"),
            (By.XPATH, "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'another device')]"),
            (By.XPATH, "//div[@role='button' and contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'quick')]"),
        ]

    def _open_quick_sign_in_panel(self, driver):
        """Find and click the Quick Sign-In or Cross-Device login button on the login page."""
        try:
            js_script = """
            const clickables = Array.from(document.querySelectorAll('button, a, div[role="button"], span[role="button"], input[type="button"]'));
            for (const el of clickables) {
                const text = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                const testId = (el.getAttribute('data-testid') || '').toLowerCase();
                const className = (el.className || '').toString().toLowerCase();
                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();

                if (
                    text.includes('quick') ||
                    text.includes('another device') ||
                    text.includes('cross-device') ||
                    text.includes('cross device') ||
                    testId.includes('quick') ||
                    testId.includes('cross-device') ||
                    testId.includes('another-device') ||
                    className.includes('quick-login') ||
                    className.includes('cross-device') ||
                    ariaLabel.includes('quick')
                ) {
                    try {
                        el.scrollIntoView({ behavior: 'auto', block: 'center' });
                        el.click();
                        return true;
                    } catch (_) {
                        try {
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            return true;
                        } catch (__) {}
                    }
                }
            }
            return false;
            """
            if driver.execute_script(js_script):
                print("[Quick Sign-In] Clicked Quick Sign-In button via JavaScript locator.")
                return True
        except Exception as err:
            print(f"[Quick Sign-In] JS click check warning: {err}")

        for by, selector in self._quick_sign_in_button_candidates():
            try:
                elements = driver.find_elements(by, selector)
            except Exception:
                elements = []
            for element in elements:
                try:
                    if not element.is_displayed():
                        continue
                    element.click()
                    print(f"[Quick Sign-In] Clicked Quick Sign-In button via selector: {selector}")
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", element)
                        print(f"[Quick Sign-In] Clicked Quick Sign-In button via JS click on: {selector}")
                        return True
                    except Exception:
                        continue
        return False

    def _is_likely_logged_in_url(self, url):
        url_l = str(url or "").lower()
        if "/login" in url_l or "/signup" in url_l or "/createaccount" in url_l:
            return False
        for token in (
            "/home",
            "/games",
            "/catalog",
            "/avatar",
            "/discover",
            "/friends",
            "/profile",
            "/groups",
            "/develop",
            "/create",
            "/transactions",
            "/my/avatar",
            "/not-approved",
            "/notapproved",
        ):
            if token in url_l:
                return True
        return "roblox.com/users/" in url_l

    def add_account_quick_sign_in(
        self,
        preferred_browser="auto",
        on_code=None,
        on_status=None,
        on_success=None,
        timeout=300,
        cancel_event=None,
    ):
        self._inc_browser_automation()
        driver = None
        try:
            if cancel_event is not None and cancel_event.is_set():
                return {
                    "success": False,
                    "username": "",
                    "code": "",
                    "error": "Quick Sign-In cancelled.",
                }

            if callable(on_status):
                on_status("Starting background browser...")

            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            driver, browser_name = self.setup_browser_driver(preferred_browser=preferred, headless=True)
            if not driver:
                return {
                    "success": False,
                    "username": "",
                    "code": "",
                    "error": "Unable to open a supported browser. Please ensure Chrome or Firefox is installed.",
                }

            if cancel_event is not None and cancel_event.is_set():
                return {
                    "success": False,
                    "username": "",
                    "code": "",
                    "error": "Quick Sign-In cancelled.",
                }

            if callable(on_status):
                on_status(f"Navigating to Roblox login...")

            try:
                driver.set_window_size(600, 800)
            except Exception:
                pass

            print("[Quick Sign-In] Navigating to https://www.roblox.com/login")
            driver.get("https://www.roblox.com/login")

            start_nav = time.time()
            opened_panel = False
            while time.time() - start_nav < 10:
                if cancel_event is not None and cancel_event.is_set():
                    return {
                        "success": False,
                        "username": "",
                        "code": "",
                        "error": "Quick Sign-In cancelled.",
                    }
                opened_panel = self._open_quick_sign_in_panel(driver)
                if opened_panel:
                    break
                time.sleep(0.5)

            if callable(on_status):
                on_status("Generating one-time sign-in code...")

            start_time = time.time()
            last_code = ""
            last_qr = ""

            while time.time() - start_time < timeout:
                if cancel_event is not None and cancel_event.is_set():
                    return {
                        "success": False,
                        "username": "",
                        "code": last_code,
                        "error": "Quick Sign-In cancelled.",
                    }

                sign_in_data = self._extract_quick_sign_in_data(driver)
                quick_code = sign_in_data.get("code") or ""
                qr_image_url = sign_in_data.get("qrImageUrl") or ""

                if quick_code and (quick_code != last_code or qr_image_url != last_qr):
                    last_code = quick_code
                    last_qr = qr_image_url
                    print(f"[Quick Sign-In] Detected code: {last_code}")
                    if callable(on_code):
                        try:
                            on_code(last_code, last_qr)
                        except TypeError:
                            on_code(last_code)
                    if callable(on_status):
                        on_status(f"Code {last_code} ready! Approve it on your other device.")

                if not quick_code and not opened_panel:
                    opened_panel = self._open_quick_sign_in_panel(driver)

                current_url = ""
                try:
                    current_url = driver.current_url
                except Exception:
                    current_url = ""

                has_cookie = False
                roblosecurity_cookie = ""
                try:
                    cookies = driver.get_cookies()
                    for cookie_obj in cookies:
                        if cookie_obj.get("name") == ".ROBLOSECURITY":
                            has_cookie = True
                            roblosecurity_cookie = cookie_obj.get("value", "")
                            break
                except Exception:
                    has_cookie = False

                if has_cookie or self._is_likely_logged_in_url(current_url):
                    if callable(on_status):
                        on_status("Authentication approved! Fetching account details...")

                    username = ""
                    cookie = roblosecurity_cookie
                    if not cookie:
                        username, cookie = self.extract_user_info(driver)
                    else:
                        username = RobloxAPI.get_username_from_api(cookie)

                    if not username or username == "Unknown":
                        extracted_username, extracted_cookie = self.extract_user_info(driver)
                        if extracted_username and extracted_username != "Unknown":
                            username = extracted_username
                        if not cookie and extracted_cookie:
                            cookie = extracted_cookie

                    if username and cookie:
                        user_id = ""
                        display_name = username
                        avatar_url = ""
                        status = "valid"
                        try:
                            status, found_uid, found_user, found_display, found_avatar = RobloxAPI.get_account_status_and_info(
                                cookie=cookie,
                                username=username
                            )
                            if found_uid:
                                user_id = found_uid
                            if found_user and found_user != "Unknown":
                                username = found_user
                            if found_display:
                                display_name = found_display
                            if found_avatar:
                                avatar_url = found_avatar
                        except Exception:
                            pass

                        record = self._build_account_record(username, cookie)
                        record["status"] = status
                        if user_id:
                            record["user_id"] = user_id
                        if display_name:
                            record["display_name"] = display_name
                        if avatar_url:
                            record["avatar_url"] = avatar_url

                        self.accounts[username] = record
                        self.save_accounts()

                        result_data = {
                            "success": True,
                            "username": username,
                            "display_name": display_name,
                            "user_id": user_id,
                            "avatar_url": avatar_url,
                            "code": last_code,
                            "error": "",
                        }

                        if callable(on_status):
                            on_status(f"Success! Account @{username} added.")

                        if callable(on_success):
                            try:
                                on_success(result_data)
                            except Exception:
                                pass

                        return result_data

                time.sleep(0.35)

            return {
                "success": False,
                "username": "",
                "code": last_code,
                "error": "Quick Sign-In timed out. Please try again.",
            }
        except Exception as exc:
            return {
                "success": False,
                "username": "",
                "code": "",
                "error": str(exc),
            }
        finally:
            self._dec_browser_automation()
            if driver is not None:
                def async_cleanup(d, p):
                    try:
                        d.quit()
                    except Exception:
                        pass
                    self.cleanup_temp_profile(p)

                cleanup_thread = threading.Thread(
                    target=async_cleanup,
                    args=(driver, getattr(driver, "_ram_temp_profile_dir", None)),
                    daemon=True
                )
                cleanup_thread.start()
    
    def add_account(self, amount=1, website="https://www.roblox.com/login", preferred_browser="auto"):
        """
        Add accounts through browser login
        amount: number of browser instances to open (max 10)
        website: URL to navigate to
        """
        self._last_browser_closed_by_user = False
        self._last_browser_close_reason = None
        self._inc_browser_automation()
        if amount > 10:
            print("[WARNING] Maximum 10 instances allowed. Setting to 10.")
            amount = 10
        
        success_count = 0
        success_count_lock = threading.Lock()
        drivers = []
        
        try:
            print(f"Launching {amount} browser instance(s) with preferred browser: {preferred_browser}")
            
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            print(f"Processed preferred browser: {preferred}")
            for i in range(amount):
                driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
                if not driver:
                    print(f"[ERROR] Failed to setup browser driver for instance {i + 1}")
                    continue
                
                try:
                    window_width = 500
                    window_height = 600
                    
                    screen_width = driver.execute_script("return screen.width;")
                    screen_height = driver.execute_script("return screen.height;")
                    
                    grid_cols = min(3, amount)
                    grid_rows = (amount + grid_cols - 1) // grid_cols
                    
                    col = i % grid_cols
                    row = i // grid_cols
                    
                    x = col * (screen_width // grid_cols) + 10
                    y = row * ((screen_height - 100) // grid_rows) + 10
                    
                    driver.set_window_position(x, y)
                    driver.set_window_size(window_width, window_height)
                except Exception as win_err:
                    if self._is_browser_closed_exception(win_err):
                        print(f"[INFO] Browser instance {i + 1} closed by user during startup.")
                        self._last_browser_closed_by_user = True
                        self._last_browser_close_reason = "user_closed"
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
                        continue
                    print(f"[WARNING] Could not set window position for instance {i + 1}: {win_err}")
                
                drivers.append(driver)
                
                try:
                    print(f"Opening {website} in {browser_name.capitalize()} (instance {i + 1}/{amount})...")
                    driver.get(website)
                except Exception as e:
                    if self._is_browser_closed_exception(e):
                        print(f"[INFO] Browser instance {i + 1} closed by user during navigation.")
                        self._last_browser_closed_by_user = True
                        self._last_browser_close_reason = "user_closed"
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
                        drivers.remove(driver)
                        continue
                    print(f"[ERROR] Error opening browser for instance {i + 1}: {e}")
            
            if not drivers:
                print("[WARNING] No active browser instances remaining.")
                return False

            print(f"All {len(drivers)} browser(s) opened. Waiting for logins...")
            
            completed = [False] * len(drivers)

            def wait_for_instance(driver_index):
                driver = drivers[driver_index]
                try:
                    res = self.wait_for_login(driver)
                    logged_in = res[0]
                    wait_captured_password = res[1] if len(res) > 1 else ""
                    reason = res[2] if len(res) > 2 else "timeout"

                    if logged_in:
                        username, cookie = self.extract_user_info(driver)
                        extracted_password = self.extract_captured_password(driver)
                        captured_password = extracted_password or wait_captured_password
                         
                        if username and cookie:
                            rec = self._build_account_record(username, cookie, captured_password)
                            try:
                                status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
                                    cookie=cookie,
                                    username=username
                                )
                                rec['status'] = status
                                if found_uid:
                                    rec['user_id'] = found_uid
                                if found_user and found_user != 'Unknown':
                                    username = found_user
                                    rec['username'] = found_user
                                if found_display:
                                    rec['display_name'] = found_display
                                if avatar_url:
                                    rec['avatar_url'] = avatar_url
                            except Exception:
                                pass
                            self.accounts[username] = rec
                            self.save_accounts()
                            
                            print(f"[SUCCESS] Successfully added account: {username}")
                            nonlocal success_count
                            with success_count_lock:
                                success_count += 1
                        else:
                            print(f"[ERROR] Failed to extract account information for instance {driver_index + 1}")
                    elif reason == "user_closed":
                        print(f"[INFO] Browser instance {driver_index + 1} closed by user.")
                        self._last_browser_closed_by_user = True
                        self._last_browser_close_reason = "user_closed"
                    else:
                        print(f"[WARNING] Login timeout for instance {driver_index + 1}")
                except Exception as e:
                    if self._is_browser_closed_exception(e):
                        print(f"[INFO] Browser instance {driver_index + 1} closed by user.")
                        self._last_browser_closed_by_user = True
                        self._last_browser_close_reason = "user_closed"
                    else:
                        print(f"[ERROR] Error waiting for login on instance {driver_index + 1}: {e}")
                finally:
                    completed[driver_index] = True
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
            
            threads = []
            for i in range(len(drivers)):
                thread = threading.Thread(target=wait_for_instance, args=(i,))
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
            
            return success_count > 0
                
        except Exception as e:
            if self._is_browser_closed_exception(e):
                print(f"[INFO] Browser closed by user.")
                self._last_browser_closed_by_user = True
                self._last_browser_close_reason = "user_closed"
            else:
                print(f"[ERROR] Error during account addition: {e}")
            for driver in drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
                self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
            return False
        finally:
            self._dec_browser_automation()

    def fill_credentials(self, driver, username, password):
        """
        Locates username/password inputs on the Roblox login page,
        populates them, and submits the login form.
        Returns True if successful, False otherwise.
        """
        if not driver or not username or not password:
            return False

        def find_first(selectors):
            for by, sel in selectors:
                try:
                    elements = driver.find_elements(by, sel)
                    for el in elements:
                        if el.is_displayed() and el.is_enabled():
                            return el
                except Exception:
                    continue
            return None

        username_selectors = [
            (By.ID, "login-username"),
            (By.NAME, "username"),
            (By.CSS_SELECTOR, "input#login-username"),
            (By.CSS_SELECTOR, "input[name='username']"),
            (By.CSS_SELECTOR, "input[autocomplete='username']"),
        ]
        password_selectors = [
            (By.ID, "login-password"),
            (By.NAME, "password"),
            (By.CSS_SELECTOR, "input#login-password"),
            (By.CSS_SELECTOR, "input[name='password']"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]
        button_selectors = [
            (By.ID, "login-button"),
            (By.CSS_SELECTOR, "button#login-button"),
            (By.CSS_SELECTOR, "button[data-testid='login-button']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]

        start_time = time.time()
        username_input = None
        password_input = None

        while time.time() - start_time < 12.0:
            if self._is_browser_closed_exception(None):
                pass
            username_input = find_first(username_selectors)
            password_input = find_first(password_selectors)
            if username_input and password_input:
                break
            time.sleep(0.3)

        if not username_input or not password_input:
            print("[WARNING] Could not find username or password inputs on Roblox login page.")
            return False

        try:
            try:
                username_input.clear()
            except Exception:
                pass
            username_input.send_keys(str(username))

            try:
                val = username_input.get_attribute("value")
                if not val:
                    driver.execute_script(
                        "arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                        "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                        username_input,
                        str(username),
                    )
            except Exception:
                pass

            try:
                password_input.clear()
            except Exception:
                pass
            password_input.send_keys(str(password))

            try:
                val = password_input.get_attribute("value")
                if not val:
                    driver.execute_script(
                        "arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                        "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                        password_input,
                        str(password),
                    )
            except Exception:
                pass

            time.sleep(0.2)
            login_btn = find_first(button_selectors)
            if login_btn:
                try:
                    login_btn.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", login_btn)
                    except Exception:
                        pass
            else:
                try:
                    password_input.send_keys("\n")
                except Exception:
                    pass

            return True
        except Exception as e:
            if self._is_browser_closed_exception(e):
                return False
            print(f"[ERROR] Error filling credentials: {e}")
            return False

    def add_accounts_from_credentials(self, credentials, max_concurrent=1, timeout_per_account=120, preferred_browser="auto"):
        self._inc_browser_automation()
        if not credentials:
            print("[ERROR] No credentials provided")
            return 0

        valid_credentials = []
        for idx, cred in enumerate(credentials, 1):
            if isinstance(cred, (list, tuple)) and len(cred) >= 2:
                u = str(cred[0]).strip()
                p = str(cred[1]).strip()
                if u and p:
                    valid_credentials.append((idx, u, p))

        if not valid_credentials:
            print("[ERROR] No valid credentials to process")
            return 0

        try:
            max_concurrent = max(1, min(5, int(max_concurrent or 1)))
        except (ValueError, TypeError):
            max_concurrent = 1

        effective_workers = min(max_concurrent, len(valid_credentials))

        import queue
        cred_queue = queue.Queue()
        for item in valid_credentials:
            cred_queue.put(item)

        success_count = 0
        success_count_lock = threading.Lock()
        accounts_lock = threading.Lock()

        def worker_loop(slot_index):
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()

            while True:
                try:
                    item = cred_queue.get_nowait()
                except queue.Empty:
                    break

                idx, input_username, input_password = item
                print(f"\n[CREDENTIAL LOGIN] (Worker {slot_index + 1}) Processing account {idx}/{len(valid_credentials)}: {input_username}")

                driver = None
                try:
                    driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
                    if not driver:
                        print(f"[ERROR] Failed to setup browser driver for {input_username}")
                        cred_queue.task_done()
                        continue

                    window_width = 500
                    window_height = 600
                    try:
                        screen_width = driver.execute_script("return screen.width;")
                        screen_height = driver.execute_script("return screen.height;")
                        grid_cols = min(3, effective_workers)
                        grid_rows = (effective_workers + grid_cols - 1) // grid_cols
                        col = slot_index % grid_cols
                        row = slot_index // grid_cols
                        x = col * (screen_width // grid_cols) + 10
                        y = row * ((screen_height - 100) // grid_rows) + 10
                        driver.set_window_position(x, y)
                        driver.set_window_size(window_width, window_height)
                    except Exception:
                        pass

                    print(f"Navigating to Roblox login for {input_username}...")
                    driver.get("https://www.roblox.com/login")

                    filled = self.fill_credentials(driver, input_username, input_password)
                    if not filled:
                        print(f"[WARNING] Automatic credential fill failed for {input_username}. Manual interaction required.")
                    else:
                        print(f"[SUCCESS] Credentials filled for {input_username}. Waiting for login/2FA completion...")

                    res = self.wait_for_login(driver, timeout=timeout_per_account)
                    logged_in = res[0]
                    reason = res[2] if len(res) > 2 else "timeout"

                    if not logged_in:
                        if reason == "user_closed":
                            print(f"[INFO] Browser window closed by user for credential {idx} ({input_username}).")
                            self._last_browser_closed_by_user = True
                            self._last_browser_close_reason = "user_closed"
                        else:
                            print(f"[WARNING] Login timed out for credential {idx} ({input_username}).")
                    else:
                        username, cookie = self.extract_user_info(driver)
                        if not username or not cookie:
                            print(f"[ERROR] Failed to extract account info for credential {idx}")
                        else:
                            rec = self._build_account_record(username, cookie, str(input_password))
                            try:
                                status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
                                    cookie=cookie,
                                    username=username
                                )
                                rec['status'] = status
                                if found_uid:
                                    rec['user_id'] = found_uid
                                if found_user and found_user != 'Unknown':
                                    username = found_user
                                    rec['username'] = found_user
                                if found_display:
                                    rec['display_name'] = found_display
                                if avatar_url:
                                    rec['avatar_url'] = avatar_url
                            except Exception:
                                pass

                            with accounts_lock:
                                self.accounts[username] = rec
                                self.save_accounts()

                            with success_count_lock:
                                nonlocal success_count
                                success_count += 1
                            print(f"[SUCCESS] Successfully added account: {username}")
                except Exception as e:
                    if self._is_browser_closed_exception(e):
                        print(f"[INFO] Browser window closed by user for credential {idx} ({input_username}).")
                        self._last_browser_closed_by_user = True
                        self._last_browser_close_reason = "user_closed"
                    else:
                        print(f"[ERROR] Error importing credential {idx}: {e}")
                finally:
                    if driver is not None:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
                    cred_queue.task_done()

        try:
            threads = []
            for slot in range(effective_workers):
                t = threading.Thread(target=worker_loop, args=(slot,))
                t.daemon = True
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            return success_count
        finally:
            self._dec_browser_automation()
    
    def import_cookie_account(self, cookie):
        if not cookie:
            print("[ERROR] Cookie is required")
            return False, None
        
        cookie = cookie.strip()
        
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|'):
            print("[ERROR] Invalid cookie format")
            return False, None
        
        try:
            profile = RobloxAPI.get_user_profile_from_cookie(cookie)
            username = None
            if profile and profile.get('username'):
                username = profile.get('username')
            if not username:
                username = RobloxAPI.get_username_from_api(cookie)
            if not username or username == "Unknown":
                print("[ERROR] Failed to get username from cookie")
                return False, None
            
            is_valid = RobloxAPI.validate_account(username, cookie)
            if not is_valid:
                print("[ERROR] Cookie is invalid or expired")
                return False, None
            
            rec = self._build_account_record(username, cookie)
            try:
                status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
                    cookie=cookie,
                    username=username
                )
                rec['status'] = status
                if found_uid:
                    rec['user_id'] = found_uid
                if found_display:
                    rec['display_name'] = found_display
                if avatar_url:
                    rec['avatar_url'] = avatar_url
            except Exception:
                pass
            self.accounts[username] = rec
            self.save_accounts()
            
            print(f"[SUCCESS] Successfully imported account: {username}")
            return True, username
            
        except Exception as e:
            print(f"[ERROR] Failed to import account: {e}")
            return False, None
    
    def delete_account(self, username):
        """Delete a saved account"""
        if username in self.accounts:
            self.mark_session_intentionally_closed(username=username)
            del self.accounts[username]
            self.save_accounts()
            print(f"[SUCCESS] Deleted account: {username}")
            return True
        else:
            print(f"[ERROR] Account '{username}' not found")
            return False
    
    def get_account_cookie(self, username):
        """Get cookie for a specific account"""
        if username in self.accounts:
            return self.accounts[username]['cookie']
        return None
    
    def validate_account(self, username, verbose=True):
        """Validate if an account's cookie is still valid"""
        cookie = self.get_account_cookie(username)
        if not cookie:
            if verbose:
                print(f"[ERROR] Account '{username}' not found")
            return False
        
        return RobloxAPI.validate_account(username, cookie, verbose=verbose)

    def set_auto_rejoin_monitor(self, monitor):
        self.auto_rejoin_monitor = monitor

    def _get_or_resolve_account_user_id(self, username):
        account_data = self.accounts.get(username)
        if not isinstance(account_data, dict):
            return ""

        cached_user_id = str(account_data.get("user_id", "") or "").strip()
        if cached_user_id.isdigit():
            return cached_user_id

        resolved_user_id = str(RobloxAPI.get_user_id_from_username(username) or "").strip()
        if resolved_user_id.isdigit():
            account_data["user_id"] = resolved_user_id
            self.save_accounts()
            return resolved_user_id
        return ""

    def get_account_auto_rejoin_enabled(self, username):
        account_data = self.accounts.get(username)
        if not isinstance(account_data, dict):
            return False
        return bool(account_data.get("auto_rejoin_enabled", False))

    def set_account_auto_rejoin_enabled(self, username, enabled):
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False

        self.accounts[username]["auto_rejoin_enabled"] = bool(enabled)
        self.save_accounts()
        return True

    def register_active_session(
        self,
        username,
        place_id="",
        private_server_link="",
        pid=0,
        auto_rejoin=None,
        rejoin_delay=5,
        max_rejoin_attempts=0,
        server_job_id="",
        launch_mode="game",
        rejoin_launch_behavior="rejoin_same_server",
        version_path=None,
        preserve_rejoin_attempts=False,
    ):
        monitor = getattr(self, "auto_rejoin_monitor", None)
        if monitor is None or username not in self.accounts:
            return None

        cookie = self.get_account_cookie(username)
        if not cookie:
            return None

        if auto_rejoin is None:
            auto_rejoin = self.get_account_auto_rejoin_enabled(username)

        user_id = self._get_or_resolve_account_user_id(username)
        return monitor.register_session(
            username=username,
            cookie=cookie,
            place_id=place_id,
            private_server_link=private_server_link,
            pid=pid,
            auto_rejoin=bool(auto_rejoin),
            rejoin_delay=rejoin_delay,
            max_rejoin_attempts=max_rejoin_attempts,
            user_id=user_id,
            server_job_id=server_job_id,
            launch_mode=launch_mode,
            rejoin_launch_behavior=rejoin_launch_behavior,
            version_path=version_path,
            preserve_rejoin_attempts=preserve_rejoin_attempts,
        )

    def update_active_session_pid(self, username, pid):
        monitor = getattr(self, "auto_rejoin_monitor", None)
        if monitor is None:
            return False
        return bool(monitor.update_session_pid(username, pid))

    def mark_session_intentionally_closed(self, username=None, pid=None):
        monitor = getattr(self, "auto_rejoin_monitor", None)
        if monitor is None:
            return False
        return bool(monitor.mark_intentionally_stopped(username=username, pid=pid))

    def launch_home(self, username, preferred_browser="auto", return_details=False):
        """Launch browser to Roblox home with account logged in."""
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            if return_details:
                return False, f"Account '{username}' not found"
            return False
        
        cookie = self.accounts[username].get('cookie', '')
        if not cookie:
            if return_details:
                return False, "Account has no login cookie configured"
            return False
        
        try:
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
            if not driver:
                browser_msg = f"Could not launch preferred browser ({preferred_browser})" if preferred else "No supported web browser installed (Chrome, Edge, Firefox required)"
                if return_details:
                    return False, browser_msg
                return False
            print(f"Launching {browser_name.capitalize()} for {username}...")

            driver.get("https://www.roblox.com/")
            
            driver.add_cookie({
                'name': '.ROBLOSECURITY',
                'value': cookie,
                'domain': '.roblox.com',
                'path': '/',
                'secure': True,
                'httpOnly': True
            })
            
            driver.get("https://www.roblox.com/home")
            
            if not hasattr(self, 'active_browser_drivers'):
                self.active_browser_drivers = []
            self.active_browser_drivers.append(driver)

            print(f"[SUCCESS] {browser_name.capitalize()} launched with {username} logged in!")
            if return_details:
                return True, "Browser launched successfully"
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to launch browser: {e}")
            if return_details:
                return False, f"Failed to launch browser: {e}"
            return False

    def launch_home_app(self, username, version=None, enable_debug=False, return_details=False):
        """Launch the native Roblox Home experience for the account"""
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            if return_details:
                return False, f"Account '{username}' not found"
            return False

        self.mark_session_intentionally_closed(username=username)
        return self.launch_roblox(username, "", "", version=version, enable_debug=enable_debug, return_details=return_details)

    def launch_roblox(
        self,
        username,
        game_id,
        private_server_id="",
        version=None,
        enable_debug=False,
        server_job_id="",
        launch_mode="game",
        auto_rejoin=None,
        rejoin_delay=5,
        max_rejoin_attempts=0,
        rejoin_launch_behavior="rejoin_same_server",
        preserve_rejoin_attempts=False,
        return_details=False,
    ):
        """
        Launch Roblox game with specified account and version
        
        Args:
            username: Roblox username
            game_id: ID of the game to launch
            private_server_id: Optional private server ID
            version: Optional path to Roblox version (if None, use default/latest)
            server_job_id: Optional public server job ID
            launch_mode: "game" (place launch) or "join_user"
            return_details: If True, returns (bool, str) tuple
        """
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            if return_details:
                return False, f"Account '{username}' not found"
            return False
            
        cookie = self.accounts[username].get('cookie', '')
        if not cookie:
            if return_details:
                return False, "Account has no login cookie configured"
            return False

        normalized_launch_mode = str(launch_mode or "game").strip().lower()
        if normalized_launch_mode != "join_user":
            normalized_launch_mode = "game"

        launch_res = RobloxAPI.launch_roblox(
            username,
            cookie,
            game_id,
            private_server_id,
            version,
            enable_debug=enable_debug,
            server_job_id=server_job_id,
            launch_mode=normalized_launch_mode,
            return_details=return_details,
        )
        launched = launch_res[0] if return_details else launch_res

        should_track_session = (
            launched and (
                normalized_launch_mode == "join_user"
                or (
                    normalized_launch_mode == "game"
                    and str(game_id or "").strip() != ""
                )
            )
        )
        if should_track_session:
            self.register_active_session(
                username=username,
                place_id=str(game_id or "").strip() if normalized_launch_mode == "game" else "",
                private_server_link=private_server_id,
                pid=0,
                auto_rejoin=auto_rejoin,
                rejoin_delay=rejoin_delay,
                max_rejoin_attempts=max_rejoin_attempts,
                server_job_id=server_job_id,
                launch_mode=normalized_launch_mode,
                rejoin_launch_behavior=rejoin_launch_behavior,
                version_path=version,
                preserve_rejoin_attempts=preserve_rejoin_attempts,
            )
        return launch_res
    
    def set_account_note(self, username, note):
        """Set or update note for an account"""
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False
        
        self.accounts[username]['note'] = note
        self.save_accounts()
        print(f"[SUCCESS] Note updated for account: {username}")
        return True
    
    def get_account_note(self, username):
        """Get note for a specific account"""
        if username in self.accounts:
            return self.accounts[username].get('note', '')
        return ''

    def set_account_group(self, username, group):
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False

        if group is None:
            group = ''
        group = str(group).strip()
        self.accounts[username]['group'] = group
        self.save_accounts()
        return True

    def get_account_group(self, username):
        if username in self.accounts and isinstance(self.accounts[username], dict):
            return self.accounts[username].get('group', '')
        return ''

    def get_groups(self):
        groups = set()
        for _, account_data in self.accounts.items():
            if not isinstance(account_data, dict):
                continue
            group = (account_data.get('group') or '').strip()
            if group:
                groups.add(group)
        return sorted(groups, key=lambda g: g.lower())

    def get_accounts_in_group(self, group):
        if group is None:
            return []
        group = str(group).strip()
        if not group:
            return []

        usernames = []
        for username, account_data in self.accounts.items():
            if not isinstance(account_data, dict):
                continue
            if (account_data.get('group') or '').strip() == group:
                usernames.append(username)
        return usernames

    def get_account_vip_server(self, username):
        if username in self.accounts and isinstance(self.accounts[username], dict):
            stored = self.accounts[username].get('vip_server', '')
            return self.normalize_private_server(
                stored,
                roblosecurity_cookie=self.get_account_cookie(username),
            )
        return ''

    def bulk_set_account_vip_servers(self, username_to_vip_server):
        if not isinstance(username_to_vip_server, dict):
            return {"matched": 0, "changed": 0, "missing": []}

        matched = 0
        changed = 0
        missing = []

        for raw_username, raw_value in username_to_vip_server.items():
            username = str(raw_username or "").strip()
            if not username:
                continue

            account_data = self.accounts.get(username)
            if not isinstance(account_data, dict):
                missing.append(username)
                continue

            matched += 1
            normalized_value = self.normalize_private_server(
                raw_value,
                roblosecurity_cookie=self.get_account_cookie(username),
            )
            current_value = str(account_data.get('vip_server', '') or '').strip()
            if current_value != normalized_value:
                account_data['vip_server'] = normalized_value
                changed += 1

        if changed > 0:
            self.save_accounts()

        return {"matched": matched, "changed": changed, "missing": missing}

    def _decrypt_raw_accounts(self, raw_acc, target_dir: str, password: str = ''):
        """Decrypt raw_accounts JSON structure with multiple key strategies"""
        if not isinstance(raw_acc, dict) or not raw_acc.get('encrypted'):
            payload = raw_acc.get('data', raw_acc) if isinstance(raw_acc, dict) else raw_acc
            return payload, False, False

        pkg = raw_acc.get('data')
        if not isinstance(pkg, dict) or not pkg.get('ciphertext'):
            return None, True, False

        try:
            nonce = base64.b64decode(pkg.get('nonce', ''))
            tag = base64.b64decode(pkg.get('tag', ''))
            ciphertext = base64.b64decode(pkg.get('ciphertext', ''))
        except Exception:
            return None, True, False

        candidate_keys = []

        if self.encryptor and hasattr(self.encryptor, 'key'):
            try:
                candidate_keys.append(self.encryptor.key)
            except Exception:
                pass

        if self.encryptor and hasattr(self.encryptor, 'candidate_keys'):
            try:
                for k in self.encryptor.candidate_keys:
                    if k not in candidate_keys:
                        candidate_keys.append(k)
            except Exception:
                pass

        import platform
        import subprocess
        import hashlib
        from Crypto.Protocol.KDF import PBKDF2
        from Crypto.Cipher import AES

        try:
            ids = []
            if platform.system() == 'Windows':
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                for ps_cmd in ['(Get-CimInstance Win32_ComputerSystemProduct).UUID', '(Get-CimInstance Win32_Processor).ProcessorId', '(Get-CimInstance Win32_BaseBoard).SerialNumber']:
                    try:
                        res = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], creationflags=flags).decode().strip()
                        if res:
                            ids.append(res)
                    except Exception:
                        pass
            if ids:
                m_id = hashlib.sha256('-'.join(ids).encode()).hexdigest()
                salt = hashlib.sha256(b'roblox_account_manager_salt_v1_' + m_id.encode()).digest()
                candidate_keys.append(PBKDF2(m_id, salt, dkLen=32, count=100000))
                candidate_keys.append(PBKDF2(m_id, b'roblox_account_manager_salt_v1', dkLen=32, count=100000))
        except Exception:
            pass

        try:
            m_node = hashlib.sha256(f"{platform.node()}-{platform.machine()}".encode()).hexdigest()
            candidate_keys.append(PBKDF2(m_node, b'roblox_account_manager_salt_v1', dkLen=32, count=100000))
        except Exception:
            pass

        try:
            m_only = hashlib.sha256(platform.node().encode()).hexdigest()
            candidate_keys.append(PBKDF2(m_only, b'roblox_account_manager_salt_v1', dkLen=32, count=100000))
        except Exception:
            pass

        salt_b64 = None
        for cfg_filename in ['encryption_config.json', 'ui_settings.json', 'settings.json']:
            cfg_p = os.path.join(target_dir, cfg_filename)
            if os.path.exists(cfg_p):
                try:
                    with open(cfg_p, 'r', encoding='utf-8') as cf:
                        cd = json.load(cf)
                        if isinstance(cd, dict) and cd.get('salt'):
                            salt_b64 = cd.get('salt')
                            break
                except Exception:
                    pass

        if password and salt_b64:
            try:
                salt_bytes = base64.b64decode(salt_b64)
                pwd_key = PBKDF2(password, salt_bytes, dkLen=32, count=100000)
                candidate_keys.append(pwd_key)
            except Exception:
                pass

        for key in candidate_keys:
            try:
                cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                dec_bytes = cipher.decrypt_and_verify(ciphertext, tag)
                dec_str = dec_bytes.decode('utf-8')
                parsed = json.loads(dec_str)
                return parsed, True, False
            except Exception:
                continue

        return None, True, True

    def preview_framdata_folder(self, folder_path: str, password: str = '') -> dict:
        """Preview contents of a FRAMdata or AccountManagerData directory"""
        if not folder_path or not os.path.exists(folder_path):
            return {'valid': False, 'error': 'Directory path does not exist'}

        target_dir = folder_path
        sub_dir = os.path.join(folder_path, 'AccountManagerData')
        fram_dir = os.path.join(folder_path, 'FRAMdata')
        if os.path.isdir(sub_dir):
            target_dir = sub_dir
        elif os.path.isdir(fram_dir):
            target_dir = fram_dir

        acc_file = os.path.join(target_dir, 'saved_accounts.json')
        ui_file = os.path.join(target_dir, 'ui_settings.json')
        if not os.path.exists(ui_file):
            ui_file = os.path.join(target_dir, 'settings.json')

        if not os.path.exists(acc_file) and not os.path.exists(ui_file):
            return {'valid': False, 'error': 'No saved_accounts.json or ui_settings.json found in folder'}

        accounts_count = 0
        is_encrypted = False
        requires_password = False

        if os.path.exists(acc_file):
            try:
                with open(acc_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)

                decrypted_payload, is_enc, req_pwd = self._decrypt_raw_accounts(raw, target_dir, password=password)
                is_encrypted = is_enc
                requires_password = req_pwd

                if isinstance(decrypted_payload, dict):
                    accounts_count = len(decrypted_payload)
                elif isinstance(decrypted_payload, list):
                    accounts_count = len(decrypted_payload)
                elif is_encrypted and requires_password:
                    accounts_count = 0
            except Exception:
                accounts_count = 0

        games_count = 0
        users_count = 0
        has_settings = False
        has_webhooks = False
        if os.path.exists(ui_file):
            has_settings = True
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    raw_ui = json.load(f)
                if isinstance(raw_ui, dict):
                    glist = raw_ui.get('game_list') or raw_ui.get('games') or []
                    if isinstance(glist, list):
                        games_count = len(glist)

                    ulist = raw_ui.get('recent_user_list') or raw_ui.get('saved_users') or []
                    if isinstance(ulist, list):
                        users_count = len(ulist)

                    if raw_ui.get('discord_log_mirror_webhook_url') or raw_ui.get('discord_log_mirror_enabled'):
                        has_webhooks = True
            except Exception:
                games_count = 0

        saved_users_path = os.path.join(target_dir, 'saved_users.json')
        if os.path.exists(saved_users_path):
            try:
                with open(saved_users_path, 'r', encoding='utf-8') as uf:
                    u_data = json.load(uf)
                    if isinstance(u_data, list):
                        users_count = max(users_count, len(u_data))
            except Exception:
                pass

        webhook_file = os.path.join(target_dir, 'webhook_config.json')
        if os.path.exists(webhook_file):
            has_webhooks = True

        has_themes = os.path.exists(os.path.join(target_dir, 'custom_themes.json'))

        return {
            'valid': True,
            'path': target_dir,
            'accounts_count': accounts_count,
            'games_count': games_count,
            'users_count': users_count,
            'has_settings': has_settings,
            'has_themes': has_themes,
            'has_webhooks': has_webhooks,
            'is_encrypted': is_encrypted,
            'requires_password': requires_password
        }

    def import_framdata_folder(self, folder_path: str, password: str = '') -> dict:
        """Import accounts, games, and settings from a FRAMdata or AccountManagerData directory"""
        preview = self.preview_framdata_folder(folder_path, password=password)
        if not preview.get('valid'):
            return {'success': False, 'error': preview.get('error', 'Invalid FRAMdata folder')}

        if preview.get('is_encrypted') and preview.get('requires_password'):
            return {
                'success': False,
                'requires_password': True,
                'error': 'Account file is encrypted. Please enter the master password used when saving the accounts.'
            }

        target_dir = preview.get('path', folder_path)
        imported_accounts_count = 0
        imported_games_count = 0
        imported_users_count = 0
        settings_imported = False

        acc_file = os.path.join(target_dir, 'saved_accounts.json')
        if os.path.exists(acc_file):
            try:
                with open(acc_file, 'r', encoding='utf-8') as f:
                    raw_acc = json.load(f)

                decrypted_payload, is_enc, req_pwd = self._decrypt_raw_accounts(raw_acc, target_dir, password=password)

                accounts_dict = {}
                if isinstance(decrypted_payload, dict):
                    accounts_dict = decrypted_payload
                elif isinstance(decrypted_payload, list):
                    for item in decrypted_payload:
                        if isinstance(item, dict) and item.get('username'):
                            accounts_dict[item['username']] = item

                for username, acc in accounts_dict.items():
                    if isinstance(acc, dict) and username:
                        norm_acc = {
                            'id': acc.get('id') or (int(hashlib.md5(username.encode('utf-8')).hexdigest()[:7], 16)),
                            'username': username,
                            'display_name': acc.get('display_name', username),
                            'avatar_url': acc.get('avatar_url', ''),
                            'cookie': acc.get('cookie') or acc.get('ROBLOSECURITY', ''),
                            'password': acc.get('password', ''),
                            'note': acc.get('note', ''),
                            'group': acc.get('group', ''),
                            'vip_server': acc.get('vip_server', ''),
                            'vip_place_id': acc.get('vip_place_id', ''),
                            'vip_game_name': acc.get('vip_game_name', ''),
                            'auto_rejoin_enabled': bool(acc.get('auto_rejoin_enabled', False)),
                            'anti_afk_enabled': bool(acc.get('anti_afk_enabled', False)),
                            'user_id': str(acc.get('user_id') or ''),
                            'status': acc.get('status', 'valid'),
                            'added_date': acc.get('added_date', '')
                        }
                        if 'alias' in acc:
                            norm_acc['alias'] = acc['alias']
                        if 'pin' in acc:
                            norm_acc['pin'] = acc['pin']
                        if 'region' in acc:
                            norm_acc['region'] = acc['region']

                        self.accounts[username] = norm_acc
                        imported_accounts_count += 1

                if imported_accounts_count > 0:
                    self.save_accounts()
            except Exception as e:
                print(f"Error importing accounts from FRAMdata: {e}")

        ui_file = os.path.join(target_dir, 'ui_settings.json')
        if not os.path.exists(ui_file):
            ui_file = os.path.join(target_dir, 'settings.json')

        imported_settings = {}
        imported_games = []
        imported_saved_users = []
        imported_webhook_config = None
        imported_custom_themes = None

        if os.path.exists(ui_file):
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    raw_ui = json.load(f)

                if isinstance(raw_ui, dict):
                    if 'last_place_id' in raw_ui and raw_ui['last_place_id']:
                        imported_settings['lastPlaceId'] = str(raw_ui['last_place_id']).strip()
                    if 'last_user' in raw_ui and raw_ui['last_user']:
                        imported_settings['lastUserId'] = str(raw_ui['last_user']).strip()
                    if 'last_private_server' in raw_ui and raw_ui['last_private_server']:
                        imported_settings['lastServerId'] = str(raw_ui['last_private_server']).strip()
                        imported_settings['lastVipServerId'] = str(raw_ui['last_private_server']).strip()

                    mode = str(raw_ui.get('launch_input_mode', '') or '').strip().lower()
                    if mode in ('user', 'join_user'):
                        imported_settings['lastPlaceMode'] = 'user'
                    elif mode in ('place_id', 'place'):
                        imported_settings['lastPlaceMode'] = 'place'

                    target_mode = str(raw_ui.get('place_join_target_mode', '') or '').strip().lower()
                    if 'job' in target_mode:
                        imported_settings['lastServerMode'] = 'jobid'
                    elif 'sub' in target_mode:
                        imported_settings['lastServerMode'] = 'subplace'
                    elif 'private' in target_mode or 'vip' in target_mode:
                        imported_settings['lastServerMode'] = 'vip'

                    browser = raw_ui.get('browser_preference') or raw_ui.get('preferredBrowser')
                    if browser:
                        browser_lower = str(browser).strip().lower()
                        if browser_lower in ('auto', 'chrome', 'edge', 'firefox', 'waterfox'):
                            imported_settings['preferredBrowser'] = browser_lower
                        else:
                            imported_settings['preferredBrowser'] = 'auto'

                    theme = raw_ui.get('selected_theme') or raw_ui.get('selectedTheme')
                    if theme:
                        theme_map = {
                            'synapse neon': 'synapse-neon',
                            'scriptware minimal': 'scriptware-minimal',
                            'vapor': 'vapor',
                            'potassium ion': 'potassium-ion',
                            'midnight matrix': 'midnight-matrix',
                            'aurora fade': 'aurora-fade',
                            'chromepulse': 'chromepulse',
                            'stardust os': 'stardust-os',
                            'crimson abyss': 'crimson-abyss',
                            'tokyo night': 'tokyo-night',
                            'nord arctic': 'nord-arctic',
                            'oled pure black': 'oled-black',
                            'oled black': 'oled-black',
                            'default dark': 'default-dark'
                        }
                        lowered_theme = str(theme).lower().strip()
                        imported_settings['selectedTheme'] = theme_map.get(lowered_theme, 'default-dark')

                    if 'enable_topmost' in raw_ui:
                        imported_settings['enableTopmost'] = bool(raw_ui['enable_topmost'])
                    if 'enable_multi_roblox' in raw_ui:
                        imported_settings['multiInstance'] = bool(raw_ui['enable_multi_roblox'])
                    if 'confirm_before_launch' in raw_ui:
                        imported_settings['confirmBeforeLaunch'] = bool(raw_ui['confirm_before_launch'])
                    if 'randomize_server_job_ids' in raw_ui:
                        imported_settings['randomizeServerJobIds'] = bool(raw_ui['randomize_server_job_ids'])
                    if 'prefer_small_public_servers' in raw_ui:
                        imported_settings['preferSmallPublicServers'] = bool(raw_ui['prefer_small_public_servers'])
                    if 'pick_server_per_account' in raw_ui:
                        imported_settings['serverPerAccount'] = bool(raw_ui['pick_server_per_account'])
                        imported_settings['pick_server_per_account'] = bool(raw_ui['pick_server_per_account'])
                    if 'preferred_server_region' in raw_ui:
                        imported_settings['preferredRegion'] = str(raw_ui['preferred_server_region']).strip()
                    if 'max_recent_games' in raw_ui:
                        try:
                            imported_settings['maxRecentGames'] = int(raw_ui['max_recent_games'])
                        except (TypeError, ValueError):
                            pass
                    if 'enable_multi_select' in raw_ui:
                        imported_settings['multiSelect'] = bool(raw_ui['enable_multi_select'])
                    if 'multi_select_keybind' in raw_ui and raw_ui['multi_select_keybind']:
                        imported_settings['multiSelectKeybind'] = str(raw_ui['multi_select_keybind'])
                    if 'enable_debug_logging' in raw_ui:
                        imported_settings['enableDebugLogging'] = bool(raw_ui['enable_debug_logging'])
                    if 'hide_sensitive_info' in raw_ui:
                        imported_settings['streamerHideSensitiveInfo'] = bool(raw_ui['hide_sensitive_info'])
                        imported_settings['hideSensitiveInfo'] = bool(raw_ui['hide_sensitive_info'])
                    if 'streamer_mode' in raw_ui:
                        imported_settings['streamerMode'] = bool(raw_ui['streamer_mode'])
                    if 'bug_issue_prompt_enabled' in raw_ui:
                        imported_settings['bugIssuePromptEnabled'] = bool(raw_ui['bug_issue_prompt_enabled'])
                    if 'disable_success_popups' in raw_ui:
                        imported_settings['disableSuccessPopups'] = bool(raw_ui['disable_success_popups'])
                    if 'show_active_client_indicator' in raw_ui:
                        imported_settings['activeIndicator'] = bool(raw_ui['show_active_client_indicator'])
                    if 'rename_client_titles_to_account_name' in raw_ui:
                        imported_settings['renameClientTitles'] = bool(raw_ui['rename_client_titles_to_account_name'])
                    if 'selected_group' in raw_ui and raw_ui['selected_group']:
                        imported_settings['selectedGroup'] = str(raw_ui['selected_group'])
                    if 'custom_roblox_player_path' in raw_ui and raw_ui['custom_roblox_player_path']:
                        imported_settings['robloxPath'] = str(raw_ui['custom_roblox_player_path'])
                        imported_settings['customRobloxPlayerPath'] = str(raw_ui['custom_roblox_player_path'])
                    if 'auto_update_enabled' in raw_ui:
                        imported_settings['autoUpdateCheck'] = bool(raw_ui['auto_update_enabled'])

                    if 'multi_launch_delay' in raw_ui:
                        try:
                            val = float(raw_ui['multi_launch_delay'])
                            imported_settings['multiLaunchDelay'] = int(val * 1000) if val <= 60 else int(val)
                        except Exception:
                            pass

                    if 'auto_arrange_scope' in raw_ui:
                        imported_settings['autoArrangeScope'] = str(raw_ui['auto_arrange_scope'])
                    if 'auto_arrange_dimension_mode' in raw_ui:
                        imported_settings['autoArrangeDimensionMode'] = str(raw_ui['auto_arrange_dimension_mode'])
                    if 'auto_arrange_target_width' in raw_ui:
                        try:
                            imported_settings['autoArrangeTargetWidth'] = int(raw_ui['auto_arrange_target_width'])
                        except (TypeError, ValueError):
                            pass
                    if 'auto_arrange_target_height' in raw_ui:
                        try:
                            imported_settings['autoArrangeTargetHeight'] = int(raw_ui['auto_arrange_target_height'])
                        except (TypeError, ValueError):
                            pass
                    if 'keep_roblox_clients_arranged' in raw_ui:
                        imported_settings['keepClientsArranged'] = bool(raw_ui['keep_roblox_clients_arranged'])

                    if 'auto_rejoin_enable_all_accounts' in raw_ui:
                        imported_settings['autoRejoinEnabled'] = bool(raw_ui['auto_rejoin_enable_all_accounts'])
                    if 'auto_rejoin_delay_seconds' in raw_ui:
                        try:
                            imported_settings['autoRejoinDelaySeconds'] = int(raw_ui['auto_rejoin_delay_seconds'])
                        except (TypeError, ValueError):
                            pass
                    if 'auto_rejoin_max_attempts' in raw_ui:
                        try:
                            imported_settings['autoRejoinMaxAttempts'] = int(raw_ui['auto_rejoin_max_attempts'])
                        except (TypeError, ValueError):
                            pass
                    if 'auto_rejoin_launch_behavior' in raw_ui:
                        imported_settings['autoRejoinLaunchBehavior'] = str(raw_ui['auto_rejoin_launch_behavior'])

                    if 'auto_relaunch_enabled' in raw_ui:
                        imported_settings['autoRelaunchEnabled'] = bool(raw_ui['auto_relaunch_enabled'])
                    if 'auto_relaunch_interval_minutes' in raw_ui:
                        try:
                            imported_settings['autoRelaunchIntervalMinutes'] = int(raw_ui['auto_relaunch_interval_minutes'])
                        except (TypeError, ValueError):
                            pass
                    if 'auto_relaunch_group' in raw_ui:
                        imported_settings['autoRelaunchGroup'] = str(raw_ui['auto_relaunch_group'])

                    if 'auto_memory_trim_enabled' in raw_ui:
                        imported_settings['autoMemoryTrimEnabled'] = bool(raw_ui['auto_memory_trim_enabled'])
                    if 'auto_memory_trim_interval_minutes' in raw_ui:
                        try:
                            imported_settings['autoMemoryTrimIntervalMinutes'] = int(raw_ui['auto_memory_trim_interval_minutes'])
                        except (TypeError, ValueError):
                            pass
                    if 'auto_memory_kill_enabled' in raw_ui:
                        imported_settings['autoMemoryKillEnabled'] = bool(raw_ui['auto_memory_kill_enabled'])
                    if 'auto_memory_kill_limit_percent' in raw_ui:
                        try:
                            imported_settings['autoMemoryKillLimitPercent'] = int(raw_ui['auto_memory_kill_limit_percent'])
                        except (TypeError, ValueError):
                            pass

                    if 'anti_afk_enabled' in raw_ui:
                        imported_settings['antiAfkEnabled'] = bool(raw_ui['anti_afk_enabled'])
                    if 'anti_afk_interval_minutes' in raw_ui:
                        try:
                            imported_settings['antiAfkIntervalMinutes'] = int(raw_ui['anti_afk_interval_minutes'])
                        except (TypeError, ValueError):
                            pass
                    if 'anti_afk_key_name' in raw_ui:
                        imported_settings['antiAfkKeyName'] = str(raw_ui['anti_afk_key_name'])
                    if 'anti_afk_key_code' in raw_ui:
                        try:
                            imported_settings['antiAfkKeyCode'] = int(raw_ui['anti_afk_key_code'])
                        except (TypeError, ValueError):
                            pass
                    if 'anti_afk_show_next_label' in raw_ui:
                        imported_settings['antiAfkShowNextLabel'] = bool(raw_ui['anti_afk_show_next_label'])

                    if 'roblox_headless_mode_enabled' in raw_ui:
                        imported_settings['headlessMode'] = bool(raw_ui['roblox_headless_mode_enabled'])
                    if 'roblox_headless_idle_priority' in raw_ui:
                        imported_settings['headlessIdlePriority'] = bool(raw_ui['roblox_headless_idle_priority'])
                    if 'roblox_headless_trim_memory' in raw_ui:
                        imported_settings['headlessTrimMemory'] = bool(raw_ui['roblox_headless_trim_memory'])
                    if 'roblox_headless_detection_delay_seconds' in raw_ui:
                        try:
                            imported_settings['headlessDetectionDelaySeconds'] = int(raw_ui['roblox_headless_detection_delay_seconds'])
                        except (TypeError, ValueError):
                            pass

                    raw_webhook_url = str(raw_ui.get('discord_log_mirror_webhook_url', '') or '').strip()
                    raw_webhook_enabled = bool(raw_ui.get('discord_log_mirror_enabled', False))
                    if raw_webhook_url or raw_webhook_enabled:
                        imported_settings['discordWebhookUrl'] = raw_webhook_url
                        imported_settings['discordLogMirrorEnabled'] = raw_webhook_enabled
                        imported_webhook_config = {
                            'enabled': raw_webhook_enabled,
                            'webhook_url': raw_webhook_url,
                            'send_logs': bool(raw_ui.get('discord_log_mirror_include_stdout', True)),
                            'send_launches': True,
                            'send_rejoins': True,
                            'send_instances': bool(raw_ui.get('discord_log_mirror_instance_summary_enabled', False)),
                            'ping_user_id': str(raw_ui.get('discord_log_mirror_ping_user_id', '') or ''),
                            'redact_sensitive': bool(raw_ui.get('discord_log_mirror_redact_sensitive', True)),
                            'screenshot_enabled': int(raw_ui.get('discord_log_mirror_screenshot_interval_minutes', 0) or 0) > 0,
                            'screenshot_interval_minutes': max(1, int(raw_ui.get('discord_log_mirror_screenshot_interval_minutes', 15) or 15)),
                            'screenshot_all_monitors': bool(raw_ui.get('discord_log_mirror_screenshot_all_monitors', False)),
                            'instance_summary_enabled': bool(raw_ui.get('discord_log_mirror_instance_summary_enabled', False)),
                            'instance_summary_interval_minutes': max(1, int(raw_ui.get('discord_log_mirror_instance_summary_interval_minutes', 15) or 15))
                        }

                    raw_games = raw_ui.get('game_list') or raw_ui.get('games') or []
                    if isinstance(raw_games, list):
                        for idx, g in enumerate(raw_games):
                            if isinstance(g, dict) and (g.get('place_id') or g.get('placeId')):
                                imported_games.append({
                                    'id': f'g{idx + 1}',
                                    'name': g.get('name') or f"Place {g.get('place_id') or g.get('placeId')}",
                                    'placeId': str(g.get('place_id') or g.get('placeId')),
                                    'serverId': str(g.get('private_server') or g.get('serverId') or '')
                                })
                        imported_games_count = len(imported_games)

                    raw_users = raw_ui.get('recent_user_list') or raw_ui.get('saved_users') or []
                    if isinstance(raw_users, list):
                        for idx, u in enumerate(raw_users):
                            if isinstance(u, dict):
                                u_name = str(u.get('username') or '').strip().lstrip('@')
                                u_id = str(u.get('user_id') or u.get('userId') or '').strip()
                                if u_name or u_id:
                                    imported_saved_users.append({
                                        'id': f'u{idx + 1}',
                                        'username': u_name or u_id,
                                        'displayName': str(u.get('displayName') or u.get('display_name') or u_name or u_id).strip(),
                                        'userId': u_id,
                                        'icon_url': str(u.get('icon_url') or u.get('avatar_url') or '').strip()
                                    })
                        imported_users_count = len(imported_saved_users)

                    settings_imported = True
            except Exception as e:
                print(f"Error importing ui_settings from FRAMdata: {e}")

        saved_users_file = os.path.join(target_dir, 'saved_users.json')
        if os.path.exists(saved_users_file):
            try:
                with open(saved_users_file, 'r', encoding='utf-8') as suf:
                    file_users = json.load(suf)
                if isinstance(file_users, list) and file_users:
                    existing_unames = {str(item.get('username', '')).lower() for item in imported_saved_users}
                    for u in file_users:
                        if isinstance(u, dict):
                            uname = str(u.get('username') or '').strip().lstrip('@')
                            if uname and uname.lower() not in existing_unames:
                                imported_saved_users.append({
                                    'id': f"u{len(imported_saved_users) + 1}",
                                    'username': uname,
                                    'displayName': str(u.get('displayName') or u.get('display_name') or uname).strip(),
                                    'userId': str(u.get('userId') or u.get('user_id') or '').strip(),
                                    'icon_url': str(u.get('icon_url') or u.get('avatar_url') or '').strip()
                                })
                                existing_unames.add(uname.lower())
                    imported_users_count = len(imported_saved_users)
            except Exception as e:
                print(f"Error importing saved_users.json: {e}")

        webhook_file = os.path.join(target_dir, 'webhook_config.json')
        if os.path.exists(webhook_file):
            try:
                with open(webhook_file, 'r', encoding='utf-8') as wf:
                    wh_cfg = json.load(wf)
                if isinstance(wh_cfg, dict):
                    imported_webhook_config = wh_cfg
                    imported_settings['discordWebhookUrl'] = str(wh_cfg.get('webhook_url', '') or '')
                    imported_settings['discordLogMirrorEnabled'] = bool(wh_cfg.get('enabled', False))
            except Exception as e:
                print(f"Error importing webhook_config.json: {e}")

        themes_file = os.path.join(target_dir, 'custom_themes.json')
        if os.path.exists(themes_file):
            try:
                with open(themes_file, 'r', encoding='utf-8') as tf:
                    t_payload = json.load(tf)
                if isinstance(t_payload, dict):
                    imported_custom_themes = t_payload
            except Exception as e:
                print(f"Error importing custom_themes.json: {e}")

        return {
            'success': True,
            'accounts_imported': imported_accounts_count,
            'games_imported': imported_games_count,
            'users_imported': imported_users_count,
            'settings_imported': settings_imported,
            'webhooks_imported': imported_webhook_config is not None,
            'themes_imported': imported_custom_themes is not None,
            'imported_settings': imported_settings,
            'imported_games': imported_games,
            'imported_saved_users': imported_saved_users,
            'imported_webhook_config': imported_webhook_config,
            'imported_custom_themes': imported_custom_themes
        }


