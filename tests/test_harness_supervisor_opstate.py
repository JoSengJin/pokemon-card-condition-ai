"""운영 상태(opstate): 우선순위 모든 쌍, 원자 저장·전이 장부, 자동 해제 금지, 손상 시 fail-closed, 정지 상태에서 Supervisor가 아무것도 시작하지 않음."""
import itertools
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from harness import ledger, opstate, queue, supervisor
from tests.test_harness_supervisor_kit import Clock, events, llm_task, make_fake, runs
from tests.test_harness_runner_kit import task

ORDER = [opstate.INTEGRITY_HALT, opstate.USER_STOPPED, opstate.DONE, opstate.BUDGET_EXCEEDED]  # 높은 것부터
LIMITS = [opstate.RATE_LIMITED_SHORT, opstate.RATE_LIMITED_WEEKLY, opstate.RATE_LIMITED_UNKNOWN]


class OpStateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_priority_every_pair_both_orders_and_exclusive_limits(self):
        levels = [[n] for n in ORDER] + [LIMITS]
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RUNNING)
        checked = 0
        for hi_i, lo_i in itertools.combinations(range(len(levels)), 2):
            for high, low in itertools.product(levels[hi_i], levels[lo_i]):
                for first, second in ((high, low), (low, high)):
                    root = tempfile.mkdtemp()
                    opstate.set_condition(root, first, 1.0, "test", "pair")
                    opstate.set_condition(root, second, 2.0, "test", "pair")
                    self.assertEqual(opstate.effective(opstate.load(root)), high, (first, second))
                    opstate.clear_by_user(root, high, 3.0, "pair check")  # 위 상태를 풀면 아래 상태가 드러난다
                    self.assertEqual(opstate.effective(opstate.load(root)), low, (first, second))
                    checked += 1
        self.assertEqual(checked, 2 * (6 + 4 * 3))  # 네 정지 상태끼리 6쌍 + 정지 상태×한도 3종 12쌍, 양쪽 순서
        for name in LIMITS:  # 한도 조건끼리는 같은 단계: 나중 것이 앞의 것을 대체한다(한 번에 하나)
            opstate.set_condition(self.root, name, 1.0, "supervisor", "limit")
            self.assertEqual(list(opstate.load(self.root)["conditions"]), [name])
        opstate.set_condition(self.root, opstate.USER_STOPPED, 2.0, "user", "stop")
        self.assertEqual(set(opstate.load(self.root)["conditions"]), {opstate.USER_STOPPED, opstate.RATE_LIMITED_UNKNOWN})

    def test_auto_clear_refused_for_halting_and_exhausted(self):
        for name in ORDER:
            opstate.set_condition(self.root, name, 1.0, "test", "x")
            with self.assertRaises(opstate.OpStateError):
                opstate.clear_auto(self.root, name, 2.0, "auto")
            self.assertIn(name, opstate.load(self.root)["conditions"])
        opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "x", {"exhausted": True})
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_auto(self.root, opstate.RATE_LIMITED_SHORT, 2.0, "auto")
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_by_user(self.root, opstate.USER_STOPPED, 3.0, "why", actor="supervisor")
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_by_user(self.root, opstate.USER_STOPPED, 3.0, "")
        self.assertTrue(opstate.clear_by_user(self.root, opstate.USER_STOPPED, 3.0, "사람 확인"))
        opstate.set_condition(self.root, opstate.RATE_LIMITED_WEEKLY, 4.0, "supervisor", "limit", {"exhausted": False})
        self.assertTrue(opstate.clear_auto(self.root, opstate.RATE_LIMITED_WEEKLY, 5.0, "시각 도달"))
        cleared = [e["data"] for e in events(self.root, "opstate_transition") if e["data"]["op"] == "clear"]
        self.assertEqual([(c["condition"], c["actor"]) for c in cleared],
                         [(opstate.USER_STOPPED, "user"), (opstate.RATE_LIMITED_WEEKLY, "supervisor")])

    def test_atomic_save_and_transition_ledger(self):
        opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "limit", {"next_try_at": 9.0})
        path = os.path.join(self.root, opstate.OPSTATE)
        before = pathlib.Path(path).read_bytes()
        with mock.patch("harness.jsonio.os.replace", side_effect=OSError("교체 직전 실패")):
            with self.assertRaises(OSError):
                opstate.set_condition(self.root, opstate.DONE, 2.0, "test", "x")
        self.assertEqual(pathlib.Path(path).read_bytes(), before)  # 교체 전 실패: 이전 내용 그대로(반쯤 쓴 파일 없음)
        opstate.set_condition(self.root, opstate.DONE, 3.0, "test", "목표 충족")
        rows = [e["data"] for e in events(self.root, "opstate_transition")]
        self.assertEqual([(r["condition"], r["effective_before"], r["effective_after"]) for r in rows],
                         [(opstate.RATE_LIMITED_SHORT, opstate.RUNNING, opstate.RATE_LIMITED_SHORT),
                          (opstate.DONE, opstate.RATE_LIMITED_SHORT, opstate.DONE)])
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])
        self.assertEqual(opstate.load(self.root)["conditions"][opstate.RATE_LIMITED_SHORT]["next_try_at"], 9.0)

    def test_unreadable_state_fails_closed(self):
        os.makedirs(os.path.join(self.root, "supervisor"))
        path = os.path.join(self.root, opstate.OPSTATE)
        with open(path, "w") as handle:
            handle.write("{깨진")
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.INTEGRITY_HALT)
        with self.assertRaises(opstate.OpStateError):
            opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "x")
        with open(path, "w") as handle:
            handle.write('{"conditions": {"MADE_UP": {}}}')
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.INTEGRITY_HALT)
        self.assertEqual(pathlib.Path(path).read_text(), '{"conditions": {"MADE_UP": {}}}')  # 증거를 덮어쓰지 않는다

    def test_integrity_halt_survives_broken_ledger(self):
        opstate.set_condition(self.root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "x")
        with open(os.path.join(self.root, "ledger.jsonl"), "a") as handle:
            handle.write('{"broken": true}\n')
        with self.assertRaises(ledger.LedgerError):
            opstate.set_condition(self.root, opstate.USER_STOPPED, 2.0, "user", "x")
        info = opstate.set_condition(self.root, opstate.INTEGRITY_HALT, 3.0, "supervisor", "장부 손상")
        self.assertIn("ledger_error", info)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.INTEGRITY_HALT)

    def test_supervisor_starts_nothing_in_halting_states(self):
        claude, log, env = make_fake(self, [{"do": "success"}] * 4)
        for name in ORDER:
            root = tempfile.mkdtemp()
            llm_task(root)
            py = queue.enqueue(root, task("py"), 1.0)
            opstate.set_condition(root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "x", {"next_try_at": 0.0})
            opstate.set_condition(root, name, 1.0, "test", "정지")
            clock = Clock(1000.0)
            out = supervisor.run(root, claude, "tests.test_harness_executors:EXECUTORS", max_cycles=4, poll_s=5,
                                 now_fn=clock.now, sleep_fn=clock.sleep, env=env)
            self.assertEqual((out["state"], out["claude_runs"], out["python_runs"]), (name, 0, 0))
            self.assertFalse(os.path.exists(os.path.join(root, "tasks", py, "done.json")))
            self.assertEqual(set(opstate.load(root)["conditions"]), {name, opstate.RATE_LIMITED_SHORT})  # 자동 해제 없음
        self.assertEqual(runs(log), [])


if __name__ == "__main__":
    unittest.main()
