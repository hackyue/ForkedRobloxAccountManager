import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import threading
import secrets
import tempfile
from typing import Optional, Dict, Any, List
from utils.error_detector import log_detailed_error

class WebhookManager:
    ALLOWED_DISCORD_HOSTS = {
        "discord.com",
        "discordapp.com",
        "canary.discord.com",
        "ptb.discord.com",
        "canary.discordapp.com",
        "ptb.discordapp.com",
    }
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(os.path.expanduser("~"), ".fram")
        os.makedirs(self.data_dir, exist_ok=True)
        self.config_path = os.path.join(self.data_dir, "webhook_config.json")
        self.lock = threading.Lock()
        self.config = {
            "enabled": False,
            "webhook_url": "",
            "send_logs": True,
            "send_launches": True,
            "send_rejoins": True,
            "send_instances": False,
            "ping_user_id": "",
            "redact_sensitive": True,
            "screenshot_enabled": False,
            "screenshot_interval_minutes": 15,
            "screenshot_all_monitors": False,
            "screenshot_window_only": False,
            "instance_summary_enabled": False,
            "instance_summary_interval_minutes": 15
        }
        self.history = []
        self._last_screenshot_time = 0
        self._last_instance_time = 0
        self.running = True
        self.load_config()
        threading.Thread(target=self._start_schedulers, daemon=True).start()

    def load_config(self):
        with self.lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        self.config.update(saved)
                except Exception as e:
                    log_detailed_error("Failed to load webhook config", exc=e, extra_info={"config_path": self.config_path}, source="webhook_manager")

    def save_config(self, new_config=None):
        with self.lock:
            if new_config and isinstance(new_config, dict):
                self.config.update(new_config)
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
            except Exception as e:
                log_detailed_error("Failed to save webhook config", exc=e, extra_info={"config_path": self.config_path}, source="webhook_manager")
        return self.config


    def canonicalize_webhook_url(self, url=None) -> Optional[str]:
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

    def is_valid_url(self, url=None):
        return self.canonicalize_webhook_url(url) is not None

    def _redact_text(self, text):
        if not text or not self.config.get("redact_sensitive", True):
            return text
        pattern = r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[^\s/]+"
        text = re.sub(pattern, "[WEBHOOK_REDACTED]", text)
        cookie_pattern = r"(_\|WARNING:-___(?:BEGIN|DO_NOT_SHARE)[^\"'\s]+)"
        text = re.sub(cookie_pattern, "[COOKIE_REDACTED]", text)
        return text

    def post_embed(self, title, description, fields=None, color=0x6366F1, url=None, thumbnail_url=None, author=None, image_url=None, footer_text=None, footer_icon=None, timestamp=None):
        target_url = (url or self.config.get("webhook_url", "")).strip()
        canonical_url = self.canonicalize_webhook_url(target_url)
        if not canonical_url:
            return False, "Invalid Discord webhook URL."

        redacted_desc = self._redact_text(description)
        embed = {
            "title": title,
            "description": redacted_desc,
            "color": color,
            "footer": {
                "text": footer_text or "Roblox Account Manager"
            },
            "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
            for field in fields:
                if isinstance(field, dict) and "name" in field and "value" in field:
                    clean_fields.append({
                        "name": str(field["name"]),
                        "value": self._redact_text(str(field["value"])),
                        "inline": bool(field.get("inline", True))
                    })
            embed["fields"] = clean_fields

        content = ""
        ping_user = str(self.config.get("ping_user_id", "")).strip()
        if ping_user:
            content = f"<@{ping_user}>"

        payload = {
            "content": content,
            "embeds": [embed]
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                canonical_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "FRAM-WebhookManager/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status in (200, 204):
                    self._add_history(title, "Success")
                    return True, "Webhook sent successfully."
                else:
                    err = f"Discord returned HTTP {response.status}"
                    self._add_history(title, err)
                    return False, err
        except urllib.error.HTTPError as e:
            err = f"HTTP Error {e.code}"
            self._add_history(title, err)
            return False, err
        except Exception as e:
            print(f"[ERROR] Webhook delivery failed: {e}")
            err = "Webhook delivery failed"
            self._add_history(title, err)
            return False, err

    def capture_window_screenshot(self, pid: Optional[int] = None):
        temp_path = os.path.join(tempfile.gettempdir(), f"fram_win_{int(time.time())}_{secrets.token_hex(4)}.png")
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd_target = 0
                if pid:
                    def enum_windows_callback(hwnd, extra):
                        nonlocal hwnd_target
                        if user32.IsWindowVisible(hwnd):
                            lpdw_process_id = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
                            if lpdw_process_id.value == pid:
                                length = user32.GetWindowTextLengthW(hwnd)
                                if length > 0:
                                    buff = ctypes.create_unicode_buffer(length + 1)
                                    user32.GetWindowTextW(hwnd, buff, length + 1)
                                    title = buff.value
                                    if "Roblox" in title:
                                        hwnd_target = hwnd
                                        return False
                                    elif hwnd_target == 0:
                                        hwnd_target = hwnd
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
                else:
                    def find_any_roblox_callback(hwnd, extra):
                        nonlocal hwnd_target
                        if user32.IsWindowVisible(hwnd):
                            length = user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buff, length + 1)
                                title = buff.value
                                if "Roblox" in title:
                                    hwnd_target = hwnd
                                    return False
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                    user32.EnumWindows(WNDENUMPROC(find_any_roblox_callback), 0)

                if hwnd_target != 0:
                    class RECT(ctypes.Structure):
                        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                    rect = RECT()
                    if user32.GetWindowRect(hwnd_target, ctypes.byref(rect)):
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 100 and h > 100:
                            from PIL import ImageGrab
                            bbox = (rect.left, rect.top, rect.right, rect.bottom)
                            img = ImageGrab.grab(bbox=bbox, all_screens=True)
                            img.save(temp_path, "PNG")
                            if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                                return temp_path
            except Exception:
                pass

        if sys.platform == "darwin":
            try:
                import subprocess
                cmd = ["/usr/sbin/screencapture", "-x", "-m", temp_path]
                subprocess.run(cmd, check=True, timeout=10)
                if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                    return temp_path
            except Exception:
                pass

        return self.capture_screenshot(all_monitors=False)

    def capture_screenshot(self, all_monitors=False):
        if self.config.get("screenshot_window_only"):
            win_img = self.capture_window_screenshot()
            if win_img and os.path.isfile(win_img) and os.path.getsize(win_img) > 0:
                return win_img

        temp_path = os.path.join(tempfile.gettempdir(), f"fram_screen_{int(time.time())}_{secrets.token_hex(4)}.png")
        try:
            from PIL import ImageGrab
            if all_monitors:
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
                if not all_monitors:
                    cmd.append("-m")
                cmd.append(temp_path)
                subprocess.run(cmd, check=True, timeout=10)
                if os.path.isfile(temp_path) and os.path.getsize(temp_path) > 0:
                    return temp_path
            except Exception:
                pass
        return None

    def post_screenshot(self, url=None, all_monitors=None):
        target_url = (url or self.config.get("webhook_url", "")).strip()
        canonical_url = self.canonicalize_webhook_url(target_url)
        if not canonical_url:
            return False, "Invalid Discord webhook URL."

        if all_monitors is None:
            all_monitors = bool(self.config.get("screenshot_all_monitors", False))

        file_path = self.capture_screenshot(all_monitors=all_monitors)
        if not file_path or not os.path.exists(file_path):
            return False, "Failed to capture display screenshot."

        try:
            boundary = f"----WebKitFormBoundary{secrets.token_hex(16)}"
            body = bytearray()
            
            payload = {
                "content": "",
                "embeds": [{
                    "title": "📸 Display Capture",
                    "description": f"Display capture ({'Window Only' if self.config.get('screenshot_window_only') else ('All Monitors' if all_monitors else 'Primary Display')}) from **Roblox Account Manager**.",
                    "color": 0x6366F1,
                    "footer": {"text": "Roblox Account Manager • Monitor Capture"},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }]
            }

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n')
            body.extend(json.dumps(payload).encode("utf-8"))
            body.extend(b"\r\n")

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="file"; filename="fram_display.png"\r\nContent-Type: image/png\r\n\r\n')
            body.extend(file_bytes)
            body.extend(b"\r\n")
            body.extend(f"--{boundary}--\r\n".encode("utf-8"))

            req = urllib.request.Request(
                canonical_url,
                data=bytes(body),
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "FRAM-WebhookManager/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status in (200, 204):
                    self._add_history("Monitor Screenshot", "Success")
                    return True, "Screenshot delivered successfully."
                else:
                    err = f"Discord returned HTTP {response.status}"
                    self._add_history("Monitor Screenshot", err)
                    return False, err
        except Exception as e:
            print(f"[ERROR] Screenshot webhook delivery failed: {e}")
            err = "Failed to send screenshot webhook"
            self._add_history("Monitor Screenshot", err)
            return False, err
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def post_window_preview(self, pid: Optional[int] = None, username: Optional[str] = None, place_id: Optional[str] = None, place_name: Optional[str] = None, memory_mb: Optional[float] = None, cpu_percent: Optional[float] = None, uptime_str: Optional[str] = None, url: Optional[str] = None):
        target_url = (url or self.config.get("webhook_url", "")).strip()
        canonical_url = self.canonicalize_webhook_url(target_url)
        if not canonical_url:
            return False, "Invalid Discord webhook URL."

        file_path = self.capture_window_screenshot(pid=pid)
        if not file_path or not os.path.exists(file_path):
            return False, "Failed to capture window preview screenshot."

        try:
            boundary = f"----WebKitFormBoundary{secrets.token_hex(16)}"
            body = bytearray()

            desc_lines = []
            if username:
                desc_lines.append(f"Live window preview for account **@{username}**.")
            elif pid:
                desc_lines.append(f"Live window preview for Roblox PID `{pid}`.")
            else:
                desc_lines.append("Live window preview for active Roblox client.")

            embed_fields = []
            if username:
                embed_fields.append({"name": "Account", "value": f"@{username}", "inline": True})
            if pid:
                embed_fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
            if place_id:
                val = f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})" if place_name else f"`{place_id}`"
                embed_fields.append({"name": "Place", "value": val, "inline": True})
            if uptime_str:
                embed_fields.append({"name": "Uptime", "value": uptime_str, "inline": True})
            if memory_mb is not None:
                embed_fields.append({"name": "Memory", "value": f"{memory_mb} MB", "inline": True})
            if cpu_percent is not None:
                embed_fields.append({"name": "CPU Usage", "value": f"{cpu_percent}%", "inline": True})

            embed = {
                "title": "🎮 Roblox Client Window Preview",
                "description": "\n".join(desc_lines),
                "color": 0x8B5CF6,
                "fields": embed_fields,
                "image": {
                    "url": "attachment://client_preview.png"
                },
                "footer": {
                    "text": "Roblox Account Manager • Window Preview"
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

            content = ""
            ping_user = str(self.config.get("ping_user_id", "")).strip()
            if ping_user:
                content = f"<@{ping_user}>"

            payload = {
                "content": content,
                "embeds": [embed]
            }

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="payload_json"\r\nContent-Type: application/json\r\n\r\n')
            body.extend(json.dumps(payload).encode("utf-8"))
            body.extend(b"\r\n")

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="file"; filename="client_preview.png"\r\nContent-Type: image/png\r\n\r\n')
            body.extend(file_bytes)
            body.extend(b"\r\n")
            body.extend(f"--{boundary}--\r\n".encode("utf-8"))

            req = urllib.request.Request(
                canonical_url,
                data=bytes(body),
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "FRAM-WebhookManager/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status in (200, 204):
                    self._add_history(f"Window Preview ({username or pid or 'Client'})", "Success")
                    return True, "Window preview delivered successfully."
                else:
                    err = f"Discord returned HTTP {response.status}"
                    self._add_history("Window Preview", err)
                    return False, err
        except Exception as e:
            err = "Failed to send window preview webhook"
            self._add_history("Window Preview", err)
            return False, err
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    def post_instance_summary(self, instances_data=None, url=None):
        target_url = (url or self.config.get("webhook_url", "")).strip()
        if not self.is_valid_url(target_url):
            return False, "Invalid Discord webhook URL."

        if instances_data is None:
            try:
                import psutil
                instances_data = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                    name = proc.info.get('name', '') or ''
                    if 'roblox' in name.lower():
                        pid = proc.info.get('pid', 0)
                        mem_bytes = proc.info.get('memory_info').rss if proc.info.get('memory_info') else 0
                        mem_mb = round(mem_bytes / (1024 * 1024), 1)
                        instances_data.append({
                            "pid": pid,
                            "name": name,
                            "memory_mb": mem_mb
                        })
            except Exception:
                instances_data = []

        count = len(instances_data)
        fields = []
        if count == 0:
            fields.append({"name": "Active Roblox Processes", "value": "No active Roblox client processes currently running.", "inline": False})
        else:
            for idx, inst in enumerate(instances_data[:10]):
                pid = inst.get("pid", "N/A")
                account = inst.get("account") or inst.get("name") or f"PID {pid}"
                mem = f"{inst.get('memory_mb', 0)} MB"
                place = inst.get("place", "Roblox Client")
                fields.append({
                    "name": f"Instance #{idx+1}: {account}",
                    "value": f"PID: `{pid}` | Memory: `{mem}` | Status: `{place}`",
                    "inline": False
                })
            if count > 10:
                fields.append({"name": "Additional Instances", "value": f"... and {count - 10} more running instances.", "inline": False})

        return self.post_embed(
            title="📊 Roblox Instance Status Report",
            description=f"Live summary report of **{count}** active Roblox process(es).",
            fields=fields,
            color=0x10B981,
            url=target_url
        )

    def stop(self):
        self.running = False

    def _start_schedulers(self):
        while self.running:
            try:
                for _ in range(30):
                    if not self.running:
                        return
                    time.sleep(1)

                if not self.config.get("enabled"):
                    continue

                now = time.time()

                if self.config.get("screenshot_enabled"):
                    screenshot_interval = int(self.config.get("screenshot_interval_minutes", 15) or 15)
                    if screenshot_interval > 0 and (now - self._last_screenshot_time >= (screenshot_interval * 60)):
                        self._last_screenshot_time = now
                        self.post_screenshot()

                if self.config.get("instance_summary_enabled"):
                    summary_interval = int(self.config.get("instance_summary_interval_minutes", 15) or 15)
                    if summary_interval > 0 and (now - self._last_instance_time >= (summary_interval * 60)):
                        self._last_instance_time = now
                        self.post_instance_summary()

            except Exception:
                pass

    def send_test_webhook(self, url=None):
        target_url = url or self.config.get("webhook_url", "")
        return self.post_embed(
            title="🔔 Webhook Test Connection",
            description="Your Discord log mirror webhook has been successfully configured and connected to **Roblox Account Manager**!",
            fields=[
                {"name": "Status", "value": "🟢 Connected & Active", "inline": True},
                {"name": "Engine", "value": "Tauri + Python API", "inline": True}
            ],
            color=0x10B981,
            url=target_url
        )

    def notify_launch(self, username, place_id=None, job_id=None, display_name=None, user_id=None, avatar_url=None, place_name=None):
        if not self.config.get("enabled") or not self.config.get("send_launches"):
            return
        fields = [
            {"name": "Account", "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**", "inline": True}
        ]
        if place_id:
            place_label = f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})" if place_name else f"[{place_id}](https://www.roblox.com/games/{place_id})"
            fields.append({"name": "Game / Place", "value": place_label, "inline": True})
        else:
            fields.append({"name": "Game / Place", "value": "Home / App", "inline": True})
        if job_id:
            fields.append({"name": "Job / Server ID", "value": f"`{job_id}`", "inline": False})

        thumb = avatar_url or (f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png" if user_id else None)
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico"
        }

        threading.Thread(
            target=self.post_embed,
            args=("🚀 Account Launch Event", f"Account **{display_name or username}** initiated Roblox client launch.", fields, 0x3B82F6),
            kwargs={"thumbnail_url": thumb, "author": author},
            daemon=True
        ).start()

    def notify_rejoin(self, username, place_id, reason=None, display_name=None, user_id=None, avatar_url=None, place_name=None):
        if not self.config.get("enabled") or not self.config.get("send_rejoins"):
            return
        fields = [
            {"name": "Account", "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**", "inline": True}
        ]
        if place_id:
            place_label = f"[{place_name or place_id}](https://www.roblox.com/games/{place_id})" if place_name else f"[{place_id}](https://www.roblox.com/games/{place_id})"
            fields.append({"name": "Target Place", "value": place_label, "inline": True})
        if reason:
            fields.append({"name": "Trigger Reason", "value": str(reason), "inline": False})

        thumb = avatar_url or (f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png" if user_id else None)
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico"
        }

        threading.Thread(
            target=self.post_embed,
            args=("🔄 Auto-Rejoin Triggered", f"Auto-Rejoin monitor re-launched account **{display_name or username}**.", fields, 0xF59E0B),
            kwargs={"thumbnail_url": thumb, "author": author},
            daemon=True
        ).start()

    def notify_crash(self, username, pid=None, reason=None, display_name=None, user_id=None, avatar_url=None):
        if not self.config.get("enabled"):
            return
        fields = [
            {"name": "Account", "value": f"**{display_name}** (`@{username}`)" if display_name else f"**@{username}**", "inline": True}
        ]
        if pid:
            fields.append({"name": "Process PID", "value": f"`{pid}`", "inline": True})
        if reason:
            fields.append({"name": "Status", "value": str(reason), "inline": False})

        thumb = avatar_url or (f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png" if user_id else None)
        author = {
            "name": f"{display_name} (@{username})" if display_name else f"@{username}",
            "icon_url": thumb or "https://www.roblox.com/favicon.ico"
        }

        threading.Thread(
            target=self.post_embed,
            args=("⚠️ Client Crash / Termination", f"Process for **{display_name or username}** terminated unexpectedly or crashed.", fields, 0xEF4444),
            kwargs={"thumbnail_url": thumb, "author": author},
            daemon=True
        ).start()

    def notify_log(self, level, message):
        if not self.config.get("enabled") or not self.config.get("send_logs"):
            return
        color = 0xEF4444 if level.lower() in ("error", "fatal") else 0x6366F1
        threading.Thread(
            target=self.post_embed,
            args=(f"📋 Console Log [{level.upper()}]", message, None, color),
            daemon=True
        ).start()

    def _add_history(self, event_type, status):
        with self.lock:
            import datetime
            self.history.insert(0, {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "event": event_type,
                "status": status
            })
            if len(self.history) > 30:
                self.history = self.history[:30]

    def get_history(self):
        with self.lock:
            return list(self.history)
