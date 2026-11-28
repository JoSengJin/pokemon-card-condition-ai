"""Claude 작업(Supervisor가 한 번에 하나만 돌리는 needs_llm=true 작업): 고르기(pick) → 실행(execute) → 결과 반영(settle).

작업별 상태 파일 root/supervisor/claude/<task_key>.json(작업 계약 2단계 R5: 한 칸 구조를 작업별로 바꿨다): {task_key, status(new|running|
rate_limited|done|failed|blocked|stale), session_id, crash_resumes, mode, run_token, hold_reason, ...}와
같은 폴더의 <task_key>.pid. Supervisor가 죽었다 다시 시작해도 이 파일들과 opstate.json만으로 이어간다.
- 큐 작업은 Claude가 일하는 동안 PENDING으로 둔다(한도로 기다리는 동안 작업권을 쥐거나 실패로 세지 않게). Claude가 끝나면 settle이
  claim → complete(완료 표시·산출물 manifest 검증)로 큐에 반영한다. 결정적 근거가 있는 실패(정책상 모델 없음, 산출물 완료 실패)만 fail(deterministic).
  Supervisor는 root마다 하나만 돈다(supervisor.lock)는 것이 전제다.
- 사람 확인 대기(status=blocked, hold_reason)는 그 작업(과 그것에 의존하는 작업)만 멈춘다. pick은 대기 작업을 건너뛰고 다른 독립 작업을
  고른다. 공통 장애 근거(현재는 한도 이벤트 → opstate 한도 조건)만 Claude 실행 전체를 멈춘다. 대기 사유: claude 실패(원인 필드 포함),
  pid 기록 불일치, 결과 반영 claim 거절, 완료 표시 없음, 선언 자리가 폴더 등(G11), 자동 재개 한도(recovery.MAX_INTERRUPTS=2) 초과, 상태 파일
  형식이 다름(job_state_invalid: 깨진 JSON·dict 아님·KNOWN 밖 status, 3차 결함 H6, 새 작업으로 보지 않는다), 내용이 모순(4차 결함 I6: 큐가
  PENDING인데 status done·failed·stale, status new인데 crash_resumes가 정수 0이 아니거나 session_id가 있음). 알림(claude_job_blocked)을
  남기며 자동 재시도하지 않는다. 사람 해제는 한 가지뿐이다: 사람이 확인한 뒤 그 작업의 상태 파일을 지우면(새 세션으로 다시 고름) 이어간다
  (status를 new·done·failed·stale로 고쳐 쓰는 것은 해제가 아니다: 위 모순 규칙에 걸려 다시 대기한다). 기존 규칙 그대로, status를
  rate_limited로 고치는 같은 세션 --resume은 그 유형의 자동 재개가 켜져 있을 때만 되고(claude_perm.AUTO_RESUME, 3단계, 지금 빈 목록이라
  대기) crash_resumes 상한을 그대로 따른다. 큐 작업이 PENDING이 아니게 되면 닫는다(VERIFIED면 done, 그 밖은 stale).
- 완료 표시(contract.COMPLETION): claude가 성공 종료하고 Claude의 선언(out/ 안 contract.DECLARATION: task_key·run_token·outputs 경로 목록)이
  이번 실행의 run_token·계약과 맞으면 execute가 산출물 sha256으로 완료 표시를 원자 저장한다. 실행(재개·새 세션 포함) 직전마다 이전 선언을
  지우고 프롬프트에 이번 run_token을 준다(검증 결함 F4: 낡은 선언 + 성공 종료로 반쯤 쓴 산출물이 완료되지 않게). Claude는 명령 실행 도구가 없어 sha256을 직접 계산할 수 없으므로 해시는
  하네스가 붙인다(인계 "계약 충돌" 참조). 실행 전에 완료 표시가 산출물과 맞으면 claude를 다시 부르지 않고 반영만 한다(adopted).
  선언만 있고 완료 표시가 없는 경우(성공 종료를 하네스가 보기 전에 죽음)는 완료로 보지 않는다(fail-closed).
- 새 세션은 `--session-id <uuid>`로 시작해 실행 전에 세션 ID를 저장한다. 실행마다 run_token(uuid)을 상태 파일과 pid 파일에 함께
  적고, pid 파일에는 boot_id·session_id·mode·run_token·pid를 남긴다. status가 running인 채 Supervisor가 죽었으면:
  pid 기록의 session_id·mode·run_token이 job과 같고 pid가 같은 부팅에서 살아 있는 동안 기다리고(겹쳐 실행 안 함), 죽었으면 `--resume`
  (작업당 MAX_INTERRUPTS회까지, 넘으면 대기). 기록이 없거나 맞지 않으면 그 작업만 사람 확인 대기.
- 자동 재개 상한(2차 결함 G3): 한 작업의 모든 자동 재개(한도 해제 뒤 --resume, 실행 중 사망 뒤 --resume, 복원 불가 확인 뒤 새 세션)를 합쳐
  crash_resumes(필드 이름은 그대로, 뜻은 자동 재개 합계)로 세고 recovery.MAX_INTERRUPTS(2)회를 넘기면 그 작업만 대기(too_many_interrupts)한다.
  새 횟수를 만들지 않았다(승인 원문: 자동 재개로 생기는 중복 사용은 기존 재시도 상한 2회 안). 시각 미상 한도의 전체 3회 상한은 따로 센다.
  crash_resumes가 없음·null·정수 아님·음수면 상한에 닿은 것으로 본다(3차 결함 H6·S30).
- `--resume`이 한도가 아닌 이유로 실패하면 새 세션을 열지 않고 그 작업을 대기시킨다(R4). claude_run.session_unrecoverable이 복원 불가를
  확인한 경우(실환경에서 확보한 '없는 세션' 출력과 정확히 같은 형식)에만 장부 상태를 가리키는 프롬프트로 새 세션을 한 번 연다. 새 세션도
  같은 execute 안이라 재개 상한(crash_resumes)·실행 직전 정지 확인·선언 삭제·완료 표시 검사를 그대로 따른다.
- 한도: resetsAt이 해석되고 지금보다 뒤이며 ratelimit.MAX_RESET_AHEAD_S(8일) 안이면 그 시각에 재개. 8일보다 멀면 미상으로 보고
  알린다(rate_limit_reset_too_far). 모르면(또는 이미 지난 값이면) UNKNOWN_BACKOFF_S(900초, 5시간=five_hour 창, 8일) 간격으로
  최대 MAX_UNKNOWN_RETRIES(3)회 다시 시도하고, 그래도 한도면 exhausted로 멈추고 알림을 남긴다(자동 해제 안 됨). 시도 횟수는 작업이 아니라
  전체(UNKNOWN_LIMIT 파일)에서 센다: 다시 시도가 다른 독립 작업의 실행이어도 이어 세고, claude 실행이 성공하면 0으로 되돌린다(검증 결함 F5).
  시각을 아는 한도는 횟수를 바꾸지 않는다. 한계: 주간 한도에서 재개 시각을 끝내 못 읽으면 마지막 시도까지 약 8일 5시간 늦어질 수 있고,
  그 뒤는 사람 확인이다. 자동 재개가 꺼진 유형은 한도에 부딪힌 작업이 대기로 바뀌고 다음 시도는 다른 독립 작업이 쓴다(최대 4개 작업).
  횟수 기록이 깨졌거나(JSON 오류) 값이 이상하면 소진으로 본다(2차 결함 G9). 횟수는 claude 실행이 성공해야만 0이 된다: 사람이 소진 조건을
  풀어도 기록은 3으로 남아 다음 시각 미상 한도는 다시 시도 없이 바로 소진된다(의도된 보수적 동작. 다시 세려면 사람이 기록 파일을 지운다).
- 모델·effort는 route.route(정책 v1)에 이전 실패 이력(route_history.history, VS4)을 넣어 정하고, 이력 오류(RouteHistoryError)·pending 결정은
  그 작업만 대기시킨다(route_history_invalid·route_pending). 실행마다 route_record와 실행 증거(claude_run_evidence)를 남긴다. 실제 적용 확인(T7)은 주장하지 않는다.
호출 깊이(시작 함수 기준): pick 2, execute 3(run_once → scan → 말단, _record_run → record_decision → append, history → facts → 말단),
settle 3(queue.claim·complete).
"""
import functools
import os
import uuid

