"""Protocol tests with temporary PDFs and mocked local endpoints; no library writes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_batch as batch


def item(key, doi="10.1234/example", **fields):
    return {"key": key, "data": {"itemType": "journalArticle", "DOI": doi,
                                "title": "An example paper with complete identifiable metadata", **fields}}


TARGET = {"libraryID": 1, "libraryName": "我的文库", "id": 44, "name": "LLM Agent", "editable": True}


class BatchTests(unittest.TestCase):
    def test_identifiers_and_arxiv_version_duplicates(self):
        self.assertEqual(batch.candidate("10.1234/EXAMPLE")["url"], "https://doi.org/10.1234/example")
        self.assertEqual(batch.doi("https://doi.org/10.1234%2FEXAMPLE"), "10.1234/example")
        self.assertEqual(batch.url_identity("https://arxiv.org/pdf/2401.12345v2.pdf"), "arxiv:2401.12345")
        self.assertEqual(batch.url_identity("https://arxiv.org/abs/2401.12345v1"), "arxiv:2401.12345")
        with self.assertRaises(ValueError):
            batch.candidate("a paper title without a resolved URL")

    def test_pdf_on_disk_required_not_connector_success(self):
        paper = batch.candidate("10.1234/example")
        child = {"key": "PDF12345", "data": {"itemType": "attachment", "contentType": "application/pdf",
                                               "linkMode": "imported_file", "filename": "paper.pdf"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, patch.object(batch, "http", return_value=[child]):
            row = batch.verify(paper, {"success": True, "item_key": "ITEM1234"}, [], [item("ITEM1234")], folder)
            self.assertEqual(row["status"], "saved_metadata_only")
            pdf = Path(folder) / "storage" / "PDF12345" / "paper.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"<html>Access denied</html>")
            self.assertFalse(batch.verify(paper, {}, [], [item("ITEM1234")], folder)["has_pdf"])
            pdf.write_bytes(b"%PDF-1.7\nTest fixture")
            self.assertTrue(batch.verify(paper, {}, [], [item("ITEM1234")], folder)["has_pdf"])

    def test_wrong_doi_is_not_accepted_from_reported_key(self):
        paper = batch.candidate({"doi":"10.1234/example", "title":"An example paper with complete identifiable metadata"})
        row = batch.verify(paper, {"success": True, "item_key": "WRONGKEY"}, [],
                           [item("WRONGKEY", "10.1234/wrong")], "")
        self.assertEqual(row["status"], "unconfirmed")

    def test_duplicate_does_not_enqueue(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, patch.object(batch, "health", return_value={"target": TARGET}), \
             patch.object(batch, "all_items", return_value=[item("EXISTING")]), patch.object(batch, "http") as http:
            report = batch.run_batch([batch.candidate("10.1234/example")], "LLM Agent", Path(folder) / "report.json", folder)
            self.assertEqual(report["results"][0]["status"], "duplicate")
            http.assert_not_called()

    def test_target_change_stops_before_any_submission(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, patch.object(batch, "health", return_value={"target": TARGET}), \
             patch.object(batch, "all_items", return_value=[]), \
             patch.object(batch, "selected_target", return_value={**TARGET, "id": 26}), patch.object(batch, "http") as http:
            report = batch.run_batch([batch.candidate("10.1234/example"), batch.candidate("10.1234/next")],
                                     "LLM Agent", Path(folder) / "report.json", folder)
            http.assert_not_called()
            self.assertEqual(len(report["remaining"]), 1)
            self.assertTrue(report["results"][0]["stop_batch"])

    def test_uncertain_save_stops_and_keeps_request_id(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, patch.object(batch, "health", return_value={"target": TARGET}), \
             patch.object(batch, "all_items", return_value=[]), patch.object(batch, "selected_target", return_value=TARGET), \
             patch.object(batch, "http", side_effect=[{"request_id": "pending-1"}, {"success": "unconfirmed"}]) as http:
            path = Path(folder) / "report.json"
            report = batch.run_batch([batch.candidate("10.1234/example"), batch.candidate("10.1234/next")], "LLM Agent", path, folder)
            self.assertEqual(http.call_count, 2)
            self.assertEqual(report["results"][0]["status"], "unconfirmed")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["results"][0]["request_id"], "pending-1")
            self.assertEqual(len(report["remaining"]), 1)

    def test_new_metadata_and_verified_pdf_in_one_batch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, patch.object(batch, "health", return_value={"target": TARGET}), \
             patch.object(batch, "all_items", side_effect=[[], [item("ITEM1234")]]), \
             patch.object(batch, "selected_target", return_value=TARGET):
            child = {"key": "PDF12345", "data": {"itemType": "attachment", "contentType": "application/pdf",
                                                   "linkMode": "imported_file", "filename": "paper.pdf"}}
            pdf = Path(folder) / "storage" / "PDF12345" / "paper.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF-1.7\nTest fixture")
            with patch.object(batch, "http", side_effect=[{"request_id": "request-1"}, {"success": True, "item_key": "ITEM1234"}, [child]]):
                report = batch.run_batch([batch.candidate("10.1234/example")], "LLM Agent", Path(folder) / "report.json", folder)
            self.assertEqual(report["results"][0]["status"], "saved_with_pdf")
            self.assertEqual(report["remaining"], [])


if __name__ == "__main__":
    unittest.main()
