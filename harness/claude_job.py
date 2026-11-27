"""Claude 작업(Supervisor가 한 번에 하나만 돌리는 needs_llm=true 작업): 고르기(pick) → 실행(execute) → 결과 반영(settle).

작업별 상태 파일 root/supervisor/claude/<task_key>.json(작업 계약 2단계 R5: 한 칸 구조를 작업별로 바꿨다): {task_key, status(new|running|
rate_limited|done|failed|blocked|stale), session_id, unknown_attempts, crash_resumes, mode, run_token, hold_reason, ...}와
같은 폴더의 <task_key>.pid. Supervisor가 죽었다 다시 시작해도 이 파일들과 opstate.json만으로 이어간다.
- 큐 작업은 Claude가 일하는 동안 PENDING으로 둔다(한도로 기다리는 동안 작업권을 쥐거나 실패로 세지 않게). Claude가 끝나면 settle이
  claim → complete(완료 표시·산출물 manifest 검증)로 큐에 반영한다. 결정적 근거가 있는 실패(정책상 모델 없음, 산출물 완료 실패)만 fail(deterministic).
  Supervisor는 root마다 하나만 돈다(supervisor.lock)는 것이 전제다.
- 사람 확인 대기(status=blocked, hold_reason)는 그 작업(과 그것에 의존하는 작업)만 멈춘다. pick은 대기 작업을 건너뛰고 다른 독립 작업을
  고른다. 공통 장애 근거(현재는 한도 이벤트 → opstate 한도 조건)만 Claude 실행 전체를 멈춘다. 대기 사유: claude 실패(원인 필드 포함),
  pid 기록 불일치, 결과 반영 claim 거절, 완료 표시 없음, 실행 중 사망 재개 한도(recovery.MAX_INTERRUPTS=2) 초과. 알림(claude_job_blocked)을
  남기며 자동 재시도하지 않는다. 사람이 확인한 뒤 그 작업의 상태 파일을 지우면(새 세션으로 다시 고름) 또는 status를 rate_limited로
  고치면(같은 세션 --resume) 이어간다. 큐 작업이 PENDING이 아니게 되면 닫는다(VERIFIED면 done, 그 밖은 stale).
- 완료 표시(contract.COMPLETION): claude가 성공 종료하고 Claude의 선언(out/ 안 contract.DECLARATION: task_key·outputs 경로 목록)이 계약과
  맞으면 execute가 산출물 sha256으로 완료 표시를 원자 저장한다. Claude는 명령 실행 도구가 없어 sha256을 직접 계산할 수 없으므로 해시는
  하네스가 붙인다(인계 "계약 충돌" 참조). 실행 전에 완료 표시가 산출물과 맞으면 claude를 다시 부르지 않고 반영만 한다(adopted).
  선언만 있고 완료 표시가 없는 경우(성공 종료를 하네스가 보기 전에 죽음)는 완료로 보지 않는다(fail-closed).
- 새 세션은 `--session-id <uuid>`로 시작해 실행 전에 세션 ID를 저장한다. 실행마다 run_token(uuid)을 상태 파일과 pid 파일에 함께
  적고, pid 파일에는 boot_id·session_id·mode·run_token·pid를 남긴다. status가 running인 채 Supervisor가 죽었으면:
  pid 기록의 session_id·mode·run_token이 job과 같고 pid가 같은 부팅에서 살아 있는 동안 기다리고(겹쳐 실행 안 함), 죽었으면 `--resume`
  (작업당 MAX_INTERRUPTS회까지, 넘으면 대기). 기록이 없거나 맞지 않으면 그 작업만 사람 확인 대기.
- `--resume`이 한도가 아닌 이유로 실패하면 새 세션을 열지 않고 그 작업을 대기시킨다(R4). claude_run.session_unrecoverable이 복원 불가를
  확인한 경우에만 장부 상태를 가리키는 프롬프트로 새 세션을 연다(현재 그 판정은 항상 False: 실제 출력 근거 미확보).
- 한도: resetsAt이 해석되고 지금보다 뒤이며 ratelimit.MAX_RESET_AHEAD_S(8일) 안이면 그 시각에 재개. 8일보다 멀면 미상으로 보고
  알린다(rate_limit_reset_too_far). 모르면(또는 이미 지난 값이면) UNKNOWN_BACKOFF_S(900초, 5시간=five_hour 창, 8일) 간격으로
  최대 MAX_UNKNOWN_RETRIES(3)회 다시 시도하고, 그래도 한도면 exhausted로 멈추고 알림을 남긴다(자동 해제 안 됨). 한계: 주간 한도에서
  재개 시각을 끝내 못 읽으면 마지막 시도까지 약 8일 5시간 늦어질 수 있고, 그 뒤는 사람 확인이다.
- 모델·effort는 route.route(정책 v1)로 정하고 실행마다 route_record와 실행 증거(claude_run_evidence)를 남긴다. 실제 적용 확인(T7)은 주장하지 않는다.
호출 깊이(시작 함수 기준): pick 2, execute 3(run_once → scan → 말단, _record_run → record_decision → append), settle 3(queue.claim·complete).
"""
import functools
import os
import uuid