from . import contract as ct
from . import cas, claude_perm, claude_run, evidence, ledger, lease, manifest, opstate, queue, ratelimit, recovery, route, route_history
from . import states
from .jsonio import read_json, write_json

JOBS = os.path.join("supervisor", "claude")  # 작업별 상태 <task_key>.json·<task_key>.pid
UNKNOWN_BACKOFF_S = (900, 5 * 3600, ratelimit.MAX_RESET_AHEAD_S)  # 재시도 횟수 3은 그대로, 간격만 기존 값·창 길이로
UNKNOWN_LIMIT = os.path.join("supervisor", "claude_unknown_limit.json")  # 시각 미상 한도의 전체 시도 횟수 {"attempts"}
MAX_UNKNOWN_RETRIES = len(UNKNOWN_BACKOFF_S)
ACTIVE = ("new", "running", "rate_limited")
HOLD = "blocked"  # 사람 확인 대기(자동으로 다시 고르거나 실행하지 않는다)
KNOWN = ACTIVE + (HOLD, "done", "failed", "stale")  # 작업 상태 파일 status의 전부(그 밖은 형식이 다른 파일, 3차 결함 H6)
_RECORDING_ERRORS = (OSError, ValueError, queue.QueueError, cas.CasError, lease.LeaseError)
_KIND_STATE = {"short": opstate.RATE_LIMITED_SHORT, "weekly": opstate.RATE_LIMITED_WEEKLY}
_CAP = "too_many_interrupts: 자동 재개 %r회(한도 뒤 재개·실행 중 사망 뒤 재개·복원 불가 뒤 새 세션 합계, 상한 recovery.MAX_INTERRUPTS)"


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
        state = states.state_of(info, False)
        try:
            job = read_json(path)
        except ValueError:  # 깨진 JSON: 아래에서 형식이 다른 상태 파일로 다룬다
            job = ValueError
        odd = isinstance(job, dict) and state == states.PENDING and (job.get("status") in ("done", "failed", "stale") or (
            job.get("status") == "new" and (type(job.get("crash_resumes")) is not int or job["crash_resumes"] != 0
                                            or job.get("session_id") is not None)))  # 4차 결함 I6: 정상 흐름에서 생기지 않는 모순
        if odd or (job is not None and not (isinstance(job, dict) and job.get("status") in KNOWN)):
            if state == states.PENDING:  # 새 작업으로 보지 않는다(재개 상한 근거가 사라진 파일, 3차 H6): 그 작업만 대기 + 알림 한 번
                seen = "깨진 JSON" if job is ValueError else repr(job)[:200]
                write_json(path, {"task_key": key, "status": HOLD, "hold_reason": "job_state_invalid: %s" % seen, "updated_at": now})
                ledger.append(log, now, "claude_job_closed", {"task_key": key, "status": HOLD, "hold_reason": "job_state_invalid"})
                opstate.notify(root, now, "claude_job_blocked", "Claude 작업 상태 파일의 형식이 달라 자동으로 고르지 않음(사람 확인 필요, "
                               "이 작업만): %s" % key, {"task_key": key, "job_state": seen})
            continue
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
    job = {"task_key": fresh[0], "status": "new", "session_id": None, "crash_resumes": 0,
           "picked_at": now, "updated_at": now}
    write_json(paths(root, fresh[0])[0], job)
    ledger.append(log, now, "claude_job_picked", {"task_key": fresh[0], "task_type": fresh[1]})
    return job


