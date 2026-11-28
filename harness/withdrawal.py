"""Silver 정책 철회의 단일 관문과 복구(설계 5-4, 2026-11-27 B+D 합의·최종 결정).

수동 철회와 감사 실패의 자동 철회는 모두 `withdraw`를 부른다. 한 호출이 하는 일(잠금 순서 silver → registry, 승격·복원과 같다):
① (policy_id를 주면) 철회 시작 기록 policy_withdrawn {policy_id, reason, batches, given}. 같은 (정책, 사유, 묶음) 기록이 있으면 쓰지 않는다.
② 장부에서 무효 묶음을 다시 계산해(eligibility.silver_facts) 그 묶음을 쓴 모델과 모든 후속 중 아직 유효한 모델을 한 invalidated 이벤트로 무효화.
③ 현재 Champion이 무효이면 같은 적격성 계산으로 복원하거나, 적격 후보가 없으면 "Champion 없음"으로 전환(champion.restore_locked, WAL).
④ 현재 Champion이 유효하지만 철회 정책의 다른 묶음 때문에 보류이면 조건부 유지로 champion_conditional을 한 번 기록(새 승격·복원 근거 아님).
모든 단계가 장부에서 다시 계산하므로, 시작 기록 뒤 어느 지점에서 죽어도 같은 호출(또는 policy_id 없이 부른 복구 호출)이 같은 최종 상태로 이어간다.
복구 전이라도 승격·복원은 같은 파생 계산으로 영향 모델을 막는다(eligibility). 장부 해시 불일치는 철회 사유가 아니라 기존 무결성 정지다
(silver_store.StoreError·registry.RegistryError가 그대로 나간다).

사유(eligibility.REASONS)와 처리: batch_label_error·contamination은 batches로 지정한 묶음 계보를 무효화하고 나머지 묶음 계보는 보류.
contamination에 batches가 없으면(오염은 확인됐으나 범위를 특정할 수 없음) 정책 전체 계보 무효. systematic_error는 정책 전체 계보 무효.
scope_change·criteria_change·unclear(목록 밖 값·사유 없음 포함)와 batches 없는 batch_label_error는 보류만(오류 자체나 범위가 미확인).
의미 변화 없는 문구 수정은 철회가 아니다(철회·재감사를 요구하지 않는다). 자동 재적격 경로는 없다.
"""
import os

from harness import champion, eligibility, ledger, registry, silver_policy, silver_store


def _start(root, now, entries, facts, policy_id, reason, batches):
    """철회 시작 기록을 검사하고 쓴다. 쓴 장부 줄 또는(같은 기록이 이미 있으면) None. 입력 형식이 틀리면 PolicyError(아무 것도 쓰지 않는다)."""
    if policy_id not in facts["policies"]:
        raise silver_policy.PolicyError("모르는 정책: %s" % (policy_id,))
    if batches is not None:
        if not isinstance(batches, (list, tuple)) or not batches or not all(isinstance(b, str) and b for b in batches):
            raise silver_policy.PolicyError("batches는 None 또는 비어 있지 않은 묶음 ID 목록")
        batches = sorted(set(batches))
        outside = [b for b in batches if facts["batch_policy"].get(b) != policy_id]
        if outside:
            raise silver_policy.PolicyError("이 정책의 묶음이 아니다: %s" % (outside,))
    code = reason if isinstance(reason, str) and reason in eligibility.REASONS else "unclear"
    for entry in entries:
        data = entry["data"]
        if entry["event"] == "policy_withdrawn" and (data["policy_id"], data.get("reason"), data.get("batches")) == (policy_id, code, batches):
            return None
    return silver_store.append(root, now, "policy_withdrawn", {"policy_id": policy_id, "reason": code, "batches": batches,
                                                               "given": reason if isinstance(reason, str) else None})


def _conditional(root, now, entries, state, facts, manifests):
    """현재 Champion이 유효하지만 철회 정책 때문에 보류이면 조건부 유지를 기록하고 그 내용을, 아니면 None을 돌려준다.
    (모델, 영향 묶음, 정책)이 같은 기록이 이미 있으면 다시 쓰지 않는다(사유가 나중에 확정돼 바뀌어도 한 번)."""
    holder = champion.current(root, state)
    if holder is None or not holder["valid"]:
        return None
    verdict = eligibility.model_reason(state, facts, manifests, holder["model_id"])
    if verdict is None or verdict["reason"] != "policy_withdrawn_hold":
        return None
    data = dict(verdict["detail"], model_id=holder["model_id"],
                reasons={p: facts["policies"][p].get("withdraw_reason") for p in verdict["detail"]["policies"]})
    key = (data["model_id"], data["batches"], data["policies"])
    if not any(e["event"] == "champion_conditional" and (e["data"]["model_id"], e["data"]["batches"], e["data"]["policies"]) == key
               for e in entries):
        silver_store.append(root, now, "champion_conditional", data)
    return data


def withdraw(root, now, policy_id=None, reason=None, batches=None):
    """정책 철회(policy_id를 줄 때) 또는 복구만(policy_id=None). 반환 {ok, already, invalidated, restore, conditional}.

    already: 이번 호출이 철회 시작 기록을 새로 쓰지 않았다(복구만이거나 같은 기록이 있음). invalidated: 이번에 새로 무효화한 모델.
    restore: champion.restore_locked 결과 요약(현재 Champion이 무효가 아니면 None). conditional: 조건부 유지 기록(없으면 None).
    CAS 손상 등으로 복원이 ChampionError를 내면 무효화는 기록된 채 오류가 나간다(같은 인자 재호출로 이어간다).
    """
    with silver_store.lock(root):
        entries = silver_store.load(root)
        facts = eligibility.silver_facts(entries)
        started = None if policy_id is None else _start(root, now, entries, facts, policy_id, reason, batches)
        if started is not None:
            entries.append(started)
            facts = eligibility.silver_facts(entries)
        with registry.lock(root):
            state = registry.load(root)
            if champion.settle(root, now, state):
                state = registry.load(root)
            ids = eligibility.invalid_models(state, facts)
            if ids:
                data = {"models": ids, "cause": "silver_withdrawal: %s" % ",".join(sorted(facts["invalid_batches"]))}
                registry.apply(state, ledger.append(os.path.join(root, registry.REGISTRY), now, "invalidated", data))
                ledger.append(os.path.join(root, "ledger.jsonl"), now, "lineage_invalidated", data)
            manifests = eligibility.manifest_reasons(root, state, facts)
            holder = champion.current(root, state)
            restore = None
            if holder is not None and not holder["valid"]:
                restore = champion.restore_locked(root, now, state, facts, manifests)
                state = registry.load(root)
            conditional = _conditional(root, now, entries, state, facts, manifests)
    summary = None if restore is None else {k: restore.get(k) for k in ("ok", "model_id", "restored_from", "reason", "cleared")}
    return {"ok": True, "already": started is None, "invalidated": ids, "restore": summary, "conditional": conditional}
