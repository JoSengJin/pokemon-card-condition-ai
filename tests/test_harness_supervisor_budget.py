"""개발 예산(D-2): 주당 실험 20·비전 300구역·봉인 주기당 승격 2, 추가 전용 장부, 주 경계는 준 시각, 초과 시 BUDGET_EXCEEDED·자동 재개 금지."""
import calendar
import os
import tempfile
import threading
import unittest

from harness import budget, ledger, opstate, supervisor
from tests.test_harness_supervisor_kit import Clock, events, llm_task, make_fake, runs

MON = calendar.timegm((2030, 1, 7, 0, 0, 0))  # 2030-01-07 월요일 00:00 UTC
WED = MON + 2 * 86400 + 3600


class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_weekly_experiments_20_then_exceeded_and_frozen(self):
        self.assertEqual(budget.LIMITS, {"experiment": ("week", 20), "vision_zone": ("week", 300), "promotion": ("seal_cycle", 2)})
        for i in range(20):
            self.assertTrue(budget.charge(self.root, "experiment", 1, WED + i)["ok"])
        over = budget.charge(self.root, "experiment", 1, WED + 30)
        self.assertEqual((over["ok"], over["reason"], over["used"], over["limit"]), (False, "limit", 20, 20))
        info = opstate.load(self.root)["conditions"][opstate.BUDGET_EXCEEDED]
        self.assertEqual((info["kind"], info["period"], info["used"]), ("experiment", "week:2030-W02", 20))
        self.assertEqual([e["data"]["kind"] for e in events(self.root, path=opstate.NOTIFICATIONS)], ["budget_exceeded"])
        later = budget.charge(self.root, "vision_zone", 1, WED + 8 * 86400)  # 다음 주·다른 항목도 재승인 전에는 거절
        self.assertEqual((later["ok"], later["reason"]), (False, "halted:BUDGET_EXCEEDED"))
        self.assertEqual(len(events(self.root, "charge", budget.BUDGET)), 20)  # 초과분은 기록하지 않는다
        self.assertEqual(ledger.verify(os.path.join(self.root, budget.BUDGET)), [])

    def test_vision_zones_300_and_amount_validation(self):
        self.assertTrue(budget.charge(self.root, "vision_zone", 299, WED)["ok"])
        self.assertEqual(budget.charge(self.root, "vision_zone", 1, WED)["used"], 300)
        self.assertFalse(budget.charge(self.root, "vision_zone", 1, WED)["ok"])
        for bad in (0, -1, 1.5, True, "1"):
            with self.assertRaises(budget.BudgetError):
                budget.charge(tempfile.mkdtemp(), "vision_zone", bad, WED)
        with self.assertRaises(budget.BudgetError):
            budget.charge(tempfile.mkdtemp(), "unknown_kind", 1, WED)

    def test_promotions_per_seal_cycle_and_user_reapproval(self):
        with self.assertRaises(budget.BudgetError):
            budget.charge(self.root, "promotion", 1, WED)
        self.assertTrue(budget.charge(self.root, "promotion", 1, WED, seal_cycle="seal-1")["ok"])
        self.assertTrue(budget.charge(self.root, "promotion", 1, WED + 9e6, seal_cycle="seal-1")["ok"])  # 주와 무관
        self.assertFalse(budget.charge(self.root, "promotion", 1, WED, seal_cycle="seal-1")["ok"])
        self.assertFalse(budget.charge(self.root, "promotion", 1, WED, seal_cycle="seal-2")["ok"])  # 정지 중
        opstate.clear_by_user(self.root, opstate.BUDGET_EXCEEDED, WED, "예산 재승인")
        self.assertTrue(budget.charge(self.root, "promotion", 1, WED, seal_cycle="seal-2")["ok"])
        self.assertFalse(budget.charge(self.root, "promotion", 1, WED, seal_cycle="seal-1")["ok"])  # 주기 사용량은 그대로

    def test_week_boundary_uses_given_time(self):
        self.assertEqual(budget.period_of("experiment", MON - 1), "week:2030-W01")
        self.assertEqual(budget.period_of("experiment", MON), "week:2030-W02")
        for i in range(20):
            self.assertTrue(budget.charge(self.root, "experiment", 1, MON - 1 - i)["ok"])
        self.assertTrue(budget.charge(self.root, "experiment", 1, MON)["ok"])
        self.assertEqual(budget.usage(self.root, "experiment", "week:2030-W01"), 20)
        with self.assertRaises(budget.BudgetError):
            budget.period_of("experiment", "2030-01-07")

    def test_supervisor_never_resumes_from_budget_exceeded(self):
        claude, log, env = make_fake(self, [{"do": "success"}])
        llm_task(self.root)
        for i in range(21):
            budget.charge(self.root, "experiment", 1, WED + i)
        clock = Clock(WED + 7 * 86400)  # 다음 주가 되어도
        out = supervisor.run(self.root, claude, max_cycles=5, poll_s=3600, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
        self.assertEqual((out["state"], out["claude_runs"], runs(log)), (opstate.BUDGET_EXCEEDED, 0, []))
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_auto(self.root, opstate.BUDGET_EXCEEDED, clock.now(), "auto")
        self.assertIn(opstate.BUDGET_EXCEEDED, opstate.load(self.root)["conditions"])

    def test_tampered_ledger_and_concurrent_charges(self):
        workers = [threading.Thread(target=budget.charge, args=(self.root, "experiment", 1, WED)) for _ in range(30)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(budget.usage(self.root, "experiment", "week:2030-W02"), 20)  # 확인·기록 사이 경합 없음
        path = os.path.join(self.root, budget.BUDGET)
        with open(path, encoding="utf-8") as handle:
            rows = handle.read().splitlines()
        rows[3] = rows[3].replace('"amount": 1', '"amount": 0')
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")
        with self.assertRaises(budget.BudgetError):
            budget.usage(self.root, "experiment", "week:2030-W02")


if __name__ == "__main__":
    unittest.main()
