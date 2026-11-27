"""Claude 작업 칸(Supervisor가 한 번에 하나만 돌리는 needs_llm=true 작업): 고르기(pick) → 실행(execute) → 결과 반영(settle).

상태 파일 root/supervisor/claude.json: {task_key, status(new|running|rate_limited|done|failed|blocked|stale), session_id,
unknown_attempts, mode, run_token, hold_reason, ...}. Supervisor가 죽었다 다시 시작해도 이 파일과 opstate.json만으로 이어간다.
- 큐 작업은 Claude가 일하는 동안 PENDING으로 둔다(한도로 기다리는 동안 작업권을 쥐거나 실패로 세지 않게). Claude가 끝나면 settle이
  claim → complete(산출물 manifest 검증)로 큐에 반영한다. 결정적 근거가 있는 실패(정책상 모델 없음, 산출물 완료 실패)만 fail(deterministic).
  Supervisor는 root마다 하나만 돈다(supervisor.lock)는 것이 전제다.
- 사람 확인 대기(status=blocked, hold_reason): claude 실패 원인을 출력만으로 일시적(네트워크 등)/결정적으로 가를 근거가 없을 때,
  pid 기록이 job과 맞지 않을 때, 결과 반영의 claim이 거절됐을 때. 큐 작업은 PENDING 그대로 두고 알림(claude_job_blocked)을 남기며,
  pick은 그 작업을 다시 고르지도 실행하지도 않는다(자동 재시도 없음). 사람이 확인한 뒤 claude.json을 지우면(새 세션으로 다시 고름)
  또는 status를 rate_limited로 고치면(같은 세션 --resume) 이어간다. 큐 작업이 PENDING이 아니게 되면 stale로 닫는다.
- 새 세션은 `--session-id <uuid>`로 시작해 실행 전에 세션 ID를 저장한다. 실행마다 run_token(uuid)을 claude.json과 claude.pid에 함께
  적고, pid 파일에는 boot_id·session_id·mode·run_token·pid를 남긴다. status가 running인 채 Supervisor가 죽었으면:
  pid 기록의 session_id·mode·run_token이 job과 같고 pid가 같은 부팅에서 살아 있는 동안 기다리고(겹쳐 실행 안 함), 죽었으면 `--resume`.
  기록이 없거나 맞지 않으면(pid 기록 전에 죽음·낡은 파일) 그 세션의 claude가 떠 있는지 알 수 없으므로 자동 재개하지 않고 사람 확인 대기.
- `--resume`이 한도가 아닌 이유로 실패(비정상 종료·세션 없음)하면 장부 상태를 가리키는 프롬프트로 새 세션을 연다(DESIGN 12절).
- 한도: resetsAt이 해석되고 지금보다 뒤이며 ratelimit.MAX_RESET_AHEAD_S(8일) 안이면 그 시각에 재개. 8일보다 멀면 미상으로 보고
  알린다(rate_limit_reset_too_far). 모르면(또는 이미 지난 값이면) UNKNOWN_BACKOFF_S 간격으로
  최대 MAX_UNKNOWN_RETRIES회 다시 시도하고, 그래도 한도면 exhausted로 멈추고 알림을 남긴다(자동 해제 안 됨).
- 모델·effort는 route.route(정책 v1)로 정하고 실행마다 route_record를 남긴다. 실제 적용 확인(T7)은 주장하지 않는다(verified=false).
호출 깊이(시작 함수 기준): pick 2, execute 3(run_once → scan → 말단), settle 3(queue.claim·complete·fail, opstate.set_condition).
"""
import functools
import os
import uuid

from . import contract as ct
from . import cas, claude_run, ledger, lease, opstate, queue, ratelimit, route, states
from .jsonio import read_json, write_json

JOB = os.path.join("supervisor", "claude.json")
PIDFILE = os.path.join("supervisor", "claude.pid")
UNKNOWN_BACKOFF_S = (60, 300, 900)
MAX_UNKNOWN_RETRIES = len(UNKNOWN_BACKOFF_S)
ACTIVE = ("new", "running", "rate_limited")
HOLD = "blocked"  # 사람 확인 대기(자동으로 다시 고르거나 실행하지 않는다)
_RECORDING_ERRORS = (OSError, ValueError, queue.QueueError, cas.CasError, lease.LeaseError)
_KIND_STATE = {"short": opstate.RATE_LIMITED_SHORT, "weekly": opstate.RATE_LIMITED_WEEKLY}


