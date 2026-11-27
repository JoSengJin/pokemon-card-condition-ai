"""철회와 Champion(2026-11-27 최종 결정 ①·코드 보완 3): 복원은 같은 적격성 계산, 보류 모델 제외, 후보가 없으면 Champion 없음,
조건부 유지 기록과 보류 상속, 수동·자동 철회의 같은 결과, 중복 철회의 멱등. 합성 시험이며 모델 성능 근거가 아니다."""
import os
import pathlib
import unittest

from harness import audit, champion, eligibility, ledger, registry, silver_store, withdrawal
from tests.test_harness_champion_support import add_model, pointer_model, read_events
from tests.test_harness_withdrawal_support import sample_of, scenario, snapshot

HOLD = "policy_withdrawn_hold"


class WithdrawalChampionTest(unittest.TestCase):
    def test_champion_on_the_failed_batch_is_restored_to_the_last_eligible_one_skipping_held_models(self):
        s = scenario(self, champions=("base", "m2", "m1"), legacy=("m1",))  # m1은 옛 코드가 감사 전에 승격시킨 상태
        r, m = s["root"], s["models"]
        res = audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        self.assertEqual((True, m["base"], m["m1"]), tuple(res["cascade"]["restore"][k] for k in ("ok", "model_id", "restored_from")))
        snap = snapshot(r, m)
        self.assertEqual(("base", ["base", "m2", "m1", "base"]), (snap["champion"], snap["history"]))  # 보류인 m2를 건너뛴다
        self.assertEqual("champion_restored", read_events(r, "ledger.jsonl")[-1]["event"])

    def test_no_eligible_candidate_switches_to_no_champion_and_a_separate_dev_baseline_keeps_exploration(self):
        s = scenario(self, champions=("m2", "m1"), legacy=("m1",))
        r, m = s["root"], s["models"]
        res = audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})["cascade"]["restore"]
        self.assertEqual((False, "no_verified_champion", True, m["m1"]), (res["ok"], res["reason"], res["cleared"], res["restored_from"]))
        state = registry.load(r)
        self.assertEqual((None, None, None), (pointer_model(r), champion.read_current(r), state["pending"]))  # 무효 m1을 가리키지 않는다
        self.assertEqual((None, "clear"), (state["history"][-1]["model_id"], state["history"][-1]["reason"]))
        self.assertEqual("champion_cleared", read_events(r, "ledger.jsonl")[-1]["event"])
        first = champion.set_dev_baseline(r, 7.0, m["m2"], "탐색 비교 기준(보류 모델)")  # Champion이 아닌 별도 기록, 보류 모델도 받는다
        self.assertEqual((True, False), (first["ok"], first["already"]))
        self.assertEqual({"model_id": m["m2"], "basis": "탐색 비교 기준(보류 모델)"}, registry.load(r)["dev_baseline"])
        self.assertTrue(champion.set_dev_baseline(r, 7.5, m["m2"], "탐색 비교 기준(보류 모델)")["already"])
        self.assertEqual("invalidated", champion.set_dev_baseline(r, 8.0, m["m1"], "x")["reason"])
        self.assertEqual(HOLD, champion.promote(r, 8.0, m["m2"])["reason"])  # Baseline은 적격성 근거가 아니다
        self.assertFalse(eligibility.parent_check(r, m["m2"])["ok"])
        self.assertEqual("no_champion", champion.restore_last_verified(r, 8.5)["reason"])
        self.assertEqual({"ok": True, "already": False, "model_id": m["base"], "previous": None}, champion.promote(r, 9.0, m["base"]))

    def test_conditional_champion_is_recorded_once_never_restored_to_and_descendants_inherit_the_hold(self):
        s = scenario(self)
        r, m = s["root"], s["models"]
        res = audit.record_verdicts(r, 6.0, "b1", {sample_of(r, "b1")[0]: "incorrect"})
        self.assertEqual({"model_id": m["m2"], "batches": ["b2"], "policies": [s["policy"]], "reasons": {s["policy"]: "batch_label_error"}},
                         res["cascade"]["conditional"])
        self.assertEqual(m["m2"], pointer_model(r))  # 조건부 유지: 포인터는 그대로
        child = add_model(r, "child", parent=m["m2"], batches=["o1"])
        grandchild = add_model(r, "grandchild", parent=child)
        for model in (m["m2"], m["c2"], child, grandchild):  # 조건부 Champion 자신의 재승격(already)도 근거가 되지 않는다
            self.assertEqual(HOLD, champion.promote(r, 7.0, model)["reason"])
        self.assertEqual(res["cascade"]["conditional"], withdrawal.withdraw(r, 7.5)["conditional"])
        self.assertEqual(["m2"], snapshot(r, m)["conditional"])  # 한 번만 기록
        self.assertTrue(champion.promote(r, 8.0, m["u"])["ok"])
        back = champion.restore_last_verified(r, 9.0, regression="u regressed", model_id=m["u"])
        self.assertEqual(m["base"], back["model_id"])  # 조건부였던 m2는 복원 후보가 아니다

    def test_manual_and_automatic_withdrawal_reach_the_same_state(self):
        auto = scenario(self, champions=("base", "m2", "m1"), legacy=("m1",))
        manual = scenario(self, champions=("base", "m2", "m1"), legacy=("m1",))
        audit.record_verdicts(auto["root"], 6.0, "b1", {sample_of(auto["root"], "b1")[0]: "incorrect"})
        withdrawal.withdraw(manual["root"], 6.0, manual["policy"], "batch_label_error", ["b1"])
        self.assertEqual(snapshot(auto["root"], auto["models"]), snapshot(manual["root"], manual["models"]))
        records = [[(e["data"]["reason"], e["data"]["batches"]) for e in silver_store.load(x["root"]) if e["event"] == "policy_withdrawn"]
                   for x in (auto, manual)]
        self.assertEqual([[("batch_label_error", ["b1"])]] * 2, records)

    def test_repeating_the_same_withdrawal_writes_nothing_and_restores_nothing_again(self):
        s = scenario(self, champions=("base", "m2", "m1"), legacy=("m1",))
        r = s["root"]
        verdicts = {sample_of(r, "b1")[0]: "incorrect"}
        audit.record_verdicts(r, 6.0, "b1", verdicts)
        paths = [os.path.join(r, rel) for rel in (silver_store.STORE, registry.REGISTRY, "ledger.jsonl", registry.POINTER)]
        before = [pathlib.Path(p).read_bytes() for p in paths]
        repeats = [withdrawal.withdraw(r, 7.0, s["policy"], "batch_label_error", ["b1"]), withdrawal.withdraw(r, 7.0),
                   audit.record_verdicts(r, 7.0, "b1")["cascade"], audit.record_verdicts(r, 7.0, "b1", verdicts)["cascade"]]
        for res in repeats:
            self.assertEqual((True, [], None, None), (res["already"], res["invalidated"], res["restore"], res["conditional"]))
        self.assertEqual(before, [pathlib.Path(p).read_bytes() for p in paths])
        self.assertEqual([[], [], []], [ledger.verify(p) for p in paths[:3]])


if __name__ == "__main__":
    unittest.main()
