import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from observation_loop_fixture import fixture, response_fixture
from card_condition.observation_page import render_page


class ObservationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_receipt"), "receipt storage missing")
        self.api = importlib.import_module("card_condition.observation_receipt")
        self.packet, self.assets = fixture()
        self.body = response_fixture(self.packet)
        self.context = dict(data_origin="synthetic_fixture", source_type="synthetic_fixture", reviewer_id="synthetic-reviewer",
                            session_id="synthetic-session", received_at="2026-11-17T00:00:01Z")

    def test_preserves_exact_raw_and_hash_with_no_human_truth(self):
        self.body['entries'][0]['note'] = '  원문\n '
        raw = (' \n' + json.dumps(self.body, ensure_ascii=False, indent=2) + '\n ').encode()
        with tempfile.TemporaryDirectory() as folder:
            ledger=Path(folder)/'ledger'
            receipt=self.api.capture_receipt(self.packet,raw,self.context,ledger)
            self.assertEqual((ledger/receipt['receipt_id']/'raw.bin').read_bytes(),raw)
            self.assertEqual(receipt['raw_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertFalse(receipt['human_truth']);self.assertFalse(receipt['eligible_for_collection'])
            self.assertEqual(receipt['status'],'synthetic_only')
            self.assertEqual(receipt['response']['entries'][0]['note'],'  원문\n ')
            self.assertEqual(receipt['context']['received_at'],self.context['received_at'])
            another=self.api.capture_receipt(self.packet,raw+b' ',self.context,ledger)
            self.assertNotEqual(another['receipt_id'],receipt['receipt_id'])
            self.assertEqual(len(self.api.load_receipts(self.packet,ledger)['receipts']),2)
            body=copy.deepcopy(self.body);body['entries'][0]['note']=chr(0xd800)
            escaped=json.dumps(body,ensure_ascii=True).encode()
            try:
                special=self.api.capture_receipt(self.packet,escaped,self.context,ledger)
            except UnicodeEncodeError:
                self.fail('escaped surrogate raw must be preserved without UTF-8 re-encoding loss')
            self.assertEqual((ledger/special['receipt_id']/'raw.bin').read_bytes(),escaped)
            self.assertEqual(special['response']['entries'][0]['note'],chr(0xd800))
            self.assertEqual(len(self.api.load_receipts(self.packet,ledger)['receipts']),3)

    def test_rejected_raw_duplicates_invalid_schema_and_ai_source_are_preserved(self):
        wrong=copy.deepcopy(self.body);wrong['entries'][0]['entry_id']='r999'
        duplicates=b'{"entries":[{"state":"normal","state":"defect"}]}'
        for raw in (b'{',duplicates,json.dumps(wrong).encode(),b'\xff'):
            with self.subTest(raw=raw[:20]),tempfile.TemporaryDirectory() as folder:
                receipt=self.api.capture_receipt(self.packet,raw,self.context,folder)
                self.assertEqual(receipt['status'],'rejected')
                self.assertIsNone(receipt['response'])
                self.assertEqual((Path(folder)/receipt['receipt_id']/'raw.bin').read_bytes(),raw)
                self.assertTrue(receipt['reasons'])
                if raw==duplicates:self.assertIn('duplicate',receipt['reasons'][0])
                self.assertEqual(len(self.api.load_receipts(self.packet,folder)['receipts']),1)
        with tempfile.TemporaryDirectory() as folder:
            context=dict(self.context,source_type='ai')
            receipt=self.api.capture_receipt(self.packet,json.dumps(self.body).encode(),context,folder)
            self.assertEqual(receipt['status'],'pending_provenance')
            self.assertFalse(receipt['human_truth'])
        with tempfile.TemporaryDirectory() as folder:
            ledger=Path(folder)/'forbidden'
            with self.assertRaises(ValueError):
                self.api.capture_receipt(self.packet,b'{}',dict(self.context,source_type='human'),ledger)
            self.assertFalse(ledger.exists())

    def test_exact_reception_is_idempotent_but_other_contexts_stay_separate(self):
        raw=json.dumps(self.body).encode()
        with tempfile.TemporaryDirectory() as folder:
            first=self.api.capture_receipt(self.packet,raw,self.context,folder)
            again=self.api.capture_receipt(self.packet,raw,self.context,folder)
            self.assertEqual(first,again)
            other=self.api.capture_receipt(self.packet,raw,dict(self.context,reviewer_id='other-synthetic'),folder)
            self.assertNotEqual(first['receipt_id'],other['receipt_id'])
            mismatch=self.api.capture_receipt(self.packet,raw,dict(self.context,session_id='other-session'),folder)
            self.assertEqual(mismatch['status'],'rejected')
            self.assertFalse(mismatch['display_verified'])
            self.assertEqual(mismatch['missing_entry_ids'],[])
            self.assertNotEqual(mismatch['receipt_id'],first['receipt_id'])
            self.assertEqual(len(self.api.load_receipts(self.packet,folder)['receipts']),3)

    def test_conflicting_observations_keep_both_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            saved=[]
            for state in ('normal','defect'):
                body=copy.deepcopy(self.body);body['entries'][0]['state']=state
                event=copy.deepcopy(body['observations']['events'][0]);event.update(event='change',entry_id='r1',state=state)
                body['observations']['events'].insert(0,event)
                raw=json.dumps(body).encode()
                saved.append(self.api.capture_receipt(self.packet,raw,self.context,folder))
            self.assertEqual(saved[0]['status'],'synthetic_only')
            self.assertEqual(saved[1]['status'],'conflict')
            self.assertEqual(saved[1]['conflicts'],['r1'])
            loaded=self.api.load_receipts(self.packet,folder)['receipts']
            self.assertEqual(len(loaded),2)
            self.assertEqual({x['response']['entries'][0]['state'] for x in loaded},{'normal','defect'})
            self.assertTrue(all(not x['human_truth'] for x in loaded))

    def test_partial_write_is_not_loaded_and_tampering_is_rejected(self):
        raw=json.dumps(self.body).encode()
        with tempfile.TemporaryDirectory() as folder:
            with patch('card_condition.observation_receipt.os.link',side_effect=OSError('synthetic disk failure')):
                with self.assertRaises(OSError):self.api.capture_receipt(self.packet,raw,self.context,folder)
            result=self.api.load_receipts(self.packet,folder)
            self.assertEqual(result['receipts'],[]);self.assertEqual(len(result['incomplete']),1)
            path=Path(folder)/result['incomplete'][0]
            self.assertEqual((path/'raw.bin').read_bytes(),raw)
            with self.assertRaises(FileExistsError):self.api.capture_receipt(self.packet,raw,self.context,folder)
            self.assertEqual((path/'raw.bin').read_bytes(),raw)
        for target in ('raw.bin','receipt.json'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as folder:
                receipt=self.api.capture_receipt(self.packet,raw,self.context,folder)
                path=Path(folder)/receipt['receipt_id']/target
                path.write_bytes(b'tampered synthetic data')
                with self.assertRaises(ValueError):self.api.load_receipts(self.packet,folder)
        with tempfile.TemporaryDirectory() as folder:
            receipt=self.api.capture_receipt(self.packet,raw,self.context,folder)
            receipt['display_verified']=False
            receipt['receipt_sha256']=self.api.receipt_digest(receipt)
            (Path(folder)/receipt['receipt_id']/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):self.api.load_receipts(self.packet,folder)
            with self.assertRaises(ValueError):self.api.capture_receipt(self.packet,raw,self.context,folder)

    def test_js_export_to_receipt_end_to_end_is_synthetic_and_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            page,raw_path=Path(folder)/'synthetic.html',Path(folder)/'response.json'
            page.write_text(render_page(self.packet,self.assets))
            r=subprocess.run(['node','tests/observation_response.test.cjs',str(page),str(raw_path)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            raw=raw_path.read_bytes();body=json.loads(raw)
            context=dict(self.context,session_id=body['session_id'])
            receipt=self.api.capture_receipt(self.packet,raw,context,Path(folder)/'ledger')
            self.assertEqual(receipt['status'],'synthetic_only')
            self.assertEqual(receipt['response']['entries'][0]['state'],'defect')
            self.assertEqual(receipt['response']['entries'][0]['note'],'  합성 메모\n ')
            self.assertEqual(receipt['collection_status'],'not_executable_pending_collection_contract_approval')
            self.assertFalse(receipt['eligible_for_collection'])
            self.assertEqual(self.api.load_receipts(self.packet,Path(folder)/'ledger')['receipts'][0],receipt)
