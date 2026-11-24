"""Is a card-level difference between two models on the same development rows within chance, and how many attempts share those rows? Read-only; prints JSON, never a verdict.

Usage: check.py CONTROL/result.json CANDIDATE/result.json EXPERIMENTS_DIR  (exit 2 when the inputs cannot be compared)
"""
import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

LOW, HIGH = .20, .60
DRAWS, SEED = 2000, 20261124
Z = 1.959963984540054
NOTES = ['기술 통계, 채택 기준 아님. 기존 사전 기준과 과거 판정을 대체하지 않는다.',
         'cohort_sha256이 다른 옛 실행(946구역 등)은 세지 않아 실제 시도 수의 하한이다.',
         '같은 평가 자료의 반복 시도는 p와 구간에 반영하지 않았다.']


def load(path):
    data = json.loads(Path(path).read_text())
    rows, scores = data['rows'], data['scores']
    if not rows or len(rows) != len(scores) or any(r['target'] not in (0, 1) for r in rows) or not all(0 <= s <= 1 for s in scores):
        raise ValueError(f'Unusable rows or scores: {path}')
    return rows, scores


def card_flags(rows, scores):
    """Per card, as card_miss in corner-mlp-head-20261121/worker.py: defect group -> missed, normal group -> false alarm."""
    best, worst = {}, {}
    for r, s in zip(rows, scores):
        dest = best if r['target'] else worst
        dest[r['group']] = max(dest.get(r['group'], 0.), s)
    return {g: s < LOW for g, s in best.items()}, {g: s >= HIGH for g, s in worst.items() if g not in best}


def rate(flags):
    """Count, rate and two-sided Wilson 95% interval."""
    k, n = sum(flags.values()), len(flags)
    if not n:
        return dict(count=0, cards=0, rate=None, wilson95=None)
    p, d = k / n, 1 + Z * Z / n
    centre, half = (p + Z * Z / (2 * n)) / d, Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return dict(count=k, cards=n, rate=p, wilson95=[max(0., centre - half), min(1., centre + half)])


def mcnemar(control, candidate):
    """Paired cards: b = newly wrong, c = recovered; two-sided exact p."""
    b = sum(candidate[g] and not control[g] for g in control)
    c = sum(control[g] and not candidate[g] for g in control)
    n = b + c
    p = min(1., 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)
    return dict(worse_b=b, better_c=c, exact_two_sided_p=p)


def same_photo(rows, control, candidate):
    """Pooled same-photo AUC (image path, as bag.auc) and a paired group bootstrap of candidate - control."""
    photos, owner, totals = {}, {}, {}
    for r, a, b in zip(rows, control, candidate):
        if owner.setdefault(r['image'], r['group']) != r['group']:
            raise ValueError('One photo belongs to several groups')
        photos.setdefault(r['image'], ([], []))[r['target']].append((a, b))
    for image, (neg, pos) in photos.items():
        t = totals.setdefault(owner[image], [0, 0., 0.])
        for p in pos:
            for n in neg:
                t[0] += 1
                for m in (0, 1):
                    t[m + 1] += (p[m] > n[m]) + .5 * (p[m] == n[m])
    pairs, won_a, won_b = [sum(t[k] for t in totals.values()) for k in range(3)]
    if not pairs:
        return dict(pairs=0, control=None, candidate=None, difference=None, bootstrap95=None)
    groups, rng, diffs = sorted(totals), random.Random(SEED), []
    for _ in range(DRAWS):
        drawn = [totals[rng.choice(groups)] for _ in groups]
        size = sum(t[0] for t in drawn)
        if size:
            diffs.append(sum(t[2] - t[1] for t in drawn) / size)
    diffs.sort()
    interval = [diffs[int(q * (len(diffs) - 1))] for q in (.025, .975)] if diffs else None
    return dict(pairs=pairs, control=won_a / pairs, candidate=won_b / pairs, difference=(won_b - won_a) / pairs,
                bootstrap95=interval, draws=DRAWS, usable_draws=len(diffs), seed=SEED, groups=len(groups))


def ledger(folder, run):
    """Every recorded run (any status) sharing the candidate run's cohort_sha256, in start order."""
    cohort = json.loads((run / 'reference.json').read_text())['cohort_sha256']
    records, unreadable = [], []
    for path in sorted(p for p in folder.iterdir() if p.is_dir()):
        try:
            if json.loads((path / 'reference.json').read_text())['cohort_sha256'] == cohort:
                record = json.loads((path / 'record.json').read_text())
                records.append((record['started_at'], path.name, record['status'], record['hypothesis_id']))
        except (OSError, ValueError, KeyError):
            unreadable.append(path.name)
    records.sort()
    names = [r[1] for r in records]
    return dict(cohort_sha256=cohort, total=len(records), by_status=dict(sorted(Counter(r[2] for r in records).items())),
                candidate_attempt_number=names.index(run.name) + 1 if run.name in names else None,
                hypothesis_ids=[r[3] for r in records], unreadable=unreadable)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('control', 'candidate', 'experiments'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    try:
        (rows, old), (other, new) = load(args.control), load(args.candidate)
        if rows != other:
            raise ValueError('Control and candidate rows or their order differ')
        before, after = card_flags(rows, old), card_flags(rows, new)
        report = dict(notes=NOTES, low=LOW, high=HIGH, rows=len(rows))
        for name, a, b in zip(('miss', 'false_alarm'), before, after):
            report[name] = dict(control=rate(a), candidate=rate(b), paired=mcnemar(a, b))
        report['same_photo_auc'] = same_photo(rows, old, new)
        report['attempts'] = ledger(args.experiments, args.candidate.resolve().parent)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
