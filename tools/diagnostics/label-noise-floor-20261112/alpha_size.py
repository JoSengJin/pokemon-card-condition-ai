"""독립 판정 규모 산정용 합성 시뮬레이션(실데이터 미사용). 이진 Krippendorff alpha(명목)의 표본 간 SD로 95% 반폭(1.96*SD)을 근사."""
import random
from collections import Counter


def alpha_nominal(units):
    o = Counter(); n = 0
    for vals in units:
        m = len(vals)
        if m < 2: continue
        for i, a in enumerate(vals):
            for j, b in enumerate(vals):
                if i != j: o[(a, b)] += 1 / (m - 1)
        n += m
    nc = Counter()
    for (a, _b), w in o.items(): nc[a] += w
    do = sum(w for (a, b), w in o.items() if a != b) / n
    de = sum(nc[a] * nc[b] for a in nc for b in nc if a != b) / (n * (n - 1))
    return 1 - do / de if de else float('nan')


def sim(n, raters, prev, err, missing, rng):
    units = []
    for _ in range(n):
        t = rng.random() < prev; vals = [(t if rng.random() > err else not t) for _ in range(raters) if rng.random() > missing]
        units.append(vals)
    return alpha_nominal(units)


def main():
    rng = random.Random(20261112); rows = []
    for err in (0.08, 0.10):
        for n in (40, 80, 120, 160, 200, 300):
            xs = [sim(n, 3, 0.5, err, 0.10, rng) for _ in range(800)]; m = sum(xs) / len(xs); sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
            rows.append((err, n, round(m, 3), round(1.96 * sd, 3)))
    for r in rows: print('err=%.2f n=%d mean_alpha=%.3f halfwidth95=%.3f' % r)


if __name__ == '__main__':
    main()
