"""실제 Supervisor 프로세스: kill -9 뒤 재시작해 같은 상태에서 이어감(대기 중·claude 실행 중), runner 종료 코드 3 → INTEGRITY_HALT."""
import os
import signal
import subprocess
import tempfile
import time
import unittest

from harness import ledger, opstate, queue, runner, states, supervisor
from tests.test_harness_runner_kit import task
from tests.test_harness_resume_kit import resumable_supervisor
from tests.test_harness_supervisor_kit import REPO, events, llm_task, make_fake, runs


def until(want, what, root, arg=None, timeout=30.0):
    """값이 want가 될 때까지 기다린다(실시간). what: opstate(유효 상태) | task(arg 작업의 큐 상태) | runs(arg 로그의 실행 수)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if what == "opstate":
            got = opstate.effective(opstate.load(root))
        elif what == "task":
            got = states.state_of(states.facts(os.path.join(root, "tasks", arg)), False)
        else:
            got = len(runs(arg))
        if got == want:
            return
        time.sleep(0.05)
    raise AssertionError("시간 안에 조건이 충족되지 않음: %s %r" % (what, want))


class SupervisorProcessTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def spawn(self, claude, env, *extra):
        # 재개 절차 시험: 하위 프로세스 Supervisor 안에서 이 유형의 자동 재개를 켠다(3단계 활성화 목록, 합성 증거)
        argv = resumable_supervisor(self, "misanalysis_general")
        proc = subprocess.Popen(argv + ["--root", self.root, "--claude-bin", claude, "--poll", "0.3", *extra],
                                cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc

    def test_kill9_while_waiting_then_restart_resumes(self):
        claude, log, env = make_fake(self, [{"do": "limit", "after": 3}, {"do": "success"}])
        key = llm_task(self.root)
        first = self.spawn(claude, env)
        until(opstate.RATE_LIMITED_SHORT, "opstate", self.root)
        os.kill(first.pid, signal.SIGKILL)
        first.wait()
        self.assertEqual(len(runs(log)), 1)
        self.spawn(claude, env)  # 새 프로세스: 파일 상태(opstate.json·claude.json)만으로 이어간다
        until(states.VERIFIED, "task", self.root, key)
        one, two = runs(log)
        self.assertEqual((two["resume"], two["session_id"]), (one["session_id"], None))
        self.assertGreaterEqual(two["t"], one["reset"])
        self.assertEqual(len(events(self.root, "claude_job_picked")), 1)  # 다시 고르지 않고 같은 작업을 이어간다
        self.assertEqual(ledger.verify(os.path.join(self.root, "ledger.jsonl")), [])

    def test_kill9_during_claude_run_does_not_double_run(self):
        claude, log, env = make_fake(self, [{"do": "success", "delay": 2}, {"do": "success"}])
        key = llm_task(self.root)
        first = self.spawn(claude, env)
        until(1, "runs", self.root, log)
        os.kill(first.pid, signal.SIGKILL)
        first.wait()
        self.spawn(claude, env)
        until(states.VERIFIED, "task", self.root, key)
        one, two = runs(log)
        self.assertGreaterEqual(two["t"], one["t"] + 2)  # 남은 claude(고아)가 끝날 때까지 겹쳐 실행하지 않았다
        self.assertEqual(two["resume"], one["session_id"])  # 실행 전에 저장한 세션 ID로 이어간다

    def test_runner_exit3_becomes_integrity_halt(self):
        self.assertEqual(supervisor.INTEGRITY_EXIT, runner.INTEGRITY_EXIT)
        claude, log, env = make_fake(self, [{"do": "success"}])
        llm_task(self.root)
        py = queue.enqueue(self.root, task("p"), 1.0)
        with open(os.path.join(self.root, "ledger.jsonl"), "a") as handle:
            handle.write('{"tampered": 1}\n')
        out = supervisor.run(self.root, claude, "tests.test_harness_executors:EXECUTORS", max_cycles=3, poll_s=0.01,
                             env=dict(env, HARNESS_MARK_DIR=tempfile.mkdtemp()))
        cond = opstate.load(self.root)["conditions"]
        self.assertEqual((out["state"], list(cond), out["python_runs"], out["claude_runs"]),
                         (opstate.INTEGRITY_HALT, [opstate.INTEGRITY_HALT], 1, 0))
        self.assertIn("종료 코드 3", cond[opstate.INTEGRITY_HALT]["reason"])
        self.assertEqual([e["data"]["kind"] for e in events(self.root, path=opstate.NOTIFICATIONS)], ["integrity_halt"])
        self.assertEqual((runs(log), states.state_of(states.facts(os.path.join(self.root, "tasks", py)), False)),
                         ([], states.PENDING))


if __name__ == "__main__":
    unittest.main()
