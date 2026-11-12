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
import random
import time
import threading
import platform
import ctypes
from datetime import datetime
import subprocess
from typing import Dict, List, Any, Optional, Tuple
import atexit
import signal
import psutil

if platform.system() == "Windows":
    try:
        import win32gui  # type: ignore[import-untyped,import-not-found]
        import win32con  # type: ignore[import-untyped,import-not-found]
        import win32process  # type: ignore[import-untyped,import-not-found]
    except ImportError:
        win32gui = win32con = win32process = None
else:
    win32gui = win32con = win32process = None
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

webhook_manager = WebhookManager(get_data_folder())
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
    add_backend_log("Unhandled API Error occurred", level='error', category='api', source='flask_api')
    return jsonify({"error": "Internal server error"}), 500

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5050",
    "http://127.0.0.1:5050",
    "tauri://localhost",
    "https://tauri.localhost",
    "http://tauri.localhost",
    "asset://localhost",
    r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    r"^https?://tauri\.localhost(:\d+)?$",
    r"^tauri://.*$"
]
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

_TRUSTED_ORIGIN_RE = re.compile(
    r"^(https?://(localhost|127\.0\.0\.1|\[::1\]|tauri\.localhost)(:\d+)?|tauri://[a-zA-Z0-9._-]*|asset://[a-zA-Z0-9._-]*)(\/.*)?$",
    re.IGNORECASE
)

def _is_trusted_local_origin(val: str) -> bool:
    if not val or val == 'null':
        return True
    v = val.strip().rstrip('/')
    if v in ALLOWED_ORIGINS:
        return True
    return bool(_TRUSTED_ORIGIN_RE.match(v))

API_AUTH_TOKEN = os.environ.get('FRAM_API_TOKEN') or secrets.token_urlsafe(48)
_BACKEND_START_TIME = time.time()
_INITIAL_PPID = os.getppid()

def _write_backend_pid(active_port=None):
    try:
        data_folder = get_data_folder()
        os.makedirs(data_folder, exist_ok=True)
        pid_path = os.path.join(data_folder, '.backend_pid')
        resolved_port = int(active_port if active_port is not None else os.environ.get('PORT', 5050))
        pid_info = {
            'pid': os.getpid(),
            'ppid': _INITIAL_PPID,
            'parent_pid': os.environ.get('FRAM_PARENT_PID'),
            'port': resolved_port,
            'started_at': _BACKEND_START_TIME,
            'executable': sys.executable
        }
        with open(pid_path, 'w', encoding='utf-8') as pf:
            json.dump(pid_info, pf)
            pf.flush()
            os.fsync(pf.fileno())
    except Exception as e:
        print(f"[WARNING] Could not write backend PID file: {e}")

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
    if level in ('error', 'fatal', 'critical') and source != 'webhook_manager':
        try:
            webhook_manager.notify_log(level, message)
        except Exception:
            pass

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
            '/api/system/platform',
            '/api/system/diagnostics',
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
            '/api/system/platform',
            '/api/system/logs',
            '/api/system/shutdown',
            '/api/system/diagnostics',
            '/api/system/last-error',
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
        self._lock = threading.Lock()

    def enable(self) -> bool:
        with self._lock:
            if platform.system() != "Windows":
                if not self.is_enabled:
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
        with self._lock:
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

def get_place_name(place_id) -> Optional[str]:
    if not place_id:
        return None
    try:
        data = load_data()
        for g in data.get('games', []):
            if str(g.get('placeId') or '').strip() == str(place_id).strip():
                return g.get('name')
    except Exception:
        pass
    return None

def _rejoin_launch_callback(session, attempt_number):
    mgr = get_account_manager()
    if not mgr:
        return False
    uname = session.username
    place_id = session.place_id
    rejoin_behavior = str(getattr(session, 'rejoin_launch_behavior', 'rejoin_same_server') or 'rejoin_same_server').strip().lower()
    if rejoin_behavior == 'rejoin_same_game':
        p_server = ""
        j_server = ""
    else:
        p_server = session.private_server_link
        j_server = session.server_job_id
    version = session.version_path
    mode = session.launch_mode
    launch_res = mgr.launch_roblox(
        username=uname,
        game_id=place_id,
        private_server_id=p_server,
        server_job_id=j_server,
        version=version,
        launch_mode=mode,
        preserve_rejoin_attempts=True,
        return_details=True
    )
    launched = launch_res[0] if isinstance(launch_res, tuple) else launch_res
    launch_err = launch_res[1] if isinstance(launch_res, tuple) and len(launch_res) > 1 else ""
    if not launched and launch_err:
        err_lower = str(launch_err).lower()
        auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
        if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
            new_status = "banned" if "banned" in err_lower else "expired"
            update_account_status(uname, new_status)
    if launched:
        now_ts = time.time()
        record_launch_event(uname)
        uname_lower = uname.lower()
        prev_info = last_launch_info.get(uname_lower, {})
        last_launch_info[uname_lower] = {
            'place_id': place_id or prev_info.get('place_id', ''),
            'server_id': (j_server or p_server) or prev_info.get('server_id', ''),
            'server_mode': prev_info.get('server_mode', 'jobid' if j_server else 'vip'),
            'version': version if version is not None else prev_info.get('version'),
            'launch_mode': mode or prev_info.get('launch_mode', 'game'),
            'timestamp': now_ts
        }
        last_launch_times[uname_lower] = now_ts
        if auto_arranger.is_enabled():
            auto_arranger.trigger_delayed_arrange(2.5)
        if headless_manager.is_enabled():
            headless_manager.trigger_delayed_headless()
        invalidate_instances_cache()
        acc_meta = mgr.accounts.get(uname, {}) if mgr and hasattr(mgr, 'accounts') else {}
        p_name = get_place_name(place_id)
        webhook_manager.notify_rejoin(
            uname,
            place_id or "Home",
            reason=f"Auto-rejoin monitor trigger (attempt {attempt_number})",
            display_name=acc_meta.get('display_name'),
            user_id=acc_meta.get('user_id'),
            avatar_url=acc_meta.get('avatar_url'),
            place_name=p_name
        )
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

def _auto_rejoin_log_hook(msg: str):
    print(msg)
    try:
        m = re.match(r"^\[AUTO REJOIN\]\s+([^:]+):\s+(.+)$", str(msg or ""))
        if m:
            uname = m.group(1).strip()
            detail = m.group(2).strip()
            detail_lower = detail.lower()
            if "disconnect detected" in detail_lower or "max rejoin attempts reached" in detail_lower:
                webhook_manager.notify_crash(uname, reason=detail)
    except Exception:
        pass

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
            log_callback=_auto_rejoin_log_hook
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
                last_account_decryption_error = "Decryption failed. Please check master password."
                exc_type, exc_value, exc_tb = sys.exc_info()
                error_detector.record_exception(exc_type or ValueError, e, exc_tb, source="account_manager_init")
            else:
                last_account_decryption_error = "Account manager initialization failed."
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
_LOAD_DATA_LOCK = threading.RLock()

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
    now = time.time()
    with _DATA_CACHE_LOCK:
        if not force_reload and _DATA_CACHE is not None and (now - _DATA_CACHE_TIME) < _DATA_CACHE_TTL:
            return _clone_data_fast(_DATA_CACHE)

    with _LOAD_DATA_LOCK:
        now = time.time()
        with _DATA_CACHE_LOCK:
            if not force_reload and _DATA_CACHE is not None and (now - _DATA_CACHE_TIME) < _DATA_CACHE_TTL:
                return _clone_data_fast(_DATA_CACHE)
        return _load_data_unlocked(force_reload)


def _load_data_unlocked(force_reload: bool = False) -> Dict[str, Any]:
    global _DATA_CACHE, _DATA_CACHE_TIME, last_account_decryption_error

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
            'autoUpdateToPreReleases': False,
            'autoUpdateToLatestRelease': True,
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
            'headlessEcoQoS': True,
            'headlessFpsCap': 15,
            'headlessGraphicsOpt': True,
            'headlessDetectionDelaySeconds': 0,
            'antiAfkEnabled': False,
            'antiAfkIntervalMinutes': 10,
            'antiAfkKeyName': 'M1',
            'antiAfkKeyCode': 0,
            'antiAfkShowNextLabel': False,
            'preferredRegion': '',
            'serverPerAccount': False,
            'pick_server_per_account': False,
            'randomServer': False,
            'randomizeServerJobIds': False
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
                        'id': account_data.get('id') or (int(hashlib.sha256(username.encode('utf-8')).hexdigest()[:7], 16)),
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
                last_account_decryption_error = "Decryption failed. Please check master password."
                exc_type, exc_value, exc_tb = sys.exc_info()
                error_detector.record_exception(exc_type or ValueError, e, exc_tb, source="account_manager_load")
            else:
                last_account_decryption_error = "Failed to load accounts."

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
    if platform.system() == "Darwin":
        try:
            import plistlib
            plist_dir = os.path.expanduser("~/Library/LaunchAgents")
            plist_path = os.path.join(plist_dir, "com.forkedaccountmanager.app.plist")
            if not enable:
                if os.path.exists(plist_path):
                    os.remove(plist_path)
                return

            exe_path = "/Applications/Forked Account Manager.app/Contents/MacOS/FRAM"
            cur = os.path.abspath(sys.executable)
            if ".app/Contents/" in cur:
                app_bundle = cur.split(".app/Contents/")[0] + ".app"
                candidate_bin = os.path.join(app_bundle, "Contents", "MacOS", "FRAM")
                if os.path.isfile(candidate_bin):
                    exe_path = candidate_bin

            os.makedirs(plist_dir, exist_ok=True)
            plist_data = {
                "Label": "com.forkedaccountmanager.app",
                "ProgramArguments": [exe_path],
                "RunAtLoad": True,
                "KeepAlive": False,
            }
            with open(plist_path, "wb") as f:
                plistlib.dump(plist_data, f)
        except Exception as e:
            print(f"Error syncing macOS LaunchAgent: {e}")
        return

    if platform.system() != "Windows":
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Forked Account Manager"

        existing_val = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as rkey:
                existing_val, _ = winreg.QueryValueEx(rkey, app_name)
        except FileNotFoundError:
            existing_val = None
        except OSError:
            existing_val = None

        if enable:
            exe_path = sys.executable
            base_dir = os.path.dirname(os.path.abspath(exe_path))
            for search_dir in (base_dir, os.path.dirname(base_dir), os.path.dirname(os.path.dirname(base_dir))):
                found_gui = False
                for gui_name in ("FRAM.exe", "Forked Account Manager.exe", "forked-account-manager.exe"):
                    candidate = os.path.join(search_dir, gui_name)
                    if os.path.isfile(candidate):
                        exe_path = candidate
                        found_gui = True
                        break
                if found_gui:
                    break
            desired_val = f'"{exe_path}"'
            if existing_val == desired_val:
                return
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as wkey:
                winreg.SetValueEx(wkey, app_name, 0, winreg.REG_SZ, desired_val)
        else:
            if existing_val is None:
                return
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as wkey:
                try:
                    winreg.DeleteValue(wkey, app_name)
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"Error syncing startup registry: {e}")

