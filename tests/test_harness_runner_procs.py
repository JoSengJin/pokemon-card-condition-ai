"""runner 프로세스 시험: kill -9 뒤 새 runner(T2-crash), 두 runner 동시 drain(T2-twin). 실제 하위 프로세스."""
import glob
import json
import os
import pathlib
import signal
import sys
import tempfile
import time
import unittest

from harness import contract, ledger, lease, queue, states
from tests.test_harness_runner_kit import spawn_runner, task

T0 = 1_000_000.0


def pair(poison_type):
    """독 작업(비정상 종료)의 키가 정상 작업의 키보다 정렬상 앞서는 한 쌍. runner는 정렬 순서로 고르므로 가장 불리한 배치다."""
    i = 0
    while True:
        bad, fine = task("P%d" % i, task_type=poison_type), task("N%d" % i)
        if contract.task_key(bad) < contract.task_key(fine):
            return i, bad, fine
        i += 1


@unittest.skipUnless(sys.platform == "darwin", "runner는 실제 부팅 식별자(macOS kern.boottime)를 쓴다")
class RunnerProcessTest(unittest.TestCase):
    def test_kill9_during_a_task_then_a_new_runner_takes_over_without_touching_others(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            keys = {n: queue.enqueue(root, task(n, task_type="slow" if n == "S" else "calc"), T0) for n in ("S", "A", "B")}
            first = spawn_runner(root, marks, {"HARNESS_SLOW": "hang"})
            self.addCleanup(first.wait)
            self.addCleanup(first.kill)
            for _ in range(1000):  # S가 실행을 시작할 때까지
                if glob.glob(os.path.join(marks, "S-start-*")):
                    break
                time.sleep(0.02)
            self.assertTrue(glob.glob(os.path.join(marks, "S-start-*")))
            os.kill(first.pid, signal.SIGKILL)
            first.wait()
            first.stdout.close()
            tdir = os.path.join(root, "tasks", keys["S"])
            self.assertEqual(states.classify(tdir, T0, lease.is_alive), states.INTERRUPTED)  # 1단계 규칙: 죽은 작업권
            second = spawn_runner(root, marks, {"HARNESS_SLOW": "fast"})
            self.addCleanup(second.kill)
            summary = json.loads(second.communicate(timeout=120)[0])
            self.assertEqual((second.returncode, summary["failed"], summary["stopped"]), (0, [], {}))
            for key in keys.values():
                self.assertEqual(states.classify(os.path.join(root, "tasks", key), T0, lease.is_alive), states.VERIFIED)
            count = lambda tag: len(glob.glob(os.path.join(marks, tag + "-*")))
            self.assertEqual((count("S-start"), count("S-run"), count("A-run"), count("B-run")), (2, 1, 1, 1))  # S만 다시, 나머지는 한 번
            path = os.path.join(root, "ledger.jsonl")
            events = [json.loads(line) for line in pathlib.Path(path).read_text().splitlines()]
            self.assertEqual(ledger.verify(path), [])
            self.assertEqual([e["event"] for e in events].count("interrupted_rerun"), 1)
            runs = [e["data"]["run_id"] for e in events if e["event"] == "claimed" and e["data"]["task_key"] == keys["S"]]
            self.assertEqual((len(runs), len(set(runs))), (2, 2))  # 새 run_id로 재실행

    def test_two_runners_draining_the_same_root_execute_each_task_exactly_once(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            keys = [queue.enqueue(root, task("T%d" % i), T0) for i in range(16)]
            runners = [spawn_runner(root, marks), spawn_runner(root, marks)]
            for proc in runners:
                self.addCleanup(proc.kill)
            summaries = [json.loads(proc.communicate(timeout=120)[0]) for proc in runners]
            self.assertEqual([proc.returncode for proc in runners], [0, 0])
            done = summaries[0]["done"] + summaries[1]["done"]
            self.assertEqual(sorted(done), sorted(keys))  # 모든 작업이 정확히 한 runner에서 끝났다
            for i, key in enumerate(keys):
                self.assertEqual(states.classify(os.path.join(root, "tasks", key), T0, lease.is_alive), states.VERIFIED)
                self.assertEqual(len(glob.glob(os.path.join(marks, "T%d-run-*" % i))), 1)  # 표식 1개 = 실행 1회
            path = os.path.join(root, "ledger.jsonl")
            claimed = [json.loads(line)["data"]["task_key"] for line in pathlib.Path(path).read_text().splitlines()
                       if json.loads(line)["event"] == "claimed"]
            self.assertEqual((sorted(claimed), ledger.verify(path)), (sorted(keys), []))
            self.assertTrue(all(s["failed"] == [] and s["stopped"] == {} for s in summaries))
            self.assertTrue(all(len(s["locked"]) == len(set(s["locked"])) for s in summaries))  # 잠긴 작업을 반복해 시도하지 않는다
            self.assertGreater(sum(len(s["locked"]) for s in summaries), 0)  # 실제로 충돌(다른 runner가 쥔 작업)이 있었다

    def test_sys_exit_in_an_executor_is_recorded_as_a_failure_and_does_not_starve_independent_tasks(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            i, bad, fine = pair("exiter")
            kb, kf = queue.enqueue(root, bad, T0), queue.enqueue(root, fine, T0)
            proc = spawn_runner(root, marks)
            self.addCleanup(proc.kill)
            summary = json.loads(proc.communicate(timeout=120)[0])
            self.assertEqual((proc.returncode, summary["done"], summary["failed"]), (0, [kf], [[kb, "deterministic"]]))
            self.assertEqual((len(glob.glob(os.path.join(marks, "P%d-run-*" % i))), len(glob.glob(os.path.join(marks, "N%d-run-*" % i)))), (1, 1))
            tdir = os.path.join(root, "tasks", kb)
            self.assertEqual(states.classify(tdir, T0, lease.is_alive), states.FAILED)
            self.assertFalse(os.path.exists(os.path.join(tdir, "lease.json")))  # 작업권을 쥔 채 죽지 않았다
            again = spawn_runner(root, marks)
            self.addCleanup(again.kill)
            second = json.loads(again.communicate(timeout=120)[0])
            self.assertEqual((second["stopped"], second["executed"], len(glob.glob(os.path.join(marks, "P%d-run-*" % i)))),
                             ({kb: "needs_failure_policy"}, 0, 1))

    def test_a_task_that_keeps_dying_stops_after_the_interrupt_limit_and_independent_tasks_still_run(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as marks:
            i, bad, fine = pair("oom")
            kb, kf = queue.enqueue(root, bad, T0), queue.enqueue(root, fine, T0)
            procs = []
            for _ in range(5):  # 독 작업은 SIGKILL로 runner를 죽인다: 2번 인수·재실행(총 3회 실행) 뒤 정지해야 한다
                proc = spawn_runner(root, marks)
                self.addCleanup(proc.kill)
                procs.append((proc, proc.communicate(timeout=120)[0]))
            self.assertEqual([p.returncode for p, _ in procs], [-signal.SIGKILL] * 3 + [0, 0])
            fourth, fifth = (json.loads(out) for _, out in procs[3:])
            self.assertEqual((fourth["done"], fourth["stopped"], fourth["stop_reasons"]),
                             ([kf], {kb: "needs_failure_policy"}, {kb: "too_many_interrupts"}))
            self.assertEqual((fifth["executed"], fifth["stopped"]), (0, {kb: "needs_failure_policy"}))  # 이후 drain은 건드리지 않는다
            self.assertEqual(len(glob.glob(os.path.join(marks, "P%d-run-*" % i))), 3)  # 최초 1회 + 이어받아 2회
            self.assertEqual(len(glob.glob(os.path.join(marks, "N%d-run-*" % i))), 1)  # 독립 작업은 한 번 실행됐다
            self.assertEqual(states.classify(os.path.join(root, "tasks", kf), T0, lease.is_alive), states.VERIFIED)
            self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])
