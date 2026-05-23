"""
Roblox API interaction utilities
Handles authentication, info, and game launching
"""

import os
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
from typing import Any, Optional

from urllib.parse import quote, parse_qs, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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

    _protocol_handler_missing_warned = False
    _http_session = None
    _http_session_lock = threading.Lock()
    _server_region_cache: dict[str, Optional[ServerRegionDetails]] = {}
    _ip_region_cache: dict[str, Optional[ServerRegionDetails]] = {}
    _server_region_cache_lock = threading.Lock()
    _public_server_region_probe_limit: int = 30
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
                RobloxAPI._ip_region_cache[normalized_address] = None
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
                RobloxAPI._ip_region_cache[normalized_address] = None
            return None

        with RobloxAPI._server_region_cache_lock:
            RobloxAPI._ip_region_cache[normalized_address] = details
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
                RobloxAPI._server_region_cache[cache_key] = None
            return None

        address = RobloxAPI._extract_join_script_address(join_script)
        details = RobloxAPI._get_ip_region_details(address, geolocation_session, enable_debug=enable_debug)
        with RobloxAPI._server_region_cache_lock:
            RobloxAPI._server_region_cache[cache_key] = details
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
            candidate = text
            lowered = candidate.lower()
            if "://" not in candidate and ("roblox.com" in lowered or lowered.startswith("roblox://")):
                candidate = f"https://{candidate}"

            if "://" in candidate:
                parsed = urlparse(candidate)
                scheme = str(parsed.scheme or "").strip().lower()
                host = str(parsed.netloc or "").strip().lower()
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

                if host.endswith("roblox.com") and path in ("share", "share-links") and share_type == "server":
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
            r"(?i)(?:roblox://navigation/share_links|https?://(?:www\.)?roblox\.com/(?:share|share-links))[^\s]*\bcode=([A-Za-z0-9_-]+)[^\s]*\b(?:type|pid)=Server\b",
            text,
        )
        if match:
            return build_result(match.group(1))
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
        session.cookies.set(".ROBLOSECURITY", roblosecurity_cookie, domain=".roblox.com")
        session.headers.update({
            "User-Agent": "Roblox/WinInet",
            "Referer": "https://www.roblox.com/",
        })

        csrf_token = RobloxAPI._fetch_csrf_token(session)
        if not csrf_token:
            print("Failed to obtain X-CSRF-TOKEN for authenticated session.")
            return None

        session.headers["X-CSRF-TOKEN"] = csrf_token
        return session

    @staticmethod
    def _fetch_csrf_token(session):
        """Try to obtain a CSRF token using a lightweight GET, then fallback probe."""
        try:
            response = session.post("https://auth.roblox.com/v2/logout", timeout=10)
            token = response.headers.get("x-csrf-token")
            if token:
                return token


            probe_headers = {
                "RBX-For-Gameauth": "true",
                "Content-Type": "application/json",
            }
            probe = session.post(
                "https://auth.roblox.com/v1/authentication-ticket/",
                headers=probe_headers,
                timeout=10
            )
            return probe.headers.get("x-csrf-token")
        except requests.exceptions.RequestException as exc:
            print(f"[ERROR] Unable to fetch CSRF token: {exc}")
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
            
        except Exception as e:
            print(f"Error getting username from API: {e}")
        
        return "Unknown"
    
    @staticmethod
    def get_game_name(place_id):
        """Fetch the game name for a given place ID."""
        if not place_id:
            return None

        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            return None

        try:
            session = RobloxAPI._get_http_session()
            place_url = f"https://apis.roblox.com/universes/v1/places/{place_id_str}/universe"
            place_response = session.get(place_url, timeout=5)
            place_response.raise_for_status()

            place_data = place_response.json()
            universe_id = place_data.get("universeId")
            if not universe_id:
                return None

            game_response = session.get(
                "https://games.roblox.com/v1/games",
                params={"universeIds": universe_id},
                timeout=5,
            )
            game_response.raise_for_status()

            game_data = game_response.json()
            entries = game_data.get("data") or []
            if entries:
                return entries[0].get("name")
        except requests.exceptions.RequestException as exc:
            print(f"[WARNING] Failed to fetch game name for place {place_id_str}: {exc}")
        except Exception as exc:
            print(f"[WARNING] Unexpected error while fetching game name for place {place_id_str}: {exc}")
        return None

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
    def get_auth_ticket(roblosecurity_cookie):
        """Get authentication ticket for launching Roblox games using a session workflow."""
        session = RobloxAPI._create_authenticated_session(roblosecurity_cookie)
        if session is None:
            return None

        ticket_url = "https://auth.roblox.com/v1/authentication-ticket/"
        ticket_headers = {
            "RBX-For-Gameauth": "true",
            "Content-Type": "application/json",
            "Referer": "https://www.roblox.com/develop",
        }

        try:
            max_attempts = 5
            response = None
            for attempt in range(1, max_attempts + 1):
                response = session.post(ticket_url, headers=ticket_headers, timeout=10)

                if response.status_code == 403:
                    refreshed_token = response.headers.get("x-csrf-token")
                    if refreshed_token:
                        session.headers["X-CSRF-TOKEN"] = refreshed_token
                        response = session.post(ticket_url, headers=ticket_headers, timeout=10)

                if response.status_code == 429:
                    delay_seconds = random.randint(15, 25)
                    print(
                        f"[WARNING] Roblox rate limited authentication tickets (429). "
                        f"Retrying in {delay_seconds}s... ({attempt}/{max_attempts})"
                    )
                    time.sleep(delay_seconds)
                    continue

                break

            if response is None or response.status_code != 200:
                status = getattr(response, "status_code", "unknown")
                print(f"Failed to get auth ticket, status: {status}")
                return None

            auth_ticket = response.headers.get("rbx-authentication-ticket")
            if not auth_ticket:
                print("Authentication ticket header missing in response.")
                return None

            return auth_ticket
        except requests.exceptions.RequestException as exc:
            print(f"Request failed: {exc}")
            return None
    
    @staticmethod
    def get_installed_versions():
        """Get list of installed Roblox versions from Bloxstrap and Fishstrap."""
        versions = []
        try:

            local_appdata = os.getenv('LOCALAPPDATA')
            if not local_appdata:
                return versions

            def scan_versions(root_name):
                entries = []
                versions_dir = Path(local_appdata) / root_name / 'Versions'
                if not versions_dir.exists():
                    return entries

                try:
                    directories = sorted(
                        [d for d in versions_dir.iterdir() if d.is_dir()],
                        key=lambda d: d.stat().st_mtime,
                        reverse=True
                    )
                except Exception:
                    directories = [d for d in versions_dir.glob('*') if d.is_dir()]

                for version_dir in directories:
                    if (version_dir / 'RobloxPlayerBeta.exe').exists():
                        entries.append({
                            'path': str(version_dir),
                            'version': version_dir.name,
                            'source': root_name
                        })
                return entries

            versions.extend(scan_versions('Bloxstrap'))
            versions.extend(scan_versions('Fishstrap'))

        except Exception as e:
            print(f"[WARNING] Could not scan for Roblox versions: {e}")
            
        return versions
        
    @staticmethod
    def _get_default_roblox_path():
        """Best-effort attempt to locate the default Roblox installation directory."""
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
        """
        def _log_debug(msg):
            if enable_debug:
                print(f"[DEBUG] {msg}")

        print(f"Getting authentication ticket for {username}...")
        auth_ticket = RobloxAPI.get_auth_ticket(cookie)
        
        if not auth_ticket:
            print("[ERROR] Failed to get authentication ticket")
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
            _log_debug(
                (
                    "Private server share link detected; "
                    f"access_code={'set' if resolved_private_server_access_code else 'none'}, "
                    f"link_code={'set' if resolved_private_server_link_code else 'none'}."
                )
            )
        

        launcher_exe = None
        launcher_name = None
        launcher_requires_player_flag = False
        explicit_executable_provided = False
        explicit_executable_path = None

        try:
            roblox_path_expanded = os.path.expandvars(str(roblox_path)) if roblox_path else ""
        except Exception:
            roblox_path_expanded = str(roblox_path) if roblox_path else ""

        if roblox_path_expanded and os.path.isfile(roblox_path_expanded):
            explicit_executable_provided = True
            explicit_executable_path = roblox_path_expanded
            effective_path = os.path.dirname(roblox_path_expanded)
        else:
            effective_path = roblox_path_expanded or RobloxAPI._get_default_roblox_path()

        using_local_install = effective_path and os.path.isdir(effective_path)

        bloxstrap_root = os.path.expandvars(r"%LOCALAPPDATA%\Bloxstrap")
        bloxstrap_launcher = os.path.join(bloxstrap_root, "Bloxstrap.exe")
        is_bloxstrap_install = False
        is_fishstrap_install = False
        is_voidstrap_install = False

        fishstrap_root = os.path.expandvars(r"%LOCALAPPDATA%\Fishstrap")
        fishstrap_launcher = os.path.join(fishstrap_root, "Fishstrap.exe")

        voidstrap_root = os.path.expandvars(r"%LOCALAPPDATA%\Voidstrap")
        voidstrap_launcher = os.path.join(voidstrap_root, "Voidstrap.exe")

        def _launch_with_launcher(target_url, context):
            """Launch via the resolved launcher executable with shared logging."""
            command = [launcher_exe]
            if launcher_requires_player_flag:
                command.append("-player")
            command.append(target_url)
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **RobloxAPI._subprocess_no_window_kwargs(),
            )
            launcher_display = launcher_name or (
                "Bloxstrap" if is_bloxstrap_install else (
                    "Fishstrap" if is_fishstrap_install else (
                        "Voidstrap" if is_voidstrap_install else os.path.basename(launcher_exe)
                    )
                )
            )
            _log_debug(f"Launching {context} via {launcher_display} with URL: {target_url}")

        if using_local_install:
            explicit_name = None
            if explicit_executable_provided and explicit_executable_path:
                explicit_name = os.path.basename(explicit_executable_path).lower()

            if explicit_name == "bloxstrap.exe":
                launcher_exe = explicit_executable_path
                launcher_name = "Bloxstrap"
                launcher_requires_player_flag = True
                is_bloxstrap_install = True
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                _log_debug(f"Using explicitly selected bootstrapper at {launcher_exe}")
            elif explicit_name == "fishstrap.exe":
                launcher_exe = explicit_executable_path
                launcher_name = "Fishstrap"
                launcher_requires_player_flag = True
                is_fishstrap_install = True
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                _log_debug(f"Using explicitly selected bootstrapper at {launcher_exe}")
            elif explicit_name == "voidstrap.exe":
                launcher_exe = explicit_executable_path
                launcher_name = "Voidstrap"
                launcher_requires_player_flag = True
                is_voidstrap_install = True
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                _log_debug(f"Using explicitly selected bootstrapper at {launcher_exe}")
            elif explicit_name == "robloxplayerlauncher.exe":
                launcher_exe = explicit_executable_path
                launcher_name = "RobloxPlayerLauncher"
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")
                _log_debug(f"Using explicitly selected launcher at {launcher_exe}")
            elif explicit_executable_provided and explicit_executable_path:
                roblox_exe = explicit_executable_path
                _log_debug(f"Using explicitly selected RobloxPlayer at {roblox_exe}")
            else:
                roblox_exe = os.path.join(effective_path, "RobloxPlayerBeta.exe")

            if launcher_exe and not os.path.exists(launcher_exe):
                print(f"[ERROR] Launcher executable not found: {launcher_exe}")
                return False
            if (not launcher_exe) and (not os.path.exists(roblox_exe)):
                print(f"[ERROR] RobloxPlayerBeta.exe not found in {effective_path}")
                return False

            if not explicit_executable_provided:
                normalized_root = bloxstrap_root.lower()
                effective_lower = effective_path.lower()
                if normalized_root and effective_lower.startswith(normalized_root):
                    is_bloxstrap_install = True
                    if os.path.exists(bloxstrap_launcher):
                        launcher_exe = bloxstrap_launcher
                        launcher_name = "Bloxstrap"
                        launcher_requires_player_flag = True
                        _log_debug(f"Using Bloxstrap launcher at {launcher_exe}")
                    else:
                        print("[WARNING] Bloxstrap path detected but Bloxstrap.exe was not found; falling back to RobloxPlayerBeta.exe")

                fishstrap_root_lower = fishstrap_root.lower()
                if not launcher_exe and fishstrap_root_lower and effective_lower.startswith(fishstrap_root_lower):
                    is_fishstrap_install = True
                    if os.path.exists(fishstrap_launcher):
                        launcher_exe = fishstrap_launcher
                        launcher_name = "Fishstrap"
                        launcher_requires_player_flag = True
                        _log_debug(f"Using Fishstrap launcher at {launcher_exe}")
                    else:
                        print("[WARNING] Fishstrap path detected but Fishstrap.exe was not found; falling back to RobloxPlayerBeta.exe")

                voidstrap_root_lower = voidstrap_root.lower()
                if not launcher_exe and voidstrap_root_lower and effective_lower.startswith(voidstrap_root_lower):
                    is_voidstrap_install = True
                    if os.path.exists(voidstrap_launcher):
                        launcher_exe = voidstrap_launcher
                        launcher_name = "Voidstrap"
                        launcher_requires_player_flag = True
                        _log_debug(f"Using Voidstrap launcher at {launcher_exe}")
                    else:
                        print("[WARNING] Voidstrap path detected but Voidstrap.exe was not found; falling back to RobloxPlayerBeta.exe")

                if not launcher_exe:
                    possible_launcher = os.path.join(effective_path, "RobloxPlayerLauncher.exe")
                    if os.path.exists(possible_launcher):
                        launcher_exe = possible_launcher
                        launcher_name = "RobloxPlayerLauncher"
                        _log_debug(f"Found RobloxPlayerLauncher.exe at {launcher_exe}")
                    else:
                        try:
                            versions_root = Path(effective_path).parent
                            launcher_candidates = []
                            for candidate_dir in versions_root.iterdir():
                                if not candidate_dir.is_dir() or not candidate_dir.name.startswith("version-"):
                                    continue
                                candidate_launcher = candidate_dir / "RobloxPlayerLauncher.exe"
                                if candidate_launcher.exists():
                                    launcher_candidates.append(candidate_launcher)

                            if launcher_candidates:
                                best_launcher = max(launcher_candidates, key=lambda p: p.stat().st_mtime)
                                launcher_exe = str(best_launcher)
                                launcher_name = "RobloxPlayerLauncher"
                                _log_debug(f"Found RobloxPlayerLauncher.exe in {best_launcher.parent.name}: {launcher_exe}")
                            else:
                                _log_debug("RobloxPlayerLauncher.exe not found, falling back to RobloxPlayerBeta.exe")
                        except Exception as exc:
                            _log_debug(f"RobloxPlayerLauncher.exe scan failed, falling back to RobloxPlayerBeta.exe: {exc}")

            print(f"Using Roblox version from: {effective_path}")
            _log_debug(f"Roblox executable resolved to {roblox_exe}")
        else:
            roblox_exe = 'RobloxPlayerBeta.exe'
            _log_debug("Using default Roblox installation (RobloxPlayerBeta.exe on PATH)")

        normalized_launch_mode = str(launch_mode or "game").strip().lower()
        if normalized_launch_mode not in {"game", "join_user"}:
            normalized_launch_mode = "game"

        if normalized_launch_mode != "join_user" and (not game_id or game_id == ""):
            browser_tracker_id = random.randint(55393295400, 55393295500)
            launch_time = int(time.time() * 1000)

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
                if launcher_exe:
                    _launch_with_launcher(url, "Roblox Home")
                elif using_local_install:
                    try:
                        subprocess.Popen(
                            [roblox_exe, url],
                            cwd=effective_path,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=creation_flags
                        )
                        _log_debug(f"Launching Roblox Home via RobloxPlayerBeta.exe with URL arg: {url}")
                    except Exception as exc:
                        _log_debug(f"RobloxPlayerBeta.exe URL-arg launch failed, falling back to -t flow: {exc}")
                        launch_args = [
                            roblox_exe,
                            "-a", "https://www.roblox.com/Login/Negotiate.ashx",
                            "-t", auth_ticket,
                        ]
                        subprocess.Popen(
                            launch_args,
                            cwd=effective_path,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=creation_flags
                        )
                        _log_debug(f"Launching custom Roblox executable with args: {' '.join(launch_args)}")
                elif RobloxAPI._launch_protocol_url(url):
                    _log_debug(f"Launching Roblox Home via protocol URL: {url}")
                else:
                    raise RuntimeError("Roblox protocol handler failed to launch.")

                print("[SUCCESS] Roblox home launched successfully!")
                if enable_debug:
                    RobloxAPI._debug_check_auto_login(username, auth_ticket)
                return True
            except Exception as e:
                print(f"[ERROR] Failed to launch Roblox: {e}")
                return False
                    
        browser_tracker_id = random.randint(55393295400, 55393295500)
        launch_time = int(time.time() * 1000)

        if normalized_launch_mode == "join_user":
            place_launch_request = "RequestFollowUser"
            place_launch_extra = "&userId=" + str(game_id)
            place_launch_base = (
                "https://assetgame.roblox.com/game/PlaceLauncher.ashx?request=" + place_launch_request +
                "&browserTrackerId=" + str(browser_tracker_id) +
                place_launch_extra
            )
        else:
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
            elif server_job_id:
                place_launch_request = "RequestGameJob"
                place_launch_extra = "&gameId=" + str(server_job_id)
            place_launch_base = (
                "https://assetgame.roblox.com/game/PlaceLauncher.ashx?request=" + place_launch_request +
                "&browserTrackerId=" + str(browser_tracker_id) +
                "&placeId=" + str(game_id) +
                "&isPlayTogetherGame=false" +
                place_launch_extra
            )

        url = (
            "roblox-player:1+launchmode:play+gameinfo:" + auth_ticket_encoded +
            "+launchtime:" + str(launch_time) +
            "+placelauncherurl:" + place_launch_base
        )

        url += (
            "+browsertrackerid:" + str(browser_tracker_id) +
            "+robloxLocale:en_us+gameLocale:en_us"
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
            if launcher_exe:
                _launch_with_launcher(url, "game")
            else:
                if using_local_install:
                    try:
                        subprocess.Popen(
                            [roblox_exe, url],
                            cwd=effective_path,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=creation_flags
                        )
                        _log_debug(f"Launching game via RobloxPlayerBeta.exe with URL arg: {url}")
                        print("[SUCCESS] Roblox launched successfully!")
                        if enable_debug:
                            RobloxAPI._debug_check_auto_login(username, auth_ticket)
                        return True
                    except Exception as exc:
                        _log_debug(f"RobloxPlayerBeta.exe URL-arg launch failed, falling back to -t flow: {exc}")
                    place_launch_url = place_launch_base
                    launch_args = [
                        roblox_exe,
                        "-a", "https://www.roblox.com/Login/Negotiate.ashx",
                        "-t", auth_ticket,
                        "-j", place_launch_url,
                    ]
                    subprocess.Popen(
                        launch_args,
                        cwd=effective_path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creation_flags
                    )
                    _log_debug(f"Launching custom Roblox executable with args: {' '.join(launch_args)}")
                elif RobloxAPI._launch_protocol_url(url):
                    _log_debug(f"Launching game via protocol URL: {url}")
                else:
                    raise RuntimeError("Roblox protocol handler failed to launch.")
            print("[SUCCESS] Roblox launched successfully!")
            if enable_debug:
                RobloxAPI._debug_check_auto_login(username, auth_ticket)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to launch Roblox: {e}")
            return False
    
    @staticmethod
    def validate_account(username, cookie, verbose=True):
        """Validate if an account's cookie is still valid and optionally print token details."""
        try:
            normalized_cookie = RobloxAPI._normalize_roblosecurity_cookie(cookie)
            headers = {
                'Cookie': f'.ROBLOSECURITY={normalized_cookie}'
            }
            
            response = RobloxAPI._get_http_session().get(
                'https://users.roblox.com/v1/users/authenticated',
                headers=headers,
                timeout=10
            )
            
            is_valid = response.status_code == 200

            if verbose:
                print(f"\n{'='*60}")
                print(f"ACCOUNT VALIDATION: {username}")
                print(f"{'='*60}")
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
    def _launch_protocol_url(url):
        """Launch the Roblox protocol URL in a cross-platform-safe way."""
        system = platform.system()
        if system == "Windows":
            try:
                os.startfile(url)
                return True
            except OSError as exc:
                winerror = getattr(exc, "winerror", None)
                if winerror in (-2147221003, 1155):
                    if not RobloxAPI._protocol_handler_missing_warned:
                        print("[WARNING] Roblox protocol handler is not registered; skipping protocol launch.")
                        RobloxAPI._protocol_handler_missing_warned = True
                    return False

                print(f"[WARNING] os.startfile failed: {exc}. Falling back to PowerShell.")
                command = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Start-Process -FilePath '{url}'"
                ]
        elif system == "Darwin":
            command = ["open", url]
        else:
            command = ["xdg-open", url]

        try:
            if system == "Windows":
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    **RobloxAPI._subprocess_no_window_kwargs(),
                )
            else:
                subprocess.run(command, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"[ERROR] Failed to trigger Roblox protocol handler: {exc}")
            return False
