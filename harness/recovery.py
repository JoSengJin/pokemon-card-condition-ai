"""상태별 처리 결정(DESIGN 9절). decide()는 실행 계획(plan)을 돌려준다.

호출 깊이 설계: decide는 아래 말단 함수들(_plan·_interrupted·_failed·_archive·checkpoint.check·new_run_id)만 부르고
말단은 서로를 부르지 않는다. CAS 복구(부수 효과)는 호출자(queue)가 cas.restore로 먼저 수행하고 결과(restored)만 넘긴다.
"""
import os
import socket

from . import checkpoint, states
from .contract import RUN_ID, new_run_id

RESUME_MIN_MINUTES = 30.0
RUNNABLE = ("run", "rerun", "retry", "resume")


def kind_of(exc):
    """예외 -> 실패 종류. 네트워크 단절·시간 초과만 일시적, 나머지(코드 오류 포함)는 결정적이다."""
    return "transient" if isinstance(exc, (ConnectionError, TimeoutError, socket.timeout)) else "deterministic"


def _plan(action, reason="", run_id=None, resumed=False, events=(), extra=None):
    plan = {"action": action, "reason": reason, "runnable": action in RUNNABLE, "resumed": resumed,
            "run_id": run_id, "events": list(events)}
    plan.update(extra or {})
    return plan


def _archive(task_dir):
    """복구 불가한 완료 기록을 history/로 옮긴다(덮어쓰지 않고 보관)."""
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
        return ("resume", "체크포인트 일치", run_id, True, [("interrupted_resumed", {"run_id": run_id})], None)
    return ("rerun", why, None, False, [("interrupted_rerun", {"prev_run_id": run_id, "reason": why})], None)


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
    restored는 호출자가 CAS에서 방금 되살린 산출물 목록. CORRUPT 복구 불가 시 완료 기록을 history/로 보관한다."""
    if state == states.CORRUPT and info["contract_state"] != "ok":  # 계약이 변조·손상: 재실행하지 않고 멈춘다
        plan = _plan("blocked", "계약 파일이 손상되었거나 task_key와 맞지 않는다")
    elif state == states.CORRUPT:
        _archive(task_dir)  # 계약이 정상인 CORRUPT는 done.json이 있는 경우뿐이다
        plan = _plan("rerun", "복구 불가: %s" % info["bad"], events=[("corrupt_unrecoverable", {"files": info["bad"]})])
    elif state == states.VERIFIED and restored:
        plan = _plan("skip", "CAS에서 복구하고 해시 재검증 통과", events=[("corrupt_restored", {"files": list(restored)})])
    elif state == states.INTERRUPTED:
        prev = info["held"] or {}
        plan = _plan(*_interrupted(prev, now, checkpoint.check(info["checkpoint"], prev.get("run_id"), current)))
    elif state == states.FAILED:
        plan = _plan(*_failed(info))
    elif state == states.PENDING:
        plan = _plan("run", "첫 실행")
    else:
        plan = _plan({states.VERIFIED: "skip", states.RUNNING: "wait"}.get(state, "unregistered"), state)
    if plan["runnable"] and not plan["run_id"]:
        plan["run_id"] = new_run_id()
    return plan
