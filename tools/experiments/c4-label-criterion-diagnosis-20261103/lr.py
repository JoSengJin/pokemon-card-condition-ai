"""Diagnosis only: human-tap left/right vs top/bottom asymmetry AUC vs centering label on train 4-tap fronts (box ok, both axes tapped). Holdout untouched; no model."""
import json
import numpy as np

A = 'artifacts/c4-expansion-20261103/'
OUT = 'artifacts/c4-label-criterion-diagnosis-20261103/'

def auc(y, s):
    p, n = s[y], s[~y]
    return float(np.mean([(a > b) + .5 * (a == b) for a in p for b in n]))

def boot(y, s, k=2000, seed=0):
    r = np.random.default_rng(seed); v = []
    for _ in range(k):
        i = r.integers(0, len(y), len(y))
        if y[i].any() and (~y[i]).any(): v.append(auc(y[i], s[i]))
    return [round(float(q), 3) for q in np.percentile(v, [2.5, 97.5])]

tb = {x['id']: x for x in json.load(open(A + 'train4-widths.json'))}
rows, skipped = [], []
for line in open(A + 'answers-train4lr.txt', encoding='utf-8'):
    i, _, v = line.strip().split('|')
    if v == '판정불가':
        skipped.append(i); continue
    t = [float(t) for t in v.split(',')]
    ol, orr = sorted(t[:2])
    il, ir = sorted(t[2:])
    left, right = il - ol, orr - ir
    x = tb[i]
    rows.append(dict(id=i, label=x['label'], box_ok=x['box_ok'], nested=ol < il < ir < orr, left=left, right=right,
                     lr=abs(left - right) / (left + right), tb=x['tb']))
use = [r for r in rows if r['box_ok'] and r['nested']]
y = np.array([r['label'] == '결함' for r in use])
out = dict(answered=len(rows) + len(skipped), skipped=len(skipped), not_nested=sum(not r['nested'] for r in rows),
           box_not_ok=sum(not r['box_ok'] for r in rows), used=len(use), defect=int(y.sum()))
for k, s in (('tb', [r['tb'] for r in use]), ('lr', [r['lr'] for r in use]), ('worst', [max(r['tb'], r['lr']) for r in use])):
    s = np.array(s); out[k] = dict(auc=round(auc(y, s), 3), ci=boot(y, s))
out['rows'] = sorted(use, key=lambda r: (r['label'], r['lr']))
json.dump(out, open(OUT + 'lr.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, ensure_ascii=False))
for r in out['rows']:
    print(r['label'], 'lr=%.3f tb=%.3f' % (r['lr'], r['tb']), r['id'][-6:])
