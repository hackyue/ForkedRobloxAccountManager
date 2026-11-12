import json
import os
import re
import sys
import time
import math
import queue
import hashlib
import datetime
import urllib.request
import urllib.error
import urllib.parse
import threading
import secrets
import tempfile
from typing import Optional, Dict, Any, List, Tuple, Callable
from utils.error_detector import log_detailed_error

ALLOWED_DISCORD_HOSTS = (
    "discord.com",
    "discordapp.com",
    "canary.discord.com",
    "ptb.discord.com",
    "canary.discordapp.com",
    "ptb.discordapp.com",
)


class WebhookManager:
    ALLOWED_DISCORD_HOSTS = set(ALLOWED_DISCORD_HOSTS)

    ALL_EVENT_CATEGORIES = [
        "launch",
        "rejoin",
        "crash",
        "account_status",
        "group_relaunch",
        "automation",
        "screenshot",
        "preview",
        "instances",
        "log",
    ]

    DEFAULT_CONFIG: Dict[str, Any] = {
        "enabled": False,
        "webhook_url": "",
        "bot_username": "FRAM Webhook",
        "bot_avatar_url": "",
        "embed_color": "#4f8ef7",
        "send_logs": True,
        "send_launches": True,
        "send_rejoins": True,
        "send_crashes": True,
        "send_account_status": True,
        "send_group_relaunch": True,
        "send_automation": False,
        "send_instances": False,
        "ping_user_id": "",
        "ping_only_alerts": False,
        "redact_sensitive": True,
        "screenshot_enabled": False,
        "screenshot_interval_minutes": 15,
        "screenshot_mode": "client_grid",  # 'client_grid' | 'all_instances' | 'window_only' | 'primary' | 'all_monitors'
        "screenshot_target_pid": None,
        "screenshot_all_monitors": False,
        "screenshot_window_only": False,
        "screenshot_on_alert": False,
        "instance_summary_enabled": False,
        "instance_summary_interval_minutes": 15,
        "instance_summary_mode": "new_message",  # 'new_message' | 'edit_live_board'
        "instance_summary_include_screenshot": False,
        "live_board_message_ids": {},
        "endpoints": [],
    }

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(os.path.expanduser("~"), ".fram")
        os.makedirs(self.data_dir, exist_ok=True)
        self.config_path = os.path.join(self.data_dir, "webhook_config.json")
        self.history_path = os.path.join(self.data_dir, "webhook_history.json")
        self.lock = threading.RLock()
        self.config: Dict[str, Any] = dict(self.DEFAULT_CONFIG)
        self.history: List[Dict[str, Any]] = []
        self._retry_cache: Dict[str, Dict[str, Any]] = {}
        self._last_screenshot_time = 0.0
        self._last_instance_time = 0.0
        self._recent_log_hashes: Dict[str, float] = {}
        self._recent_status_alerts: Dict[str, float] = {}
        self._recent_exit_alerts: Dict[str, float] = {}
        self._delivery_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=250)
        self._instances_provider: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._account_lookup: Optional[Callable[[str], Dict[str, Any]]] = None
        self.running = True

        self._migrate_legacy_config_if_needed()
        self.load_config()
        self.load_history()

        threading.Thread(target=self._delivery_worker, daemon=True, name="webhook-delivery-worker").start()
        threading.Thread(target=self._start_schedulers, daemon=True, name="webhook-scheduler").start()

    def set_instances_provider(self, provider: Callable[[], List[Dict[str, Any]]]):
        self._instances_provider = provider

    def set_account_lookup(self, lookup: Callable[[str], Dict[str, Any]]):
        self._account_lookup = lookup

    def _migrate_legacy_config_if_needed(self):
        legacy_dir = os.path.join(os.path.expanduser("~"), ".fram")
        legacy_cfg = os.path.join(legacy_dir, "webhook_config.json")
        if os.path.abspath(legacy_cfg) != os.path.abspath(self.config_path):
            if not os.path.exists(self.config_path) and os.path.exists(legacy_cfg):
                try:
                    with open(legacy_cfg, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    if isinstance(saved, dict):
                        with open(self.config_path, "w", encoding="utf-8") as out:
                            json.dump(saved, out, indent=2)
                except Exception:
                    pass

    def _sync_config_fields_unlocked(self):
        mode = self.config.get("screenshot_mode")
        if mode not in ("primary", "all_monitors", "window_only", "client_grid", "all_instances"):
            if self.config.get("screenshot_window_only"):
                mode = "window_only"
            elif self.config.get("screenshot_all_monitors"):
                mode = "all_monitors"
            else:
                mode = "client_grid"
            self.config["screenshot_mode"] = mode

        self.config["screenshot_all_monitors"] = mode == "all_monitors"
        self.config["screenshot_window_only"] = mode == "window_only"

        self.config["screenshot_interval_minutes"] = max(
            1, min(1440, int(self.config.get("screenshot_interval_minutes", 15) or 15))
        )
        self.config["instance_summary_interval_minutes"] = max(
            1, min(1440, int(self.config.get("instance_summary_interval_minutes", 15) or 15))
        )
        if not isinstance(self.config.get("live_board_message_ids"), dict):
            self.config["live_board_message_ids"] = {}
        if not isinstance(self.config.get("endpoints"), list):
            self.config["endpoints"] = []

    def load_config(self):
        with self.lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        if isinstance(saved, dict):
                            self.config.update(saved)
                    self._sync_config_fields_unlocked()
                except Exception as e:
                    log_detailed_error(
                        "Failed to load webhook config",
                        exc=e,
                        extra_info={"config_path": self.config_path},
                        source="webhook_manager",
                    )

    def save_config(self, new_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self.lock:
            if new_config and isinstance(new_config, dict):
                if "screenshot_mode" not in new_config:
                    if "screenshot_window_only" in new_config and new_config["screenshot_window_only"]:
                        new_config["screenshot_mode"] = "window_only"
                    elif "screenshot_all_monitors" in new_config and new_config["screenshot_all_monitors"]:
                        new_config["screenshot_mode"] = "all_monitors"
                    elif "screenshot_window_only" in new_config or "screenshot_all_monitors" in new_config:
                        new_config["screenshot_mode"] = "primary"
                for k, v in new_config.items():
                    if k in self.DEFAULT_CONFIG or k in self.config:
                        self.config[k] = v
                self._sync_config_fields_unlocked()
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
            except Exception as e:
                log_detailed_error(
                    "Failed to save webhook config",
                    exc=e,
                    extra_info={"config_path": self.config_path},
                    source="webhook_manager",
                )
            return dict(self.config)

    def load_history(self):
        with self.lock:
            if os.path.exists(self.history_path):
                try:
                    with open(self.history_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        if isinstance(saved, list):
                            self.history = saved[:60]
                except Exception:
                    self.history = []

    def _save_history_unlocked(self):
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history[:60], f, indent=2)
        except Exception:
            pass

    def clear_history(self):
        with self.lock:
            self.history = []
            self._retry_cache.clear()
            self._save_history_unlocked()

    def reset_live_board(self) -> Dict[str, Any]:
        with self.lock:
            self.config["live_board_message_ids"] = {}
            return self.save_config()

    def canonicalize_webhook_url(self, url: Optional[str] = None) -> Optional[str]:
        raw = (url or self.config.get("webhook_url", "") or "").strip()
        if not raw:
            return None
        try:
            parts = urllib.parse.urlsplit(raw)
            if (parts.scheme or "").lower() != "https":
                return None
            hostname = (parts.hostname or "").lower()
            if hostname not in self.ALLOWED_DISCORD_HOSTS:
                return None
            if parts.query or parts.fragment:
                return None
            path = parts.path or ""
            path_pattern = r"^/api/webhooks/\d+/[A-Za-z0-9_.-]+/?$"
            if not re.fullmatch(path_pattern, path):
                return None
            clean_path = path.rstrip("/")
            return f"https://{hostname}{clean_path}"
        except Exception:
            return None

    def _is_allowed_discord_webhook_url(self, url: str) -> bool:
        return self.canonicalize_webhook_url(url) is not None

    def is_valid_url(self, url: Optional[str] = None) -> bool:
        return self.canonicalize_webhook_url(url) is not None

    def _url_hash(self, canonical_url: str) -> str:
        return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]

    THEME_PRIMARY_COLORS: Dict[str, str] = {
        "default-dark": "#4f8ef7",
        "synapse-neon": "#8d5cf7",
        "scriptware-minimal": "#6ab0ff",
        "vapor": "#4ef0ff",
        "potassium-ion": "#ffd500",
        "midnight-matrix": "#00ff7f",
        "aurora-fade": "#ff99d6",
        "chromepulse": "#58c5ff",
        "crimson-velvet": "#f43f5e",
        "oled-pitch": "#3b82f6",
        "matcha-zen": "#10b981",
        "sunset-ember": "#f97316",
        "arctic-frost": "#0ea5e9",
        "dracula-pro": "#bd93f9",
        "cyberpunk-2077": "#fcee0a",
        "tokyo-night": "#7aa2f7",
        "catppuccin-mocha": "#cba6f7",
        "nordic-ice": "#88c0d0",
        "rose-pine": "#ebbcba",
        "gruvbox-dark": "#fabd2f",
        "monokai-pro": "#ffd866",
        "solarized-dark": "#268bd2",
    }

    def _get_theme_color_hex(self) -> str:
        try:
            settings_path = os.path.join(self.data_dir, "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                if isinstance(settings, dict):
                    accent = str(settings.get("accentColor") or "").strip()
                    if accent.startswith("#") and len(accent) in (4, 7):
                        return accent
                    theme_id = str(settings.get("selectedTheme") or "").strip()
                    if theme_id in self.THEME_PRIMARY_COLORS:
                        return self.THEME_PRIMARY_COLORS[theme_id]
        except Exception:
            pass
        return str(self.config.get("embed_color") or "#4f8ef7").strip()

    def _parse_embed_color(self, color: Any = None) -> int:
        if isinstance(color, int):
            return color
        raw = str(color or self._get_theme_color_hex() or "#4f8ef7").strip().lstrip("#")
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        try:
            return int(raw, 16)
        except Exception:
            return 0x4F8EF7

    def _redact_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        text_str = str(text)
        if not self.config.get("redact_sensitive", True):
            return text_str
        pattern = r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[^\s/\"']+"
        text_str = re.sub(pattern, "[WEBHOOK_REDACTED]", text_str)
        cookie_pattern = r"(_\|WARNING:-DO-NOT-SHARE-THIS[^\s\"']+|_\|WARNING:-___(?:BEGIN|DO_NOT_SHARE)[^\"'\s]+)"
        text_str = re.sub(cookie_pattern, "[COOKIE_REDACTED]", text_str)
        return text_str

    def _build_mention_content(
        self,
        is_alert: bool = False,
        override_ping_id: Optional[str] = None,
        override_ping_only_alerts: Optional[bool] = None,
    ) -> str:
        ping_target = str(
            override_ping_id if override_ping_id is not None else (self.config.get("ping_user_id", "") or "")
        ).strip()
        if not ping_target:
            return ""
        ping_only_alerts = (
            override_ping_only_alerts
            if override_ping_only_alerts is not None
            else bool(self.config.get("ping_only_alerts", False))
        )
        if ping_only_alerts and not is_alert:
            return ""
        if ping_target.startswith("<@") and ping_target.endswith(">"):
            return ping_target
        if ping_target.startswith("&"):
            return f"<@{ping_target}>"
        return f"<@{ping_target}>"

    def _apply_bot_identity(self, payload: Dict[str, Any]):
        bot_name = str(self.config.get("bot_username", "") or "").strip()
        if bot_name:
            payload["username"] = bot_name[:80]
        bot_avatar = str(self.config.get("bot_avatar_url", "") or "").strip()
        if bot_avatar and (bot_avatar.startswith("https://") or bot_avatar.startswith("http://")):
            payload["avatar_url"] = bot_avatar

    def _get_target_endpoints_for_category(
        self,
        category: str,
        explicit_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if explicit_url:
            canonical = self.canonicalize_webhook_url(explicit_url)
            if canonical:
                return [{
                    "name": "Direct Target",
                    "url": canonical,
                    "ping_user_id": self.config.get("ping_user_id", ""),
                    "ping_only_alerts": self.config.get("ping_only_alerts", False),
                }]
            return []

        targets: List[Dict[str, Any]] = []
        seen_urls = set()

        with self.lock:
            primary_url = self.canonicalize_webhook_url(self.config.get("webhook_url", ""))
            if primary_url:
                seen_urls.add(primary_url)
                targets.append({
                    "name": "Primary Webhook",
                    "url": primary_url,
                    "ping_user_id": self.config.get("ping_user_id", ""),
                    "ping_only_alerts": self.config.get("ping_only_alerts", False),
                })

            for ep in self.config.get("endpoints", []):
                if not isinstance(ep, dict) or not ep.get("enabled", True):
                    continue
                ep_url = self.canonicalize_webhook_url(ep.get("url", ""))
                if not ep_url or ep_url in seen_urls:
                    continue
                ep_events = ep.get("events")
                if isinstance(ep_events, list) and category not in ("test", "custom", "general"):
                    if category not in ep_events and "all" not in ep_events:
                        continue
                seen_urls.add(ep_url)
                targets.append({
                    "name": str(ep.get("name") or "Secondary Webhook")[:40],
                    "url": ep_url,
                    "ping_user_id": ep.get("ping_user_id") or self.config.get("ping_user_id", ""),
                    "ping_only_alerts": ep.get("ping_only_alerts", self.config.get("ping_only_alerts", False)),
                })

        return targets

    def _send_http_with_retry(
        self,
        request_url: str,
        body_bytes: bytes,
        content_type: str,
        method: str = "POST",
        timeout: int = 15,
        max_retries: int = 3,
    ) -> Tuple[bool, str, int, Optional[Dict[str, Any]]]:
        if not request_url or not isinstance(request_url, str):
            return False, "Missing destination URL", 400, None

        parsed = urllib.parse.urlsplit(str(request_url).strip())
        hostname = (parsed.hostname or "").lower()
        if (parsed.scheme or "").lower() != "https" or hostname not in ALLOWED_DISCORD_HOSTS:
            return False, "Invalid or untrusted destination URL", 400, None

        path = parsed.path or ""
        if not re.fullmatch(r"^/api/webhooks/\d+/[A-Za-z0-9_.-]+(?:/messages/\d+)?$", path):
            return False, "Invalid webhook endpoint path", 400, None

        query = parsed.query or ""
        if query and query != "wait=true":
            return False, "Invalid webhook query parameters", 400, None

        safe_url = f"https://{hostname}{path}" + (f"?{query}" if query else "")

        attempt = 0
        last_err = "Delivery failed"
        last_code = 0

        while attempt < max_retries:
            attempt += 1
            try:
                req = urllib.request.Request(
                    safe_url,
                    data=body_bytes,
                    headers={
                        "Content-Type": content_type,
                        "User-Agent": "FRAM-WebhookManager/3.0",
                    },
                    method=method,
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    last_code = response.status
                    raw_resp = response.read()
                    parsed_json = None
                    if raw_resp:
                        try:
                            parsed_json = json.loads(raw_resp.decode("utf-8", errors="ignore"))
                        except Exception:
                            parsed_json = None
                    if response.status in (200, 204):
                        return True, "Success", response.status, parsed_json
                    last_err = f"Discord HTTP {response.status}"
            except urllib.error.HTTPError as e:
                last_code = e.code
                if e.code == 429 and attempt < max_retries:
                    retry_after = 1.5
                    try:
                        hdr = e.headers.get("Retry-After") if e.headers else None
                        if hdr:
                            retry_after = float(hdr)
                        else:
                            err_body = json.loads(e.read().decode("utf-8", errors="ignore"))
                            retry_after = float(err_body.get("retry_after", 1.5))
                    except Exception:
                        retry_after = 1.5 * attempt
                    time.sleep(min(10.0, max(0.5, retry_after)))
                    continue
                elif e.code == 404:
                    return False, "HTTP Error 404 (Not Found)", 404, None
                elif e.code >= 500 and attempt < max_retries:
                    time.sleep(1.0 * attempt)
                    continue
                last_err = f"HTTP Error {e.code}"
                break
            except Exception as e:
                last_err = "Network / Connection Error"
                if attempt < max_retries:
                    time.sleep(0.8 * attempt)
                    continue
                print(f"[ERROR] Webhook delivery failed: {e}")
                break

        return False, last_err, last_code, None

    def _delivery_worker(self):
        while self.running:
            try:
                job = self._delivery_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                fn = job.get("fn")
                args = job.get("args", ())
                kwargs = job.get("kwargs", {})
                if callable(fn):
                    fn(*args, **kwargs)
                time.sleep(0.25)
            except Exception as e:
                print(f"[ERROR] Webhook queue worker error: {e}")
            finally:
                try:
                    self._delivery_queue.task_done()
                except Exception:
                    pass

    def _enqueue(self, fn: Callable, *args, **kwargs):
        try:
            self._delivery_queue.put_nowait({"fn": fn, "args": args, "kwargs": kwargs})
        except queue.Full:
            threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()

    def post_embed(
        self,
        title: str,
        description: str,
        fields: Optional[List[Dict[str, Any]]] = None,
        color: Optional[Any] = None,
        url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        author: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        footer_text: Optional[str] = None,
        footer_icon: Optional[str] = None,
        timestamp: Optional[str] = None,
        category: str = "general",
        is_alert: bool = False,
        edit_message_key: Optional[str] = None,
    ) -> Tuple[bool, str]:
        targets = self._get_target_endpoints_for_category(category, explicit_url=url)
        if not targets:
            return False, "Invalid or unconfigured Discord webhook URL."

        resolved_color = self._parse_embed_color(color)
        redacted_desc = self._redact_text(description)
        embed: Dict[str, Any] = {
            "title": str(title)[:256],
            "description": redacted_desc[:4096],
            "color": resolved_color,
            "footer": {
                "text": footer_text or "Forked Roblox Account Manager"
            },
            "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if footer_icon:
            embed["footer"]["icon_url"] = footer_icon
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        if author and isinstance(author, dict):
            embed["author"] = author
        if image_url:
            embed["image"] = {"url": image_url}

        if fields and isinstance(fields, list):
            clean_fields = []
            for field in fields[:25]:
                if isinstance(field, dict) and "name" in field and "value" in field:
                    clean_fields.append({
                        "name": str(field["name"])[:256],
                        "value": (self._redact_text(str(field["value"])) or "\u200b")[:1024],
                        "inline": bool(field.get("inline", True)),
                    })
            if clean_fields:
                embed["fields"] = clean_fields

        any_ok = False
        last_msg = "Webhook delivery failed"

        for target in targets:
            canonical_url = target["url"]
            ep_name = target["name"]
            payload: Dict[str, Any] = {
                "content": self._build_mention_content(
                    is_alert=is_alert,
                    override_ping_id=target.get("ping_user_id"),
                    override_ping_only_alerts=target.get("ping_only_alerts"),
                ),
                "embeds": [embed],
            }
            self._apply_bot_identity(payload)
            body_bytes = json.dumps(payload).encode("utf-8")

            start_t = time.time()
            ok = False
            msg = ""
            http_code = 0

            if edit_message_key:
                url_key = f"{edit_message_key}:{self._url_hash(canonical_url)}"
                existing_msg_id = None
                with self.lock:
                    existing_msg_id = (self.config.get("live_board_message_ids") or {}).get(url_key)

                if existing_msg_id and str(existing_msg_id).isdigit():
                    patch_url = f"{canonical_url}/messages/{existing_msg_id}"
                    ok, msg, http_code, _ = self._send_http_with_retry(
                        request_url=patch_url,
                        body_bytes=body_bytes,
                        content_type="application/json",
                        method="PATCH",
                    )
                    if ok:
                        elapsed_ms = int((time.time() - start_t) * 1000)
                        self._add_history(
                            f"{title} (Live Edit)",
                            "Success",
                            category=category,
                            ok=True,
                            duration_ms=elapsed_ms,
                            endpoint_name=ep_name,
                            http_code=http_code,
                        )
                        any_ok = True
                        last_msg = "Live dashboard message updated in Discord."
                        continue

                wait_url = f"{canonical_url}?wait=true"
                ok, msg, http_code, resp_json = self._send_http_with_retry(
                    request_url=wait_url,
                    body_bytes=body_bytes,
                    content_type="application/json",
                    method="POST",
                )
                elapsed_ms = int((time.time() - start_t) * 1000)
                if ok and isinstance(resp_json, dict) and resp_json.get("id"):
                    with self.lock:
                        if not isinstance(self.config.get("live_board_message_ids"), dict):
                            self.config["live_board_message_ids"] = {}
                        self.config["live_board_message_ids"][url_key] = str(resp_json["id"])
                        self.save_config()
            else:
                ok, msg, http_code, _ = self._send_http_with_retry(
                    request_url=canonical_url,
                    body_bytes=body_bytes,
                    content_type="application/json",
                    method="POST",
                )
                elapsed_ms = int((time.time() - start_t) * 1000)

            retry_spec = {
                "title": title,
                "description": description,
                "fields": fields,
                "color": color,
                "url": canonical_url,
                "thumbnail_url": thumbnail_url,
                "author": author,
                "category": category,
                "is_alert": is_alert,
            }
            self._add_history(
                title,
                "Success" if ok else msg,
                category=category,
                ok=ok,
                duration_ms=elapsed_ms,
                endpoint_name=ep_name,
                http_code=http_code,
                retry_spec=retry_spec,
            )
            if ok:
                any_ok = True
                last_msg = "Webhook delivered successfully."
            else:
                last_msg = msg

        return any_ok, last_msg

    def retry_history_item(self, history_id: str) -> Tuple[bool, str]:
        spec = None
        with self.lock:
            spec = self._retry_cache.get(str(history_id))
        if not spec:
            return False, "Retry payload is no longer cached in memory."
        return self.post_embed(
            title=spec.get("title", "Retry Notification"),
            description=spec.get("description", ""),
            fields=spec.get("fields"),
            color=spec.get("color"),
            url=spec.get("url"),
            thumbnail_url=spec.get("thumbnail_url"),
            author=spec.get("author"),
            category=spec.get("category", "general"),
            is_alert=bool(spec.get("is_alert", False)),
        )

    def _enumerate_visible_roblox_windows_win32(self, target_pid: Optional[int] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        if sys.platform != "win32":
            return results
        try:
            import ctypes
            user32 = ctypes.windll.user32

            known_pids = {
                int(inst["pid"])
                for inst in self._get_resolved_instances()
                if inst.get("pid")
            }

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            by_pid: Dict[int, Dict[str, Any]] = {}

            def enum_cb(hwnd, _extra):
                if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    title = ""
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value or ""
                    lpdw_pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
                    win_pid = int(lpdw_pid.value)
                    if target_pid and win_pid != int(target_pid):
                        return True
                    is_roblox_win = (
                        win_pid in known_pids
                        or "roblox" in title.lower()
                        or (target_pid and win_pid == int(target_pid))
                    )
                    if is_roblox_win:
                        rect = RECT()
                        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                            w = rect.right - rect.left
                            h = rect.bottom - rect.top
                            if w > 120 and h > 120:
                                area = w * h
                                existing = by_pid.get(win_pid)
                                if not existing or area > existing["area"]:
                                    by_pid[win_pid] = {
                                        "hwnd": hwnd,
                                        "pid": win_pid,
                                        "title": title or "Roblox",
                                        "bbox": (rect.left, rect.top, rect.right, rect.bottom),
                                        "area": area,
                                    }
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            results = list(by_pid.values())
        except Exception:
            pass
        return results

    def _capture_single_hwnd_win32(self, hwnd: int, bbox: Tuple[int, int, int, int]):
        """Captures an individual Roblox window surface even when overlapped by other multi-instance windows."""
        from PIL import Image, ImageGrab
        left, top, right, bottom = bbox
        w = max(1, right - left)
        h = max(1, bottom - top)
        if sys.platform == "win32" and hwnd:
            hwnd_dc = 0
            mfc_dc = 0
            save_bitmap = 0
            gdi32 = None
            user32 = None
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                gdi32 = ctypes.windll.gdi32

                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD),
                    ]

                hwnd_dc = user32.GetWindowDC(hwnd)
                if hwnd_dc:
                    mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
                    if mfc_dc:
                        save_bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
                        if save_bitmap:
                            gdi32.SelectObject(mfc_dc, save_bitmap)
                            # PW_RENDERFULLCONTENT (2) captures Direct3D/DWM surfaces even when occluded
                            res = user32.PrintWindow(hwnd, mfc_dc, 2)
                            if not res:
                                res = user32.PrintWindow(hwnd, mfc_dc, 0)
                            if res:
                                bmi = BITMAPINFOHEADER()
                                bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                                bmi.biWidth = w
                                bmi.biHeight = -h
                                bmi.biPlanes = 1
                                bmi.biBitCount = 32
                                bmi.biCompression = 0

                                buf_len = w * h * 4
                                buf = ctypes.create_string_buffer(buf_len)
                                lines = gdi32.GetDIBits(
                                    mfc_dc, save_bitmap, 0, h, buf, ctypes.byref(bmi), 0
                                )
                                if lines == h:
                                    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
                                    extrema = img.getextrema()
                                    if extrema and any(ch[1] > 8 for ch in extrema):
                                        return img
            except Exception:
                pass
            finally:
                try:
                    if save_bitmap and gdi32:
                        gdi32.DeleteObject(save_bitmap)
                    if mfc_dc and gdi32:
                        gdi32.DeleteDC(mfc_dc)
                    if hwnd_dc and user32:
                        user32.ReleaseDC(hwnd, hwnd_dc)
                except Exception:
                    pass

        return ImageGrab.grab(bbox=bbox, all_screens=True)

    def capture_client_grid_screenshot(self) -> Optional[str]:
        """Captures all running Roblox client windows (multi-instance) and stitches them into a labeled grid collage."""
        if sys.platform == "win32":
            try:
                from PIL import Image, ImageDraw
                windows = self._enumerate_visible_roblox_windows_win32()
                if not windows:
                    return self.capture_screenshot(mode_override="primary")

                instances_by_pid: Dict[int, Dict[str, Any]] = {}
                for inst in self._get_resolved_instances():
                    if inst.get("pid"):
                        instances_by_pid[int(inst["pid"])] = inst

                tiles: List[Tuple[Image.Image, str]] = []
                tile_w, tile_h = 640, 380
                header_h = 30

                for idx, win in enumerate(windows[:16]):
                    try:
                        raw_img = self._capture_single_hwnd_win32(win["hwnd"], win["bbox"])
                        resized = raw_img.resize((tile_w, tile_h - header_h), Image.Resampling.LANCZOS)
                        pid = win["pid"]
                        inst_meta = instances_by_pid.get(pid, {})
                        uname = inst_meta.get("username") or inst_meta.get("account")
                        mem = inst_meta.get("memory_mb")
                        place = inst_meta.get("place_name") or inst_meta.get("place")
                        label_parts = [f"#{idx + 1} @{uname}" if uname else f"#{idx + 1} PID {pid}"]
                        if place:
                            label_parts.append(str(place)[:26])
                        if mem:
                            label_parts.append(f"{mem} MB")
                        tiles.append((resized, " - ".join(label_parts)))
                    except Exception:
                        continue

                if not tiles:
                    return self.capture_screenshot(mode_override="primary")

                count = len(tiles)
                cols = 1 if count == 1 else (2 if count <= 4 else (3 if count <= 9 else 4))
                rows = math.ceil(count / cols)
                pad = 12
                canvas_w = cols * tile_w + (cols + 1) * pad
                canvas_h = rows * tile_h + (rows + 1) * pad

                theme_int = self._parse_embed_color()
                theme_rgb = ((theme_int >> 16) & 0xFF, (theme_int >> 8) & 0xFF, theme_int & 0xFF)

                canvas = Image.new("RGB", (canvas_w, canvas_h), (15, 18, 24))
                draw = ImageDraw.Draw(canvas)

                for idx, (tile_img, label) in enumerate(tiles):
                    r = idx // cols
                    c = idx % cols
                    x = pad + c * (tile_w + pad)
                    y = pad + r * (tile_h + pad)
                    draw.rectangle([x, y, x + tile_w, y + header_h], fill=(24, 28, 36))
                    draw.rectangle([x, y, x + 4, y + header_h], fill=theme_rgb)
                    draw.text((x + 12, y + 8), label, fill=(235, 240, 250))
                    canvas.paste(tile_img, (x, y + header_h))
                    draw.rectangle([x, y, x + tile_w, y + tile_h], outline=(48, 56, 70), width=1)

                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"fram_grid_{int(time.time())}_{secrets.token_hex(4)}.png",
                )
                canvas.save(temp_path, "PNG")
                if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                    return temp_path
            except Exception:
                pass

        return self.capture_window_screenshot()

    def capture_window_screenshot(self, pid: Optional[int] = None) -> Optional[str]:
        temp_path = os.path.join(tempfile.gettempdir(), f"fram_win_{int(time.time())}_{secrets.token_hex(4)}.png")
        if sys.platform == "win32":
            try:
                wins = self._enumerate_visible_roblox_windows_win32(target_pid=pid)
                if not wins and pid:
                    wins = self._enumerate_visible_roblox_windows_win32(target_pid=None)
                if wins:
                    img = self._capture_single_hwnd_win32(wins[0]["hwnd"], wins[0]["bbox"])
                    img.save(temp_path, "PNG")
                    if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                        return temp_path
            except Exception:
                pass

        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = ["/usr/sbin/screencapture", "-x", "-m", temp_path]
                subprocess.run(cmd, check=True, timeout=10, close_fds=True)
                if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                    return temp_path
            except Exception:
                pass

        return self.capture_screenshot(all_monitors=False, mode_override="primary")

    def capture_screenshot(
        self,
        all_monitors: bool = False,
        mode_override: Optional[str] = None,
        target_pid: Optional[int] = None,
    ) -> Optional[str]:
        mode = mode_override or self.config.get("screenshot_mode") or (
            "window_only"
            if self.config.get("screenshot_window_only")
            else ("all_monitors" if (all_monitors or self.config.get("screenshot_all_monitors")) else "client_grid")
        )

        if mode == "client_grid":
            grid_img = self.capture_client_grid_screenshot()
            if grid_img and os.path.isfile(grid_img) and os.path.getsize(grid_img) > 0:
                return grid_img

        if mode == "window_only":
            win_img = self.capture_window_screenshot(pid=target_pid)
            if win_img and os.path.isfile(win_img) and os.path.getsize(win_img) > 0:
                return win_img

        use_all_monitors = (mode == "all_monitors") or bool(all_monitors)
        temp_path = os.path.join(tempfile.gettempdir(), f"fram_screen_{int(time.time())}_{secrets.token_hex(4)}.png")
        try:
            from PIL import ImageGrab
            if use_all_monitors:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    left = user32.GetSystemMetrics(76)
                    top = user32.GetSystemMetrics(77)
                    width = user32.GetSystemMetrics(78)
                    height = user32.GetSystemMetrics(79)
                    if width > 0 and height > 0:
                        bbox = (left, top, left + width, top + height)
                        img = ImageGrab.grab(bbox=bbox, all_screens=True)
                    else:
                        img = ImageGrab.grab(all_screens=True)
                except Exception:
                    img = ImageGrab.grab(all_screens=True)
            else:
                img = ImageGrab.grab(all_screens=False)

            img.save(temp_path, "PNG")
            if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                return temp_path
        except Exception:
            pass

        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = ["/usr/sbin/screencapture", "-x"]
                if not use_all_monitors:
                    cmd.append("-m")
                cmd.append(temp_path)
                subprocess.run(cmd, check=True, timeout=10, close_fds=True)
                if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                    return temp_path
            except Exception:
                pass
        return None

    def _post_multipart_with_image(
        self,
        targets: List[Dict[str, Any]],
        payload_template: Dict[str, Any],
        file_path: str,
        attachment_filename: str,
        history_label: str,
        category: str,
        is_alert: bool = False,
    ) -> Tuple[bool, str]:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        any_ok = False
        last_msg = "Delivery failed"

        for target in targets:
            canonical_url = target["url"]
            ep_name = target["name"]
            start_t = time.time()
            boundary = f"----WebKitFormBoundary{secrets.token_hex(16)}"
            body = bytearray()

            payload = dict(payload_template)
            payload["content"] = self._build_mention_content(
                is_alert=is_alert,
                override_ping_id=target.get("ping_user_id"),
                override_ping_only_alerts=target.get("ping_only_alerts"),
            )
            self._apply_bot_identity(payload)

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n')
            body.extend(json.dumps(payload).encode("utf-8"))
            body.extend(b"\r\n")

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                f'Content-Disposition: form-data; name="file"; filename="{attachment_filename}"\r\nContent-Type: image/png\r\n\r\n'.encode(
                    "utf-8"
                )
            )
            body.extend(file_bytes)
            body.extend(b"\r\n")
            body.extend(f"--{boundary}--\r\n".encode("utf-8"))

            ok, msg, http_code, _ = self._send_http_with_retry(
                request_url=canonical_url,
                body_bytes=bytes(body),
                content_type=f"multipart/form-data; boundary={boundary}",
                method="POST",
                timeout=25,
            )
            elapsed_ms = int((time.time() - start_t) * 1000)
            self._add_history(
                history_label,
                "Success" if ok else msg,
                category=category,
                ok=ok,
                duration_ms=elapsed_ms,
                endpoint_name=ep_name,
                http_code=http_code,
            )
            if ok:
                any_ok = True
                last_msg = "Delivered successfully."
            else:
                last_msg = msg

        return any_ok, last_msg

    def post_all_instances_screenshots(
        self,
        url: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Captures and sends a separate screenshot embed for every running Roblox instance."""
        targets = self._get_target_endpoints_for_category("screenshot", explicit_url=url)
        if not targets:
            return False, "Invalid or unconfigured Discord webhook URL."

        windows = self._enumerate_visible_roblox_windows_win32()
        instances_by_pid: Dict[int, Dict[str, Any]] = {}
        for inst in self._get_resolved_instances():
            if inst.get("pid"):
                instances_by_pid[int(inst["pid"])] = inst

        if not windows:
            return self.post_screenshot(url=url, mode="primary")

        sent_count = 0
        last_msg = "Failed to capture instances."
        total_wins = len(windows[:12])

        for idx, win in enumerate(windows[:12]):
            pid = win["pid"]
            inst_meta = instances_by_pid.get(pid, {})
            uname = inst_meta.get("username") or inst_meta.get("account")
            place_id = inst_meta.get("place_id")
            place_name = inst_meta.get("place_name") or inst_meta.get("place")
            memory_mb = inst_meta.get("memory_mb")
            cpu_percent = inst_meta.get("cpu_percent")
            uptime_str = inst_meta.get("uptime_str")

            temp_path = os.path.join(
                tempfile.gettempdir(),
                f"fram_inst_{pid}_{int(time.time())}_{secrets.token_hex(4)}.png",
            )
            try:
                img = self._capture_single_hwnd_win32(win["hwnd"], win["bbox"])
                img.save(temp_path, "PNG")
                if not os.path.isfile(temp_path) or os.path.getsize(temp_path) == 0:
                    continue

                embed_fields = []
                if uname:
                    embed_fields.append({"name": "Account", "value": f"`@{uname}`", "inline": True})
                embed_fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
                if place_id or place_name:
                    val = (
                        f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})"
                        if place_id
                        else f"`{place_name}`"
                    )
                    embed_fields.append({"name": "Experience", "value": val, "inline": True})
                if uptime_str:
                    embed_fields.append({"name": "Uptime", "value": f"`{uptime_str}`", "inline": True})
                if memory_mb is not None:
                    embed_fields.append({"name": "Memory", "value": f"`{memory_mb} MB`", "inline": True})
                if cpu_percent is not None:
                    embed_fields.append({"name": "CPU Usage", "value": f"`{cpu_percent}%`", "inline": True})

                unix_now = int(time.time())
                title_label = f"Roblox Instance #{idx + 1} - @{uname}" if uname else f"Roblox Instance #{idx + 1} (PID {pid})"
                payload: Dict[str, Any] = {
                    "embeds": [{
                        "title": title_label,
                        "description": f"Multi-instance window capture ({idx + 1} of {total_wins}) - Captured <t:{unix_now}:R>",
                        "color": self._parse_embed_color(),
                        "fields": embed_fields,
                        "image": {"url": "attachment://instance_capture.png"},
                        "footer": {"text": "Forked Roblox Account Manager - Multi-Instance Capture"},
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }],
                }
                ok, msg = self._post_multipart_with_image(
                    targets=targets,
                    payload_template=payload,
                    file_path=temp_path,
                    attachment_filename="instance_capture.png",
                    history_label=f"Instance Capture ({f'@{uname}' if uname else f'PID {pid}'})",
                    category="screenshot",
                    is_alert=False,
                )
                if ok:
                    sent_count += 1
                    last_msg = f"Delivered {sent_count} Roblox instance capture(s)."
                else:
                    last_msg = msg
            except Exception as e:
                print(f"[ERROR] Failed delivering instance capture for PID {pid}: {e}")
                last_msg = "Failed delivering instance capture"
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

        return (sent_count > 0), last_msg

    def post_screenshot(
        self,
        url: Optional[str] = None,
        all_monitors: Optional[bool] = None,
        mode: Optional[str] = None,
        target_pid: Optional[int] = None,
    ) -> Tuple[bool, str]:
        targets = self._get_target_endpoints_for_category("screenshot", explicit_url=url)
        if not targets:
            return False, "Invalid or unconfigured Discord webhook URL."

        active_mode = mode or self.config.get("screenshot_mode") or (
            "all_monitors" if all_monitors else "client_grid"
        )
        effective_pid = target_pid if target_pid is not None else self.config.get("screenshot_target_pid")
        if effective_pid is not None:
            try:
                effective_pid = int(effective_pid)
            except Exception:
                effective_pid = None

        if active_mode == "all_instances" and not effective_pid:
            return self.post_all_instances_screenshots(url=url)

        if effective_pid and active_mode in ("window_only", "client_grid", "all_instances"):
            resolved_by_pid = {
                int(inst["pid"]): inst
                for inst in self._get_resolved_instances()
                if inst.get("pid")
            }
            inst_meta = resolved_by_pid.get(effective_pid, {})
            return self.post_window_preview(
                pid=effective_pid,
                username=inst_meta.get("username") or inst_meta.get("account"),
                place_id=inst_meta.get("place_id"),
                place_name=inst_meta.get("place_name") or inst_meta.get("place"),
                memory_mb=inst_meta.get("memory_mb"),
                cpu_percent=inst_meta.get("cpu_percent"),
                uptime_str=inst_meta.get("uptime_str"),
                url=url,
            )

        file_path = self.capture_screenshot(
            all_monitors=bool(all_monitors) or (active_mode == "all_monitors"),
            mode_override=active_mode,
            target_pid=effective_pid,
        )
        if not file_path or not os.path.exists(file_path):
            return False, "Failed to capture display screenshot."

        try:
            mode_labels = {
                "primary": "Primary Monitor",
                "all_monitors": "All Monitors",
                "window_only": "Single Roblox Window",
                "client_grid": "Multi-Instance Grid",
                "all_instances": "All Roblox Instances",
            }
            mode_str = mode_labels.get(active_mode, "Multi-Instance Grid")
            instances = self._get_resolved_instances()
            unix_now = int(time.time())
            embed_fields: List[Dict[str, Any]] = []
            if active_mode == "client_grid" and instances:
                summary_lines = []
                for idx, inst in enumerate(instances[:12]):
                    uname = inst.get("username") or inst.get("account")
                    pid_val = inst.get("pid", "N/A")
                    place = inst.get("place_name") or inst.get("place") or "Roblox"
                    mem = inst.get("memory_mb")
                    who = f"`@{uname}`" if uname else f"`PID {pid_val}`"
                    mem_str = f" - `{mem} MB`" if mem else ""
                    summary_lines.append(f"**#{idx + 1}** {who} ({place}){mem_str}")
                if summary_lines:
                    embed_fields.append({
                        "name": f"Captured Instances ({len(instances)})",
                        "value": "\n".join(summary_lines)[:1020],
                        "inline": False,
                    })

            embed_obj: Dict[str, Any] = {
                "title": "Roblox Multi-Instance Capture" if active_mode == "client_grid" and len(instances) > 1 else "Display Capture",
                "description": (
                    f"Capture Mode: **{mode_str}** - Captured <t:{unix_now}:R>\n"
                    f"Active Roblox Clients: **{len(instances)}**"
                ),
                "color": self._parse_embed_color(),
                "image": {"url": "attachment://fram_display.png"},
                "footer": {"text": "Forked Roblox Account Manager - Screen Capture"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if embed_fields:
                embed_obj["fields"] = embed_fields

            payload: Dict[str, Any] = {"embeds": [embed_obj]}
            return self._post_multipart_with_image(
                targets=targets,
                payload_template=payload,
                file_path=file_path,
                attachment_filename="fram_display.png",
                history_label=f"Screenshot ({mode_str})",
                category="screenshot",
                is_alert=False,
            )
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def post_window_preview(
        self,
        pid: Optional[int] = None,
        username: Optional[str] = None,
        place_id: Optional[str] = None,
        place_name: Optional[str] = None,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        uptime_str: Optional[str] = None,
        url: Optional[str] = None,
    ) -> Tuple[bool, str]:
        targets = self._get_target_endpoints_for_category("preview", explicit_url=url)
        if not targets:
            return False, "Invalid or unconfigured Discord webhook URL."

        if not username and not pid:
            resolved = self._get_resolved_instances()
            if resolved:
                first = resolved[0]
                pid = first.get("pid")
                username = first.get("username")
                place_id = place_id or first.get("place_id")
                place_name = place_name or first.get("place_name")
                memory_mb = memory_mb if memory_mb is not None else first.get("memory_mb")
                cpu_percent = cpu_percent if cpu_percent is not None else first.get("cpu_percent")
                uptime_str = uptime_str or first.get("uptime_str")

        file_path = self.capture_window_screenshot(pid=pid)
        if not file_path or not os.path.exists(file_path):
            return False, "Failed to capture window preview screenshot."

        try:
            desc_lines = []
            if username:
                desc_lines.append(f"Live window preview for account **@{username}**.")
            elif pid:
                desc_lines.append(f"Live window preview for Roblox PID `{pid}`.")
            else:
                desc_lines.append("Live window preview for active Roblox client.")

            embed_fields = []
            if username:
                embed_fields.append({"name": "Account", "value": f"`@{username}`", "inline": True})
            if pid:
                embed_fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
            if place_id:
                val = (
                    f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})"
                    if place_name
                    else f"`{place_id}`"
                )
                embed_fields.append({"name": "Experience", "value": val, "inline": True})
            if uptime_str:
                embed_fields.append({"name": "Uptime", "value": f"`{uptime_str}`", "inline": True})
            if memory_mb is not None:
                embed_fields.append({"name": "Memory", "value": f"`{memory_mb} MB`", "inline": True})
            if cpu_percent is not None:
                embed_fields.append({"name": "CPU Usage", "value": f"`{cpu_percent}%`", "inline": True})

            embed = {
                "title": "Roblox Client Window Preview",
                "description": "\n".join(desc_lines),
                "color": self._parse_embed_color(),
                "fields": embed_fields,
                "image": {"url": "attachment://client_preview.png"},
                "footer": {"text": "Forked Roblox Account Manager - Window Preview"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            payload: Dict[str, Any] = {"embeds": [embed]}
            return self._post_multipart_with_image(
                targets=targets,
                payload_template=payload,
                file_path=file_path,
                attachment_filename="client_preview.png",
                history_label=f"Window Preview ({username or pid or 'Client'})",
                category="preview",
                is_alert=False,
            )
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def _get_resolved_instances(self) -> List[Dict[str, Any]]:
        if callable(self._instances_provider):
            try:
                res = self._instances_provider()
                if isinstance(res, list):
                    return res
            except Exception:
                pass

        instances_data: List[Dict[str, Any]] = []
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name", "memory_info", "create_time"]):
                name = proc.info.get("name", "") or ""
                if "roblox" in name.lower() and "crashhandler" not in name.lower():
                    pid = proc.info.get("pid", 0)
                    mem_bytes = proc.info.get("memory_info").rss if proc.info.get("memory_info") else 0
                    mem_mb = round(mem_bytes / (1024 * 1024), 1)
                    uptime_s = max(0, int(time.time() - (proc.info.get("create_time") or time.time())))
                    m, s = divmod(uptime_s, 60)
                    h, m = divmod(m, 60)
                    uptime_str = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"
                    instances_data.append({
                        "pid": pid,
                        "name": name,
                        "memory_mb": mem_mb,
                        "cpu_percent": 0.0,
                        "uptime_str": uptime_str,
                    })
        except Exception:
            pass
        return instances_data

    def post_instance_summary(
        self,
        instances_data: Optional[List[Dict[str, Any]]] = None,
        url: Optional[str] = None,
        force_new_message: bool = False,
    ) -> Tuple[bool, str]:
        if instances_data is None:
            instances_data = self._get_resolved_instances()

        total_mem_mb = 0.0
        total_cpu = 0.0
        for inst in instances_data:
            try:
                total_mem_mb += float(inst.get("memory_mb", 0) or 0)
                total_cpu += float(inst.get("cpu_percent", 0) or 0)
            except Exception:
                pass

        count = len(instances_data)
        unix_now = int(time.time())
        is_live_board = (
            not force_new_message
            and self.config.get("instance_summary_mode") == "edit_live_board"
        )

        fields = [
            {"name": "Active Clients", "value": f"**{count}** running", "inline": True},
            {"name": "Total RAM", "value": f"`{round(total_mem_mb, 1)} MB`", "inline": True},
            {"name": "Total CPU", "value": f"`{round(total_cpu, 1)}%`", "inline": True},
        ]

        if count == 0:
            fields.append({
                "name": "Process List",
                "value": "No active Roblox client processes are currently running.",
                "inline": False,
            })
        else:
            for idx, inst in enumerate(instances_data[:15]):
                pid = inst.get("pid", "N/A")
                uname = inst.get("username") or inst.get("account")
                dname = inst.get("display_name")
                account_header = (
                    f"{dname} (@{uname})"
                    if (dname and uname and dname.lower() != uname.lower())
                    else (f"@{uname}" if uname else (inst.get("name") or f"PID {pid}"))
                )
                mem = f"{inst.get('memory_mb', 0)} MB"
                cpu = f"{inst.get('cpu_percent', 0.0)}%"
                uptime = inst.get("uptime_str") or inst.get("uptime") or ""
                place_id = inst.get("place_id")
                place_name = inst.get("place_name") or inst.get("place") or "Roblox Client"
                place_display = (
                    f"[{place_name}](https://www.roblox.com/games/{place_id})"
                    if place_id
                    else f"`{place_name}`"
                )
                parts = [f"PID: `{pid}`", f"RAM: `{mem}`", f"CPU: `{cpu}`"]
                if uptime:
                    parts.append(f"Up: `{uptime}`")
                parts.append(f"Game: {place_display}")
                fields.append({
                    "name": f"#{idx + 1} - {account_header}",
                    "value": " | ".join(parts),
                    "inline": False,
                })
            if count > 15:
                fields.append({
                    "name": "Additional Instances",
                    "value": f"... and **{count - 15}** more running instances.",
                    "inline": False,
                })

        title = "FRAM Live Instance Status Board" if is_live_board else "Roblox Instance Status Report"
        desc = (
            f"Live status dashboard - Updated <t:{unix_now}:R> (<t:{unix_now}:T>)\n"
            f"Monitoring **{count}** active Roblox client session(s)."
        )

        return self.post_embed(
            title=title,
            description=desc,
            fields=fields,
            color=None,
            url=url,
            category="instances",
            is_alert=False,
            edit_message_key="live_instance_board" if is_live_board else None,
        )

    def stop(self):
        self.running = False

    def _start_schedulers(self):
        while self.running:
            try:
                for _ in range(15):
                    if not self.running:
                        return
                    time.sleep(1)

                if not self.config.get("enabled"):
                    continue

                now = time.time()

                if self.config.get("screenshot_enabled"):
                    screenshot_interval = max(1, int(self.config.get("screenshot_interval_minutes", 15) or 15))
                    if self._last_screenshot_time == 0.0:
                        self._last_screenshot_time = now
                    elif now - self._last_screenshot_time >= (screenshot_interval * 60):
                        self._last_screenshot_time = now
                        self._enqueue(self.post_screenshot)

                if self.config.get("instance_summary_enabled"):
                    summary_interval = max(1, int(self.config.get("instance_summary_interval_minutes", 15) or 15))
                    if self._last_instance_time == 0.0:
                        self._last_instance_time = now
                    elif now - self._last_instance_time >= (summary_interval * 60):
                        self._last_instance_time = now
                        self._enqueue(self.post_instance_summary)

            except Exception:
                pass

    def send_test_webhook(self, url: Optional[str] = None) -> Tuple[bool, str]:
        active_triggers = []
        if self.config.get("send_launches", True):
            active_triggers.append("Launches")
        if self.config.get("send_rejoins", True):
            active_triggers.append("Auto-Rejoins")
        if self.config.get("send_crashes", True):
            active_triggers.append("Crashes & Disconnects")
        if self.config.get("send_account_status", True):
            active_triggers.append("Cookie/Ban Alerts")
        if self.config.get("send_group_relaunch", True):
            active_triggers.append("Group Relaunch")
        if self.config.get("send_logs", True):
            active_triggers.append("Error Logs")

        instances = self._get_resolved_instances()
        unix_now = int(time.time())

        return self.post_embed(
            title="FRAM Webhook Connected",
            description=(
                f"Your Discord webhook endpoint is verified and connected to **Forked Roblox Account Manager** (<t:{unix_now}:R>).\n"
                f"Queued rate-limit protection and multi-event routing are active."
            ),
            fields=[
                {"name": "Connection", "value": "Verified & Online", "inline": True},
                {"name": "Running Clients", "value": f"`{len(instances)} active`", "inline": True},
                {"name": "Enabled Triggers", "value": ", ".join(active_triggers) if active_triggers else "None", "inline": False},
            ],
            color=None,
            url=url,
            category="test",
            is_alert=False,
        )

    def _resolve_account_meta(self, username: str) -> Dict[str, Any]:
        if callable(self._account_lookup) and username:
            try:
                res = self._account_lookup(username)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass
        return {}

    def notify_launch(
        self,
        username: str,
        place_id: Optional[str] = None,
        job_id: Optional[str] = None,
        display_name: Optional[str] = None,
        user_id: Optional[Any] = None,
        avatar_url: Optional[str] = None,
        place_name: Optional[str] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_launches", True):
            return
        meta = self._resolve_account_meta(username)
        display_name = display_name or meta.get("display_name")
        user_id = user_id or meta.get("user_id")
        avatar_url = avatar_url or meta.get("avatar_url")
        group_name = meta.get("group")

        fields = [
            {
                "name": "Account",
                "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**",
                "inline": True,
            }
        ]
        if group_name and group_name != "Ungrouped":
            fields.append({"name": "Group", "value": f"`{group_name}`", "inline": True})
        if place_id:
            place_label = (
                f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})"
                if place_name
                else f"[{place_id}](https://www.roblox.com/games/{place_id})"
            )
            fields.append({"name": "Experience", "value": place_label, "inline": True})
        else:
            fields.append({"name": "Experience", "value": "Roblox Home / App", "inline": True})
        if job_id:
            fields.append({"name": "Job / Server ID", "value": f"`{job_id}`", "inline": False})

        thumb = avatar_url or (
            f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png"
            if user_id
            else None
        )
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico",
        }
        unix_now = int(time.time())

        self._enqueue(
            self.post_embed,
            "Account Launch Event",
            f"Account **{display_name or username}** launched a Roblox client session (<t:{unix_now}:R>).",
            fields,
            None,
            thumbnail_url=thumb,
            author=author,
            category="launch",
            is_alert=False,
        )

    def notify_rejoin(
        self,
        username: str,
        place_id: Optional[str],
        reason: Optional[str] = None,
        display_name: Optional[str] = None,
        user_id: Optional[Any] = None,
        avatar_url: Optional[str] = None,
        place_name: Optional[str] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_rejoins", True):
            return
        meta = self._resolve_account_meta(username)
        display_name = display_name or meta.get("display_name")
        user_id = user_id or meta.get("user_id")
        avatar_url = avatar_url or meta.get("avatar_url")

        fields = [
            {
                "name": "Account",
                "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**",
                "inline": True,
            }
        ]
        if place_id:
            place_label = (
                f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})"
                if place_name
                else f"[{place_id}](https://www.roblox.com/games/{place_id})"
            )
            fields.append({"name": "Target Place", "value": place_label, "inline": True})
        if reason:
            fields.append({"name": "Trigger Reason", "value": str(reason), "inline": False})

        thumb = avatar_url or (
            f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png"
            if user_id
            else None
        )
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico",
        }
        unix_now = int(time.time())

        self._enqueue(
            self.post_embed,
            "Auto-Rejoin Triggered",
            f"Auto-Rejoin monitor reconnected account **{display_name or username}** (<t:{unix_now}:R>).",
            fields,
            0xF59E0B,
            thumbnail_url=thumb,
            author=author,
            category="rejoin",
            is_alert=True,
        )
        if self.config.get("screenshot_on_alert"):
            self._enqueue(self.post_screenshot)

    def notify_crash(
        self,
        username: str,
        pid: Optional[int] = None,
        reason: Optional[str] = None,
        display_name: Optional[str] = None,
        user_id: Optional[Any] = None,
        avatar_url: Optional[str] = None,
        place_id: Optional[Any] = None,
        place_name: Optional[str] = None,
        uptime_str: Optional[str] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_crashes", True):
            return

        dedup_key = f"crash:{username or ''}:{pid or ''}"
        now_ts = time.time()
        with self.lock:
            # Clean up deduplication cache older than 300s
            self._recent_exit_alerts = {k: v for k, v in self._recent_exit_alerts.items() if (now_ts - v) < 300}
            if now_ts - self._recent_exit_alerts.get(dedup_key, 0.0) < 60:
                return
            self._recent_exit_alerts[dedup_key] = now_ts

        meta = self._resolve_account_meta(username)
        display_name = display_name or meta.get("display_name")
        user_id = user_id or meta.get("user_id")
        avatar_url = avatar_url or meta.get("avatar_url")

        fields = [
            {
                "name": "Account",
                "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**",
                "inline": True,
            }
        ]
        if pid:
            fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
        fields.append({"name": "Status", "value": "🚨 **Crashed**", "inline": True})
        if place_id:
            place_val = f"**{place_name}** (`{place_id}`)" if place_name else f"`{place_id}`"
            fields.append({"name": "Place", "value": place_val, "inline": True})
        if uptime_str:
            fields.append({"name": "Session Duration", "value": f"`{uptime_str}`", "inline": True})
        if reason:
            fields.append({"name": "Crash Diagnostic Detail", "value": str(reason), "inline": False})

        thumb = avatar_url or (
            f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png"
            if user_id
            else None
        )
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico",
        }
        unix_now = int(time.time())

        self._enqueue(
            self.post_embed,
            "Client Crash Alert",
            f"Roblox process for **{display_name or username}** crashed or terminated unexpectedly (<t:{unix_now}:R>).",
            fields,
            0xEF4444,
            thumbnail_url=thumb,
            author=author,
            category="crash",
            is_alert=True,
        )
        if self.config.get("screenshot_on_alert"):
            self._enqueue(self.post_screenshot)

    def notify_closed(
        self,
        username: str,
        pid: Optional[int] = None,
        reason: Optional[str] = None,
        display_name: Optional[str] = None,
        user_id: Optional[Any] = None,
        avatar_url: Optional[str] = None,
        place_id: Optional[Any] = None,
        place_name: Optional[str] = None,
        uptime_str: Optional[str] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_crashes", True):
            return

        dedup_key = f"closed:{username or ''}:{pid or ''}"
        now_ts = time.time()
        with self.lock:
            # Clean up deduplication cache older than 300s
            self._recent_exit_alerts = {k: v for k, v in self._recent_exit_alerts.items() if (now_ts - v) < 300}
            if now_ts - self._recent_exit_alerts.get(dedup_key, 0.0) < 60:
                return
            self._recent_exit_alerts[dedup_key] = now_ts

        meta = self._resolve_account_meta(username)
        display_name = display_name or meta.get("display_name")
        user_id = user_id or meta.get("user_id")
        avatar_url = avatar_url or meta.get("avatar_url")

        fields = [
            {
                "name": "Account",
                "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**",
                "inline": True,
            }
        ]
        if pid:
            fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
        fields.append({"name": "Status", "value": "⚠️ **Closed**", "inline": True})
        if place_id:
            place_val = f"**{place_name}** (`{place_id}`)" if place_name else f"`{place_id}`"
            fields.append({"name": "Place", "value": place_val, "inline": True})
        if uptime_str:
            fields.append({"name": "Session Duration", "value": f"`{uptime_str}`", "inline": True})
        if reason:
            fields.append({"name": "Exit Detail", "value": str(reason), "inline": False})

        thumb = avatar_url or (
            f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png"
            if user_id
            else None
        )
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico",
        }
        unix_now = int(time.time())

        self._enqueue(
            self.post_embed,
            "Client Closed / Disconnected Alert",
            f"Roblox session for **{display_name or username}** closed or disconnected (<t:{unix_now}:R>).",
            fields,
            0xF59E0B,
            thumbnail_url=thumb,
            author=author,
            category="crash",
            is_alert=True,
        )
        if self.config.get("screenshot_on_alert"):
            self._enqueue(self.post_screenshot)

    def notify_account_status_change(
        self,
        username: str,
        new_status: str,
        old_status: Optional[str] = None,
        display_name: Optional[str] = None,
        user_id: Optional[Any] = None,
        avatar_url: Optional[str] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_account_status", True):
            return
        norm_new = str(new_status or "").strip().lower()
        norm_old = str(old_status or "").strip().lower()
        if norm_new not in ("expired", "banned") or norm_new == norm_old:
            return

        now = time.time()
        dedup_key = f"{username.lower()}:{norm_new}"
        with self.lock:
            if now - self._recent_status_alerts.get(dedup_key, 0.0) < 300.0:
                return
            self._recent_status_alerts[dedup_key] = now

        meta = self._resolve_account_meta(username)
        display_name = display_name or meta.get("display_name")
        user_id = user_id or meta.get("user_id")
        avatar_url = avatar_url or meta.get("avatar_url")
        group_name = meta.get("group")

        is_banned = norm_new == "banned"
        title = "Account Banned / Moderated Alert" if is_banned else "Account Cookie Expired Alert"
        color = 0xEF4444 if is_banned else 0xF59E0B
        status_badge = "BANNED / TERMINATED" if is_banned else "COOKIE EXPIRED / LOGGED OUT"

        fields = [
            {
                "name": "Account",
                "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**",
                "inline": True,
            },
            {"name": "New Status", "value": status_badge, "inline": True},
        ]
        if group_name:
            fields.append({"name": "Group", "value": f"`{group_name}`", "inline": True})

        thumb = avatar_url or (
            f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png"
            if user_id
            else None
        )
        unix_now = int(time.time())

        self._enqueue(
            self.post_embed,
            title,
            f"Account **@{username}** transitioned to **{norm_new.upper()}** (<t:{unix_now}:R>). Immediate attention may be required.",
            fields,
            color,
            thumbnail_url=thumb,
            category="account_status",
            is_alert=True,
        )

    def notify_group_relaunch(
        self,
        group_name: str,
        success_count: int,
        total_count: int,
        accounts_list: Optional[List[str]] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_group_relaunch", True):
            return
        unix_now = int(time.time())
        fields = [
            {"name": "Target Group", "value": f"`{group_name}`", "inline": True},
            {"name": "Relaunched", "value": f"**{success_count} / {total_count}** accounts", "inline": True},
        ]
        if accounts_list:
            sample = ", ".join(f"`@{u}`" for u in accounts_list[:15])
            if len(accounts_list) > 15:
                sample += f" (+{len(accounts_list) - 15} more)"
            fields.append({"name": "Accounts", "value": sample, "inline": False})

        self._enqueue(
            self.post_embed,
            "Scheduled Group Auto-Relaunch Completed",
            f"Completed scheduled relaunch cycle for group **{group_name}** (<t:{unix_now}:R>).",
            fields,
            None if success_count == total_count else 0xF59E0B,
            category="group_relaunch",
            is_alert=(success_count < total_count),
        )

    def notify_automation(
        self,
        title: str,
        description: str,
        fields: Optional[List[Dict[str, Any]]] = None,
    ):
        if not self.config.get("enabled") or not self.config.get("send_automation", False):
            return
        self._enqueue(
            self.post_embed,
            title,
            description,
            fields,
            None,
            category="automation",
            is_alert=False,
        )

    def notify_log(self, level: str, message: str):
        if not self.config.get("enabled") or not self.config.get("send_logs", True):
            return
        clean_msg = str(message or "").strip()
        if not clean_msg or "webhook" in clean_msg.lower():
            return
        now = time.time()
        dedup_key = f"{level.lower()}:{clean_msg[:120]}"
        with self.lock:
            last_sent = self._recent_log_hashes.get(dedup_key, 0.0)
            if now - last_sent < 30.0:
                return
            self._recent_log_hashes[dedup_key] = now
            if len(self._recent_log_hashes) > 200:
                cutoff = now - 120.0
                self._recent_log_hashes = {k: v for k, v in self._recent_log_hashes.items() if v >= cutoff}

        is_err = level.lower() in ("error", "fatal", "critical")
        color = 0xEF4444 if is_err else 0xF59E0B
        self._enqueue(
            self.post_embed,
            f"Console Alert [{level.upper()}]",
            f"```\n{clean_msg[:1800]}\n```",
            None,
            color,
            category="log",
            is_alert=is_err,
        )

    def _add_history(
        self,
        event_type: str,
        status: str,
        category: str = "general",
        ok: Optional[bool] = None,
        duration_ms: int = 0,
        endpoint_name: str = "Primary Webhook",
        http_code: int = 0,
        retry_spec: Optional[Dict[str, Any]] = None,
    ):
        with self.lock:
            is_ok = (status == "Success") if ok is None else bool(ok)
            item_id = secrets.token_hex(4)
            entry = {
                "id": item_id,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": event_type,
                "category": category,
                "endpoint": endpoint_name,
                "status": status,
                "ok": is_ok,
                "duration_ms": duration_ms,
                "http_code": http_code,
                "can_retry": retry_spec is not None,
            }
            if retry_spec is not None:
                self._retry_cache[item_id] = retry_spec
                if len(self._retry_cache) > 60:
                    oldest_key = next(iter(self._retry_cache))
                    self._retry_cache.pop(oldest_key, None)

            self.history.insert(0, entry)
            if len(self.history) > 60:
                self.history = self.history[:60]
            self._save_history_unlocked()

    def get_history(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.history)

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = len(self.history)
            succeeded = sum(1 for item in self.history if item.get("ok", item.get("status") == "Success"))
            failed = total - succeeded
            last_ts = self.history[0].get("timestamp") if self.history else None
            avg_latency = 0
            latencies = [int(item.get("duration_ms", 0) or 0) for item in self.history if item.get("duration_ms")]
            if latencies:
                avg_latency = int(sum(latencies) / len(latencies))
            extra_eps = [
                ep for ep in (self.config.get("endpoints") or [])
                if isinstance(ep, dict) and ep.get("enabled", True) and self.is_valid_url(ep.get("url"))
            ]
            primary_valid = self.is_valid_url(self.config.get("webhook_url", ""))
            return {
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
                "avg_latency_ms": avg_latency,
                "last_timestamp": last_ts,
                "url_valid": primary_valid or len(extra_eps) > 0,
                "active_endpoints": (1 if primary_valid else 0) + len(extra_eps),
                "queue_size": self._delivery_queue.qsize(),
                "live_board_active": bool(self.config.get("live_board_message_ids")),
            }
