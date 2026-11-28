"""자동 재개 시험 공용 도구(시험 없음). 실제 활성화 목록 claude_perm.AUTO_RESUME은 비어 있다: 재개 절차 자체를 시험할 때만
합성 증거 파일로 그 유형을 켠다(실환경 증거가 아니다)."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

from harness import claude_perm

SUPERVISOR_WRAP = (  # 시험 전용: 하위 프로세스 Supervisor 안에서만 활성화 목록을 바꾼 뒤 python -m harness.supervisor와 같은 일을 한다
    "import json, sys\nfrom harness import claude_perm, supervisor\n"
    "claude_perm.AUTO_RESUME.update(json.loads(sys.argv[1]))\n"
    "result = supervisor.run(**supervisor._args(sys.argv[2:]))\n"
    "print(json.dumps(result, sort_keys=True, ensure_ascii=False), flush=True)\n"
    "sys.exit(4 if result.get('already_running') else 0)\n")


def _entry(case):
    """합성 증거 파일을 만들고 활성화 목록 항목({"evidence": 절대 경로, "sha256"})을 돌려준다."""
    base = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, base, True)
    path = os.path.join(base, "evidence.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("합성 시험용 증거(실환경 아님)\n")
    with open(path, "rb") as handle:
        return {"evidence": path, "sha256": hashlib.sha256(handle.read()).hexdigest()}


def allow_resume(case, task_type):
    """그 작업 유형의 자동 재개를 켠 상태(mock.patch.dict 문맥)."""
    return mock.patch.dict(claude_perm.AUTO_RESUME, {task_type: _entry(case)})


def resumable_supervisor(case, task_type):
    """그 유형의 자동 재개를 켠 하위 프로세스 Supervisor argv(뒤에 --root 등을 붙인다. cwd=REPO)."""
    return [sys.executable, "-c", SUPERVISOR_WRAP, json.dumps({task_type: _entry(case)})]
