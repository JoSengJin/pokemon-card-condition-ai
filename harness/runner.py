"""한도 중에도 도는 Python 작업 runner(DESIGN 4·12절). needs_llm=false 작업만 큐에서 꺼내 실행한다.

- executor는 호출자가 task_type -> callable(contract, out_dir) -> 출력 상대 경로 목록 으로 주입한다.
  이 파일은 외부 모델 호출·네트워크·하위 프로세스를 쓰지 않는다(시험이 소스를 검사한다).
- main(Supervisor가 띄우는 경로)은 executor 모듈을 직접 가져오지 않고 sandbox.sandboxed로 macOS sandbox-exec 하위 프로세스에서 실행한다
  (작업 계약 3단계 R6, 2차 결함 G1·G2: executor는 하네스 root에 쓰지 못하고 실행별 staging 폴더에만 쓴다. 확정 out/에는 하네스가
  계약 outputs를 검사해 새 파일로 복사한다). sandbox를 쓸 수 없으면 아무것도 실행하지 않고
  SANDBOX_EXIT로 끝난다(fail-closed). 하위 프로세스 실행은 sandbox.py에 있다. drain에 dict를 직접 넘기는 경로(시험)는 sandbox가 없다.
- sandbox 안 executor가 신호로 죽으면(메모리 부족 등) 작업권 기록을 남긴 채 놓아 다음 claim이 INTERRUPTED 규칙(2단계 R1)대로 다룬다.
- LLM 작업(needs_llm=true)과, VERIFIED가 아닌 LLM 작업에 (간접으로) 의존하는 작업은 건드리지 않는다(claim도 하지 않으므로 장부에도 안 남는다).
  VS3(2026-11-28): VERIFIED인 LLM 작업은 더 이상 오염원이 아니다(PLAN_GATE가 등록한 다음 실험이 ANALYZE에 의존한다). 미검증·실행 중·실패·대기·손상
  LLM 의존은 그대로 막는다. VS3 독립 검증 D3: LLM 작업에 직·간접 의존하는 실험·학습·평가는 장부(ledger.jsonl)에 그 task_key의 plan_gate_declared
  줄(PLAN_GATE만 쓴다)이 있을 때만 실행한다. 등록 경로(queue.enqueue·graph.register_missing 직접 호출·declared.json·업그레이드 전 PENDING)와
  무관하게 실행 직전 이 확인이 마지막 관문이다. 그 밖(결정론 작업 등)의 VERIFIED LLM 의존은 실행한다.
- 일시적 실패는 1단계 규칙대로 최대 2회 재시도한 뒤 정지, 결정적 실패·needs_failure_policy·blocked·
  holder_alive_without_lock은 우회하지 않고 요약에 남기고 그 작업만 멈춘다.
  장부 체인 손상(LedgerError)은 무결성 문제라 drain 전체를 멈추고 요약에 INTEGRITY를 남기며 종료 코드 3을 낸다. 데몬·예산·한도 감지는 하지 않는다(3단계).
- 완료 표시(작업 계약 2단계): executor가 정상 반환하면 산출물 해시로 complete.json을 원자 저장한 뒤 complete한다. claim 계획이 adopt
  (중단 전에 표시까지 남겼다)면 executor를 부르지 않고 complete만 한다.
- 실험 예산(B5-4, 사용자 결정 3 2026-11-28 "실행 시작 시 차감"): 실험·학습·평가 작업은 claim 뒤·executor 직전에 budget.charge(experiment, 1,
  key=논리 실험 키 dedupe.logical_key)를 한 번 부른다. 확인과 차감은 charge 한 번(예산 잠금 안)이다. 같은 논리 실험의 재시도·재개(한도 뒤·체크포인트·
  인프라 장애 복구)는 같은 키라 already(다시 빼지 않는다). 거절(한도·정지)이면 작업권을 지워 놓고(PENDING) 실행하지 않는다. 예산 장부·상태 손상은
  사용량을 모르므로 실행하지 않고 무결성 정지(종료 코드 3). 완료 표시를 반영만 하는 adopt는 차감하지 않는다.
  취소: 이번 시도가 새로 한 차감(seq)만, 실행되지 않았음이 확인된 결정적 실패일 때만(executor 전 대조·사본 실패 = not_started, 어댑터
  not_started·refused) budget.cancel한다. 결과 불명(interrupted)·실험 실패·출력 불일치는 차감 유지. 취소는 실패 기록보다 먼저 한다(그 사이 kill이면
  작업권이 남아 INTERRUPTED → 결과 확인 대기, 다시 실행되면 새로 차감). executor 상태는 sandbox 결과 줄(ChildError.status)로 받는다.
- 호출 깊이: main -> drain -> queue.claim/complete/fail(각각 깊이 2 이하)이라 최대 4다. drain -> manifest.build -> safe_path는 3.
  drain -> budget.charge/cancel -> ledger.verify -> _check_line은 3, drain -> dedupe.logical_key -> _command는 2, main -> drain -> _scan -> ledger.events -> _load는 4.
  executor는 호출자 코드(동적 호출)이며 이 깊이에 포함하지 않았다(experiment_exec.execute 자체 깊이 3).
"""
import json
import os
import sys
import time

