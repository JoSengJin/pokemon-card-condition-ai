"""VS4 비전 구역 차감의 장애·우회: 실행 전에 멈추는 경로는 차감하지 않고, 재시도·재개·새 세션과 차감 직전·직후 실제 SIGKILL 뒤 재시작에서
누락·중복이 없다. 합성 root·가짜 claude만 쓴다.
"""
import hashlib
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from harness import claude_job, claude_run, opstate, route_history, supervisor
from harness.jsonio import write_json
from tests.test_harness_resume_kit import allow_resume
from tests.test_harness_supervisor_kit import runs
from tests.test_harness_support import REPO
from tests.test_harness_vs4_vision import charged, job_of, world

# argv: root claude source point. before_charge | after_charge(장부·꼬리까지 쓴 뒤 반환 전) | after_job_saved(running 저장 뒤 claude 시작 전)
KILL = r'''
import os, signal, sys
from harness import budget, claude_run, supervisor
root, claude, source, point = sys.argv[1:5]
def die(*a, **k):
    os.kill(os.getpid(), signal.SIGKILL)
real = budget.charge
if point == "before_charge":
    budget.charge = die
elif point == "after_charge":
    budget.charge = lambda *a, **k: (real(*a, **k), die())
else:
    claude_run.run_once = die
supervisor.run(root, claude, max_cycles=1, source_root=source)
'''



class VisionChargeFaultTest(unittest.TestCase):
    def test_paths_that_stop_before_the_run_do_not_charge(self):
        cases = {"input_refused": {"extra": {"missing.txt": "a" * 64}}, "resume_disabled": {}, "resume_cap": {}, "halting": {},
                 "declaration_dir": {}, "route_pending": {}, "route_history_invalid": {}, "adopted": {}}
        for name, options in cases.items():
            with self.subTest(name):
                root, key, claude, log, env, source = world(self, **options)
                job, task_dir = claude_job.pick(root, 1.0), os.path.join(root, "tasks", key)
                if name.startswith("resume"):
                    job.update(status="rate_limited", session_id="s", crash_resumes=2 if name == "resume_cap" else 0)
                if name == "halting":
                    opstate.set_condition(root, opstate.USER_STOPPED, 2.0, "user", "RC 중단")
                if name == "declaration_dir":
                    os.makedirs(os.path.join(task_dir, "out", ".harness_complete.json", "x"))
                if name == "adopted":
                    os.makedirs(os.path.join(task_dir, "out"))
                    with open(os.path.join(task_dir, "out", "v.md"), "w", encoding="utf-8") as handle:
                        handle.write("x")
                    write_json(os.path.join(task_dir, "complete.json"), {"task_key": key, "outputs": {"v.md": hashlib.sha256(b"x").hexdigest()}})
                broken = {"route_pending": {"return_value": [{"cause": "quality_gate_miss"}] * 3},
                          "route_history_invalid": {"side_effect": route_history.RouteHistoryError("손상")}}.get(name)
                with mock.patch.object(route_history, "history", **(broken or {"return_value": []})), \
                        allow_resume(self, "misanalysis_general" if name == "resume_cap" else "unused"):
                    outcome = claude_job.execute(root, job, claude, time.time, env=env, source_root=source)
                want = {"input_refused": "failed", "halting": "halted", "adopted": "adopted"}.get(name, "held")
                self.assertEqual((outcome["kind"], runs(log), charged(root)), (want, [], []), outcome)

    def test_retry_resume_and_new_session_of_the_same_task_charge_once(self):
        root, key, claude, log, env, source = world(self, [{"do": "limit", "after": 1}, {"do": "no_session"}, {"do": "success"}])
        with allow_resume(self, "misanalysis_general"), mock.patch.object(claude_run, "session_unrecoverable", return_value=True):
            supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
            time.sleep(1.2)
            supervisor.run(root, claude, max_cycles=3, poll_s=0.2, env=env, source_root=source)  # --resume 실패 → 새 세션
        self.assertEqual([bool(r["resume"]) for r in runs(log)], [False, True, False])
        self.assertEqual((charged(root), job_of(root, key)["status"]), ([(key, 2)], "done"))
        root, key, claude, log, env, source = world(self, [{"do": "fail"}, {"do": "success"}])
        supervisor.run(root, claude, max_cycles=2, poll_s=0, env=env, source_root=source)
        os.remove(claude_job.paths(root, key)[0])  # 사람 해제(기존의 유일한 방법): 새 세션으로 다시 실행
        supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual((len(runs(log)), charged(root), job_of(root, key)["status"]), (2, [(key, 2)], "done"))

    def test_real_sigkill_around_the_charge_neither_loses_nor_doubles_it(self):
        for point, rows in (("before_charge", 0), ("after_charge", 1), ("after_job_saved", 1)):
            with self.subTest(point):
                root, key, claude, log, env, source = world(self)
                child = subprocess.run([sys.executable, "-c", KILL, root, claude, source, point], cwd=REPO, env=env,
                                       capture_output=True, text=True, timeout=120)
                self.assertEqual(child.returncode, -signal.SIGKILL, child.stderr)
                self.assertEqual((len(charged(root)), runs(log)), (rows, []))
                supervisor.run(root, claude, max_cycles=2, poll_s=0, env=env, source_root=source)
                if point == "after_job_saved":  # running 저장 뒤 pid 기록 전 사망: 기존 규칙대로 사람 확인 대기
                    self.assertEqual((job_of(root, key)["hold_reason"], runs(log)), ("pid_record_mismatch", []))
                    os.remove(claude_job.paths(root, key)[0])
                    supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
                self.assertEqual((len(runs(log)), charged(root), job_of(root, key)["status"]), (1, [(key, 2)], "done"))



if __name__ == "__main__":
    unittest.main()
