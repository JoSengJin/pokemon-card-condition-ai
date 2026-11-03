"""Diagnosis only: human-tap top/bottom asymmetry AUC vs centering label, dev 36 (8-point marks) and train 37 (4-tap, box ok). Holdout untouched."""
import json
import numpy as np

def auc(y, s):
    p, n = s[y], s[~y]
    return float(np.mean([(a > b) + .5 * (a == b) for a in p for b in n]))

def boot(y, s, k=2000, seed=0):
    r = np.random.default_rng(seed); v = []
    for _ in range(k):
        i = r.integers(0, len(y), len(y))
        if y[i].any() and (~y[i]).any(): v.append(auc(y[i], s[i]))
    return [round(float(q), 3) for q in np.percentile(v, [2.5, 97.5])]

M = 'artifacts/centering-marks-20261103/'
dev = json.load(open(M + 'analysis-front.json'))['items'] + json.load(open(M + 'analysis-front-rep.json'))['items']
tr = [x for x in json.load(open('artifacts/c4-expansion-20261103/train4-widths.json')) if x['box_ok']]
out = {}
for name, y, s in (('dev_tb', [x['target'] == 1 for x in dev], [x['tb'] for x in dev]),
                   ('dev_lr', [x['target'] == 1 for x in dev], [x['lr'] for x in dev]),
                   ('dev_worst', [x['target'] == 1 for x in dev], [x['worst'] for x in dev]),
                   ('train_tb', [x['label'] == '결함' for x in tr], [x['tb'] for x in tr])):
    y, s = np.array(y), np.array(s)
    out[name] = dict(n=len(y), defect=int(y.sum()), auc=round(auc(y, s), 3), ci=boot(y, s))
y = np.array([x['target'] == 1 for x in dev] + [x['label'] == '결함' for x in tr]); s = np.array([x['tb'] for x in dev] + [x['tb'] for x in tr])
out['combined_tb'] = dict(n=len(y), defect=int(y.sum()), auc=round(auc(y, s), 3), ci=boot(y, s))
out['train_defect_tb_lt_0.04'] = sum(x['label'] == '결함' and x['tb'] < .04 for x in tr)
out['train_normal_tb_ge_0.15'] = sum(x['label'] == '정상' and x['tb'] >= .15 for x in tr)
json.dump(out, open('artifacts/c4-label-criterion-diagnosis-20261103/auc.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
