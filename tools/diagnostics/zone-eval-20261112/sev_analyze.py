"""prereg severity-repro-20261112 결과. 기준은 prereg.json 고정. 학습·추론·라벨 변경 0."""
import glob
import json
import math
from collections import Counter
from pathlib import Path
D = Path('artifacts/severity-repro-20261112')


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d; return [round(c - h, 3), round(c + h, 3)]


def qwk(pairs, levels=(0, 1, 2)):
    n = len(pairs); k = len(levels); w = lambda i, j: ((i - j) / (k - 1)) ** 2
    o = Counter(pairs); ma = Counter(a for a, _ in pairs); mb = Counter(b for _, b in pairs)
    do = sum(w(a, b) * c for (a, b), c in o.items()) / n; de = sum(w(i, j) * ma[i] * mb[j] for i in levels for j in levels) / n ** 2
    return None if de == 0 else round(1 - do / de, 4)


def load(pat):
    out = {}
    for f in sorted(glob.glob(str(D / pat))):
        for r in json.load(open(f))['responses']: out[r['id']] = r['level']
    return out


def main():
    smp = json.load(open(D / 'sample.json')); z = {x['id']: x for x in smp['zones']}; lv = load('responses/sev*.json'); rp = load('responses/srep*.json'); assert set(lv) == set(z) and len(lv) == 60 and len(rp) == 12
    res = dict(n=60, dist=dict(Counter(lv.values())), unknown_rate=round(Counter(lv.values())['unknown'] / 60, 3))
    res['dist_wilson'] = {k: wilson(Counter(lv.values())[k], 60) for k in ('0', '1', '2', 'unknown')}
    ok = [(int(lv[i]), int(rp[i])) for i in rp if lv[i] != 'unknown' and rp[i] != 'unknown']; ex = 12 - len(ok)
    res['repeat'] = dict(n_used=len(ok), excluded_unknown=ex, agree=round(sum(a == b for a, b in ok) / len(ok), 3), quadratic_weighted_kappa=qwk(ok), confusion={f'{a}->{b}': c for (a, b), c in sorted(Counter(ok).items())})
    kn = [i for i in z if lv[i] != 'unknown']; res['cell_per'] = smp['per_cell']
    def share(t, pred, weighted):
        ids = [i for i in kn if z[i]['target'] == t]; w = lambda i: z[i]['weight'] if weighted else 1; return round(sum(w(i) for i in ids if pred(lv[i])) / sum(w(i) for i in ids), 3), len(ids)
    for wt in (True, False):
        tag = 'weighted' if wt else 'unweighted'
        res[f'target1_level2_{tag}'] = share(1, lambda l: l == '2', wt); res[f'target0_level01_{tag}'] = share(0, lambda l: l in ('0', '1'), wt)
        res[f'target1_level_ge1_{tag}'] = share(1, lambda l: l in ('1', '2'), wt); res[f'target0_level0_{tag}'] = share(0, lambda l: l == '0', wt)
    res['crosstab_level_by_target_unweighted'] = {f't{t}': dict(Counter(lv[i] for i in kn if z[i]['target'] == t)) for t in (0, 1)}
    res['crosstab_level_by_cell'] = {c: dict(Counter(lv[i] for i in z if z[i]['cell'] == c)) for c in smp['cell_sizes']}
    res['S1'] = bool(res['unknown_rate'] <= 0.20 and res['repeat']['quadratic_weighted_kappa'] is not None and res['repeat']['quadratic_weighted_kappa'] >= 0.6)
    res['S2'] = bool(res['S1'] and res['target1_level2_weighted'][0] >= 0.7 and res['target0_level01_weighted'][0] >= 0.7)
    (D / 'results.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)); print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
