"""한도 감지·재개(가짜 claude = 실제 하위 프로세스): resetsAt 뒤 --resume, --resume 실패 → 새 세션, 시각 미상 → 60·300·900초 3회 뒤 정지·알림,
USER_STOPPED는 한도가 지나도 재개 안 함, 한도 중에도 Python 작업은 계속."""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from harness import claude_job, opstate, queue, states, supervisor
from tests.test_harness_runner_kit import task
from tests.test_harness_supervisor_kit import Clock, events, llm_task, make_fake, runs

EXEC = "tests.test_harness_executors:EXECUTORS"


def state(root, key):
    return states.classify(os.path.join(root, "tasks", key), 0, lambda held: False)


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_known_reset_waits_then_resumes_same_session(self):
        claude, log, env = make_fake(self, [{"do": "limit", "reset": "sec", "after": 2}, {"do": "success"}])
        key = llm_task(self.root)
        out = supervisor.run(self.root, claude, max_cycles=5, poll_s=3, env=env)
        first, second = runs(log)
        self.assertIsNone(first["resume"])
        self.assertEqual(second["resume"], first["session_id"])  # 같은 세션을 --resume으로 이어간다
        self.assertGreaterEqual(second["t"], first["reset"])  # 저장한 재개 시각 이후에만 재개한다
        self.assertEqual((out["outcomes"], out["state"], state(self.root, key)), (["rate_limited", "done"], opstate.RUNNING, states.VERIFIED))
        moves = [(e["data"]["op"], e["data"]["condition"], e["data"]["actor"]) for e in events(self.root, "opstate_transition")]
        self.assertEqual(moves, [("set", opstate.RATE_LIMITED_SHORT, "supervisor"), ("clear", opstate.RATE_LIMITED_SHORT, "supervisor")])
        limit = events(self.root, "opstate_transition")[0]["data"]["extra"]
        self.assertAlmostEqual(limit["next_try_at"], first["reset"], places=3)
        self.assertFalse(any("--continue" in r["argv"] or "-c" in r["argv"] for r in runs(log) + runs(log, "help")))

    def test_resume_failure_opens_new_session_from_ledger_state(self):
        claude, log, env = make_fake(self, [{"do": "limit", "after": 1}, {"do": "no_session"}, {"do": "success"}])
        key = llm_task(self.root)
        supervisor.run(self.root, claude, max_cycles=5, poll_s=3, env=env)
        first, failed, fresh = runs(log)
        self.assertEqual(failed["resume"], first["session_id"])
        self.assertIsNone(fresh["resume"])
        self.assertNotEqual(fresh["session_id"], first["session_id"])
        self.assertIn("이어받지 못해", fresh["prompt"])
        self.assertIn(os.path.join(self.root, "ledger.jsonl"), fresh["prompt"])
        self.assertEqual([e["data"]["session_id"] for e in events(self.root, "claude_resume_failed")], [first["session_id"]])
        self.assertEqual(state(self.root, key), states.VERIFIED)
        with open(os.path.join(self.root, claude_job.JOB)) as handle:
            self.assertEqual(json.load(handle)["session_id"], fresh["session_id"])

    def test_unknown_reset_backs_off_three_times_then_stops_and_notifies(self):
        steps = [{"do": "limit", "reset": "garbage"}, {"do": "limit", "reset": "none", "type": None},
                 {"do": "limit", "reset": "past"}, {"do": "limit", "reset": "garbage", "field": "resetsAtSeconds"},
                 {"do": "success"}]
        claude, log, env = make_fake(self, steps)
        llm_task(self.root)
        clock = Clock(time.time())
        supervisor.run(self.root, claude, max_cycles=40, poll_s=120, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
        self.assertEqual(len(runs(log)), 4)  # 처음 1회 + 다시 시도 3회, 그 뒤로는 실행하지 않는다
        starts = [e["ts"] for e in events(self.root, "claude_run_started")]
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertEqual(len(gaps), 3)
        for gap, want in zip(gaps, (60, 300, 900)):  # 간격을 늘려 가며 다시 시도한다(설계값을 시험에 고정)
            self.assertGreaterEqual(gap, want)
            self.assertLess(gap, want + 1)
        cond = opstate.load(self.root)["conditions"]
        name, info = next(iter(cond.items()))
        self.assertEqual((len(cond), name, info["exhausted"], info["next_try_at"], info["resets_at"]),
                         (1, opstate.RATE_LIMITED_SHORT, True, None, None))
        notes = [e["data"]["kind"] for e in events(self.root, path=opstate.NOTIFICATIONS)]
        self.assertEqual(notes, ["rate_limit_unknown_exhausted"])
        kinds = [e["data"]["condition"] for e in events(self.root, "opstate_transition") if e["data"]["op"] == "set"]
        self.assertEqual(kinds[1], opstate.RATE_LIMITED_UNKNOWN)  # rateLimitType 없음: 단기로 두지 않고 미상
        with self.assertRaises(opstate.OpStateError):
            opstate.clear_auto(self.root, name, clock.now(), "auto")

    def test_user_stopped_blocks_resume_after_reset_passes(self):
        claude, log, env = make_fake(self, [{"do": "limit", "after": 1}, {"do": "success"}])
        key = llm_task(self.root)
        supervisor.run(self.root, claude, max_cycles=1, env=env)
        opstate.set_condition(self.root, opstate.USER_STOPPED, time.time(), "user", "RC 중단")
        time.sleep(1.2)
        out = supervisor.run(self.root, claude, max_cycles=4, poll_s=0.2, env=env)
        self.assertEqual((len(runs(log)), out["state"], out["claude_runs"]), (1, opstate.USER_STOPPED, 0))
        self.assertIn(opstate.RATE_LIMITED_SHORT, opstate.load(self.root)["conditions"])
        opstate.clear_by_user(self.root, opstate.USER_STOPPED, time.time(), "사용자 재개")
        supervisor.run(self.root, claude, max_cycles=3, poll_s=0.2, env=env)
        self.assertEqual((len(runs(log)), state(self.root, key)), (2, states.VERIFIED))
        self.assertEqual(runs(log)[1]["resume"], runs(log)[0]["session_id"])

    def test_python_tasks_continue_while_rate_limited(self):
        claude, log, env = make_fake(self, [{"do": "limit", "after": 600}, {"do": "success"}])
        marks = tempfile.mkdtemp()
        key = llm_task(self.root)
        clock = Clock(time.time())
        with mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks}):
            supervisor.run(self.root, claude, EXEC, max_cycles=1, now_fn=clock.now, sleep_fn=clock.sleep, env=env)
            self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RATE_LIMITED_SHORT)
            py = [queue.enqueue(self.root, task(n), clock.now()) for n in ("a", "b")]
            after_llm = queue.enqueue(self.root, task("c", depends_on=[key]), clock.now())
            out = supervisor.run(self.root, claude, EXEC, max_cycles=3, poll_s=30, now_fn=clock.now,
                                 sleep_fn=clock.sleep, env=env)
        self.assertEqual([state(self.root, k) for k in py], [states.VERIFIED, states.VERIFIED])
        self.assertEqual((state(self.root, after_llm), state(self.root, key)), (states.PENDING, states.PENDING))
        self.assertEqual((len(runs(log)), out["state"], out["claude_runs"]), (1, opstate.RATE_LIMITED_SHORT, 0))
        self.assertEqual(sorted(os.listdir(marks))[0][:6], "a-run-")


if __name__ == "__main__":
    unittest.main()
