"""상태별 처리 결정(DESIGN 9절). decide()는 실행 계획(plan)을 돌려주고 CORRUPT 복구만 부수 효과를 갖는다."""
import os
import socket

from . import cas, checkpoint, states
from .contract import new_run_id
from .jsonio import read_json
from .manifest import mismatches

RESUME_MIN_MINUTES = 30.0
RUNNABLE = ("run", "rerun", "retry", "resume")


def kind_of(exc):
    """예외 -> 실패 종류. 네트워크 단절·시간 초과만 일시적, 나머지(코드 오류 포함)는 결정적이다."""
    return "transient" if isinstance(exc, (ConnectionError, TimeoutError, socket.timeout)) else "deterministic"


def _plan(action, reason="", run_id=None, resumed=False, events=(), **extra):
    runnable = action in RUNNABLE
    plan = {"action": action, "reason": reason, "runnable": runnable, "resumed": resumed,
            "run_id": (run_id or new_run_id()) if runnable else None, "events": list(events)}
    plan.update(extra)
    return plan


def _corrupt(task_dir, cas_root):
    """보관본(CAS)에서 어긋난 산출물만 복구하고 해시를 다시 검증. 실패하면 완료 기록을 보관하고 재실행."""
    outputs = read_json(os.path.join(task_dir, "contract.json"))["outputs"]
    out_dir, done_path = os.path.join(task_dir, "out"), os.path.join(task_dir, "done.json")
    try:
        done = read_json(done_path)
    except ValueError:
        done = None
    recorded = done.get("manifest") if isinstance(done, dict) and isinstance(done.get("manifest"), dict) else {}
    bad = mismatches(out_dir, recorded, outputs)
    for rel in [r for r in bad if r in outputs and r in recorded]:
        try:
            cas.get(cas_root, recorded[rel], os.path.join(out_dir, rel))
        except (cas.CasError, OSError):
            pass  # 복구 실패는 아래 재검증에서 드러난다
    remaining = mismatches(out_dir, recorded, outputs)
    if not remaining:
        return _plan("skip", "CAS에서 복구하고 해시 재검증 통과", events=[("corrupt_restored", {"files": bad})])
    hist = os.path.join(task_dir, "history")
    os.makedirs(hist, exist_ok=True)
    os.replace(done_path, os.path.join(hist, "done-%03d.json" % (len(os.listdir(hist)) + 1)))
    return _plan("rerun", "복구 불가: %s" % remaining,
                 events=[("corrupt_unrecoverable", {"files": remaining})])


def _interrupted(task_dir, prev, now, current):
    """30분 이상 실행했고 체크포인트 지문이 모두 일치할 때만 같은 run_id로 복원한다."""
    prev = prev or {}
    run_id, started = prev.get("run_id"), prev.get("ts")
    if not isinstance(run_id, str) or not isinstance(started, (int, float)) or isinstance(started, bool):
        why = "중단된 작업권 기록(run_id·시작 시각)이 없거나 손상됨"
    elif (now - started) / 60.0 < RESUME_MIN_MINUTES:
        why = "실행 시간이 %d분 미만" % RESUME_MIN_MINUTES
    else:
        why = checkpoint.check(task_dir, run_id, current)
    if why is None:
        return _plan("resume", "체크포인트 일치", run_id=run_id, resumed=True,
                     events=[("interrupted_resumed", {"run_id": run_id})])
    return _plan("rerun", why, events=[("interrupted_rerun", {"prev_run_id": run_id, "reason": why})])


def _failed(task_dir):
    records = states.failures(task_dir)
    kind, attempts = records[-1].get("kind"), len(records)
    allowed = read_json(os.path.join(task_dir, "contract.json"))["retry_policy"].get("max_transient_retries", 2)
    info = {"failure_kind": kind, "attempts": attempts}
    if kind == "transient" and attempts <= allowed:
        return _plan("retry", "일시적 실패 재시도 %d/%d" % (attempts, allowed),
                     events=[("retry_planned", info)], **info)
    return _plan("needs_failure_policy", "결정적 실패" if kind != "transient" else "재시도 한도 소진", **info)


def decide(task_dir, cas_root, state, prev, now, current=None):
    """상태 -> 계획. prev는 중단된 작업권 기록, current는 현재 실행 지문(없으면 복원하지 않는다)."""
    if state == states.CORRUPT:
        return _corrupt(task_dir, cas_root)
    if state == states.INTERRUPTED:
        return _interrupted(task_dir, prev, now, current)
    if state == states.FAILED:
        return _failed(task_dir)
    if state == states.PENDING:
        return _plan("run", "첫 실행")
    return _plan({states.VERIFIED: "skip", states.RUNNING: "wait"}.get(state, "unregistered"), state)
