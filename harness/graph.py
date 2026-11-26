"""의존 그래프 대조(누락 방지): 의존 작업이 모두 VERIFIED인데 자신은 완료·실행·대기 중이 아닌 작업을 찾아 등록한다."""
import os

from . import contract as ct
from . import lease, queue, states


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


def register_missing(root, declared_tasks, now, is_alive=lease.is_alive):
    """디스크 상태로 reconcile하고, 큐에 없는(UNREGISTERED) 대상만 enqueue한다.

    FAILED·INTERRUPTED·CORRUPT 대상은 eligible에만 나타나며 등록·재실행하지 않는다(실패 정책은 claim/recover가 판단).
    """
    for key, task in declared_tasks.items():
        if ct.task_key(task) != key:
            raise GraphError("선언 키와 계약 해시가 다르다: %s" % key)
    wanted = set(declared_tasks) | {d for c in declared_tasks.values() for d in c["depends_on"]}
    seen = {k: states.classify(os.path.join(root, "tasks", k), now, is_alive) for k in wanted}
    eligible = reconcile(declared_tasks, seen.__getitem__)
    registered = [k for k in eligible if seen[k] == states.UNREGISTERED]
    for key in registered:
        queue.enqueue(root, declared_tasks[key], now)
    return {"eligible": eligible, "registered": registered}
