"""계보 무효화: Silver 묶음 하나가 감사에서 실패했을 때 그 묶음을 쓴 모델과 후속 모델을 모두 무효화한다.

후속 = 부모 관계(parent)로 이어진 모든 모델(손자 이하 포함). 정책 철회·Silver→Pending 전환은 이번 범위 밖이다.
무효화는 한 이벤트로 기록하고(중간에 죽어도 일부만 무효화된 상태가 없다), 현재 Champion이 포함되면 이어서 복원한다.
"""
import os

from harness import champion, ledger, registry


def affected(models, batch_id):
    """batch_id를 직접 쓴 모델과 그 모든 후속 중 아직 유효한 모델 ID(정렬). 이미 무효인 모델의 후속도 따라간다."""
    hit = {m for m, rec in models.items() if batch_id in rec["silver_batches"]}
    while True:
        more = {m for m, rec in models.items() if rec.get("parent") in hit and m not in hit}
        if not more:
            break
        hit |= more
    return sorted(m for m in hit if models[m]["status"] == "valid")


def invalidate_lineage(root, now, silver_batch_id):
    """{"ok": True, "invalidated": [모델 ID...], "restore": 복원 결과 또는 None}. Champion 복원이 CAS 손상 등으로 실패하면
    무효화는 이미 기록된 채로 ChampionError가 전파된다(포인터는 바뀌지 않음)."""
    if not isinstance(silver_batch_id, str) or not silver_batch_id:
        raise registry.RegistryError("silver_batch_id는 빈 문자열이 아닌 ID여야 한다")
    with registry.lock(root):
        state = registry.load(root)
        if champion.settle(root, now, state):
            state = registry.load(root)
        ids = affected(state["models"], silver_batch_id)
        if not ids:
            return {"ok": True, "invalidated": [], "restore": None}
        data = {"models": ids, "cause": "silver_batch: %s" % silver_batch_id}
        registry.apply(state, ledger.append(os.path.join(root, registry.REGISTRY), now, "invalidated", data))
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "lineage_invalidated", data)
        holder = champion.current(root, state)
        restore = champion.restore_locked(root, now, state) if holder is not None and holder["model_id"] in ids else None
    return {"ok": True, "invalidated": ids, "restore": restore}
