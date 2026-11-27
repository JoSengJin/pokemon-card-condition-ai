"""작업 큐: enqueue·claim·complete·fail·recover. 모든 전이는 장부(ledger.jsonl)에 기록한다.

root 아래 구조: ledger.jsonl, cas/, tasks/<task_key>/{contract.json,out/,lease.json,done.json,...}.
기록은 상태 변경 뒤에 남긴다(장부가 일어나지 않은 일을 주장하지 않게). 비정상 종료 시 장부 줄이
빠질 수 있으며, 상태 파일이 정본이다.

호출 깊이 설계(공개 함수마다 깊이 2 이하): 이 파일의 공개 함수는 states.facts·state_of·recovery.decide·
cas·ledger·lease의 말단/중간 함수를 직접 순서대로 부르고, 그 함수들은 말단만 부른다. 그래서 같은 순서가
claim과 recover에 한 번씩 보인다(사실 수집 → CAS 복구 → 다시 수집 → 판정 → 기록).
"""
import fcntl
import os

from . import contract as ct
from . import cas, claude_perm, dedupe, holder, ledger, lease, manifest, opstate, recovery, states
from .jsonio import read_json, write_json


class QueueError(Exception):
    pass


class DuplicateTask(QueueError):
    """실행 조건이 같은 작업이 이미 있다(dedupe). existing 속성에 기존 task_key."""


def _check_owner(handle, run_id):
    held = lease.read(handle.path)
    if not held or held.get("run_id") != run_id:
        raise QueueError("작업권 소유 run_id 불일치: 이 실행의 작업권이 아니다")
    return held


def enqueue(root, task, now, source_root=None):
    """계약을 큐에 등록(같은 계약이면 멱등). task_key를 돌려준다. 검사·저장은 root의 ct.ENQUEUE_LOCK 잠금 안에서 한다. 실행 조건이 같은 다른 계약이 있으면 DuplicateTask(.existing),
    등록 목록에 없는 유형·실행 조건을 판별할 수 없는 실험·학습·평가 계약·입력 SHA가 source_root(기본 저장소)의 실제 파일과 다른
    실험·학습·평가 계약은 ContractError(dedupe)."""
    ct.validate_contract(task)
    key = ct.task_key(task)
    path = os.path.join(root, "tasks", key, "contract.json")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, ct.ENQUEUE_LOCK), "a") as guard:  # 검사와 저장 사이에 다른 등록이 끼지 않게(2차 결함 G4)
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        if not os.path.exists(path):
            dup = dedupe.find_duplicate(root, task, key)  # 유형·실행 조건 형식 검사도 여기서 한다
            if dup is not None:
                err = DuplicateTask("실행 조건이 같은 작업이 이미 있다: %s" % dup)
                err.existing = dup
                raise err
            dedupe.verify_inputs(task, source_root or claude_perm.REPO)  # 등록 직전 입력 SHA를 실제 파일과 대조
            write_json(path, task)
            ledger.append(os.path.join(root, "ledger.jsonl"), now, "enqueued",
                          {"task_key": key, "task_type": task["task_type"]})
    return key


def claim(root, key, pid, boot, now, current=None):
    """작업권을 잡고 실행 여부를 정한다. 잠금 안에서 상태 분류·결정하므로 동시 claim은 한쪽만 성공한다.

    flock을 잡았다는 것은 이전 작업권의 주인 프로세스가 잠금을 쥐고 있지 않다는 증거일 뿐이다. 그래서 이전 기록의
    pid가 같은 부팅에서 살아 있고 좀비가 아니면 인수하지 않고 "holder_alive_without_lock"으로 멈춘다(잠금 없이
    실행 중인 주인이 있다는 뜻: 이중 실행 방지가 멈춤보다 우선). 좀비는 인수하고, 판정 불가(ps 실패)는 "blocked"다.
    전제: 작업권을 쥔 프로세스가 끝까지 실행하고 exec하지 않는다 — 그래서 pid는 os.getpid(), boot는 lease.boot_id()여야 한다
    (대리 claim·지어낸 부팅 식별자 거절). 시험은 공개 인자가 아니라 lease.boot_id를 patch해 합성 부팅 식별자를 쓴다(호출자가 우회하지 못하게).

    성공: {"ok": True, "run_id", "resumed", "lease"(complete/fail에 넘길 핸들), "state", "plan"}.
    실패: {"ok": False, "reason": "locked"|"unregistered"|plan action|holder_alive_without_lock|blocked, ...}.
    """
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    if pid != os.getpid():
        raise QueueError("claim의 pid는 호출 프로세스(os.getpid())여야 한다: 대리 claim은 잠금 없이 실행되는 이중 실행을 만든다")
    if boot != lease.boot_id():  # boot도 pid처럼 호출자가 지어낼 수 없다(기록 판정이 부팅 식별자에 의존)
        raise QueueError("claim의 boot는 lease.boot_id()와 같아야 한다: %r" % (boot,))
    if not os.path.isdir(task_dir):
        return {"ok": False, "reason": "unregistered"}
    handle = lease.lock(os.path.join(task_dir, "lease.json"))
    if handle is None:
        return {"ok": False, "reason": "locked"}
    try:
        info, restored = states.facts(task_dir), []
        if info["restorable"]:  # CORRUPT: 보관본에서 어긋난 산출물만 되살리고 다시 검증한다
            restored = info["bad"]
            cas.restore(os.path.join(root, "cas"), info["restorable"])
            info = states.facts(task_dir)
        state = states.state_of(info, False)  # 잠금을 잡았으므로 이전 기록의 주인은 잠금을 쥐고 있지 않다
        shown = states.CORRUPT if restored else state  # 복구 전 상태를 보고한다
        who = holder.verdict(info["held"], boot) if state == states.INTERRUPTED else "dead"
        if who == "dead":
            plan = recovery.decide(task_dir, state, info, now, current, restored)
        else:  # 잠금 없이 주인이 살아 있거나 판정 불가: 인수하지 않고 사유를 장부에 남긴다
            why = "holder_alive_without_lock" if who == "alive" else "blocked"
            plan = {"runnable": False, "action": why, "reason": why, "events": [(why, {"task_key": key, "holder": info["held"]})]}
        for event, data in plan["events"]:  # notification은 알림 장부로(opstate.notify와 같은 형식)
            ledger.append(os.path.join(root, opstate.NOTIFICATIONS if event == "notification" else "ledger.jsonl"), now, event, data)
    except BaseException:  # 판단 중 오류가 잠금을 쥔 채 남지 않게 한다(이전 기록은 보존)
        lease.release(handle)
        raise
    if not plan["runnable"]:
        lease.release(handle)
        return {"ok": False, "reason": plan["action"], "state": shown, "plan": plan}
    try:
        lease.stamp(handle, pid, boot, now, {"run_id": plan["run_id"], "resumed": plan["resumed"],
                                             "interrupts": plan.get("interrupts", 0)})
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "claimed",
                      {"task_key": key, "run_id": plan["run_id"], "pid": pid, "state_before": shown,
                       "action": plan["action"], "resumed": plan["resumed"]})
    except BaseException:  # 기록 실패로 쥔 작업권이 남아 이중 실행 오해·교착이 생기지 않게 한다
        lease.release(handle, remove=True)
        raise
    return {"ok": True, "run_id": plan["run_id"], "resumed": plan["resumed"], "lease": handle,
            "state": shown, "plan": plan}