def update_account_status(username: str, new_status: str) -> bool:
    if not username:
        return False
    norm_status = str(new_status or "expired").strip().lower()
    if norm_status not in ("valid", "expired", "banned"):
        norm_status = "expired"

    updated_any = False
    old_status = None
    manager = get_account_manager()
    if manager and hasattr(manager, "accounts") and isinstance(manager.accounts, dict):
        for acc_key in list(manager.accounts.keys()):
            if acc_key.lower() == username.lower():
                old_status = manager.accounts[acc_key].get("status")
                manager.accounts[acc_key]["status"] = norm_status
                try:
                    manager.save_accounts()
                except Exception as save_err:
                    print(f"Error saving account status to manager: {save_err}")
                updated_any = True
                break

    try:
        with data_transaction() as txn:
            data = txn.data or {}
            for acc in data.get("accounts", []):
                if isinstance(acc, dict) and str(acc.get("username", "")).strip().lower() == username.strip().lower():
                    if old_status is None:
                        old_status = acc.get("status")
                    acc["status"] = norm_status
                    updated_any = True
                    break
            if updated_any:
                txn.save()
    except Exception as txn_err:
        print(f"Error saving account status via transaction: {txn_err}")

    invalidate_data_cache()
    if updated_any and norm_status in ("expired", "banned"):
        try:
            webhook_manager.notify_account_status_change(username, norm_status, old_status=old_status)
        except Exception:
            pass
    return updated_any

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
        log_detailed_error("Failed to bulk import cookies", exc=e)
        return jsonify({'success': False, 'error': 'Failed to bulk import cookies'}), 500

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
        log_detailed_error("Failed to reorder accounts", exc=e)
        return jsonify({'error': 'Failed to reorder accounts'}), 500

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
        elif server_mode == "random":
            p_server = ""
            j_server = ""
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

        random_server = bool(
            req_data.get('randomServer')
            if 'randomServer' in req_data
            else (
                req_data.get('random_server')
                if 'random_server' in req_data
                else (
                    settings.get('randomServer')
                    if 'randomServer' in settings
                    else (
                        settings.get('randomizeServerJobIds', False)
                        or (server_mode == 'random')
                    )
                )
            )
        )

        normalized_launch_mode = str(launch_mode or 'game').strip().lower()
        is_game_launch = normalized_launch_mode not in ('join_user', 'user')

        clean_place_id = str(place_id or '').strip()
        if not clean_place_id.isdigit():
            digit_match = re.search(r'(\d{4,15})', clean_place_id)
            if digit_match:
                clean_place_id = digit_match.group(1)

        if clean_place_id:
            place_id = clean_place_id

        should_pick_server = bool(pref_region or server_per_acc or random_server or server_mode == 'random')

        if should_pick_server and clean_place_id and not p_server and not j_server and is_game_launch:
            try:
                acc_cookie = manager.accounts[username].get('cookie', '')
                pool_key = f"{clean_place_id}_{pref_region.lower()}"
                now = time.time()
                with server_job_pool_lock:
                    cached_pool = server_job_pool_cache.get(pool_key)
                    if (
                        not cached_pool
                        or (now - cached_pool.get('timestamp', 0) > 120)
                        or not cached_pool.get('all_jobs')
                    ):
                        fetched = RobloxAPI.get_public_server_job_candidates(
                            place_id=clean_place_id,
                            max_pages=3,
                            preferred_region=pref_region,
                            roblosecurity_cookie=acc_cookie
                        ) or []
                        if fetched:
                            cached_pool = {
                                'all_jobs': list(fetched),
                                'available_jobs': list(fetched),
                                'timestamp': now
                            }
                            server_job_pool_cache[pool_key] = cached_pool

                    if cached_pool and cached_pool.get('all_jobs'):
                        all_jobs = cached_pool['all_jobs']
                        if server_per_acc:
                            if not cached_pool.get('available_jobs'):
                                cached_pool['available_jobs'] = list(all_jobs)
                            if cached_pool['available_jobs']:
                                j_server = cached_pool['available_jobs'].pop(0)
                            else:
                                j_server = random.choice(all_jobs)
                        elif random_server or server_mode == 'random':
                            j_server = random.choice(all_jobs)
                        else:
                            j_server = all_jobs[0]

                        if j_server:
                            server_id = j_server
                            print(f"[INFO] Server selection (place='{clean_place_id}', region='{pref_region}', per_account={server_per_acc}, random={random_server}) assigned Job ID: {j_server}")
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
            target_pid = req_data.get('pid')
            with _INSTANCES_TRACKER_LOCK:
                if target_pid:
                    try:
                        _CLOSED_OR_CRASHED_INSTANCES.pop(int(target_pid), None)
                    except Exception:
                        pass
                if username:
                    u_norm = str(username).strip().lower()
                    for opid, odata in list(_CLOSED_OR_CRASHED_INSTANCES.items()):
                        if str(odata.get('username') or '').strip().lower() == u_norm:
                            _CLOSED_OR_CRASHED_INSTANCES.pop(opid, None)
            acc_meta = manager.accounts.get(username, {}) if manager and hasattr(manager, 'accounts') else {}
            p_name = get_place_name(place_id)
            webhook_manager.notify_launch(
                username,
                place_id=place_id,
                job_id=server_id,
                display_name=acc_meta.get('display_name'),
                user_id=acc_meta.get('user_id'),
                avatar_url=acc_meta.get('avatar_url'),
                place_name=p_name
            )
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
        err_lower = str(launch_error or "").lower()
        auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
        if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
            new_status = "banned" if "banned" in err_lower else "expired"
            update_account_status(username, new_status)
            return jsonify({
                'success': False,
                'error': launch_error or f"Roblox login session for @{username} has expired",
                'status': new_status,
                'username': username
            }), 400
        return jsonify({'success': False, 'error': launch_error or "Roblox isn't installed"}), 400
    except Exception as e:
        print(f"[ERROR] Launch account failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

last_manual_kill_timestamp = 0.0
last_launch_times = {}
last_launch_info = {}

_TRACKED_ACTIVE_GAME_INSTANCES: Dict[int, Dict[str, Any]] = {}
_CLOSED_OR_CRASHED_INSTANCES: Dict[int, Dict[str, Any]] = {}
_MANUALLY_KILLED_PIDS: Dict[int, float] = {}
_INSTANCES_TRACKER_LOCK = threading.RLock()
_LAST_NOTIFIED_EXIT_PIDS: Dict[int, float] = {}

def resolve_place_name(place_id: Any) -> Optional[str]:
    """Look up friendly game/place name from saved games by place ID."""
    if not place_id:
        return None
    try:
        p_str = str(place_id).strip()
        data = load_data()
        for g in data.get('games', []):
            if str(g.get('placeId') or g.get('place_id') or '').strip() == p_str:
                return g.get('name')
    except Exception:
        pass
    return None

@app.route('/api/roblox/kill', methods=['POST', 'OPTIONS'])
def kill_roblox_processes():
    global last_manual_kill_timestamp
    if request.method == 'OPTIONS':
        return '', 200
    try:
        last_manual_kill_timestamp = time.time()
        with _INSTANCES_TRACKER_LOCK:
            _CLOSED_OR_CRASHED_INSTANCES.clear()
            _TRACKED_ACTIVE_GAME_INSTANCES.clear()
        invalidate_instances_cache()
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
        log_detailed_error("Failed to retrieve Roblox versions", exc=e)
        return jsonify({'success': False, 'versions': [], 'error': 'Failed to retrieve Roblox versions'})

@app.route('/api/roblox/launch-app', methods=['POST', 'OPTIONS'])
def launch_roblox_app():
    """Launch Roblox application or a specific installed version directly"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        version_path = req_data.get('versionPath') or req_data.get('version_path') or ''
        version_name = req_data.get('version') or ''

        if platform.system() == 'Darwin':
            allowed_bundles = {}
            for default_app in ('/Applications/Roblox.app', os.path.expanduser('~/Applications/Roblox.app')):
                if os.path.isdir(default_app):
                    allowed_bundles[default_app.lower()] = default_app
                    allowed_bundles[os.path.realpath(default_app).lower()] = default_app
                    allowed_bundles['roblox.app'] = default_app

            for v in RobloxAPI.get_installed_versions():
                vp = v.get('path', '')
                if vp and os.path.isdir(vp):
                    norm_vp = os.path.realpath(vp)
                    allowed_bundles[vp.lower()] = norm_vp
                    allowed_bundles[norm_vp.lower()] = norm_vp
                    if v.get('version'):
                        allowed_bundles[str(v['version']).lower()] = norm_vp

            target_bundle = None
            req_token = str(version_path or version_name or '').strip().lower()
            if req_token:
                target_bundle = allowed_bundles.get(req_token)

            if not target_bundle and allowed_bundles:
                target_bundle = allowed_bundles.get('/applications/roblox.app') or next(iter(allowed_bundles.values()), None)

            if target_bundle and os.path.isdir(target_bundle) and RobloxAPI._is_safe_roblox_path(target_bundle):
                subprocess.Popen(['open', '-n', '-a', target_bundle], close_fds=True)
                return jsonify({'success': True, 'message': f'Launched {os.path.basename(target_bundle)}'})
            return jsonify({'success': False, 'error': "Roblox isn't installed"}), 404

        allowed_executables = {}
        installed_versions = RobloxAPI.get_installed_versions()
        for v in installed_versions:
            v_dir = v.get('path', '')
            if not v_dir:
                continue
            for cand in ['RobloxPlayerBeta.exe', 'RobloxPlayerLauncher.exe']:
                c_path = os.path.join(v_dir, cand)
                if os.path.isfile(c_path):
                    allowed_executables[cand.lower()] = c_path
                    allowed_executables[c_path.lower()] = c_path
                    allowed_executables[v_dir.lower()] = c_path
                    if v.get('version'):
                        allowed_executables[str(v['version']).lower()] = c_path
                    break

        for bootstrapper in RobloxAPI.BOOTSTRAPPER_CLIENTS:
            b_root = os.path.expandvars(bootstrapper.get('root', ''))
            b_launcher = os.path.join(b_root, bootstrapper.get('launcher', ''))
            if os.path.isfile(b_launcher):
                allowed_executables[b_launcher.lower()] = b_launcher
                allowed_executables[b_root.lower()] = b_launcher
                allowed_executables[str(bootstrapper.get('name', '')).lower()] = b_launcher

        target_exe = None
        requested_token = str(version_path or version_name or '').strip().lower()
        if requested_token:
            target_exe = allowed_executables.get(requested_token)

        if not target_exe and installed_versions:
            for cand in ['RobloxPlayerBeta.exe', 'RobloxPlayerLauncher.exe']:
                c_path = os.path.join(installed_versions[0].get('path', ''), cand)
                if os.path.isfile(c_path):
                    target_exe = c_path
                    break

        creation_flags = 0
        if platform.system() == 'Windows':
            creation_flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)

        if target_exe and os.path.isfile(target_exe):
            subprocess.Popen([target_exe], creationflags=creation_flags, close_fds=True)
            return jsonify({'success': True, 'message': f'Launched {os.path.basename(target_exe)}'})

        if platform.system() == 'Windows':
            try:
                os.startfile('roblox://')
                return jsonify({'success': True, 'message': 'Launched Roblox via protocol handler'})
            except Exception as pe:
                return jsonify({'success': False, 'error': "Roblox isn't installed"}), 404

        return jsonify({'success': False, 'error': "Roblox isn't installed"}), 404
    except Exception as e:
        log_detailed_error("Failed to launch Roblox application", exc=e)
        return jsonify({'success': False, 'error': 'Failed to launch Roblox application'}), 500

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

        if not target_path and not version_name:
            return jsonify({'success': False, 'error': 'Path or version is required'}), 400

        from utils.paths import get_root_app_dir
        fram_versions_root = os.path.abspath(os.path.join(get_root_app_dir(), 'RobloxVersions'))
        allowed_roots = [
            os.path.abspath(os.path.expandvars(r'%LOCALAPPDATA%\Roblox\Versions')),
            fram_versions_root,
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
                if vp and os.path.abspath(os.path.expandvars(vp)) not in ('/Applications', os.path.expanduser('~/Applications')):
                    allowed_roots.append(os.path.abspath(os.path.expandvars(vp)))
        except Exception:
            pass

        allowed_exact_paths = [
            '/Applications/Roblox.app',
            os.path.abspath(os.path.expanduser('~/Applications/Roblox.app')),
        ]

        installed_map = {}
        for v in RobloxAPI.get_installed_versions():
            p = v.get('path')
            if p:
                norm_p = os.path.abspath(os.path.realpath(p))
                installed_map[norm_p.lower()] = norm_p
                installed_map[p.lower()] = norm_p
                if v.get('version'):
                    installed_map[str(v['version']).lower()] = norm_p

        requested_token = str(target_path or version_name or '').strip().lower()
        real_target = installed_map.get(requested_token)
        if not real_target:
            cand_norm = os.path.abspath(os.path.realpath(str(target_path).strip()))
            for exact in allowed_exact_paths:
                if cand_norm.lower() == exact.lower():
                    real_target = exact
                    break

        if not real_target:
            return jsonify({'success': False, 'error': 'Version folder not found or not an installed version'}), 404

        target_to_delete = None
        if real_target in allowed_exact_paths:
            target_to_delete = real_target
        else:
            for root in allowed_roots:
                real_root = os.path.abspath(os.path.realpath(root))
                if real_target.startswith(real_root + os.sep) and real_target != real_root:
                    target_to_delete = real_target
                    break

        if not target_to_delete:
            return jsonify({'success': False, 'error': 'Forbidden deletion path'}), 403

        shutil.rmtree(target_to_delete)
        return jsonify({'success': True, 'message': f'Successfully uninstalled {version_name or os.path.basename(target_to_delete)}'})
    except Exception as e:
        log_detailed_error("Failed to uninstall Roblox version", exc=e)
        return jsonify({'success': False, 'error': 'Failed to uninstall Roblox version'}), 500

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
        err_lower = str(launch_error or "").lower()
        auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
        if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
            new_status = "banned" if "banned" in err_lower else "expired"
            update_account_status(username, new_status)
            return jsonify({
                'success': False,
                'error': launch_error or f"Roblox login session for @{username} has expired",
                'status': new_status,
                'username': username
            }), 400
        return jsonify({'success': False, 'error': launch_error or "Failed to open browser"}), 400
    except Exception as e:
        log_detailed_error("Failed to open browser", exc=e)
        return jsonify({'success': False, 'error': 'Failed to open browser'}), 500

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
        log_detailed_error("Failed to validate accounts", exc=e)
        return jsonify({'error': 'Failed to validate accounts'}), 500

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
        log_detailed_error("Failed to validate account", exc=e)
        return jsonify({'error': 'Failed to validate account'}), 500

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
    except urllib.error.URLError as e:
        log_detailed_error("BloxGen connection error", exc=e)
        return {'success': False, 'message': 'BloxGen connection error'}, 502
    except Exception as e:
        log_detailed_error("BloxGen request failed", exc=e)
        return {'success': False, 'message': 'BloxGen request failed'}, 502

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
    is_active = bool(multi_instance_controller.is_enabled) if platform.system() != "Windows" else (len(multi_instance_controller.mutex_handles) > 0)
    return jsonify({
        'success': True,
        'enabled': enabled,
        'active': is_active
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

    is_active = bool(multi_instance_controller.is_enabled) if platform.system() != "Windows" else (len(multi_instance_controller.mutex_handles) > 0)
    return jsonify({
        'success': True,
        'enabled': new_state,
        'active': is_active,
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
        log_detailed_error("Failed to toggle headless mode", exc=e)
        return jsonify({'success': False, 'error': 'Failed to toggle headless mode'}), 500

@app.route('/api/headless/apply', methods=['POST', 'OPTIONS'])
def apply_headless_now():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        res = headless_manager.apply_pass(force_trim=True, force_hide_all=True)
        return jsonify({
            'success': True,
            'pids': res.get('pids', 0),
            'hidden': res.get('hidden', 0),
            'priority': res.get('priority', 0),
            'trimmed': res.get('trimmed', 0),
            'message': f"Applied headless mode: hidden {res.get('hidden', 0)} window(s), trimmed {res.get('trimmed', 0)} process(es)"
        })
    except Exception as e:
        log_detailed_error("Failed to apply headless mode", exc=e)
        return jsonify({'success': False, 'error': 'Failed to apply headless mode'}), 500

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
        log_detailed_error("Failed to restore headless windows", exc=e)
        return jsonify({'success': False, 'error': 'Failed to restore headless windows'}), 500

@app.route('/api/anti-afk/status', methods=['GET', 'OPTIONS'])
def get_anti_afk_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify(anti_afk_manager.get_status())
    except Exception as e:
        log_detailed_error("Failed to get Anti-AFK status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get Anti-AFK status'}), 500

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
            if 'antiAfkDuration' in req_data:
                try:
                    settings['antiAfkDuration'] = max(0.05, min(10.0, float(req_data['antiAfkDuration'])))
                except (TypeError, ValueError):
                    pass
            txn.save()
        anti_afk_manager.sync_overlay()
        return jsonify(anti_afk_manager.get_status())
    except Exception as e:
        log_detailed_error("Failed to update Anti-AFK settings", exc=e)
        return jsonify({'success': False, 'error': 'Failed to update Anti-AFK settings'}), 500

@app.route('/api/anti-afk/trigger', methods=['POST', 'OPTIONS'])
def trigger_anti_afk_pass():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        res = anti_afk_manager.trigger_pass()
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to trigger Anti-AFK pass", exc=e)
        return jsonify({'success': False, 'error': 'Failed to trigger Anti-AFK pass'}), 500

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
        return jsonify({'success': False, 'error': 'Failed to list browser extensions'}), 500

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
        return jsonify({'success': False, 'error': 'Invalid browser extension request'}), 400
    except Exception as e:
        log_detailed_error("Failed to toggle browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': 'Failed to toggle browser extension'}), 500

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
        return jsonify({'success': False, 'error': 'Invalid browser extension request'}), 400
    except Exception as e:
        log_detailed_error("Failed to delete browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': 'Failed to delete browser extension'}), 500

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

        if source in ('unpacked', 'crx', 'xpi'):
            user_home = os.path.abspath(os.path.realpath(os.path.expanduser('~')))
            norm_target_path = os.path.abspath(os.path.realpath(os.path.expanduser(path_or_id)))
            if not norm_target_path.startswith(user_home + os.sep):
                return jsonify({'success': False, 'error': 'Extension file/folder must reside within user home directory'}), 400
            path_or_id = norm_target_path

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
        return jsonify({'success': False, 'error': 'Invalid browser extension request'}), 400
    except Exception as e:
        log_detailed_error("Failed to add browser extension", exc=e, source="extensions_api")
        return jsonify({'success': False, 'error': 'Failed to add browser extension'}), 500

def _choose_folder_native(prompt_title: str) -> str:
    if platform.system() == "Darwin":
        safe_title = str(prompt_title or "Select Folder").replace('"', '\\"')
        res = subprocess.run(
            ["osascript", "-e", f'POSIX path of (choose folder with prompt "{safe_title}")'],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().rstrip("/")
        return ""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_selected = filedialog.askdirectory(title=prompt_title)
        root.destroy()
        return folder_selected or ""
    except Exception:
        if platform.system() == "Windows":
            safe_title = str(prompt_title or "Select Folder").replace("'", "''")
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$f.Description = '{safe_title}'; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                timeout=120,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        return ""

def _choose_file_native(prompt_title: str, file_type: str = "any") -> str:
    if platform.system() == "Darwin":
        safe_title = str(prompt_title or "Select File").replace('"', '\\"')
        res = subprocess.run(
            ["osascript", "-e", f'POSIX path of (choose file with prompt "{safe_title}")'],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return ""
    try:
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
        file_selected = filedialog.askopenfilename(title=prompt_title, filetypes=filetypes)
        root.destroy()
        return file_selected or ""
    except Exception:
        if platform.system() == "Windows":
            safe_title = str(prompt_title or "Select File").replace("'", "''")
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                f"$f.Title = '{safe_title}'; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                timeout=120,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        return ""

@app.route('/api/extensions/browse-folder', methods=['POST', 'GET', 'OPTIONS'])
def browse_extension_folder_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        folder_selected = _choose_folder_native("Select Unpacked Extension Folder")
        if folder_selected:
            return jsonify({'success': True, 'path': folder_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        log_detailed_error("Failed to browse extension folder", exc=e)
        return jsonify({'success': False, 'cancelled': True, 'error': 'Failed to browse extension folder'}), 200

@app.route('/api/extensions/browse-file', methods=['POST', 'GET', 'OPTIONS'])
def browse_extension_file_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        file_type = str(data.get('file_type') or 'any').lower()
        file_selected = _choose_file_native("Select Extension File", file_type)
        if file_selected:
            return jsonify({'success': True, 'path': file_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        log_detailed_error("Failed to browse extension file", exc=e)
        return jsonify({'success': False, 'cancelled': True, 'error': 'Failed to browse extension file'}), 200

recent_launches = []

def record_launch_event(username):
    global recent_launches, last_launch_times
    now = time.time()
    recent_launches.append({
        'id': str(uuid.uuid4()),
        'username': username,
        'timestamp': now,
        'claimed_pid': None,
    })
    recent_launches = [l for l in recent_launches if now - l['timestamp'] < 180]
    if username:
        last_launch_times[username.lower()] = now

def get_currently_running_usernames():
    running = set()
    try:
        pid_ctime_list = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                pname = str(proc.info.get('name') or '').lower()
                if pname not in ('robloxplayerbeta.exe', 'robloxplayerbeta', 'robloxplayer', 'robloxplayer.exe'):
                    continue
                pid = int(proc.info['pid'])
                creation_time_sec = proc.info.get('create_time') or None
                pid_ctime_list.append((pid, creation_time_sec))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if pid_ctime_list:
            resolved_map = resolve_active_pids_accounts(pid_ctime_list)
            for acc_info in resolved_map.values():
                if acc_info and acc_info.get("username"):
                    running.add(str(acc_info["username"]).lower())
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

                tracked_pid = info.get('pid')
                if tracked_pid and _is_roblox_pid(tracked_pid):
                    continue

                if manager and getattr(manager, 'auto_rejoin_monitor', None):
                    monitor = manager.auto_rejoin_monitor
                    active_sessions = getattr(monitor, 'active_sessions', {}) or {}
                    active_sess = active_sessions.get(uname)
                    if active_sess is None:
                        for s_uname, s_entry in active_sessions.items():
                            if str(s_uname).lower() == uname_lower:
                                active_sess = s_entry
                                break
                    if active_sess is not None:
                        if getattr(active_sess, 'rejoin_in_progress', False):
                            continue
                        if getattr(active_sess, 'intentionally_stopped', False):
                            continue
                        if getattr(active_sess, 'disabled_reason', ''):
                            continue
                        if hasattr(monitor, '_is_manual_stop_active') and monitor._is_manual_stop_active(active_sess.username):
                            continue
                        sess_pid = int(getattr(active_sess, 'pid', 0) or 0)
                        if sess_pid > 0 and _is_roblox_pid(sess_pid):
                            continue
                        if (
                            getattr(monitor, '_running', False)
                            and getattr(active_sess, 'auto_rejoin', False)
                            and (getattr(active_sess, 'has_seen_in_game', False) or getattr(active_sess, 'has_seen_process_alive', False))
                        ):
                            continue

                place_id = info.get('place_id', '')
                server_id = info.get('server_id', '')
                server_mode = info.get('server_mode', 'vip')
                version = info.get('version')
                launch_mode = info.get('launch_mode', 'game')

                if behavior == 'rejoin_same_game':
                    p_server = ''
                    j_server = ''
                else:
                    p_server = acc.get('vip_server', '')
                    if not p_server and server_mode != 'jobid':
                        p_server = server_id
                    j_server = server_id if server_mode == "jobid" else ""

                try:
                    launch_res = manager.launch_roblox(
                        username=uname,
                        game_id=place_id,
                        private_server_id=p_server,
                        server_job_id=j_server,
                        version=version,
                        launch_mode=launch_mode,
                        preserve_rejoin_attempts=True,
                        return_details=True
                    )
                    launched = launch_res[0] if isinstance(launch_res, tuple) else launch_res
                    launch_err = launch_res[1] if isinstance(launch_res, tuple) and len(launch_res) > 1 else ""
                    if not launched and launch_err:
                        err_lower = str(launch_err).lower()
                        auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
                        if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
                            new_status = "banned" if "banned" in err_lower else "expired"
                            update_account_status(uname, new_status)
                    if launched:
                        now_ts = time.time()
                        record_launch_event(uname)
                        info.pop('pid', None)
                        info['timestamp'] = now_ts
                        last_launch_times[uname_lower] = now_ts
                        invalidate_instances_cache()
                        acc_meta = manager.accounts.get(uname, {}) if manager and hasattr(manager, 'accounts') else {}
                        p_name = get_place_name(place_id)
                        webhook_manager.notify_rejoin(
                            uname,
                            place_id or "Home",
                            reason="Client process disconnected",
                            display_name=acc_meta.get('display_name'),
                            user_id=acc_meta.get('user_id'),
                            avatar_url=acc_meta.get('avatar_url'),
                            place_name=p_name
                        )
                    time.sleep(delay)
                except Exception as e:
                    print(f"[ERROR] Auto-rejoin launch failed for {uname}: {e}")
        except Exception as e:
            print(f"[ERROR] background_auto_rejoin_worker error: {e}")

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
                launch_res = manager.launch_roblox(
                    username=uname,
                    game_id=place_id,
                    private_server_id=p_server,
                    server_job_id=job_id,
                    version=version,
                    launch_mode='game' if place_id else 'app',
                    return_details=True
                )
                launched = launch_res[0] if isinstance(launch_res, tuple) else launch_res
                launch_err = launch_res[1] if isinstance(launch_res, tuple) and len(launch_res) > 1 else ""
                if not launched and launch_err:
                    err_lower = str(launch_err).lower()
                    auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
                    if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
                        new_status = "banned" if "banned" in err_lower else "expired"
                        update_account_status(uname, new_status)
                if launched:
                    success_count += 1
                    now_ts = time.time()
                    record_launch_event(uname)
                    last_launch_times[uname_lower] = now_ts
                    last_launch_info[uname_lower] = {
                        'timestamp': now_ts,
                        'place_id': place_id,
                        'server_id': vip_server,
                        'server_mode': server_mode,
                        'version': version,
                        'launch_mode': 'game' if place_id else 'app'
                    }
                    invalidate_instances_cache()
                time.sleep(delay)
            except Exception as e:
                print(f"[ERROR] Group auto-relaunch failed for {uname}: {e}")

        summary = f"Relaunched {success_count}/{len(matching_accounts)} accounts in group '{group}'"
        group_auto_relaunch_state['last_relaunch_summary'] = summary
        print(f"[INFO] Group auto-relaunch completed: {summary}")
        try:
            webhook_manager.notify_group_relaunch(
                group_name=group,
                success_count=success_count,
                total_count=len(matching_accounts),
                accounts_list=[acc.get('username') for acc in matching_accounts if acc.get('username')]
            )
        except Exception:
            pass
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
        log_detailed_error("Failed to get auto-relaunch status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get auto-relaunch status'}), 500

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
        log_detailed_error("Failed to update auto-relaunch settings", exc=e)
        return jsonify({'success': False, 'error': 'Failed to update auto-relaunch settings'}), 500

@app.route('/api/auto-relaunch/trigger', methods=['POST', 'OPTIONS'])
def trigger_auto_relaunch_now():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        threading.Thread(target=run_group_auto_relaunch, daemon=True).start()
        return jsonify({'success': True, 'message': 'Group auto-relaunch triggered.'})
    except Exception as e:
        log_detailed_error("Failed to trigger auto-relaunch", exc=e)
        return jsonify({'success': False, 'error': 'Failed to trigger auto-relaunch'}), 500

_PID_INFO_CACHE = {}
_PID_INFO_CACHE_LOCK = threading.Lock()
_PID_CMDLINE_CACHE = {}

def resolve_pid_place_id(pid: int, acc_info: dict = None) -> str:
    if acc_info and acc_info.get('place_id'):
        return str(acc_info['place_id'])
    for uname_key, info in last_launch_info.items():
        if info.get('pid') == pid and info.get('place_id'):
            return str(info['place_id'])
    if acc_info and acc_info.get('username'):
        uname_key = acc_info['username'].lower()
        info = last_launch_info.get(uname_key)
        if info and info.get('place_id'):
            return str(info['place_id'])
    return ""

def _load_accounts_lookup(accounts_by_user=None, accounts_by_id=None):
    if accounts_by_user is not None and accounts_by_id is not None:
        return accounts_by_user, accounts_by_id
    accounts_by_user = {}
    accounts_by_id = {}
    manager = get_account_manager()
    if manager and hasattr(manager, 'accounts') and isinstance(manager.accounts, dict):
        for uname, acc in manager.accounts.items():
            if uname and isinstance(acc, dict):
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc
    try:
        app_data = load_data()
        for acc in app_data.get('accounts', []):
            if not isinstance(acc, dict):
                continue
            uname = str(acc.get('username') or '').strip()
            if uname:
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc
    except Exception:
        pass
    return accounts_by_user, accounts_by_id

def _format_account_result(uname: str, acc: Optional[dict], place_id: str = "") -> Dict[str, Any]:
    real_uname = str((acc.get('username') if acc and acc.get('username') else uname) or uname).strip()
    resolved_place = str(place_id or '').strip()
    if not resolved_place and real_uname:
        resolved_place = str(last_launch_info.get(real_uname.lower(), {}).get('place_id') or '').strip()
    return {
        'username': real_uname,
        'display_name': (acc.get('display_name') if acc and acc.get('display_name') else None) or real_uname,
        'avatar_url': acc.get('avatar_url') if acc else None,
        'user_id': acc.get('user_id') if acc else None,
        'place_id': resolved_place
    }

def _assign_exclusive_pid(uname: str, pid: int, place_id: str = "", verified: bool = False):
    uname_clean = str(uname or '').strip()
    uname_key = uname_clean.lower()
    pid_int = int(pid)
    if not uname_key or pid_int <= 0:
        return

    for other_key, other_info in list(last_launch_info.items()):
        if other_key != uname_key and other_info.get('pid') == pid_int:
            other_info.pop('pid', None)

    if uname_key in last_launch_info:
        old_pid = last_launch_info[uname_key].get('pid')
        if old_pid and int(old_pid) != pid_int:
            with _PID_INFO_CACHE_LOCK:
                old_cached = _PID_INFO_CACHE.get(int(old_pid))
                if isinstance(old_cached, dict) and not old_cached.get('verified'):
                    _PID_INFO_CACHE.pop(int(old_pid), None)
        last_launch_info[uname_key]['pid'] = pid_int
        if place_id:
            last_launch_info[uname_key]['place_id'] = str(place_id)
    else:
        last_launch_info[uname_key] = {
            'pid': pid_int,
            'place_id': str(place_id or ''),
            'server_id': '',
            'server_mode': 'vip',
            'version': None,
            'launch_mode': 'game',
            'timestamp': time.time()
        }

    with _PID_INFO_CACHE_LOCK:
        for c_pid, c_entry in list(_PID_INFO_CACHE.items()):
            if c_pid == pid_int or not isinstance(c_entry, dict):
                continue
            c_data = c_entry.get('data')
            if isinstance(c_data, dict) and str(c_data.get('username') or '').strip().lower() == uname_key:
                if verified or not c_entry.get('verified'):
                    _PID_INFO_CACHE.pop(c_pid, None)

    manager = get_account_manager()
    if manager and hasattr(manager, 'update_active_session_pid'):
        try:
            manager.update_active_session_pid(uname_clean, pid_int)
        except Exception:
            pass

def _get_roblox_logs_dir() -> str:
    if platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Logs/Roblox")
    return os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "Roblox", "logs")

def _inspect_pid_cmdline(pid: int, creation_time_sec: Optional[float] = None) -> Dict[str, str]:
    pid_int = int(pid)
    cached = _PID_CMDLINE_CACHE.get(pid_int)
    if cached and (creation_time_sec is None or cached.get('ctime') is None or abs(creation_time_sec - cached['ctime']) < 5.0):
        return cached.get('parsed', {})

    parsed: Dict[str, str] = {}
    try:
        proc = psutil.Process(pid_int)
        cmdline = proc.cmdline() or []
        cmd_str = " ".join(str(a) for a in cmdline)
        if cmd_str:
            bt_match = re.search(r'(?:browsertrackerid|browserTrackerId)[:=](\d{6,20})', cmd_str, re.IGNORECASE)
            if bt_match:
                parsed['browser_tracker_id'] = bt_match.group(1)
            lt_match = re.search(r'\+launchtime:(\d{10,16})', cmd_str, re.IGNORECASE)
            if lt_match:
                parsed['launch_time_ms'] = lt_match.group(1)
            gi_match = re.search(r'\+gameinfo:([^+\s&"\']+)', cmd_str, re.IGNORECASE)
            if gi_match:
                parsed['auth_ticket'] = urllib.parse.unquote(gi_match.group(1))
            pl_match = re.search(r'[?&]placeId=(\d{4,16})', cmd_str, re.IGNORECASE)
            if pl_match:
                parsed['place_id'] = pl_match.group(1)
    except Exception:
        pass

    if len(_PID_CMDLINE_CACHE) > 200:
        _PID_CMDLINE_CACHE.clear()
    _PID_CMDLINE_CACHE[pid_int] = {'ctime': creation_time_sec, 'parsed': parsed}
    return parsed

def _discover_pid_to_player_log_map(logs_dir: str, target_pids: Optional[set] = None) -> Dict[int, str]:
    pid_to_log: Dict[int, str] = {}
    if target_pids:
        for pid in target_pids:
            try:
                proc = psutil.Process(int(pid))
                for f in proc.open_files():
                    fpath = str(getattr(f, 'path', '') or '')
                    fname_lower = os.path.basename(fpath).lower()
                    if fname_lower.endswith('.log') and 'crashhandler' not in fname_lower and 'installer' not in fname_lower:
                        if os.path.isfile(fpath):
                            pid_to_log[int(pid)] = fpath
                            break
            except Exception:
                continue

    if not os.path.isdir(logs_dir):
        return pid_to_log

    try:
        ch_files = [
            os.path.join(logs_dir, n)
            for n in os.listdir(logs_dir)
            if n.lower().endswith('.log') and 'crashhandler' in n.lower()
        ]
        ch_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for ch_path in ch_files[:30]:
            try:
                with open(ch_path, 'r', encoding='utf-8', errors='ignore') as f:
                    ch_content = f.read(16384)
                pid_match = re.search(r'(?:--annotation=PID=|\bPID=)(\d+)', ch_content)
                if not pid_match:
                    continue
                ch_pid = int(pid_match.group(1))
                if target_pids and ch_pid not in target_pids:
                    continue
                if ch_pid in pid_to_log:
                    continue
                sentry_match = re.search(r'--sentryLogPath\s+([^\s"\']+\.log)', ch_content)
                if not sentry_match:
                    sentry_match = re.search(r'--attachment=attachment_[^=\s]+=([^\s"\']+\.log)', ch_content)
                if sentry_match:
                    player_log = sentry_match.group(1).strip()
                    if not os.path.isabs(player_log):
                        player_log = os.path.join(logs_dir, os.path.basename(player_log))
                    if os.path.isfile(player_log):
                        pid_to_log[ch_pid] = player_log
            except Exception:
                continue
    except Exception:
        pass

    return pid_to_log

def _parse_player_log_start_time(log_path: str) -> Optional[float]:
    import calendar
    fname = os.path.basename(log_path)
    ts_match = re.search(r'_(\d{8}T\d{6}Z)_Player_', fname, re.IGNORECASE)
    if ts_match:
        try:
            tm = time.strptime(ts_match.group(1).upper(), "%Y%m%dT%H%M%SZ")
            return float(calendar.timegm(tm))
        except Exception:
            pass
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline(512)
        iso_match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z', first_line)
        if iso_match:
            tm = time.strptime(iso_match.group(1), "%Y-%m-%dT%H:%M:%S")
            frac = float("0." + iso_match.group(2)) if iso_match.group(2) else 0.0
            return float(calendar.timegm(tm)) + frac
    except Exception:
        pass
    try:
        st = os.stat(log_path)
        return float(getattr(st, 'st_birthtime', 0.0) or st.st_ctime or st.st_mtime)
    except Exception:
        return None

def _parse_player_log_file(log_path: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not log_path or not os.path.isfile(log_path):
        return result
    try:
        file_size = os.path.getsize(log_path)
        head_limit = 196608
        tail_limit = 196608
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            if file_size <= (head_limit + tail_limit):
                content = f.read()
            else:
                head_text = f.read(head_limit)
                f.seek(max(head_limit, file_size - tail_limit))
                tail_text = f.read(tail_limit)
                content = head_text + "\n" + tail_text

        uid_match = re.search(r'\buserid:([1-9]\d*)', content, re.IGNORECASE)
        if not uid_match:
            uid_match = re.search(r'"UserId"(?:%3a|:)\s*([1-9]\d*)', content, re.IGNORECASE)
        if uid_match:
            result['user_id'] = uid_match.group(1)

        uname_match = re.search(r'"UserName"(?:%3a|:)(?:%22|"|\\")([^"%\s\\,]+)', content, re.IGNORECASE)
        if uname_match:
            result['username'] = uname_match.group(1)

        bt_match = re.search(r'(?:browsertrackerid[:=]|browserTrackerId\s*=\s*\[?|"BrowserTrackerId"(?:%3a|:)\s*)(\d{6,20})', content, re.IGNORECASE)
        if bt_match:
            result['browser_tracker_id'] = bt_match.group(1)

        lt_match = re.search(r'\+launchtime:(\d{10,16})', content, re.IGNORECASE)
        if lt_match:
            result['launch_time_ms'] = lt_match.group(1)

        place_matches = re.findall(r'(?:placeid|place_id|placeId|"PlaceId")(?:%3a|[:=\s"])+([1-9]\d{3,16})', content, re.IGNORECASE)
        if place_matches:
            result['place_id'] = place_matches[-1]
    except Exception:
        pass
    return result

def _match_launch_record(
    records: List[Dict[str, Any]],
    pid: Optional[int] = None,
    browser_tracker_id: str = "",
    launch_time_ms: str = "",
    auth_ticket: str = "",
    claimed_record_ids: Optional[set] = None,
) -> Optional[Dict[str, Any]]:
    claimed_ids = claimed_record_ids or set()
    if pid and int(pid) > 0:
        for r in reversed(records):
            if r.get('record_id') in claimed_ids:
                continue
            if r.get('spawned_pid') and int(r['spawned_pid']) == int(pid):
                return r
    if browser_tracker_id:
        for r in reversed(records):
            if r.get('record_id') in claimed_ids:
                continue
            if r.get('browser_tracker_id') == browser_tracker_id:
                return r
    if launch_time_ms:
        for r in reversed(records):
            if r.get('record_id') in claimed_ids:
                continue
            if r.get('launch_time_ms') == launch_time_ms:
                return r
    if auth_ticket:
        for r in reversed(records):
            if r.get('record_id') in claimed_ids:
                continue
            if r.get('auth_ticket') and r.get('auth_ticket') == auth_ticket:
                return r
    return None

def resolve_active_pids_accounts(
    pid_ctime_list: List[Tuple[int, Optional[float]]],
    accounts_by_user: Optional[Dict[str, Any]] = None,
    accounts_by_id: Optional[Dict[str, Any]] = None,
) -> Dict[int, Optional[Dict[str, Any]]]:
    if not pid_ctime_list:
        return {}

    accounts_by_user, accounts_by_id = _load_accounts_lookup(accounts_by_user, accounts_by_id)
    ordered_pids = sorted(
        [(int(p), float(ct) if ct else 0.0) for p, ct in pid_ctime_list if p],
        key=lambda item: (item[1] if item[1] > 0 else float('inf'), item[0])
    )
    active_pid_set = {p for p, _ in ordered_pids}

    resolved_by_pid: Dict[int, Dict[str, Any]] = {}
    verified_by_pid: Dict[int, bool] = {}
    log_path_by_pid: Dict[int, str] = {}
    claimed_usernames: set = set()
    claimed_record_ids: set = set()
    claimed_log_paths: set = set()

    launch_records = RobloxAPI.get_recent_launch_records(max_age_sec=3600.0)

    # Step 0: Check already-verified cache entries
    with _PID_INFO_CACHE_LOCK:
        for pid, ctime in ordered_pids:
            c_entry = _PID_INFO_CACHE.get(pid)
            if not isinstance(c_entry, dict) or not c_entry.get('verified'):
                continue
            c_ctime = c_entry.get('ctime') or 0.0
            if ctime > 0 and c_ctime > 0 and abs(ctime - c_ctime) >= 5.0:
                _PID_INFO_CACHE.pop(pid, None)
                continue
            c_data = c_entry.get('data')
            if isinstance(c_data, dict) and c_data.get('username'):
                uname_lower = str(c_data['username']).strip().lower()
                if uname_lower not in claimed_usernames:
                    c_log = c_entry.get('log_path') or ''
                    updated_data = dict(c_data)
                    if c_log and os.path.isfile(c_log):
                        log_path_by_pid[pid] = c_log
                        claimed_log_paths.add(os.path.realpath(c_log))
                        log_info = _parse_player_log_file(c_log)
                        if log_info.get('place_id'):
                            updated_data['place_id'] = log_info['place_id']
                    acc = accounts_by_user.get(uname_lower)
                    if acc:
                        updated_data = _format_account_result(
                            acc.get('username') or updated_data['username'],
                            acc,
                            updated_data.get('place_id') or ''
                        )
                    resolved_by_pid[pid] = updated_data
                    verified_by_pid[pid] = True
                    claimed_usernames.add(uname_lower)
                    if c_entry.get('record_id'):
                        claimed_record_ids.add(c_entry['record_id'])

    unresolved_pids = [(p, ct) for p, ct in ordered_pids if p not in resolved_by_pid]
    logs_dir = _get_roblox_logs_dir()

    if unresolved_pids:
        pid_to_log = _discover_pid_to_player_log_map(logs_dir, {p for p, _ in unresolved_pids})
        for pid, lpath in pid_to_log.items():
            real_lpath = os.path.realpath(lpath)
            if real_lpath not in claimed_log_paths:
                log_path_by_pid[pid] = lpath
                claimed_log_paths.add(real_lpath)

        # Also gather recent Player logs in logs_dir for fallback timestamp/token matching
        recent_player_logs: List[Tuple[str, Optional[float], Dict[str, str]]] = []
        if os.path.isdir(logs_dir):
            try:
                p_files = [
                    os.path.join(logs_dir, n)
                    for n in os.listdir(logs_dir)
                    if n.lower().endswith('.log') and '_player_' in n.lower() and 'crashhandler' not in n.lower()
                ]
                p_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                for pf in p_files[:25]:
                    real_pf = os.path.realpath(pf)
                    if real_pf in claimed_log_paths:
                        continue
                    l_start = _parse_player_log_start_time(pf)
                    l_parsed = _parse_player_log_file(pf)
                    recent_player_logs.append((pf, l_start, l_parsed))
            except Exception:
                pass

        # Step 1: Deterministic verification via Process Cmdline, Spawned PID, or Mapped Player Log
        for pid, ctime in list(unresolved_pids):
            cmd_info = _inspect_pid_cmdline(pid, ctime if ctime > 0 else None)
            matched_rec = _match_launch_record(
                launch_records,
                pid=pid,
                browser_tracker_id=cmd_info.get('browser_tracker_id', ''),
                launch_time_ms=cmd_info.get('launch_time_ms', ''),
                auth_ticket=cmd_info.get('auth_ticket', ''),
                claimed_record_ids=claimed_record_ids,
            )

            # If pid doesn't have a mapped log yet, see if any unclaimed Player log matches cmd_info or matched_rec or creation time
            if pid not in log_path_by_pid and recent_player_logs:
                target_bt = cmd_info.get('browser_tracker_id') or (matched_rec.get('browser_tracker_id') if matched_rec else '')
                target_lt = cmd_info.get('launch_time_ms') or (matched_rec.get('launch_time_ms') if matched_rec else '')
                for pf, l_start, l_parsed in recent_player_logs:
                    real_pf = os.path.realpath(pf)
                    if real_pf in claimed_log_paths:
                        continue
                    if (target_bt and l_parsed.get('browser_tracker_id') == target_bt) or (
                        target_lt and l_parsed.get('launch_time_ms') == target_lt
                    ):
                        log_path_by_pid[pid] = pf
                        claimed_log_paths.add(real_pf)
                        break

                if pid not in log_path_by_pid and ctime > 0:
                    best_pf = None
                    best_delta = 999.0
                    for pf, l_start, _ in recent_player_logs:
                        real_pf = os.path.realpath(pf)
                        if real_pf in claimed_log_paths or not l_start:
                            continue
                        delta = l_start - ctime
                        if -3.0 <= delta <= 15.0 and abs(delta) < best_delta:
                            best_delta = abs(delta)
                            best_pf = pf
                    if best_pf:
                        log_path_by_pid[pid] = best_pf
                        claimed_log_paths.add(os.path.realpath(best_pf))

            log_info = _parse_player_log_file(log_path_by_pid[pid]) if pid in log_path_by_pid else {}
            if not matched_rec and log_info:
                matched_rec = _match_launch_record(
                    launch_records,
                    browser_tracker_id=log_info.get('browser_tracker_id', ''),
                    launch_time_ms=log_info.get('launch_time_ms', ''),
                    claimed_record_ids=claimed_record_ids,
                )

            resolved_acc = None
            resolved_uname = ""
            if log_info.get('user_id') and log_info['user_id'] in accounts_by_id:
                resolved_acc = accounts_by_id[log_info['user_id']]
                resolved_uname = resolved_acc.get('username') or ''
            elif log_info.get('username'):
                uname_cand = log_info['username']
                resolved_acc = accounts_by_user.get(uname_cand.lower())
                resolved_uname = (resolved_acc.get('username') if resolved_acc else uname_cand) or uname_cand
            elif matched_rec and matched_rec.get('username'):
                uname_cand = matched_rec['username']
                resolved_acc = accounts_by_user.get(uname_cand.lower())
                resolved_uname = (resolved_acc.get('username') if resolved_acc else uname_cand) or uname_cand

            if resolved_uname and resolved_uname.lower() not in claimed_usernames:
                place_val = (
                    log_info.get('place_id')
                    or cmd_info.get('place_id')
                    or (matched_rec.get('place_id') if matched_rec else '')
                    or last_launch_info.get(resolved_uname.lower(), {}).get('place_id', '')
                )
                res_dict = _format_account_result(resolved_uname, resolved_acc, place_val)
                if not res_dict.get('user_id') and log_info.get('user_id'):
                    res_dict['user_id'] = log_info['user_id']
                resolved_by_pid[pid] = res_dict
                verified_by_pid[pid] = True
                claimed_usernames.add(resolved_uname.lower())
                if matched_rec and matched_rec.get('record_id'):
                    claimed_record_ids.add(matched_rec['record_id'])
                    RobloxAPI.claim_launch_record_pid(matched_rec['record_id'], pid)

    # Step 2: Check existing tracked PID in last_launch_info / AutoRejoinMonitor.active_sessions (only if unclaimed)
    unresolved_pids = [(p, ct) for p, ct in ordered_pids if p not in resolved_by_pid]
    if unresolved_pids:
        manager = get_account_manager()
        monitor = getattr(manager, 'auto_rejoin_monitor', None) if manager else None
        active_sessions = getattr(monitor, 'active_sessions', {}) if monitor else {}

        for pid, ctime in list(unresolved_pids):
            matched_uname = ""
            matched_place = ""
            for uname_key, info in last_launch_info.items():
                if info.get('pid') == pid and uname_key not in claimed_usernames:
                    matched_uname = uname_key
                    matched_place = str(info.get('place_id') or '')
                    break

            if not matched_uname and active_sessions:
                for uname, session in active_sessions.items():
                    if int(getattr(session, 'pid', 0) or 0) == pid and uname.lower() not in claimed_usernames:
                        matched_uname = uname
                        matched_place = str(getattr(session, 'place_id', '') or last_launch_info.get(uname.lower(), {}).get('place_id', ''))
                        break

            if matched_uname:
                acc = accounts_by_user.get(matched_uname.lower())
                res_dict = _format_account_result(matched_uname, acc, matched_place)
                resolved_by_pid[pid] = res_dict
                verified_by_pid[pid] = False
                claimed_usernames.add(matched_uname.lower())

    # Step 3: Exclusive FIFO Launch Matching for brand-new unverified processes
    unresolved_pids = [(p, ct) for p, ct in ordered_pids if p not in resolved_by_pid]
    if unresolved_pids:
        for pid, ctime in unresolved_pids:
            if ctime <= 0:
                continue
            chosen_uname = ""
            chosen_place = ""
            chosen_rec_id = ""

            # Check RobloxAPI launch records in FIFO order (oldest unclaimed launch preceding process creation)
            for rec in launch_records:
                rec_id = rec.get('record_id')
                rec_uname = str(rec.get('username') or '').strip()
                rec_uname_lower = rec_uname.lower()
                if not rec_uname or rec_uname_lower in claimed_usernames or rec_id in claimed_record_ids:
                    continue
                rec_claimed_pid = rec.get('claimed_pid')
                if rec_claimed_pid and int(rec_claimed_pid) != pid and int(rec_claimed_pid) in active_pid_set:
                    continue
                rec_ts = float(rec.get('timestamp') or 0.0)
                delta = ctime - rec_ts
                if -3.0 <= delta <= 45.0:
                    chosen_uname = rec_uname
                    chosen_place = str(rec.get('place_id') or '')
                    chosen_rec_id = str(rec_id or '')
                    break

            if not chosen_uname:
                for l_item in recent_launches:
                    l_uname = str(l_item.get('username') or '').strip()
                    l_uname_lower = l_uname.lower()
                    if not l_uname or l_uname_lower in claimed_usernames:
                        continue
                    l_claimed = l_item.get('claimed_pid')
                    if l_claimed and int(l_claimed) != pid and int(l_claimed) in active_pid_set:
                        continue
                    l_ts = float(l_item.get('timestamp') or 0.0)
                    delta = ctime - l_ts
                    if -3.0 <= delta <= 45.0:
                        chosen_uname = l_uname
                        l_item['claimed_pid'] = pid
                        break

            if chosen_uname:
                acc = accounts_by_user.get(chosen_uname.lower())
                res_dict = _format_account_result(chosen_uname, acc, chosen_place)
                resolved_by_pid[pid] = res_dict
                verified_by_pid[pid] = False
                claimed_usernames.add(chosen_uname.lower())
                if chosen_rec_id:
                    claimed_record_ids.add(chosen_rec_id)
                    RobloxAPI.claim_launch_record_pid(chosen_rec_id, pid)

    # Step 4: Persist exclusive PID bindings and update cache
    final_output: Dict[int, Optional[Dict[str, Any]]] = {}
    now_ts = time.time()
    for pid, ctime in ordered_pids:
        res_data = resolved_by_pid.get(pid)
        is_ver = bool(verified_by_pid.get(pid, False))
        if res_data and res_data.get('username'):
            _assign_exclusive_pid(
                res_data['username'],
                pid,
                place_id=res_data.get('place_id') or '',
                verified=is_ver
            )
            with _PID_INFO_CACHE_LOCK:
                _PID_INFO_CACHE[pid] = {
                    'data': res_data,
                    'ctime': ctime if ctime > 0 else None,
                    'verified': is_ver,
                    'log_path': log_path_by_pid.get(pid, ''),
                    'checked_at': now_ts,
                }
        final_output[pid] = res_data

    return final_output

def resolve_pid_account(pid, creation_time_sec=None, accounts_by_user=None, accounts_by_id=None):
    try:
        target_pid = int(pid)
    except (TypeError, ValueError):
        return None

    with _PID_INFO_CACHE_LOCK:
        cached = _PID_INFO_CACHE.get(target_pid)
        if isinstance(cached, dict) and cached.get('verified'):
            cached_ctime = cached.get('ctime')
            if creation_time_sec is None or cached_ctime is None or abs(float(creation_time_sec) - float(cached_ctime)) < 5.0:
                return cached.get('data')

    pid_ctime_list: List[Tuple[int, Optional[float]]] = []
    seen_target = False
    try:
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                pname = str(proc.info.get('name') or '').lower()
                if pname not in ('robloxplayerbeta.exe', 'robloxplayerbeta', 'robloxplayer', 'robloxplayer.exe'):
                    continue
                p_id = int(proc.info['pid'])
                p_ct = proc.info.get('create_time') or (creation_time_sec if p_id == target_pid else None)
                pid_ctime_list.append((p_id, p_ct))
                if p_id == target_pid:
                    seen_target = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

    if not seen_target:
        if creation_time_sec is None:
            try:
                creation_time_sec = psutil.Process(target_pid).create_time()
            except Exception:
                pass
        pid_ctime_list.append((target_pid, creation_time_sec))

    resolved_map = resolve_active_pids_accounts(pid_ctime_list, accounts_by_user, accounts_by_id)
    return resolved_map.get(target_pid)

_MUTED_PIDS = set()
_MUTED_PIDS_LOCK = threading.Lock()

def set_process_audio_mute(pid: int, mute: bool) -> Tuple[bool, str]:
    pid = int(pid)
    with _MUTED_PIDS_LOCK:
        if mute:
            _MUTED_PIDS.add(pid)
        else:
            _MUTED_PIDS.discard(pid)

    if platform.system() == "Windows":
        try:
            ps_script = f"""
$code = @'
using System;
using System.Runtime.InteropServices;
namespace FRAMAudio {{
    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice {{
        int Activate(ref Guid id, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object interfacePointer);
    }}
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator {{
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
    }}
    [Guid("77AA99A0-1BD6-484F-BC0A-F16E11C6052F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioSessionManager2 {{
        int dummy1();
        int dummy2();
        int GetSessionEnumerator(out IAudioSessionEnumerator SessionEnum);
    }}
    [Guid("E2F5EE11-2070-4E59-AAEE-16729403DA9E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioSessionEnumerator {{
        int GetCount(out int SessionCount);
        int GetSession(int SessionIndex, out IAudioSessionControl Session);
    }}
    [Guid("F4B1A599-7266-4319-A8CA-E70ACB11E8CD"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioSessionControl {{
        int dummy1(); int dummy2(); int dummy3(); int dummy4(); int dummy5(); int dummy6(); int dummy7(); int dummy8();
    }}
    [Guid("bfb79d95-7984-4546-98b9-4d69be44f104"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioSessionControl2 {{
        int dummy1(); int dummy2(); int dummy3(); int dummy4(); int dummy5(); int dummy6(); int dummy7(); int dummy8();
        int dummy9(); int dummy10(); int dummy11(); int dummy12(); int dummy13();
        int GetProcessId(out int RetVal);
    }}
    [Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface ISimpleAudioVolume {{
        int SetMasterVolume(float fLevel, ref Guid EventContext);
        int GetMasterVolume(out float pfLevel);
        int SetMute(bool bMute, ref Guid EventContext);
        int GetMute(out bool pbMute);
    }}
    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291433E")]
    class MMDeviceEnumeratorComObject {{ }}
    public class Muter {{
        public static bool SetMute(int targetPid, bool mute) {{
            try {{
                var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
                IMMDevice dev;
                enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
                var IID_IAudioSessionManager2 = new Guid("77AA99A0-1BD6-484F-BC0A-F16E11C6052F");
                object obj;
                dev.Activate(ref IID_IAudioSessionManager2, 23, IntPtr.Zero, out obj);
                var mgr = obj as IAudioSessionManager2;
                IAudioSessionEnumerator sessionEnum;
                mgr.GetSessionEnumerator(out sessionEnum);
                int count;
                sessionEnum.GetCount(out count);
                for (int i = 0; i < count; i++) {{
                    IAudioSessionControl ctl;
                    sessionEnum.GetSession(i, out ctl);
                    var ctl2 = ctl as IAudioSessionControl2;
                    if (ctl2 != null) {{
                        int sPid;
                        ctl2.GetProcessId(out sPid);
                        if (sPid == targetPid) {{
                            var vol = ctl as ISimpleAudioVolume;
                            if (vol != null) {{
                                Guid empty = Guid.Empty;
                                vol.SetMute(mute, ref empty);
                                return true;
                            }}
                        }}
                    }}
                }}
            }} catch {{ }}
            return false;
        }}
    }}
}}
'@
if (-not ([System.Management.Automation.PSTypeName]'FRAMAudio.Muter').Type) {{
    Add-Type -TypeDefinition $code
}}
[FRAMAudio.Muter]::SetMute({pid}, ${'true' if mute else 'false'})
"""
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5
            )
        except Exception:
            pass
    state_str = "Muted" if mute else "Unmuted"
    return True, f"{state_str} audio for PID {pid}"

_INSTANCES_CACHE: Optional[Dict[str, Any]] = None
_INSTANCES_CACHE_TIME: float = 0.0
_INSTANCES_CACHE_TTL: float = 1.5
_INSTANCES_CACHE_LOCK = threading.Lock()

def invalidate_instances_cache():
    global _INSTANCES_CACHE, _INSTANCES_CACHE_TIME
    with _INSTANCES_CACHE_LOCK:
        _INSTANCES_CACHE = None
        _INSTANCES_CACHE_TIME = 0.0

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
        if platform.system() in ("Windows", "Darwin"):
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

            if not procs_data and platform.system() == "Windows":
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

            game_pid_ctime_list = [
                (int(item['ProcessId']), item.get('CreationTimeSec'))
                for item in procs_data
                if not re.search(r'crashhandler', str(item.get('Name') or ''), re.IGNORECASE)
                and re.search(r'robloxplayer(?:beta)?(?:\.exe)?$', str(item.get('Name') or ''), re.IGNORECASE)
            ]
            resolved_accounts_map = (
                resolve_active_pids_accounts(game_pid_ctime_list, accounts_by_user, accounts_by_id)
                if game_pid_ctime_list
                else {}
            )

            for item in procs_data:
                pid = item['ProcessId']
                pname = item['Name']
                working_set = item['WorkingSetSize']
                creation_time_sec = item.get('CreationTimeSec')
                memory_mb = round(working_set / (1024 * 1024), 1)

                uptime_sec = 0
                if creation_time_sec and creation_time_sec > 0:
                    uptime_sec = max(0, int(now - creation_time_sec))

                with _MUTED_PIDS_LOCK:
                    is_muted = pid in _MUTED_PIDS

                inst_obj = {
                    "pid": pid,
                    "name": pname,
                    "status": "Running",
                    "memory_mb": memory_mb,
                    "created_at": str(creation_time_sec or ""),
                    "uptime_sec": uptime_sec,
                    "is_muted": is_muted
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
                elif re.search(r'robloxplayer(?:beta)?(?:\.exe)?$', pname, re.IGNORECASE):
                    inst_obj["process_type"] = "game"
                    acc_info = resolved_accounts_map.get(int(pid))
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

                    if inst_obj.get("place_id") and not inst_obj.get("place_name"):
                        inst_obj["place_name"] = resolve_place_name(inst_obj["place_id"])

                    is_hidden = False
                    if platform.system() == "Darwin":
                        is_hidden = pid in headless_manager.hidden_hwnds
                    elif platform.system() == "Windows" and win32gui:
                        try:
                            wins = headless_manager.get_roblox_windows(target_pids={pid}, include_hidden=True)
                            if wins:
                                is_hidden = all((hwnd in headless_manager.hidden_hwnds) or not win32gui.IsWindowVisible(hwnd) for hwnd in wins)
                        except Exception:
                            pass
                    inst_obj["is_hidden"] = is_hidden

                    game_instances.append(inst_obj)
                else:
                    inst_obj["process_type"] = "bootstrapper"
                    other_instances.append(inst_obj)

        active_pids = {inst["pid"] for inst in game_instances + crash_handlers + other_instances}
        with _MUTED_PIDS_LOCK:
            dead_muted = [p for p in _MUTED_PIDS if p not in active_pids]
            for p in dead_muted:
                _MUTED_PIDS.discard(p)
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

        # Update tracked active instances and merge with inactive (crashed/closed) instances
        with _INSTANCES_TRACKER_LOCK:
            for inst in game_instances:
                ipid = inst["pid"]
                _TRACKED_ACTIVE_GAME_INSTANCES[ipid] = inst.copy()
                _CLOSED_OR_CRASHED_INSTANCES.pop(ipid, None)
                if inst.get("username"):
                    u_norm = str(inst["username"]).strip().lower()
                    for opid, odata in list(_CLOSED_OR_CRASHED_INSTANCES.items()):
                        if str(odata.get("username") or "").strip().lower() == u_norm:
                            _CLOSED_OR_CRASHED_INSTANCES.pop(opid, None)

            inactive_instances = sorted(
                _CLOSED_OR_CRASHED_INSTANCES.values(),
                key=lambda x: x.get('closed_at', 0),
                reverse=True
            )

        crashed_count = sum(1 for inst in inactive_instances if inst.get('status') == 'Crashed')
        closed_count = sum(1 for inst in inactive_instances if inst.get('status') == 'Closed')
        all_game_instances = list(game_instances) + inactive_instances

        is_mutex_active = bool(multi_instance_controller.is_enabled) if platform.system() != "Windows" else (len(multi_instance_controller.mutex_handles) > 0)
        result_payload = {
            'success': True,
            'instances': all_game_instances,
            'activeCount': len(game_instances),
            'crashedCount': crashed_count,
            'closedCount': closed_count,
            'crashHandlers': crash_handlers,
            'otherInstances': other_instances,
            'count': len(all_game_instances),
            'crashHandlerCount': len(crash_handlers),
            'totalCpuPercent': total_roblox_cpu,
            'systemCpuPercent': system_cpu,
            'multiInstanceEnabled': app_settings.get('multiInstance', False),
            'autoTrimEnabled': app_settings.get('autoMemoryTrimEnabled', False),
            'autoTrimInterval': app_settings.get('autoMemoryTrimIntervalMinutes', 5),
            'mutexActive': is_mutex_active
        }
        with _INSTANCES_CACHE_LOCK:
            _INSTANCES_CACHE = result_payload
            _INSTANCES_CACHE_TIME = time.time()

        return jsonify(result_payload)
    except Exception as e:
        log_detailed_error("Failed to get running instances", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get running instances'}), 500

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
        log_detailed_error("Memory trim endpoint error", exc=e)
        return jsonify({'success': False, 'error': 'Failed to trim memory'}), 500

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
        log_detailed_error("Auto-arrange clients failed", exc=e)
        return jsonify({'success': False, 'count': 0, 'error': 'Failed to arrange clients'}), 500

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
        log_detailed_error("Failed to get monitors", exc=e)
        return jsonify({'success': False, 'monitors': [], 'error': 'Failed to get monitors'}), 500

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
        log_detailed_error("Failed to get auto-arrange status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get auto-arrange status'}), 500

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
        log_detailed_error("Failed to toggle auto-arrange", exc=e)
        return jsonify({'success': False, 'error': 'Failed to toggle auto-arrange'}), 500



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

_LAST_CRASH_HANDLER_DETECTED_TIME: float = 0.0

def terminate_crash_handlers(log_if_killed: bool = True):
    global _LAST_CRASH_HANDLER_DETECTED_TIME
    if platform.system() == "Windows":
        try:
            killed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pname = str(proc.info.get('name') or '').lower()
                    if 'robloxcrashhandler' in pname:
                        proc.kill()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if killed > 0:
                _LAST_CRASH_HANDLER_DETECTED_TIME = time.time()
                if log_if_killed:
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

def _detect_and_update_instance_exits():
    """Detect terminated Roblox instances, classify exit as crashed vs closed, update inactive tracking, and dispatch webhooks."""
    global last_manual_kill_timestamp, _TRACKED_ACTIVE_GAME_INSTANCES, _CLOSED_OR_CRASHED_INSTANCES, _MANUALLY_KILLED_PIDS, _LAST_NOTIFIED_EXIT_PIDS, _LAST_CRASH_HANDLER_DETECTED_TIME
    now_ts = time.time()

    # If the user performed a "kill all" recently (within 15 seconds), ignore all exits and clear inactive instances
    if (now_ts - last_manual_kill_timestamp) < 15.0:
        with _INSTANCES_TRACKER_LOCK:
            _CLOSED_OR_CRASHED_INSTANCES.clear()
            _TRACKED_ACTIVE_GAME_INSTANCES.clear()
        return

    # Clean up _MANUALLY_KILLED_PIDS older than 60s
    with _INSTANCES_TRACKER_LOCK:
        _MANUALLY_KILLED_PIDS = {k: v for k, v in _MANUALLY_KILLED_PIDS.items() if (now_ts - v) < 60.0}

    # Discover live game PIDs and active crash handlers
    running_game_pids = set()
    crash_handler_running = False
    crash_handler_target_pids = set()

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'ppid']):
            try:
                pname = str(proc.info.get('name') or '').lower()
                pid = proc.info['pid']
                if 'crashhandler' in pname:
                    crash_handler_running = True
                    _LAST_CRASH_HANDLER_DETECTED_TIME = now_ts
                    ppid = proc.info.get('ppid')
                    if ppid:
                        crash_handler_target_pids.add(ppid)
                    cmdline = proc.info.get('cmdline') or []
                    cmd_str = ' '.join(cmdline)
                    m = re.search(r'PID=(\d+)', cmd_str, re.IGNORECASE)
                    if m:
                        crash_handler_target_pids.add(int(m.group(1)))
                elif re.search(r'robloxplayer(?:beta)?(?:\.exe)?$', pname, re.IGNORECASE):
                    running_game_pids.add(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass

    exited_instances_to_notify = []

    with _INSTANCES_TRACKER_LOCK:
        # Check all tracked active instances to see if any have exited
        for pid, inst_data in list(_TRACKED_ACTIVE_GAME_INSTANCES.items()):
            if pid not in running_game_pids:
                # Process has exited!
                _TRACKED_ACTIVE_GAME_INSTANCES.pop(pid, None)

                # Skip if killed as part of manual kill all
                if (now_ts - last_manual_kill_timestamp) < 15.0:
                    continue

                # Skip if manually killed by user for this PID
                if pid in _MANUALLY_KILLED_PIDS or (now_ts - _MANUALLY_KILLED_PIDS.get(pid, 0.0) < 60.0):
                    continue

                # Determine whether it crashed or closed
                is_crash = (pid in crash_handler_target_pids) or crash_handler_running or ((now_ts - _LAST_CRASH_HANDLER_DETECTED_TIME) < 10.0)
                status = "Crashed" if is_crash else "Closed"
                exit_reason = "RobloxCrashHandler detected" if is_crash else "Client Process Closed / Disconnected"

                # Calculate final uptime
                uptime_sec = inst_data.get('uptime_sec', 0)
                created_at = inst_data.get('created_at')
                if created_at:
                    try:
                        ctime = float(created_at)
                        if ctime > 0:
                            uptime_sec = max(0, int(now_ts - ctime))
                    except Exception:
                        pass

                m, s = divmod(uptime_sec, 60)
                h, m = divmod(m, 60)
                uptime_str = f"{h}h {m}m" if h > 0 else (f"{m}m {s}s" if m > 0 else f"{s}s")

                inactive_record = dict(inst_data)
                inactive_record['status'] = status
                inactive_record['memory_mb'] = 0.0
                inactive_record['cpu_percent'] = 0.0
                inactive_record['uptime_sec'] = uptime_sec
                inactive_record['uptime_str'] = uptime_str
                inactive_record['closed_at'] = now_ts
                inactive_record['exit_reason'] = exit_reason

                _CLOSED_OR_CRASHED_INSTANCES[pid] = inactive_record

                # Prune inactive instances so map doesn't exceed 50 entries
                if len(_CLOSED_OR_CRASHED_INSTANCES) > 50:
                    oldest_pids = sorted(_CLOSED_OR_CRASHED_INSTANCES.keys(), key=lambda k: _CLOSED_OR_CRASHED_INSTANCES[k].get('closed_at', 0))[:-50]
                    for opid in oldest_pids:
                        _CLOSED_OR_CRASHED_INSTANCES.pop(opid, None)

                exited_instances_to_notify.append(inactive_record)

        # Clean up any inactive record whose account is currently running
        for pid in running_game_pids:
            active_info = _TRACKED_ACTIVE_GAME_INSTANCES.get(pid)
            if active_info and active_info.get('username'):
                u_norm = str(active_info['username']).strip().lower()
                for old_pid, old_record in list(_CLOSED_OR_CRASHED_INSTANCES.items()):
                    if str(old_record.get('username') or '').strip().lower() == u_norm:
                        _CLOSED_OR_CRASHED_INSTANCES.pop(old_pid, None)

    # Invalidate cache if any instance exited
    if exited_instances_to_notify:
        invalidate_instances_cache()

    # Dispatch webhooks outside the lock
    for inst in exited_instances_to_notify:
        pid = inst.get('pid')
        username = inst.get('username') or ''
        status = inst.get('status')
        exit_reason = inst.get('exit_reason')
        disp_name = inst.get('display_name')
        uid = inst.get('user_id')
        av_url = inst.get('avatar_url')
        place_id = inst.get('place_id')
        place_name = inst.get('place_name') or resolve_place_name(place_id)
        uptime_str = inst.get('uptime_str')

        add_backend_log(
            f"Roblox process PID {pid} ({disp_name or username or 'Unassigned'}) {status.lower()}: {exit_reason}",
            level='warn' if status == 'Crashed' else 'info',
            category='instances'
        )

        try:
            if status == "Crashed":
                webhook_manager.notify_crash(
                    username=username,
                    pid=pid,
                    reason=exit_reason,
                    display_name=disp_name,
                    user_id=uid,
                    avatar_url=av_url,
                    place_id=place_id,
                    place_name=place_name,
                    uptime_str=uptime_str,
                )
            else:
                webhook_manager.notify_closed(
                    username=username,
                    pid=pid,
                    reason=exit_reason,
                    display_name=disp_name,
                    user_id=uid,
                    avatar_url=av_url,
                    place_id=place_id,
                    place_name=place_name,
                    uptime_str=uptime_str,
                )
        except Exception as e:
            print(f"[WARN] Failed to send webhook for {status} PID {pid}: {e}")

def background_instance_tracker_worker():
    """Background worker to continuously track running instances and detect crashes or unexpected closures."""
    while True:
        try:
            time.sleep(2.5)
            _detect_and_update_instance_exits()
        except Exception as e:
            print(f"[ERROR] background_instance_tracker_worker error: {e}")

@app.route('/api/instances/kill-crash-handlers', methods=['POST', 'OPTIONS'])
def kill_all_crash_handlers():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        killed = terminate_crash_handlers(log_if_killed=True)
        return jsonify({'success': True, 'killed': killed, 'message': f'Terminated {killed} crash handler process(es)'})
    except Exception as e:
        log_detailed_error("Failed to terminate crash handlers", exc=e)
        return jsonify({'success': False, 'error': 'Failed to terminate crash handlers'}), 500

def _is_roblox_pid(pid):
    try:
        p = psutil.Process(int(pid))
        process_name = (p.name() or '').lower()
        return process_name in ALLOWED_PROCESS_NAMES or (process_name + '.exe') in ALLOWED_PROCESS_NAMES
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, TypeError):
        return False

@app.route('/api/instances/kill', methods=['POST', 'OPTIONS'])
def kill_specific_instance():
    """Kill a specific Roblox process by PID after verifying it is a Roblox process"""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        pid = req_data.get('pid')
        username = req_data.get('username')
        if not pid:
            return jsonify({'success': False, 'error': 'PID is required'}), 400

        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid PID'}), 400

        if not _is_roblox_pid(pid):
            return jsonify({'success': False, 'error': 'PID does not belong to a Roblox process'}), 403

        with _INSTANCES_TRACKER_LOCK:
            _MANUALLY_KILLED_PIDS[pid] = time.time()
            _TRACKED_ACTIVE_GAME_INSTANCES.pop(pid, None)
            _CLOSED_OR_CRASHED_INSTANCES.pop(pid, None)

        manager = get_account_manager()
        resolved_username = str(username or '').strip()

        if not resolved_username:
            try:
                acc_info = resolve_pid_account(pid)
                if acc_info and acc_info.get('username'):
                    resolved_username = str(acc_info.get('username')).strip()
            except Exception:
                pass

        if not resolved_username:
            for uname_k, l_info in list(last_launch_info.items()):
                if l_info.get('pid') == pid:
                    resolved_username = uname_k
                    break

        if not resolved_username and manager and getattr(manager, 'auto_rejoin_monitor', None):
            for candidate_uname, sess in list(getattr(manager.auto_rejoin_monitor, 'active_sessions', {}).items()):
                if int(getattr(sess, 'pid', 0) or 0) == pid:
                    resolved_username = candidate_uname
                    break

        if manager and getattr(manager, 'auto_rejoin_monitor', None):
            try:
                manager.auto_rejoin_monitor.mark_intentionally_stopped(username=resolved_username or None, pid=pid)
            except Exception:
                pass

        if resolved_username:
            uname_lower = resolved_username.lower()
            last_launch_info.pop(uname_lower, None)
            last_launch_times.pop(uname_lower, None)

            try:
                with data_transaction() as txn:
                    updated_ar = False
                    for acc in txn.data.get('accounts', []):
                        if str(acc.get('username', '')).lower() == uname_lower:
                            acc['auto_rejoin_enabled'] = False
                            updated_ar = True
                    if updated_ar:
                        txn.save()
                if manager and hasattr(manager, 'accounts') and isinstance(manager.accounts, dict):
                    for acc_key, acc_val in manager.accounts.items():
                        if str(acc_key).lower() == uname_lower and isinstance(acc_val, dict):
                            acc_val['auto_rejoin_enabled'] = False
                    try:
                        manager.save_accounts()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[WARN] Failed to disable auto_rejoin_enabled for {resolved_username}: {e}")

        if headless_manager:
            try:
                headless_manager.restored_pids.discard(int(pid))
                wins = headless_manager.get_roblox_windows(target_pids={pid}, include_hidden=True)
                for w in wins:
                    headless_manager.hidden_hwnds.discard(int(w))
                    headless_manager.restored_hwnds.discard(int(w))
            except Exception:
                pass

        if platform.system() == "Windows":
            res = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if res.returncode == 0:
                invalidate_instances_cache()
                return jsonify({
                    'success': True,
                    'message': f'Terminated process PID {pid}',
                    'username': resolved_username or None,
                    'auto_rejoin_disabled': bool(resolved_username)
                })
            else:
                return jsonify({'success': False, 'error': f'Failed to kill PID {pid}'}), 400
        else:
            res = subprocess.run(["kill", "-9", str(pid)], capture_output=True, text=True)
            invalidate_instances_cache()
            return jsonify({
                'success': True,
                'message': f'Terminated process PID {pid}',
                'username': resolved_username or None,
                'auto_rejoin_disabled': bool(resolved_username)
            })
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
            target_pid = req_data.get('pid')
            with _INSTANCES_TRACKER_LOCK:
                if target_pid:
                    try:
                        _CLOSED_OR_CRASHED_INSTANCES.pop(int(target_pid), None)
                    except Exception:
                        pass
                if username:
                    u_norm = str(username).strip().lower()
                    for opid, odata in list(_CLOSED_OR_CRASHED_INSTANCES.items()):
                        if str(odata.get('username') or '').strip().lower() == u_norm:
                            _CLOSED_OR_CRASHED_INSTANCES.pop(opid, None)
            acc_meta = manager.accounts.get(username, {}) if manager and hasattr(manager, 'accounts') else {}
            p_name = get_place_name(place_id)
            webhook_manager.notify_launch(
                username,
                place_id=place_id,
                job_id=server_id,
                display_name=acc_meta.get('display_name'),
                user_id=acc_meta.get('user_id'),
                avatar_url=acc_meta.get('avatar_url'),
                place_name=p_name
            )
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
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': f"Relaunched Roblox for @{username}"})
        err_lower = str(launch_error or "").lower()
        auth_terms = ("expired", "logged out", "cookie is invalid", "session is invalid", "cookie expired", "no login cookie", "invalid cookie", "401", "403")
        if any(term in err_lower for term in auth_terms) or "banned" in err_lower:
            new_status = "banned" if "banned" in err_lower else "expired"
            update_account_status(username, new_status)
            return jsonify({
                'success': False,
                'error': launch_error or f"Roblox login session for @{username} has expired",
                'status': new_status,
                'username': username
            }), 400
        return jsonify({'success': False, 'error': launch_error or "Roblox isn't installed"}), 400
    except Exception as e:
        print(f"[ERROR] Relaunch instance failed: {e}")
        return jsonify({'success': False, 'error': 'An internal error occurred'}), 500

@app.route('/api/instances/dismiss', methods=['POST', 'OPTIONS'])
def dismiss_instance():
    """Dismiss inactive crashed or closed instances from the Instance Manager view."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        req_data = request.json or {}
        dismiss_all = bool(req_data.get('all', False))
        pid = req_data.get('pid')

        with _INSTANCES_TRACKER_LOCK:
            if dismiss_all:
                count = len(_CLOSED_OR_CRASHED_INSTANCES)
                _CLOSED_OR_CRASHED_INSTANCES.clear()
                invalidate_instances_cache()
                return jsonify({'success': True, 'count': count, 'message': f'Dismissed {count} inactive instance(s)'})
            elif pid is not None:
                try:
                    pid_int = int(pid)
                    removed = _CLOSED_OR_CRASHED_INSTANCES.pop(pid_int, None)
                    invalidate_instances_cache()
                    return jsonify({'success': True, 'found': bool(removed), 'message': f'Dismissed instance PID {pid}'})
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'error': 'Invalid PID'}), 400
            else:
                return jsonify({'success': False, 'error': 'PID or all=True is required'}), 400
    except Exception as e:
        log_detailed_error("Failed to dismiss instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to dismiss instance'}), 500

def focus_instance(pid: int) -> Tuple[bool, str]:
    if platform.system() == "Darwin":
        try:
            headless_manager.restore_window(pid)
            headless_manager.restored_pids.add(int(pid))
            headless_manager.set_process_priority(pid, headless_manager._NORMAL_PRIORITY_CLASS)
            script = (
                f'tell application "System Events"\n'
                f'  repeat with p in (every process whose unix id is {int(pid)})\n'
                f'    set visible of p to true\n'
                f'    set frontmost of p to true\n'
                f'  end repeat\n'
                f'end tell'
            )
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                return True, "Window focused"
            return False, (res.stderr or "Failed to focus macOS window").strip()
        except Exception as e:
            log_detailed_error("Failed to focus macOS window", exc=e)
            return False, "Failed to focus window"

    if platform.system() != "Windows" or not win32gui or not win32process:
        return False, "Not supported on this platform"
    try:
        windows = headless_manager.get_roblox_windows(target_pids={pid}, include_hidden=True)
        if not windows:
            return False, f"No window found for PID {pid}"

        user32 = ctypes.windll.user32
        for hwnd in windows:
            headless_manager.restore_window(hwnd)
            headless_manager.restored_hwnds.add(int(hwnd))
            headless_manager.restored_pids.add(int(pid))
            headless_manager.set_process_priority(pid, headless_manager._NORMAL_PRIORITY_CLASS)

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, getattr(win32con, "SW_RESTORE", 9))
            else:
                win32gui.ShowWindow(hwnd, getattr(win32con, "SW_SHOW", 5))

            try:
                user32.LockSetForegroundWindow(2)
            except Exception:
                pass
            try:
                user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)

            if user32.GetForegroundWindow() != hwnd:
                try:
                    user32.keybd_event(0x12, 0, 0, 0)
                    user32.keybd_event(0x12, 0, 2, 0)
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        return True, "Window focused"
    except Exception as e:
        log_detailed_error("Failed to focus Windows window", exc=e)
        return False, "Failed to focus window"

def hide_instance(pid: int) -> Tuple[bool, str]:
    if platform.system() == "Darwin":
        try:
            headless_manager.restored_pids.discard(int(pid))
            headless_manager.restored_hwnds.discard(int(pid))
            if headless_manager.hide_window(pid):
                if headless_manager.is_idle_priority_enabled():
                    headless_manager.set_process_priority(pid, headless_manager._IDLE_PRIORITY_CLASS)
                return True, "Hidden 1 window(s)"
            return False, f"Failed to hide window for PID {pid}"
        except Exception as e:
            log_detailed_error("Failed to hide macOS window", exc=e)
            return False, "Failed to hide window"

    if platform.system() != "Windows" or not win32gui:
        return False, "Not supported on this platform"
    try:
        windows = headless_manager.get_roblox_windows(target_pids={pid}, include_hidden=False)
        if not windows:
            return False, f"No visible window found for PID {pid}"

        headless_manager.restored_pids.discard(int(pid))
        count = 0
        for hwnd in windows:
            headless_manager.restored_hwnds.discard(int(hwnd))
            if headless_manager.hide_window(hwnd):
                count += 1

        if headless_manager.is_idle_priority_enabled():
            headless_manager.set_process_priority(pid, headless_manager._IDLE_PRIORITY_CLASS)

        return True, f"Hidden {count} window(s)"
    except Exception as e:
        log_detailed_error("Failed to hide Windows window", exc=e)
        return False, "Failed to hide window"

def unhide_instance(pid: int) -> Tuple[bool, str]:
    if platform.system() == "Darwin":
        try:
            if headless_manager.restore_window(pid):
                headless_manager.restored_pids.add(int(pid))
                headless_manager.set_process_priority(pid, headless_manager._NORMAL_PRIORITY_CLASS)
                if auto_arranger and auto_arranger.is_enabled():
                    try:
                        auto_arranger.trigger_delayed_arrange(0.5)
                    except Exception:
                        pass
                return True, "Restored 1 window(s)"
            return False, f"Failed to restore window for PID {pid}"
        except Exception as e:
            log_detailed_error("Failed to restore macOS window", exc=e)
            return False, "Failed to restore window"

    if platform.system() != "Windows" or not win32gui:
        return False, "Not supported on this platform"
    try:
        windows = headless_manager.get_roblox_windows(target_pids={pid}, include_hidden=True)
        if not windows:
            return False, f"No window found for PID {pid}"

        count = 0
        for hwnd in windows:
            if headless_manager.restore_window(hwnd):
                count += 1
            headless_manager.restored_hwnds.add(int(hwnd))

        headless_manager.restored_pids.add(int(pid))
        headless_manager.set_process_priority(pid, headless_manager._NORMAL_PRIORITY_CLASS)

        if count > 0 and auto_arranger and auto_arranger.is_enabled():
            try:
                auto_arranger.trigger_delayed_arrange(0.5)
            except Exception:
                pass

        return True, f"Restored {count} window(s)"
    except Exception as e:
        log_detailed_error("Failed to restore Windows window", exc=e)
        return False, "Failed to restore window"

def trim_instance(pid: int) -> Tuple[bool, float, str]:
    if platform.system() != "Windows":
        return False, 0.0, "Not supported on this platform"
    try:
        ok, before_bytes, after_bytes = trim_process_working_set(pid)
        saved_mb = round(max(0, before_bytes - after_bytes) / (1024 * 1024), 1)
        if ok:
            return True, saved_mb, f"Reclaimed {saved_mb} MB RAM"
        return False, 0.0, "Failed to trim working set"
    except Exception as e:
        log_detailed_error("Failed to trim process working set", exc=e)
        return False, 0.0, "Failed to trim working set"

@app.route('/api/instances/focus', methods=['POST', 'OPTIONS'])
def focus_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, msg = focus_instance(pid)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to focus instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to focus instance'}), 500

@app.route('/api/instances/hide', methods=['POST', 'OPTIONS'])
def hide_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, msg = hide_instance(pid)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to hide instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to hide instance'}), 500

@app.route('/api/instances/unhide', methods=['POST', 'OPTIONS'])
def unhide_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, msg = unhide_instance(pid)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to restore instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to restore instance'}), 500

@app.route('/api/instances/trim', methods=['POST', 'OPTIONS'])
def trim_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, saved_mb, msg = trim_instance(pid)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'savedMb': saved_mb, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to trim instance working set", exc=e)
        return jsonify({'success': False, 'error': 'Failed to trim instance working set'}), 500

@app.route('/api/instances/mute', methods=['POST', 'OPTIONS'])
def mute_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, msg = set_process_audio_mute(pid, True)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to mute instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to mute instance'}), 500

@app.route('/api/instances/unmute', methods=['POST', 'OPTIONS'])
def unmute_instance_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
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

        ok, msg = set_process_audio_mute(pid, False)
        if ok:
            invalidate_instances_cache()
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to unmute instance", exc=e)
        return jsonify({'success': False, 'error': 'Failed to unmute instance'}), 500

@app.route('/api/instances/mute-all', methods=['POST', 'OPTIONS'])
def mute_all_instances_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = get_running_instances()
        if hasattr(data, 'get_json'):
            data = data.get_json()
        instances = data.get('instances', []) if isinstance(data, dict) else []
        count = 0
        for inst in instances:
            p = inst.get('pid')
            if p:
                set_process_audio_mute(p, True)
                count += 1
        invalidate_instances_cache()
        return jsonify({'success': True, 'count': count, 'message': f'Muted audio for {count} instance(s)'})
    except Exception as e:
        log_detailed_error("Failed to mute all instances", exc=e)
        return jsonify({'success': False, 'error': 'Failed to mute all instances'}), 500

@app.route('/api/instances/unmute-all', methods=['POST', 'OPTIONS'])
def unmute_all_instances_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = get_running_instances()
        if hasattr(data, 'get_json'):
            data = data.get_json()
        instances = data.get('instances', []) if isinstance(data, dict) else []
        count = 0
        for inst in instances:
            p = inst.get('pid')
            if p:
                set_process_audio_mute(p, False)
                count += 1
        invalidate_instances_cache()
        return jsonify({'success': True, 'count': count, 'message': f'Unmuted audio for {count} instance(s)'})
    except Exception as e:
        log_detailed_error("Failed to unmute all instances", exc=e)
        return jsonify({'success': False, 'error': 'Failed to unmute all instances'}), 500

@app.route('/api/instances/trim-all', methods=['POST', 'OPTIONS'])
def trim_all_instances_endpoint():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = get_running_instances()
        if hasattr(data, 'get_json'):
            data = data.get_json()
        instances = data.get('instances', []) if isinstance(data, dict) else []
        total_saved_mb = 0.0
        success_count = 0
        for inst in instances:
            p = inst.get('pid')
            if p:
                ok, saved_mb, _ = trim_instance(p)
                if ok:
                    total_saved_mb += saved_mb
                    success_count += 1
        invalidate_instances_cache()
        total_saved_mb = round(total_saved_mb, 1)
        return jsonify({
            'success': True,
            'count': success_count,
            'savedMb': total_saved_mb,
            'message': f'Trimmed {success_count} instance(s), reclaimed {total_saved_mb} MB RAM'
        })
    except Exception as e:
        log_detailed_error("Failed to trim all instances", exc=e)
        return jsonify({'success': False, 'error': 'Failed to trim all instances'}), 500

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
                    new_hash = PasswordEncryption.compute_verifier(target_password, new_encryptor.salt)
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
            log_detailed_error("Encryption setup failed", exc=e)
            return jsonify({'error': 'Encryption setup failed'}), 500
    
    save_data(data)
    return jsonify({'success': True, 'settings': data['settings']})

ALLOWED_FRAMDATA_FOLDERS: set[str] = set()

@app.route('/api/setup/select-folder', methods=['POST', 'GET', 'OPTIONS'])
def select_folder_dialog():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        folder_selected = _choose_folder_native("Select FRAMdata or AccountManagerData Folder")
        if folder_selected:
            ALLOWED_FRAMDATA_FOLDERS.add(os.path.abspath(os.path.realpath(folder_selected)))
            return jsonify({'success': True, 'path': folder_selected})
        return jsonify({'success': False, 'cancelled': True})
    except Exception as e:
        log_detailed_error("Failed to select folder", exc=e)
        return jsonify({'success': False, 'cancelled': True, 'error': 'Failed to select folder'}), 200

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

        norm_folder = os.path.abspath(os.path.realpath(str(folder_path).strip()))
        user_home = os.path.abspath(os.path.realpath(os.path.expanduser('~')))
        if not norm_folder.startswith(user_home + os.sep):
            return jsonify({'success': False, 'valid': False, 'error': 'Folder must be located inside your user directory'}), 400

        res = manager.preview_framdata_folder(norm_folder, password=password)
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to preview FRAM data", exc=e)
        return jsonify({'success': False, 'valid': False, 'error': 'Failed to preview FRAM data'}), 500

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

        norm_folder = os.path.abspath(os.path.realpath(str(folder_path).strip()))
        user_home = os.path.abspath(os.path.realpath(os.path.expanduser('~')))
        if not norm_folder.startswith(user_home + os.sep):
            return jsonify({'success': False, 'error': 'Folder must be located inside your user directory'}), 400

        res = manager.import_framdata_folder(norm_folder, password=password)

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
        log_detailed_error("Failed to import FRAM data", exc=e)
        return jsonify({'success': False, 'error': 'Failed to import FRAM data'}), 500


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
            
        temp_enc = PasswordEncryption(current_pwd, salt) if salt else None
        derived_key = temp_enc.key if temp_enc else None
        if not PasswordEncryption.verify_password_verifier(current_pwd, salt, stored_hash, derived_key):
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
            log_detailed_error("Failed to decrypt current accounts", exc=load_err)
            return jsonify({'success': False, 'error': 'Failed to decrypt current accounts'}), 400
            
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
                new_hash = PasswordEncryption.compute_verifier(new_pwd, new_encryptor.salt)
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
            log_detailed_error("Failed to switch encryption", exc=e)
            return jsonify({'success': False, 'error': 'Failed to switch encryption'}), 500

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
            log_detailed_error("Failed to get encryption status", exc=e)
            return jsonify({'enabled': False, 'method': 'none', 'error': 'Failed to get encryption status'}), 500
    
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
        norm_file_path = os.path.abspath(os.path.realpath(str(file_path).strip()))
        user_home = os.path.abspath(os.path.realpath(os.path.expanduser('~')))
        if not norm_file_path.startswith(user_home + os.sep) or not norm_file_path.lower().endswith('.json'):
            return jsonify({'error': 'Invalid export destination path'}), 400
        try:
            with open(norm_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return jsonify({'success': True, 'path': norm_file_path, 'count': len(data.get('accounts', []))})
        except Exception as e:
            log_detailed_error("Failed to export data", exc=e)
            return jsonify({'error': 'Failed to export data'}), 500

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
        'autoUpdateToPreReleases': False,
        'autoUpdateToLatestRelease': True,
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
        'headlessEcoQoS': True,
        'headlessFpsCap': 15,
        'headlessGraphicsOpt': True,
        'headlessDetectionDelaySeconds': 0,
        'antiAfkEnabled': False,
        'antiAfkIntervalMinutes': 10,
        'antiAfkKeyName': 'M1',
        'antiAfkKeyCode': 0,
        'antiAfkShowNextLabel': False,
        'preferredRegion': '',
        'serverPerAccount': False,
        'pick_server_per_account': False,
        'randomServer': False,
        'randomizeServerJobIds': False
    }

    fresh_data = {
        'accounts': [],
        'games': [],
        'saved_users': [],
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
                stderr=subprocess.DEVNULL,
                close_fds=True
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
        log_detailed_error("Failed to refresh DHCP lease", exc=e)
        return jsonify({'success': False, 'error': 'Failed to refresh DHCP lease'}), 500

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
                log_detailed_error("Browser account addition failed", exc=e)
                result['success'] = False
                result['message'] = 'Failed to add accounts' 
        
        thread = threading.Thread(target=add_accounts)
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Browser automation started'})
        
    except Exception as e:
        log_detailed_error("Failed to export data", exc=e)
        return jsonify({'error': 'Failed to export data'}), 500

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
                log_detailed_error("Browser account addition failed", exc=e)
                result['success'] = False
                result['message'] = 'Failed to add accounts' 
        
        thread = threading.Thread(target=add_creds)
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Credential login started'})
        
    except Exception as e:
        log_detailed_error("Failed to start credential login", exc=e)
        return jsonify({'error': 'Failed to start credential login'}), 500

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
        log_detailed_error("Failed to retrieve browser status", exc=e)
        return jsonify({
            'manager_available': False,
            'browsers_available': [],
            'has_supported_browser': False,
            'is_running': False,
            'active_instances': 0,
            'user_closed': False,
            'last_close_reason': None,
            'error': 'Failed to retrieve browser status'
        }), 500

@app.route('/api/browser/chromium/status', methods=['GET'])
def get_chromium_status():
    try:
        status_info = chromium_downloader_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        log_detailed_error("Failed to get chromium status", exc=e, source="chromium_api")
        return jsonify({'success': False, 'error': 'Failed to get chromium status'}), 500

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
        return jsonify({'success': False, 'error': 'Failed to start chromium download'}), 500

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
        return jsonify({'success': False, 'error': 'Failed to uninstall chromium'}), 500

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
                log_detailed_error("Quick Sign-In worker failed", exc=e)
                result_container['result'] = {'success': False, 'error': 'Quick Sign-In encountered an error'}
                result_container['status'] = 'error'
                result_container['status_message'] = 'Quick Sign-In encountered an error'
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
        log_detailed_error("Failed to start Quick Sign-In", exc=e)
        return jsonify({'error': 'Failed to start Quick Sign-In'}), 500

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
        log_detailed_error("Failed to get Quick Sign-In status", exc=e)
        return jsonify({'error': 'Failed to get Quick Sign-In status'}), 500

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
        log_detailed_error("Failed to cancel Quick Sign-In", exc=e)
        return jsonify({'error': 'Failed to cancel Quick Sign-In'}), 500

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
        log_detailed_error("Failed to validate cookie", exc=e)
        return jsonify({'valid': False, 'status': 'expired', 'error': 'Failed to validate cookie'}), 500

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
        log_detailed_error("Failed to retrieve user information", exc=e)
        return jsonify({'error': 'Failed to retrieve user information'}), 500

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
        log_detailed_error("Failed to retrieve game information", exc=e)
        return jsonify({'error': 'Failed to retrieve game information'}), 500


@app.route('/api/roblox/clear-icon-cache', methods=['POST'])
def clear_icon_cache():
    try:
        icon_cache.clear()
        return jsonify({'success': True, 'message': 'Icon cache cleared successfully'})
    except Exception as e:
        log_detailed_error("Failed to clear icon cache", exc=e)
        return jsonify({'success': False, 'error': 'Failed to clear icon cache'}), 500

@app.route('/api/roblox/icon-cache/stats', methods=['GET'])
def get_icon_cache_stats():
    try:
        stats = icon_cache.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        log_detailed_error("Failed to clear icon cache", exc=e)
        return jsonify({'success': False, 'error': 'Failed to clear icon cache'}), 500

@app.route('/api/roblox/icon-file/<path:filename>', methods=['GET'])
def get_icon_file(filename):
    try:
        from werkzeug.utils import secure_filename
        safe_filename = secure_filename(os.path.basename(filename))
        if not safe_filename or safe_filename != filename:
            return jsonify({'error': 'Invalid filename'}), 400
        from utils.paths import get_cache_folder
        icons_dir = os.path.abspath(os.path.realpath(os.path.join(get_cache_folder(), 'icons')))
        icon_path = os.path.abspath(os.path.realpath(os.path.join(icons_dir, safe_filename)))
        if not icon_path.startswith(icons_dir + os.sep) or not os.path.isfile(icon_path):
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
        log_detailed_error("Failed to retrieve subplaces", exc=e)
        return jsonify({'success': False, 'subplaces': [], 'error': 'Failed to retrieve subplaces'}), 500

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
        log_detailed_error("Failed to start browser automation", exc=e)
        return jsonify({'error': 'Failed to start browser automation'}), 500

def _get_platform_capabilities() -> Dict[str, Any]:
    sys_name = platform.system()
    is_win = sys_name == "Windows"
    is_mac = sys_name == "Darwin"
    os_name = "macos" if is_mac else ("windows" if is_win else "linux")
    return {
        "platform": os_name,
        "arch": platform.machine().lower(),
        "capabilities": {
            "multi_instance": is_win or is_mac,
            "memory_trim": is_win,
            "crash_handler_killer": is_win,
            "bootstrappers": is_win,
            "executor_presets": is_win,
            "anti_afk": is_win or is_mac,
            "anti_afk_overlay": is_win,
            "headless_mode": is_win or is_mac,
            "auto_arrange": is_win or is_mac,
            "rblxswap_hwid": is_win,
            "rblxswap_mac": is_win,
            "rblxswap_traces": is_win or is_mac,
        }
    }

@app.route('/api/system/platform', methods=['GET'])
def get_system_platform():
    return jsonify({'success': True, **_get_platform_capabilities()})

@app.route('/api/health', methods=['GET'])
def health_check():
    if _IS_SHUTTING_DOWN:
        return jsonify({
            'status': 'shutting_down',
            'pid': os.getpid(),
            'timestamp': datetime.now().isoformat()
        }), 503
    return jsonify({
        'status': 'healthy',
        'pid': os.getpid(),
        'ppid': _INITIAL_PPID,
        'parent_pid': os.environ.get('FRAM_PARENT_PID'),
        'uptime_sec': round(time.time() - _BACKEND_START_TIME, 2),
        'timestamp': datetime.now().isoformat(),
        **_get_platform_capabilities()
    })

@app.route('/api/system/diagnostics', methods=['GET'])
def get_system_diagnostics():
    try:
        cfg = get_cached_encryption_config()
        enc_enabled = cfg.is_encryption_enabled() if cfg else False
        enc_method = cfg.get_encryption_method() if cfg else None
        is_locked = bool(enc_enabled and enc_method == 'password' and active_master_password is None)
        with backend_logs_lock:
            recent_logs = list(backend_logs)[-80:]
        return jsonify({
            'success': True,
            'pid': os.getpid(),
            'ppid': _INITIAL_PPID,
            'parent_pid': os.environ.get('FRAM_PARENT_PID'),
            'frozen': bool(getattr(sys, 'frozen', False)),
            'executable': sys.executable,
            'data_folder': get_data_folder(),
            'uptime_sec': round(time.time() - _BACKEND_START_TIME, 2),
            'shutting_down': _IS_SHUTTING_DOWN,
            'encryption_enabled': enc_enabled,
            'encryption_method': enc_method,
            'vault_locked': is_locked,
            'recent_logs': recent_logs
        })
    except Exception as e:
        log_detailed_error("Failed to get system diagnostics", exc=e, source="diagnostics")
        return jsonify({'success': False, 'error': 'Failed to retrieve system diagnostics'}), 500

@app.route('/api/auth/token', methods=['GET'])
def get_auth_token():
    origin = request.headers.get('Origin', '')
    referer = request.headers.get('Referer', '')
    is_local_addr = request.remote_addr in ('127.0.0.1', '::1', 'localhost', '::ffff:127.0.0.1')
    is_allowed_origin = _is_trusted_local_origin(origin) if origin else False
    is_allowed_referer = _is_trusted_local_origin(referer) if referer else False
    if not is_local_addr and not is_allowed_origin and not is_allowed_referer:
        return jsonify({'error': 'Unauthorized origin'}), 403
    if origin and not is_allowed_origin:
        return jsonify({'error': 'Unauthorized origin'}), 403
    if referer and not is_allowed_referer:
        return jsonify({'error': 'Unauthorized origin'}), 403
    return jsonify({'token': API_AUTH_TOKEN})

_IS_SHUTTING_DOWN = False
_SHUTDOWN_LOCK = threading.Lock()
_SERVICES_STARTED = False
_SERVICES_LOCK = threading.Lock()

def perform_graceful_shutdown():
    global _IS_SHUTTING_DOWN
    with _SHUTDOWN_LOCK:
        if _IS_SHUTTING_DOWN:
            return
        _IS_SHUTTING_DOWN = True

    print(f"[INFO] Backend (PID={os.getpid()}) initiating graceful shutdown...")

    try:
        data_folder = get_data_folder()
        for fname in ('.api_token', '.backend_pid'):
            fpath = os.path.join(data_folder, fname)
            if os.path.exists(fpath):
                try:
                    os.unlink(fpath)
                except OSError:
                    pass
    except Exception:
        pass

    try:
        multi_instance_controller.disable()
    except Exception:
        pass

    try:
        anti_afk_manager.stop_loop(timeout=0.4)
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
        if account_manager is not None:
            account_manager.save_accounts()
    except Exception as e:
        log_detailed_error("Error saving accounts during shutdown", exc=e, source="shutdown")

    try:
        cleanup_temp_files(max_age_seconds=0.0)
    except Exception as e:
        log_detailed_error("Error cleaning temporary files during shutdown", exc=e, source="shutdown")

def _parent_process_watchdog():
    raw_parent = os.environ.get('FRAM_PARENT_PID', '').strip()
    target_parent_pid = int(raw_parent) if raw_parent.isdigit() and int(raw_parent) > 1 else None
    is_frozen = bool(getattr(sys, 'frozen', False))
    watch_ppid = _INITIAL_PPID if (is_frozen and _INITIAL_PPID and _INITIAL_PPID > 1) else None

    if not target_parent_pid and not watch_ppid:
        return

    print(f"[INFO] Parent process watchdog active (FRAM_PARENT_PID={target_parent_pid}, bootloader_ppid={watch_ppid})")
    while not _IS_SHUTTING_DOWN:
        time.sleep(1.5)
        try:
            if target_parent_pid and not psutil.pid_exists(target_parent_pid):
                print(f"[INFO] Parent Tauri process (PID={target_parent_pid}) exited; shutting down backend (PID={os.getpid()}).")
                perform_graceful_shutdown()
                os._exit(0)
            if watch_ppid and not psutil.pid_exists(watch_ppid):
                print(f"[INFO] Bootloader parent process (PID={watch_ppid}) exited; shutting down backend (PID={os.getpid()}).")
                perform_graceful_shutdown()
                os._exit(0)
        except Exception:
            pass

def start_background_services():
    global _SERVICES_STARTED
    with _SERVICES_LOCK:
        if _SERVICES_STARTED:
            return
        _SERVICES_STARTED = True

    _write_backend_pid()
    atexit.register(perform_graceful_shutdown)

    def _deferred_init():
        try:
            cleanup_temp_files()
        except Exception as e:
            log_detailed_error("Failed to run startup temp file cleanup", exc=e, source="startup")
        try:
            anti_afk_manager.start_loop()
        except Exception as e:
            print(f"[WARNING] Failed to start anti_afk_manager loop: {e}")

    threading.Thread(target=_deferred_init, daemon=True, name="deferred-startup-init").start()
    threading.Thread(target=_parent_process_watchdog, daemon=True, name="parent-watchdog").start()
    threading.Thread(target=background_auto_rejoin_worker, daemon=True, name="auto-rejoin-worker").start()
    threading.Thread(target=background_group_auto_relaunch_worker, daemon=True, name="group-relaunch-worker").start()
    threading.Thread(target=background_auto_memory_trim_worker, daemon=True, name="memory-trim-worker").start()
    threading.Thread(target=background_auto_crash_handler_killer_worker, daemon=True, name="crash-killer-worker").start()
    threading.Thread(target=background_instance_tracker_worker, daemon=True, name="instance-exit-tracker").start()

def _signal_handler(signum, frame):
    perform_graceful_shutdown()
    os._exit(0)

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
        log_detailed_error("Failed to get icon cache statistics", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get icon cache statistics'}), 500

@app.route('/api/installer/clients', methods=['GET'])
def get_installer_clients():
    try:
        clients = roblox_installer_manager.get_installed_clients()
        return jsonify({'success': True, 'clients': clients})
    except Exception as e:
        log_detailed_error("Failed to get available versions", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get available versions'}), 500

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
        log_detailed_error("Failed to get installer clients", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get installer clients'}), 500

@app.route('/api/installer/status', methods=['GET'])
def get_installer_status():
    try:
        status_info = roblox_installer_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        log_detailed_error("Failed to start installer download", exc=e)
        return jsonify({'success': False, 'error': 'Failed to start installer download'}), 500

@app.route('/api/installer/weao-exploits', methods=['GET'])
def get_installer_weao_exploits():
    try:
        exploits = roblox_installer_manager.get_weao_exploits()
        return jsonify({'success': True, 'exploits': exploits})
    except Exception as e:
        log_detailed_error("Failed to get installer status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get installer status'}), 500

@app.route('/api/updater/check', methods=['GET'])
def check_app_updates():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        prerelease_arg = request.args.get('prerelease')
        latest_arg = request.args.get('latest')
        settings = load_data().get('settings', {})
        if prerelease_arg is not None:
            include_prereleases = prerelease_arg.lower() == 'true'
        else:
            include_prereleases = bool(settings.get('autoUpdateToPreReleases', False))
        if latest_arg is not None:
            include_latest = latest_arg.lower() == 'true'
        else:
            include_latest = bool(settings.get('autoUpdateToLatestRelease', True))
        res = updater_manager.check_for_updates(
            force=force,
            include_prereleases=include_prereleases,
            include_latest=include_latest
        )
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to get WEAO exploits", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get WEAO exploits'}), 500

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
        log_detailed_error("Failed to check for app updates", exc=e)
        return jsonify({'success': False, 'error': 'Failed to check for app updates'}), 500

@app.route('/api/updater/status', methods=['GET'])
def get_app_update_status():
    try:
        status_info = updater_manager.get_status()
        return jsonify({'success': True, 'status': status_info})
    except Exception as e:
        log_detailed_error("Failed to start app update download", exc=e)
        return jsonify({'success': False, 'error': 'Failed to start app update download'}), 500

@app.route('/api/updater/apply', methods=['POST'])
def apply_app_update():
    try:
        res = updater_manager.apply_update()
        return jsonify(res)
    except Exception as e:
        log_detailed_error("Failed to get app update status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get app update status'}), 500

@app.route('/api/updater/releases', methods=['GET'])
def get_app_releases():
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        releases = updater_manager.get_all_releases(force=force)
        return jsonify({'success': True, 'releases': releases})
    except Exception as e:
        log_detailed_error("Failed to get app releases", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get app releases', 'releases': []}), 500

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
        log_detailed_error("Failed to apply app update", exc=e)
        return jsonify({'success': False, 'error': 'Failed to apply app update'}), 500

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
        log_detailed_error("Failed to handle Roblox global settings", exc=e)
        return jsonify({'success': False, 'error': 'Failed to handle Roblox global settings'}), 500

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
        log_detailed_error("Failed to handle Roblox device preferences", exc=e)
        return jsonify({'success': False, 'error': 'Failed to handle Roblox device preferences'}), 500

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
        log_detailed_error("Failed to handle FastFlags", exc=e)
        return jsonify({'success': False, 'error': 'Failed to handle FastFlags'}), 500

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
        log_detailed_error("Failed to validate FastFlag", exc=e)
        return jsonify({'success': False, 'error': 'Failed to validate FastFlag'}), 500

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
        log_detailed_error("Failed to backup FastFlags", exc=e)
        return jsonify({'success': False, 'error': 'Failed to backup FastFlags'}), 500

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
        log_detailed_error("Failed to restore FastFlags", exc=e)
        return jsonify({'success': False, 'error': 'Failed to restore FastFlags'}), 500

def _webhook_lookup_account(username: str) -> Dict[str, Any]:
    if not username:
        return {}
    try:
        uname_lower = str(username).strip().lower()
        data = load_data()
        for acc in data.get('accounts', []):
            if str(acc.get('username', '')).strip().lower() == uname_lower:
                return acc
        mgr = get_account_manager()
        if mgr and hasattr(mgr, 'accounts') and isinstance(mgr.accounts, dict):
            for k, v in mgr.accounts.items():
                if str(k).lower() == uname_lower and isinstance(v, dict):
                    return v
    except Exception:
        pass
    return {}

def _webhook_resolve_instances() -> List[Dict[str, Any]]:
    try:
        with _INSTANCES_CACHE_LOCK:
            cached = _INSTANCES_CACHE
        if cached and isinstance(cached.get('instances'), list):
            enriched = []
            for inst in cached['instances']:
                item = dict(inst)
                pid = item.get('pid')
                if pid is not None and str(item.get('status', '')).lower() == 'running':
                    if not _is_roblox_pid(pid):
                        item['status'] = 'Closed'
                        item['memory_mb'] = 0.0
                        item['cpu_percent'] = 0.0
                        if not item.get('exit_reason'):
                            item['exit_reason'] = 'Client Process Closed / Disconnected'
                pid_place = item.get('place_id')
                if pid_place and not item.get('place_name'):
                    item['place_name'] = get_place_name(pid_place) or str(pid_place)
                up_s = int(item.get('uptime_sec') or 0)
                if up_s > 0:
                    m, s = divmod(up_s, 60)
                    h, m = divmod(m, 60)
                    item['uptime_str'] = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"
                enriched.append(item)
            return enriched
    except Exception:
        pass

    results: List[Dict[str, Any]] = []
    try:
        app_data = load_data()
        accounts_by_user = {}
        accounts_by_id = {}
        for acc in app_data.get('accounts', []):
            uname = acc.get('username', '')
            if uname:
                accounts_by_user[uname.lower()] = acc
                uid = str(acc.get('user_id') or '').strip()
                if uid:
                    accounts_by_id[uid] = acc

        now = time.time()
        game_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'create_time']):
            try:
                pname = str(proc.info.get('name') or '')
                if not re.search(r'robloxplayer(?:beta)?(?:\.exe)?$', pname, re.IGNORECASE):
                    continue
                pid = int(proc.info['pid'])
                mem_info = proc.info.get('memory_info')
                mem_mb = round((mem_info.rss if mem_info else 0) / (1024 * 1024), 1)
                create_t = proc.info.get('create_time') or now
                game_procs.append((pid, pname, mem_mb, create_t))
            except Exception:
                continue

        resolved_map = (
            resolve_active_pids_accounts([(p, ct) for p, _, _, ct in game_procs], accounts_by_user, accounts_by_id)
            if game_procs
            else {}
        )

        for pid, pname, mem_mb, create_t in game_procs:
            try:
                up_s = max(0, int(now - create_t))
                m, s = divmod(up_s, 60)
                h, m = divmod(m, 60)
                uptime_str = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"

                acc_info = resolved_map.get(pid) or {}
                place_id = str(acc_info.get('place_id') or resolve_pid_place_id(pid, acc_info) or '')
                place_name = get_place_name(place_id) if place_id else 'Roblox Client'
                results.append({
                    'pid': pid,
                    'name': pname,
                    'status': 'Running',
                    'username': acc_info.get('username'),
                    'display_name': acc_info.get('display_name'),
                    'user_id': acc_info.get('user_id'),
                    'avatar_url': acc_info.get('avatar_url'),
                    'place_id': place_id,
                    'place_name': place_name,
                    'memory_mb': mem_mb,
                    'cpu_percent': 0.0,
                    'uptime_sec': up_s,
                    'uptime_str': uptime_str,
                })
            except Exception:
                continue

        with _INSTANCES_TRACKER_LOCK:
            for inactive in _CLOSED_OR_CRASHED_INSTANCES.values():
                results.append(dict(inactive))
    except Exception:
        pass
    return results

webhook_manager.set_account_lookup(_webhook_lookup_account)
webhook_manager.set_instances_provider(_webhook_resolve_instances)

@app.route('/api/webhook/config', methods=['GET', 'OPTIONS'])
def get_webhook_config():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify({
            'success': True,
            'config': webhook_manager.config,
            'history': webhook_manager.get_history(),
            'stats': webhook_manager.get_stats(),
            'instances': _webhook_resolve_instances()
        })
    except Exception as e:
        log_detailed_error("Failed to get webhook configuration", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get webhook configuration'}), 500

@app.route('/api/webhook/config', methods=['POST', 'OPTIONS'])
def save_webhook_config():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json() or {}
        if isinstance(data, dict):
            if "webhook_url" in data:
                raw_wh = str(data.get("webhook_url") or "").strip()
                if raw_wh:
                    canon_wh = webhook_manager.canonicalize_webhook_url(raw_wh)
                    if not canon_wh:
                        return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
                    data["webhook_url"] = canon_wh
                else:
                    data["webhook_url"] = ""
            if "endpoints" in data and isinstance(data["endpoints"], list):
                for ep in data["endpoints"]:
                    if isinstance(ep, dict):
                        raw_ep = str(ep.get("url") or "").strip()
                        if raw_ep:
                            canon_ep = webhook_manager.canonicalize_webhook_url(raw_ep)
                            if not canon_ep:
                                return jsonify({'success': False, 'error': f"Invalid Discord webhook URL in endpoint: {ep.get('name', 'Endpoint')}"}), 400
                            ep["url"] = canon_ep
                        else:
                            ep["url"] = ""
        updated = webhook_manager.save_config(data)
        return jsonify({
            'success': True,
            'config': updated,
            'stats': webhook_manager.get_stats(),
            'message': 'Webhook settings saved successfully.'
        })
    except Exception as e:
        log_detailed_error("Failed to save webhook configuration", exc=e)
        return jsonify({'success': False, 'error': 'Failed to save webhook configuration'}), 500

@app.route('/api/webhook/clear-history', methods=['POST', 'OPTIONS'])
def clear_webhook_history():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        webhook_manager.clear_history()
        return jsonify({
            'success': True,
            'history': [],
            'stats': webhook_manager.get_stats(),
            'message': 'Webhook activity history cleared.'
        })
    except Exception as e:
        log_detailed_error("Failed to clear webhook history", exc=e)
        return jsonify({'success': False, 'error': 'Failed to clear webhook history'}), 500

@app.route('/api/webhook/retry', methods=['POST', 'OPTIONS'])
def retry_webhook_history_item():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        item_id = str(data.get('id') or '').strip()
        if not item_id:
            return jsonify({'success': False, 'error': 'Missing history item ID'}), 400
        ok, msg = webhook_manager.retry_history_item(item_id)
        if ok:
            return jsonify({'success': True, 'message': msg, 'history': webhook_manager.get_history(), 'stats': webhook_manager.get_stats()})
        return jsonify({'success': False, 'error': msg}), 400
    except Exception as e:
        log_detailed_error("Failed to retry webhook item", exc=e)
        return jsonify({'success': False, 'error': 'Failed to retry webhook item'}), 500

@app.route('/api/webhook/reset-live-board', methods=['POST', 'OPTIONS'])
def reset_webhook_live_board():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        cfg = webhook_manager.reset_live_board()
        return jsonify({
            'success': True,
            'config': cfg,
            'stats': webhook_manager.get_stats(),
            'message': 'Live board message state reset. Next report will post a new Discord message.'
        })
    except Exception as e:
        log_detailed_error("Failed to reset live board", exc=e)
        return jsonify({'success': False, 'error': 'Failed to reset live board'}), 500

@app.route('/api/webhook/test', methods=['POST', 'OPTIONS'])
def test_webhook():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        custom_url = (data.get('webhook_url') or '').strip() or None
        if custom_url:
            custom_url = webhook_manager.canonicalize_webhook_url(custom_url)
            if not custom_url:
                return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
        ok, msg = webhook_manager.send_test_webhook(url=custom_url)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg or 'Failed to test webhook'}), 400
    except Exception as e:
        log_detailed_error("Failed to test webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to test webhook'}), 500

@app.route('/api/webhook/send', methods=['POST', 'OPTIONS'])
def send_webhook_custom():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        title = data.get('title', 'Notification')
        description = data.get('description', '')
        fields = data.get('fields', [])
        color = data.get('color')
        custom_url = (data.get('webhook_url') or '').strip() or None
        if custom_url:
            custom_url = webhook_manager.canonicalize_webhook_url(custom_url)
            if not custom_url:
                return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
        ok, msg = webhook_manager.post_embed(
            title=title,
            description=description,
            fields=fields,
            color=color,
            url=custom_url,
            category='custom'
        )
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg or 'Failed to send custom webhook'}), 400
    except Exception as e:
        log_detailed_error("Failed to send custom webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to send custom webhook'}), 500

@app.route('/api/webhook/test-screenshot', methods=['POST', 'OPTIONS'])
def test_webhook_screenshot():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        all_monitors = data.get('all_monitors')
        mode = data.get('mode')
        pid = data.get('pid')
        custom_url = (data.get('webhook_url') or '').strip() or None
        if custom_url:
            custom_url = webhook_manager.canonicalize_webhook_url(custom_url)
            if not custom_url:
                return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
        ok, msg = webhook_manager.post_screenshot(url=custom_url, all_monitors=all_monitors, mode=mode, target_pid=pid)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg or 'Failed to send screenshot webhook'}), 400
    except Exception as e:
        log_detailed_error("Failed to send screenshot webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to send screenshot webhook'}), 500

@app.route('/api/webhook/test-instances', methods=['POST', 'OPTIONS'])
def test_webhook_instances():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        custom_url = (data.get('webhook_url') or '').strip() or None
        if custom_url:
            custom_url = webhook_manager.canonicalize_webhook_url(custom_url)
            if not custom_url:
                return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
        force_new = bool(data.get('force_new_message', False))
        ok, msg = webhook_manager.post_instance_summary(url=custom_url, force_new_message=force_new)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg or 'Failed to send instances webhook'}), 400
    except Exception as e:
        log_detailed_error("Failed to send instances webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to send instances webhook'}), 500

@app.route('/api/webhook/preview-window', methods=['POST', 'OPTIONS'])
def send_webhook_window_preview():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        pid = data.get('pid')
        username = data.get('username')
        place_id = data.get('place_id')
        place_name = data.get('place_name') or (get_place_name(place_id) if place_id else None)
        custom_url = (data.get('webhook_url') or '').strip() or None
        if custom_url:
            custom_url = webhook_manager.canonicalize_webhook_url(custom_url)
            if not custom_url:
                return jsonify({'success': False, 'error': 'Invalid Discord webhook URL'}), 400
        
        memory_mb = None
        cpu_percent = None
        uptime_str = None
        
        if pid:
            try:
                pid = int(pid)
                p = psutil.Process(pid)
                mem = p.memory_info().rss
                memory_mb = round(mem / (1024 * 1024), 1)
                cpu_percent = round(p.cpu_percent(interval=None) / max(1, psutil.cpu_count()), 1)
                create_t = p.create_time()
                if create_t > 0:
                    up_s = max(0, int(time.time() - create_t))
                    m, s = divmod(up_s, 60)
                    h, m = divmod(m, 60)
                    uptime_str = f"{h}h {m}m {s}s" if h > 0 else (f"{m}m {s}s" if m > 0 else f"{s}s")
            except Exception:
                pass

        ok, msg = webhook_manager.post_window_preview(
            pid=pid,
            username=username,
            place_id=place_id,
            place_name=place_name,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            uptime_str=uptime_str,
            url=custom_url
        )
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'success': False, 'error': msg or 'Failed to send window preview'}), 400
    except Exception as e:
        log_detailed_error("Failed to send window preview webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to send window preview webhook'}), 500

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
        log_detailed_error("Failed to send instances webhook", exc=e)
        return jsonify({'success': False, 'error': 'Failed to send instances webhook'}), 500

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
        raw_weblauncher = str(data.get('weblauncher_dir') or '').strip().lower()
        weblauncher_dir = None
        if raw_weblauncher:
            allowed_dirs = {}
            for v in RobloxAPI.get_installed_versions():
                p = v.get('path', '')
                if p:
                    norm_v = os.path.abspath(os.path.realpath(p))
                    allowed_dirs[norm_v.lower()] = norm_v
                    allowed_dirs[p.lower()] = norm_v
            for b in RobloxAPI.BOOTSTRAPPER_CLIENTS:
                r = os.path.expandvars(b.get('root', ''))
                if r:
                    norm_r = os.path.abspath(os.path.realpath(r))
                    allowed_dirs[norm_r.lower()] = norm_r
                    allowed_dirs[r.lower()] = norm_r
            weblauncher_dir = allowed_dirs.get(raw_weblauncher)
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
        log_detailed_error("Failed to clean Roblox traces", exc=e)
        add_backend_log("[TraceCleaner] Trace cleanup failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Failed to clean Roblox traces'}), 500

@app.route('/api/rblxswap/clean-status', methods=['GET', 'OPTIONS'])
def get_rblxswap_clean_status():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        return jsonify({'success': True, 'status': roblox_swap_manager.clean_status})
    except Exception as e:
        log_detailed_error("Failed to get hardware status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get hardware status'}), 500

@app.route('/api/rblxswap/adapters', methods=['GET', 'OPTIONS'])
def get_rblxswap_adapters():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        adapters = roblox_swap_manager.get_adapters()
        return jsonify({'success': True, 'adapters': adapters})
    except Exception as e:
        log_detailed_error("Failed to get cleaner status", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get cleaner status'}), 500

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
        log_detailed_error("Failed to spoof MAC address", exc=e)
        add_backend_log("[Spoofer] MAC spoof failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Failed to spoof MAC address'}), 500

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
        log_detailed_error("Failed to get network adapters", exc=e)
        return jsonify({'success': False, 'error': 'Failed to get network adapters'}), 500

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
        log_detailed_error("Failed to reset MAC address", exc=e)
        return jsonify({'success': False, 'error': 'Failed to reset MAC address'}), 500

@app.route('/api/rblxswap/dhcp-refresh', methods=['POST', 'OPTIONS'])
def refresh_rblx_dhcp():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        ok = roblox_swap_manager.refresh_dhcp()
        add_backend_log(f"[Spoofer] Refreshed DHCP IP address lease", level='info', category='spoofer')
        return jsonify({'success': ok})
    except Exception as e:
        log_detailed_error("Failed to restart network adapter", exc=e)
        return jsonify({'success': False, 'error': 'Failed to restart network adapter'}), 500

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
        log_detailed_error("Failed to spoof HWID", exc=e)
        add_backend_log("[Spoofer] HWID spoof failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Failed to spoof HWID'}), 500

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
        log_detailed_error("Failed to restore identifiers", exc=e)
        add_backend_log("[Spoofer] Restore identifiers failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Failed to restore hardware identifiers'}), 500

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
        log_detailed_error("Failed to create system restore point", exc=e)
        add_backend_log("[Spoofer] System restore point failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Failed to create system restore point'}), 500

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
        log_detailed_error("Unified spoof operation failed", exc=e)
        add_backend_log("[Spoofer] Unified spoof failed", level='error', category='spoofer')
        return jsonify({'success': False, 'error': 'Unified spoof operation failed'}), 500

if __name__ == '__main__':
    import socket
    import socketserver
    import http.server
    port = int(os.environ.get('PORT', 5050))

    print(
        f"[INFO] Starting FRAM Backend (PID={os.getpid()}, PPID={_INITIAL_PPID}, "
        f"FRAM_PARENT_PID={os.environ.get('FRAM_PARENT_PID')}, port={port}, "
        f"frozen={getattr(sys, 'frozen', False)}, data_folder={DATA_FOLDER})"
    )

    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4):
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{port}/api/health')
                with urllib.request.urlopen(req, timeout=0.8) as resp:
                    body = resp.read().decode('utf-8', errors='ignore')
                    if resp.status == 200 and '"healthy"' in body:
                        print(f"[INFO] Healthy backend is already running on 127.0.0.1:{port}; exiting duplicate instance.")
                        os._exit(0)
            except Exception as health_err:
                print(f"[WARNING] Port {port} had an existing listener but health check failed ({health_err}); waiting for port release...")
    except OSError:
        pass

    start_background_services()

    if platform.system() == "Windows":
        # Prevent binding over an active/zombie listening socket, and mark the listening socket
        # handle as non-inheritable so child processes (e.g. RobloxPlayerBeta.exe) never inherit it.
        socketserver.TCPServer.allow_reuse_address = False
        http.server.HTTPServer.allow_reuse_address = False
        try:
            import werkzeug.serving
            werkzeug.serving.BaseWSGIServer.allow_reuse_address = False
            _orig_server_bind = werkzeug.serving.BaseWSGIServer.server_bind

            def _non_inheritable_server_bind(self):
                try:
                    excl_opt = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
                    if excl_opt is not None:
                        self.socket.setsockopt(socket.SOL_SOCKET, excl_opt, 1)
                except Exception:
                    pass
                try:
                    k32 = ctypes.windll.kernel32
                    k32.SetHandleInformation(ctypes.c_void_p(int(self.socket.fileno())), 1, 0)
                except Exception:
                    pass
                return _orig_server_bind(self)

            werkzeug.serving.BaseWSGIServer.server_bind = _non_inheritable_server_bind
        except Exception:
            pass
    else:
        socketserver.TCPServer.allow_reuse_address = True

    max_bind_attempts = 20
    for attempt in range(max_bind_attempts):
        try:
            os.environ['PORT'] = str(port)
            try:
                import classes.icon_cache as _ic_mod
                _ic_mod.BACKEND_PORT = port
            except Exception:
                pass
            _write_backend_pid(port)
            print(f"[INFO] Binding Flask server to 127.0.0.1:{port} (attempt {attempt + 1}/{max_bind_attempts})...")
            app.run(host='127.0.0.1', port=port, debug=False, threaded=True, use_reloader=False)
            break
        except (OSError, SystemExit) as e:
            if _IS_SHUTTING_DOWN:
                break
            if attempt < max_bind_attempts - 1:
                if attempt >= 1:
                    old_port = port
                    port += 1
                    print(f"[WARNING] Bind attempt {attempt + 1} on port {old_port} failed ({e}); switching to fallback port {port}...")
                else:
                    print(f"[WARNING] Bind attempt {attempt + 1} on port {port} failed ({e}); retrying in 0.4s...")
                time.sleep(0.4)
            else:
                print(f"[ERROR] Could not bind backend to port {port} after {max_bind_attempts} attempts: {e}")
                perform_graceful_shutdown()
                os._exit(1)