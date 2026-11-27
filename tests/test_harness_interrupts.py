"""작업별 연속 중단 한도(MAX_INTERRUPTS): 체크포인트 없는 재실행만 세고, 진전이 있는 재개는 초기화한다. 정지 기록은 한 번."""
import json
import os
import pathlib
import signal
import tempfile
import unittest
from unittest import mock

from harness import checkpoint, lease, queue, recovery, states
from tests.test_harness_support import RERUN_SAFE, BOOT, alive_with, claim, fingerprint, make_contract, start_workers

T0 = 1_000_000.0


def stale(root, key, pid, **extra):
    """죽은 pid의 작업권 기록(run_id=abc123, 이전 중단 횟수 등 extra)을 남긴다."""
    handle = lease.lock(os.path.join(root, "tasks", key, "lease.json"))
    lease.stamp(handle, pid, BOOT, T0, dict({"run_id": "abc123"}, **extra))
    lease.release(handle)


@mock.patch.object(recovery, "RERUN_SAFE_TYPES", RERUN_SAFE)  # 재실행 절차 시험: 등록 유형으로 본다
class InterruptLimitTest(unittest.TestCase):
    def test_interrupt_limit_counts_only_reruns_resets_on_checkpoint_resume_and_logs_the_stop_once(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            tdir, path = os.path.join(root, "tasks", key), os.path.join(root, "tasks", key, "lease.json")
            stale(root, key, 999999, interrupts=1)  # 이번이 2번째 중단(체크포인트 없음): 한도(2) 이내라 처음부터 다시 실행
            res = claim(root, key, os.getpid(), BOOT, T0 + 60)
            self.assertEqual((res["ok"], res["plan"]["action"], lease.read(path)["interrupts"]), (True, "rerun", 2))
            lease.release(res["lease"])
            stale(root, key, 999999, interrupts=2)  # 3번째 중단: 한도 초과 -> 정지, 기록은 그대로
            for _ in range(2):
                stopped = claim(root, key, os.getpid(), BOOT, T0 + 60)
                self.assertEqual((stopped["ok"], stopped["reason"], stopped["plan"]["reason"], lease.read(path)["interrupts"]),
                                 (False, "needs_failure_policy", "too_many_interrupts", 2))
            self.assertEqual(queue.recover(root, key, T0 + 60, is_alive=alive_with())["reason"], "too_many_interrupts")
            events = [json.loads(line) for line in pathlib.Path(root, "ledger.jsonl").read_text().splitlines()]
            stops = [e for e in events if e["event"] == "stopped_too_many_interrupts"]
            self.assertEqual(len(stops), 1)  # 반복 claim·recover에도 정지 기록은 한 번
            self.assertEqual((stops[0]["data"]["run_id"], stops[0]["data"]["interrupts"]), ("abc123", 3))
            for broken in ("x", -1, True, 1.5, None):  # 손상된 횟수는 한도를 넘긴 것으로 본다(보수적)
                stale(root, key, 999999, interrupts=broken)
                self.assertEqual(claim(root, key, os.getpid(), BOOT, T0 + 60)["reason"], "needs_failure_policy", broken)
            checkpoint.save(tdir, "abc123", fingerprint(), T0 + 1800)  # 진전이 있는 재개는 세지 않고 0으로 초기화한다
            for _ in range(3):  # 이미 한도에 닿은 기록(2)이어도, 연속으로 재개돼도 정지하지 않는다
                stale(root, key, 999999, interrupts=2)
                resumed = claim(root, key, os.getpid(), BOOT, T0 + 31 * 60, fingerprint())
                self.assertEqual((resumed["ok"], resumed["resumed"], lease.read(path)["interrupts"]), (True, True, 0))
                lease.release(resumed["lease"])

    def test_the_stop_is_not_logged_again_for_the_same_dead_record_but_is_for_a_new_one(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            for run_id in ("abc123", "def456"):  # 다른 중단 기록(다른 run_id)이면 새 정지로 한 번 더 기록한다
                stale(root, key, 999999, run_id=run_id, interrupts=2)
                claim(root, key, os.getpid(), BOOT, T0 + 60)
                claim(root, key, os.getpid(), BOOT, T0 + 60)
            stops = [json.loads(l)["data"]["run_id"] for l in pathlib.Path(root, "ledger.jsonl").read_text().splitlines()
                     if json.loads(l)["event"] == "stopped_too_many_interrupts"]
            self.assertEqual(stops, ["abc123", "def456"])

    def test_repeated_sigterm_without_a_checkpoint_stops_after_the_limit_and_only_once_in_the_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            for _ in range(3):  # 정상적인 중지(SIGTERM)도 체크포인트가 없으면 진전 없는 재실행으로 센다(사용자 확인 대기)
                key, gate, (proc,) = start_workers(self, root, 1)
                open(gate, "w").close()
                self.assertTrue(proc.stdout.readline().startswith("CLAIMED"))
                proc.send_signal(signal.SIGTERM)
                proc.wait()
            self.assertEqual(states.classify(os.path.join(root, "tasks", key), T0, alive_with()), states.INTERRUPTED)
            refused = [claim(root, key, os.getpid(), BOOT, T0 + 60) for _ in range(3)]
            self.assertEqual([(r["ok"], r["plan"]["reason"]) for r in refused], [(False, "too_many_interrupts")] * 3)
            events = [json.loads(line)["event"] for line in pathlib.Path(root, "ledger.jsonl").read_text().splitlines()]
            self.assertEqual((events.count("claimed"), events.count("stopped_too_many_interrupts")), (3, 1))

    def test_long_task_that_keeps_a_checkpoint_resumes_repeatedly_after_sigkill_without_stopping(self):
        with tempfile.TemporaryDirectory() as root:
            tdir = None
            for _ in range(4):  # 매번 30분 넘게 실행하고 체크포인트를 남긴 뒤 SIGKILL: 4번 중단돼도 계속 재개된다
                key = queue.enqueue(root, make_contract(), T0)
                tdir = os.path.join(root, "tasks", key)
                held = lease.read(os.path.join(tdir, "lease.json"))
                res = claim(root, key, os.getpid(), BOOT, T0 + 31 * 60 * (1 if held is None else 2), fingerprint())
                self.assertTrue(res["ok"])
                checkpoint.save(tdir, res["run_id"], fingerprint(), T0 + 3600)
                lease.release(res["lease"])  # 이 프로세스가 죽은 것처럼 기록만 남긴다
                stale(root, key, 999999, run_id=res["run_id"], interrupts=lease.read(os.path.join(tdir, "lease.json"))["interrupts"])
            final = claim(root, key, os.getpid(), BOOT, T0 + 3 * 3600, fingerprint())
            self.assertEqual((final["ok"], final["resumed"], lease.read(os.path.join(tdir, "lease.json"))["interrupts"]), (True, True, 0))
            lease.release(final["lease"])
