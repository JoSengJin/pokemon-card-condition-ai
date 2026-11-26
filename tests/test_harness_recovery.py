"""복구 시험: T-delete·T-tamper(CAS 손상 포함)·T-transient·T-code·T-30min. 합성 시험이며 모델 성능 근거가 아니다."""
import json
import os
import pathlib
import socket
import tempfile
import unittest

from harness import cas, checkpoint, ledger, lease, queue, recovery, states
from tests.test_harness_support import BOOT, alive_with, dead_lease, finish, fingerprint, make_contract

T0 = 1_000_000.0


class RecoveryTest(unittest.TestCase):
    def test_delete_after_complete_is_restored_from_cas_and_verified(self):
        with tempfile.TemporaryDirectory() as root:
            key, _ = finish(root, make_contract(outputs=("a.txt", "sub/b.txt")), T0, payload=b"data")
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            os.unlink(os.path.join(tdir, "out", "sub", "b.txt"))
            self.assertEqual(states.classify(tdir, T0, alive), states.CORRUPT)
            plan = queue.recover(root, key, T0 + 9, is_alive=alive)
            self.assertEqual((plan["state"], plan["action"], plan["runnable"]), (states.CORRUPT, "skip", False))
            self.assertEqual(states.classify(tdir, T0, alive), states.VERIFIED)
            self.assertEqual(pathlib.Path(tdir, "out", "sub", "b.txt").read_bytes(), b"data")
            self.assertIn('"corrupt_restored"', pathlib.Path(root, "ledger.jsonl").read_text())
            self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])

    def test_tampered_byte_is_restored_but_damaged_cas_forces_rerun(self):
        with tempfile.TemporaryDirectory() as root:
            key, old_run = finish(root, make_contract(), T0, payload=b"original")
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            out = pathlib.Path(tdir, "out", "result.txt")
            out.write_bytes(b"originaX")
            self.assertEqual(queue.recover(root, key, T0 + 2, is_alive=alive)["action"], "skip")
            self.assertEqual(out.read_bytes(), b"original")  # CAS에서 복구
            out.write_bytes(b"originaX")
            recorded = json.loads(pathlib.Path(tdir, "done.json").read_text())["manifest"]["result.txt"]
            blob = cas.blob_path(os.path.join(root, "cas"), recorded)
            pathlib.Path(blob).write_bytes(b"also damaged")  # CAS 보관본도 손상
            plan = queue.recover(root, key, T0 + 3, is_alive=alive)
            self.assertEqual((plan["action"], plan["runnable"]), ("rerun", True))
            self.assertNotEqual(plan["run_id"], old_run)
            self.assertEqual(states.classify(tdir, T0, alive), states.PENDING)  # 완료 기록은 history로 보관됨
            self.assertEqual(len(os.listdir(os.path.join(tdir, "history"))), 1)
            res = queue.claim(root, key, os.getpid(), BOOT, T0 + 4, is_alive=alive)
            self.assertTrue(res["ok"])
            out.write_bytes(b"rerun")
            queue.complete(root, key, res["run_id"], res["lease"], T0 + 5)
            self.assertEqual(states.classify(tdir, T0, alive), states.VERIFIED)

    def test_transient_failure_retries_at_most_twice_then_stops(self):
        with tempfile.TemporaryDirectory() as root:
            key, alive = queue.enqueue(root, make_contract(), T0), alive_with()
            for attempt in (1, 2, 3):
                res = queue.claim(root, key, os.getpid(), BOOT, T0 + attempt, is_alive=alive)
                self.assertTrue(res["ok"], attempt)
                exc = ConnectionError("네트워크 차단 모사")
                queue.fail(root, key, res["run_id"], res["lease"], recovery.kind_of(exc), repr(exc), T0 + attempt)
            plan = queue.recover(root, key, T0 + 10, is_alive=alive)
            self.assertEqual((plan["state"], plan["action"], plan["failure_kind"], plan["attempts"]),
                             (states.FAILED, "needs_failure_policy", "transient", 3))
            refused = queue.claim(root, key, os.getpid(), BOOT, T0 + 11, is_alive=alive)
            self.assertEqual((refused["ok"], refused["reason"]), (False, "needs_failure_policy"))
            self.assertEqual(len(os.listdir(os.path.join(root, "tasks", key, "failures"))), 3)  # 1회 + 재시도 2회
            strict = dict(make_contract(tag="z"), retry_policy={"max_transient_retries": 0})
            key0 = queue.enqueue(root, strict, T0)
            res0 = queue.claim(root, key0, os.getpid(), BOOT, T0, is_alive=alive)
            queue.fail(root, key0, res0["run_id"], res0["lease"], "transient", "timeout", T0)
            self.assertEqual(queue.recover(root, key0, T0 + 1, is_alive=alive)["action"], "needs_failure_policy")

    def test_code_error_is_deterministic_and_never_retried(self):
        kinds = {TypeError: "deterministic", ValueError: "deterministic", OSError: "deterministic",
                 ConnectionResetError: "transient", TimeoutError: "transient", socket.timeout: "transient"}
        for exc_type, kind in kinds.items():
            self.assertEqual(recovery.kind_of(exc_type("x")), kind, exc_type)
        with tempfile.TemporaryDirectory() as root:
            key, alive = queue.enqueue(root, make_contract(), T0), alive_with()
            res = queue.claim(root, key, os.getpid(), BOOT, T0, is_alive=alive)
            exc = TypeError("코드 오류 주입")
            queue.fail(root, key, res["run_id"], res["lease"], recovery.kind_of(exc), repr(exc), T0)
            plan = queue.recover(root, key, T0 + 1, is_alive=alive)
            self.assertEqual((plan["action"], plan["failure_kind"], plan["attempts"], plan["runnable"]),
                             ("needs_failure_policy", "deterministic", 1, False))
            self.assertEqual(queue.claim(root, key, os.getpid(), BOOT, T0 + 2, is_alive=alive)["reason"],
                             "needs_failure_policy")

    def test_30_minute_threshold_and_checkpoint_fingerprint_decide_resume(self):
        dead = alive_with(pid_alive=lambda pid: False)
        flipped = {name: fingerprint(**{name: "다름"}) for name in checkpoint.REQUIRED}
        cases = [("29분+일치", 29, fingerprint(), fingerprint(), False), ("31분+일치", 31, fingerprint(), fingerprint(), True),
                 ("정확히 30분+일치", 30, fingerprint(), fingerprint(), True), ("31분+체크포인트 없음", 31, None, fingerprint(), False),
                 ("31분+현재 지문 없음", 31, fingerprint(), None, False)]
        cases += [("31분+불일치 " + n, 31, fingerprint(), flipped[n], False) for n in checkpoint.REQUIRED]
        for label, minutes, saved, current, resumes in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as root:
                key = queue.enqueue(root, make_contract(), T0)
                tdir = os.path.join(root, "tasks", key)
                dead_lease(root, key, T0, run_id="run-old")
                if saved is not None:
                    checkpoint.save(tdir, "run-old", saved, T0 + 60)
                plan = queue.recover(root, key, T0 + minutes * 60, is_alive=dead, current=current)
                self.assertEqual((plan["state"], plan["resumed"]), (states.INTERRUPTED, resumes))
                self.assertEqual(plan["run_id"] == "run-old", resumes)
                res = queue.claim(root, key, os.getpid(), BOOT, T0 + minutes * 60, is_alive=dead, current=current)
                self.assertEqual((res["ok"], res["resumed"], res["run_id"] == "run-old"), (True, resumes, resumes))
                lease.release(res["lease"])

    def test_checkpoint_of_another_run_or_damaged_file_is_not_trusted(self):
        dead = alive_with(pid_alive=lambda pid: False)
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            tdir = os.path.join(root, "tasks", key)
            dead_lease(root, key, T0, run_id="run-old")
            checkpoint.save(tdir, "run-other", fingerprint(), T0 + 60)
            plan = queue.recover(root, key, T0 + 3600, is_alive=dead, current=fingerprint())
            self.assertEqual((plan["action"], plan["resumed"]), ("rerun", False))
            pathlib.Path(tdir, "checkpoint.json").write_text("{broken")
            plan = queue.recover(root, key, T0 + 3600, is_alive=dead, current=fingerprint())
            self.assertEqual((plan["action"], plan["resumed"]), ("rerun", False))
            self.assertIn("손상", plan["reason"])

    def test_claim_releases_its_lock_when_classification_raises(self):
        unreadable_boot = lambda: lease.boot_id("조회 실패 모사")  # LeaseError를 낸다
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            dead_lease(root, key, T0)
            with self.assertRaises(lease.LeaseError):
                queue.claim(root, key, os.getpid(), BOOT, T0, is_alive=lambda rec: lease.is_alive(rec, unreadable_boot))
            handle = lease.lock(os.path.join(root, "tasks", key, "lease.json"))
            self.assertIsNotNone(handle)  # 잠금이 풀려 있다
            self.assertEqual(handle.previous["run_id"], "r-dead")  # 중단 증거도 그대로
            lease.release(handle)
