import os
import tempfile
import unittest

from harness import route
from tests.test_harness_route_fixtures import APPROVED, contract, decision, policy, write_policy


class RouteTableTest(unittest.TestCase):
    def test_all_twelve_approved_rows(self):
        self.assertEqual(set(policy()["task_types"]), set(APPROVED))
        self.assertEqual(len(APPROVED), 12)
        for task_type, (model, effort) in APPROVED.items():
            with self.subTest(task_type):
                got = decision(task_type)
                self.assertEqual((got["model"], got["effort"]), (model, effort))
                self.assertEqual(got["policy"], "routing-policy-v1")
                self.assertEqual(got["policy_version"], "routing-policy-v1")
                self.assertEqual(got["needs_llm"], model is not None)
                self.assertEqual([(s["model"], s["effort"]) for s in got["escalation_order"]],
                                 [("sonnet", "medium"), ("sonnet", "high"), ("opus", "high")])

    def test_needs_llm_false_never_gets_a_model(self):
        for task_type in APPROVED:
            with self.subTest(task_type):
                got = route.route(contract(task_type, needs_llm=False), [], policy())
                self.assertEqual((got["model"], got["effort"], got["needs_llm"]), (None, None, False))
                self.assertIn("호출 금지", got["reason"])
        conflict = route.route(contract("deterministic", needs_llm=True), [], policy())
        self.assertEqual((conflict["model"], conflict["needs_llm"]), (None, False))

    def test_missing_or_broken_policy_uses_default_and_policy_none(self):
        broken = {"version": "x", "task_types": {}}
        for pol in (None, {}, broken, "text"):
            with self.subTest(repr(pol)):
                got = route.route(contract("model_redesign"), [], pol)
                self.assertEqual((got["model"], got["effort"], got["policy"]), ("sonnet", "medium", "none"))
                self.assertIsNone(got["policy_version"])
                self.assertEqual(got["escalation_order"], [])
        self.assertIsNone(route.load_policy(os.path.join(tempfile.gettempdir(), "no-such-policy-file.json")))

    def test_unregistered_task_type_is_not_guessed(self):
        got = decision("brand_new_type")
        self.assertEqual((got["model"], got["effort"], got["policy"]), ("sonnet", "medium", "none"))
        self.assertEqual(got["policy_version"], "routing-policy-v1")
        self.assertIn("policy=none", got["reason"])
        self.assertEqual(len(got["escalation_order"]), 3)  # 정책 파일은 있으므로 상향 순서는 유지

    def test_json_change_alone_changes_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            def mutate(data):
                data["version"] = "routing-policy-test"
                data["task_types"]["general_dev"] = {"model": "opus", "effort": "high"}
                data["task_types"]["experiment_log_summary"] = {"llm": False}
                data["escalation_order"] = [{"model": "opus", "effort": "high"}]
            changed = write_policy(os.path.join(tmp, "p.json"), mutate)
            got = route.route(contract("general_dev"), [], changed)
            self.assertEqual((got["model"], got["effort"], got["policy"]), ("opus", "high", "routing-policy-test"))
            summary = route.route(contract("experiment_log_summary"), [], changed)
            self.assertEqual((summary["model"], summary["needs_llm"]), (None, False))
            self.assertEqual(decision("general_dev")["model"], "sonnet")  # 원본 정책은 그대로

    def test_inputs_are_recorded_and_bad_contract_rejected(self):
        got = route.route(contract("silver_labeling", needs_vision=True, risk="high", escalation_level=1), [],
                          policy(), {"context_size": 1234, "budget_remaining": 5})
        self.assertEqual((got["needs_vision"], got["risk"], got["context_size"], got["budget_remaining"]),
                         (True, "high", 1234, 5))
        self.assertEqual(got["contract_escalation_level"], 1)
        for bad in (None, {}, {"task_type": "general_dev"}, {"task_type": "general_dev", "needs_llm": "yes"}):
            with self.subTest(repr(bad)), self.assertRaises(ValueError):
                route.route(bad, [], policy())

    def test_invalid_policy_row_makes_whole_policy_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed = write_policy(os.path.join(tmp, "p.json"),
                                   lambda d: d["task_types"].update(general_dev={"model": "sonnet"}))
            got = route.route(contract("complex_algorithm"), [], changed)
            self.assertEqual((got["model"], got["effort"], got["policy"]), ("sonnet", "medium", "none"))


if __name__ == "__main__":
    unittest.main()
