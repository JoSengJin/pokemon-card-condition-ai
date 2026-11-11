"""prereg label-noise-floor-20261112: 라벨 잡음 하한(Q1). 기존 응답·저장 점수만 사용, 학습·추론·라벨 변경 0. 같은 사람 재판정, 독립 검증 아님."""
import glob
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
OUT = Path('artifacts/label-noise-floor-20261112'); P = json.load(open(OUT / 'prereg.json'))
CELLS = ('0/0', '0/1', '1/0', '1/1'); GATE = dict(FP=112, FN=67)


def load(sample, pat, key):
    z = {x['id']: x for x in json.load(open(sample))['zones']}; ans = {}
    for f in sorted(glob.glob(pat)):
        for r in json.load(open(f))['responses']: ans[r['id']] = r[key]
    assert set(ans) == set(z), (sample, len(ans), len(z)); return [dict(z[i], ans=ans[i]) for i in z]


def population():
    obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
    off = {r['id']: bool(r['bad'] or r['center_out']) for r in json.load(open('artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    on, offc = Counter(), Counter()
    for r, s in zip(obs['rows'], obs['scores']): (offc if off.get(r['id'], False) else on)[f"{r['target']}/{int(s >= 0.5)}"] += 1
    assert sum(on.values()) + sum(offc.values()) == 1776; return on, offc


def rates(zs, is_def, unknown):
    out = {}
    for c in CELLS:
        rs = [z for z in zs if z['cell'] == c]; t = int(c[0]); flip = keep = 0
        for z in rs:
            a = z['ans']
            if a == 'unknown':
                if unknown == 'exclude': continue
                keep += 1; continue
            d = is_def(a); flip += (d if t == 0 else not d); keep += (not d if t == 0 else d)
        out[c] = (flip, flip + keep)
    return out


def floors(r, n):
    p = {c: (r[c][0] / r[c][1] if r[c][1] else 0.0) for c in CELLS}
    return dict(FP=sum(n[c] * p[c] for c in ('0/0', '0/1')), FN=sum(n[c] * p[c] for c in ('1/0', '1/1'))), p


def boot(zs, is_def, unknown, n, B, seed):
    rng = random.Random(seed); by = defaultdict(lambda: defaultdict(list))
    for z in zs: by[z['cell']][z['group']].append(z)
    res = dict(FP=[], FN=[])
    for _ in range(B):
        s = []
        for c in CELLS:
            gs = sorted(by[c]); s += [z for _g in range(len(gs)) for z in by[c][gs[rng.randrange(len(gs))]]]
        f, _p = floors(rates(s, is_def, unknown), n)
        for k in res: res[k].append(f[k])
    q = lambda v, a: sorted(v)[int(a * (len(v) - 1))]
    return {k: [round(q(v, 0.025), 1), round(q(v, 0.975), 1)] for k, v in res.items()}


def verdict(lo, hi, g, k):
    if lo > g: return f'{k} 하한 > {g}: 현 라벨로는 {k} 게이트 달성 불가' + (' -> 표현 가설 재개 금지' if k == 'FP' else '')
    if hi < g: return f'{k} 상한 < {g}: 라벨 잡음만으로 설명되지 않음 -> 모델 측 개선 여지 있음'
    return f'{k} 구간이 {g} 포함: 판단 불가'


def run(name, zs, is_def, unknown, on, offc, B, seed):
    r = rates(zs, is_def, unknown); f, p = floors(r, on); ci = boot(zs, is_def, unknown, on, B, seed); ext, _ = floors(r, offc)
    lit = dict(FP_literal=round(sum(on[c] * p[c] for c in ('1/0', '1/1')), 1), FN_literal=round(sum(on[c] * p[c] for c in ('0/0', '0/1')), 1))
    return dict(source=name, unknown=unknown, cell_flip={c: dict(flip=r[c][0], n=r[c][1], rate=round(p[c], 3), N=on[c]) for c in CELLS},
                FP_floor=round(f['FP'], 1), FP_ci95=ci['FP'], FN_floor=round(f['FN'], 1), FN_ci95=ci['FN'],
                verdict=dict(FP=verdict(*ci['FP'], GATE['FP'], 'FP'), FN=verdict(*ci['FN'], GATE['FN'], 'FN')),
                ref_offcard_extrapolated=dict(FP=round(f['FP'] + ext['FP'], 1), FN=round(f['FN'] + ext['FN'], 1)), ref_literal_reading=lit)


def main():
    for f, h in P['inputs'].items(): assert hashlib.sha256(open(f, 'rb').read()).hexdigest() == h, f
    on, offc = population(); B, seed = P['bootstrap']['B'], P['bootstrap']['seed']
    sev = load('artifacts/severity-repro-20261112/sample.json', 'artifacts/severity-repro-20261112/responses/sev*.json', 'level')
    zev = load('artifacts/zone-eval-set-20261112/sample.json', 'artifacts/zone-eval-set-20261112/responses/zone*.json', 'judgment')
    ge1 = lambda a: a in ('1', '2'); eq2 = lambda a: a == '2'; zd = lambda a: a == 'defect'
    res = dict(prereg=P['id'], independent_validation=False, label='같은 사람 재판정 기반, 독립 검증 아님', card_on_cells=dict(on), card_off_cells=dict(offc),
               observed_baseline=dict(FP=167, FN=57),
               primary=run('severity >=1', sev, ge1, 'exclude', on, offc, B, seed),
               sensitivity=[run('severity >=1', sev, ge1, 'as_original', on, offc, B, seed), run('severity ==2', sev, eq2, 'exclude', on, offc, B, seed),
                            run('severity ==2', sev, eq2, 'as_original', on, offc, B, seed), run('zone-eval defect', zev, zd, 'exclude', on, offc, B, seed)])
    (OUT / 'results.json').write_text(json.dumps(res, ensure_ascii=False, indent=1)); print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
