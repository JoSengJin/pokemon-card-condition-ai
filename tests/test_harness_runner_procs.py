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

from harness import ledger, lease, queue, states
from tests.test_harness_runner_kit import task
from tests.test_harness_support import spawn_runner

T0 = 1_000_000.0


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
            keys = [queue.enqueue(root, task("T%d" % i), T0) for i in range(10)]
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
