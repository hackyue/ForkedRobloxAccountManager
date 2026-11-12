"""
Roblox API interaction utilities
Handles authentication, info, and game launching
"""

import os
import json
import ipaddress
import platform
import time
import random
import subprocess
import threading
import uuid
import re
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from urllib.parse import quote, parse_qs, urlparse, urlsplit
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from classes.icon_cache import icon_cache
from utils.error_detector import log_detailed_error




@dataclass(frozen=True)
class PublicServerCandidate:
    job_id: str
    playing: int
    max_players: int
    fill_ratio: float
    ping: Optional[int] = None
    region_text: str = ""


@dataclass(frozen=True)
class ServerRegionDetails:
    city: str = ""
    region: str = ""
    country: str = ""
    country_code: str = ""
    text: str = ""

    @property
    def search_text(self) -> str:
        return " ".join(
            value
            for value in (self.city, self.region, self.country, self.country_code, self.text)
            if value
        )


class RobloxAPI:
    """Handles all Roblox API interactions"""

    BOOTSTRAPPER_CLIENTS = (
        {
            "name": "Bloxstrap",
            "root": r"%LOCALAPPDATA%\Bloxstrap",
            "launcher": "Bloxstrap.exe",
            "version_dirs": ("Versions",),
        },
        {
            "name": "Fishstrap",
            "root": r"%LOCALAPPDATA%\Fishstrap",
            "launcher": "Fishstrap.exe",
            "version_dirs": ("Versions",),
        },
        {
            "name": "Voidstrap",
            "root": r"%LOCALAPPDATA%\Voidstrap",
            "launcher": "Voidstrap.exe",
            "version_dirs": ("RblxVersions",),
        },
        {
            "name": "FrostStrap",
            "root": r"%LOCALAPPDATA%\FrostStrap",
            "launcher": "FrostStrap.exe",
            "version_dirs": ("Versions",),
        },
        {
            "name": "ExploitStrap",
            "root": r"%LOCALAPPDATA%\ExploitStrap",
            "launcher": "ExploitStrap.exe",
            "version_dirs": ("Versions",),
        },
    )

    BOOTSTRAPPER_EXE_MAP = {
        "bloxstrap": (r"%LOCALAPPDATA%\Bloxstrap\Bloxstrap.exe", True),
        "fishstrap": (r"%LOCALAPPDATA%\Fishstrap\Fishstrap.exe", True),
        "voidstrap": (r"%LOCALAPPDATA%\Voidstrap\Voidstrap.exe", True),
        "froststrap": (r"%LOCALAPPDATA%\FrostStrap\FrostStrap.exe", True),
        "exploitstrap": (r"%LOCALAPPDATA%\ExploitStrap\ExploitStrap.exe", True),
        "robloxplayerlauncher": ("RobloxPlayerLauncher.exe", False),
    }

    _protocol_handler_missing_warned = False
    _http_session = None
    _http_session_lock = threading.Lock()
    _server_region_cache: dict[str, Optional[ServerRegionDetails]] = {}
    _ip_region_cache: dict[str, Optional[ServerRegionDetails]] = {}
    _server_region_cache_lock = threading.Lock()
    _public_server_region_probe_limit: int = 30
    _recent_launch_records: list[dict[str, Any]] = []
    _launch_records_lock = threading.Lock()

    @staticmethod
    def record_launch_ticket(
        username: str,
        place_id: str,
        browser_tracker_id: int,
        launch_time_ms: int,
        auth_ticket: str = "",
        spawned_pid: Optional[int] = None,
    ) -> str:
        now = time.time()
        record_id = str(uuid.uuid4())
        uname = str(username or "").strip()
        record = {
            "record_id": record_id,
            "username": uname,
            "username_lower": uname.lower(),
            "place_id": str(place_id or "").strip(),
            "browser_tracker_id": str(browser_tracker_id or "").strip(),
            "launch_time_ms": str(launch_time_ms or "").strip(),
            "auth_ticket": str(auth_ticket or "").strip(),
            "timestamp": now,
            "spawned_pid": int(spawned_pid) if spawned_pid and int(spawned_pid) > 0 else None,
            "claimed_pid": int(spawned_pid) if spawned_pid and int(spawned_pid) > 0 else None,
        }
        with RobloxAPI._launch_records_lock:
            RobloxAPI._recent_launch_records = [
                r for r in RobloxAPI._recent_launch_records
                if (now - float(r.get("timestamp", 0.0))) < 3600.0
            ]
            RobloxAPI._recent_launch_records.append(record)
            if len(RobloxAPI._recent_launch_records) > 200:
                RobloxAPI._recent_launch_records = RobloxAPI._recent_launch_records[-200:]
        return record_id

    @staticmethod
    def update_launch_ticket_spawned_pid(record_id: str, spawned_pid: int) -> None:
        if not record_id or not spawned_pid or int(spawned_pid) <= 0:
            return
        with RobloxAPI._launch_records_lock:
            for r in RobloxAPI._recent_launch_records:
                if r.get("record_id") == record_id:
                    r["spawned_pid"] = int(spawned_pid)
                    r["claimed_pid"] = int(spawned_pid)
                    break

    @staticmethod
    def claim_launch_record_pid(record_id: str, pid: int) -> None:
        if not record_id or not pid or int(pid) <= 0:
            return
        pid_int = int(pid)
        with RobloxAPI._launch_records_lock:
            for r in RobloxAPI._recent_launch_records:
                if r.get("claimed_pid") == pid_int and r.get("record_id") != record_id:
                    r["claimed_pid"] = None
                if r.get("record_id") == record_id:
                    r["claimed_pid"] = pid_int

    @staticmethod
    def get_recent_launch_records(max_age_sec: float = 3600.0) -> list[dict[str, Any]]:
        now = time.time()
        with RobloxAPI._launch_records_lock:
            return [
                dict(r) for r in RobloxAPI._recent_launch_records
                if (now - float(r.get("timestamp", 0.0))) <= max_age_sec
            ]

    @staticmethod
    def _set_bounded_cache(target_dict: dict, key: str, value: Any, max_size: int = 2000):
        if len(target_dict) >= max_size and key not in target_dict:
            try:
                evict_count = max(1, max_size // 5)
                for k in list(target_dict.keys())[:evict_count]:
                    target_dict.pop(k, None)
            except Exception:
                pass
        target_dict[key] = value

    _server_region_aliases: dict[str, tuple[str, ...]] = {
        "australia": ("australia", "sydney", "melbourne", "au"),
        "brazil": ("brazil", "sao paulo", "saopaulo", "brasil", "br"),
        "canada": ("canada", "montreal", "toronto", "ca"),
        "europe": (
            "europe",
            "amsterdam",
            "frankfurt",
            "germany",
            "netherlands",
            "france",
            "paris",
            "london",
            "united kingdom",
            "ireland",
            "spain",
            "sweden",
            "poland",
            "italy",
        ),
        "france": ("france", "paris", "fr"),
        "germany": ("germany", "deutschland", "frankfurt", "de"),
        "hong kong": ("hong kong", "hongkong", "hk"),
        "india": ("india", "mumbai", "delhi", "in"),
        "japan": ("japan", "tokyo", "osaka", "jp"),
        "netherlands": ("netherlands", "amsterdam", "nl"),
        "singapore": ("singapore", "sg"),
        "south korea": ("south korea", "korea", "seoul", "kr"),
        "united kingdom": ("united kingdom", "great britain", "england", "london", "gb", "uk"),
        "united states": ("united states", "usa", "america", "us"),
        "us central": (
            "us central",
            "central united states",
            "illinois",
            "chicago",
            "texas",
            "dallas",
            "iowa",
            "ohio",
        ),
        "us east": (
            "us east",
            "east us",
            "eastern united states",
            "virginia",
            "ashburn",
            "new york",
            "new jersey",
            "florida",
            "miami",
            "georgia",
            "atlanta",
        ),
        "us west": (
            "us west",
            "west us",
            "western united states",
            "california",
            "los angeles",
            "san jose",
            "oregon",
            "washington",
            "seattle",
        ),
    }

    @staticmethod
    def _subprocess_no_window_kwargs():
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

    @staticmethod
    def _get_http_session():
        """Shared session for non-authenticated GET calls to reuse TCP connections."""
        if RobloxAPI._http_session is not None:
            return RobloxAPI._http_session

        with RobloxAPI._http_session_lock:
            if RobloxAPI._http_session is None:
                session = requests.Session()
                retry = Retry(
                    total=2,
                    backoff_factor=0.35,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
                )
                adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retry)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                session.headers.update({
                    "User-Agent": "Roblox/WinInet",
                })
                RobloxAPI._http_session = session

        return RobloxAPI._http_session

    @staticmethod
    def close_http_session():
        session = RobloxAPI._http_session
        RobloxAPI._http_session = None
        if session is None:
            return
        try:
            session.close()
        except Exception:
            pass

    @staticmethod
    def _log_debug(enabled, message):
        if enabled:
            print(f"[DEBUG] {message}")

    @staticmethod
    def _normalize_region_search_text(value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

    @staticmethod
    def _preferred_region_terms(preferred_region: Any) -> tuple[str, ...]:
        normalized = RobloxAPI._normalize_region_search_text(preferred_region)
        if not normalized:
            return ()
        return RobloxAPI._server_region_aliases.get(normalized, (normalized,))

    @staticmethod
    def _server_region_matches(details: ServerRegionDetails, preferred_region: Any) -> bool:
        terms = RobloxAPI._preferred_region_terms(preferred_region)
        if not terms:
            return False

        normalized_text = RobloxAPI._normalize_region_search_text(details.search_text)
        if not normalized_text:
            return False

        text_tokens = set(normalized_text.split())
        country_code = RobloxAPI._normalize_region_search_text(details.country_code)
        for term in terms:
            normalized_term = RobloxAPI._normalize_region_search_text(term)
            if not normalized_term:
                continue
            if len(normalized_term) <= 3:
                if normalized_term == country_code or normalized_term in text_tokens:
                    return True
                continue
            if normalized_term in normalized_text:
                return True
        return False

    @staticmethod
    def _coerce_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_optional_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_public_server_region_text(value: Any, depth: int = 0) -> str:
        if depth > 3:
            return ""

        region_parts: list[str] = []
        region_key_markers = ("region", "location", "country", "city", "datacenter", "data_center", "data center")
        if isinstance(value, dict):
            for key, nested_value in value.items():
                normalized_key = RobloxAPI._normalize_region_search_text(key)
                key_matches = any(marker in normalized_key for marker in region_key_markers)
                if key_matches and isinstance(nested_value, (str, int, float)):
                    region_parts.append(str(nested_value))
                elif key_matches or isinstance(nested_value, (dict, list, tuple)):
                    nested_text = RobloxAPI._extract_public_server_region_text(nested_value, depth + 1)
                    if nested_text:
                        region_parts.append(nested_text)
        elif isinstance(value, (list, tuple)):
            for nested_value in value:
                nested_text = RobloxAPI._extract_public_server_region_text(nested_value, depth + 1)
                if nested_text:
                    region_parts.append(nested_text)

        return " ".join(region_parts)

    @staticmethod
    def _extract_public_server_region_details(server: Any) -> Optional[ServerRegionDetails]:
        region_text = RobloxAPI._extract_public_server_region_text(server)
        if not region_text:
            return None
        return ServerRegionDetails(text=region_text)

    @staticmethod
    def _create_gamejoin_probe_session(roblosecurity_cookie: Optional[str] = None) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        retry = Retry(
            total=1,
            backoff_factor=0.25,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "POST"]),
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Roblox/WinInet",
            "Referer": "https://www.roblox.com/",
        })

        normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
        if normalized_cookie:
            session.cookies.set(".ROBLOSECURITY", normalized_cookie, domain=".roblox.com")
        return session

    @staticmethod
    def _extract_join_script_address(join_script: Any) -> str:
        if not isinstance(join_script, dict):
            return ""

        for endpoint_key in ("UdmuxEndpoints", "ServerConnections"):
            endpoints = join_script.get(endpoint_key)
            if not isinstance(endpoints, list):
                continue
            for endpoint in endpoints:
                if not isinstance(endpoint, dict):
                    continue
                address = str(endpoint.get("Address") or "").strip()
                if address:
                    return address

        return str(join_script.get("MachineAddress") or "").strip()

    @staticmethod
    def _get_ip_region_details(
        address: str,
        session: requests.Session,
        enable_debug: bool = False,
    ) -> Optional[ServerRegionDetails]:
        normalized_address = str(address or "").strip()
        if not normalized_address:
            return None

        try:
            parsed_address = ipaddress.ip_address(normalized_address)
        except ValueError:
            RobloxAPI._log_debug(enable_debug, f"Server region lookup skipped: invalid IP address '{normalized_address}'.")
            return None

        if not parsed_address.is_global:
            RobloxAPI._log_debug(enable_debug, f"Server region lookup skipped: non-public IP address '{normalized_address}'.")
            return None

        with RobloxAPI._server_region_cache_lock:
            if normalized_address in RobloxAPI._ip_region_cache:
                return RobloxAPI._ip_region_cache[normalized_address]

        try:
            response = session.get(f"https://ipwho.is/{normalized_address}", timeout=5)
            response.raise_for_status()
            payload = response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            RobloxAPI._log_debug(enable_debug, f"Server IP geolocation request failed for {normalized_address}: {exc}")
            return None
        except ValueError as exc:
            RobloxAPI._log_debug(enable_debug, f"Server IP geolocation response could not be parsed for {normalized_address}: {exc}")
            return None

        if not isinstance(payload, dict):
            RobloxAPI._log_debug(enable_debug, f"Server IP geolocation returned an unexpected payload for {normalized_address}.")
            return None

        if payload.get("success") is False:
            message = str(payload.get("message") or "unknown error")
            RobloxAPI._log_debug(enable_debug, f"Server IP geolocation failed for {normalized_address}: {message}")
            with RobloxAPI._server_region_cache_lock:
                RobloxAPI._set_bounded_cache(RobloxAPI._ip_region_cache, normalized_address, None)
            return None

        details = ServerRegionDetails(
            city=str(payload.get("city") or "").strip(),
            region=str(payload.get("region") or "").strip(),
            country=str(payload.get("country") or "").strip(),
            country_code=str(payload.get("country_code") or "").strip(),
            text=normalized_address,
        )
        if not details.search_text.strip():
            with RobloxAPI._server_region_cache_lock:
                RobloxAPI._set_bounded_cache(RobloxAPI._ip_region_cache, normalized_address, None)
            return None

        with RobloxAPI._server_region_cache_lock:
            RobloxAPI._set_bounded_cache(RobloxAPI._ip_region_cache, normalized_address, details)
        return details

    @staticmethod
    def _get_game_instance_region_details(
        place_id: str,
        job_id: str,
        gamejoin_session: requests.Session,
        geolocation_session: requests.Session,
        enable_debug: bool = False,
    ) -> Optional[ServerRegionDetails]:
        place_id_text = str(place_id or "").strip()
        job_id_text = str(job_id or "").strip()
        if not place_id_text or not job_id_text:
            return None

        cache_key = f"{place_id_text}:{job_id_text}"
        with RobloxAPI._server_region_cache_lock:
            if cache_key in RobloxAPI._server_region_cache:
                return RobloxAPI._server_region_cache[cache_key]

        try:
            place_id_value = int(place_id_text)
        except ValueError:
            return None

        payload = {
            "placeId": place_id_value,
            "gameId": job_id_text,
            "gameJoinAttemptId": str(uuid.uuid4()),
        }

        try:
            response = gamejoin_session.post(
                "https://gamejoin.roblox.com/v1/join-game-instance",
                json=payload,
                timeout=8,
            )
            csrf_token = response.headers.get("x-csrf-token")
            if response.status_code == 403 and csrf_token:
                gamejoin_session.headers["X-CSRF-TOKEN"] = csrf_token
                response = gamejoin_session.post(
                    "https://gamejoin.roblox.com/v1/join-game-instance",
                    json=payload,
                    timeout=8,
                )
            response.raise_for_status()
            response_payload = response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            RobloxAPI._log_debug(enable_debug, f"Game instance region probe failed for server {job_id_text}: {exc}")
            return None
        except ValueError as exc:
            RobloxAPI._log_debug(enable_debug, f"Game instance region probe response could not be parsed for server {job_id_text}: {exc}")
            return None

        if not isinstance(response_payload, dict):
            RobloxAPI._log_debug(enable_debug, f"Game instance region probe returned an unexpected payload for server {job_id_text}.")
            return None

        join_script = response_payload.get("joinScript")
        if not isinstance(join_script, dict):
            status = str(response_payload.get("status") or "unknown")
            message = str(response_payload.get("message") or "").strip()
            detail = f": {message}" if message else ""
            RobloxAPI._log_debug(enable_debug, f"Game instance region unavailable for server {job_id_text}; status {status}{detail}.")
            with RobloxAPI._server_region_cache_lock:
                RobloxAPI._set_bounded_cache(RobloxAPI._server_region_cache, cache_key, None)
            return None

        address = RobloxAPI._extract_join_script_address(join_script)
        details = RobloxAPI._get_ip_region_details(address, geolocation_session, enable_debug=enable_debug)
        with RobloxAPI._server_region_cache_lock:
            RobloxAPI._set_bounded_cache(RobloxAPI._server_region_cache, cache_key, details)
        return details

    @staticmethod
    def _rank_public_server_candidates_by_region(
        place_id: str,
        candidates: list[PublicServerCandidate],
        preferred_region: str,
        roblosecurity_cookie: Optional[str],
        enable_debug: bool = False,
    ) -> list[PublicServerCandidate]:
        if not candidates or not RobloxAPI._preferred_region_terms(preferred_region):
            return candidates

        matching_candidates: list[PublicServerCandidate] = []
        non_matching_candidates: list[PublicServerCandidate] = []
        deferred_candidates: list[PublicServerCandidate] = []
        probed_count = 0
        gamejoin_session = RobloxAPI._create_gamejoin_probe_session(roblosecurity_cookie)
        geolocation_session = RobloxAPI._get_http_session()

        try:
            for candidate in candidates:
                inline_details = ServerRegionDetails(text=candidate.region_text) if candidate.region_text else None
                if inline_details is not None and RobloxAPI._server_region_matches(inline_details, preferred_region):
                    matching_candidates.append(candidate)
                    continue

                if probed_count >= RobloxAPI._public_server_region_probe_limit:
                    deferred_candidates.append(candidate)
                    continue

                probed_count += 1
                details = RobloxAPI._get_game_instance_region_details(
                    place_id,
                    candidate.job_id,
                    gamejoin_session,
                    geolocation_session,
                    enable_debug=enable_debug,
                )
                if details is not None and RobloxAPI._server_region_matches(details, preferred_region):
                    matching_candidates.append(candidate)
                else:
                    non_matching_candidates.append(candidate)
        finally:
            try:
                gamejoin_session.close()
            except requests.exceptions.RequestException:
                pass

        if matching_candidates:
            RobloxAPI._log_debug(
                enable_debug,
                (
                    f"Preferred server region '{preferred_region}' matched "
                    f"{len(matching_candidates)} of {probed_count} probed public server candidates."
                ),
            )
            return matching_candidates + non_matching_candidates + deferred_candidates

        RobloxAPI._log_debug(
            enable_debug,
            (
                f"Preferred server region '{preferred_region}' did not match "
                f"the first {probed_count} public server candidates; using the normal order."
            ),
        )
        return non_matching_candidates + deferred_candidates

    @staticmethod
    def _format_token_preview(cookie):
        if not cookie:
            return "(No token found)"
        if len(cookie) > 60:
            return f"{cookie[:50]}...{cookie[-10:]}"
        return cookie

    @staticmethod
    def build_private_server_share_url(code):
        share_code = str(code or "").strip()
        if not share_code:
            return ""
        return f"https://www.roblox.com/share?code={share_code}&type=Server"

    @staticmethod
    def extract_private_server_share_details(value, max_depth=3):
        text = str(value or "").strip()
        if not text or max_depth < 0:
            return None

        def build_result(code_value):
            share_code = str(code_value or "").strip()
            if not share_code:
                return None
            return {
                "code": share_code,
                "type": "Server",
                "url": RobloxAPI.build_private_server_share_url(share_code),
            }

        try:
            candidate = text.strip()
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
                candidate = f"https://{candidate}"

            parsed = urlparse(candidate)
            scheme = str(parsed.scheme or "").strip().lower()
            host = str(parsed.netloc or "").strip().lower()
            if host.startswith("www."):
                host = host[4:]
            path = str(parsed.path or "").strip("/").lower()
            query_values = parse_qs(parsed.query or "")

            share_type_values = query_values.get("type") or query_values.get("pid") or []
            share_type = str(share_type_values[0] or "").strip().lower() if share_type_values else ""
            share_code_values = query_values.get("code") or []
            share_code = str(share_code_values[0] or "").strip() if share_code_values else ""

            if scheme == "roblox" and host == "navigation" and path == "share_links" and share_type == "server":
                result = build_result(share_code)
                if result:
                    return result

            if (host == "roblox.com" or host.endswith(".roblox.com")) and path in ("share", "share-links") and share_type == "server":
                result = build_result(share_code)
                if result:
                    return result

            for nested_key in ("af_dp", "af_web_dp", "deep_link_value"):
                nested_values = query_values.get(nested_key) or []
                for nested_value in nested_values:
                    nested_result = RobloxAPI.extract_private_server_share_details(
                        nested_value,
                        max_depth=max_depth - 1,
                    )
                    if nested_result:
                        return nested_result
        except Exception:
            pass

        match = re.search(
            r"(?i)(?:roblox://navigation/share_links|https?://(?:www\.)?roblox\.com/(?:share|share-links))[^\s]*",
            text,
        )
        if match:
            found_url = match.group(0)
            code_match = re.search(r"[?&]code=([A-Za-z0-9_-]+)", found_url)
            type_match = re.search(r"[?&](?:type|pid)=Server\b", found_url, re.IGNORECASE)
            if code_match and type_match:
                return build_result(code_match.group(1))
        return None

    @staticmethod
    def _extract_nested_string_value(value, key_names):
        ordered_key_names = [str(name).strip().lower() for name in (key_names or []) if str(name or "").strip()]

        def to_text(node):
            if isinstance(node, (dict, list, tuple, set)) or node is None:
                return ""
            return str(node).strip()

        def walk(node, target_key_name):
            if isinstance(node, dict):
                for key, item in node.items():
                    if str(key or "").strip().lower() == target_key_name:
                        text = to_text(item)
                        if text:
                            return text
                    nested = walk(item, target_key_name)
                    if nested:
                        return nested
            elif isinstance(node, (list, tuple, set)):
                for item in node:
                    nested = walk(item, target_key_name)
                    if nested:
                        return nested
            return ""

        for key_name in ordered_key_names:
            text = walk(value, key_name)
            if text:
                return text
        return ""

    @staticmethod
    def resolve_private_server_share_link(value, roblosecurity_cookie, enable_debug=False):
        share_details = RobloxAPI.extract_private_server_share_details(value)
        if not share_details:
            return None

        result = {
            "share_code": str(share_details.get("code") or "").strip(),
            "access_code": str(share_details.get("code") or "").strip(),
            "link_code": "",
            "place_id": "",
            "url": str(share_details.get("url") or "").strip(),
        }

        session = RobloxAPI._create_authenticated_session(roblosecurity_cookie)
        if session is None:
            RobloxAPI._log_debug(enable_debug, "Private server share link resolution skipped: authenticated session unavailable.")
            return result

        try:
            response = session.post(
                "https://apis.roblox.com/sharelinks/v1/resolve-link",
                json={
                    "linkId": result["share_code"],
                    "linkType": "Server",
                },
                timeout=10,
            )
            if response.status_code == 401:
                RobloxAPI._log_debug(enable_debug, "Private server share link resolution requires web authentication; using the share code as access code.")
                return result

            response.raise_for_status()
            payload = response.json() if response.content else {}
            invite_data = payload.get("privateServerInviteData") or payload

            result["place_id"] = RobloxAPI._extract_nested_string_value(
                invite_data,
                ("placeId", "rootPlaceId", "experienceId"),
            )
            result["link_code"] = RobloxAPI._extract_nested_string_value(
                invite_data,
                ("linkCode", "privateServerLinkCode", "privateServerId", "vipServerId"),
            )

            resolved_access_code = RobloxAPI._extract_nested_string_value(
                invite_data,
                ("accessCode", "privateServerAccessCode"),
            )
            if resolved_access_code:
                result["access_code"] = resolved_access_code

            RobloxAPI._log_debug(
                enable_debug,
                (
                    "Resolved private server share link: "
                    f"place_id={'set' if result['place_id'] else 'none'}, "
                    f"link_code={'set' if result['link_code'] else 'none'}, "
                    f"access_code={'set' if result['access_code'] else 'none'}."
                ),
            )
        except requests.exceptions.RequestException as exc:
            print(f"[WARNING] Failed to resolve private server share link: {exc}")
        except ValueError as exc:
            print(f"[WARNING] Failed to parse private server share link response: {exc}")
        except Exception as exc:
            print(f"[WARNING] Unexpected error resolving private server share link: {exc}")
        finally:
            try:
                session.close()
            except Exception:
                pass

        return result

    @staticmethod
    def normalize_private_server(value, roblosecurity_cookie=None):
        text = str(value or "").strip()
        if not text:
            return ""

        share_details = RobloxAPI.extract_private_server_share_details(text)
        if share_details:
            resolved_share_link = RobloxAPI.resolve_private_server_share_link(text, roblosecurity_cookie)
            if resolved_share_link:
                resolved_link_code = str(resolved_share_link.get("link_code") or "").strip()
                if resolved_link_code:
                    return resolved_link_code
                resolved_access_code = str(resolved_share_link.get("access_code") or "").strip()
                if resolved_access_code:
                    return resolved_access_code
            return str(share_details.get("url") or text).strip()

        parsed_code = ""
        candidate = text.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
            candidate = f"https://{candidate}"
        try:
            parsed = urlparse(candidate)
            hostname = (parsed.hostname or "").lower()
            if hostname == "roblox.com" or hostname.endswith(".roblox.com"):
                query_values = parse_qs(parsed.query or "")
                for key in ("privateServerLinkCode", "linkCode", "privateServerId", "vipServerId"):
                    values = query_values.get(key) or []
                    if values:
                        parsed_code = str(values[0] or "").strip()
                        if parsed_code:
                            break
        except Exception:
            parsed_code = ""

        if not parsed_code:
            match = re.search(
                r"(?i)(?:privateServerLinkCode|linkCode|privateServerId|vipServerId)\s*=\s*([A-Za-z0-9_-]+)",
                text,
            )
            if match:
                parsed_code = str(match.group(1) or "").strip()

        if parsed_code:
            return parsed_code
        return text
    
    @staticmethod
    def _normalize_roblosecurity_cookie(cookie):
        if cookie is None:
            return ""

        value = str(cookie).strip()

        if (len(value) >= 2) and (value[0] == value[-1]) and value[0] in ("\"", "'"):
            value = value[1:-1].strip()

        if value.lower().startswith("cookie:"):
            value = value.split(":", 1)[1].strip()

        marker = ".ROBLOSECURITY="
        if marker in value:
            value = value.split(marker, 1)[1]

        if ";" in value:
            value = value.split(";", 1)[0].strip()

        return value

    @staticmethod
    def _create_authenticated_session(roblosecurity_cookie):
        """Return a requests session bound to the provided cookie and CSRF token."""
        roblosecurity_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
        if not roblosecurity_cookie:
            return None

        session = requests.Session()
        session.trust_env = False
        session.cookies.set(".ROBLOSECURITY", roblosecurity_cookie, domain=".roblox.com", path="/")
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://www.roblox.com/",
            "Origin": "https://www.roblox.com",
            "Cookie": f".ROBLOSECURITY={roblosecurity_cookie}",
            "Accept": "application/json",
        })

        csrf_token = RobloxAPI._fetch_csrf_token(session)
        if csrf_token:
            session.headers["X-CSRF-TOKEN"] = csrf_token

        return session

    @staticmethod
    def _fetch_csrf_token(session):
        """Try to obtain a CSRF token using a non-destructive POST probe."""
        probe_urls = (
            "https://auth.roblox.com/v2/login",
            "https://auth.roblox.com/v1/authentication-ticket",
            "https://accountsettings.roblox.com/v1/email",
        )
        for probe_url in probe_urls:
            try:
                probe = session.post(probe_url, json={}, timeout=10)
                token = probe.headers.get("x-csrf-token")
                if token:
                    return token
            except Exception:
                continue
        return None

    @staticmethod
    def get_username_from_api(roblosecurity_cookie):
        """Get username using Roblox API"""
        try:
            roblosecurity_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
            if not roblosecurity_cookie:
                return "Unknown"
            headers = {
                'Cookie': f'.ROBLOSECURITY={roblosecurity_cookie}'
            }
            
            response = RobloxAPI._get_http_session().get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return user_data.get('name', 'Unknown')
            else:
                profile = RobloxAPI.get_user_profile_from_cookie(roblosecurity_cookie)
                if profile and profile.get('username'):
                    return profile.get('username')
                log_detailed_error(
                    "Roblox API authenticated user endpoint returned non-200 status code",
                    extra_info={"status_code": response.status_code, "response_text": response.text[:300]},
                    level="WARNING",
                    source="roblox_api"
                )
        except Exception as e:
            log_detailed_error("Failed to get username from Roblox API", exc=e, source="roblox_api")
        
        return "Unknown"

    @staticmethod
    def _check_banned_cookie_profile(roblosecurity_cookie, session=None):
        try:
            cookie_val = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
            if not cookie_val:
                return None
            sess = session or requests.Session()
            sess.trust_env = False
            headers = {
                'Cookie': f'.ROBLOSECURITY={cookie_val}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            resp = sess.get('https://www.roblox.com/not-approved', headers=headers, timeout=10, allow_redirects=False)
            is_banned_page = False
            page_text = ""
            final_url = ""

            if resp.status_code == 200:
                is_banned_page = True
                page_text = resp.text
                final_url = str(resp.url)
            elif resp.status_code in (301, 302, 303, 307, 308):
                loc = str(resp.headers.get('Location', '')).lower()
                if '/not-approved' in loc or '/notapproved' in loc:
                    resp_follow = sess.get('https://www.roblox.com/not-approved', headers=headers, timeout=10, allow_redirects=True)
                    if resp_follow.status_code == 200:
                        is_banned_page = True
                        page_text = resp_follow.text
                        final_url = str(resp_follow.url)
            
            if not is_banned_page:
                resp_home = sess.get('https://www.roblox.com/home', headers=headers, timeout=10, allow_redirects=True)
                home_url = str(resp_home.url).lower()
                if '/not-approved' in home_url or '/notapproved' in home_url or 'returnurl=%2fnot-approved' in home_url or 'returnurl=%2fnotapproved' in home_url:
                    resp_na = sess.get('https://www.roblox.com/not-approved', headers=headers, timeout=10, allow_redirects=False)
                    if resp_na.status_code == 200:
                        is_banned_page = True
                        page_text = resp_na.text
                        final_url = str(resp_na.url)

            if is_banned_page:
                import re
                found_id = None
                found_name = None
                found_display = None
                
                uid_match = re.search(r'data-userid=["\'](\d+)["\']', page_text)
                if uid_match:
                    found_id = uid_match.group(1)
                
                name_match = re.search(r'data-name=["\']([^"\']+)["\']', page_text)
                if name_match:
                    found_name = name_match.group(1)
                
                dname_match = re.search(r'data-displayName=["\']([^"\']+)["\']', page_text, re.IGNORECASE)
                if dname_match:
                    found_display = dname_match.group(1)

                if not found_id and final_url:
                    url_uid_match = re.search(r'[?&]userId=(\d+)', final_url, re.IGNORECASE)
                    if url_uid_match:
                        found_id = url_uid_match.group(1)
                
                if not found_id:
                    inline_uid_match = re.search(r'["\']?userId["\']?\s*[:=]\s*["\']?(\d+)', page_text)
                    if inline_uid_match:
                        found_id = inline_uid_match.group(1)

                display_name = found_display or found_name
                avatar_url = ""

                if found_id:
                    try:
                        u_url = f"https://users.roblox.com/v1/users/{found_id}"
                        u_res = sess.get(u_url, timeout=6)
                        if u_res.status_code == 200:
                            u_data = u_res.json()
                            found_name = u_data.get('name') or found_name
                            display_name = u_data.get('displayName') or display_name or found_name
                    except Exception:
                        pass

                    try:
                        avatar_url = RobloxAPI.get_avatar_headshot_url(found_id)
                    except Exception:
                        pass
                
                return {
                    'id': str(found_id or ''),
                    'username': found_name or f"BannedAccount_{abs(hash(cookie_val)) % 100000}",
                    'displayName': display_name or found_name or 'Banned Account',
                    'avatar_url': avatar_url or '',
                    'isBanned': True
                }
        except Exception as e:
            log_detailed_error("Failed while checking if cookie belongs to banned user", exc=e, source="roblox_api")
        return None

    @staticmethod
    def get_user_profile_from_cookie(roblosecurity_cookie, return_status=False):
        """Get user id, username, and display name using authenticated user endpoint."""
        try:
            roblosecurity_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
            if not roblosecurity_cookie:
                return (None, "missing") if return_status else None
            headers = {
                'Cookie': f'.ROBLOSECURITY={roblosecurity_cookie}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Referer': 'https://www.roblox.com/',
                'Accept': 'application/json'
            }
            session = requests.Session()
            session.trust_env = False
            response = session.get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                result = {
                    'id': str(data.get('id', '')),
                    'username': data.get('name', ''),
                    'displayName': data.get('displayName', data.get('name', ''))
                }
                return (result, "valid") if return_status else result
            elif response.status_code == 401:
                banned_profile = RobloxAPI._check_banned_cookie_profile(roblosecurity_cookie, session)
                if banned_profile:
                    return (banned_profile, "banned") if return_status else banned_profile
                log_detailed_error(
                    "Roblox API user profile fetch failed with 401 Unauthorized",
                    extra_info={"status_code": response.status_code, "response_text": response.text[:300]},
                    level="WARNING",
                    source="roblox_api"
                )
                return (None, "expired") if return_status else None
            else:
                banned_profile = RobloxAPI._check_banned_cookie_profile(roblosecurity_cookie, session)
                if banned_profile:
                    return (banned_profile, "banned") if return_status else banned_profile
                log_detailed_error(
                    "Roblox API user profile fetch failed with non-200/401 status code",
                    extra_info={"status_code": response.status_code, "response_text": response.text[:300]},
                    level="WARNING",
                    source="roblox_api"
                )
                return (None, "error") if return_status else None
        except Exception as e:
            log_detailed_error("Failed to get user profile from cookie via Roblox API", exc=e, source="roblox_api")
            return (None, "error") if return_status else None

    @staticmethod
    def is_user_banned(user_id):
        """Check if a Roblox user ID is banned using users.roblox.com/v1/users/{userId} isBanned boolean property."""
        if not user_id:
            return False
        try:
            url = f"https://users.roblox.com/v1/users/{user_id}"
            response = RobloxAPI._get_http_session().get(url, timeout=6)
            if response.status_code == 200:
                data = response.json()
                return bool(data.get('isBanned', False))
            else:
                log_detailed_error(
                    "Roblox user ban status endpoint returned non-200 status code",
                    extra_info={"user_id": user_id, "status_code": response.status_code},
                    level="WARNING",
                    source="roblox_api"
                )
        except Exception as e:
            log_detailed_error("Failed to check ban status for Roblox user", exc=e, extra_info={"user_id": user_id}, source="roblox_api")
        return False


    @staticmethod
    def get_account_status_and_info(cookie=None, username=None, user_id=None, existing_status=None):
        """
        Validates account status and returns (status, user_id, username, display_name, avatar_url).
        Status is strictly normalized to one of: 'valid', 'expired', 'banned'.
        """
        found_user_id = str(user_id) if user_id else None
        found_username = username
        found_display_name = username
        found_avatar_url = ""
        is_authenticated = False
        auth_state = "missing"
        profile = None

        normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie) if cookie else ""

        if normalized_cookie:
            profile, auth_state = RobloxAPI.get_user_profile_from_cookie(normalized_cookie, return_status=True)
            if profile:
                is_authenticated = True
                found_user_id = profile.get('id') or found_user_id
                found_username = profile.get('username') or found_username
                found_display_name = profile.get('displayName') or found_display_name
                found_avatar_url = profile.get('avatar_url') or found_avatar_url

        if not found_user_id and found_username:
            uid = RobloxAPI.get_user_id_from_username(found_username)
            if uid:
                found_user_id = str(uid)

        if found_user_id:
            if not found_avatar_url:
                found_avatar_url = RobloxAPI.get_avatar_headshot_url(found_user_id)
            if RobloxAPI.is_user_banned(found_user_id) or auth_state == 'banned' or (profile and profile.get('isBanned')):
                return 'banned', found_user_id, found_username, found_display_name, found_avatar_url

        if auth_state == 'banned' or (profile and profile.get('isBanned')):
            if found_user_id and not found_avatar_url:
                found_avatar_url = RobloxAPI.get_avatar_headshot_url(found_user_id)
            return 'banned', found_user_id, found_username, found_display_name, found_avatar_url

        if is_authenticated:
            return 'valid', found_user_id, found_username, found_display_name, found_avatar_url

        if auth_state == 'error':
            fallback_status = existing_status if (existing_status in ('valid', 'banned', 'expired') and normalized_cookie) else 'expired'
            return fallback_status, found_user_id, found_username, found_display_name, found_avatar_url

        return 'expired', found_user_id, found_username, found_display_name, found_avatar_url

    @staticmethod
    def get_avatar_headshot_url(user_id, use_cache=True):
        """Fetch headshot avatar image url for a user id."""
        if not user_id:
            return ""
        user_id_str = str(user_id).strip()
        if use_cache:
            cached_url = icon_cache.get_avatar_icon(user_id_str)
            if cached_url is not None:
                return cached_url
        try:
            url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id_str}&size=150x150&format=Png&isCircular=true"
            response = RobloxAPI._get_http_session().get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                items = data.get('data') or []
                if items and items[0].get('imageUrl'):
                    img_url = items[0].get('imageUrl')
                    icon_cache.set_avatar_icon(user_id_str, img_url)
                    return img_url
        except Exception as e:
            print(f"Error getting avatar headshot: {e}")
        return ""
    
    @staticmethod
    def get_place_icon_url(place_id, use_cache=True):
        """Fetch game icon image url for a place id."""
        if not place_id:
            return ""
        try:
            place_id_str = str(place_id).strip()
            if not place_id_str.isdigit():
                return ""
            if use_cache:
                cached_url = icon_cache.get_place_icon(place_id_str)
                if cached_url is not None:
                    return cached_url
            url = f"https://thumbnails.roblox.com/v1/places/gameicons?placeIds={place_id_str}&size=150x150&format=Png"
            response = RobloxAPI._get_http_session().get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                items = data.get('data') or []
                if items and items[0].get('imageUrl'):
                    img_url = items[0].get('imageUrl')
                    icon_cache.set_place_icon(place_id_str, img_url)
                    return img_url
        except Exception as e:
            print(f"Error getting place icon: {e}")
        return ""

    @staticmethod
    def get_game_details(place_id, use_cache=True):
        """Fetch game name, universe ID, and icon thumbnail for a place ID."""
        if not place_id:
            return None
        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            return None
        if use_cache:
            cached_details = icon_cache.get_game_details(place_id_str)
            if cached_details is not None:
                return cached_details
        try:
            session = RobloxAPI._get_http_session()
            universe_id = None
            game_name = None

            place_url = f"https://apis.roblox.com/universes/v1/places/{place_id_str}/universe"
            place_resp = session.get(place_url, timeout=5)
            if place_resp.status_code == 200:
                pdata = place_resp.json()
                universe_id = pdata.get("universeId")

            if universe_id:
                game_resp = session.get("https://games.roblox.com/v1/games", params={"universeIds": universe_id}, timeout=5)
                if game_resp.status_code == 200:
                    gdata = game_resp.json()
                    entries = gdata.get("data") or []
                    if entries:
                        game_name = entries[0].get("name")

            icon_url = RobloxAPI.get_place_icon_url(place_id_str, use_cache=use_cache)

            details = {
                "place_id": place_id_str,
                "universe_id": str(universe_id) if universe_id else "",
                "name": game_name or f"Place {place_id_str}",
                "icon_url": icon_url
            }
            icon_cache.set_game_details(place_id_str, details)
            return details
        except Exception as e:
            print(f"Error fetching game details for place {place_id_str}: {e}")
            fallback = {
                "place_id": place_id_str,
                "universe_id": "",
                "name": f"Place {place_id_str}",
                "icon_url": ""
            }
            return fallback

    @staticmethod
    def get_game_details_by_universe(universe_id, use_cache=True):
        """Fetch game name and icon thumbnail directly from a universe ID."""
        if not universe_id:
            return None
        universe_id_str = str(universe_id).strip()
        if not universe_id_str.isdigit():
            return None
        cache_key = f"universe_{universe_id_str}"
        if use_cache:
            cached = icon_cache.get_game_details(cache_key)
            if cached is not None:
                return cached
        try:
            session = RobloxAPI._get_http_session()
            game_name = None
            game_resp = session.get(
                "https://games.roblox.com/v1/games",
                params={"universeIds": universe_id_str},
                timeout=5
            )
            if game_resp.status_code == 200:
                gdata = game_resp.json()
                entries = gdata.get("data") or []
                if entries:
                    game_name = entries[0].get("name")
            icon_url = ""
            thumb_resp = session.get(
                "https://thumbnails.roblox.com/v1/games/icons",
                params={"universeIds": universe_id_str, "size": "150x150", "format": "Png"},
                timeout=5
            )
            if thumb_resp.status_code == 200:
                tdata = thumb_resp.json()
                titems = tdata.get("data") or []
                if titems and titems[0].get("imageUrl"):
                    icon_url = titems[0]["imageUrl"]
            details = {
                "place_id": "",
                "universe_id": universe_id_str,
                "name": game_name or f"Universe {universe_id_str}",
                "icon_url": icon_url
            }
            icon_cache.set_game_details(cache_key, details)
            return details
        except Exception as e:
            print(f"Error fetching game details for universe {universe_id_str}: {e}")
            return {
                "place_id": "",
                "universe_id": universe_id_str,
                "name": f"Universe {universe_id_str}",
                "icon_url": ""
            }

    @staticmethod
    def get_game_name(place_id):
        """Fetch the game name for a given place ID."""
        details = RobloxAPI.get_game_details(place_id)
        return details.get("name") if details else None

    @staticmethod
    def get_subplaces(place_id, max_pages=10):
        """Fetch all places in the same universe as the given place ID."""
        if not place_id:
            return []

        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            return []

        subplaces = []
        seen_ids = set()

        try:
            session = RobloxAPI._get_http_session()

            universe_response = session.get(
                f"https://apis.roblox.com/universes/v1/places/{place_id_str}/universe",
                timeout=8,
            )
            universe_response.raise_for_status()
            universe_payload = universe_response.json() if universe_response.content else {}
            universe_id = str(universe_payload.get("universeId") or "").strip()
            if not universe_id:
                return []

            cursor = ""
            pages_fetched = 0
            while pages_fetched < max_pages:
                params = {
                    "limit": 100,
                    "sortOrder": "Asc",
                }
                if cursor:
                    params["cursor"] = cursor

                places_response = session.get(
                    f"https://develop.roblox.com/v1/universes/{universe_id}/places",
                    params=params,
                    timeout=8,
                )
                places_response.raise_for_status()
                places_payload = places_response.json() if places_response.content else {}
                places = places_payload.get("data") or []

                for entry in places:
                    subplace_id = str(
                        entry.get("id")
                        or entry.get("placeId")
                        or ""
                    ).strip()
                    if not subplace_id or subplace_id in seen_ids:
                        continue
                    seen_ids.add(subplace_id)
                    subplaces.append({
                        "id": subplace_id,
                        "name": str(entry.get("name") or f"Place {subplace_id}").strip() or f"Place {subplace_id}",
                    })

                pages_fetched += 1
                cursor = str(places_payload.get("nextPageCursor") or "").strip()
                if not cursor:
                    break
        except requests.exceptions.RequestException as exc:
            print(f"[WARNING] Failed to fetch subplaces for place {place_id_str}: {exc}")
            return []
        except Exception as exc:
            print(f"[WARNING] Unexpected error while fetching subplaces for place {place_id_str}: {exc}")
            return []

        return subplaces

    @staticmethod
    def get_user_id_from_username(username):
        """Resolve a Roblox user ID from a username."""
        username_text = str(username or "").strip()
        if not username_text:
            return None

        try:
            payload = {
                "usernames": [username_text],
                "excludeBannedUsers": False,
            }
            response = RobloxAPI._get_http_session().post(
                "https://users.roblox.com/v1/usernames/users",
                json=payload,
                timeout=8,
            )
            response.raise_for_status()
            users = (response.json() or {}).get("data") or []
            if users:
                user_id = users[0].get("id")
                if user_id is not None:
                    return str(user_id).strip()
        except requests.exceptions.RequestException as exc:
            print(f"[WARNING] Failed to resolve user ID for '{username_text}': {exc}")
        except Exception as exc:
            print(f"[WARNING] Unexpected error resolving user ID for '{username_text}': {exc}")
        return None

    @staticmethod
    def get_username_from_user_id(user_id):
        """Resolve Roblox username from a numeric user ID."""
        user_id_text = str(user_id or "").strip()
        if not user_id_text or not user_id_text.isdigit():
            return None

        try:
            response = RobloxAPI._get_http_session().get(
                f"https://users.roblox.com/v1/users/{user_id_text}",
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json() if response.content else {}
            username = str(payload.get("name") or "").strip()
            return username or None
        except requests.exceptions.RequestException as exc:
            print(f"[WARNING] Failed to resolve username for user ID {user_id_text}: {exc}")
        except Exception as exc:
            print(f"[WARNING] Unexpected error resolving username for user ID {user_id_text}: {exc}")
        return None

    @staticmethod
    def get_join_user_status(user_identifier):
        """
        Resolve a user and return whether they appear joinable right now.

        Returns:
            {
                "ok": bool,
                "user_id": str,
                "username": str,
                "joinable": bool,
                "presence_type": int,
                "location": str,
                "error": str,
            }
        """
        result = {
            "ok": False,
            "user_id": "",
            "username": "",
            "joinable": False,
            "presence_type": 0,
            "location": "",
            "error": "",
        }

        text = str(user_identifier or "").strip()
        if not text:
            result["error"] = "Missing user"
            return result

        if text.isdigit():
            user_id = text
            username = RobloxAPI.get_username_from_user_id(user_id) or text
        else:
            user_id = RobloxAPI.get_user_id_from_username(text)
            if not user_id:
                result["error"] = "User not found"
                return result
            username = RobloxAPI.get_username_from_user_id(user_id) or text

        result["user_id"] = str(user_id)
        result["username"] = str(username)

        try:
            payload = {"userIds": [int(user_id)]}
            response = RobloxAPI._get_http_session().post(
                "https://presence.roblox.com/v1/presence/users",
                json=payload,
                timeout=8,
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            user_presences = data.get("userPresences") or []
            if not user_presences:
                result["ok"] = True
                result["error"] = "Presence unavailable"
                return result

            presence = user_presences[0] or {}
            presence_type = int(presence.get("userPresenceType", 0) or 0)
            place_id = str(presence.get("placeId") or "").strip()
            location = str(presence.get("lastLocation") or "").strip()
            game_id = str(presence.get("gameId") or "").strip()



            joinable = False
            if presence_type == 2:
                joinable = True
            elif presence_type == 3:
                
                joinable = False
            elif bool(place_id or game_id):
                joinable = True

            result["ok"] = True
            result["presence_type"] = presence_type
            result["joinable"] = bool(joinable)
            result["location"] = location
            return result
        except requests.exceptions.RequestException as exc:
            result["error"] = str(exc)
            return result
        except Exception as exc:
            result["error"] = str(exc)
            return result

    @staticmethod
    def get_public_server_job_candidates(
        place_id: Any,
        max_pages: int = 1,
        prefer_small: bool = False,
        enable_debug: bool = False,
        preferred_region: str = "",
        roblosecurity_cookie: Optional[str] = None,
    ) -> list[str]:
        """Fetch joinable public server job IDs for a place, optionally ranked for low population."""
        if not place_id:
            RobloxAPI._log_debug(enable_debug, "Public server candidate lookup skipped: missing place ID.")
            return []

        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            RobloxAPI._log_debug(enable_debug, f"Public server candidate lookup skipped: non-numeric place ID '{place_id_str}'.")
            return []

        server_rows: list[PublicServerCandidate] = []
        cursor = ""
        pages_fetched = 0

        try:
            session = RobloxAPI._get_http_session()
            while pages_fetched < max_pages:
                url = f"https://games.roblox.com/v1/games/{place_id_str}/servers/Public"
                params = {
                    "sortOrder": "Asc",
                    "limit": 100,
                }
                if cursor:
                    params["cursor"] = cursor
                RobloxAPI._log_debug(
                    enable_debug,
                    f"Fetching public server candidates for place {place_id_str} "
                    f"(page {pages_fetched + 1}/{max_pages}, cursor={'set' if cursor else 'none'})."
                )

                response = None
                page_ok = False
                max_attempts = 4
                for attempt in range(1, max_attempts + 1):
                    try:
                        response = session.get(url, params=params, timeout=8)
                    except requests.exceptions.RequestException as exc:
                        RobloxAPI._log_debug(
                            enable_debug,
                            f"Candidate lookup request exception on attempt {attempt}/{max_attempts} for place {place_id_str}: {exc}"
                        )
                        if attempt == max_attempts:
                            print(f"[WARNING] Failed to fetch public servers for place {place_id_str}: {exc}")
                            return []
                        backoff_seconds = min(2.0 * attempt, 6.0)
                        time.sleep(backoff_seconds)
                        continue

                    if response.status_code != 429:
                        page_ok = True
                        break

                    retry_after = str(response.headers.get("Retry-After") or "").strip()
                    delay_seconds = int(retry_after) if retry_after.isdigit() else min(2 * attempt, 8)
                    RobloxAPI._log_debug(
                        enable_debug,
                        f"Candidate lookup rate limited (429) for place {place_id_str}; "
                        f"Retry-After='{retry_after or 'n/a'}', waiting {delay_seconds}s "
                        f"(attempt {attempt}/{max_attempts})."
                    )
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)

                if not page_ok or response is None:
                    RobloxAPI._log_debug(
                        enable_debug,
                        f"Exhausted retries while fetching public server candidates for place {place_id_str}."
                    )
                    return []

                response.raise_for_status()
                payload = response.json() if response.content else {}
                servers = payload.get("data") or []

                for server in servers:
                    if not isinstance(server, dict):
                        continue
                    job_id = str(server.get("id") or "").strip()
                    if not job_id:
                        continue
                    max_players = RobloxAPI._coerce_int(server.get("maxPlayers", 0), 0)
                    playing = RobloxAPI._coerce_int(server.get("playing", 0), 0)
                    if max_players > 0 and playing >= max_players:
                        continue
                    fill_ratio = (playing / max_players) if max_players > 0 else 1.0
                    region_details = RobloxAPI._extract_public_server_region_details(server)
                    region_text = region_details.search_text if region_details is not None else ""
                    server_rows.append(
                        PublicServerCandidate(
                            job_id=job_id,
                            playing=playing,
                            max_players=max_players,
                            fill_ratio=fill_ratio,
                            ping=RobloxAPI._coerce_optional_int(server.get("ping")),
                            region_text=region_text,
                        )
                    )

                pages_fetched += 1
                cursor = str(payload.get("nextPageCursor") or "").strip()
                if not cursor:
                    break

            if not server_rows:
                return []

            if prefer_small:
                server_rows.sort(key=lambda row: (row.playing, row.fill_ratio, random.random()))
            else:
                random.shuffle(server_rows)

            preferred_region_text = str(preferred_region or "").strip()
            if preferred_region_text:
                server_rows = RobloxAPI._rank_public_server_candidates_by_region(
                    place_id_str,
                    server_rows,
                    preferred_region_text,
                    roblosecurity_cookie,
                    enable_debug=enable_debug,
                )

            return [row.job_id for row in server_rows]
        except (requests.exceptions.RequestException, ValueError) as exc:
            print(f"[WARNING] Failed to fetch public server candidates for place {place_id_str}: {exc}")
            return []
    
    @staticmethod
    def get_auth_ticket_detailed(roblosecurity_cookie):
        """Get authentication ticket for launching Roblox games with specific error details."""
        roblosecurity_cookie = RobloxAPI._normalize_roblosecurity_cookie(roblosecurity_cookie)
        if not roblosecurity_cookie:
            print("[ERROR] Cannot request auth ticket: cookie is empty")
            return None, "Account has no login cookie configured"

        session = RobloxAPI._create_authenticated_session(roblosecurity_cookie)
        if session is None:
            return None, "Failed to connect to Roblox authentication service"

        ticket_urls = (
            "https://auth.roblox.com/v1/authentication-ticket",
            "https://auth.roblox.com/v1/authentication-ticket/",
        )
        ticket_headers = {
            "RBX-For-Gameauth": "true",
            "Content-Type": "application/json",
            "Referer": "https://www.roblox.com/",
            "Origin": "https://www.roblox.com",
            "Cookie": f".ROBLOSECURITY={roblosecurity_cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        if "X-CSRF-TOKEN" in session.headers:
            ticket_headers["X-CSRF-TOKEN"] = session.headers["X-CSRF-TOKEN"]

        try:
            max_attempts = 5
            response = None
            for ticket_url in ticket_urls:
                for attempt in range(1, max_attempts + 1):
                    response = session.post(ticket_url, headers=ticket_headers, json={}, timeout=10)

                    if response.status_code == 403:
                        refreshed_token = response.headers.get("x-csrf-token")
                        if refreshed_token:
                            ticket_headers["X-CSRF-TOKEN"] = refreshed_token
                            session.headers["X-CSRF-TOKEN"] = refreshed_token
                            response = session.post(ticket_url, headers=ticket_headers, json={}, timeout=10)

                    if response.status_code == 429:
                        delay_seconds = random.randint(15, 25)
                        print(
                            f"[WARNING] Roblox rate limited authentication tickets (429). "
                            f"Retrying in {delay_seconds}s... ({attempt}/{max_attempts})"
                        )
                        time.sleep(delay_seconds)
                        continue

                    break

                if response is not None and response.status_code == 200:
                    break

            if response is None or response.status_code != 200:
                status = getattr(response, "status_code", "unknown")
                err_text = getattr(response, "text", "")[:250] if response is not None else ""
                print(f"[ERROR] Failed to get auth ticket, status: {status}, response: {err_text}")

                if status == 401:
                    return None, "Roblox cookie is expired or invalid (account logged out)"
                elif status == 403:
                    if "challenge" in err_text.lower() or "two-step" in err_text.lower() or "2fa" in err_text.lower():
                        return None, "Roblox security challenge or 2FA required"
                    return None, "Roblox session is invalid or expired (cookie expired or logged out)"
                elif status == 429:
                    return None, "Roblox rate limit reached (try again in a moment)"
                elif isinstance(status, int) and status >= 500:
                    return None, "Roblox auth servers are currently unavailable"
                return None, f"Roblox authentication ticket failed (HTTP {status})"

            auth_ticket = response.headers.get("rbx-authentication-ticket")
            if not auth_ticket and response.status_code == 200:
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        auth_ticket = payload.get("ticket") or payload.get("authenticationTicket")
                except Exception:
                    pass
                if not auth_ticket and response.text and not response.text.startswith("{") and not response.text.startswith("<"):
                    auth_ticket = response.text.strip().strip('"')

            if not auth_ticket:
                print("Authentication ticket header missing in response.")
                return None, "Roblox did not issue an authentication ticket"

            return auth_ticket, None
        except requests.exceptions.RequestException as exc:
            print(f"Request failed: {exc}")
            return None, "Cannot connect to Roblox servers (network error)"

    @staticmethod
    def get_auth_ticket(roblosecurity_cookie):
        """Get authentication ticket for launching Roblox games using a session workflow."""
        ticket, _ = RobloxAPI.get_auth_ticket_detailed(roblosecurity_cookie)
        return ticket
    
    _mac_version_hash_cache: Dict[str, str] = {}

    @staticmethod
    def _resolve_mac_version_hash(bundle_version: str) -> Optional[str]:
        ver_clean = str(bundle_version or "").strip()
        if not ver_clean:
            return None
        if ver_clean.startswith("version-"):
            return ver_clean
        cached = RobloxAPI._mac_version_hash_cache.get(ver_clean)
        if cached:
            return cached

        session = requests.Session()
        session.trust_env = False
        weao_headers = {"User-Agent": "WEAO-3PService"}
        for route in ("/api/versions/current", "/api/versions/past", "/api/versions/future"):
            for host in ("https://whatexpsare.online", "https://weao.gg", "https://whatexploitsaretra.sh"):
                try:
                    resp = session.get(f"{host}{route}", headers=weao_headers, timeout=2.5)
                    if not resp.ok:
                        continue
                    data = resp.json()
                    if not isinstance(data, dict):
                        continue
                    mac_hash = str(data.get("Mac") or "").strip()
                    mac_resp = data.get("MacResponse") if isinstance(data.get("MacResponse"), dict) else {}
                    mac_ver = str(mac_resp.get("version") or "").strip()
                    mac_upload = str(mac_resp.get("clientVersionUpload") or mac_hash).strip()
                    if mac_ver and mac_upload.startswith("version-"):
                        RobloxAPI._mac_version_hash_cache[mac_ver] = mac_upload
                    if mac_ver == ver_clean and mac_upload.startswith("version-"):
                        return mac_upload
                    break
                except Exception:
                    continue

        try:
            resp = session.get("https://clientsettings.roblox.com/v2/client-version/MacPlayer", timeout=2.5)
            if resp.ok:
                data = resp.json()
                api_ver = str(data.get("version") or "").strip()
                api_upload = str(data.get("clientVersionUpload") or "").strip()
                if api_ver and api_upload.startswith("version-"):
                    RobloxAPI._mac_version_hash_cache[api_ver] = api_upload
                    if api_ver == ver_clean:
                        return api_upload
        except Exception:
            pass

        return RobloxAPI._mac_version_hash_cache.get(ver_clean)

    @staticmethod
    def _read_mac_app_version(app_path: Path) -> str:
        if app_path.parent.name.startswith("version-"):
            return app_path.parent.name
        try:
            fram_ver_file = app_path / "Contents" / ".fram_version"
            if fram_ver_file.is_file():
                fram_ver = fram_ver_file.read_text(encoding="utf-8", errors="ignore").strip()
                if fram_ver and fram_ver.startswith("version-"):
                    return fram_ver
        except Exception:
            pass
        try:
            import plistlib
            info_plist = app_path / "Contents" / "Info.plist"
            if info_plist.is_file():
                with info_plist.open("rb") as fp:
                    plist_data = plistlib.load(fp)
                    ver = str(plist_data.get("CFBundleShortVersionString") or plist_data.get("CFBundleVersion") or "").strip()
                    if ver:
                        resolved_hash = RobloxAPI._resolve_mac_version_hash(ver)
                        if resolved_hash:
                            try:
                                fram_ver_file = app_path / "Contents" / ".fram_version"
                                if os.access(str(app_path / "Contents"), os.W_OK):
                                    fram_ver_file.write_text(resolved_hash, encoding="utf-8")
                            except Exception:
                                pass
                            return resolved_hash
                        return ver
        except Exception:
            pass
        return app_path.stem or "Roblox.app"

    @staticmethod
    def get_installed_versions(custom_path=None):
        """Get list of installed Roblox versions from standard installations, supported bootstrappers, and custom paths."""
        versions = []
        try:
            seen_paths = set()

            if platform.system() == "Darwin":
                mac_candidates = [
                    (Path("/Applications/Roblox.app"), "Roblox"),
                    (Path(os.path.expanduser("~/Applications/Roblox.app")), "Roblox (User)"),
                ]
                try:
                    from utils.paths import get_root_app_dir
                    fram_versions_dir = Path(get_root_app_dir()) / "RobloxVersions"
                    if fram_versions_dir.is_dir():
                        for v_dir in sorted(fram_versions_dir.iterdir(), key=lambda d: d.stat().st_mtime if d.exists() else 0, reverse=True):
                            if v_dir.is_dir():
                                app_bundle = v_dir / "Roblox.app"
                                if app_bundle.is_dir():
                                    mac_candidates.append((app_bundle, "Roblox (FRAM)"))
                                elif v_dir.name.endswith(".app"):
                                    mac_candidates.append((v_dir, "Roblox (FRAM)"))
                except Exception:
                    pass

                if custom_path:
                    c_path = Path(os.path.expanduser(os.path.expandvars(str(custom_path).strip())))
                    if c_path.exists():
                        if c_path.name == "RobloxPlayer" and c_path.parent.name == "MacOS":
                            mac_candidates.append((c_path.parent.parent.parent, "Custom"))
                        elif c_path.name.endswith(".app"):
                            mac_candidates.append((c_path, "Custom"))
                        elif (c_path / "Roblox.app").is_dir():
                            mac_candidates.append((c_path / "Roblox.app", "Custom"))

                for app_bundle, source_name in mac_candidates:
                    player_bin = app_bundle / "Contents" / "MacOS" / "RobloxPlayer"
                    if app_bundle.is_dir() and player_bin.is_file():
                        norm = str(app_bundle.resolve()).lower()
                        if norm not in seen_paths:
                            seen_paths.add(norm)
                            ver_str = RobloxAPI._read_mac_app_version(app_bundle)
                            if app_bundle.parent.name.startswith("version-"):
                                ver_str = app_bundle.parent.name
                            versions.append({
                                "path": str(app_bundle),
                                "version": ver_str,
                                "source": source_name,
                            })
                return versions

            local_appdata = os.getenv('LOCALAPPDATA')
            if not local_appdata:
                return versions

            def scan_dir(dir_path, source_name):
                entries = []
                p = Path(dir_path)
                if not p.is_dir():
                    return entries

                try:
                    directories = sorted(
                        [d for d in p.iterdir() if d.is_dir()],
                        key=lambda d: d.stat().st_mtime,
                        reverse=True
                    )
                except Exception:
                    directories = [d for d in p.glob('*') if d.is_dir()]

                for version_dir in directories:
                    norm = str(version_dir).lower()
                    if norm in seen_paths:
                        continue
                    if (version_dir / 'RobloxPlayerBeta.exe').exists() or (version_dir / 'RobloxPlayerLauncher.exe').exists():
                        seen_paths.add(norm)
                        entries.append({
                            'path': str(version_dir),
                            'version': version_dir.name,
                            'source': source_name
                        })
                return entries

            versions.extend(scan_dir(Path(local_appdata) / 'Roblox' / 'Versions', 'Roblox'))

            for prog_dir in [os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)')]:
                if prog_dir:
                    p_path = Path(prog_dir) / 'Roblox' / 'Versions'
                    versions.extend(scan_dir(p_path, 'Roblox'))

            for bootstrapper in RobloxAPI.BOOTSTRAPPER_CLIENTS:
                root_path = Path(os.path.expandvars(bootstrapper.get("root", "")))
                for versions_dir_name in bootstrapper.get("version_dirs", ("Versions",)):
                    versions.extend(
                        scan_dir(
                            root_path / versions_dir_name,
                            bootstrapper.get("name", root_path.name)
                        )
                    )

            try:
                for item in Path(local_appdata).iterdir():
                    if not item.is_dir():
                        continue
                    for v_dir_name in ('Versions', 'RblxVersions'):
                        candidate_vdir = item / v_dir_name
                        if candidate_vdir.is_dir():
                            versions.extend(scan_dir(candidate_vdir, item.name))
            except Exception:
                pass

            if custom_path:
                try:
                    c_path = Path(os.path.expandvars(str(custom_path)).strip())
                    if c_path.is_file():
                        c_dir = c_path.parent
                        norm = str(c_dir).lower()
                        if norm not in seen_paths:
                            seen_paths.add(norm)
                            versions.append({
                                'path': str(c_dir),
                                'version': c_dir.name,
                                'source': 'Custom'
                            })
                    elif c_path.is_dir():
                        versions.extend(scan_dir(c_path, 'Custom'))
                except Exception:
                    pass

        except Exception as e:
            print(f"[WARNING] Could not scan for Roblox versions: {e}")
            
        return versions
        
    @staticmethod
    def _get_default_roblox_path():
        """Best-effort attempt to locate the default Roblox installation directory."""
        if platform.system() == "Darwin":
            for candidate in ("/Applications/Roblox.app", os.path.expanduser("~/Applications/Roblox.app")):
                if os.path.isfile(os.path.join(candidate, "Contents", "MacOS", "RobloxPlayer")):
                    return candidate
            try:
                from utils.paths import get_root_app_dir
                fram_versions_dir = Path(get_root_app_dir()) / "RobloxVersions"
                if fram_versions_dir.is_dir():
                    for v_dir in sorted(fram_versions_dir.iterdir(), key=lambda d: d.stat().st_mtime if d.exists() else 0, reverse=True):
                        app_bundle = v_dir / "Roblox.app"
                        if (app_bundle / "Contents" / "MacOS" / "RobloxPlayer").is_file():
                            return str(app_bundle)
            except Exception:
                pass
            return None

        local_appdata = os.getenv('LOCALAPPDATA')
        if not local_appdata:
            return None

        versions_dir = Path(local_appdata) / 'Roblox' / 'Versions'
        if not versions_dir.exists():
            return None

        try:
            version_dirs = [d for d in versions_dir.iterdir() if d.is_dir()]
            version_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            for candidate in version_dirs:
                if (candidate / 'RobloxPlayerBeta.exe').exists():
                    return str(candidate)
        except Exception as exc:
            print(f"[WARNING] Could not enumerate Roblox versions: {exc}")

        return None

    @staticmethod
    def _is_roblox_process_running():
        """Return True if a Roblox player process appears to be running."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    pname = str(proc.info.get('name') or '').lower()
                    if pname in ('robloxplayerbeta.exe', 'robloxplayerbeta', 'robloxplayer', 'robloxplayer.exe'):
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        if platform.system() != "Windows":
            return False

        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq RobloxPlayerBeta.exe"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **RobloxAPI._subprocess_no_window_kwargs(),
            )
            return result.returncode == 0 and 'RobloxPlayerBeta.exe' in (result.stdout or "")
        except Exception:
            return False

    @staticmethod
    def _debug_check_auto_login(username, auth_ticket):
        """Debug helper to confirm the Roblox client launched with the expected auth ticket."""
        if not auth_ticket:
            print(f"[DEBUG] No auth ticket provided for auto-login verification of {username}.")
            return

        if platform.system() != "Windows":
            print("[DEBUG] Auto-login verification is only supported on Windows.")
            return

        time.sleep(2)
        if not RobloxAPI._is_roblox_process_running():
            print(f"[DEBUG] Roblox process not detected after launch; {username} may not have logged in.")
            return

        try:
            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='RobloxPlayerBeta.exe'\" | Select-Object -ExpandProperty CommandLine"
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                **RobloxAPI._subprocess_no_window_kwargs(),
            )
            command_lines = (result.stdout or "").strip()
            if auth_ticket in command_lines:
                print(f"[DEBUG] Roblox process launched with the auth ticket for {username}.")
            else:
                print(f"[DEBUG] Roblox process running but auth ticket not found in command line; {username} may not have auto-logged in.")
        except Exception as exc:
            print(f"[DEBUG] Unable to inspect Roblox process command line: {exc}")

    @staticmethod
    def launch_roblox(
        username,
        cookie,
        game_id,
        private_server_id="",
        roblox_path=None,
        enable_debug=False,
        server_job_id="",
        launch_mode="game",
        return_details=False,
    ):
        """
        Launch Roblox game with specified account and version
        
        Args:
            username: Roblox username
            cookie: Roblox security cookie
            game_id: ID of the game to launch
            private_server_id: Optional private server ID
            roblox_path: Optional path to Roblox version directory (if None, uses default)
            server_job_id: Optional public server job ID
            launch_mode: "game" (place launch) or "join_user"
            return_details: If True, returns (bool, str) tuple with status and error message
        """
        def _log_debug(msg):
            if enable_debug:
                print(f"[DEBUG] {msg}")

        print(f"Getting authentication ticket for {username}...")
        auth_ticket, auth_error = RobloxAPI.get_auth_ticket_detailed(cookie)
        
        if not auth_ticket:
            err = auth_error or f"Failed to get authentication ticket for {username}"
            print(f"[ERROR] {err}")
            if return_details:
                return False, err
            return False
        
        print("[SUCCESS] Got authentication ticket!")

        auth_ticket_encoded = quote(auth_ticket, safe="")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        private_server_text = str(private_server_id or "").strip()
        private_server_share_details = RobloxAPI.extract_private_server_share_details(private_server_text)
        resolved_private_server_link_code = private_server_text
        resolved_private_server_access_code = ""

        if private_server_share_details:
            share_resolution = RobloxAPI.resolve_private_server_share_link(
                private_server_text,
                cookie,
                enable_debug=enable_debug,
            ) or {}
            resolved_private_server_link_code = str(share_resolution.get("link_code") or "").strip()
            resolved_private_server_access_code = str(
                share_resolution.get("access_code")
                or private_server_share_details.get("code")
                or ""
            ).strip()
            if not game_id and share_resolution.get("place_id"):
                game_id = share_resolution.get("place_id")
            _log_debug(
                (
                    "Private server share link detected; "
                    f"access_code={'set' if resolved_private_server_access_code else 'none'}, "
                    f"link_code={'set' if resolved_private_server_link_code else 'none'}."
                )
            )
        elif private_server_text:
            normalized_code = RobloxAPI.normalize_private_server(private_server_text, cookie)
            if normalized_code:
                resolved_private_server_link_code = normalized_code
            if not game_id:
                place_match = re.search(r"(?:games|placeId=|\/)(\d{4,15})", private_server_text, re.IGNORECASE)
                if place_match:
                    game_id = place_match.group(1)
        

        launcher_exe = None
        launcher_name = None
        launcher_requires_player_flag = False
        explicit_executable_provided = False
        explicit_executable_path = None

        try:
            roblox_path_expanded = os.path.expanduser(os.path.expandvars(str(roblox_path))) if roblox_path else ""
        except Exception:
            roblox_path_expanded = str(roblox_path) if roblox_path else ""

        if roblox_path_expanded:
            if not RobloxAPI._is_safe_roblox_path(roblox_path_expanded):
                _log_debug(
                    f"User supplied roblox_path '{roblox_path_expanded}' failed security validation; "
                    "ignoring and falling back to default installation discovery."
                )
                roblox_path_expanded = ""

        is_mac = platform.system() == "Darwin"
        mac_app_bundle = None

        allowed_launchers = {}
        allowed_roblox_exes = {}

        if not is_mac:
            for bootstrapper in RobloxAPI.BOOTSTRAPPER_CLIENTS:
                root = os.path.expandvars(bootstrapper.get("root", ""))
                l_path = os.path.join(root, bootstrapper.get("launcher", ""))
                if os.path.isfile(l_path):
                    b_info = (l_path, bootstrapper.get("name", "Bootstrapper"), True)
                    allowed_launchers[str(bootstrapper.get("launcher", "")).lower()] = b_info
                    allowed_launchers[l_path.lower()] = b_info
                    allowed_launchers[os.path.realpath(l_path).lower()] = b_info
                    allowed_launchers[str(bootstrapper.get("name", "")).lower()] = b_info

        for ver in RobloxAPI.get_installed_versions():
            v_dir = ver.get("path")
            if not v_dir:
                continue
            if is_mac:
                player_bin = os.path.join(v_dir, "Contents", "MacOS", "RobloxPlayer")
                if os.path.isfile(player_bin):
                    bundle_info = (player_bin, v_dir, v_dir)
                    allowed_roblox_exes[v_dir.lower()] = bundle_info
                    allowed_roblox_exes[os.path.realpath(v_dir).lower()] = bundle_info
                    allowed_roblox_exes[player_bin.lower()] = bundle_info
                    allowed_roblox_exes[os.path.realpath(player_bin).lower()] = bundle_info
                    if ver.get("version"):
                        allowed_roblox_exes[str(ver["version"]).lower()] = bundle_info
            else:
                for c_exe in ("RobloxPlayerBeta.exe", "RobloxPlayerLauncher.exe"):
                    c_path = os.path.join(v_dir, c_exe)
                    if os.path.isfile(c_path):
                        exe_info = (c_path, v_dir, None)
                        allowed_roblox_exes[v_dir.lower()] = exe_info
                        allowed_roblox_exes[os.path.realpath(v_dir).lower()] = exe_info
                        allowed_roblox_exes[c_path.lower()] = exe_info
                        allowed_roblox_exes[os.path.realpath(c_path).lower()] = exe_info
                        if ver.get("version"):
                            allowed_roblox_exes[str(ver["version"]).lower()] = exe_info
                        if c_exe == "RobloxPlayerLauncher.exe":
                            allowed_launchers["robloxplayerlauncher.exe"] = (c_path, "RobloxPlayerLauncher", False)
                            allowed_launchers[c_path.lower()] = (c_path, "RobloxPlayerLauncher", False)
                            allowed_launchers[os.path.realpath(c_path).lower()] = (c_path, "RobloxPlayerLauncher", False)

        def _launch_mac_app_bundle(bundle_path, target_url, context):
            """Launch Roblox.app on macOS via `open -n -a` and verify launch handoff."""
            res = subprocess.run(
                ["open", "-n", "-a", bundle_path, "--args", target_url],
                capture_output=True,
                text=True,
                timeout=5,
                close_fds=True,
            )
            if res.returncode != 0:
                err_detail = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
                raise RuntimeError(f"macOS open failed for {bundle_path}: {err_detail}")
            _log_debug(f"Launching {context} on macOS via open -n -a {bundle_path} --args {target_url}")

        def _launch_with_launcher(launcher_id, target_url, context, working_dir=None):
            """Launch via a verified bootstrapper or launcher executable."""
            if launcher_id not in RobloxAPI.BOOTSTRAPPER_EXE_MAP:
                return False
            launcher_rel_path, req_player = RobloxAPI.BOOTSTRAPPER_EXE_MAP[launcher_id]
            launcher_bin = os.path.expandvars(launcher_rel_path)
            if not RobloxAPI._is_strict_roblox_launch_url(target_url):
                return False
            clean_url = str(target_url).strip()
            if not clean_url.startswith("roblox-player:"):
                return False
            _log_debug(f"Launching {context} via {launcher_id} with URL: {clean_url}")
            if hasattr(os, "startfile") and os.path.isfile(launcher_bin):
                try:
                    args = f"-player {clean_url}" if req_player else clean_url
                    os.startfile(launcher_bin, arguments=args)
                    return True
                except Exception as exc:
                    _log_debug(f"startfile failed for {launcher_bin}: {exc}")
            return RobloxAPI._launch_protocol_url(clean_url)

        roblox_exe = None
        effective_path = None
        using_local_install = False
        launcher_id = None

        lookup_key = str(roblox_path_expanded or "").strip().lower()
        if lookup_key:
            if "bloxstrap" in lookup_key:
                launcher_id = "bloxstrap"
            elif "fishstrap" in lookup_key:
                launcher_id = "fishstrap"
            elif "voidstrap" in lookup_key:
                launcher_id = "voidstrap"
            elif "froststrap" in lookup_key:
                launcher_id = "froststrap"
            elif "exploitstrap" in lookup_key:
                launcher_id = "exploitstrap"
            elif "robloxplayerlauncher" in lookup_key:
                launcher_id = "robloxplayerlauncher"

            if launcher_id and launcher_id != "robloxplayerlauncher":
                launcher_bin_path = os.path.expandvars(RobloxAPI.BOOTSTRAPPER_EXE_MAP[launcher_id][0])
                if os.path.isfile(launcher_bin_path):
                    effective_path = os.path.dirname(launcher_bin_path)
                    roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                    using_local_install = True
                else:
                    launcher_id = None
            elif lookup_key in allowed_launchers:
                launcher_exe, launcher_name, launcher_requires_player_flag = allowed_launchers[lookup_key]
                effective_path = os.path.dirname(launcher_exe)
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                using_local_install = True
                launcher_id = "robloxplayerlauncher"
            elif lookup_key in allowed_roblox_exes:
                roblox_exe, effective_path, mac_app_bundle = allowed_roblox_exes[lookup_key]
                using_local_install = True

        if not roblox_exe and not launcher_id:
            default_path = RobloxAPI._get_default_roblox_path()
            if default_path:
                def_key = default_path.lower()
                if def_key in allowed_roblox_exes:
                    roblox_exe, effective_path, mac_app_bundle = allowed_roblox_exes[def_key]
                    using_local_install = True
                elif is_mac:
                    cand_player = os.path.join(default_path, "Contents", "MacOS", "RobloxPlayer")
                    if os.path.isfile(cand_player):
                        roblox_exe = cand_player
                        effective_path = os.path.join(default_path, "Contents", "MacOS")
                        mac_app_bundle = default_path
                        using_local_install = True
                else:
                    cand_beta = os.path.join(default_path, "RobloxPlayerBeta.exe")
                    if os.path.isfile(cand_beta):
                        roblox_exe = cand_beta
                        effective_path = default_path
                        using_local_install = True

        if not roblox_exe and not is_mac:
            roblox_exe = "RobloxPlayerBeta.exe"

        normalized_launch_mode = str(launch_mode or "game").strip().lower()
        if normalized_launch_mode in ("join_user", "user"):
            normalized_launch_mode = "join_user"
        else:
            normalized_launch_mode = "game"

        if normalized_launch_mode != "join_user" and (not game_id or game_id == ""):
            browser_tracker_id = random.randint(100000000000, 999999999999)
            launch_time = int(time.time() * 1000)
            launch_record_id = RobloxAPI.record_launch_ticket(
                username=username,
                place_id="",
                browser_tracker_id=browser_tracker_id,
                launch_time_ms=launch_time,
                auth_ticket=auth_ticket,
            )

            url = (
                "roblox-player:1"
                "+launchmode:app"
                "+gameinfo:" + auth_ticket_encoded +
                "+launchtime:" + str(launch_time) +
                "+browsertrackerid:" + str(browser_tracker_id) +
                "+robloxLocale:en_us+gameLocale:en_us"
            )
            print(f"Launching Roblox Home...")
            print(f"Account: {username}")

            if RobloxAPI._is_roblox_process_running():
                print("[WARNING] Roblox is already running. Auto-login may not apply until all Roblox instances are closed.")

            try:
                if is_mac and using_local_install and mac_app_bundle:
                    _launch_mac_app_bundle(mac_app_bundle, url, "Roblox Home")
                elif launcher_id:
                    if not _launch_with_launcher(
                        launcher_id,
                        url,
                        "Roblox Home",
                        working_dir=effective_path,
                    ):
                        raise RuntimeError(f"Failed to launch Roblox Home via {launcher_id}")
                elif using_local_install:
                    try:
                        proc = subprocess.Popen(
                            [roblox_exe, url],
                            cwd=effective_path,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=creation_flags,
                            close_fds=True,
                        )
                        if getattr(proc, "pid", None):
                            RobloxAPI.update_launch_ticket_spawned_pid(launch_record_id, proc.pid)
                        _log_debug(f"Launching Roblox Home via RobloxPlayerBeta.exe with URL arg: {url}")
                    except Exception as exc:
                        _log_debug(f"RobloxPlayerBeta.exe URL-arg launch failed, falling back to protocol launch: {exc}")
                        if not RobloxAPI._launch_protocol_url(url):
                            raise
                elif RobloxAPI._launch_protocol_url(url):
                    _log_debug(f"Launching Roblox Home via protocol URL: {url}")
                else:
                    raise RuntimeError("Roblox isn't installed")

                print("[SUCCESS] Roblox home launched successfully!")
                if enable_debug:
                    RobloxAPI._debug_check_auto_login(username, auth_ticket)
                if return_details:
                    return True, "Roblox launched successfully"
                return True
            except Exception as e:
                err_msg = "Roblox isn't installed" if isinstance(e, FileNotFoundError) or "isn't installed" in str(e).lower() or "protocol handler" in str(e).lower() else "Failed to launch Roblox"
                print(f"[ERROR] Failed to launch Roblox: {e}")
                if return_details:
                    return False, err_msg
                return False
                    
        browser_tracker_id = random.randint(100000000000, 999999999999)
        launch_time = int(time.time() * 1000)

        clean_game_id = ""
        clean_server_job_id = ""

        if normalized_launch_mode == "join_user":
            user_target = str(game_id).strip()
            if user_target and not user_target.isdigit():
                resolved_uid = RobloxAPI.get_user_id_from_username(user_target)
                if resolved_uid:
                    user_target = resolved_uid
            if not user_target or not user_target.isdigit():
                err = f"Invalid user target for join_user: '{game_id}'. User target must resolve to a numeric user ID."
                print(f"[ERROR] {err}")
                if return_details:
                    return False, err
                return False
            clean_game_id = user_target
            game_id = clean_game_id
            place_launch_request = "RequestFollowUser"
            place_launch_extra = "&userId=" + clean_game_id
            place_launch_base = (
                "https://assetgame.roblox.com/game/PlaceLauncher.ashx?request=" + place_launch_request +
                "&browserTrackerId=" + str(browser_tracker_id) +
                place_launch_extra
            )
        else:
            clean_game_id = str(game_id or "").strip()
            if not clean_game_id.isdigit():
                err = f"Invalid game place ID: '{game_id}'. Place ID must contain digits only."
                print(f"[ERROR] {err}")
                if return_details:
                    return False, err
                return False

            if server_job_id:
                raw_job = str(server_job_id).strip()
                if not re.fullmatch(r"^[A-Fa-f0-9-]+$", raw_job):
                    err = f"Invalid server job ID: '{server_job_id}'. Job ID must contain UUID-like characters only."
                    print(f"[ERROR] {err}")
                    if return_details:
                        return False, err
                    return False
                clean_server_job_id = raw_job

            game_id = clean_game_id
            server_job_id = clean_server_job_id

            place_launch_request = "RequestGame"
            place_launch_extra = ""
            if private_server_id:
                if resolved_private_server_access_code:
                    place_launch_request = "RequestPrivateGame"
                    place_launch_extra = "&accessCode=" + resolved_private_server_access_code
                    if resolved_private_server_link_code:
                        place_launch_extra += "&linkCode=" + resolved_private_server_link_code
                    place_launch_extra += "&joinAttemptId=" + str(uuid.uuid4())
                else:
                    place_launch_extra = "&linkCode=" + resolved_private_server_link_code
            elif clean_server_job_id:
                place_launch_request = "RequestGameJob"
                place_launch_extra = "&gameId=" + clean_server_job_id
            place_launch_base = (
                "https://assetgame.roblox.com/game/PlaceLauncher.ashx?request=" + place_launch_request +
                "&browserTrackerId=" + str(browser_tracker_id) +
                "&placeId=" + clean_game_id +
                "&isPlayTogetherGame=false" +
                place_launch_extra
            )

        if not RobloxAPI._is_valid_placelauncher_url(place_launch_base):
            err = f"Invalid PlaceLauncher URL generated: '{place_launch_base}'"
            print(f"[ERROR] {err}")
            if return_details:
                return False, err
            return False

        url = (
            "roblox-player:1+launchmode:play+gameinfo:" + auth_ticket_encoded +
            "+launchtime:" + str(launch_time) +
            "+placelauncherurl:" + place_launch_base
        )

        url += (
            "+browsertrackerid:" + str(browser_tracker_id) +
            "+robloxLocale:en_us+gameLocale:en_us"
        )

        launch_record_id = RobloxAPI.record_launch_ticket(
            username=username,
            place_id=clean_game_id if normalized_launch_mode != "join_user" else "",
            browser_tracker_id=browser_tracker_id,
            launch_time_ms=launch_time,
            auth_ticket=auth_ticket,
        )

        print(f"Launching Roblox...")
        print(f"Account: {username}")
        if normalized_launch_mode == "join_user":
            print(f"Join User ID: {game_id}")
        else:
            print(f"Game ID: {game_id}")
            if private_server_id:
                print(
                    "Private Server: "
                    + (
                        resolved_private_server_link_code
                        or resolved_private_server_access_code
                        or private_server_text
                    )
                )
            elif server_job_id:
                print(f"Server Job ID: {server_job_id}")

        try:
            if is_mac and using_local_install and mac_app_bundle:
                _launch_mac_app_bundle(mac_app_bundle, url, "game")
            elif launcher_id:
                if not _launch_with_launcher(
                    launcher_id,
                    url,
                    "game",
                    working_dir=effective_path,
                ):
                    raise RuntimeError(f"Failed to launch game via {launcher_id}")
            else:
                if using_local_install:
                    try:
                        proc = subprocess.Popen(
                            [roblox_exe, url],
                            cwd=effective_path,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=creation_flags,
                            close_fds=True,
                        )
                        if getattr(proc, "pid", None):
                            RobloxAPI.update_launch_ticket_spawned_pid(launch_record_id, proc.pid)
                        _log_debug(f"Launching game via RobloxPlayerBeta.exe with URL arg: {url}")
                        print("[SUCCESS] Roblox launched successfully!")
                        if enable_debug:
                            RobloxAPI._debug_check_auto_login(username, auth_ticket)
                        if return_details:
                            return True, "Roblox launched successfully"
                        return True
                    except Exception as exc:
                        _log_debug(f"RobloxPlayerBeta.exe URL-arg launch failed, falling back to protocol launch: {exc}")
                        if not RobloxAPI._launch_protocol_url(url):
                            raise
                elif RobloxAPI._launch_protocol_url(url):
                    _log_debug(f"Launching game via protocol URL: {url}")
                else:
                    raise RuntimeError("Roblox isn't installed")
            print("[SUCCESS] Roblox launched successfully!")
            if enable_debug:
                RobloxAPI._debug_check_auto_login(username, auth_ticket)
            if return_details:
                return True, "Roblox launched successfully"
            return True
        except Exception as e:
            err_msg = "Roblox isn't installed" if isinstance(e, FileNotFoundError) or "isn't installed" in str(e).lower() or "protocol handler" in str(e).lower() else "Failed to launch Roblox"
            print(f"[ERROR] Failed to launch Roblox: {e}")
            if return_details:
                return False, err_msg
            return False
    
    @staticmethod
    def validate_account(username, cookie, verbose=True):
        """Validate if an account's cookie is still valid and optionally print token details."""
        try:
            normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)
            if not normalized_cookie:
                if verbose:
                    print(f"\n{'='*60}")
                    print(f"ACCOUNT VALIDATION: {username}")
                    print(f"{'='*60}")
                    print("Valid: No")
                    print("Token: (No token found)")
                    print(f"{'='*60}")
                return False

            headers = {
                'Cookie': f'.ROBLOSECURITY={normalized_cookie}'
            }
            
            response = RobloxAPI._get_http_session().get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            is_valid = response.status_code == 200
            is_banned = False
            banned_user_data = None
            if not is_valid:
                banned_profile = RobloxAPI._check_banned_cookie_profile(normalized_cookie)
                if banned_profile:
                    is_valid = True
                    is_banned = True
                    banned_user_data = banned_profile

            if verbose:
                print(f"\n{'='*60}")
                print(f"ACCOUNT VALIDATION: {username}")
                print(f"{'='*60}")
                if is_banned:
                    print("Valid: Yes (Account Banned)")
                else:
                    print(f"Valid: {'Yes' if is_valid else 'No'}")
            
                print(f"Token: {RobloxAPI._format_token_preview(normalized_cookie)}")
                print(f"Token Length: {len(normalized_cookie)} characters")
            
                if is_valid and response.status_code == 200:
                    try:
                        user_data = response.json()
                        print(f"User ID: {user_data.get('id', 'Unknown')}")
                        print(f"Display Name: {user_data.get('displayName', 'Unknown')}")
                        print(f"Username: {user_data.get('name', 'Unknown')}")
                    except Exception:
                        print("Additional info: Could not retrieve user details")
                elif is_banned and banned_user_data:
                    print(f"User ID: {banned_user_data.get('id', 'Unknown')}")
                    print(f"Display Name: {banned_user_data.get('displayName', 'Unknown')}")
                    print(f"Username: {banned_user_data.get('username', 'Unknown')}")
                    print("Status: Account is Banned")
                else:
                    print(f"Status Code: {response.status_code}")
                    if response.status_code == 401:
                        print("Reason: Token expired or invalid")
                    elif response.status_code == 403:
                        print("Reason: Access forbidden")
                    else:
                        print("Reason: Unknown error")
            
                print(f"{'='*60}")
            return is_valid
            
        except Exception as e:
            if verbose:
                print(f"\n{'='*60}")
                print(f"ACCOUNT VALIDATION: {username}")
                print(f"{'='*60}")
                print(f"Valid: No")
                print(f"Token: {RobloxAPI._format_token_preview(cookie)}")
                print(f"Error: {str(e)}")
                print(f"{'='*60}")
            return False

    @staticmethod
    def _is_safe_roblox_path(candidate_path: str) -> bool:
        """Validate that a user-supplied roblox_path points to an expected Roblox binary or folder within trusted install roots."""
        if not candidate_path or not isinstance(candidate_path, str):
            return False
        try:
            resolved = os.path.realpath(os.path.abspath(candidate_path))
            resolved_lower = resolved.lower()

            system = platform.system()
            trusted_roots = []
            if system == "Windows":
                for env_var in ["LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)", "APPDATA"]:
                    val = os.environ.get(env_var)
                    if val:
                        trusted_roots.append(os.path.realpath(os.path.abspath(val)))
            elif system == "Darwin":
                trusted_roots.extend([
                    os.path.realpath(os.path.abspath("/Applications")),
                    os.path.realpath(os.path.expanduser("~/Applications")),
                    os.path.realpath(os.path.expanduser("~/Library/Application Support")),
                ])
            else:
                trusted_roots.extend([
                    os.path.realpath(os.path.abspath("/usr")),
                    os.path.realpath(os.path.abspath("/opt")),
                    os.path.realpath(os.path.expanduser("~")),
                ])

            matched_root = None
            for root in trusted_roots:
                root_lower = root.lower()
                if resolved_lower == root_lower or resolved_lower.startswith(root_lower + os.sep):
                    matched_root = root
                    break

            if not matched_root:
                return False

            rel_path = resolved[len(matched_root):].lstrip(os.sep)
            safe_resolved = os.path.abspath(os.path.realpath(os.path.join(matched_root, rel_path)))
            if not safe_resolved.startswith(matched_root + os.sep):
                return False

            base_name = os.path.basename(safe_resolved.lower())
            if os.path.isfile(safe_resolved) or ("." in base_name and not os.path.isdir(safe_resolved)):
                allowed_exes = {
                    "robloxplayerbeta.exe",
                    "robloxplayerlauncher.exe",
                    "robloxplayerinstaller.exe",
                    "robloxplayer",
                    "roblox.app",
                    "bloxstrap.exe",
                    "fishstrap.exe",
                    "voidstrap.exe",
                    "froststrap.exe",
                    "exploitstrap.exe",
                }
                if base_name not in allowed_exes:
                    return False

            return True
        except Exception:
            return False

    @staticmethod
    def _is_valid_placelauncher_url(url: str) -> bool:
        """Enforce that place_launch_url is https, exactly assetgame.roblox.com/game/PlaceLauncher.ashx,
        contains only expected query keys, and required keys are present."""
        if not url or not isinstance(url, str):
            return False
        try:
            parsed = urlsplit(url)
            if (parsed.scheme or "").lower() != "https":
                return False
            if (parsed.hostname or "").lower() != "assetgame.roblox.com":
                return False
            if parsed.path != "/game/PlaceLauncher.ashx":
                return False
            if not parsed.query:
                return False

            allowed_keys = {
                "request",
                "browsertrackerid",
                "placeid",
                "isplaytogethergame",
                "accesscode",
                "linkcode",
                "joinattemptid",
                "gameid",
                "userid",
            }
            params = parse_qs(parsed.query, keep_blank_values=True)
            for key in params:
                if key.lower() not in allowed_keys:
                    return False

            lower_keys = {k.lower() for k in params.keys()}
            if "request" not in lower_keys or "browsertrackerid" not in lower_keys:
                return False
            if "placeid" not in lower_keys and "userid" not in lower_keys:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _is_strict_roblox_launch_url(url: str) -> bool:
        """Strictly validate Roblox protocol URL structure and parameter values."""
        if not url or not isinstance(url, str):
            return False
        cleaned = url.strip()
        pattern = r"^roblox-player:1\+[A-Za-z0-9+:\/._?&=%-]+$"
        if not re.fullmatch(pattern, cleaned, re.IGNORECASE):
            return False

        if "+launchmode:app" not in cleaned and "+launchmode:play" not in cleaned:
            return False

        if "+placelauncherurl:" in cleaned:
            parts = cleaned.split("+placelauncherurl:", 1)
            target = parts[1].split("+")[0]
            if not (
                target.startswith("https://assetgame.roblox.com/game/PlaceLauncher.ashx")
                or target.startswith("https%3A%2F%2Fassetgame.roblox.com%2Fgame%2FPlaceLauncher.ashx")
            ):
                return False

        return True

    @staticmethod
    def _is_valid_roblox_protocol_url(url: str) -> bool:
        return RobloxAPI._is_strict_roblox_launch_url(url)

    @staticmethod
    def _launch_protocol_url(url):
        """Launch the Roblox protocol URL in a cross-platform-safe way."""
        if not RobloxAPI._is_strict_roblox_launch_url(url):
            print("[ERROR] Rejected invalid or unsafe Roblox protocol URL.")
            return False

        clean_url = str(url).strip()
        try:
            import webbrowser
            return bool(webbrowser.open(clean_url))
        except Exception as exc:
            print(f"[ERROR] Failed to trigger Roblox protocol handler: {exc}")
            return False
