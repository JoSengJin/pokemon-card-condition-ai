"""W1 label ceiling (read-only): per-cell repeat agreement from existing records, and the observed-AUC ceiling of a perfect scorer under a symmetric label-flip assumption."""
import glob
import json
import math
import sys


def answers(path):
    out = {}
    for line in open(path):
        if '=' in line:
            i, rest = line.strip().split('=', 1)
            out[i] = dict(kv.split(':', 1) for part in rest.split(';') for kv in part.split(',') if kv.split(':')[0] in ('edge', 'corner', 'surface'))
    return out


def e2_repeat(old_path, new_glob):
    new = {}
    for p in sorted(glob.glob(new_glob)):
        new.update(answers(p))
    old = answers(old_path)
    return {c: [sum(old[i][c] == new[i][c] for i in old if i in new), sum(i in new for i in old)] for c in ('edge', 'corner', 'surface')}


def ceiling(flip, prevalence):
    """Observed AUC of a perfect scorer when each observed label flips with probability `flip` (symmetric, independent of the photo)."""
    tpr = prevalence*(1 - flip)/(prevalence*(1 - flip) + (1 - prevalence)*flip)
    fpr = prevalence*flip/(prevalence*flip + (1 - prevalence)*(1 - flip))
    return .5 + .5*(tpr - fpr)


def flip_from_disagreement(d):
    """Two independent judgments with flip f each disagree with probability 2f(1-f)."""
    return (1 - math.sqrt(1 - 2*d))/2


def breakeven(target, prevalence):
    lo, hi = 1e-6, .4
    for _ in range(80):
        mid = (lo + hi)/2
        lo, hi = (mid, hi) if ceiling(mid, prevalence) > target else (lo, mid)
    return lo


if __name__ == '__main__':
    prevalence = 405/946
    res = dict(e2_page1_v4=e2_repeat('artifacts/e2-scenario-20261104/walkthrough-page1-v4.txt', 'artifacts/e2-scenario-20261120/answers-*.txt'),
               prevalence_corner=prevalence, breakeven_flip_for_auc_0_8565=breakeven(.8565, prevalence), breakeven_flip_for_auc_0_8865=breakeven(.8865, prevalence),
               scenarios={name: dict(disagreement=d, flip=flip_from_disagreement(d), ceiling=ceiling(flip_from_disagreement(d), prevalence))
                          for name, d in {'surface_old_criterion_binary_12of40': .30, 'surface_new_criterion_binary_5of30': 5/30}.items()})
    print(json.dumps(res, indent=1))
