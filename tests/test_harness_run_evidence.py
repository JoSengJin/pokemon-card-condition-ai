"""1단계(증거 수집·실행 정지 감시): 가짜 claude(실제 하위 프로세스)로 stdout·stderr 대량 출력 교착 없음, 허용 필드만·비밀 가림,
무출력/총 시간 초과 시 프로세스 그룹 종료, 신호·실행 실패 원인, Python runner 총 시간 초과와 기본값."""
import functools
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from harness import claude_job, claude_run, evidence, lease, queue, states, supervisor
from tests.test_harness_runner_kit import task
from tests.test_harness_supervisor_kit import events, llm_task, make_fake, runs

ALLOWED = {"returncode", "signal", "cause", "outcome", "result_subtype", "is_error", "permission_denials", "rate_limit",
           "stderr_tail", "error", "options", "cwd", "duration_s", "last_event", "events", "bad_lines", "task_key", "mode",
           "run_token"}


def gone(pid, timeout=5.0):
    """pid가 timeout 안에 사라지면 True(부모가 죽어 launchd가 회수하는 시간을 기다린다)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not lease.pid_alive(pid):
            return True
        time.sleep(0.05)
    return False


def once(case, step, **limits):
    """가짜 claude를 기본 runner(제한 주입)로 한 번 실행한다. (run_once 결과, 손자 pid 또는 None)."""
    claude, log, env = make_fake(case, [step])
    runner = functools.partial(claude_run.default_runner, **limits)
    res = claude_run.run_once(claude, "작업", "sonnet", "medium", runner, env, session_id="s-1")
    pidfile = os.path.join(os.path.dirname(claude), "grandchild.pid")
    if not os.path.exists(pidfile):
        return res, None
    with open(pidfile, encoding="utf-8") as handle:
        return res, int(handle.read())


class EvidenceTest(unittest.TestCase):
    def test_flood_on_both_streams_does_not_deadlock_and_evidence_is_masked_and_bounded(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "noisy"}])
        llm_task(root)
        job = claude_job.pick(root, 1.0)
        outcome = claude_job.execute(root, job, claude, time.time, env=env)
        self.assertEqual((outcome["kind"], outcome["result"]["cause"]), ("failed", "unknown"))
        self.assertGreater(len(outcome["result"]["stderr"]), 300000)  # 두 흐름을 함께 끝까지 읽었다(교착 없음)
        [record] = [e["data"] for e in events(root, "claude_run_evidence")]
        self.assertLessEqual(set(record), ALLOWED)
        self.assertLessEqual(len(record["stderr_tail"]), evidence.STDERR_TAIL)
        text = json.dumps(record, ensure_ascii=False)
        for secret in ("sk-ant-secret0123456789", "abcdefgh", "zzz.yyy"):
            self.assertNotIn(secret, text)
        self.assertIn("[가림]", record["stderr_tail"])
        self.assertNotIn(runs(log)[0]["prompt"], text)  # 프롬프트 본문은 남기지 않는다
        self.assertEqual(record["options"][-2:], ["--session-id", job["session_id"]])
        self.assertEqual((record["outcome"], record["returncode"]), ("unknown", 1))

    def test_idle_and_total_timeouts_kill_the_whole_process_group(self):
        res, kid = once(self, {"do": "hang"}, idle_s=0.5, total_s=30)
        self.assertEqual((res["cause"], res["signal"], res["success"]), ("timeout_idle", 15, False))
        self.assertTrue(gone(kid))  # claude가 띄운 손자 프로세스도 끝났다
        started = time.monotonic()  # 출력이 계속 나와도 총 시간 제한은 적용된다
        res, kid = once(self, {"do": "trickle"}, idle_s=5, total_s=1)
        self.assertEqual(res["cause"], "timeout_total")
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(gone(kid))

    def test_signal_and_spawn_error_causes_and_outcomes(self):
        res, kid = once(self, {"do": "selfkill"}, idle_s=30, total_s=30)
        self.assertEqual((res["cause"], res["signal"], res["returncode"]), ("signal", 9, -9))
        self.assertTrue(gone(kid))
        missing = claude_run.run_once("/nonexistent/claude", "작업", "sonnet", "medium", env={}, session_id="s")
        self.assertEqual(missing["cause"], "spawn_error")
        contract = {"outputs": ["result.txt"]}
        self.assertEqual(evidence.outcome_of(tempfile.mkdtemp(), contract, missing), "not_started")

    def test_python_runner_total_timeout_kills_runner_and_records_cause(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        key = queue.enqueue(root, task("h", task_type="slow"), 1.0)
        with mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks, "HARNESS_SLOW": "hang"}):
            started = time.monotonic()
            code, executed = supervisor._python(root, "tests.test_harness_executors:EXECUTORS", 2.0, total_s=1.5)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual((code, executed), (-9, 0))
        [drain] = [e["data"] for e in events(root, "python_drain")]
        self.assertEqual((drain["cause"], drain["signal"]), ("timeout_total", 9))
        info = states.facts(os.path.join(root, "tasks", key))
        self.assertTrue(gone(info["held"]["pid"]))  # 작업권을 쥔 runner도 끝났고 작업권 기록이 남는다(INTERRUPTED 판정 대상)
        self.assertEqual(states.state_of(info, False), states.INTERRUPTED)

    def test_default_limits_are_configurable_and_do_not_cut_the_longest_known_experiment(self):
        self.assertGreater(supervisor.PYTHON_TOTAL_S, 113 * 60)  # 기존 실험 최대 113분은 정상 종료해야 한다
        self.assertLess(claude_run.IDLE_S, claude_run.TOTAL_S)
        parsed = supervisor._args(["--root", "r", "--claude-idle-s", "5", "--python-total-s", "9"])
        self.assertEqual(parsed["limits"], {"claude_idle_s": 5.0, "python_total_s": 9.0})
        self.assertNotIn("limits", supervisor._args(["--root", "r"]))


if __name__ == "__main__":
    unittest.main()
