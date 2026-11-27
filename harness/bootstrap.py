"""승격 판정용 통계: 실물 카드 단위 짝지은 부트스트랩과 라벨 잡음 민감도(설계 6-3). 순수 함수, stdlib만 쓴다.

개선량 = A 누락률 − B 누락률(같은 구역, 결함 구역 분모). A=기준(pred_a), B=후보(pred_b).
"""
import random
from operator import itemgetter

from .scoring import UNMEASURED, error_kind


def percentile(values, q):
    """q(0~1) 백분위. 정렬 후 (n-1)*q 위치를 선형 보간한다."""
    if not values:
        raise ValueError("빈 값 목록의 백분위는 없다")
    data = sorted(values)
    position = q * (len(data) - 1)
    low = int(position)
    high = min(low + 1, len(data) - 1)
    return data[low] + (data[high] - data[low]) * (position - low)


def improvement(defect_n, miss_a, miss_b):
    return UNMEASURED if defect_n == 0 else (miss_a - miss_b) / defect_n


def totals(rows, truths=None):
    """(결함 구역 수, A 누락 수, B 누락 수). truths가 있으면 행별 truth를 그 값으로 대신한다."""
    defect = miss_a = miss_b = 0
    for index, row in enumerate(rows):
        truth = row["truth"] if truths is None else truths[index]
        if truth == "defect":
            defect += 1
            miss_a += error_kind(truth, row["pred_a"]) == "miss"
            miss_b += error_kind(truth, row["pred_b"]) == "miss"
    return defect, miss_a, miss_b


def paired_bootstrap(rows, replicates, seed, quantile=0.10):
    """카드 그룹 단위 재표집(복원추출)으로 개선량 분포를 만들고 quantile 백분위를 하한으로 돌려준다."""
    by_card = {}
    for row in rows:
        by_card.setdefault(row["card_group"], []).append(row)
    stats = [totals(by_card[card]) for card in sorted(by_card)]
    rng = random.Random(seed)
    values = []
    for _ in range(replicates):
        picks = rng.choices(stats, k=len(stats))
        value = improvement(*(sum(column) for column in zip(*picks)))
        if isinstance(value, float):
            values.append(value)
    return {"point": improvement(*totals(rows)), "lower": percentile(values, quantile) if values else UNMEASURED,
            "quantile": quantile, "replicates": replicates, "valid_replicates": len(values),
            "n_cards": len(stats), "seed": seed}


def flip_truths(rows, noise_rate, rng):
    """uncertain 구역의 truth(defect↔normal)를 noise_rate 확률로 독립적으로 뒤집은 목록. pending은 그대로."""
    swap = {"defect": "normal", "normal": "defect"}
    return [swap[row["truth"]] if row["truth"] in swap and row.get("uncertain", False) and rng.random() < noise_rate
            else row["truth"] for row in rows]


def sensitivity(rows, noise_rate, trials, seed):
    """라벨 잡음 시행 trials회 중 개선량 > 0이 유지되는 비율. 분모가 사라진 시행은 유지 못 한 것으로 센다."""
    ordered = sorted(rows, key=itemgetter("id"))
    rng = random.Random(seed)
    kept, unmeasured, worst = 0, 0, None
    for _ in range(trials):
        value = improvement(*totals(ordered, flip_truths(ordered, noise_rate, rng)))
        if not isinstance(value, float):
            unmeasured += 1
            continue
        kept += value > 0
        worst = value if worst is None else min(worst, value)
    return {"noise_rate": noise_rate, "trials": trials, "seed": seed, "maintained": kept,
            "fraction": kept / trials, "unmeasured_trials": unmeasured,
            "min_improvement": UNMEASURED if worst is None else worst,
            "n_uncertain": sum(1 for row in rows if row.get("uncertain", False))}
