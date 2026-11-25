"""두 회차 답으로 제안서 10·11절의 수와 다음 행동 한 행을 낸다 (계약 D).

실행: python -m tools.self_agreement.score_rounds PLAN SELECTION ROUND1 ROUND2 OUT
종료 0=OUT에 새 result.json 작성, 2=입력 문제(아무것도 쓰지 않음). 해시 불일치도 종료 2이며
이유에 1행 조건으로 적는다. 사진·라벨 파일은 열지 않고 어느 행도 실험·재요청을 승인하지 않는다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from tools.self_agreement import decide, plan as cfg, stats

VALUES = ('정상', '결함', '불가', '미확인')
CONFIRMED, THREE = ('정상', '결함'), ('정상', '결함', '불가')
LIMITS = [
    '두 번 함께 틀리는 버릇과 기억 효과는 e를 과소 추정하게 할 수 있다.',
    '정상 쪽 오류율과 결함 쪽 오류율이 다르면 두 회차만으로 따로 식별되지 않는다.',
    '현행 기준에서 잰 e를 다른 기준으로 매긴 과거 평가 라벨에 그대로 옮길 수 없다.',
    '자기 일치도의 e는 정답 대비 오류율이 아니라 독립·대칭 가정 아래의 대용치다.',
    '모델이 같은 판정자의 라벨로 학습돼 모델 오류와 라벨 오류의 독립 가정도 의심된다.',
]
NOT_APPROVAL = '어느 행도 실험·라벨 변경·재요청을 승인하지 않는다. 결과를 본 뒤 규칙을 바꾸지 않는다.'


def pairs(selection, first, second, layer):
    """layer('main'|'error')의 구역마다 (1차 값, 2차 값). 번호·값·회차가 어긋나면 ValueError."""
    zones = selection['zones']
    want = {str(z['n']) for z in zones}
    if len(want) != len(zones) or any(z['layer'] not in ('main', 'error') for z in zones):
        raise ValueError('selection의 번호가 겹치거나 layer가 main·error가 아님')
    if (first['round'], second['round']) != (1, 2):
        raise ValueError('ROUND1·ROUND2의 round가 1·2가 아님')
    for rd in (first, second):
        if set(rd['answers']) != want or any(v not in VALUES for v in rd['answers'].values()):
            raise ValueError('답 번호가 selection과 다르거나 모르는 값이 있음')
    return [(first['answers'][str(z['n'])], second['answers'][str(z['n'])]) for z in zones if z['layer'] == layer]


def measures(prs, plan):
    """주 층 (1차, 2차) 목록의 모든 수. 카파는 Fraction."""
    conf = [p for p in prs if p[0] in CONFIRMED and p[1] in CONFIRMED]
    three = [p for p in prs if '미확인' not in p]
    t, n = stats.table(conf), len(conf)
    mc = stats.MCNEMAR({i: a == '결함' for i, (a, _) in enumerate(conf)}, {i: b == '결함' for i, (_, b) in enumerate(conf)})
    return dict(
        counts=dict(start=len(prs), first_unusable=sum(a not in CONFIRMED for a, _ in prs),
                    second_unusable=sum(b not in CONFIRMED for _, b in prs),
                    one_round_only=sum((a in CONFIRMED) != (b in CONFIRMED) for a, b in prs),
                    confirmed_pairs=n, unconfirmed_excluded_from_three=len(prs) - len(three)),
        table=t, table3=Counter(three), kappa=stats.kappa(conf, CONFIRMED), kappa3=stats.kappa(three, THREE),
        interval=stats.interval(conf, plan['bootstrap_draws'], plan['seed_bootstrap']) if n else None,
        p=mc['exact_two_sided_p'], error=stats.error_rate(t[2] + t[3], n) if n else None)


def report(plan, shas, selection, first, second):
    """result.json 내용. 해시가 어긋나면 ValueError('1행 조건: …')."""
    reasons = decide.invalid(plan, shas, first, second)
    if selection['plan_sha256'] != shas[0]:
        reasons.insert(0, '해시 불일치: selection plan_sha256')
    if any(r.startswith('해시 불일치') for r in reasons):
        raise ValueError('1행 조건: ' + '; '.join(reasons))
    m = measures(pairs(selection, first, second, 'main'), plan)
    row, why = decide.row(reasons, m['table'], m['kappa'], plan, m['p'])
    err = [p for p in pairs(selection, first, second, 'error') if p[0] in CONFIRMED and p[1] in CONFIRMED]
    nn, dd, b, c = m['table']
    er, show = m['error'], row >= 3
    kap = {k: (None if v is None else dict(fraction=str(v), value=float(v)))
           for k, v in (('binary', m['kappa']), ('three_class', m['kappa3'])) if show}
    full = row >= 4 and er is not None and er['e'] is not None
    return {
        'plan_sha256': shas[0], 'selection_sha256': shas[1], 'row': row, 'row_text': decide.ROW_TEXT[row],
        'reasons': why, 'counts': m['counts'],
        '확정 쌍 일치율': dict(k=nn + dd, n=sum(m['table']), rate=(nn + dd) / sum(m['table']),
                         wilson95=[1 - er['d_wilson'][1], 1 - er['d_wilson'][0]]) if show else None,
        'table': dict(normal_normal=nn, defect_defect=dd, b=b, c=c) if show else None,
        'table3': {'%s>%s' % k: v for k, v in sorted(m['table3'].items())} if show else None,
        'kappa': kap or None, 'kappa_interval': m['interval'] if show else None,
        'b': b if show else None, 'c': c if show else None,
        'b_ratio': (b / (b + c) if b + c else '해당 없음') if show else None,
        'exact_two_sided_p': m['p'] if show else None,
        'd': er if show else None, 'e': er['e'] if full else None,
        'e_interval': er['e_interval'] if full else None,
        'reference_zone_width': er['e_interval'][1] * plan['reference_zone_count']
        if full and plan['reference_zone_count'] else None,
        'card_conversion': '미측정',
        'error_layer': dict(start=len(pairs(selection, first, second, 'error')), confirmed_pairs=len(err),
                            same_answer=sum(p[0] == p[1] for p in err)),
        'limits': LIMITS, 'not_approval': NOT_APPROVAL,
    }


def main(argv):
    """종료 코드를 돌려준다. 0=result.json 1개 작성, 2=아무것도 쓰지 않음."""
    try:
        if len(argv) != 5:
            raise ValueError('인자: PLAN SELECTION ROUND1 ROUND2 OUT')
        plan, psha = cfg.load(argv[0])
        docs = [json.loads(Path(x).read_text(encoding='utf-8')) for x in argv[1:4]]
        res = report(plan, (psha, cfg.file_sha(argv[1])), *docs)
        cfg.write_new(argv[4], res)
    except (ValueError, KeyError, TypeError, OSError) as e:
        print('오류: %s %s' % (type(e).__name__, str(e).replace('\n', ' ')), file=sys.stderr)
        return 2
    print('행=%d %s / %s' % (res['row'], res['row_text'], ' | '.join(res['reasons'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
