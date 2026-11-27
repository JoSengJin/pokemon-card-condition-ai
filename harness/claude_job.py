"""Claude 작업 칸(Supervisor가 한 번에 하나만 돌리는 needs_llm=true 작업): 고르기(pick) → 실행(execute) → 결과 반영(settle).

상태 파일 root/supervisor/claude.json: {task_key, status(new|running|rate_limited|done|failed|blocked|stale), session_id,
unknown_attempts, mode, ...}. Supervisor가 죽었다 다시 시작해도 이 파일과 opstate.json만으로 이어간다.
- 큐 작업은 Claude가 일하는 동안 PENDING으로 둔다(한도로 기다리는 동안 작업권을 쥐거나 실패로 세지 않게). Claude가 끝나면 settle이
  claim → complete(산출물 manifest 검증) 또는 fail(deterministic: 결과 불명·실패는 자동 재시도하지 않음)로 큐에 반영한다.
  Supervisor는 root마다 하나만 돈다(supervisor.lock)는 것이 전제다.
- 새 세션은 `--session-id <uuid>`로 시작해 실행 전에 세션 ID를 저장한다. status가 running인 채 Supervisor가 죽었으면
  claude.pid의 pid가 같은 부팅에서 살아 있는 동안 기다리고(겹쳐 실행 안 함), 죽었으면 `--resume`으로 이어간다.
- `--resume`이 한도가 아닌 이유로 실패(비정상 종료·세션 없음)하면 장부 상태를 가리키는 프롬프트로 새 세션을 연다(DESIGN 12절).
- 한도: resetsAt이 해석되고 지금보다 뒤면 그 시각에 재개. 모르면(또는 이미 지난 값이면) UNKNOWN_BACKOFF_S 간격으로
  최대 MAX_UNKNOWN_RETRIES회 다시 시도하고, 그래도 한도면 exhausted로 멈추고 알림을 남긴다(자동 해제 안 됨).
- 모델·effort는 route.route(정책 v1)로 정하고 실행마다 route_record를 남긴다. 실제 적용 확인(T7)은 주장하지 않는다(verified=false).
호출 깊이(시작 함수 기준): pick 2, execute 3(run_once → scan → 말단), settle 3(queue.claim·complete·fail, opstate.set_condition).
"""
import functools
import os
import uuid

from . import contract as ct
from . import cas, claude_run, ledger, lease, opstate, queue, route, states
from .jsonio import read_json, write_json

JOB = os.path.join("supervisor", "claude.json")
PIDFILE = os.path.join("supervisor", "claude.pid")
UNKNOWN_BACKOFF_S = (60, 300, 900)
MAX_UNKNOWN_RETRIES = len(UNKNOWN_BACKOFF_S)
ACTIVE = ("new", "running", "rate_limited")
_RECORDING_ERRORS = (OSError, ValueError, queue.QueueError, cas.CasError, lease.LeaseError)
_KIND_STATE = {"short": opstate.RATE_LIMITED_SHORT, "weekly": opstate.RATE_LIMITED_WEEKLY}


def pick(root, now):
    """이어갈 작업(claude.json) 또는 새 작업(의존이 모두 VERIFIED인 PENDING LLM 작업, task_key 순). 없거나 기다려야 하면 None."""
    path, log = os.path.join(root, JOB), os.path.join(root, "ledger.jsonl")
    job = read_json(path)
    if isinstance(job, dict) and job.get("status") in ACTIVE:
        if states.state_of(states.facts(os.path.join(root, "tasks", ct.check_key(job["task_key"]))), False) == states.PENDING:
            held = read_json(os.path.join(root, PIDFILE), {}) if job["status"] == "running" else {}
            pid = held.get("pid") if isinstance(held, dict) else None
            if isinstance(pid, int) and held.get("boot_id") == lease.boot_id() and lease.pid_alive(pid):
                return None  # 이전 Supervisor가 띄운 claude가 아직 실행 중: 겹쳐 실행하지 않는다
            return job
        job.update(status="stale", updated_at=now)  # 큐 쪽에서 이미 끝났거나 멈춘 작업
        write_json(path, job)
        ledger.append(log, now, "claude_job_closed", {"task_key": job["task_key"], "status": "stale"})
    tasks_dir = os.path.join(root, "tasks")
    for key in sorted(os.listdir(tasks_dir)) if os.path.isdir(tasks_dir) else []:
        try:
            info = states.facts(os.path.join(tasks_dir, ct.check_key(key)))
        except ct.ContractError:
            continue
        task = info["contract"]
        if task is None or not task["needs_llm"] or states.state_of(info, False) != states.PENDING:
            continue
        if all(states.state_of(states.facts(os.path.join(tasks_dir, d)), False) == states.VERIFIED for d in task["depends_on"]):
            job = {"task_key": key, "status": "new", "session_id": None, "unknown_attempts": 0, "picked_at": now,
                   "updated_at": now}
            write_json(path, job)
            ledger.append(log, now, "claude_job_picked", {"task_key": key, "task_type": task["task_type"]})
            return job
    return None


