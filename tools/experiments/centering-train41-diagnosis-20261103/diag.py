"""Diagnosis only (NOT an ./experiment record; no training, no AI calls, holdout untouched).
Compares AUC vs the human centering-defect label of (a) human-marked top/bottom asymmetry and (b) the v2 automatic measurer, on dev 36 and train 4-tap 41 (box-ok 37)."""
import importlib.util
import json

import numpy as np


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def auc(y, s):
    p, n = s[y], s[~y]
    return float(np.mean([(a > b) + .5 * (a == b) for a in p for b in n]))


v2 = load('artifacts/centering-tb-measurer-v2-20261103/worker.py', 'v2')
A = 'artifacts/c4-expansion-20261103/'
pool = {r['id']: r for r in json.load(open(A + 'pool.json'))}
dev = json.load(open('artifacts/centering-tb-measurer-v2-20261103/rows.json'))
dev = dev['rows'] if isinstance(dev, dict) else dev
tr = [x for x in json.load(open(A + 'train4-widths.json')) if x['box_ok']]


def score(row):
    t, b = v2.widths(row)
    return abs(t - b) / (t + b)


sd = np.array([score(x) for x in dev]); yd = np.array([bool(x['target']) for x in dev])
st = np.array([score(dict(image=pool[x['id']]['image'], box=pool[x['id']]['box'])) for x in tr]); yt = np.array([x['label'] == '결함' for x in tr])
print('human tb vs label: dev', round(auc(yd, np.array([x['human_tb'] for x in dev])), 3), 'train', round(auc(yt, np.array([x['tb'] for x in tr])), 3))
print('v2 auto vs label: dev', round(auc(yd, sd), 3), 'train', round(auc(yt, st), 3), 'combined', round(auc(np.r_[yd, yt], np.r_[sd, st]), 3))
