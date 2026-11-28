"""code-check의 runner 연결(runner._execute)과 실제 sandbox-exec 안 어댑터 확인. 가짜 저장소만 쓴다(실제 실험·봉인 자료 없음)."""
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from harness import claude_perm, experiment_exec, runner, sandbox
from harness.experiment_exec import CHECK_ENV, CHECK_NAME
from tests.harness_code_check_kit import GIT, make_world

SANDBOX_CHILD = r'''
import json, os, subprocess, sys
from harness import experiment_exec as e
task, src, tdir, run = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
def errno_of(action):
    try:
        action()
        return "ok"
    except OSError as exc:
        return exc.errno
def overwrite():
    open(os.path.join(tdir, "code-check.json"), "r+b").write(b"{}")
def create():
    open(os.path.join(tdir, "other.json"), "wb").write(b"{}")
def replace():
    open(os.path.join(run, "tmp", "forged"), "wb").write(b"{}")
    os.replace(os.path.join(run, "tmp", "forged"), os.path.join(tdir, "code-check.json"))
def staged():
    open(os.path.join(run, "out", "ok"), "wb").write(b"1")
try:
    e.check_code(task, src)
    checked = "ok"
except e.ExperimentError:
    checked = "refused"
git = subprocess.run(["git", "-C", src, "rev-parse", "HEAD"], capture_output=True).returncode
print(json.dumps({"writes": [errno_of(f) for f in (overwrite, create, replace, staged)], "checked": checked, "git": git}))
'''


class CodeCheckRunTest(unittest.TestCase):
    def test_runner_does_not_call_the_executor_when_the_result_cannot_be_recorded(self):
        make_world(self)
        seen = []

        def spy(task, out_dir):
            seen.append(os.environ[CHECK_ENV])
            experiment_exec.check_code(task, self.src)  # 같은 프로세스에서 어댑터 확인까지(실제 executor 경로와 같은 함수)
            return []
        task = dict(self.task, task_type="experiment", inputs={}, outputs=[])
        task["run_conditions"] = dict(task["run_conditions"], command=["x"])
        root, out_dir = os.path.join(self.base, "root"), os.path.join(self.tdir, "out")
        with mock.patch.object(runner.dedupe, "verify_code", return_value={}):
            self.assertIsNone(runner._execute(root, {"experiment": spy}, task, out_dir, self.src))
            self.assertEqual(seen, [os.path.join(self.tdir, CHECK_NAME)])
            subprocess.run(GIT + ["-C", self.src, "update-index", "--add", "--cacheinfo", "160000,%s,mod" % self.head], check=True, capture_output=True)
            subprocess.run(GIT + ["-C", self.src, "commit", "-q", "-m", "gitlink"], check=True, capture_output=True)
            head = subprocess.run(GIT + ["-C", self.src, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            task["run_conditions"]["code_sha"] = head  # submodule(160000) 항목은 blob으로 재계산할 수 없다 → 기록 실패
            failed = runner._execute(root, {"experiment": spy}, task, out_dir, self.src)
        self.assertEqual((failed[0], failed[2], len(seen)), ("deterministic", "not_started", 1))  # executor 호출 안 함, 예산 취소 대상 상태

    def test_sandboxed_adapter_cannot_write_the_result_and_checks_it_without_git(self):
        make_world(self)
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        run = os.path.join(self.base, "run")
        for sub in ("out", "tmp"):
            os.makedirs(os.path.join(run, sub), exist_ok=True)
        prof = sandbox.profile(os.path.join(self.base, "root"), run, claude_perm.sealed_paths([sandbox.REPO, self.src]))
        argv = [sandbox.SANDBOX_EXEC, "-p", prof, sys.executable, "-B", "-c", SANDBOX_CHILD, json.dumps(self.task), self.src, self.tdir, run]

        def child():
            done = subprocess.run(argv, cwd=sandbox.REPO, capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            return json.loads(done.stdout.strip().split("\n")[-1]), done.stderr[-300:]
        first, err = child()
        self.assertEqual((first["writes"], first["checked"]), ([1, 1, 1, "ok"], "ok"), err)  # 작업 폴더 쓰기·덮어쓰기·교체 EPERM, staging만 쓸 수 있다
        self.assertNotEqual(first["git"], 0)  # sandbox 안에서는 git이 저장소를 못 읽는다(이 경로가 필요한 이유)
        self.assertEqual(subprocess.run(["git", "-C", self.src, "rev-parse", "HEAD"], capture_output=True).returncode, 0)  # 대조: sandbox 밖은 읽는다
        with open(os.path.join(self.src, "a.py"), "w", encoding="utf-8") as handle:
            handle.write("print(2)\n")  # runner 검증 뒤 실행 대상 변경
        self.assertEqual(child()[0]["checked"], "refused")
        self.assertEqual(json.load(open(self.path, encoding="utf-8"))["code_sha"], self.head)  # 결과 파일은 그대로


if __name__ == "__main__":
    unittest.main()