def _prompt(root, job, mode, failed_session=None):
    task_dir = os.path.join(root, "tasks", job["task_key"])
    base = ("하네스 작업 %s를 수행한다.\n계약 파일: %s\n산출물 폴더: %s\n계약의 outputs를 산출물 폴더에 쓴다."
            % (job["task_key"], os.path.join(task_dir, "contract.json"), os.path.join(task_dir, "out")))
    if mode == "resume":
        return "사용량 한도 또는 중단으로 멈춘 같은 작업을 이어서 진행한다.\n" + base
    if failed_session:
        return ("이전 세션 %s를 이어받지 못해 새 세션으로 시작한다. 장부 %s와 작업 폴더의 현재 상태에서 이어간다.\n"
                % (failed_session, os.path.join(root, "ledger.jsonl"))) + base
    return base


def execute(root, job, claude_bin, now_fn, runner=None, env=None):
    """claude를 실행한다(재개 가능하면 --resume, 실패하면 새 세션). {"kind": success|rate_limited|failed, "mode", "result"}."""
    path, log = os.path.join(root, JOB), os.path.join(root, "ledger.jsonl")
    contract = read_json(os.path.join(root, "tasks", job["task_key"], "contract.json"))
    decision = route.route(contract, [], route.load_policy())
    decision = route.with_support(decision, route.probe_cli_support(
        run=functools.partial(claude_run.help_text, claude_bin, runner, env)))
    if decision["model"] is None:  # 정책상 LLM 미사용 유형인데 needs_llm=true: 계약 문제이며 실행하지 않는다
        route.record_decision(root, decision, decision["applied"], {"task_key": job["task_key"]})
        return {"kind": "failed", "mode": None, "result": {"error": "route_no_model: %s" % decision["reason"]}}
    run = runner or functools.partial(claude_run.default_runner, pidfile=os.path.join(root, PIDFILE),
                                      stamp={"boot_id": lease.boot_id()})
    failed_session = None
    for mode in (("resume", "new") if job.get("session_id") and job["status"] != "new" else ("new",)):
        if mode == "new":
            job["session_id"] = str(uuid.uuid4())
        job.update(status="running", mode=mode, updated_at=now_fn())
        write_json(path, job)  # 실행 전에 세션 ID를 남긴다(실행 중 Supervisor가 죽어도 이어갈 수 있게)
        ledger.append(log, now_fn(), "claude_run_started", {"task_key": job["task_key"], "mode": mode,
                      "session_id": job["session_id"], "model": decision["model"], "effort": decision["effort"]})
        started = now_fn()
        res = claude_run.run_once(claude_bin, _prompt(root, job, mode, failed_session), decision["model"],
                                  decision["effort"], run, env, resume=job["session_id"] if mode == "resume" else None,
                                  session_id=job["session_id"] if mode == "new" else None)
        init = res["init"] or {}
        limits = list(decision["limitations"]) + ["t7_not_claimed: 이 기록만으로 실제 적용(T7) 통과를 주장하지 않는다"]
        if init.get("effort") is None:
            limits.append("observed_effort_unavailable: init 이벤트에 effort 없음(실제 적용 effort 미확인)")
        if init.get("model") is None:
            limits.append("observed_model_unavailable: init 이벤트에 model 없음(실제 적용 모델 미확인)")
        elif init["model"] != decision["model"]:
            limits.append("observed_model_differs: 요청 %s, init %s(별칭과 전체 이름의 대응 미확인)" % (decision["model"], init["model"]))
        applied = {"flags": {"model": decision["model"], "effort": decision["effort"]}, "help_check": decision["applied"],
                   "model": init.get("model"), "effort": init.get("effort"), "verified": False,
                   "source": "stream-json init" if res["init"] else "미확인(init 이벤트 없음)"}
        result = res["result"] if isinstance(res["result"], dict) else {}
        route.record_decision(root, dict(decision, limitations=limits), applied, {
            "task_key": job["task_key"], "duration_s": now_fn() - started,
            "tokens": result.get("usage") if isinstance(result.get("usage"), dict) else None})
        kind = "rate_limited" if res["limited"] else "success" if res["success"] else "failed"
        if kind == "failed" and mode == "resume":  # 세션 없음·비정상 종료: 장부 상태로 새 세션을 연다
            failed_session = job["session_id"]
            ledger.append(log, now_fn(), "claude_resume_failed", {"task_key": job["task_key"], "session_id": failed_session,
                          "returncode": res["returncode"], "error": res["error"]})
            continue
        if res["session_id"] and res["session_id"] != job["session_id"]:
            job["session_id"] = res["session_id"]  # init이 알려준 실제 세션 ID를 따른다
        return {"kind": kind, "mode": mode, "result": res}


