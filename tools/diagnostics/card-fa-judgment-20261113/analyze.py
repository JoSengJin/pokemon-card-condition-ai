"""사전 등록(card-fa-judgment-prereg-20261113.md) 규칙대로 분석. 새 추론 0."""
import json, math
from collections import Counter
O = 'artifacts/card-fa-judgment-20261113'; meta = json.load(open(f'{O}/sample_meta.json')); by = {m['code']: m for m in meta}
J = {n: {} for n in (1, 2, 3)}
for n in J:
    for b in (1, 2):
        d = json.load(open(f'{O}/responses/R{n}_b{b}.json')); exp = json.load(open(f'{O}/R{n}_b{b}.json'))['codes']
        assert [r['code'] for r in d['responses']] == exp, (n, b)
        for r in d['responses']: J[n][r['code']] = r['judgment']
assert all(set(J[n]) == set(by) for n in J)
def cons(c):
    v = Counter(J[n][c] for n in J).most_common(); return v[0][0] if v[0][1] >= 2 else 'split'
def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d; return [round(c - h, 3), round(c + h, 3)]
out = {}
for s in ('fa', 'ctl'):
    cs = [cons(c) for c, m in by.items() if m['set'] == s]; k = Counter(cs); jd = k['defect'] + k['normal']
    unk = k['unknown'] + k['split']
    out[s] = dict(n=len(cs), defect=k['defect'], normal=k['normal'], unknown_or_split=unk, unknown_rate=round(unk / len(cs), 3), p_defect_among_judgeable=[k['defect'], jd, round(k['defect'] / jd, 3) if jd else None, wilson(k['defect'], jd)])
off = [cons(c) for c, m in by.items() if m['set'] == 'fa' and m['card_off']]; out['fa_card_off_consensus'] = dict(Counter(off))
ov = [(by[c]['set'], cons(c)) for c in by if by[c]['overlap_prior_sample']]; out['overlap_prior'] = dict(n=len(ov), by={'|'.join(k): v for k, v in Counter(ov).items()})
mat = [[J[n][c] for n in J] for c in by]; out['unanimous_share'] = round(sum(len(set(r)) == 1 for r in mat) / len(mat), 3)
json.dump(out, open(f'{O}/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
