import os
import sys

def get_root_app_dir():
    env_dir = os.environ.get("FRAM_APP_DIR")
    if env_dir and env_dir.strip():
        os.makedirs(env_dir, exist_ok=True)
        return env_dir

    local_appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    app_dir = os.path.join(local_appdata, "Forked Account Manager")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

def get_data_folder():
    data_dir = os.path.join(get_root_app_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_logs_folder():
    logs_dir = os.path.join(get_root_app_dir(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir

def get_cache_folder():
    cache_dir = os.path.join(get_root_app_dir(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_extensions_folder():
    ext_dir = os.path.join(get_root_app_dir(), "extensions")
    os.makedirs(ext_dir, exist_ok=True)
    return ext_dir
