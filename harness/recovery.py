"""상태별 처리 결정(DESIGN 9절). decide()는 실행 계획(plan)을 돌려준다.

작업 계약 2단계(R1): 중단(INTERRUPTED)·일시 실패(FAILED transient)·복구 불가 손상(CORRUPT, 검증 N1) 작업의 자동 재개·재실행은
RERUN_SAFE_TYPES(코드에 등록, 기본 빈 집합) 유형만 한다. 실험·학습·평가(dedupe.CONDITION_TYPES)는 등록해도 자동 재실행하지 않는다(결과 불명). 그 밖은 await_result(결과 확인 대기):
원인·결과를 awaiting.json·장부(awaiting_result)에 한 번 남기고 알림(notification → 알림 장부)을 남긴다. 해제는 사람이 확인한 뒤
작업 폴더의 lease.json·awaiting.json을 정리하는 수동 절차다(자동 경로 없음). 첫 실행(PENDING)은 막지 않는다.
완료 표시(ct.COMPLETION)가 산출물과 맞는 INTERRUPTED는 재실행하지 않고 반영만 한다(adopt: 호출자가 executor를 부르지 않고 complete).
외부 요청을 보낸 뒤 결과를 모르는 실패는 일시 원인이 아니다: 등록 유형은 외부 요청이 없는 결정론 작업만이어야 한다(등록 조건).

호출 깊이 설계: decide는 아래 말단 함수들(_plan·_interrupted·_failed·_archive·checkpoint.check·new_run_id)만 부르고
말단은 서로를 부르지 않는다. CAS 복구(부수 효과)는 호출자(queue)가 cas.restore로 먼저 수행하고 결과(restored)만 넘긴다.
"""
import os
import socket

from . import checkpoint, dedupe, states
from .contract import RUN_ID, new_run_id
from .jsonio import write_json

RESUME_MIN_MINUTES = 30.0
# 설계에 없는 한도(메인이 제안한 값: 일시적 실패 재시도 한도와 같은 2, 사용자 확인 대기). 센 대상: 같은 작업이 비정상 종료한 뒤
# 체크포인트 없이(또는 진전 없이) 처음부터 다시 실행된 연속 횟수(rerun). 유효한 체크포인트로 이어받은 재개(resume)는 진전이
# 있으므로 세지 않고 0으로 초기화한다. 정상 종료(complete·fail)도 초기화한다. 넘으면 needs_failure_policy(too_many_interrupts)로 멈춘다.
MAX_INTERRUPTS = 2
RUNNABLE = ("run", "rerun", "retry", "resume", "adopt")
RERUN_SAFE_TYPES = frozenset()  # 재실행 안전으로 확인해 등록한 task_type(부작용·중복 반영 방지 확인 뒤에만 추가). 기본은 비어 있다


def kind_of(exc):
    """예외 -> 실패 종류. 네트워크 단절·시간 초과만 일시적, 나머지(코드 오류 포함)는 결정적이다."""
    return "transient" if isinstance(exc, (ConnectionError, TimeoutError, socket.timeout)) else "deterministic"


def _plan(action, reason="", run_id=None, resumed=False, events=(), extra=None):
    plan = {"action": action, "reason": reason, "runnable": action in RUNNABLE, "resumed": resumed,
            "run_id": run_id, "events": list(events)}
    plan.update(extra or {})
    return plan


def _deaths(prev):
    """중단된 작업권 기록의 이전 중단 횟수 + 이번 1회. 값이 손상됐으면 한도를 넘긴 것으로 본다(보수적)."""
    before = prev.get("interrupts", 0)
    if not isinstance(before, int) or isinstance(before, bool) or before < 0:
        return MAX_INTERRUPTS + 1
    return before + 1


def _archive(task_dir):
    """복구 불가한 완료 기록을 history/로 옮긴다(덮어쓰지 않고 보관). 완료 표시(COMPLETION)는 남긴다: 산출물 해시가 표시와 같을
    때만 반영되므로 손상된 산출물로는 반영되지 않고, 재실행이 끝나면 runner가 새 표시로 바꾼다."""
    hist = os.path.join(task_dir, "history")
    os.makedirs(hist, exist_ok=True)
    os.replace(os.path.join(task_dir, "done.json"), os.path.join(hist, "done-%03d.json" % (len(os.listdir(hist)) + 1)))


def _interrupted(prev, now, cp_reason):
    """30분 이상 실행했고 체크포인트 지문이 모두 일치(cp_reason이 None)할 때만 같은 run_id로 복원한다."""
    run_id, started = prev.get("run_id"), prev.get("ts")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) \
            or not isinstance(started, (int, float)) or isinstance(started, bool):
        why = "중단된 작업권 기록(16진 run_id·시작 시각)이 없거나 손상됨"
    elif (now - started) / 60.0 < RESUME_MIN_MINUTES:
        why = "실행 시간이 %d분 미만" % RESUME_MIN_MINUTES
    else:
        why = cp_reason
    if why is None:
        return ("resume", "체크포인트 일치", run_id, True, [("interrupted_resumed", {"run_id": run_id})])
    return ("rerun", why, None, False, [("interrupted_rerun", {"prev_run_id": run_id, "reason": why})])


def _failed(info):
    records = info["records"]
    kind, attempts = records[-1].get("kind"), len(records)
    allowed = info["contract"]["retry_policy"].get("max_transient_retries", 2)
    extra = {"failure_kind": kind, "attempts": attempts}
    if kind == "transient" and attempts <= allowed:
        return ("retry", "일시적 실패 재시도 %d/%d" % (attempts, allowed), None, False,
                [("retry_planned", extra)], extra)
    return ("needs_failure_policy", "결정적 실패" if kind != "transient" else "재시도 한도 소진", None, False, [], extra)


