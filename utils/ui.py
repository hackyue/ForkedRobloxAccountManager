"""
UI Module for Roblox Account Manager
Contains the main AccountManagerUI class
"""

import os
import re
import sys
import io
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


def clamp_multi_launch_delay(value):
    """Clamp arbitrary input to the allowed multi-launch delay range."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = MIN_LAUNCH_DELAY_SECONDS
    return max(MIN_LAUNCH_DELAY_SECONDS, min(MAX_LAUNCH_DELAY_SECONDS, numeric))


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
        if self.target_stream:
            self.target_stream.write(data)
        self.buffer.append_text(data, self.stream_label)
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
        atexit.register(self._cleanup)

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

    def __init__(self, root, manager):
        self.root = root
        self.manager = manager
        self.APP_VERSION = "2.4.0"
        self._game_name_after_id = None
        self._game_name_label_after_id = None
        self._game_name_request_token = 0
        self._last_game_name_query_value = None

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
        
        self.root.title("FRAM v2.4.0 - made by evanovar - modified by hackyue")
        self.root.geometry("600x600")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(True, True)
        self.root.minsize(600, 700)  # Note to self, this shit so ass
        
        self.data_folder = "AccountManagerData"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        self.settings_file = os.path.join(self.data_folder, "ui_settings.json")
        self.load_settings()
        try:
            self.root.attributes("-topmost", bool(self.settings.get("enable_topmost", False)))
        except Exception:
            pass
        self._auto_relaunch_after_id = None
        self._auto_relaunch_in_progress = False
        
        self.multi_roblox_handle = None
        self.console_output = get_console_output_buffer()
        self.console_window = ConsoleOutputWindow(self, self.console_output)
        self.account_list_drag_data = {
            "start_index": None,
            "drop_index": None,
            "start_username": None,
            "start_y": None,
            "is_dragging": False
        }
        self.account_drop_indicator = None
        self.themable_text_widgets = []
        self.themable_windows = set()

        self.theme_name = self.settings.get("selected_theme", "Synapse Neon")
        self.menu_bar = None
        self.actions_menu = None
        self.installer_menu = None
        self.menu_bar_frame = None
        self.menu_buttons = []
        self.version_options = {"Latest Version": None}
        self.installer_dialog_state = None

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
        if self.settings.get("enable_multi_select", False):
            self.account_list.bind("<Control-ButtonPress-1>", self.on_account_ctrl_click)

        self.account_drop_indicator = tk.Frame(self.account_list, height=2, bg=self.FG_ACCENT)

        scrollbar = ttk.Scrollbar(list_frame, command=self.account_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.account_list.config(yscrollcommand=scrollbar.set)

        right_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_rowconfigure(3, weight=1)  
        
        self.game_name_label = ttk.Label(right_frame, text="", style="Dark.TLabel", font=("Segoe UI", 9))
        self.game_name_label.pack(anchor="w", pady=(0, 5))
        
        ttk.Label(right_frame, text="Place ID", style="Dark.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.place_entry = ttk.Entry(right_frame, style="Dark.TEntry")
        self.place_entry.pack(fill="x", pady=(0, 5))
        self.place_entry.insert(0, self.settings.get("last_place_id", ""))
        self.place_entry.bind("<KeyRelease>", self.on_place_id_change)

        ttk.Label(right_frame, text="Private Server ID (Optional)", style="Dark.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.private_server_entry = ttk.Entry(right_frame, style="Dark.TEntry")
        self.private_server_entry.pack(fill="x", pady=(0, 5))
        self.private_server_entry.insert(0, self.settings.get("last_private_server", ""))
        self.private_server_entry.bind("<KeyRelease>", self.on_private_server_change)


        ttk.Label(right_frame, text="Roblox Version (Optional)", style="Dark.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 0))
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
        
        ttk.Label(right_frame, text="Recent games", style="Dark.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        
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

        ttk.Button(action_frame, text="Validate Account", style="Dark.TButton", command=self.validate_account).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Edit Note", style="Dark.TButton", command=self.edit_account_note).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Set Group", style="Dark.TButton", command=self.edit_account_group).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Refresh List", style="Dark.TButton", command=self.refresh_accounts).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Auto-Arrange Clients", style="Dark.TButton", command=self.auto_arrange_clients).pack(fill="x", pady=2)

        bottom_frame = ttk.Frame(self.root, style="Dark.TFrame")
        bottom_frame.pack(fill="x", padx=10, pady=(5, 10), anchor='s')

        self.add_account_split_btn = ttk.Button(
            bottom_frame,
            text="Add Account",
            style="Dark.TButton",
            command=self.add_account,
        )
        self.add_account_split_btn.pack(side="left", fill="both", expand=True, padx=(0, 2))

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

        self.root.after(500, self._auto_relaunch_maybe_start)
        self.root.after(1500, self._auto_update_maybe_start)

    def load_settings(self):
        """Load UI settings from file"""
        defaults = {
            "last_place_id": "",
            "last_private_server": "",
            "game_list": [],
            "enable_topmost": False,
            "enable_multi_roblox": False,
            "confirm_before_launch": False,
            "max_recent_games": 10,
            "enable_multi_select": False,
            "enable_debug_logging": False,
            "selected_theme": "Synapse Neon",
            "disable_success_popups": False,
            "auto_arrange_scope": "both",
            "multi_launch_delay": MIN_LAUNCH_DELAY_SECONDS,
            "custom_roblox_player_path": "",
            "selected_group": "All",
            "auto_relaunch_enabled": False,
            "auto_relaunch_interval_minutes": 60,
            "auto_relaunch_group": "",
            "auto_update_enabled": True,
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

        self._ensure_auto_arrange_scope_valid()
        if self.settings.get("enable_multi_roblox", False):
            self.root.after(100, self.initialize_multi_roblox)

        try:
            self.settings["auto_relaunch_interval_minutes"] = max(
                1,
                int(self.settings.get("auto_relaunch_interval_minutes", 60) or 60),
            )
        except (TypeError, ValueError):
            self.settings["auto_relaunch_interval_minutes"] = 60

    def _ensure_auto_arrange_scope_valid(self):
        """Keep auto-arrange scope sane, especially when only one monitor is available."""
        allowed_scopes = {"primary", "secondary", "both"}
        scope = self.settings.get("auto_arrange_scope", "both")
        if scope not in allowed_scopes:
            scope = "both"

        if not self._has_multiple_monitors():
            scope = "primary"

        self.settings["auto_arrange_scope"] = scope

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
                        on_done_callback=(
                            lambda success_count: self.root.after(focus_delay_ms, self._focus_main_window)
                            if success_count > 0 else None
                        ),
                    ),
                )
            finally:
                self._auto_relaunch_in_progress = False

        threading.Thread(target=worker, args=(group, list(usernames)), daemon=True).start()

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

        try:
            window.bind("<Destroy>", _cleanup, add="+")
            window.bind("<Map>", self._handle_window_map, add="+")
        except Exception:
            pass

        self._apply_title_bar_theme(window)

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

        menus = [getattr(self, attr, None) for attr in ("actions_menu", "installer_menu")]
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

    def refresh_installer_menu(self):
        """Populate the Roblox Installer menu with up to five recent versions."""
        if getattr(self, "installer_menu", None) is None:
            return

        self.installer_menu.delete(0, tk.END)
        versions = self.get_available_roblox_versions(limit=5)
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

            requested_version = (version or "").strip().lower()
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
            local_versions = self.get_local_roblox_versions()
            display_values = ["Latest Version"]
            self.version_options = {"Latest Version": None}

            for entry in local_versions:
                label = entry.get("label")
                path = entry.get("path")
                if not label or not path:
                    continue
                display_values.append(label)
                self.version_options[label] = path

            self.version_dropdown["values"] = display_values or ["Latest Version"]
        except Exception as e:
            print(f"Error loading Roblox versions: {e}")
            self.version_options = {"Latest Version": None}
            self.version_dropdown["values"] = ["Latest Version"]

        self.refresh_installer_menu()

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
                entries = [
                    os.path.join(base_path, d)
                    for d in os.listdir(base_path)
                    if os.path.isdir(os.path.join(base_path, d))
                ]
                entries.sort(key=lambda path: os.path.getmtime(path), reverse=True)

                if limit is not None:
                    entries = entries[:limit]

                for idx, path in enumerate(entries):
                    label = f"[{source['name']}] {os.path.basename(path)}"
                    version_name = os.path.basename(path)
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

        try:
            response = requests.get(history_url, timeout=5)
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
            if any(entry["version"] == version for entry in versions):
                continue
            status = "LIVE" if not versions else "PAST"
            versions.append({"version": version, "status": status})
            if limit and len(versions) >= limit:
                break

        return versions

    def get_available_roblox_versions(self, limit=None):
        """Get Roblox versions preferring remote history, falling back to local folders."""
        remote_versions = self.fetch_remote_versions(limit=limit)
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
                response = requests.get(api_url, headers=headers, timeout=12)
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
                with requests.get(download_url, headers=headers, stream=True, timeout=60) as resp:
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

                subprocess.Popen(args, close_fds=True)
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
        """Best-effort check to see if Google Chrome is installed (Windows)."""
        try:
            candidates = []
            pf = os.environ.get('ProgramFiles')
            pfx86 = os.environ.get('ProgramFiles(x86)')
            localapp = os.environ.get('LOCALAPPDATA')
            if pf:
                candidates.append(os.path.join(pf, 'Google', 'Chrome', 'Application', 'chrome.exe'))
            if pfx86:
                candidates.append(os.path.join(pfx86, 'Google', 'Chrome', 'Application', 'chrome.exe'))
            if localapp:
                candidates.append(os.path.join(localapp, 'Google', 'Chrome', 'Application', 'chrome.exe'))
            for path in candidates:
                if path and os.path.exists(path):
                    return True
        except Exception:
            pass
        return False

    def on_place_id_change(self, event=None):
        """Called when place ID changes"""
        place_id = self.place_entry.get().strip()
        self.settings["last_place_id"] = place_id
        self.save_settings()
        self.update_game_name()

    def on_private_server_change(self, event=None):
        """Called when private server ID changes"""
        private_server = self.private_server_entry.get().strip()
        self.settings["last_private_server"] = private_server
        self.save_settings()

    def update_game_name(self):
        """Debounced, non-blocking update of the game name label"""
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
        self.refresh_game_list()
        self.update_game_name()
        

        self.load_roblox_versions()
        
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

    def refresh_game_list(self):
        """Refresh the game list display"""
        self.game_list.delete(0, tk.END)
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
            messagebox.showwarning("No Selection", "Please select a game to delete.")
            return
        
        index = selection[0]
        game = self.settings["game_list"][index]
        confirm = messagebox.askyesno("Confirm Delete", f"Delete '{game['name']}' from list?")
        if confirm:
            self.settings["game_list"].pop(index)
            self.save_settings()
            self.refresh_game_list()
            self.show_success_message("Game removed from list!")

    def _extract_username(self, display_text):
        return display_text.split(' • ')[0]

    def refresh_accounts(self, selected_usernames=None):
        """Refresh the account list"""
        if selected_usernames is None:
            selected_usernames = [
                self._extract_username(self.account_list.get(idx))
                for idx in self.account_list.curselection()
            ]

        self.account_list.delete(0, tk.END)
        active_group = self._get_active_group()
        for username, data in self.manager.accounts.items():
            if not isinstance(data, dict):
                continue

            group = (data.get('group') or '').strip()
            if active_group and group != active_group:
                continue

            note = (data.get('note') or '').strip()
            display_text = f"{username}"
            if group:
                display_text += f" • [{group}]"
            if note:
                display_text += f" • {note}"
            self.account_list.insert(tk.END, display_text)
            if username in selected_usernames:
                idx = self.account_list.size() - 1
                self.account_list.selection_set(idx)
                self.account_list.activate(idx)
    
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

    def add_account(self):
        """
        Add a new account using browser automation
        """
        if not self.is_chrome_installed():
            messagebox.showwarning(
                "Google Chrome Required",
                "Add Account requires Google Chrome to be installed.\n"
                "Please install Google Chrome and try again."
            )
            return

        messagebox.showinfo("Add Account", "Browser will open for account login.\nPlease log in and wait for the process to complete.")
        
        def add_account_thread():
            """
            Thread function to add account without blocking UI
            """
            try:
                success = self.manager.add_account(1, "https://www.roblox.com/login", "")
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
                    success_count = self.manager.add_accounts_from_credentials(parsed_credentials)
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
        Launch multiple Chrome instances with custom Javascript execution
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
                success = self.manager.add_account(amount, website, javascript)
                
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
                errors='replace'
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
        """Arrange Roblox clients across all monitors, keeping each window inside its monitor."""
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
        total = len(hwnds)
        if total == 0:
            return

        start = 0
        for idx, work_area in enumerate(monitor_work_areas):
            remaining_monitors = len(monitor_work_areas) - idx
            remaining_windows = total - start
            if remaining_windows <= 0:
                break

            windows_for_monitor = max(1, math.ceil(remaining_windows / remaining_monitors))
            subset = hwnds[start:start + windows_for_monitor]
            if subset:
                self._arrange_windows_within_area(subset, work_area)
            start += windows_for_monitor

    def _arrange_windows_within_area(self, hwnds, work_area):
        """Tile the given HWNDs inside a single monitor work area."""
        work_left, work_top, work_right, work_bottom = work_area
        available_width = max(1, work_right - work_left)
        available_height = max(1, work_bottom - work_top)

        window_count = len(hwnds)
        if window_count == 0:
            return

        aspect_ratio = available_width / available_height if available_height else 1
        columns = max(1, math.ceil(math.sqrt(window_count * aspect_ratio)))
        columns = min(columns, window_count)
        rows = max(1, math.ceil(window_count / columns))

        column_edges = [
            work_left + round(i * available_width / columns)
            for i in range(columns + 1)
        ]
        column_edges[-1] = work_right
        row_edges = [
            work_top + round(i * available_height / rows)
            for i in range(rows + 1)
        ]
        row_edges[-1] = work_bottom

        for index, hwnd in enumerate(hwnds):
            row = index // columns
            col = index % columns
            if row >= rows:
                row = rows - 1

            left = column_edges[col]
            right = column_edges[col + 1]
            top = row_edges[row]
            bottom = row_edges[min(row + 1, len(row_edges) - 1)]

            width = max(1, right - left)
            height = max(1, bottom - top)

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.MoveWindow(hwnd, left, top, width, height, True)
            except Exception:
                continue

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

        valid_usernames = []
        invalid_usernames = []

        for username in usernames:
            try:
                is_valid = self.manager.validate_account(username)
            except Exception:
                is_valid = False
            if is_valid:
                valid_usernames.append(username)
            else:
                invalid_usernames.append(username)

        if len(usernames) == 1:
            if valid_usernames:
                messagebox.showinfo("Validation", f"Account '{usernames[0]}' is valid!")
            else:
                messagebox.showwarning("Validation", f"Account '{usernames[0]}' is invalid or expired.")
            return

        lines = [
            f"Validated {len(usernames)} account(s).",
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
        """Launch Chrome to Roblox home with the selected account(s) logged in (non-blocking)"""
        if not self.is_chrome_installed():
            messagebox.showwarning(
                "Google Chrome Required",
                "Launching browser requires Google Chrome to be installed.\n"
                "Please install Google Chrome and try again."
            )
            return

        if self.settings.get("enable_multi_select", False):
            usernames = self.get_selected_usernames()
            if not usernames:
                return
            if len(usernames) >= 3:
                confirm = messagebox.askyesno(
                    "Confirm Launch",
                    f"Are you sure you want to launch {len(usernames)} browser windows?\n\nThis will open multiple Chrome instances."
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
                    if self.manager.launch_home(uname):
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

    def launch_home_app(self):
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
        if not version_path:
            custom_player_path = (self.settings.get("custom_roblox_player_path") or "").strip()
            if custom_player_path:
                version_path = custom_player_path

        def worker(selected_usernames, delay_seconds):
            success_count = 0
            for idx, uname in enumerate(selected_usernames):
                try:
                    if self.manager.launch_home_app(uname, version=version_path or None, enable_debug=debug_enabled):
                        success_count += 1
                except Exception as e:
                    print(f"Failed to launch Roblox home for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)

            def notify():
                if success_count > 0:
                    if len(selected_usernames) == 1:
                        self.show_success_message("Roblox is launching to home! Check your desktop.")
                    else:
                        self.show_success_message(f"Roblox is launching to home for {success_count} account(s)! Check your desktop.")
                else:
                    messagebox.showerror("Error", "Failed to launch Roblox.")

            self.root.after(0, notify)

        threading.Thread(target=worker, args=(usernames, launch_delay), daemon=True).start()

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

    def _launch_game_for_usernames(self, usernames, confirm_group=None, skip_confirm=False, on_done_callback=None):
        game_id = self.place_entry.get().strip()
        private_server = self.private_server_entry.get().strip()

        selected_version_label = self.version_var.get()
        version_path = self.version_options.get(selected_version_label)
        if not version_path:
            custom_player_path = (self.settings.get("custom_roblox_player_path") or "").strip()
            if custom_player_path:
                version_path = custom_player_path

        if not game_id:
            messagebox.showwarning("Missing Information", "Please enter a Place ID.")
            return

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

        def worker(selected_usernames, pid, psid, ver, debug_flag, delay_seconds):
            success_count = 0
            for idx, uname in enumerate(selected_usernames):
                try:
                    if self.manager.launch_roblox(uname, pid, psid, ver, enable_debug=debug_flag):
                        success_count += 1
                except Exception as e:
                    print(f"Failed to launch game for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)

            def on_done():
                if success_count > 0:
                    gname = RobloxAPI.get_game_name(pid)
                    if gname:
                        self.add_game_to_list(pid, gname, psid)
                    else:
                        self.add_game_to_list(pid, f"Place {pid}", psid)
                    if len(selected_usernames) == 1:
                        self.show_success_message("Roblox is launching! Check your desktop.")
                    else:
                        self.show_success_message(f"Roblox is launching for {success_count} account(s)! Check your desktop.")

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
            args=(list(usernames), game_id, private_server, version_path, debug_enabled, launch_delay),
            daemon=True
        ).start()

    def enable_multi_roblox(self):
        """Enable Multi Roblox + 773 fix"""

        import subprocess
        import win32event
        import win32api
        

        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RobloxPlayerBeta.exe'], 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace') 
            
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
                                 capture_output=True, text=True, encoding='utf-8', errors='replace') 
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
        settings_window.resizable(False, False)
        
        settings_window.transient(self.root)
        settings_window.grab_set()
        self.register_toplevel(settings_window)
        
        if self.settings.get("enable_topmost", False):
            settings_window.attributes("-topmost", True)
        
        main_frame = ttk.Frame(settings_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        topmost_var = tk.BooleanVar(value=self.settings.get("enable_topmost", False))
        multi_roblox_var = tk.BooleanVar(value=self.settings.get("enable_multi_roblox", False))
        confirm_launch_var = tk.BooleanVar(value=self.settings.get("confirm_before_launch", False))
        multi_select_var = tk.BooleanVar(value=self.settings.get("enable_multi_select", False))
        debug_var = tk.BooleanVar(value=self.settings.get("enable_debug_logging", False))
        disable_success_var = tk.BooleanVar(value=self.settings.get("disable_success_popups", False))
        auto_update_var = tk.BooleanVar(value=self.settings.get("auto_update_enabled", True))
        theme_var = tk.StringVar(value=self.settings.get("selected_theme", self.theme_name))
        custom_launcher_var = tk.BooleanVar(value=self.settings.get("enable_custom_launcher", False))
        custom_launcher_path_var = tk.StringVar(value=self.settings.get("custom_launcher_path", ""))
        custom_launcher_player_var = tk.BooleanVar(value=self.settings.get("custom_launcher_requires_player", False))
        auto_arrange_scope_var = tk.StringVar(value=self.settings.get("auto_arrange_scope", "both"))
        custom_roblox_player_path_var = tk.StringVar(value=self.settings.get("custom_roblox_player_path", ""))
        
        checkbox_style = ttk.Style()
        checkbox_style.configure(
            "Dark.TCheckbutton",
            background=self.BG_DARK,
            foreground="white",
            font=("Segoe UI", 10)
        )
        checkbox_style.map(
            "Dark.TCheckbutton",
            background=[("active", self.BG_MID)],
            foreground=[("disabled", self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888")]
        )
        
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

        def create_tab_frame(tab_name):
            frame = ttk.Frame(content_frame, style="Dark.TFrame")
            frame.grid(row=0, column=0, sticky="nsew")
            tabs[tab_name] = frame
            return frame

        create_tab_button("General", "general")
        create_tab_button("Roblox", "roblox")
        create_tab_button("Automation", "automation")
        create_tab_button("Advanced", "advanced")

        general_tab = create_tab_frame("general")
        roblox_tab = create_tab_frame("roblox")
        automation_tab = create_tab_frame("automation")
        advanced_tab = create_tab_frame("advanced")

        ttk.Label(
            general_tab,
            text="Interface & Notifications",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Checkbutton(
            general_tab,
            text="Enable Topmost",
            variable=topmost_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_topmost", topmost_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            general_tab,
            text="Multi Select (Ctrl + Click)",
            variable=multi_select_var,
            style="Dark.TCheckbutton",
            command=on_multi_select_toggle
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            general_tab,
            text="Disable Success Popups",
            variable=disable_success_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("disable_success_popups", disable_success_var)
        ).pack(anchor="w", pady=2)

        ttk.Label(
            general_tab,
            text="Updates",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(10, 6))

        ttk.Checkbutton(
            general_tab,
            text="Enable Auto Updates",
            variable=auto_update_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("auto_update_enabled", auto_update_var)
        ).pack(anchor="w", pady=2)

        ttk.Label(
            general_tab,
            text="Theme",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 2))

        theme_combo = ttk.Combobox(
            general_tab,
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

        ttk.Label(
            general_tab,
            text="Auto-Arrange applies to",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 2))

        if self._has_multiple_monitors():
            scope_display_map = {
                "primary": "Primary monitor only",
                "secondary": "Secondary monitor only",
                "both": "All monitors"
            }
            scope_inverse_map = {label: value for value, label in scope_display_map.items()}
            selected_label = scope_display_map.get(auto_arrange_scope_var.get(), scope_display_map["both"])

            scope_combo = ttk.Combobox(
                general_tab,
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
                general_tab,
                text="Only one monitor detected. Auto-arrange will use the available screen.",
                style="Dark.TLabel",
                wraplength=320
            ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            roblox_tab,
            text="Roblox Client",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Checkbutton(
            roblox_tab,
            text="Confirm Before Launch",
            variable=confirm_launch_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("confirm_before_launch", confirm_launch_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            roblox_tab,
            text="Enable Multi Roblox",
            variable=multi_roblox_var,
            style="Dark.TCheckbutton",
            command=on_multi_roblox_toggle
        ).pack(anchor="w", pady=2)

        ttk.Label(roblox_tab, text="", style="Dark.TLabel").pack(pady=5)

        def open_global_settings_and_close_settings():
            """Open Global Settings editor and close settings window"""
            settings_window.destroy()
            self.open_global_settings_editor()

        ttk.Button(
            roblox_tab,
            text="Global Settings",
            style="Dark.TButton",
            command=open_global_settings_and_close_settings
        ).pack(fill="x", pady=(10, 2))

        custom_frame = ttk.Frame(roblox_tab, style="Dark.TFrame")
        custom_frame.pack(fill="x", pady=(0, 6))

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
            roblox_tab,
            text="Custom RobloxPlayer",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(12, 2))

        custom_player_frame = ttk.Frame(roblox_tab, style="Dark.TFrame")
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
            self.save_settings()

            if self.settings.get("auto_relaunch_enabled", False):
                self._auto_relaunch_start()
            else:
                self._auto_relaunch_stop()

        ttk.Label(
            automation_tab,
            text="Auto Relaunch",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Checkbutton(
            automation_tab,
            text="Enable Auto Relaunch",
            variable=auto_relaunch_enabled_var,
            style="Dark.TCheckbutton",
            command=on_auto_relaunch_update
        ).pack(anchor="w", pady=2)

        interval_frame = ttk.Frame(automation_tab, style="Dark.TFrame")
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

        group_frame = ttk.Frame(automation_tab, style="Dark.TFrame")
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

        ttk.Button(
            automation_tab,
            text="Run Auto Relaunch Now",
            style="Dark.TButton",
            command=self._auto_relaunch_run_once
        ).pack(fill="x", pady=(10, 0))

        ttk.Label(
            advanced_tab,
            text="Logging",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Checkbutton(
            advanced_tab,
            text="Enable Debug Logging",
            variable=debug_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_debug_logging", debug_var)
        ).pack(anchor="w", pady=2)

        def open_fastflags_and_close_settings():
            """Open FastFlags editor and close settings window"""
            settings_window.destroy()
            self.open_fastflags_editor()

        ttk.Button(
            advanced_tab,
            text="FastFlags Editor",
            style="Dark.TButton",
            command=open_fastflags_and_close_settings
        ).pack(fill="x", pady=(10, 2))

        set_active_tab("general")
        padding_w = 40
        padding_h = 40
        min_w = 420
        min_h = 460
        req_w = settings_window.winfo_reqwidth() + padding_w
        req_h = settings_window.winfo_reqheight() + padding_h
        final_w = max(req_w, min_w)
        final_h = max(req_h, min_h)
        self._center_window(settings_window, final_w, final_h)
        settings_window.deiconify()

        ttk.Button(
            main_frame,
            text="Console Output",
            style="Dark.TButton",
            command=self.open_console_output
        ).pack(fill="x", pady=(6, 4))

        ttk.Button(
            main_frame,
            text="Close",
            style="Dark.TButton",
            command=settings_window.destroy
        ).pack(fill="x", pady=(0, 0))

    def open_console_output(self):
        """Open or focus the console output window."""
        if self.console_window:
            self.console_window.show()

    def open_global_settings_editor(self):
        """Open the Global Settings editor window."""
        # Check if window already exists and focus it
        if hasattr(self, 'global_settings_window') and self.global_settings_window and self.global_settings_window.winfo_exists():
            self.global_settings_window.deiconify()
            self.global_settings_window.lift()
            self.global_settings_window.focus_force()
            return

        self.global_settings_window = tk.Toplevel(self.root)
        self.global_settings_window.title("Roblox Global Settings Editor")
        self.global_settings_window.geometry("500x600")
        self.global_settings_window.minsize(450, 500)
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

        # Create scrollable frame for settings
        settings_canvas = tk.Canvas(settings_frame, bg=self.BG_MID, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=settings_canvas.yview)
        scrollable_settings_frame = ttk.Frame(settings_canvas, style="Dark.TFrame")

        scrollable_settings_frame.bind(
            "<Configure>",
            lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
        )

        settings_canvas.create_window((0, 0), window=scrollable_settings_frame, anchor="nw")
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)

        settings_canvas.pack(side="left", fill="both", expand=True)
        settings_scrollbar.pack(side="right", fill="y")

        # Global settings variables
        self.global_settings_vars = {}
        self.global_settings_entries = {}

        # Parse and load settings
        def load_global_settings():
            try:
                # Make file writable for editing
                if os.path.exists(global_settings_path):
                    try:
                        import stat
                        os.chmod(global_settings_path, stat.S_IWRITE | stat.S_IREAD)
                    except Exception as e:
                        print(f"Warning: Could not make file writable: {e}")
                
                # Clear existing settings
                for widget in scrollable_settings_frame.winfo_children():
                    widget.destroy()
                self.global_settings_vars.clear()
                self.global_settings_entries.clear()

                # Default settings structure - simplified to only essential settings
                default_settings = {
                    "GraphicsQualityLevel": {"value": "1", "type": "choice", "options": ["1", "2", "3", "4", "5"], "description": "Graphics Quality (1=Low, 5=High)"},
                    "FramerateCap": {"value": "60", "type": "choice", "options": ["30", "60", "120", "144", "240", "0"], "description": "Framerate Limit (0=Unlimited)"},
                    "Transparency": {"value": "true", "type": "boolean", "description": "Enable Transparency Effects"},
                    "ReducedMotion": {"value": "false", "type": "boolean", "description": "Enable Reduced Motion"},
                    "FontSize": {"value": "14", "type": "choice", "options": ["12", "14", "16", "18", "20", "24"], "description": "Font Size"},
                    "MouseSensitivity": {"value": "1.0", "type": "float", "min": "0.1", "max": "5.0", "description": "Mouse Sensitivity (0.1-5.0)"},
                    "VREnabled": {"value": "false", "type": "boolean", "description": "Enable VR Mode"},
                }

                # Load existing settings from file if it exists
                if os.path.exists(global_settings_path):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(global_settings_path)
                        root = tree.getroot()
                        
                        # Load all existing settings
                        for setting in root.findall('.//Setting'):
                            name = setting.get('name')
                            value = setting.get('value', '')
                            if name and name in default_settings:
                                default_settings[name]['value'] = value
                                print(f"Loaded {name} = {value}")  # Debug output
                    except Exception as e:
                        print(f"Warning: Could not parse existing settings: {e}")

                # Create UI controls for each setting
                for setting_name, setting_info in default_settings.items():
                    setting_frame = ttk.Frame(scrollable_settings_frame, style="Dark.TFrame")
                    setting_frame.pack(fill="x", pady=3, padx=5)

                    # Setting name and description
                    name_label = ttk.Label(
                        setting_frame,
                        text=setting_name,
                        style="Dark.TLabel",
                        font=("Segoe UI", 10, "bold")
                    )
                    name_label.pack(anchor="w")

                    desc_label = ttk.Label(
                        setting_frame,
                        text=setting_info['description'],
                        style="Dark.TLabel",
                        font=("Segoe UI", 8),
                        foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888"
                    )
                    desc_label.pack(anchor="w", pady=(0, 2))

                    # Control frame
                    control_frame = ttk.Frame(setting_frame, style="Dark.TFrame")
                    control_frame.pack(fill="x", pady=(2, 5))

                    # Create appropriate control based on type
                    setting_type = setting_info['type']
                    current_value = setting_info['value']

                    if setting_type == "boolean":
                        var = tk.BooleanVar(value=current_value.lower() == "true")
                        checkbox = ttk.Checkbutton(
                            control_frame,
                            text="Enabled",
                            variable=var,
                            style="Dark.TCheckbutton"
                        )
                        checkbox.pack(side="left")
                        self.global_settings_vars[setting_name] = var

                    elif setting_type == "choice":
                        var = tk.StringVar(value=current_value)
                        combo = ttk.Combobox(
                            control_frame,
                            textvariable=var,
                            values=setting_info['options'],
                            state="readonly",
                            style="Dark.TCombobox",
                            width=12
                        )
                        combo.pack(side="left", fill="x", expand=True)
                        self.global_settings_vars[setting_name] = var

                    elif setting_type in ["integer", "float"]:
                        var = tk.StringVar(value=current_value)
                        entry = ttk.Entry(
                            control_frame,
                            textvariable=var,
                            style="Dark.TEntry",
                            width=10
                        )
                        entry.pack(side="left")
                        
                        # Add validation
                        if setting_type == "integer":
                            vcmd = (self.root.register(lambda text: text == "" or text.lstrip('-').isdigit()), "%P")
                            entry.configure(validate="key", validatecommand=vcmd)
                        else:  # float
                            vcmd = (self.root.register(lambda text: text == "" or text.replace('.', '', 1).lstrip('-').isdigit()), "%P")
                            entry.configure(validate="key", validatecommand=vcmd)
                        
                        self.global_settings_vars[setting_name] = var
                        self.global_settings_entries[setting_name] = entry

                    # Add min/max labels for numeric types
                    if setting_type in ["integer", "float"] and 'min' in setting_info and 'max' in setting_info:
                        range_label = ttk.Label(
                            control_frame,
                            text=f"({setting_info['min']} - {setting_info['max']})",
                            style="Dark.TLabel",
                            font=("Segoe UI", 8),
                            foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888"
                        )
                        range_label.pack(side="left", padx=(5, 0))

            except Exception as e:
                messagebox.showerror("Error Loading Settings", f"Failed to load global settings: {str(e)}")

        # Save the settings
        def save_global_settings():
            try:
                import xml.etree.ElementTree as ET
                from xml.dom import minidom

                # Load existing XML file if it exists, otherwise create new structure
                if os.path.exists(global_settings_path):
                    try:
                        tree = ET.parse(global_settings_path)
                        root = tree.getroot()
                    except Exception as e:
                        print(f"Warning: Could not parse existing XML, creating new: {e}")
                        root = ET.Element("Settings")
                else:
                    root = ET.Element("Settings")
                
                # Update only the settings we have controls for
                for setting_name, var in self.global_settings_vars.items():
                    # Convert boolean values to strings for XML
                    value = var.get()
                    if isinstance(value, bool):
                        value = "true" if value else "false"
                    value_str = str(value)
                    
                    print(f"Saving {setting_name} = {value_str} (type: {type(value)})")  # Debug output
                    
                    # Update Settings section (our custom settings)
                    existing_setting = root.find(f".//Setting[@name='{setting_name}']")
                    if existing_setting is not None:
                        existing_setting.set("value", value_str)
                    else:
                        setting_elem = ET.SubElement(root, "Setting")
                        setting_elem.set("name", setting_name)
                        setting_elem.set("value", value_str)
                    
                    # Also update Properties section if it exists (Roblox's main settings)
                    properties = root.find(".//Properties")
                    if properties is not None:
                        # Find the setting in Properties section
                        prop_setting = properties.find(f".//*[@name='{setting_name}']")
                        if prop_setting is not None:
                            # Handle different element types
                            if prop_setting.tag == "int":
                                prop_setting.text = value_str
                            elif prop_setting.tag == "bool":
                                prop_setting.text = value_str.lower()
                            elif prop_setting.tag == "float":
                                prop_setting.text = value_str
                            elif prop_setting.tag == "token":
                                prop_setting.text = value_str
                            elif prop_setting.tag == "string":
                                prop_setting.text = value_str
                            print(f"Updated Properties section {setting_name} = {value_str}")
                
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
                
                messagebox.showinfo("Success", f"Global settings saved successfully!\n\nBackup created at: {global_settings_path}.backup\n\nFile is now read-only.")
            except Exception as e:
                messagebox.showerror("Error Saving Settings", f"Failed to save global settings: {str(e)}")

        # Reset to defaults
        def reset_to_defaults():
            if messagebox.askyesno("Confirm Reset", "This will reset all settings to their default values. Continue?"):
                load_global_settings()
                messagebox.showinfo("Reset Complete", "Settings have been reset to defaults. Click Save to apply.")

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
            text="Close",
            style="Dark.TButton",
            command=self.global_settings_window.destroy
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Load initial settings
        load_global_settings()

    def open_fastflags_editor(self):
        """Open the FastFlags editor window."""
        # Check if window already exists and focus it
        if hasattr(self, 'fastflags_window') and self.fastflags_window and self.fastflags_window.winfo_exists():
            self.fastflags_window.deiconify()
            self.fastflags_window.lift()
            self.fastflags_window.focus_force()
            return

        self.fastflags_window = tk.Toplevel(self.root)
        self.fastflags_window.title("FastFlags Editor")
        self.fastflags_window.geometry("700x600")
        self.fastflags_window.minsize(600, 500)
        self.fastflags_window.configure(bg=self.BG_DARK)
        self.fastflags_window.resizable(True, True)
        
        self.fastflags_window.transient(self.root)
        self.fastflags_window.grab_set()
        self.register_toplevel(self.fastflags_window)
        
        if self.settings.get("enable_topmost", False):
            self.fastflags_window.attributes("-topmost", True)

        # Main frame
        main_frame = ttk.Frame(self.fastflags_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # Initialize FastFlags manager with currently selected version
        selected_version = self.version_var.get()
        version_path = None
        
        if selected_version != "Latest Version" and selected_version in self.version_options:
            version_path = self.version_options[selected_version]
        
        fastflags_manager = FastFlagsManager(version_path=version_path)

        # Title with version info
        version_info = ""
        if version_path:
            version_name = os.path.basename(version_path)
            version_info = f" - {version_name}"
        
        title_label = ttk.Label(
            main_frame,
            text=f"Roblox FastFlags Editor{version_info}",
            style="Dark.TLabel",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 10))

        # Version path info
        if version_path:
            path_label = ttk.Label(
                main_frame,
                text=f"Editing FastFlags for: {version_path}",
                style="Dark.TLabel",
                font=("Segoe UI", 9),
                foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888"
            )
            path_label.pack(anchor="w", pady=(0, 10))

        # Preset section
        preset_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        preset_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            preset_frame,
            text="Quick Presets:",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 5))

        preset_buttons_frame = ttk.Frame(preset_frame, style="Dark.TFrame")
        preset_buttons_frame.pack(fill="x")

        # Create preset buttons
        preset_var = tk.StringVar()
        presets = fastflags_manager.get_available_presets()
        
        for i, preset in enumerate(presets):
            if i % 3 == 0 and i > 0:
                preset_buttons_frame = ttk.Frame(preset_frame, style="Dark.TFrame")
                preset_buttons_frame.pack(fill="x", pady=(5, 0))
            
            def apply_preset_func(p_name=preset):
                if fastflags_manager.apply_preset(p_name):
                    messagebox.showinfo("Success", f"Applied '{p_name}' preset")
                    refresh_current_flags()
                else:
                    messagebox.showerror("Error", f"Failed to apply '{p_name}' preset")

            ttk.Button(
                preset_buttons_frame,
                text=preset,
                style="Dark.TButton",
                command=apply_preset_func
            ).pack(side="left", padx=(0, 5), fill="x", expand=True)

        # Current flags section
        flags_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        flags_frame.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(
            flags_frame,
            text="Current FastFlags:",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 5))

        # Create scrollable frame for flags
        flags_canvas = tk.Canvas(flags_frame, bg=self.BG_MID, highlightthickness=0)
        flags_scrollbar = ttk.Scrollbar(flags_frame, orient="vertical", command=flags_canvas.yview)
        scrollable_frame = ttk.Frame(flags_canvas, style="Dark.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: flags_canvas.configure(scrollregion=flags_canvas.bbox("all"))
        )

        flags_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        flags_canvas.configure(yscrollcommand=flags_scrollbar.set)

        flags_canvas.pack(side="left", fill="both", expand=True)
        flags_scrollbar.pack(side="right", fill="y")

        # Custom flag entry
        custom_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        custom_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            custom_frame,
            text="Add Custom Flag:",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 5))

        entry_frame = ttk.Frame(custom_frame, style="Dark.TFrame")
        entry_frame.pack(fill="x")

        flag_name_var = tk.StringVar()
        flag_value_var = tk.StringVar()

        ttk.Entry(
            entry_frame,
            textvariable=flag_name_var,
            style="Dark.TEntry"
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ttk.Entry(
            entry_frame,
            textvariable=flag_value_var,
            style="Dark.TEntry",
            width=15
        ).pack(side="left", padx=(0, 5))

        def add_custom_flag():
            flag_name = flag_name_var.get().strip()
            flag_value = flag_value_var.get().strip()
            
            if not flag_name or not flag_value:
                messagebox.showerror("Error", "Please enter both flag name and value")
                return
            
            # Validate flag name with detailed error message
            is_valid_name, name_error = fastflags_manager.validate_flag_name(flag_name)
            if not is_valid_name:
                messagebox.showerror("Invalid Flag Name", name_error)
                return
            
            # Validate flag value with detailed error message
            is_valid_value, value_error = fastflags_manager.validate_flag_value(flag_value)
            if not is_valid_value:
                messagebox.showerror("Invalid Flag Value", value_error)
                return
            
            if fastflags_manager.set_flag(flag_name, flag_value):
                messagebox.showinfo("Success", f"Set {flag_name} = {flag_value}")
                flag_name_var.set("")
                flag_value_var.set("")
                refresh_current_flags()
            else:
                messagebox.showerror("Error", f"Failed to set {flag_name}")

        ttk.Button(
            entry_frame,
            text="Add",
            style="Dark.TButton",
            command=add_custom_flag
        ).pack(side="left")

        # Action buttons
        action_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        action_frame.pack(fill="x", pady=(10, 0))

        def backup_flags():
            if fastflags_manager.backup_fast_flags():
                messagebox.showinfo("Success", "FastFlags backed up successfully")
            else:
                messagebox.showerror("Error", "Failed to backup FastFlags")

        def restore_flags():
            if fastflags_manager.restore_fast_flags():
                messagebox.showinfo("Success", "FastFlags restored successfully")
                refresh_current_flags()
            else:
                messagebox.showerror("Error", "Failed to restore FastFlags")

        def reset_flags():
            if messagebox.askyesno("Confirm Reset", "This will reset all FastFlags to default. Continue?"):
                if fastflags_manager.reset_to_default():
                    messagebox.showinfo("Success", "FastFlags reset to default")
                    refresh_current_flags()
                else:
                    messagebox.showerror("Error", "Failed to reset FastFlags")

        ttk.Button(
            action_frame,
            text="Backup",
            style="Dark.TButton",
            command=backup_flags
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            action_frame,
            text="Restore",
            style="Dark.TButton",
            command=restore_flags
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            action_frame,
            text="Reset All",
            style="Dark.TButton",
            command=reset_flags
        ).pack(side="left")

        ttk.Button(
            action_frame,
            text="Close",
            style="Dark.TButton",
            command=self.fastflags_window.destroy
        ).pack(side="right")

        def refresh_current_flags():
            # Clear existing flags display
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            
            # Load and display current flags
            current_flags = fastflags_manager.load_fast_flags()
            
            if not current_flags:
                ttk.Label(
                    scrollable_frame,
                    text="No FastFlags set",
                    style="Dark.TLabel",
                    font=("Segoe UI", 10),
                    foreground=self.FG_MUTED if hasattr(self, 'FG_MUTED') else "#888888"
                ).pack(anchor="w", pady=5)
                return
            
            for flag_name, flag_value in current_flags.items():
                flag_frame = ttk.Frame(scrollable_frame, style="Dark.TFrame")
                flag_frame.pack(fill="x", pady=2)
                
                ttk.Label(
                    flag_frame,
                    text=f"{flag_name}:",
                    style="Dark.TLabel",
                    font=("Segoe UI", 9)
                ).pack(side="left")
                
                ttk.Label(
                    flag_frame,
                    text=str(flag_value),
                    style="Dark.TLabel",
                    font=("Segoe UI", 9),
                    foreground=self.FG_ACCENT
                ).pack(side="left", padx=(5, 0))
                
                ttk.Button(
                    flag_frame,
                    text="Remove",
                    style="Dark.TButton",
                    command=lambda name=flag_name: remove_flag(name)
                ).pack(side="right", padx=(5, 0))

        def remove_flag(flag_name):
            if fastflags_manager.remove_flag(flag_name):
                refresh_current_flags()
            else:
                messagebox.showerror("Error", f"Failed to remove {flag_name}")

        # Handle window close
        def on_closing():
            try:
                self.fastflags_window.destroy()
                self.fastflags_window = None
            except:
                pass

        self.fastflags_window.protocol("WM_DELETE_WINDOW", on_closing)

        # Initial load of current flags
        refresh_current_flags()

        # Center window
        self.fastflags_window.update_idletasks()
        width = self.fastflags_window.winfo_reqwidth()
        height = self.fastflags_window.winfo_reqheight()
        x = (self.fastflags_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.fastflags_window.winfo_screenheight() // 2) - (height // 2)
        self.fastflags_window.geometry(f"{width}x{height}+{x}+{y}")
        self.fastflags_window.deiconify()