def settle(root, job, outcome, now):
    """실행 결과를 상태에 반영한다. 한도면 opstate 조건을 켜고, 끝났으면 큐에 complete/fail. 새 job 상태 문자열을 돌려준다."""
    path, log, key = os.path.join(root, JOB), os.path.join(root, "ledger.jsonl"), job["task_key"]
    if outcome["kind"] == "rate_limited":
        limit = outcome["result"]["rate_limit"]
        when = limit["resets_at"] if limit["resets_at"] is not None and limit["resets_at"] > now else None
        tries = job.get("unknown_attempts", 0) if when is None else 0
        exhausted = when is None and tries >= MAX_UNKNOWN_RETRIES
        next_try = when if when is not None else (None if exhausted else now + UNKNOWN_BACKOFF_S[tries])
        job.update(status="rate_limited", unknown_attempts=tries + (1 if when is None and not exhausted else 0), updated_at=now)
        write_json(path, job)
        info = {"resets_at": limit["resets_at"], "resets_at_raw": limit["resets_at_raw"], "kind": limit["kind"],
                "type_raw": limit["type_raw"], "status": limit["status"], "next_try_at": next_try, "exhausted": exhausted,
                "unknown_attempts": tries, "session_id": job["session_id"], "task_key": key}
        name = _KIND_STATE.get(limit["kind"], opstate.RATE_LIMITED_UNKNOWN)
        opstate.set_condition(root, name, now, "supervisor", "사용량 한도(Claude 작업만 멈춤)", info)
        if exhausted:
            opstate.notify(root, now, "rate_limit_unknown_exhausted",
                           "재개 시각을 몰라 %d회 다시 시도했지만 한도: Claude 작업 정지(사람 확인 필요)" % tries, info)
        return "rate_limited"
    res = queue.claim(root, key, os.getpid(), lease.boot_id(), now)
    status = "blocked"
    if res["ok"] and outcome["kind"] == "success":
        try:
            queue.complete(root, key, res["run_id"], res["lease"], now)
            status = "done"
        except _RECORDING_ERRORS as exc:
            queue.fail(root, key, res["run_id"], res["lease"], "deterministic", "claude 산출물 완료 실패: %s" % exc, now)
            status = "failed"
    elif res["ok"]:
        error = outcome["result"].get("error") or "claude 실행 실패(종료 코드 %r)" % outcome["result"].get("returncode")
        queue.fail(root, key, res["run_id"], res["lease"], "deterministic", error, now)
        status = "failed"
    job.update(status=status, updated_at=now)
    write_json(path, job)
    ledger.append(log, now, "claude_job_finished", {"task_key": key, "status": status, "mode": outcome["mode"],
                                                     "claim": None if res["ok"] else res["reason"]})
    if status != "done":
        opstate.notify(root, now, "claude_job_" + status, "Claude 작업이 끝나지 않음(%s): %s" % (status, key),
                       {"task_key": key, "claim": None if res["ok"] else res["reason"]})
    return status
