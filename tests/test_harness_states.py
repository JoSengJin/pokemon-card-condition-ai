"""상태 분류 시험(5개 상태 + 대기·미등록). T-same-hash 포함. 합성 시험이며 모델 성능 근거가 아니다."""
import json
import os
import pathlib
import tempfile
import unittest

from harness import lease, queue, states
from tests.test_harness_support import BOOT, claim, alive_with, finish, make_contract

T0 = 1_000_000.0


def mutate(task_dir, how):
    out, done = os.path.join(task_dir, "out", "result.txt"), os.path.join(task_dir, "done.json")
    if how == "delete":
        os.unlink(out)
    elif how == "flip_byte":
        with open(out, "r+b") as handle:
            handle.write(b"X")
    elif how == "symlink":
        os.unlink(out)
        os.symlink(done, out)
    elif how == "garbled_done":
        with open(done, "w") as handle:
            handle.write("{broken")
    else:  # extra_manifest_key: 선언에 없는 파일이 manifest에 끼어든 경우
        with open(done) as handle:
            record = json.load(handle)
        record["manifest"]["extra.txt"] = "00" * 32
        with open(done, "w") as handle:
            json.dump(record, handle)


class StatesTest(unittest.TestCase):
    def test_unregistered_pending_and_same_input_hash_is_not_verified(self):
        with tempfile.TemporaryDirectory() as root:
            task = make_contract()
            key = queue.enqueue(root, task, T0)
            tdir = os.path.join(root, "tasks", key)
            self.assertEqual(states.classify(os.path.join(root, "tasks", "0" * 64), T0, alive_with()), states.UNREGISTERED)
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.PENDING)
            self.assertEqual(queue.enqueue(root, task, T0 + 1), key)  # 같은 입력 해시: 멱등 등록
            os.makedirs(os.path.join(tdir, "out"))
            with open(os.path.join(tdir, "out", "result.txt"), "wb") as handle:
                handle.write(b"v1")  # 산출물이 이미 있어도 완료 기록이 없으면
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.PENDING)
            res = claim(root, key, os.getpid(), BOOT, T0)
            self.assertTrue(res["ok"] and res["plan"]["action"] == "run")  # 건너뛰지 않고 실행한다
            lease.release(res["lease"])

    def test_verified_after_complete_and_claim_skips_it(self):
        with tempfile.TemporaryDirectory() as root:
            key, run_id = finish(root, make_contract(), T0)
            tdir = os.path.join(root, "tasks", key)
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.VERIFIED)
            self.assertFalse(os.path.exists(os.path.join(tdir, "lease.json")))
            res = claim(root, key, os.getpid(), BOOT, T0 + 5)
            self.assertEqual((res["ok"], res["reason"], res["state"]), (False, "skip", states.VERIFIED))
            self.assertFalse(os.path.exists(os.path.join(tdir, "lease.json")))
            self.assertIsNotNone(run_id)

    def test_corrupt_when_outputs_deleted_changed_or_done_record_damaged(self):
        for how in ("delete", "flip_byte", "symlink", "garbled_done", "extra_manifest_key"):
            with self.subTest(how=how), tempfile.TemporaryDirectory() as root:
                key, _ = finish(root, make_contract(), T0)
                tdir = os.path.join(root, "tasks", key)
                mutate(tdir, how)
                self.assertEqual(states.classify(tdir, T0, alive_with()), states.CORRUPT)

    def test_running_versus_interrupted_uses_injected_boot_and_pid_checks(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            tdir, path = os.path.join(root, "tasks", key), os.path.join(root, "tasks", key, "lease.json")
            handle = lease.lock(path)
            lease.stamp(handle, 4242, BOOT, T0, {"run_id": "r1"})
            lease.release(handle)
            cases = [(alive_with(pid_alive=lambda pid: True), states.RUNNING),
                     (alive_with(pid_alive=lambda pid: False), states.INTERRUPTED),
                     (alive_with("재부팅 뒤", pid_alive=lambda pid: True), states.INTERRUPTED)]
            for is_alive, want in cases:
                self.assertEqual(states.classify(tdir, T0, is_alive), want)
            with open(path, "w") as handle:
                handle.write("{garbled")
            self.assertEqual(states.classify(tdir, T0, alive_with(pid_alive=lambda pid: True)), states.INTERRUPTED)
            with open(path, "w"):
                pass  # 비어 있으면 작업권 없음(잠금만 잡고 기록 전에 죽은 경우)
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.PENDING)

    def test_failed_records_are_appended_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            first = claim(root, key, os.getpid(), BOOT, T0)
            queue.fail(root, key, first["run_id"], first["lease"], "transient", "ConnectionError('x')", T0 + 1)
            self.assertEqual(states.classify(tdir, T0, alive), states.FAILED)
            fdir = os.path.join(tdir, "failures")
            before = {n: pathlib.Path(fdir, n).read_text() for n in os.listdir(fdir)}
            second = claim(root, key, os.getpid(), BOOT, T0 + 2)
            queue.fail(root, key, second["run_id"], second["lease"], "deterministic", "TypeError('y')", T0 + 3)
            after = {n: pathlib.Path(fdir, n).read_text() for n in os.listdir(fdir)}
            self.assertEqual(len(after), 2)
            self.assertTrue(all(after[n] == text for n, text in before.items()))
            self.assertEqual([r["kind"] for r in states.failures(tdir)], ["transient", "deterministic"])

    def test_complete_and_fail_require_the_owning_run_and_all_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            tdir, alive = os.path.join(root, "tasks", key), alive_with()
            res = claim(root, key, os.getpid(), BOOT, T0)
            with self.assertRaises(queue.QueueError):
                queue.complete(root, key, "다른-run", res["lease"], T0 + 1)
            with self.assertRaises(queue.QueueError):
                queue.fail(root, key, res["run_id"], res["lease"], "oops", "x", T0 + 1)
            with self.assertRaises(FileNotFoundError):  # 산출물이 없으면 부분 완료 금지
                queue.complete(root, key, res["run_id"], res["lease"], T0 + 1)
            self.assertFalse(os.path.exists(os.path.join(tdir, "done.json")))
            self.assertEqual(states.classify(tdir, T0, alive), states.RUNNING)
            lease.release(res["lease"])
