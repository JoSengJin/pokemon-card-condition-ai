"""`./experiment` 실행 어댑터(B5-8, 합성 단계). **실제 ./experiment 연결: 미완료.** 어떤 executor 표에도 등록하지 않았고 runner가 부르지 않는다.

사용자 결정(2026-11-28): B5는 실행 어댑터 계약과 합성 시험까지 하고 기존 sandbox 보안 원칙(executor는 실행별 staging에만 쓴다)을 유지한다.
실제 연결(저장소 artifacts/ 쓰기·workspace.lock이 필요해 sandbox 밖 실행이 된다)의 최소 권한·실행 경로는 첫 실험 후보 승인 때 검토한다
(초안: docs/collaboration/tasks/harness-b5-indep-20261128.md). 합성 시험 통과는 실제 실험 실행부터 다음 가설 생성까지의 검증이 아니다.

계약(task_type "experiment", outputs = OUTPUTS):
- 실행 파일은 계약이 아니라 어댑터가 정한다: <workdir>/experiment. 계약 command는 `--` 뒤에만 붙는다(옵션 주입 불가).
- 계획 JSON은 계약에서만 만든다: run_conditions.config.plan(실행 조건: reference_result·acceptance·code_changes 등, 논리 키에 들어감)
  + 설명 키 hypothesis_id·description{hypothesis, change, success_criterion, failure_criterion}(논리 키에서 빠짐: 문구만 다른 같은 실험은
  dedupe가 중복으로 거절). config.plan이 설명 키를 덮어쓰면 거절. 그 밖의 plan 내용 검사는 ./experiment(prepare)가 한다.
- 실행 전 code_sha를 workdir HEAD와 다시 대조한다(dedupe.verify_code, 추적 파일 변경도 거절).
- 결과 해석(interpret): 종료 코드와 record.json 상태가 함께 맞아야 한다. 0+completed(+result.json 해시가 record files와 같음) = 완료,
  1+failed = 실험 자체 실패(결정적), 128 초과+interrupted = 중단, 출력에 기록 줄이 없고 1(잠금 사용 중)·2(계획 오류) 안내문 = 실행 안 됨
  (not_started: 예산 차감 취소 후보, 결정 3). 그 밖(불일치·running·기록 경로가 workdir/artifacts/experiments 밖·명령/가설 불일치·시간 초과·
  신호로 죽음)은 결과 불명(unknown).
- 오류는 ExperimentError(종류, {"status", ...}). 종류는 runner 실패 종류와 같다: deterministic(거절·실패·not_started),
  interrupted(중단·결과 불명: 작업권을 남겨 INTERRUPTED → 결과 확인 전 대기. 재실행 안전 목록은 비어 있어 자동 재실행되지 않는다).
한계: 시간 초과 때 subprocess.run은 직접 자식만 죽인다(실제 ./experiment가 띄운 프로세스 그룹은 남을 수 있다 → 결과 불명으로 둔다).
호출 깊이: run → interpret → cas.sha_file (2), run → dedupe.verify_code (1), run → build_plan (1).
"""
import json
import os
import re
import shutil
import subprocess

from . import cas, dedupe
from .contract import ContractError
from .jsonio import write_json

OUTPUTS = ("plan.json", "record.json", "result.json")
TEXT_KEYS = ("hypothesis", "change", "success_criterion", "failure_criterion")
_LINE = re.compile(r"^실험 기록: (.+) / 상태: (\S+)$", re.M)
_NOT_STARTED = {1: "다른 개발·실험·검토가 진행 중입니다", 2: "실험 계획·기준 결과·코드 경로를 확인하세요"}
_ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "PYTHONIOENCODING": "utf-8"}


class ExperimentError(Exception):
    """args = (종류 deterministic|interrupted, {"status": refused|failed|not_started|interrupted|unknown, "detail": ...})."""


