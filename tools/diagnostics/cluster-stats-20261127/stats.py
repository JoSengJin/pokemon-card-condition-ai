"""Photo-clustered intervals and paired test for zone-level rates (05 §4-2). Read-only; prints JSON, never a verdict.

Usage: stats.py CANDIDATE.json [CONTROL.json]  (files with rows[group,id,target] and scores; fixed 0.5 operating point)
DEFF uses the ratio-estimator variance over photo groups, floored at 1. Photos (group) are assumed independent;
sellers are not modelled.
"""
import importlib.util
import itertools
import json
import math
import random
import sys
from pathlib import Path

DRAWS, SEED, FLIPS, EXACT_MAX = 2000, 20261126, 100_000, 20
spec = importlib.util.spec_from_file_location('cluster_wilson_src', Path(__file__).resolve().parents[1] / 'corner-rejudge-20261121/score.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
WILSON = source.wilson


def by_photo(rows, hits, keep):
    """{group: [hits, zones]} over the rows with keep true."""
    out = {}
    for row, hit, use in zip(rows, hits, keep, strict=True):
        if use:
            cell = out.setdefault(row['group'], [0, 0])
            cell[0] += bool(hit)
            cell[1] += 1
    return out


def rate(photos):
    """k/n with design effect and Wilson 95% on the effective denominator n/DEFF. n=0 is unmeasured."""
    k, n, m = sum(y for y, _ in photos.values()), sum(z for _, z in photos.values()), len(photos)
    if not n:
        return dict(k=0, n=0, photos=0, rate=None, deff=None, wilson95=None)
    if m < 2:  # one photo cannot say how much photos differ: the interval is unmeasured
        return dict(k=k, n=n, photos=m, rate=k / n, deff=None, wilson95=None)
    p = k / n
    deff = None
    if 0 < p < 1:
        variance = m / (m - 1) * sum((y - p * z) ** 2 for y, z in photos.values()) / n ** 2
        deff = variance / (p * (1 - p) / n)
    effective = n / max(1., deff or 1.)
    lo, hi = WILSON(p * effective, effective)
    return dict(k=k, n=n, photos=m, rate=p, deff=deff, wilson95=[max(0., lo), min(1., hi)])


def bootstrap(photos, draws=DRAWS, seed=SEED):
    """Percentile 95% of the rate, resampling whole photos."""
    cells, rng = [photos[g] for g in sorted(photos)], random.Random(seed)
    if len(cells) < 2:
        return None
    values = []
    for _ in range(draws):
        picked = rng.choices(cells, k=len(cells))
        values.append(sum(y for y, _ in picked) / sum(z for _, z in picked))
    values.sort()
    return [values[int(q * (draws - 1))] for q in (.025, .975)]


def sign_flip(differences, flips=FLIPS, seed=SEED):
    """Two-sided p for sum(d_i), d_i = c_i - b_i per discordant photo: exact up to 20 photos, seeded sampling above."""
    observed, k = abs(sum(differences)), len(differences)
    if k <= EXACT_MAX:
        hits = sum(abs(sum(s * d for s, d in zip(signs, differences))) >= observed
                   for signs in itertools.product((1, -1), repeat=k))
        return dict(photos=k, p=hits / 2 ** k, method='exact')
    rng, hits = random.Random(seed), 0
    for _ in range(flips):
        hits += abs(sum(d if rng.getrandbits(1) else -d for d in differences)) >= observed
    return dict(photos=k, p=(hits + 1) / (flips + 1), method=f'sampled {flips}')


def paired(rows, control_wrong, candidate_wrong, keep):
    """b = newly wrong, c = recovered, with the photo-level sign-flip test."""
    worse = by_photo(rows, [n and not o for o, n in zip(control_wrong, candidate_wrong)], keep)
    better = by_photo(rows, [o and not n for o, n in zip(control_wrong, candidate_wrong)], keep)
    either = {g: [worse[g][0] + better[g][0], worse[g][1]] for g in worse}
    differences = [better[g][0] - worse[g][0] for g in sorted(worse) if either[g][0]]
    return dict(worse_b=sum(y for y, _ in worse.values()), better_c=sum(y for y, _ in better.values()),
                discordance=rate(either), test=sign_flip(differences))


def report(candidate, control=None):
    rows = candidate['rows']
    if (any(r['target'] not in (0, 1) for r in rows) or len({r['id'] for r in rows}) != len(rows)
            or any(type(s) not in (int, float) or not 0 <= s <= 1  # NaN fails the range test
                   for data in (candidate, control) if data for s in data['scores'])):
        raise ValueError('Targets must be 0/1, candidate ids unique and every score a finite number in [0, 1]')
    if control:
        found = {r['id']: (r, s) for r, s in zip(control['rows'], control['scores'], strict=True)}
        if len(found) != len(control['rows']) or not all(
                row['id'] in found and all(k in row and k in found[row['id']][0] and found[row['id']][0][k] == row[k]
                                           for k in ('target', 'group', 'image_sha256', 'box'))
                for row in rows):
            raise ValueError('Every candidate row needs one control row with the same truth, photo and box')
        unused = len(found) - len(rows)  # never hidden: a larger control cohort is reported below
        control = dict(rows=rows, scores=[found[r['id']][1] for r in rows])
    errors = [[(s >= .5) != (r['target'] == 1) for r, s in zip(rows, data['scores'], strict=True)]
              for data in (candidate, control) if data]
    out = {}
    for name, target in (('miss', 1), ('false_alarm', 0)):
        keep = [r['target'] == target for r in rows]
        photos = by_photo(rows, errors[0], keep)
        out[name] = dict(rate(photos), bootstrap95=bootstrap(photos))
        if control:
            out[name]['paired'] = paired(rows, errors[1], errors[0], keep)
    if control:
        out['control_rows_not_used'] = unused
    return out


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    print(json.dumps(report(*(json.loads(Path(p).read_text()) for p in sys.argv[1:])), indent=1))
