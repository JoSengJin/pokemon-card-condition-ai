"""저장 중 kill -9(정한 지점·임의 시각)와 동시 호출 경합·잠금 대기. 모두 실제 훅 프로세스다."""
import fcntl
import os
import pathlib
import random
import signal
import tempfile
import time
import unittest

from harness import gold_store
from tests.test_harness_gold_support import hook, issue, launch, paste, stored

KILL = "os.kill(os.getpid(), signal.SIGKILL)"
# 지점 이름 -> (드라이버에 끼울 코드, 죽은 뒤 남아야 하는 기록 수)
POINTS = {
    "잠금 전": ("import fcntl\ndef die(*a): " + KILL + "\nfcntl.flock = die", 0),
    "발급 장부 읽기 전": ("def die(*a): " + KILL + "\ngold_store.rows = die", 0),
    "저장 장부 읽기 전": ("o = gold_store.rows\ndef f(root, name):\n    if name == gold_store.STORE: " + KILL
                    + "\n    return o(root, name)\ngold_store.rows = f", 0),
    "추가 직전": ("def die(*a): " + KILL + "\nledger.append = die", 0),
    "flush 뒤 fsync 전": ("def die(*a): " + KILL + "\nos.fsync = die", 1),
    "추가 뒤 응답 전": ("o = ledger.append\ndef f(*a):\n    o(*a)\n    " + KILL + "\nledger.append = f", 1),
}
SLOW = "o = ledger.append\ndef f(*a):\n    time.sleep(0.5)\n    return o(*a)\nledger.append = f"  # 판단과 추가 사이를 벌린다


class GoldCrashTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_kill9_at_each_point_leaves_consistent_ledger(self):
        for number, (name, (patch, left)) in enumerate(POINTS.items()):
            with self.subTest(point=name):
                meta = issue(self.root, "k%d" % number)
                before = len(stored(self.root))
                proc = launch(self.root, paste(meta), patch=patch)
                self.assertEqual((proc.wait(timeout=60), proc.stdout.read()), (-signal.SIGKILL, b""))
                proc.stdout.close()
                proc.stderr.close()
                self.assertEqual(gold_store.audit(self.root), [])
                self.assertEqual(len(stored(self.root)), before + left)
                retry = hook(self, self.root, paste(meta))  # 죽은 프로세스의 잠금은 풀려 있다
                self.assertIn("[nonce_reused]" if left else "Gold 저장됨", retry)
                self.assertEqual(len(stored(self.root)), before + 1)

    def test_torn_last_line_fails_closed(self):
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(issue(self.root, "a"))))
        second = paste(issue(self.root, "b"))
        path = pathlib.Path(self.root, gold_store.STORE)
        torn = path.read_bytes() + path.read_bytes()[:40]  # 쓰다 끊긴 줄(전원 차단 등)을 합성
        path.write_bytes(torn)
        self.assertIn("[chain_broken]", hook(self, self.root, second))
        with self.assertRaises(gold_store.GoldError):  # 끝난 키를 확인할 수 없으므로 발급도 하지 않는다
            issue(self.root, "c")
        self.assertEqual(path.read_bytes(), torn)
        self.assertIn("unparseable", [p["problem"] for p in gold_store.audit(self.root)])

    def test_kill9_at_random_times_keeps_chain_consistent(self):
        rng = random.Random(8)
        started = time.monotonic()
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(issue(self.root, "warm"))))
        span = (time.monotonic() - started) * 1.3
        for number in range(24):
            meta = issue(self.root, "r%d" % number)
            before = len(stored(self.root))
            proc = launch(self.root, paste(meta))
            time.sleep(rng.uniform(0, span))
            proc.kill()
            proc.wait(timeout=60)
            proc.stdout.close()
            proc.stderr.close()
            self.assertEqual(gold_store.audit(self.root), [], number)
            added = len(stored(self.root)) - before
            self.assertIn(added, (0, 1))
            self.assertIn("[nonce_reused]" if added else "Gold 저장됨", hook(self, self.root, paste(meta)))
        self.assertEqual(len(stored(self.root)), 25)

    def test_concurrent_same_nonce_and_same_key_save_once(self):
        meta = issue(self.root, "a")
        same_key = [paste(issue(self.root, "shared")) for _ in range(5)]
        for prompts, code in (([paste(meta)] * 5, "[nonce_reused]"), (same_key, "[completed_key]")):
            with self.subTest(code=code):
                before = len(stored(self.root))
                procs = [launch(self.root, p, patch=SLOW) for p in prompts]
                replies = [p.stdout.read().decode("utf-8") for p in procs]
                for proc in procs:
                    self.assertEqual(proc.wait(timeout=60), 0, proc.stderr.read())
                    proc.stdout.close()
                    proc.stderr.close()
                self.assertEqual(sum("Gold 저장됨" in r for r in replies), 1, replies)
                self.assertEqual(sum(code in r for r in replies), 4, replies)
                self.assertEqual(len(stored(self.root)), before + 1)
                self.assertEqual(gold_store.audit(self.root), [])

    def test_held_lock_gives_up_as_busy_before_hook_timeout(self):
        meta = issue(self.root, "a")
        with open(os.path.join(self.root, "gold", ".lock"), "a") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX)
            proc = launch(self.root, paste(meta))
            try:
                self.assertEqual(proc.wait(timeout=15), 0)  # 설정 템플릿의 훅 timeout 20초보다 먼저 답해야 한다
                reply = proc.stdout.read().decode("utf-8")
            finally:
                proc.kill()
                proc.wait(timeout=60)
                proc.stdout.close()
                proc.stderr.close()
        self.assertIn("저장하지 않음 [busy]", reply)
        self.assertEqual(stored(self.root), [])
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(meta)))  # busy는 nonce를 쓰지 않는다

    def test_concurrent_distinct_screens_and_stop_all_land(self):
        prompts = [paste(issue(self.root, "d%d" % n)) for n in range(6)] + ["중단"]
        procs = [launch(self.root, p) for p in prompts]
        replies = [p.stdout.read().decode("utf-8") for p in procs]
        for proc in procs:
            self.assertEqual(proc.wait(timeout=60), 0, proc.stderr.read())
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(sum("Gold 저장됨" in r for r in replies), 6, replies)
        self.assertIn("중단 접수", replies[-1])
        self.assertEqual(len(stored(self.root)), 6)
        self.assertEqual(gold_store.audit(self.root), [])
        self.assertTrue(os.path.exists(os.path.join(self.root, "supervisor", "opstate.json")))


if __name__ == "__main__":
    unittest.main()
