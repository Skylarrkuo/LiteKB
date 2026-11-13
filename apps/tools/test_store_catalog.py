"""Catalogue release selection and marketplace boundaries. Tests never run downloaded tools."""
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from tools.store_catalog import StoreError, get_catalog, parse_catalog, read_remote, resolve_release


def archive(data):
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("maxkb.json", json.dumps(data))
    return blob.getvalue()


def catalog_fixture():
    base = "https://apps-assets.fit2cloud.com/stable/maxkb/clock/"
    v2, v1 = base + "2/clock.tool", base + "1/clock.tool"
    return {"additionalProperties": {"tags": [{"key": "content", "name": "内容"}]}, "apps": [
        {"id": "clock", "name": "Clock", "description": "Time conversion", "tags": ["内容"], "downloadUrl": v2,
         "versions": [{"name": "2", "downloadUrl": v2}, {"name": "1", "downloadUrl": v1}]},
        {"id": "legacy", "name": "Broken", "downloadUrl": v1, "versions": []},
        {"id": "wrong", "name": "Wrong kind", "downloadUrl": base + "knowledge.kbwf"},
        {"id": "redirect", "name": "External asset", "downloadUrl": "https://example.org/unit.tool"}
    ]}


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from django.conf import settings
        if not settings.configured:
            settings.configure(USE_I18N=False)

    def test_public_shape_restrictions_and_version_history(self):
        found = parse_catalog(archive(catalog_fixture()))
        self.assertEqual([item["id"] for item in found["apps"]], ["clock"])
        item, release = resolve_release(found, "clock")
        self.assertEqual((item["label"], item["version"], release["name"]), ("content", "2", "2"))
        self.assertEqual(resolve_release(found, "clock", version="1")[1]["name"], "1")
        with self.assertRaises(StoreError):
            resolve_release(found, "clock", version="3")
        with self.assertRaises(StoreError):
            resolve_release(found, "clock", version="1", legacy_url=release["downloadUrl"])
        with self.assertRaises(StoreError):
            resolve_release(found, "unknown")

    def test_search_reuses_cached_success_and_recovers_after_upstream_error(self):
        url = "https://apps-assets.fit2cloud.com/tests/store-fixture.zip"
        from tools.store_catalog import _catalog_cache
        _catalog_cache.clear()
        self.addCleanup(_catalog_cache.clear)
        with patch("tools.store_catalog.read_remote", side_effect=[StoreError(502, "upstream"), archive(catalog_fixture())]) as http:
            with self.assertRaises(StoreError) as failure:
                get_catalog(url)
            self.assertEqual(failure.exception.status_code, 502)
            self.assertEqual(len(get_catalog(url, "conversion")["apps"]), 1)
            self.assertEqual(len(get_catalog(url, "内容")["apps"]), 1)
            self.assertEqual(get_catalog(url, "unrelated")["apps"], [])
            self.assertEqual(http.call_count, 2)

    def test_download_refuses_untrusted_url_before_transport(self):
        with patch("tools.store_catalog.requests.get") as http:
            for url in ("http://apps-assets.fit2cloud.com/t.tool", "https://external.example/t.tool",
                        "https://apps-assets.fit2cloud.com:443/t.tool", "https://apps-assets.fit2cloud.com:bad/t.tool"):
                with self.subTest(url=url), self.assertRaises(StoreError):
                    read_remote(url, 100)
            http.assert_not_called()

    def test_malformed_or_unexpected_upstream_content_is_actionable(self):
        for content in (b"not a zip", archive({"apps": [None]})):
            with self.assertRaises(StoreError) as failure:
                parse_catalog(content)
            self.assertEqual(failure.exception.status_code, 502)
        with patch("tools.store_catalog.requests.get") as http:
            request = http.return_value.__enter__.return_value
            request.status_code = 302
            with self.assertRaises(StoreError):
                read_remote("https://apps-assets.fit2cloud.com/store.zip", 1)
            self.assertFalse(http.call_args.kwargs["allow_redirects"])
            request.status_code = 200
            request.iter_content.return_value = [b"over-limit"]
            with self.assertRaises(StoreError):
                read_remote("https://apps-assets.fit2cloud.com/store.zip", 1)
