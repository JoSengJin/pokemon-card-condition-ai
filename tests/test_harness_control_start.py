"""B6-4 시작: Supervisor를 별도 세션으로 띄우고 확인한 사실만 보고한다. 가짜 claude와 합성 executors만 쓴다(실제 claude·모델 호출 없음).
시험이 띄운 프로세스는 끝난 것을 확인한다."""
import fcntl
import io
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from harness import control, lease, opstate, queue, status
from tests.test_harness_runner_kit import task
from tests.test_harness_supervisor_kit import events, llm_task, make_fake, runs
from tests.test_harness_support import REPO


def quiet(task_, out_dir):
    """운영 sandbox 그대로 도는 합성 executor(out_dir에만 쓴다)."""
    pathlib.Path(out_dir, "result.txt").write_text("ok")
    return ["result.txt"]


EXECUTORS = {"calc": quiet}
SPEC = "tests.test_harness_control_start:EXECUTORS"


def start(case, root, *args, cwd=REPO):
    """제어 명령줄로 start. (종료 코드, 출력). 띄운 pid가 있으면 시험 끝에 죽이고 없어진 것을 확인하게 등록한다."""
    done = subprocess.run([sys.executable, "-m", "harness.control", "start", "--root", root] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1"))
    for pid in map(int, re.findall(r"pid (\d+)", done.stdout)):
        case.addCleanup(gone, case, pid)
    return done.returncode, done.stdout + done.stderr


def gone(case, pid, kill=True):
    """pid가 끝났는지 확인한다(kill이면 남아 있을 때 프로세스 그룹째 죽인다)."""
    if kill:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.time() + 60
    while lease.pid_alive(pid) and time.time() < deadline:
        time.sleep(0.1)
    case.assertFalse(lease.pid_alive(pid), pid)


class ControlStartTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.key = queue.enqueue(self.root, task("py"), 1.0)

    def finished(self, output):
        """--max-cycles 시작: 이미 끝났거나(pid 없음), 띄운 pid가 스스로 끝날 때까지 기다린다."""
        for pid in map(int, re.findall(r"pid (\d+)", output)):
            gone(self, pid, kill=False)

    def test_relative_paths_with_fake_claude_and_synthetic_executors_run_one_cycle(self):
        claude, log, _env = make_fake(self, [{"do": "success"}])
        llm = llm_task(self.root)
        outside = os.path.dirname(self.root)
        code, out = start(self, os.path.basename(self.root), "--claude-bin", os.path.relpath(claude, outside),
                          "--executors", SPEC, "--max-cycles", "1", cwd=outside)  # 부른 곳 기준 상대 경로
        self.assertEqual(code, 0, out)
        self.assertIn("Python 작업: 켬", out)
        self.assertIn("Claude 작업: 켬", out)
        self.finished(out)
        self.assertEqual(len(runs(log)), 1)
        self.assertEqual(sorted(e["data"]["task_key"] for e in events(self.root, "completed")), sorted([self.key, llm]))
        self.assertIs(status.supervisor_running(self.root), False)

    def test_without_explicit_binaries_nothing_is_executed(self):
        code, out = start(self, self.root, "--max-cycles", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("Python 작업: 끔", out)
        self.assertIn("Claude 작업: 끔", out)
        self.finished(out)
        self.assertEqual(status.collect(self.root, time.time())["tasks"]["counts"], {"PENDING": 1})
        self.assertEqual(events(self.root, "claimed"), [])

    def test_stopped_root_only_watches_and_a_second_start_is_refused(self):
        opstate.set_condition(self.root, opstate.USER_STOPPED, 1.0, "user", "중단")
        before = opstate.load(self.root)
        code, out = start(self, self.root, "--executors", SPEC, "--poll", "0.2")
        self.assertEqual(code, 0, out)  # 부모는 자식을 기다리지 않고 돌아온다(timeout=120 안에)
        self.assertIn("시작 확인", out)
        self.assertIn("정지 상태(USER_STOPPED)라 감시만", out)
        self.assertIn("start는 정지를 풀지 않는다", out)
        [pid] = map(int, re.findall(r"pid (\d+)", out))
        self.assertTrue(lease.pid_alive(pid))
        self.assertEqual(os.getpgid(pid), pid)  # 별도 세션: 부른 터미널이 닫혀도 남는다
        self.assertIs(status.supervisor_running(self.root), True)
        code, again = start(self, self.root, "--poll", "0.2")
        self.assertEqual(code, 4, again)
        self.assertIn("이미 실행 중", again)
        self.assertNotIn("pid", again.replace("pid·", ""))
        time.sleep(0.5)
        self.assertEqual(opstate.load(self.root), before)
        self.assertEqual(events(self.root, "claimed"), [])

    def test_failures_are_not_reported_as_started(self):
        sup = pathlib.Path(self.root, "supervisor")
        sup.joinpath("supervisor.lock").mkdir(parents=True)  # Supervisor가 잠금 파일을 못 열고 죽는다
        code, out = start(self, self.root)
        self.assertEqual(code, 1, out)
        self.assertIn("시작 실패", out)
        self.assertNotIn("시작 확인", out)
        sup.joinpath("supervisor.lock").rmdir()
        sup.joinpath("control_start.log").unlink()
        sup.joinpath("control_start.log").mkdir()  # 출력 기록 자리를 못 열면 띄우지 않는다
        with mock.patch.object(subprocess, "Popen") as spawned, redirect_stdout(io.StringIO()) as printed:
            code = control.main(["start", "--root", self.root])
        self.assertEqual((code, spawned.call_count), (1, 0), printed.getvalue())
        sup.joinpath("control_start.log").rmdir()  # 앞 단계의 실패 원인을 치운 뒤에 본다
        with mock.patch.object(status, "supervisor_running", return_value=None), \
                mock.patch.object(subprocess, "Popen") as spawned, redirect_stdout(io.StringIO()):
            self.assertEqual((control.main(["start", "--root", self.root]), spawned.call_count), (1, 0))  # 확인 불가: 시작 안 함

    def test_losing_the_race_reports_already_running(self):
        os.makedirs(os.path.join(self.root, "supervisor"))
        with open(os.path.join(self.root, "supervisor", "supervisor.lock"), "w") as other:
            fcntl.flock(other.fileno(), fcntl.LOCK_EX)
            with mock.patch.object(status, "supervisor_running", return_value=False), redirect_stdout(io.StringIO()) as printed:
                code = control.main(["start", "--root", self.root])  # 사전 확인 뒤에 다른 쪽이 먼저 잠근 경우
        self.assertEqual(code, 4, printed.getvalue())
        self.assertIn("이미 실행 중", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
