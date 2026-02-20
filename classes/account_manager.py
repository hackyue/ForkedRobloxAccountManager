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
    LOGIN_DETECTION_INTERVAL_SECONDS = 0.1
    
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
        self.temp_profile_dir = tempfile.mkdtemp(prefix="roblox_login_")
        return self.temp_profile_dir
    
    def cleanup_temp_profile(self):
        """Clean up temporary profile directory"""
        if self.temp_profile_dir and os.path.exists(self.temp_profile_dir):
            try:
                shutil.rmtree(self.temp_profile_dir)
            except:
                pass

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

    def _setup_chrome_driver(self):
        """Setup Chrome driver with speed-oriented options."""
        profile_dir = self.create_temp_profile()

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

        service = Service(
            ChromeDriverManager().install(),
            log_path=os.devnull
        )
        driver = webdriver.Chrome(service=service, options=chrome_options)
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass
        return driver

    def _setup_firefox_driver(self):
        """Setup Firefox driver with compatible performance options."""
        if FirefoxService is None or FirefoxOptions is None or GeckoDriverManager is None:
            raise RuntimeError("Firefox Selenium support is unavailable in this environment.")

        profile_dir = self.create_temp_profile()

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

        service = FirefoxService(GeckoDriverManager().install(), log_output=os.devnull)
        return webdriver.Firefox(service=service, options=firefox_options)

    def setup_browser_driver(self, preferred_browser=None):
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
                        driver = self._setup_chrome_driver()
                    else:
                        driver = self._setup_firefox_driver()
                    return driver, browser_name
                except Exception as exc:
                    attempted.append((browser_name, str(exc)))
                    self.cleanup_temp_profile()

            for browser_name in self._get_browser_preference_order(preferred_browser):
                try:
                    if browser_name == "chrome":
                        driver = self._setup_chrome_driver()
                    else:
                        driver = self._setup_firefox_driver()
                    return driver, browser_name
                except Exception as exc:
                    attempted.append((browser_name, str(exc)))
                    self.cleanup_temp_profile()
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
        Ultra-fast login detection using ONLY URL method
        """
        print("Please log into your Roblox account")
        
        detect_interval_ms = max(50, int(self.LOGIN_DETECTION_INTERVAL_SECONDS * 1000))
        detector_script = """
        window.ultraFastDetection = {
            detected: false,
            method: null,
            debug: [],
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
                
                if result and result.get('detected'):
                    method = result.get('method', 'url_only')
                    print(f"[SUCCESS] LOGIN DETECTED! Method: {method} - Closing browser instantly...")
                    cleanup_detection()
                    return True
                
                current_time = time.time()
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
                            return True
                                
                    except Exception as e:
                        print(f"Debug error: {e}")
                
                time.sleep(self.LOGIN_DETECTION_INTERVAL_SECONDS)
                
            except WebDriverException:
                cleanup_detection()
                return False
        
        print("[WARNING] Login timeout. Please try again.")
        cleanup_detection()
        return False
    
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
                    if self.wait_for_login(driver):
                        username, cookie = self.extract_user_info(driver)
                        
                        if username and cookie:
                            self.accounts[username] = {
                                'username': username,
                                'cookie': cookie,
                                'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'note': '',
                                'group': ''
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
                    except:
                        pass
            
            threads = []
            for i in range(len(drivers)):
                thread = threading.Thread(target=wait_for_instance, args=(i,))
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
            
            for driver in drivers:
                self.cleanup_temp_profile()
            
            return success_count > 0
                
        except Exception as e:
            print(f"[ERROR] Error during account addition: {e}")
            for driver in drivers:
                try:
                    driver.quit()
                except:
                    pass
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

                logged_in = self.wait_for_login(driver, timeout=timeout_per_account)
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
                    'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'note': '',
                    'group': ''
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
                self.cleanup_temp_profile()

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
                'added_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'note': '',
                'group': ''
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
    
    def validate_account(self, username):
        """Validate if an account's cookie is still valid"""
        cookie = self.get_account_cookie(username)
        if not cookie:
            print(f"[ERROR] Account '{username}' not found")
            return False
        
        return RobloxAPI.validate_account(username, cookie)
    
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

        return self.launch_roblox(username, "", "", version=version, enable_debug=enable_debug)

    def launch_roblox(
        self,
        username,
        game_id,
        private_server_id="",
        version=None,
        enable_debug=False,
        server_job_id="",
    ):
        """
        Launch Roblox game with specified account and version
        
        Args:
            username: Roblox username
            game_id: ID of the game to launch
            private_server_id: Optional private server ID
            version: Optional path to Roblox version (if None, use default/latest)
            server_job_id: Optional public server job ID
        """
        if username not in self.accounts:
            print(f"[ERROR] Account '{username}' not found")
            return False
            
        cookie = self.accounts[username]['cookie']
        
        return RobloxAPI.launch_roblox(
            username,
            cookie,
            game_id,
            private_server_id,
            version,
            enable_debug=enable_debug,
            server_job_id=server_job_id,
        )
    
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
