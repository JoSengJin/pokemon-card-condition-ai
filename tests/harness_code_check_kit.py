"""code-check(experiment_exec.record_code·check_code) 시험 공용: 가짜 저장소·가짜 봉인 목록·runner 쪽 기록까지 만든다(실제 실험·봉인 자료 없음)."""
import json
import os
import shutil
import subprocess
import tempfile
from unittest import mock

from harness import claude_perm, experiment_exec

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def make_world(case):
    """case에 base·src·tdir(작업 폴더)·head·task·path(code-check.json)를 넣는다. 가짜 저장소 src: experiment·a.py·sub/b.txt·링크 ln·
    봉인 목록 아래 vault/s.json. 환경변수 CHECK_ENV는 runner처럼 path로 둔다. 정리는 case에 등록한다."""
    case.base = os.path.realpath(tempfile.mkdtemp(prefix="code-check-"))
    case.addCleanup(shutil.rmtree, case.base, True)
    case.src, case.tdir = os.path.join(case.base, "src"), os.path.join(case.base, "root", "tasks", "k")
    for rel, body in (("experiment", "#!/bin/sh\n"), ("a.py", "print(1)\n"), ("sub/b.txt", "bbb\n"), ("vault/s.json", "{}\n")):
        os.makedirs(os.path.dirname(os.path.join(case.src, rel)), exist_ok=True)
        with open(os.path.join(case.src, rel), "w", encoding="utf-8") as handle:
            handle.write(body)
    os.chmod(os.path.join(case.src, "experiment"), 0o755)
    os.symlink("sub/b.txt", os.path.join(case.src, "ln"))
    os.makedirs(case.tdir)
    listing = os.path.join(case.base, "sealed.json")
    with open(listing, "w", encoding="utf-8") as handle:
        json.dump({"paths": ["vault"]}, handle)
    for step in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"]):
        subprocess.run(GIT + ["-C", case.src] + step, check=True, capture_output=True)
    case.head = subprocess.run(GIT + ["-C", case.src, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    case.task = {"run_conditions": {"code_sha": case.head}}
    for patcher in (mock.patch.object(claude_perm, "SEALED_LIST", listing), mock.patch.dict(os.environ, {}, clear=False)):
        patcher.start()
        case.addCleanup(patcher.stop)
    case.path = experiment_exec.record_code(case.task, case.tdir, case.src)
    os.environ[experiment_exec.CHECK_ENV] = case.path


def refused(task, workdir):
    """check_code가 (deterministic, refused)로 거절하면 True, 통과하면 False."""
    try:
        experiment_exec.check_code(task, workdir)
    except experiment_exec.ExperimentError as exc:
        return exc.args[0] == "deterministic" and exc.args[1]["status"] == "refused"
    return False


def edit(path, files=None, drop=None, top=None):
    """code-check 파일을 읽어 top(최상위 키)·files(files 항목) 갱신, drop(files 항목 삭제) 뒤 같은 이름으로 새로 쓴다(링크·하드 링크도 끊는다)."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.update(top or {})
    data["files"].update(files or {})
    data["files"].pop(drop, None)
    os.remove(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
