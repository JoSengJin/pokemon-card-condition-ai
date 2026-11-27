"""승격 판정 사유 모음. 깨진 조건을 코드와 함께 돌려준다. 분모 0(미측정)은 통과로 세지 않고 사유로 남긴다."""

_TOLERANCE = 1e-12


def why(code, message):
    return {"code": code, "message": message}


def bootstrap_reasons(boot, sens, config):
    """카드 단위 부트스트랩 하한, 결함 카드 수·버린 재표집 비율, 민감도(공허 포함)."""
    out = []
    lower = boot["lower"]
    if not isinstance(lower, float):
        out.append(why("bootstrap_unmeasured", "결함 구역이 없어 누락 감소를 측정할 수 없다"))
    elif not lower > 0:
        out.append(why("bootstrap_lower_not_positive", "카드 단위 부트스트랩 80%% 구간 하한 %.4f이 0보다 크지 않다" % lower))
    if boot["defect_cards"] < config["min_defect_cards"]:
        out.append(why("bootstrap_too_few_cards", "결함 구역을 가진 카드 %d장 < 최소 %d장(재표집이 한두 장에 좌우된다)" % (
            boot["defect_cards"], config["min_defect_cards"])))
    kept_fraction = boot["valid_replicates"] / boot["replicates"]
    if kept_fraction < config["min_valid_fraction"]:
        out.append(why("bootstrap_too_many_discarded", "결함 구역 없는 재표집을 버리고 남은 비율 %.4f < 최소 %.4f" % (
            kept_fraction, config["min_valid_fraction"])))
    if sens["n_uncertain"] == 0:
        out.append(why("sensitivity_vacuous", "uncertain 표시가 없어 민감도 검사가 평가되지 않았다"))
    if isinstance(boot["point"], float) and sens["fraction"] < config["direction_min_fraction"]:
        out.append(why("direction_unstable", "라벨 잡음 시행에서 개선 방향 유지 비율 %.4f < 기준 %.4f" % (
            sens["fraction"], config["direction_min_fraction"])))
    return out


def alarm_reasons(base, cand, cap, delta):
    """오탐 비열등(점추정 차이 ≤ delta, 구간 검정은 확증 단계 몫)과 D-6 층별 보류율 상한."""
    out = []
    rate_b, rate_c = base["false_alarm"]["rate"], cand["false_alarm"]["rate"]
    if not (isinstance(rate_b, float) and isinstance(rate_c, float)):
        out.append(why("false_alarm_unmeasured", "정상 구역이 없어 오탐 비열등을 측정할 수 없다"))
    elif rate_c - rate_b > delta + _TOLERANCE:
        out.append(why("false_alarm_not_noninferior", "후보 오탐률 %.4f − 기준 %.4f > 허용 %.4f" % (rate_c, rate_b, delta)))
    if not cap["checked"]:
        out.append(why("abstain_unmeasured", "보류율을 측정한 층이 없다"))
    for item in cap["violations"]:
        out.append(why("abstain_cap", "층 %s 보류율 %.4f > 상한 %.4f(기준 %.4f)" % (
            item["stratum"], item["candidate"], item["limit"], item["baseline"])))
    return out