def _prompt(root, job, mode, failed_session=None):
    task_dir = os.path.join(root, "tasks", job["task_key"])
    base = ("하네스 작업 %s를 수행한다.\n실행 토큰: %s\n계약 파일: %s\n산출물 폴더: %s\n계약의 outputs를 산출물 폴더에 쓴다.\n"
            "규칙(프로젝트 지침이 로드되지 않을 수 있어 여기에 적는다):\n"
            "1. 이 작업 폴더 안의 파일만 읽는다. 계약 입력은 in/ 아래 복사본만 쓴다.\n"
            "2. 쓰기는 산출물 폴더 아래에만 한다. 하네스 상태(장부·작업권·완료 기록·운영 상태·예산)를 고치려 하지 않는다.\n"
            "3. 명령 실행·외부 호출·하위 에이전트·MCP를 쓰지 않는다. 사람 라벨·Gold·봉인 자료를 만들거나 고치지 않는다.\n"
            "4. outputs를 모두 쓴 뒤 맨 마지막에 산출물 폴더의 %s 파일에 JSON {\"task_key\": \"%s\", \"run_token\": \"%s\","
            " \"outputs\": [outputs 경로 목록]}을 쓴다. 그 뒤에는 산출물을 고치지 않는다."
            % (job["task_key"], job["run_token"], os.path.join(task_dir, "contract.json"), os.path.join(task_dir, "out"),
               ct.DECLARATION, job["task_key"], job["run_token"]))
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
    outcome = evidence.outcome_of(task_dir, contract, res, job["run_token"])
    ledger.append(os.path.join(root, "ledger.jsonl"), now, "claude_run_evidence", dict(evidence.claude_record(
        res, task_dir if res["argv"] else None, round(now - started, 3), outcome),
        task_key=job["task_key"], mode=mode, run_token=job["run_token"]))
    return outcome


