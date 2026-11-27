"""3단계 R6: 하네스가 띄운 Python executor(macOS sandbox-exec 하위 프로세스)는 사용자를 사칭해 정지를 풀거나 하네스 상태(장부·예산·
완료 표시)를 쓰지 못하고, 자기 산출물 폴더 쓰기는 된다. 실제 sandbox-exec 하위 프로세스로 시험한다."""
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from harness import lease, opstate, queue, runner, sandbox, states
from tests.test_harness_runner_kit import count, run, spawn_runner, task


class SandboxTest(unittest.TestCase):
    def test_r6_executor_cannot_lift_user_stop_or_write_harness_state(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        key = queue.enqueue(root, task("I", task_type="intruder"), 1.0)
        opstate.set_condition(root, opstate.USER_STOPPED, 1.0, "user", "RC 중단")  # 실행 중에 사용자가 건 정지(가정)
        summary = run(self, root, marks)
        with open(os.path.join(marks, "intruder.json"), encoding="utf-8") as handle:
            tried = json.load(handle)
        self.assertEqual(tried, {"clear_by_user": "PermissionError", "ledger": "PermissionError", "budget": "PermissionError",
                                 "completion": "PermissionError"})
        self.assertIn(opstate.USER_STOPPED, opstate.load(root)["conditions"])  # 사칭 해제 실패
        self.assertEqual(summary["done"], [key])  # 정상 산출물 쓰기는 유지
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.VERIFIED)


    def test_without_sandbox_exec_nothing_runs(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        key = queue.enqueue(root, task("U"), 1.0)
        printed = io.StringIO()
        with mock.patch.object(sandbox, "SANDBOX_EXEC", "/nonexistent/sandbox-exec"), \
                mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks}), redirect_stdout(printed):
            code = runner.main([root, "tests.test_harness_executors:EXECUTORS", "--max", "1"])
        self.assertEqual((code, json.loads(printed.getvalue())["executed"], count(marks, "U")), (runner.SANDBOX_EXIT, 0, 0))
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.PENDING)
        with self.assertRaises(ValueError):  # 프로필에 안전하게 적을 수 없는 경로는 거절
            sandbox.profile('/tmp/a"b')

    def test_executor_child_ends_when_its_runner_is_killed(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        queue.enqueue(root, task("S", task_type="slow"), 1.0)
        proc = spawn_runner(root, marks, {"HARNESS_SLOW": "hang"})
        self.addCleanup(proc.kill)
        deadline = time.time() + 30
        while not [n for n in os.listdir(marks) if n.startswith("S-start-")] and time.time() < deadline:
            time.sleep(0.05)
        [mark] = [n for n in os.listdir(marks) if n.startswith("S-start-")]
        child = int(mark.split("-")[2])  # 표식 이름의 pid = sandbox 안 executor 프로세스
        self.assertNotEqual(child, proc.pid)
        os.kill(proc.pid, signal.SIGKILL)
        proc.communicate()
        deadline = time.time() + 5
        while lease.pid_alive(child) and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(lease.pid_alive(child))  # 혼자 남아 다음 runner와 겹쳐 실행되지 않는다

    def test_runner_killed_ends_the_whole_executor_group_and_a_bad_table_is_a_clean_exit(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        queue.enqueue(root, task("G", task_type="slow"), 1.0)
        proc = spawn_runner(root, marks, {"HARNESS_SLOW": "hang_child"})
        self.addCleanup(proc.kill)
        deadline = time.time() + 30
        while not [n for n in os.listdir(marks) if n.startswith("G-start-")] and time.time() < deadline:
            time.sleep(0.05)
        [mark] = [n for n in os.listdir(marks) if n.startswith("G-child-")]
        grandchild = int(mark.split("-")[2])  # executor가 남긴 같은 그룹 자식(3차 변이 S39)
        os.kill(proc.pid, signal.SIGKILL)
        proc.communicate()
        deadline = time.time() + 5
        while lease.pid_alive(grandchild) and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(lease.pid_alive(grandchild))
        done = subprocess.run([sys.executable, "-m", "harness.runner", root, "tests.test_harness_boundary_kit:ALIASED"], cwd=sandbox.REPO,
                              capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        summary = json.loads(done.stdout.strip().split("\n")[-1])  # 3차 결함 H10: traceback 없이 요약과 결정적 종료 코드
        self.assertEqual((done.returncode, summary["executed"]), (runner.EXECUTOR_TABLE_EXIT, 0))
        self.assertIn("executor_table_error", summary)
        self.assertNotIn("Traceback", done.stderr)


if __name__ == "__main__":
    unittest.main()
