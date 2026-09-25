from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import collections
import json
import re
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uuid
import hashlib
import hmac
import secrets
import time
import threading
import platform
import ctypes
from datetime import datetime
import subprocess
from typing import Dict, List, Any, Optional
import atexit
import signal
import psutil
from classes.account_manager import RobloxAccountManager
from classes.roblox_api import RobloxAPI
from classes.icon_cache import icon_cache
from classes.roblox_installer import roblox_installer_manager
from classes.updater import updater_manager
from classes.webhook_manager import WebhookManager
from classes.auto_arranger import AutoArranger
from classes.headless_manager import HeadlessManager
from classes.anti_afk import AntiAfkManager
from classes.browser_extensions import BrowserExtensionManager, BrowserExtensionError
from classes.roblox_swap import RobloxSwapManager
from classes.chromium_downloader import chromium_downloader_manager
from utils.paths import get_data_folder
from utils.cleanup import cleanup_temp_files
from utils.error_detector import error_detector, log_detailed_error

webhook_manager = WebhookManager()
pid_cpu_trackers = {}
pid_cpu_trackers_lock = threading.Lock()
auto_arranger = AutoArranger(settings_getter=lambda: load_data().get('settings', {}))
headless_manager = HeadlessManager(settings_getter=lambda: load_data().get('settings', {}))
auto_arranger.headless_manager = headless_manager
headless_manager.auto_arranger = auto_arranger
anti_afk_manager = AntiAfkManager(
    settings_getter=lambda: load_data().get('settings', {}),
    accounts_getter=lambda: load_data().get('accounts', []),
    launch_info_getter=lambda: last_launch_info,
    headless_manager=headless_manager,
    log_callback=lambda msg: print(msg),
)
anti_afk_manager.start_loop()

extension_manager = BrowserExtensionManager(get_data_folder())
roblox_swap_manager = RobloxSwapManager(get_data_folder())



app = Flask(__name__)

@app.errorhandler(Exception)
def handle_global_exception(e):
    extra_info = {
        'method': request.method,
        'path': request.path,
        'remote_addr': request.remote_addr,
        'headers': dict(request.headers)
    }
    if request.is_json and request.get_json(silent=True):
        extra_info['json_body'] = request.get_json(silent=True)
    elif request.args:
        extra_info['query_params'] = dict(request.args)
    
    log_detailed_error(
        context_message=f"Unhandled API Exception on {request.method} {request.path}",
        exc=e,
        extra_info=extra_info,
        level="CRITICAL",
        source="flask_api"
    )
    add_backend_log(f"Unhandled API Error: {str(e)}", level='error', category='api', source='flask_api')
    return jsonify({"error": "Internal server error"}), 500

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5050",
    "http://127.0.0.1:5050",
    "tauri://localhost",
    "https://tauri.localhost",
    "http://tauri.localhost"
]
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

API_AUTH_TOKEN = secrets.token_urlsafe(48)

def _write_auth_token():
    try:
        token_path = os.path.join(get_data_folder(), '.api_token')
        with open(token_path, 'w', encoding='utf-8') as f:
            f.write(API_AUTH_TOKEN)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(token_path, 0o600)
        except OSError:
            pass
    except Exception as e:
        print(f"[WARNING] Could not write API auth token file: {e}")

_write_auth_token()
try:
    cleanup_temp_files()
except Exception as e:
    log_detailed_error("Failed to run startup temp file cleanup", exc=e, source="startup")

quick_signin_sessions = {}
quick_signin_lock = threading.Lock()

server_job_pool_cache = {}
server_job_pool_lock = threading.Lock()

unlock_attempt_tracker = {'count': 0, 'last_attempt': 0, 'lockout_until': 0}

backend_logs = collections.deque(maxlen=1000)
backend_logs_lock = threading.Lock()

global_state_lock = threading.RLock()

def add_backend_log(message: str, level: str = 'info', category: str = 'system', source: str = 'backend'):
    with backend_logs_lock:
        now = datetime.now()
        timestamp = now.strftime('%H:%M:%S')
        backend_logs.append({
            'timestamp': timestamp,
            'time': int(now.timestamp() * 1000),
            'message': message,
            'level': level,
            'category': category,
            'source': source
        })

import logging

logging.getLogger('werkzeug').setLevel(logging.ERROR)

def classify_log_details(line_str: str, default_level: str) -> tuple[str, str]:
    line_lower = line_str.lower()
    
    if '" options ' in line_lower or 'options /' in line_lower or line_str.startswith('OPTIONS ') or \
       '" get ' in line_lower or 'get /' in line_lower or line_str.startswith('GET ') or \
       '" post ' in line_lower or 'post /' in line_lower or line_str.startswith('POST ') or \
       '" put ' in line_lower or '" delete ' in line_lower or 'put /' in line_lower or 'delete /' in line_lower or \
       '[fetch]' in line_lower or 'fetch /' in line_lower or '[api]' in line_lower or \
       '127.0.0.1 - -' in line_lower or '" 304 -' in line_lower or '" 200 -' in line_lower or '" 301 -' in line_lower or '" 302 -' in line_lower or '" 404 -' in line_lower or \
       line_lower.startswith('127.0.0.1') or line_lower == '"' or line_lower.endswith('304 -') or line_lower.endswith('200 -'):
        if ' 500 ' in line_str or ' 502 ' in line_str or ' 503 ' in line_str:
            return ('error', 'api')
        if ' 400 ' in line_str or ' 401 ' in line_str or ' 403 ' in line_str:
            return ('warning', 'api')
        return ('api', 'api')

    if 'running on http' in line_lower or 'press ctrl+c' in line_lower or 'serving flask app' in line_lower or 'debug mode:' in line_lower:
        return ('info', 'system')
    if '[error]' in line_lower or 'error:' in line_lower or 'exception' in line_lower or 'traceback' in line_lower or 'failed' in line_lower:
        return ('error', 'system')
    if '[warning]' in line_lower or 'warning:' in line_lower:
        return ('warning', 'system')
    if '[success]' in line_lower or 'success:' in line_lower:
        return ('success', 'system')

    return (default_level, 'system')

class SystemLogTee:
    def __init__(self, original_stream, default_level='info'):
        self.original_stream = original_stream
        self.default_level = default_level
        self.buffer = ''

    def write(self, message):
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except Exception:
                pass

        self.buffer += str(message or '')
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            line_str = line.strip()
            if line_str and not ('/api/system/logs' in line_str):
                level, category = classify_log_details(line_str, self.default_level)
                add_backend_log(line_str, level=level, category=category, source='backend')

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        if self.buffer.strip():
            line_str = self.buffer.strip()
            if not ('/api/system/logs' in line_str):
                level, category = classify_log_details(line_str, self.default_level)
                add_backend_log(line_str, level=level, category=category, source='backend')
            self.buffer = ''

sys.stdout = SystemLogTee(sys.stdout, 'info')
sys.stderr = SystemLogTee(sys.stderr, 'error')

@app.after_request
def log_api_request(response):
    if request.path.startswith('/api/'):
        if request.path == '/api/system/logs':
            return response
        
        method = request.method.upper()
        status_code = response.status_code
        path = request.path

        cat = 'api'
        lvl = 'api' if status_code < 400 else ('warning' if status_code < 500 else 'error')

        msg = f"{method} {path} - {status_code}"
        add_backend_log(msg, level=lvl, category=cat, source='backend')
    return response

add_backend_log("Backend server service online", "info", category="system")

@app.before_request
def enforce_api_auth():
    if request.path.startswith('/api/'):
        if request.method == 'OPTIONS':
            return None
        auth_exempt = (
            '/api/health',
            '/api/auth/token',
            '/api/auth/status',
            '/api/auth/unlock',
            '/api/auth/lock',
            '/api/auth/switch-encryption',
            '/api/setup/complete',
            '/api/setup/encryption-status'
        )
        if request.path not in auth_exempt and not request.path.startswith('/api/roblox/icon-file/'):
            provided_token = request.headers.get('X-FRAM-Token', '')
            if not provided_token or not hmac.compare_digest(provided_token, API_AUTH_TOKEN):
                return jsonify({'error': 'Unauthorized'}), 401

_cached_encryption_config = None
_cached_encryption_mtime = 0

def get_cached_encryption_config():
    global _cached_encryption_config, _cached_encryption_mtime
    try:
        from utils.paths import get_data_folder
        from classes.encryption import EncryptionConfig
        config_path = os.path.join(get_data_folder(), 'encryption_config.json')
        if not os.path.exists(config_path):
            return None
        mtime = os.path.getmtime(config_path)
        if _cached_encryption_config is None or mtime != _cached_encryption_mtime:
            _cached_encryption_config = EncryptionConfig(config_path)
            _cached_encryption_mtime = mtime
        return _cached_encryption_config
    except Exception:
        return None

@app.before_request
def enforce_vault_lock():
    if request.path.startswith('/api/'):
        allowed = (
            '/api/auth/status',
            '/api/auth/unlock',
            '/api/auth/lock',
            '/api/auth/token',
            '/api/auth/switch-encryption',
            '/api/health',
            '/api/system/logs',
            '/api/setup/complete',
            '/api/setup/encryption-status',
            '/api/setup/preview-framdata',
            '/api/setup/import-framdata',
            '/api/setup/select-folder',
            '/api/installer/available-versions',
            '/api/installer/clients',
            '/api/installer/start',
            '/api/installer/status',
            '/api/installer/weao-exploits',
            '/api/roblox/versions',
            '/api/roblox/launch-app',
            '/api/roblox/uninstall-version',
            '/api/updater/check',
            '/api/updater/releases',
            '/api/updater/download',
            '/api/updater/status',
            '/api/updater/apply',
            '/api/browser/chromium/status',
            '/api/browser/chromium/download',
            '/api/browser/chromium/uninstall'
        )
        if request.path in allowed or request.path.startswith('/api/rblxswap/') or request.method == 'OPTIONS':
            return None
        try:
            config = get_cached_encryption_config()
            if config and config.is_encryption_enabled() and config.get_encryption_method() == 'password':
                if active_master_password is None:
                    return jsonify({'error': 'Application vault is locked', 'locked': True}), 401
        except Exception as e:
            print(f"[ERROR] Vault lock check failed, denying request for safety: {e}")
            return jsonify({'error': 'Vault lock check failed', 'locked': True}), 401

class MultiInstanceController:
    """Manages system-wide named mutexes required to allow multiple Roblox game client instances"""
    def __init__(self):
        self.mutex_handles = []
        self.is_enabled = False

    def enable(self) -> bool:
        if platform.system() != "Windows":
            print("[INFO] Multi-instance Roblox is only supported on Windows")
            self.is_enabled = True
            return True
        try:
            if not self.mutex_handles:
                kernel32 = ctypes.windll.kernel32
                kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
                kernel32.CreateMutexW.restype = ctypes.c_void_p
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel32.CloseHandle.restype = ctypes.c_bool

                m1 = kernel32.CreateMutexW(None, True, "ROBLOX_singletonEvent")
                m2 = kernel32.CreateMutexW(None, True, "ROBLOX_singletonMutex")
                self.mutex_handles = [m for m in (m1, m2) if m]
                print(f"[SUCCESS] Multi-instance Roblox enabled. Active mutex handles: {self.mutex_handles}")
            self.is_enabled = True
            return True
        except Exception as e:
            print(f"[ERROR] Failed to enable multi-instance: {e}")
            return False

    def disable(self) -> bool:
        if platform.system() != "Windows":
            self.is_enabled = False
            return True
        try:
            if self.mutex_handles:
                kernel32 = ctypes.windll.kernel32
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel32.CloseHandle.restype = ctypes.c_bool
                for m in self.mutex_handles:
                    try:
                        kernel32.CloseHandle(m)
                    except Exception:
                        pass
                self.mutex_handles = []
                print("[INFO] Multi-instance Roblox disabled. Mutexes released.")
            self.is_enabled = False
            return True
        except Exception as e:
            print(f"[ERROR] Failed to disable multi-instance: {e}")
            return False

    def sync_state(self, enabled: bool):
        if enabled:
            self.enable()
        else:
            self.disable()

multi_instance_controller = MultiInstanceController()

account_manager = None
active_master_password = None
last_account_decryption_error = None

def _rejoin_launch_callback(session, attempt_number):
    mgr = get_account_manager()
    if not mgr:
        return False
    uname = session.username
    place_id = session.place_id
    p_server = session.private_server_link
    j_server = session.server_job_id
    version = session.version_path
    mode = session.launch_mode
    launched = mgr.launch_roblox(
        username=uname,
        game_id=place_id,
        private_server_id=p_server,
        server_job_id=j_server,
        version=version,
        launch_mode=mode
    )
    if launched:
        webhook_manager.notify_rejoin(uname, place_id or "Home", reason=f"Auto-rejoin monitor trigger (attempt {attempt_number})")
    return bool(launched)

