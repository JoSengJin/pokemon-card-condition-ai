"""amendment_3 탐색 분석(결정 규칙 미적용): 칸별·가중 결함 비율, 판단불가, 보조 alpha. 새 추론 없음."""
import json, sys
from collections import Counter, defaultdict
import numpy as np
sys.path.insert(0, 'tools/diagnostics/independent-judgment-20261112')
from sim_alpha import alpha
O = 'artifacts/independent-judgment-20261112'; M = {'normal': 0, 'unknown': 1, 'defect': 2}
smp = json.load(open(f'{O}/sample.json')); main = smp['main']; sz = smp['cell_sizes_after_gallery']
J = {n: {} for n in (1, 2, 3)}
for n in (1, 2, 3):
    for b in (1, 2, 3, 4):
        d = json.load(open(f'{O}/main_responses/R{n}_b{b}.json')); assert len(d['responses']) == 40, (n, b)
        exp = json.load(open(f'{O}/main_R{n}_b{b}.json'))['codes']; assert [r['code'] for r in d['responses']] == exp, (n, b)
        for r in d['responses']: J[n][r['code']] = r['judgment']
codes = [z['code'] for z in main]; assert all(c in J[n] for n in J for c in codes)
mat = np.array([[M[J[n][c]] for n in (1, 2, 3)] for c in codes])
def cons(row):
    c = Counter(row.tolist()).most_common()
    return c[0][0] if c[0][1] >= 2 else None   # 다수결, 1:1:1은 None
cs = [cons(r) for r in mat]
if True:  # 판단불가 2명 이상은 판단 불가(1) — cons가 이미 1로 처리
    pass
cell = np.array([z['cell'] for z in main]); grp = np.array([z['group'] for z in main]); off = np.array([z['card_off'] for z in main])
def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d; return [round(float(c - h), 3), round(float(c + h), 3)]
out = dict(n=len(codes), alpha3_supplementary=round(float(alpha(mat)), 3), unknown_rate=round(float((mat == 1).mean()), 3), per_cell={}, consensus=dict(Counter(str(c) for c in cs)))
for c in sorted(sz):
    idx = [i for i in range(len(codes)) if cell[i] == c]; cc = [cs[i] for i in idx]
    d = sum(1 for x in cc if x == 2); u = sum(1 for x in cc if x == 1 or x is None); den = len(cc) - u
    out['per_cell'][c] = dict(n=len(cc), defect=d, normal=sum(1 for x in cc if x == 0), unjudgeable_or_split=u, defect_among_judgeable=[d, den, round(d / den, 3) if den else None, wilson(d, den)],
                              card_off=int(off[idx].sum()))
def weighted(ix):  # 칸 크기 가중, 판정 가능만
    num = den = 0.0
    for c in sz:
        sel = [i for i in ix if cell[i] == c and cs[i] in (0, 2)]
        if not sel: continue
        p = np.mean([cs[i] == 2 for i in sel]); num += sz[c] * p; den += sz[c]
    return num / den
rng = np.random.default_rng(20261112); gs = sorted(set(grp)); gi = {g: [i for i in range(len(codes)) if grp[i] == g] for g in gs}
bs = []
for _ in range(2000):
    ix = [i for g in rng.choice(gs, len(gs)) for i in gi[g]]
    try: bs.append(weighted(ix))
    except ZeroDivisionError: pass
out['weighted_defect_rate'] = dict(point=round(weighted(list(range(len(codes)))), 3), ci95=[round(float(x), 3) for x in np.percentile(bs, [2.5, 97.5])])
on = ~off; out['card_on_only_weighted'] = round(weighted([i for i in range(len(codes)) if on[i]]), 3)
out['card_off_consensus'] = dict(Counter(str(cs[i]) for i in range(len(codes)) if off[i]))
json.dump(out, open(f'{O}/main_explore_results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
