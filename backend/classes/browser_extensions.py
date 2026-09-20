"""Managed unpacked browser extensions for browser automation."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import quote, unquote, urljoin, urlparse

import requests


CHROME_WEB_STORE_EXTENSION_ID_PATTERN = re.compile(r"^[a-p]{32}$")
CHROME_WEB_STORE_URL_EXTENSION_ID_PATTERN = re.compile(r"/detail/(?:[^/]+/)?([a-p]{32})(?:[/?#]|$)", re.IGNORECASE)
CRX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
FIREFOX_ADDONS_API_BASE_URL = "https://addons.mozilla.org/api/v5/addons/addon"
FIREFOX_ADDONS_BASE_URL = "https://addons.mozilla.org"
FIREFOX_ADDONS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
    "Gecko/20100101 Firefox/120.0"
)


class BrowserExtensionError(RuntimeError):
    """Raised when a managed browser extension operation fails."""


@dataclass(frozen=True)
class BrowserExtension:
    key: str
    name: str
    source: str
    extension_id: str
    folder_name: str
    enabled: bool
    installed_at: str
    directory: Path
    manifest_version: int

    @property
    def display_source(self) -> str:
        if self.source == "web_store":
            return "Chrome Web Store"
        if self.source == "firefox_addons":
            return "Firefox Add-ons"
        if self.source == "crx":
            return "CRX"
        if self.source == "xpi":
            return "XPI"
        if self.source == "unpacked":
            return "Unpacked"
        return self.source or "Managed"


@dataclass(frozen=True)
class BrowserExtensionRecord:
    key: str
    name: str
    source: str
    extension_id: str
    folder_name: str
    enabled: bool
    installed_at: str

    @classmethod
    def from_mapping(cls, value: Any) -> Optional["BrowserExtensionRecord"]:
        if not isinstance(value, dict):
            return None

        key = str(value.get("key") or "").strip()
        folder_name = str(value.get("folder_name") or "").strip()
        if not key or not folder_name:
            return None

        return cls(
            key=key,
            name=str(value.get("name") or "").strip(),
            source=str(value.get("source") or "managed").strip(),
            extension_id=str(value.get("extension_id") or "").strip(),
            folder_name=folder_name,
            enabled=bool(value.get("enabled", True)),
            installed_at=str(value.get("installed_at") or "").strip(),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "source": self.source,
            "extension_id": self.extension_id,
            "folder_name": self.folder_name,
            "enabled": self.enabled,
            "installed_at": self.installed_at,
        }


class BrowserExtensionManager:
    def __init__(self, data_folder: Path | str) -> None:
        self.data_folder = Path(data_folder)
        self.extensions_folder = self.data_folder / "browser_extensions"
        self.metadata_path = self.data_folder / "browser_extensions.json"

    def ensure_storage(self) -> None:
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.extensions_folder.mkdir(parents=True, exist_ok=True)

    def list_extensions(self) -> list[BrowserExtension]:
        self.ensure_storage()
        records = self._read_records()
        extensions: list[BrowserExtension] = []
        for record in records:
            try:
                extensions.append(self._extension_from_record(record))
            except BrowserExtensionError:
                continue
        extensions.sort(key=lambda extension: extension.name.casefold())
        return extensions

    def get_enabled_extension_paths(self) -> list[Path]:
        paths: list[Path] = []
        for extension in self.list_extensions():
            if extension.enabled:
                paths.append(extension.directory)
        return paths

    def set_extension_enabled(self, key: str, enabled: bool) -> None:
        normalized_key = str(key or "").strip()
        records = self._read_records()
        updated_records: list[BrowserExtensionRecord] = []
        changed = False
        for record in records:
            if record.key == normalized_key:
                updated_records.append(
                    BrowserExtensionRecord(
                        key=record.key,
                        name=record.name,
                        source=record.source,
                        extension_id=record.extension_id,
                        folder_name=record.folder_name,
                        enabled=bool(enabled),
                        installed_at=record.installed_at,
                    )
                )
                changed = True
            else:
                updated_records.append(record)

        if not changed:
            raise BrowserExtensionError("Extension was not found.")
        self._write_records(updated_records)

    def remove_extension(self, key: str) -> None:
        normalized_key = str(key or "").strip()
        records = self._read_records()
        record = next((candidate for candidate in records if candidate.key == normalized_key), None)
        if record is None:
            raise BrowserExtensionError("Extension was not found.")

        target_dir = self.extensions_folder / record.folder_name
        self._assert_path_inside(target_dir, self.extensions_folder)
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to remove extension files: {exc}") from exc

        self._write_records([candidate for candidate in records if candidate.key != normalized_key])

    def add_from_extension_id(self, extension_id_or_url: str) -> BrowserExtension:
        extension_id = self.normalize_extension_id(extension_id_or_url)
        crx_bytes = self._download_crx(extension_id)
        return self._install_from_extractor(
            desired_key=extension_id,
            source="web_store",
            extension_id=extension_id,
            extractor=lambda target_dir: self._extract_crx(crx_bytes, target_dir),
        )

    def add_from_firefox_addon(self, addon_id_or_url: str) -> BrowserExtension:
        addon_identifier = self.normalize_firefox_addon_id(addon_id_or_url)
        addon_payload = self._fetch_firefox_addon_metadata(addon_identifier)
        file_url = self._resolve_firefox_addon_file_url(addon_payload)
        xpi_bytes = self._download_xpi(file_url)
        addon_slug = self._coerce_text(addon_payload.get("slug")) or addon_identifier
        addon_guid = self._coerce_text(addon_payload.get("guid")) or addon_slug
        return self._install_from_extractor(
            desired_key=self._sanitize_key(f"firefox-{addon_slug}"),
            source="firefox_addons",
            extension_id=addon_guid,
            extractor=lambda target_dir: self._extract_xpi(xpi_bytes, target_dir),
        )

    def add_from_crx(self, crx_path: Path | str) -> BrowserExtension:
        source_path = Path(crx_path).expanduser().resolve()
        if not source_path.is_file():
            raise BrowserExtensionError(f"CRX file was not found: {source_path}")
        try:
            crx_bytes = source_path.read_bytes()
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to read CRX file: {exc}") from exc

        digest = hashlib.sha1(crx_bytes).hexdigest()[:10]
        desired_key = self._sanitize_key(f"{source_path.stem}-{digest}")
        return self._install_from_extractor(
            desired_key=desired_key,
            source="crx",
            extension_id="",
            extractor=lambda target_dir: self._extract_crx(crx_bytes, target_dir),
        )

    def add_from_xpi(self, xpi_path: Path | str) -> BrowserExtension:
        source_path = Path(xpi_path).expanduser().resolve()
        if not source_path.is_file():
            raise BrowserExtensionError(f"XPI file was not found: {source_path}")
        try:
            xpi_bytes = source_path.read_bytes()
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to read XPI file: {exc}") from exc

        digest = hashlib.sha1(xpi_bytes).hexdigest()[:10]
        desired_key = self._sanitize_key(f"{source_path.stem}-{digest}")
        return self._install_from_extractor(
            desired_key=desired_key,
            source="xpi",
            extension_id="",
            extractor=lambda target_dir: self._extract_xpi(xpi_bytes, target_dir),
        )

    def add_from_unpacked(self, source_dir: Path | str) -> BrowserExtension:
        source_path = Path(source_dir).expanduser().resolve()
        if not source_path.is_dir():
            raise BrowserExtensionError(f"Extension folder was not found: {source_path}")
        if not (source_path / "manifest.json").is_file():
            raise BrowserExtensionError("The selected folder does not contain manifest.json.")

        desired_key = self._sanitize_key(source_path.name)
        return self._install_from_extractor(
            desired_key=desired_key,
            source="unpacked",
            extension_id="",
            extractor=lambda target_dir: self._copy_unpacked_extension(source_path, target_dir),
        )

    @classmethod
    def normalize_extension_id(cls, extension_id_or_url: str) -> str:
        raw_value = str(extension_id_or_url or "").strip().lower()
        match = CHROME_WEB_STORE_URL_EXTENSION_ID_PATTERN.search(raw_value)
        normalized_id = match.group(1).lower() if match else raw_value
        if not CHROME_WEB_STORE_EXTENSION_ID_PATTERN.fullmatch(normalized_id):
            raise BrowserExtensionError("Enter a valid 32-character Chrome Web Store extension ID.")
        return normalized_id

    @classmethod
    def normalize_firefox_addon_id(cls, addon_id_or_url: str) -> str:
        raw_value = str(addon_id_or_url or "").strip()
        if not raw_value:
            raise BrowserExtensionError("Enter a Firefox Add-ons slug, GUID, numeric ID, or URL.")

        extracted_identifier = cls._extract_firefox_addon_id_from_url(raw_value)
        normalized_identifier = unquote(extracted_identifier or raw_value).strip().strip("/")
        if (
            not normalized_identifier
            or "/" in normalized_identifier
            or "\\" in normalized_identifier
            or any(character.isspace() for character in normalized_identifier)
        ):
            raise BrowserExtensionError("Enter a Firefox Add-ons slug, GUID, numeric ID, or URL.")
        return normalized_identifier

    @classmethod
    def _extract_firefox_addon_id_from_url(cls, value: str) -> str:
        parsed_value = value
        if "://" not in parsed_value and parsed_value.lower().startswith("addons.mozilla.org/"):
            parsed_value = f"https://{parsed_value}"

        parsed_url = urlparse(parsed_value)
        host = parsed_url.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host != "addons.mozilla.org":
            return ""

        path_parts = [unquote(part).strip() for part in parsed_url.path.split("/") if part.strip()]
        for index, part in enumerate(path_parts):
            if part == "firefox" and index + 2 < len(path_parts) and path_parts[index + 1] == "addon":
                return path_parts[index + 2]
            if part == "downloads" and index + 2 < len(path_parts) and path_parts[index + 1] == "latest":
                return path_parts[index + 2]
        return ""

    def _install_from_extractor(
        self,
        desired_key: str,
        source: str,
        extension_id: str,
        extractor: Callable[[Path], None],
    ) -> BrowserExtension:
        self.ensure_storage()
        key = self._unique_key(desired_key, replace_key=extension_id or None)
        folder_name = key
        target_dir = self.extensions_folder / folder_name
        staging_dir = self.extensions_folder / f".{folder_name}.{time.time_ns()}.tmp"
        self._assert_path_inside(target_dir, self.extensions_folder)
        self._assert_path_inside(staging_dir, self.extensions_folder)

        try:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            staging_dir.mkdir(parents=True, exist_ok=True)
            extractor(staging_dir)
            manifest = self._read_manifest(staging_dir)
            name = self._resolve_manifest_name(manifest, staging_dir) or key
            if target_dir.exists():
                shutil.rmtree(target_dir)
            staging_dir.rename(target_dir)
        except BrowserExtensionError:
            raise
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to install extension: {exc}") from exc
        finally:
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir)
                except OSError:
                    pass

        record = BrowserExtensionRecord(
            key=key,
            name=name,
            source=source,
            extension_id=extension_id,
            folder_name=folder_name,
            enabled=True,
            installed_at=f"{datetime.utcnow().isoformat(timespec='seconds')}Z",
        )
        self._upsert_record(record)
        return self._extension_from_record(record)

    def _download_crx(self, extension_id: str) -> bytes:
        encoded_query = quote(f"id={extension_id}&installsource=ondemand&uc", safe="")
        url = (
            "https://clients2.google.com/service/update2/crx"
            f"?response=redirect&prodversion=120.0.0.0&acceptformat=crx2,crx3&x={encoded_query}"
        )
        try:
            response = requests.get(url, headers={"User-Agent": CRX_USER_AGENT}, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BrowserExtensionError(f"Failed to download extension CRX: {exc}") from exc

        crx_bytes = bytes(response.content or b"")
        if not crx_bytes.startswith(b"Cr24"):
            raise BrowserExtensionError("The Chrome Web Store did not return a CRX package.")
        return crx_bytes

    def _fetch_firefox_addon_metadata(self, addon_identifier: str) -> dict[str, Any]:
        encoded_identifier = quote(addon_identifier, safe="")
        url = f"{FIREFOX_ADDONS_API_BASE_URL}/{encoded_identifier}/"
        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": FIREFOX_ADDONS_USER_AGENT,
                },
                timeout=60,
            )
            if response.status_code == 404:
                raise BrowserExtensionError("Firefox Add-ons could not find that add-on.")
            response.raise_for_status()
        except BrowserExtensionError:
            raise
        except requests.RequestException as exc:
            raise BrowserExtensionError(f"Failed to fetch Firefox add-on metadata: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BrowserExtensionError("Firefox Add-ons returned invalid metadata JSON.") from exc
        if not isinstance(payload, dict):
            raise BrowserExtensionError("Firefox Add-ons returned invalid metadata.")
        return payload

    def _resolve_firefox_addon_file_url(self, addon_payload: dict[str, Any]) -> str:
        current_version = addon_payload.get("current_version")
        if not isinstance(current_version, dict):
            raise BrowserExtensionError("Firefox Add-ons did not return a current extension version.")

        file_payload = current_version.get("file")
        if not isinstance(file_payload, dict):
            raise BrowserExtensionError("Firefox Add-ons did not return an extension download.")

        file_url = self._coerce_text(file_payload.get("url"))
        if not file_url:
            raise BrowserExtensionError("Firefox Add-ons did not return an extension download URL.")
        return urljoin(FIREFOX_ADDONS_BASE_URL, file_url)

    def _download_xpi(self, file_url: str) -> bytes:
        try:
            response = requests.get(
                file_url,
                headers={
                    "Accept": "application/x-xpinstall,application/octet-stream,*/*",
                    "User-Agent": FIREFOX_ADDONS_USER_AGENT,
                },
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BrowserExtensionError(f"Failed to download Firefox XPI: {exc}") from exc

        xpi_bytes = bytes(response.content or b"")
        if not xpi_bytes.startswith(b"PK"):
            raise BrowserExtensionError("Firefox Add-ons did not return an XPI package.")
        return xpi_bytes

    def _extract_crx(self, crx_bytes: bytes, target_dir: Path) -> None:
        zip_start = self._get_crx_zip_start(crx_bytes)
        try:
            with zipfile.ZipFile(BytesIO(crx_bytes[zip_start:])) as archive:
                self._extract_zip_safely(archive, target_dir)
        except zipfile.BadZipFile as exc:
            raise BrowserExtensionError("The CRX file does not contain a valid zip payload.") from exc
        if not (target_dir / "manifest.json").is_file():
            raise BrowserExtensionError("The extension package did not contain manifest.json.")

    def _extract_xpi(self, xpi_bytes: bytes, target_dir: Path) -> None:
        try:
            with zipfile.ZipFile(BytesIO(xpi_bytes)) as archive:
                self._extract_zip_safely(archive, target_dir)
        except zipfile.BadZipFile as exc:
            raise BrowserExtensionError("The XPI file is not a valid zip package.") from exc
        if not (target_dir / "manifest.json").is_file():
            raise BrowserExtensionError("The extension package did not contain manifest.json.")

    def _copy_unpacked_extension(self, source_path: Path, target_dir: Path) -> None:
        try:
            for source_item in source_path.iterdir():
                target_item = target_dir / source_item.name
                if source_item.is_dir():
                    shutil.copytree(source_item, target_item, symlinks=False)
                else:
                    shutil.copy2(source_item, target_item)
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to copy unpacked extension: {exc}") from exc

    def _extract_zip_safely(self, archive: zipfile.ZipFile, target_dir: Path) -> None:
        root = target_dir.resolve()
        for member in archive.infolist():
            member_name = member.filename.replace("\\", "/")
            if not member_name:
                continue
            if member_name.startswith("/") or re.match(r"^[A-Za-z]:", member_name):
                raise BrowserExtensionError("The extension archive contains an unsafe path.")
            destination = (target_dir / member_name).resolve()
            try:
                destination.relative_to(root)
            except ValueError as exc:
                raise BrowserExtensionError("The extension archive contains an unsafe path.") from exc
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source_fp, destination.open("wb") as target_fp:
                    shutil.copyfileobj(source_fp, target_fp)

    @staticmethod
    def _get_crx_zip_start(crx_bytes: bytes) -> int:
        if len(crx_bytes) < 12 or not crx_bytes.startswith(b"Cr24"):
            raise BrowserExtensionError("The file is not a valid CRX package.")

        version = int.from_bytes(crx_bytes[4:8], "little")
        if version == 2:
            if len(crx_bytes) < 16:
                raise BrowserExtensionError("The CRX v2 header is incomplete.")
            public_key_length = int.from_bytes(crx_bytes[8:12], "little")
            signature_length = int.from_bytes(crx_bytes[12:16], "little")
            return 16 + public_key_length + signature_length
        if version == 3:
            header_length = int.from_bytes(crx_bytes[8:12], "little")
            return 12 + header_length
        raise BrowserExtensionError(f"Unsupported CRX version: {version}")

    def _extension_from_record(self, record: BrowserExtensionRecord) -> BrowserExtension:
        directory = self.extensions_folder / record.folder_name
        self._assert_path_inside(directory, self.extensions_folder)
        manifest = self._read_manifest(directory)
        name = record.name or self._resolve_manifest_name(manifest, directory) or record.key
        return BrowserExtension(
            key=record.key,
            name=name,
            source=record.source,
            extension_id=record.extension_id,
            folder_name=record.folder_name,
            enabled=record.enabled,
            installed_at=record.installed_at,
            directory=directory,
            manifest_version=self._coerce_manifest_version(manifest.get("manifest_version")),
        )

    def _read_manifest(self, extension_dir: Path) -> dict[str, Any]:
        manifest_path = extension_dir / "manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BrowserExtensionError(f"manifest.json was not found in {extension_dir}") from exc
        except json.JSONDecodeError as exc:
            raise BrowserExtensionError(f"manifest.json is not valid JSON: {manifest_path}") from exc
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to read manifest.json: {exc}") from exc
        if not isinstance(payload, dict):
            raise BrowserExtensionError("manifest.json must contain a JSON object.")
        return payload

    def _resolve_manifest_name(self, manifest: dict[str, Any], extension_dir: Path) -> str:
        raw_name = str(manifest.get("name") or manifest.get("short_name") or "").strip()
        message_match = re.fullmatch(r"__MSG_(.+)__", raw_name)
        if message_match is None:
            return raw_name

        default_locale = str(manifest.get("default_locale") or "").strip()
        if not default_locale:
            return raw_name

        messages_path = extension_dir / "_locales" / default_locale / "messages.json"
        try:
            messages_payload = json.loads(messages_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return raw_name
        if not isinstance(messages_payload, dict):
            return raw_name

        message_entry = messages_payload.get(message_match.group(1))
        if not isinstance(message_entry, dict):
            return raw_name
        resolved_name = str(message_entry.get("message") or "").strip()
        return resolved_name or raw_name

    @staticmethod
    def _coerce_manifest_version(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _upsert_record(self, record: BrowserExtensionRecord) -> None:
        records = self._read_records()
        if record.extension_id:
            records = [
                candidate
                for candidate in records
                if candidate.key != record.key and candidate.extension_id != record.extension_id
            ]
        else:
            records = [candidate for candidate in records if candidate.key != record.key]
        records.append(record)
        self._write_records(records)

    def _read_records(self) -> list[BrowserExtensionRecord]:
        self.ensure_storage()
        if not self.metadata_path.is_file():
            return []
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BrowserExtensionError(f"browser_extensions.json is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to read browser_extensions.json: {exc}") from exc
        if not isinstance(payload, list):
            raise BrowserExtensionError("browser_extensions.json must contain a JSON list.")

        records: list[BrowserExtensionRecord] = []
        for item in payload:
            record = BrowserExtensionRecord.from_mapping(item)
            if record is not None:
                records.append(record)
        return records

    def _write_records(self, records: Sequence[BrowserExtensionRecord]) -> None:
        self.ensure_storage()
        temp_path = self.metadata_path.with_suffix(".json.tmp")
        payload = [record.to_mapping() for record in sorted(records, key=lambda item: item.name.casefold())]
        try:
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self.metadata_path)
        except OSError as exc:
            raise BrowserExtensionError(f"Failed to write browser_extensions.json: {exc}") from exc

    def _unique_key(self, desired_key: str, replace_key: Optional[str] = None) -> str:
        key = self._sanitize_key(desired_key)
        if replace_key:
            records = self._read_records()
            existing_record = next((record for record in records if record.extension_id == replace_key), None)
            if existing_record is not None:
                return existing_record.key

        existing_keys = {record.key for record in self._read_records()}
        if key not in existing_keys and not (self.extensions_folder / key).exists():
            return key

        digest = hashlib.sha1(f"{key}:{time.time_ns()}".encode("utf-8")).hexdigest()[:8]
        return f"{key}-{digest}"

    @staticmethod
    def _sanitize_key(value: str) -> str:
        key = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
        return key[:64] or "extension"

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if isinstance(value, dict):
            preferred_value = value.get("en-US") or value.get("en_US")
            if preferred_value is not None:
                return str(preferred_value).strip()
            for candidate in value.values():
                if candidate is not None:
                    return str(candidate).strip()
            return ""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _assert_path_inside(path: Path, root: Path) -> None:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise BrowserExtensionError(f"Refusing to access path outside managed extensions: {path}") from exc
