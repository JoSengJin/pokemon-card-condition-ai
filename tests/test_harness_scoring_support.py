"""채점·승격 시험 공용 합성 구역 생성기(시험 없음). 합성 후보이며 모델 성능 근거가 아니다."""

ZONES = ("defect", "defect", "normal", "normal")  # 카드 하나에 결함 2·정상 2 구역


def predict(truth, card, spec):
    """spec: miss/fa/abs_defect/abs_normal = 해당 카드 번호 집합(range 가능). 결함 구역은 보류 > 누락 > 정상 판정 순."""
    if truth == "defect":
        if card in spec.get("abs_defect", ()):
            return "abstain"
        return "normal" if card in spec.get("miss", ()) else "defect"
    if card in spec.get("abs_normal", ()):
        return "abstain"
    return "defect" if card in spec.get("fa", ()) else "normal"


def make_rows(spec_a, spec_b, cards=100, uncertain=(), zones=ZONES):
    """카드 i의 모든 구역이 같은 stratum(짝수=front, 홀수=back)·eval_tier=dev에 속한다. uncertain 카드의 결함 구역만 uncertain 표시."""
    rows = []
    for card in range(cards):
        for index, truth in enumerate(zones):
            rows.append({"id": "c%03dz%d" % (card, index), "card_group": "card%03d" % card,
                         "eval_tier": "dev", "stratum": "front" if card % 2 == 0 else "back", "truth": truth,
                         "pred_a": predict(truth, card, spec_a), "pred_b": predict(truth, card, spec_b),
                         "uncertain": card in uncertain and truth == "defect"})
    return rows


def row(row_id, truth, pred_a="normal", pred_b="normal", card="g1", stratum="S1", tier="dev", **extra):
    """시험 한 줄용 행."""
    return dict(id=row_id, card_group=card, eval_tier=tier, stratum=stratum, truth=truth, pred_a=pred_a, pred_b=pred_b, **extra)


def clustered(cards, zones, improved):
    """결함 구역만: improved개 카드는 A가 전부 놓치고 B가 전부 잡는다. 나머지는 둘 다 잡는다."""
    return [row("c%dz%d" % (c, z), "defect", "normal" if c < improved else "defect", "defect", card="card%d" % c)
            for c in range(cards) for z in range(zones)]


def uneven():
    """카드마다 결함 구역 수가 달라(1~5) 부트스트랩 값이 연속적으로 흩어지는 자료. 카드당 첫 구역은 uncertain."""
    return [row("c%dz%d" % (c, z), "defect", "normal" if c % 3 else "defect", "defect", card="card%d" % c, uncertain=(z == 0))
            for c in range(40) for z in range(c % 5 + 1)]


def codes(result):
    return [reason["code"] for reason in result["reasons"]]