def complete(root, key, run_id, handle, now):
    """out/의 산출물 해시를 manifest로 기록하고 CAS에 보관한 뒤 done.json을 쓴다(그 뒤에 작업권 해제).
    완료 표시(ct.COMPLETION)가 task_key·산출물 해시와 정확히 같을 때만 완료한다(산출물 존재만으로는 완료가 아니다).
    이미 done.json이 있으면 다시 반영하지 않는다(QueueError). 거절하면 작업권은 호출자가 fail 또는 release로 놓는다."""
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    held = _check_owner(handle, run_id)
    task = read_json(os.path.join(task_dir, "contract.json"))
    if not isinstance(task, dict) or ct.task_key(task) != key or not task.get("outputs"):
        raise QueueError("계약 파일이 손상되었거나 task_key와 맞지 않는다")
    if os.path.exists(os.path.join(task_dir, "done.json")):
        raise QueueError("이미 완료 기록이 있다: 다시 반영하지 않는다")
    out_dir = os.path.join(task_dir, "out")
    recorded = manifest.build(out_dir, task["outputs"])
    try:
        marker = read_json(os.path.join(task_dir, ct.COMPLETION))
    except ValueError:
        marker = None
    if marker != {"task_key": key, "outputs": recorded}:
        raise QueueError("완료 표시가 없거나 산출물 해시·task_key와 맞지 않는다")
    for rel in recorded:
        cas.put(os.path.join(root, "cas"), os.path.join(out_dir, rel))
    write_json(os.path.join(task_dir, "done.json"), {"task_key": key, "run_id": run_id,
               "resumed": bool(held.get("resumed")), "completed_at": now, "manifest": recorded})
    try:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "completed",
                      {"task_key": key, "run_id": run_id, "manifest": recorded})
    finally:
        lease.release(handle, remove=True)


def fail(root, key, run_id, handle, kind, error, now):
    """실패를 failures/에 추가(덮어쓰지 않음)하고 작업권을 해제한다. kind는 transient|deterministic."""
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    ct.check_run_id(run_id)  # 쓰는 파일 이름과 세는 규칙(failures/ 필터)이 어긋나 기록이 소실되지 않게
    if kind not in ("transient", "deterministic"):
        raise QueueError("kind는 transient|deterministic: %r" % (kind,))
    _check_owner(handle, run_id)
    attempt = len(states.failures(task_dir)) + 1
    record = {"attempt": attempt, "run_id": run_id, "kind": kind, "error": str(error), "ts": now}
    write_json(os.path.join(task_dir, "failures", "%03d-%s.json" % (attempt, run_id)), record)
    try:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "failed", dict(record, task_key=key))
    finally:
        lease.release(handle, remove=True)


def recover(root, key, now, is_alive=lease.is_alive, current=None):
    """감독용 조회: 상태와 다음 처리 계획. 작업권은 잡지 않는다(CORRUPT 복구만 부수 효과).

    돌려주는 run_id는 참고용이며 실제 실행은 claim이 잠금 안에서 다시 정한다.
    """
    task_dir = os.path.join(root, "tasks", ct.check_key(key))
    info, restored = states.facts(task_dir), []
    if info["restorable"]:
        restored = info["bad"]
        cas.restore(os.path.join(root, "cas"), info["restorable"])
        info = states.facts(task_dir)
    held = info["held"]
    state = states.state_of(info, held is not None and is_alive(held))
    plan = recovery.decide(task_dir, state, info, now, current, restored)
    for event, data in plan["events"]:
        ledger.append(os.path.join(root, opstate.NOTIFICATIONS if event == "notification" else "ledger.jsonl"), now, event, data)
    return dict(plan, state=states.CORRUPT if restored else state)
