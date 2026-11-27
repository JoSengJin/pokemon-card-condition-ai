"""채점: 판단 보류(abstain)를 사람 확인 경보로 센다(설계 2절 원칙 3, 6-1). 순수 함수, stdlib만 쓴다.

- 결함 구역: pred가 normal이면 누락(miss). defect·abstain은 경보를 울린 것(hit).
- 정상 구역: pred가 defect 또는 abstain이면 오탐(false_alarm). normal이면 correct.
- truth가 pending인 구역은 어떤 분모에도 넣지 않는다. 분모가 0이면 숫자를 만들지 않고 "미측정"으로 표시한다.
"""
from itertools import groupby
from operator import itemgetter

from .scoring_rows import validate_rows

UNMEASURED = "미측정"
ABSTAIN_MARGIN = 0.05    # D-6: 기준 모델 층별 보류율 +5%p 이내
ABSTAIN_ABSOLUTE = 0.20  # D-6: 절대 상한 20%
_TOLERANCE = 1e-12       # 부동소수점 경계 비교용


def error_kind(truth, pred):
    """한 구역의 판정 결과: miss | hit | false_alarm | correct, pending이면 None."""
    if truth == "pending":
        return None
    if truth == "defect":
        return "miss" if pred == "normal" else "hit"
    return "correct" if pred == "normal" else "false_alarm"


def rate(num, den):
    """분모 0이면 rate는 숫자가 아니라 "미측정"."""
    return {"num": num, "den": den, "rate": UNMEASURED if den == 0 else num / den}


def tally(rows, key):
    """key(pred_a/pred_b) 모델의 개수 집계. layers = {층: [Gold 구역 수, 보류 수]}."""
    counts = {"defect": 0, "normal": 0, "miss": 0, "false_alarm": 0, "abstain": 0, "layers": {}}
    for row in rows:
        layer = counts["layers"].setdefault(row["layer"], [0, 0])
        kind = error_kind(row["truth"], row[key])
        if kind is None:
            continue
        counts[row["truth"]] += 1
        layer[0] += 1
        if row[key] == "abstain":
            counts["abstain"] += 1
            layer[1] += 1
        if kind in ("miss", "false_alarm"):
            counts[kind] += 1
    return counts


def risk_coverage(rows, key):
    """점수 높은 순으로 판정(보류 아님)을 누적한 위험-Coverage 점 목록. 점수가 없으면 "미측정"."""
    kept = [(row.get("score"), error_kind(row["truth"], row[key]) in ("miss", "false_alarm"))
            for row in rows if row["truth"] != "pending" and row[key] != "abstain"]
    if not kept or any(score is None for score, _ in kept):
        return UNMEASURED
    gold = sum(1 for row in rows if row["truth"] != "pending")
    kept.sort(key=itemgetter(0), reverse=True)
    points, count, errors = [], 0, 0
    for score, group in groupby(kept, key=itemgetter(0)):
        for _, wrong in group:
            count += 1
            errors += wrong
        points.append({"threshold": score, "kept": count, "coverage": count / gold, "risk": errors / count})
    return points


def report(rows, key):
    """한 모델의 누락률·오탐률·Coverage·층별 보류율·위험-Coverage와 각 분모."""
    validate_rows(rows)
    if key not in ("pred_a", "pred_b"):
        raise ValueError("key는 pred_a 또는 pred_b여야 한다: %r" % (key,))
    counts = tally(rows, key)
    gold = counts["defect"] + counts["normal"]
    return {
        "key": key, "gold_n": gold, "defect_n": counts["defect"], "normal_n": counts["normal"],
        "pending_n": len(rows) - gold,
        "miss": rate(counts["miss"], counts["defect"]),
        "false_alarm": rate(counts["false_alarm"], counts["normal"]),
        "coverage": rate(gold - counts["abstain"], gold),
        "abstain_by_layer": {layer: rate(found[1], found[0]) for layer, found in sorted(counts["layers"].items())},
        "risk_coverage": risk_coverage(rows, key),
    }


def abstain_cap(base, cand, margin=ABSTAIN_MARGIN, absolute=ABSTAIN_ABSOLUTE):
    """D-6 층별 보류율 상한: 후보 ≤ min(기준 + margin, absolute). 분모 0인 층은 unmeasured에 따로 적는다."""
    out = {"checked": [], "unmeasured": [], "violations": []}
    for layer, current in cand["abstain_by_layer"].items():
        ref = base["abstain_by_layer"].get(layer, {"rate": UNMEASURED})
        if UNMEASURED in (current["rate"], ref["rate"]):
            out["unmeasured"].append(layer)
            continue
        limit = min(ref["rate"] + margin, absolute)
        out["checked"].append(layer)
        if current["rate"] > limit + _TOLERANCE:
            out["violations"].append({"layer": layer, "candidate": current["rate"], "baseline": ref["rate"], "limit": limit})
    return out
