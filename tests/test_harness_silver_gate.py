"""Silver 품질 관문: 봉인·보정 거절, 정책 범위, 교차 검증과 Pending, 사람 Gold 대조, 묶음 규칙. 합성 후보·주입 함수이며 라벨 품질 근거가 아니다."""
import unittest

from harness import active_learning, audit, silver_gate, silver_policy, silver_store, withdrawal
from tests.test_harness_champion_support import make_root, read_events
from tests.test_harness_silver_support import FAST, SCOPE, approve, cands, judge, stored_labels
from tests.test_harness_silver_verifiers import answer


class GateTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = approve(self.root)

    def test_sealed_and_calibration_images_get_no_silver_even_when_verifiers_agree(self):
        protected = {"sealed": {"image_shas": ["img000"], "group_ids": ["grp001"]},
                     "calibration": {"image_shas": ["img002"], "group_ids": ["grp003"]}}
        res = judge(self.root, "b1", self.policy, cands(6), protected=protected)
        self.assertEqual(["sealed_image", "sealed_image", "calibration_image", "calibration_image"], [r["reason"] for r in res["rejected"]])
        self.assertEqual({"img004", "img005"}, {d["image_sha"] for d in stored_labels(self.root)})
        agree = {"independent": answer("normal"), "cv": answer("normal")}  # 합의가 있어도 봉인은 통과하지 못한다
        res = judge(self.root, "b2", self.policy, cands(1, uncertain=True), verifiers=agree, protected=protected)
        self.assertEqual((0, ["sealed_image"]), (len(res["silver"]), [r["reason"] for r in res["rejected"]]))
        with self.assertRaises(active_learning.ActiveLearningError):  # 봉인·보정 목록이 없으면 판정하지 않는다(조용한 통과 금지)
            judge(self.root, "b3", self.policy, cands(1), protected={"sealed": {"image_shas": [], "group_ids": []}})

    def test_out_of_scope_and_inactive_policy_are_refused_even_with_unanimous_agreement(self):
        agree = {"independent": answer("defect"), "cv": answer("defect")}
        other = cands(3, scope=dict(SCOPE, label_value="defect"), uncertain=True)
        res = judge(self.root, "b1", self.policy, other, verifiers=agree)
        self.assertEqual((0, ["out_of_policy_scope"] * 3), (len(res["silver"]), [r["reason"] for r in res["rejected"]]))
        self.assertEqual([], stored_labels(self.root))
        withdrawal.withdraw(self.root, 3.0, self.policy, "test")  # 목록 밖 사유 = unclear(보류)
        self.assertEqual({"ok": False, "reason": "policy_inactive"}, judge(self.root, "b2", self.policy, cands(2)))
        with self.assertRaises(silver_gate.GateError):
            judge(self.root, "b3", "pol-unknown", cands(1))

    def test_silver_carries_provenance_pending_carries_no_value_and_scope_needs_no_new_approval(self):
        for n in range(3):  # 승인된 범위 안의 여러 묶음은 새 승인 없이 계속 Silver가 된다
            self.assertEqual(4, len(judge(self.root, "b%d" % n, self.policy, cands(4, prefix="p%d" % n))["silver"]))
        unjudgeable = [dict(cands(1, prefix="u")[0], label_value=None)]
        self.assertEqual(1, len(judge(self.root, "b9", self.policy, unjudgeable)["pending"]))
        events = [e["event"] for e in read_events(self.root, silver_store.STORE)]
        self.assertEqual((1, 1), (events.count("policy_approved"), events.count("calibration_used")))
        silver = [d for d in stored_labels(self.root) if d["grade"] == "Silver"]
        for key, value in (("created_by", "agent"), ("criteria_version", "c1"), ("model_version", "m1"), ("policy_id", self.policy),
                           ("label_value", "normal")):
            self.assertEqual({value}, {d[key] for d in silver}, key)
        self.assertEqual({"policy_calibration"}, {d["verification"]["basis"] for d in silver})
        pending = [d for d in stored_labels(self.root) if d["grade"] == "Pending"]
        self.assertEqual(("agent_unjudgeable", False), (pending[0]["reason"], "label_value" in pending[0]))
        self.assertEqual(12, len(silver_gate.trainable_labels(self.root)))  # Pending은 학습에서 빠진다

    def test_compare_to_gold_takes_only_human_gold_and_feeds_the_approval(self):
        gold = [{"image_sha": "g%d" % i, "zone": "z1", "value": "normal", "created_by": "human"} for i in range(10)]
        agent = [{"image_sha": "g%d" % i, "zone": "z1", "label_value": "normal" if i else "defect"} for i in range(10)]
        agent += [{"image_sha": "extra", "zone": "z1", "label_value": "normal"}, {"image_sha": "g9", "zone": "z2", "label_value": None}]
        agent[9]["label_value"] = None  # 판단 불가는 오류로 세지 않는다
        got = silver_gate.compare_to_gold(agent, gold)
        self.assertEqual({"n": 9, "errors": 1, "error_rate": [1, 9], "unmatched": 2, "pending": 1}, got)
        scope = dict(SCOPE, stratum="back")
        res = silver_policy.approve(self.root, 5.0, scope, {"batch_id": "cal-9", "role": "confirm", "n": got["n"], "errors": got["errors"]},
                                    cap=0.10, min_n=5)
        self.assertEqual((False, "error_rate_over_cap"), (res["ok"], res["reason"]))  # 1/9 ≈ 11.1%
        for bad in (dict(gold[0], image_sha="g99", created_by="agent"), dict(gold[0], image_sha="g98", value="maybe")):  # AI 판정은 정답이 아니다
            with self.assertRaises(silver_gate.GateError):
                silver_gate.compare_to_gold(agent, gold + [bad])
        with self.assertRaises(silver_gate.GateError):  # 같은 구역의 Gold 중복
            silver_gate.compare_to_gold(agent, gold + [dict(gold[0])])

    def test_batch_rules_retry_is_idempotent_one_policy_per_batch_closed_after_audit_and_withdrawal_makes_pending(self):
        first = judge(self.root, "b1", self.policy, cands(6))
        events = read_events(self.root, silver_store.STORE)
        again = judge(self.root, "b1", self.policy, cands(6))  # 같은 인자 재호출(이어 쓰기): 중복 저장 없음
        self.assertEqual((0, 6), (len(again["silver"]), len(again["existing"])))
        self.assertEqual(events, read_events(self.root, silver_store.STORE))
        back = dict(SCOPE, stratum="back")
        second = approve(self.root, scope=back, batch="cal-2")
        mixed = judge(self.root, "b1", second, cands(2, prefix="m", scope=back))
        self.assertEqual({"ok": False, "reason": "mixed_policy_batch"}, mixed)
        self.assertEqual("pending", audit.audit_status(self.root)["b1"])
        audit.plan_audit(self.root, 4.0, "b1", seed=1, schedule=FAST)
        self.assertEqual({"ok": False, "reason": "batch_closed"}, judge(self.root, "b1", self.policy, cands(2, prefix="late")))
        withdrawal.withdraw(self.root, 5.0, self.policy, "test")
        entries = silver_store.load(self.root)
        labels = silver_gate.fold_labels(entries, silver_policy.fold(entries))["labels"]
        self.assertEqual({"Pending"}, {labels[i]["grade"] for i in first["silver"]})
        self.assertTrue(all("label_value" not in labels[i] and labels[i]["reason"] == "policy_withdrawn" for i in first["silver"]))
        self.assertEqual([], silver_gate.trainable_labels(self.root))


if __name__ == "__main__":
    unittest.main()
