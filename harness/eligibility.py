"""모델 적격성 계산(승격·복원·철회·4단계 부모 조회가 함께 쓰는 하나의 계산). 호출자가 준 감사 상태를 받지 않고 장부에서만 만든다.

입력은 Silver 저장소 줄(`silver_store.load`)과 레지스트리 상태(`registry.load`)이며, 둘 다 호출자가 잠금 순서 silver → registry로 잡은 안에서 읽는다.
판정(앞에서부터 먼저 걸리는 사유 하나):
1. invalidated: 자신 또는 조상이 레지스트리에서 무효.
2. audit_failed / lineage_invalid: 자신 또는 조상이 무효 묶음을 썼다(장부에서 파생, 레지스트리 무효화가 아직 안 쓰였어도 막는다).
   무효 묶음 = 감사 실패 묶음 ∪ 철회 기록이 무효 범위로 지정한 묶음(아래 REASONS).
3. policy_withdrawn_hold(보류): 철회된 정책(감사 실패가 기록된 정책 포함)의 묶음을 썼다. 자동 재적격 경로는 없다(사용자 결정 2026-11-27 ②).
4. manifest_missing / manifest_mismatch / manifest_parent_mismatch / manifest_pending_labels: 자신 또는 조상의 학습 manifest를 확인할 수
   없거나 선언과 다르거나, 학습 시작 가중치(start_weights_sha)가 선언된 부모(parent)의 가중치 SHA와 다르거나, Pending 라벨을 썼다(마지막은 보류).
   manifest v2(B5-2): start_weights_sha가 None(처음부터 학습)이면 parent도 None이어야 하고, 값이 있으면 선언된 부모의 weights_sha와 정확히
   같아야 한다(대소문자·공백·접두어 변형 거절). v1(키 없음)은 확인 불가라 manifest_mismatch다(fail-closed, 완화하지 않는다).
   한계: manifest 내용 자체를 학습 산출물이 정직하게 채웠는지는 여기서 알 수 없다. 하네스가 계약 입력으로 manifest를 만드는 쪽은
   train_manifest(B5-7)다. 가중치 바이트가 똑같은 두 모델은 SHA로 구분할 수 없다.
5. audit_pending: 계보가 쓴 묶음의 감사가 complete·not_required가 아니다(부모 조회에서는 보지 않는다: 감사 중에도 학습은 계속한다).
"""
import json
import os

from harness import audit_rate, cas, gate, registry, silver_policy, silver_store

AUDIT_OK = ("complete", "not_required")
# 철회 사유(정해진 목록). 이 밖의 값·사유 없음은 unclear로 기록하고 보류만 한다(신규 사용·승격 차단, 무효 범위 없음)
REASONS = ("batch_label_error", "systematic_error", "contamination", "scope_change", "criteria_change", "unclear")
SCOPED = ("batch_label_error", "contamination")  # 지정한 묶음(batches)만 무효. contamination에 묶음이 없으면 정책 전체 무효
WHOLE = ("systematic_error",)  # 정책 전체 무효
MANIFEST_FORMAT = "harness-train-manifest-v2"
MANIFEST_KEYS = frozenset(("format", "silver_batches", "silver_label_ids", "start_weights_sha"))


def silver_facts(entries):
    """Silver 장부 줄 → {policies, labels{id: {batch_id, grade}}, batch_policy, audit{묶음: 상태}, invalid_batches, held_policies}.

    grade는 저장 당시 등급(철회로 파생된 Pending이 아니다). 보류 정책 = 철회됐거나 감사 실패가 기록된 정책(silver_policy.fold가 둘 다 withdrawn으로 접는다).
    """
    pstate = silver_policy.fold(entries)
    labels, batch_policy = {}, {}
    for entry in entries:
        if entry["event"] in ("silver_label", "pending_label"):
            data = entry["data"]
            labels[data["label_id"]] = {"batch_id": data["batch_id"], "grade": data["grade"]}
            batch_policy[data["batch_id"]] = data["policy_id"]
    audited = audit_rate.fold_audit(entries)["batches"]
    audit = {b: audit_rate.status_of(audited.get(b)) for b in batch_policy}
    invalid = set()
    for entry in entries:
        data = entry["data"]
        if entry["event"] == "audit_completed" and data["status"] == "failed":
            invalid.add(data["batch_id"])  # 실패는 뒤에 덧붙인 다른 완료 줄로 되돌아가지 않는다(fold_audit는 마지막 줄을 상태로 쓴다)
        if entry["event"] != "policy_withdrawn":
            continue
        if data.get("reason") in WHOLE or (data.get("reason") == "contamination" and data.get("batches") is None):
            invalid |= {b for b, p in batch_policy.items() if p == data["policy_id"]}
        elif data.get("reason") in SCOPED:
            invalid |= set(data.get("batches") or ())
    held = {p for p, rec in pstate["policies"].items() if rec["status"] == "withdrawn"}
    return {"policies": pstate["policies"], "labels": labels, "batch_policy": batch_policy, "audit": audit,
            "invalid_batches": invalid, "held_policies": held}


