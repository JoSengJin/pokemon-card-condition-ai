"""Silver 정책: 오류율 상한 경계, 확인용 묶음 사용 기록, 철회·재승인, 등급 전이, 미리 채운 입력 거절. 합성 시험이다."""
import unittest

from harness import silver_policy, silver_store
from tests.test_harness_champion_support import make_root, read_events
from tests.test_harness_silver_support import SCOPE, approve

CAL = {"batch_id": "cal-1", "role": "confirm"}


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)

    def try_approve(self, n, errors, scope=SCOPE, cap=0.10, batch="cal-1"):
        return silver_policy.approve(self.root, 1.0, scope, dict(CAL, batch_id=batch, n=n, errors=errors), cap=cap, min_n=50)

    def test_error_rate_exactly_at_cap_is_approved_and_anything_above_is_refused(self):
        self.assertTrue(self.try_approve(50, 5)["ok"])  # 정확히 10%
        for n, errors in ((50, 6), (60, 7), (100, 11), (80, 9)):
            other = dict(SCOPE, stratum="back%d" % n)
            res = self.try_approve(n, errors, other)
            self.assertEqual((False, "error_rate_over_cap"), (res["ok"], res["reason"]), (n, errors))
        self.assertTrue(self.try_approve(60, 6, dict(SCOPE, stratum="s60"))["ok"])  # 6/60 = 10%
        self.assertTrue(self.try_approve(30 * 4, 12, dict(SCOPE, stratum="s120"))["ok"])  # 부동소수점 오차 없이 10%
        with self.assertRaises(silver_policy.PolicyError):  # 상한을 호출자가 느슨하게 못 한다
            self.try_approve(50, 0, dict(SCOPE, stratum="loose"), cap=0.11)
        with self.assertRaises(silver_policy.PolicyError):
            self.try_approve(50, 0, dict(SCOPE, stratum="zero"), cap=0)

    def test_tune_batch_cannot_approve_and_every_confirm_use_is_recorded(self):
        tune = silver_policy.approve(self.root, 1.0, SCOPE, {"batch_id": "cal-tune", "role": "tune", "n": 100, "errors": 0}, cap=0.1, min_n=50)
        self.assertEqual((False, "tune_batch_not_allowed"), (tune["ok"], tune["reason"]))
        self.assertEqual([], read_events(self.root, silver_store.STORE))  # 조정용 묶음은 아무 것도 기록하지 않는다
        self.assertEqual("too_few_regions", self.try_approve(40, 0)["reason"])
        self.assertEqual(2, self.try_approve(100, 30)["confirm_uses"])  # 같은 확인용 묶음 두 번째 사용(거절돼도 센다)
        ok = self.try_approve(100, 5)
        self.assertEqual((True, 3), (ok["ok"], ok["confirm_uses"]))
        uses = [e for e in read_events(self.root, silver_store.STORE) if e["event"] == "calibration_used"]
        self.assertEqual(3, len(uses))
        self.assertEqual({"cal-1"}, {e["data"]["batch_id"] for e in uses})
        self.assertEqual("already_approved", self.try_approve(100, 5)["reason"])

    def test_withdraw_is_idempotent_and_reapproval_is_a_new_version(self):
        first = approve(self.root)
        self.assertEqual({"ok": True, "already": False}, silver_policy.withdraw(self.root, 2.0, first, "test"))
        self.assertEqual({"ok": True, "already": True}, silver_policy.withdraw(self.root, 3.0, first, "again"))
        self.assertEqual(1, len([e for e in read_events(self.root, silver_store.STORE) if e["event"] == "policy_withdrawn"]))
        second = approve(self.root, batch="cal-2")
        self.assertNotEqual(first, second)
        self.assertTrue(second.endswith("-v2"))
        state = silver_policy.fold(silver_store.load(self.root))["policies"]
        self.assertEqual(("withdrawn", "approved"), (state[first]["status"], state[second]["status"]))
        with self.assertRaises(silver_policy.PolicyError):
            silver_policy.withdraw(self.root, 4.0, "no-such-policy", "x")

    def test_grade_transition_never_makes_an_ai_label_gold(self):
        for current in (None, "Pending", "Silver"):
            with self.assertRaises(silver_policy.PolicyError, msg=current):
                silver_policy.grade_transition(current, "Gold", "agent")  # AI 라벨은 어떤 경로로도 Gold가 아니다
        with self.assertRaises(silver_policy.PolicyError):
            silver_policy.grade_transition("Silver", "Gold", "human")  # Silver→Gold는 사람이 해도 금지
        with self.assertRaises(silver_policy.PolicyError):
            silver_policy.grade_transition("Gold", "Silver", "human")
        with self.assertRaises(silver_policy.PolicyError):
            silver_policy.grade_transition("Gold", "Pending", "human")
        self.assertEqual("Gold", silver_policy.grade_transition(None, "Gold", "human"))
        self.assertEqual("Pending", silver_policy.grade_transition(None, "Pending", "agent"))
        self.assertEqual("Silver", silver_policy.grade_transition("Pending", "Silver", "agent"))
        self.assertEqual("Pending", silver_policy.grade_transition("Silver", "Pending", "agent"))

    def test_prefilled_inputs_are_refused_at_any_depth(self):
        clean = {"screen_id": "s1", "zones": [{"zone": "z1", "prediction": None, "choice": ""}, {"zone": "z2"}]}
        self.assertIs(clean, silver_policy.reject_prefilled(clean))
        for dirty in ({"zones": [{"zone": "z1", "prediction": "normal"}]}, {"a": {"b": [{"prefilled": True}]}},
                      {"zones": [{"zone": "z1", "model_score": 0.7}]}, {"expected_label": "defect"}):
            with self.assertRaises(silver_policy.PolicyError, msg=dirty):
                silver_policy.reject_prefilled(dirty)


if __name__ == "__main__":
    unittest.main()
