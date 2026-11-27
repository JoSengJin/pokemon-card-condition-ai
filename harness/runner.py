"""한도 중에도 도는 Python 작업 runner(DESIGN 4·12절). needs_llm=false 작업만 큐에서 꺼내 실행한다.

- executor는 호출자가 task_type -> callable(contract, out_dir) -> 출력 상대 경로 목록 으로 주입한다.
  이 파일은 외부 모델 호출·네트워크·하위 프로세스를 쓰지 않는다(시험이 소스를 검사한다).
- LLM 작업(needs_llm=true)과 그것에 (간접으로) 의존하는 작업은 건드리지 않는다(claim도 하지 않으므로 장부에도 안 남는다).
- 일시적 실패는 1단계 규칙대로 최대 2회 재시도한 뒤 정지, 결정적 실패·needs_failure_policy·blocked·
  holder_alive_without_lock은 우회하지 않고 요약에 남기고 그 작업만 멈춘다.
  장부 체인 손상(LedgerError)은 무결성 문제라 drain 전체를 멈추고 요약에 INTEGRITY를 남기며 종료 코드 3을 낸다. 데몬·예산·한도 감지는 하지 않는다(3단계).
- 완료 표시(작업 계약 2단계): executor가 정상 반환하면 산출물 해시로 complete.json을 원자 저장한 뒤 complete한다. claim 계획이 adopt
  (중단 전에 표시까지 남겼다)면 executor를 부르지 않고 complete만 한다.
- 호출 깊이: main -> drain -> queue.claim/complete/fail(각각 깊이 2 이하)이라 최대 4다. drain -> manifest.build -> safe_path는 3.
  executor는 호출자 코드(동적 호출)이며 이 깊이에 포함하지 않았다.
"""
import importlib
import json
import os
import sys
import time

from . import contract as ct
from . import cas, ledger, lease, manifest, queue, recovery, states
from .jsonio import read_json, write_json


INTEGRITY_EXIT = 3  # 장부 무결성 오류로 drain이 중단된 경우의 종료 코드


class OutputMismatch(Exception):
    pass


# 한 작업의 기록(파일·CAS·계약·부팅 식별자·장부 쓰기) 오류. 그 작업만 멈추고 drain은 계속한다.
# 장부 체인이 손상된 경우(LedgerError)는 무결성 문제라 여기에 넣지 않고 drain 전체를 멈춘다.
_RECORDING_ERRORS = (OSError, ValueError, queue.QueueError, cas.CasError, lease.LeaseError)


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
    except (Exception, SystemExit) as exc:  # executor가 sys.exit()를 내도 runner가 죽지 않고 결정적 실패로 기록한다
        return recovery.kind_of(exc), "%s: %s" % (type(exc).__name__, exc)  # KeyboardInterrupt는 그대로 전파한다
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


def drain(root, executors, now_fn=time.time, max_tasks=None):
    """실행 가능한 Python 작업을 더 진행되지 않을 때까지(또는 max_tasks번 실행할 때까지) 처리하고 요약을 돌려준다.

    작업마다 claim -> executor -> complete/fail. 잠겨 있는(다른 runner가 실행 중) 작업과 정지 사유가 있는 작업은
    이번 drain에서 다시 시도하지 않는다. 일시적 실패는 다음 회차에서 곧바로 재시도한다(대기·백오프는 3단계).
    """
    summary = {"done": [], "failed": [], "stopped": {}, "stop_reasons": {}, "locked": [], "warnings": [], "executed": 0}
    parked = set()
    try:
        while True:
            todo, summary["untouched"] = _scan(root, executors)
            progressed = False
            for key in [k for k in todo if k not in parked]:
                if max_tasks is not None and summary["executed"] >= max_tasks:
                    break
                try:
                    res = queue.claim(root, key, os.getpid(), lease.boot_id(), now_fn())
                except _RECORDING_ERRORS as exc:  # 이 작업만 못 잡는다(장부·부팅 식별자 조회 오류 등). drain은 계속한다
                    progressed |= _note(summary, parked, key, "stopped", "claim_error: %s: %s" % (type(exc).__name__, exc))
                    continue
                if not res["ok"]:
                    kinds = {"locked": "locked", "skip": "skipped", "wait": "skipped", "unregistered": "skipped"}
                    if "plan" in res:
                        summary["stop_reasons"][key] = res["plan"]["reason"]
                    progressed |= _note(summary, parked, key, kinds.get(res["reason"], "stopped"), res["reason"])
                    continue
                task_dir = os.path.join(root, "tasks", key)
                task, out_dir = read_json(os.path.join(task_dir, "contract.json")), os.path.join(task_dir, "out")
                os.makedirs(out_dir, exist_ok=True)
                adopt = res["plan"]["action"] == "adopt"  # 완료 표시가 이미 맞다: executor를 다시 부르지 않고 반영만 한다
                error = None if adopt else _execute(executors, task, out_dir)
                if error is None:
                    try:
                        if not adopt:  # executor가 정상 반환한 뒤에만 쓰는 완료 표시(원자 저장)
                            write_json(os.path.join(task_dir, ct.COMPLETION),
                                       {"task_key": key, "outputs": manifest.build(out_dir, task["outputs"])})
                        queue.complete(root, key, res["run_id"], res["lease"], now_fn())
                    except _RECORDING_ERRORS as exc:
                        if os.path.exists(os.path.join(task_dir, "done.json")):  # 완료 기록은 남았고 장부만 빠졌다: VERIFIED다
                            summary["warnings"].append([key, "complete_error_after_commit: %s: %s" % (type(exc).__name__, exc)])
                        else:  # 산출물 경로·파일 문제 등: 완료할 수 없다 = 결정적 실패
                            error = ("deterministic", "%s: %s" % (type(exc).__name__, exc))
                if error is not None:
                    try:
                        queue.fail(root, key, res["run_id"], res["lease"], error[0], error[1], now_fn())
                    except _RECORDING_ERRORS as exc:  # 실패 기록도 못 남김: 작업권만 놓고 이 작업만 멈춘다
                        lease.release(res["lease"])
                        progressed |= _note(summary, parked, key, "stopped", "fail_record_error: %s: %s" % (type(exc).__name__, exc))
                        continue
                progressed |= _note(summary, parked, key, "done" if error is None else "failed",
                                    res["run_id"] if error is None else error[0])
            if not progressed:
                return summary
    except ledger.LedgerError as exc:  # 장부 체인 손상은 무결성 문제: 이 작업만이 아니라 drain 전체를 멈추고 알린다
        summary["integrity"] = "INTEGRITY: %s" % exc
        return summary


def main(argv):
    """python -m harness.runner <root> <module:EXECUTORS> [--max N] -> 요약을 JSON 한 줄로 출력."""
    module, _, attr = argv[1].partition(":")
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    summary = drain(argv[0], getattr(importlib.import_module(module), attr), max_tasks=limit)
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False), flush=True)
    return INTEGRITY_EXIT if "integrity" in summary else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
