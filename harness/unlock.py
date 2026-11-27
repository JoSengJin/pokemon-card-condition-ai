"""정지 해제(1·2단계 인계에서 3단계 몫으로 남긴 항목). 사람 또는 Supervisor 운영자가 상황을 확인한 뒤 직접 부르는 함수다.

자동 호출 경로는 없다: harness/ 안의 어떤 코드도 이 모듈을 부르지 않는다(시험이 ast로 확인). confirm=True·실행자·사유가 필요하다.
- release_interrupts: too_many_interrupts(recovery.MAX_INTERRUPTS 초과)로 멈춘 작업. 정지 표식(stopped.json)과 죽은 작업권 기록을
  history/unlock-NNN.json에 보관한 뒤, 작업권 기록의 interrupts만 0으로 다시 쓰고(pid·부팅·시작 시각·run_id 유지) 표식을 지운다.
  다음 claim은 1단계 규칙대로 INTERRUPTED를 판정한다(재실행, 횟수 1부터).
- release_holder: holder_alive_without_lock(잠금 없이 같은 부팅에서 살아 있는 pid)으로 멈춘 작업. 확인한 사람이 그 프로세스가 이 작업을
  실행하고 있지 않다고 판단했을 때만 쓴다(그렇지 않으면 이중 실행). 작업권 기록을 보관하고 지운다.
- 두 경우 모두 잠금(flock)을 잡지 못하면(실제로 실행 중) 거절하고, 해제 사실(사유·실행자·시각)을 1단계 장부에 남긴다.
"""
import os

from . import contract as ct
from . import holder, lease, ledger, recovery
from .jsonio import read_json, write_json

ACTORS = ("user", "supervisor")


def _check(actor, reason, confirm):
    if confirm is not True or actor not in ACTORS or not isinstance(reason, str) or not reason.strip():
        raise ValueError("정지 해제는 confirm=True, 실행자(%s), 사유가 필요하다" % (ACTORS,))


def _archive(task_dir, record):
    """history/unlock-NNN.json에 보관(덮어쓰지 않는다). 보관한 파일 경로."""
    hist = os.path.join(task_dir, "history")
    os.makedirs(hist, exist_ok=True)
    path = os.path.join(hist, "unlock-%03d.json" % (len([n for n in os.listdir(hist) if n.startswith("unlock-")]) + 1))
    if os.path.exists(path):
        raise FileExistsError(path)
    write_json(path, record)
    return path


def release_interrupts(root, key, actor, reason, now, confirm=False):
    """too_many_interrupts 정지 해제. {"ok": True, "archived"} 또는 {"ok": False, "reason"}."""
    _check(actor, reason, confirm)
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    stopped = read_json(os.path.join(task_dir, "stopped.json"))
    if not isinstance(stopped, dict):
        return {"ok": False, "reason": "not_stopped"}
    handle = lease.lock(os.path.join(task_dir, "lease.json"))
    if handle is None:
        return {"ok": False, "reason": "locked"}
    try:
        prev, count = handle.previous, (handle.previous or {}).get("interrupts")
        below = isinstance(count, int) and not isinstance(count, bool) and 0 <= count < recovery.MAX_INTERRUPTS
        if not isinstance(prev, dict) or prev.get("run_id") != stopped.get("run_id") or below:  # 손상된 횟수도 정지 대상이었다
            return {"ok": False, "reason": "not_too_many_interrupts"}
        if holder.verdict(prev, lease.boot_id()) != "dead":
            return {"ok": False, "reason": "holder_not_dead"}
        archived = _archive(task_dir, {"kind": "too_many_interrupts", "stopped": stopped, "lease": prev,
                                       "actor": actor, "reason": reason, "ts": now})
        keep = {k: v for k, v in prev.items() if k not in ("pid", "boot_id", "ts")}
        lease.stamp(handle, prev.get("pid"), prev.get("boot_id"), prev.get("ts"), dict(keep, interrupts=0))
        os.unlink(os.path.join(task_dir, "stopped.json"))
    finally:
        lease.release(handle)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, "unlock_too_many_interrupts",
                  {"task_key": key, "run_id": prev.get("run_id"), "actor": actor, "reason": reason,
                   "archived": os.path.relpath(archived, root)})
    return {"ok": True, "archived": archived}


def release_holder(root, key, actor, reason, now, confirm=False):
    """holder_alive_without_lock 정지 해제(작업권 기록 보관 후 삭제). {"ok": True, "archived"} 또는 {"ok": False, "reason"}."""
    _check(actor, reason, confirm)
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    if not os.path.exists(os.path.join(task_dir, "lease.json")):
        return {"ok": False, "reason": "no_lease"}
    handle = lease.lock(os.path.join(task_dir, "lease.json"))
    if handle is None:
        return {"ok": False, "reason": "locked"}
    remove = False
    try:
        prev = handle.previous
        found = holder.verdict(prev, lease.boot_id())
        if found != "alive":
            return {"ok": False, "reason": "holder_not_alive_without_lock:" + found}
        archived = _archive(task_dir, {"kind": "holder_alive_without_lock", "lease": prev, "actor": actor,
                                       "reason": reason, "ts": now})
        remove = True
    finally:
        lease.release(handle, remove=remove)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, "unlock_holder_alive",
                  {"task_key": key, "holder": prev, "actor": actor, "reason": reason,
                   "archived": os.path.relpath(archived, root)})
    return {"ok": True, "archived": archived}
