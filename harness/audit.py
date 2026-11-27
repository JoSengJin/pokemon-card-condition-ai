"""비동기 감사(설계 5-4): 감사 계획·사람 판정 입력·감사 상태 정본·실패 시 자동 철회.

- 감사 판정은 사람만 낸다. 이 파일은 사람의 판정(`correct`/`incorrect`)을 입력으로 받을 뿐 대신 판정하지 않는다(judge가 "human"이 아니면 거절).
- 감사는 비동기다: 계획을 세우고 판정을 기다리는 동안에도 선별·Silver 생성·학습은 계속된다(이 파일은 그 어떤 것도 막지 않는다). 막는 것은
  Champion 승격뿐이며, 7단계 `champion.promote`가 이 장부를 잠금 안에서 직접 읽어(eligibility) 감사가 끝나기 전의 승격을 거절한다.
  `audit_status(root)`는 조회용이며 승격에 넘기는 값이 아니다(호출자가 준 감사 상태는 믿지 않는다).
- 감사 상태의 정본은 root/silver/store.jsonl(추가 전용 해시 체인)이다: audit_planned·audit_not_required·audit_verdicts·audit_completed.
  계획되지 않은 묶음(라벨은 있으나 감사 계획 전)은 pending이다. Silver가 없는 묶음만 not_required다.
- 실패(표본 오류율 > 정책 상한, 판정이 덜 끝났어도 오류가 이미 상한을 넘으면 확정)하면 ① audit_completed(failed)를 쓰고(이 줄부터 그 정책은 철회된 것으로
  접히고 그 묶음 계보는 파생 무효라 승격이 막힌다) ② 수동 철회와 같은 관문 `withdrawal.withdraw(정책, batch_label_error, [묶음])`을 부른다
  (철회 기록 → 계보 무효화 → Champion 복원·없음 전환·조건부 기록). 중간에 죽으면 같은 인자(verdicts 생략 가능)로 다시 부르면 이어간다.
호출 깊이: record_verdicts → withdrawal.withdraw → champion.restore_locked → (eligibility.model_reason → gate.ancestors | cas.get → cas.blob_path) = 4.
"""
from fractions import Fraction

from harness import audit_rate, silver_gate, silver_policy, silver_store, withdrawal

AuditError = audit_rate.AuditError


def _outcome(plan, verdicts):
    """(상태, 오류 수, 판정한 수). 표본 오류율이 상한을 넘으면 판정이 덜 끝났어도 failed, 전부 판정하고 통과하면 complete, 아니면 pending."""
    sample = plan["sample_ids"]
    errors = sum(1 for i in sample if verdicts.get(i) == "incorrect")
    judged = sum(1 for i in sample if i in verdicts)
    if Fraction(errors, len(sample)) > Fraction(plan["cap"]):
        return "failed", errors, judged
    return ("complete" if judged == len(sample) else "pending"), errors, judged


def plan_audit(root, now, batch_id, *, seed, schedule, signals=None):
    """묶음의 감사 표본과 감사율을 정하고 장부에 남긴다. 같은 묶음을 다시 계획하면 기존 계획을 돌려준다(멱등).

    schedule: {initial, floor, initial_rounds} 사전 등록 값(audit_rate.SUGGESTED_SCHEDULE는 제안값일 뿐 기본값이 아니다).
    signals: {distribution_shift, champion_silver_disagreement} bool. 켜지면 감사율을 초기 비율로 올린다. 감사율·근거는 계획 이벤트에 남는다.
    라벨 중 Silver가 하나도 없는 묶음은 audit_not_required다(Pending뿐이라 감사할 AI 라벨이 없음).
    """
    initial, floor, rounds, active = audit_rate.check_plan_inputs(schedule, signals)
    if isinstance(seed, bool) or not isinstance(seed, (int, str)) or seed == "":
        raise AuditError("seed는 정수 또는 비어 있지 않은 문자열")
    with silver_store.lock(root):
        entries = silver_store.load(root)
        pstate = silver_policy.fold(entries)
        batch = silver_gate.fold_labels(entries, pstate)["batches"].get(batch_id)
        astate = audit_rate.fold_audit(entries)
        if batch is None:
            raise AuditError("라벨이 없는 묶음: %s" % (batch_id,))
        known = astate["batches"].get(batch_id)
        if known is not None and (known["plan"] is not None or known["not_required"]):
            return {"ok": True, "existing": True, "status": audit_rate.status_of(known), "plan": known["plan"]}
        if not batch["silver_ids"]:
            silver_store.append(root, now, "audit_not_required", {"batch_id": batch_id, "reason": "no_silver_labels"})
            return {"ok": True, "existing": False, "status": "not_required", "plan": None}
        policy = pstate["policies"][batch["policy_id"]]
        current = astate["policies"].get(policy["policy_id"], audit_rate.NEW_POLICY)
        rate, basis, raised = audit_rate.rate_for(current, active, initial, floor, rounds, Fraction(policy["cap"]))
        if not rate > 0:
            raise AuditError("감사율 0%는 금지다")
        sample = audit_rate.sample_ids(batch["silver_ids"], rate, seed)
        plan = {"batch_id": batch_id, "policy_id": policy["policy_id"], "n_silver": len(batch["silver_ids"]), "rate": str(rate),
                "prev_rate": None if current["rate"] is None else str(current["rate"]), "rate_changed": current["rate"] != rate,
                "basis": basis, "raised": raised, "cap": policy["cap"], "seed": seed, "sample_size": len(sample), "sample_ids": sample,
                "schedule": {"initial": str(initial), "floor": str(floor), "initial_rounds": rounds}}
        silver_store.append(root, now, "audit_planned", plan)
    return {"ok": True, "existing": False, "status": "pending", "plan": plan}


