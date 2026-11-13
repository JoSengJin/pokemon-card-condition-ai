"""사전 등록(card-a-eval-prereg-20261113.md) 규칙대로 A 기준 카드 단위 회수·오경보 분석. 새 추론 0."""
import json, collections, numpy as np
from collections import Counter
O = 'artifacts/card-a-eval-20261113'; S = json.load(open(f'{O}/sample_meta.json')); zones = S['zones']; cards = {c['group']: c for c in S['cards']}
J = collections.defaultdict(list)
for n in (1, 2, 3):
    for b in range(1, 15):
        exp = json.load(open(f'{O}/R{n}_b{b}.json'))['codes']; d = json.load(open(f'{O}/responses/R{n}_b{b}.json'))
        assert [r['code'] for r in d['responses']] == exp, (n, b)
        for r in d['responses']: J[r['code']].append(r['judgment'])
def cons(js):
    v = Counter(js).most_common(); return v[0][0] if v[0][1] >= 2 else 'split'
zc = {}
for z in zones:
    if z['existing'] is not None: zc[z['id']] = z['existing']
    else: assert len(J[z['code']]) == 3; zc[z['id']] = cons(J[z['code']])
byc = collections.defaultdict(list)
for z in zones: byc[z['group']].append(z)
card = {}
for g, zs in byc.items():
    c = [zc[z['id']] for z in zs]; d = sum(x == 'defect' for x in c); u = sum(x in ('unknown', 'split') for x in c)
    card[g] = 'defect' if d >= 1 else ('normal' if u <= 2 else 'undetermined')
    cards[g]['score'] = max(z['score'] for z in zs); cards[g]['a'] = card[g]
und = [g for g in card if card[g] == 'undetermined']
use = [g for g in card if card[g] != 'undetermined']
out = dict(cards=len(card), undetermined=len(und), undetermined_share=round(len(und) / len(card), 3), by_stratum_a={s: dict(Counter(card[g] for g in card if cards[g]['stratum'] == s)) for s in ('defect', 'normal')},
           zone_consensus=dict(Counter(zc.values())))
rng = np.random.default_rng(20261113)
def metrics(gs, t):
    # 층 크기 가중: 각 카드 가중치 = 층 크기 / 층 내 사용 카드 수
    cnt = Counter(cards[g]['stratum'] for g in gs); w = {g: cards[g]['stratum_size'] / cnt[cards[g]['stratum']] for g in gs}
    dd = [g for g in gs if card[g] == 'defect']; nn = [g for g in gs if card[g] == 'normal']
    rec = sum(w[g] for g in dd if cards[g]['score'] >= t) / sum(w[g] for g in dd) if dd else float('nan')
    fa = sum(w[g] for g in nn if cards[g]['score'] >= t) / sum(w[g] for g in nn) if nn else float('nan')
    return rec, fa
def unw(gs, t):
    dd = [g for g in gs if card[g] == 'defect']; nn = [g for g in gs if card[g] == 'normal']
    return (sum(cards[g]['score'] >= t for g in dd) / len(dd), len(dd), sum(cards[g]['score'] >= t for g in nn) / len(nn), len(nn))
out['A_defect_cards'] = sum(card[g] == 'defect' for g in use); out['A_normal_cards'] = sum(card[g] == 'normal' for g in use); out['grid'] = {}
for t in (.5, .6, .7, .8, .9):
    r, f = metrics(use, t); u = unw(use, t); bs = []
    for _ in range(2000):
        bg = list(rng.choice(use, len(use))); rr, ff = metrics_b = (None, None)
        # 부트스트랩은 중복 카드를 허용하므로 가중치를 층별 재계산
        cnt = Counter(cards[g]['stratum'] for g in bg); w = [cards[g]['stratum_size'] / cnt[cards[g]['stratum']] for g in bg]
        dd = [(wi, cards[g]['score']) for wi, g in zip(w, bg) if card[g] == 'defect']; nn = [(wi, cards[g]['score']) for wi, g in zip(w, bg) if card[g] == 'normal']
        if dd and nn: bs.append((sum(wi for wi, s in dd if s >= t) / sum(wi for wi, s in dd), sum(wi for wi, s in nn if s >= t) / sum(wi for wi, s in nn)))
    b = np.array(bs); out['grid'][str(t)] = dict(weighted_recall=round(r, 3), recall_ci95=[round(float(x), 3) for x in np.percentile(b[:, 0], [2.5, 97.5])], weighted_false_alarm=round(f, 3), fa_ci95=[round(float(x), 3) for x in np.percentile(b[:, 1], [2.5, 97.5])],
        unweighted=dict(recall=round(u[0], 3), n_defect=u[1], false_alarm=round(u[2], 3), n_normal=u[3]))
# 사람 target과의 일치: A 결함 카드 중 사람 결함 비율
out['human_defect_among_A_defect'] = dict(Counter(cards[g]['stratum'] for g in use if card[g] == 'defect'))
json.dump(out, open(f'{O}/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
