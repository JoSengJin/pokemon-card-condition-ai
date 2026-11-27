import copy
import unittest

from harness import route
from tests.test_harness_route_fixtures import FAIL, contract, decision, policy


def pair(d):
    return d["model"], d["effort"]


class EscalateTest(unittest.TestCase):
    def test_order_sonnet_medium_high_then_opus_high(self):
        d0 = decision("general_dev")
        d1 = route.escalate(d0, FAIL)
        d2 = route.escalate(d1, {"cause": "verification_failed"})
        self.assertEqual([pair(d0), pair(d1), pair(d2)],
                         [("sonnet", "medium"), ("sonnet", "high"), ("opus", "high")])
        self.assertTrue(d1["escalated"] and d2["escalated"])
        self.assertEqual([e["cause"] for e in d2["escalations"]], ["quality_gate_miss", "verification_failed"])
        self.assertEqual(d2["escalations"][1]["from"], {"model": "sonnet", "effort": "high"})
        self.assertEqual(d0["escalations"], [])  # 원본 불변
        self.assertEqual(pair(d0), ("sonnet", "medium"))
        for cause in ("unresolved_disagreement",):
            self.assertEqual(pair(route.escalate(decision("complex_algorithm"), {"cause": cause})), ("opus", "high"))

    def test_no_escalation_without_a_classified_escalating_cause(self):
        d0 = decision("general_dev")
        cases = {
            "원인 분류 없음": {},
            "원인 비어 있음": {"cause": ""},
            "원인 형식 오류": {"cause": 7},
            "데이터 부족": {"cause": "data_shortage"},
            "이미지 품질": {"cause": "image_quality"},
            "코드 오류": {"cause": "code_error"},
            "정책에 없는 원인": {"cause": "mystery"},
            "transient": {"cause": "quality_gate_miss", "failure_kind": "transient"},
            "dict 아님": "boom",
            "None": None,
        }
        for name, failure in cases.items():
            with self.subTest(name):
                got = route.escalate(d0, failure)
                self.assertFalse(got["escalated"])
                self.assertEqual(pair(got), ("sonnet", "medium"))
                self.assertEqual(got["escalations"], [])
                self.assertFalse(got["pending"])
        both = dict(policy(), escalate_causes=["quality_gate_miss", "data_shortage"])  # 금지 목록이 우선한다
        overlap = route.route(contract("general_dev"), [{"cause": "data_shortage"}], both)
        self.assertEqual((pair(overlap), overlap["escalated"]), (("sonnet", "medium"), False))
        self.assertIn("풀리지 않음", overlap["reason"])
        det = route.escalate(decision("deterministic"), FAIL)
        self.assertEqual((det["model"], det["escalated"]), (None, False))
        none_policy = route.route(contract("general_dev"), [], None)
        self.assertEqual(pair(route.escalate(none_policy, FAIL)), ("sonnet", "medium"))

    def test_xhigh_only_once_with_justification_and_budget(self):
        top = decision("label_disagreement")
        for name, kwargs in {"근거 없음": dict(budget_remaining=5),
                             "예산 없음": dict(xhigh_justified=True),
                             "예산 0": dict(xhigh_justified=True, budget_remaining=0),
                             "예산 bool": dict(xhigh_justified=True, budget_remaining=True),
                             "근거 truthy 아님": dict(xhigh_justified=1, budget_remaining=5)}.items():
            with self.subTest(name):
                got = route.escalate(top, FAIL, **kwargs)
                self.assertEqual(pair(got), ("opus", "high"))
                self.assertTrue(got["pending"])
                self.assertFalse(got["xhigh_used"])
        up = route.escalate(top, FAIL, xhigh_justified=True, budget_remaining=5)
        self.assertEqual(pair(up), ("opus", "xhigh"))
        self.assertTrue(up["xhigh_used"] and up["escalated"] and not up["pending"])
        again = route.escalate(up, FAIL, xhigh_justified=True, budget_remaining=5)  # 한 번만
        self.assertEqual(pair(again), ("opus", "xhigh"))
        self.assertTrue(again["pending"] and not again["escalated"])

    def test_pending_at_top_and_request_only_if_learning_value_high(self):
        top = decision("repeated_failure_analysis")
        quiet = route.escalate(top, FAIL)
        asked = route.escalate(top, FAIL, learning_value_high=True)
        self.assertEqual((quiet["pending"], quiet["request_user"]), (True, False))
        self.assertEqual((asked["pending"], asked["request_user"]), (True, True))
        self.assertEqual(pair(asked), ("opus", "high"))
        not_top = route.escalate(decision("general_dev"), FAIL, learning_value_high=True)
        self.assertEqual((not_top["pending"], not_top["request_user"]), (False, False))
        no_cause_at_top = route.escalate(top, {"cause": "data_shortage"}, learning_value_high=True)
        self.assertFalse(no_cause_at_top["pending"])  # 원인이 상향으로 풀리는 종류가 아니면 Pending 아님

    def test_history_is_replayed_by_route_with_same_rules(self):
        hist = [FAIL, {"cause": "data_shortage"}, {"cause": "verification_failed"}]
        got = route.route(contract("general_dev"), hist, policy())
        self.assertEqual(pair(got), ("opus", "high"))
        self.assertEqual(len(got["escalations"]), 2)
        self.assertEqual(pair(route.route(contract("general_dev"), [{"cause": "code_error"}] * 3, policy())),
                         ("sonnet", "medium"))
        past_top = route.route(contract("general_dev"), [FAIL, FAIL, FAIL], policy())
        self.assertTrue(past_top["pending"])
        x = [FAIL, FAIL, dict(FAIL, xhigh_justified=True)]
        self.assertEqual(pair(route.route(contract("general_dev"), x, policy(), {"budget_remaining": 3})),
                         ("opus", "xhigh"))
        self.assertEqual(pair(route.route(contract("general_dev"), x, policy())), ("opus", "high"))
        unjustified = route.route(contract("general_dev"), [FAIL] * 3, policy(), {"budget_remaining": 3})
        self.assertEqual((pair(unjustified), unjustified["pending"]), (("opus", "high"), True))
        self.assertEqual(pair(route.route(contract("general_dev"), None, policy())), ("sonnet", "medium"))

    def test_haiku_outside_chain_goes_to_first_chain_step_and_stale_support_is_cleared(self):
        d0 = decision("experiment_log_summary")
        self.assertIsNone(d0["level"])
        d0["applied"], d0["limitations"] = {"model": "haiku"}, ["old"]
        got = route.escalate(d0, FAIL)
        self.assertEqual(pair(got), ("sonnet", "medium"))
        self.assertNotIn("applied", got)
        self.assertNotIn("limitations", got)
        self.assertEqual(d0["applied"], {"model": "haiku"})  # 원본은 건드리지 않음

    def test_context_filter_passes_only_evidence_and_failure(self):
        context = {"image_sha": "ab", "label_json": {"x": 1}, "full_log": "x" * 1000, "secret": "k"}
        failure = {"cause": "unresolved_disagreement", "failure_kind": "deterministic", "error": "e",
                   "traceback": "lots", "api_key": "k"}
        before = copy.deepcopy((context, failure))
        got = route.context_for_escalation(context, ["image_sha", "label_json", "absent"], failure)
        self.assertEqual(got["evidence"], {"image_sha": "ab", "label_json": {"x": 1}})
        self.assertEqual(got["missing"], ["absent"])
        self.assertEqual(got["dropped"], ["full_log", "secret"])
        self.assertEqual(set(got["failure"]), {"cause", "failure_kind", "error"})
        self.assertEqual((context, failure), before)
        self.assertEqual(route.context_for_escalation(context, [], failure)["evidence"], {})
        with self.assertRaises(ValueError):
            route.context_for_escalation(context, "image_sha", failure)


if __name__ == "__main__":
    unittest.main()
