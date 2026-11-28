"""승격 관문의 구조 조건: 레지스트리 상태만 읽어 승격을 거절할 사유를 찾는다(쓰기 없음).

"개선되었는가"는 판정하지 않는다(6단계 몫). 여기서는 가중치 CAS 보관, 같은 층·분모·봉인 판본, 봉인 층만 본다.
유효성·Silver 감사·정책 철회 보류·학습 manifest는 `eligibility.model_reason`이 장부에서 직접 판정한다(호출자가 준 감사 상태는 받지 않는다).
"""
import os

from harness import cas

SAME = ("layer", "denominator", "seal_version")


def ancestors(models, model_id):
    """자신부터 부모 사슬을 따라 올라간 모델 ID 목록(순환이 있어도 끝난다)."""
    chain, cursor = [], model_id
    while cursor is not None and cursor not in chain:
        chain.append(cursor)
        cursor = models[cursor].get("parent")
    return chain


def check(root, state, model_id, champion):
    """구조 거절 사유 {reason, detail}, 통과하면 None. model_id는 등록된 모델이어야 한다(eligibility가 먼저 확인).
    champion은 champion.current()의 결과 또는 None."""
    models = state["models"]
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
    return None
