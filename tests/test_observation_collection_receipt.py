import copy
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from collection_runtime_fixture import candidate_fixture


class CollectionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_collection_receipt"),"candidate receipt missing")
        self.api=importlib.import_module("card_condition.observation_collection_receipt")
        self.p,self.a,self.c,self.body,self.context,self.assignment=candidate_fixture()

    def test_raw_custody_idempotency_and_context_separation(self):
        self.body["base_response"]["entries"][0]["note"]="  합성 원문\n "
        raw=(" \n"+json.dumps(self.body,ensure_ascii=False)+"\n ").encode()
        with tempfile.TemporaryDirectory() as root:
            r=self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)
            self.assertEqual(r["status"],"synthetic_only");self.assertFalse(r["human_truth"]);self.assertFalse(r["eligible_for_collection"])
            self.assertEqual((Path(root)/r["receipt_id"]/"raw.bin").read_bytes(),raw)
            self.assertEqual(self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root),r)
            another=self.api.capture_collection_receipt(self.p,self.c,raw,dict(self.context,received_at="2026-11-18T00:00:02Z"),self.assignment,root)
            self.assertNotEqual(r["receipt_id"],another["receipt_id"])
            self.assertEqual(len(self.api.load_collection_receipts(self.p,self.c,self.assignment,root)["receipts"]),2)

    def test_missing_assignment_unknown_actor_bad_logs_and_raw_rejected(self):
        for scenario in ("unknown","missing","viewport","zoom","session","duplicate"):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as root:
                b=copy.deepcopy(self.body);ctx=dict(self.context);assignment=self.assignment
                if scenario=="unknown":b["claimed_actor"]="unknown"
                if scenario=="missing":ctx["assignment_id"]=None;assignment=None
                if scenario=="viewport":b["viewport_events"][0]["layout"]=[0,600]
                if scenario=="zoom":b["zoom_events"][0]["source_matches"]=False
                if scenario=="session":ctx["session_id"]="wrong"
                raw=b'{"x":1,"x":1}' if scenario=="duplicate" else json.dumps(b).encode()
                r=self.api.capture_collection_receipt(self.p,self.c,raw,ctx,assignment,root)
                self.assertIn(r["status"],("pending_provenance","pending_observation","rejected"))
                self.assertEqual((Path(root)/r["receipt_id"]/"raw.bin").read_bytes(),raw)
                self.assertEqual(self.api.load_collection_receipts(self.p,self.c,assignment,root)["receipts"],[r])
        with tempfile.TemporaryDirectory() as root:
            forbidden=Path(root)/"forbidden"
            with self.assertRaises(ValueError):self.api.capture_collection_receipt(self.p,self.c,b"{}",dict(self.context,source_type="human"),self.assignment,forbidden)
            self.assertFalse(forbidden.exists())

    def test_manifest_rehash_and_partial_write_cannot_promote(self):
        raw=json.dumps(self.body).encode()
        for scenario in ("status","bool","rejection"):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as root:
                b=copy.deepcopy(self.body)
                if scenario=="status":b["claimed_actor"]="ai"
                r=self.api.capture_collection_receipt(self.p,self.c,json.dumps(b).encode(),self.context,self.assignment,root)
                if scenario=="status":r["status"]="synthetic_only"
                if scenario=="bool":r["summary"]["display_verified"]=1
                if scenario=="rejection":r.update(status="rejected",response=None)
                r["receipt_sha256"]=self.api.collection_digest({k:v for k,v in r.items() if k!="receipt_sha256"})
                (Path(root)/r["receipt_id"]/"receipt.json").write_text(json.dumps(r))
                with self.assertRaises(ValueError):self.api.load_collection_receipts(self.p,self.c,self.assignment,root)
                with self.assertRaises(ValueError):self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)
        with tempfile.TemporaryDirectory() as root:
            with patch("card_condition.observation_receipt.os.link",side_effect=OSError("synthetic storage fail")):
                with self.assertRaises(OSError):self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)
            result=self.api.load_collection_receipts(self.p,self.c,self.assignment,root)
            self.assertEqual(result["receipts"],[]);self.assertEqual(len(result["incomplete"]),1)
            with self.assertRaises(FileExistsError):self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)

    def test_rehashed_forbidden_source_cannot_enter_through_load(self):
        with tempfile.TemporaryDirectory() as root:
            raw=json.dumps(self.body).encode()
            r=self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)
            old=Path(root)/r["receipt_id"]
            r["context"]["source_type"]="human"
            r.update(response=None,summary=dict(missing_entry_ids=[],display_verified=False,assignment_matched=False),status="rejected",reasons=["actual human collection is not authorized","collection_not_authorized"])
            r["receipt_id"]=self.api.collection_digest({k:r[k] for k in ("packet_id","contract_id","raw_sha256","context")})
            r["receipt_sha256"]=self.api.collection_digest({k:v for k,v in r.items() if k!="receipt_sha256"})
            new=Path(root)/r["receipt_id"];old.rename(new);(new/"receipt.json").write_text(json.dumps(r))
            with self.assertRaises(ValueError):self.api.load_collection_receipts(self.p,self.c,self.assignment,root)
            with self.assertRaises(ValueError):self.api.capture_collection_receipt(self.p,self.c,raw,self.context,self.assignment,root)