from . import contract as ct
from . import cas, claude_run, evidence, ledger, lease, manifest, opstate, queue, ratelimit, recovery, route, states
from .jsonio import read_json, write_json

JOBS = os.path.join("supervisor", "claude")  # 작업별 상태 <task_key>.json·<task_key>.pid
UNKNOWN_BACKOFF_S = (900, 5 * 3600, ratelimit.MAX_RESET_AHEAD_S)  # 재시도 횟수 3은 그대로, 간격만 기존 값·창 길이로
MAX_UNKNOWN_RETRIES = len(UNKNOWN_BACKOFF_S)
ACTIVE = ("new", "running", "rate_limited")
HOLD = "blocked"  # 사람 확인 대기(자동으로 다시 고르거나 실행하지 않는다)
_RECORDING_ERRORS = (OSError, ValueError, queue.QueueError, cas.CasError, lease.LeaseError)
_KIND_STATE = {"short": opstate.RATE_LIMITED_SHORT, "weekly": opstate.RATE_LIMITED_WEEKLY}


def paths(root, key):
    """(작업 상태 파일, pid 파일) 경로."""
    base = os.path.join(root, JOBS, ct.check_key(key))
    return base + ".json", base + ".pid"


def pick(root, now):
    """이어갈 작업(작업별 상태가 new|running|rate_limited) 또는 새 작업(의존이 모두 VERIFIED인 PENDING LLM 작업, task_key 순).
    대기(blocked) 작업은 건너뛴다. 이전 Supervisor가 띄운 claude가 아직 살아 있으면(겹쳐 실행 금지) 또는 고를 것이 없으면 None."""
    log, tasks_dir = os.path.join(root, "ledger.jsonl"), os.path.join(root, "tasks")
    active, fresh = None, None
    for key in sorted(os.listdir(tasks_dir)) if os.path.isdir(tasks_dir) else []:
        try:
            info = states.facts(os.path.join(tasks_dir, ct.check_key(key)))
        except ct.ContractError:
            continue
        task = info["contract"]
        if task is None or not task["needs_llm"]:
            continue
        path, pidfile = paths(root, key)
        job, state = read_json(path), states.state_of(info, False)
        if isinstance(job, dict) and job.get("status") in ACTIVE + (HOLD,):
            if state != states.PENDING:  # 큐 쪽에서 이미 끝났거나(VERIFIED) 멈춘 작업
                job.update(status="done" if state == states.VERIFIED else "stale", updated_at=now)
                write_json(path, job)
                ledger.append(log, now, "claude_job_closed", {"task_key": key, "status": job["status"]})
            elif job["status"] == "running":
                held = read_json(pidfile, {})
                held = held if isinstance(held, dict) else {}
                if any(held.get(k) != job.get(k) for k in ("session_id", "mode", "run_token")):
                    job.update(status=HOLD, hold_reason="pid_record_mismatch", updated_at=now)  # 그 세션 claude 생존 불명
                    write_json(path, job)
                    ledger.append(log, now, "claude_job_closed", {"task_key": key, "status": HOLD,
                                                                  "hold_reason": "pid_record_mismatch"})
                    opstate.notify(root, now, "claude_job_blocked", "claude pid 기록이 작업과 맞지 않아 자동 재개하지 않음"
                                   "(사람 확인 필요, 이 작업만): %s" % key, {"task_key": key, "pid_record": held})
                    continue
                pid = held.get("pid")
                if isinstance(pid, int) and held.get("boot_id") == lease.boot_id() and lease.pid_alive(pid):
                    return None  # 이전 Supervisor가 띄운 claude가 아직 실행 중: 겹쳐 실행하지 않는다
                active = active or job
            elif job["status"] != HOLD:
                active = active or job
        elif state == states.PENDING and fresh is None and all(
                states.state_of(states.facts(os.path.join(tasks_dir, d)), False) == states.VERIFIED for d in task["depends_on"]):
            fresh = (key, task["task_type"])
    if active is not None or fresh is None:
        return active
    job = {"task_key": fresh[0], "status": "new", "session_id": None, "unknown_attempts": 0, "crash_resumes": 0,
           "picked_at": now, "updated_at": now}
    write_json(paths(root, fresh[0])[0], job)
    ledger.append(log, now, "claude_job_picked", {"task_key": fresh[0], "task_type": fresh[1]})
    return job


