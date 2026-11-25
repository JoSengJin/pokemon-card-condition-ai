"""자기 일치도 점수의 순수 계산 (계약 D).

카파는 Fraction으로 돌려주고 비교도 Fraction으로 한다(소수 비교는 경계값에서 틀림).
윌슨·정확 양측 검정은 기존 진단 파일의 식을 그대로 읽어 쓴다(수정 없음).
"""
import importlib.util
import math
import random
import statistics
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ('정상', '결함')


def borrow(rel, name):
    """이름에 '-'가 든 진단 폴더의 파일을 경로로 읽는다."""
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WILSON = borrow('tools/diagnostics/corner-rejudge-20261121/score.py', 'self_agreement_score_src').wilson
MCNEMAR = borrow('tools/diagnostics/corner-chance-check-20261124/check.py', 'self_agreement_check_src').mcnemar


def table(pairs):
    """확정 쌍 (1차, 2차) 목록 -> (정상-정상, 결함-결함, b, c). b=1차 정상->2차 결함, c=반대."""
    return tuple(sum(p == q for p in pairs) for q in (('정상', '정상'), ('결함', '결함'), ('정상', '결함'), ('결함', '정상')))


def kappa(pairs, classes):
    """코헨 카파를 정확한 분수로. 쌍이 없거나 우연 일치가 1이면 None(정의 불가)."""
    n = len(pairs)
    if n == 0:
        return None
    po = Fraction(sum(a == b for a, b in pairs), n)
    pe = sum(Fraction(sum(a == c for a, _ in pairs) * sum(b == c for _, b in pairs), n * n) for c in classes)
    return None if pe == 1 else (po - pe) / (1 - pe)


def interval(pairs, draws, seed):
    """카드 단위(주 층은 카드당 구역 1개라 쌍과 같음) 재표집 카파의 백분위 2.5·97.5."""
    rng = random.Random(seed)
    vals = [k for k in (kappa(rng.choices(pairs, k=len(pairs)), CLASSES) for _ in range(draws)) if k is not None]
    vals = sorted(float(k) for k in vals)
    if len(vals) < 2:
        lo = hi = vals[0] if vals else None
    else:
        cuts = statistics.quantiles(vals, n=40, method='inclusive')
        lo, hi = cuts[0], cuts[38]
    return dict(lo=lo, hi=hi, draws=draws, undefined=draws - len(vals))


def error_rate(k, n):
    """불일치 k, 확정 쌍 n: d의 윌슨 구간과 e=(1-sqrt(1-2d))/2. d>=0.5이면 e와 구간은 None."""
    lo, hi = WILSON(k, n)
    out = dict(d=k / n, d_wilson=[max(0., lo), min(1., hi)], e=None, e_interval=None, upper_clipped=None,
               exact_upper=1 - 0.025 ** (1 / n) if k == 0 else None)
    if k / n < .5:
        e, e_lo, e_hi = [(1 - math.sqrt(max(0., 1 - 2 * x))) / 2 for x in (k / n, max(0., lo), min(hi, .5))]
        out.update(e=e, e_interval=[e_lo, e_hi], upper_clipped=hi > .5)
    return out