def execute(root, job, claude_bin, now_fn, runner=None, env=None, limits=None, source_root=None):
    """claude를 실행한다. {"kind": success|rate_limited|failed|halted|held|adopted, "mode", "result"}.

    실행 전: 완료 표시가 산출물과 맞으면 실행하지 않고 adopted. 권한 묶음이 실행 가능(claude_perm.RUNNABLE)하지 않은 유형, 자동 재개가 꺼진
    유형의 재개(첫 실행이 아닌 실행), 실행 중 사망 뒤 재개 recovery.MAX_INTERRUPTS회 초과는 held. 계약 입력은 source_root(기본 저장소)에서
    SHA를 확인해 작업 폴더 in/으로 복사하고(거절되면 결정적 실패), 작업 폴더를 cwd로, 허용 env만 넘겨 A 옵션으로 실행한다.
    재개(--resume)가 한도가 아닌 이유로 실패하면 새 세션을 열지 않고 failed(R4). 성공 종료 + Claude 선언이 맞으면 완료 표시를 원자 저장한다.
    limits: {"claude_idle_s", "claude_total_s"}(없으면 claude_run 기본값)."""
    bounds, key = limits or {}, job["task_key"]
    path, log, task_dir = paths(root, key)[0], os.path.join(root, "ledger.jsonl"), os.path.join(root, "tasks", key)
    contract = read_json(os.path.join(task_dir, "contract.json"))
    if states.facts(task_dir)["completion"] == "ok":  # 완료 표시 직후에 죽었다: 다시 실행하지 않고 반영만 한다(R3)
        ledger.append(log, now_fn(), "claude_completion_adopted", {"task_key": key, "session_id": job.get("session_id")})
        return {"kind": "adopted", "mode": None, "result": {}}
    extra = claude_perm.options(contract["task_type"])
    if extra is None:  # B·C·미정의 유형: 필요한 통제가 없어 제한 없이 실행하지 않는다(이 작업만 대기)
        return {"kind": "held", "mode": None, "result": {"hold_reason": "no_runnable_permission_bundle: %s(%s)" % (
            contract["task_type"], claude_perm.BUNDLE_OF.get(contract["task_type"], "묶음 없음"))}}
    if job["status"] != "new" and not claude_perm.auto_resume_allowed(contract["task_type"]):
        return {"kind": "held", "mode": None, "result": {"hold_reason": "auto_resume_disabled: %s(%s 뒤 재개는 사람 확인)" % (
            contract["task_type"], job["status"])}}
    if job["status"] != "new":  # 자동 재개(한도 해제 뒤·실행 중 사망 뒤): 복원 불가 뒤 새 세션까지 합쳐 작업당 MAX_INTERRUPTS회(2차 G3)
        used = job.get("crash_resumes")  # 없음·null·정수 아님·음수는 넘은 것으로 본다(보수적, 3차 결함 H6·S30)
        if type(used) is not int or used < 0 or used >= recovery.MAX_INTERRUPTS:
            return {"kind": "held", "mode": None, "result": {"hold_reason": _CAP % used}}
        job["crash_resumes"] = used + 1
    env = claude_perm.env_of(env if env is not None else os.environ)  # --help 확인에도 같은 허용 env만 넘긴다
    policy = route.load_policy()
    try:  # 이전 실패 이력(B5-6, 결정론 검사 작업의 기록). 손상·귀속 위반이면 이력을 비우지 않고(낮은 모델로 되돌아간다) 이 작업만 대기
        history = route_history.history(root, key, policy)
    except route_history.RouteHistoryError as exc:
        return {"kind": "held", "mode": None, "result": {"hold_reason": "route_history_invalid: %s" % exc}}
    decision = route.route(contract, history, policy)
    if decision["pending"]:  # 정책의 중단: pending 결정에도 model(최상위)이 남으므로 여기서 멈춰야 반복 실행이 없다
        route.record_decision(root, decision, None, {"task_key": key})  # 실행하지 않았으므로 applied는 null
        return {"kind": "held", "mode": None, "result": {"hold_reason": "route_pending: %s" % decision["reason"]}}
    decision = route.with_support(decision, route.probe_cli_support(
        run=functools.partial(claude_run.help_text, claude_bin, runner, env)))
    if decision["model"] is None:  # 정책상 LLM 미사용 유형인데 needs_llm=true: 계약 문제이며 실행하지 않는다
        route.record_decision(root, decision, decision["applied"], {"task_key": key})
        return {"kind": "failed", "mode": None, "result": {"error": "route_no_model: %s" % decision["reason"]}}
    try:
        claude_perm.stage_inputs(task_dir, contract, source_root or claude_perm.REPO, root)
    except (OSError, ValueError) as exc:  # 계약 입력이 허용 범위 밖이거나 SHA가 다르다: 결정적(계약·자료 문제)
        return {"kind": "failed", "mode": None, "result": {"error": "input_refused: %s" % exc}}
    failed_session = None
    for mode in (("resume", "new") if job.get("session_id") and job["status"] != "new" else ("new",)):
        # 실행 직전마다 다시 본다: 실패한 --resume 실행 중에 건 정지 뒤에는 새 세션을 열지 않는다
        if opstate.effective(opstate.load(root)) in opstate.HALTING:
            return {"kind": "halted", "mode": mode, "result": {}}
        try:  # 이전 실행의 완료 선언을 지운다: 성공 종료 뒤 남은 선언은 이번 실행이 쓴 것뿐이다(F4)
            os.remove(os.path.join(task_dir, "out", ct.DECLARATION))
        except FileNotFoundError:
            pass
        except OSError as exc:  # 선언 자리가 폴더 등(Claude가 그 아래에 썼다): 이 작업만 대기(2차 결함 G11, 전체 정지 아님)
            return {"kind": "held", "mode": mode, "result": {"hold_reason": "declaration_path_invalid: %s" % exc}}
        if mode == "new":
            job["session_id"] = str(uuid.uuid4())
        job.update(status="running", mode=mode, run_token=uuid.uuid4().hex, updated_at=now_fn())
        write_json(path, job)  # 실행 전에 세션 ID를 남긴다(실행 중 Supervisor가 죽어도 이어갈 수 있게)
        run = runner or functools.partial(claude_run.default_runner, pidfile=paths(root, key)[1], stamp={
            "boot_id": lease.boot_id(), "session_id": job["session_id"], "mode": mode, "run_token": job["run_token"]},
            cwd=task_dir, idle_s=bounds.get("claude_idle_s", claude_run.IDLE_S), total_s=bounds.get("claude_total_s", claude_run.TOTAL_S))
        ledger.append(log, now_fn(), "claude_run_started", {"task_key": key, "mode": mode,
                      "session_id": job["session_id"], "model": decision["model"], "effort": decision["effort"]})
        started = now_fn()
        res = claude_run.run_once(claude_bin, _prompt(root, job, mode, failed_session), decision["model"],
                                  decision["effort"], run, env, resume=job["session_id"] if mode == "resume" else None,
                                  session_id=job["session_id"] if mode == "new" else None, extra=extra)
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
            if claude_run.session_unrecoverable(res, job["session_id"]):  # 복원 불가가 확인된 경우에만 장부 상태로 새 세션
                if job["crash_resumes"] >= recovery.MAX_INTERRUPTS:  # 새 세션도 자동 재개 횟수에 넣는다(2차 G3: 새 횟수를 만들지 않는다)
                    return {"kind": "held", "mode": mode, "result": {"hold_reason": _CAP % job["crash_resumes"]}}
                job["crash_resumes"] += 1
                failed_session = job["session_id"]
                continue
        if res["session_id"] and res["session_id"] != job["session_id"]:
            job["session_id"] = res["session_id"]  # init이 알려준 실제 세션 ID를 따른다
        return {"kind": kind, "mode": mode, "result": res}


