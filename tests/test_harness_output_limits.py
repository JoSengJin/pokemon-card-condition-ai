"""4차 결함 I8(변이 V21)·I9: 실행기 출력 상한과 kill 잔여물 정리(실제 sandbox-exec 하위 프로세스).

- V21 표준 출력이 sandbox.MAX_STDOUT_BYTES를 넘으면 그 사유("표준 출력이 상한")로 결정적 실패다(결과 JSON을 읽지 않는다).
- I9 산출물 합계 크기가 sandbox.MAX_TOTAL_OUTPUT_BYTES(설정값, 임시 4 GiB)를 넘으면 결정적 실패이고 확정 out/은 그대로다.
- I9 실행 폴더 이름은 harness-exec-<task_key>-*다. 다음 runner가 그 작업의 작업권(잠금)을 잡고 이전 주인이 죽었다고 판정한 뒤(queue.claim)
  이전 kill로 남은 작업 폴더의 .out-pending-*와 시스템 임시 폴더의 harness-exec-<task_key>-*를 지운다. 다른 작업의 실행 폴더, 링크(따라가지
  않는다), 잠금을 잡지 못한 작업의 잔여물은 건드리지 않는다.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import contract as ct
from harness import lease, queue, runner, sandbox
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_output_limits:EXECUTORS"


def emitter(task, out_dir):
    """inputs.mode: loud(표준 출력에 100 KB) / two(산출물 2개 각 3바이트) / where(result.txt에 TMPDIR 경로)."""
    mode = task["inputs"]["mode"]
    names = ["a.txt", "result.txt"] if mode == "two" else ["result.txt"]
    for name in names:
        with open(os.path.join(out_dir, name), "w") as handle:
            handle.write(os.environ["TMPDIR"] if mode == "where" else "NEW")
    if mode == "loud":
        os.write(1, b"x" * 100000 + b"\n")
    return names


EXECUTORS = {"emitter": emitter}


class OutputLimitTest(unittest.TestCase):
    def _run(self, mode):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root = os.path.join(base, "root")
        task = make_contract("L", task_type="emitter", inputs={"mode": mode}, outputs=["a.txt", "result.txt"] if mode == "two" else ["result.txt"])
        final = os.path.join(root, "tasks", ct.task_key(task), "out")
        try:
            return sandbox.run_one(root, SPEC, "emitter", task, final), final, ct.task_key(task)
        except sandbox.ChildError as exc:
            return exc, final, ct.task_key(task)

    def test_stdout_and_total_output_limits_fail_with_their_own_reason(self):
        with mock.patch.object(sandbox, "MAX_STDOUT_BYTES", 4096):
            loud, final, _ = self._run("loud")
        self.assertIsInstance(loud, sandbox.ChildError)
        self.assertEqual(loud.kind, "deterministic")
        self.assertIn("표준 출력이 상한", str(loud))  # V21: 상한 분기가 없으면 '종료 코드' 사유로 떨어진다
        self.assertEqual(os.listdir(final), [])
        with mock.patch.object(sandbox, "MAX_TOTAL_OUTPUT_BYTES", 5):
            two, final, _ = self._run("two")
        self.assertIsInstance(two, sandbox.ChildError)
        self.assertEqual(two.kind, "deterministic")
        self.assertIn("합계", str(two))
        self.assertEqual(os.listdir(final), [])
        with mock.patch.object(sandbox, "MAX_TOTAL_OUTPUT_BYTES", 6):
            self.assertEqual(self._run("two")[0], ["a.txt", "result.txt"])  # 합계가 상한과 같으면 정상
        self.assertGreaterEqual(sandbox.MAX_TOTAL_OUTPUT_BYTES, sandbox.MAX_OUTPUT_BYTES)

    def test_the_run_folder_is_named_after_the_task_and_removed(self):
        got, final, key = self._run("where")
        self.assertEqual(got, ["result.txt"])
        with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
            run = os.path.dirname(handle.read())
        self.assertTrue(os.path.basename(run).startswith("harness-exec-%s-" % key), run)
        self.assertFalse(os.path.exists(run))

    def test_leftovers_of_a_killed_run_are_swept_only_after_taking_the_lease(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root, victim = os.path.join(base, "root"), os.path.join(base, "victim")
        os.makedirs(os.path.join(victim, "keep"))
        key = queue.enqueue(root, make_contract("S", task_type="calc"), 1.0)
        task_dir = os.path.join(root, "tasks", key)
        left = [tempfile.mkdtemp(prefix=".out-pending-", dir=task_dir), tempfile.mkdtemp(prefix="harness-exec-%s-" % key)]
        other = tempfile.mkdtemp(prefix="harness-exec-%s-" % ("0" * 64))
        link = os.path.join(task_dir, ".out-pending-link")
        os.symlink(victim, link)
        for path in left + [other]:
            self.addCleanup(shutil.rmtree, path, True)
            with open(os.path.join(path, "big.bin"), "wb") as handle:
                handle.write(b"x" * 1000)
        held = lease.lock(os.path.join(task_dir, "lease.json"))  # 다른 runner가 잠금을 쥐고 있다: 건드리지 않는다
        executor = mock.Mock(return_value=["result.txt"])
        self.assertEqual(runner.drain(root, {"calc": executor}, max_tasks=1)["locked"], [key])
        self.assertTrue(all(os.path.isdir(p) for p in left))
        lease.release(held)
        runner.drain(root, {"calc": executor}, max_tasks=1)  # 잠금을 잡고 이전 주인이 없음을 본 뒤 정리
        self.assertEqual([os.path.exists(p) for p in left], [False, False])
        self.assertTrue(os.path.isdir(other))  # 다른 작업의 실행 폴더는 그대로
        self.assertTrue(os.path.islink(link) and os.path.isdir(os.path.join(victim, "keep")))  # 링크는 따라가지 않는다


if __name__ == "__main__":
    unittest.main()
