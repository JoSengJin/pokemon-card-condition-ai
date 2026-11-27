"""감사 실패 연쇄: 정책 철회(Silver→Pending) → 7단계 lineage 무효화 → 마지막 정상 Champion 복원이 자동으로 이어진다. 7단계 실제 함수와 합성 레지스트리."""
import os
import unittest

from harness import audit, champion, ledger, registry, silver_gate, silver_policy, silver_store
from tests.test_harness_champion_support import add_model, pointer_model, read_events
from tests.test_harness_silver_support import FAST, cands, cascade_setup, judge


class CascadeTest(unittest.TestCase):
    def setUp(self):
        self.s = cascade_setup(self)
        self.root = self.s["root"]

    def verdicts(self, bad, sample=None, only=None):
        """표본 중 앞의 bad개를 incorrect, 나머지를 correct로 한 판정 dict(only가 있으면 그 개수만)."""
        sample = sample or self.s["sample"]
        picked = sample if only is None else sample[:only]
        return {i: ("incorrect" if n < bad else "correct") for n, i in enumerate(picked)}

    def status(self):
        models = registry.load(self.root)["models"]
        return {name: models[mid]["status"] for name, mid in self.s["models"].items()}

    def test_failed_audit_withdraws_the_policy_invalidates_the_lineage_and_restores_the_last_good_champion(self):
        m = self.s["models"]
        self.assertEqual(m["c1"], pointer_model(self.root))  # 감사 상태를 호출자가 직접 줘서 승격된 Champion(복원 경로 시험용)
        res = audit.record_verdicts(self.root, 6.0, "b1", self.verdicts(2))
        self.assertEqual(("failed", 2, 10), (res["status"], res["errors"], res["n_sample"]))
        self.assertEqual(sorted([m["m1"], m["c1"]]), res["cascade"]["invalidated"])
        self.assertEqual((True, m["base"], m["c1"]), (res["cascade"]["restore"]["ok"], res["cascade"]["restore"]["model_id"],
                                                      res["cascade"]["restore"]["restored_from"]))
        self.assertEqual({"base": "valid", "m1": "invalidated", "c1": "invalidated", "u": "valid"}, self.status())
        self.assertEqual((m["base"], True), (pointer_model(self.root), champion.read_current(self.root)["valid"]))
        policies = silver_policy.fold(silver_store.load(self.root))["policies"]
        self.assertEqual("withdrawn", policies[self.s["policy_id"]]["status"])
        entries = silver_store.load(self.root)
        labels = silver_gate.fold_labels(entries, silver_policy.fold(entries))["labels"]
        self.assertEqual({"Pending"}, {labels[i]["grade"] for i in self.s["ids"]})  # Silver → Pending
        self.assertEqual([], silver_gate.trainable_labels(self.root))
        self.assertEqual({"b1": "failed"}, audit.audit_status(self.root))
        order = [e["event"] for e in entries if e["event"] in ("audit_verdicts", "audit_completed", "policy_withdrawn", "cascade_done")]
        self.assertEqual(["audit_verdicts", "audit_completed", "policy_withdrawn", "cascade_done"], order)
        main = [e["event"] for e in read_events(self.root, "ledger.jsonl")]
        self.assertTrue({"lineage_invalidated", "champion_restored"} <= set(main))
        for rel in ("ledger.jsonl", registry.REGISTRY, silver_store.STORE):
            self.assertEqual([], ledger.verify(os.path.join(self.root, rel)), rel)
        for name in ("m1", "c1"):  # 무효화된 모델은 어떤 감사 상태를 줘도 승격할 수 없다
            self.assertEqual("invalidated", champion.promote(self.root, 7.0, m[name], {"b1": "complete"})["reason"])
        before = (entries, read_events(self.root, registry.REGISTRY), read_events(self.root, "ledger.jsonl"))
        again = audit.record_verdicts(self.root, 8.0, "b1")  # 정산만
        same = audit.record_verdicts(self.root, 9.0, "b1", self.verdicts(2))  # 같은 판정 재전송: 연쇄를 다시 하지 않는다
        self.assertEqual(("failed", "failed"), (again["status"], same["status"]))
        self.assertEqual(before, (silver_store.load(self.root), read_events(self.root, registry.REGISTRY), read_events(self.root, "ledger.jsonl")))

    def test_unrelated_champion_stays_and_only_models_that_used_the_batch_are_invalidated(self):
        other = cascade_setup(self, champion_is_failing=False)  # Champion은 b1을 쓰지 않은 u
        self.s, self.root = other, other["root"]
        res = audit.record_verdicts(self.root, 6.0, "b1", self.verdicts(3))
        self.assertEqual("failed", res["status"])
        self.assertIsNone(res["cascade"]["restore"])
        self.assertEqual({"base": "valid", "m1": "invalidated", "c1": "invalidated", "u": "valid"}, self.status())
        self.assertEqual(other["models"]["u"], pointer_model(self.root))

    def test_failure_is_decided_as_soon_as_the_errors_exceed_the_cap_even_before_all_verdicts_arrive(self):
        one = audit.record_verdicts(self.root, 6.0, "b1", self.verdicts(1, only=3))  # 1건 오류, 3건 판정: 1/10 ≤ 10%라 아직 모른다
        self.assertEqual(("pending", 1, 3), (one["status"], one["errors"], one["judged"]))
        self.assertEqual("valid", self.status()["m1"])
        two = audit.record_verdicts(self.root, 7.0, "b1", {self.s["sample"][5]: "incorrect"})  # 오류 2건: 2/10 > 10%, 나머지 판정 없이 확정
        self.assertEqual(("failed", 2, 4), (two["status"], two["errors"], two["judged"]))
        self.assertEqual("invalidated", self.status()["m1"])
        self.assertEqual(self.s["models"]["base"], pointer_model(self.root))

    def test_audit_at_exactly_the_cap_passes_and_one_more_error_fails(self):
        policy = self.s["policy_id"]
        judge(self.root, "p1", policy, cands(20, prefix="p1"))
        passed = audit.plan_audit(self.root, 4.0, "p1", seed=1, schedule=FAST)["plan"]["sample_ids"]
        res = audit.record_verdicts(self.root, 5.0, "p1", self.verdicts(1, passed))  # 1/10 = 10% = 상한: 통과
        self.assertEqual(("complete", 1, None), (res["status"], res["errors"], res["cascade"]))
        self.assertEqual("valid", self.status()["m1"])
        self.assertEqual("approved", silver_policy.fold(silver_store.load(self.root))["policies"][policy]["status"])  # 통과한 감사는 정책을 유지
        judge(self.root, "f1", policy, cands(20, prefix="f1"))
        failed = audit.plan_audit(self.root, 6.0, "f1", seed=1, schedule=FAST)["plan"]["sample_ids"]
        res = audit.record_verdicts(self.root, 7.0, "f1", self.verdicts(2, failed))  # 2/10 = 20% > 상한
        self.assertEqual(("failed", 2), (res["status"], res["errors"]))
        self.assertEqual("withdrawn", silver_policy.fold(silver_store.load(self.root))["policies"][policy]["status"])
        self.assertEqual("audit_failed", champion.promote(self.root, 8.0, add_model(self.root, "again", batches=["f1"]),
                                                          audit.audit_status(self.root))["reason"])


if __name__ == "__main__":
    unittest.main()
