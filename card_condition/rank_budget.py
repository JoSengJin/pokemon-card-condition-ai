"""점수 순위 + 점검 예산 출력(개발용 평가). 운영 경로 미연결, 모델 호출·PokeCollector·Gemini 참조 없음."""
import math

NOTE = dict(development_evaluation=True, independent_validation=False)


def _check(scores, ids, groups, k_fraction, train_groups):
    if not (len(scores) == len(ids) == len(groups)) or not scores:
        raise ValueError('inputs must be non-empty and equal length')
    if not all(isinstance(s, (int, float)) and math.isfinite(s) for s in scores):
        raise ValueError('scores must be finite numbers')
    if len(set(ids)) != len(ids):
        raise ValueError('ids must be unique')
    if not 0 < k_fraction <= 1:
        raise ValueError('k_fraction must be in (0, 1]')
    if set(groups) & set(train_groups):
        raise ValueError('group leakage: evaluated groups overlap training groups')


def _rank(scores, ids):
    """점수 내림차순, 동률은 id 오름차순(입력 순서 무관)."""
    return sorted(range(len(ids)), key=lambda i: (-scores[i], str(ids[i])))


def rank_budget_report(scores, ids, groups, k_fraction, *, train_groups=(), label_reliability_interval):
    """상위 k_fraction(올림) 구역을 점검 대상으로 반환. label_reliability_interval은 필수 필드(예: (0.234, 0.688))."""
    _check(scores, ids, groups, k_fraction, train_groups)
    if len(label_reliability_interval) != 2 or not all(math.isfinite(x) for x in label_reliability_interval):
        raise ValueError('label_reliability_interval must be two finite numbers')
    top = _rank(scores, ids)[:math.ceil(len(ids) * k_fraction)]
    inspect = [dict(id=ids[i], score=scores[i], rank=r + 1, reason='rank_budget_top_k') for r, i in enumerate(top)]
    return dict(NOTE, k_fraction=k_fraction, checked=len(inspect), total=len(ids),
                label_reliability_interval=list(label_reliability_interval), inspect=inspect)


def card_scores(scores, groups):
    """카드(그룹) 점수 = 소속 구역 최고 점수."""
    out = {}
    for s, g in zip(scores, groups):
        out[g] = max(s, out.get(g, -math.inf))
    return out


def _wilson_upper(k, n, z=1.6448536269514722):
    p = k / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def card_operating_points(scores, groups, targets, thresholds, *, label_reliability_interval):
    """카드 단위(구역 최고 점수) 임계별 결함 카드 회수·정상 카드 오경보. targets는 구역 0/1, 카드 결함=구역 중 하나라도 1."""
    if not (len(scores) == len(groups) == len(targets)) or not scores:
        raise ValueError('inputs must be non-empty and equal length')
    if not all(isinstance(s, (int, float)) and math.isfinite(s) for s in scores) or any(t not in (0, 1) for t in targets):
        raise ValueError('scores must be finite and targets 0/1')
    if len(label_reliability_interval) != 2 or not all(math.isfinite(x) for x in label_reliability_interval):
        raise ValueError('label_reliability_interval must be two finite numbers')
    cs = card_scores(scores, groups)
    bad = {g: max(t for t, h in zip(targets, groups) if h == g) for g in cs}
    pos, neg = [cs[g] for g in cs if bad[g]], [cs[g] for g in cs if not bad[g]]
    if not pos or not neg:
        raise ValueError('need both defect and normal cards')
    points = []
    for t in thresholds:
        hit, fa = sum(x >= t for x in pos), sum(x >= t for x in neg)
        points.append(dict(threshold=t, defect_cards_found=f'{hit}/{len(pos)}', recall=hit / len(pos), recall_miss_upper95=_wilson_upper(len(pos) - hit, len(pos)),
                           normal_cards_flagged=f'{fa}/{len(neg)}', false_alarm=fa / len(neg), false_alarm_upper95=_wilson_upper(fa, len(neg))))
    return dict(NOTE, unit='card', defect_cards=len(pos), normal_cards=len(neg), label_reliability_interval=list(label_reliability_interval), points=points)