from . import contract as ct
from . import budget, cas, claude_perm, dedupe, experiment_exec, ledger, lease, manifest, opstate, queue, recovery, sandbox, states
from .jsonio import read_json, write_json


INTEGRITY_EXIT = 3  # 장부 무결성 오류로 drain이 중단된 경우의 종료 코드
SANDBOX_EXIT = 5  # sandbox-exec를 쓸 수 없어 executor를 실행하지 않은 경우의 종료 코드
EXECUTOR_TABLE_EXIT = 6  # executor 표를 sandbox 안에서 읽지 못해(감싼 표 거절 등) 아무것도 실행하지 않은 경우의 종료 코드(3차 결함 H10)
NOT_RUN = ("not_started", "refused")  # 실행되지 않았음이 확인된 상태(이 시도의 예산 차감 취소 대상, B5-4)


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
    tainted = {k for k in llm if state[k] != states.VERIFIED}  # VERIFIED LLM 작업 자체도 아래 상태 검사로 실행하지 않는다
    reach = set(llm)
    while True:  # LLM 작업에 직·간접 의존하는 모든 작업
        more = {k for k, c in contracts.items() if k not in reach and any(d in reach for d in c["depends_on"])}
        if not more:
            break
        reach |= more
    # VS3 D3: 그중 실험·학습·평가는 장부에 관문 통과 줄(plan_gate_declared)이 있을 때만 실행한다(실행 직전 마지막 관문: 공개 등록 함수로 관문을 건너뛴 등록·업그레이드 전 PENDING 차단)
    # shortcut: 회차마다 장부 전체를 읽는다(줄 수에 비례), 장부가 커지면 색인을 둔다
    passed = {d.get("task_key") for d in ledger.events(os.path.join(root, "ledger.jsonl"), "plan_gate_declared") if isinstance(d, dict)}
    tainted |= {k for k in reach - llm if contracts[k]["task_type"] in dedupe.CONDITION_TYPES and k not in passed}
    while True:  # 위 두 오염원에 직접·간접으로 의존하는 작업
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


def _execute(root, executors, task, out_dir, source_root):
    """executor를 실행한다. 정상이면 None, 오류면 (실패 종류, 설명, 상태). 종류는 1단계 규칙(recovery.kind_of). 상태는 executor를 부르기 전
    실패(대조·사본)면 "not_started", executor 오류면 그 status(실험 어댑터, sandbox는 ChildError.status) 또는 None.
    실험·학습·평가는 실행 직전에 입력을 source_root에서 작업 폴더 in/으로 복사하며 복사본 SHA를 계약과 대조한다(다르거나 폴더 밖·링크·봉인
    이름이면 executor를 부르지 않고 결정적 실패, 검증 결함 F3). executor는 그 사본을 읽는다(sandbox 경로는 HARNESS_INPUT_DIR, 2차 결함 G6).
    3차 결함: code_sha를 source_root HEAD와 다시 대조하고(H1), executor에는 command의 자리표시자 {input:<경로>}를 사본 절대 경로로 바꾼
    계약 사본을 넘긴다(H7, 계약 파일은 그대로). 위 verify_code 결과는 experiment_exec.record_code가 파일별 git blob SHA 목록(작업 폴더
    code-check.json, sandbox가 쓰지 못한다)으로 어댑터에 전달한다(실패하면 executor를 부르지 않는다). executor가 원본을 직접 읽는 것은 막지 않는다(한계)."""
    called = False
    try:
        if task["task_type"] in dedupe.CONDITION_TYPES:  # 실행 직전 code_sha를 source_root HEAD와 다시 대조(3차 결함 H1)
            dedupe.verify_code(task, source_root)
            claude_perm.stage_inputs(os.path.dirname(out_dir), task, source_root, root)
            copies, cond = os.path.join(os.path.dirname(os.path.abspath(out_dir)), "in"), task["run_conditions"]
            task = dict(task, run_conditions=dict(cond, command=[dedupe.PLACEHOLDER.sub(  # 3차 H7: 자리표시자 → 대조한 사본의 절대 경로
                lambda m: os.path.join(copies, os.path.normpath(m.group(1))), arg) for arg in cond["command"]]))
            os.environ[experiment_exec.SOURCE_ENV] = os.path.realpath(source_root)  # 실험 어댑터의 workdir(sandbox 자식도 물려받는다)
            os.environ[experiment_exec.CHECK_ENV] = experiment_exec.record_code(task, os.path.dirname(os.path.abspath(out_dir)), source_root)  # 6c564d4 뒤 sandbox는 git을 못 읽는다: 위 verify_code 결과를 어댑터에 전달(작업 폴더 code-check.json)
        called = True
        produced = executors[task["task_type"]](task, out_dir)
        if sorted(produced) != sorted(task["outputs"]):
            raise OutputMismatch("executor가 돌려준 출력 목록이 계약의 outputs와 다르다: %r" % (produced,))
    except sandbox.ChildError as exc:  # sandbox 안 실패: 자식이 정한 종류(transient|deterministic|interrupted)·상태와 원래 오류 문구
        return exc.kind, str(exc), exc.status
    except (Exception, SystemExit) as exc:  # executor가 sys.exit()를 내도 runner가 죽지 않고 결정적 실패로 기록한다
        return recovery.kind_of(exc), "%s: %s" % (type(exc).__name__, exc), getattr(exc, "status", None) if called else "not_started"
    return None  # KeyboardInterrupt는 그대로 전파한다


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


