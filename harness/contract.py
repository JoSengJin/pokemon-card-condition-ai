"""작업 계약 검증, task_key(입력 해시), run_id(시도) 발급.

완료 표시(작업 계약 2단계): COMPLETION(작업 폴더의 complete.json) = {"task_key", "outputs": {상대 경로: sha256}}. Python 작업은 executor가
정상 반환한 뒤 runner가, Claude 작업은 claude가 성공 종료하고 DECLARATION(out/ 안, Claude가 마지막에 쓰는 {"task_key", "outputs": [경로]})이
계약과 맞을 때 claude_job이 원자적으로 쓴다. queue.complete는 이 표시가 산출물 해시와 맞을 때만 완료한다. 두 이름은 outputs로 쓸 수 없다.
"""
import hashlib
import json
import re
import uuid


class ContractError(ValueError):
    pass


_REQUIRED = {
    "task_type": str, "inputs": dict, "outputs": list, "depends_on": list,
    "needs_llm": bool, "needs_vision": bool, "risk": str,
    "retry_policy": dict, "escalation_level": int,
}
_OPTIONAL = {"expected_minutes": (int, float), "run_conditions": dict}  # run_conditions 규칙은 dedupe.py
COMPLETION = "complete.json"
DECLARATION = ".harness_complete.json"
ENQUEUE_LOCK = "enqueue.lock"  # root 아래 등록 잠금 파일(중복 검사와 저장을 한 번에: queue.enqueue·graph.register_missing, 2차 결함 G4)
_HEX64 = re.compile(r"[0-9a-f]{64}")
RUN_ID = re.compile(r"[0-9a-f]+")  # 실패 기록 파일 이름(failures/NNN-<run_id>.json)과 같은 규칙


def task_key(task):
    """같은 계약이면 같은 키(정규화 JSON의 sha256). expected_minutes(예상 시간 힌트)만 키에서 뺀다. JSON으로 적을 수 없는 계약(NaN·무한대·
    Python 3.11+ 정수 변환 상한을 넘는 정수·JSON이 아닌 값·너무 깊은 중첩)은 ContractError(4차 결함 I2: 등록 경로 밖으로 다른 예외를 내지 않는다)."""
    body = {k: v for k, v in task.items() if k != "expected_minutes"}
    try:
        text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ContractError("계약을 JSON으로 정규화할 수 없다: %s: %s" % (type(exc).__name__, str(exc)[:200]))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_key(key):
    """task_key는 소문자 16진 64자만 허용(경로 구성에 쓰이므로 절대 경로·.. 등을 거절)."""
    if not isinstance(key, str) or not _HEX64.fullmatch(key):
        raise ContractError("task_key 형식 오류(소문자 16진 64자): %r" % (key,))
    return key


def check_run_id(run_id):
    """run_id는 소문자 16진(new_run_id가 만드는 형식). 파일 이름에 쓰이므로 다른 형식은 거절한다."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ContractError("run_id 형식 오류(소문자 16진): %r" % (run_id,))
    return run_id


def new_run_id():
    return uuid.uuid4().hex


def validate_contract(task):
    """계약 검증(다른 함수를 부르지 않는 말단 함수). 위반은 ContractError."""
    if not isinstance(task, dict):
        raise ContractError("계약은 dict여야 한다")
    allowed = dict(_REQUIRED, **_OPTIONAL)
    extra = sorted(set(task) - set(allowed))
    missing = sorted(set(_REQUIRED) - set(task))
    if extra or missing:
        raise ContractError("알 수 없는 필드 %s / 빠진 필드 %s" % (extra, missing))
    for name, typ in allowed.items():
        if name in task and (not isinstance(task[name], typ) or
                             (typ is not bool and isinstance(task[name], bool))):
            raise ContractError("필드 %s 타입 오류" % name)
    outputs = task["outputs"]
    if not task["task_type"] or not task["risk"]:
        raise ContractError("task_type·risk는 비어 있을 수 없다")
    if not outputs or len(set(outputs)) != len(outputs):
        raise ContractError("outputs는 비어 있지 않고 중복이 없어야 한다(산출물 해시로만 완료를 인정)")
    for rel in outputs:
        parts = rel.split("/") if isinstance(rel, str) else None
        if not parts or rel.startswith("/") or any(p in ("", ".", "..") for p in parts) or rel == DECLARATION:
            raise ContractError("outputs는 안전한 상대 경로여야 한다(완료 표시 이름 제외): %r" % (rel,))
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in task["inputs"].items()):
        raise ContractError("inputs는 경로→SHA 문자열 사전이어야 한다")
    if not all(isinstance(d, str) and _HEX64.fullmatch(d) for d in task["depends_on"]):
        raise ContractError("depends_on은 task_key(sha256 16진 64자) 목록이어야 한다")
    retries = task["retry_policy"].get("max_transient_retries", 2)
    if set(task["retry_policy"]) - {"max_transient_retries"} or isinstance(retries, bool) \
            or not isinstance(retries, int) or not 0 <= retries <= 2:
        raise ContractError("retry_policy는 max_transient_retries(0~2)만 허용한다")
    if task["escalation_level"] < 0 or task.get("expected_minutes", 0) < 0:
        raise ContractError("escalation_level·expected_minutes는 0 이상이어야 한다")
    return task
