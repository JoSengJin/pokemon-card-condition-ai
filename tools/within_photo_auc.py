"""Secondary metric for any common-runner record: AUC across all pairs, and AUC only between regions of the same group that has both classes.
Controls card design, source and lighting. Read-only; usage: within_photo_auc.py artifacts/experiments/<run>/observations.json ..."""
import collections
import json
import sys


def auc(pos, neg):
    return sum((p > n) + .5*(p == n) for p in pos for n in neg)/len(pos)/len(neg)


def summarize(rows, scores):
    groups = collections.defaultdict(list)
    for row, score in zip(rows, scores):
        groups[row['group']].append((row['target'], score))
    mixed = {g: v for g, v in groups.items() if {t for t, _ in v} == {0, 1}}
    pairs = [(a, b) for v in mixed.values() for ta, a in v if ta == 1 for tb, b in v if tb == 0]
    return dict(overall_auc=auc([s for r, s in zip(rows, scores) if r['target']], [s for r, s in zip(rows, scores) if not r['target']]),
                within_group_auc=sum((a > b) + .5*(a == b) for a, b in pairs)/len(pairs) if pairs else None,
                mixed_groups=len(mixed), within_group_pairs=len(pairs))


if __name__ == '__main__':
    for path in sys.argv[1:]:
        data = json.load(open(path))
        print(path, json.dumps(summarize(data['rows'], data['scores'])))
