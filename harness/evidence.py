"""실행 증거 기록(작업 계약 1단계): 장부에 허용한 필드만 크기 제한해 남긴다. 전체 프롬프트·Gold 정답·도구 출력은 남기지 않는다.

- 원인(cause)과 결과(outcome)는 별도 필드다. 원인은 근거가 있는 것만(claude_run.run_once 참조), 결과는
  not_started | completed | checkpoint | partial | unknown.
- stderr는 비밀처럼 보이는 값(이름=값·따옴표 JSON 값·sk-·ghp_·github_pat_·AKIA·xox 접두어·Bearer)을 가린 뒤 끝부분 STDERR_TAIL자만
  남긴다(가림은 최선 노력, 한계는 인계). 권한 거절은 tool_name·tool_use_id·file_path만 남긴다.
- CLI 인자는 모델·effort·권한·세션·출력 형식 옵션과 그 값만 남긴다(프롬프트 본문 제외).
호출 깊이: 모든 함수가 말단이다(서로·다른 harness 함수를 부르지 않는다. claude_record는 mask를 부르므로 1).
"""
import json
import os
import re

STDERR_TAIL = 2000
MASK_MARGIN = 500  # 자르기 전에 가리는 여유 글자 수(경계에서 잘린 키를 가리되 전체 출력을 훑지 않게)
VALUE_LIMIT = 200
MAX_DENIALS = 20
_SECRETS = re.compile(  # 이름=값(따옴표·JSON 포함)과 알려진 비밀 접두어. 최선 노력이며 형식이 다른 비밀은 남을 수 있다(인계)
    r"(?i)([\"']?[a-z0-9_-]{0,40}(?:api[_-]?key|token|secret|password|passwd|authorization|cookie|access[_-]?key)[a-z0-9_-]{0,40}[\"']?"
    r"\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s,\"'}]+|"
    r"sk-[a-z0-9_-]{8,}|gh[opsur]_[a-z0-9]{8,}|github_pat_[a-z0-9_]{8,}|(?:AKIA|ASIA)[0-9a-z]{12,}|xox[abprs]-[a-z0-9-]{8,}|"
    r"bearer\s+[^\s\"']+")
OPTION_FLAGS = {"--model": 1, "--effort": 1, "--permission-mode": 1, "--tools": 1, "--allowedTools": 1,
                "--disallowedTools": 1, "--output-format": 1, "--resume": 1, "--session-id": 1, "--restricted": 0,
                "--strict-mcp-config": 0, "--disable-slash-commands": 0, "--verbose": 0}


def mask(text, limit=STDERR_TAIL):
    """비밀처럼 보이는 값을 [가림]으로 바꾼 뒤 끝부분 limit자. 끝부분 limit + MASK_MARGIN자를 먼저 가리고 자른다(경계에서 잘린 키 조각이
    남지 않게, 검증 결함 F7). 한계: MASK_MARGIN보다 긴 비밀 값이 경계에 걸리면 조각이 남을 수 있다."""
    return _SECRETS.sub(lambda m: (m.group(1) or "") + "[가림]", (text or "")[-(limit + MASK_MARGIN):])[-limit:]


def options_of(argv):
    """argv에서 OPTION_FLAGS와 그 값만(순서 유지). 프롬프트(-p 다음 값)와 실행 파일 경로는 넣지 않는다."""
    kept, i = [], 0
    while i < len(argv):
        width = OPTION_FLAGS.get(argv[i])
        if width is not None:
            kept.extend(str(a)[:VALUE_LIMIT] for a in argv[i:i + 1 + width])
            i += width
        i += 1
    return kept


def outcome_of(task_dir, task, found, run_token=None):
    """Claude 실행 결과: not_started(실행 못 함) | completed(성공 + Claude 완료 선언이 이번 실행의 run_token·계약 outputs와 맞음) |
    partial(산출물 일부·전부가 있지만 완료로 볼 근거 없음) | unknown. 산출물 내용은 읽지 않는다(존재만). 실행 직전에 이전 선언을 지우므로
    (claude_job.execute) 선언은 이번 실행이 쓴 것이고, run_token으로 한 번 더 확인한다(검증 결함 F4)."""
    if found.get("cause") == "spawn_error":
        return "not_started"
    out_dir = os.path.join(task_dir, "out")
    try:
        with open(os.path.join(out_dir, ".harness_complete.json"), encoding="utf-8") as handle:
            said = json.load(handle)
    except (OSError, ValueError):
        said = None
    if found.get("success") and isinstance(said, dict) and said.get("task_key") == os.path.basename(task_dir) \
            and run_token is not None and said.get("run_token") == run_token \
            and isinstance(said.get("outputs"), list) and sorted(said["outputs"]) == sorted(task["outputs"]):
        return "completed"
    if any(os.path.isfile(os.path.join(out_dir, rel)) for rel in task["outputs"]):
        return "partial"
    return "unknown"


def claude_record(found, cwd, duration_s, outcome):
    """한 번의 claude 실행 증거(허용 필드만). found는 claude_run.run_once 결과."""
    result = found.get("result") if isinstance(found.get("result"), dict) else {}
    denials = result.get("permission_denials")
    limit = found.get("rate_limit") or {}
    return {"returncode": found.get("returncode"), "signal": found.get("signal"), "cause": found.get("cause"),
            "outcome": outcome, "result_subtype": str(result.get("subtype"))[:VALUE_LIMIT] if result else None,
            "is_error": result.get("is_error") if result else None,
            "permission_denials": [{k: mask(str(v), VALUE_LIMIT) for k, v in (
                ("tool_name", d.get("tool_name")), ("tool_use_id", d.get("tool_use_id")),
                ("file_path", (d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}).get("file_path")))
                if v is not None} for d in denials[:MAX_DENIALS] if isinstance(d, dict)]
            if isinstance(denials, list) else None,  # 도구 이름·호출 ID·대상 경로만(쓰려던 본문 등 도구 입력은 남기지 않는다, F9)
            "rate_limit": {k: (None if limit.get(k) is None else repr(limit.get(k))[:VALUE_LIMIT])
                           for k in ("resets_at_raw", "type_raw", "status")} if limit else None,
            "stderr_tail": mask(found.get("stderr")), "error": mask(found.get("error"), VALUE_LIMIT) or None,
            "options": options_of(found.get("argv") or []), "cwd": cwd, "duration_s": duration_s,
            "last_event": found.get("last_event"), "events": found.get("events"), "bad_lines": found.get("bad_lines")}
