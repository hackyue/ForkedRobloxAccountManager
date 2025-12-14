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
import requests
import json
import math
import csv
import atexit
import platform
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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


ROBLOX_CLIENT_SETTINGS_URL = "https://clientsettings.roblox.com/v2/client-version/WindowsPlayer"
ROBLOX_DEPLOY_HISTORY_URL = "https://setup.rbxcdn.com/DeployHistory.txt"
ROBLOX_DOWNLOAD_VARIANTS = [
    "https://setup.rbxcdn.com/{version}-WindowsPlayer.zip",
    "https://setup.rbxcdn.com/{version}-RobloxApp.zip",
    "https://setup.rbxcdn.com/{version}-WindowsStudio.zip",
]

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
        self.APP_VERSION = "2.3.5"
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
        
        self.root.title("FRAM v2.3.5 - made by evanovar - modified by hackyue")
        self.root.geometry("600x600")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(True, True)
        self.root.minsize(600, 700)  # Note to self, this shit so ass
        
        self.data_folder = "AccountManagerData"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        self.settings_file = os.path.join(self.data_folder, "ui_settings.json")
        self.load_settings()
        
        self.multi_roblox_handle = None
        self.console_output = get_console_output_buffer()
        self.console_window = ConsoleOutputWindow(self, self.console_output)
        self.account_list_drag_data = {
            "start_index": None,
            "drop_index": None,
            "start_username": None,
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
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=2)  

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

        ttk.Button(right_frame, text="Join Place ID", style="Dark.TButton", command=self.launch_game).pack(fill="x", pady=(0, 10))
        
        ttk.Label(right_frame, text="Recent games", style="Dark.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        
        game_list_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        game_list_frame.pack(fill="both", expand=True)
        
        self.game_list = tk.Listbox(
            game_list_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            selectbackground=self.FG_ACCENT,
            highlightthickness=0,
            border=0,
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
        ttk.Button(action_frame, text="Refresh List", style="Dark.TButton", command=self.refresh_accounts).pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Auto-Arrange Clients", style="Dark.TButton", command=self.auto_arrange_clients).pack(fill="x", pady=2)

        self.add_account_dropdown = None
        self.add_account_dropdown_visible = False
        
        bottom_frame = ttk.Frame(self.root, style="Dark.TFrame")
        bottom_frame.pack(fill="x", padx=10, pady=(5, 10), anchor='s')

        self.add_account_split_btn = ttk.Button(
            bottom_frame,
            text="Add Account",
            style="Dark.TButton",
        )
        self.add_account_split_btn.pack(side="left", fill="both", expand=True, padx=(0, 2))
        self.add_account_split_btn.bind("<Button-1>", self.on_add_account_split_click)

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

        self.root.bind("<Button-1>", self.hide_dropdown_on_click_outside)
        self.root.bind("<Configure>", self.on_root_configure)
        self.refresh_accounts()
        self.refresh_game_list()
        self.update_game_name()


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

        if getattr(self, "add_account_dropdown", None):
            self.add_account_dropdown.configure(bg=self.BG_MID, highlightbackground=self.BORDER_COLOR)
            for widget in self.add_account_dropdown.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.configure(
                        bg=self.BG_MID,
                        fg=self.FG_TEXT,
                        activebackground=self.HOVER_BG,
                        activeforeground=self.FG_TEXT,
                        bd=0
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

    def initialize_multi_roblox(self):
        """Initialize Multi Roblox on startup if enabled in settings"""
        if self.settings.get("enable_multi_roblox", False):
            success = self.enable_multi_roblox()
            if not success:
                self.settings["enable_multi_roblox"] = False
                self.save_settings()

    def build_main_menu(self):
        """Create the main menu bar and attach quick actions."""
        if getattr(self, "menu_bar_frame", None):
            self.menu_bar_frame.destroy()

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
        if self.installer_menu is None:
            return

        self.installer_menu.delete(0, tk.END)
        versions = self.get_available_roblox_versions(limit=5)

        if not versions:
            self.installer_menu.add_command(label="No versions found", state="disabled")
            return

        for entry in versions:
            display_text = self.format_version_display(entry)
            self.installer_menu.add_command(
                label=display_text,
                command=lambda v=entry["version"]: self.use_installer_version(v)
            )

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
            if not self.installer_dialog_state:
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

    def _installer_download_thread(self, version, client, target_dir):
        """Background worker that downloads and extracts the requested version."""
        temp_file = None
        response = None
        download_url = None

        try:
            last_error = None
            for template in ROBLOX_DOWNLOAD_VARIANTS:
                url = template.format(version=version)
                try:
                    response = requests.get(
                        url,
                        stream=True,
                        timeout=30,
                        headers=ROBLOX_DOWNLOAD_HEADERS,
                    )
                    response.raise_for_status()
                    download_url = url
                    break
                except requests.HTTPError as exc:
                    last_error = exc
                except requests.RequestException as exc:
                    last_error = exc

            if response is None:
                error_message = (
                    f"Failed to download {version}. "
                    f"Last error: {last_error}" if last_error else "Download failed."
                )
                self._report_installer_error(error_message)
                return

            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            first_chunk = None

            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                temp_file = tmp.name
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if first_chunk is None:
                        first_chunk = chunk
                        if not self._looks_like_zip_header(first_chunk):
                            preview = first_chunk.decode("utf-8", errors="ignore").strip()
                            if not preview:
                                preview = "Download returned an unexpected file type."
                            tmp.close()
                            try:
                                os.remove(temp_file)
                            except OSError:
                                pass
                            self._report_installer_error(preview)
                            return
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    self._report_installer_progress(downloaded, total_size)

            self._report_installer_status("Download complete. Extracting files...", force_progress=100)

            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            with zipfile.ZipFile(temp_file, "r") as zip_ref:
                zip_ref.extractall(target_dir)

            self._report_installer_success(client, target_dir)

        except Exception as exc:
            self._report_installer_error(str(exc))
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    @staticmethod
    def _looks_like_zip_header(first_bytes):
        """Return True if the initial bytes look like a ZIP archive."""
        if not first_bytes:
            return False
        signatures = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
        return any(first_bytes.startswith(sig) for sig in signatures)

    def _report_installer_progress(self, downloaded, total_size):
        """Update the progress bar based on bytes downloaded."""
        if total_size <= 0:
            message = f"Downloading... {downloaded / (1024 * 1024):.1f} MB"
            percent = 0
        else:
            percent = min(downloaded / total_size * 100, 100)
            message = (
                f"Downloading... "
                f"{downloaded / (1024 * 1024):.1f} / {total_size / (1024 * 1024):.1f} MB"
            )
        self._report_installer_status(message, percent)

    def _report_installer_status(self, message, percent=None, force_progress=None):
        """Post a status/progress update back to the UI thread."""
        def update():
            state = self.installer_dialog_state
            if not state:
                return
            if percent is not None:
                state["progress_var"].set(percent)
            if force_progress is not None:
                state["progress_var"].set(force_progress)
            if message:
                state["status_var"].set(message)
        self.root.after(0, update)

    def _report_installer_success(self, client, target_dir):
        """Handle success: notify user, refresh versions, re-enable controls."""
        def finalize():
            state = self.installer_dialog_state
            if not state:
                return
            state["download_thread"] = None
            state["close_button"].configure(state="normal", text="Close")
            state["download_button"].configure(state="normal", text="Download Again")
            state["status_var"].set(
                f"Download complete! Files extracted to:\n{target_dir}"
            )
            state["progress_var"].set(100)
            self.show_success_message(
                f"{client['name']} updated!",
                title="Download Complete"
            )
            self.load_roblox_versions()
        self.root.after(0, finalize)

    def _report_installer_error(self, error_message):
        """Reset controls and show an error message after a failure."""
        def finalize():
            state = self.installer_dialog_state
            if not state:
                return
            state["download_thread"] = None
            state["download_button"].configure(state="normal")
            state["close_button"].configure(state="normal", text="Close")
            state["status_var"].set(f"Error: {error_message}")
            messagebox.showerror("Roblox Installer", f"Download failed:\n{error_message}")
        self.root.after(0, finalize)

    def toggle_add_account_dropdown(self):
        """Toggle the Add Account dropdown menu"""
        self.add_account_dropdown_visible = not self.add_account_dropdown_visible
        if self.add_account_dropdown_visible:
            self.show_add_account_dropdown()
        else:
            self.hide_add_account_dropdown()
    
    def on_add_account_split_click(self, event):
        """Handle clicks on the unified split button: left area adds account, right area opens dropdown."""
        try:
            width = event.widget.winfo_width()
        except Exception:
            width = 0
        arrow_zone = 24
        if event.x >= max(0, width - arrow_zone):
            self.toggle_add_account_dropdown()
        else:
            self.add_account()
        return "break"
    
    def show_add_account_dropdown(self):
        """Show the Add Account dropdown menu"""
        if self.add_account_dropdown is not None:
            self.add_account_dropdown.destroy()
        
        self.add_account_dropdown = tk.Toplevel(self.root)
        self.add_account_dropdown.overrideredirect(True)
        self.add_account_dropdown.configure(bg=self.BG_MID, highlightthickness=1, highlightbackground="white")
        
        self.position_add_account_dropdown()
        
        import_cookie_btn = tk.Button(
            self.add_account_dropdown,
            text="Import Cookie",
            anchor="w",
            relief="flat",
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            activebackground=self.HOVER_BG,
            activeforeground=self.FG_TEXT,
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
            command=lambda: [self.hide_add_account_dropdown(), self.import_cookie()]
        )
        import_cookie_btn.pack(fill="x", padx=2, pady=1)
        
        javascript_btn = tk.Button(
            self.add_account_dropdown,
            text="Javascript",
            anchor="w",
            relief="flat",
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            activebackground=self.HOVER_BG,
            activeforeground=self.FG_TEXT,
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
            command=lambda: [self.hide_add_account_dropdown(), self.javascript_import()]
        )
        javascript_btn.pack(fill="x", padx=2, pady=1)
        
        self.position_add_account_dropdown()
        
        if self.settings.get("enable_topmost", False):
            self.add_account_dropdown.attributes("-topmost", True)
        
        self.add_account_dropdown.bind("<FocusOut>", lambda e: self.hide_add_account_dropdown())

    def position_add_account_dropdown(self):
        """Position the dropdown right under the split button and match its width."""
        try:
            if self.add_account_dropdown is None or not self.add_account_dropdown_visible:
                return
            self.root.update_idletasks()
            x = self.add_account_split_btn.winfo_rootx()
            y = self.add_account_split_btn.winfo_rooty() + self.add_account_split_btn.winfo_height()
            width = self.add_account_split_btn.winfo_width()
            req_h = self.add_account_dropdown.winfo_reqheight()
            self.add_account_dropdown.geometry(f"{width}x{req_h}+{x}+{y}")
            if self.settings.get("enable_topmost", False):
                self.add_account_dropdown.attributes("-topmost", True)
        except Exception:
            pass

    def on_root_configure(self, event=None):
        """Called when the main window moves/resizes; keep dropdown attached."""
        if self.add_account_dropdown_visible and self.add_account_dropdown is not None:
            self.position_add_account_dropdown()

    def hide_add_account_dropdown(self):
        """Hide the Add Account dropdown menu"""
        if self.add_account_dropdown is not None:
            self.add_account_dropdown.destroy()
            self.add_account_dropdown = None
        self.add_account_dropdown_visible = False
    
    def is_child_of(self, child, parent):
        """Check if a widget is a child of another widget"""
        while child is not None:
            if child == parent:
                return True
            child = child.master
        return False
    
    def hide_dropdown_on_click_outside(self, event):
        """Hide dropdown when clicking outside of it"""
        widget = event.widget
        if self.add_account_dropdown_visible and self.add_account_dropdown is not None:
            if not self.is_child_of(widget, self.add_account_split_btn):
                try:
                    if not self.is_child_of(widget, self.add_account_dropdown):
                        self.hide_add_account_dropdown()
                except:
                    self.hide_add_account_dropdown()


    def load_roblox_versions(self):
        """Load available Roblox versions from the standard Roblox Versions directory"""
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

            self.version_dropdown['values'] = display_values or ["Latest Version"]
        except Exception as e:
            print(f"Error loading Roblox versions: {e}")
            self.version_options = {"Latest Version": None}
            self.version_dropdown['values'] = ["Latest Version"]

        self.refresh_installer_menu()

    def get_local_roblox_versions(self, limit=None):
        """Return Roblox version directories from default, Bloxstrap, and Fishstrap installs."""
        sources = [
            {
                "name": "Roblox",
                "base": os.path.expandvars(r"%LOCALAPPDATA%\Roblox\Versions")
            },
            {
                "name": "Bloxstrap",
                "base": os.path.expandvars(r"%LOCALAPPDATA%\Bloxstrap\Versions")
            },
            {
                "name": "Fishstrap",
                "base": os.path.expandvars(r"%LOCALAPPDATA%\Fishstrap\Versions")
            },
            {
                "name": "Voidstrap",
                "base": os.path.expandvars(r"%LOCALAPPDATA%\Voidstrap\RblxVersions")
            }
        ]

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
        for username, data in self.manager.accounts.items():
            note = data.get('note', '') if isinstance(data, dict) else ''
            display_text = f"{username}"
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
        if self._drag_modifiers_active(event):
            self._reset_drag_data()
            return
        index = self.account_list.nearest(event.y)
        if index < 0 or index >= self.account_list.size():
            return "break"
        self.account_list.selection_clear(0, tk.END)
        self.account_list.selection_set(index)
        display_text = self.account_list.get(index)
        self.account_list_drag_data.update({
            "start_index": index,
            "drop_index": index,
            "start_username": self._extract_username(display_text),
            "is_dragging": False
        })
        return "break"

    def on_account_drag_motion(self, event):
        data = self.account_list_drag_data
        if data["start_index"] is None:
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

    @staticmethod
    def _drag_modifiers_active(event):

        modifiers_mask = 0x1 | 0x4 | 0x8
        return bool(event.state & modifiers_mask)

    def _reset_drag_data(self):
        self.account_list_drag_data = {
            "start_index": None,
            "drop_index": None,
            "start_username": None,
            "is_dragging": False
        }

    def _get_drop_index_from_event(self, y_coord):
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
        usernames = [self._extract_username(text) for text in self.account_list.get(0, tk.END)]
        if not usernames:
            return
        drop_index = max(0, min(drop_index, len(usernames)))
        entry = usernames.pop(start_index)
        if drop_index > start_index:
            drop_index -= 1
        usernames.insert(drop_index, entry)
        self.manager.reorder_accounts(usernames)
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
                self.root.after(0, lambda: self._add_account_complete(success))
            except Exception as e:
                self.root.after(0, lambda: self._add_account_error(str(e)))
        
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
        messagebox.showerror("Error", f"Failed to add account: {error_msg}")
    
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
    
    def javascript_import_code(self, amount, website):
        """
        Get Javascript code to execute and launch Chrome instances
        """
        js_window = tk.Toplevel(self.root)
        js_window.title("Javascript Import - Code")
        js_window.geometry("500x300")
        js_window.configure(bg=self.BG_DARK)
        js_window.resizable(False, False)
        
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        x = main_x + (main_width - 500) // 2
        y = main_y + (main_height - 300) // 2
        js_window.geometry(f"500x300+{x}+{y}")
        
        if self.settings.get("enable_topmost", False):
            js_window.attributes("-topmost", True)
        
        js_window.transient(self.root)
        self.register_toplevel(js_window)
        
        main_frame = ttk.Frame(js_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Javascript:",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 10))
        
        js_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        js_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        js_text = tk.Text(
            js_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Consolas", 9),
            height=10,
            wrap="word"
        )
        js_text.pack(side="left", fill="both", expand=True)
        self.register_themable_text_widget(js_text)
        
        js_scrollbar = ttk.Scrollbar(js_frame, command=js_text.yview)
        js_scrollbar.pack(side="right", fill="y")
        js_text.config(yscrollcommand=js_scrollbar.set)
        js_text.focus_set()
        
        def execute_javascript():
            javascript = js_text.get("1.0", "end-1c").strip()
            if not javascript:
                messagebox.showwarning("Missing Information", "Please enter Javascript code.")
                return
            js_window.destroy()
            self.launch_javascript_browsers(amount, website, javascript)
        
        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x")
        
        ttk.Button(
            button_frame,
            text="Yes",
            style="Dark.TButton",
            command=execute_javascript
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            style="Dark.TButton",
            command=js_window.destroy
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
                windows.append(hwnd)
                seen.add(hwnd)
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
        username = self.get_selected_username()
        if not username:
            return
        is_valid = self.manager.validate_account(username)
        if is_valid:
            messagebox.showinfo("Validation", f"Account '{username}' is valid!")
        else:
            messagebox.showwarning("Validation", f"Account '{username}' is invalid or expired.")
    
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

        version_label = ttk.Label(
            main_frame,
            text=f"Version: {self.APP_VERSION}",
            style="Dark.TLabel",
            font=("Segoe UI", 9)
        )
        version_label.pack(anchor="e", pady=(6, 0))

        ttk.Button(
            main_frame,
            text="Console Output",
            style="Dark.TButton",
            command=self.open_console_output
        ).pack(fill="x", pady=(8, 0))

    def open_console_output(self):
        """Open or focus the console output window."""
        if self.console_window:
            self.console_window.show()

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

        def worker(selected_usernames, delay_seconds):
            success_count = 0
            for idx, uname in enumerate(selected_usernames):
                try:
                    if self.manager.launch_home_app(uname, enable_debug=debug_enabled):
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

        game_id = self.place_entry.get().strip()
        private_server = self.private_server_entry.get().strip()
        

        selected_version_label = self.version_var.get()
        version_path = None
        version_path = self.version_options.get(selected_version_label)

        if not game_id:
            messagebox.showwarning("Missing Information", "Please enter a Place ID.")
            return

        if self.settings.get("confirm_before_launch", True) and len(usernames) > 1:
            confirm = messagebox.askyesno(
                "Confirm Launch",
                f"Are you sure you want to launch {len(usernames)} accounts?"
            )
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
                else:
                    messagebox.showerror("Error", "Failed to launch Roblox.")

            self.root.after(0, on_done)

        threading.Thread(
            target=worker,
            args=(usernames, game_id, private_server, version_path, debug_enabled, launch_delay),
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
                if self.multi_roblox_handle.get('file'):
                    try:
                        self.multi_roblox_handle['file'].close()
                    except:
                        pass
                
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
        theme_var = tk.StringVar(value=self.settings.get("selected_theme", self.theme_name))
        custom_launcher_var = tk.BooleanVar(value=self.settings.get("enable_custom_launcher", False))
        custom_launcher_path_var = tk.StringVar(value=self.settings.get("custom_launcher_path", ""))
        custom_launcher_player_var = tk.BooleanVar(value=self.settings.get("custom_launcher_requires_player", False))
        auto_arrange_scope_var = tk.StringVar(value=self.settings.get("auto_arrange_scope", "both"))
        
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
        
        tab_var = tk.StringVar(value="ram")
        tab_buttons = {}
        
        tab_bar = tk.Frame(main_frame, bg=self.BG_DARK)
        tab_bar.pack(fill="x", pady=(0, 8))
        
        def set_active_tab(tab_name):
            tab_var.set(tab_name)
            if tab_name == "ram":
                ram_tab.tkraise()
            else:
                roblox_tab.tkraise()
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
                padx=14,
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
        
        create_tab_button("RAM Settings", "ram")
        create_tab_button("Roblox Client", "roblox")
        
        content_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        content_frame.pack(fill="both", expand=True)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        ram_tab = ttk.Frame(content_frame, style="Dark.TFrame")
        ram_tab.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            ram_tab,
            text="Interface & Notifications",
            style="Dark.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))
        
        ttk.Checkbutton(
            ram_tab,
            text="Enable Topmost",
            variable=topmost_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_topmost", topmost_var)
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            ram_tab,
            text="Multi Select (Ctrl + Click)",
            variable=multi_select_var,
            style="Dark.TCheckbutton",
            command=on_multi_select_toggle
        ).pack(anchor="w", pady=2)
        
        ttk.Checkbutton(
            ram_tab,
            text="Enable Debug Logging",
            variable=debug_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_debug_logging", debug_var)
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            ram_tab,
            text="Disable Success Popups",
            variable=disable_success_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("disable_success_popups", disable_success_var)
        ).pack(anchor="w", pady=2)

        ttk.Label(
            ram_tab,
            text="Theme",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(10, 2))

        theme_combo = ttk.Combobox(
            ram_tab,
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
            ram_tab,
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
                ram_tab,
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
                ram_tab,
                text="Only one monitor detected. Auto-arrange will use the available screen.",
                style="Dark.TLabel",
                wraplength=320
            ).pack(anchor="w", pady=(0, 4))

        roblox_tab = ttk.Frame(content_frame, style="Dark.TFrame")
        roblox_tab.grid(row=0, column=0, sticky="nsew")

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

        settings_window.update_idletasks()
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