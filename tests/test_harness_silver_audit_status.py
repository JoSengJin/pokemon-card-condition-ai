"""감사 상태 정본과 7단계 승격 연계: 감사 진행 중 승격 거절, 감사 중에도 선별·라벨링 계속, 판정 입력 규칙, 변조 감지. 합성 데이터다."""
import os
import unittest

from harness import active_learning, audit, champion, ledger, silver_store
from tests.test_harness_champion_support import add_model, make_root
from tests.test_harness_silver_support import FAST, PROTECTED, al_pool, approve, cands, judge

CONFIG = {"error_priority": {"FN": 2.0, "FP": 1.0}, "stratum_scarcity": {"front": 1.0, "back": 0.5}, "threshold_width": 0.4,
          "per_group_cap": 2, "per_seller_cap": 4, "cluster_quota": 6}


class AuditStatusTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = approve(self.root)

    def planned(self, name, count=20, prefix=None):
        """묶음을 만들고 감사를 계획한다(감사율 50%). 표본 ID 목록을 돌려준다."""
        judge(self.root, name, self.policy, cands(count, prefix=prefix or name))
        return audit.plan_audit(self.root, 3.0, name, seed=2, schedule=FAST)["plan"]["sample_ids"]

    def test_status_follows_the_audit_lifecycle(self):
        judge(self.root, "b0", self.policy, cands(4, prefix="u"))
        self.assertEqual({"b0": "pending"}, audit.audit_status(self.root))  # 계획 전 = pending(모르면 통과시키지 않는다)
        sample = self.planned("b1")
        self.assertEqual("pending", audit.audit_status(self.root)["b1"])
        audit.record_verdicts(self.root, 4.0, "b1", {i: "correct" for i in sample[:5]})
        self.assertEqual("pending", audit.audit_status(self.root)["b1"])  # 판정이 덜 끝남
        res = audit.record_verdicts(self.root, 5.0, "b1", {i: "correct" for i in sample[5:]})
        self.assertEqual(("complete", 0, 10), (res["status"], res["errors"], res["n_sample"]))
        unjudgeable = [dict(cands(1, prefix="n")[0], label_value=None)]
        judge(self.root, "b2", self.policy, unjudgeable)  # Silver가 없는 묶음은 감사할 AI 라벨이 없다
        self.assertEqual("not_required", audit.plan_audit(self.root, 6.0, "b2", seed=1, schedule=FAST)["status"])
        self.assertEqual({"b0": "pending", "b1": "complete", "b2": "not_required"}, audit.audit_status(self.root))
        with self.assertRaises(audit.AuditError):
            audit.plan_audit(self.root, 7.0, "no-such-batch", seed=1, schedule=FAST)

    def test_promotion_is_refused_while_the_audit_is_pending_or_failed_and_allowed_after_it_completes(self):
        base = add_model(self.root, "base")
        judge(self.root, "b1", self.policy, cands(20, prefix="b1"))
        used = add_model(self.root, "used", batches=["b1"])  # 학습 manifest는 b1의 Silver 라벨(라벨이 생긴 뒤에 등록)
        self.assertEqual("audit_pending", champion.promote(self.root, 3.0, used)["reason"])  # 승격은 장부를 직접 읽는다(상태 인자 없음)
        sample = audit.plan_audit(self.root, 4.0, "b1", seed=2, schedule=FAST)["plan"]["sample_ids"]
        self.assertEqual("audit_pending", champion.promote(self.root, 5.0, used)["reason"])
        audit.record_verdicts(self.root, 6.0, "b1", {i: "correct" for i in sample[:9]})
        refused = champion.promote(self.root, 7.0, used)
        self.assertEqual(("audit_pending", {"b1": "pending"}), (refused["reason"], refused["detail"]))
        audit.record_verdicts(self.root, 8.0, "b1", {sample[9]: "correct"})
        self.assertTrue(champion.promote(self.root, 9.0, used)["ok"])
        sample = self.planned("b2")
        audit.record_verdicts(self.root, 10.0, "b2", {i: "incorrect" for i in sample[:3]})
        late = add_model(self.root, "late", batches=["b2"])  # 실패 뒤에 등록한 모델도 실패한 묶음을 쓰면 승격할 수 없다
        refused = champion.promote(self.root, 11.0, late)
        self.assertEqual(("audit_failed", {"b2": "failed"}), (refused["reason"], refused["detail"]))
        self.assertEqual("policy_withdrawn_hold", champion.promote(self.root, 11.5, used)["reason"])  # 같은 정책 b1: 조건부 유지일 뿐 재승격 근거 아님
        self.assertTrue(champion.promote(self.root, 12.0, base)["ok"])  # 묶음을 안 쓴 모델은 영향 없음

    def test_selection_labeling_and_planning_continue_while_an_audit_is_pending(self):
        self.planned("b1")  # b1 감사는 끝나지 않은 채로 둔다
        selection = active_learning.select(al_pool(30), PROTECTED, CONFIG, 6, 1, [])
        self.assertEqual(6, len(selection["selected"]))
        self.assertEqual(5, len(judge(self.root, "b3", self.policy, cands(5, prefix="late"))["silver"]))
        sample = audit.plan_audit(self.root, 4.0, "b3", seed=3, schedule=FAST)["plan"]["sample_ids"]
        audit.record_verdicts(self.root, 5.0, "b3", {i: "correct" for i in sample})
        self.assertEqual({"b1": "pending", "b3": "complete"}, audit.audit_status(self.root))

    def test_verdicts_come_only_from_a_human_inside_the_sample_and_are_never_flipped(self):
        sample = self.planned("b1")
        for judge_name in ("ai", "agent", "codex", ""):
            with self.assertRaises(audit.AuditError, msg=judge_name):
                audit.record_verdicts(self.root, 4.0, "b1", {sample[0]: "correct"}, judge=judge_name)
        for bad in ({"not-in-sample": "correct"}, {sample[0]: "maybe"}):
            with self.assertRaises(audit.AuditError):
                audit.record_verdicts(self.root, 4.0, "b1", bad)
        with self.assertRaises(audit.AuditError):
            audit.record_verdicts(self.root, 4.0, "never-planned", {"x": "correct"})
        audit.record_verdicts(self.root, 5.0, "b1", {sample[0]: "correct"})
        before = silver_store.load(self.root)
        audit.record_verdicts(self.root, 6.0, "b1", {sample[0]: "correct"})  # 같은 판정 반복은 쓰지 않는다
        audit.record_verdicts(self.root, 6.0, "b1")  # 정산만: 새 판정 없음
        self.assertEqual(before, silver_store.load(self.root))
        with self.assertRaises(audit.AuditError):
            audit.record_verdicts(self.root, 7.0, "b1", {sample[0]: "incorrect"})  # 번복 거절
        self.assertEqual({"b1": "pending"}, audit.audit_status(self.root))

    def test_tampering_with_the_store_is_detected_and_the_status_is_never_guessed(self):
        sample = self.planned("b1")
        audit.record_verdicts(self.root, 4.0, "b1", {i: "correct" for i in sample})
        path = os.path.join(self.root, silver_store.STORE)
        tail = ledger.tail(path)
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines(True)
        cases = {"edited": [l.replace('"correct"', '"incorrect"') for l in lines], "deleted_middle": lines[:5] + lines[6:],
                 "reordered": [lines[1], lines[0]] + lines[2:]}
        for name, damaged in cases.items():
            with open(path, "w", encoding="utf-8") as handle:
                handle.writelines(damaged)
            with self.assertRaises(silver_store.StoreError, msg=name):
                audit.audit_status(self.root)
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines[:-1])  # 꼬리 잘림은 외부에 복제한 마지막 해시와 대조할 때만 감지된다
        with self.assertRaises(silver_store.StoreError):
            silver_store.load(self.root, expected_tail=tail)
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        self.assertEqual({"b1": "complete"}, audit.audit_status(self.root))


if __name__ == "__main__":
    unittest.main()
