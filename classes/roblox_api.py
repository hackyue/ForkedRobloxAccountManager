"""
Roblox API interaction utilities
Handles authentication, info, and game launching
"""

import os
import platform
import time
import random
import subprocess
import threading
import requests
from pathlib import Path

from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry



class RobloxAPI:
    """Handles all Roblox API interactions"""

    _protocol_handler_missing_warned = False
    _http_session = None
    _http_session_lock = threading.Lock()

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
    def _format_token_preview(cookie):
        if not cookie:
            return "(No token found)"
        if len(cookie) > 60:
            return f"{cookie[:50]}...{cookie[-10:]}"
        return cookie
    
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
    def get_random_public_server_job_id(place_id, max_pages=3):
        if not place_id:
            return None

        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            return None

        collected_servers = []
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

                response = None
                page_ok = False
                max_attempts = 4
                for attempt in range(1, max_attempts + 1):
                    try:
                        response = session.get(url, params=params, timeout=8)
                    except requests.exceptions.RequestException as exc:
                        if attempt == max_attempts:
                            print(f"[WARNING] Failed to fetch public servers for place {place_id_str}: {exc}")
                            return None
                        time.sleep(min(2.0 * attempt, 6.0))
                        continue

                    if response.status_code != 429:
                        page_ok = True
                        break

                    retry_after = str(response.headers.get("Retry-After") or "").strip()
                    delay_seconds = 0
                    if retry_after.isdigit():
                        delay_seconds = int(retry_after)
                    if delay_seconds <= 0:
                        delay_seconds = min(2 * attempt, 8)
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)

                if not page_ok or response is None:
                    
                    return None

                response.raise_for_status()
                payload = response.json() if response.content else {}
                servers = payload.get("data") or []

                for server in servers:
                    job_id = str(server.get("id") or "").strip()
                    if not job_id:
                        continue
                    try:
                        max_players = int(server.get("maxPlayers", 0) or 0)
                    except Exception:
                        max_players = 0
                    try:
                        playing = int(server.get("playing", 0) or 0)
                    except Exception:
                        playing = 0
                    if max_players > 0 and playing >= max_players:
                        continue
                    collected_servers.append(job_id)

                pages_fetched += 1
                cursor = str(payload.get("nextPageCursor") or "").strip()
                if not cursor:
                    break

            if not collected_servers:
                return None
            return random.choice(collected_servers)
        except Exception as exc:
            print(f"[WARNING] Failed to fetch public servers for place {place_id_str}: {exc}")
            return None

    @staticmethod
    def get_lowest_public_server_job_id(place_id, max_pages=3):
        if not place_id:
            return None

        place_id_str = str(place_id).strip()
        if not place_id_str.isdigit():
            return None

        best_choice = None
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

                response = None
                page_ok = False
                max_attempts = 4
                for attempt in range(1, max_attempts + 1):
                    try:
                        response = session.get(url, params=params, timeout=8)
                    except requests.exceptions.RequestException as exc:
                        if attempt == max_attempts:
                            print(f"[WARNING] Failed to fetch public servers for place {place_id_str}: {exc}")
                            return None
                        time.sleep(min(2.0 * attempt, 6.0))
                        continue

                    if response.status_code != 429:
                        page_ok = True
                        break

                    retry_after = str(response.headers.get("Retry-After") or "").strip()
                    delay_seconds = 0
                    if retry_after.isdigit():
                        delay_seconds = int(retry_after)
                    if delay_seconds <= 0:
                        delay_seconds = min(2 * attempt, 8)
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)

                if not page_ok or response is None:
                    return None

                response.raise_for_status()
                payload = response.json() if response.content else {}
                servers = payload.get("data") or []

                for server in servers:
                    job_id = str(server.get("id") or "").strip()
                    if not job_id:
                        continue
                    try:
                        max_players = int(server.get("maxPlayers", 0) or 0)
                    except Exception:
                        max_players = 0
                    try:
                        playing = int(server.get("playing", 0) or 0)
                    except Exception:
                        playing = 0
                    if max_players > 0 and playing >= max_players:
                        continue
                    fill_ratio = (playing / max_players) if max_players > 0 else 1.0
                    ranking = (playing, fill_ratio, random.random())
                    if best_choice is None or ranking < best_choice[0]:
                        best_choice = (ranking, job_id)

                pages_fetched += 1
                cursor = str(payload.get("nextPageCursor") or "").strip()
                if not cursor:
                    break

            if best_choice is None:
                return None
            return best_choice[1]
        except Exception as exc:
            print(f"[WARNING] Failed to fetch low-population public server for place {place_id_str}: {exc}")
            return None
    
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
    def select_roblox_version():
        """Prompt user to select a Roblox version"""
        versions = RobloxAPI.get_installed_versions()
        
        if not versions:
            print("[WARNING] No Roblox versions found in Bloxstrap/Fishstrap Versions folders")
            return None
            
        print("\nAvailable Roblox versions:")
        for i, version in enumerate(versions, 1):
            source = version.get('source', 'Bloxstrap')
            print(f"{i}. {version['version']} [{source}]")
            
        while True:
            try:
                selection = input("\nSelect a version number (or press Enter to use default): ").strip()
                if not selection:
                    return None
                    
                index = int(selection) - 1
                if 0 <= index < len(versions):
                    return versions[index]['path']
                print("Invalid selection. Please try again.")
                
            except ValueError:
                print("Please enter a valid number.")

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
                place_launch_extra = "&linkCode=" + private_server_id
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
                print(f"Private Server: {private_server_id}")
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
    def validate_account(username, cookie):
        """Validate if an account's cookie is still valid and show detailed token info"""
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
                except:
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
