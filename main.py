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
from ctypes import wintypes
import warnings
import tkinter as tk
from tkinter import messagebox, simpledialog

warnings.filterwarnings("ignore")

from classes import RobloxAccountManager
from classes.encryption import EncryptionConfig
from utils.encryption_setup import setup_encryption
from utils.ui import AccountManagerUI


def _apply_update_mode(argv):
    pid = None
    source = None
    target = None

    try:
        if "--pid" in argv:
            pid = int(argv[argv.index("--pid") + 1])
        if "--source" in argv:
            source = argv[argv.index("--source") + 1]
        if "--target" in argv:
            target = argv[argv.index("--target") + 1]
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


def main():
    """Main application entry point"""
    password = setup_encryption()
    
    data_folder = "AccountManagerData"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    
    encryption_config = EncryptionConfig(os.path.join(data_folder, "encryption_config.json"))
    
    if encryption_config.is_encryption_enabled() and encryption_config.get_encryption_method() == 'password':
        if password is None:
            root = tk.Tk()
            root.withdraw()
            password = simpledialog.askstring("Password Required", "Enter your password to unlock:", show='*')
            root.destroy()
            
            if password is None:
                messagebox.showerror("Error", "Password is required to access encrypted accounts.")
                return
    
    try:
        manager = RobloxAccountManager(password=password)
    except ValueError as e:
        messagebox.showerror("Error", "Password is invalid. Please try again.")
        return
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize: {e}")
        return
    
    root = tk.Tk()
    app = AccountManagerUI(root, manager)

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
