"""Synthetic flow and exact real-browser exports; never actual human collection."""
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from collection_runtime_fixture import candidate_fixture,access_fixture
from card_condition.observation_collection_receipt import capture_collection_receipt,load_collection_receipts
from card_condition.observation_seal import seal_receipts,load_seal,transition_seal
from card_condition.observation_access import authorize,aggregate_projection


class CollectionFlowTests(unittest.TestCase):
    def test_fixture_receipt_load_seal_release_projection_and_quarantine(self):
        p,_,c,body,context,assignment=candidate_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=json.dumps(body,ensure_ascii=False).encode()
            record=capture_collection_receipt(p,c,raw,context,assignment,root/"receipts")
            records=load_collection_receipts(p,c,assignment,root/"receipts")["receipts"]
            seal=seal_receipts(c,[r["receipt_id"] for r in records],root/"receipts",root/"seals")
            self.assertEqual(load_seal(c,root/"receipts",root/"seals",seal["seal_id"]),seal)
            policy,actors=access_fixture(c)
            state=transition_seal(seal,root/"seals","release",actors["custodian"],policy,"synthetic-freeze-only")
            result=authorize(actors["evaluator"],"read_evaluation",state,policy)
            self.assertTrue(result["allowed"]);self.assertFalse(result["actual_access_verified"])
            self.assertEqual(set(aggregate_projection(actors["developer"],state,policy,records)),{"receipt_count","status_counts","quarantined"})
            state=transition_seal(seal,root/"seals","quarantine",actors["custodian"],policy)
            self.assertFalse(authorize(actors["evaluator"],"read_evaluation",state,policy)["allowed"])
            self.assertFalse(record["human_truth"]);self.assertFalse(seal["eligible_for_collection"])

    def test_new_javascript_is_in_package_data(self):
        metadata=tomllib.loads(Path("pyproject.toml").read_text())
        files=metadata["tool"]["setuptools"]["package-data"]["card_condition"]
        for name in ("observation_viewport.js","observation_zoom.js","observation_collection_response.js"):
            with self.subTest(name=name):self.assertIn(name,files);self.assertTrue(Path("card_condition",name).is_file())

    def test_actual_browser_raw_bytes_to_unresolved_seal(self):
        env=os.environ.get("COLLECTION_BROWSER_EVIDENCE")
        if not env:self.skipTest("requires fresh actual-browser synthetic exports")
        root=Path(env);results=[]
        for name in ("h","a","fractional","css-restored"):
            with self.subTest(name=name):
                raw=(root/(name+".raw")).read_bytes();proof=json.loads((root/(name+".proof.json")).read_bytes())
                self.assertEqual(hashlib.sha256(raw).hexdigest(),proof["sha256"]);self.assertEqual(len(raw),proof["bytes"])
                packet=json.loads((root/"pages"/"h.packet.json" if name in ("css-restored","fractional") else root/"pages"/(name+".packet.json")).read_bytes())
                contract=json.loads((root/"pages"/"h.contract.json" if name in ("css-restored","fractional") else root/"pages"/(name+".contract.json")).read_bytes())
                body=json.loads(raw);session=body["base_response"]["session_id"]
                assignment=dict(assignment_id=contract["assignment_ref"],contract_id=contract["contract_id"],session_id=session,rater_id="fixture-browser-actor",observation_mode=packet["observation_mode"],evidence_origin="synthetic_fixture")
                now=datetime.now(timezone.utc)
                context=dict(source_type="synthetic_fixture",assignment_id=assignment["assignment_id"],contract_id=contract["contract_id"],session_id=session,rater_id=assignment["rater_id"],received_at=now.isoformat())
                ledger=root/"flow-receipts"/name;output=root/"flow-seals"/name
                receipt=capture_collection_receipt(packet,contract,raw,context,assignment,ledger)
                self.assertEqual((ledger/receipt["receipt_id"]/"raw.bin").read_bytes(),raw)
                self.assertEqual(receipt["context"],context)
                self.assertNotEqual(receipt["context"]["received_at"],body["base_response"]["observations"]["events"][-1]["at"])
                self.assertEqual(capture_collection_receipt(packet,contract,raw,context,assignment,ledger),receipt)
                other=capture_collection_receipt(packet,contract,raw,dict(context,received_at=(now+timedelta(seconds=1)).isoformat()),assignment,ledger)
                self.assertNotEqual(receipt["receipt_id"],other["receipt_id"])
                records=load_collection_receipts(packet,contract,assignment,ledger)["receipts"]
                seal=seal_receipts(contract,[r["receipt_id"] for r in records],ledger,output)
                self.assertEqual(load_seal(contract,ledger,output,seal["seal_id"]),seal)
                self.assertFalse(receipt["human_truth"]);self.assertFalse(receipt["eligible_for_collection"])
                self.assertEqual(seal["truth_status"],"unresolved_synthetic")
                if name in ("h","a"):
                    self.assertEqual(receipt["status"],"synthetic_only")
                    self.assertEqual(body["base_response"]["entries"][0]["note"],"  합성 휴대폰 메모\n두 번째 줄\n ")
                    self.assertEqual({e["state"] for e in body["base_response"]["observations"]["events"] if e["event"]=="change"},{"normal","defect","unassessable","unreviewed"})
                    self.assertIsNone(contract["display_profile"]["viewport_css"]);self.assertIsNone(contract["display_profile"]["device_pixel_ratio"])
                    if name=="h":self.assertEqual(body["zoom_events"][-1]["scale"],2)
                    else:self.assertEqual(body["zoom_events"],[])
                elif name=="fractional":
                    self.assertEqual(receipt["status"],"synthetic_only");self.assertEqual(body["zoom_events"][-1]["scale"],1.1)
                else:
                    self.assertFalse(receipt["summary"]["display_verified"]);self.assertNotEqual(receipt["status"],"synthetic_only")
                policy,actors=access_fixture(contract)
                if name!="css-restored":
                    state=transition_seal(seal,output,"release",actors["custodian"],policy,"synthetic-freeze-only")
                    permission=authorize(actors["evaluator"],"read_evaluation",state,policy)
                    self.assertTrue(permission["allowed"]);self.assertFalse(permission["actual_access_verified"])
                    projection=aggregate_projection(actors["developer"],state,policy,records)
                    self.assertEqual(set(projection),{"receipt_count","status_counts","quarantined"})
                state=transition_seal(seal,output,"quarantine",actors["custodian"],policy)
                self.assertFalse(authorize(actors["evaluator"],"read_evaluation",state,policy)["allowed"])
                results.append(dict(scenario=name,bytes=len(raw),sha256=receipt["raw_sha256"],receipt_id=receipt["receipt_id"],status=receipt["status"],seal_id=seal["seal_id"],raw_equal=True,received_at=context["received_at"],mock_quarantine_verified=True))
        (root/"flow-evidence.json").write_text(json.dumps(results,indent=2))
