import importlib
import importlib.util
import json
import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from collection_runtime_fixture import candidate_fixture,access_fixture
from card_condition.observation_collection_receipt import capture_collection_receipt


class SealTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_seal"),"seal implementation missing")
        self.api=importlib.import_module("card_condition.observation_seal")
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.ledger=self.root/"receipts";self.output=self.root/"seals"
        self.p,_,self.c,self.body,self.context,self.assignment=candidate_fixture()
        self.record=capture_collection_receipt(self.p,self.c,json.dumps(self.body).encode(),self.context,self.assignment,self.ledger)
        self.policy,self.actors=access_fixture(self.c)

    def test_create_only_seal_preserves_unresolved_originals(self):
        seal=self.api.seal_receipts(self.c,[self.record["receipt_id"]],self.ledger,self.output)
        self.assertEqual(seal["truth_status"],"unresolved_synthetic");self.assertFalse(seal["human_truth"])
        self.assertEqual(self.api.load_seal(self.c,self.ledger,self.output,seal["seal_id"]),seal)
        with self.assertRaises(FileExistsError):self.api.seal_receipts(self.c,[self.record["receipt_id"]],self.ledger,self.output)
        (self.ledger/self.record["receipt_id"]/"raw.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError):self.api.load_seal(self.c,self.ledger,self.output,seal["seal_id"])

    def test_subset_traversal_symlink_and_partial_seal_rejected(self):
        with self.assertRaises(ValueError):self.api.seal_receipts(self.c,[],self.ledger,self.output)
        with self.assertRaises(ValueError):self.api.load_seal(self.c,self.ledger,self.output,"../escape")
        link=self.root/"link";link.symlink_to(self.ledger,target_is_directory=True)
        with self.assertRaises(ValueError):self.api.seal_receipts(self.c,[self.record["receipt_id"]],link,self.output)
        with patch("card_condition.observation_seal.os.link",side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):self.api.seal_receipts(self.c,[self.record["receipt_id"]],self.ledger,self.output)
        ids=[p.name for p in self.output.iterdir() if p.is_dir()]
        self.assertEqual(len(ids),1)
        with self.assertRaises(ValueError):self.api.load_seal(self.c,self.ledger,self.output,ids[0])

    def test_freeze_release_quarantine_and_event_integrity(self):
        seal=self.api.seal_receipts(self.c,[self.record["receipt_id"]],self.ledger,self.output)
        for actor,freeze in ((self.actors["custodian"],None),(self.actors["developer"],"fixture-freeze")):
            with self.assertRaises(ValueError):self.api.transition_seal(seal,self.output,"release",actor,self.policy,freeze)
        state=self.api.transition_seal(seal,self.output,"release",self.actors["custodian"],self.policy,"fixture-freeze")
        self.assertTrue(state["released"]);self.assertFalse(state["quarantined"])
        state=self.api.transition_seal(seal,self.output,"quarantine",self.actors["custodian"],self.policy)
        self.assertTrue(state["quarantined"])
        with self.assertRaises(ValueError):self.api.transition_seal(seal,self.output,"release",self.actors["custodian"],self.policy,"other")
        event=self.output/seal["seal_id"]/"events"/"00000000.json";data=json.loads(event.read_bytes());data["action"]="quarantine";event.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.api.seal_state(seal,self.output,self.policy)

    def test_receipt_lock_held_until_seal_publish(self):
        original=os.link
        def check_lock(source,target):
            with (self.ledger/".lock").open("a+b") as stream:
                with self.assertRaises(BlockingIOError):fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            original(source,target)
        with patch("card_condition.observation_seal.os.link",side_effect=check_lock):
            self.api.seal_receipts(self.c,[self.record["receipt_id"]],self.ledger,self.output)
