"""구역 행 검증과 층 사이 실물 카드 중복 검사(설계 6-5). 순수 함수, stdlib만 쓴다.

행 = dict(id, card_group, layer, truth, pred_a, pred_b, 선택: score, uncertain).
"""
import math

TRUTHS = ("defect", "normal", "pending")
PREDS = ("defect", "normal", "abstain")


def validate_rows(rows):
    """형식이 어긋나면 ValueError(추정해서 고치지 않는다)."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows는 비어 있지 않은 리스트여야 한다")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("행은 dict여야 한다: %r" % (row,))
        for name in ("id", "card_group", "layer"):
            if not isinstance(row.get(name), str) or not row[name]:
                raise ValueError("행 %r의 %s는 비어 있지 않은 문자열이어야 한다" % (row.get("id"), name))
        if row["id"] in seen:
            raise ValueError("행 id가 중복이다: %s" % row["id"])
        seen.add(row["id"])
        if row.get("truth") not in TRUTHS or row.get("pred_a") not in PREDS or row.get("pred_b") not in PREDS:
            raise ValueError("행 %s의 truth/pred_a/pred_b 값이 허용 범위 밖이다" % row["id"])
        score = row.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)):
            raise ValueError("행 %s의 score는 유한한 숫자여야 한다" % row["id"])
        if not isinstance(row.get("uncertain", False), bool):
            raise ValueError("행 %s의 uncertain은 bool이어야 한다" % row["id"])


def check_group_overlap(rows):
    """같은 실물 카드 그룹이 둘 이상의 층에 있으면 ValueError(설계 6-5)."""
    validate_rows(rows)
    layers = {}
    for row in rows:
        layers.setdefault(row["card_group"], set()).add(row["layer"])
    clashes = {group: sorted(found) for group, found in layers.items() if len(found) > 1}
    if clashes:
        detail = "; ".join("%s: %s" % (group, "/".join(clashes[group])) for group in sorted(clashes))
        raise ValueError("같은 실물 카드 그룹이 여러 층에 있다: " + detail)
