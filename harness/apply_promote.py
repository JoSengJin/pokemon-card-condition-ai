"""채점·승격 판정 적용기(B5-10, VS5): VERIFIED 평가 작업의 구역 행(out/rows.json)을 promotion.evaluate(채점·부트스트랩·민감도·보류 상한)로 판정하고
결과를 root/promotion/verdicts/<task_key>.json과 장부(promotion_verdict)에 남긴다. **판정만 기록한다. champion.promote·예산 차감·봉인 평가는 하지 않는다**(승격 실행 미승인).

계약(평가 작업 evaluation): outputs에 rows.json, depends_on에 학습 작업이 있고 run_conditions.config가
`{"promotion": {noise_rate, direction_min_fraction, min_defect_cards, min_valid_fraction[, replicates, trials, seed, delta]}, "candidate_of": <학습 작업 task_key>}`.
사전 등록 수치는 계약 config에 있어 논리 키(SHA)에 묶인다: 결과를 본 뒤 바꿀 수 없고 기본값도 없다(promotion.evaluate와 같다). 이 값들은 승인된 수치가 아니라
등록자가 정한 것이다(D-5/D-6 수치는 사용자 결정 대기). 후보 모델 = 그 학습 작업의 적용 기록(apply_train.APPLIED)이 가리키는 모델. 아직 적용 전이면 판정하지 않고
candidate_not_applied(대기)다. 행의 정답·예측은 평가 executor 산출물(하네스가 계약 manifest로 SHA를 확인한 out/ 사본)이며, 봉인(sealed) 행은 evaluate가 거절한다.
멱등: 기록이 있으면 already. 기록을 쓴 뒤 장부 줄 전에 죽으면 다음 적용이 줄만 보충한다(줄은 task_key당 하나).
정지 상태(opstate.HALTING)에서는 반영하지 않는다(pre-b5 결정 9 (나), 메인 기본값). 장부·레지스트리 손상은 그대로 올린다(무결성). 입력·형식 거절은 {"ok": False, "reason"}.
한계: 이 판정은 학습 데이터와 평가 행의 카드 그룹 겹침을 다시 확인하지 않는다(Silver 입력 단계의 protected 검사에 맡김). 모델 적격성(eligibility)도 확인하지 않는다
(승격 실행 때 champion.promote가 한다). 합성 시험은 모델 성능 근거가 아니다.
호출 깊이: apply → promotion.evaluate → paired_bootstrap → totals(3)이라 진입점은 apply 4다(apply_main의 __main__ 블록에서만 부른다).
"""
import os

from . import contract as ct
from . import apply_train, ledger, opstate, promotion, registry, states
from .jsonio import read_json, write_json

VERDICTS = os.path.join("promotion", "verdicts")
ROWS = "rows.json"
REQUIRED = ("noise_rate", "direction_min_fraction", "min_defect_cards", "min_valid_fraction")
OPTIONAL = ("replicates", "trials", "seed", "delta")


def _config(task):
    """(promotion 설정 dict, 후보 학습 작업 key) 또는 None(평가 계약이 아니거나 형식이 어긋남)."""
    cond = task.get("run_conditions")
    config = cond.get("config") if isinstance(cond, dict) else None
    promo = config.get("promotion") if isinstance(config, dict) else None
    cand = config.get("candidate_of") if isinstance(config, dict) else None
    if task["task_type"] != "evaluation" or ROWS not in task["outputs"] or not isinstance(promo, dict) or not isinstance(cand, str) \
            or not set(REQUIRED) <= set(promo) <= set(REQUIRED + OPTIONAL) or cand not in task["depends_on"]:
        return None
    return promo, cand


def apply(root, task_key, now):
    """task_key 평가 작업을 판정해 기록한다. {"ok", "task_key", "reason"?, "model_id"?, "verdict"?, "already"?}."""
    key = ct.check_key(task_key)
    halted = opstate.effective(opstate.load(root))
    if halted in opstate.HALTING:
        return {"ok": False, "task_key": key, "reason": "halted:" + halted}
    tdir, path = os.path.join(root, "tasks", key), os.path.join(root, VERDICTS, key + ".json")
    info = states.facts(tdir)
    if states.state_of(info, False) != states.VERIFIED:
        return {"ok": False, "task_key": key, "reason": "not_verified"}
    parsed = _config(info["contract"])
    if parsed is None:
        return {"ok": False, "task_key": key, "reason": "not_promotion_eval"}
    promo, cand = parsed
    rec = read_json(path)
    if rec is None:
        applied = read_json(os.path.join(root, apply_train.APPLIED, cand + ".json"))
        if applied is None:
            return {"ok": False, "task_key": key, "reason": "candidate_not_applied"}
        model = applied.get("model_id") if isinstance(applied, dict) else None
        if model not in registry.load(root)["models"]:
            return {"ok": False, "task_key": key, "reason": "applied_record_mismatch"}
        try:
            result = promotion.evaluate(read_json(os.path.join(tdir, "out", ROWS)), **promo)
            rec = {"task_key": key, "candidate_of": cand, "model_id": model, "verdict": result["verdict"], "promoted": False,
                   "decided_at": now, "result": result}
            write_json(path, rec)
        except (ValueError, TypeError) as exc:  # 형식·사전 등록 수치·봉인 행·직렬화 거절: 기록하지 않는다
            return {"ok": False, "task_key": key, "reason": "bad_rows_or_config", "detail": str(exc)[:300]}
    elif not isinstance(rec, dict) or rec.get("task_key") != key:
        return {"ok": False, "task_key": key, "reason": "verdict_record_mismatch"}
    seen = any(isinstance(d, dict) and d.get("task_key") == key for d in ledger.events(os.path.join(root, "ledger.jsonl"), "promotion_verdict"))
    if not seen:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "promotion_verdict", {
            "task_key": key, "candidate_of": rec["candidate_of"], "model_id": rec["model_id"], "verdict": rec["verdict"], "promoted": False,
            "reasons": [r["code"] for r in rec["result"]["reasons"]], "rows_sha256": rec["result"]["inputs"]["rows_sha256"],
            "gold_n": rec["result"]["inputs"]["gold_n"]})
    return {"ok": True, "task_key": key, "already": seen, "model_id": rec["model_id"], "verdict": rec["verdict"]}
