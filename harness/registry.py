"""모델 레지스트리(해시 체인). root/models/registry.jsonl에 1단계 ledger 형식으로 이벤트를 추가만 한다.

이벤트: registered(모델 기록) / switch_intent·switched·switch_aborted(Champion 전환의 선기록 로그) /
invalidated(모델 목록과 원인). 현재 상태는 이벤트를 처음부터 접어서(apply) 얻는다.
쓰기 호출(register·승격·복원·무효화)은 모두 lock(root) 안에서 load → 판단 → 추가 순서로 한다.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import re

from harness import cas, ledger

REGISTRY = os.path.join("models", "registry.jsonl")
POINTER = os.path.join("models", "champion.json")
GRADES = ("Challenger", "Dev-leader")  # Champion은 승격(switched)으로만 붙는다
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class RegistryError(Exception):
    pass


@contextlib.contextmanager
def lock(root):
    """레지스트리·포인터를 바꾸는 호출의 직렬화. 프로세스가 죽으면 flock이 풀린다."""
    path = os.path.join(root, "models", ".lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def apply(state, entry):
    """장부 줄 하나를 상태에 반영한다. 앞뒤가 맞지 않는 줄은 RegistryError(추정하지 않는다)."""
    event, data, models = entry["event"], entry["data"], state["models"]
    state["hashes"].add(entry["hash"])
    state["tail"] = entry["hash"]
    if event == "registered":
        if data["model_id"] in models:
            raise RegistryError("모델 중복 등록: %s" % data["model_id"])
        models[data["model_id"]] = dict(data, status="valid", causes=[])
    elif event == "switch_intent":
        if state["pending"] is not None or data["target"] not in models:
            raise RegistryError("전환 의도가 앞뒤와 맞지 않음(seq %s)" % entry["seq"])
        state["pending"] = dict(data, hash=entry["hash"])
    elif event in ("switched", "switch_aborted"):
        pending = state["pending"]
        if pending is None or pending["hash"] != data["intent_hash"] or pending["target"] != data["target"]:
            raise RegistryError("짝 없는 %s(seq %s)" % (event, entry["seq"]))
        state["pending"] = None
        if event == "switched":
            state["history"].append({"model_id": data["target"], "reason": data["reason"],
                                     "intent_hash": data["intent_hash"], "ts": entry["ts"]})
            models[data["target"]]["grade"] = "Champion"
    elif event == "invalidated":
        for model_id in data["models"]:
            models[model_id]["status"] = "invalidated"
            models[model_id]["causes"].append(data["cause"])
    else:
        raise RegistryError("알 수 없는 이벤트 %r(seq %s)" % (event, entry["seq"]))
    return state


def load(root, expected_tail=None):
    """체인을 검증하고 이벤트를 접어 {models, history, pending, hashes, tail}을 돌려준다. 변조는 RegistryError."""
    path = os.path.join(root, REGISTRY)
    problems = ledger.verify(path, expected_tail)
    if problems:
        raise RegistryError("레지스트리 체인 손상: %s" % (problems[:3],))
    state = {"models": {}, "history": [], "pending": None, "hashes": set(), "tail": ledger.GENESIS}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except FileNotFoundError:
        lines = []
    for raw in lines:
        apply(state, json.loads(raw))
    return state


def _validate(code_sha, data_manifest_sha, config, eval_result, silver_batches, parent, grade):
    """입력 형식 검사. 정상이면 정규화한 (평가, Silver 묶음) 쌍을 돌려주고, 아니면 RegistryError."""
    if not isinstance(code_sha, str) or not _SHA.fullmatch(code_sha):
        raise RegistryError("code_sha는 소문자 16진 40 또는 64자")
    if not isinstance(data_manifest_sha, str) or not _HEX64.fullmatch(data_manifest_sha):
        raise RegistryError("data_manifest_sha는 소문자 16진 64자")
    if grade not in GRADES or not isinstance(config, dict) or not isinstance(eval_result, dict):
        raise RegistryError("등급은 %s, config·평가는 dict" % (GRADES,))
    for key in ("layer", "denominator", "seal_version"):
        value = eval_result.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int)) or value == "":
            raise RegistryError("평가 결과의 %s는 빈 값이 아닌 문자열/정수여야 한다" % key)
    if not isinstance(eval_result.get("metrics"), dict):
        raise RegistryError("평가 결과에 metrics(dict)가 필요하다")
    if not isinstance(silver_batches, (list, tuple)) or not all(isinstance(b, str) and b for b in silver_batches):
        raise RegistryError("silver_batches는 빈 문자열이 아닌 ID 목록이어야 한다")
    if parent is not None and not isinstance(parent, str):
        raise RegistryError("parent는 모델 ID 문자열 또는 None")
    try:
        json.dumps([config, eval_result], sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as err:
        raise RegistryError("config·평가가 JSON으로 저장될 수 없다: %s" % err)
    return eval_result, sorted(set(silver_batches))


def register(root, now, weights_path, code_sha, data_manifest_sha, config, eval_result,
             silver_batches, parent=None, grade="Challenger"):
    """모델을 기록하고 가중치를 CAS(root/cas)에 보관한다. 모델 ID는 식별 필드(평가 제외)의 해시다.

    같은 모델을 같은 평가로 다시 등록하면 아무 것도 쓰지 않고 existing=True, 평가가 다르면 conflict로 거절한다.
    """
    eval_result, batches = _validate(code_sha, data_manifest_sha, config, eval_result, silver_batches, parent, grade)
    weights_sha = cas.put(os.path.join(root, "cas"), weights_path)
    ident = {"code_sha": code_sha, "weights_sha": weights_sha, "data_manifest_sha": data_manifest_sha,
             "config": config, "silver_batches": batches, "parent": parent}
    model_id = hashlib.sha256(json.dumps(ident, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                         allow_nan=False).encode("utf-8")).hexdigest()
    with lock(root):
        state = load(root)
        known = state["models"].get(model_id)
        if known is not None:
            if known["eval"] != eval_result:
                return {"ok": False, "reason": "conflict", "model_id": model_id, "existing": True}
            return {"ok": True, "model_id": model_id, "existing": True}
        if parent is not None and parent not in state["models"]:
            return {"ok": False, "reason": "unknown_parent", "model_id": model_id}
        ledger.append(os.path.join(root, REGISTRY), now, "registered",
                      dict(ident, model_id=model_id, eval=eval_result, grade=grade))
    return {"ok": True, "model_id": model_id, "existing": False}
