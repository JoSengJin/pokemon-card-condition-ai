"""Silver 품질 관문(설계 5-3·5-4): 사람 Gold 대조, 주입된 교차 검증, Silver·Pending 라벨 저장.

원칙
- AI 합의는 정답이 아니다. Silver의 근거는 승인된 정책(보정 확인용 묶음의 사람 기준 오류율)이며 `basis: policy_calibration`으로 남긴다.
  여러 판정 함수의 일치는 "불확실하다고 표시된 후보"를 해결할지 정하는 데만 쓰고, 정책 범위 밖·봉인 이미지를 통과시키지 못한다.
- 교차 검증 함수(독립 검증 `independent`, 결정론 CV `cv`)는 호출자가 주입한다. 에이전트 라벨은 넘기지 않는다(앵커링 방지).
  제공된 함수가 모두 같은 확정 값을 내고 그 값이 에이전트 라벨과 같을 때만 해결된다. 함수 오류·모름(None)·값 불일치는 Pending이다.
- Pending은 학습·평가에서 제외하고 값을 저장하지 않는다(정상·결함으로 추정 금지). 정책이 철회되면 그 정책의 Silver는 파생 상태로 Pending이 된다.
- 봉인·보정 묶음의 이미지·그룹에는 Silver를 만들지 않는다(거절). 닫힌 묶음(감사 계획 후)·다른 정책이 섞인 묶음·철회된 정책도 거절한다.
한 묶음(batch_id)은 정책 하나만 쓴다(감사가 정책 단위로 정책 오류율을 판단하기 때문). 저장 이벤트는 silver_store의 한 체인에 쓴다.
"""
import hashlib

from harness import active_learning, silver_policy, silver_store

VERIFIERS = ("independent", "cv")
PROBE_KEYS = ("image_sha", "zone", "defect_type", "stratum")


class GateError(Exception):
    pass


def label_id(image_sha, zone, criteria_version, created_by="agent"):
    """라벨 ID = (이미지 SHA, 구역, 기준 판본, 생성자)의 해시. 같은 요청을 다시 저장해도 같은 ID라서 이어 쓰기가 멱등이다."""
    text = "|".join((image_sha, zone, criteria_version, created_by))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def compare_to_gold(agent_labels, gold):
    """보정 확인용 묶음: 에이전트 제안과 사람 Gold를 (image_sha, zone)으로 대조한다. 사람이 만든 Gold만 받는다(AI 판정은 정답이 아니다).

    에이전트 제안의 label_value가 None(판단 불가)이면 오류로 세지 않고 pending에 센다. Gold가 없는 제안은 unmatched.
    반환 {n, errors, error_rate(분수 [errors, n] 또는 None), unmatched, pending}. 이 값이 silver_policy.approve의 confirm n·errors가 된다.
    """
    truth = {}
    for row in gold:
        key = (row["image_sha"], row["zone"])
        if row.get("created_by") != "human" or key in truth or row.get("value") not in silver_policy.LABEL_VALUES:
            raise GateError("Gold는 사람이 만든 중복 없는 defect/normal 판정만 받는다: %r" % (key,))
        truth[key] = row["value"]
    n = errors = unmatched = pending = 0
    for row in agent_labels:
        key = (row["image_sha"], row["zone"])
        if key not in truth:
            unmatched += 1
        elif row.get("label_value") is None:
            pending += 1
        else:
            n += 1
            errors += row["label_value"] != truth[key]
    return {"n": n, "errors": errors, "error_rate": [errors, n] if n else None, "unmatched": unmatched, "pending": pending}


def cross_verify(cand, verifiers):
    """불확실 후보를 주입된 independent·cv 함수로 교차 검증한다. 반환 {resolved, reason, results}. 에이전트 라벨은 함수에 넘기지 않는다."""
    probe = {k: cand[k] for k in PROBE_KEYS}
    results = {}
    for name in VERIFIERS:
        func = verifiers.get(name)
        if func is None:
            continue
        try:
            results[name] = func(dict(probe))
        except Exception as err:  # 주입 함수의 어떤 오류도 조용히 넘기지 않고 Pending 사유로 남긴다
            return {"resolved": False, "reason": "verifier_error:%s:%s" % (name, type(err).__name__), "results": results}
    values = set(results.values())
    if not results:
        return {"resolved": False, "reason": "no_verifier", "results": results}
    if not values <= set(silver_policy.LABEL_VALUES + (None,)):
        return {"resolved": False, "reason": "verifier_invalid_result", "results": results}
    if None in values:
        return {"resolved": False, "reason": "verifier_unknown", "results": results}
    if len(values) > 1:
        return {"resolved": False, "reason": "verifier_disagreement", "results": results}
    if values != {cand["label_value"]}:
        return {"resolved": False, "reason": "verifier_differs_from_agent", "results": results}
    return {"resolved": True, "reason": "verifiers_agree", "results": results}


