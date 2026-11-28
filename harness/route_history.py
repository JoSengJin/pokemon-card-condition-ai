"""B5-6: route()에 넘길 이전 실패 이력. 결정론 검사 작업이 기록한 원인만 읽는다(2026-11-28 사용자 조건부 승인, 가안). 읽기 전용이다.

- 기록 주체: task_type이 CHECKER_TYPES이고 needs_llm=false인 작업이 계약 outputs로 선언한 out/route_cause.json(VERDICT). 그 작업이 VERIFIED이고
  **읽은 바이트**의 sha256이 done.json manifest와 같을 때만 읽는다. Claude 작업(needs_llm=true)의 산출물, 그 밖 유형의 산출물, failures/ 기록,
  장부 문구의 cause는 읽지 않는다(모델이 상향 사유를 만들 수 없다).
- 형식(키 정확히 셋): {"target_task_key": 판정한 작업, "cause": null(통과) | 원인 문자열, "ruled_out": 검사기가 원인이 아님을 확인한 것
  (RULED_OUT 중, 중복 없이)}. xhigh_justified 같은 추가 키는 거절한다.
- 귀속: (1) target_task_key는 검사 작업의 depends_on에 있고 VERIFIED여야 한다. (2) 라우팅할 작업은 검사 작업에 depends_on으로 의존한다.
  (3) 대상은 같은 작업의 이전 시도여야 한다: needs_llm=true, 같은 task_type, 대상 inputs가 모두 같은 SHA로 들어 있다. 아니면(검사 결과를 분석하는
  다른 작업·다음 묶음) 이력으로 세지 않는다. 대상의 이전 시도는 대상의 depends_on을 같은 규칙으로 거슬러 간다. 통과 기록에서 끊는다.
- 품질 관문 실패 자체는 상향 조건이 아니다: 정책의 상향 원인(escalate_causes)은 ruled_out이 RULED_OUT 전부(데이터·검사기·판정 기준)일 때만
  넘기고, 아니면 cause=None(원인 분류 없음 → 상향 안 함)으로 넘긴다. 데이터·검사기·판정 기준 문제를 찾은 검사기는 정책의 기존
  no_escalate 원인을 적는다.
- 한 번의 실패한 시도(대상)는 검사기가 여럿이어도 한 번만 센다(두 단계 상향 방지). 그중 하나라도 상향할 수 없는 판정이면 상향하지 않는다.
  한 작업이 서로 다른 이전 시도 둘의 판정에 의존하면 순서를 정할 수 없어 오류다.
- 오류(RouteHistoryError: 의존 계약·검사 기록·대상이 손상·미검증·형식 위반·귀속 위반)면 이력을 비우지 않는다(비우면 낮은 모델로 되돌아가 상향
  횟수가 초기화된다). 호출자는 그 작업만 대기시킨다.
- 상향·중단 규칙은 route_escalate 그대로다. xhigh 필요성·학습 가치 값은 넘기지 않는다(claude_job은 budget_remaining도 주지 않아 Xhigh는 닫힘).
  주의: pending 결정에도 model이 남는다. 호출자 claude_job.execute는 decision["pending"]이면 그 작업만 대기시킨다(VS4).
- CHECKER_TYPES는 dedupe.PLAIN_TYPES에 있어 등록된다(VS4). 판정 파일을 쓰는 검사 executor는 아직 없다: 운영 executor 표에 없으면 이력은 비어 있다.
호출 깊이: history → states.facts → 말단 2(supervisor.run → claude_job.execute → history에서 불러도 4). history → _verdict(말단) 1.
"""
import hashlib
import json
import os

from . import contract as ct
from . import states

CHECKER_TYPES = ("quality_gate", "reverification", "promotion_judge")  # 품질 관문·독립 재검증·승격 판정
VERDICT = "route_cause.json"
RULED_OUT = ("checker", "criteria", "data")  # 상향 원인을 인정하려면 모두 '원인 아님'이어야 한다


class RouteHistoryError(ValueError):
    pass


