"""작업 큐: enqueue·claim·complete·fail·recover. 모든 전이는 장부(ledger.jsonl)에 기록한다.

root 아래 구조: ledger.jsonl, cas/, tasks/<task_key>/{contract.json,out/,lease.json,done.json,...}.
기록은 상태 변경 뒤에 남긴다(장부가 일어나지 않은 일을 주장하지 않게). 비정상 종료 시 장부 줄이
빠질 수 있으며, 상태 파일이 정본이다.
"""
import os

from . import contract as ct
from . import cas, ledger, lease, manifest, recovery, states
from .jsonio import read_json, write_json


class QueueError(Exception):
    pass


def _log(root, now, events):
    for event, data in events:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, event, data)


def _check_owner(handle, run_id):
    held = lease.read(handle.path)
    if not held or held.get("run_id") != run_id:
        raise QueueError("작업권 소유 run_id 불일치: 이 실행의 작업권이 아니다")
    return held


def enqueue(root, task, now):
    """계약을 큐에 등록(같은 계약이면 멱등). task_key를 돌려준다."""
    ct.validate_contract(task)
    key = ct.task_key(task)
    path = os.path.join(root, "tasks", key, "contract.json")
    if not os.path.exists(path):
        write_json(path, task)
        _log(root, now, [("enqueued", {"task_key": key, "task_type": task["task_type"]})])
    return key


def claim(root, key, pid, boot, now, is_alive=lease.is_alive, current=None):
    """작업권을 잡고 실행 여부를 정한다. 잠금 안에서 상태 분류·결정하므로 동시 claim은 한쪽만 성공한다.

    성공: {"ok": True, "run_id", "resumed", "lease"(complete/fail에 넘길 핸들), "state", "plan"}.
    실패: {"ok": False, "reason": "locked"|"unregistered"|plan action, ...}. 잠금 핸들은 프로세스가 쥐고 있다.
    """
    task_dir = os.path.join(root, "tasks", key)
    if not os.path.isdir(task_dir):
        return {"ok": False, "reason": "unregistered"}
    handle = lease.lock(os.path.join(task_dir, "lease.json"))
    if handle is None:
        return {"ok": False, "reason": "locked"}
    try:
        state = states.classify(task_dir, now, is_alive)
        plan = recovery.decide(task_dir, os.path.join(root, "cas"), state, handle.previous, now, current)
        _log(root, now, plan["events"])
    except BaseException:  # 판단 중 오류(부팅 식별자 조회 실패 등)가 잠금을 쥔 채 남지 않게 한다
        lease.release(handle)
        raise
    if not plan["runnable"]:
        lease.release(handle)
        return {"ok": False, "reason": plan["action"], "state": state, "plan": plan}
    lease.stamp(handle, pid, boot, now, {"run_id": plan["run_id"], "resumed": plan["resumed"]})
    _log(root, now, [("claimed", {"task_key": key, "run_id": plan["run_id"], "pid": pid,
                                  "state_before": state, "action": plan["action"], "resumed": plan["resumed"]})])
    return {"ok": True, "run_id": plan["run_id"], "resumed": plan["resumed"], "lease": handle,
            "state": state, "plan": plan}


def complete(root, key, run_id, handle, now):
    """out/의 산출물 해시를 manifest로 기록하고 CAS에 보관한 뒤 done.json을 쓴다(그 뒤에 작업권 해제)."""
    task_dir = os.path.join(root, "tasks", key)
    held = _check_owner(handle, run_id)
    out_dir = os.path.join(task_dir, "out")
    recorded = manifest.build(out_dir, read_json(os.path.join(task_dir, "contract.json"))["outputs"])
    for rel in recorded:
        cas.put(os.path.join(root, "cas"), os.path.join(out_dir, rel))
    write_json(os.path.join(task_dir, "done.json"), {"task_key": key, "run_id": run_id,
               "resumed": bool(held.get("resumed")), "completed_at": now, "manifest": recorded})
    _log(root, now, [("completed", {"task_key": key, "run_id": run_id, "manifest": recorded})])
    lease.release(handle, remove=True)


def fail(root, key, run_id, handle, kind, error, now):
    """실패를 failures/에 추가(덮어쓰지 않음)하고 작업권을 해제한다. kind는 transient|deterministic."""
    if kind not in ("transient", "deterministic"):
        raise QueueError("kind는 transient|deterministic: %r" % (kind,))
    _check_owner(handle, run_id)
    fdir = os.path.join(root, "tasks", key, "failures")
    os.makedirs(fdir, exist_ok=True)
    attempt = len(os.listdir(fdir)) + 1
    record = {"attempt": attempt, "run_id": run_id, "kind": kind, "error": str(error), "ts": now}
    write_json(os.path.join(fdir, "%03d-%s.json" % (attempt, run_id)), record)
    _log(root, now, [("failed", dict(record, task_key=key))])
    lease.release(handle, remove=True)


def recover(root, key, now, is_alive=lease.is_alive, current=None):
    """감독용 조회: 상태와 다음 처리 계획. 작업권은 잡지 않는다(CORRUPT 복구만 부수 효과).

    돌려주는 run_id는 참고용이며 실제 실행은 claim이 잠금 안에서 다시 정한다.
    """
    task_dir = os.path.join(root, "tasks", key)
    state = states.classify(task_dir, now, is_alive)
    plan = recovery.decide(task_dir, os.path.join(root, "cas"), state,
                           lease.read(os.path.join(task_dir, "lease.json")), now, current)
    _log(root, now, plan["events"])
    return dict(plan, state=state)
