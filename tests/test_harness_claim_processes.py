"""실제 하위 프로세스 시험: 동시 claim(T-race), 살아 있는 작업권(T-live), kill -9(T-kill)."""
import json
import os
import pathlib
import signal
import tempfile
import unittest

from harness import checkpoint, ledger, lease, queue, states
from tests.test_harness_support import BOOT, alive_with, fingerprint, make_contract, spawn_claimers


class ClaimProcessesTest(unittest.TestCase):
    def start(self, root, count):
        """작업을 등록하고 count개 프로세스를 대기시킨다. (key, gate 경로, 프로세스 목록)."""
        key = queue.enqueue(root, make_contract(), 1_000_000.0)
        gate = os.path.join(root, "go")
        procs = spawn_claimers(root, key, count, gate)
        for proc in procs:
            for cleanup in (proc.stdout.close, proc.stdin.close, proc.wait, proc.kill):
                self.addCleanup(cleanup)  # 정리는 거꾸로 실행: kill -> wait -> 파이프 닫기
        return key, gate, procs

    def test_race_exactly_one_of_many_processes_gets_running(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, procs = self.start(root, 8)
            open(gate, "w").close()  # 모든 프로세스를 동시에 출발시킨다
            replies = [proc.stdout.readline().split() for proc in procs]
            winners = [r for r in replies if r[0] == "CLAIMED"]
            self.assertEqual(len(winners), 1, replies)
            self.assertEqual(sorted(r[0] + " " + (r[1] if r[0] == "REFUSED" else "") for r in replies),
                             ["CLAIMED "] + ["REFUSED locked"] * 7)
            tdir, ledger_path = os.path.join(root, "tasks", key), os.path.join(root, "ledger.jsonl")
            self.assertEqual(states.classify(tdir, 1.0, alive_with()), states.RUNNING)
            self.assertEqual(lease.read(os.path.join(tdir, "lease.json"))["run_id"], winners[0][1])
            self.assertEqual(ledger.verify(ledger_path), [])
            events = [json.loads(line)["event"] for line in pathlib.Path(ledger_path).read_text().splitlines()]
            self.assertEqual(events.count("claimed"), 1)

    def test_live_process_keeps_running_and_second_claim_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = self.start(root, 1)
            open(gate, "w").close()
            run_id = proc.stdout.readline().split()[1]
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            self.assertEqual(states.classify(tdir, 1.0, alive), states.RUNNING)
            refused = queue.claim(root, key, os.getpid(), BOOT, 2.0, is_alive=alive)
            self.assertEqual((refused["ok"], refused["reason"]), (False, "locked"))
            self.assertEqual(queue.recover(root, key, 2.0, is_alive=alive)["action"], "wait")
            self.assertEqual(lease.read(os.path.join(tdir, "lease.json"))["run_id"], run_id)  # 기록을 건드리지 않음
            proc.stdin.close()  # 정상 종료(완료 기록 없이): 이제 작업권은 죽은 것
            proc.wait()
            self.assertEqual(states.classify(tdir, 3.0, alive), states.INTERRUPTED)

    def test_kill9_makes_interrupted_then_new_run_id(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = self.start(root, 1)
            open(gate, "w").close()
            run_id = proc.stdout.readline().split()[1]
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            self.assertEqual(states.classify(tdir, 1.0, alive), states.RUNNING)
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()
            self.assertEqual(states.classify(tdir, 1.0, alive), states.INTERRUPTED)
            started = lease.read(os.path.join(tdir, "lease.json"))["ts"]
            plan = queue.recover(root, key, started + 60, is_alive=alive)
            self.assertEqual((plan["state"], plan["action"], plan["resumed"]), (states.INTERRUPTED, "rerun", False))
            self.assertNotEqual(plan["run_id"], run_id)
            again = queue.claim(root, key, os.getpid(), BOOT, started + 61, is_alive=alive)
            self.assertTrue(again["ok"])
            self.assertNotEqual(again["run_id"], run_id)
            self.assertEqual(lease.read(os.path.join(tdir, "lease.json"))["pid"], os.getpid())
            lease.release(again["lease"])

    def test_kill9_after_30_minutes_with_matching_checkpoint_resumes_same_run(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = self.start(root, 1)
            open(gate, "w").close()
            run_id = proc.stdout.readline().split()[1]
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            started = lease.read(os.path.join(tdir, "lease.json"))["ts"]
            checkpoint.save(tdir, run_id, fingerprint(), started + 1800)
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()
            plan = queue.recover(root, key, started + 31 * 60, is_alive=alive, current=fingerprint())
            self.assertEqual((plan["action"], plan["resumed"], plan["run_id"]), ("resume", True, run_id))
            res = queue.claim(root, key, os.getpid(), BOOT, started + 31 * 60, is_alive=alive, current=fingerprint())
            self.assertEqual((res["ok"], res["resumed"], res["run_id"]), (True, True, run_id))
            self.assertTrue(lease.read(os.path.join(tdir, "lease.json"))["resumed"])
            lease.release(res["lease"])
