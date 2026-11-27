"""두 장부(Silver 저장소·레지스트리)와 포인터를 갱신하는 철회 도중 실제 SIGKILL: 끊김 없는 실행이 지나간 모든 쓰기 지점의 앞뒤에서 죽이고,
같은 호출을 다시 하면 끊김 없는 실행과 같은 최종 상태에 도달한다. 죽은 직후(복구 전)에도 영향 모델의 승격은 막힌다. 합성 시험이다."""
import unittest

from harness import audit, champion, registry, silver_gate, silver_store, withdrawal
from tests.test_harness_champion_support import add_model
from tests.test_harness_silver_support import cands, judge
from tests.test_harness_withdrawal_support import run_point, sample_of, scenario, snapshot

HOLD = "policy_withdrawn_hold"


class WithdrawalKillTest(unittest.TestCase):
    def check_points(self, setup, call, must):
        """setup(scenario 인자)으로 매번 같은 상태를 새로 만든다. 끊김 없는 실행의 지점 목록에서 하나씩 죽이고, 복구 전 불변식(장부 체인 정상,
        감사 실패나 철회 기록이 있으면 보류 모델 c2 승격 거절)을 본 뒤 같은 호출로 이어서 끝낸 최종 상태가 끊김 없는 결과와 같은지 본다."""
        ref = scenario(self, **setup)
        trace = run_point(self, ref["root"], "none", call)
        want = snapshot(ref["root"], ref["models"])
        points = sorted(set(trace), key=trace.index)
        self.assertTrue(set(must) <= {p.split(":")[1] for p in points}, (must, points))
        for point in points:
            s = scenario(self, **setup)
            run_point(self, s["root"], point, call)
            self.assertEqual([[], [], []], snapshot(s["root"], s["models"])["chains"], point)
            if any(e["event"] == "policy_withdrawn" or e["data"].get("status") == "failed" for e in silver_store.load(s["root"])):
                self.assertEqual(HOLD, champion.promote(s["root"], 9.5, s["models"]["c2"])["reason"], point)
            if call["fn"] == "withdraw":
                withdrawal.withdraw(s["root"], 10.0, **call["kw"])
            else:
                audit.record_verdicts(s["root"], 10.0, call["batch_id"], call["verdicts"])
            self.assertEqual(want, snapshot(s["root"], s["models"]), point)
        return want

    def test_kill_at_every_write_of_an_automatic_withdrawal_that_restores_the_champion(self):
        setup = {"champions": ("base", "m2", "m1"), "legacy": ("m1",)}
        probe = scenario(self, **setup)
        call = {"fn": "verdicts", "batch_id": "b1", "verdicts": {sample_of(probe["root"], "b1")[0]: "incorrect"}}
        want = self.check_points(setup, call, ("audit_verdicts", "audit_completed", "policy_withdrawn", "invalidated", "lineage_invalidated",
                                               "switch_intent", "pointer", "switched", "champion_restored", "weights"))
        self.assertEqual(("base", ("invalidated", "invalidated")), (want["champion"], want["models"]["m1"]))

    def test_kill_at_every_write_of_a_manual_withdrawal_that_leaves_no_champion(self):
        probe = scenario(self, champions=("m2", "m1"), legacy=("m1",))
        call = {"fn": "withdraw", "kw": {"policy_id": probe["policy"], "reason": "batch_label_error", "batches": ["b1"]}}
        want = self.check_points({"champions": ("m2", "m1"), "legacy": ("m1",)}, call,
                                 ("policy_withdrawn", "invalidated", "switch_intent", "pointer", "switched", "champion_cleared"))
        self.assertEqual((None, ["m2", "m1", None]), (want["champion"], want["history"]))

    def test_kill_at_every_write_of_a_hold_only_withdrawal_with_a_conditional_champion(self):
        probe = scenario(self)
        call = {"fn": "withdraw", "kw": {"policy_id": probe["policy"], "reason": "criteria_change", "batches": None}}
        want = self.check_points({}, call, ("policy_withdrawn", "champion_conditional"))
        self.assertEqual(("m2", ["m2"], ("valid", HOLD)), (want["champion"], want["conditional"], want["models"]["m1"]))

    def test_kill_between_the_failure_record_and_the_withdrawal_record_still_refuses_b2(self):
        ref = scenario(self)
        audit.record_verdicts(ref["root"], 6.0, "b1", {sample_of(ref["root"], "b1")[0]: "incorrect"})
        s = scenario(self)
        r, m = s["root"], s["models"]
        verdicts = {sample_of(r, "b1")[0]: "incorrect"}
        run_point(self, r, "after:audit_completed:1", {"fn": "verdicts", "batch_id": "b1", "verdicts": verdicts})
        self.assertNotIn("policy_withdrawn", [e["event"] for e in silver_store.load(r)])
        self.assertEqual("valid", registry.load(r)["models"][m["m1"]]["status"])  # 레지스트리 무효화도 아직 없다
        for model in (m["c2"], add_model(r, "late", batches=["b2"])):  # 복구 전: 같은 정책 b2 계보 승격 거절
            self.assertEqual(HOLD, champion.promote(r, 7.0, model)["reason"])
        self.assertEqual("audit_failed", champion.promote(r, 7.0, m["m1"])["reason"])  # 실패 묶음 계보는 파생 무효
        self.assertEqual({"ok": False, "reason": "policy_inactive"}, judge(r, "b9", s["policy"], cands(2, prefix="z")))
        self.assertEqual(20, len(silver_gate.trainable_labels(r)))  # 다른 정책 o1만 학습 가능
        withdrawal.withdraw(r, 8.0)  # 복구만(예: Supervisor): 장부만 보고 무효화·조건부 기록을 이어간다
        audit.record_verdicts(r, 9.0, "b1", verdicts)  # 같은 인자 재호출이 철회 기록을 마저 쓴다
        self.assertEqual(snapshot(ref["root"], ref["models"]), snapshot(r, m))  # 끊김 없는 실행과 같은 최종 상태


if __name__ == "__main__":
    unittest.main()
