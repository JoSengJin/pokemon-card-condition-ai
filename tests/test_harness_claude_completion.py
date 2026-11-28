"""2단계 Claude 작업의 완료 표시·중복 방지(가짜 claude = 실제 하위 프로세스, Supervisor kill -9 주입):
하네스 완료 표시 전에 죽으면 완료로 보지 않음(선언만으로는 반영 안 함), done.json 직후 죽으면 다시 실행·반영하지 않고 done으로 닫음,
실행 중 사망 재개는 작업당 2회까지, 이미 VERIFIED면 settle이 다시 complete하지 않음, 선언 없는 성공은 대기."""
import os
import subprocess
import sys
import tempfile
import time
import unittest

from harness import claude_job, lease, states, supervisor
from harness.jsonio import read_json, write_json
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_supervisor_kit import REPO, events, llm_task, make_fake, runs

KILL = r'''
import os, sys
from harness import claude_job, ledger, supervisor
root, claude, point = sys.argv[1:4]
real_append = ledger.append
def append(path, ts, event, data):
    if point == "done_json" and event == "completed":
        os.kill(os.getpid(), 9)  # done.json을 쓴 직후, 장부 completed 줄 전에 죽는다
    return real_append(path, ts, event, data)
if point == "before_marker":  # claude는 성공 종료(선언까지 씀)했지만 하네스가 해시 완료 표시를 쓰기 전에 죽는다
    claude_job.manifest.build = lambda *a, **k: os.kill(os.getpid(), 9)
ledger.append = append
supervisor.run(root, claude, max_cycles=1)
'''


def crashed(case, point, scenario):
    """가짜 claude 시나리오로 Supervisor를 point에서 kill -9. (root, key, 가짜 claude, 로그, env)."""
    root = tempfile.mkdtemp()
    claude, log, env = make_fake(case, scenario)
    key = llm_task(root)
    done = subprocess.run([sys.executable, "-c", KILL, root, claude, point], cwd=REPO, env=env, check=False, timeout=60)
    case.assertEqual(done.returncode, -9)
    return root, key, claude, log, env


def queue_state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class ClaudeCompletionTest(unittest.TestCase):
    def test_declaration_without_harness_marker_is_not_adopted(self):
        root, key, claude, log, env = crashed(self, "before_marker", [{"do": "success"}, {"do": "success"}])
        self.assertTrue(os.path.exists(os.path.join(root, "tasks", key, "out", ".harness_complete.json")))
        self.assertIsNone(states.facts(os.path.join(root, "tasks", key))["completion"])
        with allow_resume(self, "misanalysis_general"):
            supervisor.run(root, claude, max_cycles=3, poll_s=0.1, env=env)
        self.assertEqual([r["resume"] is not None for r in runs(log)], [False, True])  # 반영하지 않고 같은 세션을 재개했다
        self.assertEqual(events(root, "claude_completion_adopted"), [])
        self.assertEqual(queue_state(root, key), states.VERIFIED)

    def test_death_after_done_record_is_closed_as_done_without_rerun(self):
        root, key, claude, log, env = crashed(self, "done_json", [{"do": "success"}, {"do": "success"}])
        out = supervisor.run(root, claude, max_cycles=2, poll_s=0.1, env=env)
        self.assertEqual((len(runs(log)), out["claude_runs"], queue_state(root, key)), (1, 0, states.VERIFIED))
        self.assertEqual(read_json(claude_job.paths(root, key)[0])["status"], "done")
        self.assertEqual(events(root, "completed"), [])  # 다시 반영하지 않았다(빠진 장부 줄은 상태 파일이 정본)

    def test_crash_resume_is_capped_per_task(self):
        claude, log, env = make_fake(self, [{"do": "success"}])
        for resumed in (1, 2):  # 이미 재개한 횟수
            root = tempfile.mkdtemp()
            key = llm_task(root)
            jobfile, pidfile = claude_job.paths(root, key)
            job = claude_job.pick(root, 1.0)
            write_json(jobfile, dict(job, status="running", mode="new", session_id="s-1", run_token="t", crash_resumes=resumed))
            write_json(pidfile, {"pid": 999999, "boot_id": lease.boot_id(), "session_id": "s-1", "mode": "new", "run_token": "t"})
            picked = claude_job.pick(root, 2.0)  # 실행 중 Supervisor가 죽었고 claude pid도 죽었다
            with allow_resume(self, "misanalysis_general"):
                outcome = claude_job.execute(root, picked, claude, time.time, env=env)
            status = claude_job.settle(root, picked, outcome, time.time())
            if resumed == 1:
                self.assertEqual((status, read_json(jobfile)["crash_resumes"], runs(log)[-1]["resume"]), ("done", 2, "s-1"))
            else:
                self.assertEqual((status, queue_state(root, key)), ("blocked", states.PENDING))
                self.assertIn("too_many_interrupts", read_json(jobfile)["hold_reason"])
        self.assertEqual(len(runs(log)), 1)  # 한도(recovery.MAX_INTERRUPTS=2)를 넘은 쪽은 claude를 부르지 않았다

    def test_success_without_declaration_waits_and_verified_task_is_not_completed_again(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success", "declare": False}])
        key = llm_task(root)
        out = supervisor.run(root, claude, max_cycles=2, poll_s=0.1, env=env)
        self.assertEqual((out["outcomes"], queue_state(root, key)), (["blocked"], states.PENDING))
        self.assertIn("completion_marker_missing", read_json(claude_job.paths(root, key)[0])["hold_reason"])
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success"}])
        key = llm_task(root)
        out = supervisor.run(root, claude, max_cycles=1, env=env)
        job = read_json(claude_job.paths(root, key)[0])
        again = claude_job.settle(root, job, {"kind": "success", "mode": "new", "result": {}}, 9.0)  # 같은 반영을 한 번 더
        self.assertEqual((out["outcomes"], again, len(events(root, "completed"))), (["done"], "done", 1))


if __name__ == "__main__":
    unittest.main()
