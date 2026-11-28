"""B6 사칭 방지: sandbox 안 executor가 제어 진입점(stop)을 부르거나 상태 파일을 고쳐도 사용자 중단은 바뀌지 않는다. runner가 쓰는 것과 같은
sandbox.run_one(실제 sandbox-exec 하위 프로세스, 운영 프로필 그대로)으로 이 모듈의 EXECUTORS를 실행한다. 한계: sandbox 밖의 같은 macOS 사용자
프로세스(대화형 Claude·Codex·셸)는 막지 않는다."""
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from functools import partial

from harness import control, opstate, queue, sandbox
from harness.jsonio import write_json
from tests.test_harness_status_collect import tree
from tests.test_harness_support import make_contract


def meddle(task, out_dir):
    """하네스 root(task.inputs.root)의 중단을 풀거나 흉내 내려는 시도. 결과를 산출물 result.txt에 남긴다."""
    root, got = task["inputs"]["root"], {}
    state, supervisor_dir = os.path.join(root, opstate.OPSTATE), os.path.join(root, "supervisor")
    for command in task["inputs"]["commands"].split():
        done = subprocess.run([sys.executable, "-m", "harness.control", command, "--root", root], capture_output=True, text=True,
                              timeout=60)
        printed = io.StringIO()
        with redirect_stdout(printed):  # 하위 프로세스 없이 함수를 직접 부르는 경로
            direct = control.main([command, "--root", root])
        got[command] = [done.returncode, done.stdout, direct, printed.getvalue()]
    tries = {"clear_by_user": partial(opstate.clear_by_user, root, opstate.USER_STOPPED, time.time(), "사칭", actor="user"),
             "overwrite": partial(open, state, "w"),
             "replace": partial(write_json, state, {"conditions": {}}),
             "remove": partial(os.remove, state),
             "move_folder": partial(os.rename, supervisor_dir, supervisor_dir + ".old"),
             "ledger": partial(open, os.path.join(root, "ledger.jsonl"), "a")}
    for name, attempt in tries.items():
        try:
            attempt()
            got[name] = "written"
        except OSError as exc:
            got[name] = type(exc).__name__
    pathlib.Path(out_dir, "result.txt").write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    return ["result.txt"]


EXECUTORS = {"meddle": meddle}


def attack(root, commands):
    out_dir = os.path.join(tempfile.mkdtemp(), "out")
    job = {"inputs": {"root": root, "commands": commands}, "outputs": ["result.txt"]}
    sandbox.run_one(root, "tests.test_harness_control_sandbox:EXECUTORS", "meddle", job, out_dir)
    return json.loads(pathlib.Path(out_dir, "result.txt").read_text(encoding="utf-8"))


class ControlSandboxTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(sandbox.available())
        self.root = tempfile.mkdtemp()
        queue.enqueue(self.root, make_contract(), 1.0)

    def test_sandboxed_executor_cannot_change_a_user_stop(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(control.main(["stop", "--root", self.root]), 0)
        before = tree(self.root)
        got = attack(self.root, "stop")
        self.assertEqual({k: v for k, v in got.items() if k != "stop"},
                         dict.fromkeys(("clear_by_user", "overwrite", "replace", "remove", "move_folder", "ledger"),
                                       "PermissionError"))
        self.assertIn("이미 중단 상태", got["stop"][1])
        self.assertEqual(tree(self.root), before)  # 상태·장부 바이트와 mtime까지 그대로

    def test_sandboxed_stop_fails_honestly_and_changes_nothing(self):
        os.makedirs(os.path.join(self.root, "supervisor"))
        before = tree(self.root)
        code, out, direct, printed = attack(self.root, "stop")["stop"]
        self.assertEqual((code, direct), (1, 1), out)
        for text in (out, printed):
            self.assertIn("중단을 기록하지 못함", text)
            self.assertNotIn("중단 기록 확인", text)
        self.assertEqual(tree(self.root), before)
        self.assertEqual(opstate.effective(opstate.load(self.root)), opstate.RUNNING)


if __name__ == "__main__":
    unittest.main()
