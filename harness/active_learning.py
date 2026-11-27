"""능동 학습 선별(설계 5-5). 순수 함수이며 파일·네트워크·모델을 쓰지 않는다. 사진·라벨을 읽지 않고 호출자가 준 후보 목록만 본다.

선별 점수 = 오류 유형 우선순위 × 층 부족도 × 모델 불확실성(문턱 근처·Champion–Challenger 불일치 중 큰 값) × 예상 학습 가치(처음 1).
다양성·대표성: 실물 카드 그룹당·판매자당 상한, 임베딩 군집별 상한, 회차마다 무작위 20%. 같은 seed는 같은 선별을 낸다(정렬 키가 seed 섞은 sha256).
제외: 봉인 묶음과 보정 묶음의 실물 그룹(이미지 SHA·그룹 ID). 결과에 0건이어야 한다. protected 입력이 없으면 제외할 수 없으므로 오류다.
라우팅: 승인된 Silver 정책 범위 안이면 Silver 큐, 밖이면 사람 큐(그 라벨은 개발용 Gold). 큐 항목에는 모델 점수·기대 라벨을 담지 않는다(앵커링 방지).
능동 학습 표본은 대표 표본이 아니다: 결과에 representative=False를 남기고 무작위 부분에는 random_part=True를 붙인다.
"""
import hashlib
import math

RANDOM_PERCENT = 20  # 설계 5-5: 회차마다 무작위 20% 섞기
REQUIRED = ("region_id", "image_sha", "zone", "group_id", "seller_id", "cluster_id", "defect_type", "stratum", "error_type",
            "expected_label")
KEEP = ("region_id", "image_sha", "zone", "group_id", "defect_type", "stratum")


class ActiveLearningError(Exception):
    pass


def protected_reason(item, protected):
    """item의 이미지 SHA 또는 실물 그룹이 봉인·보정 묶음이면 'sealed'/'calibration', 아니면 None. 입력 구조가 틀리면 오류(조용히 통과 금지)."""
    for name in ("sealed", "calibration"):
        part = protected.get(name) if isinstance(protected, dict) else None
        if not isinstance(part, dict) or "image_shas" not in part or "group_ids" not in part:
            raise ActiveLearningError("protected에는 sealed·calibration의 image_shas·group_ids가 모두 있어야 한다")
        if item["image_sha"] in part["image_shas"] or item["group_id"] in part["group_ids"]:
            return name
    return None


def check_inputs(candidates, protected, config, budget, seed):
    """입력을 검사하고 집합으로 정규화한 protected를 돌려준다. 어긋나면 ActiveLearningError(빠진 값을 기본값으로 메우지 않는다)."""
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise ActiveLearningError("budget은 0 이상의 정수")
    if isinstance(seed, bool) or not isinstance(seed, (int, str)) or seed == "":
        raise ActiveLearningError("seed는 정수 또는 비어 있지 않은 문자열")
    if not isinstance(config, dict) or not isinstance(config.get("error_priority"), dict) \
            or not isinstance(config.get("stratum_scarcity"), dict):
        raise ActiveLearningError("config에는 error_priority·stratum_scarcity(dict)가 필요하다")
    for key in ("per_group_cap", "per_seller_cap", "cluster_quota"):
        if not isinstance(config.get(key), int) or isinstance(config[key], bool) or config[key] < 1:
            raise ActiveLearningError("%s는 1 이상의 정수" % key)
    width = config.get("threshold_width")
    if isinstance(width, bool) or not isinstance(width, (int, float)) or not math.isfinite(width) or width <= 0:
        raise ActiveLearningError("threshold_width는 0보다 큰 유한한 수")
    normalized = {}
    for name in ("sealed", "calibration"):
        part = protected.get(name) if isinstance(protected, dict) else None
        if not isinstance(part, dict) or "image_shas" not in part or "group_ids" not in part:
            raise ActiveLearningError("protected에는 sealed·calibration의 image_shas·group_ids가 모두 있어야 한다")
        normalized[name] = {"image_shas": set(part["image_shas"]), "group_ids": set(part["group_ids"])}
    seen = set()
    for item in candidates:
        if any(not isinstance(item.get(k), str) or not item[k] for k in REQUIRED) or item["region_id"] in seen:
            raise ActiveLearningError("후보의 필수 문자열 필드 누락·region_id 중복: %r" % (item.get("region_id"),))
        seen.add(item["region_id"])
        numbers = [item.get(k) for k in ("score", "threshold")] + [item[k] for k in ("champion_score", "challenger_score",
                                                                                     "learning_value") if item.get(k) is not None]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in numbers):
            raise ActiveLearningError("점수는 유한한 수여야 한다: %s" % item["region_id"])
        priority, scarcity = config["error_priority"].get(item["error_type"]), config["stratum_scarcity"].get(item["stratum"])
        if not isinstance(priority, (int, float)) or priority <= 0 or not isinstance(scarcity, (int, float)) or scarcity < 0:
            raise ActiveLearningError("error_priority(>0)·stratum_scarcity(≥0)에 없는 값: %s" % item["region_id"])
    return normalized