def _prompt(root, job, mode, failed_session=None):
    task_dir = os.path.join(root, "tasks", job["task_key"])
    base = ("하네스 작업 %s를 수행한다.\n계약 파일: %s\n산출물 폴더: %s\n계약의 outputs를 산출물 폴더에 쓴다.\n"
            "규칙(프로젝트 지침이 로드되지 않을 수 있어 여기에 적는다):\n"
            "1. 이 작업 폴더 안의 파일만 읽는다. 계약 입력은 in/ 아래 복사본만 쓴다.\n"
            "2. 쓰기는 산출물 폴더 아래에만 한다. 하네스 상태(장부·작업권·완료 기록·운영 상태·예산)를 고치려 하지 않는다.\n"
            "3. 명령 실행·외부 호출·하위 에이전트·MCP를 쓰지 않는다. 사람 라벨·Gold·봉인 자료를 만들거나 고치지 않는다.\n"
            "4. outputs를 모두 쓴 뒤 맨 마지막에 산출물 폴더의 %s 파일에 JSON {\"task_key\": \"%s\", \"outputs\": [outputs 경로 목록]}을"
            " 쓴다. 그 뒤에는 산출물을 고치지 않는다."
            % (job["task_key"], os.path.join(task_dir, "contract.json"), os.path.join(task_dir, "out"), ct.DECLARATION,
               job["task_key"]))
    if mode == "resume":
        return "사용량 한도 또는 중단으로 멈춘 같은 작업을 이어서 진행한다.\n" + base
    if failed_session:
        return ("이전 세션 %s를 이어받지 못해 새 세션으로 시작한다. 장부 %s와 작업 폴더의 현재 상태에서 이어간다.\n"
                % (failed_session, os.path.join(root, "ledger.jsonl"))) + base
    return base


