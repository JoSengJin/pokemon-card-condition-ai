"""모델·Effort 라우팅 `route()`. 정책은 harness/routing_policy.json(판본 포함)에서 읽고 코드는 정책 값을 갖지 않는다.

정책이 없거나 구조가 틀리거나 표에 없는 task_type이면 추정하지 않고 고정 기본값(Sonnet Medium)과 policy="none"을 쓴다.
"""
import os

from .jsonio import read_json
from .route_escalate import context_for_escalation, escalate  # noqa: F401 (공개 진입점으로 다시 내보냄)
from .route_record import record_decision  # noqa: F401
from .route_support import probe_cli_support, with_support  # noqa: F401

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routing_policy.json")
FALLBACK = {"model": "sonnet", "effort": "medium"}  # 정책 없음일 때만(설계의 최소 모델 원칙)


def load_policy(path=POLICY_PATH):
    """정책 dict. 파일이 없으면 None(→ policy=none). 내용이 깨졌으면 ValueError(추정하지 않는다)."""
    return read_json(path, None)


def _step(obj):
    return isinstance(obj, dict) and isinstance(obj.get("model"), str) and isinstance(obj.get("effort"), str)


def _valid(policy):
    """구조가 갖춰졌는지(판본·표·상향 순서·기본값·원인 목록). 틀리면 정책 없음으로 취급한다."""
    if not isinstance(policy, dict) or not isinstance(policy.get("version"), str):
        return False
    rows, order = policy.get("task_types"), policy.get("escalation_order")
    causes = (policy.get("escalate_causes"), policy.get("no_escalate_causes"))
    if not isinstance(rows, dict) or not isinstance(order, list) or not _step(policy.get("default")):
        return False
    if not all(isinstance(c, list) for c in causes) or not all(_step(s) for s in order):
        return False
    xhigh = policy.get("xhigh")
    return (xhigh is None or _step(xhigh)) and all(
        _step(r) or (isinstance(r, dict) and r.get("llm") is False) for r in rows.values())


def _choose(contract, policy, ok):
    """(모델, effort, 적용한 정책 표시, 사유). 모델이 없으면 (None, None, ...)."""
    row = policy["task_types"].get(contract["task_type"]) if ok else None
    if row is None:
        row = policy["default"] if ok else FALLBACK
        return row["model"], row["effort"], "none", "정책 없음/표에 없는 task_type: 기본값 사용(policy=none)"
    if row.get("llm") is False:
        return None, None, policy["version"], "정책상 LLM 미사용 유형(모델 호출 금지)"
    return row["model"], row["effort"], policy["version"], "정책 표 조회"


def _base(contract, policy, runtime, ok):
    model, effort, marker, why = _choose(contract, policy, ok)
    if not contract["needs_llm"]:
        model, effort, why = None, None, "needs_llm=false: 모델 호출 금지"
    order = [dict(s) for s in policy["escalation_order"]] if ok else []
    step = {"model": model, "effort": effort}
    runtime = runtime or {}
    return {
        "task_type": contract["task_type"], "needs_llm": model is not None,
        "needs_vision": contract.get("needs_vision"), "risk": contract.get("risk"),
        "contract_escalation_level": contract.get("escalation_level"),
        "context_size": runtime.get("context_size"), "budget_remaining": runtime.get("budget_remaining"),
        "model": model, "effort": effort, "reason": why, "policy": marker,
        "policy_version": policy["version"] if ok else None,
        "escalation_order": order, "xhigh": dict(policy["xhigh"]) if ok and policy.get("xhigh") else None,
        "escalate_causes": list(policy["escalate_causes"]) if ok else [],
        "no_escalate_causes": list(policy["no_escalate_causes"]) if ok else [],
        "level": order.index(step) if model is not None and step in order else None,
        "xhigh_used": False, "escalations": [], "escalated": False, "pending": False, "request_user": False,
    }


def route(contract, history, policy, runtime=None):
    """작업 계약 → 결정 dict. history(이전 실패 결과 목록)는 escalate()와 같은 규칙으로 재적용해 재시작 뒤에도 같은 결과를 낸다."""
    if not isinstance(contract, dict) or not isinstance(contract.get("task_type"), str) \
            or not isinstance(contract.get("needs_llm"), bool):
        raise ValueError("계약에 task_type(문자열)·needs_llm(bool)이 있어야 한다")
    decision = _base(contract, policy, runtime, _valid(policy))
    for failure in history or []:
        extra = failure if isinstance(failure, dict) else {}
        decision = escalate(decision, failure, xhigh_justified=extra.get("xhigh_justified") is True,
                            budget_remaining=decision["budget_remaining"],
                            learning_value_high=extra.get("learning_value_high") is True)
    return decision
