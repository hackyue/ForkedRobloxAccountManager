"""
Account Manager class
Handles account storage, browser automation, and account management
"""

import os
import sys
import json
import time
import tempfile
import hashlib
import shutil
import subprocess
import re
import threading
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
try:
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from webdriver_manager.firefox import GeckoDriverManager
except Exception:
    FirefoxService = None
    FirefoxOptions = None
    GeckoDriverManager = None

from .encryption import HardwareEncryption, PasswordEncryption, EncryptionConfig
from .roblox_api import RobloxAPI


class RobloxAccountManager:
    LOGIN_DETECTION_INTERVAL_SECONDS = 0.25
    _SELENIUM_POPEN_KW = {
        "creation_flags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
    } if os.name == "nt" else {}
    
    def __init__(self, password=None):
        self.data_folder = "AccountManagerData"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        self.accounts_file = os.path.join(self.data_folder, "saved_accounts.json")
        self.encryption_config = EncryptionConfig(os.path.join(self.data_folder, "encryption_config.json"))
        self.encryptor = None
        
        if self.encryption_config.is_encryption_enabled():
            method = self.encryption_config.get_encryption_method()
            if method == 'hardware':
                self.encryptor = HardwareEncryption()
            elif method == 'password':
                if password is None:
                    raise ValueError("Password required for password-based encryption")
                
                stored_hash = self.encryption_config.get_password_hash()
                if stored_hash:
                    entered_hash = hashlib.sha256(password.encode()).hexdigest()
                    if entered_hash != stored_hash:
                        raise ValueError("Invalid password")
                
                salt = self.encryption_config.get_salt()
                self.encryptor = PasswordEncryption(password, salt)
        
        self.accounts = self.load_accounts()
        self.temp_profile_dir = None
        self.temp_profile_dirs = set()
        self._temp_profile_lock = threading.Lock()
        self.auto_rejoin_monitor = None
        
    def load_accounts(self):
        """Load saved accounts from JSON file"""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if self.encryptor and isinstance(data, dict) and data.get('encrypted'):
                    try:
                        decrypted_data = self.encryptor.decrypt_data(data['data'])

                        self._migrate_accounts(decrypted_data)
                        return decrypted_data
                    except Exception as e:
                        raise ValueError(f"Decryption failed. Wrong password or corrupted data.")
                

                if isinstance(data, dict):
                    self._migrate_accounts(data)
                return data if isinstance(data, dict) else {}
            except ValueError:
                raise
            except Exception as e:
                print(f"[WARNING] Error loading accounts: {e}")
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

    def normalize_private_server(self, value):
        """Normalize private server input to a Roblox link code when possible."""
        text = str(value or "").strip()
        if not text:
            return ""

        parsed_code = ""
        lowered = text.lower()
        if "://" in text or "roblox.com" in lowered:
            try:
                parsed = urlparse(text if "://" in text else f"https://{text}")
                query_values = parse_qs(parsed.query or "")
                for key in ("privateServerLinkCode", "linkCode", "privateServerId", "vipServerId", "code"):
                    values = query_values.get(key) or []
                    if values:
                        parsed_code = str(values[0] or "").strip()
                        if parsed_code:
                            break
            except Exception:
                parsed_code = ""

        if not parsed_code:
            match = re.search(
                r"(?i)(?:privateServerLinkCode|linkCode|privateServerId|vipServerId|code)\s*=\s*([A-Za-z0-9_-]+)",
                text,
            )
            if match:
                parsed_code = str(match.group(1) or "").strip()

        if parsed_code:
            return parsed_code
        return text
    
    def save_accounts(self):
        """Save accounts to JSON file"""
        with open(self.accounts_file, 'w', encoding='utf-8') as f:
            if self.encryptor:
                encrypted_package = self.encryptor.encrypt_data(self.accounts)
                encrypted_data = {
                    'encrypted': True,
                    'data': encrypted_package
                }
                json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(self.accounts, f, indent=2, ensure_ascii=False)

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

    def _is_browser_installed(self, browser_name):
        """Best-effort check for local browser executable presence."""
        name = (browser_name or "").strip().lower()
        if name not in {"chrome", "firefox"}:
            return False
        if name == "firefox" and (FirefoxService is None or FirefoxOptions is None or GeckoDriverManager is None):
            return False

        try:
            candidates = []
            pf = os.environ.get("ProgramFiles")
            pfx86 = os.environ.get("ProgramFiles(x86)")
            localapp = os.environ.get("LOCALAPPDATA")
            appdata = os.environ.get("APPDATA")

            if name == "chrome":
                if pf:
                    candidates.append(os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"))
                if pfx86:
                    candidates.append(os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"))
                if localapp:
                    candidates.append(os.path.join(localapp, "Google", "Chrome", "Application", "chrome.exe"))
            elif name == "firefox":
                if pf:
                    candidates.append(os.path.join(pf, "Mozilla Firefox", "firefox.exe"))
                if pfx86:
                    candidates.append(os.path.join(pfx86, "Mozilla Firefox", "firefox.exe"))
                if localapp:
                    candidates.append(os.path.join(localapp, "Mozilla Firefox", "firefox.exe"))
                if appdata:
                    candidates.append(os.path.join(appdata, "Mozilla", "Firefox", "firefox.exe"))

            for path in candidates:
                if path and os.path.exists(path):
                    return True
        except Exception:
            pass
        return False

    def has_supported_browser(self):
        return self._is_browser_installed("chrome") or self._is_browser_installed("firefox")

    def get_available_browsers(self):
        available = []
        if self._is_browser_installed("chrome"):
            available.append("chrome")
        if self._is_browser_installed("firefox"):
            available.append("firefox")
        return available

    def _get_browser_preference_order(self, preferred_browser=None):
        preferred = (preferred_browser or "").strip().lower()
        if preferred in {"chrome", "firefox"}:
            if preferred == "firefox":
                return ["firefox", "chrome"]
            return ["chrome", "firefox"]
        return ["chrome", "firefox"]

    def _setup_chrome_driver(self, headless=False):
        """Setup Chrome driver with speed-oriented options."""
        profile_dir = self.create_temp_profile()
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option('useAutomationExtension', False)

            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-gpu-logging")
            chrome_options.add_argument("--disable-dev-tools")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_experimental_option('useAutomationExtension', False)

            exclude_switches = {"enable-automation", "enable-logging"}
            chrome_options.add_experimental_option("excludeSwitches", sorted(exclude_switches))

            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
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

            service = Service(
                ChromeDriverManager().install(),
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

    def _setup_firefox_driver(self, headless=False):
        """Setup Firefox driver with compatible performance options."""
        if FirefoxService is None or FirefoxOptions is None or GeckoDriverManager is None:
            raise RuntimeError("Firefox Selenium support is unavailable in this environment.")

        profile_dir = self.create_temp_profile()
        try:
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("-profile")
            firefox_options.add_argument(profile_dir)
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

            service = FirefoxService(
                GeckoDriverManager().install(),
                log_output=os.devnull,
                popen_kw=self._SELENIUM_POPEN_KW.copy(),
            )
            driver = webdriver.Firefox(service=service, options=firefox_options)
            setattr(driver, "_ram_temp_profile_dir", profile_dir)
            return driver
        except Exception:
            self.cleanup_temp_profile(profile_dir)
            raise

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

            for browser_name in self._get_browser_preference_order(preferred_browser):
                try:
                    if not self._is_browser_installed(browser_name):
                        continue
                    if browser_name == "chrome":
                        driver = self._setup_chrome_driver(headless=headless)
                    else:
                        driver = self._setup_firefox_driver(headless=headless)
                    return driver, browser_name
                except Exception as exc:
                    attempted.append((browser_name, str(exc)))

            for browser_name in self._get_browser_preference_order(preferred_browser):
                try:
                    if browser_name == "chrome":
                        driver = self._setup_chrome_driver(headless=headless)
                    else:
                        driver = self._setup_firefox_driver(headless=headless)
                    return driver, browser_name
                except Exception as exc:
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
        print("Please make sure Google Chrome or Mozilla Firefox is installed.")
        return None, None

    def setup_chrome_driver(self):
        """
        Backward-compatible wrapper that now supports fallback to Firefox.
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
                    try {
                        localStorage.setItem('__ram_last_password', passwordField.value);
                    } catch (_storageError) {}
                }
            } catch (_captureError) {}
             
            if (url.includes('/login') || url.includes('/signup') || url.includes('/createaccount')) {
                return false;
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
                    return True, captured_password

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
                            '/develop' in current_url or '/create' in current_url) and '/login' not in current_url and '/createaccount' not in current_url.lower():
                            print("[SUCCESS] LOGIN DETECTED via manual URL check!")
                            cleanup_detection()
                            return True, captured_password
                                
                    except Exception as e:
                        print(f"Debug error: {e}")
                
                time.sleep(self.LOGIN_DETECTION_INTERVAL_SECONDS)
                
            except WebDriverException:
                cleanup_detection()
                return False, captured_password
        
        print("[WARNING] Login timeout. Please try again.")
        cleanup_detection()
        return False, captured_password
    
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
                username = RobloxAPI.get_username_from_api(roblosecurity_cookie)
            
            if not username:
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
                    const fromStorage = localStorage.getItem('__ram_last_password');
                    if (fromStorage !== null && fromStorage !== undefined) {
                        return fromStorage;
                    }
                } catch (_storageReadError) {}
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

        try:
            driver.execute_script(
                "try { localStorage.removeItem('__ram_last_password'); } catch (_storageRemoveError) {}"
            )
        except Exception:
            pass

        return captured_password

    def _extract_quick_sign_in_code(self, driver):
        try:
            script = """
            const response = {
                modalOpen: false,
                codeFromText: "",
                codeFromImage: "",
            };
            const titleEl = document.querySelector(".cross-device-login-display-code-modal-title-container .modal-title, h4.modal-title");
            const titleText = (titleEl ? titleEl.textContent : "").toLowerCase();
            response.modalOpen = titleText.includes("quick sign in code") || titleText.includes("quick sign-in code");

            const codeEl = document.querySelector(".cross-device-login-display-code-modal-title-container ~ .modal-body .font-title, .modal-body .font-title");
            if (codeEl && codeEl.textContent) {
                response.codeFromText = String(codeEl.textContent).trim().toUpperCase();
            }

            const imgEl = document.querySelector("img.cross-device-login-display-qr-code-image, img[src*='auth-token-service'][src*='code=']");
            if (imgEl && imgEl.getAttribute("src")) {
                try {
                    const url = new URL(imgEl.getAttribute("src"), window.location.origin);
                    response.codeFromImage = String(url.searchParams.get("code") || "").trim().toUpperCase();
                } catch (_error) {}
            }

            return response;
            """
            raw_value = driver.execute_script(script)
        except Exception:
            return ""

        if not isinstance(raw_value, dict):
            return ""
        if not bool(raw_value.get("modalOpen")):
            return ""

        for candidate in (raw_value.get("codeFromText"), raw_value.get("codeFromImage")):
            normalized = str(candidate or "").strip().upper().replace(" ", "").replace("-", "")
            if len(normalized) == 6 and normalized.isalnum():
                return normalized
        return ""

    def _quick_sign_in_button_candidates(self):
        return [
            (By.CSS_SELECTOR, "button[data-testid*='quick']"),
            (By.CSS_SELECTOR, "button[data-testid*='signin']"),
            (By.CSS_SELECTOR, "button[id*='quick']"),
            (By.CSS_SELECTOR, "button[class*='quick']"),
            (By.CSS_SELECTOR, "a[data-testid*='quick']"),
            (By.CSS_SELECTOR, "a[id*='quick']"),
            (By.CSS_SELECTOR, "a[class*='quick']"),
            (By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'quick')]"),
            (By.XPATH, "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'quick')]"),
        ]

    def _open_quick_sign_in_panel(self, driver):
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
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", element)
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
        ):
            if token in url_l:
                return True
        return "roblox.com/users/" in url_l

    def add_account_quick_sign_in(
        self,
        preferred_browser="auto",
        on_code=None,
        on_status=None,
        timeout=300,
        cancel_event=None,
    ):
        driver = None
        try:
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            driver, browser_name = self.setup_browser_driver(preferred_browser=preferred, headless=True)
            if not driver:
                return {
                    "success": False,
                    "username": "",
                    "code": "",
                    "error": "Unable to open a supported browser.",
                }

            if callable(on_status):
                on_status(f"Started {browser_name.capitalize()} in background. Preparing Quick Sign-In...")

            try:
                driver.set_window_size(520, 700)
            except Exception:
                pass
            driver.get("https://www.roblox.com/login")
            time.sleep(1.5)
            self._open_quick_sign_in_panel(driver)

            start_time = time.time()
            last_code = ""
            if callable(on_status):
                on_status("Waiting for Roblox Quick Sign-In code...")

            while time.time() - start_time < timeout:
                if cancel_event is not None and cancel_event.is_set():
                    return {
                        "success": False,
                        "username": "",
                        "code": last_code,
                        "error": "Quick Sign-In was cancelled.",
                    }

                quick_code = self._extract_quick_sign_in_code(driver)
                if quick_code and quick_code != last_code:
                    last_code = quick_code
                    if callable(on_code):
                        on_code(last_code)
                    if callable(on_status):
                        on_status("Code ready. Enter it on your other device to continue.")

                current_url = ""
                try:
                    current_url = driver.current_url
                except Exception:
                    current_url = ""
                has_cookie = False
                try:
                    cookies = driver.get_cookies()
                    has_cookie = any(cookie.get("name") == ".ROBLOSECURITY" for cookie in cookies)
                except Exception:
                    has_cookie = False

                if has_cookie or self._is_likely_logged_in_url(current_url):
                    username, cookie = self.extract_user_info(driver)
                    if username and cookie:
                        self.accounts[username] = {
                            "username": username,
                            "cookie": cookie,
                            "password": "",
                            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "note": "",
                            "group": "",
                            "vip_server": "",
                            "auto_rejoin_enabled": False,
                            "user_id": "",
                        }
                        self.save_accounts()
                        return {
                            "success": True,
                            "username": username,
                            "code": last_code,
                            "error": "",
                        }

                time.sleep(0.35)

            return {
                "success": False,
                "username": "",
                "code": last_code,
                "error": "Quick Sign-In timed out before login completed.",
            }
        except Exception as exc:
            return {
                "success": False,
                "username": "",
                "code": "",
                "error": str(exc),
            }
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
                self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
    
    def add_account(self, amount=1, website="https://www.roblox.com/login", javascript="", preferred_browser="auto"):
        """
        Add accounts through browser login with optional Javascript execution
        amount: number of browser instances to open (max 10)
        website: URL to navigate to
        javascript: Javascript code to execute after page load
        """
        if amount > 10:
            print("[WARNING] Maximum 10 instances allowed. Setting to 10.")
            amount = 10
        
        success_count = 0
        drivers = []
        
        try:
            print(f"Launching {amount} browser instance(s)...")
            
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            for i in range(amount):
                driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
                if not driver:
                    print(f"[ERROR] Failed to setup browser driver for instance {i + 1}")
                    continue
                
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
                
                drivers.append(driver)
                
                try:
                    print(f"Opening {website} in {browser_name.capitalize()} (instance {i + 1}/{amount})...")
                    driver.get(website)
                    
                    if javascript:
                        print(f"Executing Javascript for instance {i + 1}...")
                        try:
                            driver.execute_script(javascript)
                            print(f"[SUCCESS] Javascript executed for instance {i + 1}")
                        except Exception as js_error:
                            print(f"[WARNING] Javascript execution failed for instance {i + 1}: {js_error}")
                    
                except Exception as e:
                    print(f"[ERROR] Error opening browser for instance {i + 1}: {e}")
            
            print(f"All {len(drivers)} browser(s) opened. Waiting for logins...")
            
            completed = [False] * len(drivers)
            
            import threading
            
            def wait_for_instance(driver_index):
                driver = drivers[driver_index]
                try:
                    logged_in, wait_captured_password = self.wait_for_login(driver)
                    if logged_in:
                        username, cookie = self.extract_user_info(driver)
                        extracted_password = self.extract_captured_password(driver)
                        captured_password = extracted_password or wait_captured_password
                         
                        if username and cookie:
                            self.accounts[username] = {
                                'username': username,
                                'cookie': cookie,
                                'password': captured_password,
                                'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'note': '',
                                'group': '',
                                'vip_server': '',
                                'auto_rejoin_enabled': False,
                                'user_id': '',
                            }
                            self.save_accounts()
                            
                            print(f"[SUCCESS] Successfully added account: {username}")
                            nonlocal success_count
                            success_count += 1
                        else:
                            print(f"[ERROR] Failed to extract account information for instance {driver_index + 1}")
                    else:
                        print(f"[WARNING] Login timeout for instance {driver_index + 1}")
                except Exception as e:
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
            print(f"[ERROR] Error during account addition: {e}")
            for driver in drivers:
                try:
                    driver.quit()
                except Exception:
                    pass
                self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))
            return False

    def add_accounts_from_credentials(self, credentials, timeout_per_account=120, preferred_browser="auto"):
        if not credentials:
            return 0

        success_count = 0

        def first_present(driver, selectors):
            for by, selector in selectors:
                try:
                    element = driver.find_element(by, selector)
                    if element is not None:
                        return element
                except Exception:
                    continue
            return None

        for idx, entry in enumerate(credentials, 1):
            driver = None
            try:
                if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                    continue
                input_username, input_password = entry
                if not input_username or not input_password:
                    continue

                print(f"Launching credential login {idx}/{len(credentials)}...")

                preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
                driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
                if not driver:
                    print(f"[ERROR] Failed to setup browser driver for credential {idx}")
                    continue

                driver.set_window_size(500, 650)
                driver.get("https://www.roblox.com/login")
                print(f"Credential login {idx}/{len(credentials)} using {browser_name.capitalize()}.")

                username_input = first_present(driver, [
                    (By.ID, "login-username"),
                    (By.NAME, "username"),
                    (By.CSS_SELECTOR, "input#login-username"),
                    (By.CSS_SELECTOR, "input[name='username']"),
                ])
                password_input = first_present(driver, [
                    (By.ID, "login-password"),
                    (By.NAME, "password"),
                    (By.CSS_SELECTOR, "input#login-password"),
                    (By.CSS_SELECTOR, "input[name='password']"),
                ])

                if username_input is None or password_input is None:
                    print(f"[ERROR] Could not locate login inputs for credential {idx}")
                    continue

                try:
                    username_input.clear()
                except Exception:
                    pass
                try:
                    password_input.clear()
                except Exception:
                    pass

                username_input.send_keys(str(input_username))
                password_input.send_keys(str(input_password))

                login_btn = first_present(driver, [
                    (By.ID, "login-button"),
                    (By.CSS_SELECTOR, "button#login-button"),
                    (By.CSS_SELECTOR, "button[type='submit']"),
                ])
                if login_btn is not None:
                    try:
                        login_btn.click()
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", login_btn)
                        except Exception:
                            pass

                logged_in, _captured_password = self.wait_for_login(driver, timeout=timeout_per_account)
                if not logged_in:
                    print(f"[WARNING] Login failed or timed out for credential {idx}")
                    continue

                username, cookie = self.extract_user_info(driver)
                if not username or not cookie:
                    print(f"[ERROR] Failed to extract account info for credential {idx}")
                    continue

                self.accounts[username] = {
                    'username': username,
                    'cookie': cookie,
                    'password': str(input_password),
                    'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'note': '',
                    'group': '',
                    'vip_server': '',
                    'auto_rejoin_enabled': False,
                    'user_id': '',
                }
                self.save_accounts()
                success_count += 1
                print(f"[SUCCESS] Successfully added account: {username}")
            except Exception as e:
                print(f"[ERROR] Error importing credential {idx}: {e}")
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    self.cleanup_temp_profile(getattr(driver, "_ram_temp_profile_dir", None))

        return success_count
    
    def import_cookie_account(self, cookie):
        if not cookie:
            print("[ERROR] Cookie is required")
            return False, None
        
        cookie = cookie.strip()
        
        if not cookie.startswith('_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|'):
            print("[ERROR] Invalid cookie format")
            return False, None
        
        try:
            username = RobloxAPI.get_username_from_api(cookie)
            if not username or username == "Unknown":
                print("[ERROR] Failed to get username from cookie")
                return False, None
            
            is_valid = RobloxAPI.validate_account(username, cookie)
            if not is_valid:
                print("[ERROR] Cookie is invalid or expired")
                return False, None
            
            self.accounts[username] = {
                'username': username,
                'cookie': cookie,
                'password': '',
                'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'note': '',
                'group': '',
                'vip_server': '',
                'auto_rejoin_enabled': False,
                'user_id': '',
            }
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

    def launch_home(self, username, preferred_browser="auto"):
        """Launch browser to Roblox home with account logged in (Chrome/Firefox)."""
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False
        
        cookie = self.accounts[username]['cookie']
        
        try:
            preferred = None if str(preferred_browser or "auto").strip().lower() == "auto" else str(preferred_browser).strip().lower()
            driver, browser_name = self.setup_browser_driver(preferred_browser=preferred)
            if not driver:
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
            
            print(f"[SUCCESS] {browser_name.capitalize()} launched with {username} logged in!")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to launch browser: {e}")
            return False

    def launch_home_app(self, username, version=None, enable_debug=False):
        """Launch the native Roblox Home experience for the account"""
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False

        self.mark_session_intentionally_closed(username=username)
        return self.launch_roblox(username, "", "", version=version, enable_debug=enable_debug)

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
        preserve_rejoin_attempts=False,
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
        """
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False
            
        cookie = self.accounts[username]['cookie']
        normalized_launch_mode = str(launch_mode or "game").strip().lower()
        if normalized_launch_mode != "join_user":
            normalized_launch_mode = "game"

        launched = RobloxAPI.launch_roblox(
            username,
            cookie,
            game_id,
            private_server_id,
            version,
            enable_debug=enable_debug,
            server_job_id=server_job_id,
            launch_mode=normalized_launch_mode,
        )
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
                version_path=version,
                preserve_rejoin_attempts=preserve_rejoin_attempts,
            )
        return launched
    
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

    def set_account_vip_server(self, username, vip_server):
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False

        normalized = self.normalize_private_server(vip_server)
        self.accounts[username]['vip_server'] = normalized
        self.save_accounts()
        return True

    def get_account_vip_server(self, username):
        if username in self.accounts and isinstance(self.accounts[username], dict):
            stored = self.accounts[username].get('vip_server', '')
            return self.normalize_private_server(stored)
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
            normalized_value = self.normalize_private_server(raw_value)
            current_value = str(account_data.get('vip_server', '') or '').strip()
            if current_value != normalized_value:
                account_data['vip_server'] = normalized_value
                changed += 1

        if changed > 0:
            self.save_accounts()

        return {"matched": matched, "changed": changed, "missing": missing}