def _record_run(root, decision, res, job, contract, mode, started, now):
    """한 번의 실행 기록: route_decision(요청·관찰 모델·effort, 제한 사항)과 claude_run_evidence(허용 필드만). 결과(outcome)를 돌려준다."""
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
        "task_key": job["task_key"], "duration_s": now - started,
        "tokens": result.get("usage") if isinstance(result.get("usage"), dict) else None})
    task_dir = os.path.join(root, "tasks", job["task_key"])
    outcome = evidence.outcome_of(task_dir, contract, res)
    ledger.append(os.path.join(root, "ledger.jsonl"), now, "claude_run_evidence", dict(evidence.claude_record(
        res, task_dir if res["argv"] else None, round(now - started, 3), outcome),
        task_key=job["task_key"], mode=mode, run_token=job["run_token"]))
    return outcome


def execute(root, job, claude_bin, now_fn, runner=None, env=None, limits=None):
    """claude를 실행한다. {"kind": success|rate_limited|failed|halted|held|adopted, "mode", "result"}.

    실행 전: 완료 표시가 산출물과 맞으면 실행하지 않고 adopted. 실행 중 사망 뒤(status=running)의 재개는 작업당 recovery.MAX_INTERRUPTS회까지
    (넘으면 held). 재개(--resume)가 한도가 아닌 이유로 실패하면 새 세션을 열지 않고 failed(R4). 성공 종료 + Claude 선언이 맞으면 완료 표시를
    원자 저장한다. limits: {"claude_idle_s", "claude_total_s"}(없으면 claude_run 기본값)."""
    bounds, key = limits or {}, job["task_key"]
    path, log, task_dir = paths(root, key)[0], os.path.join(root, "ledger.jsonl"), os.path.join(root, "tasks", key)
    contract = read_json(os.path.join(task_dir, "contract.json"))
    if states.facts(task_dir)["completion"] == "ok":  # 완료 표시 직후에 죽었다: 다시 실행하지 않고 반영만 한다(R3)
        ledger.append(log, now_fn(), "claude_completion_adopted", {"task_key": key, "session_id": job.get("session_id")})
        return {"kind": "adopted", "mode": None, "result": {}}
    if job["status"] == "running":  # 실행 중 Supervisor가 죽었고 claude도 끝났다(pick이 확인): 재개 횟수 상한
        if job.get("crash_resumes", 0) >= recovery.MAX_INTERRUPTS:
            return {"kind": "held", "mode": None, "result": {"hold_reason": "too_many_interrupts: 실행 중 사망 재개 %d회" %
                                                             job.get("crash_resumes", 0)}}
        job["crash_resumes"] = job.get("crash_resumes", 0) + 1
    decision = route.route(contract, [], route.load_policy())
    decision = route.with_support(decision, route.probe_cli_support(
        run=functools.partial(claude_run.help_text, claude_bin, runner, env)))
    if decision["model"] is None:  # 정책상 LLM 미사용 유형인데 needs_llm=true: 계약 문제이며 실행하지 않는다
        route.record_decision(root, decision, decision["applied"], {"task_key": key})
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
        run = runner or functools.partial(claude_run.default_runner, pidfile=paths(root, key)[1], stamp={
            "boot_id": lease.boot_id(), "session_id": job["session_id"], "mode": mode, "run_token": job["run_token"]},
            idle_s=bounds.get("claude_idle_s", claude_run.IDLE_S), total_s=bounds.get("claude_total_s", claude_run.TOTAL_S))
        ledger.append(log, now_fn(), "claude_run_started", {"task_key": key, "mode": mode,
                      "session_id": job["session_id"], "model": decision["model"], "effort": decision["effort"]})
        started = now_fn()
        res = claude_run.run_once(claude_bin, _prompt(root, job, mode, failed_session), decision["model"],
                                  decision["effort"], run, env, resume=job["session_id"] if mode == "resume" else None,
                                  session_id=job["session_id"] if mode == "new" else None)
        kind = "rate_limited" if res["limited"] else "success" if res["success"] else "failed"
        if _record_run(root, decision, res, job, contract, mode, started, now_fn()) == "completed":
            try:  # 성공 종료를 본 직후 산출물 해시로 완료 표시를 원자 저장한다(이 뒤에 죽어도 반영만 하면 된다)
                write_json(os.path.join(task_dir, ct.COMPLETION),
                           {"task_key": key, "outputs": manifest.build(os.path.join(task_dir, "out"), contract["outputs"])})
            except (OSError, ValueError) as exc:  # 링크·없는 파일: 완료 표시 없음 → settle이 대기시킨다
                res["error"] = "completion_marker_error: %s" % exc
        if kind == "failed" and mode == "resume":
            ledger.append(log, now_fn(), "claude_resume_failed", {"task_key": key, "session_id": job["session_id"],
                          "returncode": res["returncode"], "error": res["error"], "cause": res["cause"]})
            if claude_run.session_unrecoverable(res):  # 복원 불가가 확인된 경우에만 장부 상태로 새 세션(현재 항상 False)
                failed_session = job["session_id"]
                continue
        if res["session_id"] and res["session_id"] != job["session_id"]:
            job["session_id"] = res["session_id"]  # init이 알려준 실제 세션 ID를 따른다
        return {"kind": kind, "mode": mode, "result": res}