def set_rate(root, now, policy_id, rate, basis):
    """정책의 감사율을 수동 조정한다(다음 계획부터 적용). 0 이하는 거절하고 근거(비어 있지 않은 문자열)가 없으면 거절한다. 같은 값은 쓰지 않는다."""
    value = silver_policy.ratio(rate)
    if not 0 < value <= 1:
        raise AuditError("감사율은 0 초과 1 이하여야 한다(0%는 금지)")
    if not isinstance(basis, str) or not basis.strip():
        raise AuditError("감사율 조정에는 근거가 필요하다")
    with silver_store.lock(root):
        entries = silver_store.load(root)
        if policy_id not in silver_policy.fold(entries)["policies"]:
            raise AuditError("모르는 정책: %s" % (policy_id,))
        current = audit_rate.fold_audit(entries)["policies"].get(policy_id, audit_rate.NEW_POLICY)
        if current["override"] == value:
            return {"ok": True, "already": True}
        silver_store.append(root, now, "audit_rate_set", {"policy_id": policy_id, "rate": str(value), "basis": basis,
                                                          "prev": None if current["rate"] is None else str(current["rate"])})
    return {"ok": True, "already": False}


def record_verdicts(root, now, batch_id, verdicts=None, judge="human"):
    """사람의 감사 판정 {라벨 ID: "correct"|"incorrect"}을 기록하고, 결과가 정해지면 완료·실패를 기록한다(실패면 철회 관문을 부른다).

    verdicts를 생략하면 새 판정 없이 정산만 한다: 죽은 호출이 남긴 완료 기록·철회를 마저 쓴다(같은 인자 재호출 = 이어가기, 멱등).
    표본 밖 라벨 ID·이미 낸 판정의 번복·사람이 아닌 judge는 AuditError.
    반환 {ok, status, errors, judged, n_sample, cascade}. cascade는 실패일 때 withdrawal.withdraw의 반환(없으면 None).
    """
    if judge != "human":
        raise AuditError("감사 판정은 사람만 낸다(judge는 human)")
    verdicts = dict(verdicts or {})
    if any(v not in ("correct", "incorrect") for v in verdicts.values()):
        raise AuditError("판정은 correct 또는 incorrect")
    with silver_store.lock(root):
        entries = silver_store.load(root)
        batch = audit_rate.fold_audit(entries)["batches"].get(batch_id)
        if batch is None or batch["plan"] is None:
            raise AuditError("감사가 계획되지 않은 묶음: %s" % (batch_id,))
        plan = batch["plan"]
        bad = sorted(set(verdicts) - set(plan["sample_ids"])) + sorted(i for i, v in verdicts.items() if batch["verdicts"].get(i, v) != v)
        if bad:
            raise AuditError("표본 밖 라벨 ID 또는 이미 낸 판정의 번복: %s" % (bad,))
        new = {i: v for i, v in verdicts.items() if i not in batch["verdicts"]}
        if new:
            silver_store.append(root, now, "audit_verdicts", {"batch_id": batch_id, "verdicts": new, "judge": judge})
            batch["verdicts"].update(new)
        status, errors, judged = _outcome(plan, batch["verdicts"])
        if batch["completed"] is None and status != "pending":
            batch["completed"] = silver_store.append(root, now, "audit_completed", {
                "batch_id": batch_id, "policy_id": plan["policy_id"], "status": status, "errors": errors, "judged": judged,
                "n_sample": len(plan["sample_ids"]), "cap": plan["cap"]})["data"]
    cascade = None  # 잠금을 놓은 뒤 철회 관문을 부른다(같은 프로세스가 flock을 다시 잡으면 스스로 막힌다). 그 사이에도 실패 기록이 승격을 막는다
    if batch["completed"] is not None and batch["completed"]["status"] == "failed":
        cascade = withdrawal.withdraw(root, now, plan["policy_id"], "batch_label_error", [batch_id])
    return {"ok": True, "status": audit_rate.status_of(batch), "errors": errors, "judged": judged, "n_sample": len(plan["sample_ids"]),
            "cascade": cascade}


def audit_status(root):
    """{묶음 ID: complete|not_required|pending|failed} 조회. 승격 관문은 이 값을 받지 않고 장부를 직접 읽는다(eligibility).

    라벨이 있는 모든 묶음을 담는다: 감사가 계획되지 않았거나 판정이 덜 끝난 묶음은 pending, 실패한 묶음은 failed. 장부가 변조되면 StoreError.
    """
    with silver_store.lock(root):
        entries = silver_store.load(root)
    batches = silver_gate.fold_labels(entries, silver_policy.fold(entries))["batches"]
    audited = audit_rate.fold_audit(entries)["batches"]
    return {b: audit_rate.status_of(audited.get(b)) for b in sorted(batches)}
