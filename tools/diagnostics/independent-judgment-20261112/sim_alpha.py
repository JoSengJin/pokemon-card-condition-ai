"""합성 시뮬레이션(실데이터·실사진 미사용): 외부 판정자 3명 Krippendorff alpha 구간 반폭이 ±0.1이 되는 표본 크기.
잠재 점수 모델의 가짜 판정만 만든다. 모델 성능·실제 판정자 재현성에 대한 증거가 아니다."""
import json, sys
import numpy as np
SEED = 20261112
CELL_MU = {'TN': -0.6, 'FP': 0.2, 'FN': 0.4, 'TP': 1.3}   # 합성 가정(임의)
CATS = 3; LO, HI = -0.15, 0.45                           # 판단불가 띠(합성)
REPS, BOOT = 150, 200


def alpha(m):  # m: items x raters, 값 0..2, 결측 없음. 명목 척도 Krippendorff alpha
    n, r = m.shape
    o = np.zeros((CATS, CATS))
    for a in range(r):
        for b in range(r):
            if a != b: np.add.at(o, (m[:, a], m[:, b]), 1.0 / (r - 1))
    nc = o.sum(1); tot = nc.sum()
    de = (tot ** 2 - (nc ** 2).sum()) / (tot * (tot - 1))
    do = (o.sum() - np.trace(o)) / tot
    return 1.0 if de == 0 and do == 0 else (np.nan if de == 0 else 1 - do / de)


def draw(rng, n, s, per_cell=None):
    cells = list(CELL_MU); k = n // 4
    z = np.concatenate([rng.normal(CELL_MU[c], 1.0, k) for c in cells])
    p = z[:, None] + rng.normal(0, s, (len(z), 3))
    return np.where(p > HI, 2, np.where(p < LO, 0, 1)) * 1  # 0 정상,1 판단불가,2 결함


def run(n, s, rng):
    m = draw(rng, n, s); a = alpha(m)
    bs = []
    for _ in range(BOOT):
        idx = rng.integers(0, len(m), len(m)); v = alpha(m[idx])
        if not np.isnan(v): bs.append(v)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return a, (hi - lo) / 2


if __name__ == '__main__':
    rng = np.random.default_rng(SEED)
    out = {'synthetic': True, 'seed': SEED, 'reps': REPS, 'boot': BOOT, 'cell_mu': CELL_MU, 'band': [LO, HI], 'scenarios': []}
    big = draw(rng, 40000, 0.0)
    for s in (0.25, 0.5, 0.8, 1.2):
        pop = alpha(draw(rng, 40000, s)); unk = float((draw(rng, 4000, s) == 1).mean())
        rows = []
        for n in (40, 80, 120, 160, 200, 240):
            res = [run(n, s, rng) for _ in range(REPS)]
            rows.append(dict(n=n, mean_alpha=round(float(np.mean([r[0] for r in res])), 3), mean_halfwidth=round(float(np.mean([r[1] for r in res])), 3)))
        out['scenarios'].append(dict(rater_noise_sd=s, population_alpha=round(pop, 3), unjudgeable_rate=round(unk, 3), rows=rows))
        print(s, round(pop, 3), round(unk, 3), [(r['n'], r['mean_halfwidth']) for r in rows], flush=True)
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'sim_result.json', 'w'), indent=1, ensure_ascii=False)
