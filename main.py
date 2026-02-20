"""
Roblox Account Manager
Main entry point for the application
"""
# python -m pyinstaller --onefile --windowed main.py



import os
import sys
import time
import shutil
import subprocess
import ctypes
import warnings
import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
from functools import lru_cache

warnings.filterwarnings("ignore")

from classes import RobloxAccountManager
from classes.encryption import EncryptionConfig
from utils.encryption_setup import setup_encryption
from utils.ui import AccountManagerUI


def get_app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=1)
def get_cached_app_base_dir():
    return get_app_base_dir()


@lru_cache(maxsize=1)
def get_data_folder():
    return os.path.join(get_cached_app_base_dir(), "AccountManagerData")


def set_windows_app_user_model_id():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RobloxAccountManager.App")
    except Exception:
        pass


def _apply_update_mode(argv):
    pid = None
    source = None
    target = None

    try:
        args = iter(argv[1:])
        for arg in args:
            if arg == "--pid":
                pid = int(next(args))
            elif arg == "--source":
                source = next(args)
            elif arg == "--target":
                target = next(args)
    except Exception:
        pid = None

    if not pid or not source or not target:
        return 2

    try:
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            ctypes.windll.kernel32.WaitForSingleObject(handle, 120000)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        time.sleep(3)

    try:
        if not os.path.isfile(source):
            raise FileNotFoundError(source)

        backup_path = target + ".old"
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except Exception:
            pass

        try:
            if os.path.exists(target):
                os.replace(target, backup_path)
        except Exception:
            pass

        os.replace(source, target)

        subprocess.Popen([target], close_fds=True)
        return 0
    except Exception as exc:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Update Failed", f"Failed to apply update: {exc}")
            root.destroy()
        except Exception:
            pass
        return 1


def setup_icon(data_folder):
    icon_path = os.path.join(data_folder, "icon.ico")

    if not os.path.isfile(icon_path):
        bundled_icon_path = os.path.join(get_cached_app_base_dir(), "icon.ico")
        if os.path.isfile(bundled_icon_path):
            try:
                shutil.copyfile(bundled_icon_path, icon_path)
            except Exception:
                pass

    if not os.path.isfile(icon_path):
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/hackyue/ForkedRobloxAccountManager/Windows/icon.ico",
                timeout=10,
            )
            if response.status_code == 200:
                with open(icon_path, "wb") as f:
                    f.write(response.content)
        except Exception:
            pass

    return icon_path if os.path.isfile(icon_path) else None


def main():
    """Main application entry point"""
    data_folder = get_data_folder()
    os.makedirs(data_folder, exist_ok=True)

    encryption_config_path = os.path.join(data_folder, "encryption_config.json")
    encryption_config = EncryptionConfig(encryption_config_path)

    password = None
    if not encryption_config.is_encryption_enabled() and not encryption_config.is_no_encryption_chosen():
        password = setup_encryption()
        encryption_config = EncryptionConfig(encryption_config_path)

    if encryption_config.is_encryption_enabled() and encryption_config.get_encryption_method() == "password":
        if password is None:
            root = tk.Tk()
            root.withdraw()
            password = simpledialog.askstring("Password Required", "Enter your password to unlock:", show="*")
            root.destroy()

            if password is None:
                messagebox.showerror("Error", "Password is required to access encrypted accounts.")
                return

    try:
        manager = RobloxAccountManager(password=password)
    except ValueError:
        messagebox.showerror("Error", "Password is invalid. Please try again.")
        return
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize: {e}")
        return

    icon_path = setup_icon(data_folder)

    set_windows_app_user_model_id()
    root = tk.Tk()
    if icon_path:
        try:
            root.iconbitmap(default=icon_path)
        except Exception:
            pass

    app = AccountManagerUI(root, manager, icon_path=icon_path)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    if "--apply-update" in sys.argv:
        raise SystemExit(_apply_update_mode(sys.argv))
    main()
