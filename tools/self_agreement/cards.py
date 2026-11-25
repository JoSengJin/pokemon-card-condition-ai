"""오탐 층의 카드 단위 계산 (계약 V2-D, 설계 1.2~1.5·3.2·4절).

카드 판정은 카드의 구역을 모두 가진 오탐 층에서만 낸다. 구역 폭을 카드로 곱해 옮기지 않고,
이 파일의 어떤 값도 주 지표나 다음 행동 표에 들어가지 않는다. 사람 값은 plan 인자에서만 읽는다.
"""
import random
import statistics

from tools.self_agreement import stats

VALUES = ('정상', '결함', '불가', '미확인')
CONFIRMED = ('정상', '결함')
CARD_VALUES = ('정상', '결함', '불확정')
UNKNOWN_LIMIT = '컷 상태는 어떤 것도 승인하지 않는다. 실험·라벨 변경·재요청의 근거로 쓰지 않는다.'
LIMITS = [
    '모델이 틀렸다고 본 카드를 골라 잰 것이다. 이전 라벨의 실수가 섞여 있으면 다시 재는 것만으로 값이 옮겨 갈 수 있고, '
    '무작위 카드의 흔들림이 아니다. 불일치 건만 다시 본 결과로 정답표를 고치지 않는다.',
    '지금 오탐인 카드만 본다. 다른 정상 카드에서 새 오탐이 생기거나 결함 카드가 바뀌는 크기는 보이지 않는다.',
    '카드 수가 작아 윌슨 구간이 넓고 정확 양측 검정의 판정력이 낮다. 한쪽으로만 뒤집혀도 p가 작아지지 않을 수 있다.',
    '카드 값은 제시한 구역 안의 최댓값이고 불확정 카드는 뒤집힘 계산에서 빠진다.',
    UNKNOWN_LIMIT,
]


def judge(values):
    """구역 값 목록 -> 카드 값. 결함이 하나라도 있으면 결함, 모두 정상이면 정상, 그 밖은 불확정. 빈 목록은 ValueError."""
    if not values or any(v not in VALUES for v in values):
        raise ValueError('카드의 구역 값이 비었거나 모르는 값이 있음')
    if '결함' in values:
        return '결함'
    return '정상' if all(v == '정상' for v in values) else '불확정'


def by_card(zones, first, second):
    """fp 구역 목록 -> {group: 카드 기록}. 구역이 떨어져 있어도 group으로 묶고 입력 순서를 보지 않는다."""
    grouped = {}
    for z in zones:
        k = str(z['n'])
        grouped.setdefault(z['group'], []).append((first['answers'][k], second['answers'][k]))
    out = {}
    for g, prs in grouped.items():
        a, b = judge([p[0] for p in prs]), judge([p[1] for p in prs])
        zc = [p for p in prs if p[0] in CONFIRMED and p[1] in CONFIRMED]
        out[g] = dict(pairs=prs, first=a, second=b, cc=int(a != '불확정' and b != '불확정'),
                      cf=int(a != '불확정' and b != '불확정' and a != b), zc=len(zc), zf=sum(p[0] != p[1] for p in zc))
    return out


def boot(cards, draws, seed):
    """카드 단위 재표집: 뽑힌 카드의 구역을 모두 가져온다. 자기 난수기를 새로 만들어 주 층 구간을 바꾸지 않는다."""
    keys = sorted(cards)
    rng = random.Random(seed)
    rates = dict(card_flip_rate=[], zone_flip_rate=[])
    for _ in range(draws):
        pick = [cards[k] for k in rng.choices(keys, k=len(keys))]
        for name, flip, conf in (('card_flip_rate', 'cf', 'cc'), ('zone_flip_rate', 'zf', 'zc')):
            den = sum(c[conf] for c in pick)
            if den:
                rates[name].append(sum(c[flip] for c in pick) / den)
    out = dict(draws=draws)
    for name, vals in rates.items():
        vals.sort()
        if len(vals) < 2:
            lo = hi = vals[0] if vals else None
        else:
            cuts = statistics.quantiles(vals, n=40, method='inclusive')
            lo, hi = cuts[0], cuts[38]
        out[name] = dict(lo=lo, hi=hi, undefined=draws - len(vals))
    return out


def cut_status(flips, unknown, cut):
    """4절 표: 뒤집힌 카드 총수 flips, 불확정 쌍 unknown, 컷(null이면 판정 없음)."""
    if cut is None:
        return '컷 미정, 판정 없음'
    if flips >= cut:
        return '컷 이상'
    if flips + unknown < cut:
        return '컷 미만'
    return '판정 불가(불확정 카드)'


def summary(selection, first, second, plan):
    """result.json의 fp_layer. 구역 수·카드당 구역 수가 plan과 다르면 ValueError."""
    zones = [z for z in selection['zones'] if z['layer'] == 'fp']
    cards = by_card(zones, first, second)
    if len(zones) != plan['fp_count'] or any(len(c['pairs']) != plan['fp_zones_per_card'] for c in cards.values()):
        raise ValueError('fp 구역 수가 plan의 fp_count·fp_zones_per_card와 다름')
    prs = [p for c in cards.values() for p in c['pairs']]
    zconf = [p for p in prs if p[0] in CONFIRMED and p[1] in CONFIRMED]
    n, flips = sum(c['cc'] for c in cards.values()), sum(c['cf'] for c in cards.values())
    mc = stats.MCNEMAR({g: c['first'] == '결함' for g, c in cards.items() if c['cc']},
                       {g: c['second'] == '결함' for g, c in cards.items() if c['cc']})
    lo, hi = stats.WILSON(flips, n) if n else (None, None)
    return dict(
        zones=dict(start=len(prs), first_unusable=sum(a not in CONFIRMED for a, _ in prs),
                   second_unusable=sum(b not in CONFIRMED for _, b in prs),
                   one_round_only=sum((a in CONFIRMED) != (b in CONFIRMED) for a, b in prs),
                   confirmed_pairs=len(zconf), same_answer=sum(a == b for a, b in zconf),
                   b=sum(p == ('정상', '결함') for p in zconf), c=sum(p == ('결함', '정상') for p in zconf)),
        cards=dict(start=len(cards), zones_per_card=plan['fp_zones_per_card'], rule=plan['card_rule'],
                   first={v: sum(c['first'] == v for c in cards.values()) for v in CARD_VALUES},
                   second={v: sum(c['second'] == v for c in cards.values()) for v in CARD_VALUES},
                   confirmed_pairs=n, unchanged=n - flips, b=mc['worse_b'], c=mc['better_c'], flips=flips,
                   unknown_pairs=len(cards) - n,
                   wilson95=[max(0., lo), min(1., hi)] if n else None,
                   exact_upper=1 - 0.025 ** (1 / n) if n and flips == 0 else None,
                   exact_two_sided_p=mc['exact_two_sided_p'] if n else None),
        bootstrap=boot(cards, plan['bootstrap_draws'], plan['seed_bootstrap']),
        flip_cut=dict(cut=plan['card_flip_cut'], status=cut_status(flips, len(cards) - n, plan['card_flip_cut'])),
        main_layer_cards='해당 없음(카드당 구역 1개)', limits=LIMITS)