def score(item, config):
    """선별 점수(높을수록 먼저). 모델 불확실성 = max(문턱 근처도, Champion–Challenger 점수 차이). 둘 다 [0, 1]."""
    closeness = max(0.0, 1.0 - abs(item["score"] - item["threshold"]) / config["threshold_width"])
    pair = (item.get("champion_score"), item.get("challenger_score"))
    disagreement = min(1.0, abs(pair[0] - pair[1])) if None not in pair else 0.0
    return (config["error_priority"][item["error_type"]] * config["stratum_scarcity"][item["stratum"]]
            * max(closeness, disagreement) * item.get("learning_value", 1.0))


def tiebreak(seed, label, region_id):
    """seed를 섞은 결정적 정렬 키(파이썬 난수 구현에 의존하지 않아 버전이 달라도 같다)."""
    return hashlib.sha256(("%s|%s|%s" % (seed, label, region_id)).encode("utf-8")).hexdigest()


def pick(ordered, counts, caps, limit):
    """ordered 순서대로 그룹·판매자·군집 상한을 지키며 limit개까지 고른다. counts는 호출 사이에 공유한다(전체 선별 기준 상한)."""
    out = []
    for item in ordered:
        if len(out) >= limit:
            break
        keys = (("group", item["group_id"]), ("seller", item["seller_id"]), ("cluster", item["cluster_id"]))
        if any(counts.get(k, 0) >= caps[k[0]] for k in keys):
            continue
        for k in keys:
            counts[k] = counts.get(k, 0) + 1
        out.append(item)
    return out


def route(item, expected_label, scopes):
    """승인된 Silver 정책 범위 (결함 유형, 층, 라벨 값) 안이면 'silver', 밖이면 'human'. expected_label은 라우팅에만 쓰고 큐에 남기지 않는다."""
    key = (item["defect_type"], item["stratum"], expected_label)
    return "silver" if any((s["defect_type"], s["stratum"], s["label_value"]) == key for s in scopes) else "human"


def select(candidates, protected, config, budget, seed, scopes):
    """후보에서 budget개를 고른다. 같은 입력·seed는 같은 결과. 반환의 representative는 항상 False.

    config: error_priority{오류 유형: >0}, stratum_scarcity{층: ≥0}, threshold_width, per_group_cap, per_seller_cap, cluster_quota(군집당 최대 수).
    scopes: 승인된 Silver 정책 범위 목록(없으면 모두 사람 큐).
    """
    protected = check_inputs(candidates, protected, config, budget, seed)
    excluded, pool = {"sealed": 0, "calibration": 0}, []
    for item in candidates:
        reason = protected_reason(item, protected)
        if reason is not None:
            excluded[reason] += 1
        else:
            pool.append(item)
    scores = {item["region_id"]: score(item, config) for item in pool}
    caps = {"group": config["per_group_cap"], "seller": config["per_seller_cap"], "cluster": config["cluster_quota"]}
    n_random = (budget * RANDOM_PERCENT + 50) // 100
    ranked_order = sorted((-scores[i["region_id"]], tiebreak(seed, "rank", i["region_id"]), n) for n, i in enumerate(pool))
    counts = {}
    ranked = pick([pool[n] for _, _, n in ranked_order], counts, caps, budget - n_random)
    taken = {i["region_id"] for i in ranked}
    random_order = sorted((tiebreak(seed, "random", i["region_id"]), n) for n, i in enumerate(pool) if i["region_id"] not in taken)
    rand = pick([pool[n] for _, n in random_order], counts, caps, n_random)
    selected = ([dict({k: i[k] for k in KEEP}, part="ranked", random_part=False) for i in ranked]
                + [dict({k: i[k] for k in KEEP}, part="random", random_part=True) for i in rand])
    routed = {i["region_id"]: route(i, i["expected_label"], scopes) for i in ranked + rand}
    return {"selected": selected, "silver_queue": [s for s in selected if routed[s["region_id"]] == "silver"],
            "human_queue": [s for s in selected if routed[s["region_id"]] == "human"], "representative": False,
            "random_part_ids": [s["region_id"] for s in selected if s["random_part"]], "excluded": excluded,
            "shortfall": budget - len(selected), "seed": seed, "n_candidates": len(candidates), "n_eligible": len(pool),
            "dev_eval_note": "대표 표본이 아니다: 개발 평가에는 가중 보정하거나 random_part만 쓰고 봉인 평가에는 넣지 않는다",
            "trace": {i["region_id"]: {"score": scores[i["region_id"]], "part": "ranked" if i in ranked else "random"}
                      for i in ranked + rand}}
