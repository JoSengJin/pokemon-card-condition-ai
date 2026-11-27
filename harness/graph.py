"""의존 그래프 대조(누락 방지): 의존 작업이 모두 VERIFIED인데 자신은 완료·실행·대기 중이 아닌 작업을 찾아 등록한다."""
import os

from . import contract as ct
from . import claude_perm, dedupe, ledger, lease, states
from .jsonio import write_json


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


def register_missing(root, declared_tasks, now, is_alive=lease.is_alive, source_root=None):
    """디스크 상태로 reconcile하고, 큐에 없는(UNREGISTERED) 대상만 등록한다.

    FAILED·INTERRUPTED·CORRUPT 대상은 eligible에만 나타나며 등록·재실행하지 않는다(실패 정책은 claim/recover가 판단).
    호출 깊이 설계: queue.enqueue를 거치지 않고 같은 단계(계약 검증·중복 확인·저장·장부 기록)를 직접 한다.
    실행 조건이 같은 기존 작업이 있는 선언은 등록하지 않고 duplicates({선언 키: 기존 키})로 돌려준다. 등록 목록에 없는 유형·판별할 수 없는
    실행 조건·실제 파일(source_root, 기본 저장소)과 다른 입력 SHA는 ContractError(queue.enqueue와 같은 규칙).
    """
    for key, task in declared_tasks.items():
        if ct.task_key(task) != key:
            raise GraphError("선언 키와 계약 해시가 다르다: %s" % key)
    seen = {}
    for key in set(declared_tasks) | {d for c in declared_tasks.values() for d in c["depends_on"]}:
        info = states.facts(os.path.join(root, "tasks", key))
        seen[key] = states.state_of(info, info["held"] is not None and is_alive(info["held"]))
    eligible = reconcile(declared_tasks, seen.__getitem__)
    registered, duplicates = [], {}
    for key in [k for k in eligible if seen[k] == states.UNREGISTERED]:
        task = ct.validate_contract(declared_tasks[key])
        dup = dedupe.find_duplicate(root, task, key)  # queue.enqueue와 같은 중복 거절(실행 조건이 같은 실험)
        if dup is not None:
            duplicates[key] = dup
            continue
        dedupe.verify_inputs(task, source_root or claude_perm.REPO)
        write_json(os.path.join(root, "tasks", key, "contract.json"), task)
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "enqueued", {"task_key": key, "task_type": task["task_type"]})
        registered.append(key)
    return dict({"eligible": eligible, "registered": registered}, **({"duplicates": duplicates} if duplicates else {}))
