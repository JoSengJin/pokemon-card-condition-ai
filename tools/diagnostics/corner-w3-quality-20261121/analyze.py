"""W3 step 1-2 on stored candidate-E OOF scores (read-only, development OOF, exploratory; the metric/threshold are chosen on the same OOF so the gain is optimistic).
Pre-registered before computing: events at the v1.14 point (card miss = every defect zone < .20; false alarm = any zone >= .60 on a normal card); card quality per metric
(photo_w, mean crop_w, geometric-mean lap_var, mean sat_frac; bad = low/low/low/high); withhold the worst q of ALL cards by quality only (label-free), q in {5,10,15,20}%;
rule = the single metric with the largest drop of the remaining positive-card miss rate at q=20%. Permutation: withhold a random 20% (2000 draws, seed 20261121)."""
import json
import math
import random
import sys
from collections import defaultdict

(LOW, HIGH), QS, DRAWS = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (.20, .60), (.05, .10, .15, .20), 2000


def cards(rows, scores, metrics):
    g = defaultdict(list)
    for r, s in zip(rows, scores):
        g[r['group']].append((r, s, metrics[r['id']]))
    out = {}
    for k, v in g.items():
        pos = any(r['target'] for r, _, _ in v)
        miss = pos and all(s < LOW for r, s, _ in v if r['target'])
        fa = (not pos) and any(s >= HIGH for _, s, _ in v)
        m = [x for _, _, x in v]
        q = dict(photo_w=m[0]['photo_w'], crop_w=sum(x['crop_w'] for x in m)/len(m), lap_var=math.exp(sum(math.log(x['lap_var'] + 1e-9) for x in m)/len(m)), sat_frac=-sum(x['sat_frac'] for x in m)/len(m))
        out[k] = dict(pos=pos, miss=miss, fa=fa, **q)
    return out


def remaining(cs, keep):
    p = [c for k, c in cs.items() if k in keep and c['pos']]
    n = [c for k, c in cs.items() if k in keep and not c['pos']]
    return dict(miss=sum(c['miss'] for c in p), pos=len(p), fa=sum(c['fa'] for c in n), neg=len(n))


def main(rows_path, scores_path, metrics_path):
    rows = json.load(open(rows_path))
    scores = json.load(open(scores_path))['scores']
    cs = cards(rows, scores, json.load(open(metrics_path)))
    keys = list(cs)
    base = remaining(cs, set(keys))
    print('all', base)
    res, rng = {}, random.Random(20261121)
    for metric in ('photo_w', 'crop_w', 'lap_var', 'sat_frac'):
        order = sorted(keys, key=lambda k: cs[k][metric])
        res[metric] = {}
        for q in QS:
            cut = round(q*len(keys))
            res[metric][q] = remaining(cs, set(order[cut:]))
    best = min(res, key=lambda m: res[m][.20]['miss']/res[m][.20]['pos'])
    for m in res:
        print(m, {q: (v['miss'], v['pos'], v['fa'], v['neg']) for q, v in res[m].items()})
    cut = round(.20*len(keys))
    rate = lambda d: d['miss']/d['pos']
    chosen = rate(res[best][.20])
    draws = [rate(remaining(cs, set(rng.sample(keys, len(keys) - cut)))) for _ in range(DRAWS)]
    print('rule picks', best, 'remaining miss rate', round(chosen, 4), 'baseline', round(base['miss']/base['pos'], 4), 'random20% mean', round(sum(draws)/DRAWS, 4),
          'p(random <= chosen)', sum(d <= chosen for d in draws)/DRAWS)
    # zone-level bins for the report
    for metric in ('photo_w', 'crop_w', 'lap_var'):
        v = sorted(cs.values(), key=lambda c: c[metric]); t = len(v)//3
        for name, part in (('low', v[:t]), ('mid', v[t:2*t]), ('high', v[2*t:])):
            p = [c for c in part if c['pos']]; n = [c for c in part if not c['pos']]
            print(metric, name, 'miss', sum(c['miss'] for c in p), len(p), 'fa', sum(c['fa'] for c in n), len(n))


if __name__ == '__main__':
    main(*sys.argv[1:4])
