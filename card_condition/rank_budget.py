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
