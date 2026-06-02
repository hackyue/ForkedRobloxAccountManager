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
import threading
import traceback
import warnings
import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
from functools import lru_cache

warnings.filterwarnings("ignore")

from classes import AutoRejoinMonitor, RobloxAccountManager
from classes.encryption import EncryptionConfig
from utils.encryption_setup import setup_encryption
from utils.ui import AccountManagerUI, get_user_presence


def subprocess_no_window_kwargs():
    if os.name != "nt":
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


ADMIN_LAUNCH_ARGS = {"-admin", "--admin"}


def _clean_admin_launch_args(argv):
    return [arg for arg in argv if str(arg).lower() not in ADMIN_LAUNCH_ARGS]


def _has_admin_launch_arg(argv):
    return any(str(arg).lower() in ADMIN_LAUNCH_ARGS for arg in argv[1:])


def _is_windows_admin():
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _show_admin_launch_error(message):
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Administrator Launch Failed", message)
        root.destroy()
    except Exception:
        print(message)


def _admin_relaunch_exit_code_if_requested(argv):
    if not _has_admin_launch_arg(argv):
        return None

    cleaned_argv = [argv[0], *_clean_admin_launch_args(argv[1:])]
    sys.argv[:] = cleaned_argv

    if os.name != "nt":
        print("-admin is only supported on Windows.")
        return None

    if _is_windows_admin():
        return None

    if getattr(sys, "frozen", False):
        executable = sys.executable
        arguments = cleaned_argv[1:]
        working_dir = get_cached_app_base_dir()
    else:
        script_path = os.path.abspath(cleaned_argv[0] or __file__)
        executable = sys.executable
        arguments = [script_path, *cleaned_argv[1:]]
        working_dir = os.getcwd()

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            subprocess.list2cmdline(arguments),
            working_dir,
            1,
        )
    except Exception as exc:
        _show_admin_launch_error(f"Failed to request administrator access: {exc}")
        return 1

    if result <= 32:
        _show_admin_launch_error(f"The administrator session failed. Error code: {result}")
        return 1

    return 0


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

        subprocess.Popen([target], close_fds=True, **subprocess_no_window_kwargs())
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


def setup_icon(data_folder, allow_network=True):
    icon_path = os.path.join(data_folder, "icon.ico")

    if not os.path.isfile(icon_path):
        bundled_icon_path = os.path.join(get_cached_app_base_dir(), "icon.ico")
        if os.path.isfile(bundled_icon_path):
            try:
                shutil.copyfile(bundled_icon_path, icon_path)
            except Exception:
                pass

    if allow_network and not os.path.isfile(icon_path):
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


def install_bug_issue_hooks(root, app):
    """Route unhandled exceptions to the in-app GitHub issue prompt."""
    previous_sys_hook = sys.excepthook
    previous_tk_hook = getattr(root, "report_callback_exception", None)
    previous_thread_hook = getattr(threading, "excepthook", None)

    def _forward(exc_type, exc_value, exc_traceback, source):
        if exc_type in (KeyboardInterrupt, SystemExit):
            return
        try:
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        except Exception:
            pass
        try:
            app.report_unhandled_exception(exc_type, exc_value, exc_traceback, source=source)
        except Exception:
            pass

    def _sys_hook(exc_type, exc_value, exc_traceback):
        _forward(exc_type, exc_value, exc_traceback, source="sys")
        try:
            if callable(previous_sys_hook):
                previous_sys_hook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass

    def _tk_hook(exc_type, exc_value, exc_traceback):
        _forward(exc_type, exc_value, exc_traceback, source="tk")
        try:
            if callable(previous_tk_hook):
                previous_tk_hook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass

    sys.excepthook = _sys_hook
    root.report_callback_exception = _tk_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            try:
                exc_type = getattr(args, "exc_type", Exception)
                exc_value = getattr(args, "exc_value", Exception("Unknown thread error"))
                exc_traceback = getattr(args, "exc_traceback", None)
                _forward(exc_type, exc_value, exc_traceback, source="thread")
            except Exception:
                pass
            try:
                if callable(previous_thread_hook):
                    previous_thread_hook(args)
            except Exception:
                pass

        threading.excepthook = _thread_hook


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

    icon_path = setup_icon(data_folder, allow_network=False)

    set_windows_app_user_model_id()
    root = tk.Tk()
    if icon_path:
        try:
            root.iconbitmap(default=icon_path)
        except Exception:
            pass

    app = AccountManagerUI(root, manager, icon_path=icon_path)
    install_bug_issue_hooks(root, app)

    if not icon_path:
        def _load_icon_async() -> None:
            downloaded_icon_path = setup_icon(data_folder, allow_network=True)
            if not downloaded_icon_path:
                return

            def _apply_icon() -> None:
                app.set_icon_path(downloaded_icon_path)

            try:
                root.after(0, _apply_icon)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=_load_icon_async, daemon=True, name="load-app-icon").start()

    auto_rejoin_monitor = AutoRejoinMonitor(
        launch_callback=app.launch_auto_rejoin_session,
        presence_lookup=get_user_presence,
        log_callback=app.log_auto_rejoin_event,
        status_callback=app.set_account_rejoin_status,
        validate_account_callback=lambda username: manager.validate_account(username, verbose=False),
    )
    manager.set_auto_rejoin_monitor(auto_rejoin_monitor)
    app.set_auto_rejoin_monitor(auto_rejoin_monitor)
    auto_rejoin_monitor.start()
    root.protocol("WM_DELETE_WINDOW", app.handle_app_close)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        try:
            app.handle_app_close()
        except Exception:
            pass


if __name__ == "__main__":
    if "--apply-update" in sys.argv:
        raise SystemExit(_apply_update_mode(sys.argv))
    admin_relaunch_exit_code = _admin_relaunch_exit_code_if_requested(sys.argv)
    if admin_relaunch_exit_code is not None:
        raise SystemExit(admin_relaunch_exit_code)
    main()
