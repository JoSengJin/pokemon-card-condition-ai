"""실제 하위 프로세스 시험: 동시 claim(T-race), 살아 있는 작업권(T-live), kill -9(T-kill), 좀비·무관 pid, 실패 기록 직후 사망."""
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from harness import checkpoint, ledger, lease, queue, states
from tests.test_harness_support import (BOOT, FAIL_CRASH, REPO, alive_with, fingerprint, make_contract,
                                        start_workers)


class ClaimProcessesTest(unittest.TestCase):
    def test_race_exactly_one_of_many_processes_gets_running(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, procs = start_workers(self, root, 8)
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
            key, gate, (proc,) = start_workers(self, root, 1)
            open(gate, "w").close()
            run_id = proc.stdout.readline().split()[1]
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            self.assertEqual(states.classify(tdir, 1.0, alive), states.RUNNING)
            refused = queue.claim(root, key, os.getpid(), BOOT, 2.0)
            self.assertEqual((refused["ok"], refused["reason"]), (False, "locked"))
            self.assertEqual(queue.recover(root, key, 2.0, is_alive=alive)["action"], "wait")
            self.assertEqual(lease.read(os.path.join(tdir, "lease.json"))["run_id"], run_id)  # 기록을 건드리지 않음
            proc.stdin.close()  # 정상 종료(완료 기록 없이): 이제 작업권은 죽은 것
            proc.wait()
            self.assertEqual(states.classify(tdir, 3.0, alive), states.INTERRUPTED)

    def test_kill9_makes_interrupted_then_new_run_id(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = start_workers(self, root, 1)
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
            again = queue.claim(root, key, os.getpid(), BOOT, started + 61)
            self.assertTrue(again["ok"])
            self.assertNotEqual(again["run_id"], run_id)
            self.assertEqual(lease.read(os.path.join(tdir, "lease.json"))["pid"], os.getpid())
            lease.release(again["lease"])

    def test_kill9_after_30_minutes_with_matching_checkpoint_resumes_same_run(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = start_workers(self, root, 1)
            open(gate, "w").close()
            run_id = proc.stdout.readline().split()[1]
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            started = lease.read(os.path.join(tdir, "lease.json"))["ts"]
            checkpoint.save(tdir, run_id, fingerprint(), started + 1800)
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()
            plan = queue.recover(root, key, started + 31 * 60, is_alive=alive, current=fingerprint())
            self.assertEqual((plan["action"], plan["resumed"], plan["run_id"]), ("resume", True, run_id))
            res = queue.claim(root, key, os.getpid(), BOOT, started + 31 * 60, current=fingerprint())
            self.assertEqual((res["ok"], res["resumed"], res["run_id"]), (True, True, run_id))
            self.assertTrue(lease.read(os.path.join(tdir, "lease.json"))["resumed"])
            lease.release(res["lease"])

    def test_zombie_holder_is_running_for_observers_but_claim_takes_over(self):
        with tempfile.TemporaryDirectory() as root:
            key, gate, (proc,) = start_workers(self, root, 1)
            open(gate, "w").close()
            proc.stdout.readline()
            os.kill(proc.pid, signal.SIGKILL)
            tdir = os.path.join(root, "tasks", key)
            for _ in range(500):  # 죽었지만 회수(wait)하지 않음 = 좀비. 커널이 잠금을 풀 때까지 기다린다
                probe = lease.lock(os.path.join(tdir, "lease.json"))
                if probe is not None:
                    lease.release(probe)
                    break
                time.sleep(0.01)
            self.assertEqual(states.classify(tdir, 1.0, alive_with()), states.RUNNING)  # 관찰자는 pid 조회로 판정
            res = queue.claim(root, key, os.getpid(), BOOT, 2.0)  # flock은 이미 풀려 있다 = 쥔 쪽이 없다
            self.assertEqual((res["ok"], res["state"]), (True, states.INTERRUPTED))
            lease.release(res["lease"])

    @unittest.skipUnless(sys.platform == "darwin", "실제 부팅 식별자는 macOS에서만 조회한다")
    def test_unrelated_live_pid_in_stale_lease_does_not_block_claim(self):
        boot = lease.boot_id()  # 실제 부팅 식별자로 기록해야 pid 생존 판정만이 변수가 된다
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), 1.0)
            other = subprocess.Popen(["sleep", "30"])  # pid가 재사용된 무관한 프로세스를 모사
            self.addCleanup(other.wait)
            self.addCleanup(other.kill)
            tdir = os.path.join(root, "tasks", key)
            handle = lease.lock(os.path.join(tdir, "lease.json"))
            lease.stamp(handle, other.pid, boot, 1.0, {"run_id": "r-old"})
            lease.release(handle)
            self.assertEqual(states.classify(tdir, 2.0, lease.is_alive), states.RUNNING)  # 관찰자는 산 pid를 RUNNING으로 본다
            res = queue.claim(root, key, os.getpid(), BOOT, 2.0)
            self.assertEqual((res["ok"], res["state"], res["run_id"] != "r-old"), (True, states.INTERRUPTED, True))
            lease.release(res["lease"])

    def test_death_right_after_writing_failure_record_is_failed_not_interrupted(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), 1.0)
            done = subprocess.run([sys.executable, "-c", FAIL_CRASH, root, key, BOOT], cwd=REPO)
            self.assertEqual(done.returncode, -signal.SIGKILL)
            tdir = os.path.join(root, "tasks", key)
            self.assertEqual(len(states.failures(tdir)), 1)
            self.assertTrue(os.path.exists(os.path.join(tdir, "lease.json")))  # 작업권 해제 전에 죽었다
            self.assertEqual(states.classify(tdir, 2.0, alive_with()), states.FAILED)
            refused = queue.claim(root, key, os.getpid(), BOOT, 3.0)  # 결정적 실패는 재실행하지 않는다
            self.assertEqual((refused["ok"], refused["reason"]), (False, "needs_failure_policy"))