def settle(root, job, outcome, now):
    """실행 결과를 상태에 반영한다. 한도면 opstate 조건을 켜고, 끝났으면 큐에 complete/fail, 그 밖은 그 작업만 대기. 새 job 상태 문자열."""
    path, log, key = paths(root, job["task_key"])[0], os.path.join(root, "ledger.jsonl"), job["task_key"]
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
    status, reason, result = HOLD, None, outcome["result"]
    if outcome["kind"] == "held":
        reason = result["hold_reason"]
    elif outcome["kind"] == "failed" and outcome["mode"] is not None:
        # claude 실행 실패: 출력만으로 일시적(네트워크 등)/결정적을 가를 근거가 없다 → FAILED로 만들지 않고 이 작업만 사람 확인 대기
        reason = "claude_failed_cause_%s: %s" % (result.get("cause") or "unknown",
                                                 result.get("error") or "종료 코드 %r" % result.get("returncode"))
    elif outcome["kind"] == "success" and \
            states.facts(os.path.join(root, "tasks", key))["completion"] != "ok":  # 성공 종료만으로는 완료가 아니다
        reason = "completion_marker_missing: %s" % (result.get("error") or "Claude 선언(%s)이 없거나 계약과 다름" % ct.DECLARATION)
    else:
        res = queue.claim(root, key, os.getpid(), lease.boot_id(), now)
        if not res["ok"] and res["reason"] == "skip":  # 이미 VERIFIED: 다시 반영하지 않는다
            status = "done"
        reason = None if res["ok"] or status == "done" else "claim_refused: %s" % res["reason"]
        if res["ok"] and outcome["kind"] in ("success", "adopted"):
            try:
                queue.complete(root, key, res["run_id"], res["lease"], now)
                status = "done"
            except _RECORDING_ERRORS as exc:
                queue.fail(root, key, res["run_id"], res["lease"], "deterministic", "claude 산출물 완료 실패: %s" % exc, now)
                status = "failed"
        elif res["ok"]:  # mode=None: 실행 전 계약 문제(route_no_model)라 결정적 근거가 있다
            queue.fail(root, key, res["run_id"], res["lease"], "deterministic", result["error"], now)
            status = "failed"
    job.update(status=status, updated_at=now, hold_reason=reason)
    write_json(path, job)
    ledger.append(log, now, "claude_job_finished", {"task_key": key, "status": status, "mode": outcome["mode"],
                                                     "hold_reason": reason, "rate_limit": result.get("rate_limit")})
    if status != "done":
        opstate.notify(root, now, "claude_job_" + status, "Claude 작업이 끝나지 않음(%s, 사람 확인 필요, 이 작업만): %s" % (status, key),
                       {"task_key": key, "hold_reason": reason})
    return status
