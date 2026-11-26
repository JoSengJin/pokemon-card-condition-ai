"""한도 중에도 도는 Python 작업 runner(DESIGN 4·12절). needs_llm=false 작업만 큐에서 꺼내 실행한다.

- executor는 호출자가 task_type -> callable(contract, out_dir) -> 출력 상대 경로 목록 으로 주입한다.
  이 파일은 외부 모델 호출·네트워크·하위 프로세스를 쓰지 않는다(시험이 소스를 검사한다).
- LLM 작업(needs_llm=true)과 그것에 (간접으로) 의존하는 작업은 건드리지 않는다(claim도 하지 않으므로 장부에도 안 남는다).
- 일시적 실패는 1단계 규칙대로 최대 2회 재시도한 뒤 정지, 결정적 실패·needs_failure_policy·blocked·
  holder_alive_without_lock은 우회하지 않고 요약에 남기고 그 작업만 멈춘다. 데몬·예산·한도 감지는 하지 않는다(3단계).
- 호출 깊이: main -> drain -> queue.claim/complete/fail(각각 깊이 2 이하)이라 최대 4다.
  executor는 호출자 코드(동적 호출)이며 이 깊이에 포함하지 않았다.
"""
import importlib
import json
import os
import sys
import time

from . import contract as ct
from . import lease, queue, recovery, states
from .jsonio import read_json


class OutputMismatch(Exception):
    pass


def _scan(root, executors):
    """(실행 후보 key 목록, 건드리지 않는 작업의 사유별 목록). 읽기만 한다."""
    tasks_dir = os.path.join(root, "tasks")
    infos = {}
    for key in sorted(os.listdir(tasks_dir)) if os.path.isdir(tasks_dir) else []:
        try:
            infos[ct.check_key(key)] = states.facts(os.path.join(tasks_dir, key))
        except ct.ContractError:
            continue  # 작업 폴더가 아닌 항목
    state = {k: states.state_of(i, False) for k, i in infos.items()}
    contracts = {k: i["contract"] for k, i in infos.items() if i["contract"] is not None}
    llm = {k for k, c in contracts.items() if c["needs_llm"]}
    tainted = set(llm)
    while True:  # LLM 작업에 직접·간접으로 의존하는 작업
        more = {k for k, c in contracts.items() if k not in tainted and any(d in tainted for d in c["depends_on"])}
        if not more:
            break
        tainted |= more
    todo, waiting, no_exec = [], [], []
    for key, task in contracts.items():
        if key in tainted or state[key] in (states.VERIFIED, states.UNREGISTERED):
            continue
        if task["task_type"] not in executors:
            no_exec.append(key)
        elif not all(state.get(d) == states.VERIFIED for d in task["depends_on"]):
            waiting.append(key)
        else:
            todo.append(key)
    return todo, {"llm": sorted(llm), "llm_dependents": sorted(tainted - llm), "no_executor": sorted(no_exec),
                  "waiting_dependencies": sorted(waiting),
                  "unreadable_contract": sorted(k for k, i in infos.items() if i["contract_state"] == "bad")}


def _execute(executors, task, out_dir):
    """executor를 실행한다. 정상이면 None, 오류면 (실패 종류, 설명). 종류는 1단계 규칙(recovery.kind_of)."""
    try:
        produced = executors[task["task_type"]](task, out_dir)
        if sorted(produced) != sorted(task["outputs"]):
            raise OutputMismatch("executor가 돌려준 출력 목록이 계약의 outputs와 다르다: %r" % (produced,))
    except Exception as exc:
        return recovery.kind_of(exc), "%s: %s" % (type(exc).__name__, exc)
    return None


def _note(summary, parked, key, kind, detail):
    """결과를 요약에 반영한다. 진행(실행)이 있었으면 True. 정지·잠김·이미 처리됨·결정적 실패는 이번 drain에서 다시 건드리지 않는다."""
    if kind == "done":
        summary["done"].append(key)
    elif kind == "failed":
        summary["failed"].append([key, detail])
    elif kind == "locked":
        summary["locked"].append(key)
    elif kind == "stopped":
        summary["stopped"][key] = detail
    if kind not in ("done", "failed") or detail == "deterministic":
        parked.add(key)
    summary["executed"] += kind in ("done", "failed")
    return kind in ("done", "failed")


def drain(root, executors, now_fn=time.time, max_tasks=None, boot_id_fn=lease.boot_id):
    """실행 가능한 Python 작업을 더 진행되지 않을 때까지(또는 max_tasks번 실행할 때까지) 처리하고 요약을 돌려준다.

    작업마다 claim -> executor -> complete/fail. 잠겨 있는(다른 runner가 실행 중) 작업과 정지 사유가 있는 작업은
    이번 drain에서 다시 시도하지 않는다. 일시적 실패는 다음 회차에서 곧바로 재시도한다(대기·백오프는 3단계).
    """
    summary = {"done": [], "failed": [], "stopped": {}, "locked": [], "executed": 0}
    parked = set()
    while True:
        todo, summary["untouched"] = _scan(root, executors)
        progressed = False
        for key in [k for k in todo if k not in parked]:
            if max_tasks is not None and summary["executed"] >= max_tasks:
                break
            res = queue.claim(root, key, os.getpid(), boot_id_fn(), now_fn(), None, boot_id_fn)
            if not res["ok"]:
                kinds = {"locked": "locked", "skip": "skipped", "wait": "skipped", "unregistered": "skipped"}
                progressed |= _note(summary, parked, key, kinds.get(res["reason"], "stopped"), res["reason"])
                continue
            task_dir = os.path.join(root, "tasks", key)
            task, out_dir = read_json(os.path.join(task_dir, "contract.json")), os.path.join(task_dir, "out")
            os.makedirs(out_dir, exist_ok=True)
            error = _execute(executors, task, out_dir)
            if error is None:
                try:
                    queue.complete(root, key, res["run_id"], res["lease"], now_fn())
                except (ValueError, OSError) as exc:  # 산출물 경로·파일 문제: 완료할 수 없다 = 결정적 실패
                    error = ("deterministic", "%s: %s" % (type(exc).__name__, exc))
            if error is not None:
                queue.fail(root, key, res["run_id"], res["lease"], error[0], error[1], now_fn())
            progressed |= _note(summary, parked, key, "done" if error is None else "failed",
                                res["run_id"] if error is None else error[0])
        if not progressed:
            return summary


def main(argv):
    """python -m harness.runner <root> <module:EXECUTORS> [--max N] -> 요약을 JSON 한 줄로 출력."""
    module, _, attr = argv[1].partition(":")
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    summary = drain(argv[0], getattr(importlib.import_module(module), attr), max_tasks=limit)
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
