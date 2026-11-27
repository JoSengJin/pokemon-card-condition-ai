"""재라벨 규칙(설계 5-6). 요청 이벤트와 대상 목록만 다루며 라벨 화면을 만들거나 사람에게 보내지 않는다.

- 정당한 재라벨: 기준 판본이 바뀌었고(old != new) 영향받는 결함 유형(affected_types)에 한해, 모델 결과를 보지 않고 전체 또는 무작위(seed 고정)로 고른다.
  후보에 모델 결과 필드(점수·예측·오류 여부 등)가 하나라도 있으면 거절한다: 모델이 틀린 구역만 골라 재라벨하는 경로를 입력 단계에서 막는다.
  (필드 이름 목록으로만 판단하므로 다른 이름으로 숨긴 모델 결과는 못 잡는다. 호출자가 지켜야 하는 계약이다.)
- 중복으로 거절: 같은 `(이미지 SHA, 구역, 기준 판본, 판정자)` 키. 이미 끝난 라벨(이 저장소의 에이전트 라벨, 또는 호출자가 준 완료 키)은 다시 요청하지 않는다.
- 자기 일치도 재판정은 같은 키를 다시 판정하는 일이라 위 규칙의 예외지만, 계획 ID(plan_id)와 반복 번호가 있는 별도 종류(kind=self_agreement)로만 허용하고
  원래 끝난 라벨이 있어야 하며 `planned_repeat: true`로 따로 표시한다(새 라벨로 세지 않는다).
- 사람 판정자(judge=human)에게 가는 요청 항목에 미리 채운 필드가 있으면 거절한다(silver_policy.reject_prefilled).
"""
import hashlib
import math

from harness import silver_policy, silver_store

KEY_FIELDS = ("image_sha", "zone", "criteria_version", "judge")
MODEL_FIELDS = frozenset(("pred", "pred_a", "pred_b", "prediction", "predicted", "score", "model_score", "model_label", "model_output",
                          "model_correct", "is_error", "error", "wrong", "correct", "fn", "fp", "false_negative", "false_positive",
                          "error_type", "champion_score", "challenger_score"))


class RelabelError(Exception):
    pass


def key_of(item):
    """요청 항목의 중복 판정 키 (이미지 SHA, 구역, 기준 판본, 판정자). 형식이 틀리면 RelabelError."""
    if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in KEY_FIELDS) \
            or item["judge"] not in ("human", "agent"):
        raise RelabelError("요청 항목에는 %s(문자열, judge는 human|agent)가 필요하다" % (KEY_FIELDS,))
    return tuple(item[k] for k in KEY_FIELDS)


def fold_requests(entries):
    """장부에서 {requested: 재라벨 요청 키, repeats: (키, 계획 ID, 반복 번호), done: 끝난 에이전트 라벨 키} 집합."""
    requested, repeats, done = set(), set(), set()
    for entry in entries:
        data = entry["data"]
        if entry["event"] == "relabel_requested" and data["kind"] == "relabel":
            requested.add(tuple(data["key"]))
        elif entry["event"] == "relabel_requested":
            repeats.add((tuple(data["key"]), data["plan_id"], data["repeat_index"]))
        elif entry["event"] in ("silver_label", "pending_label"):
            done.add((data["image_sha"], data["zone"], data["criteria_version"], "agent"))
    return {"requested": requested, "repeats": repeats, "done": done}


