"""작업 폴더와 Claude 작업 칸의 상태 수집(B6-1). 읽기만 한다: CAS 복구(cas.restore)·claim·recover를 부르지 않는다.

항목 하나를 읽지 못해도 그 항목만 오류로 남기고 계속한다. 호출 깊이: scan → states.facts·lease.is_alive → 말단 2
(status.collect에서 부르면 3, control.main부터 4). 깊이를 늘리지 않으려고 states.classify 대신 facts·state_of를 직접 부른다.
"""
import os

from . import claude_job, lease, states
from . import contract as ct
from .jsonio import read_json


def scan(root):
    """{"tasks": {counts, stopped, awaiting, bad_contract, errors}, "claude_jobs": [done이 아닌 작업 칸], "unknown_limit"}."""
    counts, stopped, awaiting, bad, errors = {}, [], [], [], {}
    tasks_dir = os.path.join(root, "tasks")
    try:
        names = sorted(os.listdir(tasks_dir))
    except FileNotFoundError:
        names = []
    except OSError as exc:
        names, errors["tasks"] = [], "%s: %s" % (type(exc).__name__, exc)
    for key in names:
        try:
            info = states.facts(os.path.join(tasks_dir, ct.check_key(key)))
            state = states.state_of(info, info["held"] is not None and lease.is_alive(info["held"]))
        except ct.ContractError:
            continue  # 작업 폴더가 아닌 항목(runner와 같은 규칙)
        except Exception as exc:  # noqa: BLE001 — 조회는 한 작업의 문제로 전체 요약을 잃지 않는다
            errors[key] = "%s: %s" % (type(exc).__name__, exc)
            continue
        counts[state] = counts.get(state, 0) + 1
        if info["contract_state"] == "bad":
            bad.append(key)
        for name, found in (("stopped", stopped), ("awaiting", awaiting)):
            if info[name] is not None:
                found.append({"task_key": key, "detail": info[name]})
    jobs = []
    try:
        names = sorted(os.listdir(os.path.join(root, claude_job.JOBS)))
    except FileNotFoundError:
        names = []
    except OSError as exc:
        names, errors["claude_jobs"] = [], "%s: %s" % (type(exc).__name__, exc)
    for name in [n for n in names if n.endswith(".json")]:
        try:
            job = read_json(os.path.join(root, claude_job.JOBS, name))
        except (OSError, ValueError):
            job = None
        if not isinstance(job, dict) or job.get("status") not in claude_job.KNOWN:
            job = {"status": "unreadable"}  # 형식이 다른 상태 파일: Supervisor도 자동으로 고르지 않는다
        if job["status"] != "done":
            jobs.append({"task_key": name[:-len(".json")], "status": job["status"], "hold_reason": job.get("hold_reason"),
                         "crash_resumes": job.get("crash_resumes")})
    try:
        seen = read_json(os.path.join(root, claude_job.UNKNOWN_LIMIT))
        if seen is not None and (type(seen["attempts"]) is not int or seen["attempts"] < 0):
            raise ValueError("attempts")
        limit = None if seen is None else {"attempts": seen["attempts"], "max": claude_job.MAX_UNKNOWN_RETRIES}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        limit = {"error": "시각 미상 한도 횟수 기록을 읽지 못함(%s). Supervisor는 소진으로 본다" % type(exc).__name__}
    return {"tasks": {"counts": counts, "stopped": stopped, "awaiting": awaiting, "bad_contract": bad, "errors": errors},
            "claude_jobs": jobs, "unknown_limit": limit}
