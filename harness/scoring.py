"""채점: 판단 보류(abstain)를 사람 확인 경보로 센다(설계 2절 원칙 3, 6-1). 순수 함수, stdlib만 쓴다.

- 결함 구역: pred가 normal이면 누락(miss). defect·abstain은 경보를 울린 것(hit).
- 정상 구역: pred가 defect 또는 abstain이면 오탐(false_alarm). normal이면 correct.
- truth가 pending인 구역은 어떤 분모에도 넣지 않는다. 분모가 0이면 숫자를 만들지 않고 "미측정"으로 표시한다.
"""
from itertools import groupby
from operator import itemgetter

from .scoring_rows import validate_rows

UNMEASURED = "미측정"
ABSTAIN_MARGIN = 0.05    # D-6: 기준 모델 층(stratum)별 보류율 +5%p 이내
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
    """key(pred_a/pred_b) 모델의 개수 집계. strata = {층: [Gold 구역 수, 보류 수]}."""
    counts = {"defect": 0, "normal": 0, "miss": 0, "false_alarm": 0, "abstain": 0, "strata": {}}
    for row in rows:
        stratum = counts["strata"].setdefault(row["stratum"], [0, 0])
        kind = error_kind(row["truth"], row[key])
        if kind is None:
            continue
        counts[row["truth"]] += 1
        stratum[0] += 1
        if row[key] == "abstain":
            counts["abstain"] += 1
            stratum[1] += 1
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
    """한 모델의 누락률·오탐률·Coverage·층(stratum)별 보류율·위험-Coverage와 각 분모."""
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
        "abstain_by_stratum": {stratum: rate(found[1], found[0]) for stratum, found in sorted(counts["strata"].items())},
        "risk_coverage": risk_coverage(rows, key),
    }


def abstain_cap(base, cand, margin=ABSTAIN_MARGIN, absolute=ABSTAIN_ABSOLUTE):
    """D-6 층(stratum)별 보류율 상한: 후보 ≤ min(기준 + margin, absolute). 분모 0인 층은 unmeasured에 따로 적는다."""
    out = {"checked": [], "unmeasured": [], "violations": []}
    for stratum, current in cand["abstain_by_stratum"].items():
        ref = base["abstain_by_stratum"].get(stratum, {"rate": UNMEASURED})
        if UNMEASURED in (current["rate"], ref["rate"]):
            out["unmeasured"].append(stratum)
            continue
        limit = min(ref["rate"] + margin, absolute)
        out["checked"].append(stratum)
        if current["rate"] > limit + _TOLERANCE:
            out["violations"].append({"stratum": stratum, "candidate": current["rate"], "baseline": ref["rate"], "limit": limit})
    return out


def improvement_split(rows):
    """개선량(A 누락률 − B 누락률)을 결함 구역 단위로 나눠 보고한다. 판정에는 쓰지 않는다(사용자 결정 대기).

    A는 놓쳤는데 B가 보류로 바꾼 구역 / B가 결함으로 맞힌 구역 / A는 경보였는데 B가 정상으로 바꾼(악화) 구역.
    """
    counts = {"abstain": 0, "correct": 0, "worsened": 0}
    defect_n = 0
    for row in rows:
        if row["truth"] != "defect":
            continue
        defect_n += 1
        miss_a, miss_b = error_kind("defect", row["pred_a"]) == "miss", error_kind("defect", row["pred_b"]) == "miss"
        if miss_a and not miss_b:
            counts["abstain" if row["pred_b"] == "abstain" else "correct"] += 1
        elif miss_b and not miss_a:
            counts["worsened"] += 1
    gross = counts["abstain"] + counts["correct"]
    return {"defect_n": defect_n,
            "improvement_from_abstain_zones": rate(counts["abstain"], defect_n),
            "improvement_from_correct_zones": rate(counts["correct"], defect_n),
            "worsened_zones": rate(counts["worsened"], defect_n),
            "abstain_share_of_gross_gain": rate(counts["abstain"], gross)}
