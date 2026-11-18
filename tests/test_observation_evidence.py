import hashlib
import json
import unittest
from readiness_fixture import full, record
from test_observation_collection_contract import contract_fixture
from card_condition.observation_evidence import raw_matches, r1_status, validate_r1_record

FALSE_FLAGS = dict(r1_complete=False, collection_ready=False, human_truth=False, eligible_for_collection=False)


class EvidenceTests(unittest.TestCase):
    def assertFlags(self, result):
        for key, value in FALSE_FLAGS.items():
            self.assertIs(result[key], value)

    def test_no_real_phone_evidence_blocks_r1(self):
        c = contract_fixture(complete=True)
        for kind in ("synthetic_mock", "desktop_browser"):
            result = r1_status(full(kind), c)
            self.assertFlags(result)
            self.assertEqual(result["status"], "blocked_unverified")
            self.assertTrue(all(v == "desktop_or_mock_only" for v in result["scenarios"].values()))
        self.assertTrue(all(v == "unverified" for v in r1_status([], c)["scenarios"].values()))

    def test_null_observation_needs_reason_and_never_passes(self):
        with self.assertRaises(ValueError):
            validate_r1_record(record("keyboard", null_reason=None))
        result = r1_status([record("keyboard", "real_phone")], contract_fixture(complete=True))
        self.assertEqual(result["scenarios"]["keyboard"], "observed_null")
        self.assertIn("scenario.keyboard:observed_null", result["gaps"])
        self.assertFlags(result)

    def test_app_zoom_log_is_not_external_zoom(self):
        with self.assertRaises(ValueError):
            validate_r1_record(record("h_zoom_external", "real_phone", {"scale": 2}, source="app_zoom_log"))
        records = [record("h_zoom_app_log", "real_phone", {"scale": 2}, source="app_zoom_log")]
        result = r1_status(records, contract_fixture(complete=True))
        self.assertEqual(result["scenarios"]["h_zoom_external"], "unverified")
        self.assertEqual(result["scenarios"]["h_zoom_app_log"], "real_phone")

    def test_real_or_human_data_is_not_reclassified_as_synthetic(self):
        for bad in (dict(data_origin="real_photo"), dict(data_origin="human_input")):
            with self.assertRaises(ValueError):
                validate_r1_record(record("touch", "real_phone", {"v": 1}, **bad))
        with self.assertRaises(ValueError):
            validate_r1_record(record("touch", "real_phone", {"source_type": "human"}))

    def test_undecided_profile_blocks_even_with_full_real_phone_evidence(self):
        result = r1_status(full("real_phone"), contract_fixture())
        self.assertFlags(result)
        self.assertEqual(result["status"], "blocked_unverified")
        self.assertIn("display_profile.viewport_css", result["gaps"])
        ready = r1_status(full("real_phone"), contract_fixture(complete=True))
        self.assertEqual((ready["status"], ready["gaps"]), ("evidence_ready_for_review", []))
        self.assertFlags(ready)  # never a completion claim

    def test_raw_bytes_compared_exactly(self):
        raw = (" " + json.dumps({"memo": " 가나다\n"}, ensure_ascii=False) + "\n").encode("utf-8")
        sha = hashlib.sha256(raw).hexdigest()
        self.assertTrue(raw_matches(raw, sha))
        self.assertFalse(raw_matches(raw.strip(), sha))
        self.assertFalse(raw_matches(raw.decode("utf-8"), sha))
        self.assertFalse(raw_matches(json.dumps(json.loads(raw)).encode(), sha))
        self.assertFalse(raw_matches(raw[:-1] + b"\x00", sha))