def _verdict(task_dir):
    """VERIFIED 검사 작업의 판정 기록. done.json manifest와 다른 바이트·형식 위반은 RouteHistoryError."""
    try:
        with open(os.path.join(task_dir, "done.json"), encoding="utf-8") as handle:
            want = json.load(handle)["manifest"][VERDICT]
        with open(os.path.join(task_dir, "out", VERDICT), "rb") as handle:
            data = handle.read()
        body = json.loads(data.decode("utf-8"))
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        raise RouteHistoryError("검사 기록을 읽을 수 없다: %s: %s" % (task_dir, exc))
    if hashlib.sha256(data).hexdigest() != want or not isinstance(body, dict) \
            or set(body) != {"target_task_key", "cause", "ruled_out"} or not isinstance(body["target_task_key"], str) \
            or not (body["cause"] is None or (isinstance(body["cause"], str) and body["cause"])) \
            or not isinstance(body["ruled_out"], list) or not all(v in RULED_OUT for v in body["ruled_out"]) \
            or len(set(body["ruled_out"])) != len(body["ruled_out"]):
        raise RouteHistoryError("검사 기록의 형식이 다르거나 완료 기록과 어긋난다: %s" % task_dir)
    return body


def history(root, task_key, policy):
    """task_key 작업의 이전 실패 이력(오래된 것부터). [{"cause", "target_task_key", "checker_task_keys"}] — route()의 history로 그대로 넘긴다."""
    tasks = os.path.join(root, "tasks")
    current = states.facts(os.path.join(tasks, ct.check_key(task_key)))["contract"]
    if current is None:
        raise RouteHistoryError("작업 계약을 읽을 수 없다: %s" % task_key)
    escalating = policy.get("escalate_causes", []) if isinstance(policy, dict) else []
    found = []
    while True:  # 대상의 계약 해시가 depends_on을 포함하므로 순환할 수 없다
        attempts = {}  # 이전 시도 task_key -> (그 계약, [(검사 작업 key, 판정)])
        for dep in sorted(current["depends_on"]):
            checker_dir = os.path.join(tasks, dep)
            facts = states.facts(checker_dir)
            checker = facts["contract"]
            if checker is None:
                raise RouteHistoryError("의존 작업 계약을 읽을 수 없어 검사 작업인지 알 수 없다: %s" % dep)
            if checker["task_type"] not in CHECKER_TYPES or checker["needs_llm"] or VERDICT not in checker["outputs"]:
                continue  # 결정론 검사기의 원인 기록이 아니다
            if states.state_of(facts, False) != states.VERIFIED:
                raise RouteHistoryError("검사 작업이 VERIFIED가 아니다: %s" % dep)
            record = _verdict(checker_dir)
            key = record["target_task_key"]
            if key not in checker["depends_on"]:
                raise RouteHistoryError("검사 작업이 의존하지 않은 작업을 판정했다: %s → %s" % (dep, key))
            judged = states.facts(os.path.join(tasks, key))
            target = judged["contract"]
            if states.state_of(judged, False) != states.VERIFIED:
                raise RouteHistoryError("판정 대상이 VERIFIED가 아니다: %s" % key)
            if target["needs_llm"] and target["task_type"] == current["task_type"] \
                    and target["inputs"].items() <= current["inputs"].items():
                attempts.setdefault(key, (target, []))[1].append((dep, record))
        if len(attempts) > 1:
            raise RouteHistoryError("서로 다른 이전 시도의 판정에 함께 의존해 순서를 정할 수 없다: %s" % sorted(attempts))
        if not attempts:
            break
        (key, (current, judged_by)), = attempts.items()
        failed = [r for _, r in judged_by if r["cause"] is not None]
        if not failed:
            break  # 이전 시도는 통과했다: 그 앞의 실패는 이어지지 않는다
        # 상향할 수 없는 판정이 하나라도 있으면 상향하지 않는다: 상향 원인이 아닌 것은 이름을 남기고, 확인이 모자란 상향 원인은 지운다
        other = sorted(r["cause"] for r in failed if r["cause"] not in escalating)
        unchecked = any(set(r["ruled_out"]) != set(RULED_OUT) for r in failed)
        cause = other[0] if other else None if unchecked else min(r["cause"] for r in failed)
        found.append({"cause": cause, "target_task_key": key, "checker_task_keys": [dep for dep, _ in judged_by]})
    return found[::-1]