def decide(task_dir, state, info, now, current=None, restored=()):
    """상태 -> 계획. info는 states.facts 결과, current는 현재 실행 지문(없으면 복원하지 않는다),
    restored는 호출자가 CAS에서 방금 되살린 산출물 목록. CORRUPT 복구 불가 시 재실행 안전 유형만 완료 기록을 history/로 보관하고
    재실행하며, 그 밖은 완료 기록을 그대로 두고 결과 확인 대기다(검증 N1)."""
    task_type = info["contract"]["task_type"] if isinstance(info.get("contract"), dict) else None
    safe = task_type in RERUN_SAFE_TYPES and task_type not in dedupe.CONDITION_TYPES
    wait_for = None  # 결과 확인 대기: (사유, run_id, 원인, 오류 요약)
    if state == states.CORRUPT and info["contract_state"] != "ok":  # 계약이 변조·손상: 재실행하지 않고 멈춘다
        plan = _plan("blocked", "계약 파일이 손상되었거나 task_key와 맞지 않는다")
    elif state == states.CORRUPT and not safe:  # 완료한 단계는 다시 실행하지 않는다: 완료 기록을 보관하지 않고(PENDING이 되지 않게) 대기
        plan, wait_for = None, ("corrupt_unrecoverable", None, "unknown", "복구 불가: %s" % info["bad"])
    elif state == states.CORRUPT:
        _archive(task_dir)  # 계약이 정상인 CORRUPT는 done.json이 있는 경우뿐이다
        plan = _plan("rerun", "복구 불가: %s" % info["bad"], events=[("corrupt_unrecoverable", {"files": info["bad"]})])
    elif state == states.VERIFIED and restored:
        plan = _plan("skip", "CAS에서 복구하고 해시 재검증 통과", events=[("corrupt_restored", {"files": list(restored)})])
    elif state == states.INTERRUPTED and info.get("completion") == "ok":  # 완료 표시 직후에 죽었다: 반영만 한다
        plan = _plan("adopt", "완료 표시 일치(재실행 없음)", events=[("completion_adopted", {
            "task_key": os.path.basename(task_dir), "prev_run_id": (info["held"] or {}).get("run_id")})])
    elif state == states.INTERRUPTED and not safe:
        plan, wait_for = None, ("interrupted", (info["held"] or {}).get("run_id"), "unknown", None)
    elif state == states.INTERRUPTED:
        prev = info["held"] or {}
        plan = _plan(*_interrupted(prev, now, checkpoint.check(info["checkpoint"], prev.get("run_id"), current)))  # 체크포인트 판정이 먼저
        deaths = _deaths(prev)  # 이번 중단까지 센 진전 없는 비정상 종료 횟수
        if plan["resumed"]:
            plan["interrupts"] = 0  # 진전이 있는 재개: 연속 중단 횟수를 세지 않고 초기화한다
        elif deaths <= MAX_INTERRUPTS:
            plan["interrupts"] = deaths
        else:
            run_id, marker = prev.get("run_id"), os.path.join(task_dir, "stopped.json")
            logged = isinstance(info["stopped"], dict) and info["stopped"].get("run_id") == run_id
            if not logged:  # 정지 사유는 장부에 한 번만 남긴다(같은 중단 기록에 대한 표식)
                write_json(marker, {"run_id": run_id, "interrupts": deaths})
            plan = _plan("needs_failure_policy", "too_many_interrupts", extra={"interrupts": deaths}, events=(
                [] if logged else [("stopped_too_many_interrupts",
                                    {"task_key": os.path.basename(task_dir), "run_id": run_id, "interrupts": deaths})]))
    elif state == states.FAILED:
        plan = _plan(*_failed(info))
        if plan["action"] == "retry" and not safe:
            last = info["records"][-1]
            plan, wait_for = None, ("failed_transient", last.get("run_id"), "unknown", str(last.get("error"))[:200])
    elif state == states.PENDING:
        plan = _plan("run", "첫 실행")
    else:
        plan = _plan({states.VERIFIED: "skip", states.RUNNING: "wait"}.get(state, "unregistered"), state)
    if wait_for is not None:
        why, run_id, cause, error = wait_for
        cp = info["checkpoint"]
        outcome = "checkpoint" if isinstance(cp, dict) and cp.get("run_id") == run_id else \
            "partial" if info.get("outputs_present") else "unknown"
        record = {"task_key": os.path.basename(task_dir), "task_type": task_type, "run_id": run_id, "reason": why,
                  "cause": cause, "outcome": outcome, "error": error}
        seen = info.get("awaiting")
        logged = isinstance(seen, dict) and (seen.get("run_id"), seen.get("reason")) == (run_id, why)
        if not logged:  # 같은 대기는 장부·알림에 한 번만 남긴다
            write_json(os.path.join(task_dir, "awaiting.json"), dict(record, ts=now))
        plan = _plan("await_result", "결과 확인 대기: 재실행 안전으로 등록하지 않은 유형 %r" % task_type, extra={"outcome": outcome},
                     events=[] if logged else [("awaiting_result", record), ("notification", {
                         "kind": "task_awaiting_result", "message": "자동 재실행하지 않음(결과 확인 필요): %s" % record["task_key"],
                         "data": record})])
    if plan["runnable"] and not plan["run_id"]:
        plan["run_id"] = new_run_id()
    return plan