def check_candidate(cand, protected, policy, known, criteria_version, verifiers):
    """후보 하나의 판정 {kind: rejected|existing|silver|pending, reason, verification, label_id}. 형식이 틀리면 GateError."""
    if any(not isinstance(cand.get(k), str) or not cand[k] for k in PROBE_KEYS + ("group_id",)) or not isinstance(cand.get("uncertain"), bool):
        raise GateError("후보에는 image_sha·zone·group_id·defect_type·stratum(문자열)과 uncertain(bool)이 필요하다")
    if cand.get("created_by", "agent") != "agent" or cand.get("label_value") not in silver_policy.LABEL_VALUES + (None,):
        raise GateError("이 경로는 에이전트 라벨(defect/normal/None)만 받는다: %r" % (cand.get("image_sha"),))
    lid = label_id(cand["image_sha"], cand["zone"], criteria_version)
    reason = active_learning.protected_reason(cand, protected)
    if reason is not None:
        return {"kind": "rejected", "reason": "%s_image" % reason, "label_id": lid}
    if lid in known:
        return {"kind": "existing", "reason": "already_labeled", "label_id": lid}
    if cand["label_value"] is None:
        return {"kind": "pending", "reason": "agent_unjudgeable", "label_id": lid, "verification": {}}
    scope = policy["scope"]
    if (cand["defect_type"], cand["stratum"], cand["label_value"]) != tuple(scope[k] for k in silver_policy.SCOPE_KEYS):
        return {"kind": "rejected", "reason": "out_of_policy_scope", "label_id": lid}
    if not cand["uncertain"]:
        return {"kind": "silver", "reason": "policy_calibration", "label_id": lid, "verification": {"basis": "policy_calibration"}}
    check = cross_verify(cand, verifiers)
    verification = {"basis": "policy_calibration", "cross_verified": check["results"]}
    return {"kind": "silver" if check["resolved"] else "pending", "reason": check["reason"], "label_id": lid,
            "verification": verification}


def judge_candidates(root, now, batch_id, policy_id, candidates, protected, verifiers, *, criteria_version, model_version):
    """에이전트 후보를 품질 관문에 통과시켜 Silver 또는 Pending으로 저장한다. 같은 인자로 다시 불러도 중복 저장하지 않는다(이어 쓰기).

    반환 {ok, silver, pending, rejected, existing}. 거절(rejected)은 저장하지 않고 사유만 돌려준다. ok=False는 호출 전체의 거절이다
    (policy_inactive·batch_closed·mixed_policy_batch). 검증 함수는 {independent, cv} 중 일부만 줄 수 있다(모두 없으면 불확실 후보는 Pending).
    """
    if not (isinstance(batch_id, str) and batch_id and isinstance(criteria_version, str) and criteria_version
            and isinstance(model_version, str) and model_version):
        raise GateError("batch_id·criteria_version·model_version은 비어 있지 않은 문자열")
    if not isinstance(verifiers, dict) or set(verifiers) - set(VERIFIERS) or any(v is not None and not callable(v) for v in verifiers.values()):
        raise GateError("verifiers는 %s 중 일부를 키로 갖는 함수 dict" % (VERIFIERS,))
    with silver_store.lock(root):
        entries = silver_store.load(root)
        pstate = silver_policy.fold(entries)
        policy = pstate["policies"].get(policy_id)
        if policy is None:
            raise GateError("모르는 정책: %s" % (policy_id,))
        state = fold_labels(entries, pstate)
        batch = state["batches"].get(batch_id)
        if policy["status"] != "approved":
            return {"ok": False, "reason": "policy_inactive"}
        if any(e["event"] in ("audit_planned", "audit_not_required") and e["data"]["batch_id"] == batch_id for e in entries):
            return {"ok": False, "reason": "batch_closed"}
        if batch is not None and batch["policy_id"] != policy_id:
            return {"ok": False, "reason": "mixed_policy_batch"}
        out = {"ok": True, "silver": [], "pending": [], "rejected": [], "existing": []}
        known = set(state["labels"])
        for cand in candidates:
            verdict = check_candidate(cand, protected, policy, known, criteria_version, verifiers)
            if verdict["kind"] == "rejected":
                out["rejected"].append({"image_sha": cand["image_sha"], "zone": cand["zone"], "reason": verdict["reason"]})
            elif verdict["kind"] == "existing":
                out["existing"].append(verdict["label_id"])
            else:
                grade = "Silver" if verdict["kind"] == "silver" else "Pending"
                silver_policy.grade_transition(None, grade, "agent")
                data = {k: cand[k] for k in PROBE_KEYS + ("group_id",)}
                data.update(label_id=verdict["label_id"], batch_id=batch_id, grade=grade, created_by="agent", policy_id=policy_id,
                            criteria_version=criteria_version, model_version=model_version, verification=verdict["verification"])
                if grade == "Silver":
                    data["label_value"] = cand["label_value"]
                else:
                    data["reason"] = verdict["reason"]
                silver_store.append(root, now, "silver_label" if grade == "Silver" else "pending_label", data)
                known.add(verdict["label_id"])
                out["silver" if grade == "Silver" else "pending"].append(verdict["label_id"])
    return out


def fold_labels(entries, pstate):
    """라벨 상태 {labels: {id: 라벨}, batches: {묶음 ID: {policy_id, ids, silver_ids}}}. 철회된 정책의 Silver는 Pending으로 파생한다(값 제거)."""
    labels, batches = {}, {}
    for entry in entries:
        if entry["event"] not in ("silver_label", "pending_label"):
            continue
        data = dict(entry["data"])
        batch = batches.setdefault(data["batch_id"], {"policy_id": data["policy_id"], "ids": [], "silver_ids": []})
        batch["ids"].append(data["label_id"])
        if data["grade"] == "Silver":
            batch["silver_ids"].append(data["label_id"])
            if pstate["policies"][data["policy_id"]]["status"] == "withdrawn":
                silver_policy.grade_transition("Silver", "Pending", "agent")
                data = {k: v for k, v in data.items() if k != "label_value"}
                data.update(grade="Pending", reason="policy_withdrawn")
        labels[data["label_id"]] = data
    return {"labels": labels, "batches": batches}


def trainable_labels(root):
    """학습에 쓸 수 있는 라벨 = 현재 등급이 Silver인 것(철회·Pending 제외). label_id 순."""
    entries = silver_store.load(root)
    labels = fold_labels(entries, silver_policy.fold(entries))["labels"]
    return [labels[i] for i in sorted(labels) if labels[i]["grade"] == "Silver"]
