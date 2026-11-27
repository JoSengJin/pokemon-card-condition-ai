"""Silver 정책 철회의 B+D 처리(2026-11-27 합의·최종 결정): 직접 실패 계보 무효, 같은 정책의 다른 묶음 계보 보류, 우회 불가, 사유별 범위.

합성 시험이며 실제 Silver 품질·묶음 간 오류 상관·모델 성능의 근거가 아니다(감사 표본 2개, 판정자는 선언된 human 하나).
"""
import unittest

from harness import audit, champion, eligibility, silver_gate, silver_policy, silver_store, withdrawal
from tests.test_harness_champion_support import add_model
from tests.test_harness_silver_support import PROTECTED, cands, judge
from tests.test_harness_withdrawal_support import SCHEDULE, make_batch, sample_of, scenario, snapshot

HOLD = "policy_withdrawn_hold"


class WithdrawalPolicyTest(unittest.TestCase):
    def test_b1_failure_holds_b2_even_though_b2_passed_its_ten_percent_audit(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        make_batch(r, "b3", "planned")  # 같은 정책, 실패 시점에는 감사 대기
        c3 = add_model(r, "c3", batches=["b3"])
        res = audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        self.assertEqual(("failed", 1, 2), (res["status"], res["errors"], res["n_sample"]))  # 표본 2개 중 오류 1개(9개 이하 표본의 단일 오류)
        audit.record_verdicts(r, 7.0, "b3", {i: "correct" for i in sample_of(r, "b3")})  # 실패 뒤에 b3도 10% 감사를 통과
        self.assertEqual({"b1": "failed", "b2": "complete", "b3": "complete", "o1": "complete"}, audit.audit_status(r))
        self.assertEqual({"base": ("valid", None), "u": ("valid", None), "m1": ("invalidated", "invalidated"),
                          "c1": ("invalidated", "invalidated"), "m2": ("valid", HOLD), "c2": ("valid", HOLD)},
                         snapshot(r, m)["models"])  # b2·b3 계보는 무효화하지 않는다(다른 묶음의 오류를 확정하지 않음), 승격만 보류
        for model in (m["c2"], c3, add_model(r, "late", batches=["b2"])):
            res = champion.promote(r, 8.0, model)
            self.assertEqual((False, HOLD), (res["ok"], res["reason"]))
        self.assertTrue(champion.promote(r, 9.0, m["u"])["ok"])  # 다른 정책의 모델은 영향 없음

    def test_audits_finished_before_the_withdrawal_never_requalify(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        done = snapshot(r, m)
        self.assertEqual("complete", audit.audit_status(r)["b2"])  # 철회 전 10% 감사 결과는 보존된다
        audit.record_verdicts(r, 7.0, "b2")  # 이미 끝난 감사를 다시 정산하거나
        self.assertTrue(audit.plan_audit(r, 7.0, "b2", seed=9, schedule=SCHEDULE)["existing"])  # 다시 계획해도 새 판정이 아니다
        withdrawal.withdraw(r, 8.0, s["policy"], "unclear")  # 더 약한 사유로 다시 철회해도 무효·보류가 풀리지 않는다
        self.assertEqual(done["models"], snapshot(r, m)["models"])
        for name in ("m2", "c2"):
            res = eligibility.parent_check(r, m[name])
            self.assertEqual((False, HOLD), (res["ok"], res["reason"]))

    def test_new_version_reworded_labels_or_renaming_cannot_bypass_the_hold(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        v2 = make_batch(r, "n1")  # 같은 범위의 새 판본 정책과 새 묶음(감사 통과)
        self.assertTrue(v2.endswith("-v2"))
        same = silver_gate.judge_candidates(r, 8.0, "n3", v2, cands(20, prefix="b2"), PROTECTED, {}, criteria_version="c1", model_version="m1")
        self.assertEqual((0, 20), (len(same["silver"]), len(same["existing"])))  # 같은 키의 재생성은 기존 중복 거절 그대로
        judge_reworded = silver_gate.judge_candidates(r, 8.0, "n2", v2, cands(20, prefix="b2"), PROTECTED, {},
                                                      criteria_version="c1-reworded", model_version="m1")
        self.assertEqual(20, len(judge_reworded["silver"]))  # 기준 문구만 바꾼 같은 이미지의 새 라벨(새 라벨 ID)
        audit.plan_audit(r, 8.0, "n2", seed=1, schedule=SCHEDULE)
        audit.record_verdicts(r, 8.0, "n2", {i: "correct" for i in sample_of(r, "n2")})
        renamed = add_model(r, "m2-renamed", batches=["b2"], config={"renamed": True})  # 이름·설정만 바꾼 재등록
        mixed = add_model(r, "mixed", batches=["b2", "n2"])
        for model in (m["m2"], m["c2"], renamed, mixed):
            self.assertEqual(HOLD, champion.promote(r, 9.0, model)["reason"])
        self.assertTrue(champion.promote(r, 10.0, add_model(r, "fresh", batches=["n1", "n2"]))["ok"])  # 새 판본의 새 자료만 쓴 새 계보
        b2_ids = {e["data"]["label_id"] for e in silver_store.load(r) if e["event"] == "silver_label" and e["data"]["batch_id"] == "b2"}
        self.assertEqual(set(), b2_ids & {d["label_id"] for d in silver_gate.trainable_labels(r)})  # 철회된 b2 라벨은 계속 Pending

    def test_direct_failure_invalidates_every_descendant_even_one_registered_later(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        g1 = add_model(r, "g1", parent=m["c1"])
        gg = add_model(r, "gg", parent=g1, batches=["o1"])  # 다른 정책 묶음을 더해도 조상의 실패를 물려받는다
        res = audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        self.assertEqual(sorted([m["m1"], m["c1"], g1, gg]), res["cascade"]["invalidated"])
        late = add_model(r, "late-child", parent=m["m1"])
        self.assertEqual("invalidated", champion.promote(r, 7.0, late)["reason"])
        self.assertEqual("invalidated", eligibility.parent_check(r, m["m1"])["reason"])

    def test_systematic_error_or_unscoped_contamination_invalidates_the_whole_policy_lineage(self):
        cases = {("systematic_error", None): ("invalidated", "invalidated"), ("contamination", None): ("invalidated", "invalidated"),
                 ("contamination", ("b2",)): ("valid", HOLD)}  # 범위를 특정한 오염은 그 묶음 계보만 무효, 나머지는 보류
        for (reason, batches), m1_state in cases.items():
            with self.subTest(reason=reason, batches=batches):
                s = scenario(self)
                r, m = s["root"], s["models"]
                res = withdrawal.withdraw(r, 6.0, s["policy"], reason, None if batches is None else list(batches))
                snap = snapshot(r, m)
                self.assertEqual((m1_state, ("invalidated", "invalidated")), (snap["models"]["m1"], snap["models"]["m2"]))
                self.assertEqual((("valid", None), ("valid", None)), (snap["models"]["base"], snap["models"]["u"]))
                self.assertEqual(("base", True), (snap["champion"], res["restore"]["ok"]))  # 무효가 된 Champion m2 → 마지막 적격 base

    def test_unclear_or_unknown_reason_blocks_new_use_and_promotion_and_can_be_confirmed_later(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        res = withdrawal.withdraw(r, 6.0, s["policy"], "operator note: looks off")
        record = [e["data"] for e in silver_store.load(r) if e["event"] == "policy_withdrawn"][-1]
        self.assertEqual(("unclear", "operator note: looks off", None), (record["reason"], record["given"], record["batches"]))
        self.assertEqual(([], m["m2"]), (res["invalidated"], res["conditional"]["model_id"]))  # 무효 없음, Champion은 조건부 유지
        self.assertEqual({"ok": False, "reason": "policy_inactive"}, judge(r, "b9", s["policy"], cands(3, prefix="z")))
        self.assertEqual(20, len(silver_gate.trainable_labels(r)))  # 다른 정책 o1의 Silver만 학습 가능
        self.assertEqual(HOLD, champion.promote(r, 7.0, m["m1"])["reason"])
        self.assertTrue(withdrawal.withdraw(r, 7.5, s["policy"], None)["already"])  # 사유 없음도 unclear(같은 기록)
        confirmed = withdrawal.withdraw(r, 8.0, s["policy"], "contamination", ["b1"])  # 사유 확인 후 처리: b1 오염 확정
        self.assertEqual(sorted([m["m1"], m["c1"]]), confirmed["invalidated"])
        self.assertEqual(["m2"], snapshot(r, m)["conditional"])  # 같은 조건부 기록을 반복하지 않는다

    def test_malformed_scope_is_refused_before_anything_is_written(self):
        s = scenario(self)
        r = s["root"]
        before = silver_store.load(r)
        for policy, batches in ((s["policy"], ["o1"]), (s["policy"], []), (s["policy"], "b1"), (s["policy"], [None]), ("pol-unknown", None)):
            with self.assertRaises(silver_policy.PolicyError, msg=(policy, batches)):
                withdrawal.withdraw(r, 6.0, policy, "batch_label_error", batches)
        self.assertEqual(before, silver_store.load(r))


if __name__ == "__main__":
    unittest.main()
