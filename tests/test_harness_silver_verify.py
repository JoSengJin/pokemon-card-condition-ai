"""불확실 후보의 교차 검증: 주입된 독립 검증·결정론 CV 함수가 모두 같은 확정 값일 때만 Silver, 그 밖은 Pending. 합성 함수이며 정확도 근거가 아니다."""
import unittest

from harness import silver_gate
from tests.test_harness_champion_support import make_root
from tests.test_harness_silver_support import approve, cands, judge, stored_labels
from tests.test_harness_silver_verifiers import answer, boom, recorder


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = approve(self.root)

    def test_only_unanimous_confirmed_values_equal_to_the_agent_label_resolve_to_silver(self):
        cases = [("normal", "normal", "silver", "verifiers_agree"), ("normal", "defect", "pending", "verifier_disagreement"),
                 (None, "normal", "pending", "verifier_unknown"), ("normal", "maybe", "pending", "verifier_invalid_result"),
                 ("defect", "defect", "pending", "verifier_differs_from_agent")]
        for i, (ind, cv, kind, reason) in enumerate(cases):
            res = judge(self.root, "c%d" % i, self.policy, cands(1, prefix="x%d" % i, uncertain=True),
                        verifiers={"independent": answer(ind), "cv": answer(cv)})
            self.assertEqual(1, len(res[kind]), (ind, cv))
            label = [d for d in stored_labels(self.root) if d["batch_id"] == "c%d" % i][0]
            self.assertEqual(kind.capitalize(), label["grade"])
            if kind == "pending":
                self.assertEqual(reason, label["reason"])
            self.assertEqual("label_value" in label, kind == "silver")  # Pending은 값을 저장하지 않는다
        silver = [d for d in stored_labels(self.root) if d["grade"] == "Silver"][0]
        self.assertEqual({"independent": "normal", "cv": "normal"}, silver["verification"]["cross_verified"])
        self.assertEqual("policy_calibration", silver["verification"]["basis"])  # 합의가 아니라 정책 보정이 근거다
        self.assertEqual(1, len(silver_gate.trainable_labels(self.root)))

    def test_one_verifier_is_enough_errors_and_missing_verifiers_are_pending_and_the_agent_label_is_hidden(self):
        seen = []
        only = judge(self.root, "d1", self.policy, cands(1, prefix="y", uncertain=True), verifiers={"independent": recorder(seen, "normal")})
        self.assertEqual(1, len(only["silver"]))
        errored = judge(self.root, "d2", self.policy, cands(1, prefix="z", uncertain=True), verifiers={"cv": boom})
        none_given = judge(self.root, "d3", self.policy, cands(1, prefix="w", uncertain=True))
        self.assertEqual((1, 1), (len(errored["pending"]), len(none_given["pending"])))
        reasons = {d["batch_id"]: d["reason"] for d in stored_labels(self.root) if d["grade"] == "Pending"}
        self.assertEqual(("verifier_error:cv:RuntimeError", "no_verifier"), (reasons["d2"], reasons["d3"]))
        self.assertEqual([{"image_sha": "y000", "zone": "z1", "defect_type": "corner", "stratum": "front"}], seen)  # label_value 없음
        with self.assertRaises(silver_gate.GateError):  # 이 경로는 에이전트 라벨만 받는다(사람 라벨·알 수 없는 값은 오류)
            judge(self.root, "d4", self.policy, [dict(cands(1, prefix="h")[0], created_by="human")])
        with self.assertRaises(silver_gate.GateError):
            judge(self.root, "d5", self.policy, cands(1, prefix="v"), verifiers={"oracle": answer("normal")})
        with self.assertRaises(silver_gate.GateError):  # 확실·불확실 표시가 없는 후보는 추정하지 않고 거절한다
            judge(self.root, "d6", self.policy, [{k: v for k, v in cands(1, prefix="t")[0].items() if k != "uncertain"}])


if __name__ == "__main__":
    unittest.main()
