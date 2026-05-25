"""
UI Module for Roblox Account Manager
Contains the main AccountManagerUI class
"""

import os
import re
import sys
import io
import importlib.util
import traceback
import tempfile
import zipfile
import shutil
import hashlib
import requests
import json
import math
import csv
import base64
import atexit
import platform
import time
import subprocess
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
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
    import pywintypes
    import win32api
    import win32con
    import win32gui
    import webbrowser
    import win32process
else:
    pywintypes = None
    win32api = win32con = win32gui = win32process = None

from classes.roblox_api import RobloxAPI
from classes.fastflags import FastFlagsManager
from classes.browser_extensions import BrowserExtension, BrowserExtensionError, BrowserExtensionManager


ROBLOX_CLIENT_SETTINGS_URL = "https://clientsettings.roblox.com/v2/client-version/WindowsPlayer"
WEAO_VERSIONS_CURRENT_PATH = "/api/versions/current"
WEAO_VERSIONS_FUTURE_PATH = "/api/versions/future"
WEAO_VERSIONS_PAST_PATH = "/api/versions/past"
WEAO_API_HOSTS = ("weao.xyz", "whatexpsare.online", "weao.gg", "whatexploitsaretra.sh")
WEAO_API_USER_AGENT = "WEAO-3PService"


DISCORD_SERVER_URL = "https://discord.gg/SpMTxg8YjJ"
SERVER_REGION_ANY_LABEL = "Any"
SERVER_REGION_CHOICES: tuple[tuple[str, str], ...] = (
    ("", SERVER_REGION_ANY_LABEL),
    ("united states", "United States"),
    ("us east", "US East"),
    ("us central", "US Central"),
    ("us west", "US West"),
    ("canada", "Canada"),
    ("brazil", "Brazil"),
    ("europe", "Europe"),
    ("united kingdom", "United Kingdom"),
    ("germany", "Germany"),
    ("france", "France"),
    ("netherlands", "Netherlands"),
    ("singapore", "Singapore"),
    ("japan", "Japan"),
    ("hong kong", "Hong Kong"),
    ("south korea", "South Korea"),
    ("india", "India"),
    ("australia", "Australia"),
)
SERVER_REGION_LABEL_BY_VALUE: dict[str, str] = dict(SERVER_REGION_CHOICES)
SERVER_REGION_VALUE_BY_LABEL: dict[str, str] = {
    label: value
    for value, label in SERVER_REGION_CHOICES
}


"""Assets URLs (can be updated remotely for dynamic content without needing app updates)"""
DISCORD_LOGO_URL = (
    "https://raw.githubusercontent.com/hackyue/FRAMAssets/refs/heads/main/AppIcons/Discord.png"
)
ADDITIONAL_THEMES_URL = (
    "https://raw.githubusercontent.com/hackyue/FRAMAssets/refs/heads/main/Themes/themes.json"
)
FRAM_ASSETS_ADDONS_WEB_URL = "https://github.com/hackyue/FRAMAssets/tree/main/Addons"
FRAM_ASSETS_ADDONS_API_URL = "https://api.github.com/repos/hackyue/FRAMAssets/contents/Addons"
CHROME_FOR_TESTING_DOWNLOADS_URL = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
BROWSER_DISPLAY_NAMES: dict[str, str] = {
    "chrome": "Chrome",
    "firefox": "Firefox",
    "waterfox": "Waterfox",
    "chromium": "Chromium",
}
SUPPORTED_BROWSER_PREFERENCES: set[str] = {"auto", *BROWSER_DISPLAY_NAMES.keys()}
GECKO_BROWSER_NAMES: set[str] = {"firefox", "waterfox"}












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
INSTALLER_VERSION_ENTRY_LIMIT = 3

# Win32 flags used for native process/window detection and force-resizing Roblox windows.
TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH_CHARS = 260
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_NOSENDCHANGING = 0x0400
GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
INVALID_ACCOUNT_SYMBOL = "\u26A0"
AUTO_REJOIN_SYMBOL = "\u21BB"
ACTIVE_CLIENT_SYMBOL = "\u2B24"
SETTINGS_SYMBOL = "\u2699"
GDI_PLUS_OK = 0
DISCORD_LOG_MIRROR_SEND_DEBOUNCE_MS = 250
CLIENT_TITLE_RENAME_PID_WAIT_SECONDS = 12.0
CLIENT_TITLE_RENAME_PID_POLL_SECONDS = 0.4
CLIENT_TITLE_RENAME_MAX_ATTEMPTS = 2
CLIENT_TITLE_RENAME_DELAY_SECONDS = 0.5
CLIENT_TITLE_RENAME_STABLE_ATTEMPTS = 1
ICON_FETCH_QUEUE_MAXSIZE = 512
ICON_FETCH_BATCH_SIZE = 50
ICON_FETCH_BATCH_WAIT_SECONDS = 0.12
ICON_FETCH_RETRY_MS = 250
PYWIN32_ERROR_TYPES: tuple[type[BaseException], ...] = (
    (pywintypes.error,)
    if pywintypes is not None
    else ()
)
WINDOWS_API_ERROR_TYPES: tuple[type[BaseException], ...] = (
    AttributeError,
    ctypes.ArgumentError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
) + PYWIN32_ERROR_TYPES
SENSITIVE_CONSOLE_TEXT_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r'(?i)(\"(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\"\s*:\s*\")([^\"]*)(\")'
        ),
        r"\1[REDACTED]\3",
    ),
    (
        re.compile(
            r"(?i)('(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)'\s*:\s*')([^']*)(')"
        ),
        r"\1[REDACTED]\3",
    ),
    (
        re.compile(
            r"(?i)\b(password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (
        re.compile(r"(?i)([?&](?:password|pass|token|cookie|auth|authorization)=)([^&\s]+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(\.ROBLOSECURITY\s*=\s*)([^;\s]+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(\.ROBLOSECURITY\s*[:=]\s*)([^;\s]+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[^\s\"'<>)]*"),
        "[DISCORD_WEBHOOK_REDACTED]",
    ),
    (
        re.compile(r"(?i)([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\r\n\"']+)"),
        r"\1<user>",
    ),
    (
        re.compile(r"(?i)([\\/]+Users[\\/]+)([^\\/\r\n\"']+)"),
        r"\1<user>",
    ),
    (
        re.compile(r"(?i)([\\/]+home[\\/]+)([^\\/\r\n\"']+)"),
        r"\1<user>",
    ),
)
SENSITIVE_SETTINGS_KEY_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|cookie|token|authorization|access_token|refresh_token|webhook|secret|last_user|recent_user|user_id)"
)
DIAGNOSTIC_EXPORT_VERSION = "2"


class Guid(ctypes.Structure):
    _fields_: list[tuple[str, Any]] = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_: list[tuple[str, Any]] = [
        ("GdiplusVersion", wintypes.UINT),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]


def create_png_encoder_guid() -> Guid:
    return Guid(
        0x557CF406,
        0x1A04,
        0x11D3,
        (ctypes.c_ubyte * 8)(0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E),
    )


def save_hbitmap_as_png(hbitmap: int, screenshot_path: Path) -> bool:
    if platform.system() != "Windows" or not hbitmap:
        return False
    try:
        gdiplus = ctypes.windll.gdiplus
    except (AttributeError, OSError):
        return False

    token = ctypes.c_void_p()
    image = ctypes.c_void_p()
    startup_input = GdiplusStartupInput(1, None, False, False)
    png_encoder_guid = create_png_encoder_guid()

    try:
        gdiplus.GdiplusStartup.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(GdiplusStartupInput),
            ctypes.c_void_p,
        ]
        gdiplus.GdiplusStartup.restype = ctypes.c_ulong
        gdiplus.GdipCreateBitmapFromHBITMAP.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        gdiplus.GdipCreateBitmapFromHBITMAP.restype = ctypes.c_ulong
        gdiplus.GdipSaveImageToFile.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(Guid),
            ctypes.c_void_p,
        ]
        gdiplus.GdipSaveImageToFile.restype = ctypes.c_ulong
        gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
        gdiplus.GdipDisposeImage.restype = ctypes.c_ulong
        gdiplus.GdiplusShutdown.argtypes = [ctypes.c_void_p]
        gdiplus.GdiplusShutdown.restype = None

        startup_status = gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup_input), None)
        if startup_status != GDI_PLUS_OK:
            return False
        bitmap_status = gdiplus.GdipCreateBitmapFromHBITMAP(ctypes.c_void_p(hbitmap), None, ctypes.byref(image))
        if bitmap_status != GDI_PLUS_OK or not image.value:
            return False
        save_status = gdiplus.GdipSaveImageToFile(
            image,
            str(screenshot_path),
            ctypes.byref(png_encoder_guid),
            None,
        )
        return save_status == GDI_PLUS_OK
    except (AttributeError, OSError, ctypes.ArgumentError, ValueError):
        return False
    finally:
        if image.value:
            gdiplus.GdipDisposeImage(image)
        if token.value:
            gdiplus.GdiplusShutdown(token)


class ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH_CHARS),
    ]


@dataclass(frozen=True)
class RemoteAddonListing:
    file_name: str
    download_url: str
    html_url: str


@dataclass(frozen=True)
class ManagedChromiumDownload:
    version: str
    platform_key: str
    chrome_url: str
    chromedriver_url: str


@dataclass(frozen=True)
class ManagedChromiumInstallation:
    version: str
    binary_path: Path


@dataclass(frozen=True)
class InstanceManagerCardWidgets:
    frame: tk.Frame
    avatar_label: tk.Label
    username_label: tk.Label
    place_label: tk.Label
    pid_label: tk.Label
    status_label: tk.Label
    actions_frame: tk.Frame


@dataclass(frozen=True)
class AntiAfkWindow:
    hwnd: int
    pid: int
    title: str


@dataclass(frozen=True)
class TrackedWindowRecord:
    hwnd: int
    pid: int
    title: str
    class_name: str
    is_visible: bool
    is_hung: bool


@dataclass(frozen=True)
class TrackedProcessWindowSnapshot:
    created_at: float
    pid_to_image: dict[int, str]
    window_records: tuple[TrackedWindowRecord, ...]
    includes_windows: bool


@dataclass(frozen=True)
class AntiAfkPassSummary:
    total_windows: int
    successful_windows: int
    failed_windows: int


@dataclass(frozen=True)
class AutoMemoryKillTarget:
    pid: int
    image_name: str
    working_set_bytes: int
    usage_percent: float


@dataclass(frozen=True)
class DiscordLogFilterPreset:
    key: str
    label: str
    include_filter: str
    exclude_filter: str


DISCORD_LOG_FILTER_PRESET_CUSTOM: str = "custom"
DISCORD_LOG_FILTER_PRESETS: tuple[DiscordLogFilterPreset, ...] = (
    DiscordLogFilterPreset("all", "Everything", "", ""),
    DiscordLogFilterPreset(
        "errors",
        "Errors & Warnings",
        "error, warning, failed, fail, exception, traceback, invalid, expired",
        "",
    ),
    DiscordLogFilterPreset(
        "launches",
        "Launch Activity",
        "launch, launched, roblox, instance, process, pid, place, server",
        "",
    ),
    DiscordLogFilterPreset(
        "accounts",
        "Accounts & Validation",
        "account, validation, valid, invalid, cookie, group, note, rejoin",
        "",
    ),
    DiscordLogFilterPreset(
        "updates",
        "Updates & Downloads",
        "update, install, download, version, fastflags, addon",
        "",
    ),
    DiscordLogFilterPreset(
        "quiet",
        "Quiet Mode",
        "",
        "debug, heartbeat, polling, refresh, showing",
    ),
    DiscordLogFilterPreset(DISCORD_LOG_FILTER_PRESET_CUSTOM, "Custom", "", ""),
)
DISCORD_LOG_FILTER_PRESET_BY_KEY: dict[str, DiscordLogFilterPreset] = {
    preset.key: preset for preset in DISCORD_LOG_FILTER_PRESETS
}
DISCORD_LOG_FILTER_PRESET_BY_LABEL: dict[str, DiscordLogFilterPreset] = {
    preset.label: preset for preset in DISCORD_LOG_FILTER_PRESETS
}


def normalize_discord_log_filter_preset(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in DISCORD_LOG_FILTER_PRESET_BY_KEY:
        return key
    return "all"


def get_discord_log_filter_preset(value: Any) -> DiscordLogFilterPreset:
    return DISCORD_LOG_FILTER_PRESET_BY_KEY[normalize_discord_log_filter_preset(value)]


def coerce_bool_setting(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return default


MULTI_SELECT_KEYBIND_DEFAULT: str = "Control"
MULTI_SELECT_MODIFIER_STATE_MASKS: dict[str, int] = {
    "Shift": 0x0001,
    "Control": 0x0004,
    "Alt": 0x0008,
}
MULTI_SELECT_KEYBIND_ALIASES: dict[str, str] = {
    "control": "Control",
    "control_l": "Control",
    "control_r": "Control",
    "ctrl": "Control",
    "shift": "Shift",
    "shift_l": "Shift",
    "shift_r": "Shift",
    "alt": "Alt",
    "alt_l": "Alt",
    "alt_r": "Alt",
    "option": "Alt",
    "option_l": "Alt",
    "option_r": "Alt",
    "escape": "Escape",
    "esc": "Escape",
    "space": "space",
    "spacebar": "space",
    "return": "Return",
    "enter": "Return",
    "backspace": "BackSpace",
    "delete": "Delete",
}
MULTI_SELECT_KEYBIND_LABELS: dict[str, str] = {
    "Control": "Ctrl",
    "Shift": "Shift",
    "Alt": "Alt",
    "Escape": "Esc",
    "space": "Space",
    "Return": "Enter",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Tab": "Tab",
}


def normalize_multi_select_keybind(value: Any) -> str:
    value_text = str(value or "").strip()
    if not value_text:
        return MULTI_SELECT_KEYBIND_DEFAULT

    alias_key = value_text.replace(" ", "_").lower()
    aliased_value = MULTI_SELECT_KEYBIND_ALIASES.get(alias_key)
    if aliased_value:
        return aliased_value

    if len(value_text) == 1:
        return value_text.lower()

    return value_text


def format_multi_select_keybind(value: Any) -> str:
    key = normalize_multi_select_keybind(value)
    label = MULTI_SELECT_KEYBIND_LABELS.get(key)
    if label:
        return label
    if len(key) == 1:
        return key.upper()
    return key.replace("_", " ")


def normalize_multi_select_event_key(event: tk.Event) -> Optional[str]:
    keysym = str(getattr(event, "keysym", "") or "").strip()
    if not keysym:
        return None
    return normalize_multi_select_keybind(keysym)


def redact_sensitive_console_text(text: str) -> str:
    redacted = text
    for pattern, replacement in SENSITIVE_CONSOLE_TEXT_REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class ThemedToolTip:
    def __init__(self, widget: tk.Widget, text: str, ui: Any):
        self.widget = widget
        self.text = text
        self.ui = ui
        self.window: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event: Optional[tk.Event] = None) -> None:
        if self.window is not None or not self.text:
            return

        x_root = int(getattr(event, "x_root", 0) or 0)
        y_root = int(getattr(event, "y_root", 0) or 0)
        if not x_root or not y_root:
            x_root = self.widget.winfo_rootx() + 20
            y_root = self.widget.winfo_rooty() + self.widget.winfo_height()

        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x_root + 12}+{y_root + 14}")
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            bg=self.ui.BG_MID,
            fg=self.ui.FG_TEXT,
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=9,
            pady=5,
        )
        label.pack()
        self.window = window

    def hide(self, event: Optional[tk.Event] = None) -> None:
        if self.window is None:
            return
        try:
            self.window.destroy()
        finally:
            self.window = None


def clamp_multi_launch_delay(value):
    """Clamp arbitrary input to the allowed multi-launch delay range."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = MIN_LAUNCH_DELAY_SECONDS
    return max(MIN_LAUNCH_DELAY_SECONDS, min(MAX_LAUNCH_DELAY_SECONDS, numeric))


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


def get_user_presence(roblosecurity_cookie, user_ids, session=None, timeout=10):
    """
    Best-effort Presence API lookup for one or more Roblox user IDs.

    Returns:
        {
            "ok": bool,
            "status_code": int,
            "auth_error": bool,
            "error": str,
            "user_presences": list,
        }
    """
    result = {
        "ok": False,
        "status_code": 0,
        "auth_error": False,
        "error": "",
        "user_presences": [],
    }

    normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
    if not normalized_cookie:
        result["auth_error"] = True
        result["error"] = "Missing .ROBLOSECURITY cookie."
        return result

    normalized_user_ids = []
    for raw_user_id in list(user_ids or []):
        try:
            normalized_user_ids.append(int(raw_user_id))
        except Exception:
            continue

    if not normalized_user_ids:
        result["error"] = "No valid user IDs were provided."
        return result

    client = session or requests.Session()
    headers = {
        "Cookie": f".ROBLOSECURITY={normalized_cookie}",
        "Referer": "https://www.roblox.com/",
        "User-Agent": "Roblox/WinInet",
    }

    try:
        response = client.post(
            "https://presence.roblox.com/v1/presence/users",
            json={"userIds": normalized_user_ids},
            headers=headers,
            timeout=timeout,
        )
        result["status_code"] = int(getattr(response, "status_code", 0) or 0)
        if response.status_code in (401, 403):
            result["auth_error"] = True
            result["error"] = f"Presence request returned status {response.status_code}."
            return result
        response.raise_for_status()
        payload = response.json() if response.content else {}
        result["ok"] = True
        result["user_presences"] = payload.get("userPresences") or []
        return result
    except requests.exceptions.RequestException as exc:
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


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
    "Vapor": {
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
        self._entry_listeners: list[Callable[[], None]] = []
        atexit.register(self._cleanup)

    def set_redaction_enabled_getter(self, getter):
        self._redaction_enabled_getter = getter

    def add_entry_listener(self, listener: Callable[[], None]) -> None:
        if not callable(listener):
            return
        with self.lock:
            if listener not in self._entry_listeners:
                self._entry_listeners.append(listener)

    def _notify_entry_listeners(self) -> None:
        with self.lock:
            listeners = list(self._entry_listeners)
        for listener in listeners:
            try:
                listener()
            except (RuntimeError, tk.TclError):
                pass

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

        return redact_sensitive_console_text(text)

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
        has_new_entries = False
        with self.lock:
            buffer = self.partials[key] + data
            lines = buffer.split("\n")
            self.partials[key] = lines.pop() if buffer.endswith("\n") is False else ""
            for line in lines:
                cleaned = line.rstrip("\r")
                if cleaned:
                    self._append_entry(key, cleaned)
                    has_new_entries = True
        if has_new_entries:
            self._notify_entry_listeners()

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

    def get_all_entries(self):
        with self.lock:
            return list(self.entries)

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
        ttk.Button(button_frame, text="Export Diagnostics", style="Dark.TButton", command=self.export_logs).pack(side="left", padx=5)

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

    def export_logs(self):
        entries = self.capture.get_all_entries()
        redacted_entries = [self._redact_export_text(line) for line in entries]
        debug_entries = [
            line for line in redacted_entries
            if "[DEBUG]" in line or "[IM]" in line
        ]
        exported_at = datetime.now()
        default_name = f"fram_diagnostics_{exported_at.strftime('%Y%m%d_%H%M%S')}.txt"

        file_path = filedialog.asksaveasfilename(
            title="Export Diagnostic Report",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        sections = self._build_diagnostic_export_sections(
            exported_at=exported_at,
            redacted_entries=redacted_entries,
            debug_entries=debug_entries,
        )

        try:
            with open(file_path, "w", encoding="utf-8", newline="\n") as export_file:
                export_file.write("\n".join(sections))
            print(f"[INFO] Exported diagnostic report to {file_path}")
            messagebox.showinfo("Export Complete", f"Diagnostic report exported to:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not export logs:\n{exc}")

    def _build_diagnostic_export_sections(self, exported_at, redacted_entries, debug_entries):
        settings_snapshot = dict(getattr(self.ui, "settings", {}) or {})
        sections = [
            "ForkedRobloxAccountManager Diagnostic Export",
            f"Export Version: {DIAGNOSTIC_EXPORT_VERSION}",
            "Privacy: cookies, passwords, tokens, webhooks, private server links, account names, and user paths are redacted where detected.",
            "",
        ]

        self._append_export_section(sections, "EXPORT SUMMARY", self._format_key_values({
            "Exported At Local": exported_at.strftime("%Y-%m-%d %H:%M:%S"),
            "Exported At UTC": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "App Version": str(getattr(self.ui, "APP_VERSION", "unknown") or "unknown"),
            "Runtime Mode": "frozen executable" if getattr(sys, "frozen", False) else "source",
            "Total Log Lines": len(redacted_entries),
            "Debug Log Lines": len(debug_entries),
            "Warning/Error Lines": len(self._get_interesting_log_lines(redacted_entries)),
        }))
        self._append_export_section(sections, "RUNTIME ENVIRONMENT", self._format_runtime_diagnostics())
        self._append_export_section(sections, "APP FILES", self._format_file_diagnostics())
        self._append_export_section(sections, "APP STATE", self._format_app_state_diagnostics())
        self._append_export_section(sections, "ACCOUNT STORAGE SUMMARY", self._format_account_storage_diagnostics())
        self._append_export_section(sections, "BROWSER AUTOMATION", self._format_browser_diagnostics())
        self._append_export_section(sections, "ROBLOX DIAGNOSTICS", self._format_roblox_diagnostics())
        self._append_export_section(sections, "AUTO REJOIN SESSIONS", self._format_auto_rejoin_diagnostics())
        self._append_export_section(sections, "DISCORD LOG MIRROR", self._format_discord_log_mirror_diagnostics())
        self._append_export_section(sections, "RECENT WARNINGS AND ERRORS", self._format_log_block(
            self._get_interesting_log_lines(redacted_entries)[-120:],
            empty_text="(No warning or error lines captured)",
        ))
        self._append_export_section(sections, "USER SETTINGS SNAPSHOT", self._format_settings_snapshot(settings_snapshot))
        self._append_export_section(sections, "ALL LOGS", self._format_log_block(
            redacted_entries,
            empty_text="(No logs captured)",
        ))
        self._append_export_section(sections, "DEBUG LOGS ONLY", self._format_log_block(
            debug_entries,
            empty_text="(No debug logs captured)",
        ))
        return sections

    def _append_export_section(self, sections, title, body):
        sections.extend([
            f"=== {title} ===",
            self._redact_export_text(str(body or "(No data)")),
            "",
        ])

    def _safe_diagnostic_value(self, callback, fallback="[unavailable]"):
        try:
            return callback()
        except Exception as exc:
            return f"{fallback}: {type(exc).__name__}: {exc}"

    def _format_key_values(self, values):
        if not values:
            return "(No data)"

        rows = [(str(key), self._format_diagnostic_value(value)) for key, value in values.items()]
        max_key_len = max((len(key) for key, _ in rows), default=0)
        return "\n".join(
            self._redact_export_text(f"{key.ljust(max_key_len)} : {value}")
            for key, value in rows
        )

    def _format_diagnostic_value(self, value):
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (dict, list, tuple, set)):
            try:
                return json.dumps(value, ensure_ascii=False, default=str)
            except Exception:
                return str(value)
        return str(value)

    def _format_runtime_diagnostics(self):
        root = getattr(self.ui, "root", None)
        return self._format_key_values({
            "App Version": str(getattr(self.ui, "APP_VERSION", "unknown") or "unknown"),
            "Export Version": DIAGNOSTIC_EXPORT_VERSION,
            "Frozen Executable": bool(getattr(sys, "frozen", False)),
            "Process ID": os.getpid(),
            "Python Version": sys.version.replace("\n", " "),
            "Python Executable": sys.executable,
            "Platform": platform.platform(),
            "OS": platform.system(),
            "OS Release": platform.release(),
            "Machine": platform.machine(),
            "Processor": platform.processor() or "unknown",
            "Working Directory": os.getcwd(),
            "Command Args": list(getattr(sys, "argv", []) or []),
            "Tk Version": self._safe_diagnostic_value(
                lambda: root.tk.call("info", "patchlevel") if root is not None else "unknown"
            ),
            "Tk Scaling": self._safe_diagnostic_value(
                lambda: root.tk.call("tk", "scaling") if root is not None else "unknown"
            ),
            "Root Geometry": self._safe_diagnostic_value(
                lambda: root.geometry() if root is not None else "unknown"
            ),
            "Screen Size": self._safe_diagnostic_value(
                lambda: f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}" if root is not None else "unknown"
            ),
            "Open Themed Windows": self._safe_diagnostic_value(
                lambda: len(getattr(self.ui, "themable_windows", set()) or set())
            ),
            "Git": self._get_git_diagnostics(),
            "Dependency Versions": self._get_dependency_versions(),
        })

    def _get_git_diagnostics(self):
        if getattr(sys, "frozen", False):
            return "not available in frozen executable"

        repo_root = self._safe_diagnostic_value(lambda: str(Path(__file__).resolve().parents[1]), fallback="")
        if not repo_root:
            return "unknown"

        def run_git(args):
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                **subprocess_no_window_kwargs(),
            )
            if result.returncode != 0:
                return ""
            return str(result.stdout or "").strip()

        try:
            branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
            commit = run_git(["rev-parse", "--short", "HEAD"]) or "unknown"
            status_lines = [line for line in run_git(["status", "--short"]).splitlines() if line.strip()]
            return f"branch={branch}, commit={commit}, changed_files={len(status_lines)}"
        except Exception as exc:
            return f"unavailable: {type(exc).__name__}: {exc}"

    def _get_dependency_versions(self):
        try:
            from importlib import metadata as importlib_metadata
        except Exception:
            importlib_metadata = None

        packages = ("selenium", "webdriver-manager", "requests", "pycryptodome", "pywin32")
        versions = []
        for package_name in packages:
            version = "unknown"
            if importlib_metadata is not None:
                try:
                    version = importlib_metadata.version(package_name)
                except Exception:
                    version = "not installed"
            versions.append(f"{package_name}={version}")
        return ", ".join(versions)

    def _format_file_diagnostics(self):
        manager = getattr(self.ui, "manager", None)
        paths = {
            "App Base Directory": Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1],
            "UI Module": Path(__file__).resolve(),
            "Data Folder": getattr(self.ui, "data_folder", ""),
            "Settings File": getattr(self.ui, "settings_file", ""),
            "Accounts File": getattr(manager, "accounts_file", ""),
            "Encryption Config": getattr(getattr(manager, "encryption_config", None), "config_file", ""),
            "Custom Themes File": getattr(self.ui, "custom_themes_file", ""),
            "Addons Folder": getattr(self.ui, "addons_folder", ""),
            "Browser Extensions Folder": getattr(getattr(self.ui, "browser_extension_manager", None), "extensions_folder", ""),
            "Managed Chromium Root": self._safe_diagnostic_value(lambda: self.ui._get_managed_chromium_root(), fallback=""),
            "Temp Directory": tempfile.gettempdir(),
        }
        return self._format_key_values({name: self._describe_path(path) for name, path in paths.items()})

    def _describe_path(self, path):
        if not path:
            return "not configured"
        try:
            resolved_path = Path(path)
            exists = resolved_path.exists()
            details = [str(resolved_path), f"exists={'yes' if exists else 'no'}"]
            if exists:
                if resolved_path.is_file():
                    details.append("type=file")
                    details.append(f"size={resolved_path.stat().st_size} bytes")
                elif resolved_path.is_dir():
                    details.append("type=directory")
                    try:
                        details.append(f"items={sum(1 for _ in resolved_path.iterdir())}")
                    except OSError:
                        details.append("items=unavailable")
                else:
                    details.append("type=other")
                try:
                    modified = datetime.fromtimestamp(resolved_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    details.append(f"modified={modified}")
                except OSError:
                    pass
            return " | ".join(details)
        except Exception as exc:
            return f"{path} | unavailable: {type(exc).__name__}: {exc}"

    def _format_app_state_diagnostics(self):
        settings = getattr(self.ui, "settings", {}) or {}
        selected_usernames = self._safe_diagnostic_value(
            lambda: list(self.ui._get_selected_usernames_silent()),
            fallback=[],
        )
        if not isinstance(selected_usernames, list):
            selected_usernames = []

        return self._format_key_values({
            "Theme": settings.get("selected_theme", ""),
            "Topmost Enabled": settings.get("enable_topmost", False),
            "Debug Logging": settings.get("enable_debug_logging", False),
            "Hide Sensitive Info": settings.get("hide_sensitive_info", True),
            "Multi Roblox": settings.get("enable_multi_roblox", False),
            "Multi Select": settings.get("enable_multi_select", False),
            "Selected Group": settings.get("selected_group", ""),
            "Selected Account Count": len(selected_usernames),
            "Selected Account IDs": [self._hash_identifier(username) for username in selected_usernames],
            "Launch Input Mode": getattr(self.ui, "launch_input_mode", settings.get("launch_input_mode", "")),
            "Place Target Mode": getattr(self.ui, "place_join_target_mode", settings.get("place_join_target_mode", "")),
            "Place Entry": self._safe_diagnostic_value(lambda: self.ui.place_entry.get(), fallback=""),
            "Private Server Entry": self._safe_diagnostic_value(lambda: self.ui.private_server_entry.get(), fallback=""),
            "Version Selection": self._safe_diagnostic_value(lambda: self.ui.version_var.get(), fallback=""),
            "Recent Games": len(settings.get("game_list", []) or []),
            "Recent Users": len(settings.get("recent_user_list", []) or []),
            "Version Options": len(getattr(self.ui, "version_options", {}) or {}),
            "Keep Clients Arranged": settings.get("keep_roblox_clients_arranged", False),
            "Auto Relaunch Enabled": settings.get("auto_relaunch_enabled", False),
            "Auto Memory Trim Enabled": settings.get("auto_memory_trim_enabled", False),
            "Auto Memory Kill Enabled": settings.get("auto_memory_kill_enabled", False),
            "Anti AFK Enabled": settings.get("anti_afk_enabled", False),
            "Roblox Headless Mode": settings.get("roblox_headless_mode_enabled", False),
        })

    def _format_account_storage_diagnostics(self):
        manager = getattr(self.ui, "manager", None)
        accounts = getattr(manager, "accounts", {}) or {}
        if not isinstance(accounts, dict):
            accounts = {}

        dict_accounts = [value for value in accounts.values() if isinstance(value, dict)]
        encryption_config = getattr(manager, "encryption_config", None)
        groups = self._safe_diagnostic_value(lambda: manager.get_groups() if manager is not None else [], fallback=[])
        if not isinstance(groups, list):
            groups = []

        return self._format_key_values({
            "Account Count": len(accounts),
            "Structured Account Records": len(dict_accounts),
            "Accounts With Cookie": sum(1 for value in dict_accounts if str(value.get("cookie", "") or "").strip()),
            "Accounts With Saved Password": sum(1 for value in dict_accounts if str(value.get("password", "") or "").strip()),
            "Accounts With User ID": sum(1 for value in dict_accounts if str(value.get("user_id", "") or "").strip()),
            "Accounts With Notes": sum(1 for value in dict_accounts if str(value.get("note", "") or "").strip()),
            "Accounts With VIP Server": sum(1 for value in dict_accounts if str(value.get("vip_server", "") or "").strip()),
            "Accounts With Auto Rejoin": sum(1 for value in dict_accounts if bool(value.get("auto_rejoin_enabled", False))),
            "Group Count": len(groups),
            "Encryption Enabled": self._safe_diagnostic_value(lambda: encryption_config.is_encryption_enabled(), fallback="unknown") if encryption_config else "unknown",
            "Encryption Method": self._safe_diagnostic_value(lambda: encryption_config.get_encryption_method(), fallback="unknown") if encryption_config else "unknown",
            "No Encryption Chosen": self._safe_diagnostic_value(lambda: encryption_config.is_no_encryption_chosen(), fallback="unknown") if encryption_config else "unknown",
        })

    def _format_browser_diagnostics(self):
        available_browsers = self._safe_diagnostic_value(lambda: self.ui._get_available_browsers(), fallback=[])
        if not isinstance(available_browsers, list):
            available_browsers = []

        rows = []
        for browser_name, display_name in BROWSER_DISPLAY_NAMES.items():
            rows.append({
                "browser": display_name,
                "installed": self._safe_diagnostic_value(lambda name=browser_name: self.ui._is_browser_installed_locally(name), fallback="unknown"),
                "available": browser_name in available_browsers,
            })

        installation = None
        installation_error = ""
        try:
            installation = self.ui._get_managed_chromium_installation()
        except Exception as exc:
            installation_error = f"{type(exc).__name__}: {exc}"
        extensions_text = self._format_browser_extension_diagnostics()
        summary = self._format_key_values({
            "Preferred Browser": self._safe_diagnostic_value(lambda: self.ui._get_preferred_browser(), fallback="unknown"),
            "Available Browsers": available_browsers,
            "Managed Chromium Installed": installation is not None,
            "Managed Chromium Version": getattr(installation, "version", "") if installation is not None else "",
            "Managed Chromium Binary": getattr(installation, "binary_path", "") if installation is not None else "",
            "Managed Chromium Error": installation_error,
        })
        return "\n".join([
            summary,
            "",
            "Browser Availability:",
            self._format_table(rows, [("browser", "Browser"), ("installed", "Installed"), ("available", "Available")]),
            "",
            "Extensions:",
            extensions_text,
        ])

    def _format_browser_extension_diagnostics(self):
        manager = getattr(self.ui, "browser_extension_manager", None)
        if manager is None:
            return "(Extension manager unavailable)"
        try:
            extensions = manager.list_extensions()
        except BrowserExtensionError as exc:
            return f"Extension manager error: {exc}"
        except Exception as exc:
            return f"Extension manager unavailable: {type(exc).__name__}: {exc}"

        rows = []
        for extension in extensions:
            rows.append({
                "enabled": bool(extension.enabled),
                "name": extension.name,
                "source": extension.display_source,
                "manifest": extension.manifest_version or "",
                "id": extension.extension_id,
            })
        if not rows:
            return "(No managed browser extensions)"
        return self._format_table(
            rows,
            [
                ("enabled", "Enabled"),
                ("name", "Name"),
                ("source", "Source"),
                ("manifest", "MV"),
                ("id", "Extension ID"),
            ],
        )

    def _format_roblox_diagnostics(self):
        process_rows = self._safe_diagnostic_value(lambda: self.ui._get_discord_active_instance_rows(), fallback=[])
        if not isinstance(process_rows, list):
            process_rows = []

        installed_versions = self._safe_diagnostic_value(lambda: RobloxAPI.get_installed_versions(), fallback=[])
        if not isinstance(installed_versions, list):
            installed_versions = []

        total_memory_bytes = 0
        for row in process_rows:
            try:
                total_memory_bytes += int(row.get("memory_bytes") or 0)
            except (AttributeError, TypeError, ValueError):
                continue

        summary = self._format_key_values({
            "Running Roblox Instances": len(process_rows),
            "Not Responding Instances": sum(1 for row in process_rows if str(row.get("status", "")).lower() == "not responding"),
            "Total Roblox Memory": self._format_bytes(total_memory_bytes) if total_memory_bytes else "unknown",
            "Installed Roblox Versions Found": len(installed_versions),
            "Selected Version": self._safe_diagnostic_value(lambda: self.ui.version_var.get(), fallback=""),
            "Custom Roblox Player Path": self._describe_path((getattr(self.ui, "settings", {}) or {}).get("custom_roblox_player_path", "")),
        })

        version_rows = []
        for version in installed_versions[:20]:
            if isinstance(version, dict):
                version_rows.append({
                    "name": version.get("name", "") or version.get("version", ""),
                    "version": version.get("version", ""),
                    "path": version.get("path", ""),
                })

        return "\n".join([
            summary,
            "",
            "Running Instances:",
            self._format_table(
                process_rows,
                [
                    ("pid", "PID"),
                    ("image", "Image"),
                    ("account", "Account"),
                    ("status", "Status"),
                    ("place", "Place"),
                    ("memory_bytes", "Memory"),
                    ("auto_rejoin", "Auto Rejoin"),
                    ("title", "Window Title"),
                ],
                transforms={"memory_bytes": self._format_bytes},
                empty_text="(No running Roblox instances detected)",
            ),
            "",
            "Installed Versions:",
            self._format_table(
                version_rows,
                [("name", "Name"), ("version", "Version"), ("path", "Path")],
                empty_text="(No installed Roblox versions detected)",
            ),
        ])

    def _format_auto_rejoin_diagnostics(self):
        monitor = getattr(self.ui, "_auto_rejoin_monitor", None)
        if monitor is None:
            return "Monitor Attached: no"

        sessions = []
        try:
            lock = getattr(monitor, "_lock", None)
            if lock is not None:
                with lock:
                    sessions = list(getattr(monitor, "active_sessions", {}).values())
            else:
                sessions = list(getattr(monitor, "active_sessions", {}).values())
        except Exception:
            sessions = []

        rows = []
        for session in sessions:
            username = str(getattr(session, "username", "") or "")
            rows.append({
                "account": self._hash_identifier(username),
                "pid": getattr(session, "pid", 0),
                "place": getattr(session, "place_id", ""),
                "mode": getattr(session, "launch_mode", ""),
                "auto": bool(getattr(session, "auto_rejoin", False)),
                "attempts": f"{getattr(session, 'rejoin_attempts', 0)}/{getattr(session, 'max_rejoin_attempts', 0)}",
                "process": bool(getattr(session, "has_seen_process_alive", False)),
                "window": bool(getattr(session, "has_seen_window", False)),
                "in_game": bool(getattr(session, "has_seen_in_game", False)),
                "rejoining": bool(getattr(session, "rejoin_in_progress", False)),
                "disabled": getattr(session, "disabled_reason", ""),
            })

        summary = self._format_key_values({
            "Monitor Attached": True,
            "Thread Alive": self._safe_diagnostic_value(lambda: bool(getattr(monitor, "_thread", None) and monitor._thread.is_alive()), fallback="unknown"),
            "Active Sessions": len(rows),
            "Manual Stop Grace Entries": self._safe_diagnostic_value(lambda: len(getattr(monitor, "_manual_stop_grace", {}) or {}), fallback="unknown"),
        })
        return "\n".join([
            summary,
            "",
            self._format_table(
                rows,
                [
                    ("account", "Account ID"),
                    ("pid", "PID"),
                    ("place", "Place"),
                    ("mode", "Mode"),
                    ("auto", "Auto"),
                    ("attempts", "Attempts"),
                    ("process", "Seen Process"),
                    ("window", "Seen Window"),
                    ("in_game", "Seen In Game"),
                    ("rejoining", "Rejoining"),
                    ("disabled", "Disabled Reason"),
                ],
                empty_text="(No active auto-rejoin sessions)",
            ),
        ])

    def _format_discord_log_mirror_diagnostics(self):
        settings = getattr(self.ui, "settings", {}) or {}
        webhook_url = self._safe_diagnostic_value(lambda: self.ui._get_discord_log_mirror_webhook_url(), fallback="")
        current_total = self._safe_diagnostic_value(lambda: self.ui._discord_log_mirror_get_current_total(), fallback="unknown")
        return self._format_key_values({
            "Enabled": settings.get("discord_log_mirror_enabled", False),
            "Webhook Configured": bool(str(webhook_url or "").strip()),
            "Webhook Valid": self._safe_diagnostic_value(lambda: self.ui._is_valid_discord_webhook_url(webhook_url), fallback="unknown"),
            "Include STDOUT": settings.get("discord_log_mirror_include_stdout", True),
            "Include STDERR": settings.get("discord_log_mirror_include_stderr", True),
            "Redact Sensitive": settings.get("discord_log_mirror_redact_sensitive", True),
            "Filter Preset": settings.get("discord_log_mirror_filter_preset", "all"),
            "Max Lines Per Message": settings.get("discord_log_mirror_max_lines_per_message", ""),
            "Last Sent Index": getattr(self.ui, "_discord_log_mirror_last_index", ""),
            "Current Log Total": current_total,
            "Send In Progress": getattr(self.ui, "_discord_log_mirror_in_progress", False),
            "Screenshot Interval Minutes": settings.get("discord_log_mirror_screenshot_interval_minutes", 0),
            "Instance Summary Enabled": settings.get("discord_log_mirror_instance_summary_enabled", False),
            "Last Error": getattr(self.ui, "_discord_log_mirror_last_error", ""),
        })

    def _format_table(self, rows, columns, transforms=None, empty_text="(No rows)"):
        rows = list(rows or [])
        if not rows:
            return empty_text
        transforms = transforms or {}
        prepared_rows = []
        for row in rows:
            prepared_row = []
            for key, _label in columns:
                try:
                    value = row.get(key, "") if isinstance(row, dict) else getattr(row, key, "")
                except Exception:
                    value = ""
                transform = transforms.get(key)
                if callable(transform):
                    value = transform(value)
                value_text = self._clip_diagnostic_text(self._format_diagnostic_value(value))
                prepared_row.append(self._redact_export_text(value_text))
            prepared_rows.append(prepared_row)

        widths = []
        for column_index, (_key, label) in enumerate(columns):
            width = len(str(label))
            for row in prepared_rows:
                if column_index < len(row):
                    width = max(width, len(row[column_index]))
            widths.append(min(width, 80))

        header = " | ".join(str(label).ljust(widths[index]) for index, (_key, label) in enumerate(columns))
        divider = "-+-".join("-" * width for width in widths)
        lines = [header, divider]
        for row in prepared_rows:
            lines.append(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))
        return "\n".join(lines)

    def _clip_diagnostic_text(self, value, max_length=180):
        text = str(value or "")
        if len(text) <= max_length:
            return text
        return f"{text[:max_length - 3]}..."

    def _format_log_block(self, entries, empty_text="(No logs captured)"):
        if not entries:
            return empty_text
        return "\n".join(self._redact_export_text(entry) for entry in entries)

    def _get_interesting_log_lines(self, entries):
        tokens = (
            "[error]",
            "[warning]",
            "traceback",
            "exception",
            "failed",
            "failure",
            "timed out",
            "timeout",
            "invalid",
            "denied",
            "not responding",
        )
        interesting = []
        for entry in entries:
            entry_l = str(entry or "").lower()
            if any(token in entry_l for token in tokens):
                interesting.append(entry)
        return interesting

    def _format_bytes(self, value):
        try:
            byte_count = float(value or 0)
        except (TypeError, ValueError):
            return "unknown"
        if byte_count <= 0:
            return "unknown"
        units = ("B", "KB", "MB", "GB", "TB")
        unit_index = 0
        while byte_count >= 1024 and unit_index < len(units) - 1:
            byte_count /= 1024.0
            unit_index += 1
        if unit_index == 0:
            return f"{int(byte_count)} {units[unit_index]}"
        return f"{byte_count:.1f} {units[unit_index]}"

    def _format_settings_snapshot(self, settings_snapshot):
        if not settings_snapshot:
            return "(No settings found)"

        keys = [str(key) for key in settings_snapshot.keys()]
        max_key_len = max(len(key) for key in keys) if keys else 0
        lines = []
        for key in sorted(keys, key=lambda x: x.lower()):
            value = settings_snapshot.get(key)
            lower_key = str(key).lower()
            if self._is_sensitive_settings_key(lower_key) or any(
                marker in lower_key for marker in ("private_server", "vip_server", "linkcode", "link_code")
            ):
                value_text = "[REDACTED]"
            elif isinstance(value, (dict, list, tuple)):
                value_text = json.dumps(value, ensure_ascii=False, default=str)
            else:
                value_text = str(value)
            value_text = self._redact_export_text(value_text)
            lines.append(f"{key.ljust(max_key_len)} : {value_text}")
        return "\n".join(lines)

    def _is_sensitive_settings_key(self, key):
        return bool(SENSITIVE_SETTINGS_KEY_PATTERN.search(str(key or "")))

    def _redact_export_text(self, text):
        if not text:
            return text
        redacted = redact_sensitive_console_text(str(text))
        redacted = self._redact_account_identifiers(redacted)
        return self._redact_private_server_ids(redacted)

    def _hash_identifier(self, value):
        normalized = str(value or "").strip().casefold()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()[:12]

    def _redact_account_identifiers(self, text):
        if not text:
            return text

        redacted = str(text)
        account_names = set()
        try:
            accounts = getattr(getattr(self.ui, "manager", None), "accounts", {}) or {}
            if isinstance(accounts, dict):
                account_names.update(str(username or "").strip() for username in accounts.keys())
        except Exception:
            pass

        try:
            with self.ui._pid_account_lock:
                account_names.update(
                    str(username or "").strip()
                    for username in dict(getattr(self.ui, "_pid_account_map", {}) or {}).values()
                )
        except Exception:
            pass

        try:
            monitor = getattr(self.ui, "_auto_rejoin_monitor", None)
            sessions = getattr(monitor, "active_sessions", {}) if monitor is not None else {}
            if isinstance(sessions, dict):
                account_names.update(str(username or "").strip() for username in sessions.keys())
        except Exception:
            pass

        for account_name in sorted((name for name in account_names if len(name) >= 3), key=len, reverse=True):
            replacement = f"[ACCOUNT:{self._hash_identifier(account_name)}]"
            redacted = re.sub(re.escape(account_name), replacement, redacted, flags=re.IGNORECASE)
        return redacted

    def _redact_private_server_ids(self, text):
        if not text:
            return text
        redacted = str(text)
        private_server_key = (
            r"(?:private[_\s-]*server(?:[_\s-]*(?:id|link|code))*|"
            r"vip[_\s-]*server(?:[_\s-]*(?:id|link|code))*|"
            r"link[_\s-]*code)"
        )
        redacted = re.sub(
            rf'(?i)("{private_server_key}"\s*:\s*")([^"]+)(")',
            r"\1[REDACTED]\3",
            redacted,
        )
        redacted = re.sub(
            rf"(?i)('{private_server_key}'\s*:\s*')([^']+)(')",
            r"\1[REDACTED]\3",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(roblox://navigation/share_links\?[^\s]*?\bcode=)([^&\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(https?://(?:www\.)?roblox\.com/(?:share|share-links)\?[^\s]*?\bcode=)([^&\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([?&](?:linkCode|privateServerLinkCode)=)([^&\s]+)",
            r"\1[REDACTED]",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(\b(?:private[_\s-]*server(?:[_\s-]*id)?|link[_\s-]*code)\b\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)",
            r"\1[REDACTED]",
            redacted,
        )
        return redacted

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


class FRAMAddonAPI:
    def __init__(self, ui, addon_name, addon_path, addon_fram_version=""):
        self.ui = ui
        self.root = ui.root
        self.manager = ui.manager
        self.settings = ui.settings
        self.data_folder = ui.data_folder
        self.addons_folder = ui.addons_folder
        self.addon_name = str(addon_name or "Addon").strip() or "Addon"
        self.addon_path = str(addon_path or "").strip()
        self.fram_version = str(getattr(ui, "APP_VERSION", "unknown") or "unknown").strip() or "unknown"
        self.addon_fram_version = str(addon_fram_version or "").strip()
        self.tk = tk
        self.ttk = ttk

    def run_on_ui_thread(self, callback, *args, **kwargs):
        if not callable(callback):
            return None
        return self.root.after(0, lambda: callback(*args, **kwargs))

    def show_info(self, message, title=None):
        messagebox.showinfo(
            title or self.addon_name,
            str(message or ""),
            parent=getattr(self.ui, "addons_window", None) or self.root,
        )

    def show_error(self, message, title=None):
        messagebox.showerror(
            title or self.addon_name,
            str(message or ""),
            parent=getattr(self.ui, "addons_window", None) or self.root,
        )

    def show_success(self, message, title=None):
        self.ui.show_success_message(str(message or ""), title=title or self.addon_name)

    def get_selected_username(self):
        try:
            return self.ui.get_selected_username()
        except Exception:
            return None

    def get_selected_usernames(self):
        try:
            if self.ui.settings.get("enable_multi_select", False):
                return list(self.ui.get_selected_usernames() or [])
            username = self.ui.get_selected_username()
            return [username] if username else []
        except Exception:
            return []

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value, save=True):
        self.settings[key] = value
        if save:
            self.ui.save_settings()

    def refresh_accounts(self, selected_usernames=None):
        return self.ui.refresh_accounts(selected_usernames=selected_usernames)

    def refresh_game_list(self):
        return self.ui.refresh_game_list()

    def launch_game(self, *args, **kwargs):
        return self.ui.launch_game(*args, **kwargs)

    def launch_home(self, *args, **kwargs):
        return self.ui.launch_home(*args, **kwargs)

    def launch_home_app(self, *args, **kwargs):
        return self.ui.launch_home_app(*args, **kwargs)

    def auto_arrange_clients(self, show_feedback=True):
        return self.ui.auto_arrange_clients(show_feedback=show_feedback)

    def open_addons_folder(self):
        return self.ui._open_addons_folder()


class AccountManagerUI:
    ROBLOX_CLIENT_EXECUTABLES = {
        "robloxplayerbeta.exe",
        "robloxplayerlauncher.exe",
    }
    ROBLOX_HEADLESS_TARGET_EXECUTABLES = {"robloxplayerbeta.exe"}
    ANTI_AFK_TARGET_EXECUTABLES: set[str] = {"robloxplayerbeta.exe"}
    ANTI_AFK_DEFAULT_INTERVAL_MINUTES: int = 10
    ANTI_AFK_MIN_INTERVAL_MINUTES: int = 1
    ANTI_AFK_MAX_INTERVAL_MINUTES: int = 19
    ANTI_AFK_WAIT_CHECK_SECONDS: int = 60
    ANTI_AFK_DEFAULT_KEY_NAME: str = "M1"
    ANTI_AFK_DEFAULT_KEY_CODE: int = 0
    ANTI_AFK_MOUSE_BUTTON_ALIASES: dict[str, str] = {
        "m1": "M1",
        "mouse1": "M1",
        "left click": "M1",
        "button 1": "M1",
        "m2": "M2",
        "mouse2": "M2",
        "right click": "M2",
        "button 3": "M2",
        "m3": "M3",
        "mouse3": "M3",
        "middle click": "M3",
        "button 2": "M3",
    }
    ANTI_AFK_KEY_NAME_ALIASES: dict[str, str] = {
        "space": "Space",
        "up": "Up Arrow",
        "up arrow": "Up Arrow",
        "down": "Down Arrow",
        "down arrow": "Down Arrow",
        "left": "Left Arrow",
        "left arrow": "Left Arrow",
        "right": "Right Arrow",
        "right arrow": "Right Arrow",
    }
    KEEP_CLIENTS_ARRANGED_INTERVAL_MS = 5000
    ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS = 2
    ROBLOX_HEADLESS_MEMORY_TRIM_INTERVAL_SECONDS = 30
    _PROCESS_SET_INFORMATION = 0x0200
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _IDLE_PRIORITY_CLASS = 0x00000040
    _NORMAL_PRIORITY_CLASS = 0x00000020

    def __init__(self, root, manager, icon_path=None):
        self.root = root
        self.manager = manager
        self.icon_path = icon_path
        self.APP_VERSION = "2.5.3"
        self._game_name_after_id = None
        self._game_name_label_after_id = None
        self._game_name_request_token = 0
        self._last_game_name_query_value = None

        self._auto_relaunch_after_id = None
        self._auto_relaunch_in_progress = False
        self._auto_memory_trim_after_id = None
        self._auto_memory_trim_in_progress = False
        self._auto_memory_kill_after_id: Optional[str] = None
        self._auto_memory_kill_in_progress: bool = False
        self._anti_afk_after_id: Optional[str] = None
        self._anti_afk_in_progress: bool = False
        self._anti_afk_last_result: Optional[AntiAfkPassSummary] = None
        self._anti_afk_next_run_at: Optional[float] = None
        self._anti_afk_next_label_after_id: Optional[str] = None
        self._anti_afk_next_label_positioned: bool = False
        self._anti_afk_next_label_drag_offset: tuple[int, int] = (0, 0)
        self._anti_afk_wait_after_id: Optional[str] = None
        self.anti_afk_next_window: Optional[tk.Toplevel] = None
        self.anti_afk_next_label: Optional[tk.Label] = None
        self.anti_afk_next_label_var: Optional[tk.StringVar] = None
        self._discord_log_mirror_after_id = None
        self._discord_log_mirror_in_progress = False
        self._discord_log_mirror_screenshot_after_id = None
        self._discord_log_mirror_screenshot_in_progress = False
        self._discord_log_mirror_instance_summary_after_id = None
        self._discord_log_mirror_instance_summary_in_progress = False
        self._discord_log_mirror_last_index = 0
        self._discord_log_mirror_last_error = ""
        self._discord_log_mirror_sent_startup_notice = False
        self._keep_clients_arranged_after_id = None
        self._keep_clients_arranged_last_signature = None
        self._keep_clients_arranged_check_in_progress = False
        self._keep_clients_arranged_check_pending = False
        self._keep_clients_arranged_generation = 0
        self._roblox_headless_after_id = None
        self._roblox_headless_in_progress = False
        self._roblox_headless_generation = 0
        self._roblox_headless_last_trim_ts = 0.0
        self._roblox_headless_seen_pids = set()
        self._roblox_headless_last_empty_log_ts = 0.0
        self._auto_update_check_started = False
        self._auto_update_prompt_shown = False

        self.multi_roblox_handle = None
        self._pid_account_map = {}
        self._pid_launch_context_map = {}
        self._pid_account_lock = threading.Lock()
        self._client_title_rename_lock = threading.Lock()
        self._client_title_rename_active_pids: set[int] = set()
        self._tracked_roblox_exes = {
            "robloxplayerbeta.exe",
            "robloxstudiobeta.exe",
            "robloxplayerlauncher.exe",
            "robloxstudiolauncherbeta.exe",
        }

        self.console_output = get_console_output_buffer()
        self.console_window = ConsoleOutputWindow(self, self.console_output)
        self._account_validation_status = {}
        self._account_rejoin_status = {}
        self._account_rejoin_status_after_ids = {}
        self._active_client_indicator_cache = {"ts": 0.0, "usernames": set()}
        self._auto_rejoin_monitor = None
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
        self._pressed_multi_select_keys: set[str] = set()

        self.themable_text_widgets = []
        self.themable_windows = set()
        self._theme_refresh_callbacks = {}

        self.menu_bar = None
        self.actions_menu = None
        self.installer_menu = None
        self.add_account_menu = None
        self.account_context_menu = None
        self._account_context_auto_rejoin_index = None
        self.launch_input_context_menu = None
        self.place_target_context_menu = None
        self.recent_list_edit_button = None
        self.menu_bar_frame = None
        self.menu_buttons = []
        self.version_options = {"Latest Version": None}
        self.installer_dialog_state = None
        self._installer_versions_cache = None
        self._http_session = None
        self._http_session_lock = threading.Lock()
        self._discord_webhook_session: Optional[requests.Session] = None
        self._discord_webhook_session_lock = threading.RLock()
        self._settings_save_after_ids = {}
        self._discord_button_image = None
        self._place_icon_images: dict[str, tk.PhotoImage] = {}
        self._place_icon_fetch_pending: set[str] = set()
        self._place_icon_fetch_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._place_icon_fetch_lock = threading.Lock()
        self._place_icon_fetch_queue: queue.Queue[str] = queue.Queue(maxsize=ICON_FETCH_QUEUE_MAXSIZE)
        self._place_icon_fetch_worker_started = False
        self._place_icon_fetch_deferred: set[str] = set()
        self._place_icon_fetch_retry_after_id: Optional[str] = None
        self._user_icon_images: dict[str, tk.PhotoImage] = {}
        self._user_icon_fetch_pending: set[str] = set()
        self._user_icon_fetch_callbacks: dict[str, list[Callable[[str], None]]] = {}
        self._user_icon_fetch_lock = threading.Lock()
        self._user_icon_fetch_queue: queue.Queue[str] = queue.Queue(maxsize=ICON_FETCH_QUEUE_MAXSIZE)
        self._user_icon_fetch_worker_started = False
        self._user_icon_fetch_deferred: set[str] = set()
        self._user_icon_fetch_retry_after_id: Optional[str] = None
        self._tracked_process_window_snapshot: Optional[TrackedProcessWindowSnapshot] = None
        self._tracked_process_window_snapshot_lock = threading.RLock()
        self._tracked_process_window_snapshot_ttl_seconds: float = 0.75
        self._roblox_command_line_cache: dict[str, dict[int, str]] = {"pid_to_commandline": {}}
        self._roblox_command_line_cache_lock: Any = threading.Lock()
        self._recent_place_id_log_cache = {"ts": 0.0, "values": []}

        self.global_settings_window = None
        self.global_settings_values = None
        self.global_settings_meta = None
        self.global_settings_xml_names = None
        self.fastflags_window = None
        self.instance_manager_window = None
        self.addons_window = None
        self.browser_extensions_window = None
        self.discord_log_mirror_window = None

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
        
        self.root.title("FRAM v2.5.3 - made by evanovar - modified by hackyue")
        self.root.geometry("600x600")
        self.root.configure(bg="#2b2b2b")
        self.root.resizable(True, True)
        self.root.minsize(600, 700)  # Note to self, this shit so ass
        
        self.data_folder = "AccountManagerData"
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        self.addons_folder = os.path.join(self.data_folder, "addons")
        self._ensure_addons_folder()
        self.browser_extension_manager: BrowserExtensionManager
        if hasattr(self.manager, "get_browser_extension_manager"):
            self.browser_extension_manager = self.manager.get_browser_extension_manager()
        else:
            self.browser_extension_manager = BrowserExtensionManager(Path(self.data_folder))
            self.browser_extension_manager.ensure_storage()

        self.settings_file = os.path.join(self.data_folder, "ui_settings.json")
        self.custom_themes_file = os.path.join(self.data_folder, "custom_themes.json")
        self.custom_themes = {}
        self._load_custom_themes_from_disk()
        self.load_settings()
        self.console_output.set_redaction_enabled_getter(
            lambda: bool(self.settings.get("hide_sensitive_info", False))
        )
        self.console_output.add_entry_listener(self._on_console_output_entry_added)
        try:
            self.root.attributes("-topmost", bool(self.settings.get("enable_topmost", False)))
        except Exception:
            pass
        self.theme_name = self.settings.get("selected_theme", "Synapse Neon")

        self.apply_theme(self.theme_name, persist=True)
        self.register_toplevel(self.root)
        self.root.after(50, self._apply_title_bar_theme_all)
        self.root.bind_all("<KeyPress>", self._on_multi_select_key_press, add="+")
        self.root.bind_all("<KeyRelease>", self._on_multi_select_key_release, add="+")
        self.root.bind("<FocusOut>", self._clear_multi_select_pressed_keys, add="+")

      
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

        self.account_context_menu = tk.Menu(self.root, tearoff=False)
        self.account_context_menu.add_command(label="Copy Username", command=self.copy_selected_account_usernames)
        self.account_context_menu.add_command(label="Copy Password", command=self.copy_selected_account_passwords)
        self.account_context_menu.add_command(label="Copy Cookie", command=self.copy_selected_account_cookies)
        self.account_context_menu.add_command(label="Copy User:Pass", command=self.copy_selected_account_username_passwords)
        self.account_context_menu.add_command(label="Copy User:Pass:Cookie", command=self.copy_selected_account_username_password_cookies)
        self.account_context_menu.add_separator()
        self.account_context_menu.add_command(label="Validate Account", command=self.validate_account)
        self.account_context_menu.add_command(label="Edit Note", command=self.edit_account_note)
        self.account_context_menu.add_command(label="Set Group", command=self.edit_account_group)
        self.account_context_menu.add_command(label="Set VIP Server", command=self.edit_account_vip_server)
        self.account_context_menu.add_separator()
        self.account_context_menu.add_command(
            label="Enable Auto-Rejoin",
            command=self.toggle_selected_account_auto_rejoin,
        )
        self._account_context_auto_rejoin_index = self.account_context_menu.index("end")

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
        initial_launch_input_mode = self._normalize_launch_input_mode(
            self.settings.get("launch_input_mode", "place_id")
        )
        self.place_entry.insert(
            0,
            self.settings.get(self._get_launch_input_setting_key(initial_launch_input_mode), ""),
        )
        self.place_entry.bind("<KeyRelease>", self.on_place_id_change)
        self.place_label.bind("<Button-3>", self.show_launch_input_context_menu)
        self.place_entry.bind("<Button-3>", self.show_launch_input_context_menu)
        ThemedToolTip(self.place_label, "Right click to change to Join user", self)
        ThemedToolTip(self.place_entry, "Right click to change to Join user", self)

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
        self.private_server_entry.bind("<FocusOut>", self.on_private_server_change)
        self.private_server_entry.bind("<Button-1>", self.on_place_target_field_click)
        self.private_server_label.bind("<Button-3>", self.show_place_target_context_menu)
        self.private_server_entry.bind("<Button-3>", self.show_place_target_context_menu)
        ThemedToolTip(self.private_server_label, "Right click to change modes", self)
        ThemedToolTip(self.private_server_entry, "Right click to change modes", self)

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
        
        self.recent_list_edit_button = ttk.Button(
            right_frame,
            text="Edit",
            style="Dark.TButton",
            command=self.open_recent_list_editor,
        )
        self.recent_list_edit_button.pack(fill="x", pady=(5, 0))

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

        self.anti_afk_next_label_var = tk.StringVar(value="")
        self._refresh_anti_afk_next_label()

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
        self.root.after(500, self._auto_memory_kill_maybe_start)
        self.root.after(500, self._anti_afk_maybe_start)
        self.root.after(700, self._roblox_headless_maybe_start)
        self.root.after(900, self._discord_log_mirror_maybe_start)
        self.root.after(1500, self._auto_update_maybe_start)

    def load_settings(self):
        """Load UI settings from file"""
        defaults = {
            "last_place_id": "",
            "last_user": "",
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
            "pick_server_per_account": False,
            "preferred_server_region": "",
            "max_recent_games": 10,
            "enable_multi_select": False,
            "multi_select_keybind": MULTI_SELECT_KEYBIND_DEFAULT,
            "enable_debug_logging": False,
            "hide_sensitive_info": True,
            "bug_issue_prompt_enabled": True,
            "selected_theme": "Synapse Neon",
            "disable_success_popups": False,
            "auto_arrange_scope": "both",
            "auto_arrange_dimension_mode": "auto",
            "auto_arrange_target_width": 800,
            "auto_arrange_target_height": 600,
            "keep_roblox_clients_arranged": False,
            "multi_launch_delay": MIN_LAUNCH_DELAY_SECONDS,
            "custom_roblox_player_path": "",
            "show_active_client_indicator": True,
            "rename_client_titles_to_account_name": True,
            "selected_group": "All",
            "auto_rejoin_enable_all_accounts": False,
            "auto_rejoin_delay_seconds": 5,
            "auto_rejoin_max_attempts": 0,
            "auto_rejoin_launch_behavior": "rejoin_same_server",
            "auto_relaunch_enabled": False,
            "auto_relaunch_interval_minutes": 60,
            "auto_relaunch_group": "",
            "auto_memory_trim_enabled": False,
            "auto_memory_trim_interval_minutes": 5,
            "auto_memory_kill_enabled": False,
            "auto_memory_kill_limit_percent": 90,
            "anti_afk_enabled": False,
            "anti_afk_interval_minutes": self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES,
            "anti_afk_key_name": self.ANTI_AFK_DEFAULT_KEY_NAME,
            "anti_afk_key_code": self.ANTI_AFK_DEFAULT_KEY_CODE,
            "anti_afk_show_next_label": False,
            "anti_afk_next_label_x": None,
            "anti_afk_next_label_y": None,
            "discord_log_mirror_enabled": False,
            "discord_log_mirror_webhook_url": "",
            "discord_log_mirror_include_stdout": True,
            "discord_log_mirror_include_stderr": True,
            "discord_log_mirror_redact_sensitive": True,
            "discord_log_mirror_send_startup_notice": False,
            "discord_log_mirror_filter_preset": "all",
            "discord_log_mirror_include_filter": "",
            "discord_log_mirror_exclude_filter": "",
            "discord_log_mirror_ping_user_id": "",
            "discord_log_mirror_ping_only_errors": True,
            "discord_log_mirror_screenshot_interval_minutes": 0,
            "discord_log_mirror_screenshot_all_monitors": False,
            "discord_log_mirror_instance_summary_enabled": False,
            "discord_log_mirror_instance_summary_interval_minutes": 15,
            "discord_log_mirror_max_lines_per_message": 20,
            "roblox_headless_mode_enabled": False,
            "roblox_headless_idle_priority": True,
            "roblox_headless_trim_memory": True,
            "auto_update_enabled": True,
            "browser_preference": "auto",
        }

        try:
            with open(self.settings_file, "r", encoding="utf-8") as settings_fp:
                self.settings = json.load(settings_fp)
        except Exception:
            self.settings = defaults.copy()

        legacy_auto_arrange_after_group_launch = self.settings.pop("auto_arrange_after_group_launch", False)
        legacy_auto_arrange_after_launch = self.settings.pop("auto_arrange_after_launch", None)
        self.settings.pop("installer_previous_versions", None)
        self.settings.pop("discord_log_mirror_batch_interval_seconds", None)
        if "keep_roblox_clients_arranged" not in self.settings:
            migrated_keep_clients_arranged = legacy_auto_arrange_after_launch
            if migrated_keep_clients_arranged is None:
                migrated_keep_clients_arranged = legacy_auto_arrange_after_group_launch
            self.settings["keep_roblox_clients_arranged"] = bool(migrated_keep_clients_arranged)

        had_last_user_setting = "last_user" in self.settings

        for key, value in defaults.items():
            self.settings.setdefault(key, value)

        if (
            not had_last_user_setting
            and self._normalize_launch_input_mode(self.settings.get("launch_input_mode", "place_id")) == "join_user"
        ):
            self.settings["last_user"] = str(self.settings.get("last_place_id", "") or "").strip()

        self.settings["last_place_id"] = str(self.settings.get("last_place_id", "") or "").strip()
        self.settings["last_user"] = str(self.settings.get("last_user", "") or "").strip()
        self.settings["preferred_server_region"] = self._normalize_server_region_preference(
            self.settings.get("preferred_server_region", "")
        )

        self.settings["multi_launch_delay"] = clamp_multi_launch_delay(
            self.settings.get("multi_launch_delay", MIN_LAUNCH_DELAY_SECONDS)
        )
        self.settings["multi_select_keybind"] = normalize_multi_select_keybind(
            self.settings.get("multi_select_keybind", MULTI_SELECT_KEYBIND_DEFAULT)
        )
        self.settings["rename_client_titles_to_account_name"] = coerce_bool_setting(
            self.settings.get("rename_client_titles_to_account_name", True),
            True,
        )
        browser_pref = str(self.settings.get("browser_preference", "auto") or "auto").strip().lower()
        if browser_pref not in SUPPORTED_BROWSER_PREFERENCES:
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
        if platform.system() != "Windows":
            self.settings["auto_memory_kill_enabled"] = False
        self.settings["auto_memory_kill_enabled"] = bool(
            self.settings.get("auto_memory_kill_enabled", False)
        )
        self.settings["auto_memory_kill_limit_percent"] = self._normalize_auto_memory_kill_limit_percent(
            self.settings.get("auto_memory_kill_limit_percent", 90)
        )
        if platform.system() != "Windows":
            self.settings["anti_afk_enabled"] = False
        self.settings["anti_afk_enabled"] = bool(self.settings.get("anti_afk_enabled", False))
        self.settings["anti_afk_interval_minutes"] = self._normalize_anti_afk_interval_minutes(
            self.settings.get("anti_afk_interval_minutes", self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES)
        )
        anti_afk_key_name = self.settings.get("anti_afk_key_name", self.ANTI_AFK_DEFAULT_KEY_NAME)
        if (
            not bool(self.settings.get("anti_afk_default_key_migrated_to_m1", False))
            and str(anti_afk_key_name or "").strip().casefold() == "f15"
        ):
            anti_afk_key_name = self.ANTI_AFK_DEFAULT_KEY_NAME
        self.settings["anti_afk_key_name"] = self._normalize_anti_afk_key_name(
            anti_afk_key_name
        )
        self.settings["anti_afk_key_code"] = self._normalize_anti_afk_key_code(
            self.settings.get("anti_afk_key_code", self.ANTI_AFK_DEFAULT_KEY_CODE),
            self.settings["anti_afk_key_name"],
        )
        self.settings["anti_afk_show_next_label"] = bool(
            self.settings.get("anti_afk_show_next_label", False)
        )
        self._normalize_anti_afk_next_label_position_settings()
        self.settings["anti_afk_default_key_migrated_to_m1"] = True
        try:
            discord_max_lines = int(self.settings.get("discord_log_mirror_max_lines_per_message", 20) or 20)
        except (TypeError, ValueError):
            discord_max_lines = 20
        self.settings["discord_log_mirror_max_lines_per_message"] = max(1, min(50, discord_max_lines))
        self.settings["discord_log_mirror_webhook_url"] = str(
            self.settings.get("discord_log_mirror_webhook_url", "") or ""
        ).strip()
        self.settings["discord_log_mirror_include_stdout"] = bool(
            self.settings.get("discord_log_mirror_include_stdout", True)
        )
        self.settings["discord_log_mirror_include_stderr"] = bool(
            self.settings.get("discord_log_mirror_include_stderr", True)
        )
        self.settings["discord_log_mirror_redact_sensitive"] = bool(
            self.settings.get("discord_log_mirror_redact_sensitive", True)
        )
        self.settings["discord_log_mirror_send_startup_notice"] = bool(
            self.settings.get("discord_log_mirror_send_startup_notice", False)
        )
        self.settings["discord_log_mirror_filter_preset"] = normalize_discord_log_filter_preset(
            self.settings.get("discord_log_mirror_filter_preset", "all")
        )
        self.settings["discord_log_mirror_ping_user_id"] = re.sub(
            r"\D",
            "",
            str(self.settings.get("discord_log_mirror_ping_user_id", "") or ""),
        )
        self.settings["discord_log_mirror_ping_only_errors"] = bool(
            self.settings.get("discord_log_mirror_ping_only_errors", True)
        )
        try:
            screenshot_interval = int(self.settings.get("discord_log_mirror_screenshot_interval_minutes", 0) or 0)
        except (TypeError, ValueError):
            screenshot_interval = 0
        self.settings["discord_log_mirror_screenshot_interval_minutes"] = max(0, min(1440, screenshot_interval))
        self.settings["discord_log_mirror_screenshot_all_monitors"] = bool(
            self.settings.get("discord_log_mirror_screenshot_all_monitors", False)
        )
        self.settings["discord_log_mirror_instance_summary_enabled"] = bool(
            self.settings.get("discord_log_mirror_instance_summary_enabled", False)
        )
        try:
            instance_summary_interval = int(
                self.settings.get("discord_log_mirror_instance_summary_interval_minutes", 15) or 15
            )
        except (TypeError, ValueError):
            instance_summary_interval = 15
        self.settings["discord_log_mirror_instance_summary_interval_minutes"] = max(
            1,
            min(1440, instance_summary_interval),
        )
        if platform.system() != "Windows":
            self.settings["roblox_headless_mode_enabled"] = False
        self.settings["roblox_headless_mode_enabled"] = bool(
            self.settings.get("roblox_headless_mode_enabled", False)
        )
        self.settings["roblox_headless_idle_priority"] = bool(
            self.settings.get("roblox_headless_idle_priority", True)
        )
        self.settings["roblox_headless_trim_memory"] = bool(
            self.settings.get("roblox_headless_trim_memory", True)
        )

        try:
            auto_rejoin_delay = int(self.settings.get("auto_rejoin_delay_seconds", 5) or 5)
        except (TypeError, ValueError):
            auto_rejoin_delay = 5
        self.settings["auto_rejoin_delay_seconds"] = max(0, auto_rejoin_delay)

        try:
            auto_rejoin_max_attempts = int(self.settings.get("auto_rejoin_max_attempts", 0) or 0)
        except (TypeError, ValueError):
            auto_rejoin_max_attempts = 0
        self.settings["auto_rejoin_max_attempts"] = max(0, auto_rejoin_max_attempts)
        self.settings["auto_rejoin_launch_behavior"] = self._normalize_auto_rejoin_launch_behavior(
            self.settings.get("auto_rejoin_launch_behavior", "rejoin_same_server")
        )
        self._set_keep_clients_arranged_enabled(
            self.settings.get("keep_roblox_clients_arranged", False),
            save=False,
            arrange_now=True,
        )

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

    def set_auto_rejoin_monitor(self, monitor):
        self._auto_rejoin_monitor = monitor
        try:
            self.manager.set_auto_rejoin_monitor(monitor)
        except Exception:
            pass
        self._apply_auto_rejoin_preferences_to_active_sessions()
        self.refresh_accounts()

    def _get_auto_rejoin_delay_seconds(self):
        try:
            value = int(self.settings.get("auto_rejoin_delay_seconds", 5) or 5)
        except (TypeError, ValueError):
            value = 5
        return max(0, value)

    def _get_auto_rejoin_max_attempts(self):
        try:
            value = int(self.settings.get("auto_rejoin_max_attempts", 0) or 0)
        except (TypeError, ValueError):
            value = 0
        return max(0, value)

    def _normalize_auto_rejoin_launch_behavior(self, value: Any) -> str:
        normalized = str(value or "rejoin_same_server").strip().lower()
        if normalized in {"relaunch_client_same_server", "relaunch_client", "client", "app"}:
            return "rejoin_same_server"
        if normalized in {"relaunch_client_same_game", "relaunch_game_client"}:
            return "rejoin_same_game"
        if normalized in {"rejoin_same_game", "same_game"}:
            return "rejoin_same_game"
        return "rejoin_same_server"

    def _get_auto_rejoin_launch_behavior(self) -> str:
        behavior = self._normalize_auto_rejoin_launch_behavior(
            self.settings.get("auto_rejoin_launch_behavior", "rejoin_same_server")
        )
        self.settings["auto_rejoin_launch_behavior"] = behavior
        return behavior

    def _normalize_server_region_preference(self, value: Any) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
        if not normalized:
            return ""

        allowed_values = {region_value for region_value, _label in SERVER_REGION_CHOICES}
        if normalized in allowed_values:
            return normalized

        for region_value, label in SERVER_REGION_CHOICES:
            normalized_label = re.sub(r"[^a-z0-9]+", " ", str(label or "").casefold()).strip()
            if normalized == normalized_label:
                return region_value
        return ""

    def _is_auto_rejoin_force_enabled(self):
        return bool(self.settings.get("auto_rejoin_enable_all_accounts", False))

    def _is_account_auto_rejoin_enabled(self, username):
        try:
            return bool(self.manager.get_account_auto_rejoin_enabled(username))
        except Exception:
            return False

    def _get_effective_auto_rejoin_enabled(self, username):
        return self._is_auto_rejoin_force_enabled() or self._is_account_auto_rejoin_enabled(username)

    def _apply_auto_rejoin_preferences_to_active_sessions(self, usernames=None):
        monitor = getattr(self, "_auto_rejoin_monitor", None)
        if monitor is None:
            return

        if usernames is None:
            usernames = list(getattr(self.manager, "accounts", {}).keys())

        delay_seconds = self._get_auto_rejoin_delay_seconds()
        max_attempts = self._get_auto_rejoin_max_attempts()
        rejoin_launch_behavior = self._get_auto_rejoin_launch_behavior()

        for username in list(usernames or []):
            try:
                monitor.update_session_preferences(
                    username,
                    auto_rejoin=self._get_effective_auto_rejoin_enabled(username),
                    rejoin_delay=delay_seconds,
                    max_rejoin_attempts=max_attempts,
                    rejoin_launch_behavior=rejoin_launch_behavior,
                )
            except Exception:
                continue

    def _get_auto_rejoin_session_snapshot(self, username):
        monitor = getattr(self, "_auto_rejoin_monitor", None)
        if monitor is None:
            return None
        try:
            return monitor.get_session_snapshot(username)
        except Exception:
            return None

    def _is_account_auto_rejoin_monitored(self, username):
        session = self._get_auto_rejoin_session_snapshot(username)
        if not isinstance(session, dict):
            return False
        return bool(session.get("auto_rejoin", False))

    def _get_active_client_indicator_enabled(self):
        return bool(self.settings.get("show_active_client_indicator", True))

    def _get_rename_client_titles_enabled(self) -> bool:
        return coerce_bool_setting(
            self.settings.get("rename_client_titles_to_account_name", True),
            True,
        )

    def _log_client_title_rename(self, message: str, debug: bool = False) -> None:
        if debug and not self.settings.get("enable_debug_logging", False):
            return
        level = "DEBUG" if debug else "INFO"
        print(f"[{level}] Title rename: {message}")

    def _invalidate_active_client_indicator_cache(self):
        self._active_client_indicator_cache = {"ts": 0.0, "usernames": set()}

    def _get_active_client_usernames(self):
        if not self._get_active_client_indicator_enabled():
            return set()

        cache = getattr(self, "_active_client_indicator_cache", None)
        now = time.time()
        if (
            isinstance(cache, dict)
            and isinstance(cache.get("usernames"), set)
            and (now - float(cache.get("ts", 0.0))) < 1.5
        ):
            return set(cache.get("usernames", set()))

        running_pids = self._get_running_tracked_roblox_pid_set()
        usernames = set()
        try:
            with self._pid_account_lock:
                pid_account_map = dict(self._pid_account_map)
        except Exception:
            pid_account_map = {}

        for pid_value, username in pid_account_map.items():
            try:
                normalized_pid = int(pid_value)
            except Exception:
                continue
            normalized_username = str(username or "").strip()
            if normalized_pid in running_pids and normalized_username:
                usernames.add(normalized_username)

        self._active_client_indicator_cache = {"ts": now, "usernames": set(usernames)}
        return usernames

    def log_auto_rejoin_event(self, message):
        print(str(message or "").strip())

    def set_account_rejoin_status(self, username, status_text, ttl_seconds=0):
        username = str(username or "").strip()
        text = str(status_text or "").strip()
        ttl_ms = max(0, int(ttl_seconds or 0)) * 1000
        if not username:
            return

        def apply():
            pending_id = self._account_rejoin_status_after_ids.pop(username, None)
            if pending_id is not None:
                try:
                    self.root.after_cancel(pending_id)
                except Exception:
                    pass

            if text:
                self._account_rejoin_status[username] = text
            else:
                self._account_rejoin_status.pop(username, None)

            if text and ttl_ms > 0:
                def clear_status(target_username=username):
                    self.set_account_rejoin_status(target_username, "", 0)

                try:
                    self._account_rejoin_status_after_ids[username] = self.root.after(ttl_ms, clear_status)
                except Exception:
                    pass

            self.refresh_accounts(selected_usernames=self._get_selected_usernames_silent())

        try:
            if threading.current_thread() is threading.main_thread():
                apply()
            else:
                self.root.after(0, apply)
        except Exception:
            pass

    def _get_multi_launch_delay(self):
        """Return the current launch delay, clamped to the supported range."""
        return clamp_multi_launch_delay(self.settings.get("multi_launch_delay", MIN_LAUNCH_DELAY_SECONDS))

    def _get_managed_chromium_root(self) -> Path:
        if hasattr(self, "manager") and hasattr(self.manager, "get_managed_chromium_root"):
            return Path(self.manager.get_managed_chromium_root())
        return Path(self.data_folder) / "browser" / "chromium"

    def _get_managed_chromium_installation(self) -> Optional[ManagedChromiumInstallation]:
        binary_path = None
        if hasattr(self, "manager") and hasattr(self.manager, "get_managed_chromium_binary_path"):
            binary_path = self.manager.get_managed_chromium_binary_path()

        root = self._get_managed_chromium_root()
        if binary_path is None:
            candidates = [
                root / "chrome-win64" / "chrome.exe",
                root / "chrome-win32" / "chrome.exe",
                root / "chrome-win" / "chrome.exe",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    binary_path = candidate
                    break

        if binary_path is None:
            return None

        resolved_binary_path = Path(binary_path)
        if not resolved_binary_path.is_file():
            return None

        version = ""
        manifest_path = root / "managed_chromium.json"
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest_data, dict):
                version = str(manifest_data.get("version") or "").strip()
        except (OSError, json.JSONDecodeError):
            version = ""

        return ManagedChromiumInstallation(version=version, binary_path=resolved_binary_path)

    def _get_preferred_browser(self) -> str:
        """Return browser automation preference: auto, chrome, firefox, waterfox, or chromium."""
        value = str(self.settings.get("browser_preference", "auto") or "auto").strip().lower()
        if value not in SUPPORTED_BROWSER_PREFERENCES:
            value = "auto"

        available = self._get_available_browsers()
        if not available:
            return value
        if len(available) == 1:
            return available[0]
        if value in SUPPORTED_BROWSER_PREFERENCES and (value == "auto" or value in available):
            return value
        return "auto"

    def _is_browser_installed_locally(self, browser_name: Any) -> bool:
        name = str(browser_name or "").strip().lower()
        if name not in BROWSER_DISPLAY_NAMES:
            return False

        try:
            if hasattr(self, "manager") and hasattr(self.manager, "_is_browser_installed"):
                return bool(self.manager._is_browser_installed(name))
        except (AttributeError, OSError, RuntimeError, TypeError):
            pass

        if name == "chromium":
            installation = self._get_managed_chromium_installation()
            if installation is None:
                return False
            driver_candidates = [
                self._get_managed_chromium_root() / "chromedriver-win64" / "chromedriver.exe",
                self._get_managed_chromium_root() / "chromedriver-win32" / "chromedriver.exe",
                self._get_managed_chromium_root() / "chromedriver-win" / "chromedriver.exe",
            ]
            return any(candidate.is_file() for candidate in driver_candidates)

        try:
            candidates = []
            pf = os.environ.get("ProgramFiles")
            pfx86 = os.environ.get("ProgramFiles(x86)")
            localapp = os.environ.get("LOCALAPPDATA")
            appdata = os.environ.get("APPDATA")

            executable_name_by_browser = {
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "waterfox": "waterfox.exe",
            }
            executable_name = executable_name_by_browser.get(name)
            if executable_name:
                for command_name in (executable_name, executable_name[:-4]):
                    resolved_path = shutil.which(command_name)
                    if resolved_path and os.path.exists(resolved_path):
                        return True

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
            elif name == "waterfox":
                waterfox_folders = ("Waterfox", "Waterfox Current", "Waterfox Classic")
                for base_path in (pf, pfx86):
                    if not base_path:
                        continue
                    for folder_name in waterfox_folders:
                        candidates.append(os.path.join(base_path, folder_name, "waterfox.exe"))
                if localapp:
                    for folder_name in waterfox_folders:
                        candidates.append(os.path.join(localapp, folder_name, "waterfox.exe"))
                        candidates.append(os.path.join(localapp, "Programs", folder_name, "waterfox.exe"))
                if appdata:
                    for folder_name in waterfox_folders:
                        candidates.append(os.path.join(appdata, folder_name, "waterfox.exe"))

            for path in candidates:
                if path and os.path.exists(path):
                    return True
        except OSError:
            pass
        return False

    def _get_available_browsers(self) -> list[str]:
        available = []
        try:
            if hasattr(self, "manager") and hasattr(self.manager, "get_available_browsers"):
                manager_available = self.manager.get_available_browsers()
                if isinstance(manager_available, (list, tuple, set)):
                    for name in manager_available:
                        normalized = str(name or "").strip().lower()
                        if normalized in BROWSER_DISPLAY_NAMES and normalized not in available:
                            available.append(normalized)
                    if available:
                        return available
        except (AttributeError, OSError, RuntimeError, TypeError):
            pass

        if self._is_browser_installed_locally("chrome"):
            available.append("chrome")
        if self._is_browser_installed_locally("firefox"):
            available.append("firefox")
        if self._is_browser_installed_locally("waterfox"):
            available.append("waterfox")
        if self._is_browser_installed_locally("chromium"):
            available.append("chromium")
        return available

    def _get_managed_chromium_platform_key(self) -> str:
        if platform.system() != "Windows":
            raise RuntimeError("The managed Chromium download is only available for Windows in this app.")

        machine = platform.machine().strip().lower()
        if machine in {"x86", "i386", "i686"}:
            return "win32"
        return "win64"

    def _select_managed_chromium_download_url(self, downloads: Any, asset_name: str, platform_key: str) -> str:
        if not isinstance(downloads, dict):
            raise RuntimeError("The Chromium download manifest is missing download entries.")

        entries = downloads.get(asset_name)
        if not isinstance(entries, list):
            raise RuntimeError(f"The Chromium download manifest is missing {asset_name}.")

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("platform") or "").strip().lower() != platform_key:
                continue
            url = str(entry.get("url") or "").strip()
            if url:
                return url

        raise RuntimeError(f"No {asset_name} download was found for {platform_key}.")

    def _get_managed_chromium_download(self) -> ManagedChromiumDownload:
        platform_key = self._get_managed_chromium_platform_key()
        try:
            response = self._get_http_session().get(CHROME_FOR_TESTING_DOWNLOADS_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch the Chromium download manifest: {exc}") from exc

        try:
            manifest = response.json()
        except ValueError as exc:
            raise RuntimeError("The Chromium download manifest was not valid JSON.") from exc

        if not isinstance(manifest, dict):
            raise RuntimeError("The Chromium download manifest was not a JSON object.")

        channels = manifest.get("channels")
        if not isinstance(channels, dict):
            raise RuntimeError("The Chromium download manifest is missing channels.")

        stable_channel = channels.get("Stable")
        if not isinstance(stable_channel, dict):
            raise RuntimeError("The Chromium download manifest is missing the Stable channel.")

        version = str(stable_channel.get("version") or "").strip()
        downloads = stable_channel.get("downloads")
        if not version:
            raise RuntimeError("The Chromium download manifest is missing a Stable version.")

        return ManagedChromiumDownload(
            version=version,
            platform_key=platform_key,
            chrome_url=self._select_managed_chromium_download_url(downloads, "chrome", platform_key),
            chromedriver_url=self._select_managed_chromium_download_url(downloads, "chromedriver", platform_key),
        )

    def _download_managed_chromium_archive(
        self,
        url: str,
        target_path: Path,
        description: str,
        status_callback: Callable[[str], None],
    ) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        last_status_update = 0.0

        try:
            with self._get_http_session().get(url, stream=True, timeout=90) as response:
                response.raise_for_status()
                total_bytes = int(response.headers.get("Content-Length") or 0)
                downloaded_bytes = 0
                status_callback(f"Downloading {description}...")
                with temp_path.open("wb") as target_fp:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        target_fp.write(chunk)
                        downloaded_bytes += len(chunk)
                        now = time.time()
                        if now - last_status_update < 0.35:
                            continue
                        last_status_update = now
                        if total_bytes:
                            status_callback(
                                f"Downloading {description} {downloaded_bytes / (1024 * 1024):.1f} / "
                                f"{total_bytes / (1024 * 1024):.1f} MB"
                            )
                        else:
                            status_callback(f"Downloading {description} {downloaded_bytes / (1024 * 1024):.1f} MB")
                temp_path.replace(target_path)
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to download {description}: {exc}") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to save {description}: {exc}") from exc
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def _extract_managed_chromium_archive(self, archive_path: Path, target_dir: Path, description: str) -> None:
        try:
            resolved_target_dir = target_dir.resolve()
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    resolved_member_path = (target_dir / member.filename).resolve()
                    try:
                        resolved_member_path.relative_to(resolved_target_dir)
                    except ValueError as exc:
                        raise RuntimeError(f"The {description} archive contains an unsafe path.") from exc
                archive.extractall(target_dir)
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"The {description} archive was not a valid zip file.") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to extract {description}: {exc}") from exc

    def _install_managed_chromium(self, status_callback: Callable[[str], None]) -> ManagedChromiumInstallation:
        root = self._get_managed_chromium_root()
        parent_dir = root.parent
        staging_dir = parent_dir / "chromium_staging"
        download_dir = parent_dir / "downloads"
        download = self._get_managed_chromium_download()
        chrome_archive_path = download_dir / f"chrome-{download.version}-{download.platform_key}.zip"
        driver_archive_path = download_dir / f"chromedriver-{download.version}-{download.platform_key}.zip"

        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            staging_dir.mkdir(parents=True, exist_ok=True)

            self._download_managed_chromium_archive(
                download.chrome_url,
                chrome_archive_path,
                "Chromium",
                status_callback,
            )
            self._download_managed_chromium_archive(
                download.chromedriver_url,
                driver_archive_path,
                "Chromium driver",
                status_callback,
            )

            status_callback("Extracting Chromium...")
            self._extract_managed_chromium_archive(chrome_archive_path, staging_dir, "Chromium")
            status_callback("Extracting Chromium driver...")
            self._extract_managed_chromium_archive(driver_archive_path, staging_dir, "Chromium driver")

            expected_binary_path = staging_dir / f"chrome-{download.platform_key}" / "chrome.exe"
            expected_driver_path = staging_dir / f"chromedriver-{download.platform_key}" / "chromedriver.exe"
            if not expected_binary_path.is_file() or not expected_driver_path.is_file():
                raise RuntimeError("The Chromium download did not contain the expected browser and driver files.")

            manifest = {
                "version": download.version,
                "platform": download.platform_key,
                "downloaded_at": f"{datetime.utcnow().isoformat(timespec='seconds')}Z",
                "source": CHROME_FOR_TESTING_DOWNLOADS_URL,
            }
            (staging_dir / "managed_chromium.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )

            if root.exists():
                shutil.rmtree(root)
            staging_dir.rename(root)

            installation = self._get_managed_chromium_installation()
            if installation is None:
                raise RuntimeError("Chromium was downloaded but could not be detected.")
            status_callback(f"Chromium {installation.version or download.version} is ready.")
            return installation
        except OSError as exc:
            raise RuntimeError(f"Failed to install Chromium: {exc}") from exc
        finally:
            for archive_path in (chrome_archive_path, driver_archive_path):
                if archive_path.exists():
                    try:
                        archive_path.unlink()
                    except OSError:
                        pass
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir)
                except OSError:
                    pass

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

    def _normalize_auto_memory_kill_limit_percent(self, value: Any) -> int:
        try:
            percent = int(value or 90)
        except (TypeError, ValueError, tk.TclError):
            percent = 90
        return max(1, min(100, percent))

    def _get_auto_memory_kill_limit_percent(self) -> int:
        percent = self._normalize_auto_memory_kill_limit_percent(
            self.settings.get("auto_memory_kill_limit_percent", 90)
        )
        self.settings["auto_memory_kill_limit_percent"] = percent
        return percent

    def _auto_memory_kill_maybe_start(self) -> None:
        if self.settings.get("auto_memory_kill_enabled", False):
            self._auto_memory_kill_start()

    def _auto_memory_kill_stop(self) -> None:
        after_id = getattr(self, "_auto_memory_kill_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._auto_memory_kill_after_id = None

    def _auto_memory_kill_config_valid(self) -> bool:
        if platform.system() != "Windows":
            return False
        if not bool(self.settings.get("auto_memory_kill_enabled", False)):
            return False
        return self._get_auto_memory_kill_limit_percent() >= 1

    def _auto_memory_kill_start(self) -> None:
        self._auto_memory_kill_stop()
        if not self._auto_memory_kill_config_valid():
            return
        self._auto_memory_kill_after_id = self.root.after(
            5 * 1000,
            self._auto_memory_kill_tick,
        )

    def _auto_memory_kill_tick(self) -> None:
        self._auto_memory_kill_after_id = None
        self._auto_memory_kill_run_once()

    def _get_auto_memory_kill_targets(self) -> list[AutoMemoryKillTarget]:
        total_memory_bytes = self._get_total_physical_memory_bytes()
        if not total_memory_bytes:
            return []

        pid_to_image = self._query_tracked_process_pid_map(
            {"robloxplayerbeta.exe"},
            use_cache=False,
        )
        targets: list[AutoMemoryKillTarget] = []
        for pid, image_name in sorted(pid_to_image.items()):
            working_set_bytes = self._memtrim_get_working_set(pid)
            if not working_set_bytes:
                continue
            usage_percent = (float(working_set_bytes) / float(total_memory_bytes)) * 100.0
            targets.append(
                AutoMemoryKillTarget(
                    pid=int(pid),
                    image_name=str(image_name or "RobloxPlayerBeta.exe"),
                    working_set_bytes=int(working_set_bytes),
                    usage_percent=usage_percent,
                )
            )
        return targets

    def _auto_memory_kill_run_pass(self) -> list[AutoMemoryKillTarget]:
        limit_percent = self._get_auto_memory_kill_limit_percent()
        over_limit_targets = [
            target
            for target in self._get_auto_memory_kill_targets()
            if target.usage_percent >= float(limit_percent)
        ]
        if not over_limit_targets:
            return []

        killed_targets: list[AutoMemoryKillTarget] = []
        for target in over_limit_targets:
            try:
                result = subprocess.run(
                    ["taskkill", "/PID", str(target.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=12,
                    **subprocess_no_window_kwargs(),
                )
            except Exception as exc:
                print(f"[WARNING] Auto RAM kill failed for Roblox PID {target.pid}: {exc}")
                continue

            if result.returncode == 0:
                self._mark_active_sessions_manually_stopped(pids=[target.pid])
                killed_targets.append(target)
                print(
                    (
                        "[INFO] Auto RAM kill closed Roblox "
                        f"PID {target.pid} at {target.usage_percent:.1f}% "
                        f"of system RAM (limit {limit_percent}%)."
                    )
                )
            else:
                combined_output = ((result.stdout or "") + (result.stderr or "")).strip()
                print(
                    (
                        "[WARNING] Auto RAM kill failed for Roblox "
                        f"PID {target.pid}: {combined_output or 'taskkill failed'}"
                    )
                )

        if killed_targets:
            self._invalidate_tracked_process_caches()
            self._invalidate_active_client_indicator_cache()
        return killed_targets

    def _auto_memory_kill_run_once(self) -> None:
        if not self._auto_memory_kill_config_valid():
            return
        if getattr(self, "_auto_memory_kill_in_progress", False):
            self._auto_memory_kill_start()
            return

        self._auto_memory_kill_in_progress = True

        def worker() -> None:
            try:
                self._auto_memory_kill_run_pass()
            finally:
                def finish() -> None:
                    self._auto_memory_kill_in_progress = False
                    if self._auto_memory_kill_config_valid():
                        self._auto_memory_kill_start()

                try:
                    self.root.after(0, finish)
                except Exception:
                    self._auto_memory_kill_in_progress = False

        threading.Thread(target=worker, daemon=True, name="auto-memory-kill").start()

    def _normalize_anti_afk_interval_minutes(self, value: Any) -> int:
        try:
            minutes = int(value or self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES)
        except (TypeError, ValueError, tk.TclError):
            minutes = self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES
        return max(
            self.ANTI_AFK_MIN_INTERVAL_MINUTES,
            min(self.ANTI_AFK_MAX_INTERVAL_MINUTES, minutes),
        )

    def _get_anti_afk_interval_minutes(self) -> int:
        minutes = self._normalize_anti_afk_interval_minutes(
            self.settings.get("anti_afk_interval_minutes", self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES)
        )
        self.settings["anti_afk_interval_minutes"] = minutes
        return minutes

    def _normalize_anti_afk_key_name(self, value: Any) -> str:
        raw_key_name = str(value or self.ANTI_AFK_DEFAULT_KEY_NAME).strip()
        if not raw_key_name:
            return self.ANTI_AFK_DEFAULT_KEY_NAME

        normalized_lookup_name = raw_key_name.replace("_", " ").casefold()
        mouse_button_name = self.ANTI_AFK_MOUSE_BUTTON_ALIASES.get(normalized_lookup_name)
        if mouse_button_name:
            return mouse_button_name

        keyboard_key_name = self.ANTI_AFK_KEY_NAME_ALIASES.get(normalized_lookup_name)
        if keyboard_key_name:
            return keyboard_key_name

        if len(raw_key_name) == 1:
            return raw_key_name.upper()

        function_key_match = re.fullmatch(r"(?i)f([1-9]|1[0-9]|2[0-4])", raw_key_name)
        if function_key_match:
            return f"F{function_key_match.group(1)}"

        return raw_key_name.replace("_", " ")

    def _get_anti_afk_legacy_key_code(self, key_name: str) -> int:
        if len(key_name) == 1:
            character = key_name.upper()
            if "A" <= character <= "Z" or "0" <= character <= "9":
                return ord(character)

        function_key_match = re.fullmatch(r"(?i)f([1-9]|1[0-9]|2[0-4])", key_name)
        if function_key_match:
            return 0x70 + int(function_key_match.group(1)) - 1

        special_key_codes = {
            "Space": 0x20,
            "Left Arrow": 0x25,
            "Up Arrow": 0x26,
            "Right Arrow": 0x27,
            "Down Arrow": 0x28,
        }
        return int(special_key_codes.get(key_name, self.ANTI_AFK_DEFAULT_KEY_CODE))

    def _normalize_anti_afk_key_code(self, value: Any, key_name: str) -> int:
        if key_name in {"M1", "M2", "M3"}:
            return self.ANTI_AFK_DEFAULT_KEY_CODE
        try:
            key_code = int(value or 0)
        except (TypeError, ValueError, tk.TclError):
            key_code = 0
        if key_code > 0:
            return key_code
        return self._get_anti_afk_legacy_key_code(key_name)

    def _get_anti_afk_key_name(self) -> str:
        key_name = self._normalize_anti_afk_key_name(
            self.settings.get("anti_afk_key_name", self.ANTI_AFK_DEFAULT_KEY_NAME)
        )
        self.settings["anti_afk_key_name"] = key_name
        return key_name

    def _get_anti_afk_key_code(self) -> int:
        key_name = self._get_anti_afk_key_name()
        key_code = self._normalize_anti_afk_key_code(
            self.settings.get("anti_afk_key_code", self.ANTI_AFK_DEFAULT_KEY_CODE),
            key_name,
        )
        self.settings["anti_afk_key_code"] = key_code
        return key_code

    def _anti_afk_maybe_start(self) -> None:
        if self.settings.get("anti_afk_enabled", False):
            self._anti_afk_start()
        else:
            self._refresh_anti_afk_next_label()

    def _cancel_anti_afk_schedule(self) -> None:
        after_id = getattr(self, "_anti_afk_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except (AttributeError, RuntimeError, tk.TclError):
            pass
        self._anti_afk_after_id = None

    def _anti_afk_stop(self) -> None:
        self._cancel_anti_afk_schedule()
        self._cancel_anti_afk_wait_check()
        self._anti_afk_next_run_at = None
        self._refresh_anti_afk_next_label()

    def _anti_afk_config_valid(self) -> bool:
        if platform.system() != "Windows":
            return False
        if win32gui is None or win32process is None or win32con is None:
            return False
        if not bool(self.settings.get("anti_afk_enabled", False)):
            return False
        return self._get_anti_afk_interval_minutes() >= self.ANTI_AFK_MIN_INTERVAL_MINUTES

    def _anti_afk_start(self) -> None:
        self._cancel_anti_afk_schedule()
        self._cancel_anti_afk_wait_check()
        if not self._anti_afk_config_valid():
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            return
        if not self._anti_afk_has_roblox_player_instance():
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            self._schedule_anti_afk_wait_check()
            self._log_anti_afk(
                (
                    "Waiting for RobloxPlayerBeta.exe before starting maintenance; "
                    f"checking again in {self.ANTI_AFK_WAIT_CHECK_SECONDS}s."
                ),
                debug=True,
            )
            return
        self._schedule_anti_afk_maintenance()
        self._log_anti_afk(
            (
                f"Enabled with {self._get_anti_afk_interval_minutes()} minute interval "
                f"and {self._get_anti_afk_key_name()} key."
            ),
            debug=True,
        )

    def _anti_afk_has_roblox_player_instance(self) -> bool:
        return bool(self._anti_afk_find_roblox_windows(use_cache=False))

    def _cancel_anti_afk_wait_check(self) -> None:
        after_id = getattr(self, "_anti_afk_wait_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except (AttributeError, RuntimeError, tk.TclError):
            pass
        self._anti_afk_wait_after_id = None

    def _schedule_anti_afk_wait_check(self, delay_ms: Optional[int] = None) -> None:
        if not self._anti_afk_config_valid():
            return
        if delay_ms is None and getattr(self, "_anti_afk_wait_after_id", None) is not None:
            return
        self._cancel_anti_afk_wait_check()
        if delay_ms is None:
            delay_ms = self.ANTI_AFK_WAIT_CHECK_SECONDS * 1000
        try:
            self._anti_afk_wait_after_id = self.root.after(
                max(0, int(delay_ms)),
                self._anti_afk_wait_check,
            )
        except (RuntimeError, tk.TclError):
            self._anti_afk_wait_after_id = None

    def _anti_afk_wait_check(self) -> None:
        self._anti_afk_wait_after_id = None
        if not self._anti_afk_config_valid():
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            return
        has_scheduled_maintenance = (
            getattr(self, "_anti_afk_next_run_at", None) is not None
            or getattr(self, "_anti_afk_after_id", None) is not None
        )
        if not self._anti_afk_has_roblox_player_instance():
            self._cancel_anti_afk_schedule()
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            self._schedule_anti_afk_wait_check()
            if has_scheduled_maintenance:
                self._log_anti_afk(
                    "RobloxPlayerBeta.exe is no longer detected; maintenance countdown paused.",
                    debug=True,
                )
            return
        if has_scheduled_maintenance:
            self._schedule_anti_afk_wait_check()
            return
        self._schedule_anti_afk_maintenance()
        self._log_anti_afk("RobloxPlayerBeta.exe detected; maintenance countdown started.", debug=True)

    def _schedule_anti_afk_maintenance(self) -> None:
        self._cancel_anti_afk_schedule()
        interval_ms = self._get_anti_afk_interval_minutes() * 60 * 1000
        self._anti_afk_next_run_at = time.monotonic() + (interval_ms / 1000.0)
        try:
            self._anti_afk_after_id = self.root.after(interval_ms, self._anti_afk_tick)
        except (RuntimeError, tk.TclError):
            self._anti_afk_after_id = None
            self._anti_afk_next_run_at = None
        self._refresh_anti_afk_next_label()
        if self._anti_afk_after_id is not None:
            self._schedule_anti_afk_wait_check()

    def _anti_afk_tick(self) -> None:
        self._anti_afk_after_id = None
        if not self._anti_afk_config_valid():
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            return
        if not self._anti_afk_has_roblox_player_instance():
            self._anti_afk_next_run_at = None
            self._refresh_anti_afk_next_label()
            self._schedule_anti_afk_wait_check()
            self._log_anti_afk("RobloxPlayerBeta.exe is no longer detected; waiting for the next instance.", debug=True)
            return
        self._anti_afk_run_once(show_feedback=False)
        self._schedule_anti_afk_maintenance()

    def _cancel_anti_afk_next_label_update(self) -> None:
        after_id = getattr(self, "_anti_afk_next_label_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except (AttributeError, RuntimeError, tk.TclError):
            pass
        self._anti_afk_next_label_after_id = None

    def _format_anti_afk_remaining_seconds(self, remaining_seconds: float) -> str:
        seconds = max(0, int(round(remaining_seconds)))
        if seconds >= 3600:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        if seconds >= 60:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _get_anti_afk_next_label_text(self) -> str:
        next_run_at = getattr(self, "_anti_afk_next_run_at", None)
        if next_run_at is None:
            return ""

        remaining_seconds = max(0.0, float(next_run_at) - time.monotonic())
        remaining_text = self._format_anti_afk_remaining_seconds(remaining_seconds)
        return f"Anti-AFK Input will send in {remaining_text}"

    def _destroy_anti_afk_next_label_window(self) -> None:
        window = getattr(self, "anti_afk_next_window", None)
        self.anti_afk_next_window = None
        self.anti_afk_next_label = None
        self._anti_afk_next_label_positioned = False
        if window is None:
            return
        try:
            if window.winfo_exists():
                window.destroy()
        except tk.TclError:
            pass

    def _normalize_anti_afk_next_label_position_settings(self) -> None:
        for key in ("anti_afk_next_label_x", "anti_afk_next_label_y"):
            value = self.settings.get(key)
            if value in (None, ""):
                self.settings[key] = None
                continue
            try:
                self.settings[key] = int(value)
            except (TypeError, ValueError):
                self.settings[key] = None

    def _get_saved_anti_afk_next_label_position(self) -> Optional[tuple[int, int]]:
        self._normalize_anti_afk_next_label_position_settings()
        x_position = self.settings.get("anti_afk_next_label_x")
        y_position = self.settings.get("anti_afk_next_label_y")
        if x_position is None or y_position is None:
            return None
        try:
            return int(x_position), int(y_position)
        except (TypeError, ValueError):
            return None

    def _save_anti_afk_next_label_position(self, x_position: int, y_position: int) -> None:
        self.settings["anti_afk_next_label_x"] = int(x_position)
        self.settings["anti_afk_next_label_y"] = int(y_position)
        self.save_settings()

    def _begin_anti_afk_next_label_drag(self, event: tk.Event) -> str:
        window = getattr(self, "anti_afk_next_window", None)
        if window is None:
            return "break"
        try:
            self._anti_afk_next_label_drag_offset = (
                int(getattr(event, "x_root", 0) or 0) - int(window.winfo_x()),
                int(getattr(event, "y_root", 0) or 0) - int(window.winfo_y()),
            )
        except tk.TclError:
            self._anti_afk_next_label_drag_offset = (0, 0)
        return "break"

    def _drag_anti_afk_next_label(self, event: tk.Event) -> str:
        window = getattr(self, "anti_afk_next_window", None)
        if window is None:
            return "break"
        x_offset, y_offset = self._anti_afk_next_label_drag_offset
        x_position = int(getattr(event, "x_root", 0) or 0) - int(x_offset)
        y_position = int(getattr(event, "y_root", 0) or 0) - int(y_offset)
        try:
            window.geometry(f"+{x_position}+{y_position}")
            self._anti_afk_next_label_positioned = True
        except tk.TclError:
            pass
        return "break"

    def _end_anti_afk_next_label_drag(self, _event: tk.Event) -> str:
        window = getattr(self, "anti_afk_next_window", None)
        if window is None:
            return "break"
        try:
            self._save_anti_afk_next_label_position(int(window.winfo_x()), int(window.winfo_y()))
        except tk.TclError:
            pass
        return "break"

    def _ensure_anti_afk_next_label_window(self) -> bool:
        window = getattr(self, "anti_afk_next_window", None)
        if window is not None:
            try:
                if window.winfo_exists():
                    return True
            except tk.TclError:
                pass
            self.anti_afk_next_window = None
            self.anti_afk_next_label = None
            self._anti_afk_next_label_positioned = False

        text_var = getattr(self, "anti_afk_next_label_var", None)
        if text_var is None:
            return False

        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.configure(
            bg=self.BG_MID,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            highlightthickness=1,
            bd=0,
        )
        window.resizable(False, False)
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.anti_afk_next_window = window
        self.anti_afk_next_label = tk.Label(
            window,
            textvariable=text_var,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
        )
        self.anti_afk_next_label.pack()
        for drag_widget in (window, self.anti_afk_next_label):
            drag_widget.bind("<ButtonPress-1>", self._begin_anti_afk_next_label_drag, add="+")
            drag_widget.bind("<B1-Motion>", self._drag_anti_afk_next_label, add="+")
            drag_widget.bind("<ButtonRelease-1>", self._end_anti_afk_next_label_drag, add="+")
        return True

    def _position_anti_afk_next_label_window(self) -> None:
        window = getattr(self, "anti_afk_next_window", None)
        if window is None:
            return
        try:
            self.root.update_idletasks()
            window.update_idletasks()
            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            root_width = self.root.winfo_width()
            screen_width = self.root.winfo_screenwidth()
            label_width = window.winfo_reqwidth()
            label_height = window.winfo_reqheight()
            if self._anti_afk_next_label_positioned:
                x_position = int(window.winfo_x())
                y_position = int(window.winfo_y())
            else:
                saved_position = self._get_saved_anti_afk_next_label_position()
                if saved_position is not None:
                    x_position, y_position = saved_position
                else:
                    x_position = root_x + root_width + 12
                    if x_position + label_width > screen_width:
                        x_position = max(8, root_x - label_width - 12)
                    y_position = max(8, root_y + 24)
                self._anti_afk_next_label_positioned = True
            window.geometry(f"{label_width}x{label_height}+{x_position}+{y_position}")
        except tk.TclError:
            pass

    def _refresh_anti_afk_next_label(self) -> None:
        text_var = getattr(self, "anti_afk_next_label_var", None)
        if text_var is None:
            return

        self._cancel_anti_afk_next_label_update()
        show_label = bool(self.settings.get("anti_afk_show_next_label", False))
        has_next_run = bool(self.settings.get("anti_afk_enabled", False)) and self._anti_afk_next_run_at is not None

        if not show_label or not has_next_run:
            self._destroy_anti_afk_next_label_window()
            return

        text_var.set(self._get_anti_afk_next_label_text())
        if not self._ensure_anti_afk_next_label_window():
            return
        self._position_anti_afk_next_label_window()

        try:
            self._anti_afk_next_label_after_id = self.root.after(1000, self._refresh_anti_afk_next_label)
        except (RuntimeError, tk.TclError):
            self._anti_afk_next_label_after_id = None

    def _anti_afk_find_roblox_windows(self, use_cache: bool = False) -> list[AntiAfkWindow]:
        if platform.system() != "Windows":
            return []

        target_exes = self._normalize_tracked_executable_names(self.ANTI_AFK_TARGET_EXECUTABLES)
        snapshot = self._get_tracked_process_window_snapshot(use_cache=use_cache, include_windows=True)
        pid_to_image = {
            int(pid_value): str(image_name or "").strip()
            for pid_value, image_name in snapshot.pid_to_image.items()
            if str(image_name or "").strip().lower() in target_exes
        }
        records_by_pid: dict[int, TrackedWindowRecord] = {}
        for record in snapshot.window_records:
            if record.pid in pid_to_image and record.pid not in records_by_pid:
                records_by_pid[record.pid] = record

        windows: list[AntiAfkWindow] = []
        for pid_value in sorted(pid_to_image.keys()):
            record = records_by_pid.get(pid_value)
            if record is None:
                continue
            windows.append(
                AntiAfkWindow(
                    hwnd=int(record.hwnd),
                    pid=int(pid_value),
                    title=record.title or str(pid_to_image.get(pid_value, "") or "Roblox"),
                )
            )
        return windows

    def _anti_afk_post_window_input(self, hwnd: int, key_name: str, key_code: int) -> bool:
        if platform.system() != "Windows" or win32gui is None or win32con is None:
            return False
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            width = max(1, int(right - left))
            height = max(1, int(bottom - top))
            jitter = 1 if int(time.monotonic()) % 2 else -1
            x_value = max(0, min(width - 1, int(width / 2) + jitter))
            y_value = max(0, min(height - 1, int(height / 2)))
            mouse_lparam = (y_value << 16) | x_value
            win32gui.PostMessage(hwnd, getattr(win32con, "WM_MOUSEMOVE", 0x0200), 0, mouse_lparam)
            if key_name in {"M1", "M2", "M3"}:
                mouse_message_names = {
                    "M1": ("WM_LBUTTONDOWN", "WM_LBUTTONUP", "MK_LBUTTON", 0x0201, 0x0202, 0x0001),
                    "M2": ("WM_RBUTTONDOWN", "WM_RBUTTONUP", "MK_RBUTTON", 0x0204, 0x0205, 0x0002),
                    "M3": ("WM_MBUTTONDOWN", "WM_MBUTTONUP", "MK_MBUTTON", 0x0207, 0x0208, 0x0010),
                }
                down_name, up_name, mask_name, down_default, up_default, mask_default = mouse_message_names[key_name]
                win32gui.PostMessage(
                    hwnd,
                    getattr(win32con, down_name, down_default),
                    getattr(win32con, mask_name, mask_default),
                    mouse_lparam,
                )
                win32gui.PostMessage(hwnd, getattr(win32con, up_name, up_default), 0, mouse_lparam)
            else:
                if key_code <= 0:
                    return False
                win32gui.PostMessage(hwnd, getattr(win32con, "WM_KEYDOWN", 0x0100), key_code, 1)
                win32gui.PostMessage(
                    hwnd,
                    getattr(win32con, "WM_KEYUP", 0x0101),
                    key_code,
                    0xC0000001,
                )
            return True
        except WINDOWS_API_ERROR_TYPES:
            return False

    def _anti_afk_run_pass(self) -> AntiAfkPassSummary:
        windows = self._anti_afk_find_roblox_windows(use_cache=False)
        key_name = self._get_anti_afk_key_name()
        key_code = self._get_anti_afk_key_code()
        successful_windows = 0
        for window in windows:
            if self._anti_afk_post_window_input(window.hwnd, key_name, key_code):
                successful_windows += 1
            time.sleep(0.02)
        failed_windows = len(windows) - successful_windows
        if windows:
            self._log_anti_afk(
                (
                    f"{key_name} pulse sent to "
                    f"{successful_windows}/{len(windows)} Roblox client(s)."
                ),
                debug=True,
            )
        else:
            self._log_anti_afk("No Roblox clients detected.", debug=True)
        return AntiAfkPassSummary(
            total_windows=len(windows),
            successful_windows=successful_windows,
            failed_windows=failed_windows,
        )

    def _anti_afk_run_once(self, show_feedback: bool = False) -> None:
        if platform.system() != "Windows":
            if show_feedback:
                messagebox.showerror("Anti-AFK", "This feature is only available on Windows.")
            return
        if getattr(self, "_anti_afk_in_progress", False):
            if show_feedback:
                messagebox.showinfo("Anti-AFK", "Anti-AFK is already running.")
            return

        self._anti_afk_in_progress = True

        def worker() -> None:
            error_message = ""
            try:
                summary = self._anti_afk_run_pass()
            except WINDOWS_API_ERROR_TYPES as exc:
                summary = AntiAfkPassSummary(
                    total_windows=0,
                    successful_windows=0,
                    failed_windows=0,
                )
                error_message = str(exc)

            def finish() -> None:
                self._anti_afk_in_progress = False
                self._anti_afk_last_result = summary
                if not show_feedback:
                    return
                if error_message:
                    messagebox.showerror("Anti-AFK", f"Anti-AFK failed:\n{error_message}")
                    return
                if summary.total_windows <= 0:
                    messagebox.showinfo("Anti-AFK", "No Roblox clients were detected.")
                    return
                if summary.failed_windows > 0:
                    messagebox.showwarning(
                        "Anti-AFK",
                        (
                            f"Sent Anti-AFK input to {summary.successful_windows} Roblox client(s).\n"
                            f"Failed clients: {summary.failed_windows}"
                        ),
                    )
                    return
                self.show_success_message(
                    f"Sent Anti-AFK input to {summary.successful_windows} Roblox client(s).",
                    title="Anti-AFK",
                )

            try:
                self.root.after(0, finish)
            except (RuntimeError, tk.TclError):
                self._anti_afk_in_progress = False
                self._anti_afk_last_result = summary

        threading.Thread(target=worker, daemon=True, name="anti-afk").start()

    def _log_anti_afk(self, message: str, debug: bool = False) -> None:
        if debug and not self.settings.get("enable_debug_logging", False):
            return
        level = "DEBUG" if debug else "INFO"
        print(f"[{level}] Anti-AFK: {message}")

    def _roblox_headless_maybe_start(self):
        if self.settings.get("roblox_headless_mode_enabled", False):
            self._log_roblox_headless("NoClient mode is enabled.")
            self._set_roblox_headless_mode_enabled(
                True,
                save=False,
                run_now=True,
                restore_when_disabled=False,
            )

    def _log_roblox_headless(self, message, debug=False):
        if debug and not self.settings.get("enable_debug_logging", False):
            return
        level = "DEBUG" if debug else "INFO"
        print(f"[{level}] {message}")

    def _roblox_headless_config_valid(self):
        if platform.system() != "Windows":
            return False
        if win32gui is None or win32process is None:
            return False
        return bool(self.settings.get("roblox_headless_mode_enabled", False))

    def _cancel_roblox_headless_pass(self):
        after_id = getattr(self, "_roblox_headless_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._roblox_headless_after_id = None

    def _set_roblox_headless_mode_enabled(
        self,
        enabled,
        save=False,
        run_now=False,
        restore_when_disabled=True,
    ):
        enabled = bool(enabled)
        if enabled and platform.system() != "Windows":
            enabled = False

        self.settings["roblox_headless_mode_enabled"] = enabled
        if save:
            self.save_settings()

        self._roblox_headless_generation = int(getattr(self, "_roblox_headless_generation", 0)) + 1
        self._cancel_roblox_headless_pass()

        if not enabled:
            self._log_roblox_headless("NoClient mode disabled.")
            self._roblox_headless_seen_pids = set()
            if restore_when_disabled:
                self.restore_roblox_headless_windows(show_feedback=False)
            return enabled

        self._log_roblox_headless("Client monitor enabled.")
        self._log_roblox_headless(
            (
                f"idle_priority={bool(self.settings.get('roblox_headless_idle_priority', True))}, "
                f"trim_memory={bool(self.settings.get('roblox_headless_trim_memory', True))}, "
                f"scan_interval={self.ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS}s."
            ),
            debug=True,
        )
        self._schedule_roblox_headless_pass(
            delay_ms=50 if run_now else self.ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS * 1000,
        )
        return enabled

    def _schedule_roblox_headless_pass(self, delay_ms=None):
        self._cancel_roblox_headless_pass()
        if not self._roblox_headless_config_valid():
            return

        if delay_ms is None:
            delay_ms = self.ROBLOX_HEADLESS_SCAN_INTERVAL_SECONDS * 1000
        self._roblox_headless_after_id = self.root.after(
            max(100, int(delay_ms)),
            self._run_roblox_headless_pass,
        )

    def _run_roblox_headless_pass(self):
        self._roblox_headless_after_id = None
        if not self._roblox_headless_config_valid():
            return

        if self._roblox_headless_in_progress:
            self._schedule_roblox_headless_pass()
            return

        self._roblox_headless_in_progress = True
        run_generation = int(getattr(self, "_roblox_headless_generation", 0))

        def worker():
            try:
                self._apply_roblox_headless_pass(force_trim=False)
            finally:
                def finish():
                    self._roblox_headless_in_progress = False
                    if (
                        int(getattr(self, "_roblox_headless_generation", 0)) == run_generation
                        and self._roblox_headless_config_valid()
                    ):
                        self._schedule_roblox_headless_pass()

                try:
                    self.root.after(0, finish)
                except Exception:
                    self._roblox_headless_in_progress = False

        threading.Thread(target=worker, daemon=True, name="roblox-headless-mode").start()

    @classmethod
    def _set_process_priority_class(cls, pid, priority_class):
        if not pid or platform.system() != "Windows":
            return False, "invalid pid"

        handle = None
        try:
            kernel32 = ctypes.windll.kernel32
            access = cls._PROCESS_SET_INFORMATION | cls._PROCESS_QUERY_LIMITED_INFORMATION
            handle = kernel32.OpenProcess(access, False, int(pid))
            if not handle:
                err = kernel32.GetLastError()
                return False, f"OpenProcess failed (err={err})"
            ok = kernel32.SetPriorityClass(handle, int(priority_class))
            if ok:
                return True, "ok"
            err = kernel32.GetLastError()
            return False, f"SetPriorityClass failed (err={err})"
        except Exception as exc:
            return False, str(exc)
        finally:
            if handle:
                try:
                    ctypes.windll.kernel32.CloseHandle(handle)
                except Exception:
                    pass

    def _get_roblox_headless_pid_map(self) -> dict[int, str]:
        target_exes = self._normalize_tracked_executable_names(self.ROBLOX_HEADLESS_TARGET_EXECUTABLES)
        snapshot = self._get_tracked_process_window_snapshot(use_cache=False, include_windows=True)
        return {
            int(pid_value): str(image_name or "").strip()
            for pid_value, image_name in snapshot.pid_to_image.items()
            if str(image_name or "").strip().lower() in target_exes
        }

    def _get_roblox_headless_windows(
        self,
        target_pids: Any = None,
        include_hidden: bool = False,
    ) -> list[int]:
        if platform.system() != "Windows":
            return []

        if target_pids is None:
            target_pids = set(self._get_roblox_headless_pid_map().keys())
        else:
            target_pids = self._normalize_pid_set(target_pids)
        if not target_pids:
            return []

        snapshot = self._get_tracked_process_window_snapshot(use_cache=True, include_windows=True)
        windows: list[int] = []
        for record in snapshot.window_records:
            if record.pid not in target_pids:
                continue
            if not include_hidden and not record.is_visible:
                continue
            if record.title or record.class_name == "WINDOWSCLIENT":
                windows.append(record.hwnd)
        return windows

    def _hide_roblox_headless_window(self, hwnd):
        if not hwnd or win32gui is None:
            return False

        changed = False
        try:
            if win32gui.IsWindowVisible(hwnd):
                win32gui.ShowWindow(hwnd, getattr(win32con, "SW_HIDE", 0))
                changed = True
        except Exception:
            pass

        try:
            win32gui.PostMessage(
                hwnd,
                getattr(win32con, "WM_SYSCOMMAND", 0x0112),
                getattr(win32con, "SC_MINIMIZE", 0xF020),
                0,
            )
        except Exception:
            pass

        return changed

    def _get_window_pid_title(self, hwnd):
        pid_value = 0
        title_text = ""
        if not hwnd or win32process is None or win32gui is None:
            return pid_value, title_text

        try:
            _, pid_value = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pid_value = 0

        try:
            title_text = str(win32gui.GetWindowText(hwnd) or "").strip()
        except Exception:
            title_text = ""

        return int(pid_value or 0), title_text

    def _restore_roblox_headless_window(self, hwnd):
        if not hwnd or win32gui is None:
            return False

        try:
            win32gui.ShowWindow(hwnd, getattr(win32con, "SW_SHOW", 5))
            win32gui.ShowWindow(hwnd, getattr(win32con, "SW_RESTORE", 9))
            return True
        except Exception:
            return False

    def _apply_roblox_headless_pass(self, force_trim=False):
        pid_map = self._get_roblox_headless_pid_map()
        pids = set(pid_map.keys())
        if not pids:
            now = time.monotonic()
            if force_trim or (now - float(getattr(self, "_roblox_headless_last_empty_log_ts", 0.0) or 0.0)) >= 30.0:
                self._log_roblox_headless("No Roblox clients detected.")
                self._roblox_headless_last_empty_log_ts = now
            self._roblox_headless_seen_pids = set()
            return {
                "pids": 0,
                "hidden": 0,
                "priority": 0,
                "trimmed": 0,
                "new_pids": [],
                "priority_failures": [],
                "trim_failures": [],
            }

        hidden_count = 0
        priority_count = 0
        trimmed_count = 0
        priority_failures = []
        trim_failures = []
        previous_pids = set(getattr(self, "_roblox_headless_seen_pids", set()) or set())
        new_pids = sorted(pids - previous_pids)
        self._roblox_headless_seen_pids = set(pids)

        visible_windows = self._get_roblox_headless_windows(target_pids=pids, include_hidden=False)
        for hwnd in visible_windows:
            if self._hide_roblox_headless_window(hwnd):
                hidden_count += 1
                pid_value, title_text = self._get_window_pid_title(hwnd)
                self._log_roblox_headless(
                    f"Hidden Roblox window hwnd={int(hwnd)} pid={pid_value} title={title_text or '(untitled)'}.",
                    debug=True,
                )

        if self.settings.get("roblox_headless_idle_priority", True):
            for pid in pids:
                ok, msg = self._set_process_priority_class(pid, self._IDLE_PRIORITY_CLASS)
                if ok:
                    priority_count += 1
                else:
                    priority_failures.append((pid, msg))
        else:
            for pid in pids:
                self._set_process_priority_class(pid, self._NORMAL_PRIORITY_CLASS)

        if self.settings.get("roblox_headless_trim_memory", True):
            now = time.monotonic()
            should_trim = force_trim or (
                now - float(getattr(self, "_roblox_headless_last_trim_ts", 0.0) or 0.0)
            ) >= self.ROBLOX_HEADLESS_MEMORY_TRIM_INTERVAL_SECONDS
            if should_trim:
                for pid in pids:
                    ok, msg = self._memtrim_pid(pid)
                    if ok:
                        trimmed_count += 1
                    else:
                        trim_failures.append((pid, msg))
                self._roblox_headless_last_trim_ts = now

        should_log_info_summary = bool(new_pids or hidden_count or force_trim)
        should_log_debug_summary = bool(
            should_log_info_summary or trimmed_count or priority_failures or trim_failures
        )
        if should_log_info_summary:
            self._log_roblox_headless(
                (
                    f"Processed {len(pids)} Roblox client(s): "
                    f"hidden {hidden_count} window(s), "
                    f"trimmed {trimmed_count} process(es)."
                )
            )
        if should_log_debug_summary:
            self._log_roblox_headless(
                (
                    f"Pass details: new_pids={new_pids or 'none'}, "
                    f"idle_priority_ok={priority_count}, "
                    f"priority_failures={len(priority_failures)}, "
                    f"trim_failures={len(trim_failures)}."
                ),
                debug=True,
            )
            for pid, msg in priority_failures[:5]:
                self._log_roblox_headless(f"Priority failed for pid={pid}: {msg}", debug=True)
            if len(priority_failures) > 5:
                self._log_roblox_headless(
                    f"Priority failed for {len(priority_failures) - 5} more process(es).",
                    debug=True,
                )
            for pid, msg in trim_failures[:5]:
                self._log_roblox_headless(f"Memory trim failed for pid={pid}: {msg}", debug=True)
            if len(trim_failures) > 5:
                self._log_roblox_headless(
                    f"Memory trim failed for {len(trim_failures) - 5} more process(es).",
                    debug=True,
                )

        return {
            "pids": len(pids),
            "hidden": hidden_count,
            "priority": priority_count,
            "trimmed": trimmed_count,
            "new_pids": new_pids,
            "priority_failures": priority_failures,
            "trim_failures": trim_failures,
        }

    def apply_roblox_headless_once(self, show_feedback=True):
        if platform.system() != "Windows":
            if show_feedback:
                messagebox.showerror("Headless Mode", "This feature is only available on Windows.")
            return

        def worker():
            self._log_roblox_headless("Manual Apply Now requested.")
            summary = self._apply_roblox_headless_pass(force_trim=True)

            def finish():
                if not show_feedback:
                    return
                if int(summary.get("pids", 0) or 0) <= 0:
                    messagebox.showinfo("Headless Mode", "No Roblox clients were detected.")
                    return
                self.show_success_message(
                    (
                        f"Applied headless mode to {summary['pids']} Roblox process(es).\n"
                        f"Hidden windows: {summary['hidden']}\n"
                        f"Idle priority set: {summary['priority']}\n"
                        f"Memory trimmed: {summary['trimmed']}"
                    ),
                    title="Headless Mode",
                )

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="roblox-headless-once").start()

    def _restore_roblox_headless_pass(self):
        pid_map = self._get_roblox_headless_pid_map()
        pids = set(pid_map.keys())
        restored_count = 0
        priority_count = 0
        restore_failures = []
        priority_failures = []

        windows = self._get_roblox_headless_windows(target_pids=pids, include_hidden=True)
        for hwnd in windows:
            pid_value, title_text = self._get_window_pid_title(hwnd)
            if self._restore_roblox_headless_window(hwnd):
                restored_count += 1
                self._log_roblox_headless(
                    f"Restored Roblox window hwnd={int(hwnd)} pid={pid_value} title={title_text or '(untitled)'}.",
                    debug=True,
                )
            else:
                restore_failures.append((int(hwnd), pid_value))

        for pid in pids:
            ok, msg = self._set_process_priority_class(pid, self._NORMAL_PRIORITY_CLASS)
            if ok:
                priority_count += 1
            else:
                priority_failures.append((pid, msg))

        self._roblox_headless_seen_pids = set()
        self._log_roblox_headless(
            (
                f"Restore complete: clients={len(pids)}, "
                f"restored_windows={restored_count}, "
                f"normal_priority_ok={priority_count}."
            )
        )
        for hwnd, pid in restore_failures[:5]:
            self._log_roblox_headless(f"Restore failed for hwnd={hwnd} pid={pid}.", debug=True)
        if len(restore_failures) > 5:
            self._log_roblox_headless(
                f"Restore failed for {len(restore_failures) - 5} more window(s).",
                debug=True,
            )
        for pid, msg in priority_failures[:5]:
            self._log_roblox_headless(f"Normal priority failed for pid={pid}: {msg}", debug=True)
        if len(priority_failures) > 5:
            self._log_roblox_headless(
                f"Normal priority failed for {len(priority_failures) - 5} more process(es).",
                debug=True,
            )

        return {
            "pids": len(pids),
            "restored": restored_count,
            "priority": priority_count,
            "restore_failures": restore_failures,
            "priority_failures": priority_failures,
        }

    def restore_roblox_headless_windows(self, show_feedback=True):
        if platform.system() != "Windows":
            if show_feedback:
                messagebox.showerror("Headless Mode", "This feature is only available on Windows.")
            return

        def worker():
            self._log_roblox_headless("Restore Windows requested.")
            summary = self._restore_roblox_headless_pass()

            def finish():
                if not show_feedback:
                    return
                if int(summary.get("pids", 0) or 0) <= 0:
                    messagebox.showinfo("Headless Mode", "No Roblox clients were detected.")
                    return
                self.show_success_message(
                    (
                        f"Restored {summary['restored']} Roblox window(s).\n"
                        f"Normal priority set: {summary['priority']} process(es)."
                    ),
                    title="Headless Mode",
                )

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True, name="roblox-headless-restore").start()

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

    def _mark_active_sessions_manually_stopped(self, usernames=None, pids=None):
        cleared_usernames = set()
        self._invalidate_active_client_indicator_cache()

        for username in list(usernames or []):
            normalized_username = str(username or "").strip()
            if not normalized_username:
                continue
            try:
                if self.manager.mark_session_intentionally_closed(username=normalized_username):
                    cleared_usernames.add(normalized_username)
            except Exception:
                continue

        for raw_pid in list(pids or []):
            try:
                pid_value = int(raw_pid)
            except Exception:
                continue
            if pid_value <= 0:
                continue

            mapped_username = ""
            try:
                with self._pid_account_lock:
                    mapped_username = str(self._pid_account_map.get(pid_value, "") or "").strip()
            except Exception:
                mapped_username = ""

            try:
                if self.manager.mark_session_intentionally_closed(
                    username=mapped_username or None,
                    pid=pid_value,
                ):
                    if mapped_username:
                        cleared_usernames.add(mapped_username)
            except Exception:
                continue

        for username in cleared_usernames:
            self.set_account_rejoin_status(username, "", 0)
        return cleared_usernames

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
        self.BG_FRAME = theme["frame_bg"]
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
            padding=6,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
        )
        self.style.map(
            "Dark.TButton",
            background=[("active", self.HOVER_BG)],
            foreground=[("disabled", self.FG_MUTED)],
        )
        self.style.configure(
            "Dark.TEntry",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
        )
        self.style.configure(
            "Dark.TCombobox",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
            arrowcolor=self.FG_TEXT,
        )
        self.style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", self.ENTRY_BG)],
            foreground=[("readonly", self.ENTRY_FG)],
            arrowcolor=[("active", self.FG_ACCENT_ALT), ("readonly", self.FG_TEXT)],
        )
        self.style.configure(
            "Dark.TSpinbox",
            fieldbackground=self.ENTRY_BG,
            background=self.ENTRY_BG,
            foreground=self.ENTRY_FG,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
            arrowcolor=self.FG_TEXT,
        )
        self.style.map(
            "Dark.TSpinbox",
            fieldbackground=[("readonly", self.ENTRY_BG)],
            foreground=[("readonly", self.ENTRY_FG)],
            arrowcolor=[("active", self.FG_ACCENT_ALT), ("readonly", self.FG_TEXT)],
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
            indicatorbackground=self.ENTRY_BG,
            indicatorforeground=self.FG_ACCENT,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
        )
        self.style.map(
            "Dark.TCheckbutton",
            background=[("active", self.BG_MID)],
            foreground=[("disabled", self.FG_MUTED)],
        )
        for notebook_style in ("TNotebook", "Dark.TNotebook"):
            self.style.configure(
                notebook_style,
                background=self.BG_FRAME,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.BORDER_COLOR,
                darkcolor=self.BORDER_COLOR,
            )
        for notebook_tab_style in ("TNotebook.Tab", "Dark.TNotebook.Tab"):
            self.style.configure(
                notebook_tab_style,
                background=self.BG_MID,
                foreground=self.FG_MUTED,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.BORDER_COLOR,
                darkcolor=self.BORDER_COLOR,
                padding=(12, 6),
                font=self.FONT,
            )
            self.style.map(
                notebook_tab_style,
                background=[("selected", self.BG_LIGHT), ("active", self.HOVER_BG)],
                foreground=[("selected", self.FG_TEXT), ("active", self.FG_TEXT)],
            )
        for scrollbar_style in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
            self.style.configure(
                scrollbar_style,
                background=self.BG_LIGHT,
                troughcolor=self.BG_FRAME,
                arrowcolor=self.FG_TEXT,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.BORDER_COLOR,
                darkcolor=self.BORDER_COLOR,
            )
            self.style.map(
                scrollbar_style,
                background=[("active", self.HOVER_BG)],
                arrowcolor=[("active", self.FG_ACCENT_ALT)],
            )
        for progressbar_style in (
            "Horizontal.TProgressbar",
            "Vertical.TProgressbar",
            "Dark.Horizontal.TProgressbar",
            "Dark.Vertical.TProgressbar",
        ):
            self.style.configure(
                progressbar_style,
                background=self.FG_ACCENT,
                troughcolor=self.BG_FRAME,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.FG_ACCENT_ALT,
                darkcolor=self.FG_ACCENT,
            )
        for scale_style in ("Horizontal.TScale", "Vertical.TScale", "Dark.Horizontal.TScale", "Dark.Vertical.TScale"):
            self.style.configure(
                scale_style,
                background=self.FG_ACCENT,
                troughcolor=self.BG_FRAME,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.FG_ACCENT_ALT,
                darkcolor=self.FG_ACCENT,
            )
            self.style.map(scale_style, background=[("active", self.FG_ACCENT_ALT)])
        for radiobutton_style in ("TRadiobutton", "Dark.TRadiobutton"):
            self.style.configure(
                radiobutton_style,
                background=self.BG_DARK,
                foreground=self.FG_TEXT,
                font=self.FONT,
                indicatorbackground=self.ENTRY_BG,
                indicatorforeground=self.FG_ACCENT,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.BORDER_COLOR,
                darkcolor=self.BORDER_COLOR,
            )
            self.style.map(
                radiobutton_style,
                background=[("active", self.BG_MID)],
                foreground=[("disabled", self.FG_MUTED)],
            )
        for panedwindow_style in ("TPanedwindow", "Dark.TPanedwindow"):
            self.style.configure(
                panedwindow_style,
                background=self.BG_FRAME,
                bordercolor=self.BORDER_COLOR,
                lightcolor=self.BORDER_COLOR,
                darkcolor=self.BORDER_COLOR,
            )
        self.style.configure(
            "Sash",
            background=self.BG_LIGHT,
            troughcolor=self.BG_FRAME,
            bordercolor=self.BORDER_COLOR,
            lightcolor=self.BORDER_COLOR,
            darkcolor=self.BORDER_COLOR,
            sashthickness=8,
        )

        if getattr(self, "status_label", None):
            self.status_label.configure(bg=self.BG_DARK)

        if getattr(self, "anti_afk_next_window", None):
            self.anti_afk_next_window.configure(bg=self.BG_MID, highlightbackground=self.BORDER_COLOR)

        if getattr(self, "anti_afk_next_label", None):
            self.anti_afk_next_label.configure(bg=self.BG_MID, fg=self.FG_TEXT)

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

    def register_toplevel(self, window: Any) -> None:
        if window in self.themable_windows:
            self._apply_window_icon(window)
            self._apply_title_bar_theme(window)
            return

        self.themable_windows.add(window)

        def _cleanup(event: tk.Event, win: Any = window) -> None:
            self.themable_windows.discard(win)
            self._theme_refresh_callbacks.pop(win, None)

        try:
            window.bind("<Destroy>", _cleanup, add="+")
            window.bind("<Map>", self._handle_window_map, add="+")
        except (AttributeError, RuntimeError, tk.TclError):
            pass

        self._apply_window_icon(window)
        self._apply_title_bar_theme(window)

    def set_icon_path(self, icon_path: Optional[str]) -> None:
        if not icon_path:
            return

        try:
            icon_file_path = Path(icon_path)
            if not icon_file_path.is_file():
                return
        except (OSError, ValueError):
            return

        self.icon_path = str(icon_file_path)
        self._apply_window_icon_all()

    def _apply_window_icon_all(self) -> None:
        stale_windows: list[Any] = []
        for window in list(self.themable_windows):
            try:
                if window.winfo_exists():
                    self._apply_window_icon(window)
                else:
                    stale_windows.append(window)
            except (AttributeError, RuntimeError, tk.TclError):
                stale_windows.append(window)

        for window in stale_windows:
            self.themable_windows.discard(window)

    def _apply_window_icon(self, window: Any) -> None:
        icon_path = str(self.icon_path or "").strip()
        if not icon_path:
            return

        try:
            if not Path(icon_path).is_file():
                return
        except (OSError, ValueError):
            return

        try:
            window.iconbitmap(icon_path)
        except tk.TclError:
            pass

        try:
            window.iconbitmap(default=icon_path)
        except tk.TclError:
            pass

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

        vip_btn = tk.Button(
            self.menu_bar_frame,
            text="VIP Servers",
            command=self.open_vip_server_manager,
            relief="flat",
            borderwidth=0,
            highlightthickness=0
        )
        vip_btn.pack(side="left", padx=(0, 8))
        self.menu_buttons.append(vip_btn)

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

    def open_recent_list_editor(self) -> None:
        launch_mode = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
        if launch_mode == "join_user":
            self.open_recent_users_editor()
            return
        self.open_recent_games_editor()

    def open_recent_games_editor(self) -> None:
        games = self.settings.get("game_list", [])
        if not isinstance(games, list):
            games = []
            self.settings["game_list"] = games

        window = tk.Toplevel(self.root)
        window.title("Edit Recent Games")
        window.geometry("900x560")
        window.minsize(760, 460)
        window.configure(bg=self.BG_DARK)
        window.transient(self.root)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        selected_index_var = tk.IntVar(value=-1)
        list_view_var = tk.BooleanVar(value=False)
        search_var = tk.StringVar(value="")
        name_var = tk.StringVar(value="")
        place_id_var = tk.StringVar(value="")
        private_server_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="")
        requested_icon_place_ids: set[str] = set()
        last_canvas_width = [0]

        main = ttk.Frame(window, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=10, pady=10)

        toolbar = ttk.Frame(main, style="Dark.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            toolbar,
            text="List View",
            variable=list_view_var,
            style="Dark.TCheckbutton",
            command=lambda: render_games(),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        search_entry = ttk.Entry(toolbar, textvariable=search_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=1, sticky="ew")

        ttk.Button(
            toolbar,
            text="Search",
            style="Dark.TButton",
            command=lambda: render_games(),
        ).grid(row=0, column=2, sticky="e", padx=(8, 0))

        body = ttk.Frame(main, style="Dark.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=0, minsize=240)
        body.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            body,
            bg=self.BG_DARK,
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        tile_host = tk.Frame(canvas, bg=self.BG_DARK, highlightthickness=0, bd=0)
        canvas_window = canvas.create_window((0, 0), window=tile_host, anchor="nw")

        detail_panel = ttk.Frame(body, style="Dark.TFrame")
        detail_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        detail_panel.configure(width=240)
        detail_panel.grid_propagate(False)
        detail_panel.columnconfigure(0, weight=1)

        ttk.Label(detail_panel, text="Selected Game", style="Dark.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        ttk.Label(detail_panel, text="Place Name", style="Dark.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(detail_panel, textvariable=name_var, style="Dark.TEntry").grid(row=2, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(detail_panel, text="Place ID", style="Dark.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Entry(detail_panel, textvariable=place_id_var, style="Dark.TEntry").grid(row=4, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(detail_panel, text="Private Server ID", style="Dark.TLabel").grid(row=5, column=0, sticky="w")
        ttk.Entry(detail_panel, textvariable=private_server_var, style="Dark.TEntry").grid(row=6, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(detail_panel, textvariable=status_var, style="Dark.TLabel", wraplength=220).grid(
            row=7,
            column=0,
            sticky="ew",
            pady=(0, 10),
        )

        ttk.Button(detail_panel, text="Use Selected", style="Dark.TButton", command=lambda: use_selected()).grid(
            row=8,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Save Changes", style="Dark.TButton", command=lambda: save_selected()).grid(
            row=9,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Delete Selected", style="Dark.TButton", command=lambda: delete_selected()).grid(
            row=10,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Close", style="Dark.TButton", command=window.destroy).grid(
            row=11,
            column=0,
            sticky="ew",
        )

        def get_games() -> list[Any]:
            game_rows = self.settings.get("game_list", [])
            if not isinstance(game_rows, list):
                game_rows = []
                self.settings["game_list"] = game_rows
            return game_rows

        def get_game_text(game: Any, key: str) -> str:
            if not isinstance(game, dict):
                return ""
            return str(game.get(key) or "").strip()

        def filtered_games() -> list[tuple[int, Any]]:
            query = search_var.get().strip().lower()
            matches: list[tuple[int, Any]] = []
            for index, game in enumerate(get_games()):
                name = get_game_text(game, "name")
                place_id = get_game_text(game, "place_id")
                private_server = get_game_text(game, "private_server")
                haystack = f"{name} {place_id} {private_server}".lower()
                if query and query not in haystack:
                    continue
                matches.append((index, game))
            return matches

        def set_selected(index: int) -> None:
            game_rows = get_games()
            if index < 0 or index >= len(game_rows):
                selected_index_var.set(-1)
                name_var.set("")
                place_id_var.set("")
                private_server_var.set("")
                status_var.set("")
                render_games()
                return

            game = game_rows[index]
            selected_index_var.set(index)
            name_var.set(get_game_text(game, "name"))
            place_id_var.set(get_game_text(game, "place_id"))
            private_server_var.set(get_game_text(game, "private_server"))
            status_var.set("")
            render_games()

        def refresh_after_icon_fetch(_place_id: str) -> None:
            try:
                if not window.winfo_exists():
                    return
            except tk.TclError:
                return
            render_games()

        def shorten_card_value(value: str, max_length: int) -> str:
            normalized_value = str(value or "").strip()
            if len(normalized_value) <= max_length:
                return normalized_value
            if max_length <= 3:
                return normalized_value[:max_length]
            return f"{normalized_value[:max_length - 3]}..."

        def make_tile(parent: tk.Widget, row_index: int, game: Any, row: int, column: int) -> None:
            is_list_view = bool(list_view_var.get())
            selected = row_index == selected_index_var.get()
            background = self.BG_LIGHT if selected else self.BG_MID
            border = self.FG_ACCENT if selected else self.BORDER_COLOR
            tile = tk.Frame(
                parent,
                bg=background,
                highlightbackground=border,
                highlightthickness=2 if selected else 1,
                bd=0,
                width=1 if is_list_view else 178,
                height=92 if is_list_view else 1,
            )
            tile.grid(row=row, column=column, sticky="ew", padx=6, pady=6)
            tile.grid_propagate(not is_list_view)
            tile.columnconfigure(0, weight=0 if is_list_view else 1)
            tile.columnconfigure(1, weight=1 if is_list_view else 0)
            tile.rowconfigure(0, weight=1 if is_list_view else 0)

            name = get_game_text(game, "name") or "Unknown Place"
            place_id = get_game_text(game, "place_id")
            private_server = get_game_text(game, "private_server")

            preview_size = 62 if is_list_view else 86
            preview = tk.Frame(tile, bg=self.BG_DARK, width=preview_size, height=preview_size, highlightthickness=0, bd=0)
            if is_list_view:
                preview.grid(row=0, column=0, sticky="nw", padx=8, pady=8)
            else:
                preview.grid(row=0, column=0, sticky="n", padx=8, pady=(8, 4))
            preview.grid_propagate(False)
            icon_display_size = 58 if is_list_view else 78
            icon_image = self._load_cached_place_icon_image(place_id, icon_display_size)
            preview_label = tk.Label(
                preview,
                text="" if icon_image is not None else "PLACE",
                image=icon_image if icon_image is not None else "",
                bg=self.BG_DARK,
                fg=self.FG_ACCENT_ALT,
                font=("Segoe UI", 8, "bold"),
            )
            if icon_image is not None:
                preview_label.image = icon_image
            elif place_id and place_id not in requested_icon_place_ids:
                requested_icon_place_ids.add(place_id)
                self._queue_place_icon_fetch(place_id, refresh_after_icon_fetch)
            preview_label.place(relx=0.5, rely=0.5, anchor="center")

            text_frame = tk.Frame(tile, bg=background, highlightthickness=0, bd=0)
            if is_list_view:
                text_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
            else:
                text_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 8))
            text_frame.columnconfigure(0, weight=1)

            wrap_length = max(160, int(canvas.winfo_width() or 520) - 120) if is_list_view else 150

            name_label = tk.Label(
                text_frame,
                text=name,
                bg=background,
                fg=self.FG_TEXT,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                justify="left",
                wraplength=wrap_length,
            )
            name_label.grid(row=0, column=0, sticky="ew")
            id_label = tk.Label(
                text_frame,
                text=f"ID: {place_id or 'Unknown'}",
                bg=background,
                fg=self.FG_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
                wraplength=wrap_length,
            )
            id_label.grid(row=1, column=0, sticky="ew", pady=(3, 0))

            private_label = None
            if private_server:
                private_text = shorten_card_value(private_server, 54) if is_list_view else private_server
                private_label = tk.Label(
                    text_frame,
                    text=f"Private: {private_text}",
                    bg=background,
                    fg=self.FG_ACCENT_ALT,
                    font=("Segoe UI", 8),
                    anchor="w",
                    justify="left",
                    wraplength=wrap_length,
                )
                private_label.grid(row=2, column=0, sticky="ew", pady=(3, 0))

            clickable_widgets = [tile, preview, preview_label, text_frame, name_label, id_label]
            if private_label is not None:
                clickable_widgets.append(private_label)
            for widget in clickable_widgets:
                widget.bind("<Button-1>", lambda _event, selected_index=row_index: set_selected(selected_index))

        def get_tile_column_count() -> int:
            if list_view_var.get():
                return 1

            canvas_width = int(canvas.winfo_width() or 0)
            if canvas_width <= 1:
                canvas_width = 600
            return max(1, min(3, canvas_width // 192))

        def render_games() -> None:
            for child in tile_host.winfo_children():
                child.destroy()

            visible_games = filtered_games()
            if not visible_games:
                tk.Label(
                    tile_host,
                    text="No recent games found.",
                    bg=self.BG_DARK,
                    fg=self.FG_MUTED,
                    font=("Segoe UI", 10),
                ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            else:
                columns = get_tile_column_count()
                for column_index in range(3):
                    tile_host.columnconfigure(
                        column_index,
                        weight=1 if column_index < columns else 0,
                        minsize=0,
                        uniform="recent_game_tiles" if column_index < columns else "",
                    )
                for visible_index, (game_index, game) in enumerate(visible_games):
                    row = visible_index // columns
                    column = visible_index % columns
                    make_tile(tile_host, game_index, game, row, column)

            tile_host.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        def save_selected() -> None:
            index = selected_index_var.get()
            game_rows = get_games()
            if index < 0 or index >= len(game_rows):
                status_var.set("Select a game first.")
                return

            place_id = place_id_var.get().strip()
            if not place_id:
                status_var.set("Place ID is required.")
                return

            private_server = self.manager.normalize_private_server(private_server_var.get().strip())
            private_server_var.set(private_server)
            game_rows[index] = {
                "place_id": place_id,
                "name": name_var.get().strip() or f"Place {place_id}",
                "private_server": private_server,
            }
            self.save_settings()
            self.refresh_game_list()
            status_var.set("Saved.")
            render_games()

        def use_selected() -> None:
            index = selected_index_var.get()
            game_rows = get_games()
            if index < 0 or index >= len(game_rows):
                status_var.set("Select a game first.")
                return

            game = game_rows[index]
            place_id = get_game_text(game, "place_id")
            private_server = self.manager.normalize_private_server(get_game_text(game, "private_server"))
            if not place_id:
                status_var.set("Selected game does not have a Place ID.")
                return

            self._set_launch_input_mode("place_id", save=True)
            self.place_entry.delete(0, tk.END)
            self.place_entry.insert(0, place_id)
            self.private_server_entry.delete(0, tk.END)
            self.private_server_entry.insert(0, private_server)
            self.settings["last_place_id"] = place_id
            self.settings["last_private_server"] = private_server
            self.save_settings()
            self.update_game_name()
            status_var.set("Loaded into launcher.")

        def delete_selected() -> None:
            index = selected_index_var.get()
            game_rows = get_games()
            if index < 0 or index >= len(game_rows):
                status_var.set("Select a game first.")
                return

            game = game_rows[index]
            name = get_game_text(game, "name") or get_game_text(game, "place_id") or "this game"
            confirm = messagebox.askyesno("Confirm Delete", f"Delete '{name}' from recent games?", parent=window)
            if not confirm:
                return

            game_rows.pop(index)
            self.save_settings()
            self.refresh_game_list()
            selected_index_var.set(-1)
            name_var.set("")
            place_id_var.set("")
            private_server_var.set("")
            status_var.set("Deleted.")
            render_games()

        def resize_canvas(event: tk.Event) -> None:
            width = max(1, int(event.width))
            canvas.itemconfigure(canvas_window, width=width)
            previous_width = int(last_canvas_width[0] or 0)
            if previous_width <= 0:
                last_canvas_width[0] = width
                render_games()
                return
            if abs(width - previous_width) < 64:
                return
            last_canvas_width[0] = width
            render_games()

        search_var.trace_add("write", lambda *_args: render_games())
        tile_host.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", resize_canvas)
        window.bind("<Escape>", lambda _event: window.destroy())

        render_games()
        if filtered_games():
            set_selected(filtered_games()[0][0])
        window.update_idletasks()
        self._center_window(window, max(900, window.winfo_reqwidth() + 40), max(560, window.winfo_reqheight() + 40))

    def open_recent_users_editor(self) -> None:
        users = self.settings.get("recent_user_list", [])
        if not isinstance(users, list):
            users = []
            self.settings["recent_user_list"] = users

        window = tk.Toplevel(self.root)
        window.title("Edit Recent Users")
        window.geometry("640x440")
        window.minsize(540, 360)
        window.configure(bg=self.BG_DARK)
        window.transient(self.root)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        selected_index_var = tk.IntVar(value=-1)
        search_var = tk.StringVar(value="")
        username_var = tk.StringVar(value="")
        user_id_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="")
        requested_icon_user_ids: set[str] = set()

        main = ttk.Frame(window, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=12, pady=12)

        toolbar = ttk.Frame(main, style="Dark.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)

        search_entry = ttk.Entry(toolbar, textvariable=search_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            toolbar,
            text="Search",
            style="Dark.TButton",
            command=lambda: render_users(),
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        body = ttk.Frame(main, style="Dark.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=0, minsize=230)
        body.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(body, style="Dark.TFrame")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        user_canvas = tk.Canvas(
            list_frame,
            bg=self.BG_MID,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            highlightthickness=1,
            bd=0,
        )
        user_canvas.grid(row=0, column=0, sticky="nsew")
        user_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=user_canvas.yview)
        user_scrollbar.grid(row=0, column=1, sticky="ns")
        user_canvas.configure(yscrollcommand=user_scrollbar.set)
        user_row_host = tk.Frame(user_canvas, bg=self.BG_MID, highlightthickness=0, bd=0)
        user_canvas_window = user_canvas.create_window((0, 0), window=user_row_host, anchor="nw")

        detail_panel = ttk.Frame(body, style="Dark.TFrame")
        detail_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        detail_panel.configure(width=230)
        detail_panel.grid_propagate(False)
        detail_panel.columnconfigure(0, weight=1)

        ttk.Label(detail_panel, text="Selected User", style="Dark.TLabel", font=("Segoe UI", 10, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        ttk.Label(detail_panel, text="Username", style="Dark.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(detail_panel, textvariable=username_var, style="Dark.TEntry").grid(row=2, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(detail_panel, text="User ID", style="Dark.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Entry(detail_panel, textvariable=user_id_var, style="Dark.TEntry").grid(row=4, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(detail_panel, textvariable=status_var, style="Dark.TLabel", wraplength=210).grid(
            row=5,
            column=0,
            sticky="ew",
            pady=(0, 10),
        )
        ttk.Button(detail_panel, text="Use Selected", style="Dark.TButton", command=lambda: use_selected_user()).grid(
            row=6,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Resolve", style="Dark.TButton", command=lambda: resolve_user_details()).grid(
            row=7,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Save Changes", style="Dark.TButton", command=lambda: save_selected_user()).grid(
            row=8,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Delete Selected", style="Dark.TButton", command=lambda: delete_selected_user()).grid(
            row=9,
            column=0,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(detail_panel, text="Close", style="Dark.TButton", command=window.destroy).grid(
            row=10,
            column=0,
            sticky="ew",
        )

        def get_users() -> list[Any]:
            user_rows = self.settings.get("recent_user_list", [])
            if not isinstance(user_rows, list):
                user_rows = []
                self.settings["recent_user_list"] = user_rows
            return user_rows

        def get_user_text(user: Any, key: str) -> str:
            if not isinstance(user, dict):
                return ""
            return str(user.get(key) or "").strip()

        def get_user_display_text(user: Any) -> str:
            user_id = get_user_text(user, "user_id")
            username = get_user_text(user, "username")
            if username and user_id:
                return f"{username} ({user_id})"
            return username or user_id or "Unknown User"

        def filtered_users() -> list[tuple[int, Any]]:
            query = search_var.get().strip().lower()
            matches: list[tuple[int, Any]] = []
            for index, user in enumerate(get_users()):
                if not isinstance(user, dict):
                    continue
                user_id = get_user_text(user, "user_id")
                username = get_user_text(user, "username")
                if not user_id and not username:
                    continue
                haystack = f"{username} {user_id}".lower()
                if query and query not in haystack:
                    continue
                matches.append((index, user))
            return matches

        def set_selected_user(index: int) -> None:
            user_rows = get_users()
            if index < 0 or index >= len(user_rows):
                selected_index_var.set(-1)
                username_var.set("")
                user_id_var.set("")
                status_var.set("")
                render_users()
                return

            user = user_rows[index]
            selected_index_var.set(index)
            username_var.set(get_user_text(user, "username"))
            user_id_var.set(get_user_text(user, "user_id"))
            status_var.set("")
            render_users()

        def refresh_after_user_icon_fetch(_user_id: str) -> None:
            try:
                if not window.winfo_exists():
                    return
            except tk.TclError:
                return
            render_users()

        def make_user_row(parent: tk.Widget, row_index: int, user: Any, row: int) -> None:
            selected = row_index == selected_index_var.get()
            background = self.BG_LIGHT if selected else self.BG_MID
            border = self.FG_ACCENT if selected else self.BORDER_COLOR
            row_frame = tk.Frame(
                parent,
                bg=background,
                highlightbackground=border,
                highlightthickness=2 if selected else 1,
                bd=0,
                height=68,
            )
            row_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=4)
            row_frame.grid_propagate(False)
            row_frame.columnconfigure(1, weight=1)

            user_id = get_user_text(user, "user_id")
            username = get_user_text(user, "username") or "Unknown User"
            avatar_frame = tk.Frame(row_frame, bg=self.BG_DARK, width=50, height=50, highlightthickness=0, bd=0)
            avatar_frame.grid(row=0, column=0, sticky="nw", padx=8, pady=8)
            avatar_frame.grid_propagate(False)

            avatar_image = self._load_cached_user_icon_image(user_id, 48)
            avatar_label = tk.Label(
                avatar_frame,
                text="" if avatar_image is not None else "USER",
                image=avatar_image if avatar_image is not None else "",
                bg=self.BG_DARK,
                fg=self.FG_ACCENT_ALT,
                font=("Segoe UI", 8, "bold"),
            )
            if avatar_image is not None:
                avatar_label.image = avatar_image
            elif user_id and user_id not in requested_icon_user_ids:
                requested_icon_user_ids.add(user_id)
                self._queue_user_icon_fetch(user_id, refresh_after_user_icon_fetch)
            avatar_label.place(relx=0.5, rely=0.5, anchor="center")

            text_frame = tk.Frame(row_frame, bg=background, highlightthickness=0, bd=0)
            text_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
            text_frame.columnconfigure(0, weight=1)

            username_label = tk.Label(
                text_frame,
                text=username,
                bg=background,
                fg=self.FG_TEXT,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
                justify="left",
            )
            username_label.grid(row=0, column=0, sticky="ew")
            user_id_label = tk.Label(
                text_frame,
                text=f"ID: {user_id or 'Unknown'}",
                bg=background,
                fg=self.FG_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
            )
            user_id_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))

            clickable_widgets = [row_frame, avatar_frame, avatar_label, text_frame, username_label, user_id_label]
            for widget in clickable_widgets:
                widget.bind("<Button-1>", lambda _event, selected_index=row_index: set_selected_user(selected_index))
                widget.bind("<Double-Button-1>", lambda _event: use_selected_user())

        def render_users() -> None:
            for child in user_row_host.winfo_children():
                child.destroy()

            user_row_host.columnconfigure(0, weight=1)
            visible_users = filtered_users()
            if not visible_users:
                tk.Label(
                    user_row_host,
                    text="No recent users found.",
                    bg=self.BG_MID,
                    fg=self.FG_MUTED,
                    font=("Segoe UI", 10),
                ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            else:
                for visible_index, (actual_index, user) in enumerate(visible_users):
                    make_user_row(user_row_host, actual_index, user, visible_index)

            user_row_host.update_idletasks()
            user_canvas.configure(scrollregion=user_canvas.bbox("all"))

        def save_selected_user() -> None:
            index = selected_index_var.get()
            user_rows = get_users()
            if index < 0 or index >= len(user_rows):
                status_var.set("Select a user first.")
                return

            username = username_var.get().strip()
            user_id = user_id_var.get().strip()
            if not user_id:
                status_var.set("User ID is required.")
                return
            if not user_id.isdigit():
                status_var.set("User ID must be numeric.")
                return

            for other_index in range(len(user_rows) - 1, -1, -1):
                if other_index == index:
                    continue
                other_user_id = get_user_text(user_rows[other_index], "user_id")
                if other_user_id != user_id:
                    continue
                user_rows.pop(other_index)
                if other_index < index:
                    index -= 1

            user_rows[index] = {"user_id": user_id, "username": username}
            selected_index_var.set(index)
            self.save_settings()
            self.refresh_game_list()
            status_var.set("Saved.")
            render_users()

        def use_selected_user() -> None:
            index = selected_index_var.get()
            user_rows = get_users()
            if index < 0 or index >= len(user_rows):
                status_var.set("Select a user first.")
                return

            user = user_rows[index]
            value = get_user_text(user, "username") or get_user_text(user, "user_id")
            if not value:
                status_var.set("Selected user is empty.")
                return

            self._set_launch_input_mode("join_user", save=True)
            self.place_entry.delete(0, tk.END)
            self.place_entry.insert(0, value)
            self.settings["last_user"] = value
            self.save_settings()
            self.update_game_name()
            status_var.set("Loaded into launcher.")

        def delete_selected_user() -> None:
            index = selected_index_var.get()
            user_rows = get_users()
            if index < 0 or index >= len(user_rows):
                status_var.set("Select a user first.")
                return

            user = user_rows[index]
            display_name = get_user_display_text(user)
            confirm = messagebox.askyesno("Confirm Delete", f"Delete '{display_name}' from recent users?", parent=window)
            if not confirm:
                return

            user_rows.pop(index)
            self.save_settings()
            self.refresh_game_list()
            selected_index_var.set(-1)
            username_var.set("")
            user_id_var.set("")
            status_var.set("Deleted.")
            render_users()

        def resolve_user_details() -> None:
            username = username_var.get().strip()
            user_id = user_id_var.get().strip()
            if user_id and not user_id.isdigit():
                status_var.set("User ID must be numeric.")
                return
            if not username and not user_id:
                status_var.set("Enter a username or User ID first.")
                return

            status_var.set("Resolving...")

            def worker(username_text: str, user_id_text: str) -> None:
                resolved_user_id = user_id_text
                resolved_username = username_text
                if resolved_user_id and not resolved_username:
                    resolved_username = RobloxAPI.get_username_from_user_id(resolved_user_id) or ""
                elif resolved_username:
                    resolved_user_id = RobloxAPI.get_user_id_from_username(resolved_username) or resolved_user_id
                    if resolved_user_id and not resolved_username:
                        resolved_username = RobloxAPI.get_username_from_user_id(resolved_user_id) or ""

                def apply_result() -> None:
                    try:
                        if not window.winfo_exists():
                            return
                    except tk.TclError:
                        return
                    if resolved_user_id:
                        user_id_var.set(resolved_user_id)
                    if resolved_username:
                        username_var.set(resolved_username)
                    status_var.set("Resolved." if resolved_user_id else "User not found.")

                try:
                    self.root.after(0, apply_result)
                except (RuntimeError, tk.TclError):
                    pass

            threading.Thread(target=worker, args=(username, user_id), daemon=True, name="resolve-recent-user").start()

        def resize_user_canvas(event: tk.Event) -> None:
            user_canvas.itemconfigure(user_canvas_window, width=max(1, int(event.width)))

        search_var.trace_add("write", lambda *_args: render_users())
        user_row_host.bind("<Configure>", lambda _event: user_canvas.configure(scrollregion=user_canvas.bbox("all")))
        user_canvas.bind("<Configure>", resize_user_canvas)
        window.bind("<Return>", lambda _event: save_selected_user())
        window.bind("<Escape>", lambda _event: window.destroy())

        render_users()
        if filtered_users():
            set_selected_user(filtered_users()[0][0])
        window.update_idletasks()
        self._center_window(window, max(640, window.winfo_reqwidth() + 40), max(440, window.winfo_reqheight() + 40))

    def _ensure_addons_folder(self):
        addons_dir = str(getattr(self, "addons_folder", "") or "").strip()
        if not addons_dir:
            addons_dir = os.path.join(str(getattr(self, "data_folder", "AccountManagerData") or "AccountManagerData"), "addons")
            self.addons_folder = addons_dir

        try:
            os.makedirs(addons_dir, exist_ok=True)
        except Exception:
            return addons_dir

        template_path = os.path.join(addons_dir, "_template_addon.py")
        if not os.path.exists(template_path):
            current_fram_version = str(getattr(self, "APP_VERSION", "unknown") or "unknown").strip() or "unknown"
            template_text = (
                "\"\"\"FRAM addon template.\n"
                "Rename this file so it no longer starts with an underscore to load it.\n"
                "\"\"\"\n\n"
                "ADDON_NAME = \"Example Addon\"\n"
                "ADDON_DESCRIPTION = \"Opened from Settings > Tools > Utilities.\"\n"
                f"ADDON_FRAM_VERSION = \"{current_fram_version}\"\n\n"
                "def build_tab(parent, api):\n"
                "    from tkinter import ttk\n\n"
                "    ttk.Label(\n"
                "        parent,\n"
                "        text=\"Hello from a FRAM addon.\",\n"
                "        style=\"Dark.TLabel\",\n"
                "        font=(\"Segoe UI\", 11, \"bold\"),\n"
                "    ).pack(anchor=\"w\")\n"
                "    ttk.Label(\n"
                "        parent,\n"
                "        text=\"Use the api object to interact with FRAM.\",\n"
                "        style=\"Dark.TLabel\",\n"
                "    ).pack(anchor=\"w\", pady=(4, 10))\n"
                "    ttk.Button(\n"
                "        parent,\n"
                "        text=\"Refresh Accounts\",\n"
                "        style=\"Dark.TButton\",\n"
                "        command=api.refresh_accounts,\n"
                "    ).pack(anchor=\"w\")\n"
            )
            try:
                with open(template_path, "w", encoding="utf-8", newline="\n") as template_file:
                    template_file.write(template_text)
            except Exception:
                pass

        return addons_dir

    def _open_addons_folder(self, owner_window=None):
        addons_dir = self._ensure_addons_folder()
        try:
            if hasattr(os, "startfile"):
                os.startfile(addons_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", addons_dir], **subprocess_no_window_kwargs())
            else:
                subprocess.Popen(["xdg-open", addons_dir], **subprocess_no_window_kwargs())
            return True
        except Exception as exc:
            messagebox.showerror(
                "Addons",
                f"Failed to open the addons folder:\n{exc}",
                parent=owner_window or getattr(self, "addons_window", None) or self.root,
            )
            return False

    def _get_remote_addon_target_path(self, file_name: str) -> Path:
        normalized_name = Path(str(file_name or "")).name
        if not normalized_name or normalized_name != str(file_name or ""):
            raise RuntimeError("Remote addon filename is invalid.")
        if not normalized_name.lower().endswith(".py"):
            raise RuntimeError("Remote addon is not a Python file.")
        return Path(self._ensure_addons_folder()) / normalized_name

    def _fetch_remote_addon_listings(self) -> list[RemoteAddonListing]:
        headers = {"Accept": "application/vnd.github+json"}
        response = self._get_http_session().get(FRAM_ASSETS_ADDONS_API_URL, headers=headers, timeout=12)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("FRAMAssets returned an unexpected addons payload.")

        listings: list[RemoteAddonListing] = []
        for item in payload:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type") or "").strip().lower()
            file_name = str(item.get("name") or "").strip()
            download_url = str(item.get("download_url") or "").strip()
            html_url = str(item.get("html_url") or "").strip() or FRAM_ASSETS_ADDONS_WEB_URL

            if item_type != "file":
                continue
            if not file_name.lower().endswith(".py"):
                continue
            if file_name.startswith("_"):
                continue
            if not download_url:
                continue

            listings.append(
                RemoteAddonListing(
                    file_name=file_name,
                    download_url=download_url,
                    html_url=html_url,
                )
            )

        listings.sort(key=lambda listing: listing.file_name.lower())
        return listings

    def _download_remote_addon_listing(self, listing: RemoteAddonListing) -> Path:
        target_path = self._get_remote_addon_target_path(listing.file_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        response = self._get_http_session().get(listing.download_url, timeout=30)
        response.raise_for_status()
        content = bytes(response.content or b"")
        if not content:
            raise RuntimeError("The selected addon download was empty.")

        temp_path = target_path.with_name(f"{target_path.name}.tmp")
        temp_path.write_bytes(content)
        temp_path.replace(target_path)
        return target_path

    def _get_addon_file_paths(self):
        addons_dir = self._ensure_addons_folder()
        try:
            names = os.listdir(addons_dir)
        except Exception:
            return []

        addon_files = []
        for name in names:
            if not str(name).lower().endswith(".py"):
                continue
            if str(name).startswith("_"):
                continue
            full_path = os.path.join(addons_dir, name)
            if os.path.isfile(full_path):
                addon_files.append(full_path)

        addon_files.sort(key=lambda path: os.path.basename(path).lower())
        return addon_files

    def _load_addon_module(self, file_path):
        seed = f"{os.path.abspath(file_path)}:{time.time_ns()}"
        module_name = f"fram_addon_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to create an import spec for the addon.")

        module = importlib.util.module_from_spec(spec)
        addons_dir = self._ensure_addons_folder()
        added_to_path = False
        if addons_dir and addons_dir not in sys.path:
            sys.path.insert(0, addons_dir)
            added_to_path = True

        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        finally:
            if added_to_path:
                try:
                    sys.path.remove(addons_dir)
                except ValueError:
                    pass

        return module

    def _get_addon_builder(self, module):
        for attr_name in ("build_tab", "build_ui", "register"):
            builder = getattr(module, attr_name, None)
            if callable(builder):
                return builder
        raise RuntimeError("Addon must define a callable build_tab(parent, api).")

    def _collect_addon_entries(self):
        addon_files = self._get_addon_file_paths()
        entries = []
        loaded_count = 0
        failed_count = 0

        for file_path in addon_files:
            file_label = os.path.basename(file_path)
            entry = {
                "kind": "addon",
                "file_path": file_path,
                "file_label": file_label,
                "name": os.path.splitext(file_label)[0],
                "description": "",
                "fram_version": "",
                "module": None,
                "builder": None,
                "traceback": "",
                "content_frame": None,
            }
            try:
                module = self._load_addon_module(file_path)
                builder = self._get_addon_builder(module)
                entry["module"] = module
                entry["builder"] = builder
                entry["name"] = str(getattr(module, "ADDON_NAME", entry["name"]) or "").strip() or entry["name"]
                entry["description"] = str(getattr(module, "ADDON_DESCRIPTION", "") or "").strip()
                entry["fram_version"] = str(getattr(module, "ADDON_FRAM_VERSION", "") or "").strip()
                loaded_count += 1
            except Exception:
                entry["kind"] = "error"
                entry["traceback"] = traceback.format_exc()
                failed_count += 1
            entries.append(entry)

        summary = {
            "files": len(addon_files),
            "loaded": loaded_count,
            "failed": failed_count,
        }
        return entries, summary

    def _build_addons_panel(self, parent, owner_window=None, close_callback=None):
        panel = tk.Frame(parent, bg=self.BG_DARK, highlightthickness=0, bd=0)
        panel.pack(fill="both", expand=True)

        title_font = ("Segoe UI", 16, "bold")
        section_title_font = ("Segoe UI", 11, "bold")
        body_font = ("Segoe UI", 10)
        small_font = ("Segoe UI", 9)

        state = {
            "entries": [],
            "summary": {"files": 0, "loaded": 0, "failed": 0},
            "overview_frame": None,
            "active_frame": None,
        }
        fit_state = {"after_id": None}

        def apply_owner_window_fit(recenter=False):
            if owner_window is None or not owner_window.winfo_exists():
                return
            try:
                owner_window.update_idletasks()
                screen_width = owner_window.winfo_screenwidth()
                screen_height = owner_window.winfo_screenheight()
                max_width = max(screen_width - 80, 320)
                max_height = max(screen_height - 80, 240)
                final_width = min(owner_window.winfo_reqwidth() + 20, max_width)
                final_height = min(owner_window.winfo_reqheight() + 20, max_height)
                if recenter or not owner_window.winfo_viewable():
                    self._center_window(owner_window, final_width, final_height)
                    return
                current_x = max(owner_window.winfo_x(), 0)
                current_y = max(owner_window.winfo_y(), 0)
                final_x = min(current_x, max(screen_width - final_width, 0))
                final_y = min(current_y, max(screen_height - final_height, 0))
                owner_window.geometry(f"{final_width}x{final_height}+{final_x}+{final_y}")
            except Exception:
                return

        def schedule_owner_window_fit(recenter=False):
            if owner_window is None or not owner_window.winfo_exists():
                return
            after_id = fit_state.get("after_id")
            if after_id is not None:
                try:
                    owner_window.after_cancel(after_id)
                except Exception:
                    pass

            def run_fit():
                fit_state["after_id"] = None
                apply_owner_window_fit(recenter=recenter)

            fit_state["after_id"] = owner_window.after_idle(run_fit)

        def create_text_area(parent_widget, text_value, height=10):
            container = tk.Frame(parent_widget, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            container.pack(fill="both", expand=True)
            text_widget = tk.Text(
                container,
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                insertbackground=self.FG_TEXT,
                relief="flat",
                borderwidth=0,
                wrap="word",
                height=height,
                font=body_font,
                padx=4,
                pady=4,
            )
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            text_widget.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            text_widget.insert("1.0", text_value)
            text_widget.configure(state="disabled")
            return container

        def create_section_card(parent_widget, title_text, subtitle_text=""):
            outer = tk.Frame(
                parent_widget,
                bg=self.BG_LIGHT,
                highlightbackground=self.BORDER_COLOR,
                highlightthickness=1,
                bd=0,
                padx=12,
                pady=12,
            )
            title_label = tk.Label(
                outer,
                text=title_text,
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=section_title_font,
                anchor="w",
                justify="left",
            )
            title_label.pack(anchor="w")
            if subtitle_text:
                subtitle_label = tk.Label(
                    outer,
                    text=subtitle_text,
                    bg=self.BG_LIGHT,
                    fg=self.FG_MUTED,
                    font=small_font,
                    anchor="w",
                    justify="left",
                    wraplength=520,
                )
                subtitle_label.pack(anchor="w", pady=(4, 10))
            body = tk.Frame(outer, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            body.pack(fill="both", expand=True)
            return outer, body

        def create_stat_chip(parent_widget, label_text, accent_color):
            chip = tk.Frame(
                parent_widget,
                bg=self.BG_LIGHT,
                highlightbackground=self.BORDER_COLOR,
                highlightthickness=1,
                bd=0,
                padx=10,
                pady=6,
            )
            accent = tk.Frame(chip, bg=accent_color, width=8, height=8, highlightthickness=0, bd=0)
            accent.pack(side="left", padx=(0, 8))
            value_var = tk.StringVar(value="0")
            tk.Label(
                chip,
                textvariable=value_var,
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(side="left")
            tk.Label(
                chip,
                text=label_text,
                bg=self.BG_LIGHT,
                fg=self.FG_MUTED,
                font=small_font,
                anchor="w",
            ).pack(side="left", padx=(6, 0))
            return chip, value_var

        header_card = tk.Frame(
            panel,
            bg=self.BG_MID,
            highlightbackground=self.BORDER_COLOR,
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=14,
        )
        header_card.pack(fill="x", pady=(0, 12))

        hero_row = tk.Frame(header_card, bg=self.BG_MID, highlightthickness=0, bd=0)
        hero_row.pack(fill="x")

        hero_text = tk.Frame(hero_row, bg=self.BG_MID, highlightthickness=0, bd=0)
        hero_text.pack(side="left", fill="x", expand=True)

        summary_row = tk.Frame(hero_text, bg=self.BG_MID, highlightthickness=0, bd=0)
        summary_row.pack(anchor="w")

        scripts_card, scripts_value_var = create_stat_chip(summary_row, "Detected Scripts", self.FG_ACCENT)
        scripts_card.pack(side="left")
        loaded_card, loaded_value_var = create_stat_chip(summary_row, "Loaded Cleanly", "#5fbf88")
        loaded_card.pack(side="left", padx=(8, 0))
        failed_card, failed_value_var = create_stat_chip(summary_row, "Load Errors", "#d96c6c")
        failed_card.pack(side="left", padx=(8, 0))

        action_row = tk.Frame(hero_row, bg=self.BG_MID, highlightthickness=0, bd=0)
        action_row.pack(side="right", anchor="ne")

        def close_panel():
            if callable(close_callback):
                close_callback()

        body_frame = tk.Frame(panel, bg=self.BG_DARK, highlightthickness=0, bd=0)
        body_frame.pack(fill="both", expand=True)
        body_frame.grid_rowconfigure(0, weight=1)
        body_frame.grid_columnconfigure(1, weight=1)

        library_card = tk.Frame(
            body_frame,
            bg=self.BG_MID,
            highlightbackground=self.BORDER_COLOR,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=12,
            width=250,
        )
        library_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        library_card.grid_propagate(False)
        library_card.grid_rowconfigure(2, weight=1)
        library_card.grid_columnconfigure(0, weight=1)

        tk.Label(
            library_card,
            text="Library",
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=section_title_font,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            library_card,
            text="Overview, loaded addons, and import failures.",
            bg=self.BG_MID,
            fg=self.FG_MUTED,
            font=small_font,
            anchor="w",
            justify="left",
            wraplength=210,
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))

        list_frame = tk.Frame(library_card, bg=self.BG_MID, highlightthickness=0, bd=0)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        addon_list = tk.Listbox(
            list_frame,
            bg=self.LIST_BG,
            fg=self.FG_TEXT,
            selectbackground=self.FG_ACCENT,
            selectforeground=self.FG_TEXT,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            relief="flat",
            borderwidth=0,
            activestyle="none",
            exportselection=False,
            font=("Segoe UI", 10),
        )
        addon_list.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=addon_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        addon_list.configure(yscrollcommand=list_scroll.set)

        tk.Label(
            library_card,
            text="Tip: scripts starting with '_' are ignored.",
            bg=self.BG_MID,
            fg=self.FG_MUTED,
            font=small_font,
            anchor="w",
            justify="left",
            wraplength=210,
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))

        detail_card = tk.Frame(
            body_frame,
            bg=self.BG_MID,
            highlightbackground=self.BORDER_COLOR,
            highlightthickness=1,
            bd=0,
            padx=16,
            pady=16,
        )
        detail_card.grid(row=0, column=1, sticky="nsew")
        detail_card.grid_rowconfigure(2, weight=1)
        detail_card.grid_columnconfigure(0, weight=1)

        detail_header = tk.Frame(detail_card, bg=self.BG_MID, highlightthickness=0, bd=0)
        detail_header.grid(row=0, column=0, sticky="ew")
        detail_header.grid_columnconfigure(0, weight=1)

        detail_title_var = tk.StringVar(value="FRAM Addons")
        detail_subtitle_var = tk.StringVar(value="")
        detail_path_var = tk.StringVar(value="")
        detail_badge_var = tk.StringVar(value="Overview")

        title_column = tk.Frame(detail_header, bg=self.BG_MID, highlightthickness=0, bd=0)
        title_column.grid(row=0, column=0, sticky="ew")

        tk.Label(
            title_column,
            textvariable=detail_title_var,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_column,
            textvariable=detail_subtitle_var,
            bg=self.BG_MID,
            fg=self.FG_MUTED,
            font=body_font,
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            title_column,
            textvariable=detail_path_var,
            bg=self.BG_MID,
            fg=self.FG_MUTED,
            font=small_font,
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(anchor="w", pady=(8, 0))

        detail_badge = tk.Label(
            detail_header,
            textvariable=detail_badge_var,
            bg=self.FG_ACCENT_ALT,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
        )
        detail_badge.grid(row=0, column=1, sticky="ne", padx=(12, 0))

        divider = tk.Frame(detail_card, bg=self.BORDER_COLOR, height=1, highlightthickness=0, bd=0)
        divider.grid(row=1, column=0, sticky="ew", pady=(14, 14))

        content_host = tk.Frame(detail_card, bg=self.BG_MID, highlightthickness=0, bd=0)
        content_host.grid(row=2, column=0, sticky="nsew")

        status_var = tk.StringVar(value="")
        status_label = tk.Label(
            panel,
            textvariable=status_var,
            bg=self.BG_DARK,
            fg=self.FG_MUTED,
            font=small_font,
            anchor="w",
            justify="left",
        )
        status_label.pack(fill="x", pady=(10, 0))

        def set_badge(kind):
            if kind == "error":
                detail_badge.configure(bg="#8f3a3a", fg="#f8fbff")
                detail_badge_var.set("Load Error")
            elif kind == "addon":
                detail_badge.configure(bg="#335f46", fg="#f8fbff")
                detail_badge_var.set("Loaded")
            else:
                detail_badge.configure(bg=self.FG_ACCENT_ALT, fg=self.FG_TEXT)
                detail_badge_var.set("Overview")

        def show_frame(frame):
            active_frame = state.get("active_frame")
            if active_frame is not None:
                try:
                    active_frame.pack_forget()
                except Exception:
                    pass
            state["active_frame"] = frame
            if frame is not None:
                frame.pack(fill="both", expand=True)
                schedule_owner_window_fit()

        def build_overview_frame():
            frame = tk.Frame(content_host, bg=self.BG_MID, highlightthickness=0, bd=0)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_rowconfigure(1, weight=1)

            intro_card, intro_body = create_section_card(
                frame,
                "Quick Start",
                "Drop FRAM-compatible Python scripts into the addons folder, then reload the library.",
            )
            intro_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
            quick_start_lines = [
                "1. Put a .py script in AccountManagerData/addons",
                "2. Keep the filename from starting with '_'",
                "3. Define build_tab(parent, api)",
                "4. Optionally set ADDON_NAME, ADDON_DESCRIPTION, and ADDON_FRAM_VERSION",
            ]
            tk.Label(
                intro_body,
                text="\n".join(quick_start_lines),
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=body_font,
                anchor="w",
                justify="left",
            ).pack(anchor="w")

            api_card, api_body = create_section_card(
                frame,
                "Available API",
                "Your addon receives a lightweight FRAM API object for common actions.",
            )
            api_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
            api_lines = [
                "ui / manager / settings",
                "launch_game / launch_home / launch_home_app",
                "refresh_accounts / refresh_game_list",
                "show_info / show_error / show_success",
                "data_folder / addons_folder / fram_version / open_addons_folder",
            ]
            tk.Label(
                api_body,
                text="\n".join(api_lines),
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=body_font,
                anchor="w",
                justify="left",
            ).pack(anchor="w")

            remote_card = tk.Frame(
                frame,
                bg=self.BG_LIGHT,
                highlightbackground=self.BORDER_COLOR,
                highlightthickness=1,
                bd=0,
                padx=12,
                pady=12,
            )
            remote_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
            remote_card.grid_columnconfigure(0, weight=1)
            remote_card.grid_rowconfigure(1, weight=1)

            remote_header = tk.Frame(remote_card, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            remote_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
            remote_header.grid_columnconfigure(0, weight=1)

            remote_text = tk.Frame(remote_header, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            remote_text.grid(row=0, column=0, sticky="ew")

            tk.Label(
                remote_text,
                text="Download Addons",
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=section_title_font,
                anchor="w",
                justify="left",
            ).pack(anchor="w")

            tk.Label(
                remote_text,
                text="Browse public FRAM addons and install them.",
                bg=self.BG_LIGHT,
                fg=self.FG_MUTED,
                font=small_font,
                anchor="w",
                justify="left",
                wraplength=420,
            ).pack(anchor="w", pady=(4, 0))

            remote_actions = tk.Frame(remote_header, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            remote_actions.grid(row=0, column=1, sticky="ne", padx=(12, 0))

            remote_body = tk.Frame(remote_card, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            remote_body.grid(row=1, column=0, sticky="nsew")
            remote_body.grid_columnconfigure(0, weight=1)
            remote_body.grid_rowconfigure(0, weight=1)

            remote_download_button = ttk.Button(
                remote_actions,
                text="Download Selected",
                style="Dark.TButton",
                state="disabled",
            )
            remote_download_button.pack(side="left")

            remote_view_button = ttk.Button(
                remote_actions,
                text="View On GitHub",
                style="Dark.TButton",
            )
            remote_view_button.pack(side="left", padx=(6, 0))

            remote_list_frame = tk.Frame(remote_body, bg=self.BG_LIGHT, highlightthickness=0, bd=0)
            remote_list_frame.grid(row=0, column=0, sticky="nsew")
            remote_list_frame.grid_rowconfigure(0, weight=1)
            remote_list_frame.grid_columnconfigure(0, weight=1)

            remote_list = tk.Listbox(
                remote_list_frame,
                bg=self.LIST_BG,
                fg=self.FG_TEXT,
                selectbackground=self.FG_ACCENT,
                selectforeground=self.FG_TEXT,
                highlightbackground=self.BORDER_COLOR,
                highlightcolor=self.BORDER_COLOR,
                relief="flat",
                borderwidth=0,
                activestyle="none",
                exportselection=False,
                font=("Segoe UI", 10),
                height=7,
            )
            remote_list.grid(row=0, column=0, sticky="nsew")
            remote_list_scroll = ttk.Scrollbar(remote_list_frame, orient="vertical", command=remote_list.yview)
            remote_list_scroll.grid(row=0, column=1, sticky="ns")
            remote_list.configure(yscrollcommand=remote_list_scroll.set)

            remote_state = {
                "entries": [],
                "load_generation": 0,
                "download_generation": 0,
                "loading": False,
                "downloading": False,
            }

            def is_overview_alive():
                try:
                    return bool(frame.winfo_exists())
                except Exception:
                    return False

            def get_remote_parent():
                return owner_window or getattr(self, "addons_window", None) or self.root

            def get_selected_remote_listing():
                selection = remote_list.curselection()
                if not selection:
                    return None
                index = int(selection[0])
                entries = list(remote_state.get("entries", []))
                if index < 0 or index >= len(entries):
                    return None
                return entries[index]

            def format_remote_listing_label(listing):
                try:
                    target_path = self._get_remote_addon_target_path(listing.file_name)
                except RuntimeError:
                    return listing.file_name
                if target_path.is_file():
                    return f"{listing.file_name} (Installed)"
                return listing.file_name

            def open_selected_remote_listing():
                listing = get_selected_remote_listing()
                target_url = listing.html_url if listing is not None else FRAM_ASSETS_ADDONS_WEB_URL
                try:
                    import webbrowser as std_webbrowser
                    std_webbrowser.open(target_url, new=2)
                except Exception:
                    pass

            def update_remote_selection_details(_event=None):
                listing = get_selected_remote_listing()
                can_download = (
                    listing is not None
                    and not bool(remote_state.get("loading"))
                    and not bool(remote_state.get("downloading"))
                )
                remote_download_button.configure(state="normal" if can_download else "disabled")

            def render_remote_catalog():
                remote_list.delete(0, tk.END)
                entries = list(remote_state.get("entries", []))
                if not entries:
                    remote_list.insert(tk.END, "No downloadable addons found.")
                    remote_list.selection_clear(0, tk.END)
                    remote_download_button.configure(state="disabled")
                    return
                for listing in entries:
                    remote_list.insert(tk.END, format_remote_listing_label(listing))
                remote_list.selection_clear(0, tk.END)
                remote_list.selection_set(0)
                remote_list.activate(0)
                update_remote_selection_details()

            def refresh_remote_catalog():
                if not is_overview_alive():
                    return
                remote_state["load_generation"] = int(remote_state.get("load_generation", 0)) + 1
                generation = int(remote_state["load_generation"])
                remote_state["loading"] = True
                remote_state["entries"] = []
                remote_list.delete(0, tk.END)
                remote_list.insert(tk.END, "Loading remote addons...")
                remote_download_button.configure(state="disabled")

                def worker():
                    try:
                        listings = self._fetch_remote_addon_listings()
                    except Exception as exc:
                        def apply_error(error_message=str(exc)):
                            if not is_overview_alive() or generation != int(remote_state.get("load_generation", 0)):
                                return
                            remote_state["loading"] = False
                            remote_list.delete(0, tk.END)
                            remote_list.insert(tk.END, "Unable to load remote addons.")
                            remote_download_button.configure(state="disabled")
                            schedule_owner_window_fit()

                        self.root.after(0, apply_error)
                        return

                    def apply_success(remote_listings=listings):
                        if not is_overview_alive() or generation != int(remote_state.get("load_generation", 0)):
                            return
                        remote_state["loading"] = False
                        remote_state["entries"] = list(remote_listings)
                        render_remote_catalog()
                        schedule_owner_window_fit()

                    self.root.after(0, apply_success)

                threading.Thread(target=worker, daemon=True).start()

            def download_selected_remote_listing():
                if bool(remote_state.get("loading")) or bool(remote_state.get("downloading")):
                    return

                listing = get_selected_remote_listing()
                if listing is None:
                    return

                try:
                    target_path = self._get_remote_addon_target_path(listing.file_name)
                except RuntimeError as exc:
                    messagebox.showerror("Addons", str(exc), parent=get_remote_parent())
                    return

                if target_path.is_file():
                    overwrite = messagebox.askyesno(
                        "Addons",
                        (
                            f"{listing.file_name} already exists in your addons folder.\n\n"
                            "Do you want to replace it with the FRAMAssets version?"
                        ),
                        parent=get_remote_parent(),
                    )
                    if not overwrite:
                        return

                remote_state["download_generation"] = int(remote_state.get("download_generation", 0)) + 1
                generation = int(remote_state["download_generation"])
                remote_state["downloading"] = True
                remote_download_button.configure(state="disabled")

                def worker():
                    try:
                        self._download_remote_addon_listing(listing)
                    except Exception as exc:
                        def apply_error(error_message=str(exc), listing_name=listing.file_name):
                            if not is_overview_alive() or generation != int(remote_state.get("download_generation", 0)):
                                return
                            remote_state["downloading"] = False
                            update_remote_selection_details()
                            messagebox.showerror(
                                "Addons",
                                f"Failed to download {listing_name}:\n{error_message}",
                                parent=get_remote_parent(),
                            )

                        self.root.after(0, apply_error)
                        return

                    def apply_success(listing_name=listing.file_name):
                        if not is_overview_alive() or generation != int(remote_state.get("download_generation", 0)):
                            return
                        remote_state["downloading"] = False
                        self.show_success_message(f"Downloaded addon: {listing_name}")
                        reload_addons()

                    self.root.after(0, apply_success)

                threading.Thread(target=worker, daemon=True).start()

            remote_download_button.configure(command=download_selected_remote_listing)
            remote_view_button.configure(command=open_selected_remote_listing)
            remote_list.bind("<<ListboxSelect>>", update_remote_selection_details)
            remote_list.bind("<Double-Button-1>", lambda _event: download_selected_remote_listing())

            refresh_remote_catalog()
            return frame

        def build_error_frame(entry):
            frame = tk.Frame(content_host, bg=self.BG_MID, highlightthickness=0, bd=0)
            alert_card, alert_body = create_section_card(
                frame,
                "Import Failure",
                "FRAM found the script, but it failed during import or did not expose a valid addon builder.",
            )
            alert_card.pack(fill="x", pady=(0, 12))
            tk.Label(
                alert_body,
                text="Check the traceback below, fix the script, then click Reload.",
                bg=self.BG_LIGHT,
                fg=self.FG_TEXT,
                font=body_font,
                anchor="w",
                justify="left",
                wraplength=560,
            ).pack(anchor="w")

            trace_card, trace_body = create_section_card(
                frame,
                "Traceback",
                entry.get("file_path", ""),
            )
            trace_card.pack(fill="both", expand=True)
            create_text_area(trace_body, entry.get("traceback", "").strip() or "Unknown addon load error.", height=20)
            return frame

        def build_addon_frame(entry):
            frame = tk.Frame(content_host, bg=self.BG_MID, highlightthickness=0, bd=0)

            surface_card, surface_body = create_section_card(
                frame,
                "Addon UI",
            )
            surface_card.pack(fill="both", expand=True)

            addon_host = ttk.Frame(surface_body, style="Dark.TFrame")
            addon_host.pack(fill="both", expand=True)

            try:
                api = FRAMAddonAPI(
                    self,
                    entry.get("name", "Addon"),
                    entry.get("file_path", ""),
                    addon_fram_version=entry.get("fram_version", ""),
                )
                build_result = entry["builder"](addon_host, api)
                if isinstance(build_result, tk.Widget) and not build_result.winfo_manager():
                    build_result.pack(fill="both", expand=True)
            except Exception:
                entry["kind"] = "error"
                entry["traceback"] = traceback.format_exc()
                try:
                    frame.destroy()
                except Exception:
                    pass
                return build_error_frame(entry)

            return frame

        def get_entry_frame(entry):
            frame = entry.get("content_frame")
            if frame is not None:
                return frame
            if entry.get("kind") == "error":
                frame = build_error_frame(entry)
            else:
                frame = build_addon_frame(entry)
            entry["content_frame"] = frame
            return frame

        def show_overview():
            if state.get("overview_frame") is None:
                state["overview_frame"] = build_overview_frame()
            detail_title_var.set("FRAM Addons")
            detail_subtitle_var.set("Review the library, loader contract, and available downloads before opening an addon.")
            detail_path_var.set(f"Folder: {self.addons_folder}")
            set_badge("overview")
            show_frame(state["overview_frame"])

        def show_entry(index):
            if index <= 0:
                show_overview()
                return
            if index - 1 >= len(state.get("entries", [])):
                show_overview()
                return

            entry = state["entries"][index - 1]
            detail_title_var.set(entry.get("name", entry.get("file_label", "Addon")))
            frame = get_entry_frame(entry)
            if entry.get("kind") == "error":
                detail_subtitle_var.set("This script was detected but failed to load cleanly.")
            else:
                description = entry.get("description", "") or "This addon loaded successfully and exposed a FRAM addon view."
                fram_version = str(entry.get("fram_version", "") or "").strip()
                if fram_version:
                    detail_subtitle_var.set(f"{description} Built for FRAM {fram_version}.")
                else:
                    detail_subtitle_var.set(description)
            detail_path_var.set(entry.get("file_path", ""))
            set_badge(entry.get("kind"))
            show_frame(frame)

        def handle_list_selection(_event=None):
            selection = addon_list.curselection()
            if not selection:
                return
            show_entry(int(selection[0]))

        def reload_addons():
            addon_list.delete(0, tk.END)
            for child in list(content_host.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass

            entries, summary = self._collect_addon_entries()
            state["entries"] = entries
            state["summary"] = summary
            state["overview_frame"] = None
            state["active_frame"] = None

            scripts_value_var.set(str(summary.get("files", 0)))
            loaded_value_var.set(str(summary.get("loaded", 0)))
            failed_value_var.set(str(summary.get("failed", 0)))

            addon_list.insert(tk.END, "Overview")
            for entry in entries:
                label = entry.get("name", entry.get("file_label", "Addon"))
                if entry.get("kind") == "error":
                    label = f"Error: {label}"
                addon_list.insert(tk.END, label)

            if summary.get("files", 0) == 0:
                status_var.set("No addons found yet. Open the folder, add a script, then reload.")
            else:
                status_var.set(
                    f"Detected {summary.get('files', 0)} script(s). "
                    f"Loaded {summary.get('loaded', 0)} cleanly, "
                    f"{summary.get('failed', 0)} failed."
                )

            addon_list.selection_clear(0, tk.END)
            addon_list.selection_set(0)
            addon_list.activate(0)
            show_overview()

        ttk.Button(
            action_row,
            text="Reload",
            style="Dark.TButton",
            command=reload_addons,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            action_row,
            text="Open Folder",
            style="Dark.TButton",
            command=lambda: self._open_addons_folder(owner_window=owner_window),
        ).pack(side="left", padx=(0, 6))
        if callable(close_callback):
            ttk.Button(
                action_row,
                text="Close",
                style="Dark.TButton",
                command=close_panel,
            ).pack(side="left")

        addon_list.bind("<<ListboxSelect>>", handle_list_selection)
        addon_list.bind("<Double-Button-1>", handle_list_selection)

        reload_addons()
        return panel

    def open_addons_window(self):
        self._ensure_addons_folder()
        existing_window = getattr(self, "addons_window", None)
        if existing_window and existing_window.winfo_exists():
            existing_window.deiconify()
            existing_window.lift()
            existing_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("FRAM Addons - Manage your addon library, inspect load errors, and launch addon tools from one place.")
        window.configure(bg=self.BG_DARK)
        window.withdraw()
        window.transient(self.root)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)
        self.addons_window = window

        main_frame = ttk.Frame(window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=16, pady=14)

        def on_close():
            self.addons_window = None
            try:
                window.destroy()
            except Exception:
                pass

        self._build_addons_panel(main_frame, owner_window=window, close_callback=on_close)

        window.protocol("WM_DELETE_WINDOW", on_close)
        window.update_idletasks()
        final_width = min(window.winfo_reqwidth() + 20, max(window.winfo_screenwidth() - 80, 320))
        final_height = min(window.winfo_reqheight() + 20, max(window.winfo_screenheight() - 80, 240))
        self._center_window(window, final_width, final_height)
        window.deiconify()

    def open_browser_extensions_window(self) -> None:
        manager: BrowserExtensionManager = self.browser_extension_manager
        manager.ensure_storage()

        existing_window = getattr(self, "browser_extensions_window", None)
        if existing_window and existing_window.winfo_exists():
            existing_window.deiconify()
            existing_window.lift()
            existing_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("Extension Manager")
        window.configure(bg=self.BG_DARK)
        window.withdraw()
        window.transient(self.root)
        window.resizable(True, True)
        window.minsize(780, 500)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)
        self.browser_extensions_window = window

        main_frame = ttk.Frame(window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=16, pady=14)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text="Extension Manager",
            style="Dark.TLabel",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            header_frame,
            text="Manage extensions for browsers.",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        status_var = tk.StringVar()

        content_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        columns = ("enabled", "name", "source", "extension_id", "manifest")
        tree = ttk.Treeview(
            content_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="Dark.Treeview",
        )
        tree.heading("enabled", text="Enabled")
        tree.heading("name", text="Name")
        tree.heading("source", text="Source")
        tree.heading("extension_id", text="Extension ID")
        tree.heading("manifest", text="Manifest")
        tree.column("enabled", width=80, anchor="center", stretch=False)
        tree.column("name", width=220, anchor="w")
        tree.column("source", width=120, anchor="w", stretch=False)
        tree.column("extension_id", width=250, anchor="w")
        tree.column("manifest", width=80, anchor="center", stretch=False)
        tree.grid(row=0, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(content_frame, orient="vertical", command=tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=tree_scroll.set)

        action_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        action_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        for column_index in range(5):
            action_frame.grid_columnconfigure(column_index, weight=1)

        ttk.Label(
            action_frame,
            textvariable=status_var,
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(6, 0))

        extension_cache: dict[str, BrowserExtension] = {}
        task_buttons: list[ttk.Button] = []
        chromium_download_state: dict[str, Optional[threading.Thread]] = {"thread": None}

        def is_chromium_ready() -> bool:
            try:
                return "chromium" in self._get_available_browsers()
            except (AttributeError, OSError, RuntimeError, TypeError):
                return False

        def is_firefox_ready() -> bool:
            try:
                return "firefox" in self._get_available_browsers()
            except (AttributeError, OSError, RuntimeError, TypeError):
                return False

        def is_waterfox_ready() -> bool:
            try:
                return "waterfox" in self._get_available_browsers()
            except (AttributeError, OSError, RuntimeError, TypeError):
                return False

        def get_raw_browser_preference() -> str:
            browser_preference = str(self.settings.get("browser_preference", "auto") or "auto").strip().lower()
            if browser_preference not in SUPPORTED_BROWSER_PREFERENCES:
                return "auto"
            return browser_preference

        def get_extension_browser_mode() -> str:
            browser_preference = get_raw_browser_preference()
            if browser_preference == "auto":
                return "chromium" if is_chromium_ready() else "auto_missing_chromium"
            if browser_preference == "chrome":
                return "chrome"
            if browser_preference == "chromium":
                return "chromium" if is_chromium_ready() else "chromium_missing"
            if browser_preference == "firefox":
                return "firefox" if is_firefox_ready() else "firefox_missing"
            if browser_preference == "waterfox":
                return "waterfox" if is_waterfox_ready() else "waterfox_missing"
            return "unsupported"

        def is_chromium_extension(extension: BrowserExtension) -> bool:
            return extension.source in {"web_store", "crx", "unpacked"}

        def is_firefox_extension(extension: BrowserExtension) -> bool:
            return extension.source in {"firefox_addons", "xpi", "unpacked"}

        def is_extension_visible(extension: BrowserExtension) -> bool:
            mode = get_extension_browser_mode()
            if mode in {"chromium", "chromium_missing", "auto_missing_chromium"}:
                return is_chromium_extension(extension)
            if mode in {"firefox", "firefox_missing", "waterfox", "waterfox_missing"}:
                return is_firefox_extension(extension)
            return False

        def refresh_status() -> None:
            mode = get_extension_browser_mode()
            if mode == "unsupported":
                status_var.set("Selected browser is not supported. Extension Manager supports Firefox, Waterfox, and Chromium.")
                return
            if mode == "chrome":
                if is_chromium_ready():
                    status_var.set("Chrome is selected. Switch to Chromium to manage Chromium extensions.")
                else:
                    status_var.set("Chrome is selected. Download Chromium to use the Extension Manager.")
                return
            if mode == "auto_missing_chromium":
                status_var.set("Download Chromium or select Firefox/Waterfox in Browser Automation to manage extensions.")
                return
            if mode == "chromium_missing":
                status_var.set("Chromium is not installed. Download Chromium to manage Chromium extensions.")
                return
            if mode == "firefox_missing":
                status_var.set("Firefox is not installed. Select another Browser Automation option first.")
                return
            if mode == "waterfox_missing":
                status_var.set("Waterfox is not installed. Select another Browser Automation option first.")
                return
            status_var.set("")

        def refresh_tree(select_key: str = "") -> None:
            extension_cache.clear()
            for item in tree.get_children():
                tree.delete(item)

            try:
                extensions = manager.list_extensions()
            except BrowserExtensionError as exc:
                status_var.set(str(exc))
                messagebox.showerror("Extension Manager", str(exc), parent=window)
                return

            for extension in extensions:
                if not is_extension_visible(extension):
                    continue
                extension_cache[extension.key] = extension
                tree.insert(
                    "",
                    "end",
                    iid=extension.key,
                    values=(
                        "Yes" if extension.enabled else "No",
                        extension.name,
                        extension.display_source,
                        extension.extension_id,
                        extension.manifest_version or "",
                    ),
                )

            if select_key and tree.exists(select_key):
                tree.selection_set(select_key)
                tree.focus(select_key)
            refresh_status()

        def selected_extensions() -> list[BrowserExtension]:
            selected: list[BrowserExtension] = []
            for key in tree.selection():
                extension = extension_cache.get(str(key))
                if extension is not None:
                    selected.append(extension)
            return selected

        def set_task_buttons_enabled(enabled: bool) -> None:
            state = "normal" if enabled else "disabled"
            for button in task_buttons:
                try:
                    button.configure(state=state)
                except tk.TclError:
                    pass

        def schedule_ui(callback: Callable[[], None]) -> None:
            def guarded_callback() -> None:
                try:
                    if window.winfo_exists():
                        callback()
                except tk.TclError:
                    pass

            try:
                self.root.after(0, guarded_callback)
            except tk.TclError:
                pass

        def run_manager_task(
            status_text: str,
            worker_func: Callable[[], Any],
            success_callback: Callable[[Any], None],
        ) -> None:
            set_task_buttons_enabled(False)
            status_var.set(status_text)

            def worker() -> None:
                try:
                    result = worker_func()
                except BrowserExtensionError as exc:
                    error_message = str(exc)

                    def apply_error() -> None:
                        set_task_buttons_enabled(True)
                        status_var.set(error_message)
                        messagebox.showerror("Extension Manager", error_message, parent=window)

                    schedule_ui(apply_error)
                    return

                def apply_success() -> None:
                    set_task_buttons_enabled(True)
                    success_callback(result)

                schedule_ui(apply_success)

            threading.Thread(target=worker, daemon=True, name="browser-extension-manager").start()

        def add_chrome_extension_id() -> None:
            if get_extension_browser_mode() not in {"chromium", "chromium_missing"}:
                messagebox.showwarning("Extension Manager", "Switch Browser Automation to Chromium first.", parent=window)
                return
            extension_id = simpledialog.askstring(
                "Add Chrome Extension",
                "Chrome Web Store extension ID or URL:",
                parent=window,
            )
            if extension_id is None:
                return
            extension_id = extension_id.strip()
            if not extension_id:
                return

            def on_success(result: Any) -> None:
                extension = result if isinstance(result, BrowserExtension) else None
                refresh_tree(extension.key if extension is not None else "")
                status_var.set(f"Added {extension.name}." if extension is not None else "Extension added.")

            run_manager_task(
                "Downloading extension...",
                lambda: manager.add_from_extension_id(extension_id),
                on_success,
            )

        def add_firefox_addon_id() -> None:
            if get_extension_browser_mode() not in GECKO_BROWSER_NAMES:
                messagebox.showwarning("Extension Manager", "Switch Browser Automation to Firefox or Waterfox first.", parent=window)
                return
            addon_id = simpledialog.askstring(
                "Add Firefox Extension",
                "Firefox Add-ons slug, GUID, numeric ID, or URL:",
                parent=window,
            )
            if addon_id is None:
                return
            addon_id = addon_id.strip()
            if not addon_id:
                return

            def on_success(result: Any) -> None:
                extension = result if isinstance(result, BrowserExtension) else None
                refresh_tree(extension.key if extension is not None else "")
                status_var.set(f"Added {extension.name}." if extension is not None else "Extension added.")

            run_manager_task(
                "Downloading Firefox extension...",
                lambda: manager.add_from_firefox_addon(addon_id),
                on_success,
            )

        def import_extension_package() -> None:
            mode = get_extension_browser_mode()
            if mode in {"chromium", "chromium_missing"}:
                dialog_title = "Import CRX Extension"
                filetypes = (("CRX files", "*.crx"), ("All files", "*.*"))
                status_text = "Importing CRX..."
                fallback_status_text = "CRX imported."
                import_func: Callable[[str], BrowserExtension] = manager.add_from_crx
            elif mode in GECKO_BROWSER_NAMES:
                dialog_title = "Import XPI Extension"
                filetypes = (("XPI files", "*.xpi"), ("All files", "*.*"))
                status_text = "Importing XPI..."
                fallback_status_text = "XPI imported."
                import_func = manager.add_from_xpi
            else:
                messagebox.showwarning("Extension Manager", "Browser not supported.", parent=window)
                return

            file_path = filedialog.askopenfilename(
                parent=window,
                title=dialog_title,
                filetypes=filetypes,
            )
            if not file_path:
                return

            def import_package() -> BrowserExtension:
                suffix = Path(file_path).suffix.casefold()
                if mode in {"chromium", "chromium_missing"} and suffix != ".crx":
                    raise BrowserExtensionError("Select a CRX extension package.")
                if mode in GECKO_BROWSER_NAMES and suffix != ".xpi":
                    raise BrowserExtensionError("Select an XPI extension package.")
                return import_func(file_path)

            def on_success(result: Any) -> None:
                extension = result if isinstance(result, BrowserExtension) else None
                refresh_tree(extension.key if extension is not None else "")
                status_var.set(f"Imported {extension.name}." if extension is not None else fallback_status_text)

            run_manager_task(
                status_text,
                import_package,
                on_success,
            )

        def import_unpacked() -> None:
            folder_path = filedialog.askdirectory(parent=window, title="Import Unpacked Extension")
            if not folder_path:
                return

            def on_success(result: Any) -> None:
                extension = result if isinstance(result, BrowserExtension) else None
                refresh_tree(extension.key if extension is not None else "")
                status_var.set(f"Imported {extension.name}." if extension is not None else "Folder imported.")

            run_manager_task(
                "Importing unpacked extension...",
                lambda: manager.add_from_unpacked(folder_path),
                on_success,
            )

        def toggle_selected() -> None:
            extensions = selected_extensions()
            if not extensions:
                messagebox.showwarning("Extension Manager", "Select at least one extension first.", parent=window)
                return
            target_enabled = not all(extension.enabled for extension in extensions)
            try:
                for extension in extensions:
                    manager.set_extension_enabled(extension.key, target_enabled)
            except BrowserExtensionError as exc:
                messagebox.showerror("Extension Manager", str(exc), parent=window)
                return
            selected_keys = [extension.key for extension in extensions]
            refresh_tree(selected_keys[0] if selected_keys else "")
            for key in selected_keys:
                if tree.exists(key):
                    tree.selection_add(key)
            status_var.set("Selected extension(s) enabled." if target_enabled else "Selected extension(s) disabled.")

        def remove_selected() -> None:
            extensions = selected_extensions()
            if not extensions:
                messagebox.showwarning("Extension Manager", "Select at least one extension first.", parent=window)
                return
            confirmed = messagebox.askyesno(
                "Remove Extension",
                f"Remove {len(extensions)} selected extension(s)?",
                parent=window,
            )
            if not confirmed:
                return
            try:
                for extension in extensions:
                    manager.remove_extension(extension.key)
            except BrowserExtensionError as exc:
                messagebox.showerror("Extension Manager", str(exc), parent=window)
                return
            refresh_tree()
            status_var.set("Selected extension(s) removed.")

        def use_chromium() -> None:
            if not is_chromium_ready():
                messagebox.showwarning(
                    "Extension Manager",
                    "Chromium is not installed. Use Browser Automation to download it first.",
                    parent=window,
                )
                return
            self.settings["browser_preference"] = "chromium"
            self.save_settings()
            refresh_tree()
            refresh_action_buttons()
            refresh_status()
            status_var.set("Browser Automation is set to Chromium.")

        def use_firefox() -> None:
            if not is_firefox_ready():
                messagebox.showwarning(
                    "Extension Manager",
                    "Firefox is not installed.",
                    parent=window,
                )
                return
            self.settings["browser_preference"] = "firefox"
            self.save_settings()
            refresh_status()
            status_var.set("Browser Automation is set to Firefox.")

        def set_chromium_download_status(message: str) -> None:
            schedule_ui(lambda: status_var.set(message))

        def begin_chromium_download() -> None:
            active_thread = chromium_download_state.get("thread")
            if active_thread is not None and active_thread.is_alive():
                return

            set_task_buttons_enabled(False)
            status_var.set("Starting Chromium download...")

            def worker() -> None:
                try:
                    installation = self._install_managed_chromium(set_chromium_download_status)
                except RuntimeError as exc:
                    error_message = str(exc)

                    def apply_error() -> None:
                        chromium_download_state["thread"] = None
                        set_task_buttons_enabled(True)
                        refresh_tree()
                        refresh_action_buttons()
                        status_var.set(error_message)
                        messagebox.showerror("Download Chromium", error_message, parent=window)

                    schedule_ui(apply_error)
                    return

                def apply_success() -> None:
                    self.settings["browser_preference"] = "chromium"
                    self.save_settings()
                    chromium_download_state["thread"] = None
                    set_task_buttons_enabled(True)
                    refresh_tree()
                    refresh_action_buttons()
                    version_text = f" {installation.version}" if installation.version else ""
                    status_var.set(f"Chromium{version_text} is ready. Browser Automation is set to Chromium.")
                    messagebox.showinfo(
                        "Download Chromium",
                        f"Chromium{version_text} is ready to use.",
                        parent=window,
                    )

                schedule_ui(apply_success)

            thread = threading.Thread(target=worker, daemon=True, name="download-managed-chromium")
            chromium_download_state["thread"] = thread
            thread.start()

        def activate_chromium() -> None:
            if get_extension_browser_mode() == "chrome" and is_chromium_ready():
                use_chromium()
                return
            begin_chromium_download()

        def open_extensions_folder() -> None:
            target_path = manager.extensions_folder
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(target_path))
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", str(target_path)], **subprocess_no_window_kwargs())
                else:
                    subprocess.Popen(["xdg-open", str(target_path)], **subprocess_no_window_kwargs())
            except OSError as exc:
                messagebox.showerror("Extension Manager", f"Failed to open folder:\n{exc}", parent=window)

        def close_window() -> None:
            self.browser_extensions_window = None
            try:
                window.destroy()
            except tk.TclError:
                pass

        add_id_button = ttk.Button(action_frame, text="Add Chrome ID", style="Dark.TButton", command=add_chrome_extension_id)
        add_id_button.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=3)

        add_firefox_button = ttk.Button(
            action_frame,
            text="Add Firefox ID",
            style="Dark.TButton",
            command=add_firefox_addon_id,
        )
        add_firefox_button.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

        import_crx_button = ttk.Button(
            action_frame,
            text="Import Package",
            style="Dark.TButton",
            command=import_extension_package,
        )
        import_crx_button.grid(row=0, column=2, sticky="ew", padx=4, pady=3)

        import_folder_button = ttk.Button(
            action_frame,
            text="Import Folder",
            style="Dark.TButton",
            command=import_unpacked,
        )
        import_folder_button.grid(row=0, column=3, sticky="ew", padx=4, pady=3)

        toggle_button = ttk.Button(action_frame, text="Enable / Disable", style="Dark.TButton", command=toggle_selected)
        toggle_button.grid(row=0, column=4, sticky="ew", padx=(4, 0), pady=3)

        remove_button = ttk.Button(action_frame, text="Remove", style="Dark.TButton", command=remove_selected)
        remove_button.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=3)

        download_chromium_button = ttk.Button(
            action_frame,
            text="Download Chromium",
            style="Dark.TButton",
            command=activate_chromium,
        )
        download_chromium_button.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

        open_folder_button = ttk.Button(action_frame, text="Open Folder", style="Dark.TButton", command=open_extensions_folder)
        open_folder_button.grid(row=1, column=3, sticky="ew", padx=4, pady=3)

        close_button = ttk.Button(action_frame, text="Close", style="Dark.TButton", command=close_window)
        close_button.grid(row=1, column=4, sticky="ew", padx=(4, 0), pady=3)

        all_action_buttons = [
            add_id_button,
            add_firefox_button,
            import_crx_button,
            import_folder_button,
            toggle_button,
            remove_button,
            download_chromium_button,
            open_folder_button,
            close_button,
        ]

        def grid_action_button(
            button: ttk.Button,
            row: int,
            column: int,
            padx: tuple[int, int] | int = 4,
            columnspan: int = 1,
        ) -> None:
            button.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=padx, pady=3)

        def refresh_action_buttons() -> None:
            for button in all_action_buttons:
                button.grid_forget()

            task_buttons.clear()
            mode = get_extension_browser_mode()
            download_chromium_button.configure(
                text="Use Chromium" if mode == "chrome" and is_chromium_ready() else "Download Chromium"
            )
            if mode in GECKO_BROWSER_NAMES:
                import_crx_button.configure(text="Import XPI")
                grid_action_button(add_firefox_button, 0, 0, (0, 4))
                grid_action_button(import_crx_button, 0, 1)
                grid_action_button(import_folder_button, 0, 2)
                grid_action_button(toggle_button, 0, 3)
                grid_action_button(remove_button, 0, 4, (4, 0))
                grid_action_button(open_folder_button, 1, 3)
                grid_action_button(close_button, 1, 4, (4, 0))
                task_buttons.extend([add_firefox_button, import_crx_button, import_folder_button, toggle_button, remove_button])
                return

            if mode == "chromium":
                import_crx_button.configure(text="Import CRX")
                grid_action_button(add_id_button, 0, 0, (0, 4))
                grid_action_button(import_crx_button, 0, 1)
                grid_action_button(import_folder_button, 0, 2)
                grid_action_button(toggle_button, 0, 3)
                grid_action_button(remove_button, 0, 4, (4, 0))
                grid_action_button(open_folder_button, 1, 3)
                grid_action_button(close_button, 1, 4, (4, 0))
                task_buttons.extend([add_id_button, import_crx_button, import_folder_button, toggle_button, remove_button])
                return

            if mode == "chromium_missing":
                import_crx_button.configure(text="Import CRX")
                grid_action_button(download_chromium_button, 0, 0, (0, 4))
                grid_action_button(add_id_button, 0, 1)
                grid_action_button(import_crx_button, 0, 2)
                grid_action_button(import_folder_button, 0, 3)
                grid_action_button(toggle_button, 0, 4, (4, 0))
                grid_action_button(remove_button, 1, 0, (0, 4))
                grid_action_button(open_folder_button, 1, 3)
                grid_action_button(close_button, 1, 4, (4, 0))
                task_buttons.extend(
                    [
                        download_chromium_button,
                        add_id_button,
                        import_crx_button,
                        import_folder_button,
                        toggle_button,
                        remove_button,
                    ]
                )
                return

            if mode == "auto_missing_chromium":
                grid_action_button(download_chromium_button, 0, 0, (0, 4))
                grid_action_button(open_folder_button, 0, 3)
                grid_action_button(close_button, 0, 4, (4, 0))
                task_buttons.append(download_chromium_button)
                return

            if mode == "chrome":
                grid_action_button(download_chromium_button, 0, 0, (0, 4))
                grid_action_button(open_folder_button, 0, 3)
                grid_action_button(close_button, 0, 4, (4, 0))
                task_buttons.append(download_chromium_button)
                return

            grid_action_button(open_folder_button, 0, 3)
            grid_action_button(close_button, 0, 4, (4, 0))

        def on_tree_double_click(_event: tk.Event) -> None:
            if get_extension_browser_mode() in {"chromium", "chromium_missing", "firefox", "waterfox"}:
                toggle_selected()

        tree.bind("<Double-Button-1>", on_tree_double_click)
        window.protocol("WM_DELETE_WINDOW", close_window)
        refresh_action_buttons()
        refresh_tree()
        window.update_idletasks()
        width = max(780, min(window.winfo_reqwidth() + 20, max(window.winfo_screenwidth() - 80, 360)))
        height = max(500, min(window.winfo_reqheight() + 20, max(window.winfo_screenheight() - 80, 320)))
        self._center_window(window, width, height)
        window.deiconify()

    def refresh_installer_menu(self):
        """Populate the Roblox Installer menu with available versions."""
        if getattr(self, "installer_menu", None) is None:
            return

        self.installer_menu.delete(0, tk.END)
        versions = self.get_available_roblox_versions()
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
                command=lambda item=entry: self.use_installer_version(item)
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

    def use_installer_version(self, version_entry):
        """Begin the guided installer flow for the selected Roblox version."""
        if isinstance(version_entry, dict):
            version = (version_entry.get("version") or "").strip()
        else:
            version = str(version_entry or "").strip()
            version_entry = {"version": version}

        if not version:
            return

        clients = self.get_installed_clients()
        if not clients:
            messagebox.showwarning(
                "Roblox Installer",
                "No supported clients were found.\n\nInstall Roblox, Bloxstrap, or Fishstrap first."
            )
            return

        self._show_installer_dialog(version_entry, clients)

    def _show_installer_dialog(self, version_entry, clients):
        """Create (or refresh) the installer dialog for choosing a client and tracking progress."""
        self._close_installer_dialog()

        version = (version_entry.get("version") or "").strip()
        version_label = self.format_version_display(version_entry)

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
            text=f"Install {version_label}",
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
            "version_entry": version_entry,
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

        version_entry = state.get("version_entry") or {"version": version}

        thread = threading.Thread(
            target=self._installer_download_thread,
            args=(version_entry, client, target_dir),
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

    def _installer_download_thread(self, version_entry, client, target_dir):
        root = getattr(self, "root", None)
        version = ""
        if isinstance(version_entry, dict):
            version = str(version_entry.get("version") or "").strip()
        else:
            version = str(version_entry or "").strip()
            version_entry = {"version": version}

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
            download_channel = str(version_entry.get("download_channel") or "").strip().upper()
            if hasattr(self, "settings") and isinstance(self.settings, dict):
                channel = (self.settings.get("roblox_download_channel") or channel)
            if download_channel:
                channel = download_channel
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

    def _fetch_weao_windows_version(self, route_path: str, status: str) -> Optional[dict[str, Any]]:
        """Fetch a Windows Roblox version hash from a WEAO route."""
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {"User-Agent": WEAO_API_USER_AGENT}
        last_exc = None
        normalized_route_path = route_path if str(route_path).startswith("/") else f"/{route_path}"
        subdomain_route_path = normalized_route_path
        if subdomain_route_path.startswith("/api/"):
            subdomain_route_path = subdomain_route_path[4:]
        candidate_urls = []
        for host in WEAO_API_HOSTS:
            for scheme in ("https", "http"):
                candidate_urls.append(f"{scheme}://{host}{normalized_route_path}")
        candidate_urls.extend((
            f"https://api.weao.xyz{subdomain_route_path}",
            f"https://api.whatexpsare.online{subdomain_route_path}",
        ))

        for url in candidate_urls:
            try:
                response = session.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                last_exc = exc
                continue

            if not isinstance(data, dict) or data.get("error"):
                continue

            win = data.get("Windows")
            if not win or not isinstance(win, str):
                continue
            win = win.strip()
            if not re.fullmatch(r"version-[0-9a-fA-F]+", win):
                continue
            return {
                "version": win,
                "status": status,
                "date": data.get("WindowsDate"),
                "download_channel": "LIVE",
                "source": "WEAO",
            }

        status_label = str(status or "").strip().replace("_", " ").title() or "Unknown"
        print(f"[INFO] WEAO returned no {status_label} Version")
        if last_exc is not None and bool(self.settings.get("enable_debug_logging", False)):
            print(f"Failed to fetch WEAO {status} Windows version: {last_exc}")
        return None

    def fetch_remote_versions(self, limit=INSTALLER_VERSION_ENTRY_LIMIT):
        """Fetch Roblox installer versions from WEAO LIVE endpoints."""
        route_specs = (
            (WEAO_VERSIONS_FUTURE_PATH, "FUTURE"),
            (WEAO_VERSIONS_CURRENT_PATH, "LIVE"),
            (WEAO_VERSIONS_PAST_PATH, "PAST"),
        )
        fetched_versions = []
        for route_path, status in route_specs:
            entry = self._fetch_weao_windows_version(route_path, status)
            if entry:
                fetched_versions.append(entry)

        display_priority = {"FUTURE": 0, "LIVE": 1, "PAST": 2}
        dedupe_priority = {"LIVE": 0, "FUTURE": 1, "PAST": 2}
        deduped_versions = {}
        for entry in fetched_versions:
            version = entry.get("version")
            if not version:
                continue
            existing = deduped_versions.get(version)
            if existing is None or dedupe_priority.get(entry.get("status"), 99) < dedupe_priority.get(existing.get("status"), 99):
                deduped_versions[version] = entry

        ordered_versions = sorted(
            deduped_versions.values(),
            key=lambda item: display_priority.get(item.get("status"), 99)
        )
        if limit is not None:
            ordered_versions = ordered_versions[:limit]
        return ordered_versions

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

    def get_available_roblox_versions(self):
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
            remote_versions = self.fetch_remote_versions(limit=INSTALLER_VERSION_ENTRY_LIMIT)
            if remote_versions:
                self._installer_versions_cache = {"ts": now, "versions": remote_versions}

        if remote_versions:
            return remote_versions
        return self.get_local_roblox_versions(limit=INSTALLER_VERSION_ENTRY_LIMIT)

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

    def _theme_required_keys(self):
        return {
            "root_bg",
            "frame_bg",
            "panel_bg",
            "panel_alt",
            "text",
            "text_muted",
            "accent",
            "accent_alt",
            "entry_bg",
            "entry_fg",
            "border",
            "hover_bg",
            "list_bg",
            "list_select",
            "font",
            "font_size",
        }

    def _validate_theme_object(self, name, value):
        if not isinstance(value, dict):
            return False, f"Theme '{name}' must be an object."
        missing = [key for key in self._theme_required_keys() if key not in value]
        if missing:
            return False, f"Theme '{name}' is missing required keys: {', '.join(sorted(missing))}"
        return True, ""

    def _merge_themes(self, themes_payload):
        if not isinstance(themes_payload, dict):
            raise ValueError("Theme payload must be a JSON object.")

        merged_count = 0
        for theme_name, theme_obj in themes_payload.items():
            name = str(theme_name or "").strip()
            if not name:
                continue
            is_valid, error_message = self._validate_theme_object(name, theme_obj)
            if not is_valid:
                raise ValueError(error_message)

            normalized = {
                "root_bg": str(theme_obj["root_bg"]),
                "frame_bg": str(theme_obj["frame_bg"]),
                "panel_bg": str(theme_obj["panel_bg"]),
                "panel_alt": str(theme_obj["panel_alt"]),
                "text": str(theme_obj["text"]),
                "text_muted": str(theme_obj["text_muted"]),
                "accent": str(theme_obj["accent"]),
                "accent_alt": str(theme_obj["accent_alt"]),
                "entry_bg": str(theme_obj["entry_bg"]),
                "entry_fg": str(theme_obj["entry_fg"]),
                "border": str(theme_obj["border"]),
                "hover_bg": str(theme_obj["hover_bg"]),
                "list_bg": str(theme_obj["list_bg"]),
                "list_select": str(theme_obj["list_select"]),
                "font": str(theme_obj["font"]),
                "font_size": int(theme_obj["font_size"]),
            }
            THEMES[name] = normalized
            self.custom_themes[name] = dict(normalized)
            merged_count += 1

        return merged_count

    def _save_custom_themes_to_disk(self):
        try:
            os.makedirs(self.data_folder, exist_ok=True)
            with open(self.custom_themes_file, "w", encoding="utf-8") as handle:
                json.dump(self.custom_themes, handle, indent=2)
            return True
        except Exception as exc:
            print(f"Failed to save custom themes: {exc}")
            return False

    def _load_custom_themes_from_disk(self):
        try:
            if not os.path.exists(self.custom_themes_file):
                self.custom_themes = {}
                return
            with open(self.custom_themes_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                self.custom_themes = {}
                return
            self.custom_themes = {}
            for theme_name, theme_obj in payload.items():
                name = str(theme_name or "").strip()
                if not name:
                    continue
                is_valid, _ = self._validate_theme_object(name, theme_obj)
                if not is_valid:
                    continue
                THEMES[name] = dict(theme_obj)
                self.custom_themes[name] = dict(theme_obj)
        except Exception as exc:
            print(f"Failed to load custom themes: {exc}")
            self.custom_themes = {}

    def install_additional_themes_from_url(self, url):
        target_url = str(url or "").strip()
        if not target_url:
            raise ValueError("Theme URL is empty.")

        response = self._get_http_session().get(target_url, timeout=15)
        response.raise_for_status()
        payload = response.json()
        merged = self._merge_themes(payload)
        self._save_custom_themes_to_disk()
        return merged

    def _load_discord_button_image(self, size=32, allow_network=True):
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

        if not allow_network:
            return None

        try:
            response = self._get_http_session().get(DISCORD_LOGO_URL, timeout=5)
            if response.status_code == 200 and response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                with open(png_path, "wb") as cache_fp:
                    cache_fp.write(response.content)
                image = _load_png(png_path)
                if image is not None:
                    return image
        except Exception:
            pass

        return None

    def _get_place_icon_cache_dir(self) -> Path:
        data_folder = str(getattr(self, "data_folder", "AccountManagerData") or "AccountManagerData")
        return Path(data_folder) / "cache" / "place_icons"

    def _get_place_icon_cache_path(self, place_id: str) -> Path:
        normalized_place_id = str(place_id or "").strip()
        safe_place_id = re.sub(r"[^0-9A-Za-z_-]+", "_", normalized_place_id).strip("_")
        if not safe_place_id:
            safe_place_id = hashlib.sha256(normalized_place_id.encode("utf-8")).hexdigest()[:16]
        return self._get_place_icon_cache_dir() / f"place_{safe_place_id}_150x150.png"

    def _load_cached_place_icon_image(self, place_id: str, size: int = 78) -> Optional[tk.PhotoImage]:
        normalized_place_id = str(place_id or "").strip()
        if not normalized_place_id:
            return None

        image_key = f"{normalized_place_id}:{int(size)}"
        cached_image = self._place_icon_images.get(image_key)
        if cached_image is not None:
            return cached_image

        icon_path = self._get_place_icon_cache_path(normalized_place_id)
        if not icon_path.is_file():
            return None

        try:
            image = tk.PhotoImage(file=str(icon_path))
            largest_dimension = max(int(image.width()), int(image.height()))
            if largest_dimension > int(size):
                ratio = max(1, int(math.ceil(largest_dimension / float(size))))
                image = image.subsample(ratio, ratio)
            self._place_icon_images[image_key] = image
            return image
        except (OSError, tk.TclError, ValueError):
            try:
                icon_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def _collect_icon_fetch_batch(self, fetch_queue: queue.Queue[str], first_icon_id: str) -> list[str]:
        icon_ids = [first_icon_id]
        deadline = time.monotonic() + ICON_FETCH_BATCH_WAIT_SECONDS
        while len(icon_ids) < ICON_FETCH_BATCH_SIZE:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                break
            try:
                icon_ids.append(fetch_queue.get(timeout=remaining_seconds))
            except queue.Empty:
                break
        return icon_ids

    def _extract_thumbnail_icon_urls(self, thumbnail_rows: Any, target_ids: set[str]) -> dict[str, str]:
        if not isinstance(thumbnail_rows, list):
            return {}

        icon_urls: dict[str, str] = {}
        for thumbnail_row in thumbnail_rows:
            if not isinstance(thumbnail_row, dict):
                continue
            target_id = str(
                thumbnail_row.get("targetId")
                or thumbnail_row.get("id")
                or thumbnail_row.get("placeId")
                or thumbnail_row.get("userId")
                or ""
            ).strip()
            image_url = str(thumbnail_row.get("imageUrl") or "").strip()
            if target_id in target_ids and image_url:
                icon_urls[target_id] = image_url
        return icon_urls

    def _download_icon_images_to_cache(
        self,
        icon_urls: dict[str, str],
        cache_path_resolver: Callable[[str], Path],
    ) -> set[str]:
        fetched_icon_ids: set[str] = set()
        if not icon_urls:
            return fetched_icon_ids

        session = self._get_http_session()
        for icon_id, image_url in icon_urls.items():
            normalized_icon_id = str(icon_id or "").strip()
            normalized_image_url = str(image_url or "").strip()
            if not normalized_icon_id or not normalized_image_url:
                continue
            try:
                cache_path = cache_path_resolver(normalized_icon_id)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                image_response = session.get(normalized_image_url, timeout=12)
                image_response.raise_for_status()
                if not image_response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                    continue
                cache_path.write_bytes(image_response.content)
                fetched_icon_ids.add(normalized_icon_id)
            except (OSError, ValueError, requests.exceptions.RequestException):
                continue
        return fetched_icon_ids

    def _discard_icon_image_cache_entries(self, image_cache: dict[str, tk.PhotoImage], icon_ids: set[str]) -> None:
        if not icon_ids:
            return
        for image_key in list(image_cache.keys()):
            icon_id = image_key.split(":", 1)[0]
            if icon_id in icon_ids:
                image_cache.pop(image_key, None)

    def _fetch_place_icons_to_cache(self, place_ids: list[str]) -> set[str]:
        normalized_place_ids = list(dict.fromkeys(
            str(place_id or "").strip()
            for place_id in place_ids
            if str(place_id or "").strip().isdigit()
        ))
        if not normalized_place_ids:
            return set()

        try:
            thumbnail_response = self._get_http_session().get(
                "https://thumbnails.roblox.com/v1/places/gameicons",
                params={
                    "placeIds": ",".join(normalized_place_ids),
                    "returnPolicy": "PlaceHolder",
                    "size": "150x150",
                    "format": "Png",
                    "isCircular": "false",
                },
                timeout=8,
            )
            thumbnail_response.raise_for_status()
            thumbnail_payload = thumbnail_response.json() if thumbnail_response.content else {}
            thumbnail_rows = thumbnail_payload.get("data") if isinstance(thumbnail_payload, dict) else []
            icon_urls = self._extract_thumbnail_icon_urls(
                thumbnail_rows,
                set(normalized_place_ids),
            )
            fetched_place_ids = self._download_icon_images_to_cache(icon_urls, self._get_place_icon_cache_path)
            self._discard_icon_image_cache_entries(self._place_icon_images, fetched_place_ids)
            return fetched_place_ids
        except (OSError, ValueError, requests.exceptions.RequestException):
            return set()

    def _fetch_place_icon_to_cache(self, place_id: str) -> bool:
        normalized_place_id = str(place_id or "").strip()
        if not normalized_place_id.isdigit():
            return False
        return normalized_place_id in self._fetch_place_icons_to_cache([normalized_place_id])

    def _ensure_place_icon_fetch_worker(self) -> None:
        with self._place_icon_fetch_lock:
            if self._place_icon_fetch_worker_started:
                return
            self._place_icon_fetch_worker_started = True

        threading.Thread(
            target=self._place_icon_fetch_worker,
            daemon=True,
            name="fetch-place-icons",
        ).start()

    def _place_icon_fetch_worker(self) -> None:
        while True:
            first_place_id = self._place_icon_fetch_queue.get()
            place_ids = [first_place_id]
            try:
                place_ids = self._collect_icon_fetch_batch(self._place_icon_fetch_queue, first_place_id)
                fetched_place_ids = self._fetch_place_icons_to_cache(place_ids)
                self._complete_place_icon_fetch_batch(place_ids, fetched_place_ids)
            finally:
                for _place_id in place_ids:
                    self._place_icon_fetch_queue.task_done()

    def _enqueue_place_icon_fetch_id(self, place_id: str) -> None:
        normalized_place_id = str(place_id or "").strip()
        with self._place_icon_fetch_lock:
            if normalized_place_id not in self._place_icon_fetch_pending:
                self._place_icon_fetch_deferred.discard(normalized_place_id)
                return

        try:
            self._place_icon_fetch_queue.put_nowait(normalized_place_id)
        except queue.Full:
            with self._place_icon_fetch_lock:
                self._place_icon_fetch_deferred.add(normalized_place_id)
            self._schedule_deferred_place_icon_fetches()

    def _schedule_deferred_place_icon_fetches(self) -> None:
        with self._place_icon_fetch_lock:
            if self._place_icon_fetch_retry_after_id is not None:
                return
        try:
            after_id = self.root.after(ICON_FETCH_RETRY_MS, self._drain_deferred_place_icon_fetches)
        except (RuntimeError, tk.TclError):
            return
        with self._place_icon_fetch_lock:
            self._place_icon_fetch_retry_after_id = after_id

    def _drain_deferred_place_icon_fetches(self) -> None:
        with self._place_icon_fetch_lock:
            self._place_icon_fetch_retry_after_id = None
            deferred_place_ids = list(self._place_icon_fetch_deferred)
            self._place_icon_fetch_deferred.clear()

        for place_id in deferred_place_ids:
            self._enqueue_place_icon_fetch_id(place_id)

    def _complete_place_icon_fetch_batch(self, place_ids: list[str], fetched_place_ids: set[str]) -> None:
        callbacks_by_place_id: dict[str, list[Callable[[str], None]]] = {}
        with self._place_icon_fetch_lock:
            for place_id in place_ids:
                self._place_icon_fetch_pending.discard(place_id)
                callbacks = list(self._place_icon_fetch_callbacks.pop(place_id, []))
                if place_id in fetched_place_ids and callbacks:
                    callbacks_by_place_id[place_id] = callbacks

        if not callbacks_by_place_id:
            return

        def apply_callbacks() -> None:
            for fetched_place_id, callbacks in callbacks_by_place_id.items():
                for place_icon_callback in callbacks:
                    place_icon_callback(fetched_place_id)

        try:
            self.root.after(0, apply_callbacks)
        except (RuntimeError, tk.TclError):
            pass

    def _queue_place_icon_fetch(self, place_id: str, callback: Callable[[str], None]) -> None:
        normalized_place_id = str(place_id or "").strip()
        if not normalized_place_id.isdigit() or not callable(callback):
            return
        if self._get_place_icon_cache_path(normalized_place_id).is_file():
            return

        self._ensure_place_icon_fetch_worker()
        should_enqueue = False
        with self._place_icon_fetch_lock:
            self._place_icon_fetch_callbacks.setdefault(normalized_place_id, []).append(callback)
            if normalized_place_id not in self._place_icon_fetch_pending:
                self._place_icon_fetch_pending.add(normalized_place_id)
                should_enqueue = True

        if should_enqueue:
            self._enqueue_place_icon_fetch_id(normalized_place_id)

    def _get_user_icon_cache_dir(self) -> Path:
        data_folder = str(getattr(self, "data_folder", "AccountManagerData") or "AccountManagerData")
        return Path(data_folder) / "cache" / "user_icons"

    def _get_user_icon_cache_path(self, user_id: str) -> Path:
        normalized_user_id = str(user_id or "").strip()
        safe_user_id = re.sub(r"[^0-9A-Za-z_-]+", "_", normalized_user_id).strip("_")
        if not safe_user_id:
            safe_user_id = hashlib.sha256(normalized_user_id.encode("utf-8")).hexdigest()[:16]
        return self._get_user_icon_cache_dir() / f"user_{safe_user_id}_48x48.png"

    def _load_cached_user_icon_image(self, user_id: str, size: int = 48) -> Optional[tk.PhotoImage]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return None

        image_key = f"{normalized_user_id}:{int(size)}"
        cached_image = self._user_icon_images.get(image_key)
        if cached_image is not None:
            return cached_image

        icon_path = self._get_user_icon_cache_path(normalized_user_id)
        if not icon_path.is_file():
            return None

        try:
            image = tk.PhotoImage(file=str(icon_path))
            largest_dimension = max(int(image.width()), int(image.height()))
            if largest_dimension > int(size):
                ratio = max(1, int(math.ceil(largest_dimension / float(size))))
                image = image.subsample(ratio, ratio)
            self._user_icon_images[image_key] = image
            return image
        except (OSError, tk.TclError, ValueError):
            try:
                icon_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def _fetch_user_icons_to_cache(self, user_ids: list[str]) -> set[str]:
        normalized_user_ids = list(dict.fromkeys(
            str(user_id or "").strip()
            for user_id in user_ids
            if str(user_id or "").strip().isdigit()
        ))
        if not normalized_user_ids:
            return set()

        try:
            thumbnail_response = self._get_http_session().get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={
                    "userIds": ",".join(normalized_user_ids),
                    "size": "48x48",
                    "format": "Png",
                    "isCircular": "false",
                },
                timeout=8,
            )
            thumbnail_response.raise_for_status()
            thumbnail_payload = thumbnail_response.json() if thumbnail_response.content else {}
            thumbnail_rows = thumbnail_payload.get("data") if isinstance(thumbnail_payload, dict) else []
            icon_urls = self._extract_thumbnail_icon_urls(
                thumbnail_rows,
                set(normalized_user_ids),
            )
            fetched_user_ids = self._download_icon_images_to_cache(icon_urls, self._get_user_icon_cache_path)
            self._discard_icon_image_cache_entries(self._user_icon_images, fetched_user_ids)
            return fetched_user_ids
        except (OSError, ValueError, requests.exceptions.RequestException):
            return set()

    def _fetch_user_icon_to_cache(self, user_id: str) -> bool:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id.isdigit():
            return False
        return normalized_user_id in self._fetch_user_icons_to_cache([normalized_user_id])

    def _ensure_user_icon_fetch_worker(self) -> None:
        with self._user_icon_fetch_lock:
            if self._user_icon_fetch_worker_started:
                return
            self._user_icon_fetch_worker_started = True

        threading.Thread(
            target=self._user_icon_fetch_worker,
            daemon=True,
            name="fetch-user-icons",
        ).start()

    def _user_icon_fetch_worker(self) -> None:
        while True:
            first_user_id = self._user_icon_fetch_queue.get()
            user_ids = [first_user_id]
            try:
                user_ids = self._collect_icon_fetch_batch(self._user_icon_fetch_queue, first_user_id)
                fetched_user_ids = self._fetch_user_icons_to_cache(user_ids)
                self._complete_user_icon_fetch_batch(user_ids, fetched_user_ids)
            finally:
                for _user_id in user_ids:
                    self._user_icon_fetch_queue.task_done()

    def _enqueue_user_icon_fetch_id(self, user_id: str) -> None:
        normalized_user_id = str(user_id or "").strip()
        with self._user_icon_fetch_lock:
            if normalized_user_id not in self._user_icon_fetch_pending:
                self._user_icon_fetch_deferred.discard(normalized_user_id)
                return

        try:
            self._user_icon_fetch_queue.put_nowait(normalized_user_id)
        except queue.Full:
            with self._user_icon_fetch_lock:
                self._user_icon_fetch_deferred.add(normalized_user_id)
            self._schedule_deferred_user_icon_fetches()

    def _schedule_deferred_user_icon_fetches(self) -> None:
        with self._user_icon_fetch_lock:
            if self._user_icon_fetch_retry_after_id is not None:
                return
        try:
            after_id = self.root.after(ICON_FETCH_RETRY_MS, self._drain_deferred_user_icon_fetches)
        except (RuntimeError, tk.TclError):
            return
        with self._user_icon_fetch_lock:
            self._user_icon_fetch_retry_after_id = after_id

    def _drain_deferred_user_icon_fetches(self) -> None:
        with self._user_icon_fetch_lock:
            self._user_icon_fetch_retry_after_id = None
            deferred_user_ids = list(self._user_icon_fetch_deferred)
            self._user_icon_fetch_deferred.clear()

        for user_id in deferred_user_ids:
            self._enqueue_user_icon_fetch_id(user_id)

    def _complete_user_icon_fetch_batch(self, user_ids: list[str], fetched_user_ids: set[str]) -> None:
        callbacks_by_user_id: dict[str, list[Callable[[str], None]]] = {}
        with self._user_icon_fetch_lock:
            for user_id in user_ids:
                self._user_icon_fetch_pending.discard(user_id)
                callbacks = list(self._user_icon_fetch_callbacks.pop(user_id, []))
                if user_id in fetched_user_ids and callbacks:
                    callbacks_by_user_id[user_id] = callbacks

        if not callbacks_by_user_id:
            return

        def apply_callbacks() -> None:
            for fetched_user_id, callbacks in callbacks_by_user_id.items():
                for user_icon_callback in callbacks:
                    user_icon_callback(fetched_user_id)

        try:
            self.root.after(0, apply_callbacks)
        except (RuntimeError, tk.TclError):
            pass

    def _queue_user_icon_fetch(self, user_id: str, callback: Callable[[str], None]) -> None:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id.isdigit() or not callable(callback):
            return
        if self._get_user_icon_cache_path(normalized_user_id).is_file():
            return

        self._ensure_user_icon_fetch_worker()
        should_enqueue = False
        with self._user_icon_fetch_lock:
            self._user_icon_fetch_callbacks.setdefault(normalized_user_id, []).append(callback)
            if normalized_user_id not in self._user_icon_fetch_pending:
                self._user_icon_fetch_pending.add(normalized_user_id)
                should_enqueue = True

        if should_enqueue:
            self._enqueue_user_icon_fetch_id(normalized_user_id)

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

    def _get_addons_folder_path(self) -> Optional[Path]:
        addons_folder = str(getattr(self, "addons_folder", "") or "").strip()
        if not addons_folder:
            return None
        try:
            return Path(addons_folder).resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            return None

    def _is_addon_traceback_path(self, file_path: Any, addons_folder: Path) -> bool:
        path_text = str(file_path or "").strip()
        if not path_text:
            return False
        try:
            candidate_path = Path(path_text).resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            return False
        try:
            candidate_path.relative_to(addons_folder)
            return True
        except ValueError:
            return False

    def _traceback_contains_addon_frame(self, exc_traceback: Any, addons_folder: Path) -> bool:
        if exc_traceback is None:
            return False
        try:
            extracted_frames = traceback.extract_tb(exc_traceback)
        except Exception:
            return False
        for frame in extracted_frames:
            if self._is_addon_traceback_path(getattr(frame, "filename", ""), addons_folder):
                return True
        return False

    def _is_addon_exception(self, exc_value: Any, exc_traceback: Any) -> bool:
        addons_folder = self._get_addons_folder_path()
        if addons_folder is None:
            return False

        current_value = exc_value
        current_traceback = exc_traceback
        seen_ids = set()

        while True:
            if self._traceback_contains_addon_frame(current_traceback, addons_folder):
                return True
            if current_value is None:
                return False
            current_id = id(current_value)
            if current_id in seen_ids:
                return False
            seen_ids.add(current_id)
            current_value = getattr(current_value, "__cause__", None) or getattr(current_value, "__context__", None)
            current_traceback = getattr(current_value, "__traceback__", None) if current_value is not None else None

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
            text="Privacy: Nothing is sent automatically. Sensitive values are redacted before opening the draft or exporting diagnostics.",
            style="Dark.TLabel",
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        button_row = ttk.Frame(container, style="Dark.TFrame")
        button_row.pack(fill="x")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        button_row.columnconfigure(2, weight=1)
        button_row.columnconfigure(3, weight=1)

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

        def export_diagnostics():
            try:
                if getattr(self, "console_window", None) is not None:
                    self.console_window.export_logs()
                else:
                    messagebox.showerror("Export Diagnostics", "Console diagnostics are not available.", parent=dialog)
            except Exception as exc:
                messagebox.showerror("Export Diagnostics", f"Failed to export diagnostics:\n{exc}", parent=dialog)

        def never_ask_again():
            self.settings["bug_issue_prompt_enabled"] = False
            self.save_settings()
            close_prompt()

        ttk.Button(
            button_row,
            text="Create GitHub Issue",
            style="Dark.TButton",
            command=open_issue,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ttk.Button(
            button_row,
            text="Export Diagnostics",
            style="Dark.TButton",
            command=export_diagnostics,
        ).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Button(
            button_row,
            text="Not Now",
            style="Dark.TButton",
            command=close_prompt,
        ).grid(row=0, column=2, sticky="ew", padx=4)

        ttk.Button(
            button_row,
            text="Never Ask Again",
            style="Dark.TButton",
            command=never_ask_again,
        ).grid(row=0, column=3, sticky="ew", padx=(4, 0))

        dialog.protocol("WM_DELETE_WINDOW", close_prompt)
        dialog.update_idletasks()
        self._center_window(dialog, max(700, dialog.winfo_reqwidth() + 20), max(210, dialog.winfo_reqheight() + 20))
        dialog.deiconify()

    def report_unhandled_exception(self, exc_type, exc_value, exc_traceback, source="unknown"):
        """Queue a privacy-safe issue draft prompt for unexpected crashes."""
        if exc_type in (KeyboardInterrupt, SystemExit):
            return
        if not self.settings.get("bug_issue_prompt_enabled", True):
            return
        if self._is_addon_exception(exc_value, exc_traceback):
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
        Returns True when at least one supported browser is available.
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
            appdata = os.environ.get("APPDATA")

            if pf:
                candidates.append(os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(pf, "Mozilla Firefox", "firefox.exe"))
            if pfx86:
                candidates.append(os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(pfx86, "Mozilla Firefox", "firefox.exe"))
            if localapp:
                candidates.append(os.path.join(localapp, "Google", "Chrome", "Application", "chrome.exe"))
                candidates.append(os.path.join(localapp, "Mozilla Firefox", "firefox.exe"))

            waterfox_folders = ("Waterfox", "Waterfox Current", "Waterfox Classic")
            for base_path in (pf, pfx86):
                if not base_path:
                    continue
                for folder_name in waterfox_folders:
                    candidates.append(os.path.join(base_path, folder_name, "waterfox.exe"))
            if localapp:
                for folder_name in waterfox_folders:
                    candidates.append(os.path.join(localapp, folder_name, "waterfox.exe"))
                    candidates.append(os.path.join(localapp, "Programs", folder_name, "waterfox.exe"))
            if appdata:
                for folder_name in waterfox_folders:
                    candidates.append(os.path.join(appdata, folder_name, "waterfox.exe"))

            for path in candidates:
                if path and os.path.exists(path):
                    return True
            return any(
                self._is_browser_installed_locally(browser_name)
                for browser_name in ("waterfox", "chromium")
            )
        except Exception:
            pass
        return False

    def on_place_id_change(self, event: Optional[tk.Event] = None) -> None:
        """Called when place ID changes"""
        value = self.place_entry.get().strip()
        setting_key = self._get_launch_input_setting_key(
            getattr(self, "launch_input_mode", "place_id")
        )
        self._schedule_setting_save(setting_key, value, delay_ms=250)
        self.update_game_name()

    def _get_launch_input_setting_key(self, mode: Any) -> str:
        normalized = self._normalize_launch_input_mode(mode)
        if normalized == "join_user":
            return "last_user"
        return "last_place_id"

    def _replace_launch_input_value(self, value: Any) -> None:
        if not getattr(self, "place_entry", None):
            return
        self.place_entry.delete(0, tk.END)
        self.place_entry.insert(0, str(value or ""))

    def on_private_server_change(self, event=None):
        """Called when private server ID changes"""
        self._apply_private_server_entry_normalization(save=True)

    def _get_private_server_normalization_cookie(self):
        for username in self._get_selected_usernames_silent():
            cookie = str(self.manager.get_account_cookie(username) or "").strip()
            if cookie:
                return cookie

        for account_data in self.manager.accounts.values():
            if not isinstance(account_data, dict):
                continue
            cookie = str(account_data.get("cookie") or "").strip()
            if cookie:
                return cookie

        return ""

    def _normalize_private_server_entry_value(self, value):
        text = str(value or "").strip()
        if not text:
            return ""
        if self._normalize_place_target_mode(getattr(self, "place_join_target_mode", "private_server")) != "private_server":
            return text
        return self.manager.normalize_private_server(
            text,
            roblosecurity_cookie=self._get_private_server_normalization_cookie(),
        )

    def _apply_private_server_entry_normalization(self, save=True):
        entry = getattr(self, "private_server_entry", None)
        if entry is None:
            return ""

        raw_value = str(entry.get() or "")
        normalized_value = self._normalize_private_server_entry_value(raw_value)
        if raw_value != normalized_value:
            entry.delete(0, tk.END)
            entry.insert(0, normalized_value)

        if save:
            self._schedule_setting_save("last_private_server", normalized_value, delay_ms=250)
        return normalized_value

    def on_place_target_field_click(self, event=None):
        if self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id")) != "place_id":
            return None
        if self._normalize_place_target_mode(getattr(self, "place_join_target_mode", "private_server")) != "subplaces":
            return None
        self.open_subplaces_selector()
        return "break"

    def _normalize_launch_input_mode(self, mode):
        normalized = str(mode or "place_id").strip().lower()
        if normalized == "join_user":
            return "join_user"
        return "place_id"

    def _normalize_place_target_mode(self, mode):
        normalized = str(mode or "private_server").strip().lower()
        if normalized == "subplaces":
            return "subplaces"
        if normalized == "job_id":
            return "job_id"
        return "private_server"

    def _set_place_target_mode(self, mode, save=True):
        normalized = self._normalize_place_target_mode(mode)
        self.place_join_target_mode = normalized
        if normalized == "job_id":
            self.private_server_label.configure(text="Job ID (Optional)")
        elif normalized == "subplaces":
            self.private_server_label.configure(text="SubPlace ID (Optional)")
        else:
            self.private_server_label.configure(text="Private Server ID (Optional)")
        self._apply_private_server_entry_normalization(save=False)
        if save:
            self._schedule_setting_save("place_join_target_mode", normalized, delay_ms=0)

    def toggle_place_target_mode(self):
        current_mode = self._normalize_place_target_mode(self.place_join_target_mode)
        if current_mode == "private_server":
            next_mode = "job_id"
        elif current_mode == "job_id":
            next_mode = "subplaces"
        else:
            next_mode = "private_server"
        self._set_place_target_mode(next_mode, save=True)

    def _set_place_target_mode_from_menu(self, mode):
        normalized = self._normalize_place_target_mode(mode)
        self._set_place_target_mode(normalized, save=True)
        if normalized == "subplaces":
            self.open_subplaces_selector()

    def open_subplaces_selector(self):
        if self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id")) != "place_id":
            return

        place_id = str(self.place_entry.get() or "").strip()
        if not place_id:
            messagebox.showwarning("Missing Place ID", "Enter a Place ID first to load subplaces.")
            return
        if not place_id.isdigit():
            messagebox.showwarning("Invalid Place ID", "Place ID must be numeric to load subplaces.")
            return

        def worker(base_place_id):
            subplaces = RobloxAPI.get_subplaces(base_place_id)

            def on_result():
                if not subplaces:
                    messagebox.showinfo("SubPlaces", f"No subplaces found for Place ID {base_place_id}.")
                    return
                self._show_subplaces_window(base_place_id, subplaces)

            self.root.after(0, on_result)

        threading.Thread(target=worker, args=(place_id,), daemon=True).start()

    def _show_subplaces_window(self, base_place_id, subplaces):
        if not subplaces:
            return

        window = tk.Toplevel(self.root)
        window.title(f"SubPlaces for {base_place_id}")
        window.geometry("560x430")
        window.minsize(460, 320)
        window.configure(bg=self.BG_DARK)
        window.transient(self.root)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        main_frame = ttk.Frame(window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(
            main_frame,
            text=f"Select a subplace from universe of Place ID {base_place_id}",
            style="Dark.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        list_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        list_frame.pack(fill="both", expand=True)

        listbox = tk.Listbox(
            list_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            selectbackground=self.FG_ACCENT,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            font=("Segoe UI", 9),
        )
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)

        for place in subplaces:
            place_id = str(place.get("id") or "").strip()
            place_name = str(place.get("name") or f"Place {place_id}").strip()
            listbox.insert(tk.END, f"{place_name} ({place_id})")

        selected_subplace_id = str(self.private_server_entry.get() or "").strip()
        if selected_subplace_id:
            for idx, place in enumerate(subplaces):
                if str(place.get("id") or "").strip() == selected_subplace_id:
                    listbox.selection_set(idx)
                    listbox.see(idx)
                    break

        def apply_selected():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Select a subplace first.")
                return

            selected = subplaces[selection[0]]
            selected_id = str(selected.get("id") or "").strip()
            if not selected_id:
                return

            self.private_server_entry.delete(0, tk.END)
            self.private_server_entry.insert(0, selected_id)
            self.settings["last_private_server"] = selected_id
            self.save_settings()
            window.destroy()

        button_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text="Use Selected", style="Dark.TButton", command=apply_selected).pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        ttk.Button(button_frame, text="Cancel", style="Dark.TButton", command=window.destroy).pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )

        listbox.bind("<Double-Button-1>", lambda _evt: apply_selected())
        window.bind("<Return>", lambda _evt: apply_selected())
        window.bind("<Escape>", lambda _evt: window.destroy())

    def show_place_target_context_menu(self, event):
        if self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id")) != "place_id":
            return
        menu = getattr(self, "place_target_context_menu", None)
        if menu is None:
            return
        try:
            menu.delete(0, "end")
            current_mode = self._normalize_place_target_mode(self.place_join_target_mode)
            mode_labels = {
                "private_server": "Private Server ID",
                "job_id": "Job ID",
                "subplaces": "SubPlaces",
            }
            for mode_key in ("private_server", "job_id", "subplaces"):
                prefix = "✓ " if mode_key == current_mode else ""
                menu.add_command(
                    label=f"{prefix}{mode_labels.get(mode_key, mode_key)}",
                    command=lambda m=mode_key: self._set_place_target_mode_from_menu(m),
                )
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _set_launch_input_mode(self, mode: Any, save: bool = True) -> None:
        normalized = self._normalize_launch_input_mode(mode)
        previous = self._normalize_launch_input_mode(getattr(self, "launch_input_mode", "place_id"))
        if previous != normalized and getattr(self, "place_entry", None):
            if save:
                previous_key = self._get_launch_input_setting_key(previous)
                self.settings[previous_key] = self.place_entry.get().strip()
            next_key = self._get_launch_input_setting_key(normalized)
            self._replace_launch_input_value(self.settings.get(next_key, ""))
            self._last_game_name_query_value = None

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
        private_server = self.manager.normalize_private_server(private_server)
        
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
                self.settings["last_user"] = value
                self.save_settings()
                self.update_game_name()
                return

            game = self.settings["game_list"][index]
            self.place_entry.delete(0, tk.END)
            self.place_entry.insert(0, game["place_id"])
            self.settings["last_place_id"] = game["place_id"]
            
            private_server = self.manager.normalize_private_server(game.get("private_server", ""))
            if game.get("private_server", "") != private_server:
                game["private_server"] = private_server
            self.private_server_entry.delete(0, tk.END)
            self.private_server_entry.insert(0, private_server)
            self.settings["last_private_server"] = private_server
            
            self.save_settings()
            self.update_game_name()

    def _extract_username(self, display_text):
        prefixes = [
            f"{INVALID_ACCOUNT_SYMBOL} ",
            f"{ACTIVE_CLIENT_SYMBOL} ",
            f"{AUTO_REJOIN_SYMBOL} ",
        ]
        trimmed = True
        while trimmed:
            trimmed = False
            for prefix in prefixes:
                if display_text.startswith(prefix):
                    display_text = display_text[len(prefix):]
                    trimmed = True
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
        active_client_usernames = self._get_active_client_usernames()
        display_items = []
        username_to_indices = {}
        invalid_indices = []

        for username in list(self._account_validation_status.keys()):
            if username not in self.manager.accounts:
                self._account_validation_status.pop(username, None)

        for username in list(self._account_rejoin_status.keys()):
            if username not in self.manager.accounts:
                self._account_rejoin_status.pop(username, None)

        for username, data in self.manager.accounts.items():
            if not isinstance(data, dict):
                continue

            self._account_validation_status.setdefault(username, None)

            group = (data.get('group') or '').strip()
            if active_group and group != active_group:
                continue

            note = (data.get('note') or '').strip()
            vip_server = (data.get('vip_server') or '').strip()
            rejoin_status = str(self._account_rejoin_status.get(username, "") or "").strip()
            is_monitored = self._is_account_auto_rejoin_monitored(username)
            has_active_client = username in active_client_usernames
            display_text = f"{username}"
            if is_monitored:
                display_text = f"{AUTO_REJOIN_SYMBOL} {display_text}"
            if has_active_client:
                display_text = f"{ACTIVE_CLIENT_SYMBOL} {display_text}"
            if self._account_validation_status.get(username) is False:
                display_text = f"{INVALID_ACCOUNT_SYMBOL} {display_text}"
            if group:
                display_text += f" | [{group}]"
            if vip_server:
                display_text += " | [VIP]"
            if note:
                display_text += f" | {note}"
            if rejoin_status:
                display_text += f" | {rejoin_status}"

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

    def _get_selected_account_username_password_rows(self, include_cookie: bool) -> list[str]:
        usernames = self._get_selected_usernames_silent()
        rows: list[str] = []
        for username in usernames:
            account_data = self.manager.accounts.get(username)
            if not isinstance(account_data, dict):
                if include_cookie:
                    rows.append(f"{username}:notfound:notfound")
                else:
                    rows.append(f"{username}:notfound")
                continue
            password_value = str(account_data.get("password", "") or "").strip()
            if include_cookie:
                cookie_value = str(account_data.get("cookie", "") or "").strip()
                saved_password_value = password_value if password_value else "notfound"
                saved_cookie_value = cookie_value if cookie_value else "notfound"
                rows.append(f"{username}:{saved_password_value}:{saved_cookie_value}")
                continue
            saved_password_value = password_value if password_value else "notfound"
            rows.append(f"{username}:{saved_password_value}")
        return list(dict.fromkeys(rows))

    def copy_selected_account_username_passwords(self) -> None:
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Copy user:pass", "Please select at least one account first.")
            return

        rows = self._get_selected_account_username_password_rows(include_cookie=False)
        if not rows:
            messagebox.showinfo("Copy user:pass", "No selected account rows found.")
            return

        if self._copy_text_to_clipboard("\n".join(rows)):
            self.show_success_message("user:pass copied." if len(rows) == 1 else "user:pass entries copied.")

    def copy_selected_account_username_password_cookies(self) -> None:
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Copy user:pass:cookie", "Please select at least one account first.")
            return

        rows = self._get_selected_account_username_password_rows(include_cookie=True)
        if not rows:
            messagebox.showinfo(
                "Copy user:pass:cookie", "No saved username:password:cookie found for the selected account(s)."
            )
            return

        if self._copy_text_to_clipboard("\n".join(rows)):
            self.show_success_message(
                "user:pass:cookie copied." if len(rows) == 1 else "user:pass:cookie entries copied."
            )

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

        self._update_account_context_menu_state()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def on_account_drag_start(self, event: tk.Event) -> Optional[str]:
        if self.settings.get("enable_multi_select", False) and self._multi_select_modifier_active(event):
            return self.on_account_multi_select_click(event)
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

    def on_account_multi_select_click(self, event: tk.Event) -> Optional[str]:
        if not self.settings.get("enable_multi_select", False):
            return
        if not self._multi_select_modifier_active(event):
            return
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

    def _on_multi_select_key_press(self, event: tk.Event) -> None:
        key = normalize_multi_select_event_key(event)
        if key:
            self._pressed_multi_select_keys.add(key)

    def _on_multi_select_key_release(self, event: tk.Event) -> None:
        key = normalize_multi_select_event_key(event)
        if key:
            self._pressed_multi_select_keys.discard(key)

    def _clear_multi_select_pressed_keys(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self._pressed_multi_select_keys.clear()

    def _multi_select_modifier_active(self, event: tk.Event) -> bool:
        key = self._get_multi_select_keybind()
        state = int(getattr(event, "state", 0) or 0)
        state_mask = MULTI_SELECT_MODIFIER_STATE_MASKS.get(key)
        if state_mask is not None and bool(state & state_mask):
            return True
        return key in self._pressed_multi_select_keys

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
                "Quick Sign-In requires Google Chrome, Mozilla Firefox, Waterfox, or Chromium.\n"
                "Install a browser or use Settings to download Chromium, then try again."
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
                "Add Account requires Google Chrome, Mozilla Firefox, Waterfox, or Chromium.\n"
                "Install a browser or use Settings to download Chromium, then try again."
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
    
    def import_cookie(self) -> None:
        """
        Import accounts using .ROBLOSECURITY cookies.
        """
        import_window = tk.Toplevel(self.root)
        import_window.title("Import Cookies")
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
        import_window.grab_set()
        self.register_toplevel(import_window)
        
        main_frame = ttk.Frame(import_window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(
            main_frame,
            text="Import Accounts from Cookies",
            style="Dark.TLabel",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 15))
        
        ttk.Label(
            main_frame,
            text="Paste one .ROBLOSECURITY cookie per line:",
            style="Dark.TLabel"
        ).pack(anchor="w", pady=(0, 5))
        
        cookie_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        cookie_frame.pack(fill="both", expand=True, pady=(0, 15))
        
        cookie_text = tk.Text(
            cookie_frame,
            bg=self.BG_MID,
            fg=self.FG_TEXT,
            font=("Segoe UI", 9),
            height=8,
            wrap="none"
        )
        cookie_text.pack(side="left", fill="both", expand=True)
        self.register_themable_text_widget(cookie_text)
        
        cookie_scrollbar = ttk.Scrollbar(cookie_frame, command=cookie_text.yview)
        cookie_scrollbar.pack(side="right", fill="y")
        cookie_text.config(yscrollcommand=cookie_scrollbar.set)
        
        def parse_cookies(raw_text: str) -> list[str]:
            cookies: list[str] = []
            for line in (raw_text or "").splitlines():
                cookie = line.strip()
                if cookie:
                    cookies.append(cookie)
            return cookies

        def complete_import(imported_usernames: list[str], failed_count: int) -> None:
            imported_count = len(imported_usernames)
            if imported_count > 0:
                self.refresh_accounts()

            if imported_count == 1 and failed_count == 0:
                self.show_success_message(f"Account '{imported_usernames[0]}' imported successfully!")
                return

            if imported_count > 0 and failed_count == 0:
                self.show_success_message(f"Imported {imported_count} account(s) successfully!")
                return

            if imported_count > 0:
                messagebox.showwarning(
                    "Import Complete",
                    f"Imported {imported_count} account(s). Failed to import {failed_count} cookie(s)."
                )
                return

            messagebox.showerror("Error", "No accounts were imported. Please check the cookie values.")

        def worker(cookies: list[str]) -> None:
            imported_usernames: list[str] = []
            failed_count = 0
            try:
                for cookie in cookies:
                    success, username = self.manager.import_cookie_account(cookie)
                    if success:
                        imported_usernames.append(str(username or "").strip() or "Unknown")
                    else:
                        failed_count += 1
                self.root.after(0, lambda: complete_import(imported_usernames, failed_count))
            except Exception as e:
                error_message = str(e)
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Error", f"Failed to import accounts: {error_message}")
                )

        def do_import() -> None:
            cookies = parse_cookies(cookie_text.get("1.0", "end-1c"))
            
            if not cookies:
                messagebox.showwarning("Missing Information", "Please paste at least one cookie.")
                return
            
            threading.Thread(target=worker, args=(cookies,), daemon=True).start()
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

    def force_quit_roblox(self):
        """Force close all Roblox instances via taskkill."""
        confirm = messagebox.askyesno(
            "Force Quit Roblox",
            "This will immediately close all running RobloxPlayerBeta.exe processes. Continue?"
        )
        if not confirm:
            return

        active_usernames = [
            username
            for username in getattr(self.manager, "accounts", {}).keys()
            if self._get_auto_rejoin_session_snapshot(username)
        ]
        self._mark_active_sessions_manually_stopped(usernames=active_usernames)

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

        self._invalidate_tracked_process_caches()
        self._invalidate_active_client_indicator_cache()
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

    class _MemoryStatusEx(ctypes.Structure):
        """Layout for kernel32.GlobalMemoryStatusEx."""

        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    def _memtrim_find_roblox_windows(self, use_cache: bool = False) -> list[tuple[int, str, int]]:
        """Return [(hwnd, title, pid)] for visible Roblox client windows (memory trim)."""
        if platform.system() != "Windows":
            return []

        snapshot = self._get_tracked_process_window_snapshot(use_cache=use_cache, include_windows=True)
        results: list[tuple[int, str, int]] = []
        for record in snapshot.window_records:
            if not record.is_visible:
                continue
            image_name = str(snapshot.pid_to_image.get(record.pid, "") or "").strip().lower()
            has_roblox_title = "Roblox" in record.title
            has_roblox_window_class = record.class_name == "WINDOWSCLIENT"
            has_roblox_process = "roblox" in image_name
            if not (has_roblox_title or has_roblox_window_class):
                continue
            if not (has_roblox_process or has_roblox_title):
                continue
            results.append((record.hwnd, record.title, record.pid))
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
    def _get_total_physical_memory_bytes(cls) -> Optional[int]:
        if platform.system() != "Windows":
            return None

        try:
            memory_status = cls._MemoryStatusEx()
            memory_status.dwLength = ctypes.sizeof(memory_status)
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
            if not ok:
                return None
            total_physical_bytes = int(memory_status.ullTotalPhys)
            if total_physical_bytes <= 0:
                return None
            return total_physical_bytes
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

    def auto_arrange_clients(self, show_feedback=True):
        """Automatically tile active Roblox client windows on the primary monitor."""
        if platform.system() != "Windows" or not win32gui:
            if show_feedback:
                messagebox.showerror("Auto-Arrange Clients", "This feature is only available on Windows.")
            return False

        try:
            roblox_windows = self._get_roblox_client_windows(use_cache=False)
        except Exception as exc:
            if show_feedback:
                messagebox.showerror("Auto-Arrange Clients", f"Failed to detect Roblox clients:\n{exc}")
            return False

        if not roblox_windows:
            if show_feedback:
                messagebox.showinfo("Auto-Arrange Clients", "No active Roblox client windows were detected.")
            return False

        try:
            arranged_signature = self._arrange_roblox_client_windows(roblox_windows)
        except Exception as exc:
            if show_feedback:
                messagebox.showerror("Auto-Arrange Clients", f"Failed to arrange Roblox clients:\n{exc}")
            return False

        if self.settings.get("keep_roblox_clients_arranged", False):
            self._keep_clients_arranged_last_signature = arranged_signature

        if show_feedback:
            self.show_success_message(
                f"Auto-arranged {len(roblox_windows)} Roblox client(s)!",
                title="Auto-Arrange Clients"
            )
        return True

    def _arrange_roblox_client_windows(self, roblox_windows):
        self._arrange_windows_on_primary_monitor(roblox_windows)
        return self._get_roblox_window_signature(roblox_windows)

    def _cancel_keep_clients_arranged_check(self):
        after_id = getattr(self, "_keep_clients_arranged_after_id", None)
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self._keep_clients_arranged_after_id = None

    def _set_keep_clients_arranged_enabled(self, enabled, save=False, arrange_now=False):
        enabled = bool(enabled)
        self.settings["keep_roblox_clients_arranged"] = enabled
        if save:
            self.save_settings()
        if not enabled:
            self._cancel_keep_clients_arranged_check()
            self._keep_clients_arranged_last_signature = None
            self._keep_clients_arranged_check_pending = False
            self._keep_clients_arranged_generation = int(getattr(self, "_keep_clients_arranged_generation", 0)) + 1
            return
        delay_ms = 250 if arrange_now else self.KEEP_CLIENTS_ARRANGED_INTERVAL_MS
        self._schedule_keep_clients_arranged_check(delay_ms=delay_ms, reset_signature=True)

    def _get_roblox_window_signature(self, hwnds):
        signature = []
        for hwnd in self._sort_windows_by_position(list(hwnds or [])):
            try:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            except Exception:
                left = top = right = bottom = 0
            signature.append(
                (
                    int(hwnd),
                    int(left),
                    int(top),
                    max(0, int(right) - int(left)),
                    max(0, int(bottom) - int(top)),
                )
            )
        return tuple(signature)

    def _schedule_keep_clients_arranged_check(self, delay_ms=None, reset_signature=False):
        if reset_signature:
            self._keep_clients_arranged_last_signature = None
            self._keep_clients_arranged_generation = int(getattr(self, "_keep_clients_arranged_generation", 0)) + 1

        self._cancel_keep_clients_arranged_check()

        if not self.settings.get("keep_roblox_clients_arranged", False):
            return

        if platform.system() != "Windows" or not win32gui:
            return

        if delay_ms is None:
            delay_ms = self.KEEP_CLIENTS_ARRANGED_INTERVAL_MS

        self._keep_clients_arranged_after_id = self.root.after(
            max(100, int(delay_ms)),
            self._run_keep_clients_arranged_check,
        )

    def _run_keep_clients_arranged_check(self):
        self._keep_clients_arranged_after_id = None

        if not self.settings.get("keep_roblox_clients_arranged", False):
            return

        if platform.system() != "Windows" or not win32gui:
            return

        if self._keep_clients_arranged_check_in_progress:
            self._keep_clients_arranged_check_pending = True
            return

        self._keep_clients_arranged_check_in_progress = True
        run_generation = int(getattr(self, "_keep_clients_arranged_generation", 0))
        previous_signature = self._keep_clients_arranged_last_signature

        def worker():
            next_signature = None
            try:
                roblox_windows = self._get_roblox_client_windows(use_cache=True)
                next_signature = self._get_roblox_window_signature(roblox_windows)
                if roblox_windows and next_signature != previous_signature:
                    next_signature = self._arrange_roblox_client_windows(roblox_windows)
            except Exception:
                next_signature = None

            def apply():
                self._keep_clients_arranged_check_in_progress = False
                should_run_pending = bool(self._keep_clients_arranged_check_pending)
                self._keep_clients_arranged_check_pending = False

                if int(getattr(self, "_keep_clients_arranged_generation", 0)) != run_generation:
                    if should_run_pending and self.settings.get("keep_roblox_clients_arranged", False):
                        self._schedule_keep_clients_arranged_check(delay_ms=250)
                    return

                if not self.settings.get("keep_roblox_clients_arranged", False):
                    return

                if platform.system() != "Windows" or not win32gui:
                    return

                self._keep_clients_arranged_last_signature = next_signature
                if should_run_pending:
                    self._schedule_keep_clients_arranged_check(delay_ms=250)
                else:
                    self._schedule_keep_clients_arranged_check()

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True, name="keep-clients-arranged").start()

    def _notify_roblox_windows_changed(self, success_count: Any, delay_ms: int = 2000) -> None:
        if int(success_count or 0) <= 0:
            return
        self._invalidate_tracked_process_caches()
        self._invalidate_active_client_indicator_cache()
        if self._get_rename_client_titles_enabled():
            self._log_client_title_rename(
                f"Roblox launch detected; scheduling title refresh in {int(delay_ms)} ms.",
                debug=True,
            )
            self._schedule_rename_tracked_roblox_client_window_titles(delay_ms=delay_ms)
        if self.settings.get("roblox_headless_mode_enabled", False):
            self._log_roblox_headless(
                f"Roblox launch detected; scheduling NoClient pass in {int(delay_ms)} ms.",
                debug=True,
            )
            self._schedule_roblox_headless_pass(delay_ms=delay_ms)
        if self.settings.get("anti_afk_enabled", False):
            self._log_anti_afk(
                f"Roblox launch detected; scheduling activation check in {int(delay_ms)} ms.",
                debug=True,
            )
            self._schedule_anti_afk_wait_check(delay_ms=delay_ms)
        if not self.settings.get("keep_roblox_clients_arranged", False):
            return
        self._schedule_keep_clients_arranged_check(
            delay_ms=delay_ms,
            reset_signature=True,
        )

    def _get_roblox_client_windows(self, use_cache=True):
        """Return a list of HWNDs for visible Roblox client windows."""
        snapshot = self._get_tracked_window_snapshot(
            self.ROBLOX_CLIENT_EXECUTABLES,
            use_cache=use_cache,
        )
        windows = list((snapshot.get("pid_to_hwnd", {}) or {}).values())
        windows.sort(key=int)
        return windows

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

    def toggle_selected_account_auto_rejoin(self):
        usernames = self._get_selected_usernames_silent()
        if not usernames:
            messagebox.showwarning("Auto-Rejoin", "Please select at least one account first.")
            return

        all_enabled = all(self._is_account_auto_rejoin_enabled(username) for username in usernames)
        target_enabled = not all_enabled

        changed = 0
        for username in usernames:
            if self.manager.set_account_auto_rejoin_enabled(username, target_enabled):
                changed += 1

        self._apply_auto_rejoin_preferences_to_active_sessions(usernames)
        self.refresh_accounts(selected_usernames=usernames)

        if changed <= 0:
            return

        if len(usernames) == 1:
            state_text = "enabled" if target_enabled else "disabled"
            self.show_success_message(f"Auto-Rejoin {state_text} for '{usernames[0]}'.")
        else:
            state_text = "enabled" if target_enabled else "disabled"
            self.show_success_message(f"Auto-Rejoin {state_text} for {changed} account(s).")

    def _update_account_context_menu_state(self):
        menu = getattr(self, "account_context_menu", None)
        menu_index = getattr(self, "_account_context_auto_rejoin_index", None)
        if menu is None or menu_index is None:
            return

        usernames = self._get_selected_usernames_silent()
        all_enabled = bool(usernames) and all(
            self._is_account_auto_rejoin_enabled(username) for username in usernames
        )
        label = "Disable Auto-Rejoin" if all_enabled else "Enable Auto-Rejoin"
        try:
            menu.entryconfigure(menu_index, label=label)
        except Exception:
            pass

    def edit_account_vip_server(self):
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
            initial_value = self.manager.get_account_vip_server(usernames[0])

        vip_input = simpledialog.askstring(
            "Set VIP Server",
            "Enter private server link or VIP link code (blank to clear):",
            initialvalue=initial_value
        )
        if vip_input is None:
            return

        mapping = {uname: vip_input for uname in usernames}
        result = self.manager.bulk_set_account_vip_servers(mapping)
        self.refresh_accounts(selected_usernames=usernames)

        if result.get("changed", 0) > 0:
            if len(usernames) == 1:
                self.show_success_message(f"VIP server updated for '{usernames[0]}'.")
            else:
                self.show_success_message(f"VIP server updated for {result.get('changed', 0)} account(s).")

    def _read_vip_server_csv_mapping(self, file_path):
        mapping = {}
        with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.reader(csv_file))

        if not rows:
            return mapping

        header = [str(cell or "").strip().lower() for cell in rows[0]]
        username_header_aliases = {"username", "user", "account", "name"}
        vip_header_aliases = {
            "private_server_link",
            "private_server",
            "vip_server",
            "vip",
            "vip_link",
            "private_server_link_or_code",
        }

        has_header = (
            any(cell in username_header_aliases for cell in header)
            and any(cell in vip_header_aliases for cell in header)
        )

        if has_header:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                field_lookup = {}
                for raw_field in (reader.fieldnames or []):
                    normalized_field = str(raw_field or "").strip().lower()
                    if normalized_field:
                        field_lookup[normalized_field] = raw_field
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    username = ""
                    vip_value = ""
                    for key in username_header_aliases:
                        source_field = field_lookup.get(key)
                        username = str(row.get(source_field, "") or "").strip() if source_field else ""
                        if username:
                            break
                    for key in vip_header_aliases:
                        source_field = field_lookup.get(key)
                        vip_value = str(row.get(source_field, "") or "").strip() if source_field else ""
                        if vip_value:
                            break
                    if username:
                        mapping[username] = vip_value
            return mapping

        for row in rows:
            if not row:
                continue
            username = str(row[0] if len(row) >= 1 else "").strip()
            vip_value = str(row[1] if len(row) >= 2 else "").strip()
            if username:
                mapping[username] = vip_value

        return mapping

    def open_vip_server_manager(self):
        window = tk.Toplevel(self.root)
        window.title("VIP Server Mapping")
        window.geometry("780x460")
        window.minsize(680, 360)
        window.configure(bg=self.BG_DARK)
        window.transient(self.root)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        main_frame = ttk.Frame(window, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(
            main_frame,
            text="Assign private server links/codes per account",
            style="Dark.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        list_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        list_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            list_frame,
            columns=("username", "group", "vip_server"),
            show="headings",
            style="Dark.Treeview",
            selectmode="extended",
        )
        tree.heading("username", text="Username")
        tree.heading("group", text="Group")
        tree.heading("vip_server", text="VIP Server")
        tree.column("username", width=170, anchor="w")
        tree.column("group", width=130, anchor="w")
        tree.column("vip_server", width=420, anchor="w")
        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        selected_label_var = tk.StringVar(value="Selected: (none)")
        selected_label = ttk.Label(main_frame, textvariable=selected_label_var, style="Dark.TLabel")
        selected_label.pack(anchor="w", pady=(8, 4))

        vip_entry = ttk.Entry(main_frame, style="Dark.TEntry")
        vip_entry.pack(fill="x")

        def refresh_tree():
            selected_usernames = []
            for item_id in tree.selection():
                values = tree.item(item_id, "values") or []
                if len(values) >= 1:
                    selected_usernames.append(str(values[0]))

            tree.delete(*tree.get_children())
            for username, data in self.manager.accounts.items():
                if not isinstance(data, dict):
                    continue
                group = str(data.get("group", "") or "").strip()
                vip_server = str(data.get("vip_server", "") or "").strip()
                tree.insert("", "end", values=(username, group, vip_server))

            if selected_usernames:
                wanted = set(selected_usernames)
                for item_id in tree.get_children():
                    values = tree.item(item_id, "values") or []
                    if len(values) >= 1 and str(values[0]) in wanted:
                        tree.selection_add(item_id)
                on_tree_select()

        def on_tree_select(_event=None):
            selected_items = tree.selection()
            if not selected_items:
                selected_label_var.set("Selected: (none)")
                vip_entry.delete(0, tk.END)
                return

            usernames = []
            first_value = ""
            for index, item_id in enumerate(selected_items):
                values = tree.item(item_id, "values") or []
                if len(values) < 1:
                    continue
                usernames.append(str(values[0]))
                if index == 0 and len(values) >= 3:
                    first_value = str(values[2] or "").strip()

            if not usernames:
                selected_label_var.set("Selected: (none)")
                vip_entry.delete(0, tk.END)
                return

            if len(usernames) == 1:
                selected_label_var.set(f"Selected: {usernames[0]}")
            else:
                selected_label_var.set(f"Selected: {len(usernames)} accounts")
            vip_entry.delete(0, tk.END)
            vip_entry.insert(0, first_value)

        def apply_to_selection():
            selected_items = tree.selection()
            if not selected_items:
                messagebox.showwarning("VIP Server Mapping", "Select at least one account first.")
                return

            vip_value = vip_entry.get().strip()
            mapping = {}
            for item_id in selected_items:
                values = tree.item(item_id, "values") or []
                if len(values) >= 1:
                    mapping[str(values[0])] = vip_value

            if not mapping:
                return

            result = self.manager.bulk_set_account_vip_servers(mapping)
            refresh_tree()
            self.refresh_accounts(selected_usernames=list(mapping.keys()))

            changed = result.get("changed", 0)
            if changed > 0:
                self.show_success_message(f"Updated VIP mapping for {changed} account(s).")

        def clear_selection():
            vip_entry.delete(0, tk.END)
            apply_to_selection()

        def launch_selection():
            selected_items = tree.selection()
            if not selected_items:
                messagebox.showwarning("Launch", "Select at least one account first.")
                return

            usernames = []
            for item_id in selected_items:
                values = tree.item(item_id, "values") or []
                if len(values) >= 1:
                    usernames.append(str(values[0]))
            if not usernames:
                messagebox.showwarning("Launch", "Select at least one account first.")
                return

            self._launch_game_for_usernames(usernames)

        button_row = ttk.Frame(main_frame, style="Dark.TFrame")
        button_row.pack(fill="x", pady=(8, 0))

        ttk.Button(button_row, text="Apply to Selected", style="Dark.TButton", command=apply_to_selection).pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        ttk.Button(button_row, text="Clear Selected", style="Dark.TButton", command=clear_selection).pack(
            side="left", fill="x", expand=True, padx=(5, 5)
        )
        ttk.Button(button_row, text="Launch", style="Dark.TButton", command=launch_selection).pack(
            side="left", fill="x", expand=True, padx=(5, 5)
        )
        ttk.Button(button_row, text="Close", style="Dark.TButton", command=window.destroy).pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )

        tree.bind("<<TreeviewSelect>>", on_tree_select)
        window.bind("<Escape>", lambda _evt: window.destroy())
        refresh_tree()

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
                "Launching browser requires Google Chrome, Mozilla Firefox, Waterfox, or Chromium.\n"
                "Install a browser or use Settings to download Chromium, then try again."
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
                    before_pids = self._get_running_tracked_roblox_pid_set(use_cache=False)
                    launched = self.manager.launch_home_app(uname, version=version_path or None, enable_debug=debug_enabled)
                    after_pids = before_pids
                    if launched:
                        success_count += 1
                        after_pids = self._wait_for_tracked_roblox_pid_change(before_pids)
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

                    self._notify_roblox_windows_changed(success_count)

                    if on_done_callback is not None:
                        try:
                            on_done_callback(success_count)
                        except Exception:
                            pass
                else:
                    messagebox.showerror("Error", "Failed to launch Roblox.")

            self.root.after(0, notify)

        threading.Thread(target=worker, args=(usernames, launch_delay, on_done_callback), daemon=True).start()

    def _invalidate_tracked_process_caches(self) -> None:
        try:
            with self._tracked_process_window_snapshot_lock:
                self._tracked_process_window_snapshot = None
        except (AttributeError, RuntimeError):
            self._tracked_process_window_snapshot = None
        try:
            with self._roblox_command_line_cache_lock:
                self._roblox_command_line_cache = {"pid_to_commandline": {}}
        except (AttributeError, RuntimeError):
            self._roblox_command_line_cache = {"pid_to_commandline": {}}

    def _get_running_tracked_roblox_pid_set(self, use_cache: bool = True) -> set[int]:
        return set(
            self._query_tracked_process_pid_map(
                getattr(self, "_tracked_roblox_exes", set()),
                use_cache=use_cache,
            ).keys()
        )

    def _normalize_pid_set(self, pid_values: Any) -> set[int]:
        if pid_values is None:
            return set()
        if isinstance(pid_values, (str, bytes)):
            iterable_values = [pid_values]
        else:
            try:
                iterable_values = list(pid_values)
            except TypeError:
                iterable_values = [pid_values]

        normalized_pids: set[int] = set()
        for raw_pid in iterable_values:
            try:
                pid_value = int(raw_pid)
            except (TypeError, ValueError):
                continue
            if pid_value > 0:
                normalized_pids.add(pid_value)
        return normalized_pids

    def _wait_for_tracked_roblox_pid_change(
        self,
        before_pids: Any,
        timeout_seconds: float = CLIENT_TITLE_RENAME_PID_WAIT_SECONDS,
        poll_interval_seconds: float = CLIENT_TITLE_RENAME_PID_POLL_SECONDS,
    ) -> set[int]:
        normalized_before = self._normalize_pid_set(before_pids)
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        sleep_seconds = max(0.1, float(poll_interval_seconds))
        last_seen = self._get_running_tracked_roblox_pid_set(use_cache=False)

        while time.monotonic() <= deadline:
            last_seen = self._get_running_tracked_roblox_pid_set(use_cache=False)
            new_pids = sorted(last_seen - normalized_before)
            if new_pids:
                self._log_client_title_rename(
                    f"Detected new Roblox PID(s) after launch: {', '.join(str(pid) for pid in new_pids)}.",
                    debug=True,
                )
                return last_seen
            time.sleep(sleep_seconds)

        self._log_client_title_rename(
            "No new Roblox PID was detected before the launch wait timed out.",
            debug=True,
        )
        return last_seen

    def _query_tasklist_pid_map(self, executables: Any, use_cache: bool = True) -> dict[int, str]:
        """Return pid->image_name for the provided executable names."""
        return self._query_tracked_process_pid_map(executables, use_cache=use_cache)

    def _normalize_tracked_executable_names(self, executables: Any) -> set[str]:
        if isinstance(executables, (str, bytes)):
            raw_values = [executables]
        else:
            try:
                raw_values = list(executables or [])
            except TypeError:
                raw_values = [executables]
        return {
            str(item or "").strip().lower()
            for item in raw_values
            if str(item or "").strip()
        }

    def _empty_tracked_process_window_snapshot(
        self,
        created_at: Optional[float] = None,
    ) -> TrackedProcessWindowSnapshot:
        timestamp = time.monotonic() if created_at is None else float(created_at)
        return TrackedProcessWindowSnapshot(
            created_at=timestamp,
            pid_to_image={},
            window_records=(),
            includes_windows=False,
        )

    def _query_windows_process_image_map(self) -> dict[int, str]:
        if platform.system() != "Windows":
            return {}

        snapshot_handle: Any = None
        pid_to_image: dict[int, str] = {}
        try:
            kernel32 = ctypes.windll.kernel32
            create_snapshot = kernel32.CreateToolhelp32Snapshot
            create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
            create_snapshot.restype = wintypes.HANDLE

            process_first = kernel32.Process32FirstW
            process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
            process_first.restype = wintypes.BOOL

            process_next = kernel32.Process32NextW
            process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
            process_next.restype = wintypes.BOOL

            snapshot_handle = create_snapshot(TH32CS_SNAPPROCESS, 0)
            if not snapshot_handle or snapshot_handle == INVALID_HANDLE_VALUE:
                return {}

            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(ProcessEntry32W)
            has_entry = bool(process_first(snapshot_handle, ctypes.byref(entry)))
            while has_entry:
                pid_value = int(entry.th32ProcessID)
                image_name = str(entry.szExeFile or "").strip()
                if pid_value > 0 and image_name:
                    pid_to_image[pid_value] = image_name

                entry = ProcessEntry32W()
                entry.dwSize = ctypes.sizeof(ProcessEntry32W)
                has_entry = bool(process_next(snapshot_handle, ctypes.byref(entry)))
        except WINDOWS_API_ERROR_TYPES:
            return {}
        finally:
            if snapshot_handle and snapshot_handle != INVALID_HANDLE_VALUE:
                try:
                    ctypes.windll.kernel32.CloseHandle(snapshot_handle)
                except WINDOWS_API_ERROR_TYPES:
                    pass

        return pid_to_image

    def _query_windows_window_records(self) -> tuple[TrackedWindowRecord, ...]:
        if platform.system() != "Windows" or win32gui is None or win32process is None or win32con is None:
            return ()

        records: list[TrackedWindowRecord] = []

        def enum_handler(hwnd: int, _: Any) -> bool:
            try:
                if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                    return True
                _, pid_value = win32process.GetWindowThreadProcessId(hwnd)
                normalized_pid = int(pid_value)
                if normalized_pid <= 0:
                    return True
                title_text = str(win32gui.GetWindowText(hwnd) or "").strip()
                class_name = str(win32gui.GetClassName(hwnd) or "").strip()
                is_visible = bool(win32gui.IsWindowVisible(hwnd))
            except WINDOWS_API_ERROR_TYPES:
                return True

            is_hung = False
            try:
                is_hung = bool(ctypes.windll.user32.IsHungAppWindow(int(hwnd)))
            except WINDOWS_API_ERROR_TYPES:
                is_hung = False

            records.append(
                TrackedWindowRecord(
                    hwnd=int(hwnd),
                    pid=normalized_pid,
                    title=title_text,
                    class_name=class_name,
                    is_visible=is_visible,
                    is_hung=is_hung,
                )
            )
            return True

        try:
            win32gui.EnumWindows(enum_handler, None)
        except WINDOWS_API_ERROR_TYPES:
            return ()

        return tuple(records)

    def _build_tracked_process_window_snapshot(
        self,
        include_windows: bool,
    ) -> TrackedProcessWindowSnapshot:
        created_at = time.monotonic()
        return TrackedProcessWindowSnapshot(
            created_at=created_at,
            pid_to_image=self._query_windows_process_image_map(),
            window_records=self._query_windows_window_records() if include_windows else (),
            includes_windows=include_windows,
        )

    def _get_tracked_process_window_snapshot(
        self,
        use_cache: bool = True,
        include_windows: bool = True,
    ) -> TrackedProcessWindowSnapshot:
        if platform.system() != "Windows":
            return self._empty_tracked_process_window_snapshot()

        lock = getattr(self, "_tracked_process_window_snapshot_lock", None)
        if lock is None:
            snapshot = self._build_tracked_process_window_snapshot(include_windows=include_windows)
            self._tracked_process_window_snapshot = snapshot
            return snapshot

        with lock:
            cached_snapshot = getattr(self, "_tracked_process_window_snapshot", None)
            ttl_seconds = float(getattr(self, "_tracked_process_window_snapshot_ttl_seconds", 0.75) or 0.75)
            if (
                use_cache
                and isinstance(cached_snapshot, TrackedProcessWindowSnapshot)
                and (time.monotonic() - cached_snapshot.created_at) < ttl_seconds
                and (cached_snapshot.includes_windows or not include_windows)
            ):
                return cached_snapshot

            snapshot = self._build_tracked_process_window_snapshot(include_windows=include_windows)
            self._tracked_process_window_snapshot = snapshot
            return snapshot

    def _query_tracked_process_pid_map(self, executables: Any, use_cache: bool = True) -> dict[int, str]:
        """Return pid->image_name from a native Windows process snapshot."""
        target_exes = self._normalize_tracked_executable_names(executables)
        if not target_exes:
            return {}

        snapshot = self._get_tracked_process_window_snapshot(use_cache=use_cache, include_windows=False)
        return {
            int(pid_value): str(image_name or "").strip()
            for pid_value, image_name in snapshot.pid_to_image.items()
            if str(image_name or "").strip().lower() in target_exes
        }

    def _get_tracked_window_snapshot(self, executables: Any, use_cache: bool = True) -> dict[str, dict[int, Any]]:
        target_exes = self._normalize_tracked_executable_names(executables)
        if not target_exes:
            return {
                "pid_to_image": {},
                "pid_to_hwnd": {},
                "pid_to_title": {},
                "pid_to_hung": {},
            }

        snapshot = self._get_tracked_process_window_snapshot(use_cache=use_cache, include_windows=True)
        pid_to_image: dict[int, str] = {
            int(pid_value): str(image_name or "").strip()
            for pid_value, image_name in snapshot.pid_to_image.items()
            if str(image_name or "").strip().lower() in target_exes
        }
        pid_to_hwnd: dict[int, int] = {}
        pid_to_title: dict[int, str] = {}
        pid_to_hung: dict[int, bool] = {}
        target_pids = {int(pid_value) for pid_value in pid_to_image.keys()}

        for record in snapshot.window_records:
            if record.pid not in target_pids or not record.is_visible:
                continue
            pid_to_hwnd.setdefault(record.pid, record.hwnd)
            if record.title:
                pid_to_title.setdefault(record.pid, record.title)
            if record.is_hung:
                pid_to_hung[record.pid] = True

        return {
            "pid_to_image": dict(pid_to_image),
            "pid_to_hwnd": dict(pid_to_hwnd),
            "pid_to_title": dict(pid_to_title),
            "pid_to_hung": dict(pid_to_hung),
        }

    def _prune_roblox_command_line_cache(
        self,
        running_pid_to_image: dict[int, str],
        target_exes: set[str],
    ) -> dict[int, str]:
        running_pids = set(running_pid_to_image.keys())
        with self._roblox_command_line_cache_lock:
            cache = getattr(self, "_roblox_command_line_cache", None)
            cached_pid_to_commandline = dict(
                (cache.get("pid_to_commandline", {}) or {}) if isinstance(cache, dict) else {}
            )
            pruned_pid_to_commandline: dict[int, str] = {}
            for raw_pid, command_line in cached_pid_to_commandline.items():
                try:
                    pid_value = int(raw_pid)
                except (TypeError, ValueError):
                    continue
                image_name = str(running_pid_to_image.get(pid_value, "") or "").strip().lower()
                if pid_value in running_pids and image_name in target_exes:
                    pruned_pid_to_commandline[pid_value] = str(command_line or "")
            self._roblox_command_line_cache = {
                "pid_to_commandline": dict(pruned_pid_to_commandline),
            }
        return pruned_pid_to_commandline

    def _store_roblox_command_line_cache_entries(self, pid_to_commandline: dict[int, str]) -> None:
        if not pid_to_commandline:
            return
        with self._roblox_command_line_cache_lock:
            cache = getattr(self, "_roblox_command_line_cache", None)
            cached_pid_to_commandline = dict(
                (cache.get("pid_to_commandline", {}) or {}) if isinstance(cache, dict) else {}
            )
            cached_pid_to_commandline.update(pid_to_commandline)
            self._roblox_command_line_cache = {
                "pid_to_commandline": cached_pid_to_commandline,
            }

    def _query_roblox_process_command_lines(
        self,
        executables: Any,
        pid_values: Optional[set[int]] = None,
        use_cache: bool = True,
    ) -> dict[int, str]:
        """Return pid->commandline for tracked Roblox executables via CIM."""
        pid_to_commandline = {}
        target_exes = {str(item).strip().lower() for item in (executables or set()) if item}
        if not target_exes:
            return pid_to_commandline

        target_pids = self._normalize_pid_set(pid_values) if pid_values is not None else None
        if pid_values is not None and not target_pids:
            return pid_to_commandline

        running_pid_to_image = self._query_tracked_process_pid_map(target_exes, use_cache=use_cache)
        running_pids = set(running_pid_to_image.keys())
        requested_pids = set(running_pids)
        if target_pids is not None:
            requested_pids = target_pids & running_pids
        if not requested_pids:
            self._prune_roblox_command_line_cache(running_pid_to_image, target_exes)
            return pid_to_commandline

        pruned_pid_to_commandline = self._prune_roblox_command_line_cache(
            running_pid_to_image,
            target_exes,
        )

        for pid_value in requested_pids:
            if pid_value in pruned_pid_to_commandline:
                pid_to_commandline[pid_value] = pruned_pid_to_commandline[pid_value]

        missing_pids = requested_pids - set(pid_to_commandline.keys())
        if not missing_pids:
            return pid_to_commandline

        process_names = sorted({name[:-4] if name.endswith(".exe") else name for name in target_exes})
        if not process_names:
            return pid_to_commandline

        escaped_names = ", ".join([f"'{name}'" for name in process_names])
        pid_filter = " OR ".join([f"ProcessId={pid_value}" for pid_value in sorted(missing_pids)])
        ps_script = (
            f"$names=@({escaped_names}); "
            f"Get-CimInstance Win32_Process -Filter \"{pid_filter}\" | "
            "Where-Object { $names -contains (($_.Name -replace '\\.exe$','').ToLower()) } | "
            "Select-Object ProcessId,Name,CommandLine | "
            "ConvertTo-Json -Compress"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
                **subprocess_no_window_kwargs(),
            )
        except Exception:
            return pid_to_commandline

        stdout = str(result.stdout or "").strip()
        if not stdout:
            if result.returncode == 0:
                missing_pid_to_commandline = {
                    int(pid_value): ""
                    for pid_value in missing_pids
                }
                self._store_roblox_command_line_cache_entries(missing_pid_to_commandline)
                pid_to_commandline.update(missing_pid_to_commandline)
            return pid_to_commandline

        try:
            payload = json.loads(stdout)
        except Exception:
            return pid_to_commandline

        rows = payload if isinstance(payload, list) else [payload]
        fetched_pid_to_commandline = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                pid_value = int(row.get("ProcessId", 0) or 0)
            except (TypeError, ValueError):
                pid_value = 0
            if pid_value <= 0 or pid_value not in missing_pids:
                continue
            row_image_name = str(row.get("Name", "") or "").strip().lower()
            if row_image_name and not row_image_name.endswith(".exe"):
                row_image_name = f"{row_image_name}.exe"
            if row_image_name and row_image_name not in target_exes:
                continue
            command_line = str(row.get("CommandLine", "") or "").strip()
            fetched_pid_to_commandline[pid_value] = command_line

        known_missing_pids = set(missing_pids)
        known_missing_pids.difference_update(fetched_pid_to_commandline.keys())
        for pid_value in known_missing_pids:
            fetched_pid_to_commandline[int(pid_value)] = ""

        if fetched_pid_to_commandline:
            self._store_roblox_command_line_cache_entries(fetched_pid_to_commandline)
            pid_to_commandline.update(fetched_pid_to_commandline)

        return pid_to_commandline

    def _extract_place_id_from_command_line(self, command_line):
        text = str(command_line or "").strip()
        if not text:
            return ""

        patterns = [
            r"(?i)[?&]placeId=(\d+)",
            r"(?i)placeid%3d(\d+)",
            r"(?i)placeid[:=](\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                place_id = str(match.group(1) or "").strip()
                if place_id.isdigit():
                    return place_id
        return ""

    def _read_recent_place_ids_from_logs(self, max_files=12):
        cache = getattr(self, "_recent_place_id_log_cache", None)
        now = time.monotonic()
        if (
            isinstance(cache, dict)
            and (now - float(cache.get("ts", 0.0) or 0.0)) < 15.0
        ):
            return list(cache.get("values", []) or [])

        place_ids = []
        logs_dir = os.path.join(os.path.expandvars(r"%LOCALAPPDATA%"), "Roblox", "logs")
        if not os.path.isdir(logs_dir):
            return place_ids

        try:
            entries = [
                os.path.join(logs_dir, name)
                for name in os.listdir(logs_dir)
                if name.lower().endswith(".log")
            ]
            entries.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        except Exception:
            return place_ids

        patterns = [
            re.compile(r"(?i)[?&]placeId=(\d+)"),
            re.compile(r"(?i)\bplaceid\b[^0-9]{0,8}(\d+)"),
        ]

        for log_path in entries[:max_files]:
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as log_file:
                    content = log_file.read()
            except Exception:
                continue

            for pattern in patterns:
                for match in pattern.findall(content):
                    place_id = str(match or "").strip()
                    if place_id.isdigit():
                        place_ids.append(place_id)

        if not place_ids:
            return []

        unique = []
        seen = set()
        for place_id in reversed(place_ids):
            if place_id in seen:
                continue
            seen.add(place_id)
            unique.append(place_id)
        unique.reverse()
        self._recent_place_id_log_cache = {"ts": now, "values": list(unique)}
        return unique

    def _query_pid_place_id_map(self, executables, pid_values: Optional[set[int]] = None, allow_log_fallback=True, use_cache=True):
        pid_to_place_id = {}
        target_pids = None
        if pid_values is not None:
            target_pids = set()
            for raw_pid in pid_values:
                try:
                    pid_value = int(raw_pid)
                except Exception:
                    continue
                if pid_value > 0:
                    target_pids.add(pid_value)
            if not target_pids:
                return pid_to_place_id

        pid_to_commandline = self._query_roblox_process_command_lines(
            executables,
            pid_values=target_pids,
            use_cache=use_cache,
        )

        for pid_value, command_line in pid_to_commandline.items():
            place_id = self._extract_place_id_from_command_line(command_line)
            if place_id:
                pid_to_place_id[int(pid_value)] = place_id

        try:
            with self._pid_account_lock:
                launch_context_map = dict(self._pid_launch_context_map)
        except Exception:
            launch_context_map = {}

        for pid_value, context in launch_context_map.items():
            normalized_pid = int(pid_value)
            if target_pids is not None and normalized_pid not in target_pids:
                continue
            if normalized_pid in pid_to_place_id:
                continue
            normalized = self._normalize_launch_context(context)
            if normalized.get("mode") == "game":
                game_id = str(normalized.get("game_id", "") or "").strip()
                if game_id.isdigit():
                    pid_to_place_id[normalized_pid] = game_id

        if allow_log_fallback and not pid_to_place_id and pid_to_commandline:
            recent_place_ids = self._read_recent_place_ids_from_logs(max_files=8)
            if recent_place_ids:
                fallback_place_id = str(recent_place_ids[0] or "").strip()
                if fallback_place_id.isdigit():
                    for pid_value in pid_to_commandline.keys():
                        pid_to_place_id[int(pid_value)] = fallback_place_id

        return pid_to_place_id

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

    def _select_primary_session_pid(self, pid_values):
        normalized_pids = []
        for raw_pid in list(pid_values or []):
            try:
                pid_value = int(raw_pid)
            except Exception:
                continue
            if pid_value > 0:
                normalized_pids.append(pid_value)

        if not normalized_pids:
            return 0

        pid_to_image = self._query_tasklist_pid_map(getattr(self, "_tracked_roblox_exes", set()))
        ranked = []
        for pid_value in sorted(set(normalized_pids)):
            image_name = str(pid_to_image.get(pid_value, "") or "").strip().lower()
            has_window = bool(self._find_main_window_for_pid(pid_value))
            ranked.append((
                0 if image_name == "robloxplayerbeta.exe" else 1,
                0 if has_window else 1,
                pid_value,
            ))

        ranked.sort()
        return int(ranked[0][2]) if ranked else 0

    def _assign_new_pids_to_account(
        self,
        username: Any,
        before_pids: Any,
        after_pids: Any,
        launch_context: Optional[dict[str, Any]] = None,
    ) -> None:
        normalized_username = str(username or "").strip()
        if not normalized_username:
            return

        normalized_before = self._normalize_pid_set(before_pids)
        normalized_after = self._normalize_pid_set(after_pids)
        new_pids = normalized_after - normalized_before
        if not new_pids:
            self._log_client_title_rename(
                f"No new Roblox PID could be mapped to account {normalized_username}.",
                debug=True,
            )
            return

        normalized_context = self._normalize_launch_context(launch_context)
        with self._pid_account_lock:
            for pid_value in new_pids:
                self._pid_account_map[int(pid_value)] = normalized_username
                self._pid_launch_context_map[int(pid_value)] = dict(normalized_context)

        self._log_client_title_rename(
            (
                f"Mapped Roblox PID(s) {', '.join(str(pid) for pid in sorted(new_pids))} "
                f"to account {normalized_username}."
            ),
            debug=True,
        )

        self._invalidate_active_client_indicator_cache()

        for pid_value in new_pids:
            self._rename_roblox_client_window_title(int(pid_value), normalized_username)

        session_pid = self._select_primary_session_pid(new_pids)
        if session_pid > 0:
            try:
                self.manager.update_active_session_pid(normalized_username, session_pid)
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
            self.set_account_rejoin_status(normalized_username, "", 0)

        root = getattr(self, "root", None)
        if root is not None:
            try:
                root.after(
                    0,
                    lambda target_username=normalized_username: self.refresh_accounts(
                        selected_usernames=self._get_selected_usernames_silent() or [target_username]
                    ),
                )
            except (AttributeError, tk.TclError, TypeError):
                pass

    def _schedule_rename_tracked_roblox_client_window_titles(self, delay_ms: int = 0) -> None:
        if platform.system() != "Windows":
            self._log_client_title_rename("Skipping title refresh because this platform is not Windows.", debug=True)
            return
        if not self._get_rename_client_titles_enabled():
            self._log_client_title_rename("Skipping title refresh because the setting is disabled.", debug=True)
            return

        root = getattr(self, "root", None)
        if root is None:
            self._rename_tracked_roblox_client_window_titles()
            return

        try:
            root.after(max(0, int(delay_ms)), self._rename_tracked_roblox_client_window_titles)
        except (tk.TclError, TypeError, ValueError):
            self._rename_tracked_roblox_client_window_titles()

    def _rename_tracked_roblox_client_window_titles(self) -> None:
        if platform.system() != "Windows":
            self._log_client_title_rename("Skipping tracked title refresh because this platform is not Windows.", debug=True)
            return
        if not self._get_rename_client_titles_enabled():
            self._log_client_title_rename("Skipping tracked title refresh because the setting is disabled.", debug=True)
            return

        running_pids = self._get_running_tracked_roblox_pid_set(use_cache=False)
        with self._pid_account_lock:
            pid_account_map = dict(self._pid_account_map)

        queued_count = 0
        for raw_pid, raw_username in pid_account_map.items():
            try:
                pid_value = int(raw_pid)
            except (TypeError, ValueError):
                continue
            username = str(raw_username or "").strip()
            if pid_value not in running_pids or not username:
                continue
            queued_count += 1
            self._rename_roblox_client_window_title(pid_value, username)

        self._log_client_title_rename(
            f"Queued title refresh for {queued_count} tracked Roblox client(s).",
            debug=True,
        )

    def _rename_roblox_client_window_title(self, pid_value: Any, username: Any) -> None:
        if platform.system() != "Windows":
            self._log_client_title_rename("Skipping title rename because this platform is not Windows.", debug=True)
            return

        try:
            normalized_pid = int(pid_value)
        except (TypeError, ValueError):
            self._log_client_title_rename(f"Skipping title rename for invalid PID {pid_value!r}.", debug=True)
            return

        normalized_username = str(username or "").strip()
        if normalized_pid <= 0 or not normalized_username:
            self._log_client_title_rename(
                f"Skipping title rename for pid={normalized_pid} because the account name is empty.",
                debug=True,
            )
            return
        if not self._get_rename_client_titles_enabled():
            self._log_client_title_rename(
                f"Skipping title rename for pid={normalized_pid} because the setting is disabled.",
                debug=True,
            )
            return

        with self._client_title_rename_lock:
            if normalized_pid in self._client_title_rename_active_pids:
                self._log_client_title_rename(
                    f"Title rename worker is already active for pid={normalized_pid}.",
                    debug=True,
                )
                return
            self._client_title_rename_active_pids.add(normalized_pid)

        def _rename_worker(target_pid: int, target_name: str) -> None:
            stable_attempts = 0
            saw_window = False
            last_title = ""
            try:
                for attempt in range(1, CLIENT_TITLE_RENAME_MAX_ATTEMPTS + 1):
                    if not self._get_rename_client_titles_enabled():
                        self._log_client_title_rename(
                            f"Stopped title rename for pid={target_pid} because the setting was disabled.",
                            debug=True,
                        )
                        return

                    hwnd = self._find_main_window_for_pid(target_pid, include_hidden=True, use_cache=False)
                    if not hwnd:
                        if attempt in {1, CLIENT_TITLE_RENAME_MAX_ATTEMPTS}:
                            self._log_client_title_rename(
                                f"Waiting for Roblox window for pid={target_pid} (attempt {attempt}).",
                                debug=True,
                            )
                        stable_attempts = 0
                        time.sleep(CLIENT_TITLE_RENAME_DELAY_SECONDS)
                        continue

                    saw_window = True
                    try:
                        current_title = str(win32gui.GetWindowText(hwnd) or "").strip()
                    except WINDOWS_API_ERROR_TYPES:
                        current_title = ""
                    last_title = current_title

                    if current_title != target_name:
                        try:
                            win32gui.SetWindowText(hwnd, target_name)
                            self._invalidate_tracked_process_caches()
                            stable_attempts = 1
                            self._log_client_title_rename(
                                (
                                    f"Set title for pid={target_pid} hwnd={int(hwnd)} "
                                    f"from {current_title or '(blank)'} to {target_name}."
                                ),
                                debug=True,
                            )
                        except WINDOWS_API_ERROR_TYPES as exc:
                            stable_attempts = 0
                            self._log_client_title_rename(
                                f"SetWindowText failed for pid={target_pid}: {exc}.",
                                debug=True,
                            )
                    else:
                        stable_attempts += 1

                    if stable_attempts >= CLIENT_TITLE_RENAME_STABLE_ATTEMPTS:
                        self._log_client_title_rename(
                            f"Title rename confirmed for pid={target_pid} as {target_name}.",
                            debug=True,
                        )
                        return

                    time.sleep(CLIENT_TITLE_RENAME_DELAY_SECONDS)

                if saw_window:
                    self._log_client_title_rename(
                        (
                            f"Title rename did not stabilize for pid={target_pid}; "
                            f"last observed title was {last_title or '(blank)'}."
                        ),
                        debug=True,
                    )
                else:
                    self._log_client_title_rename(
                        f"No Roblox window was found for pid={target_pid} before title rename timed out.",
                        debug=True,
                    )
            finally:
                with self._client_title_rename_lock:
                    self._client_title_rename_active_pids.discard(target_pid)

        threading.Thread(
            target=_rename_worker,
            args=(normalized_pid, normalized_username),
            daemon=True,
            name=f"rename-client-title-{normalized_pid}",
        ).start()

    def _find_main_window_for_pid(
        self,
        pid_value: Any,
        include_hidden: bool = False,
        use_cache: bool = True,
    ) -> Optional[int]:
        if platform.system() != "Windows":
            return None

        try:
            normalized_pid = int(pid_value)
        except (TypeError, ValueError):
            return None

        snapshot = self._get_tracked_process_window_snapshot(use_cache=use_cache, include_windows=True)
        for record in snapshot.window_records:
            if record.pid != normalized_pid:
                continue
            if include_hidden or record.is_visible:
                return record.hwnd
        return None

    def launch_game(
        self,
        usernames=None,
        place_id_override=None,
        private_server_override=None,
        manual_server_job_id_override=None,
        version_path_override=None,
        launch_mode_override=None,
        join_input_override=None,
        skip_confirm=False,
        on_done_callback=None,
        run_async=True,
        show_feedback=True,
        update_recent_history=True,
        preserve_rejoin_attempts=False,
    ):
        """Launch Roblox for the selected account(s) or explicit usernames."""
        if usernames is None:
            if self.settings.get("enable_multi_select", False):
                usernames = self.get_selected_usernames()
                if not usernames:
                    return False
            else:
                username = self.get_selected_username()
                if not username:
                    return False
                usernames = [username]

        return self._launch_game_for_usernames(
            usernames,
            skip_confirm=skip_confirm,
            on_done_callback=on_done_callback,
            place_id_override=place_id_override,
            private_server_override=private_server_override,
            manual_server_job_id_override=manual_server_job_id_override,
            version_path_override=version_path_override,
            launch_mode_override=launch_mode_override,
            join_input_override=join_input_override,
            run_async=run_async,
            show_feedback=show_feedback,
            update_recent_history=update_recent_history,
            preserve_rejoin_attempts=preserve_rejoin_attempts,
        )

    def launch_group_game(self):
        group = self._get_active_group()
        if not group:
            return

        usernames = self.manager.get_accounts_in_group(group)
        if not usernames:
            messagebox.showwarning("Empty Group", f"No accounts found in group '{group}'.")
            return

        self._launch_game_for_usernames(usernames, confirm_group=group)

    def launch_auto_rejoin_session(self, session: Any, attempt_number: int = 0) -> bool:
        username = str(getattr(session, "username", "") or "").strip()
        if not username:
            return False

        rejoin_launch_behavior = self._normalize_auto_rejoin_launch_behavior(
            getattr(session, "rejoin_launch_behavior", self._get_auto_rejoin_launch_behavior())
        )
        place_id = str(getattr(session, "place_id", "") or "").strip()
        if not place_id:
            return False

        private_server = ""
        server_job_id = ""
        if rejoin_launch_behavior == "rejoin_same_server":
            private_server = str(getattr(session, "private_server_link", "") or "").strip()
        if rejoin_launch_behavior == "rejoin_same_server" and not private_server:
            server_job_id = str(getattr(session, "server_job_id", "") or "").strip()

        return bool(
            self.launch_game(
                usernames=[username],
                place_id_override=place_id,
                private_server_override=private_server,
                manual_server_job_id_override=server_job_id,
                version_path_override=getattr(session, "version_path", None),
                launch_mode_override="place_id",
                join_input_override=place_id,
                skip_confirm=True,
                run_async=False,
                show_feedback=False,
                update_recent_history=False,
                preserve_rejoin_attempts=True,
            )
        )

    def _launch_game_for_usernames(
        self,
        usernames,
        confirm_group=None,
        skip_confirm=False,
        on_done_callback=None,
        place_id_override=None,
        private_server_override=None,
        manual_server_job_id_override=None,
        version_path_override=None,
        launch_mode_override=None,
        join_input_override=None,
        run_async=True,
        show_feedback=True,
        update_recent_history=True,
        preserve_rejoin_attempts=False,
    ):
        target_value = (
            str(place_id_override).strip()
            if place_id_override is not None
            else self.place_entry.get().strip()
        )
        launch_mode = self._normalize_launch_input_mode(
            launch_mode_override
            if launch_mode_override is not None
            else getattr(self, "launch_input_mode", "place_id")
        )
        place_target_mode = self._normalize_place_target_mode(getattr(self, "place_join_target_mode", "private_server"))
        game_id = target_value
        place_target_value = (
            str(private_server_override).strip()
            if private_server_override is not None
            else (self.private_server_entry.get().strip() if launch_mode == "place_id" else "")
        )
        if private_server_override is not None:
            private_server = str(private_server_override).strip()
        else:
            private_server = place_target_value if (launch_mode == "place_id" and place_target_mode == "private_server") else ""
        if private_server:
            private_server = self.manager.normalize_private_server(private_server)
        manual_server_job_id = (
            str(manual_server_job_id_override).strip()
            if manual_server_job_id_override is not None
            else (place_target_value if (launch_mode == "place_id" and place_target_mode == "job_id") else "")
        )
        if launch_mode == "place_id" and place_target_mode == "subplaces" and place_target_value:
            if not str(place_target_value).isdigit():
                messagebox.showwarning("Invalid SubPlace ID", "SubPlace ID must be numeric.")
                return
            game_id = place_target_value

        if version_path_override is not None:
            version_path = version_path_override or None
        else:
            selected_version_label = self.version_var.get()
            version_path = self.version_options.get(selected_version_label)

        if not target_value:
            required_label = "Join User" if launch_mode == "join_user" else "Place ID"
            messagebox.showwarning("Missing Information", f"Please enter a {required_label}.")
            return False

        if place_id_override is None:
            self.settings[self._get_launch_input_setting_key(launch_mode)] = target_value
            self.save_settings()

        if launch_mode == "join_user" and not str(game_id).isdigit():
            resolved_user_id = RobloxAPI.get_user_id_from_username(game_id)
            if not resolved_user_id:
                messagebox.showwarning("User Not Found", f"Could not find Roblox user '{game_id}'.")
                return False
            game_id = resolved_user_id

        if (not skip_confirm) and self.settings.get("confirm_before_launch", True) and len(usernames) > 1:
            prompt = (
                f"Are you sure you want to launch {len(usernames)} accounts in group '{confirm_group}'?"
                if confirm_group else
                f"Are you sure you want to launch {len(usernames)} accounts?"
            )
            confirm = messagebox.askyesno("Confirm Launch", prompt)
            if not confirm:
                return False

        debug_enabled = self.settings.get("enable_debug_logging", False)
        launch_delay = self._get_multi_launch_delay()
        randomize_server_jobs = self.settings.get("randomize_server_job_ids", False)
        prefer_small_servers = self.settings.get("prefer_small_public_servers", False)
        pick_server_per_account = self.settings.get("pick_server_per_account", False)
        preferred_server_region = self._normalize_server_region_preference(
            self.settings.get("preferred_server_region", "")
        )

        def run_launch_batch(
            selected_usernames: list[str],
            pid: str,
            psid: str,
            manual_job_id: str,
            ver: Any,
            debug_flag: bool,
            delay_seconds: float,
            randomize_jobs: bool,
            prefer_small: bool,
            pick_per_account: bool,
            preferred_region: str,
            active_launch_mode: str,
            join_input_text: Any,
        ) -> dict[str, Any]:
            success_count = 0
            recent_join_username = ""
            last_effective_private_server = psid
            public_server_job_pool: list[str] = []
            public_server_pool_loaded = False
            if active_launch_mode == "join_user":
                entered = str(join_input_text or "").strip()
                if entered and not entered.isdigit():
                    recent_join_username = entered
                else:
                    recent_join_username = RobloxAPI.get_username_from_user_id(pid) or ""
            public_server_selection_enabled = bool(randomize_jobs or prefer_small or pick_per_account or preferred_region)
            if active_launch_mode == "join_user":
                if psid:
                    print("[INFO] Private server ID is ignored in Join User mode.")
                if public_server_selection_enabled:
                    print("[INFO] Public server selection settings are ignored in Join User mode.")
            if randomize_jobs and manual_job_id:
                print("[INFO] Random Job ID setting ignored because a manual Job ID is set.")
            if prefer_small and manual_job_id:
                print("[INFO] Lowest-population server setting ignored because a manual Job ID is set.")
            if pick_per_account and manual_job_id:
                print("[INFO] Per-account server selection setting ignored because a manual Job ID is set.")
            if preferred_region and manual_job_id:
                print("[INFO] Preferred server region setting ignored because a manual Job ID is set.")
            if prefer_small and randomize_jobs and not psid and not manual_job_id and active_launch_mode != "join_user":
                print("[INFO] Lowest-population server setting is enabled; random server selection will be ignored.")

            def take_public_server_job_id() -> str:
                nonlocal public_server_job_pool, public_server_pool_loaded
                if public_server_job_pool:
                    return public_server_job_pool.pop(0)

                if public_server_pool_loaded:
                    return ""

                region_probe_cookie = ""
                if selected_usernames:
                    region_probe_cookie = self.manager.get_account_cookie(selected_usernames[0]) or ""
                public_server_job_pool = RobloxAPI.get_public_server_job_candidates(
                    pid,
                    max_pages=1,
                    prefer_small=bool(prefer_small),
                    enable_debug=debug_flag,
                    preferred_region=preferred_region,
                    roblosecurity_cookie=region_probe_cookie,
                ) or []
                public_server_pool_loaded = True
                if public_server_job_pool:
                    mode_label = (
                        "preferred-region"
                        if preferred_region else
                        "low-population" if prefer_small else
                        "randomized" if randomize_jobs else
                        "per-account"
                    )
                    print(f"[INFO] Loaded {len(public_server_job_pool)} {mode_label} public server candidates for this launch batch.")
                    return public_server_job_pool.pop(0)
                if preferred_region:
                    print("[INFO] Preferred-region public server unavailable; launching without job ID override.")
                elif prefer_small:
                    print("[INFO] Low-population public server unavailable; launching without job ID override.")
                elif pick_per_account:
                    print("[INFO] Per-account public server selection unavailable; launching without job ID override.")
                else:
                    print("[INFO] Random public server unavailable; launching without randomized job ID.")
                return ""

            for idx, uname in enumerate(selected_usernames):
                try:
                    account_private_server = psid
                    if active_launch_mode != "join_user" and not manual_job_id:
                        mapped_vip_server = self.manager.get_account_vip_server(uname)
                        if mapped_vip_server:
                            account_private_server = mapped_vip_server
                            print(f"[INFO] Using mapped VIP server for {uname}.")

                    server_job_id = ""
                    effective_server_job_id = ""
                    if active_launch_mode == "join_user":
                        server_job_id = ""
                    elif manual_job_id:
                        server_job_id = str(manual_job_id).strip()
                    elif prefer_small and not account_private_server:
                        server_job_id = take_public_server_job_id()
                    elif randomize_jobs and not account_private_server:
                        server_job_id = take_public_server_job_id()
                    elif pick_per_account and not account_private_server:
                        server_job_id = take_public_server_job_id()
                    elif preferred_region and not account_private_server:
                        server_job_id = take_public_server_job_id()

                    if randomize_jobs and account_private_server:
                        print(f"[INFO] Random Job ID setting ignored for {uname} because a private server link code is set.")
                    if prefer_small and account_private_server:
                        print(f"[INFO] Lowest-population server setting ignored for {uname} because a private server link code is set.")
                    if pick_per_account and account_private_server:
                        print(f"[INFO] Per-account server selection setting ignored for {uname} because a private server link code is set.")
                    if preferred_region and account_private_server:
                        print(f"[INFO] Preferred server region setting ignored for {uname} because a private server link code is set.")

                    before_pids = self._get_running_tracked_roblox_pid_set(use_cache=False)
                    effective_auto_rejoin = self._get_effective_auto_rejoin_enabled(uname)
                    launched = self.manager.launch_roblox(
                        uname,
                        pid,
                        account_private_server,
                        ver,
                        enable_debug=debug_flag,
                        server_job_id=server_job_id,
                        launch_mode=active_launch_mode,
                        auto_rejoin=effective_auto_rejoin,
                        rejoin_delay=self._get_auto_rejoin_delay_seconds(),
                        max_rejoin_attempts=self._get_auto_rejoin_max_attempts(),
                        rejoin_launch_behavior=self._get_auto_rejoin_launch_behavior(),
                        preserve_rejoin_attempts=preserve_rejoin_attempts,
                    )
                    last_effective_private_server = account_private_server
                    effective_server_job_id = server_job_id
                    if (
                        active_launch_mode != "join_user"
                        and (not launched)
                        and server_job_id
                        and public_server_selection_enabled
                        and not account_private_server
                        and not manual_job_id
                    ):
                        print("[INFO] Server job ID launch failed; retrying with default launch.")
                        launched = self.manager.launch_roblox(
                            uname,
                            pid,
                            account_private_server,
                            ver,
                            enable_debug=debug_flag,
                            server_job_id="",
                            launch_mode=active_launch_mode,
                            auto_rejoin=effective_auto_rejoin,
                            rejoin_delay=self._get_auto_rejoin_delay_seconds(),
                            max_rejoin_attempts=self._get_auto_rejoin_max_attempts(),
                            rejoin_launch_behavior=self._get_auto_rejoin_launch_behavior(),
                            preserve_rejoin_attempts=preserve_rejoin_attempts,
                        )
                        if launched:
                            effective_server_job_id = ""
                    if launched:
                        success_count += 1
                    after_pids = before_pids
                    if launched:
                        after_pids = self._wait_for_tracked_roblox_pid_change(before_pids)
                    self._assign_new_pids_to_account(
                        uname,
                        before_pids,
                        after_pids,
                        launch_context={
                            "mode": "join_user" if active_launch_mode == "join_user" else "game",
                            "game_id": pid,
                            "private_server_id": account_private_server,
                            "server_job_id": effective_server_job_id,
                            "version_path": ver,
                        },
                    )
                except Exception as e:
                    print(f"Failed to launch game for {uname}: {e}")
                if delay_seconds > 0 and idx < len(selected_usernames) - 1:
                    time.sleep(delay_seconds)

            game_name = ""
            if success_count > 0 and update_recent_history and active_launch_mode != "join_user":
                game_name = RobloxAPI.get_game_name(pid) or ""

            return {
                "success_count": success_count,
                "selected_usernames": list(selected_usernames),
                "active_launch_mode": active_launch_mode,
                "recent_private_server": last_effective_private_server if len(selected_usernames) == 1 else psid,
                "recent_join_username": recent_join_username,
                "pid": pid,
                "game_name": game_name,
            }

        def handle_launch_result(result: dict[str, Any]) -> bool:
            success_count = int(result.get("success_count", 0) or 0)
            selected_usernames = list(result.get("selected_usernames") or [])
            active_launch_mode = str(result.get("active_launch_mode") or launch_mode).strip()
            if success_count > 0:
                if update_recent_history:
                    if active_launch_mode != "join_user":
                        recent_private_server = str(result.get("recent_private_server") or "").strip()
                        gname = str(result.get("game_name") or "").strip()
                        if gname:
                            self.add_game_to_list(game_id, gname, recent_private_server)
                        else:
                            self.add_game_to_list(game_id, f"Place {game_id}", recent_private_server)
                    else:
                        self.add_recent_user_to_list(game_id, str(result.get("recent_join_username") or "").strip())

                if show_feedback:
                    if len(selected_usernames) == 1:
                        self.show_success_message("Roblox is launching! Check your desktop.")
                    else:
                        self.show_success_message(
                            f"Roblox is launching for {success_count} account(s)! Check your desktop."
                        )

                self._notify_roblox_windows_changed(success_count)

                if on_done_callback is not None:
                    try:
                        on_done_callback(success_count)
                    except Exception:
                        pass
            else:
                if show_feedback:
                    messagebox.showerror("Error", "Failed to launch Roblox.")
                elif on_done_callback is not None:
                    try:
                        on_done_callback(0)
                    except Exception:
                        pass

            return success_count > 0

        worker_args = (
            list(usernames),
            game_id,
            private_server,
            manual_server_job_id,
            version_path,
            debug_enabled,
            launch_delay,
            randomize_server_jobs,
            prefer_small_servers,
            pick_server_per_account,
            preferred_server_region,
            launch_mode,
            join_input_override if join_input_override is not None else target_value,
        )

        if run_async:
            def threaded_worker() -> None:
                result = run_launch_batch(*worker_args)
                self.root.after(0, lambda: handle_launch_result(result))

            threading.Thread(target=threaded_worker, daemon=True).start()
            return True

        result = run_launch_batch(*worker_args)
        if (
            show_feedback
            or update_recent_history
            or on_done_callback is not None
            or self._get_rename_client_titles_enabled()
            or self.settings.get("roblox_headless_mode_enabled", False)
            or self.settings.get("anti_afk_enabled", False)
            or self.settings.get("keep_roblox_clients_arranged", False)
        ):
            if threading.current_thread() is threading.main_thread():
                return handle_launch_result(result)
            success_holder = {"ok": bool(result.get("success_count", 0))}
            done_event = threading.Event()

            def apply_result() -> None:
                try:
                    success_holder["ok"] = handle_launch_result(result)
                finally:
                    done_event.set()

            self.root.after(0, apply_result)
            done_event.wait(timeout=10)
            return bool(success_holder["ok"])
        return bool(result.get("success_count", 0))

    def enable_multi_roblox(self):
        """Enable Multi Roblox + 773 fix"""

        import subprocess
        import win32event
        import win32api
        

        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RobloxPlayerBeta.exe'], 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=4,
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
                                 timeout=4,
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

    def _get_multi_select_keybind(self) -> str:
        key = normalize_multi_select_keybind(
            self.settings.get("multi_select_keybind", MULTI_SELECT_KEYBIND_DEFAULT)
        )
        self.settings["multi_select_keybind"] = key
        return key

    def _get_multi_select_label_text(self) -> str:
        return f"Multi Select ({format_multi_select_keybind(self._get_multi_select_keybind())} + Click)"

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
            text="Manage FRAM preferences, Roblox behavior, automation, and tools.",
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

        discord_image = self._load_discord_button_image(size=32, allow_network=False)
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
        if discord_image is None:
            def load_discord_image():
                fetched_image = self._load_discord_button_image(size=32, allow_network=True)
                if fetched_image is None:
                    return

                def apply_discord_image():
                    try:
                        if not settings_window.winfo_exists() or not discord_click_target.winfo_exists():
                            return
                    except Exception:
                        return
                    self._settings_discord_icon = fetched_image
                    discord_click_target.configure(image=fetched_image, text="")
                    discord_click_target.image = fetched_image

                try:
                    self.root.after(0, apply_discord_image)
                except Exception:
                    pass

            threading.Thread(target=load_discord_image, daemon=True, name="load-discord-icon").start()
        
        topmost_var = tk.BooleanVar(value=self.settings.get("enable_topmost", False))
        multi_roblox_var = tk.BooleanVar(value=self.settings.get("enable_multi_roblox", False))
        confirm_launch_var = tk.BooleanVar(value=self.settings.get("confirm_before_launch", False))
        randomize_job_id_var = tk.BooleanVar(value=self.settings.get("randomize_server_job_ids", False))
        prefer_small_servers_var = tk.BooleanVar(value=self.settings.get("prefer_small_public_servers", False))
        pick_server_per_account_var = tk.BooleanVar(value=self.settings.get("pick_server_per_account", False))
        preferred_server_region_var = tk.StringVar(
            value=self._normalize_server_region_preference(self.settings.get("preferred_server_region", ""))
        )
        multi_select_var = tk.BooleanVar(value=self.settings.get("enable_multi_select", False))
        multi_select_text_var = tk.StringVar(value=self._get_multi_select_label_text())
        active_client_indicator_var = tk.BooleanVar(value=self.settings.get("show_active_client_indicator", True))
        rename_client_titles_var = tk.BooleanVar(value=self._get_rename_client_titles_enabled())
        debug_var = tk.BooleanVar(value=self.settings.get("enable_debug_logging", False))
        hide_sensitive_var = tk.BooleanVar(value=self.settings.get("hide_sensitive_info", False))
        bug_prompt_var = tk.BooleanVar(value=self.settings.get("bug_issue_prompt_enabled", True))
        disable_success_var = tk.BooleanVar(value=self.settings.get("disable_success_popups", False))
        auto_update_var = tk.BooleanVar(value=self.settings.get("auto_update_enabled", True))
        anti_afk_enabled_var = tk.BooleanVar(value=bool(self.settings.get("anti_afk_enabled", False)))
        anti_afk_interval_var = tk.IntVar(value=self._get_anti_afk_interval_minutes())
        anti_afk_key_var = tk.StringVar(value=self._get_anti_afk_key_name())
        anti_afk_key_code_state = {"value": self._get_anti_afk_key_code()}
        anti_afk_key_button_text_var = tk.StringVar(value=anti_afk_key_var.get())
        anti_afk_show_next_label_var = tk.BooleanVar(
            value=bool(self.settings.get("anti_afk_show_next_label", False))
        )
        theme_var = tk.StringVar(value=self.settings.get("selected_theme", self.theme_name))
        browser_preference_var = tk.StringVar(value=self._get_preferred_browser())
        custom_launcher_var = tk.BooleanVar(value=self.settings.get("enable_custom_launcher", False))
        custom_launcher_path_var = tk.StringVar(value=self.settings.get("custom_launcher_path", ""))
        custom_launcher_player_var = tk.BooleanVar(value=self.settings.get("custom_launcher_requires_player", False))
        auto_arrange_scope_var = tk.StringVar(value=self.settings.get("auto_arrange_scope", "both"))
        auto_arrange_dimension_mode_var = tk.StringVar(
            value=self.settings.get("auto_arrange_dimension_mode", "auto")
        )
        keep_clients_arranged_var = tk.BooleanVar(
            value=self.settings.get("keep_roblox_clients_arranged", False)
        )
        roblox_headless_mode_var = tk.BooleanVar(
            value=self.settings.get("roblox_headless_mode_enabled", False)
        )
        roblox_headless_idle_priority_var = tk.BooleanVar(
            value=self.settings.get("roblox_headless_idle_priority", True)
        )
        roblox_headless_trim_memory_var = tk.BooleanVar(
            value=self.settings.get("roblox_headless_trim_memory", True)
        )
        auto_arrange_target_width_var = tk.IntVar(
            value=int(self.settings.get("auto_arrange_target_width", 800) or 800)
        )
        auto_arrange_target_height_var = tk.IntVar(
            value=int(self.settings.get("auto_arrange_target_height", 600) or 600)
        )
        custom_roblox_player_path_var = tk.StringVar(value=self.settings.get("custom_roblox_player_path", ""))
        
        def auto_save_setting(setting_name, var):
            def save():
                self.settings[setting_name] = var.get()
                if setting_name == "enable_topmost":
                    self.root.attributes("-topmost", var.get())
                    settings_window.attributes("-topmost", var.get())
                    self.console_window.update_topmost(var.get())
                self.save_settings()
            return save

        def on_keep_clients_arranged_toggle():
            self._set_keep_clients_arranged_enabled(
                keep_clients_arranged_var.get(),
                save=True,
                arrange_now=keep_clients_arranged_var.get(),
            )

        def on_roblox_headless_toggle():
            if platform.system() != "Windows":
                roblox_headless_mode_var.set(False)
                self.settings["roblox_headless_mode_enabled"] = False
                self.save_settings()
                messagebox.showerror("Headless Mode", "This feature is only available on Windows.")
                return
            self._set_roblox_headless_mode_enabled(
                roblox_headless_mode_var.get(),
                save=True,
                run_now=roblox_headless_mode_var.get(),
                restore_when_disabled=True,
            )

        def on_roblox_headless_option_change():
            self.settings["roblox_headless_idle_priority"] = bool(roblox_headless_idle_priority_var.get())
            self.settings["roblox_headless_trim_memory"] = bool(roblox_headless_trim_memory_var.get())
            self.save_settings()
            self._log_roblox_headless(
                (
                    "Options updated: "
                    f"idle_priority={self.settings['roblox_headless_idle_priority']}, "
                    f"trim_memory={self.settings['roblox_headless_trim_memory']}."
                )
            )
            if self.settings.get("roblox_headless_mode_enabled", False):
                self._schedule_roblox_headless_pass(delay_ms=50)
        
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
                selections = self.account_list.curselection()
                if len(selections) > 1:
                    active_index = self.account_list.index(tk.ACTIVE)
                    target_index = active_index if active_index in selections else selections[0]
                    self.account_list.selection_clear(0, tk.END)
                    self.account_list.selection_set(target_index)
                    self.account_list.activate(target_index)
            self.save_settings()

        def refresh_multi_select_keybind_text() -> None:
            multi_select_text_var.set(self._get_multi_select_label_text())
            _refresh_settings_search_index()

        multi_select_keybind_capture_active = {"value": False}
        multi_select_keybind_menu = tk.Menu(settings_window, tearoff=False)

        def begin_multi_select_keybind_capture() -> None:
            multi_select_keybind_capture_active["value"] = True
            try:
                settings_window.focus_force()
            except tk.TclError:
                pass

        def capture_multi_select_keybind(event: tk.Event) -> Optional[str]:
            if not multi_select_keybind_capture_active["value"]:
                return None
            key = normalize_multi_select_event_key(event)
            if key is None:
                return "break"
            self.settings["multi_select_keybind"] = key
            self._pressed_multi_select_keys.clear()
            self.save_settings()
            multi_select_keybind_capture_active["value"] = False
            refresh_multi_select_keybind_text()
            return "break"

        settings_window.bind("<KeyPress>", capture_multi_select_keybind, add="+")

        def show_multi_select_keybind_menu(event: tk.Event) -> str:
            multi_select_keybind_menu.delete(0, tk.END)
            multi_select_keybind_menu.add_command(
                label="Change Bind...",
                command=begin_multi_select_keybind_capture,
            )
            try:
                multi_select_keybind_menu.tk_popup(event.x_root, event.y_root)
            finally:
                multi_select_keybind_menu.grab_release()
            return "break"

        def on_active_client_indicator_toggle():
            self.settings["show_active_client_indicator"] = active_client_indicator_var.get()
            self.save_settings()
            self._invalidate_active_client_indicator_cache()
            self.refresh_accounts(selected_usernames=self._get_selected_usernames_silent())

        def on_rename_client_titles_toggle() -> None:
            enabled = bool(rename_client_titles_var.get())
            self.settings["rename_client_titles_to_account_name"] = enabled
            self.save_settings()
            self._log_client_title_rename(
                f"Rename Title to Account Name setting {'enabled' if enabled else 'disabled'}.",
                debug=True,
            )
            if not enabled:
                return
            self._rename_tracked_roblox_client_window_titles()

        tab_var = tk.StringVar(value="general")
        tab_buttons = {}
        tabs = {}
        tab_content_frames = {}
        settings_cards = []
        settings_muted_labels = [settings_intro_label]

        search_row = ttk.Frame(main_frame, style="Dark.TFrame")
        search_row.pack(fill="x", pady=(0, 8))
        search_row.columnconfigure(1, weight=1)

        ttk.Label(
            search_row,
            text="Search",
            style="Dark.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(search_row, textvariable=search_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=1, sticky="ew")

        tab_bar = tk.Frame(main_frame, bg=self.BG_DARK)
        tab_bar.pack(fill="x", pady=(0, 8))

        search_empty_label = ttk.Label(
            main_frame,
            text="No settings matched your search.",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        )
        settings_muted_labels.append(search_empty_label)

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
            tab_content_frames[str(frame)] = tab_name
            return frame

        create_tab_button("General", "general")
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

        def create_settings_card(parent, title, subtitle="", header_action_builder=None):
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
            header_frames = [header]
            if header_action_builder is None:
                title_parent = header
            else:
                header.columnconfigure(0, weight=1)
                title_parent = tk.Frame(header, bg=self.BG_MID)
                title_parent.grid(row=0, column=0, sticky="ew")
                header_frames.append(title_parent)
                header_action_frame = tk.Frame(header, bg=self.BG_MID)
                header_action_frame.grid(row=0, column=1, sticky="e", padx=(10, 0))
                header_frames.append(header_action_frame)
                header_action_builder(header_action_frame)
            ttk.Label(
                title_parent,
                text=title,
                style="Dark.TLabel",
                font=("Segoe UI", 11, "bold")
            ).pack(anchor="w")
            if subtitle:
                subtitle_label = ttk.Label(
                    title_parent,
                    text=subtitle,
                    style="Dark.TLabel",
                    font=("Segoe UI", 9),
                    foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888"
                )
                subtitle_label.pack(anchor="w", pady=(2, 0))
                settings_muted_labels.append(subtitle_label)
            body = ttk.Frame(outer, style="Dark.TFrame")
            body.pack(fill="x", padx=10, pady=(8, 10))
            settings_cards.append(
                {
                    "outer": outer,
                    "header": header,
                    "header_frames": header_frames,
                    "body": body,
                    "parent": parent,
                    "tab_name": tab_content_frames.get(str(parent), ""),
                    "title": title,
                    "subtitle": subtitle,
                    "search_text": "",
                }
            )
            return body

        def _collect_settings_widget_text(widget):
            parts = []

            try:
                text_value = widget.cget("text")
            except Exception:
                text_value = ""
            if text_value:
                parts.append(str(text_value))

            try:
                values = widget.cget("values")
            except Exception:
                values = ()
            if values:
                try:
                    parts.extend(str(value) for value in values)
                except Exception:
                    parts.append(str(values))

            for child in widget.winfo_children():
                child_text = _collect_settings_widget_text(child)
                if child_text:
                    parts.append(child_text)

            return " ".join(parts)

        def _refresh_settings_search_index():
            for card in settings_cards:
                search_parts = [
                    str(card.get("title", "") or ""),
                    str(card.get("subtitle", "") or ""),
                    _collect_settings_widget_text(card.get("body")),
                ]
                card["search_text"] = " ".join(part for part in search_parts if part).lower()

        def _refresh_settings_card_visibility(*_):
            query = str(search_var.get() or "").strip().lower()
            visible_counts = {tab_name: 0 for tab_name in tab_buttons.keys()}

            for card in settings_cards:
                outer = card.get("outer")
                if outer and outer.winfo_exists():
                    outer.pack_forget()

            for card in settings_cards:
                card_query_text = str(card.get("search_text", "") or "")
                visible = not query or query in card_query_text
                card["visible"] = visible
                if not visible:
                    continue

                outer = card.get("outer")
                if outer and outer.winfo_exists():
                    outer.pack(fill="x", pady=(0, 10))
                tab_name = str(card.get("tab_name", "") or "")
                if tab_name:
                    visible_counts[tab_name] = visible_counts.get(tab_name, 0) + 1

            matching_tabs = [tab_name for tab_name in tab_buttons.keys() if visible_counts.get(tab_name, 0) > 0]
            if query and matching_tabs and tab_var.get() not in matching_tabs:
                set_active_tab(matching_tabs[0])

            if query and not matching_tabs:
                if not search_empty_label.winfo_manager():
                    search_empty_label.pack(fill="x", pady=(0, 8), before=content_frame)
            elif search_empty_label.winfo_manager():
                search_empty_label.pack_forget()

            try:
                settings_window.update_idletasks()
            except Exception:
                pass

            for data in tab_scroll_state.values():
                canvas = data.get("canvas")
                if canvas and canvas.winfo_exists():
                    try:
                        canvas.configure(scrollregion=canvas.bbox("all"))
                    except Exception:
                        pass

            active_canvas = tab_scroll_state.get(tab_var.get(), {}).get("canvas")
            if active_canvas and active_canvas.winfo_exists():
                try:
                    active_canvas.yview_moveto(0)
                except Exception:
                    pass

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
                for header_frame in list(card.get("header_frames", []) or []):
                    if header_frame and header_frame.winfo_exists():
                        header_frame.configure(bg=self.BG_MID)

            for label in settings_muted_labels:
                if label and label.winfo_exists():
                    label.configure(foreground=self.FG_MUTED)

            for data in tab_scroll_state.values():
                canvas = data.get("canvas")
                if canvas and canvas.winfo_exists():
                    canvas.configure(bg=self.BG_DARK)

        window_behavior_card = create_settings_card(general_tab, "FRAM Behavior", "FRAM and account list interaction")

        ttk.Checkbutton(
            window_behavior_card,
            text="Enable Topmost",
            variable=topmost_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_topmost", topmost_var)
        ).pack(anchor="w", pady=2)

        multi_select_row = ttk.Frame(window_behavior_card, style="Dark.TFrame")
        multi_select_row.pack(fill="x", pady=2)
        multi_select_row.columnconfigure(0, weight=1)

        multi_select_checkbutton = ttk.Checkbutton(
            multi_select_row,
            textvariable=multi_select_text_var,
            variable=multi_select_var,
            style="Dark.TCheckbutton",
            command=on_multi_select_toggle
        )
        multi_select_checkbutton.grid(row=0, column=0, sticky="w")

        for widget in (multi_select_row, multi_select_checkbutton):
            widget.bind("<Button-3>", show_multi_select_keybind_menu)
        ThemedToolTip(multi_select_checkbutton, "Change Key by right clicking", self)

        ttk.Checkbutton(
            window_behavior_card,
            text="Active Accounts Indicator",
            variable=active_client_indicator_var,
            style="Dark.TCheckbutton",
            command=on_active_client_indicator_toggle
        ).pack(anchor="w", pady=2)

        notifications_card = create_settings_card(general_tab, "Notifications", "App feedback shown after actions complete")

        ttk.Checkbutton(
            notifications_card,
            text="Disable Success Popups",
            variable=disable_success_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("disable_success_popups", disable_success_var)
        ).pack(anchor="w", pady=2)

        appearance_card = create_settings_card(general_tab, "Appearance")

        theme_combo = ttk.Combobox(
            appearance_card,
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

        def install_additional_themes():
            try:
                imported = self.install_additional_themes_from_url(ADDITIONAL_THEMES_URL)
                theme_names = list(THEMES.keys())
                theme_combo.configure(values=theme_names)
                current_theme = str(theme_var.get() or "").strip()
                if current_theme and current_theme in theme_names:
                    theme_combo.set(current_theme)
                messagebox.showinfo("Themes", f"Installed {imported} theme(s).")
                if install_themes_button is not None and install_themes_button.winfo_exists():
                    install_themes_button.destroy()
            except Exception as exc:
                messagebox.showerror("Themes", f"Failed to install themes: {exc}")

        install_themes_button = None
        if not bool(self.custom_themes):
            install_themes_button = ttk.Button(
                appearance_card,
                text="Install Additional Themes",
                style="Dark.TButton",
                command=install_additional_themes,
            )
            install_themes_button.pack(fill="x", pady=(2, 0))

        launch_confirmation_card = create_settings_card(
            general_tab,
            "Launch Confirmation",
            "Review multi-account launches before they start",
        )

        ttk.Checkbutton(
            launch_confirmation_card,
            text="Confirm Before Launch",
            variable=confirm_launch_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("confirm_before_launch", confirm_launch_var)
        ).pack(anchor="w", pady=2)

        multi_client_card = create_settings_card(
            roblox_tab,
            "Multi-Client Launching",
            "Allow multiple Roblox clients to run at once",
        )

        ttk.Checkbutton(
            multi_client_card,
            text="Enable Multi Roblox",
            variable=multi_roblox_var,
            style="Dark.TCheckbutton",
            command=on_multi_roblox_toggle
        ).pack(anchor="w", pady=2)

        server_selection_card = create_settings_card(
            roblox_tab,
            "Server Selection",
            "Control how place launches choose public servers",
        )

        ttk.Checkbutton(
            server_selection_card,
            text="Prefer Random Servers",
            variable=randomize_job_id_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("randomize_server_job_ids", randomize_job_id_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            server_selection_card,
            text="Prefer Small Servers",
            variable=prefer_small_servers_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("prefer_small_public_servers", prefer_small_servers_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            server_selection_card,
            text="Server For Each Account",
            variable=pick_server_per_account_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("pick_server_per_account", pick_server_per_account_var)
        ).pack(anchor="w", pady=2)

        ttk.Label(
            server_selection_card,
            text="Preferred Region",
            style="Dark.TLabel",
        ).pack(anchor="w", pady=(8, 2))

        preferred_server_region_combo = ttk.Combobox(
            server_selection_card,
            values=[label for _value, label in SERVER_REGION_CHOICES],
            state="readonly",
            style="Dark.TCombobox",
        )
        preferred_server_region_combo.set(
            SERVER_REGION_LABEL_BY_VALUE.get(preferred_server_region_var.get(), SERVER_REGION_ANY_LABEL)
        )
        preferred_server_region_combo.pack(fill="x", pady=(0, 2))

        def on_preferred_server_region_change(_event: Optional[tk.Event] = None) -> None:
            selected_label = str(preferred_server_region_combo.get() or SERVER_REGION_ANY_LABEL).strip()
            selected_value = SERVER_REGION_VALUE_BY_LABEL.get(selected_label, "")
            preferred_server_region_var.set(selected_value)
            self.settings["preferred_server_region"] = selected_value
            self.save_settings()

        preferred_server_region_combo.bind("<<ComboboxSelected>>", on_preferred_server_region_change)

        launch_delay_card = create_settings_card(
            roblox_tab,
            "Launch Delay",
            "Delay between each account when launching multiple clients",
        )

        ttk.Label(
            launch_delay_card,
            text="Launch Delay (seconds)",
            style="Dark.TLabel",
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
            launch_delay_card,
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

        custom_player_card = create_settings_card(
            roblox_tab,
            "Roblox Executable",
            "Add a custom Roblox player to launch with",
        )

        ttk.Label(
            custom_player_card,
            text="Custom Roblox Player",
            style="Dark.TLabel",
        ).pack(anchor="w", pady=(0, 2))

        custom_player_frame = ttk.Frame(custom_player_card, style="Dark.TFrame")
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

        client_windows_card = create_settings_card(
            roblox_tab,
            "Rename Title to Account Name",
            "Sets each tracked Roblox client window title to the account that launched it",
        )

        ttk.Checkbutton(
            client_windows_card,
            text="Enable title renaming",
            variable=rename_client_titles_var,
            style="Dark.TCheckbutton",
            command=on_rename_client_titles_toggle
        ).pack(anchor="w", pady=2)

        headless_mode_card = create_settings_card(
            roblox_tab,
            "NoClient Mode",
            "Hide/minimize Roblox clients for complete performance",
        )

        headless_control_state = "normal" if platform.system() == "Windows" else "disabled"
        ttk.Checkbutton(
            headless_mode_card,
            text="Enable Headless Mode",
            variable=roblox_headless_mode_var,
            style="Dark.TCheckbutton",
            command=on_roblox_headless_toggle,
            state=headless_control_state,
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            headless_mode_card,
            text="Set Roblox Priority to Idle",
            variable=roblox_headless_idle_priority_var,
            style="Dark.TCheckbutton",
            command=on_roblox_headless_option_change,
            state=headless_control_state,
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            headless_mode_card,
            text="Trim Roblox Memory While Headless",
            variable=roblox_headless_trim_memory_var,
            style="Dark.TCheckbutton",
            command=on_roblox_headless_option_change,
            state=headless_control_state,
        ).pack(anchor="w", pady=2)

        headless_button_frame = ttk.Frame(headless_mode_card, style="Dark.TFrame")
        headless_button_frame.pack(fill="x", pady=(8, 0))
        headless_button_frame.columnconfigure(0, weight=1)
        headless_button_frame.columnconfigure(1, weight=1)

        ttk.Button(
            headless_button_frame,
            text="Apply Now",
            style="Dark.TButton",
            command=lambda: self.apply_roblox_headless_once(show_feedback=True),
            state=headless_control_state,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ttk.Button(
            headless_button_frame,
            text="Restore Windows",
            style="Dark.TButton",
            command=lambda: self.restore_roblox_headless_windows(show_feedback=True),
            state=headless_control_state,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        if platform.system() != "Windows":
            ttk.Label(
                headless_mode_card,
                text="Windows only.",
                style="Dark.TLabel",
                foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
            ).pack(anchor="w", pady=(6, 0))

        def open_global_settings_and_close_settings():
            """Open Roblox Settings and close settings window"""
            settings_window.destroy()
            self.open_global_settings_editor()

        roblox_settings_card = create_settings_card(
            roblox_tab,
            "Roblox Settings",
            "Open the Roblox client settings editor",
        )

        ttk.Button(
            roblox_settings_card,
            text="Open Roblox Settings",
            style="Dark.TButton",
            command=open_global_settings_and_close_settings
        ).pack(fill="x")

        roblox_auto_arrange_card = create_settings_card(
            roblox_tab,
            "Window Arrangement",
            "Keep Roblox clients organized across your monitors",
        )

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
                self._schedule_keep_clients_arranged_check(delay_ms=250, reset_signature=True)

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
            self._schedule_keep_clients_arranged_check(delay_ms=250, reset_signature=True)

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

        ttk.Checkbutton(
            roblox_auto_arrange_card,
            text="Keep Roblox Clients Arranged",
            variable=keep_clients_arranged_var,
            style="Dark.TCheckbutton",
            command=on_keep_clients_arranged_toggle
        ).pack(anchor="w", pady=(8, 0))

        automation_browser_card = create_settings_card(
            general_tab,
            "Browser Automation",
            "Choose which browser Roblox web launches should use",
        )

        browser_selector_frame = ttk.Frame(automation_browser_card, style="Dark.TFrame")
        browser_selector_frame.pack(fill="x", pady=(0, 4))
        browser_status_var = tk.StringVar()
        browser_download_state = {"thread": None}
        browser_download_button_holder = {"button": None}
        browser_status_label_holder = {"label": None}
        browser_display_names = BROWSER_DISPLAY_NAMES

        def get_browser_value_to_label() -> dict[str, str]:
            available_browsers = self._get_available_browsers()
            value_to_label = {}
            auto_browser_order = (
                ("chromium", "chrome", "firefox", "waterfox")
                if "chromium" in available_browsers
                else ("chrome", "firefox", "waterfox")
            )
            ordered_available = [
                browser_name
                for browser_name in auto_browser_order
                if browser_name in available_browsers
            ]
            if len(ordered_available) >= 2:
                auto_label = ", ".join(browser_display_names[browser_name] for browser_name in ordered_available)
                value_to_label["auto"] = f"Auto ({auto_label})"
            if "chrome" in available_browsers:
                value_to_label["chrome"] = "Chrome only"
            if "firefox" in available_browsers:
                value_to_label["firefox"] = "Firefox only"
            if "waterfox" in available_browsers:
                value_to_label["waterfox"] = "Waterfox only"
            if "chromium" in available_browsers:
                value_to_label["chromium"] = "Chromium only"
            return value_to_label

        def update_browser_status(message: str) -> None:
            browser_status_var.set(message)
            status_label = browser_status_label_holder.get("label")
            if status_label is None:
                return
            try:
                if message:
                    if not status_label.winfo_manager():
                        status_label.pack(fill="x", pady=(0, 4))
                else:
                    status_label.pack_forget()
            except tk.TclError:
                pass

        def refresh_browser_controls() -> None:
            for child in browser_selector_frame.winfo_children():
                child.destroy()

            available_browsers = self._get_available_browsers()
            browser_value_to_label = get_browser_value_to_label()
            browser_label_to_value = {label: value for value, label in browser_value_to_label.items()}
            current_browser_pref = browser_preference_var.get()
            if len(available_browsers) == 1:
                current_browser_pref = available_browsers[0]
            elif current_browser_pref not in browser_value_to_label:
                current_browser_pref = (
                    "auto"
                    if "auto" in browser_value_to_label
                    else available_browsers[0]
                    if available_browsers
                    else "auto"
                )

            browser_preference_var.set(current_browser_pref)
            self.settings["browser_preference"] = current_browser_pref
            self.save_settings()

            if browser_value_to_label:
                current_browser_label = browser_value_to_label.get(
                    current_browser_pref,
                    next(iter(browser_value_to_label.values())),
                )
                browser_combo = ttk.Combobox(
                    browser_selector_frame,
                    values=list(browser_value_to_label.values()),
                    state="readonly",
                    style="Dark.TCombobox",
                )
                browser_combo.set(current_browser_label)
                browser_combo.pack(fill="x", pady=(0, 4))

                def on_browser_preference_change(_event: Optional[tk.Event] = None) -> None:
                    selected_label = (browser_combo.get() or "").strip()
                    selected_value = browser_label_to_value.get(selected_label, current_browser_pref)
                    browser_preference_var.set(selected_value)
                    self.settings["browser_preference"] = selected_value
                    self.save_settings()

                browser_combo.bind("<<ComboboxSelected>>", on_browser_preference_change)
            else:
                ttk.Label(
                    browser_selector_frame,
                    text="No supported browser detected.",
                    style="Dark.TLabel",
                    wraplength=340,
                    justify="left",
                ).pack(fill="x", pady=(0, 4))

            installation = self._get_managed_chromium_installation()
            chromium_button = browser_download_button_holder.get("button")
            if chromium_button is not None:
                chromium_button.configure(
                    text="Update Chromium" if installation else "Download Chromium",
                    state="normal",
                )
            if installation and installation.version:
                update_browser_status(f"Chromium {installation.version} is installed.")
            elif installation:
                update_browser_status("Chromium is installed.")
            else:
                update_browser_status("")

        def set_browser_download_status(message: str) -> None:
            def apply_status() -> None:
                update_browser_status(message)

            try:
                self.root.after(0, apply_status)
            except tk.TclError:
                pass

        def begin_chromium_download() -> None:
            active_thread = browser_download_state.get("thread")
            if active_thread is not None and active_thread.is_alive():
                return

            if self._get_managed_chromium_installation() is not None:
                should_update = messagebox.askyesno(
                    "Download Chromium",
                    "Chromium is already installed.\n\nDo you want to replace it with the latest Stable build?",
                    parent=settings_window,
                )
                if not should_update:
                    return

            chromium_button = browser_download_button_holder.get("button")
            if chromium_button is not None:
                chromium_button.configure(state="disabled")
            update_browser_status("Starting Chromium download...")

            def worker() -> None:
                try:
                    installation = self._install_managed_chromium(set_browser_download_status)
                except RuntimeError as exc:
                    error_message = str(exc)

                    def apply_error() -> None:
                        try:
                            if not settings_window.winfo_exists():
                                return
                        except tk.TclError:
                            return
                        browser_download_state["thread"] = None
                        chromium_button = browser_download_button_holder.get("button")
                        if chromium_button is not None:
                            chromium_button.configure(state="normal")
                        update_browser_status(error_message)
                        messagebox.showerror("Download Chromium", error_message, parent=settings_window)

                    try:
                        self.root.after(0, apply_error)
                    except tk.TclError:
                        pass
                    return

                def apply_success() -> None:
                    self.settings["browser_preference"] = "chromium"
                    self.save_settings()
                    try:
                        if not settings_window.winfo_exists():
                            return
                    except tk.TclError:
                        return
                    browser_download_state["thread"] = None
                    browser_preference_var.set("chromium")
                    refresh_browser_controls()
                    version_text = f" {installation.version}" if installation.version else ""
                    messagebox.showinfo(
                        "Download Chromium",
                        f"Chromium{version_text} is ready to use.",
                        parent=settings_window,
                    )

                try:
                    self.root.after(0, apply_success)
                except tk.TclError:
                    pass

            thread = threading.Thread(target=worker, daemon=True, name="download-managed-chromium")
            browser_download_state["thread"] = thread
            thread.start()

        browser_download_button = ttk.Button(
            automation_browser_card,
            text="Download Chromium",
            style="Dark.TButton",
            command=begin_chromium_download,
        )
        browser_download_button.pack(fill="x", pady=(2, 4))
        browser_download_button_holder["button"] = browser_download_button

        browser_status_label = ttk.Label(
            automation_browser_card,
            textvariable=browser_status_var,
            style="Dark.TLabel",
            wraplength=340,
            justify="left",
        )
        browser_status_label_holder["label"] = browser_status_label

        refresh_browser_controls()

        updates_card = create_settings_card(general_tab, "App Updates", "Automatic update checks")

        ttk.Checkbutton(
            updates_card,
            text="Enable Auto Updates",
            variable=auto_update_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("auto_update_enabled", auto_update_var)
        ).pack(anchor="w", pady=2)

        anti_afk_supported = (
            platform.system() == "Windows"
            and win32gui is not None
            and win32process is not None
            and win32con is not None
        )
        anti_afk_key_capture_active = {"value": False}
        anti_afk_key_capture_release_block = {"value": False}
        anti_afk_key_button_holder = {"widget": None}

        def refresh_anti_afk_key_button_text() -> None:
            if anti_afk_key_capture_active["value"]:
                anti_afk_key_button_text_var.set("Listening...")
            else:
                anti_afk_key_button_text_var.set(anti_afk_key_var.get())
            _refresh_settings_search_index()

        def normalize_anti_afk_event_key(event: tk.Event) -> Optional[tuple[str, int]]:
            keysym = str(getattr(event, "keysym", "") or "").strip()
            if not keysym:
                return None
            key_name = self._normalize_anti_afk_key_name(keysym)
            try:
                key_code = int(getattr(event, "keycode", 0) or 0)
            except (TypeError, ValueError, tk.TclError):
                key_code = 0
            return key_name, self._normalize_anti_afk_key_code(key_code, key_name)

        def normalize_anti_afk_event_mouse(event: tk.Event) -> Optional[tuple[str, int]]:
            try:
                button_number = int(getattr(event, "num", 0) or 0)
            except (TypeError, ValueError, tk.TclError):
                return None
            button_map = {
                1: "M1",
                2: "M3",
                3: "M2",
            }
            key_name = button_map.get(button_number)
            if key_name is None:
                return None
            return key_name, self.ANTI_AFK_DEFAULT_KEY_CODE

        def finish_anti_afk_key_capture(key_name: str, key_code: int) -> str:
            normalized_key_name = self._normalize_anti_afk_key_name(key_name)
            normalized_key_code = self._normalize_anti_afk_key_code(key_code, normalized_key_name)
            anti_afk_key_capture_active["value"] = False
            anti_afk_key_var.set(normalized_key_name)
            anti_afk_key_code_state["value"] = normalized_key_code
            refresh_anti_afk_key_button_text()
            on_anti_afk_update()
            return "break"

        def begin_anti_afk_key_capture() -> None:
            if not anti_afk_supported:
                return
            anti_afk_key_capture_active["value"] = True
            refresh_anti_afk_key_button_text()
            try:
                settings_window.focus_force()
            except tk.TclError:
                pass

        def capture_anti_afk_key(event: tk.Event) -> Optional[str]:
            if not anti_afk_key_capture_active["value"]:
                return None
            captured_key = normalize_anti_afk_event_key(event)
            if captured_key is None:
                return "break"
            return finish_anti_afk_key_capture(*captured_key)

        def capture_anti_afk_mouse(event: tk.Event) -> Optional[str]:
            if not anti_afk_key_capture_active["value"]:
                return None
            captured_key = normalize_anti_afk_event_mouse(event)
            if captured_key is None:
                return "break"
            try:
                anti_afk_key_capture_release_block["value"] = event.widget is anti_afk_key_button_holder["widget"]
            except (NameError, AttributeError, tk.TclError):
                anti_afk_key_capture_release_block["value"] = False
            return finish_anti_afk_key_capture(*captured_key)

        settings_window.bind("<KeyPress>", capture_anti_afk_key, add="+")
        settings_window.bind("<ButtonPress>", capture_anti_afk_mouse, add="+")

        def block_anti_afk_capture_button_release(_event: tk.Event) -> Optional[str]:
            if not anti_afk_key_capture_release_block["value"]:
                return None
            anti_afk_key_capture_release_block["value"] = False
            return "break"

        def on_anti_afk_update(*_: object) -> None:
            if not anti_afk_supported:
                anti_afk_enabled_var.set(False)
                self.settings["anti_afk_enabled"] = False
                self.save_settings()
                self._anti_afk_stop()
                return
            try:
                interval = anti_afk_interval_var.get()
            except (tk.TclError, ValueError):
                interval = self.ANTI_AFK_DEFAULT_INTERVAL_MINUTES
            normalized_interval = self._normalize_anti_afk_interval_minutes(interval)
            if interval != normalized_interval:
                anti_afk_interval_var.set(normalized_interval)

            key_name = self._normalize_anti_afk_key_name(anti_afk_key_var.get())
            if anti_afk_key_var.get() != key_name:
                anti_afk_key_var.set(key_name)
            key_code = self._normalize_anti_afk_key_code(anti_afk_key_code_state.get("value", 0), key_name)
            anti_afk_key_code_state["value"] = key_code

            self.settings["anti_afk_enabled"] = bool(anti_afk_enabled_var.get())
            self.settings["anti_afk_interval_minutes"] = int(normalized_interval)
            self.settings["anti_afk_key_name"] = key_name
            self.settings["anti_afk_key_code"] = key_code
            self.settings["anti_afk_show_next_label"] = bool(anti_afk_show_next_label_var.get())
            self.save_settings()
            refresh_anti_afk_key_button_text()

            if self._anti_afk_config_valid():
                self._anti_afk_start()
            else:
                self._anti_afk_stop()
            self._refresh_anti_afk_next_label()

        anti_afk_control_state = "normal" if anti_afk_supported else "disabled"

        def build_anti_afk_header_action(parent: tk.Misc) -> None:
            anti_afk_key_button = ttk.Button(
                parent,
                textvariable=anti_afk_key_button_text_var,
                style="Dark.TButton",
                command=begin_anti_afk_key_capture,
                state=anti_afk_control_state,
            )
            anti_afk_key_button.pack(side="right")
            anti_afk_key_button.bind("<ButtonRelease>", block_anti_afk_capture_button_release)
            anti_afk_key_button_holder["widget"] = anti_afk_key_button

        anti_afk_card = create_settings_card(
            automation_tab,
            "Anti-AFK",
            "Keeps Roblox clients active with periodic background input",
            header_action_builder=build_anti_afk_header_action,
        )

        ttk.Checkbutton(
            anti_afk_card,
            text="Enable Anti-AFK",
            variable=anti_afk_enabled_var,
            style="Dark.TCheckbutton",
            command=on_anti_afk_update,
            state=anti_afk_control_state,
        ).pack(anchor="w", pady=(0, 2))

        ttk.Checkbutton(
            anti_afk_card,
            text="Show Floating Countdown",
            variable=anti_afk_show_next_label_var,
            style="Dark.TCheckbutton",
            command=on_anti_afk_update,
            state=anti_afk_control_state,
        ).pack(anchor="w", pady=(0, 8))

        anti_afk_options_frame = ttk.Frame(anti_afk_card, style="Dark.TFrame")
        anti_afk_options_frame.pack(fill="x", pady=(0, 2))
        anti_afk_options_frame.columnconfigure(0, weight=1)
        anti_afk_options_frame.columnconfigure(1, weight=0)

        ttk.Label(
            anti_afk_options_frame,
            text="Interval (minutes)",
            style="Dark.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        anti_afk_interval_spin = ttk.Spinbox(
            anti_afk_options_frame,
            from_=self.ANTI_AFK_MIN_INTERVAL_MINUTES,
            to=self.ANTI_AFK_MAX_INTERVAL_MINUTES,
            increment=1,
            textvariable=anti_afk_interval_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_anti_afk_update,
            state=anti_afk_control_state,
        )
        anti_afk_interval_spin.grid(row=0, column=1, sticky="e", pady=(0, 6))
        anti_afk_interval_spin.bind("<FocusOut>", lambda _evt: on_anti_afk_update())
        anti_afk_interval_spin.bind("<Return>", lambda _evt: on_anti_afk_update())

        if not anti_afk_supported:
            ttk.Label(
                anti_afk_card,
                text="Windows only.",
                style="Dark.TLabel",
                foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
            ).pack(anchor="w", pady=(6, 0))

        auto_rejoin_enable_all_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_rejoin_enable_all_accounts", False))
        )
        auto_rejoin_delay_var = tk.IntVar(value=self._get_auto_rejoin_delay_seconds())
        auto_rejoin_max_attempts_var = tk.IntVar(value=self._get_auto_rejoin_max_attempts())
        auto_rejoin_launch_behavior_labels = {
            "Rejoin Same Server": "rejoin_same_server",
            "Rejoin Same Game": "rejoin_same_game",
        }
        auto_rejoin_launch_behavior_value_to_label = {
            value: label
            for label, value in auto_rejoin_launch_behavior_labels.items()
        }
        auto_rejoin_launch_behavior_var = tk.StringVar(
            value=auto_rejoin_launch_behavior_value_to_label.get(
                self._get_auto_rejoin_launch_behavior(),
                "Rejoin Same Server",
            )
        )

        def on_auto_rejoin_settings_update(*_):
            try:
                delay_seconds = int(auto_rejoin_delay_var.get())
            except (tk.TclError, ValueError):
                delay_seconds = 5
            delay_seconds = max(0, delay_seconds)
            if auto_rejoin_delay_var.get() != delay_seconds:
                auto_rejoin_delay_var.set(delay_seconds)

            try:
                max_attempts = int(auto_rejoin_max_attempts_var.get())
            except (tk.TclError, ValueError):
                max_attempts = 0
            max_attempts = max(0, max_attempts)
            if auto_rejoin_max_attempts_var.get() != max_attempts:
                auto_rejoin_max_attempts_var.set(max_attempts)

            rejoin_launch_behavior = auto_rejoin_launch_behavior_labels.get(
                auto_rejoin_launch_behavior_var.get(),
                "rejoin_same_server",
            )
            auto_rejoin_launch_behavior_var.set(
                auto_rejoin_launch_behavior_value_to_label.get(
                    rejoin_launch_behavior,
                    "Rejoin Same Server",
                )
            )

            self.settings["auto_rejoin_enable_all_accounts"] = bool(auto_rejoin_enable_all_var.get())
            self.settings["auto_rejoin_delay_seconds"] = int(delay_seconds)
            self.settings["auto_rejoin_max_attempts"] = int(max_attempts)
            self.settings["auto_rejoin_launch_behavior"] = rejoin_launch_behavior
            self.save_settings()
            self._apply_auto_rejoin_preferences_to_active_sessions()
            self.refresh_accounts(selected_usernames=self._get_selected_usernames_silent())

        auto_rejoin_card = create_settings_card(
            automation_tab,
            "Auto Rejoin On Kick",
            "Automatically handles the account if it gets kicked/crashes",
        )

        ttk.Checkbutton(
            auto_rejoin_card,
            text="Enable Auto-Rejoin For All Accounts",
            variable=auto_rejoin_enable_all_var,
            style="Dark.TCheckbutton",
            command=on_auto_rejoin_settings_update,
        ).pack(anchor="w", pady=2)

        auto_rejoin_behavior_frame = ttk.Frame(auto_rejoin_card, style="Dark.TFrame")
        auto_rejoin_behavior_frame.pack(fill="x", pady=(6, 0))
        ttk.Label(auto_rejoin_behavior_frame, text="Disconnect Action", style="Dark.TLabel").pack(side="left")
        auto_rejoin_behavior_combo = ttk.Combobox(
            auto_rejoin_behavior_frame,
            values=list(auto_rejoin_launch_behavior_labels.keys()),
            textvariable=auto_rejoin_launch_behavior_var,
            state="readonly",
            style="Dark.TCombobox",
            width=20,
        )
        auto_rejoin_behavior_combo.pack(side="right")
        auto_rejoin_behavior_combo.bind("<<ComboboxSelected>>", on_auto_rejoin_settings_update)

        auto_rejoin_delay_frame = ttk.Frame(auto_rejoin_card, style="Dark.TFrame")
        auto_rejoin_delay_frame.pack(fill="x", pady=(6, 0))
        ttk.Label(auto_rejoin_delay_frame, text="Delay (seconds)", style="Dark.TLabel").pack(side="left")
        auto_rejoin_delay_spin = ttk.Spinbox(
            auto_rejoin_delay_frame,
            from_=0,
            to=600,
            increment=1,
            textvariable=auto_rejoin_delay_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_auto_rejoin_settings_update,
        )
        auto_rejoin_delay_spin.pack(side="right")
        auto_rejoin_delay_spin.bind("<FocusOut>", lambda _evt: on_auto_rejoin_settings_update())
        auto_rejoin_delay_spin.bind("<Return>", lambda _evt: on_auto_rejoin_settings_update())

        auto_rejoin_attempts_frame = ttk.Frame(auto_rejoin_card, style="Dark.TFrame")
        auto_rejoin_attempts_frame.pack(fill="x", pady=(6, 0))
        ttk.Label(auto_rejoin_attempts_frame, text="Max Attempts (0=unlimited)", style="Dark.TLabel").pack(side="left")
        auto_rejoin_attempts_spin = ttk.Spinbox(
            auto_rejoin_attempts_frame,
            from_=0,
            to=999,
            increment=1,
            textvariable=auto_rejoin_max_attempts_var,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_auto_rejoin_settings_update,
        )
        auto_rejoin_attempts_spin.pack(side="right")
        auto_rejoin_attempts_spin.bind("<FocusOut>", lambda _evt: on_auto_rejoin_settings_update())
        auto_rejoin_attempts_spin.bind("<Return>", lambda _evt: on_auto_rejoin_settings_update())



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

        def on_auto_memory_kill_update(*_):
            if not _auto_trim_win:
                return
            try:
                current_limit_percent = int(auto_memory_kill_limit_spin.get())
            except (tk.TclError, ValueError):
                current_limit_percent = 90
            limit_percent = self._normalize_auto_memory_kill_limit_percent(
                current_limit_percent
            )
            if current_limit_percent != limit_percent:
                auto_memory_kill_limit_spin.delete(0, tk.END)
                auto_memory_kill_limit_spin.insert(0, str(limit_percent))

            self.settings["auto_memory_kill_enabled"] = bool(auto_memory_kill_check.instate(["selected"]))
            self.settings["auto_memory_kill_limit_percent"] = int(limit_percent)
            self.save_settings()

            if self._auto_memory_kill_config_valid():
                self._auto_memory_kill_start()
            else:
                self._auto_memory_kill_stop()

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

        auto_memory_kill_card = create_settings_card(
            automation_tab,
            "Auto Kill Roblox Based On Ram Usage",
            "Closes Roblox When It Reaches A Ram Usage Past The Limit",
        )

        auto_memory_kill_check = ttk.Checkbutton(
            auto_memory_kill_card,
            text="Enable Auto Kill",
            style="Dark.TCheckbutton",
            command=on_auto_memory_kill_update,
            state=auto_trim_ctrl_state,
        )
        auto_memory_kill_check.pack(anchor="w", pady=2)
        if bool(self.settings.get("auto_memory_kill_enabled", False)):
            auto_memory_kill_check.state(["selected"])
        else:
            auto_memory_kill_check.state(["!selected"])

        auto_memory_kill_limit_frame = ttk.Frame(auto_memory_kill_card, style="Dark.TFrame")
        auto_memory_kill_limit_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(
            auto_memory_kill_limit_frame,
            text="Limit (% of system RAM)",
            style="Dark.TLabel",
        ).pack(side="left")

        auto_memory_kill_limit_spin = ttk.Spinbox(
            auto_memory_kill_limit_frame,
            from_=1,
            to=100,
            increment=1,
            width=8,
            style="Dark.TSpinbox",
            justify="center",
            command=on_auto_memory_kill_update,
            state=auto_trim_ctrl_state,
        )
        auto_memory_kill_limit_spin.insert(0, str(self._get_auto_memory_kill_limit_percent()))
        auto_memory_kill_limit_spin.pack(side="right")
        auto_memory_kill_limit_spin.bind("<FocusOut>", lambda _: on_auto_memory_kill_update())
        auto_memory_kill_limit_spin.bind("<Return>", lambda _: on_auto_memory_kill_update())

        if not _auto_trim_win:
            ttk.Label(
                auto_memory_kill_card,
                text="Windows only.",
                style="Dark.TLabel",
                foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
            ).pack(anchor="w", pady=(6, 0))

        diagnostics_card = create_settings_card(general_tab, "Diagnostics", "Verbose logging for troubleshooting")

        ttk.Checkbutton(
            diagnostics_card,
            text="Enable Debug Logging",
            variable=debug_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("enable_debug_logging", debug_var)
        ).pack(anchor="w", pady=2)

        privacy_reports_card = create_settings_card(
            general_tab,
            "Privacy & Reports",
            "Mask sensitive values and control bug report prompts",
        )

        ttk.Checkbutton(
            privacy_reports_card,
            text="Hide Sensitive Info",
            variable=hide_sensitive_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("hide_sensitive_info", hide_sensitive_var)
        ).pack(anchor="w", pady=2)

        ttk.Checkbutton(
            privacy_reports_card,
            text="Prompt for Bug Reports",
            variable=bug_prompt_var,
            style="Dark.TCheckbutton",
            command=auto_save_setting("bug_issue_prompt_enabled", bug_prompt_var)
        ).pack(anchor="w", pady=2)

        def open_instance_manager_and_close_settings():
            settings_window.destroy()
            self.open_instance_manager()

        def open_discord_log_mirror_and_close_settings():
            settings_window.destroy()
            self.open_discord_log_mirror_panel()

        discord_mirror_card = create_settings_card(
            advanced_tab,
            "Discord Monitor",
            "Send logs and screenshots to a Discord webhook",
        )

        ttk.Button(
            discord_mirror_card,
            text="Open Discord Monitor",
            style="Dark.TButton",
            command=open_discord_log_mirror_and_close_settings,
        ).pack(fill="x")

        console_card = create_settings_card(advanced_tab, "Console", "Open the live log console")

        ttk.Button(
            console_card,
            text="Open Console",
            style="Dark.TButton",
            command=self.open_console_output
        ).pack(fill="x")

        instance_manager_card = create_settings_card(
            advanced_tab,
            "Instance Manager",
            "Inspect and control active Roblox clients",
        )

        ttk.Button(
            instance_manager_card,
            text="Instance Manager",
            style="Dark.TButton",
            command=open_instance_manager_and_close_settings
        ).pack(fill="x")

        def open_fastflags_and_close_settings():
            settings_window.destroy()
            self.open_fastflags_editor()

        def open_addons_and_close_settings():
            settings_window.destroy()
            self.open_addons_window()

        def open_extensions_and_close_settings() -> None:
            settings_window.destroy()
            self.open_browser_extensions_window()

        fastflags_card = create_settings_card(
            roblox_tab,
            "Fast Flags",
            "Open the Roblox fast flags editor",
        )

        ttk.Button(
            fastflags_card,
            text="Fast Flags Editor",
            style="Dark.TButton",
            command=open_fastflags_and_close_settings
        ).pack(fill="x")

        extensions_card = create_settings_card(
            advanced_tab,
            "Extension Manager",
            "Manage Chromium, Firefox, and Waterfox browser automation extensions",
        )

        ttk.Button(
            extensions_card,
            text="Extension Manager",
            style="Dark.TButton",
            command=open_extensions_and_close_settings
        ).pack(fill="x")

        addons_card = create_settings_card(
            advanced_tab,
            "Addons",
            "Manage addon tabs and extensions",
        )

        ttk.Button(
            addons_card,
            text="Addons",
            style="Dark.TButton",
            command=open_addons_and_close_settings
        ).pack(fill="x")

        footer_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        footer_frame.pack(fill="x", pady=(8, 0))

        ttk.Button(
            footer_frame,
            text="Close",
            style="Dark.TButton",
            command=settings_window.destroy
        ).pack(fill="x")

        _refresh_settings_search_index()
        search_var.trace_add("write", _refresh_settings_card_visibility)
        settings_window.bind("<Control-f>", lambda _evt: (search_entry.focus_set(), "break")[1])
        _refresh_settings_card_visibility()
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

    def open_instance_manager(self) -> None:
        if platform.system() != "Windows":
            messagebox.showerror("Instance Manager", "This feature is only available on Windows.")
            return

        if self.instance_manager_window and self.instance_manager_window.winfo_exists():
            self.instance_manager_window.deiconify()
            self.instance_manager_window.lift()
            self.instance_manager_window.focus_force()
            return

        return self._open_instance_manager_v3()

    def _open_instance_manager_v3(self) -> None:
        window = tk.Toplevel(self.root)
        self.instance_manager_window = window
        window.withdraw()
        window.title("Instance Manager")
        window.configure(bg=self.BG_DARK)
        window.resizable(True, True)
        window.minsize(980, 620)
        self.register_toplevel(window)
        if self.settings.get("enable_topmost", False):
            window.attributes("-topmost", True)

        state: dict[str, Any] = {
            "rows": [],
            "selected": set(),
            "pid_to_hwnd": {},
            "avatar_photo_by_user_id": {},
            "avatar_pending_user_id": set(),
            "user_id_by_username": {},
            "user_id_pending_username": set(),
            "place_id_by_pid": {},
            "place_id_retry_after_by_pid": {},
            "cards_by_pid": {},
            "card_columns": 0,
            "auto_refresh_after_id": None,
            "refresh_in_progress": False,
            "refresh_pending": False,
            "closing": False,
        }

        target_exes = set(getattr(self, "_tracked_roblox_exes", set()) or {
            "robloxplayerbeta.exe",
            "robloxstudiobeta.exe",
            "robloxplayerlauncher.exe",
            "robloxstudiolauncherbeta.exe",
        })
        metadata_retry_seconds = 60.0

        default_avatar = tk.PhotoImage(width=48, height=48)
        themed_buttons: list[tuple[tk.Button, bool]] = []
        control_labels: list[tk.Label] = []

        def themed_font(size_delta: int = 0, weight: Optional[str] = None) -> tuple[Any, ...]:
            family = str(self.FONT[0]) if getattr(self, "FONT", None) else "Segoe UI"
            try:
                base_size = int(self.FONT[1])
            except (IndexError, TypeError, ValueError):
                base_size = 10
            size = max(1, base_size + size_delta)
            if weight:
                return (family, size, weight)
            return (family, size)

        def recolor_default_avatar() -> None:
            try:
                default_avatar.put(self.BG_LIGHT, to=(0, 0, 47, 47))
            except tk.TclError:
                pass

        def configure_instance_manager_button(button: tk.Button, danger: bool) -> None:
            foreground = self.FG_ACCENT_ALT if danger else self.FG_TEXT
            button.configure(
                bg=self.BG_MID if danger else self.BG_LIGHT,
                fg=foreground,
                activebackground=self.HOVER_BG,
                activeforeground=self.FG_TEXT,
                font=themed_font(0, "bold"),
                highlightbackground=self.BORDER_COLOR,
                highlightcolor=self.BORDER_COLOR,
            )

        def mbtn(parent: tk.Misc, text: str, cmd: Callable[[], Any], danger: bool = False) -> tk.Button:
            button = tk.Button(
                parent,
                text=text,
                command=cmd,
                relief="flat",
                bd=0,
                padx=10,
                pady=6,
                cursor="hand2",
            )
            themed_buttons.append((button, danger))
            configure_instance_manager_button(button, danger)
            return button

        recolor_default_avatar()

        root = tk.Frame(window, bg=self.BG_DARK)
        root.pack(fill="both", expand=True, padx=16, pady=14)

        title_label = tk.Label(root, text="Live Instances", bg=self.BG_DARK, fg=self.FG_TEXT, font=themed_font(10, "bold"))
        title_label.pack(anchor="w")
        subtitle_label = tk.Label(root, text="Shows running Roblox clients with accounts attached to it", bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font())
        subtitle_label.pack(anchor="w", pady=(2, 10))

        controls = tk.Frame(root, bg=self.BG_DARK)
        controls.pack(fill="x", pady=(0, 8))
        controls.grid_columnconfigure(1, weight=1)
        filter_var = tk.StringVar()
        status_var = tk.StringVar(value="All")
        auto_refresh_var = tk.BooleanVar(value=True)
        interval_var = tk.IntVar(value=5)
        search_label = tk.Label(controls, text="Search", bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font(-1))
        control_labels.append(search_label)
        search_label.grid(row=0, column=0, sticky="w", padx=(0, 6))
        search_entry = ttk.Entry(controls, textvariable=filter_var, style="Dark.TEntry")
        search_entry.grid(row=0, column=1, sticky="ew")
        status_label = tk.Label(controls, text="Status", bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font(-1))
        control_labels.append(status_label)
        status_label.grid(row=0, column=2, sticky="w", padx=(10, 4))
        status_combo = ttk.Combobox(controls, textvariable=status_var, values=("All", "Running", "Not Responding"), state="readonly", style="Dark.TCombobox", width=16)
        status_combo.grid(row=0, column=3, sticky="w")
        ttk.Checkbutton(controls, text="Auto Refresh", variable=auto_refresh_var, style="Dark.TCheckbutton").grid(row=0, column=4, sticky="w", padx=(10, 0))
        interval_label = tk.Label(controls, text="Every (s)", bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font(-1))
        control_labels.append(interval_label)
        interval_label.grid(row=0, column=5, sticky="w", padx=(8, 4))
        ttk.Spinbox(controls, from_=1, to=30, increment=1, textvariable=interval_var, width=4, style="Dark.TSpinbox", justify="center").grid(row=0, column=6, sticky="w")

        action_bar = tk.Frame(root, bg=self.BG_DARK)
        action_bar.pack(fill="x", pady=(0, 8))
        loaded_var = tk.StringVar(value="0 running instance(s)")

        mbtn(action_bar, "Refresh", lambda: refresh(False)).pack(side="left", padx=(0, 6))
        mbtn(action_bar, "Focus Selected", lambda: focus_selected()).pack(side="left", padx=(0, 6))
        mbtn(action_bar, "Kill Selected", lambda: kill_selected(), danger=True).pack(side="left", padx=(0, 6))
        loaded_label = tk.Label(action_bar, textvariable=loaded_var, bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font())
        loaded_label.pack(side="right")

        shell = tk.Frame(root, bg=self.BG_FRAME, highlightthickness=1, highlightbackground=self.BORDER_COLOR, bd=0)
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, bg=self.BG_FRAME, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        host = tk.Frame(canvas, bg=self.BG_FRAME)
        host_id = canvas.create_window((0, 0), window=host, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        host.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda _e: canvas.itemconfigure(host_id, width=canvas.winfo_width()))

        def extract_account_from_title(title_text: str) -> str:
            text = str(title_text or "").strip()
            if not text:
                return ""
            for match in re.finditer(r"@([A-Za-z0-9_]{3,})", text):
                return match.group(1)
            for match in re.finditer(r"([A-Za-z0-9_]{3,})@", text):
                return match.group(1)
            return ""

        def fetch_avatar_async(user_id: str) -> None:
            if (not user_id) or user_id in state["avatar_photo_by_user_id"] or user_id in state["avatar_pending_user_id"]:
                return
            state["avatar_pending_user_id"].add(user_id)

            def worker() -> None:
                image_data = ""
                try:
                    meta = RobloxAPI._get_http_session().get(
                        f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=48x48&format=Png",
                        timeout=8,
                    )
                    payload = meta.json() if meta.content else {}
                    data = payload.get("data") or []
                    image_url = str((data[0] or {}).get("imageUrl") or "").strip() if data else ""
                    if image_url:
                        img = RobloxAPI._get_http_session().get(image_url, timeout=8)
                        if img.content:
                            image_data = base64.b64encode(img.content).decode("ascii")
                except Exception:
                    image_data = ""

                def done() -> None:
                    photo = None
                    if image_data:
                        try:
                            photo = tk.PhotoImage(data=image_data)
                        except Exception:
                            photo = None
                    state["avatar_pending_user_id"].discard(user_id)
                    if photo is not None:
                        state["avatar_photo_by_user_id"][user_id] = photo
                    render()

                self.root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        def avatar_for(username: str) -> tk.PhotoImage:
            uname = str(username or "").strip()
            if not uname:
                return default_avatar
            user_id = str(state["user_id_by_username"].get(uname, "") or "").strip()
            if user_id:
                return state["avatar_photo_by_user_id"].get(user_id, default_avatar)
            if uname not in state["user_id_pending_username"]:
                state["user_id_pending_username"].add(uname)

                def worker() -> None:
                    resolved = ""
                    try:
                        resolved = str(RobloxAPI.get_user_id_from_username(uname) or "").strip()
                    except Exception:
                        resolved = ""

                    def done() -> None:
                        state["user_id_pending_username"].discard(uname)
                        state["user_id_by_username"][uname] = resolved
                        if resolved:
                            fetch_avatar_async(resolved)
                        render()

                    self.root.after(0, done)

                threading.Thread(target=worker, daemon=True).start()
            return default_avatar

        def focus_pid(pid: int) -> None:
            hwnd = state["pid_to_hwnd"].get(int(pid))
            if not hwnd:
                return
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            except Exception:
                pass

        def kill_pids(pid_values: Any) -> None:
            pids = [int(pid) for pid in pid_values if str(pid).isdigit() and int(pid) > 0]
            if not pids:
                return

            def worker() -> None:
                for pid in pids:
                    try:
                        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, **subprocess_no_window_kwargs())
                    except Exception:
                        pass
                self._invalidate_tracked_process_caches()
                self._invalidate_active_client_indicator_cache()
                self.root.after(0, lambda: refresh(False))

            threading.Thread(target=worker, daemon=True).start()

        def toggle_selected(pid: int, additive: bool = False) -> None:
            pid = int(pid)
            if additive:
                if pid in state["selected"]:
                    state["selected"].remove(pid)
                else:
                    state["selected"].add(pid)
            else:
                if state["selected"] == {pid}:
                    state["selected"].clear()
                else:
                    state["selected"] = {pid}
            render()

        def filtered_rows() -> list[dict[str, Any]]:
            rows = list(state["rows"])
            query_text = str(filter_var.get() or "").strip().lower()
            status_text = str(status_var.get() or "All").strip().lower()
            if status_text != "all":
                rows = [row for row in rows if str(row.get("status", "")).strip().lower() == status_text]
            if query_text:
                rows = [
                    row for row in rows
                    if query_text in f"{row.get('username', '')} {row.get('place_id', '')} {row.get('pid', '')} {row.get('status', '')}".lower()
                ]
            return rows

        def bind_card_widget(widget: tk.Widget, pid: int) -> None:
            widget.bind("<Button-1>", lambda event, current_pid=pid: toggle_selected(current_pid, additive=bool(event.state & 0x0004)))
            widget.bind("<Double-Button-1>", lambda _event, current_pid=pid: focus_pid(current_pid))

        def create_card(pid: int) -> InstanceManagerCardWidgets:
            card = tk.Frame(host, bg=self.BG_MID, highlightthickness=1, highlightbackground=self.BORDER_COLOR, bd=0, padx=10, pady=10)
            card.grid_columnconfigure(1, weight=1)
            avatar_label = tk.Label(card, image=default_avatar, bg=self.BG_MID, bd=0)
            avatar_label.image = default_avatar
            avatar_label.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 10))
            username_label = tk.Label(card, text="Unknown", bg=self.BG_MID, fg=self.FG_TEXT, font=themed_font(2, "bold"))
            username_label.grid(row=0, column=1, sticky="w")
            place_label = tk.Label(card, text="Place ID: Unknown", bg=self.BG_MID, fg=self.FG_MUTED, font=themed_font())
            place_label.grid(row=1, column=1, sticky="w", pady=(2, 0))
            pid_label = tk.Label(card, text=f"PID: {pid}", bg=self.BG_MID, fg=self.FG_MUTED, font=themed_font())
            pid_label.grid(row=2, column=1, sticky="w", pady=(2, 0))
            status_label = tk.Label(card, text="Running", bg=self.BG_LIGHT, fg=self.FG_ACCENT_ALT, font=themed_font(-1, "bold"), padx=8, pady=2)
            status_label.grid(row=0, column=2, sticky="e")
            actions_frame = tk.Frame(card, bg=self.BG_MID)
            actions_frame.grid(row=2, column=2, sticky="e")
            mbtn(actions_frame, "Focus", lambda current_pid=pid: focus_pid(current_pid)).pack(side="left", padx=(0, 6))
            mbtn(actions_frame, "Kill", lambda current_pid=pid: kill_pids([current_pid]), danger=True).pack(side="left")
            widgets = (card, avatar_label, username_label, place_label, pid_label, status_label, actions_frame)
            for widget in widgets:
                bind_card_widget(widget, pid)
            return InstanceManagerCardWidgets(
                frame=card,
                avatar_label=avatar_label,
                username_label=username_label,
                place_label=place_label,
                pid_label=pid_label,
                status_label=status_label,
                actions_frame=actions_frame,
            )

        def update_card(card_widgets: InstanceManagerCardWidgets, row: dict[str, Any], selected: bool) -> None:
            pid = int(row["pid"])
            background = self.HOVER_BG if selected else self.BG_MID
            border_color = self.FG_ACCENT if selected else self.BORDER_COLOR
            avatar = avatar_for(str(row.get("username", "")))
            status_text = str(row.get("status", "Running"))
            status_color = self.FG_ACCENT_ALT if status_text.lower() == "running" else self.FG_ACCENT
            card_widgets.frame.configure(bg=background, highlightbackground=border_color, highlightcolor=border_color)
            card_widgets.avatar_label.configure(image=avatar, bg=background)
            card_widgets.avatar_label.image = avatar
            card_widgets.username_label.configure(text=str(row.get("username", "Unknown")), bg=background, fg=self.FG_TEXT, font=themed_font(2, "bold"))
            card_widgets.place_label.configure(text=f"Place ID: {row.get('place_id', 'Unknown')}", bg=background, fg=self.FG_MUTED, font=themed_font())
            card_widgets.pid_label.configure(text=f"PID: {pid}", bg=background, fg=self.FG_MUTED, font=themed_font())
            card_widgets.status_label.configure(text=status_text, bg=self.BG_LIGHT, fg=status_color, font=themed_font(-1, "bold"))
            card_widgets.actions_frame.configure(bg=background)

        def render() -> None:
            rows = filtered_rows()
            visible_pids = {int(row["pid"]) for row in rows}
            state["selected"] = {pid for pid in state["selected"] if pid in visible_pids}

            cards_by_pid = state["cards_by_pid"]
            for pid in list(cards_by_pid.keys()):
                if pid in visible_pids:
                    continue
                try:
                    cards_by_pid[pid].frame.destroy()
                except Exception:
                    pass
                cards_by_pid.pop(pid, None)

            column_count = 2 if int(canvas.winfo_width() or 1) >= 1120 else 1
            if int(state.get("card_columns", 0) or 0) != column_count:
                for column in range(2):
                    host.grid_columnconfigure(column, weight=1 if column < column_count else 0, uniform="cards" if column < column_count else "")
                state["card_columns"] = column_count

            for index, row in enumerate(rows):
                pid = int(row["pid"])
                card_widgets = cards_by_pid.get(pid)
                if card_widgets is None:
                    card_widgets = create_card(pid)
                    cards_by_pid[pid] = card_widgets
                update_card(card_widgets, row, selected=pid in state["selected"])
                card_widgets.frame.grid(row=index // column_count, column=index % column_count, sticky="ew", padx=8, pady=8)

            loaded_var.set(f"{len(state['rows'])} running instance(s)")
            canvas.configure(scrollregion=canvas.bbox("all"))

        def apply_instance_manager_theme() -> None:
            try:
                if not window.winfo_exists():
                    return
            except (RuntimeError, tk.TclError):
                return

            window.configure(bg=self.BG_DARK)
            root.configure(bg=self.BG_DARK)
            title_label.configure(bg=self.BG_DARK, fg=self.FG_TEXT, font=themed_font(10, "bold"))
            subtitle_label.configure(bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font())
            controls.configure(bg=self.BG_DARK)
            action_bar.configure(bg=self.BG_DARK)
            loaded_label.configure(bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font())
            shell.configure(bg=self.BG_FRAME, highlightbackground=self.BORDER_COLOR, highlightcolor=self.BORDER_COLOR)
            canvas.configure(bg=self.BG_FRAME)
            host.configure(bg=self.BG_FRAME)

            for label in control_labels:
                try:
                    if label.winfo_exists():
                        label.configure(bg=self.BG_DARK, fg=self.FG_MUTED, font=themed_font(-1))
                except (RuntimeError, tk.TclError):
                    continue

            alive_buttons: list[tuple[tk.Button, bool]] = []
            for button, danger in themed_buttons:
                try:
                    if button.winfo_exists():
                        configure_instance_manager_button(button, danger)
                        alive_buttons.append((button, danger))
                except (RuntimeError, tk.TclError):
                    continue
            themed_buttons[:] = alive_buttons

            recolor_default_avatar()
            try:
                render()
            except tk.TclError:
                pass

        def snapshot(from_auto: bool = False) -> tuple[list[dict[str, Any]], dict[int, str], dict[int, float]]:
            tracked_snapshot = self._get_tracked_window_snapshot(
                target_exes,
                use_cache=from_auto,
            )
            pid_to_image = dict(tracked_snapshot.get("pid_to_image", {}) or {})
            pid_to_hwnd = dict(tracked_snapshot.get("pid_to_hwnd", {}) or {})
            pid_to_title = dict(tracked_snapshot.get("pid_to_title", {}) or {})
            pid_to_hung = dict(tracked_snapshot.get("pid_to_hung", {}) or {})
            place_id_by_pid = {
                int(pid): str(place_id or "").strip()
                for pid, place_id in dict(state.get("place_id_by_pid", {})).items()
                if str(place_id or "").strip()
            }
            place_id_retry_after_by_pid = {
                int(pid): float(retry_after or 0.0)
                for pid, retry_after in dict(state.get("place_id_retry_after_by_pid", {})).items()
            }

            running_pids = {int(pid) for pid in pid_to_image.keys()}
            for pid in list(place_id_by_pid.keys()):
                if pid not in running_pids:
                    place_id_by_pid.pop(pid, None)
                    place_id_retry_after_by_pid.pop(pid, None)

            metadata_target_pids = set()
            if running_pids:
                if from_auto:
                    now = time.monotonic()
                    for pid in running_pids:
                        if str(place_id_by_pid.get(pid, "") or "").strip():
                            continue
                        retry_after = float(place_id_retry_after_by_pid.get(pid, 0.0) or 0.0)
                        if now >= retry_after:
                            metadata_target_pids.add(pid)
                else:
                    metadata_target_pids = set(running_pids)

            if metadata_target_pids:
                resolved_place_ids = self._query_pid_place_id_map(
                    target_exes,
                    pid_values=metadata_target_pids,
                    allow_log_fallback=not from_auto,
                    use_cache=from_auto,
                )
                retry_at = time.monotonic() + metadata_retry_seconds
                for pid in metadata_target_pids:
                    resolved_place_id = str(resolved_place_ids.get(pid, "") or "").strip()
                    if resolved_place_id:
                        place_id_by_pid[pid] = resolved_place_id
                        place_id_retry_after_by_pid.pop(pid, None)
                    else:
                        place_id_retry_after_by_pid[pid] = retry_at

            rows = []
            for pid in sorted(pid_to_image.keys()):
                mapped = ""
                try:
                    with self._pid_account_lock:
                        mapped = str(self._pid_account_map.get(int(pid), "") or "").strip()
                except Exception:
                    mapped = ""
                username = mapped or extract_account_from_title(pid_to_title.get(int(pid), "")) or "Unknown"
                rows.append({
                    "pid": int(pid),
                    "username": username,
                    "place_id": str(place_id_by_pid.get(int(pid), "") or "").strip() or "Unknown",
                    "status": "Not Responding" if pid_to_hung.get(int(pid)) else "Running",
                    "hwnd": pid_to_hwnd.get(int(pid)),
                })
            return rows, place_id_by_pid, place_id_retry_after_by_pid

        def refresh(from_auto: bool = False) -> None:
            if state["closing"]:
                return
            if state["refresh_in_progress"]:
                if not from_auto:
                    state["refresh_pending"] = True
                return
            state["refresh_in_progress"] = True

            def worker() -> None:
                try:
                    rows, place_id_by_pid, place_id_retry_after_by_pid = snapshot(from_auto=from_auto)
                except Exception:
                    rows = []
                    place_id_by_pid = dict(state.get("place_id_by_pid", {}))
                    place_id_retry_after_by_pid = dict(state.get("place_id_retry_after_by_pid", {}))

                def done() -> None:
                    state["refresh_in_progress"] = False
                    if state["closing"]:
                        return
                    state["rows"] = rows
                    state["pid_to_hwnd"] = {int(row["pid"]): row.get("hwnd") for row in rows}
                    state["place_id_by_pid"] = place_id_by_pid
                    state["place_id_retry_after_by_pid"] = place_id_retry_after_by_pid
                    render()
                    if state["refresh_pending"]:
                        state["refresh_pending"] = False
                        refresh(False)
                    elif from_auto:
                        schedule_auto_refresh()

                self.root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        def schedule_auto_refresh() -> None:
            after_id = state.get("auto_refresh_after_id")
            if after_id is not None:
                try:
                    window.after_cancel(after_id)
                except Exception:
                    pass
                state["auto_refresh_after_id"] = None
            if state["closing"] or not auto_refresh_var.get():
                return
            try:
                interval = int(interval_var.get())
            except Exception:
                interval = 5
            interval = max(1, min(30, interval))
            state["auto_refresh_after_id"] = window.after(interval * 1000, auto_refresh_tick)

        def auto_refresh_tick() -> None:
            state["auto_refresh_after_id"] = None
            if state["closing"] or not auto_refresh_var.get():
                return
            try:
                if str(window.state()) == "iconic":
                    schedule_auto_refresh()
                    return
            except Exception:
                pass
            if state["refresh_in_progress"]:
                schedule_auto_refresh()
                return
            refresh(True)

        def focus_selected() -> None:
            selected = sorted(int(pid) for pid in state["selected"] if int(pid) > 0)
            if selected:
                focus_pid(selected[0])

        def kill_selected() -> None:
            selected = sorted(int(pid) for pid in state["selected"] if int(pid) > 0)
            if not selected:
                messagebox.showwarning("Kill Selected", "Select at least one instance first.")
                return
            if messagebox.askyesno("Kill Selected", f"Kill {len(selected)} selected instance(s)?"):
                kill_pids(selected)

        filter_var.trace_add("write", lambda *_: render())
        status_var.trace_add("write", lambda *_: render())
        auto_refresh_var.trace_add("write", lambda *_: schedule_auto_refresh())
        interval_var.trace_add("write", lambda *_: schedule_auto_refresh())
        status_combo.bind("<<ComboboxSelected>>", lambda _evt: render())
        search_entry.bind("<Escape>", lambda _evt: (filter_var.set(""), "break")[1])
        self.register_theme_refresh(window, apply_instance_manager_theme)

        def on_close() -> None:
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
        self._center_window(window, max(980, window.winfo_reqwidth() + 70), max(620, window.winfo_reqheight() + 70))
        window.deiconify()
        refresh(False)
        schedule_auto_refresh()

    def open_console_output(self):
        """Open or focus the console output window."""
        if self.console_window:
            self.console_window.show()

    def open_discord_log_mirror_panel(self, parent: Optional[tk.Misc] = None) -> None:
        if self.discord_log_mirror_window and self.discord_log_mirror_window.winfo_exists():
            self.discord_log_mirror_window.deiconify()
            self.discord_log_mirror_window.lift()
            self.discord_log_mirror_window.focus_force()
            return

        owner = parent or self.root
        window = tk.Toplevel(owner)
        window.withdraw()
        window.title("Discord Monitor")
        window.configure(bg=self.BG_DARK)
        window.resizable(True, True)
        window.transient(owner)
        window.grab_set()
        self.register_toplevel(window)
        self.discord_log_mirror_window = window

        if self.settings.get("enable_topmost", False):
            try:
                window.attributes("-topmost", True)
            except tk.TclError:
                pass

        enabled_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_enabled", False))
        webhook_var = tk.StringVar(value=self.settings.get("discord_log_mirror_webhook_url", ""))
        stdout_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_include_stdout", True))
        stderr_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_include_stderr", True))
        redact_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_redact_sensitive", True))
        startup_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_send_startup_notice", False))
        ping_user_id_var = tk.StringVar(value=self.settings.get("discord_log_mirror_ping_user_id", ""))
        ping_only_errors_var = tk.BooleanVar(value=self.settings.get("discord_log_mirror_ping_only_errors", True))
        screenshot_interval_var = tk.IntVar(
            value=int(self.settings.get("discord_log_mirror_screenshot_interval_minutes", 0) or 0)
        )
        instance_summary_enabled_var = tk.BooleanVar(
            value=bool(self.settings.get("discord_log_mirror_instance_summary_enabled", False))
        )
        instance_summary_interval_var = tk.IntVar(
            value=int(self.settings.get("discord_log_mirror_instance_summary_interval_minutes", 15) or 15)
        )
        all_monitors_available = self._get_discord_screenshot_monitor_count() > 1
        screenshot_all_monitors_var = tk.BooleanVar(
            value=all_monitors_available
            and bool(self.settings.get("discord_log_mirror_screenshot_all_monitors", False))
        )
        selected_filter_preset = get_discord_log_filter_preset(
            self.settings.get("discord_log_mirror_filter_preset", "all")
        )
        if selected_filter_preset.key == DISCORD_LOG_FILTER_PRESET_CUSTOM:
            selected_filter_preset = get_discord_log_filter_preset("all")
        preset_labels = [
            preset.label
            for preset in DISCORD_LOG_FILTER_PRESETS
            if preset.key != DISCORD_LOG_FILTER_PRESET_CUSTOM
        ]
        filter_preset_label_var = tk.StringVar(value=selected_filter_preset.label)
        max_lines_var = tk.IntVar(value=self._get_discord_log_mirror_max_lines_per_message())

        def close_panel() -> None:
            try:
                save_panel_settings()
            except tk.TclError:
                pass
            try:
                window.destroy()
            finally:
                self.discord_log_mirror_window = None
                try:
                    if owner is not self.root and owner.winfo_exists():
                        owner.grab_set()
                        owner.focus_force()
                except tk.TclError:
                    pass

        def save_panel_settings(*_args: object) -> None:
            try:
                max_lines = int(max_lines_var.get())
            except (tk.TclError, ValueError):
                max_lines = 20
            try:
                screenshot_interval = int(screenshot_interval_var.get())
            except (tk.TclError, ValueError):
                screenshot_interval = 0
            try:
                instance_summary_interval = int(instance_summary_interval_var.get())
            except (tk.TclError, ValueError):
                instance_summary_interval = 15

            max_lines = max(1, min(50, max_lines))
            screenshot_interval = max(0, min(1440, screenshot_interval))
            instance_summary_interval = max(1, min(1440, instance_summary_interval))
            max_lines_var.set(max_lines)
            screenshot_interval_var.set(screenshot_interval)
            instance_summary_interval_var.set(instance_summary_interval)

            webhook_url = str(webhook_var.get() or "").strip()
            ping_user_id = re.sub(r"\D", "", str(ping_user_id_var.get() or ""))
            ping_user_id_var.set(ping_user_id)
            self.settings["discord_log_mirror_enabled"] = bool(enabled_var.get())
            self.settings["discord_log_mirror_webhook_url"] = webhook_url
            self.settings["discord_log_mirror_include_stdout"] = bool(stdout_var.get())
            self.settings["discord_log_mirror_include_stderr"] = bool(stderr_var.get())
            self.settings["discord_log_mirror_redact_sensitive"] = bool(redact_var.get())
            self.settings["discord_log_mirror_send_startup_notice"] = bool(startup_var.get())
            self.settings["discord_log_mirror_ping_user_id"] = ping_user_id
            self.settings["discord_log_mirror_ping_only_errors"] = bool(ping_only_errors_var.get())
            self.settings["discord_log_mirror_screenshot_interval_minutes"] = screenshot_interval
            self.settings["discord_log_mirror_screenshot_all_monitors"] = (
                all_monitors_available and bool(screenshot_all_monitors_var.get())
            )
            self.settings["discord_log_mirror_instance_summary_enabled"] = bool(instance_summary_enabled_var.get())
            self.settings["discord_log_mirror_instance_summary_interval_minutes"] = instance_summary_interval
            screenshot_all_monitors_var.set(bool(self.settings["discord_log_mirror_screenshot_all_monitors"]))
            selected_preset = DISCORD_LOG_FILTER_PRESET_BY_LABEL.get(
                str(filter_preset_label_var.get() or ""),
                get_discord_log_filter_preset(self.settings.get("discord_log_mirror_filter_preset", "all")),
            )
            self.settings["discord_log_mirror_filter_preset"] = selected_preset.key
            self.settings["discord_log_mirror_include_filter"] = selected_preset.include_filter
            self.settings["discord_log_mirror_exclude_filter"] = selected_preset.exclude_filter
            self.settings["discord_log_mirror_max_lines_per_message"] = max_lines
            self.save_settings()

            if self.settings["discord_log_mirror_enabled"] and webhook_url and self._is_valid_discord_webhook_url(webhook_url):
                self._discord_log_mirror_start(reset_index=True)
            else:
                self._discord_log_mirror_stop()

        def send_test() -> None:
            save_panel_settings()
            self._send_discord_log_mirror_test(window)

        def send_test_screenshot() -> None:
            save_panel_settings()
            self._send_discord_log_mirror_test_screenshot(window)

        def send_instance_summary() -> None:
            save_panel_settings()
            self._send_discord_log_mirror_instance_summary(window)

        def apply_filter_preset(*_args: object) -> None:
            selected_preset = DISCORD_LOG_FILTER_PRESET_BY_LABEL.get(str(filter_preset_label_var.get() or ""))
            if selected_preset is None:
                selected_preset = get_discord_log_filter_preset("all")
                filter_preset_label_var.set(selected_preset.label)
            save_panel_settings()

        window.minsize(700, 560)

        main = ttk.Frame(window, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=18, pady=16)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        header = ttk.Frame(main, style="Dark.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Discord Monitor",
            style="Dark.TLabel",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Webhook logging, alerts, screenshots, and instance reports",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        body_host = ttk.Frame(main, style="Dark.TFrame")
        body_host.grid(row=1, column=0, sticky="nsew")
        body_host.rowconfigure(0, weight=1)
        body_host.columnconfigure(0, weight=1)

        body_canvas = tk.Canvas(body_host, bg=self.BG_DARK, highlightthickness=0, bd=0)
        body_scroll = ttk.Scrollbar(body_host, orient="vertical", command=body_canvas.yview)
        body_canvas.configure(yscrollcommand=body_scroll.set)
        body_canvas.grid(row=0, column=0, sticky="nsew")
        body_scroll.grid(row=0, column=1, sticky="ns")

        body = ttk.Frame(body_canvas, style="Dark.TFrame")
        body_window = body_canvas.create_window((0, 0), window=body, anchor="nw")

        def sync_body_scrollregion(_evt: Optional[tk.Event] = None) -> None:
            try:
                body_canvas.configure(scrollregion=body_canvas.bbox("all"))
            except tk.TclError:
                pass

        def sync_body_width(_evt: Optional[tk.Event] = None) -> None:
            try:
                body_canvas.itemconfigure(body_window, width=body_canvas.winfo_width())
            except tk.TclError:
                pass
            sync_body_scrollregion()

        def on_body_mousewheel(event: tk.Event) -> str:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                body_canvas.yview_scroll(-1 * int(delta / 120), "units")
            return "break"

        body.bind("<Configure>", sync_body_scrollregion)
        body_canvas.bind("<Configure>", sync_body_width)
        body_canvas.bind("<MouseWheel>", on_body_mousewheel)
        body.bind("<MouseWheel>", on_body_mousewheel)

        def create_monitor_section(parent: tk.Widget, title: str, subtitle: str) -> ttk.Frame:
            outer = tk.Frame(
                parent,
                bg=self.BG_MID,
                highlightbackground=self.BORDER_COLOR,
                highlightthickness=1,
                bd=0,
            )
            outer.pack(fill="x", pady=(0, 10))
            section_header = tk.Frame(outer, bg=self.BG_MID)
            section_header.pack(fill="x", padx=12, pady=(10, 0))
            ttk.Label(
                section_header,
                text=title,
                style="Dark.TLabel",
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                section_header,
                text=subtitle,
                style="Dark.TLabel",
                font=("Segoe UI", 9),
                foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
            ).pack(anchor="w", pady=(2, 0))
            section_body = ttk.Frame(outer, style="Dark.TFrame")
            section_body.pack(fill="x", padx=12, pady=(10, 12))
            return section_body

        def create_row(parent: tk.Widget) -> ttk.Frame:
            row = ttk.Frame(parent, style="Dark.TFrame")
            row.pack(fill="x", pady=(0, 8))
            return row

        connection_section = create_monitor_section(
            body,
            "Connection",
            "Control the webhook endpoint and when FRAM starts sending to it",
        )
        connection_options_row = create_row(connection_section)
        ttk.Checkbutton(
            connection_options_row,
            text="Enable Discord Logging",
            variable=enabled_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(side="left")
        ttk.Checkbutton(
            connection_options_row,
            text="Connected notice on startup",
            variable=startup_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(side="left", padx=(18, 0))
        ttk.Label(connection_section, text="Webhook URL", style="Dark.TLabel").pack(anchor="w", pady=(2, 3))
        webhook_entry = ttk.Entry(connection_section, textvariable=webhook_var, style="Dark.TEntry", show="*")
        webhook_entry.pack(fill="x")
        webhook_entry.bind("<FocusOut>", lambda _evt: save_panel_settings())
        webhook_entry.bind("<Return>", lambda _evt: (save_panel_settings(), "break")[1])

        logs_section = create_monitor_section(
            body,
            "Log Delivery",
            "Choose which console entries are mirrored and how messages are batched",
        )
        stream_frame = create_row(logs_section)
        ttk.Checkbutton(
            stream_frame,
            text="Normal logs",
            variable=stdout_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(side="left")
        ttk.Checkbutton(
            stream_frame,
            text="Errors",
            variable=stderr_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            stream_frame,
            text="Redact sensitive info",
            variable=redact_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(side="left", padx=(18, 0))
        filter_grid = ttk.Frame(logs_section, style="Dark.TFrame")
        filter_grid.pack(fill="x")
        filter_grid.columnconfigure(1, weight=1)
        ttk.Label(filter_grid, text="Log Filter", style="Dark.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
        filter_preset_combo = ttk.Combobox(
            filter_grid,
            textvariable=filter_preset_label_var,
            values=preset_labels,
            state="readonly",
            style="Dark.TCombobox",
        )
        filter_preset_combo.grid(row=0, column=1, sticky="ew")
        filter_preset_combo.bind("<<ComboboxSelected>>", apply_filter_preset)
        ttk.Label(filter_grid, text="Lines per message", style="Dark.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=(8, 0),
        )
        lines_spin = ttk.Spinbox(
            filter_grid,
            from_=1,
            to=50,
            increment=1,
            textvariable=max_lines_var,
            width=7,
            style="Dark.TSpinbox",
            justify="center",
            command=save_panel_settings,
        )
        lines_spin.grid(row=1, column=1, sticky="w", pady=(8, 0))
        lines_spin.bind("<FocusOut>", lambda _evt: save_panel_settings())
        lines_spin.bind("<Return>", lambda _evt: (save_panel_settings(), "break")[1])

        alerts_section = create_monitor_section(
            body,
            "Alerts",
            "Optionally mention a Discord user when important log entries are sent",
        )
        alerts_grid = ttk.Frame(alerts_section, style="Dark.TFrame")
        alerts_grid.pack(fill="x")
        alerts_grid.columnconfigure(1, weight=1)
        ttk.Label(alerts_grid, text="Ping User ID", style="Dark.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ping_entry = ttk.Entry(alerts_grid, textvariable=ping_user_id_var, style="Dark.TEntry")
        ping_entry.grid(row=0, column=1, sticky="ew")
        ping_entry.bind("<FocusOut>", lambda _evt: save_panel_settings())
        ping_entry.bind("<Return>", lambda _evt: (save_panel_settings(), "break")[1])
        ttk.Checkbutton(
            alerts_section,
            text="Ping only on errors and warnings",
            variable=ping_only_errors_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).pack(anchor="w", pady=(8, 0))

        captures_section = create_monitor_section(
            body,
            "Screenshots",
            "Send monitor captures on a fixed interval",
        )
        screenshot_grid = ttk.Frame(captures_section, style="Dark.TFrame")
        screenshot_grid.pack(fill="x")
        ttk.Label(screenshot_grid, text="Send every", style="Dark.TLabel").grid(row=0, column=0, sticky="w")
        screenshot_spin = ttk.Spinbox(
            screenshot_grid,
            from_=0,
            to=1440,
            increment=1,
            textvariable=screenshot_interval_var,
            width=7,
            style="Dark.TSpinbox",
            justify="center",
            command=save_panel_settings,
        )
        screenshot_spin.grid(row=0, column=1, sticky="w", padx=(8, 6))
        ttk.Label(screenshot_grid, text="minutes (0 = off)", style="Dark.TLabel").grid(row=0, column=2, sticky="w")
        screenshot_spin.bind("<FocusOut>", lambda _evt: save_panel_settings())
        screenshot_spin.bind("<Return>", lambda _evt: (save_panel_settings(), "break")[1])
        if all_monitors_available:
            ttk.Checkbutton(
                captures_section,
                text="Capture all monitors",
                variable=screenshot_all_monitors_var,
                style="Dark.TCheckbutton",
                command=save_panel_settings,
            ).pack(anchor="w", pady=(8, 0))

        instances_section = create_monitor_section(
            body,
            "Active Instances",
            "Post running Roblox accounts, PIDs, status, RAM, place, and rejoin state",
        )
        instance_summary_frame = ttk.Frame(instances_section, style="Dark.TFrame")
        instance_summary_frame.pack(fill="x")
        ttk.Checkbutton(
            instance_summary_frame,
            text="Send Active Instance Summary",
            variable=instance_summary_enabled_var,
            style="Dark.TCheckbutton",
            command=save_panel_settings,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(instance_summary_frame, text="every", style="Dark.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 6))
        instance_summary_spin = ttk.Spinbox(
            instance_summary_frame,
            from_=1,
            to=1440,
            increment=1,
            textvariable=instance_summary_interval_var,
            width=7,
            style="Dark.TSpinbox",
            justify="center",
            command=save_panel_settings,
        )
        instance_summary_spin.grid(row=0, column=2, sticky="w")
        ttk.Label(instance_summary_frame, text="minutes", style="Dark.TLabel").grid(row=0, column=3, sticky="w", padx=(6, 0))
        instance_summary_spin.bind("<FocusOut>", lambda _evt: save_panel_settings())
        instance_summary_spin.bind("<Return>", lambda _evt: (save_panel_settings(), "break")[1])

        button_frame = ttk.Frame(main, style="Dark.TFrame")
        button_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        for column_index in range(4):
            button_frame.columnconfigure(column_index, weight=1)
        ttk.Button(button_frame, text="Send Test", style="Dark.TButton", command=send_test).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )
        ttk.Button(
            button_frame,
            text="Send Test Screenshot",
            style="Dark.TButton",
            command=send_test_screenshot,
        ).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(
            button_frame,
            text="Send Summary Now",
            style="Dark.TButton",
            command=send_instance_summary,
        ).grid(row=0, column=2, sticky="ew", padx=5)
        ttk.Button(button_frame, text="Close", style="Dark.TButton", command=close_panel).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(5, 0),
        )

        window.protocol("WM_DELETE_WINDOW", close_panel)
        window.bind("<Escape>", lambda _evt: (close_panel(), "break")[1])
        window.update_idletasks()
        self._center_window(window, max(740, window.winfo_reqwidth() + 50), max(620, window.winfo_reqheight() + 50))
        window.deiconify()
        webhook_entry.focus_set()

    def _get_discord_log_mirror_webhook_url(self) -> str:
        return str(self.settings.get("discord_log_mirror_webhook_url", "") or "").strip()

    def _is_valid_discord_webhook_url(self, webhook_url: str) -> bool:
        return bool(
            re.match(
                r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[^\s/]+",
                str(webhook_url or "").strip(),
            )
        )

    def _discord_log_mirror_get_current_total(self) -> int:
        _, total = self.console_output.get_entries_since(10**9)
        return int(total)

    def _discord_log_mirror_maybe_start(self) -> None:
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if self.settings.get("discord_log_mirror_enabled", False) and self._is_valid_discord_webhook_url(webhook_url):
            self._discord_log_mirror_start(reset_index=True)
        else:
            self._discord_log_mirror_stop()

    def _on_console_output_entry_added(self) -> None:
        self._discord_log_mirror_schedule()

    def _discord_log_mirror_start(self, reset_index: bool = False) -> None:
        if reset_index:
            self._discord_log_mirror_last_index = self._discord_log_mirror_get_current_total()
        if self.settings.get("discord_log_mirror_send_startup_notice", False):
            self._discord_log_mirror_send_startup_notice()
        self._discord_log_mirror_schedule_screenshot(reset=True)
        self._discord_log_mirror_schedule_instance_summary(reset=True)

    def _discord_log_mirror_stop(self) -> None:
        after_id = self._discord_log_mirror_after_id
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._discord_log_mirror_after_id = None
        self._discord_log_mirror_in_progress = False
        self._discord_log_mirror_cancel_screenshot()
        self._discord_log_mirror_cancel_instance_summary()

    def _discord_log_mirror_schedule(self, delay_ms: Optional[int] = None) -> None:
        if self._discord_log_mirror_after_id is not None:
            return
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self.settings.get("discord_log_mirror_enabled", False) or not self._is_valid_discord_webhook_url(webhook_url):
            return
        if delay_ms is None:
            delay_ms = DISCORD_LOG_MIRROR_SEND_DEBOUNCE_MS
        try:
            self._discord_log_mirror_after_id = self.root.after(max(0, int(delay_ms)), self._discord_log_mirror_poll)
        except (RuntimeError, tk.TclError):
            self._discord_log_mirror_after_id = None

    def _get_discord_log_mirror_max_lines_per_message(self) -> int:
        try:
            value = int(self.settings.get("discord_log_mirror_max_lines_per_message", 20) or 20)
        except (TypeError, ValueError):
            value = 20
        return max(1, min(50, value))

    def _get_discord_log_mirror_screenshot_interval_minutes(self) -> int:
        try:
            value = int(self.settings.get("discord_log_mirror_screenshot_interval_minutes", 0) or 0)
        except (TypeError, ValueError):
            value = 0
        return max(0, min(1440, value))

    def _get_discord_log_mirror_instance_summary_interval_minutes(self) -> int:
        try:
            value = int(self.settings.get("discord_log_mirror_instance_summary_interval_minutes", 15) or 15)
        except (TypeError, ValueError):
            value = 15
        return max(1, min(1440, value))

    def _get_discord_screenshot_monitor_count(self) -> int:
        if not win32api:
            return 0
        try:
            return len(win32api.EnumDisplayMonitors(None, None))
        except (AttributeError, TypeError, win32api.error):
            return 0

    def _discord_log_mirror_should_capture_all_monitors(self) -> bool:
        return bool(self.settings.get("discord_log_mirror_screenshot_all_monitors", False)) and (
            self._get_discord_screenshot_monitor_count() > 1
        )

    def _get_discord_screenshot_virtual_bounds(self) -> Optional[tuple[int, int, int, int]]:
        if not win32api or not win32con:
            return None
        try:
            left = int(win32api.GetSystemMetrics(getattr(win32con, "SM_XVIRTUALSCREEN", 76)))
            top = int(win32api.GetSystemMetrics(getattr(win32con, "SM_YVIRTUALSCREEN", 77)))
            width = int(win32api.GetSystemMetrics(getattr(win32con, "SM_CXVIRTUALSCREEN", 78)))
            height = int(win32api.GetSystemMetrics(getattr(win32con, "SM_CYVIRTUALSCREEN", 79)))
        except (AttributeError, TypeError, ValueError, win32api.error):
            return None
        if width <= 0 or height <= 0:
            return None
        return left, top, left + width, top + height

    def _get_discord_screenshot_current_monitor_bounds(self) -> Optional[tuple[int, int, int, int]]:
        if not win32api or not win32gui:
            return None
        try:
            hwnd = int(self.root.winfo_id())
            monitor_handle = win32api.MonitorFromWindow(
                hwnd,
                getattr(win32con, "MONITOR_DEFAULTTONEAREST", 2),
            )
            monitor_info = win32api.GetMonitorInfo(monitor_handle)
        except (AttributeError, TypeError, ValueError, tk.TclError, win32api.error):
            return None

        monitor_bounds = monitor_info.get("Monitor")
        if not monitor_bounds or len(monitor_bounds) != 4:
            return None
        return (
            int(monitor_bounds[0]),
            int(monitor_bounds[1]),
            int(monitor_bounds[2]),
            int(monitor_bounds[3]),
        )

    def _get_discord_screenshot_bounds(self) -> Optional[tuple[int, int, int, int]]:
        if self._discord_log_mirror_should_capture_all_monitors():
            virtual_bounds = self._get_discord_screenshot_virtual_bounds()
            if virtual_bounds is not None:
                return virtual_bounds
        current_monitor_bounds = self._get_discord_screenshot_current_monitor_bounds()
        if current_monitor_bounds is not None:
            return current_monitor_bounds
        return self._get_discord_screenshot_virtual_bounds()

    def _discord_log_mirror_cancel_screenshot(self) -> None:
        after_id = self._discord_log_mirror_screenshot_after_id
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._discord_log_mirror_screenshot_after_id = None
        self._discord_log_mirror_screenshot_in_progress = False

    def _discord_log_mirror_schedule_screenshot(self, reset: bool = False) -> None:
        if reset:
            self._discord_log_mirror_cancel_screenshot()
        if self._discord_log_mirror_screenshot_after_id is not None:
            return
        if not self.settings.get("discord_log_mirror_enabled", False):
            return
        if not self._is_valid_discord_webhook_url(self._get_discord_log_mirror_webhook_url()):
            return
        interval_minutes = self._get_discord_log_mirror_screenshot_interval_minutes()
        if interval_minutes <= 0:
            return
        try:
            self._discord_log_mirror_screenshot_after_id = self.root.after(
                interval_minutes * 60 * 1000,
                self._discord_log_mirror_send_screenshot,
            )
        except tk.TclError:
            self._discord_log_mirror_screenshot_after_id = None

    def _discord_log_mirror_cancel_instance_summary(self) -> None:
        after_id = self._discord_log_mirror_instance_summary_after_id
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._discord_log_mirror_instance_summary_after_id = None
        self._discord_log_mirror_instance_summary_in_progress = False

    def _discord_log_mirror_schedule_instance_summary(self, reset: bool = False) -> None:
        if reset:
            self._discord_log_mirror_cancel_instance_summary()
        if self._discord_log_mirror_instance_summary_after_id is not None:
            return
        if not self.settings.get("discord_log_mirror_enabled", False):
            return
        if not self.settings.get("discord_log_mirror_instance_summary_enabled", False):
            return
        if not self._is_valid_discord_webhook_url(self._get_discord_log_mirror_webhook_url()):
            return
        interval_minutes = self._get_discord_log_mirror_instance_summary_interval_minutes()
        try:
            self._discord_log_mirror_instance_summary_after_id = self.root.after(
                interval_minutes * 60 * 1000,
                self._discord_log_mirror_instance_summary_tick,
            )
        except tk.TclError:
            self._discord_log_mirror_instance_summary_after_id = None

    def _discord_log_mirror_instance_summary_tick(self) -> None:
        self._discord_log_mirror_instance_summary_after_id = None
        if self._discord_log_mirror_instance_summary_in_progress:
            self._discord_log_mirror_schedule_instance_summary()
            return
        self._send_discord_log_mirror_instance_summary(parent=None, manual=False)

    def _discord_log_mirror_poll(self) -> None:
        self._discord_log_mirror_after_id = None
        if not self.settings.get("discord_log_mirror_enabled", False):
            return
        if not self._is_valid_discord_webhook_url(self._get_discord_log_mirror_webhook_url()):
            return
        if self._discord_log_mirror_in_progress:
            self._discord_log_mirror_schedule()
            return

        entries, total = self.console_output.get_entries_since(self._discord_log_mirror_last_index)
        self._discord_log_mirror_last_index = int(total)
        filtered_entries = self._filter_discord_log_mirror_entries(entries)

        if filtered_entries:
            self._discord_log_mirror_in_progress = True
            threading.Thread(
                target=self._discord_log_mirror_send_entries,
                args=(filtered_entries,),
                daemon=True,
                name="discord-log-mirror",
            ).start()

    def _discord_log_mirror_send_screenshot(self) -> None:
        self._discord_log_mirror_screenshot_after_id = None
        if self._discord_log_mirror_screenshot_in_progress:
            self._discord_log_mirror_schedule_screenshot()
            return
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self.settings.get("discord_log_mirror_enabled", False) or not self._is_valid_discord_webhook_url(webhook_url):
            self._discord_log_mirror_cancel_screenshot()
            return
        if self._get_discord_log_mirror_screenshot_interval_minutes() <= 0:
            self._discord_log_mirror_cancel_screenshot()
            return

        self._discord_log_mirror_screenshot_in_progress = True

        def worker() -> None:
            try:
                screenshot_path = self._capture_discord_monitor_screenshot()
                if screenshot_path is None:
                    self._discord_log_mirror_last_error = "Could not capture screenshot."
                    return
                try:
                    ok, error = self._post_discord_webhook_file(
                        webhook_url,
                        "FRAM screenshot",
                        screenshot_path,
                        "fram_screenshot.png",
                    )
                    if ok:
                        self._discord_log_mirror_last_error = ""
                    else:
                        self._discord_log_mirror_last_error = error
                finally:
                    try:
                        screenshot_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            finally:
                self._discord_log_mirror_screenshot_in_progress = False
                try:
                    self.root.after(0, self._discord_log_mirror_schedule_screenshot)
                except (RuntimeError, tk.TclError):
                    pass

        threading.Thread(target=worker, daemon=True, name="discord-log-mirror-screenshot").start()

    def _capture_discord_monitor_screenshot(self) -> Optional[Path]:
        if platform.system() != "Windows":
            return None
        try:
            import win32ui
        except ImportError:
            return None

        bounds = self._get_discord_screenshot_bounds()
        if bounds is None:
            return None

        left, top, right, bottom = bounds
        width = max(1, int(right - left))
        height = max(1, int(bottom - top))
        temp_file = tempfile.NamedTemporaryFile(prefix="fram_screenshot_", suffix=".png", delete=False)
        screenshot_path = Path(temp_file.name)
        temp_file.close()

        desktop_hwnd = None
        screen_dc = None
        source_dc = None
        memory_dc = None
        bitmap = None
        try:
            desktop_hwnd = win32gui.GetDesktopWindow()
            screen_dc = win32gui.GetWindowDC(desktop_hwnd)
            source_dc = win32ui.CreateDCFromHandle(screen_dc)
            memory_dc = source_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(source_dc, width, height)
            memory_dc.SelectObject(bitmap)
            copy_flags = win32con.SRCCOPY | getattr(win32con, "CAPTUREBLT", 0x40000000)
            memory_dc.BitBlt((0, 0), (width, height), source_dc, (int(left), int(top)), copy_flags)
            if save_hbitmap_as_png(int(bitmap.GetHandle()), screenshot_path):
                return screenshot_path
            try:
                screenshot_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        except (win32gui.error, win32ui.error, OSError):
            try:
                screenshot_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        finally:
            if bitmap is not None:
                try:
                    win32gui.DeleteObject(bitmap.GetHandle())
                except win32gui.error:
                    pass
            if memory_dc is not None:
                try:
                    memory_dc.DeleteDC()
                except win32ui.error:
                    pass
            if source_dc is not None:
                try:
                    source_dc.DeleteDC()
                except win32ui.error:
                    pass
            if screen_dc is not None and desktop_hwnd is not None:
                try:
                    win32gui.ReleaseDC(desktop_hwnd, screen_dc)
                except win32gui.error:
                    pass

    def _parse_discord_log_mirror_terms(self, value: Any) -> list[str]:
        raw_text = str(value or "").strip()
        if not raw_text:
            return []
        return [
            term.strip().lower()
            for term in re.split(r"[\n,]", raw_text)
            if term.strip()
        ]

    def _filter_discord_log_mirror_entries(self, entries: list[str]) -> list[str]:
        include_stdout = bool(self.settings.get("discord_log_mirror_include_stdout", True))
        include_stderr = bool(self.settings.get("discord_log_mirror_include_stderr", True))
        include_terms = self._parse_discord_log_mirror_terms(
            self.settings.get("discord_log_mirror_include_filter", "")
        )
        exclude_terms = self._parse_discord_log_mirror_terms(
            self.settings.get("discord_log_mirror_exclude_filter", "")
        )
        redact_sensitive = bool(self.settings.get("discord_log_mirror_redact_sensitive", True))

        filtered_entries = []
        for entry in entries:
            if "[STDOUT]" in entry and not include_stdout:
                continue
            if "[STDERR]" in entry and not include_stderr:
                continue
            searchable_entry = entry.lower()
            if include_terms and not any(term in searchable_entry for term in include_terms):
                continue
            if exclude_terms and any(term in searchable_entry for term in exclude_terms):
                continue
            filtered_entries.append(redact_sensitive_console_text(entry) if redact_sensitive else entry)

        return filtered_entries

    def _discord_log_mirror_send_entries(self, entries: list[str]) -> None:
        try:
            webhook_url = self._get_discord_log_mirror_webhook_url()
            if not self._is_valid_discord_webhook_url(webhook_url):
                self._discord_log_mirror_last_error = "Invalid Discord webhook URL."
                return
            ping_user_id = self._get_discord_log_mirror_ping_user_id()
            should_ping_batch = self._discord_log_mirror_should_ping_entries(entries)
            ping_sent = False
            for message in self._build_discord_log_mirror_messages(entries):
                message_ping_user_id = ping_user_id if should_ping_batch and not ping_sent else ""
                ok, error = self._post_discord_webhook_message(
                    webhook_url,
                    message,
                    ping_user_id=message_ping_user_id,
                )
                if not ok:
                    self._discord_log_mirror_last_error = error
                    return
                if message_ping_user_id:
                    ping_sent = True
            self._discord_log_mirror_last_error = ""
        finally:
            self._discord_log_mirror_in_progress = False
            try:
                self.root.after(0, self._discord_log_mirror_schedule)
            except (RuntimeError, tk.TclError):
                pass

    def _format_discord_summary_text(self, value: Any, fallback: str = "n/a", max_length: int = 90) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if not text:
            return fallback
        if len(text) > max_length:
            return text[: max(0, max_length - 3)] + "..."
        return text

    def _format_discord_memory_value(self, value: Any) -> str:
        try:
            byte_count = int(value)
        except (TypeError, ValueError):
            return "n/a"
        if byte_count <= 0:
            return "n/a"
        return f"{byte_count / (1024 * 1024):.1f} MB"

    def _format_discord_embed_value(self, value: Any, fallback: str = "n/a", max_length: int = 1024) -> str:
        text = str(value or "").strip()
        if not text:
            text = fallback
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > max_length:
            return text[: max(0, max_length - 3)] + "..."
        return text

    def _extract_account_from_window_title(self, title_text: Any) -> str:
        text = str(title_text or "").strip()
        if not text:
            return ""

        accounts = getattr(self.manager, "accounts", {})
        account_lookup = {}
        if isinstance(accounts, dict):
            account_lookup = {
                str(username).strip().lower(): str(username).strip()
                for username in accounts.keys()
                if str(username).strip()
            }

        exact_match = account_lookup.get(text.lower())
        if exact_match:
            return exact_match

        for pattern in (r"([A-Za-z0-9_]{3,})@", r"@([A-Za-z0-9_]{3,})"):
            for match in re.finditer(pattern, text):
                candidate = str(match.group(1) or "").strip()
                if not candidate:
                    continue
                resolved = account_lookup.get(candidate.lower())
                if resolved:
                    return resolved
                return candidate
        return ""

    def _format_discord_instance_place(self, context: dict[str, Any], resolved_place_id: str) -> str:
        mode = str(context.get("mode", "home") or "home").strip().lower()
        context_place_id = str(context.get("game_id", "") or "").strip()
        place_id = str(resolved_place_id or "").strip() or context_place_id
        if mode == "home":
            return "Home"
        if mode == "join_user":
            return f"Join User {context_place_id}" if context_place_id else "Join User"
        if place_id:
            return f"Place {place_id}"
        return "Unknown"

    def _format_discord_instance_auto_rejoin(self, username: str) -> str:
        normalized_username = str(username or "").strip()
        if not normalized_username or normalized_username == "Unknown":
            return "Unknown"

        session = self._get_auto_rejoin_session_snapshot(normalized_username)
        if isinstance(session, dict):
            enabled = bool(session.get("auto_rejoin", False))
            try:
                attempts = int(session.get("rejoin_attempts", 0) or 0)
            except (TypeError, ValueError):
                attempts = 0
            try:
                max_attempts = int(session.get("max_rejoin_attempts", 0) or 0)
            except (TypeError, ValueError):
                max_attempts = 0
            attempt_text = f"{attempts}/{max_attempts}" if max_attempts > 0 else str(attempts)
            if enabled:
                status = f"On ({attempt_text})"
                if bool(session.get("rejoin_in_progress", False)):
                    status = f"{status}, rejoining"
                return status
            disabled_reason = self._format_discord_summary_text(session.get("disabled_reason", ""), fallback="", max_length=40)
            return f"Off ({disabled_reason})" if disabled_reason else "Off"

        return "On" if self._get_effective_auto_rejoin_enabled(normalized_username) else "Off"

    def _get_discord_active_instance_rows(self) -> list[dict[str, Any]]:
        target_executables = set(self.ROBLOX_CLIENT_EXECUTABLES)
        snapshot = self._get_tracked_window_snapshot(target_executables, use_cache=False)
        pid_to_image = dict(snapshot.get("pid_to_image", {}) or {})
        pid_to_title = dict(snapshot.get("pid_to_title", {}) or {})
        pid_to_hung = dict(snapshot.get("pid_to_hung", {}) or {})
        pid_values = {int(pid_value) for pid_value in pid_to_image.keys()}
        pid_to_place_id = self._query_pid_place_id_map(
            target_executables,
            pid_values=pid_values,
            allow_log_fallback=False,
            use_cache=False,
        )

        with self._pid_account_lock:
            pid_account_map = dict(self._pid_account_map)
            pid_launch_context_map = dict(self._pid_launch_context_map)

        rows = []
        for pid_value in sorted(pid_values):
            title_text = str(pid_to_title.get(pid_value, "") or "").strip()
            mapped_username = str(pid_account_map.get(pid_value, "") or "").strip()
            username = mapped_username or self._extract_account_from_window_title(title_text) or "Unknown"
            context = self._normalize_launch_context(pid_launch_context_map.get(pid_value))
            memory_bytes = self._memtrim_get_working_set(pid_value) if platform.system() == "Windows" else None
            rows.append(
                {
                    "pid": pid_value,
                    "image": str(pid_to_image.get(pid_value, "") or "").strip() or "Roblox",
                    "account": username,
                    "status": "Not Responding" if pid_to_hung.get(pid_value) else "Running",
                    "place": self._format_discord_instance_place(
                        context,
                        str(pid_to_place_id.get(pid_value, "") or "").strip(),
                    ),
                    "memory_bytes": memory_bytes,
                    "auto_rejoin": self._format_discord_instance_auto_rejoin(username),
                    "title": title_text,
                }
            )
        return rows

    def _build_discord_active_instance_summary_embed(self) -> dict[str, Any]:
        rows = self._get_discord_active_instance_rows()
        not_responding_count = sum(1 for row in rows if str(row.get("status", "")).lower() == "not responding")
        total_memory_bytes = 0
        for row in rows:
            try:
                total_memory_bytes += int(row.get("memory_bytes") or 0)
            except (TypeError, ValueError):
                continue
        monitored_count = sum(
            1
            for row in rows
            if str(row.get("auto_rejoin", "")).strip().lower().startswith("on")
        )

        if not rows:
            embed_color = 0x5865F2
            description = "No active Roblox client instances detected."
        elif not_responding_count > 0:
            embed_color = 0xF59E0B
            description = "Active Roblox clients were found, with at least one not responding."
        else:
            embed_color = 0x22C55E
            description = "Active Roblox clients are running normally."

        fields: list[dict[str, Any]] = [
            {
                "name": "Overview",
                "value": self._format_discord_embed_value(
                    (
                        f"Active: **{len(rows)}**\n"
                        f"Not responding: **{not_responding_count}**\n"
                        f"Total RAM: **{self._format_discord_memory_value(total_memory_bytes)}**"
                    )
                ),
                "inline": True,
            },
            {
                "name": "Automation",
                "value": self._format_discord_embed_value(
                    (
                        f"NoClient: **{'On' if self.settings.get('roblox_headless_mode_enabled', False) else 'Off'}**\n"
                        f"Memory Trim: **{'On' if self.settings.get('auto_memory_trim_enabled', False) else 'Off'}**\n"
                        f"Memory Kill: **{'On' if self.settings.get('auto_memory_kill_enabled', False) else 'Off'}**\n"
                        f"Anti-AFK: **{'On' if self.settings.get('anti_afk_enabled', False) else 'Off'}**\n"
                        f"Title Rename: **{'On' if self._get_rename_client_titles_enabled() else 'Off'}**"
                    )
                ),
                "inline": True,
            },
            {
                "name": "Auto Rejoin",
                "value": self._format_discord_embed_value(
                    (
                        f"Force: **{'On' if self._is_auto_rejoin_force_enabled() else 'Off'}**\n"
                        f"Monitored: **{monitored_count}**\n"
                        f"Delay: **{self._get_auto_rejoin_delay_seconds()}s** | "
                        f"Max attempts: **{self._get_auto_rejoin_max_attempts()}**"
                    )
                ),
                "inline": True,
            },
        ]

        max_instance_fields = 12
        for row in rows[:max_instance_fields]:
            account = self._format_discord_summary_text(row.get("account"), fallback="Unknown", max_length=48)
            fields.append(
                {
                    "name": f"{account} - {row.get('status')}",
                    "value": self._format_discord_embed_value(
                        (
                            f"PID: `{row.get('pid')}`\n"
                            f"Place: `{self._format_discord_summary_text(row.get('place'), fallback='Unknown', max_length=80)}`\n"
                            f"RAM: `{self._format_discord_memory_value(row.get('memory_bytes'))}`\n"
                            f"Rejoin: `{row.get('auto_rejoin')}`"
                        )
                    ),
                    "inline": True,
                }
            )

        if len(rows) > max_instance_fields:
            fields.append(
                {
                    "name": "More Instances",
                    "value": f"{len(rows) - max_instance_fields} additional Roblox client(s) not shown.",
                    "inline": False,
                }
            )

        embed = {
            "title": "FRAM Active Instance Summary",
            "description": description,
            "color": embed_color,
            "fields": fields,
            "footer": {"text": "FRAM Discord Monitor"},
            "timestamp": datetime.now().astimezone().isoformat(),
        }
        if self.settings.get("discord_log_mirror_redact_sensitive", True):
            embed["description"] = redact_sensitive_console_text(str(embed.get("description", "")))
            for field in fields:
                field["name"] = redact_sensitive_console_text(str(field.get("name", "")))
                field["value"] = redact_sensitive_console_text(str(field.get("value", "")))
        return embed

    def _send_discord_log_mirror_instance_summary(
        self,
        parent: Optional[tk.Misc] = None,
        manual: bool = True,
    ) -> None:
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self._is_valid_discord_webhook_url(webhook_url):
            if parent is not None:
                messagebox.showerror("Discord", "Enter a valid Discord webhook URL first.", parent=parent)
            return
        if not manual:
            if not self.settings.get("discord_log_mirror_enabled", False):
                return
            if not self.settings.get("discord_log_mirror_instance_summary_enabled", False):
                return
        if self._discord_log_mirror_instance_summary_in_progress:
            if manual and parent is not None:
                messagebox.showinfo("Discord", "An active instance summary is already being sent.", parent=parent)
            return

        self._discord_log_mirror_instance_summary_in_progress = True

        def worker() -> None:
            ok = False
            error = ""
            try:
                embed = self._build_discord_active_instance_summary_embed()
                ok, error = self._post_discord_webhook_message(webhook_url, "", embeds=[embed])
                self._discord_log_mirror_last_error = "" if ok else error
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError, tk.TclError) as exc:
                error = str(exc)
                self._discord_log_mirror_last_error = error

            def done() -> None:
                self._discord_log_mirror_instance_summary_in_progress = False
                if manual and parent is not None:
                    try:
                        dialog_parent = parent if parent.winfo_exists() else self.root
                    except tk.TclError:
                        dialog_parent = self.root
                    if ok:
                        messagebox.showinfo("Discord", "Active instance summary sent.", parent=dialog_parent)
                    else:
                        messagebox.showerror("Discord", f"Active instance summary failed:\n{error}", parent=dialog_parent)
                if not manual:
                    self._discord_log_mirror_schedule_instance_summary()

            try:
                self.root.after(0, done)
            except (RuntimeError, tk.TclError):
                self._discord_log_mirror_instance_summary_in_progress = False

        threading.Thread(target=worker, daemon=True, name="discord-log-mirror-instance-summary").start()

    def _get_discord_log_mirror_ping_user_id(self) -> str:
        return re.sub(r"\D", "", str(self.settings.get("discord_log_mirror_ping_user_id", "") or ""))

    def _discord_log_mirror_should_ping_entries(self, entries: list[str]) -> bool:
        if not self._get_discord_log_mirror_ping_user_id():
            return False
        if not bool(self.settings.get("discord_log_mirror_ping_only_errors", True)):
            return True
        for entry in entries:
            entry_text = str(entry or "").lower()
            if "[stderr]" in entry_text or "[error]" in entry_text:
                return True
            if re.search(r"\b(error|failed|exception|traceback|warning)\b", entry_text):
                return True
        return False

    def _build_discord_log_mirror_messages(self, entries: list[str]) -> list[str]:
        max_lines = self._get_discord_log_mirror_max_lines_per_message()
        messages = []
        current_lines = []
        current_length = 0
        max_content_length = 1850

        for entry in entries:
            normalized_entry = str(entry or "").replace("```", "` ` `")
            projected_length = current_length + len(normalized_entry) + 1
            if current_lines and (len(current_lines) >= max_lines or projected_length > max_content_length):
                messages.append("```text\n" + "\n".join(current_lines) + "\n```")
                current_lines = []
                current_length = 0
            if len(normalized_entry) > max_content_length:
                normalized_entry = normalized_entry[: max_content_length - 3] + "..."
            current_lines.append(normalized_entry)
            current_length += len(normalized_entry) + 1

        if current_lines:
            messages.append("```text\n" + "\n".join(current_lines) + "\n```")

        return messages

    def _get_discord_webhook_session(self) -> requests.Session:
        if self._discord_webhook_session is not None:
            return self._discord_webhook_session

        with self._discord_webhook_session_lock:
            if self._discord_webhook_session is None:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=2, pool_maxsize=4, max_retries=0)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                session.headers.update({"User-Agent": "FRAM"})
                self._discord_webhook_session = session

        session = self._discord_webhook_session
        if session is None:
            raise RuntimeError("Discord webhook session was not initialized.")
        return session

    def _close_discord_webhook_session(self) -> None:
        with self._discord_webhook_session_lock:
            if self._discord_webhook_session is not None:
                self._discord_webhook_session.close()
            self._discord_webhook_session = None

    def _post_discord_webhook_message(
        self,
        webhook_url: str,
        content: str = "",
        ping_user_id: str = "",
        embeds: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[bool, str]:
        normalized_ping_user_id = re.sub(r"\D", "", str(ping_user_id or ""))
        message_content = str(content or "")
        allowed_mentions = {"parse": []}
        if normalized_ping_user_id:
            message_content = f"<@{normalized_ping_user_id}> {message_content}".strip()
            allowed_mentions = {"users": [normalized_ping_user_id]}
        payload = {
            "username": "FRAM Logs",
            "allowed_mentions": allowed_mentions,
        }
        if message_content:
            payload["content"] = message_content
        if embeds:
            payload["embeds"] = embeds[:10]
        if "content" not in payload and "embeds" not in payload:
            payload["content"] = "FRAM"
        try:
            with self._discord_webhook_session_lock:
                response = self._get_discord_webhook_session().post(
                    webhook_url,
                    json=payload,
                    timeout=10,
                )
            if response.status_code in (200, 204):
                return True, ""
            return False, f"Discord returned HTTP {response.status_code}."
        except requests.exceptions.RequestException as exc:
            return False, str(exc)

    def _post_discord_webhook_file(
        self,
        webhook_url: str,
        content: str,
        file_path: Path,
        file_name: str,
    ) -> tuple[bool, str]:
        payload = {
            "content": content,
            "username": "FRAM Logs",
            "allowed_mentions": {"parse": []},
        }
        content_type = "image/png" if file_name.lower().endswith(".png") else "application/octet-stream"
        try:
            with file_path.open("rb") as file_handle:
                with self._discord_webhook_session_lock:
                    response = self._get_discord_webhook_session().post(
                        webhook_url,
                        data={"payload_json": json.dumps(payload)},
                        files={"file": (file_name, file_handle, content_type)},
                        timeout=20,
                    )
            if response.status_code in (200, 204):
                return True, ""
            return False, f"Discord returned HTTP {response.status_code}."
        except (OSError, requests.exceptions.RequestException) as exc:
            return False, str(exc)

    def _discord_log_mirror_send_startup_notice(self) -> None:
        if self._discord_log_mirror_sent_startup_notice:
            return
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self._is_valid_discord_webhook_url(webhook_url):
            return
        self._discord_log_mirror_sent_startup_notice = True

        def worker() -> None:
            self._post_discord_webhook_message(webhook_url, "FRAM is connected.")

        threading.Thread(target=worker, daemon=True, name="discord-log-mirror-startup").start()

    def _send_discord_log_mirror_test(self, parent: tk.Misc) -> None:
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self._is_valid_discord_webhook_url(webhook_url):
            messagebox.showerror("Discord", "Enter a valid Discord webhook URL first.", parent=parent)
            return

        def worker() -> None:
            ok, error = self._post_discord_webhook_message(webhook_url, "FRAM test message.")

            def done() -> None:
                try:
                    dialog_parent = parent if parent.winfo_exists() else self.root
                except tk.TclError:
                    dialog_parent = self.root
                if ok:
                    messagebox.showinfo("Discord", "Test message sent.", parent=dialog_parent)
                else:
                    messagebox.showerror("Discord", f"Test message failed:\n{error}", parent=dialog_parent)

            try:
                self.root.after(0, done)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=worker, daemon=True, name="discord-log-mirror-test").start()

    def _send_discord_log_mirror_test_screenshot(self, parent: tk.Misc) -> None:
        webhook_url = self._get_discord_log_mirror_webhook_url()
        if not self._is_valid_discord_webhook_url(webhook_url):
            messagebox.showerror("Discord", "Enter a valid Discord webhook URL first.", parent=parent)
            return

        def worker() -> None:
            screenshot_path = self._capture_discord_monitor_screenshot()
            if screenshot_path is None:
                ok = False
                error = "Could not capture a screenshot."
            else:
                try:
                    ok, error = self._post_discord_webhook_file(
                        webhook_url,
                        "FRAM test screenshot",
                        screenshot_path,
                        "fram_screenshot.png",
                    )
                finally:
                    try:
                        screenshot_path.unlink(missing_ok=True)
                    except OSError:
                        pass

            def done() -> None:
                try:
                    dialog_parent = parent if parent.winfo_exists() else self.root
                except tk.TclError:
                    dialog_parent = self.root
                if ok:
                    messagebox.showinfo("Discord", "Test screenshot sent.", parent=dialog_parent)
                else:
                    messagebox.showerror("Discord", f"Test screenshot failed:\n{error}", parent=dialog_parent)

            try:
                self.root.after(0, done)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=worker, daemon=True, name="discord-log-mirror-test-screenshot").start()

    def handle_app_close(self):
        monitor = getattr(self, "_auto_rejoin_monitor", None)
        if monitor is not None:
            try:
                monitor.stop()
            except Exception:
                pass

        try:
            self._auto_relaunch_stop()
        except Exception:
            pass

        try:
            self._auto_memory_trim_stop()
        except Exception:
            pass

        try:
            self._auto_memory_kill_stop()
        except Exception:
            pass

        try:
            self._anti_afk_stop()
        except (AttributeError, RuntimeError, tk.TclError):
            pass

        try:
            self._cancel_anti_afk_next_label_update()
        except (AttributeError, RuntimeError, tk.TclError):
            pass

        try:
            self._discord_log_mirror_stop()
        except (RuntimeError, tk.TclError):
            pass

        try:
            self._cancel_roblox_headless_pass()
        except Exception:
            pass

        try:
            self._cancel_keep_clients_arranged_check()
        except Exception:
            pass

        for after_id_name in (
            "_game_name_after_id",
            "_game_name_label_after_id",
        ):
            after_id = getattr(self, after_id_name, None)
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
            setattr(self, after_id_name, None)

        for pending_after_id in list(getattr(self, "_settings_save_after_ids", {}).values()):
            try:
                self.root.after_cancel(pending_after_id)
            except Exception:
                pass
        self._settings_save_after_ids = {}

        try:
            if self._http_session is not None:
                self._http_session.close()
        except Exception:
            pass
        self._http_session = None

        try:
            self._close_discord_webhook_session()
        except Exception:
            pass

        try:
            RobloxAPI.close_http_session()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass


    def open_global_settings_editor(self):
        """Open the Roblox Settings window."""
        if self.global_settings_window and self.global_settings_window.winfo_exists():
            self.global_settings_window.deiconify()
            self.global_settings_window.lift()
            self.global_settings_window.focus_force()
            return

        self.global_settings_window = tk.Toplevel(self.root)
        self.global_settings_window.title("Roblox Settings")
        self.global_settings_window.geometry("980x700")
        self.global_settings_window.minsize(860, 560)
        self.global_settings_window.configure(bg=self.BG_DARK)
        self.global_settings_window.resizable(True, True)
        self.global_settings_window.transient(self.root)
        self.global_settings_window.grab_set()
        self.register_toplevel(self.global_settings_window)
        if self.settings.get("enable_topmost", False):
            self.global_settings_window.attributes("-topmost", True)

        settings_path = os.path.expandvars(r"%LOCALAPPDATA%\Roblox\GlobalBasicSettings_13.xml")
        main = ttk.Frame(self.global_settings_window, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=20, pady=15)

        ttk.Label(main, text="Roblox Settings", style="Dark.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            main,
            text=f"Editing: {settings_path}",
            style="Dark.TLabel",
            font=("Segoe UI", 9),
            foreground=self.FG_MUTED if hasattr(self, "FG_MUTED") else "#888888",
        ).pack(anchor="w", pady=(0, 8))

        status_var = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=status_var, style="Dark.TLabel").pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True, pady=(0, 10))

        def build_field_specs() -> dict[str, tuple[dict[str, object], ...]]:
            return {
                "Graphics": (
                    {"key": "GraphicsQualityLevel", "label": "Graphics Quality Level", "xml_name": "GraphicsQualityLevel", "xml_type": "int", "control": "scale", "default": 21, "minimum": 1.0, "maximum": 21.0, "display": "int"},
                    {"key": "GraphicsOptimizationMode", "label": "Graphics Optimization Mode", "xml_name": "GraphicsOptimizationMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Auto", 0), ("Performance", 1), ("Quality", 2))},
                    {"key": "MaxQualityEnabled", "label": "Max Quality Enabled", "xml_name": "MaxQualityEnabled", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "VignetteEnabled", "label": "Vignette Enabled", "xml_name": "VignetteEnabled", "xml_type": "bool", "control": "bool", "default": True},
                    {"key": "FramerateCap", "label": "Framerate Cap", "xml_name": "FramerateCap", "xml_type": "int", "control": "spinbox", "default": 120, "minimum": 0, "maximum": 999},
                    {"key": "Fullscreen", "label": "Fullscreen", "xml_name": "Fullscreen", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "StartMaximized", "label": "Start Maximized", "xml_name": "StartMaximized", "xml_type": "bool", "control": "bool", "default": True},
                ),
                "Audio": (
                    {"key": "MasterVolume", "label": "Master Volume", "xml_name": "MasterVolume", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                    {"key": "PartyVoiceVolume", "label": "Party Voice Volume", "xml_name": "PartyVoiceVolume", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                ),
                "Controls": (
                    {"key": "ComputerMovementMode", "label": "Computer Movement Mode", "xml_name": "ComputerMovementMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Default", 0), ("Keyboard+Mouse", 1), ("Click To Move", 2))},
                    {"key": "ControlMode", "label": "Control Mode", "xml_name": "ControlMode", "xml_type": "token", "control": "combo", "default": 1, "options": (("Mouse Lock", 0), ("Classic", 1), ("Dynamic", 2))},
                    {"key": "MouseSensitivity", "label": "Mouse Sensitivity", "xml_name": "MouseSensitivity", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "MouseSensitivityFirstPersonX", "label": "Mouse Sensitivity First Person X", "xml_name": "MouseSensitivityFirstPerson", "xml_type": "Vector2", "component": "X", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "MouseSensitivityFirstPersonY", "label": "Mouse Sensitivity First Person Y", "xml_name": "MouseSensitivityFirstPerson", "xml_type": "Vector2", "component": "Y", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "MouseSensitivityThirdPersonX", "label": "Mouse Sensitivity Third Person X", "xml_name": "MouseSensitivityThirdPerson", "xml_type": "Vector2", "component": "X", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "MouseSensitivityThirdPersonY", "label": "Mouse Sensitivity Third Person Y", "xml_name": "MouseSensitivityThirdPerson", "xml_type": "Vector2", "component": "Y", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "GamepadCameraSensitivity", "label": "Gamepad Camera Sensitivity", "xml_name": "GamepadCameraSensitivity", "xml_type": "float", "control": "scale", "default": 1.0, "minimum": 0.0, "maximum": 4.0, "display": "float"},
                    {"key": "HapticStrength", "label": "Haptic Strength", "xml_name": "HapticStrength", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                ),
                "Camera": (
                    {"key": "CameraMode", "label": "Camera Mode", "xml_name": "CameraMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Classic", 0), ("Follow", 1))},
                    {"key": "CameraYInverted", "label": "Camera Y Inverted", "xml_name": "CameraYInverted", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "ComputerCameraMovementMode", "label": "Computer Camera Movement Mode", "xml_name": "ComputerCameraMovementMode", "xml_type": "token", "control": "combo", "default": 0, "options": (("Default", 0), ("Follow", 1), ("Classic", 2), ("Orbital", 3), ("Camera Toggle", 4))},
                ),
                "Accessibility": (
                    {"key": "ReducedMotion", "label": "Reduced Motion", "xml_name": "ReducedMotion", "xml_type": "bool", "control": "bool", "default": True},
                    {"key": "ReadAloud", "label": "Read Aloud", "xml_name": "ReadAloud", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "AllTutorialsDisabled", "label": "All Tutorials Disabled", "xml_name": "AllTutorialsDisabled", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "PreferredTextSize", "label": "Preferred Text Size", "xml_name": "PreferredTextSize", "xml_type": "token", "control": "combo", "default": 1, "options": (("Small", 0), ("Normal", 1), ("Large", 2), ("Extra Large", 3))},
                    {"key": "PreferredTransparency", "label": "Preferred Transparency", "xml_name": "PreferredTransparency", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "percent"},
                    {"key": "PlayerNamesEnabled", "label": "Player Names Enabled", "xml_name": "PlayerNamesEnabled", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "PerformanceStatsVisible", "label": "Performance Stats Visible", "xml_name": "PerformanceStatsVisible", "xml_type": "bool", "control": "bool", "default": False},
                ),
                "Chat": (
                    {"key": "ChatVisible", "label": "Chat Visible", "xml_name": "ChatVisible", "xml_type": "bool", "control": "bool", "default": True},
                    {"key": "ChatTranslationEnabled", "label": "Chat Translation Enabled", "xml_name": "ChatTranslationEnabled", "xml_type": "bool", "control": "bool", "default": True},
                    {"key": "ChatTranslationToggleEnabled", "label": "Chat Translation Toggle Enabled", "xml_name": "ChatTranslationToggleEnabled", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "ChatTranslationLocale", "label": "Chat Translation Locale", "xml_name": "ChatTranslationLocale", "xml_type": "string", "control": "entry", "default": "en_us"},
                ),
                "Display": (
                    {"key": "PlayerListVisible", "label": "Player List Visible", "xml_name": "PlayerListVisible", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "BadgeVisible", "label": "Badge Visible", "xml_name": "BadgeVisible", "xml_type": "bool", "control": "bool", "default": False},
                    {"key": "PlayerHeight", "label": "Player Height", "xml_name": "PlayerHeight", "xml_type": "float", "control": "scale", "default": 0.0, "minimum": 0.0, "maximum": 1.0, "display": "float"},
                ),
            }

        def format_float_value(value: float) -> str:
            return f"{float(value):.6g}"

        def format_scale_value(field_spec: dict[str, object], value: float) -> str:
            display_mode = str(field_spec.get("display") or "float")
            if display_mode == "percent":
                return f"{int(round(float(value) * 100))}%"
            if display_mode == "int":
                return str(int(round(float(value))))
            return f"{float(value):.2f}"

        def is_roblox_running() -> bool:
            if platform.system() != "Windows":
                return False
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq RobloxPlayerBeta.exe"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    **subprocess_no_window_kwargs(),
                )
            except Exception:
                return False
            return bool(result.returncode == 0 and "RobloxPlayerBeta.exe" in str(result.stdout or ""))

        def get_properties_node(root_element: object) -> object:
            item_node = root_element.find(".//Item[@class='UserGameSettings']")
            if item_node is None:
                raise ValueError("UserGameSettings item not found")
            properties_node = item_node.find("Properties")
            if properties_node is None:
                raise ValueError("Properties node not found")
            return properties_node

        def read_field_value(properties_node: object, field_spec: dict[str, object]) -> object:
            xml_name = str(field_spec.get("xml_name") or "")
            xml_type = str(field_spec.get("xml_type") or "")
            default_value = field_spec.get("default")
            if xml_type == "Vector2":
                vector_node = properties_node.find(f"Vector2[@name='{xml_name}']")
                if vector_node is None:
                    return default_value
                component_name = str(field_spec.get("component") or "")
                component_node = vector_node.find(component_name)
                if component_node is None or component_node.text is None:
                    return default_value
                return float(component_node.text.strip() or default_value)

            field_node = properties_node.find(f"{xml_type}[@name='{xml_name}']")
            if field_node is None or field_node.text is None:
                return default_value

            raw_value = field_node.text.strip()
            if xml_type == "bool":
                return raw_value.lower() == "true"
            if xml_type in {"int", "token"}:
                return int(raw_value or int(default_value or 0))
            if xml_type == "float":
                return float(raw_value or float(default_value or 0.0))
            return raw_value

        def write_field_value(properties_node: object, field_spec: dict[str, object], value: object) -> None:
            xml_name = str(field_spec.get("xml_name") or "")
            xml_type = str(field_spec.get("xml_type") or "")
            if xml_type == "Vector2":
                vector_node = properties_node.find(f"Vector2[@name='{xml_name}']")
                if vector_node is None:
                    return
                component_name = str(field_spec.get("component") or "")
                component_node = vector_node.find(component_name)
                if component_node is None:
                    return
                component_node.text = format_float_value(float(value))
                return

            field_node = properties_node.find(f"{xml_type}[@name='{xml_name}']")
            if field_node is None:
                return
            if xml_type == "bool":
                field_node.text = "true" if bool(value) else "false"
            elif xml_type in {"int", "token"}:
                field_node.text = str(int(value))
            elif xml_type == "float":
                field_node.text = format_float_value(float(value))
            else:
                field_node.text = str(value or "")

        field_specs_by_tab = build_field_specs()
        field_specs_by_key = {
            str(field_spec.get("key") or ""): field_spec
            for fields in field_specs_by_tab.values()
            for field_spec in fields
        }
        preset_values = {
            field_key: field_spec.get("default")
            for field_key, field_spec in field_specs_by_key.items()
        }
        low_preset_values = dict(preset_values)
        low_preset_values.update(
            {
                "GraphicsQualityLevel": 1,
                "GraphicsOptimizationMode": 1,
                "MaxQualityEnabled": False,
                "VignetteEnabled": False,
                "FramerateCap": 30,
                "Fullscreen": False,
                "StartMaximized": False,
                "ReducedMotion": True,
                "ChatVisible": False,
                "ChatTranslationEnabled": False,
                "ChatTranslationToggleEnabled": False,
                "PlayerNamesEnabled": False,
                "PerformanceStatsVisible": False,
                "PlayerListVisible": False,
                "BadgeVisible": False,
            }
        )
        high_preset_values = dict(preset_values)
        high_preset_values.update(
            {
                "GraphicsQualityLevel": 21,
                "GraphicsOptimizationMode": 2,
                "MaxQualityEnabled": True,
                "VignetteEnabled": True,
                "FramerateCap": 240,
                "Fullscreen": True,
                "StartMaximized": True,
                "ReducedMotion": False,
                "ChatVisible": True,
                "ChatTranslationEnabled": True,
                "PlayerNamesEnabled": True,
                "PlayerListVisible": True,
                "BadgeVisible": True,
            }
        )
        roblox_setting_presets = {
            "Low": low_preset_values,
            "Default": preset_values,
            "High": high_preset_values,
        }
        field_bindings: dict[str, dict[str, object]] = {}
        int_validator = (self.root.register(lambda proposed: proposed == "" or proposed.isdigit()), "%P")

        def update_scale_label(field_key: str) -> None:
            binding = field_bindings.get(field_key)
            if not binding:
                return
            variable = binding.get("variable")
            display_var = binding.get("display_var")
            field_spec = binding.get("field_spec")
            if variable is None or display_var is None or field_spec is None:
                return
            try:
                current_value = float(variable.get())
            except Exception:
                current_value = float(field_spec.get("default") or 0.0)
            display_var.set(format_scale_value(field_spec, current_value))

        def set_field_value(field_key: str, value: object) -> None:
            binding = field_bindings[field_key]
            field_spec = binding["field_spec"]
            control_type = str(field_spec.get("control") or "")
            variable = binding["variable"]
            if control_type == "combo":
                value_to_label = binding["value_to_label"]
                variable.set(value_to_label.get(int(value), next(iter(value_to_label.values()), "")))
                return
            if control_type == "bool":
                variable.set(bool(value))
                return
            if control_type == "spinbox":
                variable.set(str(int(value)))
                return
            if control_type == "scale":
                variable.set(float(value))
                update_scale_label(field_key)
                return
            variable.set(str(value))

        def get_field_value(field_key: str) -> object:
            binding = field_bindings[field_key]
            field_spec = binding["field_spec"]
            control_type = str(field_spec.get("control") or "")
            variable = binding["variable"]
            if control_type == "combo":
                label_to_value = binding["label_to_value"]
                current_label = str(variable.get() or "")
                if current_label not in label_to_value:
                    raise ValueError(f"{field_spec['label']} has an invalid selection.")
                return int(label_to_value[current_label])
            if control_type == "bool":
                return bool(variable.get())
            if control_type == "spinbox":
                raw_value = str(variable.get() or "").strip()
                if raw_value == "":
                    raw_value = str(int(field_spec.get("default") or 0))
                numeric_value = int(raw_value)
                minimum = int(field_spec.get("minimum") or 0)
                maximum = int(field_spec.get("maximum") or 0)
                return max(minimum, min(maximum, numeric_value))
            if control_type == "scale":
                numeric_value = float(variable.get())
                minimum = float(field_spec.get("minimum") or 0.0)
                maximum = float(field_spec.get("maximum") or 0.0)
                clamped_value = max(minimum, min(maximum, numeric_value))
                if str(field_spec.get("display") or "") == "int":
                    return int(round(clamped_value))
                return clamped_value
            return str(variable.get() or "")

        def apply_defaults() -> None:
            for field_key, field_spec in field_specs_by_key.items():
                set_field_value(field_key, field_spec.get("default"))

        def apply_preset(preset_name: str) -> None:
            values = roblox_setting_presets.get(preset_name)
            if not values:
                return
            for field_key, field_value in values.items():
                if field_key in field_bindings:
                    set_field_value(field_key, field_value)
            status_var.set(f"Applied {preset_name} preset. Click Save to write the changes.")

        presets_frame = ttk.Frame(main, style="Dark.TFrame")
        presets_frame.pack(fill="x", pady=(0, 10), before=notebook)
        presets_frame.columnconfigure(0, weight=1)
        presets_frame.columnconfigure(1, weight=1)
        presets_frame.columnconfigure(2, weight=1)

        ttk.Button(
            presets_frame,
            text="Low",
            style="Dark.TButton",
            command=lambda: apply_preset("Low"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ttk.Button(
            presets_frame,
            text="Default",
            style="Dark.TButton",
            command=lambda: apply_preset("Default"),
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Button(
            presets_frame,
            text="High",
            style="Dark.TButton",
            command=lambda: apply_preset("High"),
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        for tab_name, field_specs in field_specs_by_tab.items():
            tab = ttk.Frame(notebook, style="Dark.TFrame")
            notebook.add(tab, text=tab_name)
            tab.columnconfigure(0, weight=1)
            row_index = 0

            for field_spec in field_specs:
                field_key = str(field_spec.get("key") or "")
                row_frame = ttk.Frame(tab, style="Dark.TFrame")
                row_frame.grid(row=row_index, column=0, sticky="ew", padx=12, pady=(10, 0))
                row_frame.columnconfigure(1, weight=1)

                ttk.Label(
                    row_frame,
                    text=str(field_spec.get("label") or ""),
                    style="Dark.TLabel",
                    font=("Segoe UI", 9, "bold"),
                ).grid(row=0, column=0, sticky="w", padx=(0, 12))

                control_type = str(field_spec.get("control") or "")
                if control_type == "bool":
                    variable = tk.BooleanVar(value=bool(field_spec.get("default")))
                    widget = ttk.Checkbutton(row_frame, text="Enabled", variable=variable, style="Dark.TCheckbutton")
                    widget.grid(row=0, column=1, sticky="w")
                    field_bindings[field_key] = {"field_spec": field_spec, "variable": variable, "widget": widget}
                elif control_type == "combo":
                    variable = tk.StringVar(value="")
                    options = tuple(field_spec.get("options") or ())
                    label_to_value = {str(label): int(value) for label, value in options}
                    value_to_label = {int(value): str(label) for label, value in options}
                    widget = ttk.Combobox(
                        row_frame,
                        textvariable=variable,
                        values=list(label_to_value.keys()),
                        state="readonly",
                        style="Dark.TCombobox",
                    )
                    widget.grid(row=0, column=1, sticky="ew")
                    field_bindings[field_key] = {
                        "field_spec": field_spec,
                        "variable": variable,
                        "widget": widget,
                        "label_to_value": label_to_value,
                        "value_to_label": value_to_label,
                    }
                elif control_type == "spinbox":
                    variable = tk.StringVar(value=str(field_spec.get("default")))
                    widget = ttk.Spinbox(
                        row_frame,
                        from_=int(field_spec.get("minimum") or 0),
                        to=int(field_spec.get("maximum") or 0),
                        increment=1,
                        textvariable=variable,
                        width=10,
                        style="Dark.TSpinbox",
                        justify="center",
                        validate="key",
                        validatecommand=int_validator,
                    )
                    widget.grid(row=0, column=1, sticky="w")
                    field_bindings[field_key] = {"field_spec": field_spec, "variable": variable, "widget": widget}
                elif control_type == "scale":
                    control_frame = ttk.Frame(row_frame, style="Dark.TFrame")
                    control_frame.grid(row=0, column=1, sticky="ew")
                    control_frame.columnconfigure(0, weight=1)
                    variable = tk.DoubleVar(value=float(field_spec.get("default") or 0.0))
                    display_var = tk.StringVar(value="")
                    widget = ttk.Scale(
                        control_frame,
                        from_=float(field_spec.get("minimum") or 0.0),
                        to=float(field_spec.get("maximum") or 0.0),
                        variable=variable,
                        orient="horizontal",
                        command=lambda _value, target_key=field_key: update_scale_label(target_key),
                    )
                    widget.grid(row=0, column=0, sticky="ew")
                    ttk.Label(
                        control_frame,
                        textvariable=display_var,
                        style="Dark.TLabel",
                        width=8,
                    ).grid(row=0, column=1, sticky="e", padx=(10, 0))
                    field_bindings[field_key] = {
                        "field_spec": field_spec,
                        "variable": variable,
                        "widget": widget,
                        "display_var": display_var,
                    }
                    update_scale_label(field_key)
                else:
                    variable = tk.StringVar(value=str(field_spec.get("default") or ""))
                    widget = ttk.Entry(row_frame, textvariable=variable, style="Dark.TEntry")
                    widget.grid(row=0, column=1, sticky="ew")
                    field_bindings[field_key] = {"field_spec": field_spec, "variable": variable, "widget": widget}

                row_index += 1

        save_allowed = False

        def load_from_file() -> None:
            nonlocal save_allowed
            apply_defaults()
            if not os.path.exists(settings_path):
                save_allowed = False
                save_button.configure(state="disabled")
                status_var.set("Settings file not found.")
                messagebox.showerror("File Not Found", "GlobalBasicSettings_13.xml was not found.\nMake sure Roblox is installed.")
                return

            try:
                import xml.etree.ElementTree as ET

                xml_tree = ET.parse(settings_path)
                properties_node = get_properties_node(xml_tree.getroot())
                for field_key, field_spec in field_specs_by_key.items():
                    set_field_value(field_key, read_field_value(properties_node, field_spec))
                save_allowed = True
                save_button.configure(state="normal")
                status_var.set("Settings loaded successfully.")
            except ET.ParseError:
                save_allowed = False
                save_button.configure(state="disabled")
                status_var.set("Could not read the settings file.")
                messagebox.showerror("Parse Error", "Could not read the settings file.")
            except Exception:
                save_allowed = False
                save_button.configure(state="disabled")
                status_var.set("Could not read the settings file.")
                messagebox.showerror("Parse Error", "Could not read the settings file.")

        def reset_to_default() -> None:
            apply_defaults()
            status_var.set("Controls reset to default values.")

        def save_settings() -> None:
            if not save_allowed:
                return

            if is_roblox_running():
                messagebox.showwarning(
                    "Roblox Running",
                    "Roblox is currently running. Changes may be overwritten.\nClose Roblox first for best results.",
                )

            try:
                import xml.etree.ElementTree as ET

                xml_tree = ET.parse(settings_path)
                properties_node = get_properties_node(xml_tree.getroot())
                for field_key, field_spec in field_specs_by_key.items():
                    write_field_value(properties_node, field_spec, get_field_value(field_key))
                if hasattr(ET, "indent"):
                    ET.indent(xml_tree, space="\t")
                xml_tree.write(settings_path, encoding="unicode", xml_declaration=False)
                status_var.set("Settings saved successfully.")
                messagebox.showinfo("Roblox Settings", "Settings saved successfully.")
                load_from_file()
            except Exception as e:
                messagebox.showerror("Save Failed", f"Could not write settings:\n{e}")

        def close_window() -> None:
            try:
                self.global_settings_window.destroy()
            finally:
                self.global_settings_window = None

        buttons = ttk.Frame(main, style="Dark.TFrame")
        buttons.pack(fill="x")
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)

        ttk.Button(
            buttons,
            text="Reset to Default",
            style="Dark.TButton",
            command=reset_to_default,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        save_button = ttk.Button(
            buttons,
            text="Save",
            style="Dark.TButton",
            command=save_settings,
        )
        save_button.grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Button(
            buttons,
            text="Close",
            style="Dark.TButton",
            command=close_window,
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        self.global_settings_window.protocol("WM_DELETE_WINDOW", close_window)
        load_from_file()
        self.global_settings_window.bind("<Control-s>", lambda _evt: (save_settings(), "break")[1])

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

