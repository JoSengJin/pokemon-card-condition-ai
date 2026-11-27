"""claim의 이중 실행 방어: 대리 pid 거절, exec 뒤 잠금 상실, 잠금 없이 산 pid는 정지, 좀비·죽은 pid는 인수."""
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

from harness import holder, lease, queue, states
from tests.test_harness_support import BOOT, EXEC_CLAIM, REPO, alive_with, claim, make_contract

T0 = 1_000_000.0


def stale(root, key, pid, boot=BOOT, **extra):
    """주인이 없는 작업권 파일(잠금은 풀려 있고 기록만 남음)을 만든다. extra는 기록에 더할 필드(예: interrupts)."""
    handle = lease.lock(os.path.join(root, "tasks", key, "lease.json"))
    lease.stamp(handle, pid, boot, T0, dict({"run_id": "abc123"}, **extra))
    lease.release(handle)


class ClaimHolderTest(unittest.TestCase):
    def test_claim_for_another_pid_or_a_made_up_boot_is_rejected_before_touching_anything(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            before = pathlib.Path(root, "ledger.jsonl").read_text()
            with self.assertRaises(queue.QueueError):  # 대리 claim: 감독자만 죽으면 작업자가 잠금 없이 실행된다
                claim(root, key, os.getpid() + 1, BOOT, T0)
            with self.assertRaises(queue.QueueError):  # boot도 lease.boot_id()와 같아야 한다(호출자가 지어낼 수 없다)
                claim(root, key, os.getpid(), "지어낸-부팅", T0)
            with self.assertRaises(queue.QueueError):  # 실제 lease.boot_id()와 비교한다(BOOT는 이 기기의 부팅 식별자가 아니다)
                queue.claim(root, key, os.getpid(), BOOT, T0)
            with self.assertRaises(TypeError):  # 공개 인자로는 부팅 식별자 조회를 바꿀 수 없다(G 우회 불가)
                queue.claim(root, key, os.getpid(), "가짜", T0, None, lambda: "가짜")
            with self.assertRaises(TypeError):
                queue.claim(root, key, os.getpid(), "가짜", T0, boot_id_fn=lambda: "가짜")
            self.assertFalse(os.path.exists(os.path.join(root, "tasks", key, "lease.json")))
            self.assertEqual(pathlib.Path(root, "ledger.jsonl").read_text(), before)
            if sys.platform == "darwin":  # 주입 없이 실제 부팅 식별자로는 성공한다
                real = queue.claim(root, key, os.getpid(), lease.boot_id(), T0)
                self.assertTrue(real["ok"])
                lease.release(real["lease"], remove=True)

    def test_after_exec_the_same_pid_runs_without_a_lock_and_a_second_claim_stops(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            proc = subprocess.Popen([sys.executable, "-c", EXEC_CLAIM, root, key, BOOT], cwd=REPO,
                                    stdout=subprocess.PIPE, text=True)
            for cleanup in (proc.stdout.close, proc.wait, proc.kill):
                self.addCleanup(cleanup)
            self.assertEqual(proc.stdout.readline().strip(), "CLAIMED")
            path = os.path.join(root, "tasks", key, "lease.json")
            for _ in range(500):  # exec가 끝나 잠금 fd(close-on-exec)가 사라질 때까지
                probe = lease.lock(path)
                if probe is not None:
                    lease.release(probe)
                    break
                time.sleep(0.01)
            self.assertIsNone(proc.poll())  # 같은 pid가 계속 실행 중이다
            stopped = claim(root, key, os.getpid(), BOOT, time.time())
            self.assertEqual((stopped["ok"], stopped["reason"]), (False, "holder_alive_without_lock"))
            self.assertIn('"holder_alive_without_lock"', pathlib.Path(root, "ledger.jsonl").read_text())
            self.assertEqual(states.classify(os.path.join(root, "tasks", key), T0, alive_with()), states.RUNNING)
            proc.kill()
            proc.wait()
            self.assertTrue(claim(root, key, os.getpid(), BOOT, time.time())["ok"])  # 죽은 뒤에는 인수

    def test_unrelated_live_pid_stops_claim_until_it_dies_or_the_boot_differs(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            other = subprocess.Popen(["sleep", "30"])  # pid가 재사용된 무관한 프로세스를 모사
            self.addCleanup(other.wait)
            self.addCleanup(other.kill)
            path = os.path.join(root, "tasks", key, "lease.json")
            stale(root, key, other.pid)
            self.assertEqual(states.classify(os.path.dirname(path), T0, alive_with()), states.RUNNING)
            stopped = claim(root, key, os.getpid(), BOOT, T0 + 1)
            self.assertEqual((stopped["ok"], stopped["reason"], stopped["state"]),
                             (False, "holder_alive_without_lock", states.INTERRUPTED))
            self.assertEqual(lease.read(path)["pid"], other.pid)  # 기록을 건드리지 않았다
            stale(root, key, other.pid, boot="다른-부팅")  # 부팅 식별자가 다른 옛 기록(재부팅 전 pid)은 인수한다
            rebooted = claim(root, key, os.getpid(), BOOT, T0 + 2)
            self.assertTrue(rebooted["ok"])
            lease.release(rebooted["lease"], remove=True)
            stale(root, key, other.pid)
            other.kill()
            other.wait()
            self.assertTrue(claim(root, key, os.getpid(), BOOT, T0 + 3)["ok"])  # 죽은 pid는 인수

    def test_zombie_probe_decides_takeover_stop_or_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            other = subprocess.Popen(["sleep", "30"])
            self.addCleanup(other.wait)
            self.addCleanup(other.kill)
            for found, ok, reason in ((True, True, None), (False, False, "holder_alive_without_lock"),
                                      (None, False, "blocked")):
                stale(root, key, other.pid)
                with mock.patch.object(holder, "is_zombie", return_value=found):
                    res = claim(root, key, os.getpid(), BOOT, T0 + 1)
                self.assertEqual((res["ok"], res.get("reason")), (ok, reason), found)
                if res["ok"]:
                    lease.release(res["lease"], remove=True)

    def test_holder_verdict_and_ps_parsing(self):
        ps = lambda text, code=0: (lambda cmd, **kw: types.SimpleNamespace(stdout=text, returncode=code))
        self.assertIs(holder.is_zombie(1, run=ps("Z+\n")), True)
        self.assertIs(holder.is_zombie(1, run=ps("Ss\n")), False)
        self.assertIsNone(holder.is_zombie(1, run=ps("", 1)))  # 조회 실패는 추정하지 않는다
        self.assertIsNone(holder.is_zombie(1, run=ps("Z\n", 1)))  # 종료 코드가 실패면 출력이 Z여도 믿지 않는다
        self.assertIsNone(holder.is_zombie(1, run=mock.Mock(side_effect=OSError("ps 없음"))))
        rec = {"pid": os.getppid(), "boot_id": BOOT, "ts": 0}  # 살아 있고 내가 아닌 pid
        self.assertEqual(holder.verdict(rec, BOOT, zombie=lambda pid: False), "alive")
        self.assertEqual(holder.verdict(rec, "다른", zombie=lambda pid: False), "dead")
        self.assertEqual(holder.verdict(dict(rec, pid=os.getpid()), BOOT, zombie=lambda pid: False), "dead")
        for broken in (None, {}, {"pid": "x"}):
            self.assertEqual(holder.verdict(broken, BOOT), "dead")
