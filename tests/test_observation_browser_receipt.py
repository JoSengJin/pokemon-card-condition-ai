"""Consume exact strings extracted by the real browser tool, never recreate responses."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import unittest
from card_condition.observation_receipt import capture_receipt, load_receipts
from card_condition.observation_response import validate_response


class BrowserReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get("SYNTHETIC_BROWSER_EVIDENCE")
        if not root:
            raise unittest.SkipTest("real browser evidence required; run the documented browser session first")
        cls.root = Path(root)

    def test_exact_browser_utf8_raw_to_receipt(self):
        results = []
        for scenario in ("h", "a", "explicit"):
            with self.subTest(scenario=scenario):
                raw = (self.root/(scenario+".raw")).read_bytes()
                proof = json.loads((self.root/(scenario+".proof.json")).read_bytes())
                self.assertEqual(len(raw), proof["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), proof["sha256"])
                body = json.loads(raw)
                packet = json.loads((self.root/"pages"/(scenario+".packet.json")).read_bytes())
                self.assertTrue(validate_response(packet,body)["display_verified"])
                context = dict(data_origin="synthetic_fixture", source_type="synthetic_fixture", reviewer_id="browser-automation-fixture",
                               session_id=body["session_id"], received_at=datetime.now(timezone.utc).isoformat())
                ledger = self.root/"receipts"/scenario
                receipt = capture_receipt(packet,raw,context,ledger)
                self.assertEqual(receipt["status"],"synthetic_only")
                self.assertEqual(receipt["raw_sha256"],proof["sha256"])
                self.assertEqual((ledger/receipt["receipt_id"]/"raw.bin").read_bytes(),raw)
                self.assertEqual(receipt["response"],body)
                self.assertEqual(receipt["context"]["session_id"],body["session_id"])
                self.assertEqual(receipt["context"]["received_at"],context["received_at"])
                self.assertNotEqual(context["received_at"],body["observations"]["events"][-1]["at"])
                self.assertEqual(capture_receipt(packet,raw,context,ledger),receipt)
                other = capture_receipt(packet,raw,dict(context,reviewer_id="separate-fixture-context"),ledger)
                self.assertNotEqual(other["receipt_id"],receipt["receipt_id"])
                loaded = load_receipts(packet,ledger)
                self.assertFalse(loaded["incomplete"])
                self.assertIn(receipt,loaded["receipts"])
                self.assertTrue(all(not item["human_truth"] and not item["eligible_for_collection"] for item in loaded["receipts"]))
                self.assertEqual(receipt["collection_status"],"not_executable_pending_collection_contract_approval")
                if scenario in ("h","a"):
                    self.assertEqual(body["entries"][0]["note"],"  한글 합성 메모\n두 번째 줄\n ")
                    self.assertEqual(body["entries"][0]["state"],"unreviewed")
                    self.assertEqual({e["state"] for e in body["observations"]["events"] if e["event"]=="change"},
                                     {"unreviewed","normal","defect","unassessable"})
                    for key in ("viewport_css","image_css","device_pixel_ratio"):
                        self.assertIsNone(body["observations"]["profile"][key])
                results.append(dict(scenario=scenario,bytes=len(raw),sha256=proof["sha256"],receipt_id=receipt["receipt_id"],
                                    status=receipt["status"],received_at=context["received_at"],raw_equals=True))
        (self.root/"receipt-evidence.json").write_text(json.dumps(results,indent=2))

    def test_invalidated_browser_originals_never_become_verified(self):
        results = []
        for scenario in ("css-change","ref-change","src-change","detach"):
            with self.subTest(scenario=scenario):
                raw = (self.root/(scenario+".raw")).read_bytes()
                proof = json.loads((self.root/(scenario+".proof.json")).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(),proof["sha256"])
                self.assertEqual(len(raw),proof["bytes"])
                body = json.loads(raw)
                self.assertEqual(body["entries"][0]["state"],"defect" if scenario=="css-change" else "normal")
                self.assertEqual(body["entries"][0]["note"],"  보존 합성 메모\n ")
                self.assertIn("invalidate",[e["event"] for e in body["observations"]["events"]])
                packet = json.loads((self.root/"pages"/"h.packet.json").read_bytes())
                context = dict(data_origin="synthetic_fixture",source_type="synthetic_fixture",reviewer_id="browser-automation-fixture",
                               session_id=body["session_id"],received_at=datetime.now(timezone.utc).isoformat())
                ledger = self.root/"receipts"/scenario
                receipt = capture_receipt(packet,raw,context,ledger)
                self.assertIn(receipt["status"],("pending_observation","rejected"))
                self.assertFalse(receipt["display_verified"])
                self.assertEqual((ledger/receipt["receipt_id"]/"raw.bin").read_bytes(),raw)
                self.assertIn(receipt,load_receipts(packet,ledger)["receipts"])
                self.assertEqual(capture_receipt(packet,raw,context,ledger),receipt)
                results.append(dict(scenario=scenario,bytes=len(raw),sha256=proof["sha256"],status=receipt["status"],reasons=receipt["reasons"]))
        (self.root/"invalidated-receipt-evidence.json").write_text(json.dumps(results,indent=2))
