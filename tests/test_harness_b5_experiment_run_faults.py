"""B5-4·B5-8 연결의 장애·진입점: 같은 논리 실험의 재시도는 다시 차감·취소하지 않고, 차감 직후·취소 직전·직후 실제 SIGKILL 뒤 재시작으로 예산을
우회할 수 없으며, 실제 진입점(python -m harness.supervisor 1회차, sandbox-exec)이 등록한 어댑터를 부른다(연결 C 증거, 합성 root·가짜 experiment).
**실제 ./experiment 연결: 미완료**(sandbox가 원본 저장소 쓰기를 막아 기록을 남기는 실행은 결과 불명이 된다).
"""
import functools
import os
import signal
import subprocess
import sys
import unittest

from harness import budget, dedupe, experiment_exec, queue, runner, sandbox, states
from tests import harness_depth_kit as kit
from tests.test_harness_b5_experiment_run import CLOCK, NOW, _state, _task, _world
from tests.test_harness_supervisor_kit import events

KILL = r'''
import os, signal, sys
sys.path.insert(0, sys.argv[1])
from harness import budget, experiment_exec, queue, runner
def die(*a, **k):
    os.kill(os.getpid(), signal.SIGKILL)
point = sys.argv[4]
if point == "after_charge":
    experiment_exec.run = die
elif point == "before_cancel":
    budget.cancel = die
elif point == "after_cancel":
    queue.fail = die
runner.drain(sys.argv[2], experiment_exec.EXECUTORS, now_fn=lambda: 1894000000.0, source_root=sys.argv[3])
'''


class ExperimentRunFaultTest(unittest.TestCase):
    def test_retry_of_the_same_logical_experiment_is_not_charged_again_nor_refunded(self):
        root, src, head = _world(self)
        key = queue.enqueue(root, _task(head, "busy"), NOW, source_root=src)
        calls = []

        def flaky(task, out_dir):  # 첫 시도는 인프라 장애(일시적), 둘째 시도는 실행 안 됨(not_started)
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionError("network down")
            return experiment_exec.execute(task, out_dir)
        first = runner.drain(root, {"experiment": flaky}, now_fn=CLOCK, source_root=src)
        self.assertEqual((len(calls), first["stopped"]), (1, {key: "await_result"}))  # 실험은 자동 재시도하지 않는다(기존 정책)
        folder = os.path.join(root, "tasks", key)
        os.rename(os.path.join(folder, "failures"), os.path.join(folder, "failures-checked"))  # 사람이 원인을 확인하고 대기를 푼 것(수동 절차 흉내)
        os.remove(os.path.join(folder, "awaiting.json"))
        runner.drain(root, {"experiment": flaky}, now_fn=CLOCK, source_root=src)
        self.assertEqual((len(calls), _state(root, key)), (2, states.FAILED))
        # 둘째 시도의 not_started는 첫 시도가 한 차감(실행됐을 수 있음)을 취소하지 않는다: 이번 시도가 새로 한 차감만 취소한다
        self.assertEqual([r["event"] for r in events(root, path=budget.BUDGET)], ["charge"])

    def test_kill_after_charge_and_around_cancel_cannot_bypass_the_budget_on_restart(self):
        for point, used in (("after_charge", 1), ("before_cancel", 1), ("after_cancel", 0)):
            with self.subTest(point=point):
                root, src, head = _world(self)
                key = queue.enqueue(root, _task(head, "completed" if point == "after_charge" else "busy"), NOW, source_root=src)
                child = subprocess.run([sys.executable, "-c", KILL, kit.REPO, root, src, point], capture_output=True, timeout=120)
                self.assertEqual(child.returncode, -signal.SIGKILL, child.stderr[-500:])
                again = runner.drain(root, experiment_exec.EXECUTORS, now_fn=functools.partial(float, NOW + 5), source_root=src)
                self.assertEqual((again["executed"], _state(root, key)), (0, states.INTERRUPTED), again)  # 결과 확인 대기: 다시 실행 안 함
                self.assertEqual(budget.usage(root, "experiment", budget.period_of("experiment", NOW)), used)
                self.assertEqual(len(events(root, "charge", budget.BUDGET)), 1)
                log = os.path.join(src, "artifacts", "argv.log")
                self.assertEqual(len(open(log).read().splitlines()) if os.path.exists(log) else 0, 0 if point == "after_charge" else 1)
                if point == "after_charge":  # 사람이 결과 불명을 확인하고 대기를 푼 뒤 같은 논리 실험을 이어 실행: 다시 빼지 않는다
                    for name in ("lease.json", "awaiting.json"):
                        os.remove(os.path.join(root, "tasks", key, name))
                    resumed = runner.drain(root, experiment_exec.EXECUTORS, now_fn=CLOCK, source_root=src)
                    self.assertEqual(resumed["done"], [key], resumed)
                    self.assertEqual([r["event"] for r in events(root, path=budget.BUDGET)], ["charge"])

    def test_supervisor_entry_point_runs_the_registered_adapter_in_the_sandbox(self):
        """연결(C) 증거: 실제 진입점 python -m harness.supervisor 1회차, 실제 sandbox-exec, 가짜 experiment. 실제 ./experiment 연결은 미완료."""
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        for mode, want in (("busy", (["charge", "cancel"], states.FAILED)), ("completed", (["charge"], states.INTERRUPTED))):
            root, src, head = _world(self)
            key = queue.enqueue(root, _task(head, mode), NOW, source_root=src)
            done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--executors", "harness.experiment_exec:EXECUTORS",
                                   "--source-root", src, "--max-cycles", "1", "--poll", "0"], cwd=kit.REPO, capture_output=True, text=True,
                                  timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr[-800:])
            self.assertEqual(([r["event"] for r in events(root, path=budget.BUDGET)], _state(root, key)), want, mode)
            self.assertEqual(events(root, "charge", budget.BUDGET)[0]["data"]["key"], dedupe.logical_key(_task(head, mode)))
            self.assertEqual([e["data"]["task_key"] for e in events(root, "claimed")], [key])
            self.assertFalse(os.path.exists(os.path.join(src, "artifacts")), mode)  # sandbox가 원본 저장소 쓰기를 막았다(기록 없음)
            if mode == "busy":
                [drained] = events(root, "python_drain")
                self.assertEqual(drained["data"]["summary"]["failed"], [[key, "deterministic"]])
            else:  # 결과 불명은 실행 0건이어도 그 회차의 사유가 장부에 남는다. 대기 중인 다음 회차는 줄을 늘리지 않는다
                [drained] = events(root, "python_drain")
                self.assertTrue(drained["data"]["summary"]["stopped"][key].startswith("executor_killed:"), drained)
                again = subprocess.run(done.args, cwd=kit.REPO, capture_output=True, text=True, timeout=300)
                self.assertEqual((again.returncode, len(events(root, "python_drain"))), (0, 1), again.stderr[-800:])
        self.assertEqual(sorted(sandbox.sandboxed(root, "harness.experiment_exec:EXECUTORS")), ["experiment"])


if __name__ == "__main__":
    unittest.main()
