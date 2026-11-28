"""2차 결함 G1·G2·G6·G7(실행기 경계, 실제 sandbox-exec 하위 프로세스).

- executor가 쓸 수 있는 곳은 실행마다 새로 만드는 staging 폴더(out/·tmp/)뿐이고, 확정 out/에는 쓸 권한이 한 번도 없다. 하네스가 실행 뒤
  계약 outputs만 링크·하드 링크·특수 파일·폴더를 거절하며 새 파일로 복사한다. 그래서 늦게까지 사는 자손이 staging을 바꿔도 확정 산출물은
  바뀌지 않는다(G1·G7). 실행이 끝나면 executor의 프로세스 그룹을 끝낸다(setsid 자손은 남는 한계, 하지만 확정 out/에 쓰지 못한다).
- out 자리를 링크로 바꿔도 다음 실행은 새 staging을 받으므로 허용 범위가 넓어지지 않는다(G2).
- 실험 executor는 SHA를 확인한 입력 사본(작업 폴더 in/, executor 쓰기 불가)을 읽는다: 대조 뒤 원본이 바뀌어도 대조한 내용으로 실행한다(G6).
- 프로필: 실행 폴더는 하네스 root·저장소 밖이어야 하고(G2·변이 N06·N07), Apple Event 보내기를 거절한다(변이 N03).
"""
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from harness import contract as ct
from harness import queue, runner, sandbox, states
from tests import test_harness_boundary_kit as kit
from tests.test_harness_git_kit import CODE, git_source
from tests.test_harness_support import make_contract

SPEC = "tests.test_harness_boundary_kit:EXECUTORS"


class ExecBoundaryTest(unittest.TestCase):
    def _root(self):
        """(하네스 root, 표식 폴더). root에는 운영 상태 파일과 다른 작업 폴더가 있다."""
        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        root, marks = os.path.join(base, "root"), os.path.join(base, "marks")
        for sub in ("supervisor", os.path.join("tasks", "other"), "marks"):
            os.makedirs(os.path.join(root if sub != "marks" else base, sub))
        with open(os.path.join(root, "supervisor", "opstate.json"), "w", encoding="utf-8") as handle:
            handle.write("ORIG")
        return root, marks

    def test_late_descendants_cannot_change_confirmed_outputs_or_write_the_final_out(self):
        root, marks = self._root()
        task = make_contract("L", task_type="lingerer")
        final = os.path.join(root, "tasks", ct.task_key(task), "out")
        os.makedirs(final)
        with mock.patch.dict(os.environ, {"HARNESS_TEST_ROOT": root, "HARNESS_MARK_DIR": marks}), \
                mock.patch.object(sandbox, "profile", kit.marked_profile(sandbox.profile, marks)):
            self.assertEqual(sandbox.run_one(root, SPEC, "lingerer", task, final), ["result.txt"])
        with open(os.path.join(marks, "now.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"write_final": "denied:1", "plant_final_tmp_link": "denied:1"})
        deadline = time.time() + 10
        while not os.path.exists(os.path.join(marks, "late.json")) and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.5)
        with open(os.path.join(marks, "late.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["append_final"], "denied:1")  # setsid 손자도 확정 out/에는 못 쓴다
        self.assertEqual(sorted(os.listdir(final)), ["result.txt"])
        with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "PAYLOAD")  # 확정 산출물은 그대로
        self.assertFalse(os.path.exists(os.path.join(marks, "child.txt")))  # 같은 그룹 자식은 실행 뒤 끝났다

    def test_link_hardlink_fifo_dir_outputs_and_a_swapped_out_folder_are_refused(self):
        root, _ = self._root()
        with mock.patch.dict(os.environ, {"HARNESS_TEST_ROOT": root}):
            for mode in ("symlink", "hardlink", "fifo", "dir", "swap"):
                task = make_contract("S", task_type="shaper", inputs={"mode": mode})
                final = os.path.join(root, "tasks", ct.task_key(task), "out")
                with self.assertRaises(sandbox.ChildError, msg=mode) as caught:
                    sandbox.run_one(root, SPEC, "shaper", task, final)
                self.assertEqual(caught.exception.kind, "deterministic", mode)
                self.assertFalse(os.path.lexists(os.path.join(final, "result.txt")), mode)
                self.assertFalse(os.path.islink(final), mode)
            task = make_contract("S", task_type="shaper", inputs={"mode": "write_other"})  # swap 뒤의 같은 작업 다시 실행에 해당
            final = os.path.join(root, "tasks", ct.task_key(task), "out")
            sandbox.run_one(root, SPEC, "shaper", task, final)
        with open(os.path.join(final, "result.txt"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"write_other": "denied:1"})
        self.assertEqual(os.listdir(os.path.join(root, "tasks", "other")), [])
        with open(os.path.join(root, "supervisor", "opstate.json"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "ORIG")

    def test_experiment_executor_reads_the_verified_input_copy(self):
        root, _ = self._root()
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)  # code_sha는 source_root의 HEAD와 대조한다(3차 결함 H1)
        os.makedirs(os.path.join(src, "data"))
        with open(os.path.join(src, "data", "a.json"), "wb") as handle:
            handle.write(b"verified")
        want = hashlib.sha256(b"verified").hexdigest()
        task = make_contract("E", task_type="experiment", inputs={"data/a.json": want}, outputs=("metrics.json",))
        task["run_conditions"] = {"command": ["python", "t.py", "{input:data/a.json}"], "code_sha": CODE,
                                  "input_roles": {"data/a.json": "data"}}
        key = queue.enqueue(root, task, 1.0, source_root=src)

        def swap():  # 대조가 끝난 뒤(executor가 읽기 전) 다른 프로세스가 원본을 바꾼다
            time.sleep(0.5)
            with open(os.path.join(src, "data", "a.json"), "wb") as handle:
                handle.write(b"swapped-after-verify")
        threading.Thread(target=swap, daemon=True).start()
        summary = runner.drain(root, sandbox.sandboxed(root, SPEC), max_tasks=1, source_root=src)
        self.assertEqual(summary["done"], [key], summary)
        with open(os.path.join(root, "tasks", key, "out", "metrics.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"seen": want, "write_input_copy": "denied:1"})
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.VERIFIED)

    def test_profile_grants_only_a_run_folder_outside_root_and_repo(self):
        root, _ = self._root()
        run = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, run, True)
        text = sandbox.profile(root, run)
        real = os.path.realpath(run)
        self.assertIn('(subpath "%s/out")' % real, text)
        self.assertIn('(subpath "%s/tmp")' % real, text)
        self.assertNotIn('(subpath "%s")' % real, text)  # 실행 폴더 자체·입력 자리(in/)는 쓸 수 없다
        self.assertIn("(deny appleevent-send)", text)
        for path in sandbox.DENY_EXEC:
            self.assertIn('(literal "%s")' % path, text)
        for bad in (os.path.join(root, "tasks"), os.path.join(root, "tasks", "k"), root, os.path.join(sandbox.REPO, "harness")):
            with self.assertRaises(ValueError, msg=bad):
                sandbox.profile(root, bad)


if __name__ == "__main__":
    unittest.main()
