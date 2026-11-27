"""3차 결함 H4·H5·변이 S09·S10·S18: 확정 out/ 반영은 다 검사한 뒤 한 번에, 크기는 정해진 만큼만(실제 sandbox-exec 하위 프로세스).

- S09 확정 out/ 자체가 링크면(같은 사용자 다른 프로세스가 바꾼 경우) 중첩 산출물(n/a.txt)도 링크 대상에 쓰지 않는다.
- S10 executor가 돌려준 출력 목록이 계약 outputs와 다르면 확정 out/은 그대로다(복사하지 않는다).
- H5 산출물 하나라도 거절되면 이번에 복사한 다른 산출물도 확정 out/에 남지 않는다(이전 산출물 그대로): 하네스 소유 임시 폴더에 다 검사·복사한 뒤
  옮긴다.
- H4 산출물은 열 때 fstat 크기까지만 복사하고(replace_new limit), 산출물·표준 출력이 상한(sandbox.MAX_OUTPUT_BYTES·MAX_STDOUT_BYTES)을 넘으면
  결정적 실패다.
- S18 CORRUPT 복구(cas.restore)는 검사 뒤 보관본이 바뀌어도 쓴 내용 해시가 다르면 대상을 바꾸지 않는다.
"""
import hashlib
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import cas, safefs, sandbox
from harness import contract as ct
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_output_commit:EXECUTORS"


def writer(task, out_dir):
    """inputs.mode대로 staging에 산출물을 쓴다: nested(n/a.txt) / wrong_list(result.txt를 쓰고 []를 돌려줌) / partial(a_report.json 정상 +
    result.txt는 링크) / big(result.txt를 1 MiB 희소 파일로) / loud(표준 출력 fd 1에 100 KB를 쓰고 정상 반환)."""
    mode = task["inputs"]["mode"]
    if mode == "nested":
        os.makedirs(os.path.join(out_dir, "n"))
        with open(os.path.join(out_dir, "n", "a.txt"), "w") as handle:
            handle.write("NEW")
        return ["n/a.txt"]
    if mode == "partial":
        with open(os.path.join(out_dir, "a_report.json"), "w") as handle:
            handle.write("NEW")
        os.symlink("/etc/hosts", os.path.join(out_dir, "result.txt"))
        return ["a_report.json", "result.txt"]
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        handle.write("NEW")
        if mode == "big":
            handle.truncate(1 << 20)
    if mode == "loud":
        os.write(1, b"x" * 100000 + b"\n")
    return [] if mode == "wrong_list" else ["result.txt"]


EXECUTORS = {"writer": writer}


class OutputCommitTest(unittest.TestCase):
    def _run(self, mode, outputs=("result.txt",), previous=None):
        """새 root에서 writer를 mode로 실행한다. (ChildError 또는 출력 목록, 확정 out/ 경로)."""
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root = os.path.join(base, "root")
        task = make_contract("W", task_type="writer", inputs={"mode": mode}, outputs=outputs)
        final = os.path.join(root, "tasks", ct.task_key(task), "out")
        os.makedirs(final)
        for rel, text in (previous or {}).items():
            with open(os.path.join(final, rel), "w", encoding="utf-8") as handle:
                handle.write(text)
        try:
            return sandbox.run_one(root, SPEC, "writer", task, final), final
        except sandbox.ChildError as exc:
            return exc, final

    def test_a_linked_final_out_is_refused_even_for_nested_outputs(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root, victim = os.path.join(base, "root"), os.path.join(base, "victim")
        os.makedirs(victim)
        task = make_contract("N", task_type="writer", inputs={"mode": "nested"}, outputs=("n/a.txt",))
        final = os.path.join(root, "tasks", ct.task_key(task), "out")
        os.makedirs(os.path.dirname(final))
        os.symlink(victim, final)
        with self.assertRaises(sandbox.ChildError):
            sandbox.run_one(root, SPEC, "writer", task, final)
        self.assertEqual((os.listdir(victim), os.path.islink(final)), ([], True))

    def test_a_wrong_output_list_leaves_the_final_out_untouched(self):
        got, final = self._run("wrong_list")
        self.assertIsInstance(got, sandbox.ChildError)
        self.assertEqual((got.kind, os.listdir(final)), ("deterministic", []))

    def test_one_refused_output_leaves_no_copied_output_and_keeps_the_previous_ones(self):
        got, final = self._run("partial", outputs=("a_report.json", "result.txt"), previous={"a_report.json": "OLD"})
        self.assertIsInstance(got, sandbox.ChildError)
        self.assertEqual(sorted(os.listdir(final)), ["a_report.json"])
        with open(os.path.join(final, "a_report.json"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "OLD")
        self.assertEqual([n for n in os.listdir(os.path.dirname(final)) if n != "out"], [])  # 하네스 임시 폴더도 남지 않는다

    def test_outputs_and_stdout_over_the_limits_are_deterministic_failures(self):
        with mock.patch.object(sandbox, "MAX_OUTPUT_BYTES", 4096):
            big, final = self._run("big")
            self.assertEqual(os.listdir(final), [])
        with mock.patch.object(sandbox, "MAX_STDOUT_BYTES", 4096):
            loud, final = self._run("loud")
            self.assertEqual(os.listdir(final), [])
        for got in (big, loud):
            self.assertIsInstance(got, sandbox.ChildError)
            self.assertEqual(got.kind, "deterministic")
        self.assertEqual(self._run("loud")[0], ["result.txt"])  # 상한 안이면 정상

    def test_copies_stop_at_the_given_size_and_restore_checks_what_it_wrote(self):
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        src, dest = os.path.join(base, "src"), os.path.join(base, "dest")
        with open(src, "wb") as handle:
            handle.write(b"0123456789" * 10)
        fd = os.open(src, os.O_RDONLY)
        try:
            self.assertEqual(safefs.replace_new(dest, fd, limit=10), hashlib.sha256(b"0123456789").hexdigest())
        finally:
            os.close(fd)
        with open(dest, "rb") as handle:
            self.assertEqual(handle.read(), b"0123456789")
        store = os.path.join(base, "cas")
        sha = cas.put(store, src)
        with open(cas.blob_path(store, sha), "wb") as handle:  # 해시 검사 뒤 보관본이 바뀐 경우(검사는 통과한 것으로 둔다)
            handle.write(b"tampered")
        with mock.patch.object(cas, "sha_file", return_value=sha):
            self.assertEqual(cas.restore(store, [(sha, dest)]), [dest])
        with open(dest, "rb") as handle:
            self.assertEqual(handle.read(), b"0123456789")


if __name__ == "__main__":
    unittest.main()
