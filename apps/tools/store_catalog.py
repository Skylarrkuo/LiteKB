"""Read-only FIT2CLOUD catalogue and package resolution for the workspace tool store."""
import hashlib
import io
import json
import zipfile
from urllib.parse import urlsplit

import requests
from django.core.cache.backends.locmem import LocMemCache
from django.utils.translation import gettext_lazy as _

from common.exception.app_exception import AppApiException
from common.utils.url_validator import ALLOWED_DOWNLOAD_HOSTS, validate_trusted_url

CATALOG_URL = "https://apps-assets.fit2cloud.com/stable/maxkb.json.zip"
_catalog_cache = LocMemCache("litekb-tool-catalog", {"TIMEOUT": 300, "OPTIONS": {"MAX_ENTRIES": 4}})


class StoreError(AppApiException):
    """Keep the normal console error body and expose the HTTP status to API clients."""

    def __init__(self, code, message):
        super().__init__(code, message)
        self.status_code = code


def trusted_asset(url):
    try:
        return validate_trusted_url(url, ALLOWED_DOWNLOAD_HOSTS)
    except ValueError:
        return False


def read_remote(url, max_bytes):
    if not trusted_asset(url):
        raise StoreError(400, _("Illegal download url"))
    try:
        with requests.get(url, timeout=(5, 20), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise StoreError(502, _("Tool store download failed") + f" (HTTP {response.status_code})")
            body = bytearray()
            for chunk in response.iter_content(64 * 1024):
                if len(body) + len(chunk) > max_bytes:
                    raise StoreError(502, _("Tool store file is too large"))
                body.extend(chunk)
            return bytes(body)
    except requests.RequestException:
        raise StoreError(502, _("Tool store is temporarily unavailable")) from None


def parse_catalog(blob):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            files = [file for file in archive.infolist() if not file.is_dir() and file.filename.endswith(".json")]
            if len(files) != 1 or files[0].file_size > 8 * 1024 * 1024:
                raise ValueError()
            catalog = json.loads(archive.read(files[0]))
        tags = catalog["additionalProperties"]["tags"]
        if not isinstance(tags, list) or not isinstance(catalog["apps"], list):
            raise ValueError()
        tag_keys = {tag["name"]: tag["key"] for tag in tags}
        apps = []
        for row in catalog["apps"]:
            if not isinstance(row, dict) or not row.get("id") or not row.get("name"):
                continue
            url = row.get("downloadUrl")
            if not trusted_asset(url) or not urlsplit(url).path.endswith(".tool"):
                continue
            versions = [v for v in row.get("versions") or [] if isinstance(v, dict) and v.get("name")
                        and trusted_asset(v.get("downloadUrl")) and urlsplit(v["downloadUrl"]).path.endswith(".tool")]
            current = next((v for v in versions if v["downloadUrl"] == url), None)
            if not current:
                continue
            labels = [tag_keys.get(tag, tag) for tag in row.get("tags", [])]
            apps.append({**row, "icon": row.get("icon") if trusted_asset(row.get("icon")) else "",
                         "label": next(iter(labels), ""), "labels": labels, "version": current["name"], "versions": versions})
        return {"apps": apps, "additionalProperties": {"tags": tags}}
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError, zipfile.BadZipFile):
        raise StoreError(502, _("Invalid tool store catalogue")) from None


def get_catalog(url=CATALOG_URL, query=""):
    key = hashlib.sha256(url.encode()).hexdigest()
    catalog = _catalog_cache.get(key)
    if catalog is None:
        catalog = parse_catalog(read_remote(url, 2 * 1024 * 1024))
        _catalog_cache.set(key, catalog)
    query = query.strip().casefold()
    if not query:
        return catalog
    def matches(item):
        values = [item.get(k) or "" for k in ("id", "name", "description", "title")]
        return any(query in str(value).casefold() for value in [*values, *item.get("tags", [])])
    return {**catalog, "apps": [item for item in catalog["apps"] if matches(item)]}


def resolve_release(catalog, template_id, version=None, legacy_url=None):
    item = next((row for row in catalog["apps"] if row["id"] == template_id), None)
    if item is None:
        raise StoreError(404, _("Tool not found"))
    for release in item["versions"]:
        if version and release["name"] != version:
            continue
        if legacy_url and release["downloadUrl"] != legacy_url:
            continue
        if not version and not legacy_url and release["name"] != item["version"]:
            continue
        return item, release
    raise StoreError(400, _("Unknown tool store version"))