def _manifest_reason(root, record, facts, models):
    """모델 하나의 학습 manifest 대조 → 사유 문자열 또는 None. CAS 보관본의 해시가 이름과 같아야 하고, 형식이 맞고,
    silver_batches가 선언과 같고, 모든 라벨 ID가 Silver 장부에 있으며 선언한 묶음 안에 있어야 한다(선언 묶음 중 라벨을 안 쓴 묶음은 허용: 더 막는 쪽).
    start_weights_sha는 선언된 부모(models[record["parent"]])의 weights_sha와 같아야 한다(부모가 없으면 None)."""
    sha = record["data_manifest_sha"]
    path = cas.blob_path(os.path.join(root, "cas"), sha)
    try:
        intact = cas.sha_file(path) == sha
    except OSError:
        intact = False
    if not intact:
        return "manifest_missing"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return "manifest_mismatch"
    shaped = isinstance(data, dict) and set(data) == MANIFEST_KEYS and data["format"] == MANIFEST_FORMAT
    ids = data["silver_label_ids"] if shaped else None
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) \
            or data["silver_batches"] != record["silver_batches"]:
        return "manifest_mismatch"
    parent = record["parent"]
    want = None if parent is None else models.get(parent, {}).get("weights_sha", "")  # 모르는 부모는 어떤 값과도 같지 않다
    start = data["start_weights_sha"]
    if type(start) is not type(want) or start != want or (parent is not None and not want):
        return "manifest_parent_mismatch"
    found = [facts["labels"].get(i) for i in ids]
    if None in found or not {f["batch_id"] for f in found} <= set(record["silver_batches"]):
        return "manifest_mismatch"
    return "manifest_pending_labels" if any(f["grade"] != "Silver" for f in found) else None


def manifest_reasons(root, state, facts):
    """모든 등록 모델의 manifest 대조 결과 {모델 ID: 사유 또는 None}."""
    # shortcut: 호출마다 모든 모델의 manifest를 다시 읽는다. 모델이 수천 개가 되면 필요한 계보만 읽는다
    return {m: _manifest_reason(root, rec, facts, state["models"]) for m, rec in state["models"].items()}


def model_reason(state, facts, manifests, model_id, need_audit=True):
    """적격성 판정. 적격이면 None, 아니면 {reason, detail}. need_audit=False는 부모 조회(감사 대기는 막지 않는다)."""
    models = state["models"]
    if model_id not in models:
        return {"reason": "unknown_model", "detail": model_id}
    chain = gate.ancestors(models, model_id)
    bad = [m for m in chain if models[m]["status"] != "valid"]
    if bad:
        return {"reason": "invalidated", "detail": bad}
    batches = sorted({b for m in chain for b in models[m]["silver_batches"]})
    failed = {b: facts["audit"].get(b) for b in batches if b in facts["invalid_batches"]}
    if failed:
        return {"reason": "audit_failed" if "failed" in failed.values() else "lineage_invalid", "detail": failed}
    held = [b for b in batches if facts["batch_policy"].get(b) in facts["held_policies"]]
    if held:
        return {"reason": "policy_withdrawn_hold", "detail": {"batches": held,
                                                              "policies": sorted({facts["batch_policy"][b] for b in held})}}
    unverified = {m: manifests.get(m, "manifest_missing") for m in chain}  # 대조 결과가 없는 모델은 확인 불가로 본다
    unverified = {m: r for m, r in unverified.items() if r is not None}
    if unverified:
        return {"reason": sorted(unverified.values())[0], "detail": unverified}
    waiting = {b: facts["audit"].get(b) for b in batches if facts["audit"].get(b) not in AUDIT_OK}
    if need_audit and waiting:
        return {"reason": "audit_pending", "detail": waiting}
    return None


def invalid_models(state, facts):
    """레지스트리에 아직 무효로 쓰이지 않았지만 자신 또는 조상이 무효 묶음을 쓴 모델 ID(정렬). 철회 복구가 한 이벤트로 무효화한다."""
    models = state["models"]
    return sorted(m for m, rec in models.items() if rec["status"] == "valid"
                  and any(b in facts["invalid_batches"] for a in gate.ancestors(models, m) for b in models[a]["silver_batches"]))


def parent_check(root, model_id):
    """4단계 계획 관문용 공개 조회(쓰기 없음): model_id가 승격 후보를 학습할 부모로 적격한가. {ok, model_id, reason?, detail?}.

    ok=False이면 그 계보에서 이어 학습한 모델은 승격할 수 없으므로, Silver 묶음·부모가 없는 등록 모델(적격한 초기 가중치)을 이 함수로
    확인해 새 계보를 시작한다. 초기 모델도 같은 계산(무효·보류·manifest)을 거친다. 감사 대기는 막지 않는다.
    """
    with silver_store.lock(root), registry.lock(root):  # 잠금 순서 silver → registry(승격·복원·철회와 같다)
        facts = silver_facts(silver_store.load(root))
        state = registry.load(root)
        verdict = model_reason(state, facts, manifest_reasons(root, state, facts), model_id, need_audit=False)
        if verdict is None and not cas.has(os.path.join(root, "cas"), state["models"][model_id]["weights_sha"]):
            verdict = {"reason": "weights_missing", "detail": state["models"][model_id]["weights_sha"]}
    return {"ok": True, "model_id": model_id} if verdict is None else dict(verdict, ok=False, model_id=model_id)