def drain(root, executors, now_fn=time.time, max_tasks=None, source_root=None):
    """실행 가능한 Python 작업을 더 진행되지 않을 때까지(또는 max_tasks번 실행할 때까지) 처리하고 요약을 돌려준다.

    작업마다 claim -> executor -> complete/fail. 잠겨 있는(다른 runner가 실행 중) 작업과 정지 사유가 있는 작업은
    이번 drain에서 다시 시도하지 않는다. 일시적 실패는 다음 회차에서 곧바로 재시도한다(대기·백오프는 3단계).
    source_root: 실험·학습·평가 입력 원본 폴더(기본 저장소 sandbox.REPO).
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
                spent, spend_key = None, None
                if not adopt and task["task_type"] in dedupe.CONDITION_TYPES:  # 실행 시작 시 실험 예산 차감(B5-4, 키 = 논리 실험 키)
                    try:
                        spend_key = dedupe.logical_key(task)
                        spent = budget.charge(root, "experiment", 1, now_fn(), key=spend_key)
                    except (budget.BudgetError, opstate.OpStateError, ledger.LedgerError) as exc:  # 사용량을 모른다: 실행하지 않고 무결성 정지
                        lease.release(res["lease"], remove=True)
                        summary["integrity"] = "INTEGRITY: budget: %s: %s" % (type(exc).__name__, exc)
                        return summary
                    except _RECORDING_ERRORS as exc:  # 이 작업만(계약 키 계산·기록 오류): 실행하지 않고 작업권을 지워 놓는다
                        spent = {"ok": False, "reason": "error: %s: %s" % (type(exc).__name__, exc)}
                    if not spent["ok"]:
                        lease.release(res["lease"], remove=True)
                        progressed |= _note(summary, parked, key, "stopped", "budget_refused:%s" % spent["reason"])
                        continue
                error = None if adopt else _execute(root, executors, task, out_dir, source_root or sandbox.REPO)
                if error is not None and error[0] == "deterministic" and error[2] in NOT_RUN and spent and "seq" in spent:
                    try:  # 실행되지 않았음이 확인됐다: 이번 시도가 새로 한 차감만 되돌린다(재시도의 already 차감은 되돌리지 않는다)
                        undo = budget.cancel(root, "experiment", spend_key, spent["seq"], now_fn())
                        if not undo["ok"]:
                            summary["warnings"].append([key, "budget_cancel_refused: %s" % undo["reason"]])
                    except (budget.BudgetError, ledger.LedgerError, OSError) as exc:  # 취소하지 못하면 차감 유지(보수적)
                        summary["warnings"].append([key, "budget_cancel_error: %s: %s" % (type(exc).__name__, exc)])
                if error is not None and error[0] == "interrupted":  # 작업권 기록은 남기고 잠금만 놓는다 → 다음 claim이 INTERRUPTED로 본다
                    lease.release(res["lease"])
                    progressed |= _note(summary, parked, key, "stopped", "executor_killed: %s" % error[1])
                    continue
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
    """python -m harness.runner <root> <module:EXECUTORS> [--max N] [--source-root D] -> 요약을 JSON 한 줄로 출력.
    executor는 sandbox 안에서만 실행한다."""
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    source = argv[argv.index("--source-root") + 1] if "--source-root" in argv else None
    if not sandbox.available():
        print(json.dumps({"sandbox_unavailable": sandbox.SANDBOX_EXEC, "executed": 0}, ensure_ascii=False), flush=True)
        return SANDBOX_EXIT
    try:
        table = sandbox.sandboxed(os.path.abspath(argv[0]), argv[1])
    except sandbox.ChildError as exc:  # 표를 못 읽음(감싼 표 거절 등): traceback 없이 요약을 남기고 결정적 종료 코드(3차 결함 H10)
        print(json.dumps({"executor_table_error": str(exc)[:2000], "executed": 0}, ensure_ascii=False), flush=True)
        return EXECUTOR_TABLE_EXIT
    summary = drain(argv[0], table, max_tasks=limit, source_root=source)
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False), flush=True)
    return INTEGRITY_EXIT if "integrity" in summary else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