def settle(root, job, outcome, now):
    """실행 결과를 상태에 반영한다. 한도면 opstate 조건을 켜고, 끝났으면 큐에 complete/fail, 그 밖은 그 작업만 대기. 새 job 상태 문자열."""
    path, log, key = paths(root, job["task_key"])[0], os.path.join(root, "ledger.jsonl"), job["task_key"]
    counter = os.path.join(root, UNKNOWN_LIMIT)
    if outcome["kind"] == "halted":  # job·큐를 그대로 둔다: 사용자가 정지를 풀면 같은 상태에서 이어간다
        return "halted"
    if outcome["kind"] == "success" and os.path.exists(counter):  # 성공한 실행: 시각 미상 시도 횟수를 0으로
        write_json(counter, {"attempts": 0, "updated_at": now, "task_key": key})
    if outcome["kind"] == "rate_limited":
        limit = outcome["result"]["rate_limit"]
        far = limit["resets_at"] is not None and limit["resets_at"] > now + ratelimit.MAX_RESET_AHEAD_S
        when = limit["resets_at"] if limit["resets_at"] is not None and limit["resets_at"] > now and not far else None
        try:
            seen = read_json(counter, {"attempts": 0})  # 파일이 없으면 0회
        except ValueError:  # 깨진 기록은 소진으로 본다(Claude 실행만 멈춘다. 전체 INTEGRITY_HALT가 아니다, 2차 결함 G9)
            seen = None
        tries = seen.get("attempts") if isinstance(seen, dict) else None
        tries = tries if type(tries) is int and tries >= 0 else MAX_UNKNOWN_RETRIES  # 기록이 이상하면 소진으로 본다(보수적)
        exhausted = when is None and tries >= MAX_UNKNOWN_RETRIES
        next_try = when if when is not None else (None if exhausted else now + UNKNOWN_BACKOFF_S[tries])
        if when is None and not exhausted:  # 전체 기준으로 이어 센다(작업이 바뀌어도 초기화하지 않는다)
            write_json(counter, {"attempts": tries + 1, "updated_at": now, "task_key": key})
        job.update(status="rate_limited", updated_at=now)
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
