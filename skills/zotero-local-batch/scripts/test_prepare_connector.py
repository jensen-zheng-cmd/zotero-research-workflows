import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import prepare_connector as prepare


class ArchiveTests(unittest.TestCase):
    def archive(self, name):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as output:
            output.writestr(name, "fixture")
        return data.getvalue()

    def test_expected_archive_can_be_verified(self):
        payload = self.archive("build/manifestv3/agentAPI.js")
        prepare.validate_archive(payload, hashlib.sha256(payload).hexdigest())

    def test_wrong_hash_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare.validate_archive(self.archive("safe.txt"), "0" * 64)

    def test_traversal_is_rejected_before_extraction(self):
        for name in ("../escape.txt", "..\\escape.txt", "/absolute", "C:/absolute"):
            with self.subTest(name=name):
                payload = self.archive(name)
                with self.assertRaises(ValueError):
                    prepare.validate_archive(payload, hashlib.sha256(payload).hexdigest())

    def test_existing_output_is_preserved_without_downloading(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            target = Path(folder) / "user.txt"
            target.write_text("keep", encoding="utf-8")
            with patch.object(prepare.urllib.request, "urlopen") as opened:
                with self.assertRaises(ValueError):
                    prepare.prepare(folder)
                opened.assert_not_called()
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
