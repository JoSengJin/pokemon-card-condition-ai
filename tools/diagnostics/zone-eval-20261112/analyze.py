"""prereg zone-eval-set-20261112 결과 계산. 기준은 prereg.json 고정. 학습·추론·라벨 변경 0, 저장 점수만 사용."""
import glob
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, 'tools/diagnostics/label-reliability-20261111')
from kappa import stats
D = Path('artifacts/zone-eval-set-20261112'); SEED, B = 20261112, 4000


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d
    return [round(c - h, 3), round(c + h, 3)]


def load(pat):
    out = {}
    for f in sorted(glob.glob(str(D / pat))):
        for r in json.load(open(f))['responses']: out[r['id']] = r['judgment']
    return out


def estimates(zs, sizes):
    """zs: [(cell,judgment)]. 칸 크기 가중, 판단불가 제외. 반환: FN_new, FP_new(추정 곳 수), 모델음성 중 결함율, 모델양성 중 정상율."""
    by = defaultdict(list)
    for c, j in zs: by[c].append(j)
    frac = {c: (lambda v: (v.count('defect') / len(v), v.count('normal') / len(v)) if v else (0, 0))([j for j in by[c] if j != 'unknown']) for c in sizes}
    fn = sum(sizes[c] * frac[c][0] for c in ('0/0', '1/0')); fp = sum(sizes[c] * frac[c][1] for c in ('0/1', '1/1'))
    neg, pos = sizes['0/0'] + sizes['1/0'], sizes['0/1'] + sizes['1/1']
    return dict(FN_new=fn, FP_new=fp, neg_defect_rate=fn / neg, pos_normal_rate=fp / pos)


def wauc(items):
    pos = [(s, w) for s, w, t in items if t == 1]; neg = [(s, w) for s, w, t in items if t == 0]
    num = sum(wp * wn * ((sp > sn) + 0.5 * (sp == sn)) for sp, wp in pos for sn, wn in neg); return num / (sum(w for _, w in pos) * sum(w for _, w in neg))


def main():
    smp = json.load(open(D / 'sample.json')); sizes = smp['cell_sizes']; z = {x['id']: x for x in smp['zones']}
    jud = load('responses/zone*.json'); rep = load('responses/repeat*.json'); assert set(jud) == set(z) and len(rep) == 20
    cells = {c: Counter(jud[i] for i in z if z[i]['cell'] == c) for c in sizes}
    res = dict(n=len(jud), overall=dict(Counter(jud.values())), cell_sizes=sizes)
    res['cells'] = {c: dict(counts=dict(cells[c]), **{k: wilson(cells[c][k], 25) for k in ('defect', 'normal', 'unknown')}) for c in sizes}
    zs = [(z[i]['cell'], jud[i]) for i in z]; res['estimate'] = estimates(zs, sizes)
    rng = random.Random(SEED); bs = []
    for _ in range(B):
        r = []
        for c in sizes: r += [(c, x) for x in rng.choices([jud[i] for i in z if z[i]['cell'] == c], k=25)]
        e = estimates(r, sizes); bs.append((e['FN_new'], e['FP_new']))
    q = lambda v: [round(sorted(v)[int(len(v) * p)], 1) for p in (0.025, 0.975)]
    res['estimate_ci'] = dict(FN_new=q([a for a, _ in bs]), FP_new=q([b for _, b in bs]))
    res['original_onframe'] = dict(FN=sizes['1/0'], FP=sizes['0/1'])
    # 판단불가 제외 가중 AUC (새 판정 기준)
    o = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json')); sc = {r['id']: x for r, x in zip(o['rows'], o['scores'])}
    items = [(sc[i], sizes[z[i]['cell']] / 25, 1 if jud[i] == 'defect' else 0) for i in z if jud[i] != 'unknown']; res['weighted_AUC_new_labels'] = round(wauc(items), 4)
    res['unknown_rate'] = round(Counter(jud.values())['unknown'] / 100, 3)
    pairs = [(jud[i], rep[i]) for i in rep]; res['repeat'] = dict(**stats(pairs), confusion={f'{a}->{b}': c for (a, b), c in sorted(Counter(pairs).items())})
    s1 = res['unknown_rate'] <= 0.20 and res['repeat']['agree'] >= 0.70; res['S1_usable'] = s1
    res['S2_FP_40pct_lower'] = bool(s1 and res['estimate']['FP_new'] <= 0.6 * sizes['0/1'])
    (D / 'results.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)); print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