def pick(root, now):
    """이어갈 작업(claude.json) 또는 새 작업(의존이 모두 VERIFIED인 PENDING LLM 작업, task_key 순). 없거나 기다려야 하면 None."""
    path, log = os.path.join(root, JOB), os.path.join(root, "ledger.jsonl")
    job = read_json(path)
    if isinstance(job, dict) and job.get("status") in ACTIVE + (HOLD,):
        if states.state_of(states.facts(os.path.join(root, "tasks", ct.check_key(job["task_key"]))), False) == states.PENDING:
            if job["status"] == "running":
                held = read_json(os.path.join(root, PIDFILE), {})
                held = held if isinstance(held, dict) else {}
                if any(held.get(k) != job.get(k) for k in ("session_id", "mode", "run_token")):
                    job.update(status=HOLD, hold_reason="pid_record_mismatch", updated_at=now)  # 그 세션 claude 생존 불명
                    write_json(path, job)
                    ledger.append(log, now, "claude_job_closed", {"task_key": job["task_key"], "status": HOLD,
                                                                  "hold_reason": "pid_record_mismatch"})
                    opstate.notify(root, now, "claude_job_blocked", "claude pid 기록이 작업과 맞지 않아 자동 재개하지 않음"
                                   "(사람 확인 필요): %s" % job["task_key"], {"task_key": job["task_key"], "pid_record": held})
                    return None
                pid = held.get("pid")
                if isinstance(pid, int) and held.get("boot_id") == lease.boot_id() and lease.pid_alive(pid):
                    return None  # 이전 Supervisor가 띄운 claude가 아직 실행 중: 겹쳐 실행하지 않는다
            return None if job["status"] == HOLD else job
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
    """claude를 실행한다(재개 가능하면 --resume, 실패하면 새 세션). {"kind": success|rate_limited|failed|halted, "mode", "result"}."""
    path, log = os.path.join(root, JOB), os.path.join(root, "ledger.jsonl")
    contract = read_json(os.path.join(root, "tasks", job["task_key"], "contract.json"))
    decision = route.route(contract, [], route.load_policy())
    decision = route.with_support(decision, route.probe_cli_support(
        run=functools.partial(claude_run.help_text, claude_bin, runner, env)))
    if decision["model"] is None:  # 정책상 LLM 미사용 유형인데 needs_llm=true: 계약 문제이며 실행하지 않는다
        route.record_decision(root, decision, decision["applied"], {"task_key": job["task_key"]})
        return {"kind": "failed", "mode": None, "result": {"error": "route_no_model: %s" % decision["reason"]}}
    failed_session = None
    for mode in (("resume", "new") if job.get("session_id") and job["status"] != "new" else ("new",)):
        # 실행 직전마다 다시 본다: 실패한 --resume 실행 중에 건 정지 뒤에는 새 세션을 열지 않는다
        if opstate.effective(opstate.load(root)) in opstate.HALTING:
            return {"kind": "halted", "mode": mode, "result": {}}
        if mode == "new":
            job["session_id"] = str(uuid.uuid4())
        job.update(status="running", mode=mode, run_token=uuid.uuid4().hex, updated_at=now_fn())
        write_json(path, job)  # 실행 전에 세션 ID를 남긴다(실행 중 Supervisor가 죽어도 이어갈 수 있게)
        run = runner or functools.partial(claude_run.default_runner, pidfile=os.path.join(root, PIDFILE), stamp={
            "boot_id": lease.boot_id(), "session_id": job["session_id"], "mode": mode, "run_token": job["run_token"]})
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
    if outcome["kind"] == "halted":  # job·큐를 그대로 둔다: 사용자가 정지를 풀면 같은 상태에서 이어간다
        return "halted"
    if outcome["kind"] == "rate_limited":
        limit = outcome["result"]["rate_limit"]
        far = limit["resets_at"] is not None and limit["resets_at"] > now + ratelimit.MAX_RESET_AHEAD_S
        when = limit["resets_at"] if limit["resets_at"] is not None and limit["resets_at"] > now and not far else None
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
        if far:
            opstate.notify(root, now, "rate_limit_reset_too_far", "재개 시각이 8일보다 멀어 믿지 않고 미상으로 다시 시도", info)
        if exhausted:
            opstate.notify(root, now, "rate_limit_unknown_exhausted",
                           "재개 시각을 몰라 %d회 다시 시도했지만 한도: Claude 작업 정지(사람 확인 필요)" % tries, info)
        return "rate_limited"
    status, reason = HOLD, None
    if outcome["kind"] == "failed" and outcome["mode"] is not None:
        # claude 실행 실패: 출력만으로 일시적(네트워크 등)/결정적을 가를 근거가 없다 → FAILED로 만들지 않고 사람 확인 대기
        reason = "claude_failed_cause_unknown: %s" % (outcome["result"].get("error") or
                                                      "종료 코드 %r" % outcome["result"].get("returncode"))
    else:
        res = queue.claim(root, key, os.getpid(), lease.boot_id(), now)
        reason = None if res["ok"] else "claim_refused: %s" % res["reason"]
        if res["ok"] and outcome["kind"] == "success":
            try:
                queue.complete(root, key, res["run_id"], res["lease"], now)
                status = "done"
            except _RECORDING_ERRORS as exc:
                queue.fail(root, key, res["run_id"], res["lease"], "deterministic", "claude 산출물 완료 실패: %s" % exc, now)
                status = "failed"
        elif res["ok"]:  # mode=None: 실행 전 계약 문제(route_no_model)라 결정적 근거가 있다
            queue.fail(root, key, res["run_id"], res["lease"], "deterministic", outcome["result"]["error"], now)
            status = "failed"
    job.update(status=status, updated_at=now, hold_reason=reason)
    write_json(path, job)
    ledger.append(log, now, "claude_job_finished", {"task_key": key, "status": status, "mode": outcome["mode"],
                                                     "hold_reason": reason, "rate_limit": outcome["result"].get("rate_limit")})
    if status != "done":
        opstate.notify(root, now, "claude_job_" + status, "Claude 작업이 끝나지 않음(%s, 사람 확인 필요): %s" % (status, key),
                       {"task_key": key, "hold_reason": reason})
    return status