def build_plan(task):
    """계약 → 계획 dict. 형식이 맞지 않으면 ExperimentError(deterministic, refused). 말단."""
    cond = task.get("run_conditions") if isinstance(task.get("run_conditions"), dict) else {}
    plan, text = (cond.get("config") or {}).get("plan"), cond.get("description")
    if not isinstance(plan, dict) or not plan or set(plan) & set(TEXT_KEYS + ("hypothesis_id",)):
        raise ExperimentError("deterministic", {"status": "refused", "detail": "config.plan이 없거나 설명 키를 덮어쓴다"})
    if not isinstance(text, dict) or set(text) != set(TEXT_KEYS) or not all(isinstance(v, str) and v.strip() for v in text.values()) \
            or not isinstance(cond.get("hypothesis_id"), str) or not cond["hypothesis_id"].strip():
        raise ExperimentError("deterministic", {"status": "refused", "detail": "hypothesis_id·description(%s)이 필요하다" % (TEXT_KEYS,)})
    return dict(plan, hypothesis_id=cond["hypothesis_id"], **text)


def interpret(code, stdout, workdir, command, hypothesis_id):
    """(상태, 실험 폴더 또는 None). 상태: completed|failed|interrupted|not_started|unknown. 말단에 가깝다(cas.sha_file만 부른다)."""
    found = _LINE.findall(stdout or "")
    if not found:
        hint = _NOT_STARTED.get(code)
        return ("not_started" if hint and hint in (stdout or "") else "unknown"), None
    if len(found) != 1:
        return "unknown", None
    path, said = found[0]
    base = os.path.realpath(os.path.join(workdir, "artifacts", "experiments"))
    folder = os.path.dirname(os.path.realpath(path))
    if os.path.basename(path) != "record.json" or os.path.dirname(folder) != base or os.path.islink(path) or not os.path.isfile(path):
        return "unknown", None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return "unknown", None
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("status") != said \
            or record.get("command") != command or record.get("hypothesis_id") != hypothesis_id:
        return "unknown", None
    result = os.path.join(folder, "result.json")
    if said == "completed" and code == 0 and os.path.isfile(result) and not os.path.islink(result) \
            and cas.sha_file(result) == (record.get("files") or {}).get("result.json"):
        return "completed", folder
    if (said, code) == ("failed", 1):
        return "failed", folder
    if said == "interrupted" and code > 128:
        return "interrupted", folder
    return "unknown", folder


def run(task, out_dir, workdir, timeout=None):
    """계약의 실험 하나를 <workdir>/experiment로 실행한다. 완료면 OUTPUTS(out_dir 안 사본) 목록, 아니면 ExperimentError."""
    if task.get("task_type") != "experiment" or sorted(task.get("outputs") or []) != sorted(OUTPUTS):
        raise ExperimentError("deterministic", {"status": "refused", "detail": "experiment 유형·outputs %s만 받는다" % (OUTPUTS,)})
    plan = build_plan(task)
    try:
        dedupe.verify_code(task, workdir)  # 실행 직전 code_sha = workdir HEAD, 추적 파일 변경 없음
    except ContractError as exc:
        raise ExperimentError("deterministic", {"status": "refused", "detail": str(exc)})
    command = task["run_conditions"]["command"]
    write_json(os.path.join(out_dir, "plan.json"), plan)
    argv = [os.path.join(workdir, "experiment"), "--plan", os.path.join(os.path.abspath(out_dir), "plan.json"), "--"] + list(command)
    try:
        done = subprocess.run(argv, cwd=workdir, env=_ENV, stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise ExperimentError("interrupted", {"status": "unknown", "detail": "time_budget"})
    except OSError as exc:  # 실행 파일을 띄우지 못함: 실행되지 않았음이 확인된 경우
        raise ExperimentError("deterministic", {"status": "not_started", "detail": str(exc)})
    status, folder = interpret(done.returncode, done.stdout, workdir, list(command), plan["hypothesis_id"])
    info = {"status": status, "return_code": done.returncode, "experiment_dir": folder}
    if status == "completed":
        for name in ("record.json", "result.json"):
            shutil.copyfile(os.path.join(folder, name), os.path.join(out_dir, name))
        with open(os.path.join(out_dir, "record.json"), "r", encoding="utf-8") as handle:  # 사본을 다시 대조(해석과 복사 사이 변경)
            copied = json.load(handle)
        if copied.get("status") == "completed" and cas.sha_file(os.path.join(out_dir, "result.json")) == copied["files"].get("result.json"):
            return list(OUTPUTS)
        info["status"] = "unknown"
    raise ExperimentError("deterministic" if status in ("failed", "not_started") else "interrupted", info)
