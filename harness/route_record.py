"""라우팅 결정을 1단계 장부(ledger.jsonl)에 남긴다(정책 판본·요청값·실제 적용값·상향 이유·사용량·품질 관문·재작업)."""
import os
import time

from . import ledger

_EXTRAS = ("task_key", "tokens", "duration_s", "quality_gate", "rework")


def record_decision(root, decision, applied, extras=None):
    """route_decision 이벤트를 추가한다. extras에 없는 항목은 null로 명시한다. 알 수 없는 extras 키는 오타 방지로 거절한다."""
    extras = dict(extras or {})
    ts = extras.pop("ts", None)
    unknown = sorted(set(extras) - set(_EXTRAS))
    if unknown:
        raise ValueError("알 수 없는 extras 키: %s" % unknown)
    data = {
        "policy": decision["policy"], "policy_version": decision["policy_version"],
        "task_type": decision["task_type"], "needs_llm": decision["needs_llm"],
        "requested": {"model": decision["model"], "effort": decision["effort"]},
        "applied": applied, "limitations": decision.get("limitations"),
        "escalations": list(decision.get("escalations", [])), "reason": decision["reason"],
        "pending": decision.get("pending"),
    }
    data.update({k: extras.get(k) for k in _EXTRAS})
    return ledger.append(os.path.join(root, "ledger.jsonl"), time.time() if ts is None else ts,
                         "route_decision", data)
