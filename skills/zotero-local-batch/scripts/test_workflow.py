"""Observable coordinator boundaries with local PDFs and mocked endpoints; no live writes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

import pymupdf
import workflow as w
from test_local_batch import item

PAPER = w.b.candidate({"doi": "10.1234/example", "title": "An example paper with complete identifiable metadata"})
TARGET = {"key": "DEST1234", "path": "Root → Same", "id": 46, "libraryID": 1, "name": "Same"}


class WorkflowTests(unittest.TestCase):
    def test_connector_paths_disambiguate_names_and_libraries(self):
        selected = {"targets": [{"id":"L1","name":"Library","level":0},
                    {"id":"C44","name":"Root","level":1},
                    {"id":"C46","name":"Same","level":2},
                    {"id":"C20","name":"Other","level":1},
                    {"id":"C21","name":"Same","level":2},
                    {"id":"L2","name":"Group","level":0},
                    {"id":"C47","name":"Root","level":1},
                    {"id":"C48","name":"Same","level":2}]}
        self.assertEqual(w.connector_collection_id(["Root", "Same"], selected), 46)
        self.assertEqual(w.connector_collection_id(["Other", "Same"], selected), 21)
        with self.assertRaises(ValueError):
            w.connector_collection_id(["Missing"], selected)

    def test_ambiguous_api_target_requires_full_path(self):
        collections = [
            {"key":"ROOT0001","data":{"name":"Root","parentCollection":False}},
            {"key":"ROOT0002","data":{"name":"Other","parentCollection":False}},
            {"key":"DEST1234","data":{"name":"Same","parentCollection":"ROOT0001"}},
            {"key":"OTHER123","data":{"name":"Same","parentCollection":"ROOT0002"}}]
        with patch.object(w, "paged", return_value=collections), patch.object(w.b,"http") as http:
            with self.assertRaises(ValueError):
                w.resolve_target("Same")
            http.assert_not_called()

    def test_membership_preserves_originals_and_deduplicates_patch_keys(self):
        existing=item("EXIST123", collections=["OLD12345"])
        existing["version"]=7
        updates=w.membership_updates([PAPER,PAPER],[existing],TARGET["key"])
        self.assertEqual(updates,[{"key":"EXIST123","version":7,"collections":["OLD12345","DEST1234"]}])

    def test_resume_uncertain_blocks_reenqueue_but_recognizes_saved_item(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root=Path(directory)
            w.write_json(root/'manifest.json',{"server_id":"server1","target":TARGET,"candidates":[PAPER]})
            w.write_json(root/'saves.json',{"results":[{"candidate":PAPER,"status":"pending","request_id":"r1"}]})
            with patch.object(w,'server_id',return_value='server1'), patch.object(w,'resolve_target',return_value=TARGET), patch.object(w.b,'all_items',return_value=[]):
                result=w.resume_plan(root/'manifest.json')
                self.assertEqual(result['blockers'][0]['request_id'],'r1')
                self.assertNotIn('candidates',result)
            with patch.object(w,'server_id',return_value='server1'), patch.object(w,'resolve_target',return_value=TARGET), patch.object(w.b,'all_items',return_value=[item('EXIST123')]):
                result=w.resume_plan(root/'manifest.json')
                self.assertFalse(result['blockers'])
                self.assertEqual(result['candidates'],[PAPER])

    def test_resume_different_database_stops_before_library_reads(self):
        with patch.object(w,'read_json',return_value={'server_id':'old'}), patch.object(w,'server_id',return_value='new'), patch.object(w.b,'all_items') as library:
            with self.assertRaises(RuntimeError):
                w.resume_plan('manifest.json')
            library.assert_not_called()

    def test_write_uses_single_local_authorization_without_persisting_secret(self):
        secret='local-secret-not-for-reports'
        updates=[{'key':'EXIST123','version':7,'collections':['OLD12345','DEST1234']}]
        authorization=BytesIO(json.dumps({'key':secret,'remember':False}).encode())
        response=BytesIO(json.dumps({'successful':{'0':{'key':'EXIST123'}},'failed':{}}).encode())
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, patch.object(w,'server_id',return_value='server1'), \
             patch.object(w.b.OPENER,'open',side_effect=[authorization,response]) as opened, \
             patch.object(w.b,'http',return_value={'data':{'collections':['OLD12345','DEST1234']}}):
            root=Path(directory)
            self.assertEqual(w.apply_updates(updates,'server1',root,'membership'),1)
            requests=[call.args[0] for call in opened.call_args_list]
            self.assertTrue(requests[0].full_url.endswith('/api/local/authorize'))
            self.assertEqual(requests[1].get_header('Zotero-api-key'),secret)
            for file in root.glob('*.json'):
                self.assertNotIn(secret,file.read_text(encoding='utf-8'))

    def test_write_different_database_stops_before_authorization(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory, patch.object(w,'server_id',return_value='new'), patch.object(w.b.OPENER,'open') as opened:
            with self.assertRaises(RuntimeError):
                w.apply_updates([{'key':'EXIST123','version':1,'pages':'1-12'}],'old',Path(directory),'metadata')
            opened.assert_not_called()

    def test_metadata_only_empty_fields_and_known_identity(self):
        existing=item('EXIST123', collections=['DEST1234'], abstractNote='Keep original')
        existing['version']=7
        record={'item_key':'EXIST123','identity':{'doi':'10.1234/example'},
                'source_url':'https://publisher.example/article','fields':{'abstractNote':'New','pages':'1-12'}}
        with patch.object(w.b,'http',return_value=existing):
            self.assertEqual(w.metadata_updates([record],TARGET),[{'key':'EXIST123','version':7,'pages':'1-12'}])
            record['fields']={'DOI':'10.1234/changed'}
            with self.assertRaises(ValueError):
                w.metadata_updates([record],TARGET)

    def test_audit_validates_real_pdf_and_flags_preprint_edition(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root=Path(directory)
            pdf=root/'storage'/'PDF12345'/'paper.pdf'
            pdf.parent.mkdir(parents=True)
            with pymupdf.open() as document:
                page=document.new_page()
                page.insert_text((30,40),PAPER['title'],fontsize=9)
                page.insert_text((30,60),'arXiv:2508.17094v3')
                document.save(pdf)
            existing=item('EXIST123', collections=['DEST1234'],abstractNote='Abstract',date='2026',creators=[{'lastName':'Author'}])
            child={'key':'PDF12345','data':{'contentType':'application/pdf','linkMode':'imported_file','filename':'paper.pdf','url':'https://arxiv.org/pdf/2508.17094'}}
            with patch.object(w.b,'all_items',return_value=[existing]), patch.object(w,'paged',return_value=[child]):
                result=w.audit([PAPER],TARGET,root)
                self.assertEqual(result['complete'],1)
                self.assertIn('version_notice',result['papers'][0])
                pdf.write_bytes(b'<html>Login</html>')
                result=w.audit([PAPER],TARGET,root)
                self.assertEqual(result['verified_pdfs'],0)
                self.assertFalse(result['papers'][0]['complete'])


if __name__=='__main__':
    unittest.main()