def select_targets(candidates, change, judge, seed, fraction=None):
    """기준 판본 변경으로 영향받는 유형의 재라벨 대상을 모델 결과 없이 고른다. fraction이 None이면 전체, 아니면 seed 고정 무작위 부분.

    change = {"old", "new", "affected_types": [결함 유형...]}. 반환 {targets: [{image_sha, zone, defect_type, criteria_version(=new), judge}], basis}.
    """
    change = change if isinstance(change, dict) else {}
    types = change.get("affected_types")
    versions = [change.get("old"), change.get("new")]
    if not (isinstance(types, list) and types and all(isinstance(t, str) and t for t in types)) \
            or not all(isinstance(v, str) and v for v in versions) or versions[0] == versions[1]:
        raise RelabelError("change에는 서로 다른 old·new 기준 판본과 비어 있지 않은 affected_types가 필요하다")
    if judge not in ("human", "agent") or isinstance(seed, bool) or not isinstance(seed, (int, str)) or seed == "":
        raise RelabelError("judge는 human|agent, seed는 정수 또는 비어 있지 않은 문자열")
    pool = {}
    for item in candidates:
        leaked = sorted(MODEL_FIELDS & set(item))
        if leaked:
            raise RelabelError("모델 결과 필드가 있는 후보는 재라벨 대상 선정에 쓰지 않는다: %s" % (leaked,))
        if any(not isinstance(item.get(k), str) or not item[k] for k in ("image_sha", "zone", "defect_type")):
            raise RelabelError("후보에는 image_sha·zone·defect_type(문자열)이 필요하다")
        if item["defect_type"] in types:
            pool[(item["image_sha"], item["zone"])] = item["defect_type"]
    keys = sorted(pool)
    if fraction is not None:
        share = silver_policy.ratio(fraction)
        if not 0 < share <= 1:
            raise RelabelError("fraction은 0 초과 1 이하")
        count = max(1, math.ceil(share * len(keys))) if keys else 0
        order = sorted((hashlib.sha256(("%s|%s|%s" % (seed, k[0], k[1])).encode("utf-8")).hexdigest(), k) for k in keys)
        keys = sorted(k for _, k in order[:count])
    targets = [{"image_sha": k[0], "zone": k[1], "defect_type": pool[k], "criteria_version": change["new"], "judge": judge} for k in keys]
    return {"targets": targets, "basis": {"kind": "criteria_change", "old": change["old"], "new": change["new"], "affected_types": sorted(types),
                                          "mode": "all" if fraction is None else "random", "fraction": None if fraction is None else str(fraction),
                                          "seed": seed, "model_results_used": False}}


def request_relabel(root, now, selection, completed=()):
    """select_targets의 결과로 재라벨을 요청(이벤트 기록)한다. 중복 키·이미 끝난 라벨은 거절한다. 반환 {ok, accepted, rejected}.

    completed: 호출자가 아는 끝난 라벨 키(예: 사람 Gold의 (이미지 SHA, 구역, 기준 판본, human))의 목록.
    """
    basis, targets = selection["basis"], selection["targets"]
    if basis.get("kind") != "criteria_change" or basis.get("model_results_used") is not False:
        raise RelabelError("select_targets의 결과(기준 판본 변경 기반, 모델 결과 미사용)만 받는다")
    finished = {tuple(k) for k in completed}
    accepted, rejected = [], []
    with silver_store.lock(root):
        state = fold_requests(silver_store.load(root))
        for item in targets:
            silver_policy.reject_prefilled(item)
            key = key_of(item)
            if item["criteria_version"] != basis["new"] or item["defect_type"] not in basis["affected_types"]:
                raise RelabelError("대상이 기준 판본 변경 범위(new 판본·affected_types) 밖이다: %r" % (key,))
            if key in state["requested"]:
                rejected.append({"key": list(key), "reason": "duplicate_request"})
            elif key in state["done"] or key in finished:
                rejected.append({"key": list(key), "reason": "already_completed"})
            else:
                silver_store.append(root, now, "relabel_requested", {"key": list(key), "kind": "relabel", "defect_type": item["defect_type"],
                                                                     "basis": basis})
                state["requested"].add(key)
                accepted.append(list(key))
    return {"ok": True, "accepted": accepted, "rejected": rejected}


def request_repeat(root, now, items, plan_id, completed=()):
    """자기 일치도 재판정을 계획된 반복으로 요청한다. 항목마다 repeat_index(≥1)가 있고, 원래 끝난 라벨이 있어야 하며, 같은
    (키, plan_id, repeat_index)는 한 번만 받는다. 기록은 kind=self_agreement, planned_repeat=true다(새 라벨로 세지 않는다)."""
    if not isinstance(plan_id, str) or not plan_id:
        raise RelabelError("자기 일치도 재판정에는 계획 ID(plan_id)가 필요하다")
    finished = {tuple(k) for k in completed}
    accepted, rejected = [], []
    with silver_store.lock(root):
        state = fold_requests(silver_store.load(root))
        for item in items:
            silver_policy.reject_prefilled(item)
            key, index = key_of(item), item.get("repeat_index")
            if not isinstance(index, int) or isinstance(index, bool) or index < 1:
                raise RelabelError("repeat_index는 1 이상의 정수")
            if (key, plan_id, index) in state["repeats"]:
                rejected.append({"key": list(key), "reason": "duplicate_repeat"})
            elif key not in state["done"] and key not in finished:
                rejected.append({"key": list(key), "reason": "no_original_label"})
            else:
                silver_store.append(root, now, "relabel_requested", {"key": list(key), "kind": "self_agreement", "plan_id": plan_id,
                                                                     "repeat_index": index, "planned_repeat": True})
                state["repeats"].add((key, plan_id, index))
                accepted.append(list(key))
    return {"ok": True, "accepted": accepted, "rejected": rejected}
