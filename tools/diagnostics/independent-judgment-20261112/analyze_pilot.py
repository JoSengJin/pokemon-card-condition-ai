"""파일럿 분석(사전 등록 기준): 외부(AI) 판정자 alpha, 판단불가율. 새 추론 없음."""
import json, sys
from collections import Counter
import numpy as np
sys.path.insert(0, 'tools/diagnostics/independent-judgment-20261112')
from sim_alpha import alpha
OUT = 'artifacts/independent-judgment-20261112'; M = {'normal': 0, 'unknown': 1, 'defect': 2}
smp = json.load(open(f'{OUT}/sample.json'))['pilot']; codes = [z['code'] for z in smp]
R = {}
for n in (1, 2, 3):
    d = json.load(open(f'{OUT}/pilot_responses/R{n}.json')); r = {x['code']: x for x in d['responses']}
    assert set(r) == set(codes) and len(d['responses']) == 40, n
    R[n] = r
mat = np.array([[M[R[n][c]['judgment']] for n in (1, 2, 3)] for c in codes])
rng = np.random.default_rng(20261112); bs = []
for _ in range(2000):
    v = alpha(mat[rng.integers(0, 40, 40)])
    if not np.isnan(v): bs.append(v)
bin_ = np.where(mat == 2, 1, 0)
def a2(m):  # 이진(결함 vs 그 외)
    return alpha_bin(m)
def alpha_bin(m):
    import sim_alpha as s; s.CATS = 2; v = s.alpha(m); s.CATS = 3; return v
maj = []
for row in mat:
    c = Counter(row.tolist()).most_common(); maj.append(c[0][0] if c[0][1] >= 2 and (c[0][0] != 1 or c[0][1] >= 2) else None)
unk_rate = float((mat == 1).mean()); unk_any = float((mat == 1).any(1).mean())
pair = {f'R{a}-R{b}': float((mat[:, a - 1] == mat[:, b - 1]).mean()) for a, b in ((1, 2), (1, 3), (2, 3))}
off = np.array([z['card_off'] for z in smp]); cells = np.array([z['cell'] for z in smp])
res = dict(alpha3=round(float(alpha(mat)), 3), ci95=[round(float(x), 3) for x in np.percentile(bs, [2.5, 97.5])], alpha_binary=round(float(alpha_bin(bin_)), 3),
           unknown_rate=round(unk_rate, 3), unknown_any_rater=round(unk_any, 3), pairwise_agreement=pair,
           counts={n: dict(Counter(R[n][c]['judgment'] for c in codes)) for n in R}, consensus=dict(Counter(str(m) for m in maj)),
           card_off_items=int(off.sum()), unknown_on_card_off=int(((mat == 1).sum(1) >= 1)[off].sum()),
           defect_majority_by_cell={c: int(sum(1 for i in range(40) if cells[i] == c and maj[i] == 2)) for c in sorted(set(cells))},
           definition_issues={n: json.load(open(f'{OUT}/pilot_responses/R{n}.json')).get('definition_issues') for n in R},
           ambiguity_notes=sum(1 for n in R for c in codes if R[n][c]['ambiguity_note']),
           pass_alpha=bool(alpha(mat) >= .5), pass_unknown=bool(unk_rate <= .2))
json.dump(res, open(f'{OUT}/pilot_results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))
