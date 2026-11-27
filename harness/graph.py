"""의존 그래프 대조(누락 방지): 의존 작업이 모두 VERIFIED인데 자신은 완료·실행·대기 중이 아닌 작업을 찾아 등록한다.

선언 하나의 문제는 그 선언만 거절하고 알린다(2차 결함 G5: 한 작업의 문제로 Supervisor 전체를 INTEGRITY_HALT로 멈추지 않는다).
호출 깊이: register_missing → dedupe.find_duplicate → logical_key → _command 3, register_missing → note_rejected → ledger.append 2.
"""
import fcntl
import os

from . import contract as ct
from . import claude_perm, dedupe, ledger, lease, opstate, states
from .jsonio import read_json, write_json

REJECTED = os.path.join("supervisor", "declared_rejected.json")  # 알린 선언 거절 {선언 키: 사유}(같은 사유는 다시 알리지 않는다)


class GraphError(Exception):
    pass


def _acyclic(nodes):
    """반복형 깊이 우선 탐색으로 순환 의존을 찾아 GraphError. nodes: 키 -> 의존 키 목록."""
    seen = {}
    for start in nodes:
        if start in seen:
            continue
        seen[start] = 1
        stack = [(start, iter(nodes[start]))]
        while stack:
            node, deps = stack[-1]
            for dep in deps:
                if seen.get(dep) == 1:
                    raise GraphError("순환 의존: %s -> %s" % (node, dep))
                if dep in nodes and dep not in seen:
                    seen[dep] = 1
                    stack.append((dep, iter(nodes[dep])))
                    break
            else:
                seen[node] = 2
                stack.pop()


def reconcile(declared_tasks, state_of):
    """declared_tasks: {task_key: 계약}. 조건에 맞는 task_key 목록(선언 순서). 순환이면 GraphError."""
    nodes = {k: list(c["depends_on"]) for k, c in declared_tasks.items()}
    _acyclic(nodes)
    skip = (states.VERIFIED, states.RUNNING, states.PENDING)
    return [k for k, deps in nodes.items()
            if state_of(k) not in skip and all(state_of(d) == states.VERIFIED for d in deps)]


def note_rejected(root, rejected, now):
    """거절한 선언 {선언 키 또는 "<declared.json>": 사유}를 장부(declaration_rejected)와 알림에 남긴다. 같은 키·같은 사유는 한 번만
    (기록 root/supervisor/declared_rejected.json, 깨졌으면 처음부터 다시 남긴다). 새로 남긴 수를 돌려준다."""
    path = os.path.join(root, REJECTED)
    try:
        known = read_json(path, {})
    except ValueError:
        known = None
    known = known if isinstance(known, dict) else {}
    fresh = {k: v for k, v in sorted(rejected.items()) if known.get(k) != v}
    for key, why in fresh.items():
        data = {"declaration": key, "reason": why[:300]}
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "declaration_rejected", data)
        ledger.append(os.path.join(root, opstate.NOTIFICATIONS), now, "notification", {
            "kind": "declaration_rejected", "message": "선언 하나를 등록하지 않음(그 선언과 의존 작업만, 사람 확인): %s" % key, "data": data})
    if fresh:
        write_json(path, dict(known, **fresh))
    return len(fresh)


def register_missing(root, declared_tasks, now, is_alive=lease.is_alive, source_root=None):
    """디스크 상태로 reconcile하고, 큐에 없는(UNREGISTERED) 대상만 등록한다.

    FAILED·INTERRUPTED·CORRUPT 대상은 eligible에만 나타나며 등록·재실행하지 않는다(실패 정책은 claim/recover가 판단).
    호출 깊이 설계: queue.enqueue를 거치지 않고 같은 단계(계약 검증·중복 확인·저장·장부 기록)를 같은 잠금(ct.ENQUEUE_LOCK) 안에서 직접 한다.
    실행 조건이 같은 기존 작업이 있는 선언은 등록하지 않고 duplicates({선언 키: 기존 키})로 돌려준다.
    선언별 문제(2차 결함 G5: 계약 형식·선언 키와 계약 해시 불일치·등록 목록에 없는 유형·판별할 수 없는 실행 조건·실제 파일(source_root,
    기본 저장소)과 다른 입력 SHA)는 그 선언만 등록하지 않고 rejected({선언 키: 사유})로 돌려주며 note_rejected로 한 번 알린다(전체 정지 없음).
    그 선언에 의존하는 선언은 의존이 VERIFIED가 아니므로 등록되지 않고 기다린다. 선언 전체가 dict가 아니거나 순환이면 GraphError(파일 단위).
    """
    if not isinstance(declared_tasks, dict):
        raise GraphError("선언 파일은 {task_key: 계약} dict여야 한다")
    valid, rejected = {}, {}
    for key, task in declared_tasks.items():
        try:
            ct.validate_contract(task)
            if ct.task_key(task) != key:
                raise GraphError("선언 키와 계약 해시가 다르다: %s" % key)
            valid[key] = task
        except (ValueError, TypeError, GraphError) as exc:  # ContractError는 ValueError
            rejected[str(key)] = "%s: %s" % (type(exc).__name__, exc)
    seen = {}
    for key in set(valid) | {d for c in valid.values() for d in c["depends_on"]}:
        info = states.facts(os.path.join(root, "tasks", key))
        seen[key] = states.state_of(info, info["held"] is not None and is_alive(info["held"]))
    eligible = reconcile(valid, seen.__getitem__)
    registered, duplicates = [], {}
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, ct.ENQUEUE_LOCK), "a") as guard:  # queue.enqueue와 같은 등록 잠금(2차 결함 G4)
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        for key in [k for k in eligible if seen[k] == states.UNREGISTERED]:
            task = valid[key]
            if os.path.exists(os.path.join(root, "tasks", key, "contract.json")):
                continue  # 잠금을 기다리는 사이 다른 등록이 먼저 했다
            try:
                dup = dedupe.find_duplicate(root, task, key)  # queue.enqueue와 같은 중복 거절(실행 조건이 같은 실험)
                if dup is None:
                    dedupe.verify_inputs(task, source_root or claude_perm.REPO)
            except ct.ContractError as exc:
                rejected[key] = "ContractError: %s" % exc
                continue
            if dup is not None:
                duplicates[key] = dup
                continue
            write_json(os.path.join(root, "tasks", key, "contract.json"), task)
            ledger.append(os.path.join(root, "ledger.jsonl"), now, "enqueued", {"task_key": key, "task_type": task["task_type"]})
            registered.append(key)
    note_rejected(root, rejected, now)
    extra = dict({"duplicates": duplicates} if duplicates else {}, **({"rejected": rejected} if rejected else {}))
    return dict({"eligible": eligible, "registered": registered}, **extra)
