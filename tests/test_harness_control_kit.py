"""B6 제어 명령줄 시험 공용 도구(시험 없음). 합성 executors, 제어 명령줄 하위 프로세스 실행, 띄운 프로세스 종료 확인."""
import os
import pathlib
import re
import signal
import subprocess
import sys
import time

from harness import lease
from tests.test_harness_support import REPO


def quiet(task_, out_dir):
    """운영 sandbox 그대로 도는 합성 executor(out_dir에만 쓴다)."""
    pathlib.Path(out_dir, "result.txt").write_text("ok")
    return ["result.txt"]


EXECUTORS = {"calc": quiet}
SPEC = "tests.test_harness_control_kit:EXECUTORS"


def spawn(*args, cwd=REPO):
    return subprocess.Popen([sys.executable, "-m", "harness.control"] + list(args), cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            env=dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1"))


def cli(*args, cwd=REPO):
    """(종료 코드, 표준 출력 + 표준 오류)."""
    proc = spawn(*args, cwd=cwd)
    out, err = proc.communicate(timeout=120)
    return proc.returncode, out + err


def start(case, root, *args, cwd=REPO):
    """start 명령. (종료 코드, 출력, 출력에 나온 pid 목록). pid는 시험 끝에 죽이고 없어진 것을 확인하게 등록한다."""
    code, out = cli("start", "--root", root, *args, cwd=cwd)
    pids = [int(p) for p in re.findall(r"pid (\d+)", out)]
    for pid in pids:
        case.addCleanup(gone, case, pid)
    return code, out, pids


def gone(case, pid, kill=True):
    """pid가 끝났는지 확인한다(kill이면 남아 있을 때 프로세스 그룹째 죽인다. kill=False면 스스로 끝나기를 기다린다)."""
    if kill:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.time() + 60
    while lease.pid_alive(pid) and time.time() < deadline:
        time.sleep(0.1)
    case.assertFalse(lease.pid_alive(pid), pid)
