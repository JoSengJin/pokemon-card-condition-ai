"""B6-5 해제 시험 공용 도구(시험 없음): 해제 진입점·훅 진입점을 실제 하위 프로세스로 부른다(훅 설치 없음, 모의 입력)."""
import os
import re
import subprocess
import sys

from harness import opstate
from tests.test_harness_gold_support import launch
from tests.test_harness_support import REPO


def cli(*args):
    """(종료 코드, 표준 출력, 표준 오류) — 사람이 터미널에서 치는 진입점 그대로."""
    done = subprocess.run([sys.executable, "-m", "harness.control_release"] + list(args), cwd=REPO, capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return done.returncode, done.stdout, done.stderr


def hook(root, prompt):
    """설치하지 않은 훅 진입점에 모의 입력을 넣는다. (종료 코드, 표준 출력, 표준 오류)."""
    proc = launch(root, prompt)
    out, err = proc.stdout.read().decode("utf-8"), proc.stderr.read().decode("utf-8")
    proc.stdout.close()
    proc.stderr.close()
    return proc.wait(timeout=60), out, err


def code_in(text):
    return re.search(r"확인 코드: ([0-9]{6})", text).group(1)


def stopped(root):
    return opstate.USER_STOPPED in opstate.load(root)["conditions"]