def _rejoin_presence_lookup(cookie, user_ids, session=None):
    try:
        import requests
        s = session or requests.Session()
        headers = {
            "User-Agent": "Roblox/WinInet",
            "Referer": "https://www.roblox.com/"
        }
        if cookie:
            headers["Cookie"] = f".ROBLOSECURITY={cookie}"
        valid_ids = [int(u) for u in user_ids if str(u).isdigit()]
        if not valid_ids:
            return {"ok": False}
        resp = s.post("https://presence.roblox.com/v1/presence/users", json={"userIds": valid_ids}, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json() or {}
            return {"ok": True, "user_presences": data.get("userPresences") or []}
        if resp.status_code in (401, 403):
            return {"ok": False, "auth_error": True}
        return {"ok": False}
    except Exception:
        return {"ok": False}

def init_auto_rejoin_monitor(manager):
    if not manager:
        return None
    if getattr(manager, 'auto_rejoin_monitor', None) is not None:
        return manager.auto_rejoin_monitor
    try:
        from classes.auto_rejoin import AutoRejoinMonitor
        monitor = AutoRejoinMonitor(
            launch_callback=_rejoin_launch_callback,
            presence_lookup=_rejoin_presence_lookup,
            log_callback=lambda msg: print(msg)
        )
        manager.set_auto_rejoin_monitor(monitor)
        monitor.start()
        anti_afk_manager.auto_rejoin_monitor = monitor
        return monitor
    except Exception as e:
        print(f"Failed to start AutoRejoinMonitor: {e}")
        return None

def get_account_manager(password=None):
    global account_manager, active_master_password, last_account_decryption_error
    with global_state_lock:
        pwd = password or active_master_password
        try:
            from utils.paths import get_data_folder
            from classes.encryption import EncryptionConfig
            config_path = os.path.join(get_data_folder(), 'encryption_config.json')
            config = EncryptionConfig(config_path)
            if config.is_encryption_enabled() and config.get_encryption_method() == 'password':
                if not pwd:
                    return None
            if account_manager is None or password is not None:
                account_manager = RobloxAccountManager(password=pwd)
                account_manager.on_save_callback = invalidate_data_cache
                if pwd:
                    active_master_password = pwd
                last_account_decryption_error = None
                init_auto_rejoin_monitor(account_manager)
        except Exception as e:
            print(f"Error initializing account manager: {e}")
            account_manager = None
            if "Failed to decrypt" in str(e) or "Decryption failed" in str(e):
                last_account_decryption_error = str(e)
                exc_type, exc_value, exc_tb = sys.exc_info()
                error_detector.record_exception(exc_type or ValueError, e, exc_tb, source="account_manager_init")
            else:
                raise e
        return account_manager

DATA_FOLDER = get_data_folder()
ACCOUNTS_FILE = os.path.join(DATA_FOLDER, 'accounts.json')
GAMES_FILE = os.path.join(DATA_FOLDER, 'games.json')
SAVED_USERS_FILE = os.path.join(DATA_FOLDER, 'saved_users.json')
SETTINGS_FILE = os.path.join(DATA_FOLDER, 'settings.json')

os.makedirs(DATA_FOLDER, exist_ok=True)

_DATA_CACHE: Optional[Dict[str, Any]] = None
_DATA_CACHE_TIME: float = 0.0
_DATA_CACHE_TTL: float = 1.5
_DATA_CACHE_LOCK = threading.Lock()

def invalidate_data_cache():
    global _DATA_CACHE, _DATA_CACHE_TIME
    with _DATA_CACHE_LOCK:
        _DATA_CACHE = None
        _DATA_CACHE_TIME = 0.0

def _clone_data_fast(src: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    return {
        'accounts': [dict(a) for a in src.get('accounts', []) if isinstance(a, dict)],
        'games': [dict(g) for g in src.get('games', []) if isinstance(g, dict)],
        'saved_users': [dict(u) for u in src.get('saved_users', []) if isinstance(u, dict)],
        'settings': dict(src.get('settings', {}))
    }

def load_data(force_reload: bool = False) -> Dict[str, Any]:
    global _DATA_CACHE, _DATA_CACHE_TIME, last_account_decryption_error
    now = time.time()
    with _DATA_CACHE_LOCK:
        if not force_reload and _DATA_CACHE is not None and (now - _DATA_CACHE_TIME) < _DATA_CACHE_TTL:
            return _clone_data_fast(_DATA_CACHE)

    data = {
        'accounts': [],
        'games': [],
        'saved_users': [],
        'settings': {
            'firstLaunch': True,
            'multiSelect': True,
            'activeIndicator': True,
            'disableSuccessPopups': False,
            'confirmBeforeLaunch': True,
            'compactRows': False,
            'accentIndex': 0,
            'selectedTheme': 'default-dark',
            'accentColor': '',
            'robloxPath': '',
            'launchClient': 'standard',
            'autoUpdateCheck': True,
            'autoCheckRobloxUpdates': True,
            'disableExecutorPresets': False,
            'swapPreserveSettings': True,
            'encryptionEnabled': False,
            'encryptionMethod': 'none',
            'preferredBrowser': 'auto',
            'credentialImportInstances': 1,
            'multiInstance': False,
            'showTableAvatars': True,
            'downloadAvatarIcons': True,
            'showSavedGamesBar': True,
            'autoSaveLaunchDetails': True,
            'showDetailPanel': True,
            'detailPanelPosition': 'right',
            'launchBarPosition': 'bottom',
            'toastPosition': 'bottom-right',
            'toastDuration': 3500,
            'enableSoundEffects': True,
            'showLaunchNotifications': True,
            'showErrorNotifications': True,
            'defaultStartupView': 'accounts',
            'autoValidateOnLaunch': True,
            'autoSortAccounts': 'none',
            'multiLaunchDelay': 1000,
            'confirmBulkDelete': True,
            'autoKillRobloxOnExit': False,
            'minimizeToTray': False,
            'startAtStartup': False,
            'streamerMode': False,
            'streamerHideUsernames': True,
            'streamerHideAvatars': True,
            'streamerHideSensitiveInfo': True,
            'streamerHideGroupsAndNotes': False,
            'streamerBlurLevel': 'medium',
            'streamerRevealOnHover': False,
            'autoArrangeScope': 'both',
            'autoArrangeDimensionMode': 'auto',
            'autoArrangeTargetWidth': 800,
            'autoArrangeTargetHeight': 600,
            'keepClientsArranged': False,
            'headlessMode': False,
            'headlessTrimMemory': True,
            'headlessIdlePriority': True,
            'headlessDetectionDelaySeconds': 0,
            'antiAfkEnabled': False,
            'antiAfkIntervalMinutes': 10,
            'antiAfkKeyName': 'M1',
            'antiAfkKeyCode': 0,
            'antiAfkShowNextLabel': False,
            'preferredRegion': '',
            'serverPerAccount': False,
            'pick_server_per_account': False
        }
    }
    
    accounts_by_username = {}

    manager = None
    try:
        manager = get_account_manager()
    except Exception as e:
        print(f"Error initializing account manager in load_data: {e}")

    if manager:
        try:
            manager.accounts = manager.load_accounts()
            last_account_decryption_error = None
            for username, account_data in manager.accounts.items():
                if isinstance(account_data, dict):
                    accounts_by_username[username] = {
                        'id': account_data.get('id') or (int(hashlib.md5(username.encode('utf-8')).hexdigest()[:7], 16)),
                        'username': username,
                        'display_name': account_data.get('display_name', username),
                        'avatar_url': account_data.get('avatar_url', ''),
                        'cookie': account_data.get('cookie', ''),
                        'password': account_data.get('password', ''),
                        'note': account_data.get('note', ''),
                        'group': account_data.get('group', ''),
                        'vip_server': account_data.get('vip_server', ''),
                        'vip_place_id': account_data.get('vip_place_id', ''),
                        'vip_game_name': account_data.get('vip_game_name', ''),
                        'auto_rejoin_enabled': account_data.get('auto_rejoin_enabled', False),
                        'anti_afk_enabled': account_data.get('anti_afk_enabled', False),
                        'user_id': account_data.get('user_id', ''),
                        'status': account_data.get('status', 'valid' if RobloxAPI._normalize_roblosecurity_cookie(account_data.get('cookie', '')) else 'expired'),
                        'added_date': account_data.get('added_date', '')
                    }
        except Exception as e:
            print(f"Error loading from account manager: {e}")
            if "Failed to decrypt" in str(e) or "Decryption failed" in str(e):
                last_account_decryption_error = str(e)
                exc_type, exc_value, exc_tb = sys.exc_info()
                error_detector.record_exception(exc_type or ValueError, e, exc_tb, source="account_manager_load")

    if not last_account_decryption_error and os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                json_accounts = json.load(f)
                if isinstance(json_accounts, list):
                    for acc in json_accounts:
                        if isinstance(acc, dict) and acc.get('username'):
                            u = acc['username']
                            if u not in accounts_by_username:
                                accounts_by_username[u] = acc
                            else:
                                existing = accounts_by_username[u]
                                for k, v in acc.items():
                                    if v and not existing.get(k):
                                        existing[k] = v
        except Exception as e:
            print(f"Error loading accounts from JSON: {e}")

    cached_config = get_cached_encryption_config()
    is_locked = bool(cached_config and cached_config.is_encryption_enabled()
                     and cached_config.get_encryption_method() == 'password'
                     and active_master_password is None)

    data['accounts'] = list(accounts_by_username.values())
    for idx, acc in enumerate(data['accounts']):
        if not acc.get('id'):
            acc['id'] = idx + 1
        has_cookie = bool(RobloxAPI._normalize_roblosecurity_cookie(acc.get('cookie', '')))
        raw_status = str(acc.get('status', '')).lower()
        if not has_cookie and not is_locked:
            acc['status'] = 'banned' if raw_status == 'banned' else 'expired'
        elif raw_status in ('valid', 'banned', 'expired'):
            acc['status'] = raw_status
        elif raw_status in ('online', 'ingame', 'offline', 'active', 'ok'):
            acc['status'] = 'valid' if (has_cookie or is_locked) else 'expired'
        elif raw_status in ('invalid', 'error', 'missing'):
            acc['status'] = 'expired'
        else:
            acc['status'] = 'valid' if (has_cookie or is_locked) else 'expired'

    if os.path.exists(GAMES_FILE):
        try:
            with open(GAMES_FILE, 'r', encoding='utf-8') as f:
                data['games'] = json.load(f)
        except Exception as e:
            print(f"Error loading games from JSON: {e}")

    if os.path.exists(SAVED_USERS_FILE):
        try:
            with open(SAVED_USERS_FILE, 'r', encoding='utf-8') as f:
                data['saved_users'] = json.load(f)
        except Exception as e:
            print(f"Error loading saved users from JSON: {e}")
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                data['settings'].update(loaded_settings)
        except Exception as e:
            print(f"Error loading settings from JSON: {e}")
    
    multi_instance_controller.sync_state(data['settings'].get('multiInstance', False))
    auto_arranger.sync_watchdog(data['settings'].get('keepClientsArranged', False))
    headless_manager.sync_watchdog(data['settings'].get('headlessMode', False))

    with _DATA_CACHE_LOCK:
        _DATA_CACHE = data
        _DATA_CACHE_TIME = time.time()

    return _clone_data_fast(data)

_SAVE_DATA_LOCK = threading.RLock()


class _DataTransaction:
    """Context manager for atomic read-modify-write operations on app data.
    
    Acquires _SAVE_DATA_LOCK on entry, loads fresh data, and provides save()
    to persist changes before releasing the lock. This prevents concurrent
    requests from overwriting each other's mutations.
    
    Usage:
        with data_transaction() as txn:
            txn.data['accounts'].append(new_account)
            txn.save()
            return jsonify(new_account)
    """

    def __init__(self):
        self.data: Optional[Dict[str, Any]] = None
        self._saved = False

    def __enter__(self):
        _SAVE_DATA_LOCK.acquire()
        self.data = load_data(force_reload=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _SAVE_DATA_LOCK.release()
        return False

    def save(self):
        if self.data is not None:
            save_data(self.data)
            self._saved = True


def data_transaction() -> _DataTransaction:
    """Create a transaction for atomic read-modify-write on app data."""
    return _DataTransaction()


def _atomic_json_write(target_path: str, data_obj: Any):
    tmp_path = f"{target_path}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data_obj, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        max_retries = 10
        for attempt in range(max_retries):
            try:
                os.replace(tmp_path, target_path)
                break
            except (PermissionError, OSError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data_obj, f, indent=2, ensure_ascii=False)
        except Exception as write_err:
            print(f"Error writing to {target_path}: {write_err}")

def save_data(data: Dict[str, Any]):
    with _SAVE_DATA_LOCK:
        invalidate_data_cache()
        from utils.paths import get_data_folder
        from classes.encryption import EncryptionConfig
        config_path = os.path.join(get_data_folder(), 'encryption_config.json')
        config = EncryptionConfig(config_path)
        encryption_enabled = config.is_encryption_enabled()

        saved_to_manager_successfully = False
        manager = get_account_manager()
        if manager:
            try:
                accounts_dict = {}
                for account in data.get('accounts', []):
                    if isinstance(account, dict):
                        username = account.get('username', '')
                        if username:
                            cookie = account.get('cookie', '')
                            if not cookie and isinstance(manager.accounts, dict) and username in manager.accounts:
                                existing_cookie = manager.accounts[username].get('cookie', '')
                                if existing_cookie:
                                    cookie = existing_cookie
                            password = account.get('password', '')
                            if not password and isinstance(manager.accounts, dict) and username in manager.accounts:
                                existing_pwd = manager.accounts[username].get('password', '')
                                if existing_pwd:
                                    password = existing_pwd
                            accounts_dict[username] = {
                                'id': account.get('id'),
                                'username': username,
                                'display_name': account.get('display_name', username),
                                'avatar_url': account.get('avatar_url', ''),
                                'cookie': cookie,
                                'password': password,
                                'note': account.get('note', ''),
                                'group': account.get('group', ''),
                                'vip_server': account.get('vip_server', ''),
                                'vip_place_id': account.get('vip_place_id', ''),
                                'vip_game_name': account.get('vip_game_name', ''),
                                'auto_rejoin_enabled': account.get('auto_rejoin_enabled', False),
                                'anti_afk_enabled': account.get('anti_afk_enabled', False),
                                'user_id': account.get('user_id', ''),
                                'status': account.get('status', 'valid'),
                                'added_date': account.get('added_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            }
                manager.accounts = accounts_dict
                manager.save_accounts()
                saved_to_manager_successfully = True
            except Exception as e:
                print(f"Error syncing with account manager: {e}")

        sanitized_accounts = []
        for account in data.get('accounts', []):
            if isinstance(account, dict):
                acc_copy = dict(account)
                if encryption_enabled and saved_to_manager_successfully and manager and manager.encryptor:
                    acc_copy['cookie'] = ''
                    acc_copy['password'] = ''
                sanitized_accounts.append(acc_copy)

        _atomic_json_write(ACCOUNTS_FILE, sanitized_accounts)
        _atomic_json_write(GAMES_FILE, data.get('games', []))
        _atomic_json_write(SAVED_USERS_FILE, data.get('saved_users', []))
        _atomic_json_write(SETTINGS_FILE, data.get('settings', {}))

        multi_instance_controller.sync_state(data.get('settings', {}).get('multiInstance', False))
        sync_startup_registry(data.get('settings', {}).get('startAtStartup', False))
        auto_arranger.sync_watchdog(data.get('settings', {}).get('keepClientsArranged', False))
        headless_manager.sync_watchdog(data.get('settings', {}).get('headlessMode', False))

def sync_startup_registry(enable: bool):
    if platform.system() != "Windows":
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Forked Account Manager"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            exe_path = sys.executable
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Error syncing startup registry: {e}")

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    data = load_data()
    if last_account_decryption_error:
        return jsonify({'success': False, 'error': last_account_decryption_error}), 500
    settings = data.get('settings', {})
    download_avatars = settings.get('downloadAvatarIcons', True)
    updated = False
    if download_avatars:
        accounts_needing_avatars = [acc for acc in data.get('accounts', []) if not acc.get('avatar_url')]
        if accounts_needing_avatars:
            def bg_fetch_avatars():
                from concurrent.futures import ThreadPoolExecutor
                def fetch_avatar(acc):
                    try:
                        uid = acc.get('user_id') or RobloxAPI.get_user_id_from_username(acc.get('username', ''))
                        if uid:
                            acc['user_id'] = str(uid)
                            headshot = RobloxAPI.get_avatar_headshot_url(uid)
                            if headshot:
                                acc['avatar_url'] = headshot
                                return True
                    except Exception:
                        pass
                    return False

                with _SAVE_DATA_LOCK:
                    cur_data = load_data()
                    cur_accounts = [a for a in cur_data.get('accounts', []) if isinstance(a, dict) and not a.get('avatar_url')]
                    if not cur_accounts:
                        return
                    max_workers = min(10, max(1, len(cur_accounts)))
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        results = list(executor.map(fetch_avatar, cur_accounts))
                    if any(results):
                        save_data(cur_data)

            threading.Thread(target=bg_fetch_avatars, daemon=True).start()
    return jsonify(data['accounts'])

@app.route('/api/accounts', methods=['POST'])
def create_account():
    account_data = request.json or {}

    cookie = account_data.get('cookie', '')
    if cookie:
        cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)
        account_data['cookie'] = cookie
    username = account_data.get('username', '')
    user_id = account_data.get('user_id', '')

    if cookie:
        status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
            cookie=cookie,
            username=username,
            user_id=user_id,
            existing_status=account_data.get('status', 'valid')
        )
        account_data['status'] = status
        if found_uid: account_data['user_id'] = found_uid
        if found_user and found_user != 'Unknown': account_data['username'] = found_user
        if found_display: account_data['display_name'] = found_display
        if avatar_url: account_data['avatar_url'] = avatar_url
    else:
        account_data['status'] = 'expired'

    if 'password' not in account_data:
        account_data['password'] = ''
    if 'cookie' not in account_data:
        account_data['cookie'] = ''

    with data_transaction() as txn:
        max_id = max([acc.get('id', 0) for acc in txn.data['accounts']] + [0])
        account_data['id'] = max_id + 1
        txn.data['accounts'].append(account_data)
        txn.save()
    return jsonify(account_data), 201

@app.route('/api/accounts/bulk-import-cookies', methods=['POST'])
def bulk_import_cookies():
    try:
        payload = request.json or {}
        items = payload.get('accounts', [])
        default_group = str(payload.get('default_group', '') or '').strip()
        default_note = str(payload.get('default_note', '') or '').strip()

        if not isinstance(items, list) or len(items) == 0:
            return jsonify({'success': False, 'error': 'No accounts or cookies provided'}), 400

        imported_accounts = []
        errors = []

        from concurrent.futures import ThreadPoolExecutor

        def process_item(item_data):
            try:
                raw_cookie = str(item_data.get('cookie', '') or '').strip()
                cookie = RobloxAPI._normalize_roblosecurity_cookie(raw_cookie)
                if not cookie:
                    return None, 'Empty cookie string'

                username = str(item_data.get('username', '') or '').strip()
                user_id = str(item_data.get('user_id', '') or '').strip()
                password = str(item_data.get('password', '') or '').strip()
                group = str(item_data.get('group', '') or '').strip() or default_group
                note = str(item_data.get('note', '') or '').strip() or default_note

                status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
                    cookie=cookie,
                    username=username,
                    user_id=user_id
                )

                resolved_username = found_user if (found_user and found_user != 'Unknown') else username
                if not resolved_username:
                    resolved_username = f"Account_{abs(hash(cookie)) % 100000}"

                acc_record = {
                    'username': resolved_username,
                    'display_name': found_display or resolved_username,
                    'avatar_url': avatar_url or '',
                    'cookie': cookie,
                    'password': password,
                    'group': group,
                    'note': note,
                    'status': status,
                    'user_id': found_uid or user_id or '',
                    'vip_server': '',
                    'auto_rejoin_enabled': False,
                    'added_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                return acc_record, None
            except Exception as item_err:
                return None, str(item_err)

        max_workers = min(10, max(1, len(items)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_item, items))

        with data_transaction() as txn:
            data = txn.data
            existing_accounts = data.get('accounts', [])
            max_id = max([acc.get('id', 0) for acc in existing_accounts] + [0])

            for acc_record, err in results:
                if acc_record:
                    max_id += 1
                    acc_record['id'] = max_id

                    norm_cookie = RobloxAPI._normalize_roblosecurity_cookie(acc_record['cookie'])
                    existing_idx = -1
                    for idx, existing in enumerate(data['accounts']):
                        ex_cookie = RobloxAPI._normalize_roblosecurity_cookie(existing.get('cookie', ''))
                        if (ex_cookie and norm_cookie and ex_cookie == norm_cookie) or (acc_record['username'] and existing.get('username') == acc_record['username']):
                            existing_idx = idx
                            break

                    if existing_idx >= 0:
                        acc_record['id'] = data['accounts'][existing_idx]['id']
                        data['accounts'][existing_idx] = acc_record
                    else:
                        data['accounts'].append(acc_record)

                    imported_accounts.append(acc_record)
                elif err:
                    errors.append(err)

            txn.save()

        return jsonify({
            'success': True,
            'imported_count': len(imported_accounts),
            'failed_count': len(errors),
            'accounts': imported_accounts,
            'errors': errors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['GET'])
def get_account(account_id):
    data = load_data()
    account = next((acc for acc in data['accounts'] if acc['id'] == account_id), None)
    if account:
        return jsonify(account)
    return jsonify({'error': 'Account not found'}), 404

@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    update_data = request.json or {}
    allowed_fields = {'username', 'display_name', 'avatar_url', 'cookie', 'password',
                      'note', 'group', 'vip_server', 'vip_place_id', 'vip_game_name',
                      'auto_rejoin_enabled', 'user_id', 'status', 'added_date'}

    cookie_info = None
    if 'cookie' in update_data:
        raw_cookie = RobloxAPI._normalize_roblosecurity_cookie(update_data.get('cookie', ''))
        cookie_info = RobloxAPI.get_account_status_and_info(
            cookie=raw_cookie,
            username=update_data.get('username', ''),
            user_id=update_data.get('user_id', ''),
            existing_status=update_data.get('status', 'valid')
        )

    with data_transaction() as txn:
        account = next((acc for acc in txn.data['accounts'] if acc['id'] == account_id), None)
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        for key, value in update_data.items():
            if key in allowed_fields:
                account[key] = value

        if cookie_info is not None:
            account['cookie'] = RobloxAPI._normalize_roblosecurity_cookie(account.get('cookie', ''))
            status, found_uid, found_user, found_display, avatar_url = cookie_info
            account['status'] = status
            if found_uid: account['user_id'] = found_uid
            if found_user and found_user != 'Unknown': account['username'] = found_user
            if found_display: account['display_name'] = found_display
            if avatar_url: account['avatar_url'] = avatar_url

        txn.save()
    return jsonify(account)

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    with data_transaction() as txn:
        account = next((acc for acc in txn.data['accounts'] if acc['id'] == account_id), None)
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        txn.data['accounts'].remove(account)
        txn.save()
    return jsonify({'message': 'Account deleted'})

@app.route('/api/accounts/bulk-delete', methods=['POST'])
def bulk_delete_accounts():
    req_data = request.json or {}
    account_ids = req_data.get('ids', [])
    if not isinstance(account_ids, list):
        return jsonify({'error': 'ids must be a list'}), 400
    with data_transaction() as txn:
        txn.data['accounts'] = [acc for acc in txn.data['accounts'] if acc['id'] not in account_ids]
        txn.save()
    return jsonify({'message': f'Deleted {len(account_ids)} accounts'})

@app.route('/api/accounts/reorder', methods=['POST'])
def reorder_accounts():
    try:
        req_data = request.json or {}
        ordered_ids = req_data.get('ids')
        ordered_usernames = req_data.get('usernames')

        if not ordered_ids and not ordered_usernames:
            return jsonify({'error': 'ids or usernames required'}), 400

        with data_transaction() as txn:
            acc_map_by_id = {acc['id']: acc for acc in txn.data.get('accounts', [])}
            acc_map_by_uname = {acc['username']: acc for acc in txn.data.get('accounts', [])}

            new_accounts = []
            seen_ids = set()

            if ordered_ids:
                for aid in ordered_ids:
                    if aid in acc_map_by_id and aid not in seen_ids:
                        new_accounts.append(acc_map_by_id[aid])
                        seen_ids.add(aid)
            elif ordered_usernames:
                for uname in ordered_usernames:
                    if uname in acc_map_by_uname:
                        acc = acc_map_by_uname[uname]
                        if acc['id'] not in seen_ids:
                            new_accounts.append(acc)
                            seen_ids.add(acc['id'])

            for acc in txn.data.get('accounts', []):
                if acc['id'] not in seen_ids:
                    new_accounts.append(acc)
                    seen_ids.add(acc['id'])

            txn.data['accounts'] = new_accounts
            txn.save()

        try:
            manager = get_account_manager()
            if manager:
                manager.reorder_accounts([acc['username'] for acc in new_accounts])
        except Exception:
            pass

        return jsonify({'success': True, 'accounts': new_accounts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/bulk-vip', methods=['POST'])
def bulk_vip_accounts():
    req_data = request.json or {}
    mapping = req_data.get('mapping', {})
    changed = 0
    with data_transaction() as txn:
        data = txn.data
        for acc in data.get('accounts', []):
            uname = acc.get('username', '')
            acc_id = str(acc.get('id', ''))
            val = mapping.get(uname) if uname in mapping else mapping.get(acc_id)
            if val is not None:
                if isinstance(val, dict):
                    acc['vip_server'] = str(val.get('vip_server', '') or '')
                    if 'vip_place_id' in val:
                        acc['vip_place_id'] = str(val.get('vip_place_id', '') or '')
                    if 'vip_game_name' in val:
                        acc['vip_game_name'] = str(val.get('vip_game_name', '') or '')
                else:
                    acc['vip_server'] = str(val)
                changed += 1
        if changed > 0:
            txn.save()
    return jsonify({'success': True, 'changed': changed})

@app.route('/api/accounts/launch', methods=['POST'])
def launch_account():
    """Launch Roblox game with selected account and optional version"""
    try:
        req_data = request.json or {}
        username = req_data.get('username', '')
        place_id = req_data.get('placeId') or req_data.get('place_id') or ''
        server_id = req_data.get('serverId') or req_data.get('server_id') or ''
        server_mode = req_data.get('serverMode') or 'vip'
        version = req_data.get('version') or req_data.get('version_path') or None
        launch_mode = req_data.get('launchMode', 'game')

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400

        manager = get_account_manager()
        if not manager:
            return jsonify({'success': False, 'error': 'Account manager not available'}), 500

        manager.accounts = manager.load_accounts()
        if username not in manager.accounts:
            return jsonify({'success': False, 'error': f"Account '{username}' not found"}), 404

        if not manager.accounts[username].get('cookie'):
            cached_data = load_data()
            for acc in cached_data.get('accounts', []):
                if acc.get('username') == username and acc.get('cookie'):
                    manager.accounts[username]['cookie'] = acc.get('cookie')
                    break

        if not place_id and server_id and server_mode == 'vip':
            place_match = re.search(r'/games/(\d+)', server_id)
            if place_match:
                place_id = place_match.group(1)

        if server_mode == "subplace":
            p_server = ""
            j_server = ""
            if server_id:
                place_id = server_id
        else:
            p_server = "" if server_mode == "jobid" else server_id
            j_server = server_id if server_mode == "jobid" else ""

        settings = load_data().get('settings', {})
        pref_region = (
            req_data.get('preferredRegion')
            or req_data.get('preferred_region')
            or settings.get('preferredRegion')
            or settings.get('preferred_server_region')
            or ''
        )
        pref_region = str(pref_region).strip()

        server_per_acc = bool(
            req_data.get('serverPerAccount')
            if 'serverPerAccount' in req_data
            else (
                req_data.get('pick_server_per_account')
                if 'pick_server_per_account' in req_data
                else (
                    settings.get('serverPerAccount')
                    if 'serverPerAccount' in settings
                    else settings.get('pick_server_per_account', False)
                )
            )
        )

        if (pref_region or server_per_acc) and place_id and not p_server and not j_server and launch_mode == 'game':
            try:
                acc_cookie = manager.accounts[username].get('cookie', '')
                pool_key = f"{place_id}_{pref_region}_{server_per_acc}"
                now = time.time()
                candidates = []
                with server_job_pool_lock:
                    if (
                        server_job_pool_cache.get('key') == pool_key
                        and now - server_job_pool_cache.get('timestamp', 0) < 60
                        and server_job_pool_cache.get('jobs')
                    ):
                        candidates = server_job_pool_cache['jobs']
                    else:
                        candidates = RobloxAPI.get_public_server_job_candidates(
                            place_id=place_id,
                            max_pages=3,
                            preferred_region=pref_region,
                            roblosecurity_cookie=acc_cookie
                        ) or []
                        server_job_pool_cache['key'] = pool_key
                        server_job_pool_cache['jobs'] = candidates
                        server_job_pool_cache['timestamp'] = now

                    if candidates:
                        j_server = candidates.pop(0) if server_per_acc else candidates[0]
                        print(f"[INFO] Server selection (region='{pref_region}', per_account={server_per_acc}) assigned Job ID: {j_server}")
            except Exception as e:
                print(f"[WARNING] Server selection lookup failed: {e}")

        launched, launch_error = manager.launch_roblox(
            username=username,
            game_id=place_id,
            private_server_id=p_server,
            server_job_id=j_server,
            version=version,
            launch_mode=launch_mode,
            return_details=True
        )

        if launched:
            record_launch_event(username)
            webhook_manager.notify_launch(username, place_id=place_id, job_id=server_id)
            if auto_arranger.is_enabled():
                auto_arranger.trigger_delayed_arrange(2.5)
            if headless_manager.is_enabled():
                headless_manager.trigger_delayed_headless()
            last_launch_info[username.lower()] = {
                'place_id': place_id,
                'server_id': server_id,
                'server_mode': server_mode,
                'version': version,
                'launch_mode': launch_mode,
                'timestamp': time.time()
            }
            return jsonify({'success': True, 'message': f"Launched Roblox for @{username}"})
        return jsonify({'success': False, 'error': launch_error or "Roblox isn't installed"}), 400
    except Exception as e:
        print(f"[ERROR] Launch account failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

last_manual_kill_timestamp = 0.0
last_launch_times = {}
last_launch_info = {}

@app.route('/api/roblox/kill', methods=['POST', 'OPTIONS'])
def kill_roblox_processes():
    global last_manual_kill_timestamp
    if request.method == 'OPTIONS':
        return '', 200
    try:
        last_manual_kill_timestamp = time.time()
        killed_count = 0
        target_executables = ["RobloxPlayerBeta.exe", "RobloxPlayerLauncher.exe", "Bloxstrap.exe", "Fishstrap.exe", "Voidstrap.exe", "FrostStrap.exe", "ExploitStrap.exe"]

        if platform.system() == "Windows":
            for exe in target_executables:
                try:
                    cmd = ["taskkill", "/F", "/IM", exe, "/T"]
                    res = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if res.returncode == 0:
                        killed_count += 1
                except Exception:
                    pass
        else:
            for exe in ["RobloxPlayerBeta", "RobloxPlayer"]:
                try:
                    subprocess.run(["pkill", "-9", "-f", exe], capture_output=True)
                    killed_count += 1
                except Exception:
                    pass

        return jsonify({'success': True, 'message': 'Terminated Roblox processes', 'killed': killed_count})
    except Exception as e:
        print(f"[ERROR] Kill Roblox processes failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

@app.route('/api/roblox/versions', methods=['GET'])
def get_roblox_versions():
    """Get installed Roblox versions across all bootstrappers and standard installations"""
    try:
        settings = load_data().get('settings', {})
        custom_path = settings.get('robloxPath', '')
        versions = RobloxAPI.get_installed_versions(custom_path=custom_path)
        return jsonify({'success': True, 'versions': versions})
    except Exception as e:
        return jsonify({'success': False, 'versions': [], 'error': str(e)})

@app.route('/api/roblox/launch-app', methods=['POST', 'OPTIONS'])
def launch_roblox_app():
    """Launch Roblox application or a specific installed version directly"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        version_path = req_data.get('versionPath') or req_data.get('version_path') or ''
        version_name = req_data.get('version') or ''

        target_exe = None
        if version_path:
            norm_path = os.path.expandvars(str(version_path)).strip()
            if os.path.isdir(norm_path):
                for candidate in ['RobloxPlayerBeta.exe', 'RobloxPlayerLauncher.exe']:
                    c_path = os.path.join(norm_path, candidate)
                    if os.path.isfile(c_path):
                        target_exe = c_path
                        break
            elif os.path.isfile(norm_path):
                target_exe = norm_path

        if not target_exe and version_name:
            installed = RobloxAPI.get_installed_versions()
            for v in installed:
                if v.get('version') == version_name:
                    v_dir = v.get('path', '')
                    for candidate in ['RobloxPlayerBeta.exe', 'RobloxPlayerLauncher.exe']:
                        c_path = os.path.join(v_dir, candidate)
                        if os.path.isfile(c_path):
                            target_exe = c_path
                            break
                    if target_exe:
                        break

        if not target_exe:
            settings = load_data().get('settings', {})
            custom_path = settings.get('robloxPath', '')
            if custom_path:
                norm_c = os.path.expandvars(custom_path).strip()
                if os.path.isfile(norm_c):
                    target_exe = norm_c

        if not target_exe:
            installed = RobloxAPI.get_installed_versions()
            if installed:
                for candidate in ['RobloxPlayerBeta.exe', 'RobloxPlayerLauncher.exe']:
                    c_path = os.path.join(installed[0]['path'], candidate)
                    if os.path.isfile(c_path):
                        target_exe = c_path
                        break

        if not target_exe:
            for bootstrapper in RobloxAPI.BOOTSTRAPPER_CLIENTS:
                b_root = os.path.expandvars(bootstrapper.get('root', ''))
                b_launcher = os.path.join(b_root, bootstrapper.get('launcher', ''))
                if os.path.isfile(b_launcher):
                    target_exe = b_launcher
                    break

        creation_flags = 0
        if platform.system() == 'Windows':
            creation_flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

        if target_exe and os.path.isfile(target_exe):
            subprocess.Popen([target_exe], creationflags=creation_flags, close_fds=True if platform.system() != 'Windows' else False)
            return jsonify({'success': True, 'message': f'Launched {os.path.basename(target_exe)}'})

        if platform.system() == 'Windows':
            try:
                os.startfile('roblox://')
                return jsonify({'success': True, 'message': 'Launched Roblox via protocol handler'})
            except Exception as pe:
                return jsonify({'success': False, 'error': "Roblox isn't installed"}), 404

        return jsonify({'success': False, 'error': "Roblox isn't installed"}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/uninstall-version', methods=['POST', 'OPTIONS'])
def uninstall_roblox_version():
    """Safely uninstall / remove an installed Roblox version folder"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        import shutil
        req_data = request.json or {}
        target_path = req_data.get('path') or ''
        version_name = req_data.get('version') or ''

        if not target_path:
            return jsonify({'success': False, 'error': 'Path is required'}), 400

        norm_path = os.path.abspath(os.path.expandvars(str(target_path).strip()))
        if not os.path.isdir(norm_path):
            return jsonify({'success': False, 'error': 'Version folder not found'}), 404

        allowed_roots = [
            os.path.abspath(os.path.expandvars(r'%LOCALAPPDATA%\Roblox\Versions')),
        ]
        for b in RobloxAPI.BOOTSTRAPPER_CLIENTS:
            for v_dir in b.get('version_dirs', ('Versions',)):
                allowed_roots.append(os.path.abspath(os.path.expandvars(os.path.join(b['root'], v_dir))))
        for p in [os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)')]:
            if p:
                allowed_roots.append(os.path.abspath(os.path.join(p, 'Roblox', 'Versions')))
        try:
            for c in roblox_installer_manager.get_installed_clients():
                vp = c.get('versions_path')
                if vp:
                    allowed_roots.append(os.path.abspath(os.path.expandvars(vp)))
        except Exception:
            pass

        is_allowed = False
        for root in allowed_roots:
            try:
                if os.path.commonpath([norm_path, root]) == root and norm_path != root:
                    is_allowed = True
                    break
            except Exception:
                pass

        if not is_allowed:
            return jsonify({'success': False, 'error': 'Path is not an allowed Roblox version directory'}), 403

        shutil.rmtree(norm_path)
        return jsonify({'success': True, 'message': f'Successfully uninstalled {version_name or os.path.basename(norm_path)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/launch-home', methods=['POST'])
def launch_home_browser():
    """Launch browser logged into Roblox for account"""
    try:
        req_data = request.json or {}
        username = req_data.get('username', '')
        preferred_browser = req_data.get('preferredBrowser', 'auto')

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400

        manager = get_account_manager()
        if not manager:
            return jsonify({'success': False, 'error': 'Account manager not available'}), 500

        manager.accounts = manager.load_accounts()
        if username not in manager.accounts:
            return jsonify({'success': False, 'error': f"Account '{username}' not found"}), 404

        launched, launch_error = manager.launch_home(username, preferred_browser=preferred_browser, return_details=True)
        if launched:
            return jsonify({'success': True, 'message': f"Opened browser for @{username}"})
        return jsonify({'success': False, 'error': launch_error or "Failed to open browser"}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/validate-all', methods=['POST'])
def validate_all_accounts():
    try:
        cached_config = get_cached_encryption_config()
        is_locked_vault = (cached_config and cached_config.is_encryption_enabled()
                           and cached_config.get_encryption_method() == 'password'
                           and active_master_password is None)

        if is_locked_vault:
            data = load_data(force_reload=True)
            accounts = data['accounts']
            summary = {'total': len(accounts), 'valid': 0, 'expired': 0, 'banned': 0, 'skipped': len(accounts)}
            for acc in accounts:
                s = acc.get('status', 'valid')
                if s in summary:
                    summary[s] += 1
            return jsonify({
                'accounts': accounts,
                'summary': summary,
                'vault_locked': True,
                'message': 'Validation skipped: vault is locked. Unlock to validate accounts.'
            })

        manager = get_account_manager()
        data = load_data(force_reload=True)
        accounts = data['accounts']
        summary = {'total': len(accounts), 'valid': 0, 'expired': 0, 'banned': 0}

        def validate_single(acc):
            cookie = acc.get('cookie', '')
            username = acc.get('username', '')
            if not cookie and manager and isinstance(manager.accounts, dict) and username in manager.accounts:
                cookie = manager.accounts[username].get('cookie', '')
                if cookie:
                    acc['cookie'] = cookie
            user_id = acc.get('user_id', '')
            normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)
            existing_status = acc.get('status', 'expired') if normalized_cookie else 'expired'
            return RobloxAPI.get_account_status_and_info(
                cookie=normalized_cookie,
                username=username,
                user_id=user_id,
                existing_status=existing_status
            )

        from concurrent.futures import ThreadPoolExecutor
        max_workers = min(10, max(1, len(accounts)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(validate_single, accounts))

        with data_transaction() as txn:
            data = txn.data
            accounts_by_id = {acc.get('id'): acc for acc in data.get('accounts', []) if isinstance(acc, dict) and acc.get('id')}
            for acc, (status, found_uid, found_user, found_display, avatar_url) in zip(accounts, results):
                target = accounts_by_id.get(acc.get('id'))
                if target:
                    target['status'] = status
                    if found_uid:
                        target['user_id'] = found_uid
                    if found_user and found_user != 'Unknown':
                        target['username'] = found_user
                    if found_display:
                        target['display_name'] = found_display
                    if avatar_url:
                        target['avatar_url'] = avatar_url

                if status in summary:
                    summary[status] += 1
                else:
                    summary['expired'] += 1

            txn.save()
            return jsonify({'accounts': data['accounts'], 'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/validate', methods=['POST'])
def validate_single_account(account_id):
    try:
        cached_config = get_cached_encryption_config()
        is_locked_vault = (cached_config and cached_config.is_encryption_enabled()
                           and cached_config.get_encryption_method() == 'password'
                           and active_master_password is None)

        manager = get_account_manager()
        data = load_data(force_reload=True)
        account = next((acc for acc in data['accounts'] if acc['id'] == account_id), None)

        if not account:
            return jsonify({'error': 'Account not found'}), 404

        cookie = account.get('cookie', '')
        username = account.get('username', '')
        if not cookie and manager and isinstance(manager.accounts, dict) and username in manager.accounts:
            cookie = manager.accounts[username].get('cookie', '')
            if cookie:
                account['cookie'] = cookie
        user_id = account.get('user_id', '')
        normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)

        if not normalized_cookie and is_locked_vault:
            existing_status = account.get('status', 'expired')
            return jsonify({
                'account': account,
                'status': existing_status,
                'valid': False,
                'vault_locked': True,
                'message': 'Validation skipped: vault is locked. Unlock to validate.'
            })

        existing_status = account.get('status', 'expired') if normalized_cookie else 'expired'
        status, found_uid, found_user, found_display, avatar_url = RobloxAPI.get_account_status_and_info(
            cookie=normalized_cookie,
            username=username,
            user_id=user_id,
            existing_status=existing_status
        )

        with data_transaction() as txn:
            target = next((acc for acc in txn.data.get('accounts', []) if acc.get('id') == account_id), None)
            if not target:
                return jsonify({'error': 'Account not found'}), 404

            target['status'] = status
            if found_uid:
                target['user_id'] = found_uid
            if found_user and found_user != 'Unknown':
                target['username'] = found_user
            if found_display:
                target['display_name'] = found_display
            if avatar_url:
                target['avatar_url'] = avatar_url

            txn.save()
            return jsonify({'account': target, 'status': status, 'valid': status == 'valid'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games', methods=['GET'])
def get_games():
    data = load_data()
    return jsonify(data['games'])

@app.route('/api/games', methods=['POST'])
def create_game():
    game_data = request.json
    if not game_data or not isinstance(game_data, dict):
        return jsonify({'error': 'Invalid game data'}), 400

    with data_transaction() as txn:
        data = txn.data
        if 'games' not in data or not isinstance(data['games'], list):
            data['games'] = []

        max_id = 0
        for game in data['games']:
            game_id = game.get('id', '')
            if isinstance(game_id, str) and game_id.startswith('g'):
                try:
                    num_id = int(game_id[1:])
                    max_id = max(max_id, num_id)
                except ValueError:
                    pass

        game_data['id'] = f'g{max_id + 1}'
        data['games'].append(game_data)
        txn.save()

    return jsonify(game_data), 201

@app.route('/api/games/<string:game_id>', methods=['DELETE'])
def delete_game(game_id):
    with data_transaction() as txn:
        data = txn.data
        games = data.get('games', [])
        game = next((g for g in games if g.get('id') == game_id), None)
        if not game:
            return jsonify({'error': 'Game not found'}), 404
        games.remove(game)
        txn.save()

    return jsonify({'message': 'Game deleted'})

@app.route('/api/saved-users', methods=['GET'])
def get_saved_users():
    data = load_data()
    return jsonify(data.get('saved_users', []))

@app.route('/api/saved-users', methods=['POST'])
def create_saved_user():
    user_data = request.json or {}
    if not isinstance(user_data, dict):
        return jsonify({'error': 'Invalid user data'}), 400

    username = str(user_data.get('username', '') or '').strip().lstrip('@')
    if not username:
        return jsonify({'error': 'Username is required'}), 400

    user_id = str(user_data.get('user_id', '') or user_data.get('userId', '') or '').strip()
    display_name = str(user_data.get('display_name', '') or user_data.get('displayName', '') or '').strip()
    icon_url = str(user_data.get('icon_url', '') or user_data.get('avatar_url', '') or '').strip()

    if not user_id or not icon_url:
        try:
            if username.isdigit():
                found_id = username
            else:
                found_id = RobloxAPI.get_user_id_from_username(username)
            if found_id:
                user_id = str(found_id)
                resolved_name = RobloxAPI.get_username_from_user_id(user_id)
                if resolved_name:
                    username = resolved_name
                headshot = RobloxAPI.get_avatar_headshot_url(found_id)
                if headshot and not icon_url:
                    icon_url = headshot
        except Exception as e:
            print(f"Error fetching roblox info for saved user: {e}")

    with data_transaction() as txn:
        data = txn.data
        if 'saved_users' not in data or not isinstance(data['saved_users'], list):
            data['saved_users'] = []

        max_num = 0
        for u in data['saved_users']:
            uid_str = str(u.get('id', ''))
            if uid_str.startswith('u'):
                try:
                    max_num = max(max_num, int(uid_str[1:]))
                except ValueError:
                    pass

        record = {
            'id': f'u{max_num + 1}',
            'username': username,
            'display_name': display_name or username,
            'user_id': user_id,
            'icon_url': icon_url
        }

        data['saved_users'].append(record)
        txn.save()

    return jsonify(record), 201

@app.route('/api/saved-users/<string:user_id>', methods=['DELETE'])
def delete_saved_user(user_id):
    with data_transaction() as txn:
        data = txn.data
        saved = data.get('saved_users', [])
        item = next((u for u in saved if str(u.get('id')) == str(user_id) or str(u.get('user_id')) == str(user_id) or str(u.get('username')).lower() == str(user_id).lower()), None)
        if not item:
            return jsonify({'error': 'Saved user not found'}), 404
        saved.remove(item)
        txn.save()

    return jsonify({'message': 'Saved user deleted', 'success': True})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    data = load_data()
    return jsonify(data['settings'])

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    settings_data = request.json or {}
    with data_transaction() as txn:
        if 'settings' not in txn.data or not isinstance(txn.data['settings'], dict):
            txn.data['settings'] = {}
        for key, value in settings_data.items():
            txn.data['settings'][key] = value
        txn.save()
        result_settings = txn.data['settings']
    return jsonify(result_settings)

def bloxgen_api_request(endpoint, method='GET', params=None, body_data=None):
    base_url = 'https://core.bloxgen.net'
    url = f"{base_url}{endpoint}"
    if params:
        filtered_params = {k: v for k, v in params.items() if v is not None}
        if filtered_params:
            query_string = urllib.parse.urlencode(filtered_params)
            url = f"{url}?{query_string}"
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'ForkedRobloxAccountManager/3.0'
    }
    
    data_bytes = None
    if body_data is not None:
        data_bytes = json.dumps(body_data).encode('utf-8')
        
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_body = resp.read().decode('utf-8')
            return json.loads(resp_body), resp.status
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8')
            return json.loads(err_body), e.code
        except Exception:
            return {'success': False, 'message': f'HTTP Error {e.code}'}, e.code
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/bloxgen/balance', methods=['GET'])
def bloxgen_get_balance():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/balance', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/prices', methods=['GET'])
def bloxgen_get_prices():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/prices', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/daily-limit', methods=['GET'])
def bloxgen_get_daily_limit():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/daily-limit', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/stock', methods=['GET'])
def bloxgen_get_stock():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/stock', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/generate', methods=['POST'])
def bloxgen_generate():
    body = request.json or {}
    res_data, status_code = bloxgen_api_request('/api/generate', method='POST', body_data=body)
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/checker/single', methods=['POST'])
def bloxgen_check_single():
    body = request.json or {}
    res_data, status_code = bloxgen_api_request('/api/checker/single', method='POST', body_data=body)
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/checker/access', methods=['GET'])
def bloxgen_checker_access():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/checker/access', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/botting/status', methods=['GET'])
def bloxgen_botting_status():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/botting/status', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/botting/pricing', methods=['GET'])
def bloxgen_botting_pricing():
    api_key = request.args.get('apiKey', '')
    res_data, status_code = bloxgen_api_request('/api/botting/pricing', params={'apiKey': api_key})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/botting/check', methods=['GET'])
def bloxgen_botting_check():
    api_key = request.args.get('apiKey', '')
    account = request.args.get('account', '')
    res_data, status_code = bloxgen_api_request('/api/botting/check', params={'apiKey': api_key, 'account': account})
    return jsonify(res_data), status_code

@app.route('/api/bloxgen/botting/create', methods=['POST'])
def bloxgen_botting_create():
    body = request.json or {}
    res_data, status_code = bloxgen_api_request('/api/botting/create', method='POST', body_data=body)
    return jsonify(res_data), status_code

@app.route('/api/multi-instance/status', methods=['GET'])
def get_multi_instance_status():
    """Get current multi-instance status"""
    data = load_data()
    enabled = data['settings'].get('multiInstance', False)
    return jsonify({
        'success': True,
        'enabled': enabled,
        'active': len(multi_instance_controller.mutex_handles) > 0
    })

@app.route('/api/multi-instance/toggle', methods=['POST'])
def toggle_multi_instance():
    """Toggle multi-instance state and persist setting"""
    req_data = request.json or {}
    new_state = req_data.get('enabled')
    with data_transaction() as txn:
        data = txn.data
        if 'settings' not in data or not isinstance(data['settings'], dict):
            data['settings'] = {}
        if new_state is None:
            new_state = not data['settings'].get('multiInstance', False)

        data['settings']['multiInstance'] = bool(new_state)
        multi_instance_controller.sync_state(data['settings']['multiInstance'])
        txn.save()

    return jsonify({
        'success': True,
        'enabled': new_state,
        'active': len(multi_instance_controller.mutex_handles) > 0,
        'message': f"Multi-instance {'enabled' if new_state else 'disabled'}"
    })

@app.route('/api/headless/status', methods=['GET'])
def get_headless_status():
    data = load_data()
    enabled = data.get('settings', {}).get('headlessMode', False)
    pids = list(headless_manager.get_roblox_pids())
    return jsonify({
        'success': True,
        'enabled': bool(enabled),
        'active': headless_manager.watchdog_running,
        'pids': pids,
        'pid_count': len(pids),
        'hidden_count': len(headless_manager.hidden_hwnds)
    })

@app.route('/api/headless/toggle', methods=['POST', 'OPTIONS'])
def toggle_headless_mode():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        new_state = req_data.get('enabled')
        with data_transaction() as txn:
            data = txn.data
            if 'settings' not in data or not isinstance(data['settings'], dict):
                data['settings'] = {}
            if new_state is None:
                new_state = not data['settings'].get('headlessMode', False)

            data['settings']['headlessMode'] = bool(new_state)
            txn.save()

        if new_state:
            headless_manager.trigger_delayed_headless([0.5, 2.0])
        else:
            headless_manager.restore_all_windows()

        return jsonify({
            'success': True,
            'enabled': data['settings']['headlessMode'],
            'message': f"Headless mode {'enabled' if data['settings']['headlessMode'] else 'disabled'}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/headless/apply', methods=['POST', 'OPTIONS'])
def apply_headless_now():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        res = headless_manager.apply_pass(force_trim=True)
        return jsonify({
            'success': True,
            'pids': res.get('pids', 0),
            'hidden': res.get('hidden', 0),
            'priority': res.get('priority', 0),
            'trimmed': res.get('trimmed', 0),
            'message': f"Applied headless mode: hidden {res.get('hidden', 0)} window(s), trimmed {res.get('trimmed', 0)} process(es)"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/headless/restore', methods=['POST', 'OPTIONS'])
def restore_headless_windows():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        res = headless_manager.restore_all_windows()
        return jsonify({
            'success': True,
            'restored': res.get('restored', 0),
            'priority': res.get('priority', 0),
            'message': f"Restored {res.get('restored', 0)} Roblox window(s) to visible state"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/anti-afk/status', methods=['GET', 'OPTIONS'])
def get_anti_afk_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify(anti_afk_manager.get_status())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/anti-afk/settings', methods=['POST', 'OPTIONS'])
def update_anti_afk_settings():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        with data_transaction() as txn:
            data = txn.data
            if 'settings' not in data or not isinstance(data['settings'], dict):
                data['settings'] = {}
            settings = data['settings']
            if 'antiAfkEnabled' in req_data:
                settings['antiAfkEnabled'] = bool(req_data['antiAfkEnabled'])
            if 'antiAfkIntervalMinutes' in req_data:
                try:
                    settings['antiAfkIntervalMinutes'] = max(1, min(19, int(req_data['antiAfkIntervalMinutes'])))
                except (TypeError, ValueError):
                    pass
            if 'antiAfkKeyName' in req_data:
                settings['antiAfkKeyName'] = str(req_data['antiAfkKeyName'])
            if 'antiAfkShowNextLabel' in req_data:
                settings['antiAfkShowNextLabel'] = bool(req_data['antiAfkShowNextLabel'])
            txn.save()
        anti_afk_manager.sync_overlay()
        return jsonify(anti_afk_manager.get_status())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/anti-afk/trigger', methods=['POST', 'OPTIONS'])
def trigger_anti_afk_pass():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        res = anti_afk_manager.trigger_pass()
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/extensions', methods=['GET', 'OPTIONS'])
def get_browser_extensions():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        exts = extension_manager.list_extensions()
        res = []
        for ext in exts:
            res.append({
                'key': ext.key,
                'name': ext.name,
                'source': ext.source,
                'display_source': ext.display_source,
                'extension_id': ext.extension_id,
                'folder_name': ext.folder_name,
                'enabled': ext.enabled,
                'installed_at': ext.installed_at,
                'directory': str(ext.directory),
                'manifest_version': ext.manifest_version
            })
        return jsonify({'success': True, 'extensions': res})
    except Exception as e:
        log_detailed_error("Failed to list browser extensions", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/extensions/toggle', methods=['POST', 'OPTIONS'])
def toggle_browser_extension():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        key = str(data.get('key') or '').strip()
        enabled = bool(data.get('enabled', True))
        if not key:
            return jsonify({'success': False, 'error': 'Extension key is required'}), 400
        extension_manager.set_extension_enabled(key, enabled)
        return jsonify({'success': True, 'key': key, 'enabled': enabled})
    except BrowserExtensionError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log_detailed_error("Failed to toggle browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/extensions/delete', methods=['POST', 'OPTIONS'])
def delete_browser_extension():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        key = str(data.get('key') or '').strip()
        if not key:
            return jsonify({'success': False, 'error': 'Extension key is required'}), 400
        extension_manager.remove_extension(key)
        return jsonify({'success': True, 'key': key})
    except BrowserExtensionError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log_detailed_error("Failed to delete browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/extensions/add', methods=['POST', 'OPTIONS'])
def add_browser_extension():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        source = str(data.get('source') or '').strip().lower()
        path_or_id = str(data.get('path_or_id') or '').strip()
        if not source or not path_or_id:
            return jsonify({'success': False, 'error': 'Source and target path or ID are required'}), 400

        if source in ('web_store', 'chrome'):
            ext = extension_manager.add_from_extension_id(path_or_id)
        elif source in ('firefox', 'firefox_addons'):
            ext = extension_manager.add_from_firefox_addon(path_or_id)
        elif source == 'unpacked':
            ext = extension_manager.add_from_unpacked(path_or_id)
        elif source == 'crx':
            ext = extension_manager.add_from_crx(path_or_id)
        elif source == 'xpi':
            ext = extension_manager.add_from_xpi(path_or_id)
        else:
            return jsonify({'success': False, 'error': f'Unsupported extension source: {source}'}), 400

        return jsonify({
            'success': True,
            'extension': {
                'key': ext.key,
                'name': ext.name,
                'source': ext.source,
                'display_source': ext.display_source,
                'extension_id': ext.extension_id,
                'folder_name': ext.folder_name,
                'enabled': ext.enabled,
                'installed_at': ext.installed_at,
                'directory': str(ext.directory),
                'manifest_version': ext.manifest_version
            }
        })
    except BrowserExtensionError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log_detailed_error("Failed to add browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/extensions/browse-folder', methods=['POST', 'GET', 'OPTIONS'])
def browse_extension_folder_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_selected = filedialog.askdirectory(title="Select Unpacked Extension Folder")
        root.destroy()
        if folder_selected:
            return jsonify({'success': True, 'path': folder_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        return jsonify({'success': False, 'cancelled': True, 'error': str(e)}), 200

@app.route('/api/extensions/browse-file', methods=['POST', 'GET', 'OPTIONS'])
def browse_extension_file_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        file_type = str(data.get('file_type') or 'any').lower()
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if file_type == 'crx':
            filetypes = [("Chrome Extension (*.crx)", "*.crx"), ("All Files", "*.*")]
        elif file_type == 'xpi':
            filetypes = [("Firefox Add-on (*.xpi)", "*.xpi"), ("All Files", "*.*")]
        else:
            filetypes = [("Extension Packages (*.crx;*.xpi)", "*.crx;*.xpi"), ("All Files", "*.*")]
        file_selected = filedialog.askopenfilename(title="Select Extension File", filetypes=filetypes)
        root.destroy()
        if file_selected:
            return jsonify({'success': True, 'path': file_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        return jsonify({'success': False, 'cancelled': True, 'error': str(e)}), 200

recent_launches = []

def record_launch_event(username):
    global recent_launches, last_launch_times
    now = time.time()
    recent_launches.append({'username': username, 'timestamp': now})
    recent_launches = [l for l in recent_launches if now - l['timestamp'] < 180]
    if username:
        last_launch_times[username.lower()] = now

def get_currently_running_usernames():
    running = set()
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                pname = str(proc.info.get('name') or '')
                if 'robloxplayerbeta' not in pname.lower():
                    continue
                pid = proc.info['pid']
                creation_time_sec = proc.info.get('create_time') or None
                acc_info = resolve_pid_account(pid, creation_time_sec)
                if acc_info and acc_info.get("username"):
                    running.add(acc_info["username"].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return running

def background_auto_rejoin_worker():
    global last_manual_kill_timestamp, last_launch_times, last_launch_info
    while True:
        try:
            time.sleep(15)
            now = time.time()
            if now - last_manual_kill_timestamp < 45:
                continue

            data = load_data()
            settings = data.get('settings', {})
            global_auto = bool(settings.get('autoRejoinEnabled', False))

            accounts = data.get('accounts', [])
            rejoin_candidates = [a for a in accounts if (a.get('auto_rejoin_enabled') or global_auto) and a.get('username')]

            if not rejoin_candidates:
                continue

            manager = get_account_manager()
            if not manager:
                continue

            delay = int(settings.get('autoRejoinDelaySeconds', 5) or 5)
            headless = bool(settings.get('headlessMode', False))
            behavior = str(settings.get('autoRejoinLaunchBehavior', 'rejoin_same_server'))
            multi_instance = bool(settings.get('multiInstance', False))

            running_usernames = get_currently_running_usernames()

            if not multi_instance and len(running_usernames) > 0:
                continue

            latest_candidate = None
            latest_time = 0
            if not multi_instance:
                for acc in rejoin_candidates:
                    uname = acc.get('username', '')
                    uname_lower = uname.lower()
                    if not uname:
                        continue
                    info = last_launch_info.get(uname_lower)
                    if info and info['timestamp'] > latest_time:
                        latest_time = info['timestamp']
                        latest_candidate = uname_lower

            for acc in rejoin_candidates:
                uname = acc.get('username', '')
                uname_lower = uname.lower()
                if not uname:
                    continue

                if not multi_instance and uname_lower != latest_candidate:
                    continue

                info = last_launch_info.get(uname_lower)
                if not info:
                    continue

                last_l = info['timestamp']
                if (now - last_l) < (30 + delay):
                    continue

                if uname_lower in running_usernames:
                    continue

                if manager and getattr(manager, 'auto_rejoin_monitor', None):
                    active_sess = getattr(manager.auto_rejoin_monitor, 'active_sessions', {}).get(uname)
                    if active_sess and getattr(active_sess, 'rejoin_in_progress', False):
                        continue

                place_id = info.get('place_id', '')
                server_id = info.get('server_id', '')
                server_mode = info.get('server_mode', 'vip')
                version = info.get('version')
                launch_mode = info.get('launch_mode', 'game')

                p_server = acc.get('vip_server', '') if behavior == 'rejoin_same_server' else ''
                if not p_server and server_mode != 'jobid':
                    p_server = server_id

                j_server = server_id if server_mode == "jobid" else ""

                try:
                    launched = manager.launch_roblox(
                        username=uname,
                        game_id=place_id,
                        private_server_id=p_server,
                        server_job_id=j_server,
                        version=version,
                        launch_mode=launch_mode
                    )
                    if launched:
                        info['timestamp'] = time.time()
                        last_launch_times[uname_lower] = time.time()
                        webhook_manager.notify_rejoin(uname, place_id or "Home", reason="Client process disconnected")
                    time.sleep(delay)
                except Exception as e:
                    print(f"[ERROR] Auto-rejoin launch failed for {uname}: {e}")
        except Exception as e:
            print(f"[ERROR] background_auto_rejoin_worker error: {e}")

threading.Thread(target=background_auto_rejoin_worker, daemon=True).start()

group_auto_relaunch_state = {
    'next_run_ts': None,
    'last_run_ts': None,
    'in_progress': False,
    'last_relaunch_summary': None
}
group_auto_relaunch_lock = threading.Lock()

def run_group_auto_relaunch():
    with group_auto_relaunch_lock:
        if group_auto_relaunch_state['in_progress']:
            return
        group_auto_relaunch_state['in_progress'] = True

    try:
        data = load_data()
        settings = data.get('settings', {})
        enabled = bool(settings.get('auto_relaunch_enabled', settings.get('autoRelaunchEnabled', False)))
        group = str(settings.get('auto_relaunch_group', settings.get('autoRelaunchGroup', ''))).strip()
        interval_min = max(1, int(settings.get('auto_relaunch_interval_minutes', settings.get('autoRelaunchIntervalMinutes', 60)) or 60))
        
        now = time.time()
        group_auto_relaunch_state['next_run_ts'] = now + (interval_min * 60)
        group_auto_relaunch_state['last_run_ts'] = now

        if not enabled or not group:
            return

        manager = get_account_manager()
        if not manager:
            return

        matching_accounts = [
            acc for acc in data.get('accounts', [])
            if str(acc.get('group', '')).strip().lower() == group.lower()
        ]
        if not matching_accounts:
            return

        monitor = getattr(manager, 'auto_rejoin_monitor', None)
        for acc in matching_accounts:
            uname = acc.get('username', '')
            if monitor is not None and uname:
                try:
                    monitor.mark_intentionally_stopped(username=uname)
                except Exception:
                    pass

        delay = float(settings.get('multiLaunchDelay', 1000)) / 1000.0
        success_count = 0

        for acc in matching_accounts:
            uname = acc.get('username')
            if not uname:
                continue
            
            uname_lower = uname.lower()
            launch_info = last_launch_info.get(uname_lower, {})
            place_id = launch_info.get('place_id') or acc.get('place_id') or ''
            vip_server = launch_info.get('server_id') or acc.get('vip_server') or ''
            server_mode = launch_info.get('server_mode', 'vip')
            job_id = vip_server if server_mode == 'jobid' else ''
            p_server = vip_server if server_mode != 'jobid' else ''
            version = launch_info.get('version') or acc.get('roblox_version') or 'auto'

            try:
                launched = manager.launch_roblox(
                    username=uname,
                    game_id=place_id,
                    private_server_id=p_server,
                    server_job_id=job_id,
                    version=version,
                    launch_mode='game' if place_id else 'app'
                )
                if launched:
                    success_count += 1
                    last_launch_times[uname_lower] = time.time()
                    last_launch_info[uname_lower] = {
                        'timestamp': time.time(),
                        'place_id': place_id,
                        'server_id': vip_server,
                        'server_mode': server_mode,
                        'version': version,
                        'launch_mode': 'game' if place_id else 'app'
                    }
                time.sleep(delay)
            except Exception as e:
                print(f"[ERROR] Group auto-relaunch failed for {uname}: {e}")

        summary = f"Relaunched {success_count}/{len(matching_accounts)} accounts in group '{group}'"
        group_auto_relaunch_state['last_relaunch_summary'] = summary
        print(f"[INFO] Group auto-relaunch completed: {summary}")
    finally:
        with group_auto_relaunch_lock:
            group_auto_relaunch_state['in_progress'] = False

def background_group_auto_relaunch_worker():
    while True:
        try:
            time.sleep(5)
            data = load_data()
            settings = data.get('settings', {})
            enabled = bool(settings.get('auto_relaunch_enabled', settings.get('autoRelaunchEnabled', False)))
            group = str(settings.get('auto_relaunch_group', settings.get('autoRelaunchGroup', ''))).strip()
            interval_min = max(1, int(settings.get('auto_relaunch_interval_minutes', settings.get('autoRelaunchIntervalMinutes', 60)) or 60))

            if not enabled or not group:
                with group_auto_relaunch_lock:
                    group_auto_relaunch_state['next_run_ts'] = None
                continue

            now = time.time()
            if group_auto_relaunch_state['next_run_ts'] is None:
                with group_auto_relaunch_lock:
                    group_auto_relaunch_state['next_run_ts'] = now + (interval_min * 60)

            if now >= group_auto_relaunch_state['next_run_ts']:
                run_group_auto_relaunch()
        except Exception as e:
            print(f"[ERROR] background_group_auto_relaunch_worker: {e}")
            time.sleep(10)

threading.Thread(target=background_group_auto_relaunch_worker, daemon=True).start()

@app.route('/api/auto-relaunch/status', methods=['GET', 'OPTIONS'])
def get_auto_relaunch_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = load_data()
        settings = data.get('settings', {})
        enabled = bool(settings.get('auto_relaunch_enabled', settings.get('autoRelaunchEnabled', False)))
        group = str(settings.get('auto_relaunch_group', settings.get('autoRelaunchGroup', ''))).strip()
        interval_min = max(1, int(settings.get('auto_relaunch_interval_minutes', settings.get('autoRelaunchIntervalMinutes', 60)) or 60))
        now = time.time()
        next_ts = group_auto_relaunch_state.get('next_run_ts')
        rem = max(0, int(next_ts - now)) if (enabled and next_ts) else 0

        matching = [
            acc.get('username') for acc in data.get('accounts', [])
            if group and str(acc.get('group', '')).strip().lower() == group.lower()
        ]

        return jsonify({
            'success': True,
            'enabled': enabled,
            'interval_minutes': interval_min,
            'group': group,
            'accounts_in_group': len(matching),
            'next_run_ts': next_ts,
            'last_run_ts': group_auto_relaunch_state.get('last_run_ts'),
            'seconds_until_next_run': rem,
            'in_progress': group_auto_relaunch_state.get('in_progress', False),
            'last_summary': group_auto_relaunch_state.get('last_relaunch_summary')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-relaunch/settings', methods=['POST', 'OPTIONS'])
def update_auto_relaunch_settings():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        with data_transaction() as txn:
            data = txn.data
            if 'settings' not in data or not isinstance(data['settings'], dict):
                data['settings'] = {}
            settings = data['settings']
            if 'auto_relaunch_enabled' in req_data or 'autoRelaunchEnabled' in req_data:
                val = bool(req_data.get('auto_relaunch_enabled', req_data.get('autoRelaunchEnabled')))
                settings['auto_relaunch_enabled'] = val
                settings['autoRelaunchEnabled'] = val
            if 'auto_relaunch_interval_minutes' in req_data or 'autoRelaunchIntervalMinutes' in req_data:
                val = max(1, int(req_data.get('auto_relaunch_interval_minutes', req_data.get('autoRelaunchIntervalMinutes', 60))))
                settings['auto_relaunch_interval_minutes'] = val
                settings['autoRelaunchIntervalMinutes'] = val
            if 'auto_relaunch_group' in req_data or 'autoRelaunchGroup' in req_data:
                val = str(req_data.get('auto_relaunch_group', req_data.get('autoRelaunchGroup', ''))).strip()
                settings['auto_relaunch_group'] = val
                settings['autoRelaunchGroup'] = val
            txn.save()

        with group_auto_relaunch_lock:
            interval_min = max(1, int(settings.get('auto_relaunch_interval_minutes', 60)))
            group_auto_relaunch_state['next_run_ts'] = time.time() + (interval_min * 60)
        return get_auto_relaunch_status()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-relaunch/trigger', methods=['POST', 'OPTIONS'])
def trigger_auto_relaunch_now():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        threading.Thread(target=run_group_auto_relaunch, daemon=True).start()
        return jsonify({'success': True, 'message': 'Group auto-relaunch triggered.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

_PID_INFO_CACHE = {}
_PID_INFO_CACHE_LOCK = threading.Lock()

def resolve_pid_place_id(pid: int, acc_info: dict = None) -> str:
    if acc_info and acc_info.get('place_id'):
        return str(acc_info['place_id'])
    if acc_info and acc_info.get('username'):
        uname_key = acc_info['username'].lower()
        info = last_launch_info.get(uname_key)
        if info and info.get('place_id'):
            return str(info['place_id'])
    for uname_key, info in last_launch_info.items():
        if info.get('pid') == pid and info.get('place_id'):
            return str(info['place_id'])
    return ""

def resolve_pid_account(pid, creation_time_sec=None, accounts_by_user=None, accounts_by_id=None):
    with _PID_INFO_CACHE_LOCK:
        if pid in _PID_INFO_CACHE:
            cached_data, cached_ctime = _PID_INFO_CACHE[pid]
            if creation_time_sec is None or cached_ctime is None or abs(creation_time_sec - cached_ctime) < 5.0:
                return cached_data

    if accounts_by_user is None or accounts_by_id is None:
        manager = get_account_manager()
        accounts_by_user = {}
        accounts_by_id = {}
        if manager and hasattr(manager, 'accounts') and isinstance(manager.accounts, dict):
            for uname, acc in manager.accounts.items():
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc
        
        app_data = load_data()
        for acc in app_data.get('accounts', []):
            uname = acc.get('username', '')
            if uname:
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc

    resolved_result = None

    for uname_key, info in last_launch_info.items():
        if info.get('pid') == pid:
            acc = accounts_by_user.get(uname_key)
            resolved_result = {
                'username': acc.get('username') if acc else uname_key,
                'display_name': acc.get('display_name') if acc else uname_key,
                'avatar_url': acc.get('avatar_url') if acc else None,
                'user_id': acc.get('user_id') if acc else None,
                'place_id': info.get('place_id') or ''
            }
            break

    if not resolved_result:
        manager = get_account_manager()
        if manager and hasattr(manager, 'auto_rejoin_monitor') and manager.auto_rejoin_monitor:
            monitor = manager.auto_rejoin_monitor
            sessions = getattr(monitor, 'sessions', {})
            for uname, session in sessions.items():
                if int(getattr(session, 'pid', 0) or 0) == pid:
                    acc = accounts_by_user.get(uname.lower())
                    session_place = getattr(session, 'place_id', '') or last_launch_info.get(uname.lower(), {}).get('place_id', '')
                    resolved_result = {
                        'username': uname,
                        'display_name': acc.get('display_name') if acc else uname,
                        'avatar_url': acc.get('avatar_url') if acc else None,
                        'user_id': acc.get('user_id') if acc else None,
                        'place_id': session_place or ''
                    }
                    break

    if not resolved_result:
        try:
            logs_dir = os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "Roblox", "logs")
            if os.path.isdir(logs_dir):
                entries = [os.path.join(logs_dir, n) for n in os.listdir(logs_dir) if n.lower().endswith(".log")]
                entries.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                for log_path in entries[:10]:
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(50000)
                            if str(pid) in content:
                                uid_match = re.search(r"userid:(\d+)", content, re.IGNORECASE)
                                place_match = re.search(r'(?:placeid|place_id|placeId)[:=\s"]+(\d{4,16})', content, re.IGNORECASE)
                                log_place = place_match.group(1) if place_match else ''
                                if uid_match and uid_match.group(1) in accounts_by_id:
                                    acc = accounts_by_id[uid_match.group(1)]
                                    uname_key = acc.get('username', '').lower()
                                    if uname_key in last_launch_info:
                                        last_launch_info[uname_key]['pid'] = pid
                                        if not log_place:
                                            log_place = last_launch_info[uname_key].get('place_id', '')
                                    resolved_result = {
                                        'username': acc.get('username'),
                                        'display_name': acc.get('display_name') or acc.get('username'),
                                        'avatar_url': acc.get('avatar_url'),
                                        'user_id': acc.get('user_id'),
                                        'place_id': log_place or ''
                                    }
                                    break
                    except Exception:
                        pass
        except Exception:
            pass

    if not resolved_result and creation_time_sec:
        best_match = None
        min_diff = 20.0
        for l in recent_launches:
            diff = abs(creation_time_sec - l['timestamp'])
            if diff < min_diff:
                min_diff = diff
                best_match = l['username']
        if best_match:
            acc = accounts_by_user.get(best_match.lower())
            best_place = ''
            if best_match.lower() in last_launch_info:
                last_launch_info[best_match.lower()]['pid'] = pid
                best_place = last_launch_info[best_match.lower()].get('place_id', '')
            manager = get_account_manager()
            if manager and hasattr(manager, 'update_active_session_pid'):
                try:
                    manager.update_active_session_pid(best_match, pid)
                except Exception:
                    pass
            resolved_result = {
                'username': best_match,
                'display_name': acc.get('display_name') if acc else best_match,
                'avatar_url': acc.get('avatar_url') if acc else None,
                'user_id': acc.get('user_id') if acc else None,
                'place_id': best_place or ''
            }

    with _PID_INFO_CACHE_LOCK:
        _PID_INFO_CACHE[pid] = (resolved_result, creation_time_sec)

    return resolved_result

_INSTANCES_CACHE: Optional[Dict[str, Any]] = None
_INSTANCES_CACHE_TIME: float = 0.0
_INSTANCES_CACHE_TTL: float = 1.5
_INSTANCES_CACHE_LOCK = threading.Lock()

@app.route('/api/instances', methods=['GET'])
def get_running_instances():
    """List running Roblox processes, separating actual game clients from crash handlers"""
    global _INSTANCES_CACHE, _INSTANCES_CACHE_TIME
    now = time.time()
    with _INSTANCES_CACHE_LOCK:
        if _INSTANCES_CACHE is not None and (now - _INSTANCES_CACHE_TIME) < _INSTANCES_CACHE_TTL:
            import copy
            return jsonify(copy.deepcopy(_INSTANCES_CACHE))

    try:
        app_data = load_data()
        app_settings = app_data.get('settings', {})

        accounts_by_user = {}
        accounts_by_id = {}
        manager = get_account_manager()
        if manager and hasattr(manager, 'accounts') and isinstance(manager.accounts, dict):
            for uname, acc in manager.accounts.items():
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc

        for acc in app_data.get('accounts', []):
            uname = acc.get('username', '')
            if uname:
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc

        game_instances = []
        crash_handlers = []
        other_instances = []
        if platform.system() == "Windows":
            target_keywords = ('roblox', 'bloxstrap', 'fishstrap', 'voidstrap', 'froststrap', 'exploitstrap')
            procs_data = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
                    try:
                        pname = str(proc.info.get('name') or '')
                        if any(k in pname.lower() for k in target_keywords):
                            mem_info = proc.info.get('memory_info')
                            working_set = mem_info.rss if mem_info else 0
                            create_time = proc.info.get('create_time') or 0.0
                            procs_data.append({
                                'ProcessId': proc.info['pid'],
                                'Name': pname,
                                'WorkingSetSize': working_set,
                                'CreationTimeSec': create_time
                            })
                    except Exception:
                        continue
            except Exception:
                procs_data = []

            if not procs_data:
                ps_script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'Roblox|Bloxstrap|Fishstrap|Voidstrap|FrostStrap|ExploitStrap' } | Select-Object ProcessId, Name, WorkingSetSize, CreationDate | ConvertTo-Json -Compress"
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if res.returncode == 0 and res.stdout.strip():
                    try:
                        raw_json = json.loads(res.stdout.strip())
                        if isinstance(raw_json, dict):
                            raw_json = [raw_json]
                        for item in raw_json:
                            creation_date = item.get("CreationDate") or ""
                            creation_time_sec = None
                            if creation_date and isinstance(creation_date, str) and '/Date(' in creation_date:
                                try:
                                    ms_str = re.search(r'/Date\((\d+)', creation_date).group(1)
                                    creation_time_sec = float(ms_str) / 1000.0
                                except Exception:
                                    pass
                            procs_data.append({
                                'ProcessId': int(item.get("ProcessId")),
                                'Name': str(item.get("Name") or ""),
                                'WorkingSetSize': int(item.get("WorkingSetSize") or 0),
                                'CreationTimeSec': creation_time_sec
                            })
                    except Exception:
                        pass

            for item in procs_data:
                pid = item['ProcessId']
                pname = item['Name']
                working_set = item['WorkingSetSize']
                creation_time_sec = item.get('CreationTimeSec')
                memory_mb = round(working_set / (1024 * 1024), 1)

                inst_obj = {
                    "pid": pid,
                    "name": pname,
                    "status": "Running",
                    "memory_mb": memory_mb,
                    "created_at": str(creation_time_sec or "")
                }

                cpu_percent = 0.0
                try:
                    with pid_cpu_trackers_lock:
                        if pid not in pid_cpu_trackers:
                            p = psutil.Process(pid)
                            p.cpu_percent(interval=None)
                            pid_cpu_trackers[pid] = p
                        else:
                            p = pid_cpu_trackers[pid]
                            if p.is_running():
                                raw_cpu = p.cpu_percent(interval=None)
                                cpu_percent = round(raw_cpu / max(1, psutil.cpu_count()), 1)
                            else:
                                del pid_cpu_trackers[pid]
                except Exception:
                    with pid_cpu_trackers_lock:
                        pid_cpu_trackers.pop(pid, None)

                inst_obj["cpu_percent"] = cpu_percent

                if re.search(r'crashhandler', pname, re.IGNORECASE):
                    inst_obj["process_type"] = "crash_handler"
                    crash_handlers.append(inst_obj)
                elif re.search(r'robloxplayerbeta', pname, re.IGNORECASE):
                    inst_obj["process_type"] = "game"
                    acc_info = resolve_pid_account(pid, creation_time_sec, accounts_by_user, accounts_by_id)
                    if acc_info:
                        inst_obj["username"] = acc_info.get("username")
                        inst_obj["display_name"] = acc_info.get("display_name")
                        inst_obj["avatar_url"] = acc_info.get("avatar_url")
                        inst_obj["user_id"] = acc_info.get("user_id")
                        if acc_info.get("place_id"):
                            inst_obj["place_id"] = str(acc_info.get("place_id"))

                    if not inst_obj.get("place_id"):
                        resolved_place = resolve_pid_place_id(pid, acc_info)
                        if resolved_place:
                            inst_obj["place_id"] = str(resolved_place)

                    game_instances.append(inst_obj)
                else:
                    inst_obj["process_type"] = "bootstrapper"
                    other_instances.append(inst_obj)

        active_pids = {inst["pid"] for inst in game_instances + crash_handlers + other_instances}
        with pid_cpu_trackers_lock:
            for tracked_pid in list(pid_cpu_trackers.keys()):
                if tracked_pid not in active_pids:
                    pid_cpu_trackers.pop(tracked_pid, None)

        with _PID_INFO_CACHE_LOCK:
            for cached_pid in list(_PID_INFO_CACHE.keys()):
                if cached_pid not in active_pids:
                    _PID_INFO_CACHE.pop(cached_pid, None)

        total_roblox_cpu = round(sum(inst.get("cpu_percent", 0.0) for inst in game_instances + crash_handlers + other_instances), 1)
        system_cpu = 0.0
        try:
            system_cpu = round(psutil.cpu_percent(interval=None), 1)
        except Exception:
            pass

        result_payload = {
            'success': True,
            'instances': game_instances,
            'crashHandlers': crash_handlers,
            'otherInstances': other_instances,
            'count': len(game_instances),
            'crashHandlerCount': len(crash_handlers),
            'totalCpuPercent': total_roblox_cpu,
            'systemCpuPercent': system_cpu,
            'multiInstanceEnabled': app_settings.get('multiInstance', False),
            'autoTrimEnabled': app_settings.get('autoMemoryTrimEnabled', False),
            'autoTrimInterval': app_settings.get('autoMemoryTrimIntervalMinutes', 5),
            'mutexActive': len(multi_instance_controller.mutex_handles) > 0
        }
        with _INSTANCES_CACHE_LOCK:
            _INSTANCES_CACHE = result_payload
            _INSTANCES_CACHE_TIME = time.time()

        return jsonify(result_payload)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_ulong),
        ('PageFaultCount', ctypes.c_ulong),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]

def trim_process_working_set(pid: int):
    if platform.system() != "Windows" or not pid:
        return False, 0, 0
    try:
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p

        kernel32.SetProcessWorkingSetSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
        kernel32.SetProcessWorkingSetSize.restype = ctypes.c_bool

        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        psapi.EmptyWorkingSet.restype = ctypes.c_bool

        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_bool

        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool

        access = 0x0100 | 0x0400 | 0x0008 | 0x0010 | 0x1000 | 0x0200
        handle = kernel32.OpenProcess(access, False, int(pid))
        if not handle:
            return False, 0, 0

        pmc_before = PROCESS_MEMORY_COUNTERS()
        pmc_before.cb = ctypes.sizeof(pmc_before)
        ok_before = psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc_before), ctypes.sizeof(pmc_before))
        before_bytes = pmc_before.WorkingSetSize if ok_before else 0

        size_max = ctypes.c_size_t(-1).value
        ok_empty = psapi.EmptyWorkingSet(handle)
        ok_set = kernel32.SetProcessWorkingSetSize(handle, size_max, size_max)
        time.sleep(0.05)

        pmc_after = PROCESS_MEMORY_COUNTERS()
        pmc_after.cb = ctypes.sizeof(pmc_after)
        ok_after = psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc_after), ctypes.sizeof(pmc_after))
        after_bytes = pmc_after.WorkingSetSize if ok_after else before_bytes

        kernel32.CloseHandle(handle)
        return bool(ok_empty or ok_set), before_bytes, after_bytes
    except Exception:
        return False, 0, 0

def trim_all_roblox_instances():
    if platform.system() != "Windows":
        return 0, 0.0
    pids = set()
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = str(proc.info.get('name') or '').lower()
                if any(x in name for x in ['roblox', 'bloxstrap', 'fishstrap', 'voidstrap', 'froststrap', 'exploitstrap']):
                    pids.add(int(proc.info['pid']))
            except Exception:
                continue
    except Exception:
        pass

    if not pids:
        try:
            ps_script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'Roblox|Bloxstrap|Fishstrap|Voidstrap|FrostStrap|ExploitStrap' } | Select-Object -ExpandProperty ProcessId"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    line = line.strip()
                    if line.isdigit():
                        pids.add(int(line))
        except Exception:
            pass

    if not pids:
        return 0, 0.0

    total_before = 0
    total_after = 0
    trimmed_count = 0
    for pid in pids:
        ok, b_bytes, a_bytes = trim_process_working_set(pid)
        if ok:
            trimmed_count += 1
            total_before += b_bytes
            total_after += a_bytes

    saved_mb = round(max(0, total_before - total_after) / (1024 * 1024), 1)
    return trimmed_count, saved_mb

@app.route('/api/roblox/trim-memory', methods=['POST', 'OPTIONS'])
def trim_roblox_memory_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if platform.system() != "Windows":
            return jsonify({'success': False, 'error': 'Memory trimming is only supported on Windows'}), 400

        count, saved_mb = trim_all_roblox_instances()
        add_backend_log(f"Trimmed {count} Roblox instance(s), reclaimed {saved_mb} MB RAM", level='info', category='system')
        return jsonify({
            'success': True,
            'trimmedCount': count,
            'savedMb': saved_mb,
            'message': f"Trimmed {count} instance(s), reclaimed {saved_mb} MB RAM"
        })
    except Exception as e:
        print(f"[ERROR] Memory trim endpoint error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/auto-arrange', methods=['POST', 'OPTIONS'])
def auto_arrange_roblox_clients_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if platform.system() != "Windows":
            return jsonify({
                'success': False,
                'count': 0,
                'monitors': 0,
                'error': 'Auto-Arrange is only supported on Windows operating systems'
            }), 400

        req_data = request.json or {}
        scope = req_data.get('scope')
        dim_mode = req_data.get('dimensionMode') or req_data.get('dimension_mode')
        t_w = req_data.get('targetWidth') or req_data.get('target_width')
        t_h = req_data.get('targetHeight') or req_data.get('target_height')

        result = auto_arranger.arrange_clients(
            scope=scope,
            dimension_mode=dim_mode,
            target_width=t_w,
            target_height=t_h
        )

        if result.get('success'):
            add_backend_log(f"Auto-arranged {result.get('count', 0)} Roblox client(s) across {result.get('monitors', 0)} monitor(s)", level='info', category='system')
            return jsonify(result)
        else:
            return jsonify(result), 200
    except Exception as e:
        print(f"[ERROR] Auto-arrange clients failed: {e}")
        return jsonify({'success': False, 'count': 0, 'error': str(e)}), 500

@app.route('/api/roblox/auto-arrange/monitors', methods=['GET'])
def get_auto_arrange_monitors_endpoint():
    try:
        raw_monitors = auto_arranger.get_monitor_work_areas()
        monitors_list = []
        for idx, (is_prim, work) in enumerate(raw_monitors):
            w = max(0, work[2] - work[0])
            h = max(0, work[3] - work[1])
            monitors_list.append({
                'id': idx + 1,
                'is_primary': is_prim,
                'width': w,
                'height': h,
                'work_area': [work[0], work[1], work[2], work[3]]
            })
        return jsonify({'success': True, 'monitors': monitors_list})
    except Exception as e:
        return jsonify({'success': False, 'monitors': [], 'error': str(e)}), 500

@app.route('/api/roblox/auto-arrange/status', methods=['GET'])
def get_auto_arrange_status_endpoint():
    try:
        data = load_data()
        settings = data.get('settings', {})
        hwnds = auto_arranger.get_roblox_client_windows()
        raw_monitors = auto_arranger.get_monitor_work_areas()
        return jsonify({
            'success': True,
            'keepClientsArranged': bool(settings.get('keepClientsArranged', False)),
            'activeRobloxWindows': len(hwnds),
            'monitorsCount': len(raw_monitors),
            'scope': settings.get('autoArrangeScope', 'both'),
            'dimensionMode': settings.get('autoArrangeDimensionMode', 'auto'),
            'targetWidth': settings.get('autoArrangeTargetWidth', 800),
            'targetHeight': settings.get('autoArrangeTargetHeight', 600)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/auto-arrange/toggle', methods=['POST', 'OPTIONS'])
def toggle_auto_arrange_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        new_state = req_data.get('enabled')
        with data_transaction() as txn:
            data = txn.data
            if 'settings' not in data or not isinstance(data['settings'], dict):
                data['settings'] = {}
            if new_state is None:
                new_state = not data.get('settings', {}).get('keepClientsArranged', False)

            data['settings']['keepClientsArranged'] = bool(new_state)
            txn.save()

        auto_arranger.sync_watchdog(new_state)

        return jsonify({
            'success': True,
            'enabled': bool(new_state),
            'message': f"Auto-arrange {'enabled' if new_state else 'disabled'}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



def background_auto_memory_trim_worker():
    last_trim_time = time.time()
    while True:
        try:
            time.sleep(30)
            data = load_data()
            settings = data.get('settings', {})
            enabled = bool(settings.get('autoMemoryTrimEnabled', False))
            if not enabled:
                continue

            interval_min = int(settings.get('autoMemoryTrimIntervalMinutes', 5) or 5)
            interval_sec = max(60, interval_min * 60)

            now = time.time()
            if now - last_trim_time >= interval_sec:
                last_trim_time = now
                trim_all_roblox_instances()
        except Exception as e:
            print(f"[ERROR] background_auto_memory_trim_worker error: {e}")

threading.Thread(target=background_auto_memory_trim_worker, daemon=True).start()

ALLOWED_PROCESS_NAMES = {
    'robloxplayerbeta.exe',
    'robloxplayerlauncher.exe',
    'robloxcrashhandler.exe',
    'bloxstrap.exe',
    'fishstrap.exe',
    'voidstrap.exe',
    'froststrap.exe',
    'exploitstrap.exe',
    'robloxplayerbeta',
    'robloxplayer',
    'robloxcrashhandler'
}

def terminate_crash_handlers(log_if_killed: bool = True):
    if platform.system() == "Windows":
        try:
            ps_script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'RobloxCrashHandler' } | Select-Object -ExpandProperty ProcessId"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            killed = 0
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    line = line.strip()
                    if line.isdigit():
                        subprocess.run(["taskkill", "/F", "/PID", line], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        killed += 1
            if killed > 0 and log_if_killed:
                add_backend_log(f"Terminated {killed} RobloxCrashHandler process(es)", level='info', category='system')
            return killed
        except Exception as e:
            print(f"[ERROR] terminate_crash_handlers error: {e}")
            return 0
    return 0

def background_auto_crash_handler_killer_worker():
    while True:
        try:
            time.sleep(5)
            data = load_data()
            settings = data.get('settings', {})
            enabled = bool(settings.get('autoCloseCrashHandlers', False) or settings.get('autoCloseRobloxCrashHandlers', False))
            if enabled:
                terminate_crash_handlers(log_if_killed=True)
        except Exception as e:
            print(f"[ERROR] background_auto_crash_handler_killer_worker error: {e}")

threading.Thread(target=background_auto_crash_handler_killer_worker, daemon=True).start()

@app.route('/api/instances/kill-crash-handlers', methods=['POST', 'OPTIONS'])
def kill_all_crash_handlers():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        killed = terminate_crash_handlers(log_if_killed=True)
        return jsonify({'success': True, 'killed': killed, 'message': f'Terminated {killed} crash handler process(es)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _is_roblox_pid(pid):
    try:
        p = psutil.Process(int(pid))
        process_name = (p.name() or '').lower()
        return process_name in ALLOWED_PROCESS_NAMES or (process_name + '.exe') in ALLOWED_PROCESS_NAMES
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, TypeError):
        return False

@app.route('/api/instances/kill', methods=['POST'])
def kill_specific_instance():
    """Kill a specific Roblox process by PID after verifying it is a Roblox process"""
    try:
        req_data = request.json or {}
        pid = req_data.get('pid')
        if not pid:
            return jsonify({'success': False, 'error': 'PID is required'}), 400

        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid PID'}), 400

        if not _is_roblox_pid(pid):
            return jsonify({'success': False, 'error': 'PID does not belong to a Roblox process'}), 403

        if platform.system() == "Windows":
            res = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if res.returncode == 0:
                return jsonify({'success': True, 'message': f'Terminated process PID {pid}'})
            else:
                return jsonify({'success': False, 'error': f'Failed to kill PID {pid}'}), 400
        else:
            res = subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
            return jsonify({'success': True, 'message': f'Terminated process PID {pid}'})
    except Exception as e:
        print(f"[ERROR] Kill specific instance failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

@app.route('/api/instances/relaunch', methods=['POST', 'OPTIONS'])
def relaunch_specific_instance():
    """Relaunch a specific Roblox instance by terminating its PID and re-launching the tied account"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        pid = req_data.get('pid')
        username = req_data.get('username')
        place_id = req_data.get('placeId') or req_data.get('place_id') or ''
        server_id = req_data.get('serverId') or req_data.get('server_id') or ''
        server_mode = req_data.get('serverMode') or 'vip'
        version = req_data.get('version')
        launch_mode = req_data.get('launchMode', 'game')

        if pid:
            try:
                pid = int(pid)
                if _is_roblox_pid(pid):
                    if platform.system() == "Windows":
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    else:
                        subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
                    time.sleep(1.0)
            except Exception:
                pass

        if not username:
            return jsonify({'success': False, 'error': 'Cannot relaunch: no account username tied to this instance'}), 400

        manager = get_account_manager()
        if not manager:
            return jsonify({'success': False, 'error': 'Account manager not available'}), 500

        manager.accounts = manager.load_accounts()
        if username not in manager.accounts:
            return jsonify({'success': False, 'error': f"Account '{username}' not found in saved accounts"}), 404

        prev_info = last_launch_info.get(username.lower(), {})
        if not place_id:
            place_id = prev_info.get('place_id', '')
        if not server_id:
            server_id = prev_info.get('server_id', '')
        if not version:
            version = prev_info.get('version')
        if not launch_mode:
            launch_mode = prev_info.get('launch_mode', 'game')

        if server_mode == "subplace":
            p_server = ""
            j_server = ""
            if server_id:
                place_id = server_id
        else:
            p_server = "" if server_mode == "jobid" else server_id
            j_server = server_id if server_mode == "jobid" else ""

        launched, launch_error = manager.launch_roblox(
            username=username,
            game_id=place_id,
            private_server_id=p_server,
            server_job_id=j_server,
            version=version,
            launch_mode=launch_mode,
            return_details=True
        )

        if launched:
            record_launch_event(username)
            webhook_manager.notify_launch(username, place_id=place_id, job_id=server_id)
            if auto_arranger.is_enabled():
                auto_arranger.trigger_delayed_arrange(2.5)
            if headless_manager.is_enabled():
                headless_manager.trigger_delayed_headless()
            last_launch_info[username.lower()] = {
                'place_id': place_id,
                'server_id': server_id,
                'server_mode': server_mode,
                'version': version,
                'launch_mode': launch_mode,
                'timestamp': time.time()
            }
            add_backend_log(f"Relaunched instance for @{username} (Place ID: {place_id or 'None'})", level='info', category='roblox')
            return jsonify({'success': True, 'message': f"Relaunched Roblox for @{username}"})
        return jsonify({'success': False, 'error': launch_error or "Roblox isn't installed"}), 400
    except Exception as e:
        print(f"[ERROR] Relaunch instance failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

@app.route('/api/setup/complete', methods=['POST', 'OPTIONS'])
def complete_setup():
    global active_master_password, account_manager, last_account_decryption_error, _cached_encryption_config, _cached_encryption_mtime
    if request.method == 'OPTIONS':
        return '', 200
    data = load_data()
    setup_data = request.json or {}
    
    for key, value in setup_data.items():
        if key not in ['encryptionPassword', 'confirmPassword']:
            data['settings'][key] = value
    
    if 'preferredBrowser' not in data['settings']:
        data['settings']['preferredBrowser'] = setup_data.get('preferredBrowser', 'auto')
    
    data['settings']['firstLaunch'] = False
    
    from utils.paths import get_data_folder
    from classes.encryption import EncryptionConfig, PasswordEncryption, HardwareEncryption
    data_folder = get_data_folder()
    encryption_config_path = os.path.join(data_folder, 'encryption_config.json')
    config = EncryptionConfig(encryption_config_path)
    
    curr_enabled = config.is_encryption_enabled()
    curr_method = config.get_encryption_method() if curr_enabled else 'none'
    
    target_enabled = bool(setup_data.get('encryptionEnabled'))
    target_method = setup_data.get('encryptionMethod', 'password') if target_enabled else 'none'
    target_password = str(setup_data.get('encryptionPassword', '') or '')
    
    with global_state_lock:
        try:
            if curr_method == 'password' and active_master_password:
                manager = get_account_manager(password=active_master_password)
            else:
                manager = get_account_manager()
                
            if manager is not None:
                try:
                    manager.accounts = manager.load_accounts()
                except Exception:
                    pass
            else:
                manager = get_account_manager()

            accounts_file = os.path.join(data_folder, 'saved_accounts.json')
            if os.path.exists(accounts_file):
                try:
                    import shutil
                    shutil.copy2(accounts_file, f"{accounts_file}.bak")
                except Exception:
                    pass

            if target_method == 'password':
                if target_password:
                    new_encryptor = PasswordEncryption(target_password)
                    salt_b64 = new_encryptor.get_salt_b64()
                    new_hash = hashlib.sha256(new_encryptor.key).hexdigest()
                    config.enable_password_encryption(salt_b64, new_hash)
                    active_master_password = target_password
                    if manager is not None:
                        manager.encryptor = new_encryptor
                elif curr_method == 'password':
                    if manager is not None and active_master_password and manager.encryptor is None:
                        manager.encryptor = PasswordEncryption(active_master_password, config.get_salt())
                else:
                    return jsonify({'error': 'Password is required to enable Master Password encryption'}), 400
                data['settings']['encryptionEnabled'] = True
                data['settings']['encryptionMethod'] = 'password'
            elif target_method == 'hardware':
                config.enable_hardware_encryption()
                if manager is not None:
                    manager.encryptor = HardwareEncryption(data_folder=data_folder, config=config)
                active_master_password = None
                data['settings']['encryptionEnabled'] = True
                data['settings']['encryptionMethod'] = 'hardware'
            else:
                config.disable_encryption()
                if manager is not None:
                    manager.encryptor = None
                active_master_password = None
                data['settings']['encryptionEnabled'] = False
                data['settings']['encryptionMethod'] = 'none'

            if manager is not None:
                manager.encryption_config = config
                manager.save_accounts()
            last_account_decryption_error = None

            _cached_encryption_config = config
            if os.path.exists(encryption_config_path):
                _cached_encryption_mtime = os.path.getmtime(encryption_config_path)
            invalidate_data_cache()
        except Exception as e:
            print(f"Error setting up encryption: {e}")
            return jsonify({'error': f'Encryption setup failed: {str(e)}'}), 500
    
    save_data(data)
    return jsonify({'success': True, 'settings': data['settings']})

@app.route('/api/setup/select-folder', methods=['POST', 'GET', 'OPTIONS'])
def select_folder_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_selected = filedialog.askdirectory(title="Select FRAMdata or AccountManagerData Folder")
        root.destroy()
        if folder_selected:
            return jsonify({'success': True, 'path': folder_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        return jsonify({'success': False, 'cancelled': True, 'error': str(e)}), 200

@app.route('/api/setup/preview-framdata', methods=['POST', 'OPTIONS'])
def preview_framdata():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        folder_path = req_data.get('path', '')
        password = req_data.get('password', '')
        manager = get_account_manager()
        if not manager:
            return jsonify({'success': False, 'valid': False, 'error': 'Account manager not initialized'}), 500
        res = manager.preview_framdata_folder(folder_path, password=password)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'valid': False, 'error': str(e)}), 500

@app.route('/api/setup/import-framdata', methods=['POST', 'OPTIONS'])
def import_framdata():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        folder_path = req_data.get('path', '')
        password = req_data.get('password', '')
        manager = get_account_manager()
        if not manager:
            return jsonify({'success': False, 'error': 'Account manager not initialized'}), 500
        res = manager.import_framdata_folder(folder_path, password=password)

        if res.get('success'):
            data = load_data()
            imp_settings = res.get('imported_settings', {})
            for k, v in imp_settings.items():
                data['settings'][k] = v

            imp_games = res.get('imported_games', [])
            if imp_games:
                existing_places = {g.get('placeId') for g in data['games'] if isinstance(g, dict)}
                for g in imp_games:
                    if g.get('placeId') not in existing_places:
                        data['games'].append(g)
                        existing_places.add(g.get('placeId'))

            imp_users = res.get('imported_saved_users', [])
            if imp_users:
                if 'saved_users' not in data or not isinstance(data['saved_users'], list):
                    data['saved_users'] = []
                existing_usernames = {str(u.get('username', '')).lower() for u in data['saved_users'] if isinstance(u, dict)}
                max_u_num = 0
                for u in data['saved_users']:
                    if isinstance(u, dict):
                        uid_str = str(u.get('id', ''))
                        if uid_str.startswith('u'):
                            try:
                                max_u_num = max(max_u_num, int(uid_str[1:]))
                            except ValueError:
                                pass
                for u in imp_users:
                    if isinstance(u, dict):
                        u_name = str(u.get('username', '')).strip()
                        if u_name and u_name.lower() not in existing_usernames:
                            max_u_num += 1
                            data['saved_users'].append({
                                'id': f"u{max_u_num}",
                                'username': u_name,
                                'display_name': str(u.get('displayName') or u.get('display_name') or u_name).strip(),
                                'user_id': str(u.get('userId') or u.get('user_id') or '').strip(),
                                'icon_url': str(u.get('icon_url') or '').strip()
                            })
                            existing_usernames.add(u_name.lower())

            imp_webhook = res.get('imported_webhook_config')
            if imp_webhook and isinstance(imp_webhook, dict):
                try:
                    webhook_manager.save_config(imp_webhook)
                except Exception as ex:
                    print(f"Error saving imported webhook config: {ex}")

            imp_themes = res.get('imported_custom_themes')
            if imp_themes and isinstance(imp_themes, dict):
                try:
                    custom_themes_file = os.path.join(DATA_FOLDER, 'custom_themes.json')
                    existing_themes = {}
                    if os.path.exists(custom_themes_file):
                        with open(custom_themes_file, 'r', encoding='utf-8') as tf:
                            loaded = json.load(tf)
                            if isinstance(loaded, dict):
                                existing_themes = loaded
                    existing_themes.update(imp_themes)
                    _atomic_json_write(custom_themes_file, existing_themes)
                    if 'customThemes' not in data['settings'] or not isinstance(data['settings']['customThemes'], list):
                        data['settings']['customThemes'] = []
                    theme_list = list(existing_themes.values()) if isinstance(existing_themes, dict) else []
                    data['settings']['customThemes'] = theme_list
                except Exception as ex:
                    print(f"Error saving imported custom themes: {ex}")

            save_data(data)

        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/last-error', methods=['GET'])
def get_last_error():
    report = error_detector.last_error_report or {'has_error': False}
    return jsonify(report)

@app.route('/api/auth/status', methods=['GET'])
def get_auth_status():
    from utils.paths import get_data_folder
    from classes.encryption import EncryptionConfig
    config_path = os.path.join(get_data_folder(), 'encryption_config.json')
    config = EncryptionConfig(config_path)
    
    enabled = config.is_encryption_enabled()
    method = config.get_encryption_method()
    is_locked = False
    
    if enabled and method == 'password':
        is_locked = (active_master_password is None)
        
    return jsonify({
        'encryptionEnabled': enabled,
        'encryptionMethod': method or 'none',
        'locked': is_locked
    })

@app.route('/api/auth/unlock', methods=['POST'])
def unlock_app():
    global active_master_password, account_manager
    
    now = time.time()
    if now < unlock_attempt_tracker['lockout_until']:
        remaining = int(unlock_attempt_tracker['lockout_until'] - now)
        return jsonify({'success': False, 'error': f'Too many failed attempts. Try again in {remaining} seconds.'}), 429
    
    req_data = request.json or {}
    password = req_data.get('password', '')
    
    if not password:
        return jsonify({'success': False, 'error': 'Password is required'}), 400
        
    try:
        mgr = get_account_manager(password=password)
        if mgr is None:
            unlock_attempt_tracker['count'] += 1
            unlock_attempt_tracker['last_attempt'] = now
            if unlock_attempt_tracker['count'] >= 5:
                lockout_seconds = min(2 ** unlock_attempt_tracker['count'], 600)
                unlock_attempt_tracker['lockout_until'] = now + lockout_seconds
            return jsonify({'success': False, 'error': 'Invalid master password'}), 401
        
        unlock_attempt_tracker['count'] = 0
        unlock_attempt_tracker['lockout_until'] = 0
        with global_state_lock:
            active_master_password = password
            invalidate_data_cache()
            load_data(force_reload=True)
        return jsonify({'success': True, 'unlocked': True})
    except Exception as e:
        unlock_attempt_tracker['count'] += 1
        unlock_attempt_tracker['last_attempt'] = now
        if unlock_attempt_tracker['count'] >= 5:
            lockout_seconds = min(2 ** unlock_attempt_tracker['count'], 600)
            unlock_attempt_tracker['lockout_until'] = now + lockout_seconds
        print(f"[ERROR] Unlock failed: {e}")
        return jsonify({'success': False, 'error': 'Invalid master password'}), 401

@app.route('/api/auth/lock', methods=['POST'])
def lock_app():
    global active_master_password, account_manager
    with global_state_lock:
        active_master_password = None
        account_manager = None
        invalidate_data_cache()
    return jsonify({'success': True, 'locked': True})

@app.route('/api/auth/switch-encryption', methods=['POST'])
def switch_encryption():
    global active_master_password, account_manager, last_account_decryption_error
    
    req_data = request.json or {}
    new_method = str(req_data.get('method', '')).strip().lower()
    current_pwd = str(req_data.get('current_password', '') or '')
    new_pwd = str(req_data.get('new_password', '') or '')
    
    if new_method not in ('password', 'hardware', 'none'):
        return jsonify({'success': False, 'error': 'Invalid encryption method'}), 400
        
    from utils.paths import get_data_folder
    from classes.encryption import EncryptionConfig, PasswordEncryption, HardwareEncryption
    data_folder = get_data_folder()
    config_path = os.path.join(data_folder, 'encryption_config.json')
    config = EncryptionConfig(config_path)
    
    curr_enabled = config.is_encryption_enabled()
    curr_method = config.get_encryption_method() if curr_enabled else 'none'
    
    if curr_method == 'password':
        stored_hash = config.get_password_hash()
        salt = config.get_salt()
        if not current_pwd:
            return jsonify({'success': False, 'error': 'Current master password is required'}), 400
            
        if salt:
            temp_enc = PasswordEncryption(current_pwd, salt)
            entered_hash = hashlib.sha256(temp_enc.key).hexdigest()
        else:
            entered_hash = hashlib.sha256(current_pwd.encode()).hexdigest()
            
        if not stored_hash or not hmac.compare_digest(entered_hash, stored_hash):
            return jsonify({'success': False, 'error': 'Current master password is incorrect'}), 401
            
    if new_method == 'password':
        if len(new_pwd) < 8:
            return jsonify({'success': False, 'error': 'New password must be at least 8 characters long'}), 400
            
    with global_state_lock:
        try:
            if curr_method == 'password':
                manager = get_account_manager(password=current_pwd)
            else:
                manager = get_account_manager()
                
            if manager is None:
                return jsonify({'success': False, 'error': 'Failed to initialize account manager'}), 500
                
            manager.accounts = manager.load_accounts()
        except Exception as load_err:
            return jsonify({'success': False, 'error': f'Failed to decrypt current accounts: {str(load_err)}'}), 400
            
        try:
            accounts_file = os.path.join(data_folder, 'saved_accounts.json')
            if os.path.exists(accounts_file):
                try:
                    bak_file = f"{accounts_file}.bak"
                    import shutil
                    shutil.copy2(accounts_file, bak_file)
                except Exception:
                    pass
                    
            if new_method == 'password':
                new_encryptor = PasswordEncryption(new_pwd)
                salt_b64 = new_encryptor.get_salt_b64()
                new_hash = hashlib.sha256(new_encryptor.key).hexdigest()
                config.enable_password_encryption(salt_b64, new_hash)
                manager.encryptor = new_encryptor
                active_master_password = new_pwd
            elif new_method == 'hardware':
                config.enable_hardware_encryption()
                manager.encryptor = HardwareEncryption(data_folder=data_folder, config=config)
                active_master_password = None
            elif new_method == 'none':
                config.disable_encryption()
                manager.encryptor = None
                active_master_password = None
                
            manager.encryption_config = config
            manager.save_accounts()
            last_account_decryption_error = None
            
            data = load_data()
            if 'settings' not in data or not isinstance(data['settings'], dict):
                data['settings'] = {}
            data['settings']['encryptionEnabled'] = (new_method != 'none')
            data['settings']['encryptionMethod'] = new_method
            
            save_data(data)
            invalidate_data_cache()
            
            global _cached_encryption_config, _cached_encryption_mtime
            _cached_encryption_config = config
            if os.path.exists(config_path):
                _cached_encryption_mtime = os.path.getmtime(config_path)
                
            return jsonify({
                'success': True,
                'encryptionEnabled': (new_method != 'none'),
                'encryptionMethod': new_method,
                'settings': data['settings']
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to switch encryption: {str(e)}'}), 500

@app.route('/api/setup/encryption-status', methods=['GET'])
def encryption_status():
    """Check current encryption status"""
    from utils.paths import get_data_folder
    encryption_config_path = os.path.join(get_data_folder(), 'encryption_config.json')
    
    if os.path.exists(encryption_config_path):
        try:
            with open(encryption_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return jsonify({
                    'enabled': config.get('encryption_enabled', False),
                    'method': config.get('encryption_method', 'none')
                })
        except Exception as e:
            return jsonify({'enabled': False, 'method': 'none', 'error': str(e)}), 500
    
    return jsonify({'enabled': False, 'method': 'none'})

@app.route('/api/export', methods=['GET', 'POST', 'OPTIONS'])
def export_data():
    if request.method == 'OPTIONS':
        return '', 200
    cached_config = get_cached_encryption_config()
    if cached_config and cached_config.is_encryption_enabled() and active_master_password is None:
        return jsonify({'error': 'Application locked. Unlock required.'}), 403
    
    include_credentials = True
    file_path = None
    if request.method == 'POST':
        req_json = request.get_json(silent=True) or {}
        include_credentials = bool(req_json.get('include_credentials', req_json.get('includeCredentials', True)))
        file_path = req_json.get('file_path') or req_json.get('filePath')
    else:
        req_val = request.args.get('include_credentials', request.args.get('includeCredentials', 'true')).lower()
        include_credentials = req_val not in ('false', '0', 'no')
        file_path = request.args.get('file_path') or request.args.get('filePath')

    data = load_data()
    if not include_credentials:
        sanitized_accounts = []
        for acc in data.get('accounts', []):
            acc_copy = dict(acc)
            acc_copy['cookie'] = ''
            acc_copy['password'] = ''
            sanitized_accounts.append(acc_copy)
        data['accounts'] = sanitized_accounts

    if file_path:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return jsonify({'success': True, 'path': file_path, 'count': len(data.get('accounts', []))})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify(data)

@app.route('/api/import', methods=['POST'])
def import_data():
    import_payload = request.json
    if not import_payload:
        return jsonify({'error': 'Invalid import data'}), 400

    data = load_data()
    imported_count = 0

    accounts_list = None
    if isinstance(import_payload, list):
        accounts_list = import_payload
    elif isinstance(import_payload, dict):
        if 'accounts' in import_payload and isinstance(import_payload['accounts'], list):
            accounts_list = import_payload['accounts']
        elif 'data' in import_payload and isinstance(import_payload['data'], dict) and 'accounts' in import_payload['data']:
            accounts_list = import_payload['data']['accounts']

    if accounts_list is not None:
        max_id = max([acc.get('id', 0) for acc in data['accounts']] + [0])
        allowed_account_fields = {'username', 'display_name', 'avatar_url', 'cookie', 'password',
                                  'note', 'group', 'vip_server', 'auto_rejoin_enabled', 'user_id',
                                  'status', 'added_date'}
        for account in accounts_list:
            if not isinstance(account, dict):
                continue
            uname = str(account.get('username') or '').strip()
            cookie = str(account.get('cookie') or '').strip()
            if not uname and not cookie:
                continue

            sanitized = {k: v for k, v in account.items() if k in allowed_account_fields}
            max_id += 1
            sanitized['id'] = max_id

            user_id = sanitized.get('user_id', '')
            avatar_url = sanitized.get('avatar_url', '')

            status, found_uid, found_user, found_display, found_avatar = RobloxAPI.get_account_status_and_info(
                cookie=cookie,
                username=uname or sanitized.get('username', ''),
                user_id=user_id
            )

            if found_uid:
                sanitized['user_id'] = str(found_uid)
            if found_user and found_user != 'Unknown':
                sanitized['username'] = found_user
            elif not sanitized.get('username'):
                sanitized['username'] = uname or 'Unknown'

            if found_display:
                sanitized['display_name'] = found_display

            if found_avatar:
                sanitized['avatar_url'] = found_avatar
            elif sanitized.get('user_id'):
                sanitized['avatar_url'] = RobloxAPI.get_avatar_headshot_url(sanitized['user_id'])

            if status:
                sanitized['status'] = status
            elif 'status' not in sanitized:
                sanitized['status'] = 'expired'

            data['accounts'].append(sanitized)
            imported_count += 1

    IMPORT_SETTINGS_BLOCKLIST = {
        'encryptionEnabled', 'encryptionMethod', 'firstLaunch',
    }
    if isinstance(import_payload, dict):
        if 'games' in import_payload and isinstance(import_payload['games'], list):
            for game in import_payload['games']:
                if isinstance(game, dict) and game.get('placeId'):
                    data['games'].append(game)
        if 'settings' in import_payload and isinstance(import_payload['settings'], dict):
            for k, v in import_payload['settings'].items():
                if k not in IMPORT_SETTINGS_BLOCKLIST:
                    data['settings'][k] = v

    save_data(data)
    return jsonify({'message': f'Imported {imported_count} account(s) successfully!'})

@app.route('/api/clear-all', methods=['POST'])
def clear_all_data():
    global last_account_decryption_error
    last_account_decryption_error = None

    from utils.paths import get_data_folder, get_cache_folder
    import shutil

    data_folder = get_data_folder()
    cache_folder = get_cache_folder()

    manager = get_account_manager()
    if manager:
        try:
            manager.accounts = {}
            manager.encryptor = None
        except Exception as e:
            print(f"Error resetting account manager: {e}")

    if os.path.exists(data_folder):
        for item in os.listdir(data_folder):
            item_path = os.path.join(data_folder, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
            except Exception as e:
                print(f"Error deleting {item_path}: {e}")

    if os.path.exists(cache_folder):
        for item in os.listdir(cache_folder):
            item_path = os.path.join(cache_folder, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
            except Exception as e:
                print(f"Error deleting cache {item_path}: {e}")

    _write_auth_token()

    default_settings = {
        'firstLaunch': True,
        'multiSelect': True,
        'activeIndicator': True,
        'disableSuccessPopups': False,
        'confirmBeforeLaunch': True,
        'compactRows': False,
        'accentIndex': 0,
        'selectedTheme': 'default-dark',
        'accentColor': '',
        'robloxPath': '',
        'launchClient': 'standard',
        'autoUpdateCheck': True,
        'autoCheckRobloxUpdates': True,
        'disableExecutorPresets': False,
        'encryptionEnabled': False,
        'encryptionMethod': 'none',
        'preferredBrowser': 'auto',
        'multiInstance': False,
        'showTableAvatars': True,
        'downloadAvatarIcons': True,
        'showSavedGamesBar': True,
        'showDetailPanel': True,
        'detailPanelPosition': 'right',
        'launchBarPosition': 'bottom',
        'toastPosition': 'bottom-right',
        'toastDuration': 3500,
        'enableSoundEffects': True,
        'showLaunchNotifications': True,
        'showErrorNotifications': True,
        'defaultStartupView': 'accounts',
        'autoValidateOnLaunch': True,
        'autoSortAccounts': 'none',
        'multiLaunchDelay': 1000,
        'confirmBulkDelete': True,
        'autoKillRobloxOnExit': False,
        'minimizeToTray': False,
        'streamerMode': False,
        'streamerHideUsernames': True,
        'streamerHideAvatars': True,
        'streamerHideSensitiveInfo': True,
        'streamerHideGroupsAndNotes': False,
        'streamerBlurLevel': 'medium',
        'streamerRevealOnHover': False
    }

    fresh_data = {
        'accounts': [],
        'games': [],
        'settings': default_settings
    }

    save_data(fresh_data)

    if manager:
        try:
            config_path = os.path.join(data_folder, 'encryption_config.json')
            from classes.encryption import EncryptionConfig
            manager.encryption_config = EncryptionConfig(config_path)
        except Exception as e:
            print(f"Error updating manager encryption config: {e}")

    return jsonify({'message': 'All data cleared', 'settings': default_settings})

def find_windows_uninstaller():
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        candidates = [
            os.path.join(os.path.dirname(sys.executable), "uninstall.exe"),
            os.path.join(os.path.dirname(sys.executable), "unins000.exe"),
            r"C:\Program Files\Forked Account Manager\uninstall.exe",
            r"C:\Program Files (x86)\Forked Account Manager\uninstall.exe"
        ]
        if os.environ.get("LOCALAPPDATA"):
            candidates.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Forked Account Manager", "uninstall.exe"))

        for path in candidates:
            if os.path.exists(path):
                return f'"{path}"'

        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for root_key, reg_path in registry_paths:
            try:
                key = winreg.OpenKey(root_key, reg_path)
                subkeys_count = winreg.QueryInfoKey(key)[0]
                for i in range(subkeys_count):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                        if "forked account manager" in str(display_name).lower() or "fram" == str(display_name).lower():
                            try:
                                uninstall_str, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                winreg.CloseKey(subkey)
                                winreg.CloseKey(key)
                                return uninstall_str
                            except Exception:
                                pass
                        winreg.CloseKey(subkey)
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception as e:
        print(f"Error finding windows uninstaller: {e}")

    return None

@app.route('/api/app/uninstall', methods=['POST'])
def uninstall_application():
    try:
        from utils.paths import get_root_app_dir
        root_dir = get_root_app_dir()
        
        sync_startup_registry(False)

        manager = get_account_manager()
        if manager:
            try:
                manager.accounts = {}
                manager.save_accounts()
            except Exception:
                pass
        
        program_files_dir = "C:\\Program Files\\Forked Account Manager"
        uninstaller_cmd = find_windows_uninstaller()
        
        if platform.system() == "Windows":
            temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or "C:\\Windows\\Temp"
            bat_path = os.path.join(temp_dir, "uninstall_fram.bat")
            
            kill_cmds = """taskkill /F /IM "backend.exe" 2>nul
taskkill /F /IM "FRAM.exe" 2>nul
taskkill /F /IM "fram.exe" 2>nul
taskkill /F /IM "ForkedRobloxAccountManager.exe" 2>nul
taskkill /F /IM "Forked Account Manager.exe" 2>nul"""
            
            if uninstaller_cmd:
                bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
{kill_cmds}
timeout /t 1 /nobreak > nul
start "" {uninstaller_cmd}
timeout /t 3 /nobreak > nul
if exist "{root_dir}" (
    rd /s /q "{root_dir}" 2>nul
)
(goto) 2>nul & del "%~f0"
"""
            else:
                bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
{kill_cmds}
timeout /t 1 /nobreak > nul
set count=0
:loop1
if exist "{program_files_dir}" (
    rd /s /q "{program_files_dir}" 2>nul
    set /a count+=1
    if %count% LSS 10 (
        timeout /t 1 /nobreak > nul
        goto loop1
    )
)
set count=0
:loop2
if exist "{root_dir}" (
    rd /s /q "{root_dir}" 2>nul
    set /a count+=1
    if %count% LSS 10 (
        timeout /t 1 /nobreak > nul
        goto loop2
    )
)
(goto) 2>nul & del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
                
            subprocess.Popen(
                [bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW | 0x00000008,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            if os.path.exists(root_dir):
                import shutil
                try:
                    shutil.rmtree(root_dir)
                except Exception:
                    pass

        import threading
        threading.Timer(1.0, lambda: os._exit(0)).start()

        return jsonify({'success': True, 'message': 'Application uninstall sequence started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clear-accounts', methods=['POST'])
def clear_accounts():
    """Clear only accounts, not settings or games"""
    with data_transaction() as txn:
        txn.data['accounts'] = []
        txn.save()
    
    manager = get_account_manager()
    if manager:
        try:
            manager.accounts = {}
            manager.save_accounts()
        except Exception as e:
            print(f"Error clearing account manager: {e}")
    
    return jsonify({'message': 'All accounts cleared'})

@app.route('/api/accounts/add-browser', methods=['POST'])
def add_account_browser():
    """Add account using browser automation"""
    try:
        req_data = request.json or {}
        amount = req_data.get('amount', 1)
        website = req_data.get('website', 'https://www.roblox.com/login')
        preferred_browser = req_data.get('preferred_browser') or req_data.get('preferredBrowser') or 'auto'
        
        print(f"[Browser Login] Request received - Amount: {amount}, Website: {website}, Browser: {preferred_browser}")
        
        manager = get_account_manager()
        if not manager:
            return jsonify({'error': 'Account manager not available. Check encryption setup.'}), 500
        
        import threading
        result = {'success': False, 'message': ''}
        
        def add_accounts():
            try:
                success = manager.add_account(
                    amount=amount,
                    website=website,
                    preferred_browser=preferred_browser
                )
                result['success'] = success
                result['message'] = 'Accounts added successfully' if success else 'Failed to add accounts'
                if success:
                    invalidate_data_cache()
                    fresh_data = load_data(force_reload=True)
                    save_data(fresh_data)
            except Exception as e:
                result['success'] = False
                result['message'] = str(e)
        
        thread = threading.Thread(target=add_accounts)
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Browser automation started'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/add-credentials', methods=['POST'])
def add_account_credentials():
    """Add account using username/password credentials"""
    try:
        req_data = request.json or {}
        credentials = req_data.get('credentials', [])
        timeout_per_account = req_data.get('timeout_per_account', 120)
        preferred_browser = req_data.get('preferred_browser') or req_data.get('preferredBrowser') or 'auto'
        max_concurrent = int(req_data.get('max_concurrent') or req_data.get('maxConcurrent') or 1)
        max_concurrent = max(1, min(5, max_concurrent))
        
        if not credentials:
            return jsonify({'error': 'No credentials provided'}), 400
        
        manager = get_account_manager()
        if not manager:
            return jsonify({'error': 'Account manager not available. Check encryption setup.'}), 500
        
        import threading
        result = {'success': False, 'count': 0, 'message': ''}
        
        def add_creds():
            try:
                count = manager.add_accounts_from_credentials(
                    credentials=credentials,
                    max_concurrent=max_concurrent,
                    timeout_per_account=timeout_per_account,
                    preferred_browser=preferred_browser
                )
                result['success'] = count > 0
                result['count'] = count
                result['message'] = f'Successfully added {count} accounts'
                if count > 0:
                    invalidate_data_cache()
                    fresh_data = load_data(force_reload=True)
                    save_data(fresh_data)
            except Exception as e:
                result['success'] = False
                result['message'] = str(e)
        
        thread = threading.Thread(target=add_creds)
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Credential login started'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/browser/status', methods=['GET'])
def browser_status():
    """Check browser availability and account manager status"""
    try:
        manager = get_account_manager()
        if not manager:
            return jsonify({
                'manager_available': False,
                'browsers_available': [],
                'has_supported_browser': False,
                'is_running': False,
                'active_instances': 0,
                'user_closed': False,
                'last_close_reason': None,
                'error': 'Account manager not available'
            })
        
        available_browsers = manager.get_available_browsers()
        has_browser = len(available_browsers) > 0
        is_running = manager.is_browser_automation_running()
        active_instances = getattr(manager, '_active_browser_automation_count', 0)
        user_closed = getattr(manager, '_last_browser_closed_by_user', False)
        close_reason = getattr(manager, '_last_browser_close_reason', None)
        
        return jsonify({
            'manager_available': True,
            'browsers_available': available_browsers,
            'has_supported_browser': has_browser,
            'is_running': is_running,
            'active_instances': active_instances,
            'user_closed': user_closed,
            'last_close_reason': close_reason,
            'accounts_count': len(manager.accounts)
        })
    except Exception as e:
        return jsonify({
            'manager_available': False,
            'browsers_available': [],
            'has_supported_browser': False,
            'is_running': False,
            'active_instances': 0,
            'user_closed': False,
            'last_close_reason': None,
            'error': str(e)
        }), 500

@app.route('/api/browser/chromium/status', methods=['GET'])
def get_chromium_status():
    try:
        status_info = chromium_downloader_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        log_detailed_error("Failed to get chromium status", exc=e, source="chromium_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/browser/chromium/download', methods=['POST'])
def start_chromium_download():
    try:
        manager = get_account_manager()
        if manager:
            manager._browser_installed_cache = {}
            manager._browser_installed_cache_time = 0
        res = chromium_downloader_manager.start_download()
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to start chromium download", exc=e, source="chromium_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/browser/chromium/uninstall', methods=['POST'])
def uninstall_chromium():
    try:
        manager = get_account_manager()
        if manager:
            manager._browser_installed_cache = {}
            manager._browser_installed_cache_time = 0
        res = chromium_downloader_manager.uninstall()
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to uninstall chromium", exc=e, source="chromium_api")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/add-quick-signin', methods=['POST'])
def add_quick_signin():
    """Start Quick Sign-In process in background with cancellation and status tracking"""
    try:
        data = request.json or {}
        preferred_browser = data.get('preferredBrowser') or data.get('preferred_browser') or 'auto'
        timeout = int(data.get('timeout', 300))
        
        manager = get_account_manager()
        if not manager:
            return jsonify({'error': 'Account manager not available'}), 500
        
        import threading
        import time

        now = time.time()
        with quick_signin_lock:
            expired_sessions = [sid for sid, s in quick_signin_sessions.items() if (now - s.get('created_at', now)) > 600]
            for sid in expired_sessions:
                quick_signin_sessions.pop(sid, None)

        cancel_event = threading.Event()
        session_id = str(uuid.uuid4())
        
        result_container = {
            'session_id': session_id,
            'result': None,
            'status': 'starting',
            'status_message': 'Starting Quick Sign-In process...',
            'code': '',
            'qr_image_url': '',
            'created_at': time.time(),
            'completed_at': None,
            'cancel_event': cancel_event,
        }
        
        def on_code(code, qr_url=''):
            result_container['code'] = code
            result_container['qr_image_url'] = qr_url or ''
            result_container['status'] = 'code_ready'
            result_container['status_message'] = f'Code {code} ready for confirmation.'
        
        def on_status(status_text):
            result_container['status_message'] = status_text

        def on_success(result_data):
            result_container['result'] = result_data
            result_container['status'] = 'completed'
            result_container['status_message'] = f"Account @{result_data.get('username')} successfully connected!"
            result_container['completed_at'] = time.time()
            try:
                invalidate_data_cache()
                fresh_data = load_data(force_reload=True)
                save_data(fresh_data)
            except Exception as sync_err:
                print(f"Error syncing data after quick sign-in: {sync_err}")
        
        def run_quick_signin():
            try:
                result = manager.add_account_quick_sign_in(
                    preferred_browser=preferred_browser,
                    on_code=on_code,
                    on_status=on_status,
                    on_success=on_success,
                    timeout=timeout,
                    cancel_event=cancel_event,
                )
                if not result_container.get('completed_at'):
                    result_container['result'] = result
                    result_container['completed_at'] = time.time()

                    if result.get('success'):
                        result_container['status'] = 'completed'
                        result_container['status_message'] = f"Account @{result.get('username')} successfully connected!"
                        try:
                            invalidate_data_cache()
                            fresh_data = load_data(force_reload=True)
                            save_data(fresh_data)
                        except Exception as sync_err:
                            print(f"Error syncing data after quick sign-in: {sync_err}")
                    elif cancel_event.is_set():
                        result_container['status'] = 'cancelled'
                        result_container['status_message'] = 'Quick Sign-In was cancelled.'
                    else:
                        result_container['status'] = 'error'
                        result_container['status_message'] = result.get('error', 'Quick Sign-In failed')
            except Exception as e:
                result_container['result'] = {'success': False, 'error': str(e)}
                result_container['status'] = 'error'
                result_container['status_message'] = str(e)
                result_container['completed_at'] = time.time()

        thread = threading.Thread(target=run_quick_signin, daemon=True)
        thread.start()
        
        with quick_signin_lock:
            quick_signin_sessions[session_id] = result_container
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'starting',
            'status_message': 'Starting Quick Sign-In process...'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quick-signin/status/<session_id>', methods=['GET'])
def get_quick_signin_status(session_id):
    """Get current status, code, QR URL, and result of a Quick Sign-In session"""
    try:
        with quick_signin_lock:
            if session_id not in quick_signin_sessions:
                return jsonify({'error': 'Session not found'}), 404
            session = quick_signin_sessions[session_id]
            time_elapsed = int(time.time() - session.get('created_at', time.time()))
            
            response = {
                'session_id': session_id,
                'status': session['status'],
                'status_message': session.get('status_message', ''),
                'code': session.get('code', ''),
                'qr_image_url': session.get('qr_image_url', ''),
                'time_elapsed': time_elapsed,
                'result': session.get('result')
            }
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quick-signin/cancel/<session_id>', methods=['POST'])
def cancel_quick_signin(session_id):
    """Cancel an active Quick Sign-In session and terminate background browser"""
    try:
        with quick_signin_lock:
            if session_id in quick_signin_sessions:
                session = quick_signin_sessions[session_id]
                cancel_event = session.get('cancel_event')
                if cancel_event:
                    cancel_event.set()
                session['status'] = 'cancelled'
                session['status_message'] = 'Quick Sign-In was cancelled by user.'
                return jsonify({'success': True, 'message': 'Session cancelled successfully'})
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/roblox/validate-cookie', methods=['POST'])
def validate_cookie():
    try:
        data = request.json or {}
        cookie = data.get('cookie', '')

        if not cookie:
            return jsonify({'error': 'Cookie is required'}), 400

        status, user_id, username, display_name, avatar_url = RobloxAPI.get_account_status_and_info(cookie=cookie)

        with data_transaction() as txn:
            all_data = txn.data
            updated_any = False
            norm_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)
            for acc in all_data.get('accounts', []):
                acc_cookie = RobloxAPI._normalize_roblosecurity_cookie(acc.get('cookie', ''))
                if (acc_cookie and norm_cookie and acc_cookie == norm_cookie) or (username and username != 'Unknown' and acc.get('username') == username):
                    acc['status'] = status
                    if user_id: acc['user_id'] = user_id
                    if username and username != 'Unknown': acc['username'] = username
                    if display_name: acc['display_name'] = display_name
                    if avatar_url: acc['avatar_url'] = avatar_url
                    updated_any = True
            if updated_any:
                txn.save()

        if status == 'expired' or (status != 'banned' and (not username or username == 'Unknown')):
            return jsonify({'valid': False, 'status': 'expired', 'error': 'Invalid or expired cookie'}), 400

        return jsonify({
            'valid': status == 'valid',
            'status': status,
            'is_banned': status == 'banned',
            'username': username,
            'user_id': user_id,
            'display_name': display_name,
            'avatar_url': avatar_url
        })
    except Exception as e:
        return jsonify({'valid': False, 'status': 'expired', 'error': str(e)}), 500

@app.route('/api/roblox/user-info', methods=['POST'])
def get_user_info():
    """Get detailed user information from username or user ID and check join status"""
    try:
        data = request.json or {}
        user_identifier = str(data.get('username', '') or data.get('user_identifier', '') or '').strip()
        user_identifier = user_identifier.lstrip('@')
        
        if not user_identifier:
            return jsonify({'error': 'Username or user ID is required'}), 400
        
        join_status = RobloxAPI.get_join_user_status(user_identifier)
        user_id = str(join_status.get('user_id') or '').strip()
        username = str(join_status.get('username') or '').strip()

        if not user_id:
            if user_identifier.isdigit():
                user_id = user_identifier
                username = RobloxAPI.get_username_from_user_id(user_id) or user_identifier
            else:
                found_id = RobloxAPI.get_user_id_from_username(user_identifier)
                if not found_id:
                    return jsonify({'error': 'User not found'}), 404
                user_id = str(found_id)
                username = RobloxAPI.get_username_from_user_id(user_id) or user_identifier

        if not username:
            username = RobloxAPI.get_username_from_user_id(user_id) or user_identifier

        avatar_url = RobloxAPI.get_avatar_headshot_url(user_id)
        if not avatar_url:
            avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=true"

        joinable = bool(join_status.get('joinable', False))
        presence_type = int(join_status.get('presence_type', 0) or 0)
        location = str(join_status.get('location', '') or '')

        is_banned = RobloxAPI.is_user_banned(user_id)
        status = 'banned' if is_banned else 'valid'
        
        return jsonify({
            'username': username,
            'user_id': user_id,
            'display_name': username,
            'avatar_url': avatar_url,
            'joinable': joinable,
            'presence_type': presence_type,
            'location': location,
            'is_banned': is_banned,
            'status': status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/roblox/game-info', methods=['POST'])
def get_game_info():
    """Get game information and icon from place ID or universe ID"""
    try:
        data = request.json or {}
        placeId = str(data.get('placeId') or data.get('place_id') or '').strip()
        universeId = str(data.get('universeId') or data.get('universe_id') or '').strip()
        force_refresh = bool(data.get('forceRefresh') or data.get('refresh'))

        if not placeId and not universeId:
            return jsonify({'error': 'Place ID or Universe ID is required'}), 400

        details = None
        if placeId:
            details = RobloxAPI.get_game_details(placeId, use_cache=not force_refresh)

        if not details and universeId:
            details = RobloxAPI.get_game_details_by_universe(universeId, use_cache=not force_refresh)

        if details:
            return jsonify(details)

        fallback_name = f'Place {placeId}' if placeId else (f'Universe {universeId}' if universeId else 'Roblox Game')
        return jsonify({
            'place_id': placeId,
            'universe_id': universeId,
            'name': fallback_name,
            'icon_url': ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/roblox/clear-icon-cache', methods=['POST'])
def clear_icon_cache():
    try:
        icon_cache.clear()
        return jsonify({'success': True, 'message': 'Icon cache cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/icon-cache/stats', methods=['GET'])
def get_icon_cache_stats():
    try:
        stats = icon_cache.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/icon-file/<path:filename>', methods=['GET'])
def get_icon_file(filename):
    try:
        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename != filename:
            return jsonify({'error': 'Invalid filename'}), 400
        from utils.paths import get_cache_folder
        icons_dir = os.path.join(get_cache_folder(), 'icons')
        icon_path = os.path.join(icons_dir, safe_filename)
        if not os.path.isfile(icon_path):
            return jsonify({'error': 'File not found'}), 404
        return send_from_directory(icons_dir, safe_filename)
    except Exception:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/roblox/subplaces/<place_id>', methods=['GET'])
def get_subplaces_endpoint(place_id):
    try:
        subplaces = RobloxAPI.get_subplaces(place_id)
        return jsonify({'success': True, 'place_id': place_id, 'subplaces': subplaces})
    except Exception as e:
        return jsonify({'success': False, 'subplaces': [], 'error': str(e)}), 500

@app.route('/api/roblox/private-server-resolve', methods=['POST'])
def resolve_private_server():
    try:
        data = request.json or {}
        input_value = str(data.get('input') or '').strip()
        cookie = str(data.get('cookie') or '').strip()
        
        if not input_value:
            return jsonify({'error': 'Input is required'}), 400
        
        if not cookie:
            manager = get_account_manager()
            if manager and hasattr(manager, 'accounts') and isinstance(manager.accounts, dict):
                for acc in manager.accounts.values():
                    if isinstance(acc, dict) and acc.get('cookie'):
                        cookie = acc['cookie']
                        break
        
        share_details = RobloxAPI.extract_private_server_share_details(input_value)
        if share_details:
            resolved_share_link = RobloxAPI.resolve_private_server_share_link(input_value, cookie) or {}
            resolved_link_code = str(resolved_share_link.get("link_code") or "").strip()
            resolved_access_code = str(
                resolved_share_link.get("access_code")
                or share_details.get("code")
                or ""
            ).strip()
            resolved_place_id = str(resolved_share_link.get("place_id") or "").strip()
            final_code = resolved_link_code or resolved_access_code or input_value
            return jsonify({
                'input': input_value,
                'resolved': final_code,
                'link_code': resolved_link_code,
                'access_code': resolved_access_code,
                'place_id': resolved_place_id,
                'url': str(resolved_share_link.get("url") or "")
            })

        resolved = RobloxAPI.normalize_private_server(input_value, cookie)
        place_id = ""
        place_match = re.search(r"(?:games|placeId=|\/)(\d{4,15})", input_value, re.IGNORECASE)
        if place_match:
            place_id = place_match.group(1)

        return jsonify({
            'input': input_value,
            'resolved': resolved,
            'link_code': resolved if resolved != input_value else "",
            'place_id': place_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/auth/token', methods=['GET'])
def get_auth_token():
    origin = request.headers.get('Origin', '')
    referer = request.headers.get('Referer', '')
    is_allowed_origin = origin and origin in ALLOWED_ORIGINS
    is_allowed_referer = referer and any(referer.startswith(o) for o in ALLOWED_ORIGINS)
    is_local = request.remote_addr in ('127.0.0.1', '::1', 'localhost') and not origin and not referer
    if not is_allowed_origin and not is_allowed_referer and not is_local:
        return jsonify({'error': 'Unauthorized origin'}), 403
    return jsonify({'token': API_AUTH_TOKEN})

_IS_SHUTTING_DOWN = False
_SHUTDOWN_LOCK = threading.Lock()

def perform_graceful_shutdown():
    global _IS_SHUTTING_DOWN
    with _SHUTDOWN_LOCK:
        if _IS_SHUTTING_DOWN:
            return
        _IS_SHUTTING_DOWN = True

    try:
        anti_afk_manager.stop_loop()
    except Exception as e:
        log_detailed_error("Error stopping anti_afk_manager during shutdown", exc=e, source="shutdown")

    try:
        auto_arranger.stop_watchdog()
    except Exception as e:
        log_detailed_error("Error stopping auto_arranger during shutdown", exc=e, source="shutdown")

    try:
        headless_manager.sync_watchdog(False)
    except Exception as e:
        log_detailed_error("Error stopping headless_manager during shutdown", exc=e, source="shutdown")

    try:
        webhook_manager.stop()
    except Exception as e:
        log_detailed_error("Error stopping webhook_manager during shutdown", exc=e, source="shutdown")

    try:
        icon_cache.flush()
    except Exception as e:
        log_detailed_error("Error flushing icon_cache during shutdown", exc=e, source="shutdown")

    try:
        mgr = get_account_manager()
        if mgr:
            mgr.save_accounts()
    except Exception as e:
        log_detailed_error("Error saving accounts during shutdown", exc=e, source="shutdown")

    try:
        cleanup_temp_files(max_age_seconds=0.0)
    except Exception as e:
        log_detailed_error("Error cleaning temporary files during shutdown", exc=e, source="shutdown")

    try:
        token_path = os.path.join(get_data_folder(), '.api_token')
        if os.path.exists(token_path):
            os.unlink(token_path)
    except Exception:
        pass

atexit.register(perform_graceful_shutdown)

def _signal_handler(signum, frame):
    perform_graceful_shutdown()
    sys.exit(0)

try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, AttributeError):
    pass

@app.route('/api/system/shutdown', methods=['POST', 'OPTIONS'])
def shutdown_system():
    if request.method == 'OPTIONS':
        return '', 200

    def _delayed_exit():
        time.sleep(0.05)
        perform_graceful_shutdown()
        time.sleep(0.05)
        os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return jsonify({'success': True, 'message': 'Graceful shutdown initiated'})

@app.route('/api/installer/available-versions', methods=['GET'])
def get_installer_available_versions():
    try:
        versions = roblox_installer_manager.get_available_versions()
        return jsonify({'success': True, 'versions': versions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/installer/clients', methods=['GET'])
def get_installer_clients():
    try:
        clients = roblox_installer_manager.get_installed_clients()
        return jsonify({'success': True, 'clients': clients})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/installer/start', methods=['POST'])
def start_installer_download():
    try:
        data = request.json or {}
        version_entry = data.get('version_entry') or {}
        client_id = data.get('client_id') or ''
        overwrite = bool(data.get('overwrite', False))
        res = roblox_installer_manager.start_installation(version_entry, client_id, overwrite)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/installer/status', methods=['GET'])
def get_installer_status():
    try:
        status_info = roblox_installer_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/installer/weao-exploits', methods=['GET'])
def get_installer_weao_exploits():
    try:
        exploits = roblox_installer_manager.get_weao_exploits()
        return jsonify({'success': True, 'exploits': exploits})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/updater/check', methods=['GET'])
def check_app_updates():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        res = updater_manager.check_for_updates(force=force)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/updater/download', methods=['POST'])
def start_app_update_download():
    try:
        data = request.get_json(silent=True) or {}
        download_url = data.get('download_url')
        asset_name = data.get('asset_name')
        expected_sha256 = data.get('sha256') or data.get('expected_sha256')
        total_bytes = data.get('total_bytes') or data.get('asset_size') or data.get('size') or 0
        res = updater_manager.start_download(
            download_url=download_url,
            asset_name=asset_name,
            expected_sha256=expected_sha256,
            total_bytes=total_bytes
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/updater/status', methods=['GET'])
def get_app_update_status():
    try:
        status_info = updater_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/updater/apply', methods=['POST'])
def apply_app_update():
    try:
        res = updater_manager.apply_update()
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/updater/releases', methods=['GET'])
def get_app_releases():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        releases = updater_manager.get_all_releases(force=force)
        return jsonify({'success': True, 'releases': releases})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'releases': []}), 500

@app.route('/api/system/logs', methods=['GET'])
def get_system_logs():
    with backend_logs_lock:
        return jsonify({'success': True, 'logs': list(backend_logs)})

@app.route('/api/roblox/global-settings', methods=['GET', 'POST', 'OPTIONS'])
def handle_roblox_global_settings():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.roblox_global_settings import roblox_global_settings_manager
        if request.method == 'GET':
            data = roblox_global_settings_manager.load_settings()
            return jsonify(data)
        elif request.method == 'POST':
            req_data = request.json or {}
            new_settings = req_data.get('settings', {})
            result = roblox_global_settings_manager.save_settings(new_settings)
            if result.get('success'):
                return jsonify(result)
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/ixp-settings', methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def handle_roblox_ixp_settings():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.roblox_ixp_settings import roblox_ixp_settings_manager
        if request.method == 'GET':
            data = roblox_ixp_settings_manager.load_settings()
            return jsonify(data)
        elif request.method == 'POST':
            req_data = request.json or {}
            new_settings = req_data.get('settings', {})
            result = roblox_ixp_settings_manager.save_settings(new_settings)
            if result.get('success'):
                return jsonify(result)
            return jsonify(result), 400
        elif request.method == 'DELETE':
            result = roblox_ixp_settings_manager.reset_settings()
            return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/fastflags', methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
def handle_roblox_fastflags():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.fastflags import FastFlagsManager
        manager = FastFlagsManager()
        if request.method == 'GET':
            flags = manager.load_fast_flags()
            file_path = manager.get_fast_flags_file()
            exists = os.path.exists(file_path)
            return jsonify({
                'success': True,
                'exists': exists,
                'file_path': file_path,
                'flags': flags
            })
        elif request.method == 'DELETE':
            success = manager.reset_to_default()
            if success:
                return jsonify({'success': True, 'message': 'FastFlags reset to default successfully.'})
            return jsonify({'success': False, 'error': 'Failed to reset FastFlags.'}), 400
        elif request.method == 'POST':
            req_data = request.json or {}
            new_flags = req_data.get('flags', {})
            success = manager.save_fast_flags(new_flags)
            if success:
                return jsonify({'success': True, 'message': 'FastFlags saved successfully.'})
            return jsonify({'success': False, 'error': 'Failed to save FastFlags.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/fastflags/validate', methods=['POST', 'OPTIONS'])
def validate_roblox_fastflag():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.fastflags import FastFlagsManager
        manager = FastFlagsManager()
        req_data = request.json or {}
        flag_name = req_data.get('name', '')
        valid, message = manager.validate_flag_name(flag_name)
        return jsonify({'success': True, 'valid': valid, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/fastflags/backup', methods=['POST', 'OPTIONS'])
def backup_roblox_fastflags():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.fastflags import FastFlagsManager
        manager = FastFlagsManager()
        success = manager.backup_fast_flags()
        if success:
            return jsonify({'success': True, 'message': 'FastFlags backup created successfully.'})
        return jsonify({'success': False, 'error': 'Failed to backup FastFlags.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/fastflags/restore', methods=['POST', 'OPTIONS'])
def restore_roblox_fastflags():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.fastflags import FastFlagsManager
        manager = FastFlagsManager()
        success = manager.restore_fast_flags()
        if success:
            return jsonify({'success': True, 'message': 'FastFlags restored from backup successfully.'})
        return jsonify({'success': False, 'error': 'Failed to restore FastFlags.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/roblox/fastflags/reset', methods=['POST', 'OPTIONS'])
def reset_roblox_fastflags():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        from classes.fastflags import FastFlagsManager
        manager = FastFlagsManager()
        success = manager.reset_to_default()
        if success:
            return jsonify({'success': True, 'message': 'FastFlags reset to default successfully.'})
        return jsonify({'success': False, 'error': 'Failed to reset FastFlags.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/config', methods=['GET', 'OPTIONS'])
def get_webhook_config():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify({
            'success': True,
            'config': webhook_manager.config,
            'history': webhook_manager.get_history()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/config', methods=['POST', 'OPTIONS'])
def save_webhook_config():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        updated = webhook_manager.save_config(data)
        return jsonify({
            'success': True,
            'config': updated,
            'message': 'Webhook settings saved successfully.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/test', methods=['POST', 'OPTIONS'])
def test_webhook():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        url = data.get('webhook_url') or webhook_manager.config.get('webhook_url', '')
        ok, msg = webhook_manager.send_test_webhook(url)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/send', methods=['POST', 'OPTIONS'])
def send_webhook_custom():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        title = data.get('title', 'Notification')
        description = data.get('description', '')
        fields = data.get('fields', [])
        color = data.get('color', 0x6366F1)
        ok, msg = webhook_manager.post_embed(title, description, fields, color)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/test-screenshot', methods=['POST', 'OPTIONS'])
def test_webhook_screenshot():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        url = data.get('webhook_url') or webhook_manager.config.get('webhook_url', '')
        all_monitors = data.get('all_monitors')
        ok, msg = webhook_manager.post_screenshot(url, all_monitors=all_monitors)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/webhook/test-instances', methods=['POST', 'OPTIONS'])
def test_webhook_instances():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        url = data.get('webhook_url') or webhook_manager.config.get('webhook_url', '')
        ok, msg = webhook_manager.post_instance_summary(url=url)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/status', methods=['GET', 'OPTIONS'])
def get_rblxswap_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        elevated = roblox_swap_manager.is_elevated()
        backup = roblox_swap_manager.get_backup_info()
        anticheats = roblox_swap_manager.detect_anticheats()
        return jsonify({
            'success': True,
            'elevated': elevated,
            'backup': backup,
            'anticheats': anticheats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/clean', methods=['POST', 'OPTIONS'])
def clean_rblx_traces():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        preserve_settings = data.get('preserve_settings', True)
        preserve_fastflags = data.get('preserve_fastflags', False)
        preserve_app_settings = data.get('preserve_app_settings', True)
        delete_studio = data.get('delete_studio', False)
        purge_auth = data.get('purge_auth', True)
        weblauncher_dir = data.get('weblauncher_dir')
        res = roblox_swap_manager.clean_traces(
            preserve_settings=preserve_settings,
            preserve_fastflags=preserve_fastflags,
            preserve_app_settings=preserve_app_settings,
            delete_studio=delete_studio,
            purge_auth=purge_auth,
            weblauncher_dir=weblauncher_dir
        )
        for l in res.get('logs', []):
            lvl = l.get('level', 'info')
            if lvl == 'warn':
                lvl = 'warning'
            add_backend_log(f"[TraceCleaner] {l.get('msg', '')}", level=lvl, category='spoofer')
        return jsonify(res)
    except Exception as e:
        add_backend_log(f"[TraceCleaner] Error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/clean-status', methods=['GET', 'OPTIONS'])
def get_rblxswap_clean_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify({'success': True, 'status': roblox_swap_manager.clean_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/adapters', methods=['GET', 'OPTIONS'])
def get_rblxswap_adapters():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        adapters = roblox_swap_manager.get_adapters()
        return jsonify({'success': True, 'adapters': adapters})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/spoof-mac', methods=['POST', 'OPTIONS'])
def spoof_rblx_mac():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        all_adapters = data.get('all_adapters', False)
        mirror_oui = data.get('mirror_oui', True)
        restart = data.get('restart', True)
        adapter_desc = data.get('adapter_desc')
        custom_mac = data.get('mac')

        roblox_swap_manager.create_backup()

        if all_adapters:
            adapters = roblox_swap_manager.get_adapters()
            results = []
            for a in adapters:
                desc = a.get('description')
                orig_mac = a.get('mac')
                name = a.get('name')
                new_mac = custom_mac if (custom_mac and len(adapters) == 1) else roblox_swap_manager.generate_mac(base_mac=orig_mac, mirror_oui=mirror_oui)
                ok = roblox_swap_manager.set_network_address(desc, new_mac)
                if ok and restart and name:
                    roblox_swap_manager.cycle_adapter(name)
                results.append({'name': name, 'desc': desc, 'mac': new_mac, 'ok': ok})
            add_backend_log(f"[Spoofer] Spoofed MAC addresses for {len(results)} adapters", level='info', category='spoofer')
            return jsonify({'success': any(r['ok'] for r in results), 'results': results})
        else:
            if not adapter_desc:
                return jsonify({'success': False, 'error': 'Missing adapter description'}), 400
            new_mac = custom_mac or roblox_swap_manager.generate_mac(mirror_oui=False)
            ok = roblox_swap_manager.set_network_address(adapter_desc, new_mac)
            adapter_name = data.get('adapter_name')
            if ok and restart and adapter_name:
                roblox_swap_manager.cycle_adapter(adapter_name)
            add_backend_log(f"[Spoofer] Spoofed MAC for {adapter_name or adapter_desc}: {new_mac}", level='info', category='spoofer')
            return jsonify({'success': ok, 'mac': new_mac})
    except Exception as e:
        add_backend_log(f"[Spoofer] Spoof MAC error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/reset-mac', methods=['POST', 'OPTIONS'])
def reset_rblx_mac():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        all_adapters = data.get('all_adapters', False)
        restart = data.get('restart', True)

        if all_adapters:
            adapters = roblox_swap_manager.get_adapters()
            results = []
            for a in adapters:
                desc = a.get('description')
                name = a.get('name')
                ok = roblox_swap_manager.clear_network_address(desc)
                if restart and name:
                    roblox_swap_manager.cycle_adapter(name)
                results.append({'name': name, 'desc': desc, 'ok': ok})
            add_backend_log(f"[Spoofer] Reset MAC addresses for {len(results)} adapters", level='info', category='spoofer')
            return jsonify({'success': True, 'results': results})
        else:
            adapter_desc = data.get('adapter_desc')
            adapter_name = data.get('adapter_name')
            if not adapter_desc:
                return jsonify({'success': False, 'error': 'Missing adapter description'}), 400
            ok = roblox_swap_manager.clear_network_address(adapter_desc)
            if restart and adapter_name:
                roblox_swap_manager.cycle_adapter(adapter_name)
            add_backend_log(f"[Spoofer] Reset MAC address for {adapter_name or adapter_desc}", level='info', category='spoofer')
            return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/restart-adapter', methods=['POST', 'OPTIONS'])
def restart_rblx_adapter():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        adapter_name = data.get('adapter_name')
        if not adapter_name:
            return jsonify({'success': False, 'error': 'Missing adapter name'}), 400
        ok = roblox_swap_manager.cycle_adapter(adapter_name)
        add_backend_log(f"[Spoofer] Cycled network adapter {adapter_name}", level='info', category='spoofer')
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/dhcp-refresh', methods=['POST', 'OPTIONS'])
def refresh_rblx_dhcp():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        ok = roblox_swap_manager.refresh_dhcp()
        add_backend_log(f"[Spoofer] Refreshed DHCP IP address lease", level='info', category='spoofer')
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/spoof-hwid', methods=['POST', 'OPTIONS'])
def spoof_rblx_hwid():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        guids = data.get('guids', True)
        volume = data.get('volume', False)
        results = roblox_swap_manager.spoof_identifiers(guids=guids, volume=volume)
        for r in results:
            if r.get('ok'):
                add_backend_log(f"[Spoofer] Rotated {r.get('name')}: {r.get('value')}", level='info', category='spoofer')
            else:
                add_backend_log(f"[Spoofer] Failed rotating {r.get('name')}: {r.get('error')}", level='warning', category='spoofer')
        return jsonify({'success': any(r.get('ok', False) for r in results), 'results': results})
    except Exception as e:
        add_backend_log(f"[Spoofer] HWID spoof error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/restore', methods=['POST', 'OPTIONS'])
def restore_rblx_identifiers():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        guids = data.get('guids', True)
        mac = data.get('mac', True)
        volume = data.get('volume', True)
        res = roblox_swap_manager.restore_identifiers(guids=guids, mac=mac, volume=volume)
        add_backend_log(f"[Spoofer] Restored genuine hardware identifiers from snapshot", level='info', category='spoofer')
        return jsonify(res)
    except Exception as e:
        add_backend_log(f"[Spoofer] Restore identifiers error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/restore-point', methods=['POST', 'OPTIONS'])
def create_rblx_restore_point():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        desc = data.get('desc', 'FRAM RblxSwap Pre-Spoof')
        res = roblox_swap_manager.create_system_restore_point(desc=desc)
        add_backend_log(f"[Spoofer] System restore point requested: {desc}", level='info', category='spoofer')
        return jsonify(res)
    except Exception as e:
        add_backend_log(f"[Spoofer] System restore point error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rblxswap/spoof-all', methods=['POST', 'OPTIONS'])
def spoof_rblx_all():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        guids = data.get('guids', True)
        volume = data.get('volume', False)
        mac = data.get('mac', False)
        all_adapters = data.get('all_adapters', False)
        adapter_desc = data.get('adapter_desc')
        adapter_name = data.get('adapter_name')
        custom_mac = data.get('custom_mac')
        mirror_oui = data.get('mirror_oui', True)
        restart = data.get('restart', True)
        create_restore_point = data.get('create_restore_point', False)
        restore_point_desc = data.get('restore_point_desc', 'FRAM RblxSwap Pre-Spoof')
        res = roblox_swap_manager.spoof_all(
            guids=guids,
            volume=volume,
            mac=mac,
            all_adapters=all_adapters,
            adapter_desc=adapter_desc,
            adapter_name=adapter_name,
            custom_mac=custom_mac,
            mirror_oui=mirror_oui,
            restart=restart,
            create_restore_point=create_restore_point,
            restore_point_desc=restore_point_desc
        )
        if res.get('success'):
            add_backend_log("[Spoofer] Hardware & MAC spoof completed successfully", level='info', category='spoofer')
        else:
            add_backend_log(f"[Spoofer] Hardware & MAC spoof failed: {res.get('error')}", level='warning', category='spoofer')
        return jsonify(res)
    except Exception as e:
        add_backend_log(f"[Spoofer] Unified spoof error: {str(e)}", level='error', category='spoofer')
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    if platform.system() == 'Windows':
        import socketserver
        socketserver.TCPServer.allow_reuse_address = False

    max_bind_attempts = 10
    for attempt in range(max_bind_attempts):
        try:
            app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
            break
        except OSError as e:
            if attempt < max_bind_attempts - 1:
                time.sleep(0.6)
            else:
                print(f"[ERROR] Could not bind backend to port {port}: {e}")
                sys.exit(1)