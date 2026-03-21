"""
UI Module for Roblox Account Manager
Contains the main AccountManagerUI class
"""

import os
import re
import sys
import io
import traceback
import tempfile
import zipfile
import shutil
import hashlib
import requests
import json
import math
import csv
import atexit
import platform
import time
import subprocess
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import msvcrt
import ctypes
from ctypes import wintypes

if platform.system() == "Windows":
    import win32api
    import win32con
    import win32gui
    import webbrowser
    import win32process
else:
    win32api = win32con = win32gui = win32process = None

from classes.roblox_api import RobloxAPI
from classes.fastflags import FastFlagsManager


ROBLOX_CLIENT_SETTINGS_URL = "https://clientsettings.roblox.com/v2/client-version/WindowsPlayer"
ROBLOX_DEPLOY_HISTORY_URL = "https://setup.rbxcdn.com/DeployHistory.txt"
DISCORD_SERVER_URL = "https://discord.gg/SpMTxg8YjJ"
DISCORD_LOGO_URL = (
    "https://raw.githubusercontent.com/hackyue/icons/refs/heads/main/discord-square-color-icon.png"
)

ROBLOX_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/octet-stream,application/zip;q=0.9,*/*;q=0.8",
    "Referer": "https://www.roblox.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

RDD_HOST_PATH = "https://setup-aws.rbxcdn.com"

RDD_BINARY_TYPES = {
    "WindowsPlayer": {
        "blob_dir": "/"
    },
    "WindowsStudio64": {
        "blob_dir": "/"
    },
}

RDD_EXTRACT_ROOTS = {
    "player": {
        "RobloxApp.zip": "",
        "redist.zip": "",
        "shaders.zip": "shaders/",
        "ssl.zip": "ssl/",
        "WebView2.zip": "",
        "WebView2RuntimeInstaller.zip": "WebView2RuntimeInstaller/",
        "content-avatar.zip": "content/avatar/",
        "content-configs.zip": "content/configs/",
        "content-fonts.zip": "content/fonts/",
        "content-sky.zip": "content/sky/",
        "content-sounds.zip": "content/sounds/",
        "content-textures2.zip": "content/textures/",
        "content-models.zip": "content/models/",
        "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
        "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
        "content-terrain.zip": "PlatformContent/pc/terrain/",
        "content-textures3.zip": "PlatformContent/pc/textures/",
        "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
        "extracontent-translations.zip": "ExtraContent/translations/",
        "extracontent-models.zip": "ExtraContent/models/",
        "extracontent-textures.zip": "ExtraContent/textures/",
        "extracontent-places.zip": "ExtraContent/places/",
    },
    "studio": {
        "RobloxStudio.zip": "",
        "RibbonConfig.zip": "RibbonConfig/",
        "redist.zip": "",
        "Libraries.zip": "",
        "LibrariesQt5.zip": "",
        "WebView2.zip": "",
        "WebView2RuntimeInstaller.zip": "",
        "shaders.zip": "shaders/",
        "ssl.zip": "ssl/",
        "Qml.zip": "Qml/",
        "Plugins.zip": "Plugins/",
        "StudioFonts.zip": "StudioFonts/",
        "BuiltInPlugins.zip": "BuiltInPlugins/",
        "ApplicationConfig.zip": "ApplicationConfig/",
        "BuiltInStandalonePlugins.zip": "BuiltInStandalonePlugins/",
        "content-qt_translations.zip": "content/qt_translations/",
        "content-sky.zip": "content/sky/",
        "content-fonts.zip": "content/fonts/",
        "content-avatar.zip": "content/avatar/",
        "content-models.zip": "content/models/",
        "content-sounds.zip": "content/sounds/",
        "content-configs.zip": "content/configs/",
        "content-api-docs.zip": "content/api_docs/",
        "content-textures2.zip": "content/textures/",
        "content-studio_svg_textures.zip": "content/studio_svg_textures/",
        "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
        "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries/",
        "content-terrain.zip": "PlatformContent/pc/terrain/",
        "content-textures3.zip": "PlatformContent/pc/textures/",
        "extracontent-translations.zip": "ExtraContent/translations/",
        "extracontent-luapackages.zip": "ExtraContent/LuaPackages/",
        "extracontent-textures.zip": "ExtraContent/textures/",
        "extracontent-scripts.zip": "ExtraContent/scripts/",
        "extracontent-models.zip": "ExtraContent/models/",
        "studiocontent-models.zip": "StudioContent/models/",
        "studiocontent-textures.zip": "StudioContent/textures/",
    },
}

RDD_APP_SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Settings>
\t<ContentFolder>content</ContentFolder>
\t<BaseUrl>http://www.roblox.com</BaseUrl>
</Settings>
"""

MIN_LAUNCH_DELAY_SECONDS = 0.0
MAX_LAUNCH_DELAY_SECONDS = 60.0

MIN_INSTALLER_PREVIOUS_VERSIONS = 5
MAX_INSTALLER_PREVIOUS_VERSIONS = 15

# Win32 flags used for force-resizing Roblox windows (test.py approach).
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOSENDCHANGING = 0x0400
GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
INVALID_ACCOUNT_SYMBOL = "\u26A0"


def clamp_multi_launch_delay(value):
    """Clamp arbitrary input to the allowed multi-launch delay range."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = MIN_LAUNCH_DELAY_SECONDS
    return max(MIN_LAUNCH_DELAY_SECONDS, min(MAX_LAUNCH_DELAY_SECONDS, numeric))


def clamp_installer_previous_versions(value):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        int_value = MIN_INSTALLER_PREVIOUS_VERSIONS
    return max(MIN_INSTALLER_PREVIOUS_VERSIONS, min(MAX_INSTALLER_PREVIOUS_VERSIONS, int_value))


def subprocess_no_window_kwargs():
    """Return subprocess kwargs that prevent transient console windows on Windows."""
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


THEMES = {
    "Synapse Neon": {
        "root_bg": "#05050b",
        "frame_bg": "#0f0f1c",
        "panel_bg": "#13132b",
        "panel_alt": "#1c1c3a",
        "text": "#f6f7fb",
        "text_muted": "#b7b9d6",
        "accent": "#8d5cf7",
        "accent_alt": "#18e0ff",
        "entry_bg": "#1b1b33",
        "entry_fg": "#f6f7fb",
        "border": "#5f2eea",
        "hover_bg": "#1f1f39",
        "list_bg": "#161631",
        "list_select": "#18e0ff",
        "font": "Consolas",
        "font_size": 10
    },
    "ScriptWare Minimal": {
        "root_bg": "#111217",
        "frame_bg": "#16171d",
        "panel_bg": "#1d1f26",
        "panel_alt": "#22242c",
        "text": "#f0f2f7",
        "text_muted": "#c8ccd8",
        "accent": "#6ab0ff",
        "accent_alt": "#d9dde8",
        "entry_bg": "#1f2129",
        "entry_fg": "#f5f7fb",
        "border": "#2a2d36",
        "hover_bg": "#272a34",
        "list_bg": "#1c1e25",
        "list_select": "#6ab0ff",
        "font": "Consolas",
        "font_size": 10
    },
    "Voxlis Vapor": {
        "root_bg": "#042f33",
        "frame_bg": "#0a3f4b",
        "panel_bg": "#0e4c5c",
        "panel_alt": "#135b6d",
        "text": "#e7fbff",
        "text_muted": "#b9e6f0",
        "accent": "#4ef0ff",
        "accent_alt": "#8efaf2",
        "entry_bg": "#0d3d49",
        "entry_fg": "#e2fbff",
        "border": "#68f6ff",
        "hover_bg": "#136374",
        "list_bg": "#0b3b47",
        "list_select": "#4ef0ff",
        "font": "Montserrat",
        "font_size": 10
    },
    "Potassium Ion": {
        "root_bg": "#050406",
        "frame_bg": "#0b0a0f",
        "panel_bg": "#120f18",
        "panel_alt": "#1d1723",
        "text": "#fef9c3",
        "text_muted": "#fcd34d",
        "accent": "#ffd500",
        "accent_alt": "#fffd8c",
        "entry_bg": "#1a1421",
        "entry_fg": "#fff9bf",
        "border": "#ffd500",
        "hover_bg": "#251c2d",
        "list_bg": "#151019",
        "list_select": "#ffd500",
        "font": "Orbitron",
        "font_size": 10
    },
    "Midnight Matrix": {
        "root_bg": "#000000",
        "frame_bg": "#030b0c",
        "panel_bg": "#041416",
        "panel_alt": "#062024",
        "text": "#9cffc7",
        "text_muted": "#5dd39b",
        "accent": "#00ff7f",
        "accent_alt": "#6bffa8",
        "entry_bg": "#041a1c",
        "entry_fg": "#d0ffe8",
        "border": "#00ff7f",
        "hover_bg": "#082d32",
        "list_bg": "#031214",
        "list_select": "#00ff7f",
        "font": "IBM Plex Mono",
        "font_size": 10
    },
    "Aurora Fade": {
        "root_bg": "#2b153d",
        "frame_bg": "#311846",
        "panel_bg": "#381d52",
        "panel_alt": "#432263",
        "text": "#f9e8ff",
        "text_muted": "#d8b4fe",
        "accent": "#ff99d6",
        "accent_alt": "#b8a2ff",
        "entry_bg": "#3f225c",
        "entry_fg": "#fff2ff",
        "border": "#f472b6",
        "hover_bg": "#4b2670",
        "list_bg": "#341b4c",
        "list_select": "#ff99d6",
        "font": "Poppins",
        "font_size": 10
    },
    "ChromePulse": {
        "root_bg": "#1a1c20",
        "frame_bg": "#212428",
        "panel_bg": "#262a2f",
        "panel_alt": "#2d3238",
        "text": "#f2f5ff",
        "text_muted": "#cdd5e0",
        "accent": "#58c5ff",
        "accent_alt": "#88d8ff",
        "entry_bg": "#2b3036",
        "entry_fg": "#f2f5ff",
        "border": "#7dd3ff",
        "hover_bg": "#343941",
        "list_bg": "#24282e",
        "list_select": "#58c5ff",
        "font": "Eurostile",
        "font_size": 10
    },
    "Stardust OS": {
        "root_bg": "#05030a",
        "frame_bg": "#0b0714",
        "panel_bg": "#100a1c",
        "panel_alt": "#170f29",
        "text": "#f0e7ff",
        "text_muted": "#cdb4ff",
        "accent": "#b46bff",
        "accent_alt": "#7dd3ff",
        "entry_bg": "#120c20",
        "entry_fg": "#f4ecff",
        "border": "#d8b4fe",
        "hover_bg": "#1f1435",
        "list_bg": "#0f0a1b",
        "list_select": "#b46bff",
        "font": "Raleway",
        "font_size": 10
    }
}


class _ConsoleStreamProxy(io.TextIOBase):
    def __init__(self, buffer, stream_label, target_stream):
        self.buffer = buffer
        self.stream_label = stream_label
        self.target_stream = target_stream

    def write(self, data):
        if not data:
            return 0
        safe_data = self.buffer.sanitize_text(data)
        if self.target_stream:
            self.target_stream.write(safe_data)
        self.buffer.append_text(safe_data, self.stream_label)
        return len(data)

    def flush(self):
        if self.target_stream:
            self.target_stream.flush()


class ConsoleOutputBuffer:
    """Capture stdout/stderr prints with timestamps for in-app viewing."""

    def __init__(self, max_entries=5000):
        self.max_entries = max_entries
        self.entries = []
        self.lock = threading.Lock()
        self.partials = {"STDOUT": "", "STDERR": ""}
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stdout_proxy = None
        self.stderr_proxy = None
        self._redaction_enabled_getter = None
        atexit.register(self._cleanup)

    def set_redaction_enabled_getter(self, getter):
        self._redaction_enabled_getter = getter

    def _is_redaction_enabled(self):
        if not callable(self._redaction_enabled_getter):
            return False
        try:
            return bool(self._redaction_enabled_getter())
        except Exception:
            return False

    def sanitize_text(self, text):
        if not text or not self._is_redaction_enabled():
            return text

        redacted = text

        # JSON-like fields: "password": "...", "cookie": "...", etc.
        redacted = re.sub(
            r'(?i)(\"(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\"\s*:\s*\")([^\"]*)(\")',
            r"\1[REDACTED]\3",
            redacted,
        )
        redacted = re.sub(
            r"(?i)('(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)'\s*:\s*')([^']*)(')",
            r"\1[REDACTED]\3",
            redacted,
        )

        # Key/value pairs in plain logs.
        redacted = re.sub(
            r"(?i)\b(password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)",
            r"\1\2[REDACTED]",
            redacted,
        )

        # Query-string params.
        redacted = re.sub(
            r"(?i)([?&](?:password|pass|token|cookie|auth|authorization)=)([^&\s]+)",
            r"\1[REDACTED]",
            redacted,
        )

        # Roblox security cookie in headers or cookie strings.
        redacted = re.sub(
            r"(?i)(\.ROBLOSECURITY\s*=\s*)([^;\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(\.ROBLOSECURITY\s*[:=]\s*)([^;\s]+)",
            r"\1[REDACTED]",
            redacted,
        )

        # Redact username segment in local filesystem paths.
        redacted = re.sub(
            r"(?i)([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\\/]+Users[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\\/]+home[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )

        return redacted

    def start_capture(self):
        if self.stdout_proxy and self.stderr_proxy:
            return
        self.stdout_proxy = _ConsoleStreamProxy(self, "OUT", self.original_stdout)
        self.stderr_proxy = _ConsoleStreamProxy(self, "ERR", self.original_stderr)
        sys.stdout = self.stdout_proxy
        sys.stderr = self.stderr_proxy

    def stop_capture(self):
        if self.stdout_proxy:
            sys.stdout = self.original_stdout
            self.stdout_proxy = None
        if self.stderr_proxy:
            sys.stderr = self.original_stderr
            self.stderr_proxy = None

    def _cleanup(self):
        self.stop_capture()
        self.clear()

    def append_text(self, data, label):
        if not data:
            return
        key = "STDOUT" if label == "OUT" else "STDERR"
        with self.lock:
            buffer = self.partials[key] + data
            lines = buffer.split("\n")
            self.partials[key] = lines.pop() if buffer.endswith("\n") is False else ""
            for line in lines:
                cleaned = line.rstrip("\r")
                if cleaned:
                    self._append_entry(key, cleaned)

    def _append_entry(self, label, line):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{label}] {line}"
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            overflow = len(self.entries) - self.max_entries
            if overflow > 0:
                self.entries = self.entries[overflow:]

    def get_entries_since(self, index):
        with self.lock:
            total = len(self.entries)
            start = min(max(index, 0), total)
            return self.entries[start:], total

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.partials = {"STDOUT": "", "STDERR": ""}


class ConsoleOutputWindow:
    """Dedicated console output viewer window."""

    POLL_INTERVAL_MS = 400

    def __init__(self, ui, capture):
        self.ui = ui
        self.capture = capture
        self.window = None
        self.text_widget = None
        self.after_id = None
        self.last_index = 0

    def show(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            self.update_topmost(self.ui.settings.get("enable_topmost", False))
            return

        self.window = tk.Toplevel(self.ui.root)
        self.window.title("Console Output")
        self.window.geometry("700x500")
        self.window.minsize(500, 450)
        self.window.configure(bg=self.ui.BG_DARK)
        self.window.resizable(True, True)
        self.window.transient(self.ui.root)
        self.window.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.update_topmost(self.ui.settings.get("enable_topmost", False))
        self.ui.register_toplevel(self.window)

        main_frame = ttk.Frame(self.window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        text_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        text_frame.pack(fill="both", expand=True)

        self.text_widget = tk.Text(
            text_frame,
            bg=self.ui.BG_MID,
            fg=self.ui.FG_TEXT,
            insertbackground=self.ui.FG_TEXT,
            state="disabled",
            wrap="word",
            relief="flat"
        )
        self.text_widget.pack(side="left", fill="both", expand=True)
        self.ui.register_themable_text_widget(self.text_widget)

        scrollbar = ttk.Scrollbar(text_frame, command=self.text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text="Clear", style="Dark.TButton", command=self.clear).pack(side="left", padx=(0, 5))
        ttk.Button(button_frame, text="Copy All", style="Dark.TButton", command=self.copy_all).pack(side="left", padx=5)

        self.last_index = 0
        entries, self.last_index = self.capture.get_entries_since(0)
        self._append_entries(entries, replace=True)
        self._schedule_poll()

    def _schedule_poll(self):
        if not self.window:
            return
        self.after_id = self.window.after(self.POLL_INTERVAL_MS, self._poll_updates)

    def _poll_updates(self):
        if not self.window:
            return
        entries, new_index = self.capture.get_entries_since(self.last_index)
        if entries:
            self._append_entries(entries)
        self.last_index = new_index
        self._schedule_poll()

    def _append_entries(self, entries, replace=False):
        if not self.text_widget or not entries and not replace:
            if replace and self.text_widget:
                self._set_text("")
            return
        text_to_add = "\n".join(entries)
        if text_to_add:
            text_to_add += "\n"
        self.text_widget.configure(state="normal")
        if replace:
            self.text_widget.delete("1.0", tk.END)
        if text_to_add:
            self.text_widget.insert(tk.END, text_to_add)
        self.text_widget.configure(state="disabled")
        self.text_widget.see(tk.END)

    def _set_text(self, value):
        if not self.text_widget:
            return
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", tk.END)
        if value:
            self.text_widget.insert(tk.END, value)
        self.text_widget.configure(state="disabled")
        self.text_widget.see(tk.END)

    def clear(self):
        self.capture.clear()
        self.last_index = 0
        self._set_text("")

    def copy_all(self):
        if not self.window or not self.text_widget:
            return
        try:
            text = self.text_widget.get("1.0", "end-1c")
            self.window.clipboard_clear()
            self.window.clipboard_append(text)
        except Exception:
            pass

    def _stop_poll(self):
        if self.window and self.after_id:
            try:
                self.window.after_cancel(self.after_id)
            except Exception:
                pass
        self.after_id = None

    def _handle_close(self):
        self._stop_poll()
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = None
        self.text_widget = None

    def update_topmost(self, enabled):
        if self.window:
            self.window.attributes("-topmost", bool(enabled))

    def apply_theme(self):
        if not self.window or not self.text_widget:
            return
        self.window.configure(bg=self.ui.BG_DARK)
        self.text_widget.configure(bg=self.ui.BG_MID, fg=self.ui.FG_TEXT, insertbackground=self.ui.FG_TEXT)


_CONSOLE_OUTPUT_BUFFER = None


def get_console_output_buffer():
    global _CONSOLE_OUTPUT_BUFFER
    if _CONSOLE_OUTPUT_BUFFER is None:
        _CONSOLE_OUTPUT_BUFFER = ConsoleOutputBuffer()
        _CONSOLE_OUTPUT_BUFFER.start_capture()
    return _CONSOLE_OUTPUT_BUFFER


class AccountManagerUI:
    ROBLOX_CLIENT_EXECUTABLES = {
        "robloxplayerbeta.exe",
        "robloxplayerlauncher.exe",
    }

    def __init__(self, root, manager, icon_path=None):
        self.root = root
        self.manager = manager
        self.icon_path = icon_path
        self.APP_VERSION = "2.4.2"
        self._game_name_after_id = None
        self._game_name_label_after_id = None
        self._game_name_request_token = 0
        self._last_game_name_query_value = None

        self._auto_relaunch_after_id = None
        self._auto_relaunch_in_progress = False
        self._auto_memory_trim_after_id = None
        self._auto_memory_trim_in_progress = False
        self._auto_update_check_started = False
        self._auto_update_prompt_shown = False

        self.multi_roblox_handle = None
        self._pid_account_map = {}
        self._pid_launch_context_map = {}
        self._pid_account_lock = threading.Lock()
        self._tracked_roblox_exes = {
            "robloxplayerbeta.exe",
            "robloxstudiobeta.exe",
            "robloxplayerlauncher.exe",
            "robloxstudiolauncherbeta.exe",
        }

        self.console_output = get_console_output_buffer()
        self.console_window = ConsoleOutputWindow(self, self.console_output)
        self._account_validation_status = {}
        self._startup_validation_started = False
        self._startup_validation_in_progress = False

        self.account_list_drag_data = {
            "start_index": None,
            "drop_index": None,
            "start_username": None,
            "start_y": None,
            "is_dragging": False,
        }
        self.account_drop_indicator = None

        self.themable_text_widgets = []
        self.themable_windows = set()
        self._theme_refresh_callbacks = {}

        self.menu_bar = None
        self.actions_menu = None
        self.installer_menu = None
        self.add_account_menu = None
        self.account_context_menu = None
        self.launch_input_context_menu = None
        self.place_target_context_menu = None
        self.menu_bar_frame = None
        self.menu_buttons = []
        self.version_options = {"Latest Version": None}
        self.installer_dialog_state = None
        self._installer_versions_cache = None
        self._http_session = None
        self._http_session_lock = threading.Lock()
        self._settings_save_after_ids = {}
        self._discord_button_image = None

        self.global_settings_window = None
        self.global_settings_values = None
        self.global_settings_meta = None
        self.global_settings_xml_names = None
        self.fastflags_window = None
        self.instance_manager_window = None

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.status_label = None
        
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except:
                pass
        
        self.root.title("FRAM v2.4.2 - made by evanovar - modified by hackyue")
        self.root.geometry("600x600")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(True, True)
        self.root.minsize(600, 700)  # Note to self, this shit so ass
        
        self.data_folder = "AccountManagerData"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        self.settings_file = os.path.join(self.data_folder, "ui_settings.json")
        self.load_settings()
        self.console_output.set_redaction_enabled_getter(
            lambda: bool(self.settings.get("hide_sensitive_info", False))
        )
        try:
            self.root.attributes("-topmost", bool(self.settings.get("enable_topmost", False)))
        except Exception:
            pass
        self.theme_name = self.settings.get("selected_theme", "Synapse Neon")

        self.apply_theme(self.theme_name, persist=True)
        self.register_toplevel(self.root)
        self.root.after(50, self._apply_title_bar_theme_all)

      
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.build_main_menu()

        main_frame = ttk.Frame(self.root, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)

        left_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_rowconfigure(1, weight=1)  

        header_frame = ttk.Frame(left_frame, style="Dark.TFrame")
        header_frame.pack(fill="x", anchor="w")
        
        ttk.Label(header_frame, text="Account List", style="Dark.TLabel").pack(side="left")
        
        encryption_status = ""
        encryption_color = self.FG_TEXT
        if self.manager.encryption_config.is_encryption_enabled():
            method = self.manager.encryption_config.get_encryption_method()
            if method == 'hardware':
                encryption_status = "[HARDWARE ENCRYPTED]"
                encryption_color = "#90EE90"
            elif method == 'password':
                encryption_status = "[PASSWORD ENCRYPTED]"
                encryption_color = "#87CEEB"
        else:
            encryption_status = "[NOT ENCRYPTED]"
            encryption_color = "#FFB6C1"
            
        self.status_label = tk.Label(
            header_frame,
            text=encryption_status,
            bg=self.BG_DARK,
            fg=encryption_color,
            font=("Segoe UI", 8, "bold")
        )
        self.status_label.pack(side="right", padx=(5, 0))

        group_frame = ttk.Frame(left_frame, style="Dark.TFrame")
        group_frame.pack(fill="x", pady=(6, 0))

        ttk.Label(group_frame, text="Group", style="Dark.TLabel").pack(side="left")

        self.group_var = tk.StringVar()
        self.group_dropdown = ttk.Combobox(
            group_frame,
            textvariable=self.group_var,
            state="readonly",
            style="Dark.TCombobox",
            width=12,
        )
        self.group_dropdown.pack(side="right", fill="x", expand=True)
        self.group_dropdown.bind("<<ComboboxSelected>>", self.on_group_change)
        self.refresh_group_dropdown_values()

        list_frame = ttk.Frame(left_frame, style="Dark.TFrame")
        list_frame.pack(fill="both", expand=True, pady=(5, 0))

        selectmode = tk.EXTENDED if self.settings.get("enable_multi_select", False) else tk.SINGLE
        
        self.account_list = tk.Listbox(
            list_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            selectbackground=self.FG_ACCENT,
            highlightthickness=0,
            border=0,
            font=("Segoe UI", 10),
            width=20,
            selectmode=selectmode,
        )
        self.account_list.pack(side="left", fill="both", expand=True, pady=2)
        self.account_list.bind("<ButtonPress-1>", self.on_account_drag_start)
        self.account_list.bind("<B1-Motion>", self.on_account_drag_motion)
        self.account_list.bind("<ButtonRelease-1>", self.on_account_drag_stop)
        self.account_list.bind("<Button-3>", self.show_account_context_menu)
        if self.settings.get("enable_multi_select", False):
            self.account_list.bind("<Control-ButtonPress-1>", self.on_account_ctrl_click)

        self.account_context_menu = tk.Menu(self.root, tearoff=False)
        self.account_context_menu.add_command(label="Copy Username", command=self.copy_selected_account_usernames)
        self.account_context_menu.add_command(label="Copy Password", command=self.copy_selected_account_passwords)
        self.account_context_menu.add_command(label="Copy Cookie", command=self.copy_selected_account_cookies)
        self.account_context_menu.add_separator()
        self.account_context_menu.add_command(label="Validate Account", command=self.validate_account)
        self.account_context_menu.add_command(label="Edit Note", command=self.edit_account_note)
        self.account_context_menu.add_command(label="Set Group", command=self.edit_account_group)

        self.account_drop_indicator = tk.Frame(self.account_list, height=2, bg=self.FG_ACCENT)

        scrollbar = ttk.Scrollbar(list_frame, command=self.account_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.account_list.config(yscrollcommand=scrollbar.set)

        right_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(3, weight=1)  
        
        self.game_name_label = ttk.Label(right_frame, text="", style="Dark.TLabel", font=("Segoe UI", 9))
        self.game_name_label.pack(anchor="w", pady=(0, 5))

        self.launch_input_mode = "place_id"
        self.place_label = ttk.Label(right_frame, text="Place ID", style="Dark.TLabel", font=("Segoe UI", 9, "bold"))
        self.place_label.pack(anchor="w")
        self.place_entry = ttk.Entry(right_frame, style="Dark.TEntry")
        self.place_entry.pack(fill="x", pady=(0, 5))
        self.place_entry.insert(0, self.settings.get("last_place_id", ""))
        self.place_entry.bind("<KeyRelease>", self.on_place_id_change)
        self.place_label.bind("<Button-3>", self.show_launch_input_context_menu)
        self.place_entry.bind("<Button-3>", self.show_launch_input_context_menu)

        self.private_server_field_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        self.private_server_field_frame.pack(fill="x", pady=(0, 5))
        self.private_server_label = ttk.Label(
            self.private_server_field_frame,
            text="Private Server ID (Optional)",
            style="Dark.TLabel",
            font=("Segoe UI", 9, "bold"),
        )
        self.private_server_label.pack(anchor="w")
        self.private_server_entry = ttk.Entry(self.private_server_field_frame, style="Dark.TEntry")
        self.private_server_entry.pack(fill="x")
        self.private_server_entry.insert(0, self.settings.get("last_private_server", ""))
        self.private_server_entry.bind("<KeyRelease>", self.on_private_server_change)
        self.private_server_label.bind("<Button-3>", self.show_place_target_context_menu)
        self.private_server_entry.bind("<Button-3>", self.show_place_target_context_menu)

        self.version_label = ttk.Label(right_frame, text="Roblox Version (Optional)", style="Dark.TLabel", font=("Segoe UI", 9, "bold"))
        self.version_label.pack(anchor="w", pady=(5, 0))
        self.version_var = tk.StringVar()
        self.version_dropdown = ttk.Combobox(
            right_frame,
            textvariable=self.version_var,
            state="readonly",
            style="Dark.TCombobox"
        )
        self.version_dropdown.pack(fill="x", pady=(0, 10))
        

        self.load_roblox_versions()
        

        self.version_var.set("Latest Version")

        self.join_action_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        self.join_action_frame.pack(fill="x", pady=(0, 10))

        self.join_place_button = ttk.Button(
            self.join_action_frame,
            text="Join Place ID",
            style="Dark.TButton",
            command=self.launch_game,
        )
        self.join_place_button.pack(side="left", fill="x", expand=True)
        self.join_place_button.bind("<Button-3>", self.show_launch_input_context_menu)

        self.launch_input_context_menu = tk.Menu(self.root, tearoff=False)
        self.place_target_context_menu = tk.Menu(self.root, tearoff=False)
        self.place_join_target_mode = "private_server"
        self._set_place_target_mode(self.settings.get("place_join_target_mode", "private_server"), save=False)
        self._set_launch_input_mode(self.settings.get("launch_input_mode", "place_id"), save=False)

        self.run_group_button = ttk.Button(
            self.join_action_frame,
            text="Run Group",
            style="Dark.TButton",
            command=self.launch_group_game,
        )
        self._run_group_button_visible = False

        for widget in (self.join_action_frame, self.join_place_button, self.run_group_button):
            widget.bind("<Enter>", self._on_join_area_enter)
            widget.bind("<Leave>", self._on_join_area_leave)
        
        self.recent_list_label = ttk.Label(right_frame, text="Recent games", style="Dark.TLabel", font=("Segoe UI", 9, "bold"))
        self.recent_list_label.pack(anchor="w", pady=(10, 2))
        
        game_list_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        game_list_frame.pack(fill="both", expand=True)
        
        self.game_list = tk.Listbox(
            game_list_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            selectbackground=self.FG_ACCENT,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            font=("Segoe UI", 9),
            height=5,
        )
        self.game_list.pack(side="left", fill="both", expand=True)
        self.game_list.bind("<<ListboxSelect>>", self.on_game_select)
        
        game_scrollbar = ttk.Scrollbar(game_list_frame, command=self.game_list.yview)
        game_scrollbar.pack(side="right", fill="y")
        self.game_list.config(yscrollcommand=game_scrollbar.set)
        
        ttk.Button(right_frame, text="Delete Selected", style="Dark.TButton", command=self.delete_game_from_list).pack(fill="x", pady=(5, 0))

        ttk.Label(right_frame, text="Quick Actions", style="Dark.TLabel").pack(anchor="w", pady=(10, 5))

        action_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        action_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(action_frame, text="Refresh List", style="Dark.TButton", command=self.refresh_accounts).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Arrange Clients", style="Dark.TButton", command=self.auto_arrange_clients).pack(fill="x", pady=2)
        self.trim_roblox_memory_btn = ttk.Button(
            action_frame,
            text="Trim Roblox Memory",
            style="Dark.TButton",
            command=self.trim_roblox_memory,
        )
        self.trim_roblox_memory_btn.pack(fill="x", pady=2)

        bottom_frame = ttk.Frame(self.root, style="Dark.TFrame")
        bottom_frame.pack(fill="x", padx=10, pady=(5, 10), anchor='s')

        self.add_account_split_btn = ttk.Button(
            bottom_frame,
            text="Add Account",
            style="Dark.TButton",
            command=self.add_account,
        )
        self.add_account_split_btn.pack(side="left", fill="both", expand=True, padx=(0, 2))
        self.add_account_split_btn.bind("<Button-3>", self.show_add_account_menu)

        self.add_account_menu = tk.Menu(self.root, tearoff=False)
        self.add_account_menu.add_command(label="Quick Sign-In", command=self.open_quick_sign_in_window)

        ttk.Button(bottom_frame, text="Remove", style="Dark.TButton", command=self.delete_account).pack(
            side="left", fill="both", expand=True, padx=2
        )

        ttk.Button(bottom_frame, text="Launch Browser", style="Dark.TButton", command=self.launch_home).pack(
            side="left", fill="both", expand=True, padx=2
        )
        ttk.Button(bottom_frame, text="Launch Roblox App", style="Dark.TButton", command=self.launch_home_app).pack(
            side="left", fill="both", expand=True, padx=2
        )
        ttk.Button(bottom_frame, text="Settings", style="Dark.TButton", command=self.open_settings).pack(
            side="left", fill="both", expand=True, padx=(2, 0)
        )

        self.refresh_accounts()
        self.refresh_game_list()
        self._schedule_startup_account_validation()

        self.root.after(500, self._auto_relaunch_maybe_start)
        self.root.after(500, self._auto_memory_trim_maybe_start)
        self.root.after(1500, self._auto_update_maybe_start)

    def load_settings(self):
        """Load UI settings from file"""
        defaults = {
            "last_place_id": "",
            "last_private_server": "",
            "launch_input_mode": "place_id",
            "place_join_target_mode": "private_server",
            "game_list": [],
            "recent_user_list": [],
            "enable_topmost": False,
            "enable_multi_roblox": False,
            "confirm_before_launch": False,
            "randomize_server_job_ids": False,
            "prefer_small_public_servers": False,
            "max_recent_games": 10,
            "enable_multi_select": False,
            "enable_debug_logging": False,
            "hide_sensitive_info": True,
            "bug_issue_prompt_enabled": True,
            "selected_theme": "Synapse Neon",
            "disable_success_popups": False,
            "auto_arrange_scope": "both",
            "auto_arrange_dimension_mode": "auto",
            "auto_arrange_target_width": 800,
            "auto_arrange_target_height": 600,
            "multi_launch_delay": MIN_LAUNCH_DELAY_SECONDS,
            "custom_roblox_player_path": "",
            "selected_group": "All",
            "auto_relaunch_enabled": False,
            "auto_relaunch_interval_minutes": 60,
            "auto_relaunch_group": "",
            "auto_memory_trim_enabled": False,
            "auto_memory_trim_interval_minutes": 5,
            "auto_arrange_after_group_launch": False,
            "auto_update_enabled": True,
            "installer_previous_versions": MIN_INSTALLER_PREVIOUS_VERSIONS,
            "browser_preference": "auto",
        }

        try:
            with open(self.settings_file, "r", encoding="utf-8") as settings_fp:
                self.settings = json.load(settings_fp)
        except Exception:
            self.settings = defaults.copy()

        for key, value in defaults.items():
            self.settings.setdefault(key, value)

        self.settings["multi_launch_delay"] = clamp_multi_launch_delay(
            self.settings.get("multi_launch_delay", MIN_LAUNCH_DELAY_SECONDS)
        )

        self.settings["installer_previous_versions"] = clamp_installer_previous_versions(
            self.settings.get("installer_previous_versions", MIN_INSTALLER_PREVIOUS_VERSIONS)
        )
        browser_pref = str(self.settings.get("browser_preference", "auto") or "auto").strip().lower()
        if browser_pref not in {"auto", "chrome", "firefox"}:
            browser_pref = "auto"
        self.settings["browser_preference"] = browser_pref

        self._ensure_auto_arrange_scope_valid()
        self._ensure_auto_arrange_dimension_settings_valid()
        if self.settings.get("enable_multi_roblox", False):
            self.root.after(100, self.initialize_multi_roblox)

        try:
            self.settings["auto_relaunch_interval_minutes"] = max(
                1,
                int(self.settings.get("auto_relaunch_interval_minutes", 60) or 60),
            )
        except (TypeError, ValueError):
            self.settings["auto_relaunch_interval_minutes"] = 60

        if "auto_memory_trim_interval_seconds" in self.settings:
            try:
                old_sec = int(self.settings.pop("auto_memory_trim_interval_seconds", 300) or 300)
            except (TypeError, ValueError):
                old_sec = 300
            migrated = max(1, min(120, int(round(old_sec / 60.0))))
            self.settings.setdefault("auto_memory_trim_interval_minutes", migrated)

        try:
            mm = int(self.settings.get("auto_memory_trim_interval_minutes", 5) or 5)
        except (TypeError, ValueError):
            mm = 5
        self.settings["auto_memory_trim_interval_minutes"] = max(1, min(120, mm))

    def _ensure_auto_arrange_scope_valid(self):
        """Keep auto-arrange scope sane, especially when only one monitor is available."""
        allowed_scopes = {"primary", "secondary", "both"}
        scope = self.settings.get("auto_arrange_scope", "both")
        if scope not in allowed_scopes:
            scope = "both"

        if not self._has_multiple_monitors():
            scope = "primary"

        self.settings["auto_arrange_scope"] = scope

    def _ensure_auto_arrange_dimension_settings_valid(self):
        """Validate dimension mode and preferred client size settings."""
        allowed_modes = {"auto", "target_size"}
        mode = self.settings.get("auto_arrange_dimension_mode", "auto")
        if mode not in allowed_modes:
            mode = "auto"
        self.settings["auto_arrange_dimension_mode"] = mode

        try:
            width = int(self.settings.get("auto_arrange_target_width", 800))
        except (TypeError, ValueError):
            width = 800
        try:
            height = int(self.settings.get("auto_arrange_target_height", 600))
        except (TypeError, ValueError):
            height = 600

        self.settings["auto_arrange_target_width"] = max(50, min(7680, width))
        self.settings["auto_arrange_target_height"] = max(50, min(4320, height))

    def _has_multiple_monitors(self):
        """Return True if more than one monitor is available."""
        if not win32api:
            return False

        try:
            monitors = win32api.EnumDisplayMonitors(None, None)
            return len(monitors) > 1
        except Exception:
            return False

    def _format_delay_value(self, value):
        """Return a user-friendly string for the launch delay value."""
        clamped_value = clamp_multi_launch_delay(value)
        if math.isclose(clamped_value, round(clamped_value)):
            return str(int(round(clamped_value)))
        return f"{clamped_value:.1f}".rstrip("0").rstrip(".")

    def _get_multi_launch_delay(self):
        """Return the current launch delay, clamped to the supported range."""
        return clamp_multi_launch_delay(self.settings.get("multi_launch_delay", MIN_LAUNCH_DELAY_SECONDS))

    def _get_preferred_browser(self):
        """Return browser automation preference: auto, chrome, or firefox."""
        value = str(self.settings.get("browser_preference", "auto") or "auto").strip().lower()
        if value not in {"auto", "chrome", "firefox"}:
            value = "auto"

        available = self._get_available_browsers()
        if not available:
            return value
        if len(available) == 1:
            return available[0]
        if value in {"auto", "chrome", "firefox"} and (value == "auto" or value in available):
            return value
        return "auto"

    def _is_browser_installed_locally(self, browser_name):
        name = str(browser_name or "").strip().lower()
        if name not in {"chrome", "firefox"}:
            return False

        try:
            if hasattr(self, "manager") and hasattr(self.manager, "_is_browser_installed"):
                return bool(self.manager._is_browser_installed(name))
        except Exception:
            pass

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
            else:
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

    def _get_available_browsers(self):
        available = []
        try:
            if hasattr(self, "manager") and hasattr(self.manager, "get_available_browsers"):
                manager_available = self.manager.get_available_browsers()
                if isinstance(manager_available, (list, tuple, set)):
                    for name in manager_available:
                        normalized = str(name or "").strip().lower()
                        if normalized in {"chrome", "firefox"} and normalized not in available:
                            available.append(normalized)
                    if available:
                        return available
        except Exception:
            pass

        if self._is_browser_installed_locally("chrome"):
            available.append("chrome")
        if self._is_browser_installed_locally("firefox"):
            available.append("firefox")
        return available

    def _focus_main_window(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        try:
            self.root.deiconify()
        except Exception:
            pass

        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

        if platform.system() != "Windows" or not win32gui:
            return

        try:
            hwnd = self.root.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
        except Exception:
            return

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _auto_relaunch_maybe_start(self):
        if self.settings.get("auto_relaunch_enabled", False):
            self._auto_relaunch_start()

    def _auto_relaunch_start(self):
        self._auto_relaunch_stop()
        if not self._auto_relaunch_config_valid():
            return

        interval_minutes = int(self.settings.get("auto_relaunch_interval_minutes", 60) or 60)
        interval_ms = max(1, interval_minutes) * 60 * 1000
        self._auto_relaunch_after_id = self.root.after(interval_ms, self._auto_relaunch_tick)

    def _auto_relaunch_stop(self):
        after_id = getattr(self, "_auto_relaunch_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._auto_relaunch_after_id = None

    def _auto_relaunch_config_valid(self):
        if not self.settings.get("auto_relaunch_enabled", False):
            return False

        group = (self.settings.get("auto_relaunch_group") or "").strip()
        if not group or group == "All":
            return False

        if group not in set(self.manager.get_groups()):
            return False

        try:
            interval = int(self.settings.get("auto_relaunch_interval_minutes", 60) or 60)
        except (TypeError, ValueError):
            return False
        return interval >= 1

    def _auto_relaunch_tick(self):
        self._auto_relaunch_after_id = None

        if self.settings.get("auto_relaunch_enabled", False):
            interval_minutes = int(self.settings.get("auto_relaunch_interval_minutes", 60) or 60)
            interval_ms = max(1, interval_minutes) * 60 * 1000
            self._auto_relaunch_after_id = self.root.after(interval_ms, self._auto_relaunch_tick)

        self._auto_relaunch_run_once()

    def _auto_relaunch_run_once(self):
        if not self._auto_relaunch_config_valid():
            return

        if getattr(self, "_auto_relaunch_in_progress", False):
            return

        group = (self.settings.get("auto_relaunch_group") or "").strip()
        usernames = self.manager.get_accounts_in_group(group)
        if not usernames:
            return

        game_id = self.place_entry.get().strip()
        if not game_id:
            return

        self._auto_relaunch_in_progress = True

        def worker(selected_group, selected_usernames):
            try:
                self._close_all_roblox_clients_silent()
                focus_delay_ms = int(self._get_multi_launch_delay() * 1000)
                self.root.after(
                    0,
                    lambda: self._launch_game_for_usernames(
                        selected_usernames,
                        confirm_group=selected_group,
                        skip_confirm=True,
                        trigger_auto_arrange=True,
                        on_done_callback=(
                            lambda success_count: self.root.after(focus_delay_ms, self._focus_main_window)
                            if success_count > 0 else None
                        ),
                    ),
                )
            finally:
                self._auto_relaunch_in_progress = False

        threading.Thread(target=worker, args=(group, list(usernames)), daemon=True).start()

    def _auto_memory_trim_maybe_start(self):
        if self.settings.get("auto_memory_trim_enabled", False):
            self._auto_memory_trim_start()

    def _auto_memory_trim_stop(self):
        after_id = getattr(self, "_auto_memory_trim_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._auto_memory_trim_after_id = None

    def _auto_memory_trim_config_valid(self):
        if platform.system() != "Windows":
            return False
        if not self.settings.get("auto_memory_trim_enabled", False):
            return False
        try:
            minutes = int(self.settings.get("auto_memory_trim_interval_minutes", 5) or 5)
        except (TypeError, ValueError):
            return False
        return 1 <= minutes <= 120

    def _auto_memory_trim_start(self):
        self._auto_memory_trim_stop()
        if not self._auto_memory_trim_config_valid():
            return
        minutes = int(self.settings.get("auto_memory_trim_interval_minutes", 5) or 5)
        minutes = max(1, min(120, minutes))
        interval_ms = max(1, minutes) * 60 * 1000
        self._auto_memory_trim_after_id = self.root.after(
            interval_ms, self._auto_memory_trim_tick
        )

    def _auto_memory_trim_tick(self):
        self._auto_memory_trim_after_id = None

        if self._auto_memory_trim_config_valid():
            minutes = int(self.settings.get("auto_memory_trim_interval_minutes", 5) or 5)
            minutes = max(1, min(120, minutes))
            interval_ms = minutes * 60 * 1000
            self._auto_memory_trim_after_id = self.root.after(
                interval_ms, self._auto_memory_trim_tick
            )

        self._auto_memory_trim_run_once()

    def _auto_memory_trim_run_once(self):
        if platform.system() != "Windows":
            return
        if not self.settings.get("auto_memory_trim_enabled", False):
            return
        if getattr(self, "_auto_memory_trim_in_progress", False):
            return

        self._auto_memory_trim_in_progress = True

        def worker():
            try:
                wins = self._memtrim_find_roblox_windows()
                if wins:
                    self._memtrim_run_pass(wins)
            finally:
                def _clear_busy():
                    self._auto_memory_trim_in_progress = False

                try:
                    self.root.after(0, _clear_busy)
                except Exception:
                    self._auto_memory_trim_in_progress = False

        threading.Thread(target=worker, daemon=True, name="auto-memory-trim").start()

    def _close_all_roblox_clients_silent(self):
        exes = set(self.ROBLOX_CLIENT_EXECUTABLES)
        exes.update({"RobloxPlayerBeta.exe", "RobloxPlayerLauncher.exe"})
        for exe in sorted(exes):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", exe],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    **subprocess_no_window_kwargs(),
                )
            except Exception:
                pass

    def show_success_message(self, message, title="Success"):
        """Show a success message if popups are enabled."""
        if not self.settings.get("disable_success_popups", False):
            messagebox.showinfo(title, message)

    def apply_theme(self, theme_name, persist=True):
        """Apply the selected theme to the UI."""
        theme = THEMES.get(theme_name)
        if theme is None:
            fallback_name = next(iter(THEMES.keys()))
            theme = THEMES[fallback_name]
            theme_name = fallback_name

        self.theme_name = theme_name
        self.BG_ROOT = theme["root_bg"]
        self.BG_DARK = theme["panel_bg"]
        self.BG_LIGHT = theme["panel_alt"]
        self.BG_MID = theme["panel_alt"]
        self.FG_TEXT = theme["text"]
        self.FG_MUTED = theme["text_muted"]
        self.FG_ACCENT = theme["accent"]
        self.FG_ACCENT_ALT = theme["accent_alt"]
        self.ENTRY_BG = theme["entry_bg"]
        self.ENTRY_FG = theme["entry_fg"]
        self.BORDER_COLOR = theme["border"]
        self.HOVER_BG = theme["hover_bg"]
        self.LIST_BG = theme["list_bg"]
        self.LIST_SELECT = theme["list_select"]
        self.FONT = (theme["font"], theme["font_size"])

        self.root.configure(bg=self.BG_ROOT)

        self.style.configure("Dark.TFrame", background=self.BG_DARK)
        self.style.configure("Dark.TLabel", background=self.BG_DARK, foreground=self.FG_TEXT, font=self.FONT)
        self.style.configure(
            "Dark.TButton",
            background=self.BG_LIGHT,
            foreground=self.FG_TEXT,
            font=self.FONT,
            padding=6
        )
        self.style.map("Dark.TButton", background=[("active", self.HOVER_BG)])
        self.style.configure(
            "Dark.TEntry",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG
        )
        self.style.configure(
            "Dark.TCombobox",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG
        )
        self.style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", self.ENTRY_BG)],
            foreground=[("readonly", self.ENTRY_FG)]
        )
        self.style.configure(
            "Dark.TSpinbox",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG
        )
        self.style.map(
            "Dark.TSpinbox",
            fieldbackground=[("readonly", self.ENTRY_BG)],
            foreground=[("readonly", self.ENTRY_FG)]
        )

        self.style.configure(
            "Dark.Treeview",
            background=self.LIST_BG,
            fieldbackground=self.LIST_BG,
            foreground=self.FG_TEXT,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
        )
        self.style.map(
            "Dark.Treeview",
            background=[("selected", self.FG_ACCENT)],
            foreground=[("selected", self.FG_TEXT)],
        )
        self.style.configure(
            "Dark.Treeview.Heading",
            background=self.BG_LIGHT,
            foreground=self.FG_TEXT,
            bordercolor=self.BORDER_COLOR,
            relief="flat",
            font=self.FONT,
        )
        self.style.map(
            "Dark.Treeview.Heading",
            background=[("active", self.HOVER_BG)],
            foreground=[("active", self.FG_TEXT)],
        )
        self.style.configure(
            "Dark.TCheckbutton",
            background=self.BG_DARK,
            foreground=self.FG_TEXT,
            font=("Segoe UI", 10),
        )
        self.style.map(
            "Dark.TCheckbutton",
            background=[("active", self.BG_MID)],
            foreground=[("disabled", self.FG_MUTED)],
        )

        if getattr(self, "status_label", None):
            self.status_label.configure(bg=self.BG_DARK)

        if getattr(self, "account_list", None):
            self.account_list.configure(
                bg=self.LIST_BG,
                fg=self.FG_TEXT,
                selectbackground=self.FG_ACCENT,
                highlightbackground=self.BORDER_COLOR,
                highlightcolor=self.BORDER_COLOR
            )
        if getattr(self, "account_drop_indicator", None):
            self.account_drop_indicator.configure(bg=self.FG_ACCENT)

        if getattr(self, "game_list", None):
            self.game_list.configure(
                bg=self.LIST_BG,
                fg=self.FG_TEXT,
                selectbackground=self.FG_ACCENT,
                highlightbackground=self.BORDER_COLOR,
                highlightcolor=self.BORDER_COLOR
            )

        self._apply_menu_palette_defaults()
        self.apply_menu_theme()
        if getattr(self, "console_window", None):
            self.console_window.apply_theme()

        self._apply_themable_text_widgets()
        self._apply_theme_refresh_callbacks()
        self._apply_title_bar_theme_all()

        if persist:
            self.settings["selected_theme"] = theme_name
            self.save_settings()

    def register_themable_text_widget(self, widget):
        if widget not in self.themable_text_widgets:
            self.themable_text_widgets.append(widget)
        self._apply_text_widget_theme(widget)

    def _apply_themable_text_widgets(self):
        alive_widgets = []
        for widget in self.themable_text_widgets:
            try:
                if widget.winfo_exists():
                    self._apply_text_widget_theme(widget)
                    alive_widgets.append(widget)
            except Exception:
                continue
        self.themable_text_widgets = alive_widgets

    def _apply_text_widget_theme(self, widget):
        try:
            widget.configure(
                bg=self.BG_MID,
                fg=self.FG_TEXT,
                insertbackground=self.FG_TEXT,
                highlightbackground=self.BORDER_COLOR,
                highlightcolor=self.BORDER_COLOR
            )
        except tk.TclError:
            try:
                widget.configure(bg=self.BG_MID, fg=self.FG_TEXT)
            except tk.TclError:
                pass

    def register_toplevel(self, window):
        if window in self.themable_windows:
            self._apply_title_bar_theme(window)
            return

        self.themable_windows.add(window)

        def _cleanup(event, win=window):
            self.themable_windows.discard(win)
            self._theme_refresh_callbacks.pop(win, None)

        try:
            window.bind("<Destroy>", _cleanup, add="+")
            window.bind("<Map>", self._handle_window_map, add="+")
        except Exception:
            pass

        self._apply_title_bar_theme(window)

    def register_theme_refresh(self, window, callback):
        if window is None or callback is None:
            return
        self._theme_refresh_callbacks[window] = callback
        try:
            callback()
        except Exception:
            pass

    def _apply_theme_refresh_callbacks(self):
        stale = []
        for window, callback in list(self._theme_refresh_callbacks.items()):
            try:
                if window.winfo_exists():
                    callback()
                else:
                    stale.append(window)
            except Exception:
                stale.append(window)
        for window in stale:
            self._theme_refresh_callbacks.pop(window, None)

    def _handle_window_map(self, event):
        widget = event.widget if event else None
        if widget is None:
            return
        try:
            self._apply_title_bar_theme(widget)
        except Exception:
            pass

    def _apply_title_bar_theme_all(self):
        stale = []
        for window in list(self.themable_windows):
            try:
                if window.winfo_exists():
                    self._apply_title_bar_theme(window)
                else:
                    stale.append(window)
            except Exception:
                stale.append(window)
        for win in stale:
            self.themable_windows.discard(win)

    def _apply_title_bar_theme(self, window):
        if platform.system() != "Windows":
            return

        try:
            hwnd = window.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
        except Exception:
            return

        try:
            dwmapi = ctypes.windll.dwmapi
        except Exception:
            return

        def _set_attr(attr, val):
            try:
                dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass

        is_dark = self._is_dark_color(self.BG_ROOT)
        use_dark = ctypes.c_int(1 if is_dark else 0)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        _set_attr(DWMWA_USE_IMMERSIVE_DARK_MODE, use_dark)

        caption_color = ctypes.c_int(self._hex_to_colorref(self.BG_DARK))
        text_color = ctypes.c_int(self._hex_to_colorref(self.FG_TEXT))
        border_color = ctypes.c_int(self._hex_to_colorref(self.BORDER_COLOR))

        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36
        DWMWA_BORDER_COLOR = 34

        _set_attr(DWMWA_CAPTION_COLOR, caption_color)
        _set_attr(DWMWA_TEXT_COLOR, text_color)
        _set_attr(DWMWA_BORDER_COLOR, border_color)

    def _center_window(self, window, width, height):
        """Center the given window on screen with specified dimensions."""
        try:
            window.update_idletasks()
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            x = max((screen_width - width) // 2, 0)
            y = max((screen_height - height) // 2, 0)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            window.geometry(f"{width}x{height}")

    @staticmethod
    def _hex_to_colorref(hex_color):
        if not isinstance(hex_color, str):
            return 0
        value = hex_color.lstrip('#')
        if len(value) != 6:
            return 0
        try:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
        except ValueError:
            return 0
        return (b << 16) | (g << 8) | r

    @staticmethod
    def _is_dark_color(hex_color):
        if not isinstance(hex_color, str):
            return False
        value = hex_color.lstrip('#')
        if len(value) != 6:
            return False
        try:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
        except ValueError:
            return False
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance < 128

    def apply_menu_theme(self):
        """Apply theme colors to the menubar and dropdown menus."""
        if getattr(self, "menu_bar_frame", None):
            self.menu_bar_frame.configure(bg=self.BG_DARK)
        for button in getattr(self, "menu_buttons", []):
            try:
                button.configure(
                    bg=self.BG_LIGHT,
                    fg=self.FG_TEXT,
                    activebackground=self.HOVER_BG,
                    activeforeground=self.FG_TEXT,
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    padx=10,
                    pady=4
                )
            except tk.TclError:
                pass

        menus = [getattr(self, attr, None) for attr in ("actions_menu", "installer_menu", "add_account_menu")]
        for menu in menus:
            self._style_menu_recursive(menu)

    def build_main_menu(self):
        """Create the main menu bar and attach quick actions."""
        if getattr(self, "menu_bar_frame", None):
            try:
                self.menu_bar_frame.destroy()
            except Exception:
                pass

        self.menu_bar_frame = tk.Frame(self.root, bg=self.BG_DARK, highlightthickness=0)
        self.menu_bar_frame.pack(fill="x", padx=10, pady=(10, 4))
        self.menu_buttons = []

        import_btn = tk.Button(
            self.menu_bar_frame,
            text="Import Cookie",
            command=self.import_cookie,
            relief="flat",
            borderwidth=0,
            highlightthickness=0
        )
        import_btn.pack(side="left", padx=(0, 8))
        self.menu_buttons.append(import_btn)

        cred_btn = tk.Button(
            self.menu_bar_frame,
            text="Import User:Pass",
            command=self.import_username_password,
            relief="flat",
            borderwidth=0,
            highlightthickness=0
        )
        cred_btn.pack(side="left", padx=(0, 8))
        self.menu_buttons.append(cred_btn)

        force_btn = tk.Button(
            self.menu_bar_frame,
            text="Force Quit Roblox",
            command=self.force_quit_roblox,
            relief="flat",
            borderwidth=0,
            highlightthickness=0
        )
        force_btn.pack(side="left", padx=(0, 8))
        self.menu_buttons.append(force_btn)

        self.installer_menu = tk.Menu(self.root, tearoff=False)
        installer_btn = tk.Button(
            self.menu_bar_frame,
            text="Roblox Installer",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            command=self.show_installer_menu
        )
        installer_btn.pack(side="left", padx=(0, 8))
        installer_btn.bind("<Button-1>", self.show_installer_menu)
        self.installer_button = installer_btn
        self.menu_buttons.append(installer_btn)

        self.refresh_installer_menu()
        self.apply_menu_theme()

    def show_installer_menu(self, event=None):
        if not getattr(self, "installer_menu", None):
            return
        button = getattr(self, "installer_button", None)
        if button is None:
            return
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            self.installer_menu.tk_popup(x, y)
        finally:
            try:
                self.installer_menu.grab_release()
            except Exception:
                pass

    def show_add_account_menu(self, event=None):
        if not getattr(self, "add_account_menu", None):
            return
        if event is None:
            button = getattr(self, "add_account_split_btn", None)
            if button is None:
                return
            try:
                x = button.winfo_rootx()
                y = button.winfo_rooty() + button.winfo_height()
            except Exception:
                return
        else:
            x = event.x_root
            y = event.y_root
        try:
            self.add_account_menu.tk_popup(x, y)
        finally:
            try:
                self.add_account_menu.grab_release()
            except Exception:
                pass

    def refresh_installer_menu(self):
        """Populate the Roblox Installer menu with up to five recent versions."""
        if getattr(self, "installer_menu", None) is None:
            return

        self.installer_menu.delete(0, tk.END)
        limit = clamp_installer_previous_versions(
            self.settings.get("installer_previous_versions", MIN_INSTALLER_PREVIOUS_VERSIONS)
        )
        versions = self.get_available_roblox_versions(limit=limit)
        if not versions:
            self.installer_menu.add_command(label="No versions found", state="disabled")
            return

        for entry in versions:
            label = self.format_version_display(entry)
            version = entry.get("version")
            if not version:
                continue
            self.installer_menu.add_command(
                label=label,
                command=lambda v=version: self.use_installer_version(v)
            )

    def _apply_menu_palette_defaults(self):
        try:
            root = self.root
            root.option_add("*Menu.background", self.BG_DARK)
            root.option_add("*Menu.foreground", self.FG_TEXT)
            root.option_add("*Menu.activeBackground", self.HOVER_BG)
            root.option_add("*Menu.activeForeground", self.FG_TEXT)
            root.option_add("*Menu.selectColor", self.FG_ACCENT)
        except Exception:
            pass

    def _style_menu_recursive(self, menu):
        if menu is None:
            return
        try:
            menu.configure(
                bg=self.BG_DARK,
                fg=self.FG_TEXT,
                activebackground=self.HOVER_BG,
                activeforeground=self.FG_TEXT,
                borderwidth=0,
                relief="flat",
                tearoff=False
            )
        except tk.TclError:
            return

        end_index = menu.index("end")
        if end_index is None:
            return
        for index in range(end_index + 1):
            try:
                submenu_name = menu.entrycget(index, "menu")
            except tk.TclError:
                continue
            if submenu_name:
                try:
                    submenu = menu.nametowidget(submenu_name)
                except Exception:
                    submenu = None
                self._style_menu_recursive(submenu)

    def use_installer_version(self, version):
        """Begin the guided installer flow for the selected Roblox version."""
        clients = self.get_installed_clients()
        if not clients:
            messagebox.showwarning(
                "Roblox Installer",
                "No supported clients were found.\n\nInstall Roblox, Bloxstrap, or Fishstrap first."
            )
            return

        self._show_installer_dialog(version, clients)

    def _show_installer_dialog(self, version, clients):
        """Create (or refresh) the installer dialog for choosing a client and tracking progress."""
        self._close_installer_dialog()

        window = tk.Toplevel(self.root)
        window.title("Roblox Installer")
        window.configure(bg=self.BG_DARK)
        window.resizable(False, False)
        self.register_toplevel(window)

        WIDTH, HEIGHT = 420, 360
        self._center_window(window, WIDTH, HEIGHT)

        main_frame = ttk.Frame(window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(
            main_frame,
            text=f"Install {version}",
            style="Dark.TLabel",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(
            main_frame,
            text="Choose a client target:",
            style="Dark.TLabel"
        ).pack(anchor="w")

        clients_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        clients_frame.pack(fill="x", pady=(4, 12))

        selected_client = tk.StringVar(value="")

        for client in clients:
            radio = ttk.Radiobutton(
                clients_frame,
                text=f"{client['name']}  ({client['versions_path']})",
                value=client["id"],
                variable=selected_client,
                style="Dark.TRadiobutton"
            )
            radio.pack(anchor="w", pady=2, fill="x")

        progress_var = tk.DoubleVar(value=0.0)
        status_var = tk.StringVar(value="Select a client to begin.")

        progress_bar = ttk.Progressbar(
            main_frame,
            maximum=100,
            variable=progress_var
        )
        progress_bar.pack(fill="x", pady=(10, 4))

        status_label = ttk.Label(
            main_frame,
            textvariable=status_var,
            style="Dark.TLabel",
            wraplength=WIDTH - 60
        )
        status_label.pack(fill="x", pady=(0, 10))

        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")

        download_btn = ttk.Button(
            button_frame,
            text="Download",
            style="Dark.TButton",
            state="disabled",
            command=self._begin_installer_download
        )
        download_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        close_btn = ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=self._close_installer_dialog
        )
        close_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        def on_selection_change(*_):
            state = self.installer_dialog_state
            if not state:
                return
            if selected_client.get():
                download_btn.configure(state="normal")
            else:
                download_btn.configure(state="disabled")

        selected_client.trace_add("write", on_selection_change)

        window.protocol("WM_DELETE_WINDOW", self._handle_installer_close_request)

        self.installer_dialog_state = {
            "window": window,
            "version": version,
            "clients": clients,
            "selected_client": selected_client,
            "progress_var": progress_var,
            "status_var": status_var,
            "progress_bar": progress_bar,
            "download_button": download_btn,
            "close_button": close_btn,
            "download_thread": None,
        }

    def _begin_installer_download(self):
        """Kick off the download/extract workflow in a background thread."""
        state = self.installer_dialog_state
        if not state:
            return

        if state.get("download_thread"):
            return

        client = self._get_selected_installer_client()
        if not client:
            messagebox.showwarning("Roblox Installer", "Please select a client first.")
            return

        version = state["version"]
        target_dir = os.path.join(client["versions_path"], version)

        if os.path.exists(target_dir):
            overwrite = messagebox.askyesno(
                "Roblox Installer",
                f"The folder for {version} already exists inside {client['name']}.\n\n"
                "Do you want to delete it and replace with a fresh download?"
            )
            if not overwrite:
                return
            try:
                shutil.rmtree(target_dir)
            except Exception as exc:
                messagebox.showerror("Roblox Installer", f"Failed to remove existing folder:\n{exc}")
                return

        state["download_button"].configure(state="disabled")
        state["close_button"].configure(state="disabled")
        state["status_var"].set("Starting download...")
        state["progress_var"].set(0)

        thread = threading.Thread(
            target=self._installer_download_thread,
            args=(version, client, target_dir),
            daemon=True
        )
        state["download_thread"] = thread
        thread.start()

    def _get_selected_installer_client(self):
        """Return the client entry currently selected in the installer dialog."""
        state = self.installer_dialog_state
        if not state:
            return None
        selected_id = state["selected_client"].get()
        for client in state["clients"]:
            if client["id"] == selected_id:
                return client
        return None

    def _handle_installer_close_request(self):
        """Prevent closing while download is running."""
        state = self.installer_dialog_state
        if not state:
            return
        thread = state.get("download_thread")
        if thread and thread.is_alive():
            messagebox.showwarning(
                "Roblox Installer",
                "Please wait for the download to finish before closing."
            )
            return
        self._close_installer_dialog()

    def _close_installer_dialog(self):
        """Destroy the installer dialog window and reset state."""
        state = self.installer_dialog_state
        if not state:
            return

        window = state.get("window")
        if window and window.winfo_exists():
            window.destroy()
        self.installer_dialog_state = None

    def _installer_download_thread(self, version, client, target_dir):
        root = getattr(self, "root", None)

        def ui_update(status=None, progress=None):
            if root is None:
                return

            def apply():
                current = self.installer_dialog_state
                if not current:
                    return
                window = current.get("window")
                if not window or not window.winfo_exists():
                    return
                if status is not None:
                    try:
                        current["status_var"].set(status)
                    except Exception:
                        pass
                if progress is not None:
                    try:
                        current["progress_var"].set(progress)
                    except Exception:
                        pass

            try:
                root.after(0, apply)
            except Exception:
                pass

        def ui_finish(success, message):
            if root is None:
                return

            def apply():
                current = self.installer_dialog_state
                if current:
                    try:
                        current["close_button"].configure(state="normal")
                    except Exception:
                        pass
                    try:
                        current["download_button"].configure(state="normal")
                    except Exception:
                        pass
                    current["download_thread"] = None

                if success:
                    try:
                        self.load_roblox_versions()
                    except Exception:
                        pass

                if success:
                    try:
                        messagebox.showinfo("Roblox Installer", message)
                    except Exception:
                        pass
                else:
                    try:
                        messagebox.showerror("Roblox Installer", message)
                    except Exception:
                        pass

            try:
                root.after(0, apply)
            except Exception:
                pass

        temp_root = None
        try:
            channel = "LIVE"
            if hasattr(self, "settings") and isinstance(self.settings, dict):
                channel = (self.settings.get("roblox_download_channel") or channel)
            channel = str(channel).strip() or "LIVE"

            requested_version = (version or "").strip()
            if requested_version and not requested_version.startswith("version-"):
                requested_version = "version-" + requested_version
            if not requested_version:
                raise ValueError("Missing version")

            binary_type = "WindowsPlayer"
            blob_dir = RDD_BINARY_TYPES.get(binary_type, {}).get("blob_dir", "/")

            ui_update(status="Fetching manifest...", progress=0)

            session = requests.Session()
            session.trust_env = False

            channel_path = RDD_HOST_PATH
            if channel != "LIVE":
                channel_path = f"{RDD_HOST_PATH}/channel/{channel.lower()}"

            version_path = f"{channel_path}{blob_dir}{requested_version}-"
            manifest_url = version_path + "rbxPkgManifest.txt"

            try:
                resp = session.get(manifest_url, headers=ROBLOX_DOWNLOAD_HEADERS, timeout=15)
                resp.raise_for_status()
                manifest_body = resp.text
            except Exception as exc:
                raise RuntimeError(f"Failed to fetch rbxPkgManifest.txt:\n{manifest_url}\n\n{exc}")

            lines = [line.strip() for line in manifest_body.splitlines() if line.strip()]
            if not lines or lines[0] != "v0":
                raise RuntimeError("Unknown rbxPkgManifest format")

            packages = []
            for line in lines[1:]:
                name = (line.split() or [""])[0]
                if name.lower().endswith(".zip"):
                    packages.append(name)
            if not packages:
                raise RuntimeError("Manifest contained no packages")

            if "RobloxApp.zip" in packages:
                extract_roots = RDD_EXTRACT_ROOTS["player"]
            elif "RobloxStudio.zip" in packages:
                extract_roots = RDD_EXTRACT_ROOTS["studio"]
            else:
                raise RuntimeError("Bad/unrecognized rbxPkgManifest")

            temp_root = tempfile.mkdtemp(prefix="ram_rdd_")
            build_dir = os.path.join(temp_root, "build")
            os.makedirs(build_dir, exist_ok=True)

            app_settings_path = os.path.join(build_dir, "AppSettings.xml")
            with open(app_settings_path, "w", encoding="utf-8") as f:
                f.write(RDD_APP_SETTINGS_XML)

            pkgs_dir = os.path.join(temp_root, "pkgs")
            os.makedirs(pkgs_dir, exist_ok=True)

            total_pkgs = len(packages)
            for idx, package_name in enumerate(packages, 1):
                progress = (idx - 1) / max(1, total_pkgs) * 70.0
                ui_update(status=f"Downloading {package_name}... ({idx}/{total_pkgs})", progress=progress)

                pkg_url = version_path + package_name
                pkg_path = os.path.join(pkgs_dir, package_name)

                with session.get(pkg_url, headers=ROBLOX_DOWNLOAD_HEADERS, stream=True, timeout=(10, 120)) as r:
                    r.raise_for_status()
                    with open(pkg_path, "wb") as out:
                        for chunk in r.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                out.write(chunk)

                extract_root = extract_roots.get(package_name)
                if extract_root is None:
                    shutil.copy2(pkg_path, os.path.join(build_dir, package_name))
                    continue

                ui_update(status=f"Extracting {package_name}... ({idx}/{total_pkgs})", progress=progress + 5.0)
                with zipfile.ZipFile(pkg_path, "r") as zf:
                    for info in zf.infolist():
                        name = info.filename
                        if not name or name.endswith("/") or name.endswith("\\"):
                            continue
                        fixed = name.replace("\\", "/").lstrip("/")
                        normalized = os.path.normpath(fixed)
                        if normalized.startswith("..") or os.path.isabs(normalized):
                            continue
                        normalized = normalized.replace("\\", "/")
                        dest_path = os.path.join(build_dir, extract_root, normalized)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with zf.open(info, "r") as src_f, open(dest_path, "wb") as dst_f:
                            shutil.copyfileobj(src_f, dst_f)

                if idx == 1 or idx == total_pkgs or (idx % 5) == 0:
                    progress = (idx / max(1, total_pkgs)) * 80.0
                    ui_update(status=f"Assembling files... ({idx}/{total_pkgs})", progress=progress)

            ui_update(status="Installing files...", progress=85)
            os.makedirs(target_dir, exist_ok=True)
            items = os.listdir(build_dir)
            total_items = len(items) or 1
            for idx, name in enumerate(items, 1):
                src = os.path.join(build_dir, name)
                dst = os.path.join(target_dir, name)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
                if idx == 1 or idx == total_items or (idx % 25) == 0:
                    progress = 85.0 + (idx / total_items) * 15.0
                    ui_update(status=f"Installing files... ({idx}/{total_items})", progress=progress)

            ui_update(status="Done.", progress=100)
            ui_finish(True, f"Installed {version} into {client['name']}.")

        except Exception as exc:
            ui_update(status="Failed.", progress=0)
            ui_finish(False, f"Failed to install {version}:\n{exc}")
        finally:
            if temp_root and os.path.isdir(temp_root):
                try:
                    shutil.rmtree(temp_root)
                except Exception:
                    pass

    def load_roblox_versions(self):
        """Load available Roblox versions from standard and custom folders."""
        try:
            current_selection = self.version_var.get() if hasattr(self, "version_var") else "Latest Version"
            local_versions = self.get_local_roblox_versions()
            display_values = ["Latest Version"]
            self.version_options = {"Latest Version": None}
            seen_paths = set()

            for entry in local_versions:
                label = entry.get("label")
                path = entry.get("path")
                if not label or not path:
                    continue
                normalized_path = os.path.normcase(os.path.normpath(path))
                if normalized_path in seen_paths:
                    continue
                seen_paths.add(normalized_path)
                display_values.append(label)
                self.version_options[label] = path

            custom_entry = self._get_custom_roblox_player_entry()
            if custom_entry:
                custom_label = custom_entry["label"]
                custom_path = custom_entry["path"]
                normalized_custom = os.path.normcase(os.path.normpath(custom_path))
                if normalized_custom not in seen_paths:
                    display_values.append(custom_label)
                    self.version_options[custom_label] = custom_path

            self.version_dropdown["values"] = display_values or ["Latest Version"]
            if current_selection in self.version_options:
                self.version_var.set(current_selection)
            elif current_selection in (display_values or []):
                self.version_var.set(current_selection)
            else:
                self.version_var.set("Latest Version")
        except Exception as e:
            print(f"Error loading Roblox versions: {e}")
            self.version_options = {"Latest Version": None}
            self.version_dropdown["values"] = ["Latest Version"]
            self.version_var.set("Latest Version")

        self.refresh_installer_menu()

    def _get_custom_roblox_player_entry(self):
        """Return a normalized custom Roblox executable entry for the version dropdown."""
        raw_path = (self.settings.get("custom_roblox_player_path") or "").strip()
        if not raw_path:
            return None

        expanded_path = os.path.expandvars(raw_path)
        normalized_path = os.path.normpath(expanded_path)
        if not os.path.isfile(normalized_path):
            return None

        exe_name = os.path.basename(normalized_path).lower()
        if exe_name not in self.ROBLOX_CLIENT_EXECUTABLES:
            return None

        parent_name = os.path.basename(os.path.dirname(normalized_path)) or "Custom"
        label = f"[Custom] {parent_name} - {os.path.basename(normalized_path)}"
        return {
            "label": label,
            "path": normalized_path,
        }

    def _select_version_by_path(self, path):
        if not path:
            return
        try:
            normalized_target = os.path.normcase(os.path.normpath(path))
        except Exception:
            return
        for label, option_path in self.version_options.items():
            if not option_path:
                continue
            try:
                normalized_option = os.path.normcase(os.path.normpath(option_path))
            except Exception:
                continue
            if normalized_option == normalized_target:
                self.version_var.set(label)
                return

    def _collect_version_sources(self):
        """Return a deduplicated list of version sources (standard + custom)."""
        sources = []
        seen = set()

        def add_source(name, base_path):
            if not base_path:
                return
            expanded = os.path.expandvars(base_path)
            if not expanded:
                return
            normalized = os.path.normcase(os.path.normpath(expanded))
            if normalized in seen:
                return
            seen.add(normalized)
            sources.append({"name": name, "base": expanded})

        add_source("Roblox", r"%LOCALAPPDATA%\Roblox\Versions")
        add_source("Bloxstrap", r"%LOCALAPPDATA%\Bloxstrap\Versions")
        add_source("Fishstrap", r"%LOCALAPPDATA%\Fishstrap\Versions")
        add_source("Voidstrap", r"%LOCALAPPDATA%\Voidstrap\RblxVersions")

        return sources

    def get_local_roblox_versions(self, limit=None):
        """Return Roblox version directories from known sources."""
        sources = self._collect_version_sources()

        versions = []
        for source in sources:
            base_path = source["base"]
            if not base_path or not os.path.exists(base_path):
                continue

            try:
                entries = []
                with os.scandir(base_path) as iterator:
                    for entry in iterator:
                        try:
                            if not entry.is_dir():
                                continue
                            stat = entry.stat()
                        except OSError:
                            continue
                        entries.append((float(getattr(stat, "st_mtime", 0.0)), entry.path, entry.name))

                entries.sort(key=lambda item: item[0], reverse=True)

                if limit is not None:
                    entries = entries[:limit]

                for idx, entry in enumerate(entries):
                    _, path, version_name = entry
                    label = f"[{source['name']}] {version_name}"
                    versions.append({
                        "label": label,
                        "path": path,
                        "version": version_name,
                        "status": "LIVE" if idx == 0 else "PAST"
                    })
            except Exception as exc:
                print(f"Error while enumerating {source['name']} versions: {exc}")

        return versions

    def fetch_remote_versions(self, limit=5):
        """Fetch Roblox version history from Roblox CDN (LIVE channel)."""
        history_url = "https://setup.rbxcdn.com/DeployHistory.txt"
        versions = []
        seen_versions = set()

        try:
            response = self._get_http_session().get(history_url, timeout=5)
            response.raise_for_status()
        except Exception as exc:
            print(f"Failed to fetch remote Roblox versions: {exc}")
            return versions

        lines = response.text.splitlines()
        version_pattern = re.compile(r"version-[0-9a-fA-F]+")

        for line in reversed(lines):
            line = line.strip()
            if "WindowsPlayer" not in line:
                continue
            match = version_pattern.search(line)
            if not match:
                continue
            version = match.group(0)
            if version in seen_versions:
                continue
            seen_versions.add(version)
            status = "LIVE" if not versions else "PAST"
            versions.append({"version": version, "status": status})
            if limit and len(versions) >= limit:
                break

        return versions

    def _get_http_session(self):
        """Lazily initialize a shared HTTP session with retry/backoff."""
        if self._http_session is not None:
            return self._http_session

        with self._http_session_lock:
            if self._http_session is None:
                session = requests.Session()
                retry = Retry(
                    total=2,
                    backoff_factor=0.35,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
                )
                adapter = HTTPAdapter(pool_connections=12, pool_maxsize=12, max_retries=retry)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                session.headers.update({"User-Agent": "FRAM"})
                self._http_session = session

        return self._http_session

    def get_available_roblox_versions(self, limit=None):
        """Get Roblox versions preferring remote history, falling back to local folders."""
        cache_ttl_seconds = 60
        now = time.time()
        cache = getattr(self, "_installer_versions_cache", None)
        if (
            isinstance(cache, dict)
            and cache.get("versions")
            and (now - float(cache.get("ts", 0))) < cache_ttl_seconds
        ):
            remote_versions = cache["versions"]
        else:
            remote_versions = self.fetch_remote_versions(limit=MAX_INSTALLER_PREVIOUS_VERSIONS)
            if remote_versions:
                self._installer_versions_cache = {"ts": now, "versions": remote_versions}

        if limit is not None:
            remote_versions = remote_versions[:limit]
        if remote_versions:
            return remote_versions
        return self.get_local_roblox_versions(limit=limit)

    def get_installed_clients(self):
        """Return installed client targets that have a Versions directory on disk."""
        candidates = [
            ("Roblox", os.path.expandvars(r"%LOCALAPPDATA%\Roblox\Versions")),
            ("Bloxstrap", os.path.expandvars(r"%LOCALAPPDATA%\Bloxstrap\Versions")),
            ("Fishstrap", os.path.expandvars(r"%LOCALAPPDATA%\Fishstrap\Versions")),
            ("Voidstrap", os.path.expandvars(r"%LOCALAPPDATA%\Voidstrap\RblxVersions")),
        ]

        installed = []
        for name, base_path in candidates:
            if not base_path:
                continue
            try:
                if os.path.isdir(base_path):
                    installed.append({
                        "id": f"{name.lower()}_{abs(hash(base_path))}",
                        "name": name,
                        "versions_path": base_path
                    })
            except Exception:
                continue

        installed.sort(key=lambda entry: entry["name"])
        return installed

    def format_version_display(self, entry):
        """Return display text for a Roblox version entry with status indicator."""
        status = entry.get("status", "PAST").upper()
        version = entry.get("version", "")
        return f"[{status}] {version}"

    def save_settings(self):
        """Save UI settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def _load_discord_button_image(self, size=32):
        """Load Discord logo PNG for the settings header button (cached under AccountManagerData/cache)."""
        if self._discord_button_image is not None:
            return self._discord_button_image

        cache_dir = os.path.join(self.data_folder, "cache")
        png_path = os.path.join(cache_dir, f"discord_square_logo_{int(size)}.png")

        def _load_png(path):
            try:
                img = tk.PhotoImage(file=path)
                try:
                    width = int(img.width())
                    if width > int(size):
                        ratio = max(1, int(round(width / float(size))))
                        img = img.subsample(ratio, ratio)
                except Exception:
                    pass
                self._discord_button_image = img
                return img
            except Exception:
                return None

        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass

        if os.path.isfile(png_path):
            image = _load_png(png_path)
            if image is not None:
                return image

        try:
            response = requests.get(DISCORD_LOGO_URL, timeout=10)
            if response.status_code == 200 and response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                with open(png_path, "wb") as cache_fp:
                    cache_fp.write(response.content)
                image = _load_png(png_path)
                if image is not None:
                    return image
        except Exception:
            pass

        return None

    def _sanitize_issue_report_text(self, text):
        """Best-effort redaction for issue drafts to avoid exposing secrets."""
        if not text:
            return ""

        redacted = str(text)

        redacted = re.sub(
            r'(?i)(\"(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\"\s*:\s*\")([^\"]*)(\")',
            r"\1[REDACTED]\3",
            redacted,
        )
        redacted = re.sub(
            r"(?i)('(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)'\s*:\s*')([^']*)(')",
            r"\1[REDACTED]\3",
            redacted,
        )
        redacted = re.sub(
            r"(?i)\b(password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)",
            r"\1\2[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([?&](?:password|pass|token|cookie|auth|authorization)=)([^&\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(\.ROBLOSECURITY\s*=\s*)([^;\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(\.ROBLOSECURITY\s*[:=]\s*)([^;\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(authorization\s*:\s*bearer\s+)([^\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(sessionid\s*=\s*)([^;\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)\b[A-F0-9]{32,}\b",
            "[REDACTED_HEX]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\\/]+Users[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\\/]+home[\\/]+)([^\\/\r\n\"']+)",
            r"\1<user>",
            redacted,
        )
        return redacted

    def _build_bug_issue_draft(self, exc_type, exc_value, exc_traceback, source="unknown"):
        exception_name = getattr(exc_type, "__name__", str(exc_type) or "Exception")
        exception_message = str(exc_value or "").strip() or "(no message)"
        raw_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        trace_text = self._sanitize_issue_report_text(raw_traceback).strip()

        account_count = 0
        try:
            account_count = len(getattr(self.manager, "accounts", {}) or {})
        except Exception:
            account_count = 0

        title = f"Crash: {exception_name} ({source})"
        body = (
            "## Summary\n"
            f"Unhandled exception detected in `{source}`.\n\n"
            "## Environment\n"
            f"- App Version: {getattr(self, 'APP_VERSION', 'unknown')}\n"
            f"- OS: {platform.system()} {platform.release()}\n"
            f"- Python: {sys.version.split()[0]}\n"
            f"- Saved Account Count: {account_count}\n\n"
            "## Exception\n"
            f"- Type: `{exception_name}`\n"
            f"- Message: `{self._sanitize_issue_report_text(exception_message)}`\n\n"
            "## Traceback (sanitized)\n"
            "```text\n"
            f"{trace_text}\n"
            "```\n"
        )

        try:
            from urllib.parse import urlencode
            query = urlencode(
                {
                    "title": self._sanitize_issue_report_text(title)[:180],
                    "body": body[:7000],
                    "labels": "bug,auto-report",
                }
            )
            issue_url = f"https://github.com/hackyue/ForkedRobloxAccountManager/issues/new?{query}"
        except Exception:
            issue_url = "https://github.com/hackyue/ForkedRobloxAccountManager/issues/new"

        return {
            "title": title,
            "body": body,
            "issue_url": issue_url,
            "signature": self._sanitize_issue_report_text(f"{exception_name}|{exception_message}|{source}")[:400],
        }

    def _show_bug_issue_prompt(self, issue_data):
        if not issue_data:
            return
        if not self.settings.get("bug_issue_prompt_enabled", True):
            return
        if getattr(self, "_bug_issue_prompt_open", False):
            return

        try:
            signature = issue_data.get("signature", "")
            if signature:
                if signature == getattr(self, "_last_bug_issue_signature", ""):
                    return
                self._last_bug_issue_signature = signature
        except Exception:
            pass

        self._bug_issue_prompt_open = True
        dialog = tk.Toplevel(self.root)
        dialog.title("Bug Detected")
        dialog.configure(bg=self.BG_DARK)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        self.register_toplevel(dialog)

        if self.settings.get("enable_topmost", False):
            dialog.attributes("-topmost", True)

        container = ttk.Frame(dialog, style="Dark.TFrame")
        container.pack(fill="both", expand=True, padx=14, pady=12)

        ttk.Label(
            container,
            text="A bug was detected. Do you want to create a GitHub issue draft for the developer?",
            style="Dark.TLabel",
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            container,
            text="Privacy: Nothing is sent automatically. Sensitive values are redacted before opening the draft.",
            style="Dark.TLabel",
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        button_row = ttk.Frame(container, style="Dark.TFrame")
        button_row.pack(fill="x")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        button_row.columnconfigure(2, weight=1)

        def close_prompt():
            try:
                dialog.destroy()
            except Exception:
                pass
            self._bug_issue_prompt_open = False

        def open_issue():
            try:
                import webbrowser
                webbrowser.open(issue_data.get("issue_url", ""), new=2)
            except Exception:
                pass
            close_prompt()

        def never_ask_again():
            self.settings["bug_issue_prompt_enabled"] = False
            self.save_settings()
            close_prompt()

        ttk.Button(
            button_row,
            text="Create GitHub Issue",
            style="Dark.TButton",
            command=open_issue,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ttk.Button(
            button_row,
            text="Not Now",
            style="Dark.TButton",
            command=close_prompt,
        ).grid(row=0, column=1, sticky="ew", padx=3)

        ttk.Button(
            button_row,
            text="Never Ask Again",
            style="Dark.TButton",
            command=never_ask_again,
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        dialog.protocol("WM_DELETE_WINDOW", close_prompt)
        dialog.update_idletasks()
        self._center_window(dialog, max(520, dialog.winfo_reqwidth() + 20), max(210, dialog.winfo_reqheight() + 20))
        dialog.deiconify()

    def report_unhandled_exception(self, exc_type, exc_value, exc_traceback, source="unknown"):
        """Queue a privacy-safe issue draft prompt for unexpected crashes."""
        if exc_type in (KeyboardInterrupt, SystemExit):
            return
        if not self.settings.get("bug_issue_prompt_enabled", True):
            return

        try:
            issue_data = self._build_bug_issue_draft(exc_type, exc_value, exc_traceback, source=source)
        except Exception:
            return

        def _show():
            try:
                self._show_bug_issue_prompt(issue_data)
            except Exception:
                pass

        try:
            self.root.after(0, _show)
        except Exception:
            pass

    def _schedule_setting_save(self, key, value, delay_ms=250):
        """Debounce frequent UI setting writes to keep typing responsive."""
        self.settings[key] = value
        pending_id = self._settings_save_after_ids.get(key)
        if pending_id is not None:
            try:
                self.root.after_cancel(pending_id)
            except Exception:
                pass

        def _commit(setting_key=key):
            self._settings_save_after_ids.pop(setting_key, None)
            self.save_settings()

        try:
            self._settings_save_after_ids[key] = self.root.after(delay_ms, _commit)
        except Exception:
            self.save_settings()

    def _is_frozen_exe(self):
        try:
            return bool(getattr(sys, "frozen", False)) and os.path.isfile(sys.executable)
        except Exception:
            return False

    def _parse_version_tuple(self, version_str):
        if not version_str:
            return (0,)
        value = str(version_str).strip()
        if value.lower().startswith("v"):
            value = value[1:]
        parts = []
        for part in value.split("."):
            try:
                parts.append(int(part))
            except Exception:
                parts.append(0)
        return tuple(parts) if parts else (0,)

    def _auto_update_maybe_start(self):
        if not self.settings.get("auto_update_enabled", True):
            return
        if not self._is_frozen_exe():
            return
        if getattr(self, "_auto_update_check_started", False):
            return
        self._auto_update_check_started = True

        def worker():
            try:
                api_url = "https://api.github.com/repos/hackyue/ForkedRobloxAccountManager/releases/latest"
                headers = {
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "FRAM",
                }
                response = self._get_http_session().get(api_url, headers=headers, timeout=12)
                response.raise_for_status()
                release = response.json()

                latest_tag = (release.get("tag_name") or "").strip()
                latest_tuple = self._parse_version_tuple(latest_tag)
                current_tuple = self._parse_version_tuple(getattr(self, "APP_VERSION", "0"))
                if latest_tuple <= current_tuple:
                    return

                self.root.after(0, lambda: self._prompt_update_available(release))
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update_available(self, release):
        if getattr(self, "_auto_update_prompt_shown", False):
            return
        self._auto_update_prompt_shown = True

        try:
            latest_tag = (release.get("tag_name") or "").strip()
            latest_display = latest_tag[1:] if latest_tag.lower().startswith("v") else latest_tag
        except Exception:
            latest_display = ""

        current_display = getattr(self, "APP_VERSION", "")
        prompt = (
            f"A new version is available.\n\n"
            f"Current: {current_display}\n"
            f"Latest: {latest_display}\n\n"
            f"Update now?"
        )

        if not messagebox.askyesno("Update Available", prompt, parent=self.root):
            return

        self._download_update_and_apply(release)

    def _download_update_and_apply(self, release):
        def worker():
            downloaded_path = None
            progress_state = {"window": None, "status_var": None, "progress_var": None, "progress_bar": None}
            progress_ready = threading.Event()

            try:
                assets = release.get("assets") or []
                asset = None
                for entry in assets:
                    name = (entry.get("name") or "").lower()
                    if name.endswith(".exe"):
                        asset = entry
                        break
                if not asset:
                    raise RuntimeError("No EXE asset found in latest release")

                download_url = asset.get("browser_download_url")
                if not download_url:
                    raise RuntimeError("Missing download URL")

                expected_digest = asset.get("digest")
                expected_sha256 = None
                if isinstance(expected_digest, str) and expected_digest.lower().startswith("sha256:"):
                    expected_sha256 = expected_digest.split(":", 1)[1].strip().lower()

                try:
                    os.makedirs(self.data_folder, exist_ok=True)
                except Exception:
                    pass

                fd, downloaded_path = tempfile.mkstemp(prefix="fram_update_", suffix=".exe", dir=self.data_folder)
                os.close(fd)

                def open_progress():
                    try:
                        window = tk.Toplevel(self.root)
                        window.withdraw()
                        window.title("Updating")
                        window.configure(bg=self.BG_DARK)
                        window.resizable(False, False)
                        window.transient(self.root)
                        try:
                            window.grab_set()
                        except Exception:
                            pass
                        self.register_toplevel(window)

                        WIDTH, HEIGHT = 420, 150
                        self._center_window(window, WIDTH, HEIGHT)

                        main_frame = ttk.Frame(window, style="Dark.TFrame")
                        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

                        status_var = tk.StringVar(value="Starting download...")
                        progress_var = tk.DoubleVar(value=0.0)

                        ttk.Label(
                            main_frame,
                            textvariable=status_var,
                            style="Dark.TLabel",
                            wraplength=WIDTH - 60,
                        ).pack(anchor="w", fill="x")

                        progress_bar = ttk.Progressbar(
                            main_frame,
                            maximum=100,
                            variable=progress_var,
                            mode="determinate",
                        )
                        progress_bar.pack(fill="x", pady=(12, 0))

                        window.protocol("WM_DELETE_WINDOW", lambda: None)

                        if self.settings.get("enable_topmost", False):
                            try:
                                window.attributes("-topmost", True)
                            except Exception:
                                pass

                        window.deiconify()
                        try:
                            window.lift()
                        except Exception:
                            pass

                        progress_state["window"] = window
                        progress_state["status_var"] = status_var
                        progress_state["progress_var"] = progress_var
                        progress_state["progress_bar"] = progress_bar
                    finally:
                        progress_ready.set()

                def ui_update(message=None, percent=None, indeterminate=None):
                    def apply():
                        window = progress_state.get("window")
                        if window is None:
                            return
                        try:
                            if not window.winfo_exists():
                                return
                        except Exception:
                            return

                        if message is not None:
                            try:
                                progress_state["status_var"].set(message)
                            except Exception:
                                pass

                        bar = progress_state.get("progress_bar")
                        if indeterminate is not None and bar is not None:
                            try:
                                if indeterminate:
                                    bar.configure(mode="indeterminate")
                                    bar.start(12)
                                else:
                                    bar.stop()
                                    bar.configure(mode="determinate")
                            except Exception:
                                pass

                        if percent is not None:
                            try:
                                progress_state["progress_var"].set(max(0.0, min(100.0, float(percent))))
                            except Exception:
                                pass

                    try:
                        self.root.after(0, apply)
                    except Exception:
                        pass

                def ui_close():
                    def apply():
                        window = progress_state.get("window")
                        if window is None:
                            return
                        try:
                            if window.winfo_exists():
                                window.destroy()
                        except Exception:
                            pass

                    try:
                        self.root.after(0, apply)
                    except Exception:
                        pass

                self.root.after(0, open_progress)
                progress_ready.wait(2.0)

                headers = {"User-Agent": "FRAM"}
                hasher = hashlib.sha256()
                with self._get_http_session().get(download_url, headers=headers, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    total_bytes = None
                    try:
                        total_bytes = int(resp.headers.get("Content-Length") or "")
                    except Exception:
                        total_bytes = None

                    if not total_bytes:
                        ui_update(indeterminate=True)

                    downloaded_bytes = 0
                    last_ui_update = 0.0
                    with open(downloaded_path, "wb") as fp:
                        for chunk in resp.iter_content(chunk_size=1024 * 256):
                            if not chunk:
                                continue
                            fp.write(chunk)
                            hasher.update(chunk)

                            downloaded_bytes += len(chunk)
                            now = time.time()
                            if (now - last_ui_update) >= 0.15:
                                last_ui_update = now
                                if total_bytes and total_bytes > 0:
                                    percent = (downloaded_bytes / total_bytes) * 100.0
                                    status = (
                                        f"Downloading update... {downloaded_bytes / (1024 * 1024):.1f} / "
                                        f"{total_bytes / (1024 * 1024):.1f} MB"
                                    )
                                    ui_update(message=status, percent=percent, indeterminate=False)
                                else:
                                    status = f"Downloading update... {downloaded_bytes / (1024 * 1024):.1f} MB"
                                    ui_update(message=status)

                ui_update(message="Applying update...", percent=100.0, indeterminate=True)

                if expected_sha256:
                    actual = hasher.hexdigest().lower()
                    if actual != expected_sha256:
                        raise RuntimeError("Downloaded update failed integrity check")

                target_exe = sys.executable
                if not (target_exe and os.path.isfile(target_exe)):
                    raise RuntimeError("Unable to locate current executable")

                updater_copy = os.path.join(self.data_folder, "FRAM_Updater.exe")
                try:
                    if os.path.exists(updater_copy):
                        os.remove(updater_copy)
                except Exception:
                    pass

                shutil.copy2(target_exe, updater_copy)

                args = [
                    updater_copy,
                    "--apply-update",
                    "--pid",
                    str(os.getpid()),
                    "--source",
                    downloaded_path,
                    "--target",
                    target_exe,
                ]

                subprocess.Popen(args, close_fds=True, **subprocess_no_window_kwargs())
                ui_close()
                self.root.after(0, self.root.destroy)
            except Exception as exc:
                ui_close()
                if downloaded_path:
                    try:
                        os.remove(downloaded_path)
                    except Exception:
                        pass

                try:
                    self.root.after(0, lambda: messagebox.showerror("Update Failed", str(exc), parent=self.root))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def is_chrome_installed(self):
        """
        Backward-compatible wrapper.
        Returns True when at least one supported browser (Chrome/Firefox) is available.
        """
        try:
            if hasattr(self, "manager") and hasattr(self.manager, "has_supported_browser"):
                return bool(self.manager.has_supported_browser())
        except Exception:
            pass

        # Fallback local check
        try:
            candidates = []
            pf = os.environ.get("ProgramFiles")
            pfx86 = os.environ.get("ProgramFiles(x86)")
            localapp = os.environ.get("LOCALAPPDATA")

            if pf:
                candidates.append(os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(pf, "Mozilla Firefox", "firefox.exe"))
            if pfx86:
                candidates.append(os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(pfx86, "Mozilla Firefox", "firefox.exe"))
            if localapp:
                candidates.append(os.path.join(localapp, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(localapp, "Mozilla Firefox", "firefox.exe"))

            for path in candidates:
                if path and os.path.exists(path):
                    return True
        except Exception:
            pass
        return False

    def on_place_id_change(self, event=None):
        """Called when place ID changes"""
        place_id = self.place_entry.get().strip()
        self._schedule_setting_save("last_place_id", place_id, delay_ms=250)
        self.update_game_name()

    def on_private_server_change(self, event=None):
        """Called when private server ID changes"""
        private_server = self.private_server_entry.get().strip()
        self._schedule_setting_save("last_private_server", private_server, delay_ms=250)

    def _normalize_launch_input_mode(self, mode):
        normalized = str(mode or "place_id").strip().lower()
        if normalized == "join_user":
            return "join_user"
        return "place_id"

    def _normalize_place_target_mode(self, mode):
        normalized = str(mode or "private_server").strip().lower()
        if normalized == "job_id":
            return "job_id"
        return "private_server"

    def _set_place_target_mode(self, mode, save=True):
        normalized = self._normalize_place_target_mode(mode)
        self.place_join_target_mode = normalized
        if normalized == "job_id":
            self.private_server_label.configure(text="Job ID (Optional)")
        else:
            self.private_server_label.configure(text="Private Server ID (Optional)")
        if save:
            self._schedule_setting_save("place_join_target_mode", normalized, delay_ms=0)

    def toggle_place_target_mode(self):
        next_mode = "job_id" if self._normalize_place_target_mode(self.place_join_target_mode) == "private_server" else "private_server"
        self._set_place_target_mode(next_mode, save=True)

    def show_place_target_context_menu(self, event):
        if self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id")) != "place_id":
            return
        menu = getattr(self, "place_target_context_menu", None)
        if menu is None:
            return
        try:
            menu.delete(0, "end")
            current_mode = self._normalize_place_target_mode(self.place_join_target_mode)
            target_mode = "job_id" if current_mode == "private_server" else "private_server"
            target_label = "Join Job ID" if target_mode == "job_id" else "Private Server ID"
            menu.add_command(
                label=f"Switch to {target_label}",
                command=self.toggle_place_target_mode,
            )
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _set_launch_input_mode(self, mode, save=True):
        normalized = self._normalize_launch_input_mode(mode)
        self.launch_input_mode = normalized

        is_join_user = normalized == "join_user"
        self.place_label.configure(text="Join User" if is_join_user else "Place ID")
        self.join_place_button.configure(text="Join User" if is_join_user else "Join Place ID")
        if hasattr(self, "recent_list_label") and self.recent_list_label:
            self.recent_list_label.configure(text="Recent users" if is_join_user else "Recent games")

        private_server_visible = self.private_server_field_frame.winfo_manager()
        if is_join_user:
            if private_server_visible:
                self.private_server_field_frame.pack_forget()
        else:
            if not private_server_visible:
                self.private_server_field_frame.pack(fill="x", pady=(0, 5), before=self.version_label)
            self._set_place_target_mode(self.place_join_target_mode, save=False)

        if save:
            self._schedule_setting_save("launch_input_mode", normalized, delay_ms=0)

        if is_join_user:
            self._last_game_name_query_value = None
        self.update_game_name()
        if getattr(self, "game_list", None):
            self.refresh_game_list()

    def toggle_launch_input_mode(self):
        next_mode = "join_user" if self._normalize_launch_input_mode(self.launch_input_mode) == "place_id" else "place_id"
        self._set_launch_input_mode(next_mode, save=True)

    def show_launch_input_context_menu(self, event):
        menu = getattr(self, "launch_input_context_menu", None)
        if menu is None:
            return
        try:
            menu.delete(0, "end")
            current_mode = self._normalize_launch_input_mode(self.launch_input_mode)
            target_mode = "join_user" if current_mode == "place_id" else "place_id"
            target_label = "Join User" if target_mode == "join_user" else "Place ID"
            menu.add_command(
                label=f"Switch to {target_label}",
                command=self.toggle_launch_input_mode,
            )
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def update_game_name(self):
        """Debounced, non-blocking update of the game name label"""
        if self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id")) == "join_user":
            join_user_value = self.place_entry.get().strip()
            if join_user_value == self._last_game_name_query_value:
                return

            self._last_game_name_query_value = join_user_value
            self._game_name_request_token += 1
            request_token = self._game_name_request_token

            if self._game_name_after_id is not None:
                try:
                    self.root.after_cancel(self._game_name_after_id)
                except Exception:
                    pass
                self._game_name_after_id = None

            if not join_user_value:
                self.game_name_label.config(text="")
                return

            self._set_game_name_label("Checking user status...")

            def schedule_join_user_fetch(token=request_token, user_text=join_user_value):
                def worker(identifier, active_token):
                    status = RobloxAPI.get_join_user_status(identifier)
                    self.root.after(0, lambda: self._handle_join_user_status_result(active_token, status))

                threading.Thread(target=worker, args=(user_text, token), daemon=True).start()

            self._game_name_after_id = self.root.after(350, schedule_join_user_fetch)
            return

        place_id = self.place_entry.get().strip()
        if place_id == self._last_game_name_query_value:
            return

        self._last_game_name_query_value = place_id
        self._game_name_request_token += 1
        request_token = self._game_name_request_token

        if self._game_name_after_id is not None:
            try:
                self.root.after_cancel(self._game_name_after_id)
            except Exception:
                pass
            self._game_name_after_id = None

        def schedule_fetch(token=request_token, pid=place_id):
            if not pid or not pid.isdigit():
                self._handle_game_name_result(token, None)
                return

            def worker(pid_value, active_token):
                name = RobloxAPI.get_game_name(pid_value)
                self.root.after(0, lambda: self._handle_game_name_result(active_token, name))

            threading.Thread(target=worker, args=(pid, token), daemon=True).start()

        self._game_name_after_id = self.root.after(350, schedule_fetch)

    def _handle_game_name_result(self, token, name):
        if token != self._game_name_request_token:
            return
        text = f"Current: {name}" if name else ""
        self._set_game_name_label(text)

    def _handle_join_user_status_result(self, token, status):
        if token != self._game_name_request_token:
            return

        if not isinstance(status, dict):
            self._set_game_name_label("User status unavailable")
            return

        username = str(status.get("username") or "").strip()
        user_id = str(status.get("user_id") or "").strip()
        has_identity = bool(username or user_id)
        if not has_identity:
            error = str(status.get("error") or "").strip()
            if error.lower() == "user not found":
                self._set_game_name_label("User not found")
            elif error:
                self._set_game_name_label(f"User status unavailable ({error})")
            else:
                self._set_game_name_label("User status unavailable")
            return

        display_name = username if username else user_id
        joinable = bool(status.get("joinable", False))
        state_text = "Joinable" if joinable else "Not Joinable"
        self._set_game_name_label(f"User: {display_name} | {state_text}")

    def _set_game_name_label(self, text):
        if self._game_name_label_after_id is not None:
            try:
                self.root.after_cancel(self._game_name_label_after_id)
            except Exception:
                pass
            self._game_name_label_after_id = None

        def update_label():
            try:
                self.game_name_label.config(text=text)
            except Exception:
                pass

        self._game_name_label_after_id = self.root.after(0, update_label)

    def add_game_to_list(self, place_id, game_name, private_server=""):
        """Add a game to the saved list (max based on settings)"""
        self.update_game_name()
        
        for game in self.settings["game_list"]:
            if game["place_id"] == place_id and game.get("private_server", "") == private_server:
                return
        
        self.settings["game_list"].insert(0, {
            "place_id": place_id,
            "name": game_name,
            "private_server": private_server
        })
        
        max_games = self.settings.get("max_recent_games", 10)
        if len(self.settings["game_list"]) > max_games:
            self.settings["game_list"] = self.settings["game_list"][:max_games]
        
        self.save_settings()
        self.refresh_game_list()

    def add_recent_user_to_list(self, user_id, username=""):
        """Add a user to the recent users list."""
        user_id_text = str(user_id or "").strip()
        username_text = str(username or "").strip()
        if not user_id_text:
            return

        recent_users = self.settings.get("recent_user_list", [])
        if not isinstance(recent_users, list):
            recent_users = []

        normalized_users = []
        for row in recent_users:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("user_id") or "").strip()
            row_name = str(row.get("username") or "").strip()
            if not row_id:
                continue
            if row_id == user_id_text:
                continue
            normalized_users.append({"user_id": row_id, "username": row_name})

        normalized_users.insert(0, {"user_id": user_id_text, "username": username_text})
        max_games = self.settings.get("max_recent_games", 10)
        if len(normalized_users) > max_games:
            normalized_users = normalized_users[:max_games]

        self.settings["recent_user_list"] = normalized_users
        self.save_settings()
        self.refresh_game_list()

    def refresh_game_list(self):
        """Refresh the game list display"""
        self.game_list.delete(0, tk.END)
        launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
        if launch_mode == "join_user":
            for user in self.settings.get("recent_user_list", []):
                if not isinstance(user, dict):
                    continue
                user_id = str(user.get("user_id") or "").strip()
                username = str(user.get("username") or "").strip()
                if not user_id:
                    continue
                if username:
                    display_text = f"{username} ({user_id})"
                else:
                    display_text = user_id
                self.game_list.insert(tk.END, display_text)
            return

        for game in self.settings["game_list"]:
            private_server = game.get("private_server", "")
            prefix = "[P] " if private_server else ""
            display_text = f"{prefix}{game['name']} ({game['place_id']})"
            self.game_list.insert(tk.END, display_text)

    def on_game_select(self, event=None):
        """Called when a game is selected from the list"""
        selection = self.game_list.curselection()
        if selection:
            index = selection[0]
            launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
            if launch_mode == "join_user":
                recent_users = self.settings.get("recent_user_list", [])
                if index >= len(recent_users):
                    return
                user = recent_users[index]
                user_id = str(user.get("user_id") or "").strip()
                username = str(user.get("username") or "").strip()
                value = username or user_id
                if not value:
                    return
                self.place_entry.delete(0, tk.END)
                self.place_entry.insert(0, value)
                self.settings["last_place_id"] = value
                self.save_settings()
                self.update_game_name()
                return

            game = self.settings["game_list"][index]
            self.place_entry.delete(0, tk.END)
            self.place_entry.insert(0, game["place_id"])
            self.settings["last_place_id"] = game["place_id"]
            
            private_server = game.get("private_server", "")
            self.private_server_entry.delete(0, tk.END)
            self.private_server_entry.insert(0, private_server)
            self.settings["last_private_server"] = private_server
            
            self.save_settings()
            self.update_game_name()

    def delete_game_from_list(self):
        """Delete selected game from the list"""
        selection = self.game_list.curselection()
        if not selection:
            launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
            thing = "user" if launch_mode == "join_user" else "game"
            messagebox.showwarning("No Selection", f"Please select a {thing} to delete.")
            return
        
        index = selection[0]
        launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
        if launch_mode == "join_user":
            recent_users = self.settings.get("recent_user_list", [])
            if index >= len(recent_users):
                return
            user = recent_users[index]
            user_id = str(user.get("user_id") or "").strip()
            username = str(user.get("username") or "").strip()
            display_name = username or user_id or "this user"
            confirm = messagebox.askyesno("Confirm Delete", f"Delete '{display_name}' from list?")
            if confirm:
                recent_users.pop(index)
                self.settings["recent_user_list"] = recent_users
                self.save_settings()
                self.refresh_game_list()
                self.show_success_message("User removed from list!")
            return

        game = self.settings["game_list"][index]
        confirm = messagebox.askyesno("Confirm Delete", f"Delete '{game['name']}' from list?")
        if confirm:
            self.settings["game_list"].pop(index)
            self.save_settings()
            self.refresh_game_list()
            self.show_success_message("Game removed from list!")

    def _extract_username(self, display_text):
        if display_text.startswith(f"{INVALID_ACCOUNT_SYMBOL} "):
            display_text = display_text[2:]
        if display_text.startswith("[!] "):
            display_text = display_text[4:]
        if " | " in display_text:
            return display_text.split(" | ", 1)[0]
        return display_text

    def refresh_accounts(self, selected_usernames=None):
        """Refresh the account list"""
        if selected_usernames is None:
            selected_usernames = [
                self._extract_username(self.account_list.get(idx))
                for idx in self.account_list.curselection()
            ]

        self.account_list.delete(0, tk.END)
        active_group = self._get_active_group()
        display_items = []
        username_to_indices = {}
        invalid_indices = []

        for username in list(self._account_validation_status.keys()):
            if username not in self.manager.accounts:
                self._account_validation_status.pop(username, None)

        for username, data in self.manager.accounts.items():
            if not isinstance(data, dict):
                continue

            self._account_validation_status.setdefault(username, None)

            group = (data.get('group') or '').strip()
            if active_group and group != active_group:
                continue

            note = (data.get('note') or '').strip()
            display_text = f"{username}"
            if self._account_validation_status.get(username) is False:
                display_text = f"{INVALID_ACCOUNT_SYMBOL} {display_text}"
            if group:
                display_text += f" | [{group}]"
            if note:
                display_text += f" | {note}"

            idx = len(display_items)
            display_items.append(display_text)
            username_to_indices.setdefault(username, []).append(idx)
            if self._account_validation_status.get(username) is False:
                invalid_indices.append(idx)

        if display_items:
            self.account_list.insert(tk.END, *display_items)
            for idx in invalid_indices:
                try:
                    self.account_list.itemconfig(idx, fg="#ff4d4f")
                except Exception:
                    pass

        first_selected_idx = None
        for username in selected_usernames:
            for idx in username_to_indices.get(username, []):
                self.account_list.selection_set(idx)
                if first_selected_idx is None:
                    first_selected_idx = idx

        if first_selected_idx is not None:
            self.account_list.activate(first_selected_idx)

    def _schedule_startup_account_validation(self):
        """Kick off a quiet, background account validation pass after startup."""
        if getattr(self, "_startup_validation_started", False):
            return
        self._startup_validation_started = True
        self.root.after(1200, self._validate_accounts_on_startup_silent)

    def _validate_accounts_on_startup_silent(self):
        """Validate all accounts without popups and mark invalid ones in the list."""
        if getattr(self, "_startup_validation_in_progress", False):
            return
        if getattr(self, "_validation_in_progress", False):
            self.root.after(1000, self._validate_accounts_on_startup_silent)
            return

        usernames = [uname for uname, data in self.manager.accounts.items() if isinstance(data, dict)]
        if not usernames:
            return

        self._startup_validation_in_progress = True

        def worker(all_usernames):
            status_updates = {}
            for uname in all_usernames:
                try:
                    status_updates[uname] = bool(self.manager.validate_account(uname, verbose=False))
                except Exception:
                    status_updates[uname] = False

            def done():
                self._startup_validation_in_progress = False
                self._account_validation_status.update(status_updates)
                self.refresh_accounts()
                total = len(all_usernames)
                passed = sum(1 for u in all_usernames if status_updates.get(u))
                print(f"[INFO] {passed}/{total} Accounts Passed validation")

            self.root.after(0, done)

        threading.Thread(target=worker, args=(list(usernames),), daemon=True).start()

    def get_selected_username(self):
        """Get the currently selected username"""
        selection = self.account_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an account first.")
            return None
        
        display_text = self.account_list.get(selection[0])
        return self._extract_username(display_text)
    
    def get_selected_usernames(self):
        """Get all selected usernames (for multi-select mode)"""
        selections = self.account_list.curselection()
        if not selections:
            messagebox.showwarning("No Selection", "Please select at least one account first.")
            return []
        
        return [self._extract_username(self.account_list.get(index)) for index in selections]

    def _get_selected_usernames_silent(self):
        """Get selected usernames without showing warning popups."""
        selections = self.account_list.curselection()
        if not selections:
            return []
        return [self._extract_username(self.account_list.get(index)) for index in selections]

    def _copy_text_to_clipboard(self, text):
        """Copy text to clipboard and return True on success."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            return True
        except Exception:
            return False

    def copy_selected_account_usernames(self):
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Copy Username", "Please select at least one account first.")
            return

        unique_usernames = list(dict.fromkeys(usernames))
        if self._copy_text_to_clipboard("\n".join(unique_usernames)):
            self.show_success_message("Username copied." if len(unique_usernames) == 1 else "Usernames copied.")

    def copy_selected_account_passwords(self):
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Copy Password", "Please select at least one account first.")
            return

        passwords = []
        for username in usernames:
            account_data = self.manager.accounts.get(username)
            if not isinstance(account_data, dict):
                continue
            password_value = str(account_data.get("password", "") or "").strip()
            if password_value:
                passwords.append(password_value)

        if not passwords:
            messagebox.showinfo("Copy Password", "No password found for the selected account(s).")
            return

        unique_passwords = list(dict.fromkeys(passwords))
        if self._copy_text_to_clipboard("\n".join(unique_passwords)):
            self.show_success_message("Password copied." if len(unique_passwords) == 1 else "Passwords copied.")

    def copy_selected_account_cookies(self):
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Copy Cookie", "Please select at least one account first.")
            return

        cookies = []
        for username in usernames:
            cookie_value = str(self.manager.get_account_cookie(username) or "").strip()
            if cookie_value:
                cookies.append(cookie_value)

        if not cookies:
            messagebox.showinfo("Copy Cookie", "No cookie found for the selected account(s).")
            return

        unique_cookies = list(dict.fromkeys(cookies))
        if self._copy_text_to_clipboard("\n".join(unique_cookies)):
            self.show_success_message("Cookie copied." if len(unique_cookies) == 1 else "Cookies copied.")

    def show_account_context_menu(self, event):
        if not self.account_list or self.account_list.size() <= 0:
            return "break"

        index = self.account_list.nearest(event.y)
        if index < 0 or index >= self.account_list.size():
            return "break"

        bbox = self.account_list.bbox(index)
        if bbox:
            _, y, _, height = bbox
            if event.y < y or event.y > (y + height):
                return "break"

        self._hide_drop_indicator()
        self._reset_drag_data()

        current_selection = set(self.account_list.curselection())
        if index not in current_selection:
            self.account_list.selection_clear(0, tk.END)
            self.account_list.selection_set(index)
        self.account_list.activate(index)

        menu = getattr(self, "account_context_menu", None)
        if menu is None:
            return "break"

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def on_account_drag_start(self, event):
        if self.account_list.size() <= 1:
            return
        index = self.account_list.nearest(event.y)
        if index < 0 or index >= self.account_list.size():
            return "break"
        self.account_list.selection_clear(0, tk.END)
        self.account_list.selection_set(index)
        self.account_list.activate(index)
        display_text = self.account_list.get(index)
        self.account_list_drag_data.update({
            "start_index": index,
            "drop_index": index,
            "start_username": self._extract_username(display_text),
            "start_y": event.y,
            "is_dragging": False
        })
        return "break"

    def on_account_drag_motion(self, event):
        data = self.account_list_drag_data
        if data["start_index"] is None:
            return "break"
        start_y = data.get("start_y")
        if not data["is_dragging"]:
            if start_y is None:
                data["start_y"] = event.y
                return "break"
            if abs(event.y - start_y) < 4:
                return "break"
        drop_index = self._get_drop_index_from_event(event.y)
        data["drop_index"] = drop_index
        data["is_dragging"] = True
        self._update_drop_indicator(drop_index)
        return "break"

    def on_account_drag_stop(self, event):
        data = self.account_list_drag_data

        self._hide_drop_indicator()
        if not data["is_dragging"] or data["start_index"] is None:
            self._reset_drag_data()
            return "break"

        drop_index = data["drop_index"]
        start_index = data["start_index"]
        if drop_index is None or drop_index == start_index or drop_index == start_index + 1:
            self._reset_drag_data()
            return "break"

        self._finalize_account_reorder(start_index, drop_index, data["start_username"])
        self._reset_drag_data()
        return "break"

    def on_account_ctrl_click(self, event):
        if not self.settings.get("enable_multi_select", False):
            return "break"
        if self.account_list.size() <= 0:
            return "break"
        index = self.account_list.nearest(event.y)
        if index < 0 or index >= self.account_list.size():
            return "break"

        self._hide_drop_indicator()
        self._reset_drag_data()

        if index in self.account_list.curselection():
            self.account_list.selection_clear(index)
        else:
            self.account_list.selection_set(index)
        self.account_list.activate(index)
        return "break"

    @staticmethod
    def _drag_modifiers_active(event):
        modifiers_mask = 0x1 | 0x4 | 0x8
        return bool(event.state & modifiers_mask)

    @staticmethod
    def _ctrl_modifier_active(event):
        return bool(event.state & 0x4)

    def _reset_drag_data(self):
        self.account_list_drag_data = {
            "start_index": None,
            "drop_index": None,
            "start_username": None,
            "start_y": None,
            "is_dragging": False
        }

    def _get_drop_index_from_event(self, y_coord):
        try:
            self.account_list.update_idletasks()
        except Exception:
            pass
        size = self.account_list.size()
        if size == 0:
            return None
        nearest = self.account_list.nearest(y_coord)
        nearest = min(max(nearest, 0), size - 1)
        bbox = self.account_list.bbox(nearest)
        if not bbox:
            return None
        _, y, _, height = bbox
        if y_coord > y + height / 2:
            return min(nearest + 1, size)
        return nearest

    def _update_drop_indicator(self, drop_index):
        try:
            self.account_list.update_idletasks()
        except Exception:
            pass
        if self.account_drop_indicator is None or drop_index is None:
            self._hide_drop_indicator()
            return
        size = self.account_list.size()
        if size == 0:
            self._hide_drop_indicator()
            return
        if drop_index >= size:
            bbox = self.account_list.bbox(size - 1)
            if not bbox:
                self._hide_drop_indicator()
                return
            y = bbox[1] + bbox[3]
        else:
            bbox = self.account_list.bbox(drop_index)
            if not bbox:
                self._hide_drop_indicator()
                return
            y = bbox[1]
        self.account_drop_indicator.place(x=0, y=y - 1, relwidth=1)

    def _hide_drop_indicator(self):
        if self.account_drop_indicator:
            self.account_drop_indicator.place_forget()

    def _finalize_account_reorder(self, start_index, drop_index, moved_username):
        visible_usernames = [self._extract_username(text) for text in self.account_list.get(0, tk.END)]
        if not visible_usernames:
            return

        drop_index = max(0, min(drop_index, len(visible_usernames)))
        entry = visible_usernames.pop(start_index)
        if drop_index > start_index:
            drop_index -= 1
        visible_usernames.insert(drop_index, entry)

        active_group = self._get_active_group()
        if not active_group:
            self.manager.reorder_accounts(visible_usernames)
            self.refresh_accounts(selected_usernames=[moved_username])
            return

        current_order = list(self.manager.accounts.keys())
        visible_set = set(visible_usernames)
        if not current_order or not visible_set:
            return

        replacement_iter = iter(visible_usernames)
        new_order = []
        for username in current_order:
            if username in visible_set:
                try:
                    new_order.append(next(replacement_iter))
                except StopIteration:
                    new_order.append(username)
            else:
                new_order.append(username)

        self.manager.reorder_accounts(new_order)
        self.refresh_accounts(selected_usernames=[moved_username])

    def _copy_quick_sign_in_code(self, code_var):
        code = str(code_var.get() or "").strip()
        if not code or code.startswith("Waiting"):
            messagebox.showinfo("Quick Sign-In", "A code is not available yet.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.root.update()
            self.show_success_message("Quick Sign-In code copied.")
        except Exception as exc:
            messagebox.showerror("Quick Sign-In", f"Failed to copy code: {exc}")

    def open_quick_sign_in_window(self):
        if not self.is_chrome_installed():
            messagebox.showwarning(
                "Browser Required",
                "Quick Sign-In requires Google Chrome or Mozilla Firefox to be installed.\n"
                "Please install one of them and try again."
            )
            return

        quick_window = tk.Toplevel(self.root)
        quick_window.title("Quick Sign-In")
        quick_window.geometry("460x250")
        quick_window.configure(bg=self.BG_DARK)
        quick_window.resizable(False, False)

        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        x = main_x + (main_width - 460) // 2
        y = main_y + (main_height - 250) // 2
        quick_window.geometry(f"460x250+{x}+{y}")

        if self.settings.get("enable_topmost", False):
            quick_window.attributes("-topmost", True)

        quick_window.transient(self.root)
        quick_window.grab_set()
        self.register_toplevel(quick_window)

        content = ttk.Frame(quick_window, style="Dark.TFrame")
        content.pack(fill="both", expand=True, padx=18, pady=16)

        ttk.Label(
            content,
            text="Quick Sign-In",
            style="Dark.TLabel",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            content,
            text="Enter this code on your phone, tablet, or another signed-in device.",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 10))

        code_var = tk.StringVar(value="Waiting for code...")
        status_var = tk.StringVar(value="Opening browser...")

        code_label = tk.Label(
            content,
            textvariable=code_var,
            bg=self.BG_MID,
            fg=self.FG_ACCENT,
            font=("Consolas", 21, "bold"),
            relief="solid",
            borderwidth=1,
            padx=18,
            pady=12,
        )
        code_label.pack(fill="x")

        status_label = ttk.Label(
            content,
            textvariable=status_var,
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            wraplength=420,
        )
        status_label.pack(anchor="w", pady=(10, 12))

        button_row = ttk.Frame(content, style="Dark.TFrame")
        button_row.pack(fill="x")

        copy_button = ttk.Button(
            button_row,
            text="Copy Code",
            style="Dark.TButton",
            command=lambda: self._copy_quick_sign_in_code(code_var),
        )
        copy_button.pack(side="left", fill="x", expand=True, padx=(0, 4))

        close_button = ttk.Button(
            button_row,
            text="Cancel",
            style="Dark.TButton",
        )
        close_button.pack(side="left", fill="x", expand=True, padx=(4, 0))

        cancel_event = threading.Event()

        def ui_update(fn):
            self.root.after(
                0,
                lambda: fn() if quick_window.winfo_exists() else None
            )

        def set_code(value):
            cleaned = str(value or "").strip()
            if not cleaned:
                return
            ui_update(lambda: code_var.set(cleaned))

        def set_status(value):
            ui_update(lambda: status_var.set(str(value or "")))

        def close_window():
            cancel_event.set()
            if quick_window.winfo_exists():
                quick_window.destroy()

        close_button.configure(command=close_window)
        quick_window.protocol("WM_DELETE_WINDOW", close_window)

        def run_quick_sign_in():
            result = self.manager.add_account_quick_sign_in(
                preferred_browser=self._get_preferred_browser(),
                on_code=set_code,
                on_status=set_status,
                timeout=300,
                cancel_event=cancel_event,
            )

            def finalize():
                success = bool(result.get("success"))
                error_message = str(result.get("error") or "").strip()
                username = str(result.get("username") or "").strip()

                if success:
                    self.refresh_accounts(selected_usernames=[username] if username else None)
                    self.show_success_message(f"Account added via Quick Sign-In: {username}")
                    if quick_window.winfo_exists():
                        quick_window.destroy()
                    return

                if error_message and "cancelled" not in error_message.lower():
                    if quick_window.winfo_exists():
                        status_var.set(error_message)
                    messagebox.showerror("Quick Sign-In", error_message)

            self.root.after(0, finalize)

        threading.Thread(target=run_quick_sign_in, daemon=True).start()

    def add_account(self):
        """
        Add a new account using browser automation
        """
        if not self.is_chrome_installed():
            messagebox.showwarning(
                "Browser Required",
                "Add Account requires Google Chrome or Mozilla Firefox to be installed.\n"
                "Please install one of them and try again."
            )
            return

        messagebox.showinfo("Add Account", "Browser will open for account login.\nPlease log in and wait for the process to complete.")
        
        def add_account_thread():
            """
            Thread function to add account without blocking UI
            """
            try:
                success = self.manager.add_account(
                    1,
                    "https://www.roblox.com/login",
                    "",
                    preferred_browser=self._get_preferred_browser(),
                )
                self.root.after(
                    0,
                    lambda: self._add_account_complete(success)
                )
            except Exception as e:
                self.root.after(
                    0,
                    lambda: self._add_account_error(str(e))
                )
        
        thread = threading.Thread(target=add_account_thread, daemon=True)
        thread.start()
    
    def _add_account_complete(self, success):
        """
        Called when account addition completes (on main thread)
        """
        if success:
            self.refresh_accounts()
            self.show_success_message("Account added successfully!")
        else:
            messagebox.showerror("Error", "Failed to add account.\nPlease make sure you completed the login process.")
    
    def _add_account_error(self, error_msg):
        """
        Called when account addition encounters an error (on main thread)
        """
        messagebox.showerror("Error", f"Failed to add account: {str(error_msg)}")
    
    def import_cookie(self):
        """
        Import an account using a .ROBLOSECURITY cookie
        """
        import_window = tk.Toplevel(self.root)
        import_window.title("Import Cookie")
        import_window.geometry("450x250")
        import_window.configure(bg=self.BG_DARK)
        import_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 450) // 2
        y = main_y + (main_height - 250) // 2
        import_window.geometry(f"450x250+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            import_window.attributes("-topmost", True)
        
        import_window.transient(self.root)
        import_window.grab_set()
        self.register_toplevel(import_window)
        
        main_frame = ttk.Frame(import_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Import Account from Cookie",
            style="Dark.TLabel",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 15))
        
        ttk.Label(main_frame, text="Cookie (.ROBLOSECURITY):", style="Dark.TLabel").pack(anchor="w", pady=(0, 5))
        
        cookie_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        cookie_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        cookie_text = tk.Text(
            cookie_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9),
            height=5,
            wrap="word"
        )
        cookie_text.pack(side="left", fill="both", expand=True)
        self.register_themable_text_widget(cookie_text)
        
        cookie_scrollbar = ttk.Scrollbar(cookie_frame, command=cookie_text.yview)
        cookie_scrollbar.pack(side="right", fill="y")
        cookie_text.config(yscrollcommand=cookie_scrollbar.set)
        
        def do_import():
            cookie = cookie_text.get("1.0", "end-1c").strip()
            
            if not cookie:
                messagebox.showwarning("Missing Information", "Please enter the cookie.")
                return
            
            try:
                success, username = self.manager.import_cookie_account(cookie)
                if success:
                    self.refresh_accounts()
                    self.show_success_message(f"Account '{username}' imported successfully!")
                    import_window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to import account. Please check the cookie.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import account: {str(e)}")
        
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")
        
        ttk.Button(
            button_frame,
            text="Import",
            style="Dark.TButton",
            command=do_import
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=import_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def import_username_password(self):
        import_window = tk.Toplevel(self.root)
        import_window.title("Import Username:Password")
        import_window.geometry("450x320")
        import_window.configure(bg=self.BG_DARK)
        import_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 450) // 2
        y = main_y + (main_height - 320) // 2
        import_window.geometry(f"450x320+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            import_window.attributes("-topmost", True)
        
        import_window.transient(self.root)
        self.register_toplevel(import_window)
        
        main_frame = ttk.Frame(import_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Import Accounts from Username:Password",
            style="Dark.TLabel",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 15))
        
        ttk.Label(
            main_frame,
            text="Paste one per line (example: C0d3Danc3r94:Bloxgen2M4KF)",
            style="Dark.TLabel",
        ).pack(anchor="w", pady=(0, 5))

        cred_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        cred_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        cred_text = tk.Text(
            cred_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9),
            height=8,
            wrap="none"
        )
        cred_text.pack(side="left", fill="both", expand=True)
        self.register_themable_text_widget(cred_text)
        
        cred_scrollbar = ttk.Scrollbar(cred_frame, command=cred_text.yview)
        cred_scrollbar.pack(side="right", fill="y")
        cred_text.config(yscrollcommand=cred_scrollbar.set)
        
        def parse_credentials(raw_text):
            credentials = []
            invalid_lines = 0
            for line in (raw_text or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                if ":" not in line:
                    invalid_lines += 1
                    continue
                username, password = line.split(":", 1)
                username = username.strip()
                password = password.strip()
                if not username or not password:
                    invalid_lines += 1
                    continue
                credentials.append((username, password))
            return credentials, invalid_lines

        def do_import():
            raw = cred_text.get("1.0", "end-1c")
            credentials, invalid_lines = parse_credentials(raw)
            
            if not credentials:
                messagebox.showwarning("Missing Information", "Please paste at least one username:password line.")
                return
            
            if invalid_lines:
                messagebox.showwarning(
                    "Invalid Lines",
                    f"Skipped {invalid_lines} invalid line(s). Format must be username:password."
                )

            def worker(parsed_credentials):
                try:
                    success_count = self.manager.add_accounts_from_credentials(
                        parsed_credentials,
                        preferred_browser=self._get_preferred_browser(),
                    )
                    if success_count > 0:
                        self.root.after(0, lambda: [
                            self.refresh_accounts(),
                            self.show_success_message(f"Imported {success_count} account(s) successfully!"),
                        ])
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error",
                            "No accounts were imported. Check the console for details."
                        ))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"Failed to import accounts: {str(e)}"
                    ))

            threading.Thread(target=worker, args=(credentials,), daemon=True).start()
            import_window.destroy()

        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="Import",
            style="Dark.TButton",
            command=do_import
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=import_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def javascript_import(self):
        """
        Launch multiple browser instances with custom Javascript execution
        """
        amount_window = tk.Toplevel(self.root)
        amount_window.title("Javascript Import - Amount")
        amount_window.geometry("350x150")
        amount_window.configure(bg=self.BG_DARK)
        amount_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 350) // 2
        y = main_y + (main_height - 150) // 2
        amount_window.geometry(f"350x150+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            amount_window.attributes("-topmost", True)
        
        amount_window.transient(self.root)
        self.register_toplevel(amount_window)
        
        main_frame = ttk.Frame(amount_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Amount to open (max 10):",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        amount_entry = ttk.Entry(main_frame, style="Dark.TEntry")
        amount_entry.pack(fill="x", pady=(0, 15))
        amount_entry.insert(0, "1")
        amount_entry.focus_set()
        
        def proceed_to_website():
            try:
                amount = int(amount_entry.get().strip())
                if amount < 1 or amount > 10:
                    messagebox.showwarning("Invalid Amount", "Please enter a number between 1 and 10.")
                    return
                amount_window.destroy()
                self.javascript_import_website(amount)
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number.")
        
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")
        
        ttk.Button(
            button_frame,
            text="Yes",
            style="Dark.TButton",
            command=proceed_to_website
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=amount_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def javascript_import_website(self, amount):
        """
        Get website URL for Javascript import
        """
        website_window = tk.Toplevel(self.root)
        website_window.title("Javascript Import - Website")
        website_window.geometry("450x150")
        website_window.configure(bg=self.BG_DARK)
        website_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 450) // 2
        y = main_y + (main_height - 150) // 2
        website_window.geometry(f"450x150+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            website_window.attributes("-topmost", True)
        
        website_window.transient(self.root)
        self.register_toplevel(website_window)
        
        main_frame = ttk.Frame(website_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Website link to launch:",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        website_entry = ttk.Entry(main_frame, style="Dark.TEntry")
        website_entry.pack(fill="x", pady=(0, 15))
        website_entry.insert(0, "https://www.roblox.com/CreateAccount")
        website_entry.focus_set()
        
        def proceed_to_javascript():
            website = website_entry.get().strip()
            if not website:
                messagebox.showwarning("Missing Information", "Please enter a website URL.")
                return
            if not website.startswith(('http://', 'https://')):
                messagebox.showwarning("Invalid URL", "Please enter a valid URL starting with http:// or https://")
                return
            website_window.destroy()
            self.javascript_import_code(amount, website)
        
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")
        
        ttk.Button(
            button_frame,
            text="Yes",
            style="Dark.TButton",
            command=proceed_to_javascript
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=website_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def launch_javascript_browsers(self, amount, website, javascript):
        """
        Launch account addition with Javascript execution
        """
        def launch_thread():
            """
            Thread function to add account without blocking UI
            """
            try:
                success = self.manager.add_account(
                    amount,
                    website,
                    javascript,
                    preferred_browser=self._get_preferred_browser(),
                )
                
                if success:
                    self.root.after(0, lambda: [
                        self.refresh_accounts(),
                        self.show_success_message(
                            "Account(s) added successfully with Javascript execution!"
                        )
                    ])
                else:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Error",
                        "Failed to add accounts. Please check the console for details."
                    ))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to launch browsers: {str(e)}"
                ))
        
        thread = threading.Thread(target=launch_thread, daemon=True)
        thread.start()

    def force_quit_roblox(self):
        """Force close all Roblox instances via taskkill."""
        confirm = messagebox.askyesno(
            "Force Quit Roblox",
            "This will immediately close all running RobloxPlayerBeta.exe processes. Continue?"
        )
        if not confirm:
            return

        try:
            result = subprocess.run(
                ['taskkill', '/F', '/IM', 'RobloxPlayerBeta.exe'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=12,
                **subprocess_no_window_kwargs(),
            )
        except Exception as exc:
            messagebox.showerror("Force Quit Roblox", f"Failed to run taskkill: {exc}")
            return

        combined_output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            messagebox.showinfo("Force Quit Roblox", "All Roblox instances have been closed.")
        elif "not found" in combined_output.lower():
            messagebox.showinfo("Force Quit Roblox", "No Roblox instances were running.")
        else:
            messagebox.showerror(
                "Force Quit Roblox",
                f"Unable to close Roblox instances. Details:\n{combined_output.strip() or 'Unknown error.'}"
            )

    _MEMORY_TRIM_SET_QUOTA = 0x0100
    _MEMORY_TRIM_QUERY = 0x0400
    _MEMORY_TRIM_VM_OP = 0x0008
    _MEMORY_TRIM_SIZE_T_MAX = ctypes.c_size_t(-1).value

    class _MemoryTrimProcessCounters(ctypes.Structure):
        """Layout for psapi.GetProcessMemoryInfo (working set size)."""

        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    @classmethod
    def _memtrim_find_roblox_windows(cls):
        """Return [(hwnd, title, pid)] for visible Roblox client windows (memory trim)."""
        if platform.system() != "Windows" or win32gui is None or win32process is None:
            return []

        results = []

        def enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True

            title = win32gui.GetWindowText(hwnd)
            window_class = win32gui.GetClassName(hwnd)
            if "Roblox" not in title and window_class != "WINDOWSCLIENT":
                return True

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    import psutil

                    if "roblox" in psutil.Process(pid).name().lower():
                        results.append((hwnd, title, pid))
                except ImportError:
                    if "Roblox" in title:
                        results.append((hwnd, title, pid))
            except Exception:
                if "Roblox" in title:
                    results.append((hwnd, title, 0))

            return True

        win32gui.EnumWindows(enum_handler, None)
        return results

    @classmethod
    def _memtrim_get_working_set(cls, pid):
        """Return working set size in bytes, or None."""
        if not pid or platform.system() != "Windows":
            return None

        access = cls._MEMORY_TRIM_QUERY | cls._MEMORY_TRIM_VM_OP
        try:
            handle = ctypes.windll.kernel32.OpenProcess(access, False, pid)
            if not handle:
                return None

            pmc = cls._MemoryTrimProcessCounters()
            pmc.cb = ctypes.sizeof(pmc)
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(pmc), ctypes.sizeof(pmc)
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            return pmc.WorkingSetSize if ok else None
        except Exception:
            return None

    @classmethod
    def _memtrim_pid(cls, pid):
        """Call SetProcessWorkingSetSize on pid. Returns (ok, message)."""
        if not pid or platform.system() != "Windows":
            return False, "invalid pid"

        access = (
            cls._MEMORY_TRIM_SET_QUOTA
            | cls._MEMORY_TRIM_QUERY
            | cls._MEMORY_TRIM_VM_OP
        )
        try:
            handle = ctypes.windll.kernel32.OpenProcess(access, False, pid)
            if not handle:
                err = ctypes.windll.kernel32.GetLastError()
                return False, f"OpenProcess failed (err={err})"

            size_max = ctypes.c_size_t(cls._MEMORY_TRIM_SIZE_T_MAX)
            ok = ctypes.windll.kernel32.SetProcessWorkingSetSize(
                handle, size_max, size_max
            )
            ctypes.windll.kernel32.CloseHandle(handle)
            if ok:
                return True, "ok"

            err = ctypes.windll.kernel32.GetLastError()
            return False, f"SetProcessWorkingSetSize failed (err={err})"
        except Exception as exc:
            return False, str(exc)

    @classmethod
    def _memtrim_run_pass(cls, windows, on_result=None):
        """Trim each unique PID in windows; optional per-row callback."""
        seen = {}
        results = []
        for hwnd, title, pid in windows:
            if pid in seen:
                row = (hwnd, title, pid, None, None, True, "shared pid")
            else:
                before = cls._memtrim_get_working_set(pid)
                ok, msg = cls._memtrim_pid(pid)
                time.sleep(0.05)
                after = cls._memtrim_get_working_set(pid) if ok else before
                seen[pid] = (before, after)
                row = (hwnd, title, pid, before, after, ok, msg)
            results.append(row)
            if on_result:
                on_result(*row)
        return results

    @classmethod
    def _memtrim_summarize(cls, results):
        """Aggregate totals and failure list from _memtrim_run_pass output."""
        total_before = 0
        total_after = 0
        failures = []
        for _hwnd, title, _pid, before, after, ok, msg in results:
            if before:
                total_before += before
            if after:
                total_after += after
            if not ok and msg != "shared pid":
                failures.append((title, msg))
        saved_mb = (
            (total_before - total_after) / (1024 * 1024)
            if total_before and total_after
            else 0.0
        )
        return total_before, total_after, saved_mb, failures

    def trim_roblox_memory(self):
        """Trim working sets of running Roblox clients to reclaim idle RAM (Windows)."""
        if platform.system() != "Windows":
            messagebox.showerror(
                "Trim Roblox Memory",
                "This feature is only available on Windows.",
            )
            return

        wins = self._memtrim_find_roblox_windows()
        if not wins:
            messagebox.showinfo(
                "Trim Roblox Memory",
                "No Roblox windows found. Open Roblox and try again.",
            )
            return

        try:
            self.trim_roblox_memory_btn.configure(state="disabled")
        except tk.TclError:
            pass

        def worker():
            results = self._memtrim_run_pass(wins)

            def finish():
                try:
                    self.trim_roblox_memory_btn.configure(state="normal")
                except tk.TclError:
                    pass

                _tb, _ta, saved_mb, failures = self._memtrim_summarize(results)
                unique_pids = len({row[2] for row in results if row[2]})
                lines = [
                    f"Trimmed {len(wins)} window(s) ({unique_pids} unique process(es)).",
                    f"Approx. working set reduction this pass: {saved_mb:+.1f} MB",
                ]
                if failures:
                    lines.append("")
                    lines.append(
                        "Some processes could not be trimmed (try running as Administrator):"
                    )
                    for title, msg in failures[:5]:
                        lines.append(f"  • {title[:48]}: {msg}")
                    if len(failures) > 5:
                        lines.append(f"  … and {len(failures) - 5} more.")
                    messagebox.showwarning("Trim Roblox Memory", "\n".join(lines))
                else:
                    self.show_success_message("\n".join(lines), title="Trim Roblox Memory")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="roblox-memory-trim").start()

    def auto_arrange_clients(self):
        """Automatically tile active Roblox client windows on the primary monitor."""
        if platform.system() != "Windows" or not win32gui:
            messagebox.showerror("Auto-Arrange Clients", "This feature is only available on Windows.") # it only supports windows :sob:
            return

        try:
            roblox_windows = self._get_roblox_client_windows()
        except Exception as exc:
            messagebox.showerror("Auto-Arrange Clients", f"Failed to detect Roblox clients:\n{exc}")
            return

        if not roblox_windows:
            messagebox.showinfo("Auto-Arrange Clients", "No active Roblox client windows were detected.")
            return

        try:
            self._arrange_windows_on_primary_monitor(roblox_windows)
        except Exception as exc:
            messagebox.showerror("Auto-Arrange Clients", f"Failed to arrange Roblox clients:\n{exc}")
            return

        self.show_success_message(
            f"Auto-arranged {len(roblox_windows)} Roblox client(s)!",
            title="Auto-Arrange Clients"
        )

    def _get_roblox_client_windows(self):
        """Return a list of HWNDs for visible Roblox client windows."""
        windows = []
        if not win32gui:
            return windows

        seen = set()
        def enum_handler(hwnd, _):
            if hwnd in seen:
                return True
            if not win32gui.IsWindowVisible(hwnd):
                return True

            if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                return True

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True

            exe_path = self._get_process_executable(pid)
            exe_name = os.path.basename(exe_path).lower() if exe_path else ""

            if not exe_name:
                return True

            if exe_name in self.ROBLOX_CLIENT_EXECUTABLES:
                if hwnd not in seen:
                    seen.add(hwnd)
                    windows.append(hwnd)
            return True

        win32gui.EnumWindows(enum_handler, None)
        return windows

    def _get_process_executable(self, pid):
        """Best-effort attempt to resolve the executable path for a process ID."""
        if not win32api or not win32process:
            return None

        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        access_flags = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        handle = None

        try:
            try:
                handle = win32api.OpenProcess(access_flags, False, pid)
            except Exception:
                handle = win32api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

            if not handle:
                return None
            return win32process.GetModuleFileNameEx(handle, 0)
        except Exception:
            return None
        finally:
            if handle:
                try:
                    win32api.CloseHandle(handle)
                except Exception:
                    pass

    def _get_monitor_work_areas(self):
        """Return a list of monitor work areas (primary first)."""
        if not win32api:
            return []

        try:
            monitors = win32api.EnumDisplayMonitors(None, None)
        except Exception:
            return []

        if not monitors:
            return []

        work_areas = []
        for handle, _, _ in monitors:
            try:
                info = win32api.GetMonitorInfo(handle)
            except Exception:
                continue

            work = info.get("Work") or info.get("WorkArea") or info.get("Monitor")
            if not work:
                continue

            is_primary = bool(info.get("Flags", 0) & getattr(win32con, "MONITORINFOF_PRIMARY", 0))
            work_areas.append((is_primary, (work[0], work[1], work[2], work[3])))

        # Primary monitor first, then sort others left-to-right / top-to-bottom for stability.
        work_areas.sort(key=lambda item: (not item[0], item[1][0], item[1][1]))
        return [area for _, area in work_areas]

    def _arrange_windows_on_primary_monitor(self, hwnds):
        """Arrange Roblox clients across selected monitor work areas."""
        if not win32api or not win32gui:
            return

        monitor_work_areas = self._get_monitor_work_areas()
        if not monitor_work_areas:
            return

        scope = self.settings.get("auto_arrange_scope", "both")
        monitor_work_areas = self._filter_monitor_areas_by_scope(monitor_work_areas, scope)
        if not monitor_work_areas:
            return

        hwnds = list(hwnds)
        if not hwnds:
            return

        hwnds = self._sort_windows_by_position(hwnds)
        if not monitor_work_areas:
            return

        monitor_assignments = [[] for _ in monitor_work_areas]
        for index, hwnd in enumerate(hwnds):
            monitor_assignments[index % len(monitor_work_areas)].append(hwnd)

        for monitor_index, assigned_hwnds in enumerate(monitor_assignments):
            if not assigned_hwnds:
                continue
            self._arrange_windows_within_area(assigned_hwnds, monitor_work_areas[monitor_index])

    def _sort_windows_by_position(self, hwnds):
        """Sort windows by current top-left position for deterministic arrangement."""
        positioned = []
        for hwnd in hwnds:
            try:
                left, top, _, _ = win32gui.GetWindowRect(hwnd)
            except Exception:
                left = top = 0
            positioned.append((top, left, hwnd))
        positioned.sort(key=lambda item: (item[0], item[1], item[2]))
        return [item[2] for item in positioned]

    def _get_min_window_size(self, hwnd):
        """Probe the minimum resizable Roblox window size enforced by Windows/client."""
        fallback = (320, 240)
        if not win32gui or not hwnd:
            return fallback

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            left, top, _, _ = win32gui.GetWindowRect(hwnd)
            win32gui.MoveWindow(hwnd, left, top, 1, 1, True)
            min_left, min_top, min_right, min_bottom = win32gui.GetWindowRect(hwnd)
            min_width = max(1, min_right - min_left)
            min_height = max(1, min_bottom - min_top)
            return min_width, min_height
        except Exception:
            return fallback

    def _arrange_windows_within_area(self, hwnds, work_area):
        """Tile the given HWNDs inside a single monitor work area."""
        work_left, work_top, work_right, work_bottom = work_area
        available_width = max(1, work_right - work_left)
        available_height = max(1, work_bottom - work_top)

        window_count = len(hwnds)
        if window_count == 0:
            return

        dimension_mode = self.settings.get("auto_arrange_dimension_mode", "auto")
        columns, rows, tile_width, tile_height = self._get_auto_arrange_tile_layout(
            window_count,
            available_width,
            available_height,
            dimension_mode,
        )

        for index, hwnd in enumerate(hwnds):
            row = index // columns
            col = index % columns
            if row >= rows:
                row = rows - 1

            left = work_left + (col * tile_width)
            top = work_top + (row * tile_height)
            width = max(1, tile_width)
            height = max(1, tile_height)

            # Keep every tile fully inside the monitor work area.
            left = min(left, work_right - width)
            top = min(top, work_bottom - height)

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                ok, _, _ = self._move_resize_window_unclamped(hwnd, left, top, width, height, strip_styles=False)
                if not ok:
                    ok, _, _ = self._move_resize_window_unclamped(hwnd, left, top, width, height, strip_styles=True)
                if not ok:
                    win32gui.MoveWindow(hwnd, left, top, width, height, True)
            except Exception:
                continue

    def _get_auto_arrange_tile_layout(self, window_count, available_width, available_height, dimension_mode):
        """Return (columns, rows, tile_width, tile_height) for auto-arrange."""
        if window_count <= 0:
            return 1, 1, max(1, available_width), max(1, available_height)

        mode = str(dimension_mode or "auto").strip().lower()
        if mode == "target_size":
            target_width = max(1, int(self.settings.get("auto_arrange_target_width", 800) or 800))
            target_height = max(1, int(self.settings.get("auto_arrange_target_height", 600) or 600))

            columns = max(1, min(window_count, available_width // target_width))
            rows = max(1, math.ceil(window_count / columns))

            while rows * target_height > available_height and columns < window_count:
                columns += 1
                rows = max(1, math.ceil(window_count / columns))

            tile_width = max(1, min(target_width, available_width // columns))
            tile_height = max(1, min(target_height, available_height // rows))
            return columns, rows, tile_width, tile_height

        aspect_ratio = available_width / available_height if available_height else 1
        columns = max(1, math.ceil(math.sqrt(window_count * aspect_ratio)))
        columns = min(columns, window_count)
        rows = max(1, math.ceil(window_count / columns))
        tile_width = max(1, available_width // columns)
        tile_height = max(1, available_height // rows)
        return columns, rows, tile_width, tile_height

    def _move_resize_window_unclamped(self, hwnd, x, y, width, height, strip_styles=False):
        """
        Resize using SetWindowPos + SWP_NOSENDCHANGING (test.py method) to bypass
        Roblox minimum-size clamping. Returns (success, actual_width, actual_height).
        """
        if platform.system() != "Windows":
            return False, 0, 0

        user32 = ctypes.windll.user32
        flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_NOSENDCHANGING

        original_style = None
        if strip_styles:
            original_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            stripped_style = original_style & ~(WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
            user32.SetWindowLongW(hwnd, GWL_STYLE, stripped_style)

        user32.SetWindowPos(hwnd, None, int(x), int(y), int(width), int(height), flags)

        if original_style is not None:
            user32.SetWindowLongW(hwnd, GWL_STYLE, original_style)
            user32.SetWindowPos(hwnd, None, int(x), int(y), int(width), int(height), flags)

        time.sleep(0.05)
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            return False, 0, 0

        actual_width = max(1, right - left)
        actual_height = max(1, bottom - top)
        return actual_width == int(width) and actual_height == int(height), actual_width, actual_height

    def _filter_monitor_areas_by_scope(self, work_areas, scope):
        """Filter monitor work areas according to the chosen auto-arrange scope."""
        if not work_areas:
            return []

        if scope == "primary":
            return work_areas[:1]

        if scope == "secondary":
            return work_areas[1:2] if len(work_areas) > 1 else []

        if scope == "both":
            return work_areas

        return work_areas

    def delete_account(self):
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
            if len(usernames) == 1:
                confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{usernames[0]}'?")
            else:
                confirm = messagebox.askyesno(
                    "Confirm Delete",
                    f"Are you sure you want to delete {len(usernames)} accounts?\n\n" + "\n".join(usernames)
                )

            if confirm:
                for username in usernames:
                    self.manager.delete_account(username)
                self.refresh_accounts()
                self.show_success_message(f"{len(usernames)} account(s) deleted successfully!")
        else:
            username = self.get_selected_username()
            if not username:
                return
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{username}'?")
            if confirm:
                self.manager.delete_account(username)
                self.refresh_accounts()
                self.show_success_message(f"Account '{username}' deleted successfully!")

    def validate_account(self):
        """Validate the selected account"""
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]

        if getattr(self, "_validation_in_progress", False):
            messagebox.showinfo("Validation", "Validation is already running.")
            return

        self._validation_in_progress = True
        try:
            self.root.config(cursor="watch")
        except Exception:
            pass

        def worker(selected_usernames):
            valid_usernames = []
            invalid_usernames = []

            for uname in selected_usernames:
                try:
                    is_valid = self.manager.validate_account(uname)
                except Exception:
                    is_valid = False
                if is_valid:
                    valid_usernames.append(uname)
                else:
                    invalid_usernames.append(uname)

            def done():
                self._validation_in_progress = False
                try:
                    self.root.config(cursor="")
                except Exception:
                    pass

                for uname in valid_usernames:
                    self._account_validation_status[uname] = True
                for uname in invalid_usernames:
                    self._account_validation_status[uname] = False
                self.refresh_accounts(selected_usernames=selected_usernames)

                if len(selected_usernames) == 1:
                    if valid_usernames:
                        messagebox.showinfo("Validation", f"Account '{selected_usernames[0]}' is valid!")
                    else:
                        messagebox.showwarning("Validation", f"Account '{selected_usernames[0]}' is invalid or expired.")
                    return

                lines = [
                    f"Validated {len(selected_usernames)} account(s).",
                    "",
                    f"Valid: {len(valid_usernames)}",
                    f"Invalid/Expired: {len(invalid_usernames)}",
                ]

                if valid_usernames:
                    lines.extend(["", "Valid accounts:", *valid_usernames])
                if invalid_usernames:
                    lines.extend(["", "Invalid/Expired accounts:", *invalid_usernames])

                message = "\n".join(lines)
                if invalid_usernames:
                    messagebox.showwarning("Validation", message)
                else:
                    messagebox.showinfo("Validation", message)

            self.root.after(0, done)

        threading.Thread(target=worker, args=(list(usernames),), daemon=True).start()
    
    def edit_account_note(self):
        """Edit note for the selected account(s)"""
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]
        
        if len(usernames) == 1:
            current_note = self.manager.get_account_note(usernames[0])
            title_text = f"Edit Note - {usernames[0]}"
            label_text = f"Edit note for '{usernames[0]}'"
        else:
            current_note = ""
            title_text = f"Edit Note - {len(usernames)} Accounts"
            label_text = f"Edit note for {len(usernames)} accounts"
        
        note_window = tk.Toplevel(self.root)
        note_window.title(title_text)
        note_window.geometry("450x220")
        note_window.configure(bg=self.BG_DARK)
        note_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 450) // 2
        y = main_y + (main_height - 220) // 2
        note_window.geometry(f"450x220+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            note_window.attributes("-topmost", True)
        
        note_window.transient(self.root)
        note_window.grab_set()
        self.register_toplevel(note_window)
        
        main_frame = ttk.Frame(note_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text=label_text,
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        ttk.Label(main_frame, text="Note:", style="Dark.TLabel").pack(anchor="w", pady=(0, 5))
        
        note_text = tk.Text(
            main_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9),
            height=3,
            wrap="word"
        )
        note_text.pack(fill="both", expand=True, pady=(0, 15))
        self.register_themable_text_widget(note_text)
        note_text.insert("1.0", current_note)
        note_text.focus_set()
        
        def save_note():
            new_note = note_text.get("1.0", "end-1c").strip()
            for uname in usernames:
                self.manager.set_account_note(uname, new_note)
            self.refresh_accounts()
            if len(usernames) == 1:
                self.show_success_message(f"Note updated for '{usernames[0]}'!")
            else:
                self.show_success_message(f"Note updated for {len(usernames)} accounts!")
            note_window.destroy()
        
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")
        
        ttk.Button(
            button_frame,
            text="Save",
            style="Dark.TButton",
            command=save_note
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=note_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    def edit_account_group(self):
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]

        initial_value = ""
        if len(usernames) == 1:
            initial_value = self.manager.get_account_group(usernames[0])

        group = simpledialog.askstring(
            "Set Group",
            "Enter group name (blank to clear):",
            initialvalue=initial_value
        )
        if group is None:
            return

        group = group.strip()
        for uname in usernames:
            self.manager.set_account_group(uname, group)

        self.refresh_group_dropdown_values()
        self.refresh_accounts(selected_usernames=usernames)

    def refresh_group_dropdown_values(self):
        groups = self.manager.get_groups()
        values = ["All"] + groups

        dropdown = getattr(self, "group_dropdown", None)
        if dropdown is not None:
            dropdown["values"] = values

        selected = (self.settings.get("selected_group") or "All").strip()
        if selected not in values:
            selected = "All"

        group_var = getattr(self, "group_var", None)
        if group_var is not None:
            group_var.set(selected)

    def on_group_change(self, event=None):
        selected = (self.group_var.get() or "All").strip() if getattr(self, "group_var", None) else "All"
        self.settings["selected_group"] = selected
        self.save_settings()
        self.refresh_accounts()
        self._hide_run_group_button()

    def _get_active_group(self):
        selected = (self.group_var.get() or "All").strip() if getattr(self, "group_var", None) else "All"
        return "" if selected == "All" else selected

    def _on_join_area_enter(self, event=None):
        if self._get_active_group():
            self._show_run_group_button()

    def _on_join_area_leave(self, event=None):
        self.root.after(75, self._hide_run_group_button)

    def _show_run_group_button(self):
        if getattr(self, "_run_group_button_visible", False):
            return
        if not self._get_active_group():
            return
        try:
            self.run_group_button.pack(side="right", padx=(6, 0))
            self._run_group_button_visible = True
        except Exception:
            pass

    def _hide_run_group_button(self):
        if not getattr(self, "_run_group_button_visible", False):
            return
        try:
            if self._get_active_group() and self._widget_under_mouse(self.join_action_frame):
                return
            self.run_group_button.pack_forget()
            self._run_group_button_visible = False
        except Exception:
            pass

    def _widget_under_mouse(self, widget):
        try:
            x_root = self.root.winfo_pointerx()
            y_root = self.root.winfo_pointery()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            w = widget.winfo_width()
            h = widget.winfo_height()
            return x <= x_root <= x + w and y <= y_root <= y + h
        except Exception:
            return False

    def launch_home(self):
        """Launch browser to Roblox home with the selected account(s) logged in (non-blocking)"""
        if not self.is_chrome_installed():
            messagebox.showwarning(
                "Browser Required",
                "Launching browser requires Google Chrome or Mozilla Firefox to be installed.\n"
                "Please install one and try again."
            )
            return

        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
            if len(usernames) >= 3:
                confirm = messagebox.askyesno(
                    "Confirm Launch",
                    f"Are you sure you want to launch {len(usernames)} browser windows?\n\nThis will open multiple browser instances."
                )
                if not confirm:
                    return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]

        launch_delay = self._get_multi_launch_delay()

        def worker(selected_usernames, delay_seconds):
            success_count = 0
            for idx, uname in enumerate(selected_usernames):
                try:
                    if self.manager.launch_home(uname, preferred_browser=self._get_preferred_browser()):
                        success_count += 1
                except Exception as e:
                    print(f"Failed to launch browser for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)
            if success_count > 0:
                self.root.after(0, lambda: self.show_success_message(f"Launched {success_count} browser(s)!"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to launch any browsers."))

        threading.Thread(target=worker, args=(usernames, launch_delay), daemon=True).start()

    def launch_home_app(self, on_done_callback=None):
        """Launch the Roblox client to the home page for the selected account(s) (non-blocking)"""
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
            if len(usernames) >= 3:
                confirm = messagebox.askyesno(
                    "Confirm Launch",
                    f"Are you sure you want to launch {len(usernames)} Roblox instances to home?\n\nThis will open multiple Roblox windows."
                )
                if not confirm:
                    return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]

        debug_enabled = self.settings.get("enable_debug_logging", False)
        launch_delay = self._get_multi_launch_delay()

        selected_version_label = self.version_var.get()
        version_path = self.version_options.get(selected_version_label)

        def worker(selected_usernames, delay_seconds, done_callback):
            success_count = 0
            for idx, uname in enumerate(selected_usernames):
                try:
                    before_pids = self._get_running_tracked_roblox_pid_set()
                    if self.manager.launch_home_app(uname, version=version_path or None, enable_debug=debug_enabled):
                        success_count += 1
                    time.sleep(0.8)
                    after_pids = self._get_running_tracked_roblox_pid_set()
                    if not (set(after_pids) - set(before_pids)):
                        time.sleep(1.0)
                        after_pids = self._get_running_tracked_roblox_pid_set()
                    self._assign_new_pids_to_account(
                        uname,
                        before_pids,
                        after_pids,
                        launch_context={
                            "mode": "home",
                            "version_path": version_path or None,
                        },
                    )
                except Exception as e:
                    print(f"Failed to launch Roblox home for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)

            def notify(success_count=success_count, selected_usernames=selected_usernames, on_done_callback=done_callback):
                if success_count > 0:
                    if len(selected_usernames) == 1:
                        self.show_success_message("Roblox is launching to home! Check your desktop.")
                    else:
                        self.show_success_message(f"Roblox is launching to home for {success_count} account(s)! Check your desktop.")

                    if on_done_callback is not None:
                        try:
                            on_done_callback(success_count)
                        except Exception:
                            pass
                else:
                    messagebox.showerror("Error", "Failed to launch Roblox.")

            self.root.after(0, notify)

        threading.Thread(target=worker, args=(usernames, launch_delay, on_done_callback), daemon=True).start()

    def _get_running_tracked_roblox_pid_set(self):
        return set(self._query_tasklist_pid_map(getattr(self, "_tracked_roblox_exes", set())).keys())

    def _query_tasklist_pid_map(self, executables):
        """Return pid->image_name for the provided executable names via tasklist."""
        pid_to_image = {}
        if not executables:
            return pid_to_image

        target_exes = {str(item).strip().lower() for item in executables if item}
        if not target_exes:
            return pid_to_image

        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                **subprocess_no_window_kwargs(),
            )
        except Exception:
            return pid_to_image

        stdout = (result.stdout or "").strip()
        if not stdout or stdout.lower().startswith("info:"):
            return pid_to_image

        try:
            rows = csv.reader(io.StringIO(stdout))
        except Exception:
            return pid_to_image

        for row in rows:
            if not row or len(row) < 2:
                continue
            image_name = (row[0] or "").strip().strip('"')
            if not image_name or image_name.lower() not in target_exes:
                continue
            pid_text = (row[1] or "").strip().strip('"')
            try:
                pid_value = int(pid_text)
            except Exception:
                continue
            if pid_value > 0:
                pid_to_image[pid_value] = image_name

        return pid_to_image

    def _normalize_launch_context(self, launch_context):
        context = {
            "mode": "home",
            "game_id": "",
            "private_server_id": "",
            "server_job_id": "",
            "version_path": None,
        }
        if not isinstance(launch_context, dict):
            return context

        mode = str(launch_context.get("mode", "home") or "home").strip().lower()
        if mode == "game":
            context["mode"] = "game"
        elif mode == "join_user":
            context["mode"] = "join_user"
        else:
            context["mode"] = "home"
        context["game_id"] = str(launch_context.get("game_id", "") or "").strip()
        context["private_server_id"] = str(launch_context.get("private_server_id", "") or "").strip()
        context["server_job_id"] = str(launch_context.get("server_job_id", "") or "").strip()
        version_path = launch_context.get("version_path")
        context["version_path"] = str(version_path).strip() if version_path else None
        return context

    def _assign_new_pids_to_account(self, username, before_pids, after_pids, launch_context=None):
        if not username:
            return
        try:
            new_pids = set(after_pids) - set(before_pids)
        except Exception:
            return
        if not new_pids:
            return
        normalized_context = self._normalize_launch_context(launch_context)
        try:
            with self._pid_account_lock:
                for pid_value in new_pids:
                    self._pid_account_map[int(pid_value)] = str(username)
                    self._pid_launch_context_map[int(pid_value)] = dict(normalized_context)
        except Exception:
            pass

        for pid_value in new_pids:
            self._rename_roblox_client_window_title(int(pid_value), str(username))

    def _rename_roblox_client_window_title(self, pid_value, username):
        if platform.system() != "Windows":
            return
        if not pid_value or not username:
            return

        def _rename_worker(target_pid, target_name):
            max_attempts = 15
            delay_seconds = 0.4
            for _ in range(max_attempts):
                hwnd = self._find_main_window_for_pid(target_pid)
                if hwnd:
                    try:
                        win32gui.SetWindowText(hwnd, target_name)
                        return
                    except Exception:
                        pass
                time.sleep(delay_seconds)

        threading.Thread(target=_rename_worker, args=(int(pid_value), str(username)), daemon=True).start()

    def _find_main_window_for_pid(self, pid_value):
        if platform.system() != "Windows":
            return None

        found_hwnd = {"value": None}

        def _enum_handler(hwnd, _):
            if found_hwnd["value"] is not None:
                return False
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                return True
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if int(window_pid) != int(pid_value):
                return True
            found_hwnd["value"] = hwnd
            return False

        try:
            win32gui.EnumWindows(_enum_handler, None)
        except Exception:
            return None
        return found_hwnd["value"]

    def launch_game(self):
        """Launch Roblox game with the selected account(s)"""
        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
        else:
            username = self.get_selected_username()
            if not username:
                return
            usernames = [username]

        self._launch_game_for_usernames(usernames)

    def launch_group_game(self):
        group = self._get_active_group()
        if not group:
            return

        usernames = self.manager.get_accounts_in_group(group)
        if not usernames:
            messagebox.showwarning("Empty Group", f"No accounts found in group '{group}'.")
            return

        self._launch_game_for_usernames(usernames, confirm_group=group)

    def _launch_game_for_usernames(
        self,
        usernames,
        confirm_group=None,
        skip_confirm=False,
        on_done_callback=None,
        trigger_auto_arrange=False,
    ):
        target_value = self.place_entry.get().strip()
        launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
        place_target_mode = self._normalize_place_target_mode(getattr(self, "place_join_target_mode", "private_server"))
        game_id = target_value
        place_target_value = self.private_server_entry.get().strip() if launch_mode == "place_id" else ""
        private_server = place_target_value if (launch_mode == "place_id" and place_target_mode == "private_server") else ""
        manual_server_job_id = place_target_value if (launch_mode == "place_id" and place_target_mode == "job_id") else ""

        selected_version_label = self.version_var.get()
        version_path = self.version_options.get(selected_version_label)

        if not target_value:
            required_label = "Join User" if launch_mode == "join_user" else "Place ID"
            messagebox.showwarning("Missing Information", f"Please enter a {required_label}.")
            return

        if launch_mode == "join_user" and not str(game_id).isdigit():
            resolved_user_id = RobloxAPI.get_user_id_from_username(game_id)
            if not resolved_user_id:
                messagebox.showwarning("User Not Found", f"Could not find Roblox user '{game_id}'.")
                return
            game_id = resolved_user_id

        if (not skip_confirm) and self.settings.get("confirm_before_launch", True) and len(usernames) > 1:
            prompt = (
                f"Are you sure you want to launch {len(usernames)} accounts in group '{confirm_group}'?"
                if confirm_group else
                f"Are you sure you want to launch {len(usernames)} accounts?"
            )
            confirm = messagebox.askyesno("Confirm Launch", prompt)
            if not confirm:
                return

        debug_enabled = self.settings.get("enable_debug_logging", False)
        launch_delay = self._get_multi_launch_delay()
        randomize_server_jobs = self.settings.get("randomize_server_job_ids", False)
        prefer_small_servers = self.settings.get("prefer_small_public_servers", False)

        def worker(selected_usernames, pid, psid, manual_job_id, ver, debug_flag, delay_seconds, randomize_jobs, prefer_small, active_launch_mode, join_input_text):
            success_count = 0
            recent_join_username = ""
            if active_launch_mode == "join_user":
                entered = str(join_input_text or "").strip()
                if entered and not entered.isdigit():
                    recent_join_username = entered
                else:
                    recent_join_username = RobloxAPI.get_username_from_user_id(pid) or ""
            if active_launch_mode == "join_user":
                if psid:
                    print("[INFO] Private server ID is ignored in Join User mode.")
                if randomize_jobs or prefer_small:
                    print("[INFO] Public server selection settings are ignored in Join User mode.")
            if randomize_jobs and psid:
                print("[INFO] Random Job ID setting ignored because a private server link code is set.")
            if prefer_small and psid:
                print("[INFO] Lowest-population server setting ignored because a private server link code is set.")
            if randomize_jobs and manual_job_id:
                print("[INFO] Random Job ID setting ignored because a manual Job ID is set.")
            if prefer_small and manual_job_id:
                print("[INFO] Lowest-population server setting ignored because a manual Job ID is set.")
            if prefer_small and randomize_jobs and not psid and not manual_job_id and active_launch_mode != "join_user":
                print("[INFO] Lowest-population server setting is enabled; random server selection will be ignored.")
            for idx, uname in enumerate(selected_usernames):
                try:
                    server_job_id = ""
                    effective_server_job_id = ""
                    if active_launch_mode == "join_user":
                        server_job_id = ""
                    elif manual_job_id:
                        server_job_id = str(manual_job_id).strip()
                    elif prefer_small and not psid:
                        max_small_server_attempts = 3
                        for attempt in range(1, max_small_server_attempts + 1):
                            server_job_id = RobloxAPI.get_lowest_public_server_job_id(pid) or ""
                            if server_job_id:
                                break
                            if attempt < max_small_server_attempts:
                                time.sleep(0.6 * attempt)
                        if not server_job_id:
                            print("[INFO] Low-population public server unavailable; launching without job ID override.")
                    elif randomize_jobs and not psid:
                        max_random_job_attempts = 3
                        for attempt in range(1, max_random_job_attempts + 1):
                            server_job_id = RobloxAPI.get_random_public_server_job_id(pid) or ""
                            if server_job_id:
                                break
                            if attempt < max_random_job_attempts:
                                time.sleep(0.6 * attempt)
                        if not server_job_id:
                            print("[INFO] Random public server unavailable; launching without randomized job ID.")
                    before_pids = self._get_running_tracked_roblox_pid_set()
                    launched = self.manager.launch_roblox(
                        uname,
                        pid,
                        psid,
                        ver,
                        enable_debug=debug_flag,
                        server_job_id=server_job_id,
                        launch_mode=active_launch_mode,
                    )
                    effective_server_job_id = server_job_id
                    if (
                        active_launch_mode != "join_user"
                        and (not launched)
                        and server_job_id
                        and (randomize_jobs or prefer_small)
                        and not psid
                        and not manual_job_id
                    ):
                        print("[INFO] Server job ID launch failed; retrying with default launch.")
                        launched = self.manager.launch_roblox(
                            uname,
                            pid,
                            psid,
                            ver,
                            enable_debug=debug_flag,
                            server_job_id="",
                            launch_mode=active_launch_mode,
                        )
                        if launched:
                            effective_server_job_id = ""
                    if launched:
                        success_count += 1
                    time.sleep(0.8)
                    after_pids = self._get_running_tracked_roblox_pid_set()
                    if not (set(after_pids) - set(before_pids)):
                        time.sleep(1.0)
                        after_pids = self._get_running_tracked_roblox_pid_set()
                    self._assign_new_pids_to_account(
                        uname,
                        before_pids,
                        after_pids,
                        launch_context={
                            "mode": "join_user" if active_launch_mode == "join_user" else "game",
                            "game_id": pid,
                            "private_server_id": psid,
                            "server_job_id": effective_server_job_id,
                            "version_path": ver,
                        },
                    )
                except Exception as e:
                    print(f"Failed to launch game for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)

            def on_done():
                if success_count > 0:
                    if active_launch_mode != "join_user":
                        gname = RobloxAPI.get_game_name(pid)
                        if gname:
                            self.add_game_to_list(pid, gname, psid)
                        else:
                            self.add_game_to_list(pid, f"Place {pid}", psid)
                    else:
                        self.add_recent_user_to_list(pid, recent_join_username)
                    if len(selected_usernames) == 1:
                        self.show_success_message("Roblox is launching! Check your desktop.")
                    else:
                        self.show_success_message(f"Roblox is launching for {success_count} account(s)! Check your desktop.")

                    if trigger_auto_arrange and self.settings.get("auto_arrange_after_group_launch", False):
                        self._schedule_auto_arrange_clients_silent()

                    if on_done_callback is not None:
                        try:
                            on_done_callback(success_count)
                        except Exception:
                            pass
                else:
                    messagebox.showerror("Error", "Failed to launch Roblox.")

            self.root.after(0, on_done)

        threading.Thread(
            target=worker,
            args=(
                list(usernames),
                game_id,
                private_server,
                manual_server_job_id,
                version_path,
                debug_enabled,
                launch_delay,
                randomize_server_jobs,
                prefer_small_servers,
                launch_mode,
                target_value,
            ),
            daemon=True
        ).start()

    def _schedule_auto_arrange_clients_silent(self, attempts_remaining=8, delay_ms=800):
        """Arrange Roblox windows after launches settle, without showing popups."""
        if attempts_remaining <= 0:
            return

        if platform.system() != "Windows" or not win32gui:
            return

        try:
            roblox_windows = self._get_roblox_client_windows()
        except Exception:
            roblox_windows = []

        if roblox_windows:
            try:
                self._arrange_windows_on_primary_monitor(roblox_windows)
                return
            except Exception:
                pass

        self.root.after(
            max(100, int(delay_ms)),
            lambda: self._schedule_auto_arrange_clients_silent(
                attempts_remaining=attempts_remaining - 1,
                delay_ms=delay_ms,
            ),
        )

    def enable_multi_roblox(self):
        """Enable Multi Roblox + 773 fix"""

        import subprocess
        import win32event
        import win32api
        

        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RobloxPlayerBeta.exe'], 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=10,
                                  **subprocess_no_window_kwargs()) 
            
            if result.stdout and 'RobloxPlayerBeta.exe' in result.stdout:
                response = messagebox.askquestion( 
                    "Roblox Already Running",
                    "A Roblox instance is already running.\n\n"
                    "To use Multi Roblox, you need to close all Roblox instances first.\n\n"
                    "Do you want to close all Roblox instances now?",
                    icon='warning'
                )
                
                if response == 'yes':
                    subprocess.run(['taskkill', '/F', '/IM', 'RobloxPlayerBeta.exe'], 
                                 capture_output=True, text=True, encoding='utf-8', errors='replace',
                                 timeout=10,
                                 **subprocess_no_window_kwargs()) 
                    self.show_success_message("All Roblox instances have been closed.")
                else:
                    return False
            

            mutex = win32event.CreateMutex(None, True, "ROBLOX_singletonEvent") 
            
            cookies_path = os.path.join(
                os.getenv('LOCALAPPDATA'),
                r'Roblox\LocalStorage\RobloxCookies.dat'
            )
            
            cookie_file = None
            if os.path.exists(cookies_path):
                try:
                    cookie_file = open(cookies_path, 'r+b')
                    msvcrt.locking(cookie_file.fileno(), msvcrt.LK_NBLCK, os.path.getsize(cookies_path))
                    print("[INFO] Error 773 fix applied.")

                except OSError:
                    print("[ERROR] Could not lock RobloxCookies.dat. It may already be locked.")

            else:
                print("[ERROR] Cookies file not found. 773 fix skipped.")

            self.multi_roblox_handle = {'mutex': mutex, 'file': cookie_file}
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to enable Multi Roblox: {str(e)}")
            return False
    
    def disable_multi_roblox(self):
        """Disable Multi Roblox and release resources"""
        try:
            if self.multi_roblox_handle:
                
                if self.multi_roblox_handle.get('mutex'):
                    try:
                        import win32event
                        win32event.ReleaseMutex(self.multi_roblox_handle['mutex'])
                    except:
                        pass
                
                self.multi_roblox_handle = None
        except Exception as e:
            print(f"Error disabling Multi Roblox: {e}")
    
    def initialize_multi_roblox(self):
        """Initialize Multi Roblox on startup if enabled in settings"""
        if self.settings.get("enable_multi_roblox", False):
            success = self.enable_multi_roblox()
            if not success:
                self.settings["enable_multi_roblox"] = False
                self.save_settings()

    def open_settings(self):
        """Open the Settings window"""
        settings_window = tk.Toplevel(self.root)
        settings_window.withdraw()
        settings_window.title("Settings")
        settings_window.configure(bg=self.BG_DARK)
        settings_window.resizable(True, True)
        
        settings_window.transient(self.root)
        settings_window.grab_set()
        self.register_toplevel(settings_window)
        
        if self.settings.get("enable_topmost", False):
            settings_window.attributes("-topmost", True)
        
        main_frame = ttk.Frame(settings_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        header_row = tk.Frame(main_frame, bg=self.BG_DARK)
        header_row.pack(fill="x")
        header_text_frame = tk.Frame(header_row, bg=self.BG_DARK)
        header_text_frame.pack(side="left", fill="x", expand=True)

        ttk.Label(
            header_text_frame,
            text="Settings",
            style="Dark.TLabel",
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")
        settings_intro_label = ttk.Label(
            header_text_frame,
            text="Manage app preferences, Roblox launch behavior, and automation tools.",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        )
        settings_intro_label.pack(anchor="w", pady=(2, 10))

        def open_discord_server():
            opened = False
            try:
                if webbrowser is not None:
                    opened = bool(webbrowser.open(DISCORD_SERVER_URL, new=2))
                else:
                    import webbrowser as std_webbrowser
                    opened = bool(std_webbrowser.open(DISCORD_SERVER_URL, new=2))
            except Exception:
                opened = False

            if opened:
                return

            try:
                settings_window.clipboard_clear()
                settings_window.clipboard_append(DISCORD_SERVER_URL)
                settings_window.update_idletasks()
            except Exception:
                pass
            messagebox.showinfo(
                "Discord",
                "Could not open the Discord invite automatically. The invite link was copied to your clipboard.",
                parent=settings_window,
            )

        discord_image = self._load_discord_button_image(size=32)
        if discord_image is not None:
            self._settings_discord_icon = discord_image
            discord_click_target = tk.Label(
                header_row,
                image=discord_image,
                bg=self.BG_DARK,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )
        else:
            self._settings_discord_icon = None
            discord_click_target = tk.Label(
                header_row,
                text="Discord",
                bg=self.BG_DARK,
                fg=self.FG_ACCENT,
                font=("Segoe UI", 11, "underline"),
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )

        discord_click_target.bind("<Button-1>", lambda _e: open_discord_server())
        discord_click_target.pack(side="right", padx=(8, 0), pady=(0, 8))
        
        topmost_var = tk.BooleanVar(value=self.settings.get("enable_topmost", False))
        multi_roblox_var = tk.BooleanVar(value=self.settings.get("enable_multi_roblox", False))
        confirm_launch_var = tk.BooleanVar(value=self.settings.get("confirm_before_launch", False))
        randomize_job_id_var = tk.BooleanVar(value=self.settings.get("randomize_server_job_ids", False))
        prefer_small_servers_var = tk.BooleanVar(value=self.settings.get("prefer_small_public_servers", False))
        multi_select_var = tk.BooleanVar(value=self.settings.get("enable_multi_select", False))
        debug_var = tk.BooleanVar(value=self.settings.get("enable_debug_logging", False))
        hide_sensitive_var = tk.BooleanVar(value=self.settings.get("hide_sensitive_info", False))
        bug_prompt_var = tk.BooleanVar(value=self.settings.get("bug_issue_prompt_enabled", True))
        disable_success_var = tk.BooleanVar(value=self.settings.get("disable_success_popups", False))
        auto_update_var = tk.BooleanVar(value=self.settings.get("auto_update_enabled", True))
        theme_var = tk.StringVar(value=self.settings.get("selected_theme", self.theme_name))
        browser_preference_var = tk.StringVar(value=self._get_preferred_browser())
        custom_launcher_var = tk.BooleanVar(value=self.settings.get("enable_custom_launcher", False))
        custom_launcher_path_var = tk.StringVar(value=self.settings.get("custom_launcher_path", ""))
        custom_launcher_player_var = tk.BooleanVar(value=self.settings.get("custom_launcher_requires_player", False))
        auto_arrange_scope_var = tk.StringVar(value=self.settings.get("auto_arrange_scope", "both"))
        auto_arrange_dimension_mode_var = tk.StringVar(
            value=self.settings.get("auto_arrange_dimension_mode", "auto")
        )
        auto_arrange_target_width_var = tk.IntVar(
            value=int(self.settings.get("auto_arrange_target_width", 800) or 800)
        )
        auto_arrange_target_height_var = tk.IntVar(
            value=int(self.settings.get("auto_arrange_target_height", 600) or 600)
        )
        custom_roblox_player_path_var = tk.StringVar(value=self.settings.get("custom_roblox_player_path", ""))
        installer_previous_versions_var = tk.IntVar(value=clamp_installer_previous_versions(self.settings.get("installer_previous_versions", MIN_INSTALLER_PREVIOUS_VERSIONS)))
        
        def auto_save_setting(setting_name, var):
            def save():
                self.settings[setting_name] = var.get()
                if setting_name == "enable_topmost":
                    self.root.attributes("-topmost", var.get())
                    settings_window.attributes("-topmost", var.get())
                    self.console_window.update_topmost(var.get())
                self.save_settings()
            return save
        
        def on_multi_roblox_toggle():
            if multi_roblox_var.get():
                success = self.enable_multi_roblox()
                if not success:
                    multi_roblox_var.set(False)
                    self.settings["enable_multi_roblox"] = False
                else:
                    self.settings["enable_multi_roblox"] = True
            else:
                self.disable_multi_roblox()
                self.settings["enable_multi_roblox"] = False
            self.save_settings()

        def on_multi_select_toggle():
            self.settings["enable_multi_select"] = multi_select_var.get()
            if multi_select_var.get():
                self.account_list.config(selectmode=tk.EXTENDED)
            else:
                self.account_list.config(selectmode=tk.SINGLE)
            self.save_settings()

        tab_var = tk.StringVar(value="general")
        tab_buttons = {}
        tabs = {}
        settings_cards = []
        settings_muted_labels = [settings_intro_label]

        tab_bar = tk.Frame(main_frame, bg=self.BG_DARK)
        tab_bar.pack(fill="x", pady=(0, 8))

        def set_active_tab(tab_name):
            tab_var.set(tab_name)
            tab = tabs.get(tab_name)
            if tab is not None:
                tab.tkraise()
            for name, btn in tab_buttons.items():
                if name == tab_name:
                    btn.configure(
                        bg=self.BG_LIGHT,
                        fg=self.FG_TEXT,
                        activebackground=self.BG_LIGHT,
                        activeforeground=self.FG_TEXT
                    )
                else:
                    btn.configure(
                        bg=self.BG_MID,
                        fg=self.FG_MUTED,
                        activebackground=self.BG_MID,
                        activeforeground=self.FG_TEXT
                    )

        def create_tab_button(label, tab_name):
            btn = tk.Button(
                tab_bar,
                text=label,
                relief="flat",
                borderwidth=0,
                padx=12,
                pady=3,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
                bg=self.BG_MID,
                fg=self.FG_MUTED,
                activebackground=self.BG_MID,
                activeforeground=self.FG_TEXT
            )
            btn.pack(side="left", padx=(0, 8))
            btn.configure(command=lambda n=tab_name: set_active_tab(n))
            tab_buttons[tab_name] = btn

        content_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        content_frame.pack(fill="both", expand=True)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        tab_scroll_state = {}

        def create_tab_frame(tab_name):
            tab_container = ttk.Frame(content_frame, style="Dark.TFrame")
            tab_container.grid(row=0, column=0, sticky="nsew")
            tab_container.grid_rowconfigure(0, weight=1)
            tab_container.grid_columnconfigure(0, weight=1)

            canvas = tk.Canvas(
                tab_container,
                bg=self.BG_DARK,
                highlightthickness=0,
                bd=0,
            )
            v_scroll = ttk.Scrollbar(tab_container, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=v_scroll.set)

            canvas.grid(row=0, column=0, sticky="nsew")
            v_scroll.grid(row=0, column=1, sticky="ns")

            frame = ttk.Frame(canvas, style="Dark.TFrame")
            canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")

            def _sync_scrollregion(_evt=None):
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                except Exception:
                    pass

            def _on_canvas_resize(_evt=None):
                try:
                    required_width = max(frame.winfo_reqwidth(), canvas.winfo_width())
                    canvas.itemconfigure(canvas_window, width=required_width)
                except Exception:
                    pass
                _sync_scrollregion()

            frame.bind("<Configure>", _sync_scrollregion)
            canvas.bind("<Configure>", _on_canvas_resize)

            tab_scroll_state[tab_name] = {"canvas": canvas}
            tabs[tab_name] = tab_container
            return frame

        create_tab_button("Experience", "general")
        create_tab_button("Roblox", "roblox")
        create_tab_button("Automation", "automation")
        create_tab_button("Tools", "advanced")

        general_tab = create_tab_frame("general")
        roblox_tab = create_tab_frame("roblox")
        automation_tab = create_tab_frame("automation")
        advanced_tab = create_tab_frame("advanced")

        def _settings_resolve_wheel_widget(w):
            if w is None:
                return None
            if not isinstance(w, str):
                return w
            path = w.strip()
            while path:
                for base in (self.root, settings_window):
                    try:
                        return base.nametowidget(path)
                    except (tk.TclError, KeyError):
                        continue
                if "." not in path or path == ".":
                    break
                path = path.rsplit(".", 1)[0]
            return None

        def _settings_wheel_target_canvas(event_widget):
            w = _settings_resolve_wheel_widget(event_widget)
            while w is not None:
                if isinstance(w, tk.Canvas):
                    for _tab_name, data in tab_scroll_state.items():
                        if data.get("canvas") is w:
                            return w
                try:
                    w = w.master
                except (tk.TclError, AttributeError):
                    break
            return None

        def _settings_event_in_window(event_widget, toplevel):
            sw = str(toplevel)
            w = _settings_resolve_wheel_widget(event_widget)
            while w is not None:
                try:
                    wid = str(w)
                except tk.TclError:
                    break
                if wid == sw or wid.startswith(sw + "."):
                    return True
                try:
                    w = w.master
                except (tk.TclError, AttributeError):
                    break
            return False

        def _settings_wheel_on_nested_control(event_widget):
            w = _settings_resolve_wheel_widget(event_widget)
            while w is not None:
                if isinstance(w, (tk.Spinbox, ttk.Spinbox, ttk.Combobox)):
                    return True
                try:
                    w = w.master
                except (tk.TclError, AttributeError):
                    break
            return False

        def _settings_on_mousewheel(event):
            if not _settings_event_in_window(event.widget, settings_window):
                return
            if _settings_wheel_on_nested_control(event.widget):
                return

            canvas = _settings_wheel_target_canvas(event.widget)
            if canvas is None:
                return

            system = platform.system()
            if system == "Linux":
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    return
            else:
                delta = getattr(event, "delta", 0) or 0
                if not delta:
                    return
                if system == "Darwin":
                    steps = int(-delta) if abs(delta) < 100 else int(-delta / 120)
                else:
                    steps = int(-delta / 120)
                if steps:
                    canvas.yview_scroll(steps, "units")

        def _teardown_settings_mousewheel():
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    settings_window.unbind_all(seq)
                except tk.TclError:
                    pass

        settings_window.bind_all("<MouseWheel>", _settings_on_mousewheel)
        if platform.system() == "Linux":
            settings_window.bind_all("<Button-4>", _settings_on_mousewheel)
            settings_window.bind_all("<Button-5>", _settings_on_mousewheel)

        def _on_settings_window_destroy(event):
            destroyed = _settings_resolve_wheel_widget(event.widget)
            if destroyed is not settings_window:
                return
            _teardown_settings_mousewheel()

        settings_window.bind("<Destroy>", _on_settings_window_destroy)

        def create_settings_card(parent, title, subtitle=""):
            outer = tk.Frame(
                parent,
                bg=self.BG_MID,
                highlightbackground=self.BORDER_COLOR,
                highlightthickness=1,
                bd=0,
            )
            outer.pack(fill="x", pady=(0, 10))
            header = tk.Frame(outer, bg=self.BG_MID)
            header.pack(fill="x", padx=10, pady=(8, 0))
            ttk.Label(
                header,
                text=title,
                style="Dark.TLabel",
                font=("Segoe UI", 11, "bold")
            ).pack(anchor="w")
            if subtitle:
                subtitle_label = ttk.Label(
                    header,
                    text=subtitle,
                    style="Dark.TLabel",
                    font=("Segoe UI", 9),
                    foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888"
                )
                subtitle_label.pack(anchor="w", pady=(2, 0))
                settings_muted_labels.append(subtitle_label)
            body = ttk.Frame(outer, style="Dark.TFrame")
            body.pack(fill="x", padx=10, pady=(8, 10))
            settings_cards.append({"outer": outer, "header": header})
            return body

        def _refresh_settings_theme():
            if not settings_window.winfo_exists():
                return

            settings_window.configure(bg=self.BG_DARK)
            tab_bar.configure(bg=self.BG_DARK)
            header_row.configure(bg=self.BG_DARK)
            header_text_frame.configure(bg=self.BG_DARK)

            for tab_name, btn in tab_buttons.items():
                if tab_name == tab_var.get():
                    btn.configure(
                        bg=self.BG_LIGHT,
                        fg=self.FG_TEXT,
                        activebackground=self.BG_LIGHT,
                        activeforeground=self.FG_TEXT,
                    )
                else:
                    btn.configure(
                        bg=self.BG_MID,
                        fg=self.FG_MUTED,
                        activebackground=self.BG_MID,
                        activeforeground=self.FG_TEXT,
                    )

            for card in settings_cards:
                outer = card.get("outer")
                header = card.get("header")
                if outer and outer.winfo_exists():
                    outer.configure(bg=self.BG_MID, highlightbackground=self.BORDER_COLOR, highlightcolor=self.BORDER_COLOR)
                if header and header.winfo_exists():
                    header.configure(bg=self.BG_MID)

            for label in settings_muted_labels:
                if label and label.winfo_exists():
                    label.configure(foreground=self.FG_MUTED)

            for data in tab_scroll_state.values():
                canvas = data.get("canvas")
                if canvas and canvas.winfo_exists():
                    canvas.configure(bg=self.BG_DARK)

        interface_card = create_settings_card(general_tab, "Interface & Notifications", "Behavior and interaction preferences")

        ttk.Checkbutton(
            interface_card,
            text="Enable Topmost",
            variable=topmost_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_topmost", topmost_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            interface_card,
            text="Multi Select (Ctrl + Click)",
            variable=multi_select_var,
            style="Dark.TCheckbutton",
            command=on_multi_select_toggle
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            interface_card,
            text="Disable Success Popups",
            variable=disable_success_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("disable_success_popups", disable_success_var)
        ).pack(anchor="w", pady=2)

        installer_versions_frame = create_settings_card(general_tab, "Installer", "Version list and update visibility")

        installer_versions_row = ttk.Frame(installer_versions_frame, style="Dark.TFrame")
        installer_versions_row.pack(fill="x")

        ttk.Label(
            installer_versions_row,
            text="Previous versions visible",
            style="Dark.TLabel"
        ).pack(side="left")

        installer_versions_after_id = None

        def _apply_installer_previous_versions_setting():
            nonlocal installer_versions_after_id
            installer_versions_after_id = None

            clamped = clamp_installer_previous_versions(installer_previous_versions_var.get())
            if installer_previous_versions_var.get() != clamped:
                installer_previous_versions_var.set(clamped)

            if self.settings.get("installer_previous_versions", MIN_INSTALLER_PREVIOUS_VERSIONS) != clamped:
                self.settings["installer_previous_versions"] = clamped
                self.save_settings()
                self.refresh_installer_menu()

        def on_installer_previous_versions_update(*_):
            nonlocal installer_versions_after_id
            clamped = clamp_installer_previous_versions(installer_previous_versions_var.get())
            if installer_previous_versions_var.get() != clamped:
                installer_previous_versions_var.set(clamped)

            if installer_versions_after_id is not None:
                try:
                    settings_window.after_cancel(installer_versions_after_id)
                except Exception:
                    pass
            installer_versions_after_id = settings_window.after(250, _apply_installer_previous_versions_setting)

        installer_versions_spin = ttk.Spinbox(
            installer_versions_row,
            from_=MIN_INSTALLER_PREVIOUS_VERSIONS,
            to=MAX_INSTALLER_PREVIOUS_VERSIONS,
            increment=1,
            textvariable=installer_previous_versions_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_installer_previous_versions_update
        )
        installer_versions_spin.pack(side="right")
        installer_versions_spin.bind("<FocusOut>", lambda _: on_installer_previous_versions_update())
        installer_versions_spin.bind("<Return>", lambda _: on_installer_previous_versions_update())

        updates_card = create_settings_card(general_tab, "App Updates", "Automatic update checks")

        ttk.Checkbutton(
            updates_card,
            text="Enable Auto Updates",
            variable=auto_update_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("auto_update_enabled", auto_update_var)
        ).pack(anchor="w", pady=2)

        theme_card = create_settings_card(general_tab, "Theme")

        theme_combo = ttk.Combobox(
            theme_card,
            values=list(THEMES.keys()),
            textvariable=theme_var,
            state="readonly",
            style="Dark.TCombobox"
        )
        theme_combo.pack(fill="x", pady=(0, 4))
        theme_combo.set(theme_var.get())

        def on_theme_change(_=None):
            selected_theme = theme_combo.get()
            if not selected_theme:
                return
            theme_var.set(selected_theme)
            self.apply_theme(selected_theme)

        theme_combo.bind("<<ComboboxSelected>>", on_theme_change)

        browser_card = create_settings_card(general_tab, "Browser Automation")
        available_browsers = self._get_available_browsers()
        browser_value_to_label = {}
        if len(available_browsers) >= 2:
            browser_value_to_label["auto"] = "Auto (Chrome first, then Firefox)"
        if "chrome" in available_browsers:
            browser_value_to_label["chrome"] = "Chrome only"
        if "firefox" in available_browsers:
            browser_value_to_label["firefox"] = "Firefox only"
        browser_label_to_value = {label: value for value, label in browser_value_to_label.items()}
        current_browser_pref = browser_preference_var.get()
        if len(available_browsers) == 1:
            current_browser_pref = available_browsers[0]
        elif current_browser_pref not in browser_value_to_label:
            current_browser_pref = "auto" if "auto" in browser_value_to_label else available_browsers[0] if available_browsers else "auto"

        browser_preference_var.set(current_browser_pref)
        self.settings["browser_preference"] = current_browser_pref
        self.save_settings()

        if browser_value_to_label:
            browser_pref_label_var = tk.StringVar(
                value=browser_value_to_label.get(current_browser_pref, next(iter(browser_value_to_label.values())))
            )
            browser_combo = ttk.Combobox(
                browser_card,
                values=list(browser_value_to_label.values()),
                textvariable=browser_pref_label_var,
                state="readonly",
                style="Dark.TCombobox",
            )
            browser_combo.pack(fill="x", pady=(0, 4))

            def on_browser_preference_change(_=None):
                selected_label = (browser_combo.get() or "").strip()
                selected_value = browser_label_to_value.get(selected_label, current_browser_pref)
                browser_preference_var.set(selected_value)
                self.settings["browser_preference"] = selected_value
                self.save_settings()

            browser_combo.bind("<<ComboboxSelected>>", on_browser_preference_change)
        else:
            ttk.Label(
                browser_card,
                text=(
                    "No supported browser detected.\n"
                    "Please download Google Chrome or Mozilla Firefox."
                ),
                style="Dark.TLabel",
                wraplength=340,
                justify="left",
            ).pack(fill="x", pady=(0, 4))

        roblox_client_card = create_settings_card(roblox_tab, "Launch Rules")

        ttk.Checkbutton(
            roblox_client_card,
            text="Confirm Before Launch",
            variable=confirm_launch_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("confirm_before_launch", confirm_launch_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            roblox_client_card,
            text="Enable Multi Roblox",
            variable=multi_roblox_var,
            style="Dark.TCheckbutton",
            command=on_multi_roblox_toggle
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            roblox_client_card,
            text="Randomize Server Job IDs",
            variable=randomize_job_id_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("randomize_server_job_ids", randomize_job_id_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            roblox_client_card,
            text="Prefer Small Servers",
            variable=prefer_small_servers_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("prefer_small_public_servers", prefer_small_servers_var)
        ).pack(anchor="w", pady=2)

        def open_global_settings_and_close_settings():
            """Open Global Settings editor and close settings window"""
            settings_window.destroy()
            self.open_global_settings_editor()

        ttk.Button(
            roblox_client_card,
            text="Open Client Global Settings",
            style="Dark.TButton",
            command=open_global_settings_and_close_settings
        ).pack(fill="x", pady=(8, 0))

        roblox_auto_arrange_card = create_settings_card(roblox_tab, "Roblox Window Arrangement")

        if self._has_multiple_monitors():
            scope_display_map = {
                "primary": "Primary monitor only",
                "secondary": "Secondary monitor only",
                "both": "All monitors"
            }
            scope_inverse_map = {label: value for value, label in scope_display_map.items()}
            selected_label = scope_display_map.get(auto_arrange_scope_var.get(), scope_display_map["both"])

            scope_combo = ttk.Combobox(
                roblox_auto_arrange_card,
                values=list(scope_display_map.values()),
                state="readonly",
                style="Dark.TCombobox"
            )
            scope_combo.pack(fill="x", pady=(0, 4))
            scope_combo.set(selected_label)

            def on_scope_change(_=None):
                label = scope_combo.get()
                value = scope_inverse_map.get(label, "both")
                auto_arrange_scope_var.set(value)
                self.settings["auto_arrange_scope"] = value
                self.save_settings()

            scope_combo.bind("<<ComboboxSelected>>", on_scope_change)
        else:
            self.settings["auto_arrange_scope"] = "primary"
            auto_arrange_scope_var.set("primary")
            ttk.Label(
                roblox_auto_arrange_card,
                text="Only one monitor detected. Auto-arrange will use the available screen.",
                style="Dark.TLabel",
                wraplength=320
            ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            roblox_auto_arrange_card,
            text="Client dimensions",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(6, 2))

        dimension_display_map = {
            "auto": "Auto-fit per monitor",
            "target_size": "Preferred fixed size (shrink if needed)",
        }
        dimension_inverse_map = {label: value for value, label in dimension_display_map.items()}

        dimension_combo = ttk.Combobox(
            roblox_auto_arrange_card,
            values=list(dimension_display_map.values()),
            state="readonly",
            style="Dark.TCombobox"
        )
        dimension_combo.pack(fill="x", pady=(0, 6))
        dimension_combo.set(
            dimension_display_map.get(auto_arrange_dimension_mode_var.get(), dimension_display_map["auto"])
        )

        target_size_frame = ttk.Frame(roblox_auto_arrange_card, style="Dark.TFrame")
        target_size_frame.pack(fill="x", pady=(0, 4))
        target_size_frame.columnconfigure(1, weight=1)
        target_size_frame.columnconfigure(3, weight=1)

        ttk.Label(target_size_frame, text="Width", style="Dark.TLabel").grid(row=0, column=0, sticky="w")
        target_width_spin = ttk.Spinbox(
            target_size_frame,
            from_=50,
            to=7680,
            increment=10,
            textvariable=auto_arrange_target_width_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center"
        )
        target_width_spin.grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Label(target_size_frame, text="Height", style="Dark.TLabel").grid(row=0, column=2, sticky="w")
        target_height_spin = ttk.Spinbox(
            target_size_frame,
            from_=50,
            to=4320,
            increment=10,
            textvariable=auto_arrange_target_height_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center"
        )
        target_height_spin.grid(row=0, column=3, sticky="w", padx=(6, 0))

        def _save_auto_arrange_dimensions():
            mode = auto_arrange_dimension_mode_var.get()
            if mode not in {"auto", "target_size"}:
                mode = "auto"
                auto_arrange_dimension_mode_var.set(mode)

            try:
                target_width = int(auto_arrange_target_width_var.get())
            except (TypeError, ValueError, tk.TclError):
                target_width = int(self.settings.get("auto_arrange_target_width", 800) or 800)
            try:
                target_height = int(auto_arrange_target_height_var.get())
            except (TypeError, ValueError, tk.TclError):
                target_height = int(self.settings.get("auto_arrange_target_height", 600) or 600)

            target_width = max(50, min(7680, target_width))
            target_height = max(50, min(4320, target_height))
            auto_arrange_target_width_var.set(target_width)
            auto_arrange_target_height_var.set(target_height)

            self.settings["auto_arrange_dimension_mode"] = mode
            self.settings["auto_arrange_target_width"] = target_width
            self.settings["auto_arrange_target_height"] = target_height
            self.save_settings()
            _update_target_size_state()

        def _update_target_size_state():
            is_target_size_mode = auto_arrange_dimension_mode_var.get() == "target_size"
            state = "normal" if is_target_size_mode else "disabled"
            target_width_spin.configure(state=state)
            target_height_spin.configure(state=state)

        def on_dimension_mode_change(_=None):
            label = (dimension_combo.get() or "").strip()
            mode = dimension_inverse_map.get(label, "auto")
            auto_arrange_dimension_mode_var.set(mode)
            _save_auto_arrange_dimensions()

        dimension_combo.bind("<<ComboboxSelected>>", on_dimension_mode_change)
        target_width_spin.configure(command=_save_auto_arrange_dimensions)
        target_height_spin.configure(command=_save_auto_arrange_dimensions)
        target_width_spin.bind("<FocusOut>", lambda _evt: _save_auto_arrange_dimensions())
        target_width_spin.bind("<Return>", lambda _evt: _save_auto_arrange_dimensions())
        target_height_spin.bind("<FocusOut>", lambda _evt: _save_auto_arrange_dimensions())
        target_height_spin.bind("<Return>", lambda _evt: _save_auto_arrange_dimensions())
        _update_target_size_state()

        custom_frame = create_settings_card(roblox_tab, "Launch Timing & Executable")

        ttk.Label(
            custom_frame,
            text="Launch Delay (seconds)",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(0, 2))

        delay_var = tk.DoubleVar(value=self._get_multi_launch_delay())

        def on_delay_var_change(*_):
            try:
                value = float(delay_var.get())
            except (tk.TclError, ValueError):
                return
            clamped = clamp_multi_launch_delay(value)
            if not math.isclose(value, clamped):
                delay_var.set(clamped)
                return
            if not math.isclose(self.settings.get("multi_launch_delay", MIN_LAUNCH_DELAY_SECONDS), clamped):
                self.settings["multi_launch_delay"] = clamped
                self.save_settings()

        vcmd = (self.root.register(lambda text: text == "" or re.match(r"^\d*\.?\d*$", text) is not None), "%P")

        delay_spin = ttk.Spinbox(
            custom_frame,
            from_=MIN_LAUNCH_DELAY_SECONDS,
            to=MAX_LAUNCH_DELAY_SECONDS,
            increment=0.5,
            textvariable=delay_var,
            format="%.1f",
            width=8,
            validate="key",
            validatecommand=vcmd,
            style="Dark.TSpinbox",
            justify="center",
            command=on_delay_var_change
        )
        delay_spin.pack(anchor="w")
        delay_spin.bind("<FocusOut>", lambda _: on_delay_var_change())
        delay_spin.bind("<Return>", lambda _: on_delay_var_change())
        delay_var.trace_add("write", on_delay_var_change)

        ttk.Label(
            custom_frame,
            text="Custom Roblox Player",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 2))

        custom_player_frame = ttk.Frame(custom_frame, style="Dark.TFrame")
        custom_player_frame.pack(fill="x", pady=(0, 6))
        custom_player_frame.columnconfigure(0, weight=1)
        custom_player_entry = ttk.Entry(custom_player_frame, style="Dark.TEntry", textvariable=custom_roblox_player_path_var)
        custom_player_entry.grid(row=0, column=0, sticky="ew")

        def save_custom_player_path(value):
            if value is None:
                return
            value = (value or "").strip()
            self.settings["custom_roblox_player_path"] = value
            custom_roblox_player_path_var.set(value)
            self.save_settings()
            if hasattr(self, "version_dropdown") and hasattr(self, "version_var"):
                self.load_roblox_versions()
                if value:
                    self._select_version_by_path(value)

        def browse_custom_player_path():
            path = filedialog.askopenfilename(
                parent=settings_window,
                title="Select RobloxPlayer executable",
                filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
            )
            if not path:
                return
            path = os.path.normpath(path)
            if not os.path.isfile(path):
                messagebox.showerror("Custom RobloxPlayer", "Selected path is not a file.")
                return
            exe_name = os.path.basename(path).lower()
            if exe_name not in self.ROBLOX_CLIENT_EXECUTABLES:
                messagebox.showerror(
                    "Custom RobloxPlayer",
                    "Please select RobloxPlayerBeta.exe or RobloxPlayerLauncher.exe."
                )
                return
            save_custom_player_path(path)

        def clear_custom_player_path():
            save_custom_player_path("")

        ttk.Button(
            custom_player_frame,
            text="Browse",
            style="Dark.TButton",
            command=browse_custom_player_path
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Button(
            custom_player_frame,
            text="Clear",
            style="Dark.TButton",
            command=clear_custom_player_path
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        custom_player_entry.bind("<FocusOut>", lambda _evt: save_custom_player_path(custom_roblox_player_path_var.get()))
        custom_player_entry.bind("<Return>", lambda _evt: save_custom_player_path(custom_roblox_player_path_var.get()))

        auto_relaunch_enabled_var = tk.BooleanVar(value=self.settings.get("auto_relaunch_enabled", False))
        auto_relaunch_interval_var = tk.IntVar(value=self.settings.get("auto_relaunch_interval_minutes", 60))
        auto_relaunch_group_var = tk.StringVar(value=self.settings.get("auto_relaunch_group", ""))
        auto_arrange_after_group_launch_var = tk.BooleanVar(
            value=self.settings.get("auto_arrange_after_group_launch", False)
        )

        def on_auto_relaunch_update(*_):
            try:
                interval = int(auto_relaunch_interval_var.get())
            except (tk.TclError, ValueError):
                interval = 60

            interval = max(1, interval)
            if auto_relaunch_interval_var.get() != interval:
                auto_relaunch_interval_var.set(interval)

            self.settings["auto_relaunch_enabled"] = bool(auto_relaunch_enabled_var.get())
            self.settings["auto_relaunch_interval_minutes"] = int(interval)
            self.settings["auto_relaunch_group"] = (auto_relaunch_group_var.get() or "").strip()
            self.settings["auto_arrange_after_group_launch"] = bool(auto_arrange_after_group_launch_var.get())
            self.save_settings()

            if self.settings.get("auto_relaunch_enabled", False):
                self._auto_relaunch_start()
            else:
                self._auto_relaunch_stop()

        auto_relaunch_card = create_settings_card(automation_tab, "Auto Relaunch")

        ttk.Checkbutton(
            auto_relaunch_card,
            text="Enable Auto Relaunch",
            variable=auto_relaunch_enabled_var,
            style="Dark.TCheckbutton",
            command=on_auto_relaunch_update
        ).pack(anchor="w", pady=2)

        interval_frame = ttk.Frame(auto_relaunch_card, style="Dark.TFrame")
        interval_frame.pack(fill="x", pady=(4, 0))

        ttk.Label(interval_frame, text="Interval (minutes)", style="Dark.TLabel").pack(side="left")

        interval_spin = ttk.Spinbox(
            interval_frame,
            from_=1,
            to=1440,
            increment=1,
            textvariable=auto_relaunch_interval_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_auto_relaunch_update
        )
        interval_spin.pack(side="right")
        interval_spin.bind("<FocusOut>", lambda _: on_auto_relaunch_update())
        interval_spin.bind("<Return>", lambda _: on_auto_relaunch_update())

        groups = [""] + self.manager.get_groups()
        if auto_relaunch_group_var.get() not in groups:
            auto_relaunch_group_var.set("")

        group_frame = ttk.Frame(auto_relaunch_card, style="Dark.TFrame")
        group_frame.pack(fill="x", pady=(6, 0))
        ttk.Label(group_frame, text="Group", style="Dark.TLabel").pack(side="left")

        auto_relaunch_group_combo = ttk.Combobox(
            group_frame,
            values=groups,
            textvariable=auto_relaunch_group_var,
            state="readonly",
            style="Dark.TCombobox",
            width=18
        )
        auto_relaunch_group_combo.pack(side="right", fill="x", expand=True)
        auto_relaunch_group_combo.bind("<<ComboboxSelected>>", lambda _=None: on_auto_relaunch_update())

        ttk.Checkbutton(
            auto_relaunch_card,
            text="Auto Arrange Clients After Group Launch",
            variable=auto_arrange_after_group_launch_var,
            style="Dark.TCheckbutton",
            command=on_auto_relaunch_update
        ).pack(anchor="w", pady=(8, 0))

        ttk.Button(
            auto_relaunch_card,
            text="Run Auto Relaunch",
            style="Dark.TButton",
            command=self._auto_relaunch_run_once
        ).pack(fill="x", pady=(10, 0))

        _auto_trim_win = platform.system() == "Windows"
        auto_memory_trim_enabled_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_memory_trim_enabled", False))
        )
        auto_memory_trim_interval_var = tk.IntVar(
            value=int(self.settings.get("auto_memory_trim_interval_minutes", 5) or 5)
        )

        def on_auto_memory_trim_update(*_):
            if not _auto_trim_win:
                return
            try:
                minutes = int(auto_memory_trim_interval_var.get())
            except (tk.TclError, ValueError):
                minutes = 5
            minutes = max(1, min(120, minutes))
            if auto_memory_trim_interval_var.get() != minutes:
                auto_memory_trim_interval_var.set(minutes)

            self.settings["auto_memory_trim_enabled"] = bool(auto_memory_trim_enabled_var.get())
            self.settings["auto_memory_trim_interval_minutes"] = int(minutes)
            self.save_settings()

            if self._auto_memory_trim_config_valid():
                self._auto_memory_trim_start()
            else:
                self._auto_memory_trim_stop()

        auto_trim_card = create_settings_card(
            automation_tab,
            "Auto Trim Roblox Memory",
            "Automatically trims Roblox's memory on interval",
        )

        auto_trim_ctrl_state = "normal" if _auto_trim_win else "disabled"
        ttk.Checkbutton(
            auto_trim_card,
            text="Enable Auto Trim Memory",
            variable=auto_memory_trim_enabled_var,
            style="Dark.TCheckbutton",
            command=on_auto_memory_trim_update,
            state=auto_trim_ctrl_state,
        ).pack(anchor="w", pady=2)

        auto_trim_interval_frame = ttk.Frame(auto_trim_card, style="Dark.TFrame")
        auto_trim_interval_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(
            auto_trim_interval_frame,
            text="Interval (minutes)",
            style="Dark.TLabel",
        ).pack(side="left")

        auto_trim_interval_spin = ttk.Spinbox(
            auto_trim_interval_frame,
            from_=1,
            to=120,
            increment=1,
            textvariable=auto_memory_trim_interval_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_auto_memory_trim_update,
            state=auto_trim_ctrl_state,
        )
        auto_trim_interval_spin.pack(side="right")
        auto_trim_interval_spin.bind("<FocusOut>", lambda _: on_auto_memory_trim_update())
        auto_trim_interval_spin.bind("<Return>", lambda _: on_auto_memory_trim_update())

        if not _auto_trim_win:
            ttk.Label(
                auto_trim_card,
                text="Windows only.",
                style="Dark.TLabel",
                foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
            ).pack(anchor="w", pady=(6, 0))

        logging_card = create_settings_card(advanced_tab, "Diagnostics")

        ttk.Checkbutton(
            logging_card,
            text="Enable Debug Logging",
            variable=debug_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_debug_logging", debug_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            logging_card,
            text="Hide Sensitive Info",
            variable=hide_sensitive_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("hide_sensitive_info", hide_sensitive_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            logging_card,
            text="Prompt for Bug Reports",
            variable=bug_prompt_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("bug_issue_prompt_enabled", bug_prompt_var)
        ).pack(anchor="w", pady=2)

        def open_instance_manager_and_close_settings():
            settings_window.destroy()
            self.open_instance_manager()

        tools_card = create_settings_card(advanced_tab, "Utilities")

        ttk.Button(
            tools_card,
            text="Instance Manager",
            style="Dark.TButton",
            command=open_instance_manager_and_close_settings
        ).pack(fill="x", pady=(0, 10))

        def open_fastflags_and_close_settings():
            settings_window.destroy()
            self.open_fastflags_editor()

        ttk.Button(
            tools_card,
            text="Fast Flags Editor",
            style="Dark.TButton",
            command=open_fastflags_and_close_settings
        ).pack(fill="x", pady=(0, 0))

        self.register_theme_refresh(settings_window, _refresh_settings_theme)
        set_active_tab("general")
        padding_w = 40
        padding_h = 40
        min_w = 760
        min_h = 620
        req_w = settings_window.winfo_reqwidth() + padding_w
        req_h = settings_window.winfo_reqheight() + padding_h
        final_w = max(req_w, min_w)
        final_h = max(req_h, min_h)
        self._center_window(settings_window, final_w, final_h)
        settings_window.deiconify()

        footer_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        footer_frame.pack(fill="x", pady=(8, 0))
        footer_frame.columnconfigure(0, weight=1)
        footer_frame.columnconfigure(1, weight=1)

        ttk.Button(
            footer_frame,
            text="Open Console",
            style="Dark.TButton",
            command=self.open_console_output
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ttk.Button(
            footer_frame,
            text="Close",
            style="Dark.TButton",
            command=settings_window.destroy
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def open_instance_manager(self):
        if platform.system() != "Windows":
            messagebox.showerror("Instance Manager", "This feature is only available on Windows.")
            return

        if self.instance_manager_window and self.instance_manager_window.winfo_exists():
            self.instance_manager_window.deiconify()
            self.instance_manager_window.lift()
            self.instance_manager_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.instance_manager_window = window
        window.withdraw()
        window.title("Instance Manager")
        window.configure(bg="#060a14")
        window.resizable(True, True)
        window.minsize(980, 560)
        self.register_toplevel(window)

        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        main_frame = tk.Frame(window, bg="#060a14")
        main_frame.pack(fill="both", expand=True, padx=18, pady=14)

        header_frame = tk.Frame(main_frame, bg="#060a14")
        header_frame.pack(fill="x", pady=(0, 8))
        tk.Label(
            header_frame,
            text="Instance Manager",
            bg="#060a14",
            fg="#f3f7ff",
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        tk.Label(
            header_frame,
            text="Monitor and control your Roblox instances",
            bg="#060a14",
            fg="#8ea2c8",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        card_running_var = tk.StringVar(value="0")
        card_not_responding_var = tk.StringVar(value="0")
        card_closed_var = tk.StringVar(value="0")

        def create_metric_card(parent, title, value_var, border_color, value_color):
            card = tk.Frame(
                parent,
                bg="#0a1222",
                highlightthickness=1,
                highlightbackground=border_color,
                highlightcolor=border_color,
                bd=0,
            )
            tk.Label(
                card,
                text=title,
                bg="#0a1222",
                fg="#9fb2d5",
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w", padx=14, pady=(14, 4))
            tk.Label(
                card,
                textvariable=value_var,
                bg="#0a1222",
                fg=value_color,
                font=("Segoe UI Semibold", 20),
            ).pack(anchor="w", padx=14, pady=(0, 12))
            return card

        cards_frame = tk.Frame(main_frame, bg="#060a14")
        cards_frame.pack(fill="x", pady=(4, 10))
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)
        cards_frame.grid_columnconfigure(2, weight=1)
        create_metric_card(cards_frame, "Running", card_running_var, "#1f7f66", "#3ee8ab").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        create_metric_card(cards_frame, "Not Responding", card_not_responding_var, "#9a6f1d", "#ffc34d").grid(row=0, column=1, sticky="ew", padx=(4, 4))
        create_metric_card(cards_frame, "Closed", card_closed_var, "#8c2c42", "#ff6f8d").grid(row=0, column=2, sticky="ew", padx=(8, 0))

        toolbar_frame = tk.Frame(main_frame, bg="#060a14")
        toolbar_frame.pack(fill="x", pady=(2, 8))
        button_frame = ttk.Frame(toolbar_frame, style="Dark.TFrame")
        button_frame.pack(side="left")

        loaded_count_var = tk.StringVar(value="0 instances loaded")
        tk.Label(
            toolbar_frame,
            textvariable=loaded_count_var,
            bg="#060a14",
            fg="#8ea2c8",
            font=("Consolas", 10),
        ).pack(side="right", padx=(12, 0))

        controls_frame = tk.Frame(main_frame, bg="#060a14")
        controls_frame.pack(fill="x", pady=(0, 10))
        controls_frame.grid_columnconfigure(1, weight=1)

        tk.Label(controls_frame, text="Filter", bg="#060a14", fg="#8ea2c8", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        filter_var = tk.StringVar()
        filter_entry = ttk.Entry(controls_frame, textvariable=filter_var, style="Dark.TEntry")
        filter_entry.grid(row=0, column=1, sticky="ew")

        tk.Label(controls_frame, text="Status", bg="#060a14", fg="#8ea2c8", font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(10, 4))
        status_filter_var = tk.StringVar(value="All")
        status_filter_combo = ttk.Combobox(
            controls_frame,
            textvariable=status_filter_var,
            values=("All", "Running", "Not Responding", "Closed"),
            state="readonly",
            style="Dark.TCombobox",
            width=16,
        )
        status_filter_combo.grid(row=0, column=3, sticky="w")

        known_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Known Accounts",
            variable=known_only_var,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=4, sticky="w", padx=(10, 0))

        auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls_frame,
            text="Auto Refresh",
            variable=auto_refresh_var,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=5, sticky="w", padx=(10, 0))

        tk.Label(controls_frame, text="Every (s)", bg="#060a14", fg="#8ea2c8", font=("Segoe UI", 9)).grid(row=0, column=6, sticky="w", padx=(8, 4))
        refresh_interval_var = tk.IntVar(value=5)
        refresh_interval_spin = ttk.Spinbox(
            controls_frame,
            from_=1,
            to=30,
            increment=1,
            textvariable=refresh_interval_var,
            width=4,
            style="Dark.TSpinbox",
            justify="center",
        )
        refresh_interval_spin.grid(row=0, column=7, sticky="w")

        self.style.configure(
            "Instance.Treeview",
            background="#0a1020",
            fieldbackground="#0a1020",
            foreground="#e7efff",
            borderwidth=0,
            rowheight=38,
            font=("Consolas", 10),
        )
        self.style.map(
            "Instance.Treeview",
            background=[("selected", "#18213d")],
            foreground=[("selected", "#f8fbff")],
        )
        self.style.configure(
            "Instance.Treeview.Heading",
            background="#121a2d",
            foreground="#8ea2c8",
            borderwidth=0,
            relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        self.style.map(
            "Instance.Treeview.Heading",
            background=[("active", "#1a2642")],
            foreground=[("active", "#b6c7e9")],
        )

        list_frame = tk.Frame(
            main_frame,
            bg="#0a1020",
            highlightthickness=1,
            highlightbackground="#1a2642",
            highlightcolor="#1a2642",
            bd=0,
        )
        list_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            list_frame,
            columns=("pid", "status", "exe", "account", "game", "uptime"),
            show="headings",
            height=14,
            selectmode="extended",
            style="Instance.Treeview",
        )
        tree.heading("pid", text="PID", anchor="w")
        tree.heading("status", text="Status", anchor="w")
        tree.heading("exe", text="Executable", anchor="w")
        tree.heading("account", text="Account", anchor="w")
        tree.heading("game", text="Game", anchor="w")
        tree.heading("uptime", text="Uptime", anchor="w")
        tree.column("pid", width=110, anchor="w")
        tree.column("status", width=160, anchor="w")
        tree.column("exe", width=320, anchor="w")
        tree.column("account", width=180, anchor="w")
        tree.column("game", width=300, anchor="w")
        tree.column("uptime", width=130, anchor="w")
        tree.pack(side="left", fill="both", expand=True)

        tree.tag_configure("state_running", foreground="#3ee8ab")
        tree.tag_configure("state_not_responding", foreground="#ffc34d")
        tree.tag_configure("state_closed", foreground="#ff6f8d")

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        list_scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=list_scroll.set)

        self.style.configure(
            "InstanceAction.TButton",
            background="#121a2d",
            foreground="#d7e6ff",
            font=("Segoe UI Semibold", 9),
            padding=6,
        )
        self.style.map(
            "InstanceAction.TButton",
            background=[("active", "#1a2642")],
            foreground=[("active", "#f3f8ff")],
        )
        self.style.configure(
            "InstanceDanger.TButton",
            background="#2a1220",
            foreground="#ff7b92",
            font=("Segoe UI Semibold", 9),
            padding=6,
        )
        self.style.map(
            "InstanceDanger.TButton",
            background=[("active", "#341628")],
            foreground=[("active", "#ffa6b5")],
        )

        state = {
            "pid_to_hwnd": {},
            "pid_to_account": {},
            "pid_to_running": {},
            "pid_to_launch_context": {},
            "rows": [],
            "game_name_cache": {},
            "game_name_pending": set(),
            "first_seen": {},
            "closed_since": {},
            "instance_store": {},
            "render_static_by_pid": {},
            "render_order": [],
            "sort_column": "pid",
            "sort_desc": False,
            "refresh_in_progress": False,
            "refresh_pending": False,
            "auto_refresh_after_id": None,
            "closing": False,
            "refresh_seq": 0,
            "active_refresh_id": 0,
            "refresh_started_at": 0.0,
            "sync_refresh_interval": False,
            "last_schedule_log_at": 0.0,
        }
        max_instance_history = 500
        instance_debug = bool(self.settings.get("enable_debug_logging", False))
        snapshot_warn_seconds = 1.5
        refresh_watchdog_seconds = 20.0

        target_exes = set(getattr(self, "_tracked_roblox_exes", set()) or {
            "robloxplayerbeta.exe",
            "robloxstudiobeta.exe",
            "robloxplayerlauncher.exe",
            "robloxstudiolauncherbeta.exe",
        })

        def im_log(message, force=False):
            if force or instance_debug:
                print(f"[IM] {message}")

        im_log(
            f"Window opened. auto_refresh={auto_refresh_var.get()} interval={refresh_interval_var.get()}s "
            f"tracked_exes={sorted(target_exes)}",
        )

        def format_uptime(seconds_value):
            try:
                total = max(0, int(seconds_value))
            except Exception:
                total = 0
            hours, rem = divmod(total, 3600)
            minutes, secs = divmod(rem, 60)
            if hours > 0:
                return f"{hours}h {minutes:02d}m"
            if minutes > 0:
                return f"{minutes}m {secs:02d}s"
            return f"{secs}s"

        def extract_account_from_title(title_text: str):
            if not title_text:
                return ""
            candidates = []
            for match in re.finditer(r"([A-Za-z0-9_]{3,})@", title_text):
                candidates.append(match.group(1))
            for match in re.finditer(r"@([A-Za-z0-9_]{3,})", title_text):
                candidates.append(match.group(1))
            if not candidates:
                return ""
            accounts = getattr(self.manager, "accounts", {})
            if isinstance(accounts, dict):
                account_lookup = {str(k).lower(): str(k) for k in accounts.keys()}
                for candidate in candidates:
                    resolved = account_lookup.get(candidate.lower())
                    if resolved:
                        return resolved
            return candidates[0]

        def get_selected_pids():
            selected = []
            for item in tree.selection():
                try:
                    selected.append(int(item))
                except Exception:
                    continue
            return selected

        def is_window_not_responding(hwnd):
            try:
                user32 = ctypes.windll.user32
                return bool(user32.IsHungAppWindow(int(hwnd)))
            except Exception:
                return False

        def prune_instance_history():
            store = state["instance_store"]
            if len(store) <= max_instance_history:
                return

            running_pids = {
                pid_value
                for pid_value, record in store.items()
                if bool((record or {}).get("running", False))
            }
            removable_closed = [pid_value for pid_value in list(store.keys()) if pid_value not in running_pids]
            removable_closed.sort(key=lambda pid_value: float(state["closed_since"].get(pid_value, 0)))

            overflow = len(store) - max_instance_history
            removed_pids = []
            for pid_value in removable_closed:
                if overflow <= 0:
                    break
                store.pop(pid_value, None)
                state["closed_since"].pop(pid_value, None)
                state["first_seen"].pop(pid_value, None)
                removed_pids.append(int(pid_value))
                overflow -= 1

            if removed_pids:
                try:
                    with self._pid_account_lock:
                        for pid_value in removed_pids:
                            self._pid_account_map.pop(int(pid_value), None)
                            self._pid_launch_context_map.pop(int(pid_value), None)
                except Exception:
                    pass

        def format_status_display(status_text):
            normalized = str(status_text or "").strip().lower()
            if normalized == "running":
                return "* Running", "state_running"
            if normalized == "not responding":
                return "* Not Responding", "state_not_responding"
            return "* Closed", "state_closed"

        def _resolve_game_name_async(place_id):
            place_text = str(place_id or "").strip()
            if not place_text.isdigit():
                return
            if place_text in state["game_name_cache"]:
                return
            if place_text in state["game_name_pending"]:
                return
            state["game_name_pending"].add(place_text)

            def worker():
                resolved_name = ""
                try:
                    resolved_name = RobloxAPI.get_game_name(place_text) or ""
                except Exception:
                    resolved_name = ""
                if not resolved_name:
                    resolved_name = f"Place {place_text}"

                def apply():
                    state["game_name_pending"].discard(place_text)
                    state["game_name_cache"][place_text] = resolved_name
                    apply_rows_to_tree()

                self.root.after(0, apply)

            threading.Thread(target=worker, daemon=True).start()

        def get_game_display_for_row(row):
            context = self._normalize_launch_context(row.get("launch_context"))
            mode = context.get("mode", "home")
            place_id = str(context.get("game_id", "") or "").strip()

            if mode == "game" and place_id.isdigit():
                cached_name = state["game_name_cache"].get(place_id)
                if cached_name:
                    return cached_name
                _resolve_game_name_async(place_id)
                return f"Place {place_id}"
            if mode == "join_user":
                return f"Join User {place_id}" if place_id else "Join User"
            if mode == "home":
                return "Home"
            return "-"

        def apply_rows_to_tree():
            rows = list(state.get("rows", []))
            filter_text = (filter_var.get() or "").strip().lower()
            known_only = bool(known_only_var.get())
            status_filter_value = (status_filter_var.get() or "All").strip().lower()

            if known_only:
                rows = [row for row in rows if (row.get("account") or "").strip()]

            if status_filter_value and status_filter_value != "all":
                rows = [
                    row for row in rows
                    if str(row.get("status", "")).strip().lower() == status_filter_value
                ]

            if filter_text:
                filtered_rows = []
                for row in rows:
                    game_value = get_game_display_for_row(row)
                    haystack = " ".join([
                        str(row.get("pid", "")),
                        str(row.get("status", "")),
                        str(row.get("image", "")),
                        str(row.get("account", "")),
                        str(game_value),
                        str(row.get("title", "")),
                    ]).lower()
                    if filter_text in haystack:
                        filtered_rows.append(row)
                rows = filtered_rows

            sort_column = state.get("sort_column", "pid")
            sort_desc = bool(state.get("sort_desc", False))

            def sort_key(row):
                if sort_column == "pid":
                    return int(row.get("pid", 0))
                if sort_column == "uptime":
                    return int(row.get("uptime_seconds", 0))
                if sort_column == "status":
                    return str(row.get("status", "")).lower()
                if sort_column == "account":
                    return str(row.get("account", "")).lower()
                if sort_column == "game":
                    return str(get_game_display_for_row(row)).lower()
                if sort_column == "exe":
                    return str(row.get("image", "")).lower()
                return str(row.get("title", "")).lower()

            try:
                rows.sort(key=sort_key, reverse=sort_desc)
            except Exception:
                pass

            selected_before = set(get_selected_pids())
            new_pid_to_hwnd = {}
            new_pid_to_account = {}
            new_pid_to_running = {}
            new_pid_to_launch_context = {}
            desired_order = []
            desired_static_by_pid = {}
            desired_uptime_by_pid = {}

            for row in rows:
                pid_value = int(row.get("pid", 0))
                if pid_value <= 0:
                    continue

                iid = str(pid_value)
                status_value = row.get("status", "")
                status_display, status_tag = format_status_display(status_value)
                image_value = row.get("image", "")
                account_value = row.get("account", "") or ""
                game_value = get_game_display_for_row(row)
                uptime_value = format_uptime(row.get("uptime_seconds", 0))
                pid_display = f"# {pid_value}"

                new_pid_to_hwnd[pid_value] = row.get("hwnd")
                new_pid_to_account[pid_value] = account_value
                new_pid_to_running[pid_value] = bool(row.get("running", False))
                new_pid_to_launch_context[pid_value] = self._normalize_launch_context(row.get("launch_context"))

                desired_order.append(iid)
                desired_static_by_pid[iid] = (pid_display, status_display, image_value, account_value, game_value, status_tag)
                desired_uptime_by_pid[iid] = uptime_value

            existing_order = list(tree.get_children())
            desired_set = set(desired_order)

            # Remove stale rows only.
            for iid in existing_order:
                if iid in desired_set:
                    continue
                try:
                    tree.delete(iid)
                except Exception:
                    pass

            # Insert missing rows.
            for iid in desired_order:
                if tree.exists(iid):
                    continue
                static_values = desired_static_by_pid[iid]
                uptime_value = desired_uptime_by_pid[iid]
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(static_values[0], static_values[1], static_values[2], static_values[3], static_values[4], uptime_value),
                    tags=(static_values[5],),
                )

            # Reorder only when needed.
            current_order = list(tree.get_children())
            if current_order != desired_order:
                for idx, iid in enumerate(desired_order):
                    try:
                        tree.move(iid, "", idx)
                    except Exception:
                        continue

            # Update changed rows in place.
            previous_static = state.get("render_static_by_pid", {})
            for iid in desired_order:
                static_values = desired_static_by_pid[iid]
                uptime_value = desired_uptime_by_pid[iid]
                if previous_static.get(iid) != static_values:
                    try:
                        tree.item(
                            iid,
                            values=(static_values[0], static_values[1], static_values[2], static_values[3], static_values[4], uptime_value),
                            tags=(static_values[5],),
                        )
                    except Exception:
                        pass
                    continue
                try:
                    if tree.set(iid, "uptime") != uptime_value:
                        tree.set(iid, "uptime", uptime_value)
                except Exception:
                    pass

            state["pid_to_hwnd"] = new_pid_to_hwnd
            state["pid_to_account"] = new_pid_to_account
            state["pid_to_running"] = new_pid_to_running
            state["pid_to_launch_context"] = new_pid_to_launch_context
            state["render_static_by_pid"] = desired_static_by_pid
            state["render_order"] = desired_order

            reselected = 0
            for pid_value in sorted(selected_before):
                iid = str(pid_value)
                if tree.exists(iid):
                    tree.selection_add(iid)
                    reselected += 1

            total = len(state.get("rows", []))
            shown = len(rows)
            running_count = sum(1 for r in state.get("rows", []) if str(r.get("status", "")).lower() == "running")
            not_resp_count = sum(1 for r in state.get("rows", []) if str(r.get("status", "")).lower() == "not responding")
            closed_count = sum(1 for r in state.get("rows", []) if str(r.get("status", "")).lower() == "closed")
            card_running_var.set(str(running_count))
            card_not_responding_var.set(str(not_resp_count))
            card_closed_var.set(str(closed_count))
            loaded_count_var.set(f"{total} instances loaded")

        def build_snapshot():
            started = time.perf_counter()
            pid_to_image = self._query_tasklist_pid_map(target_exes)
            pid_to_hwnd = {}
            pid_to_titles = {}
            pid_to_hung = {}

            def enum_handler(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                    return True
                try:
                    _, pid_value = win32process.GetWindowThreadProcessId(hwnd)
                except Exception:
                    return True

                image = pid_to_image.get(pid_value)
                exe_name = str(image).lower() if image else ""
                if exe_name not in target_exes:
                    return True

                title_text = ""
                try:
                    title_text = win32gui.GetWindowText(hwnd) or ""
                except Exception:
                    title_text = ""

                pid_to_hwnd.setdefault(pid_value, hwnd)
                if title_text.strip():
                    pid_to_titles.setdefault(pid_value, []).append(title_text.strip())
                if is_window_not_responding(hwnd):
                    pid_to_hung[pid_value] = True
                return True

            try:
                win32gui.EnumWindows(enum_handler, None)
            except Exception:
                pass

            now = time.time()
            running_pids = set(pid_to_image.keys())

            for pid_value in running_pids:
                image = pid_to_image.get(pid_value) or ""
                titles = pid_to_titles.get(pid_value) or []
                title_text = titles[0] if titles else ""
                is_not_responding = bool(pid_to_hung.get(pid_value))
                mapped_account = ""
                mapped_launch_context = None
                try:
                    with self._pid_account_lock:
                        mapped_account = self._pid_account_map.get(int(pid_value), "")
                        mapped_launch_context = self._pid_launch_context_map.get(int(pid_value))
                except Exception:
                    mapped_account = ""
                    mapped_launch_context = None

                account = mapped_account or extract_account_from_title(title_text)
                first_seen = state["first_seen"].setdefault(pid_value, now)
                state["closed_since"].pop(pid_value, None)
                state["instance_store"][pid_value] = {
                    "pid": pid_value,
                    "image": image,
                    "account": account,
                    "title": title_text,
                    "hwnd": pid_to_hwnd.get(pid_value),
                    "uptime_seconds": max(0, int(now - first_seen)),
                    "status": "Not Responding" if is_not_responding else "Running",
                    "running": True,
                    "launch_context": self._normalize_launch_context(mapped_launch_context),
                }

            stored_pids = set(state["instance_store"].keys())
            for pid_value in (stored_pids - running_pids):
                record = state["instance_store"].get(pid_value) or {}
                closed_since = state["closed_since"].setdefault(pid_value, now)
                first_seen = state["first_seen"].get(pid_value, closed_since)
                frozen_uptime = max(0, int(closed_since - first_seen))
                record["pid"] = pid_value
                record["running"] = False
                record["status"] = "Closed"
                record["hwnd"] = None
                record["uptime_seconds"] = max(
                    frozen_uptime,
                    int(record.get("uptime_seconds", 0) or 0)
                )
                state["instance_store"][pid_value] = record

            prune_instance_history()

            rows = []
            for pid_value in sorted(state["instance_store"].keys()):
                record = state["instance_store"].get(pid_value) or {}
                rows.append({
                    "pid": pid_value,
                    "image": record.get("image", "") or "",
                    "account": record.get("account", "") or "",
                    "title": record.get("title", "") or "",
                    "hwnd": record.get("hwnd"),
                    "uptime_seconds": int(record.get("uptime_seconds", 0) or 0),
                    "status": record.get("status", "Closed") or "Closed",
                    "running": bool(record.get("running", False)),
                    "launch_context": self._normalize_launch_context(record.get("launch_context")),
                })
            elapsed = time.perf_counter() - started
            if elapsed >= snapshot_warn_seconds:
                im_log(
                    f"Slow snapshot: {elapsed:.3f}s | running={len(running_pids)} "
                    f"stored={len(state['instance_store'])} rows={len(rows)}",
                    force=True,
                )
            else:
                im_log(
                    f"Snapshot: {elapsed:.3f}s | running={len(running_pids)} "
                    f"stored={len(state['instance_store'])} rows={len(rows)}"
                )
            return rows

        def refresh_instances(from_auto=False):
            if state["closing"]:
                im_log("Refresh skipped: window closing")
                return None
            if state["refresh_in_progress"]:
                elapsed = 0.0
                try:
                    elapsed = max(0.0, time.perf_counter() - float(state.get("refresh_started_at", 0.0)))
                except Exception:
                    elapsed = 0.0
                if elapsed > refresh_watchdog_seconds:
                    im_log(
                        f"Refresh watchdog tripped after {elapsed:.1f}s; clearing stuck refresh gate",
                        force=True,
                    )
                    state["refresh_in_progress"] = False
                    state["refresh_pending"] = False
                else:
                    if not from_auto:
                        state["refresh_pending"] = True
                        im_log("Refresh deferred: refresh already in progress, pending=True")
                    else:
                        im_log("Auto refresh tick skipped: refresh already in progress")
                    return
            state["refresh_in_progress"] = True
            state["refresh_started_at"] = time.perf_counter()
            state["refresh_seq"] = int(state.get("refresh_seq", 0)) + 1
            refresh_id = state["refresh_seq"]
            state["active_refresh_id"] = refresh_id
            refresh_started = time.perf_counter()
            trigger = "auto" if from_auto else "manual"
            im_log(f"Refresh #{refresh_id} started ({trigger})")

            def worker():
                rows = []
                try:
                    rows = build_snapshot()
                except Exception as exc:
                    im_log(f"Refresh #{refresh_id} worker error: {exc}", force=True)
                    rows = []

                def apply():
                    if int(state.get("active_refresh_id", 0)) != int(refresh_id):
                        im_log(f"Refresh #{refresh_id} apply dropped (stale refresh)")
                        return
                    state["refresh_in_progress"] = False
                    if state["closing"]:
                        im_log(f"Refresh #{refresh_id} apply skipped: window closing")
                        return
                    state["rows"] = rows
                    apply_rows_to_tree()
                    elapsed = time.perf_counter() - refresh_started
                    im_log(f"Refresh #{refresh_id} applied in {elapsed:.3f}s | rows={len(rows)}")
                    if state["refresh_pending"]:
                        state["refresh_pending"] = False
                        im_log(f"Refresh #{refresh_id} draining pending refresh")
                        refresh_instances(from_auto=from_auto)
                    elif from_auto:
                        im_log(f"Refresh #{refresh_id} scheduling next auto refresh")
                        schedule_auto_refresh()

                self.root.after(0, apply)

            threading.Thread(target=worker, daemon=True).start()

        def schedule_auto_refresh():
            after_id = state.get("auto_refresh_after_id")
            if after_id is not None:
                try:
                    window.after_cancel(after_id)
                except Exception:
                    pass
                state["auto_refresh_after_id"] = None

            if state["closing"] or not auto_refresh_var.get():
                im_log("Auto refresh not scheduled (disabled or closing)")
                return
            try:
                interval = int(refresh_interval_var.get())
            except Exception:
                interval = 5
            interval = max(1, min(30, interval))
            try:
                current_interval = int(refresh_interval_var.get())
            except Exception:
                current_interval = interval
            if current_interval != interval:
                state["sync_refresh_interval"] = True
                try:
                    refresh_interval_var.set(interval)
                finally:
                    state["sync_refresh_interval"] = False

            state["auto_refresh_after_id"] = window.after(interval * 1000, _auto_refresh_tick)
            now = time.perf_counter()
            if (now - float(state.get("last_schedule_log_at", 0.0))) >= 2.0:
                state["last_schedule_log_at"] = now
                im_log(f"Auto refresh scheduled in {interval}s")

        def _auto_refresh_tick():
            state["auto_refresh_after_id"] = None
            if state["closing"] or not auto_refresh_var.get():
                im_log("Auto refresh tick ignored (disabled or closing)")
                return
            try:
                if str(window.state()) == "iconic":
                    im_log("Auto refresh tick skipped: window minimized")
                    schedule_auto_refresh()
                    return
            except Exception:
                pass
            if state["refresh_in_progress"]:
                im_log("Auto refresh tick found in-progress refresh; rescheduling")
                schedule_auto_refresh()
                return
            im_log("Auto refresh tick -> refresh start")
            refresh_instances(from_auto=True)

        def on_sort(column_name):
            if state.get("sort_column") == column_name:
                state["sort_desc"] = not bool(state.get("sort_desc", False))
            else:
                state["sort_column"] = column_name
                state["sort_desc"] = False
            apply_rows_to_tree()

        tree.heading("pid", text="PID", anchor="w", command=lambda: on_sort("pid"))
        tree.heading("status", text="Status", anchor="w", command=lambda: on_sort("status"))
        tree.heading("exe", text="Executable", anchor="w", command=lambda: on_sort("exe"))
        tree.heading("account", text="Account", anchor="w", command=lambda: on_sort("account"))
        tree.heading("game", text="Game", anchor="w", command=lambda: on_sort("game"))
        tree.heading("uptime", text="Uptime", anchor="w", command=lambda: on_sort("uptime"))

        def focus_selected():
            selected = get_selected_pids()
            if not selected:
                return
            target_pid = None
            for pid_value in selected:
                if state["pid_to_running"].get(pid_value):
                    target_pid = pid_value
                    break
            if target_pid is None:
                return
            hwnd = state["pid_to_hwnd"].get(target_pid)
            if not hwnd:
                return
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            except Exception:
                pass

        def remove_rows_for_pids(pid_values, reason=""):
            pid_set = set()
            for pid_value in (pid_values or []):
                try:
                    pid_int = int(pid_value)
                except Exception:
                    continue
                if pid_int > 0:
                    pid_set.add(pid_int)
            if not pid_set:
                return

            for pid_value in list(pid_set):
                state["instance_store"].pop(pid_value, None)
                state["closed_since"].pop(pid_value, None)
                state["first_seen"].pop(pid_value, None)
                state["pid_to_hwnd"].pop(pid_value, None)
                state["pid_to_account"].pop(pid_value, None)
                state["pid_to_running"].pop(pid_value, None)
                state["pid_to_launch_context"].pop(pid_value, None)
            try:
                with self._pid_account_lock:
                    for pid_value in list(pid_set):
                        self._pid_account_map.pop(int(pid_value), None)
                        self._pid_launch_context_map.pop(int(pid_value), None)
            except Exception:
                pass

            state["rows"] = [
                row for row in state.get("rows", [])
                if int(row.get("pid", 0) or 0) not in pid_set
            ]
            if reason:
                im_log(f"Removed rows ({reason}): {sorted(pid_set)}")
            else:
                im_log(f"Removed rows: {sorted(pid_set)}")
            apply_rows_to_tree()

        def close_selected():
            selected = get_selected_pids()
            if not selected:
                im_log("Close requested with no selection")
                return
            running_selected = [pid for pid in selected if state["pid_to_running"].get(pid)]
            if not running_selected:
                im_log(f"Close requested for non-running selection: {selected}")
                messagebox.showinfo("Close Instance", "No running instances selected.")
                return
            if len(running_selected) == 1:
                prompt = f"Close Roblox instance PID {running_selected[0]}?"
            else:
                prompt = f"Close {len(running_selected)} Roblox instances?"
            confirm = messagebox.askyesno("Close Instance", prompt)
            if not confirm:
                return

            remove_rows_for_pids(running_selected, reason="close")

            def worker(pid_values):
                im_log(f"Close worker started for PIDs: {pid_values}")
                for pid_value in pid_values:
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(pid_value), "/T", "/F"],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            timeout=12,
                            **subprocess_no_window_kwargs(),
                        )
                        im_log(f"Close worker taskkill ok PID={pid_value}")
                    except Exception:
                        im_log(f"Close worker taskkill failed PID={pid_value}", force=True)
                        continue
                self.root.after(0, refresh_instances)

            threading.Thread(target=worker, args=(list(running_selected),), daemon=True).start()

        def relaunch_selected():
            selected = get_selected_pids()
            if not selected:
                im_log("Relaunch requested with no selection")
                return
            pairs = []
            for pid_value in selected:
                account = state["pid_to_account"].get(pid_value) or ""
                if account:
                    is_running = bool(state["pid_to_running"].get(pid_value))
                    launch_context = self._normalize_launch_context(
                        state.get("pid_to_launch_context", {}).get(pid_value)
                    )
                    pairs.append((pid_value, account, is_running, launch_context))

            if not pairs:
                im_log(f"Relaunch requested but no account mapping for selection: {selected}", force=True)
                messagebox.showerror("Relaunch", "Unable to detect an account for this instance.")
                return

            # If the user relaunches a closed row, remove it immediately from the list.
            closed_pids = [pid_value for (pid_value, _account, is_running, _ctx) in pairs if not is_running]
            if closed_pids:
                remove_rows_for_pids(closed_pids, reason="relaunch-closed")

            debug_enabled = self.settings.get("enable_debug_logging", False)
            selected_version_label = self.version_var.get() if hasattr(self, "version_var") else ""
            version_path = self.version_options.get(selected_version_label) if hasattr(self, "version_options") else None

            def worker():
                im_log(f"Relaunch worker started for pairs: {pairs}")
                delay_seconds = self._get_multi_launch_delay()
                for idx, (pid_value, account, was_running, launch_context) in enumerate(pairs):
                    before_pids = self._get_running_tracked_roblox_pid_set()
                    context = self._normalize_launch_context(launch_context)
                    context_mode = context.get("mode", "home")
                    target_version = context.get("version_path") or version_path or None

                    if was_running:
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", str(pid_value), "/T", "/F"],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                timeout=12,
                                **subprocess_no_window_kwargs(),
                            )
                            im_log(f"Relaunch worker closed running PID={pid_value} account={account}")
                        except Exception:
                            im_log(f"Relaunch worker failed to close PID={pid_value}", force=True)

                    launched = False
                    try:
                        context_game_id = str(context.get("game_id") or "").strip()
                        if context_mode in {"game", "join_user"} and context_game_id:
                            launched = bool(
                                self.manager.launch_roblox(
                                    account,
                                    context_game_id,
                                    str(context.get("private_server_id") or "").strip(),
                                    target_version,
                                    enable_debug=debug_enabled,
                                    server_job_id=str(context.get("server_job_id") or "").strip(),
                                    launch_mode=context_mode,
                                )
                            )
                        else:
                            launched = bool(
                                self.manager.launch_home_app(
                                    account,
                                    version=target_version,
                                    enable_debug=debug_enabled,
                                )
                            )
                        if launched:
                            im_log(
                                f"Relaunch worker launch requested for account={account} "
                                f"mode={context_mode} game_id={context.get('game_id', '')}"
                            )
                        else:
                            im_log(f"Relaunch worker launch returned False for account={account}", force=True)
                    except Exception:
                        im_log(f"Relaunch worker launch failed for account={account}", force=True)

                    try:
                        time.sleep(0.8)
                        after_pids = self._get_running_tracked_roblox_pid_set()
                        if not (set(after_pids) - set(before_pids)):
                            time.sleep(1.0)
                            after_pids = self._get_running_tracked_roblox_pid_set()
                        self._assign_new_pids_to_account(
                            account,
                            before_pids,
                            after_pids,
                            launch_context=context,
                        )
                        if launched:
                            new_pids = sorted(set(after_pids) - set(before_pids))
                            im_log(f"Relaunch worker mapped account={account} to new_pids={new_pids}")
                    except Exception:
                        im_log(f"Relaunch worker PID/account mapping failed for account={account}", force=True)

                    if delay_seconds > 0 and idx < len(pairs) - 1:
                        time.sleep(delay_seconds)
                self.root.after(0, refresh_instances)

            threading.Thread(target=worker, daemon=True).start()

        def copy_account():
            selected = get_selected_pids()
            if not selected:
                return
            accounts = []
            for pid_value in selected:
                account = (state["pid_to_account"].get(pid_value) or "").strip()
                if account:
                    accounts.append(account)
            if not accounts:
                return
            seen = set()
            unique_accounts = []
            for account in accounts:
                if account in seen:
                    continue
                seen.add(account)
                unique_accounts.append(account)
            try:
                window.clipboard_clear()
                window.clipboard_append("\n".join(unique_accounts))
                window.update_idletasks()
            except Exception:
                pass

        def copy_password():
            selected = get_selected_pids()
            if not selected:
                return
            passwords = []
            for pid_value in selected:
                account = (state["pid_to_account"].get(pid_value) or "").strip()
                if not account:
                    continue
                account_data = self.manager.accounts.get(account)
                if isinstance(account_data, dict):
                    password_value = str(account_data.get("password", "") or "").strip()
                else:
                    password_value = ""
                if password_value:
                    passwords.append(password_value)
            if not passwords:
                messagebox.showinfo("Copy Password", "No password found for the selected instance(s).")
                return
            seen = set()
            unique_passwords = []
            for password_value in passwords:
                if password_value in seen:
                    continue
                seen.add(password_value)
                unique_passwords.append(password_value)
            try:
                window.clipboard_clear()
                window.clipboard_append("\n".join(unique_passwords))
                window.update_idletasks()
            except Exception:
                pass

        def update_selection_status():
            return

        def on_filter_change(*_args):
            apply_rows_to_tree()

        def on_tree_select(_evt=None):
            update_selection_status()

        def on_auto_refresh_toggle(*_args):
            im_log(f"Auto refresh toggled -> {bool(auto_refresh_var.get())}")
            schedule_auto_refresh()

        def on_refresh_interval_change(*_args):
            if state.get("sync_refresh_interval"):
                return
            try:
                new_interval = int(refresh_interval_var.get())
            except Exception:
                new_interval = refresh_interval_var.get()
            im_log(f"Refresh interval changed -> {new_interval}")
            schedule_auto_refresh()

        filter_var.trace_add("write", on_filter_change)
        known_only_var.trace_add("write", on_filter_change)
        status_filter_var.trace_add("write", on_filter_change)
        auto_refresh_var.trace_add("write", on_auto_refresh_toggle)
        refresh_interval_var.trace_add("write", on_refresh_interval_change)
        tree.bind("<<TreeviewSelect>>", on_tree_select)
        status_filter_combo.bind("<<ComboboxSelected>>", on_tree_select)
        filter_entry.bind("<Escape>", lambda _evt: (filter_var.set(""), "break")[1])

        ttk.Button(button_frame, text="Refresh", style="InstanceAction.TButton", command=refresh_instances).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Focus", style="InstanceAction.TButton", command=focus_selected).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Close", style="InstanceDanger.TButton", command=close_selected).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Relaunch", style="InstanceAction.TButton", command=relaunch_selected).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Copy Account", style="InstanceAction.TButton", command=copy_account).pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="Copy Password", style="InstanceAction.TButton", command=copy_password).pack(side="left")

        tree.bind("<Double-1>", lambda _evt: focus_selected())

        def on_close():
            state["closing"] = True
            after_id = state.get("auto_refresh_after_id")
            if after_id is not None:
                try:
                    window.after_cancel(after_id)
                except Exception:
                    pass
                state["auto_refresh_after_id"] = None
            try:
                window.destroy()
            finally:
                self.instance_manager_window = None

        window.protocol("WM_DELETE_WINDOW", on_close)

        window.update_idletasks()
        padding_w = 80
        padding_h = 80
        min_w = 760
        min_h = 420
        req_w = window.winfo_reqwidth() + padding_w
        req_h = window.winfo_reqheight() + padding_h
        final_w = max(req_w, min_w)
        final_h = max(req_h, min_h)
        self._center_window(window, final_w, final_h)
        window.deiconify()
        refresh_instances()
        schedule_auto_refresh()

    def open_console_output(self):
        """Open or focus the console output window."""
        if self.console_window:
            self.console_window.show()

    def open_global_settings_editor(self):
        """Open the Global Settings editor window."""
        # Check if window already exists and focus it
        if self.global_settings_window and self.global_settings_window.winfo_exists():
            self.global_settings_window.deiconify()
            self.global_settings_window.lift()
            self.global_settings_window.focus_force()
            return

        self.global_settings_window = tk.Toplevel(self.root)
        self.global_settings_window.title("Roblox Global Settings Editor")
        self.global_settings_window.geometry("980x700")
        self.global_settings_window.minsize(860, 560)
        self.global_settings_window.configure(bg=self.BG_DARK)
        self.global_settings_window.resizable(True, True)
        
        self.global_settings_window.transient(self.root)
        self.global_settings_window.grab_set()
        self.register_toplevel(self.global_settings_window)
        
        if self.settings.get("enable_topmost", False):
            self.global_settings_window.attributes("-topmost", True)

        # Main frame
        main_frame = ttk.Frame(self.global_settings_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Roblox Global Settings Editor",
            style="Dark.TLabel",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # File path info
        global_settings_path = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\GlobalBasicSettings_13.xml")
        path_label = ttk.Label(
            main_frame,
            text=f"Editing: {global_settings_path}",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888"
        )
        path_label.pack(anchor="w", pady=(0, 10))

        # Settings frame
        settings_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        settings_frame.pack(fill="both", expand=True, pady=(0, 10))

        list_frame = ttk.Frame(settings_frame, style="Dark.TFrame")
        list_frame.pack(side="left", fill="both", expand=False)

        detail_frame = ttk.Frame(settings_frame, style="Dark.TFrame")
        detail_frame.pack(side="right", fill="both", expand=True, padx=(12, 0))

        self.global_settings_values = {}
        self.global_settings_xml_names = {}
        self.global_settings_meta = {}
        original_values = {}
        dirty_keys = set()

        selected_setting_var = tk.StringVar(value="")
        editor_value_str = tk.StringVar(value="")
        editor_value_bool = tk.BooleanVar(value=False)
        modified_only_var = tk.BooleanVar(value=False)
        status_var = tk.StringVar(value="Ready.")

        xml_tree = None
        xml_root = None

        settings_def = []

        search_var = tk.StringVar(value="")
        search_frame = ttk.Frame(list_frame, style="Dark.TFrame")
        search_frame.pack(fill="x", pady=(0, 6))
        search_frame.columnconfigure(0, weight=1)
        search_entry = ttk.Entry(search_frame, textvariable=search_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(
            search_frame,
            text="Modified Only",
            variable=modified_only_var,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        tree = ttk.Treeview(
            list_frame,
            columns=("setting", "type", "value", "status"),
            show="headings",
            height=18,
            selectmode="browse",
            style="Dark.Treeview",
        )
        tree.heading("setting", text="Setting")
        tree.heading("type", text="Type")
        tree.heading("value", text="Value")
        tree.heading("status", text="Status")
        tree.column("setting", width=230, anchor="w")
        tree.column("type", width=70, anchor="w")
        tree.column("value", width=200, anchor="w")
        tree.column("status", width=90, anchor="w")
        tree.pack(side="left", fill="both", expand=True)

        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        list_scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=list_scroll.set)

        detail_title = ttk.Label(detail_frame, text="", style="Dark.TLabel", font=("Segoe UI", 11, "bold"))
        detail_title.pack(anchor="w")

        detail_desc = ttk.Label(
            detail_frame,
            text="",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888",
            wraplength=260
        )
        detail_desc.pack(anchor="w", pady=(2, 10))
        ttk.Label(detail_frame, textvariable=status_var, style="Dark.TLabel").pack(anchor="w", pady=(0, 10))

        editor_container = ttk.Frame(detail_frame, style="Dark.TFrame")
        editor_container.pack(fill="x")

        editor_entry = ttk.Entry(editor_container, textvariable=editor_value_str, style="Dark.TEntry")
        editor_combo = ttk.Combobox(editor_container, textvariable=editor_value_str, state="readonly", style="Dark.TCombobox")
        editor_check = ttk.Checkbutton(editor_container, text="Enabled", variable=editor_value_bool, style="Dark.TCheckbutton")

        def set_editor_mode(mode: str, options=None):
            for w in (editor_entry, editor_combo, editor_check):
                w.pack_forget()

            if mode == "bool":
                editor_check.pack(anchor="w")
            elif mode == "choice":
                editor_combo.configure(values=options or [])
                editor_combo.pack(fill="x")
            else:
                editor_entry.pack(fill="x")

        def get_properties_node(root_elem, xml_name: str):
            properties = root_elem.find(".//Properties")
            if properties is None:
                return None
            return properties.find(f".//*[@name='{xml_name}']")

        def read_value_from_xml(root_elem, item_meta):
            xml_name = item_meta["xml"]
            prop = get_properties_node(root_elem, xml_name)
            if prop is not None and prop.text is not None:
                return prop.text.strip()

            fallback_setting = root_elem.find(f".//Setting[@name='{xml_name}']")
            if fallback_setting is not None:
                return (fallback_setting.get("value") or "").strip()

            if item_meta["type"] == "bool":
                return "false"
            if item_meta["type"] in ("int", "token", "int64"):
                return "0"
            return ""

        def refresh_tree_values():
            query = (search_var.get() or "").strip().lower()
            for row in tree.get_children():
                tree.delete(row)

            shown = 0
            for item in settings_def:
                key = item["key"]
                value = self.global_settings_values.get(key, "")
                value_text = str(value)
                type_text = item.get("type", "string")
                is_modified = str(value_text) != str(original_values.get(key, ""))
                if modified_only_var.get() and (not is_modified):
                    continue
                if query:
                    haystack = f"{key} {type_text} {value_text}".lower()
                    if query not in haystack:
                        continue
                shown += 1
                tree.insert(
                    "",
                    "end",
                    iid=key,
                    values=(key, type_text, value_text, "Modified" if is_modified else ""),
                )

            status_var.set(
                f"Settings: {shown}/{len(settings_def)} shown | Modified: {len(dirty_keys)}"
            )

            sel = tree.selection()
            if not sel:
                children = tree.get_children()
                if children:
                    tree.selection_set(children[0])
                    tree.focus(children[0])
                    on_select_setting()
                else:
                    selected_setting_var.set("")
                    detail_title.configure(text="")
                    detail_desc.configure(text="")
                    editor_value_str.set("")
                    editor_value_bool.set(False)
                    set_editor_mode("text")
                    return

        # Parse and load settings
        def load_global_settings():
            nonlocal xml_tree, xml_root
            try:
                if os.path.exists(global_settings_path):
                    try:
                        import stat
                        os.chmod(global_settings_path, stat.S_IWRITE | stat.S_IREAD)
                    except Exception:
                        pass

                import xml.etree.ElementTree as ET
                if os.path.exists(global_settings_path):
                    xml_tree = ET.parse(global_settings_path)
                    xml_root = xml_tree.getroot()
                else:
                    xml_tree = None
                    xml_root = None

                settings_def.clear()
                self.global_settings_xml_names.clear()
                self.global_settings_meta.clear()

                supported_tags = {"bool", "int", "int64", "float", "token", "string"}
                properties = xml_root.find(".//Properties") if xml_root is not None else None
                if properties is not None:
                    for child in list(properties):
                        try:
                            name_attr = child.get("name")
                        except Exception:
                            name_attr = None

                        if not name_attr:
                            continue
                        if child.tag not in supported_tags:
                            continue
                        if list(child):
                            continue

                        settings_def.append({
                            "key": name_attr,
                            "xml": name_attr,
                            "type": child.tag,
                            "description": f"{child.tag} setting",
                        })

                settings_def.sort(key=lambda x: x["key"].lower())

                for item in settings_def:
                    self.global_settings_xml_names[item["key"]] = item["xml"]
                    self.global_settings_meta[item["key"]] = item

                self.global_settings_values.clear()
                for item in settings_def:
                    if xml_root is None:
                        current = "false" if item["type"] == "bool" else ("0" if item["type"] in ("int", "token", "int64") else "")
                    else:
                        current = read_value_from_xml(xml_root, item)
                    self.global_settings_values[item["key"]] = current
                original_values.clear()
                original_values.update(self.global_settings_values)
                dirty_keys.clear()

                refresh_tree_values()

                if settings_def:
                    first_key = settings_def[0]["key"]
                    tree.selection_set(first_key)
                    tree.focus(first_key)
                    on_select_setting()

            except Exception as e:
                messagebox.showerror("Error Loading Settings", f"Failed to load global settings: {str(e)}")

        def on_select_setting(_event=None):
            sel = tree.selection()
            if not sel:
                return
            key = sel[0]
            selected_setting_var.set(key)

            meta = self.global_settings_meta.get(key, {})
            detail_title.configure(text=key)
            detail_desc.configure(text=meta.get("description", ""))

            current_value = self.global_settings_values.get(key, "")
            if meta.get("type") == "bool":
                editor_value_bool.set(str(current_value).strip().lower() == "true")
                set_editor_mode("bool")
            else:
                editor_value_str.set(str(current_value))
                set_editor_mode("text")

        tree.bind("<<TreeviewSelect>>", on_select_setting)

        def _on_search_change(*_):
            refresh_tree_values()

        search_var.trace_add("write", _on_search_change)
        modified_only_var.trace_add("write", _on_search_change)

        def normalize_value_for_type(type_name, value_str):
            t = (type_name or "").lower()
            v = (value_str or "").strip()
            if t == "bool":
                return "true" if v.lower() in {"1", "true", "yes", "on"} else "false"
            if t in {"int", "int64", "token"}:
                if v == "":
                    return "0"
                int(v)
                return v
            if t == "float":
                if v == "":
                    return "0"
                float(v)
                return v
            return v

        def apply_current_edit():
            key = selected_setting_var.get()
            if not key:
                return
            meta = self.global_settings_meta.get(key, {})
            type_name = meta.get("type", "string")
            try:
                if type_name == "bool":
                    normalized = "true" if bool(editor_value_bool.get()) else "false"
                else:
                    normalized = normalize_value_for_type(type_name, editor_value_str.get())
            except ValueError:
                messagebox.showerror("Invalid Value", f"Value is not valid for type '{type_name}'.")
                return

            self.global_settings_values[key] = normalized
            if str(normalized) != str(original_values.get(key, "")):
                dirty_keys.add(key)
            else:
                dirty_keys.discard(key)

            refresh_tree_values()
            tree.selection_set(key)
            tree.focus(key)

        def revert_current_edit():
            key = selected_setting_var.get()
            if not key:
                return
            self.global_settings_values[key] = original_values.get(key, "")
            dirty_keys.discard(key)
            refresh_tree_values()
            tree.selection_set(key)
            tree.focus(key)
            on_select_setting()

        detail_button_row = ttk.Frame(detail_frame, style="Dark.TFrame")
        detail_button_row.pack(fill="x", pady=(10, 0))
        detail_button_row.columnconfigure(0, weight=1)
        detail_button_row.columnconfigure(1, weight=1)
        ttk.Button(detail_button_row, text="Apply", style="Dark.TButton", command=apply_current_edit).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(detail_button_row, text="Revert", style="Dark.TButton", command=revert_current_edit).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        # Save the settings
        def save_global_settings():
            try:
                apply_current_edit()

                import xml.etree.ElementTree as ET
                from xml.dom import minidom

                # Load existing XML file if it exists, otherwise create new structure
                if os.path.exists(global_settings_path):
                    try:
                        xml_tree_local = ET.parse(global_settings_path)
                        root = xml_tree_local.getroot()
                    except Exception as e:
                        print(f"Warning: Could not parse existing XML, creating new: {e}")
                        root = ET.Element("Settings")
                else:
                    root = ET.Element("Settings")
                
                for item in settings_def:
                    key = item["key"]
                    xml_name = item["xml"]
                    value_str = str(self.global_settings_values.get(key, "")).strip()

                    if item.get("type") == "bool":
                        value_str = "true" if value_str.lower() == "true" else "false"

                    if item.get("type") == "string":
                        pass
                    else:
                        if value_str == "":
                            value_str = "0" if item.get("type") in {"int", "int64", "float", "token"} else value_str

                    properties = root.find(".//Properties")
                    if properties is not None:
                        prop_setting = properties.find(f".//*[@name='{xml_name}']")
                        if prop_setting is not None:
                            if prop_setting.tag == "bool":
                                prop_setting.text = value_str.lower()
                            else:
                                prop_setting.text = value_str

                    existing_setting = root.find(f".//Setting[@name='{xml_name}']")
                    if existing_setting is not None:
                        existing_setting.set("value", value_str)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(global_settings_path), exist_ok=True)
                
                # Create backup
                if os.path.exists(global_settings_path):
                    backup_path = global_settings_path + ".backup"
                    try:
                        import shutil
                        shutil.copy2(global_settings_path, backup_path)
                    except Exception:
                        pass  # Ignore backup errors
                
                # Pretty print XML
                xml_str = ET.tostring(root, encoding='unicode')
                dom = minidom.parseString(xml_str)
                pretty_xml = dom.toprettyxml(indent="\t")[23:]  # Remove XML declaration line
                
                # Save the file
                with open(global_settings_path, 'w', encoding='utf-8') as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                    f.write(pretty_xml)
                
                # Set file as read-only after saving
                try:
                    import stat
                    os.chmod(global_settings_path, stat.S_IREAD)
                except Exception as e:
                    print(f"Warning: Could not set file as read-only: {e}")
                
                original_values.clear()
                original_values.update(self.global_settings_values)
                dirty_keys.clear()
                refresh_tree_values()
                messagebox.showinfo("Success", f"Global settings saved successfully!\n\nBackup created at: {global_settings_path}.backup\n\nFile is now read-only.")
            except Exception as e:
                messagebox.showerror("Error Saving Settings", f"Failed to save global settings: {str(e)}")

        # Reset to defaults
        def reset_to_defaults():
            if messagebox.askyesno("Confirm Reset", "Set all loaded values to defaults?\n\nClick Save to write changes."):
                for item in settings_def:
                    key = item["key"]
                    item_type = item.get("type", "string")
                    if item_type == "bool":
                        self.global_settings_values[key] = "false"
                    elif item_type in {"int", "int64", "token", "float"}:
                        self.global_settings_values[key] = "0"
                    else:
                        self.global_settings_values[key] = ""

                    if str(self.global_settings_values[key]) != str(original_values.get(key, "")):
                        dirty_keys.add(key)
                    else:
                        dirty_keys.discard(key)

                refresh_tree_values()
                messagebox.showinfo("Reset Complete", "Values reset to defaults. Click Save to apply.")

        # Button frame
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")

        ttk.Button(
            button_frame,
            text="Reset to Defaults",
            style="Dark.TButton",
            command=reset_to_defaults
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Save",
            style="Dark.TButton",
            command=save_global_settings
        ).pack(side="left", fill="x", expand=True, padx=5)

        ttk.Button(
            button_frame,
            text="Reload",
            style="Dark.TButton",
            command=load_global_settings
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Close",
            style="Dark.TButton",
            command=self.global_settings_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Load initial settings
        load_global_settings()
        self.global_settings_window.bind("<Control-f>", lambda _evt: (search_entry.focus_set(), "break")[1])
        self.global_settings_window.bind("<Control-s>", lambda _evt: (save_global_settings(), "break")[1])
        self.global_settings_window.bind("<Escape>", lambda _evt: (search_var.set(""), "break")[1])

    def open_fastflags_editor(self):
        """Open the FastFlags editor window."""
        if self.fastflags_window and self.fastflags_window.winfo_exists():
            self.fastflags_window.deiconify()
            self.fastflags_window.lift()
            self.fastflags_window.focus_force()
            return

        self.fastflags_window = tk.Toplevel(self.root)
        self.fastflags_window.title("FastFlags Editor")
        self.fastflags_window.geometry("980x700")
        self.fastflags_window.minsize(860, 560)
        self.fastflags_window.configure(bg=self.BG_DARK)
        self.fastflags_window.resizable(True, True)

        self.fastflags_window.transient(self.root)
        self.fastflags_window.grab_set()
        self.register_toplevel(self.fastflags_window)

        if self.settings.get("enable_topmost", False):
            self.fastflags_window.attributes("-topmost", True)

        selected_version = self.version_var.get()
        version_path = None
        if selected_version != "Latest Version" and selected_version in self.version_options:
            version_path = self.version_options[selected_version]

        fastflags_manager = FastFlagsManager(version_path=version_path)
        current_flags_cache = dict(fastflags_manager.load_fast_flags() or {})

        main_frame = ttk.Frame(self.fastflags_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=18, pady=14)

        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill="x", pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text="FastFlags Editor",
            style="Dark.TLabel",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        target_path = fastflags_manager.get_fast_flags_file()
        path_text = target_path if target_path else "FastFlags path unavailable"
        ttk.Label(
            header_frame,
            text=path_text,
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        toolbar_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        toolbar_frame.pack(fill="x", pady=(0, 8))
        toolbar_frame.columnconfigure(1, weight=1)

        preset_var = tk.StringVar(value="")
        presets = fastflags_manager.get_available_presets()
        preset_combo = ttk.Combobox(
            toolbar_frame,
            textvariable=preset_var,
            values=presets,
            state="readonly",
            style="Dark.TCombobox",
            width=24,
        )
        preset_combo.grid(row=0, column=0, sticky="w")
        if presets:
            preset_combo.set(presets[0])

        search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(toolbar_frame, textvariable=search_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        status_var = tk.StringVar(value="")
        status_label = ttk.Label(toolbar_frame, textvariable=status_var, style="Dark.TLabel")
        status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        paned = ttk.Panedwindow(main_frame, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=(0, 10))

        list_panel = ttk.Frame(paned, style="Dark.TFrame")
        editor_panel = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(list_panel, weight=3)
        paned.add(editor_panel, weight=2)

        tree = ttk.Treeview(
            list_panel,
            columns=("name", "value"),
            show="headings",
            selectmode="browse",
            style="Dark.Treeview",
        )
        tree.heading("name", text="Flag")
        tree.heading("value", text="Value")
        tree.column("name", width=390, anchor="w")
        tree.column("value", width=210, anchor="w")
        tree.pack(side="left", fill="both", expand=True)

        list_scroll = ttk.Scrollbar(list_panel, orient="vertical", command=tree.yview)
        list_scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=list_scroll.set)

        editor_panel.columnconfigure(0, weight=1)
        ttk.Label(editor_panel, text="Selected Flag", style="Dark.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        selected_name_var = tk.StringVar(value="")
        selected_name_entry = ttk.Entry(editor_panel, textvariable=selected_name_var, style="Dark.TEntry")
        selected_name_entry.grid(row=1, column=0, sticky="ew")

        ttk.Label(editor_panel, text="Value (JSON)", style="Dark.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=(12, 4)
        )
        selected_value_var = tk.StringVar(value="")
        selected_value_entry = ttk.Entry(editor_panel, textvariable=selected_value_var, style="Dark.TEntry")
        selected_value_entry.grid(row=3, column=0, sticky="ew")

        quick_row = ttk.Frame(editor_panel, style="Dark.TFrame")
        quick_row.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        quick_row.columnconfigure(0, weight=1)
        quick_row.columnconfigure(1, weight=1)

        add_row = ttk.Frame(editor_panel, style="Dark.TFrame")
        add_row.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        add_row.columnconfigure(0, weight=1)

        ttk.Label(add_row, text="Create or Update Flag", style="Dark.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        add_name_var = tk.StringVar(value="")
        add_value_var = tk.StringVar(value="")
        ttk.Entry(add_row, textvariable=add_name_var, style="Dark.TEntry").grid(row=1, column=0, sticky="ew", pady=(6, 4))
        ttk.Entry(add_row, textvariable=add_value_var, style="Dark.TEntry").grid(row=2, column=0, sticky="ew")

        action_row = ttk.Frame(editor_panel, style="Dark.TFrame")
        action_row.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        action_row.columnconfigure(0, weight=1)
        action_row.columnconfigure(1, weight=1)
        action_row.columnconfigure(2, weight=1)

        footer_row = ttk.Frame(main_frame, style="Dark.TFrame")
        footer_row.pack(fill="x")

        refresh_after_id = {"id": None}

        def to_edit_text(value):
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)

        def normalize_flag_value(text):
            value_text = str(text or "").strip()
            if not value_text:
                return None, "Flag value cannot be empty."
            if value_text in ("True", "False"):
                value_text = value_text.lower()

            try:
                parsed = json.loads(value_text)
                if not isinstance(parsed, (str, int, float, bool)):
                    return None, "Value must be string, number, or boolean."
                return parsed, None
            except Exception:
                # Backward-compatible convenience: plain text without quotes is treated as string.
                if re.match(r"^[A-Za-z0-9_.:/@\- ]+$", value_text):
                    return value_text, None
                return None, "Invalid value. Use JSON literals, e.g. true, 60, 3.14, or \"text\"."

        def save_current_flags(show_success=False):
            ok = fastflags_manager.save_fast_flags(current_flags_cache)
            if not ok:
                messagebox.showerror("FastFlags", "Failed to save FastFlags.")
                return False
            if show_success:
                self.show_success_message("FastFlags saved.")
            return True

        def update_status(filtered_count=None):
            total = len(current_flags_cache)
            if filtered_count is None:
                filtered_count = total
            status_var.set(f"Showing {filtered_count} / {total} flags")

        def refresh_tree():
            query = (search_var.get() or "").strip().lower()
            selected_name = selected_name_var.get().strip()
            for item in tree.get_children():
                tree.delete(item)

            keys = sorted(current_flags_cache.keys(), key=lambda x: x.lower())
            filtered = 0
            for name in keys:
                value = current_flags_cache.get(name)
                value_text = to_edit_text(value)
                if query and query not in name.lower() and query not in value_text.lower():
                    continue
                filtered += 1
                tree.insert("", "end", iid=name, values=(name, value_text))

            update_status(filtered_count=filtered)

            if selected_name and tree.exists(selected_name):
                tree.selection_set(selected_name)
                tree.focus(selected_name)
            elif tree.get_children():
                first = tree.get_children()[0]
                tree.selection_set(first)
                tree.focus(first)
                on_tree_select()
            else:
                selected_name_var.set("")
                selected_value_var.set("")

        def queue_refresh_tree(*_args):
            pending = refresh_after_id.get("id")
            if pending is not None:
                try:
                    self.fastflags_window.after_cancel(pending)
                except Exception:
                    pass
            refresh_after_id["id"] = self.fastflags_window.after(120, refresh_tree)

        def on_tree_select(_evt=None):
            sel = tree.selection()
            if not sel:
                return
            name = sel[0]
            selected_name_var.set(name)
            selected_value_var.set(to_edit_text(current_flags_cache.get(name)))

        def apply_preset():
            preset_name = (preset_var.get() or "").strip()
            if not preset_name:
                return
            preset_flags = fastflags_manager.presets.get(preset_name) or {}
            for key, value in preset_flags.items():
                parsed, _err = normalize_flag_value(to_edit_text(value))
                if _err is None:
                    current_flags_cache[key] = parsed
                else:
                    current_flags_cache[key] = value
            if save_current_flags():
                refresh_tree()
                self.show_success_message(f"Applied preset: {preset_name}")

        def save_selected_flag():
            name = (selected_name_var.get() or "").strip()
            value_text = (selected_value_var.get() or "").strip()
            if not name:
                messagebox.showerror("FastFlags", "No flag selected.")
                return

            original_name = ""
            sel = tree.selection()
            if sel:
                original_name = sel[0]

            valid_name, name_error = fastflags_manager.validate_flag_name(name)
            if not valid_name:
                messagebox.showerror("Invalid Flag Name", name_error)
                return

            parsed, value_error = normalize_flag_value(value_text)
            if value_error:
                messagebox.showerror("Invalid Value", value_error)
                return

            if original_name and original_name != name and original_name in current_flags_cache:
                del current_flags_cache[original_name]
            current_flags_cache[name] = parsed
            if save_current_flags():
                refresh_tree()

        def add_or_update_flag():
            name = (add_name_var.get() or "").strip()
            value_text = (add_value_var.get() or "").strip()
            if not name:
                messagebox.showerror("FastFlags", "Please provide a flag name.")
                return

            valid_name, name_error = fastflags_manager.validate_flag_name(name)
            if not valid_name:
                messagebox.showerror("Invalid Flag Name", name_error)
                return

            parsed, value_error = normalize_flag_value(value_text)
            if value_error:
                messagebox.showerror("Invalid Value", value_error)
                return

            current_flags_cache[name] = parsed
            if save_current_flags():
                add_name_var.set("")
                add_value_var.set("")
                selected_name_var.set(name)
                selected_value_var.set(to_edit_text(parsed))
                refresh_tree()

        def remove_selected():
            name = (selected_name_var.get() or "").strip()
            if not name:
                return
            if name not in current_flags_cache:
                return
            del current_flags_cache[name]
            if save_current_flags():
                selected_name_var.set("")
                selected_value_var.set("")
                refresh_tree()

        def backup_flags():
            if fastflags_manager.backup_fast_flags():
                self.show_success_message("FastFlags backup created.")
            else:
                messagebox.showerror("FastFlags", "Failed to backup FastFlags.")

        def restore_flags():
            if fastflags_manager.restore_fast_flags():
                current_flags_cache.clear()
                current_flags_cache.update(fastflags_manager.load_fast_flags() or {})
                refresh_tree()
                self.show_success_message("FastFlags restored from backup.")
            else:
                messagebox.showerror("FastFlags", "Failed to restore FastFlags backup.")

        def reset_flags():
            confirm = messagebox.askyesno("Reset FastFlags", "Reset all FastFlags to default?")
            if not confirm:
                return
            if fastflags_manager.reset_to_default():
                current_flags_cache.clear()
                refresh_tree()
                self.show_success_message("FastFlags reset to default.")
            else:
                messagebox.showerror("FastFlags", "Failed to reset FastFlags.")

        def on_close():
            pending = refresh_after_id.get("id")
            if pending is not None:
                try:
                    self.fastflags_window.after_cancel(pending)
                except Exception:
                    pass
                refresh_after_id["id"] = None
            try:
                self.fastflags_window.destroy()
            finally:
                self.fastflags_window = None

        ttk.Button(toolbar_frame, text="Apply Preset", style="Dark.TButton", command=apply_preset).grid(
            row=0, column=2, padx=(8, 0), sticky="w"
        )
        ttk.Button(toolbar_frame, text="Refresh", style="Dark.TButton", command=refresh_tree).grid(
            row=0, column=3, padx=(6, 0), sticky="w"
        )

        ttk.Button(quick_row, text="Save Selected", style="Dark.TButton", command=save_selected_flag).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(quick_row, text="Remove Selected", style="Dark.TButton", command=remove_selected).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Button(add_row, text="Add / Update", style="Dark.TButton", command=add_or_update_flag).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )

        ttk.Button(action_row, text="Backup", style="Dark.TButton", command=backup_flags).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(action_row, text="Restore", style="Dark.TButton", command=restore_flags).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(action_row, text="Reset All", style="Dark.TButton", command=reset_flags).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        ttk.Button(footer_row, text="Close", style="Dark.TButton", command=on_close).pack(side="right")

        tree.bind("<<TreeviewSelect>>", on_tree_select)
        tree.bind("<Delete>", lambda _evt: remove_selected())
        search_var.trace_add("write", queue_refresh_tree)
        search_entry.bind("<Escape>", lambda _evt: (search_var.set(""), "break")[1])
        self.fastflags_window.bind("<Control-f>", lambda _evt: (search_entry.focus_set(), "break")[1])
        self.fastflags_window.bind("<Control-s>", lambda _evt: (save_selected_flag(), "break")[1])
        selected_value_entry.bind("<Return>", lambda _evt: (save_selected_flag(), "break")[1])

        self.fastflags_window.protocol("WM_DELETE_WINDOW", on_close)

        refresh_tree()
        self.fastflags_window.update_idletasks()
        width = max(860, self.fastflags_window.winfo_reqwidth())
        height = max(560, self.fastflags_window.winfo_reqheight())
        x = (self.fastflags_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.fastflags_window.winfo_screenheight() // 2) - (height // 2)
        self.fastflags_window.geometry(f"{width}x{height}+{x}+{y}")
        self.fastflags_window.deiconify()

