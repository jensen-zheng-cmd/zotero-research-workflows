"""Portable discovery and truthful diagnostics; no live library access."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import doctor
import runtime_config as rc


class RuntimeTests(unittest.TestCase):
    def make_data(self, path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "zotero.sqlite").write_bytes(b"test fixture, not a database")
        return path

    def make_profile(self, root, directory, use=True):
        profile = root / "Profiles/test.default"
        profile.mkdir(parents=True)
        (root / "profiles.ini").write_text("[Profile0]\nIsRelative=1\nPath=Profiles/test.default\nDefault=1\n", encoding="utf-8")
        (profile / "prefs.js").write_text(
            'user_pref("extensions.zotero.useDataDir", ' + ("true" if use else "false") + ');\n'
            'user_pref("extensions.zotero.dataDir", ' + json.dumps(str(directory)) + ');', encoding="utf-8")

    def test_windows_roaming_override_and_unicode_custom_directory(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            home = Path(tmp)
            data = self.make_data(home / "文献 目录")
            roaming = home / "roaming override"
            self.make_profile(roaming / "Zotero/Zotero", data)
            found = rc.discover_data_dirs(home, "Windows", {"APPDATA": str(roaming)})
            self.assertEqual(found, [str(data.resolve())])

    def test_macos_profile_discovery(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            home = Path(tmp)
            data = self.make_data(home / "Library data")
            self.make_profile(home / "Library/Application Support/Zotero", data)
            self.assertEqual(rc.discover_data_dirs(home, "Darwin", {}), [str(data.resolve())])

    def test_disabled_custom_directory_is_not_used(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            home = Path(tmp)
            data = self.make_data(home / "stale data")
            current = self.make_data(home / "Zotero")
            self.make_profile(home / "Library/Application Support/Zotero", data, use=False)
            self.assertEqual(rc.discover_data_dirs(home, "Darwin", {}), [str(current.resolve())])

    def test_multiple_candidates_require_resolution(self):
        with patch.object(rc, "discover_data_dirs", return_value=["one", "two"]):
            self.assertIsNone(rc.data_dir_default({"data_dir": None}))
            self.assertEqual(rc.data_dir_default({"data_dir": "confirmed"}), "confirmed")

    def test_remote_or_credential_endpoints_are_rejected(self):
        for url in ("https://127.0.0.1:23119", "http://example.org:23119",
                    "http://user:key@localhost:23119", "http://localhost:23119/api",
                    "http://localhost:23119/?key=secret", "http://localhost"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                rc.local_url(url)
        self.assertEqual(rc.local_url("http://[::1]:23119/"), "http://[::1]:23119")

    def test_explicit_missing_config_does_not_silently_fallback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "missing.json"
            with patch.dict(os.environ, {"ZOTERO_BATCH_CONFIG": str(path)}):
                with self.assertRaises(ValueError):
                    rc.settings()

    def test_configure_preserves_existing_config(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            data = self.make_data(root / "Zotero")
            config = root / "runtime.local.json"
            with patch.dict(os.environ, {"ZOTERO_BATCH_CONFIG": str(config)}):
                doctor.configure(str(data))
                original = config.read_bytes()
                self.assertEqual(rc.settings()["data_dir"], str(data.resolve()))
                with self.assertRaises(ValueError):
                    doctor.configure(str(data))
                self.assertEqual(config.read_bytes(), original)

    def test_configured_endpoints_are_loaded(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            config = Path(tmp) / "runtime.local.json"
            config.write_text(json.dumps({"schema_version": 1, "api_base": "http://localhost:23120",
                                          "bridge_base": "http://localhost:2620"}), encoding="utf-8")
            with patch.dict(os.environ, {"ZOTERO_BATCH_CONFIG": str(config)}):
                self.assertEqual(rc.settings()["api_base"], "http://localhost:23120")
                self.assertEqual(rc.settings()["bridge_base"], "http://localhost:2620")

    def test_invalid_data_dir_fails_before_save(self):
        with self.assertRaises(ValueError):
            rc.require_data_dir(None)


class DoctorTests(unittest.TestCase):
    def responses(self, url, body=None):
        if url.endswith("/api/"):
            return {"headers": {"Zotero-Server-ID": "test-instance", "Zotero-API-Version": "3"}, "body": {}}
        if url.endswith("/getSelectedCollection"):
            return {"headers": {}, "body": {"libraryID": 1, "id": 7, "editable": True, "filesEditable": True}}
        return {"headers": {}, "body": {"extension_connected": True, "extension_version": "0.5.3+tabreuse", "zotero_running": False}}

    def test_ready_environment_does_not_claim_live_acceptance(self):
        with patch.object(doctor, "get_json", side_effect=self.responses), \
             patch.object(doctor.platform, "system", return_value="Darwin"), \
             patch.object(rc, "data_dir_default", return_value="fake-data"), \
             patch.object(rc, "valid_data_dir", return_value=True), \
             patch.object(doctor.importlib.metadata, "version", return_value="test"), \
             patch.object(doctor.importlib.util, "find_spec", return_value=object()):
            result = doctor.probe({"api_base": "http://localhost:23119", "bridge_base": "http://localhost:2619"})
            self.assertTrue(result["environment_ready"])
            self.assertFalse(result["installation_complete"])
            self.assertEqual(result["live_acceptance"], "not_performed")

    def test_unreachable_services_have_specific_actions(self):
        with patch.object(doctor, "get_json", side_effect=OSError("connection refused")), \
             patch.object(rc, "data_dir_default", return_value=None):
            result = doctor.probe({"api_base": "http://localhost:23119", "bridge_base": "http://localhost:2619"})
            self.assertFalse(result["environment_ready"])
            failed = {row["name"]: row for row in result["checks"] if not row["ok"]}
            for name in ("zotero_local_api", "bridge", "connector", "tab_reuse", "data_dir"):
                self.assertTrue(failed[name]["next_action"])


if __name__ == "__main__":
    unittest.main()
