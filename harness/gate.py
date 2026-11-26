"""승격 관문: 레지스트리 상태를 읽어 승격을 거절할 사유를 찾는다(쓰기 없음).

"개선되었는가"는 판정하지 않는다(6단계 몫). 여기서는 구조 조건만 본다:
유효성(자신과 조상), 가중치 CAS 보관, 같은 층·분모·봉인 판본, 봉인 층, 계보 전체의 Silver 감사 완료.
"""
import os

from harness import cas

SAME = ("layer", "denominator", "seal_version")
AUDIT_OK = ("complete", "not_required")


def ancestors(models, model_id):
    """자신부터 부모 사슬을 따라 올라간 모델 ID 목록(순환이 있어도 끝난다)."""
    chain, cursor = [], model_id
    while cursor is not None and cursor not in chain:
        chain.append(cursor)
        cursor = models[cursor].get("parent")
    return chain


def audit_reason(models, chain, audit_status):
    """계보 전체가 쓴 Silver 묶음의 감사 상태. 실패가 하나라도 있으면 audit_failed, 완료·불필요가 아니면(누락 포함) audit_pending."""
    batches = sorted({b for m in chain for b in models[m]["silver_batches"]})
    seen = {b: audit_status.get(b) for b in batches}
    if any(s == "failed" for s in seen.values()):
        return "audit_failed", {b: s for b, s in seen.items() if s == "failed"}
    waiting = {b: s for b, s in seen.items() if s not in AUDIT_OK}
    return ("audit_pending", waiting) if waiting else (None, None)


def check(root, state, model_id, champion, audit_status):
    """승격 거절 사유 {reason, detail}, 통과하면 None. champion은 champion.current()의 결과 또는 None."""
    models = state["models"]
    if model_id not in models:
        return {"reason": "unknown_model", "detail": model_id}
    chain = ancestors(models, model_id)
    bad = [m for m in chain if models[m]["status"] != "valid"]
    if bad:
        return {"reason": "invalidated", "detail": bad}
    if not cas.has(os.path.join(root, "cas"), models[model_id]["weights_sha"]):
        return {"reason": "weights_missing", "detail": models[model_id]["weights_sha"]}
    evaluation = models[model_id]["eval"]
    if champion is not None:
        base = models[champion["model_id"]]["eval"]
        differing = [k for k in SAME if evaluation[k] != base[k]]
        if differing:
            return {"reason": "not_comparable", "detail": differing}
    if evaluation["layer"] != "sealed":
        return {"reason": "not_sealed", "detail": evaluation["layer"]}
    reason, detail = audit_reason(models, chain, audit_status)
    return {"reason": reason, "detail": detail} if reason else None
