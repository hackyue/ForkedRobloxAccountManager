import os
import json
import time
import threading
import requests
from typing import Dict, Any, Optional

from utils.paths import get_cache_folder
from utils.error_detector import log_detailed_error

class IconCacheManager:
    """Thread-safe persistent cache system that downloads and saves icon images to cache/icons/."""
    
    DEFAULT_VALID_TTL = 86400.0 * 30
    DEFAULT_EMPTY_TTL = 300.0

    def __init__(self, cache_file_name: str = "icon_cache.json"):
        self.data_folder = get_cache_folder()
        self.icons_folder = os.path.join(self.data_folder, "icons")
        os.makedirs(self.icons_folder, exist_ok=True)
        self.cache_file_path = os.path.join(self.data_folder, cache_file_name)
        self._lock = threading.RLock()
        self._dirty = False
        self._save_timer = None
        self._memory_cache = {
            "place_icons": {},
            "avatar_icons": {},
            "game_details": {}
        }
        self._load_disk_cache()

    def _schedule_save(self):
        with self._lock:
            self._dirty = True
            if self._save_timer is not None:
                return
            self._save_timer = threading.Timer(2.0, self._flush_dirty_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _flush_dirty_save(self):
        with self._lock:
            self._save_timer = None
            if not self._dirty:
                return
            self._dirty = False
        self._save_disk_cache()

    def flush(self):
        with self._lock:
            if self._save_timer is not None:
                try:
                    self._save_timer.cancel()
                except Exception:
                    pass
                self._save_timer = None
            if self._dirty:
                self._dirty = False
                self._save_disk_cache()

    def _load_disk_cache(self):
        with self._lock:
            if os.path.exists(self.cache_file_path):
                try:
                    with open(self.cache_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._memory_cache["place_icons"] = data.get("place_icons", {})
                            self._memory_cache["avatar_icons"] = data.get("avatar_icons", {})
                            self._memory_cache["game_details"] = data.get("game_details", {})
                except Exception as e:
                    log_detailed_error("Failed to load icon cache from disk", exc=e, extra_info={"cache_file_path": self.cache_file_path}, source="icon_cache")

    def _save_disk_cache(self):
        try:
            temp_path = self.cache_file_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2)
            os.replace(temp_path, self.cache_file_path)
        except Exception as e:
            log_detailed_error("Failed to save icon cache to disk", exc=e, extra_info={"cache_file_path": self.cache_file_path}, source="icon_cache")

    def download_and_save_image(self, url: str, filename: str) -> Optional[str]:
        if not url or not url.startswith(("http://", "https://")):
            return None
        file_path = os.path.join(self.icons_folder, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return f"http://127.0.0.1:5050/api/roblox/icon-file/{filename}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and resp.content:
                temp_file = file_path + ".tmp"
                with open(temp_file, "wb") as f:
                    f.write(resp.content)
                os.replace(temp_file, file_path)
                return f"http://127.0.0.1:5050/api/roblox/icon-file/{filename}"
            else:
                log_detailed_error(
                    "Icon download failed with non-200 status code",
                    extra_info={"url": url, "filename": filename, "status_code": resp.status_code},
                    level="WARNING",
                    source="icon_cache"
                )
        except Exception as e:
            log_detailed_error("Exception while downloading icon image", exc=e, extra_info={"url": url, "filename": filename}, source="icon_cache")
        return None


    def get_place_icon_file_path(self, place_id: str) -> str:
        safe_id = "".join(c for c in str(place_id).strip() if c.isalnum() or c in ("_", "-"))
        return f"place_{safe_id}.png"

    def get_avatar_icon_file_path(self, user_id: str) -> str:
        safe_id = "".join(c for c in str(user_id).strip() if c.isalnum() or c in ("_", "-"))
        return f"avatar_{safe_id}.png"

    def get_place_icon(self, place_id: str) -> Optional[str]:
        if not place_id:
            return None
        key = str(place_id).strip()
        filename = self.get_place_icon_file_path(key)
        local_file_path = os.path.join(self.icons_folder, filename)
        if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
            return f"http://127.0.0.1:5050/api/roblox/icon-file/{filename}"
        with self._lock:
            entry = self._memory_cache["place_icons"].get(key)
            if entry and isinstance(entry, dict):
                timestamp = entry.get("timestamp", 0)
                url = entry.get("local_url") or entry.get("icon_url", "")
                ttl = self.DEFAULT_VALID_TTL if url else self.DEFAULT_EMPTY_TTL
                if time.time() - timestamp < ttl:
                    return url
        return None

    def set_place_icon(self, place_id: str, icon_url: str):
        if not place_id:
            return
        key = str(place_id).strip()
        filename = self.get_place_icon_file_path(key)
        local_url = self.download_and_save_image(icon_url, filename)
        final_url = local_url or icon_url
        with self._lock:
            self._memory_cache["place_icons"][key] = {
                "icon_url": icon_url,
                "local_url": final_url,
                "file": filename,
                "timestamp": time.time()
            }
        self._schedule_save()

    def get_avatar_icon(self, user_id: str) -> Optional[str]:
        if not user_id:
            return None
        key = str(user_id).strip()
        filename = self.get_avatar_icon_file_path(key)
        local_file_path = os.path.join(self.icons_folder, filename)
        if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
            return f"http://127.0.0.1:5050/api/roblox/icon-file/{filename}"
        with self._lock:
            entry = self._memory_cache["avatar_icons"].get(key)
            if entry and isinstance(entry, dict):
                timestamp = entry.get("timestamp", 0)
                url = entry.get("local_url") or entry.get("avatar_url", "")
                ttl = self.DEFAULT_VALID_TTL if url else self.DEFAULT_EMPTY_TTL
                if time.time() - timestamp < ttl:
                    return url
        return None

    def set_avatar_icon(self, user_id: str, avatar_url: str):
        if not user_id:
            return
        key = str(user_id).strip()
        filename = self.get_avatar_icon_file_path(key)
        local_url = self.download_and_save_image(avatar_url, filename)
        final_url = local_url or avatar_url
        with self._lock:
            self._memory_cache["avatar_icons"][key] = {
                "avatar_url": avatar_url,
                "local_url": final_url,
                "file": filename,
                "timestamp": time.time()
            }
        self._schedule_save()

    def get_game_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        if not place_id:
            return None
        key = str(place_id).strip()
        with self._lock:
            entry = self._memory_cache["game_details"].get(key)
            if entry and isinstance(entry, dict):
                timestamp = entry.get("timestamp", 0)
                data = entry.get("data")
                if data and isinstance(data, dict):
                    filename = self.get_place_icon_file_path(key)
                    local_file_path = os.path.join(self.icons_folder, filename)
                    if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 0:
                        data["icon_url"] = f"http://127.0.0.1:5050/api/roblox/icon-file/{filename}"
                    has_icon = bool(data.get("icon_url"))
                    ttl = self.DEFAULT_VALID_TTL if has_icon else self.DEFAULT_EMPTY_TTL
                    if time.time() - timestamp < ttl:
                        return data
        return None

    def set_game_details(self, place_id: str, details: Dict[str, Any]):
        if not place_id or not isinstance(details, dict):
            return
        key = str(place_id).strip()
        raw_icon_url = details.get("icon_url", "")
        if raw_icon_url and raw_icon_url.startswith(("http://", "https://")):
            filename = self.get_place_icon_file_path(key)
            local_url = self.download_and_save_image(raw_icon_url, filename)
            if local_url:
                details["icon_url"] = local_url
        with self._lock:
            self._memory_cache["game_details"][key] = {
                "data": details,
                "timestamp": time.time()
            }
            if raw_icon_url:
                self._memory_cache["place_icons"][key] = {
                    "icon_url": raw_icon_url,
                    "local_url": details.get("icon_url") or raw_icon_url,
                    "timestamp": time.time()
                }
        self._schedule_save()

    def clear(self):
        with self._lock:
            self._memory_cache = {
                "place_icons": {},
                "avatar_icons": {},
                "game_details": {}
            }
            self._save_disk_cache()
            if os.path.exists(self.icons_folder):
                for f in os.listdir(self.icons_folder):
                    try:
                        os.remove(os.path.join(self.icons_folder, f))
                    except Exception:
                        pass

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            file_count = 0
            disk_bytes = 0
            if os.path.exists(self.icons_folder):
                for f in os.listdir(self.icons_folder):
                    fp = os.path.join(self.icons_folder, f)
                    try:
                        if os.path.isfile(fp):
                            file_count += 1
                            disk_bytes += os.path.getsize(fp)
                    except Exception:
                        pass
            if os.path.exists(self.cache_file_path):
                try:
                    disk_bytes += os.path.getsize(self.cache_file_path)
                except Exception:
                    pass
            return {
                "place_icons": len(self._memory_cache["place_icons"]),
                "avatar_icons": len(self._memory_cache["avatar_icons"]),
                "game_details": len(self._memory_cache["game_details"]),
                "saved_image_files": file_count,
                "disk_bytes": disk_bytes,
                "disk_size_mb": round(disk_bytes / (1024 * 1024), 2)
            }

icon_cache = IconCacheManager()
