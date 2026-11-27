import os
import tempfile
import unittest

from harness import ledger, route
from tests.test_harness_route_fixtures import FAIL, HELP, decision


def read_lines(root):
    import json
    with open(os.path.join(root, "ledger.jsonl"), encoding="utf-8") as handle:
        return [json.loads(x) for x in handle]


class RecordTest(unittest.TestCase):
    def test_all_required_fields_with_explicit_nulls(self):
        with tempfile.TemporaryDirectory() as root:
            d = decision("general_dev")
            entry = route.record_decision(root, d, None, {"ts": 5.0})
            data = entry["data"]
            self.assertEqual(entry["event"], "route_decision")
            self.assertEqual((data["policy_version"], data["policy"], data["task_type"]),
                             ("routing-policy-v1", "routing-policy-v1", "general_dev"))
            self.assertEqual(data["requested"], {"model": "sonnet", "effort": "medium"})
            for key in ("applied", "limitations", "task_key", "tokens", "duration_s", "quality_gate", "rework"):
                self.assertIn(key, data)
                self.assertIsNone(data[key], key)  # 없으면 null로 명시
            self.assertEqual((data["escalations"], data["pending"]), ([], False))
            self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])

    def test_applied_requested_escalation_and_usage_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            support = route.probe_cli_support(run=lambda argv: (0, HELP))
            d = route.with_support(route.escalate(decision("general_dev"), FAIL), support)
            extras = {"task_key": "ab" * 32, "tokens": {"input": 10, "output": 3}, "duration_s": 1.5,
                      "quality_gate": "fail", "rework": True, "ts": 9.0}
            data = route.record_decision(root, d, d["applied"], extras)["data"]
            self.assertEqual(data["requested"], {"model": "sonnet", "effort": "high"})
            self.assertEqual(data["applied"], {"model": "sonnet", "effort": "high", "verified": False})
            self.assertEqual(data["escalations"][0]["cause"], "quality_gate_miss")
            self.assertTrue(data["limitations"][0].startswith("actual_application_unverified"))
            self.assertEqual({k: data[k] for k in extras if k != "ts"}, {k: v for k, v in extras.items() if k != "ts"})

    def test_unknown_extras_rejected_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                route.record_decision(root, decision(), None, {"token": 1})
            self.assertFalse(os.path.exists(os.path.join(root, "ledger.jsonl")))

    def test_appends_to_existing_chain_without_breaking_it(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "ledger.jsonl")
            ledger.append(path, 1.0, "enqueued", {"task_key": "k"})
            route.record_decision(root, decision("silver_labeling"), None, {"ts": 2.0})
            route.record_decision(root, decision("general_dev"), None, {"ts": 3.0})
            self.assertEqual(ledger.verify(path), [])
            self.assertEqual([x["event"] for x in read_lines(root)], ["enqueued", "route_decision", "route_decision"])

    def test_pending_and_xhigh_state_are_in_the_record(self):
        with tempfile.TemporaryDirectory() as root:
            top = route.escalate(decision("label_disagreement"), FAIL, learning_value_high=True)
            data = route.record_decision(root, top, None, {"ts": 1.0})["data"]
            self.assertTrue(data["pending"])
            self.assertEqual(data["requested"], {"model": "opus", "effort": "high"})

    def test_no_llm_decision_records_null_request(self):
        with tempfile.TemporaryDirectory() as root:
            d = route.route({"task_type": "deterministic", "needs_llm": False}, [], route.load_policy())
            data = route.record_decision(root, d, d.get("applied"), {"ts": 1.0})["data"]
            self.assertEqual((data["requested"], data["needs_llm"]), ({"model": None, "effort": None}, False))

    def test_corrupt_ledger_tail_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "ledger.jsonl")
            route.record_decision(root, decision(), None, {"ts": 1.0})
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("garbage\n")
            with self.assertRaises(ledger.LedgerError):
                route.record_decision(root, decision(), None, {"ts": 2.0})


if __name__ == "__main__":
    unittest.main()
