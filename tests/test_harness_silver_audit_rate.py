"""감사율: 0% 거절, 초기 10% → 최저 2% 하한, 상향 신호, 조정 근거 기록, 표본 재현. 합성 묶음이며 라벨 품질 근거가 아니다."""
import unittest
from fractions import Fraction

from harness import audit, audit_rate, silver_store
from tests.test_harness_champion_support import make_root, read_events
from tests.test_harness_silver_support import FAST, approve, cands, judge

SLOW = {"initial": 0.5, "floor": 0.1, "initial_rounds": 2}  # 합성 값(권고 아님)


class AuditRateTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = approve(self.root)

    def run_round(self, name, count=20, schedule=SLOW, signals=None, seed=1):
        """묶음 하나를 만들고 계획해 표본을 모두 맞다고 판정한다(사람 판정 입력). 계획 dict를 돌려준다."""
        judge(self.root, name, self.policy, cands(count, prefix=name))
        plan = audit.plan_audit(self.root, 3.0, name, seed=seed, schedule=schedule, signals=signals)["plan"]
        audit.record_verdicts(self.root, 4.0, name, {i: "correct" for i in plan["sample_ids"]})
        return plan

    def plans(self):
        return [e["data"] for e in read_events(self.root, silver_store.STORE) if e["event"] == "audit_planned"]

    def test_rate_starts_at_ten_percent_decays_by_half_and_stops_at_the_two_percent_floor(self):
        suggested = audit_rate.SUGGESTED_SCHEDULE  # 제안값: 초기 10%, 최저 2%, 초기 3회차
        rates = [self.run_round("r%d" % n, count=50, schedule=suggested)["rate"] for n in range(8)]
        self.assertEqual(["1/10"] * 3 + ["1/20", "1/40", "1/50", "1/50", "1/50"], rates)
        self.assertTrue(all(Fraction(r) >= Fraction(2, 100) for r in rates))  # 2% 아래로는 내려가지 않는다
        self.assertEqual([True, False, False, True, True, True, False, False], [p["rate_changed"] for p in self.plans()])
        last = self.plans()[-1]
        self.assertEqual((1, "decay"), (last["sample_size"], last["basis"]["why"]))  # 50개의 2% = 1개(최소 1개)

    def test_signals_raise_the_rate_back_and_the_basis_is_recorded(self):
        rates = [self.run_round("a%d" % n)["rate"] for n in range(5)]  # 50%, 2회차 유지, 25%, 12.5%, 최저 10%
        self.assertEqual(["1/2", "1/2", "1/4", "1/8", "1/10"], rates)
        prev = {audit_rate.SIGNAL_KEYS[0]: "1/10", audit_rate.SIGNAL_KEYS[1]: "1/2"}
        for key in audit_rate.SIGNAL_KEYS:  # 분포 변화, Champion–Silver 불일치 급증
            raised = self.run_round("s_" + key, signals={key: True})
            self.assertEqual(("1/2", True, "signal", [key], prev[key]),
                             (raised["rate"], raised["raised"], raised["basis"]["why"], raised["basis"]["signals"], raised["prev_rate"]))
        again = self.run_round("after")  # 상향 직후에는 연속 통과 회차가 부족해 초기 비율을 유지한다
        self.assertEqual(("1/2", "initial_rounds"), (again["rate"], again["basis"]["why"]))
        self.assertEqual("1/4", self.run_round("after2")["rate"])  # 통과 회차가 채워지면 다시 낮아진다

    def test_zero_is_refused_and_manual_or_automatic_changes_leave_value_and_basis_in_the_ledger(self):
        for bad in (0, 0.0, -0.1, 1.5):
            with self.assertRaises(audit.AuditError, msg=bad):
                audit.set_rate(self.root, 5.0, self.policy, bad, "근거")
        with self.assertRaises(audit.AuditError):
            audit.set_rate(self.root, 5.0, self.policy, 0.05, "  ")  # 근거 없는 조정
        with self.assertRaises(audit.AuditError):
            audit.set_rate(self.root, 5.0, "pol-unknown", 0.1, "근거")
        judge(self.root, "z1", self.policy, cands(10, prefix="z1"))
        for schedule in ({"initial": 0.1, "floor": 0, "initial_rounds": 3}, {"initial": 0, "floor": 0, "initial_rounds": 3},
                         {"initial": 0.02, "floor": 0.1, "initial_rounds": 3}, {"initial": 0.1, "floor": 0.02, "initial_rounds": 0},
                         {"initial": 0.1, "floor": 0.02}):
            with self.assertRaises(audit.AuditError, msg=schedule):
                audit.plan_audit(self.root, 6.0, "z1", seed=1, schedule=schedule)
        for signals in ({"unknown_signal": True}, {"distribution_shift": "yes"}):
            with self.assertRaises(audit.AuditError):
                audit.plan_audit(self.root, 6.0, "z1", seed=1, schedule=FAST, signals=signals)
        self.assertEqual([], self.plans())  # 거절된 호출은 아무 것도 쓰지 않는다
        self.run_round("m0", schedule=FAST)
        audit.set_rate(self.root, 5.0, self.policy, 0.2, "표본 20개 오류 0건, 위험도 낮음")
        self.assertEqual({"ok": True, "already": True}, audit.set_rate(self.root, 6.0, self.policy, 0.2, "같은 값"))
        manual = self.run_round("m1", schedule=FAST)
        self.assertEqual(("1/5", "manual_override"), (manual["rate"], manual["basis"]["why"]))
        events = [e["data"] for e in read_events(self.root, silver_store.STORE) if e["event"] == "audit_rate_set"]
        self.assertEqual([("1/5", "1/2", "표본 20개 오류 0건, 위험도 낮음")], [(e["rate"], e["prev"], e["basis"]) for e in events])
        self.assertEqual("1/2", self.run_round("m2", schedule=FAST, signals={"distribution_shift": True})["rate"])  # 신호는 수동 조정도 해제
        self.assertEqual("1/4", self.run_round("m3", schedule=FAST)["rate"])  # 해제됐으므로 수동 값(1/5)이 아니라 일정대로 낮아진다
        for plan in self.plans():  # 계획마다 값·직전 값·변경 여부·근거가 남는다
            self.assertTrue({"rate", "prev_rate", "rate_changed", "basis", "schedule"} <= set(plan))

    def test_sample_is_reproducible_bounded_and_the_cumulative_rule_returns_to_the_initial_rate(self):
        schedule = {"initial": 0.25, "floor": 0.1, "initial_rounds": 1}
        judge(self.root, "p1", self.policy, cands(40, prefix="p1"))
        ids = sorted(e["data"]["label_id"] for e in silver_store.load(self.root) if e["event"] == "silver_label")
        first = audit.plan_audit(self.root, 3.0, "p1", seed=5, schedule=schedule)["plan"]
        self.assertEqual(10, first["sample_size"])  # 40개의 25%
        self.assertTrue(set(first["sample_ids"]) <= set(ids))
        self.assertEqual(first, audit.plan_audit(self.root, 4.0, "p1", seed=99, schedule=schedule)["plan"])  # 같은 묶음 재계획은 기존 계획(멱등)
        same = audit_rate.sample_ids(ids, Fraction(1, 4), 5)
        self.assertEqual(first["sample_ids"], same)
        self.assertEqual(same, audit_rate.sample_ids(list(reversed(ids)), Fraction(1, 4), 5))
        self.assertNotEqual(same, audit_rate.sample_ids(ids, Fraction(1, 4), 6))
        self.assertEqual(1, len(audit_rate.sample_ids(ids[:10], Fraction(1, 50), 1)))
        state = dict(audit_rate.NEW_POLICY, rate=Fraction(1, 20), clean_rounds=5, audited=20, errors=3)  # 누적 15% > 상한 10%
        rate, basis, raised = audit_rate.rate_for(state, [], Fraction(1, 10), Fraction(1, 50), 3, Fraction(1, 10))
        self.assertEqual((Fraction(1, 10), "cumulative_error_over_cap", False), (rate, basis["why"], raised))


if __name__ == "__main__":
    unittest.main()
