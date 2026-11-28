"""학습 적용기(B5-7): VERIFIED 학습 작업의 산출물을 모델 레지스트리에 Challenger로 등록한다. 승격하지 않는다(실제 승격은 미승인).

- 대상: task_type "training", outputs에 WEIGHTS·EVAL이 있는 작업. 상태는 states.facts → state_of로 직접 판정한다(VERIFIED만).
- manifest는 train_manifest.build가 계약 입력 사본·Silver 장부로 만든다(out/에 executor가 쓴 manifest 파일은 읽지 않는다). CAS에 보관하고
  그 SHA를 data_manifest_sha로 등록한다. 부모는 manifest와 같은 계산에서 나온 값만 쓴다(eligibility가 다시 대조한다).
- 멱등: 같은 작업을 다시 적용하면 적용 기록(APPLIED/<task_key>.json)으로 already=True. 등록 뒤·기록 전에 죽어도 registry.register가
  같은 식별 필드면 다시 쓰지 않으므로(existing) 모델은 하나다. 적용 기록이 레지스트리에 없는 모델을 가리키면 applied_record_mismatch(추정하지 않음).
- 정지 상태(opstate.HALTING) 중에는 반영하지 않는다(pre-b5 결정 9 미정: 반영을 미뤄도 잃는 것이 없는 fail-closed 기본값. 재개 뒤 다시 적용).
- 장부 손상(RegistryError·StoreError)은 그대로 올린다(무결성 문제). 입력·형식 거절은 {"ok": False, "reason"}.
- config는 {"run_config": 계약 config, "seed": 계약 seed}, code_sha는 계약 run_conditions.code_sha(소문자). 평가는 out/EVAL(dev 평가 기록일 뿐,
  승격 판정 근거가 아니다).
호출 깊이: apply → registry.register → load → ledger.verify → _check_line (4). 그래서 apply는 진입점이다: 다른 함수 안에서 부르면 한도를
넘으므로 통합 때는 별도 프로세스(`python -m harness.apply_train <root> <task_key>`, 아래 모듈 수준 코드)로 부른다.
한계: VERIFIED 판정 뒤 등록까지 사이에 out/ 파일이 바뀌는 경합은 막지 않는다(out/은 하네스만 쓴다는 runner 전제).
"""
import json
import os
import sys
import time

from . import contract as ct
from . import cas, eligibility, opstate, registry, silver_store, states, train_manifest
from .jsonio import read_json, write_json

APPLIED = os.path.join("models", "train_applied")
WEIGHTS, EVAL = "weights.bin", "eval.json"


def apply(root, task_key, now):
    """task_key 학습 작업을 등록한다. {"ok", "task_key", "reason"?, "model_id"?, "already"?}."""
    key = ct.check_key(task_key)
    halted = opstate.effective(opstate.load(root))
    if halted in opstate.HALTING:
        return {"ok": False, "task_key": key, "reason": "halted:" + halted}
    tdir, record_path = os.path.join(root, "tasks", key), os.path.join(root, APPLIED, key + ".json")
    info = states.facts(tdir)
    if states.state_of(info, False) != states.VERIFIED:
        return {"ok": False, "task_key": key, "reason": "not_verified"}
    task = info["contract"]
    if task["task_type"] != "training" or not {WEIGHTS, EVAL} <= set(task["outputs"]) \
            or not isinstance(task.get("run_conditions"), dict) or not isinstance(task["run_conditions"].get("code_sha"), str):
        return {"ok": False, "task_key": key, "reason": "not_training"}
    facts = eligibility.silver_facts(silver_store.load(root))
    state = registry.load(root)
    if os.path.exists(record_path):
        done = read_json(record_path)
        if not isinstance(done, dict) or done.get("task_key") != key or done.get("model_id") not in state["models"]:
            return {"ok": False, "task_key": key, "reason": "applied_record_mismatch"}
        return {"ok": True, "task_key": key, "already": True, "model_id": done["model_id"]}
    try:
        manifest, parent = train_manifest.build(tdir, task, facts, state["models"])
        result = read_json(os.path.join(tdir, "out", EVAL))
    except train_manifest.TrainManifestError as exc:
        return {"ok": False, "task_key": key, "reason": exc.args[0], "detail": exc.args[1] if len(exc.args) > 1 else None}
    except ValueError as exc:
        return {"ok": False, "task_key": key, "reason": "bad_eval", "detail": str(exc)}
    staged = os.path.join(root, "models", "incoming", key + ".manifest.json")
    write_json(staged, manifest)  # 정렬 키 JSON: 같은 manifest는 같은 SHA
    sha = cas.put(os.path.join(root, "cas"), staged)
    cond = task["run_conditions"]
    try:
        made = registry.register(root, now, os.path.join(tdir, "out", WEIGHTS), cond["code_sha"].lower(), sha,
                                 {"run_config": cond.get("config") or {}, "seed": cond.get("seed")}, result,
                                 manifest["silver_batches"], parent=parent)
    except registry.RegistryError as exc:  # 체인 손상은 위 registry.load에서 이미 올라간다. 여기는 입력 형식 거절
        return {"ok": False, "task_key": key, "reason": "register_refused", "detail": str(exc)}
    if not made["ok"]:
        return {"ok": False, "task_key": key, "reason": made["reason"], "model_id": made["model_id"]}
    write_json(record_path, {"task_key": key, "model_id": made["model_id"], "applied_at": now, "existing": made["existing"]})
    return {"ok": True, "task_key": key, "already": False, "model_id": made["model_id"], "existing": made["existing"]}


if __name__ == "__main__":  # 진입점(함수가 아니라 깊이에 더하지 않는다): python -m harness.apply_train <root> <task_key>
    print(json.dumps(apply(sys.argv[1], sys.argv[2], time.time()), ensure_ascii=False, sort_keys=True))
