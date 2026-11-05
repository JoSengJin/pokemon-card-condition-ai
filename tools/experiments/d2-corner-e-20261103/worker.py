"""First evaluation of the back-CORNER inspection-priority use on independent holdout photos (intakes y, z; corner labels entered blind). The control head is trained once on the pooled back corner_defect rows (never on the holdout); band thresholds fixed from the development out-of-fold scores before any holdout score existed. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
def _load(name, path):
    s = importlib.util.spec_from_file_location(name, ROOT/path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


pairmod = _load('pairmod', 'tools/experiments/corner-same-photo-pair-cv-20261102/worker.py')
spec = importlib.util.spec_from_file_location('gcv', ROOT/'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
bag, sw = cv.bag, cv.sw
DRAWS, SEED = 2000, 20261101


def metrics(rows, scores, low, high):
    by = {}
    for r, s in zip(rows, scores):
        by.setdefault(r['group'], []).append((s, r['target']))
    def band(lo, hi):
        sel = [t for g in by.values() for s, t in g if lo <= s < hi]
        return (sum(sel)/len(sel), len(sel)) if sel else (None, 0)
    lo_rate, lo_n = band(-1, low)
    hi_rate, hi_n = band(high, 2)
    mixed = [g for g in by.values() if any(t for _, t in g) and not all(t for _, t in g)]
    hit = [sorted(g, key=lambda x: -x[0])[0][1] for g in mixed]
    chance = [sum(t for _, t in g)/len(g) for g in mixed]
    return dict(low_rate=lo_rate, low_areas=lo_n, high_rate=hi_rate, high_areas=hi_n, gap=None if lo_rate is None or hi_rate is None else hi_rate - lo_rate,
                mixed_photos=len(mixed), hit_at_1=sum(hit)/len(hit) if hit else None, chance=sum(chance)/len(chance) if chance else None,
                hit_gap=sum(hit)/len(hit) - sum(chance)/len(chance) if hit else None)


def bootstrap(rows, scores, low, high):
    keys = sorted({r['group'] for r in rows})
    idx_of = {}
    for i, r in enumerate(rows):
        idx_of.setdefault(r['group'], []).append(i)
    rng = random.Random(SEED)
    gaps, hits = [], []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx_of[g]]
        # resampled photos keep their identity only through the index list; rebuild groups with unique labels per draw position
        sub_rows, sub_scores, n = [], [], 0
        for g in [rng.choice(keys) for _ in keys]:
            n += 1
            for i in idx_of[g]:
                sub_rows.append(dict(rows[i], group=f'{g}#{n}'))
                sub_scores.append(scores[i])
        m = metrics(sub_rows, sub_scores, low, high)
        if m['gap'] is not None and m['hit_gap'] is not None:
            gaps.append(m['gap'])
            hits.append(m['hit_gap'])
    q = lambda v, a: sorted(v)[int(a*(len(v) - 1))]
    return dict(gap=dict(lo=q(gaps, .025), hi=q(gaps, .975)), hit_gap=dict(lo=q(hits, .025), hi=q(hits, .975)), draws=len(gaps))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'd2-corner-e-20261103':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    old = json.loads((ROOT/plan['train_rows']).read_text())
    if len(old) != plan['expected_train_rows']:
        raise ValueError('Frozen training rows differ')
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows'] or len({r['group'] for r in test}) != plan['expected_holdout_groups']:
        raise ValueError('Frozen holdout rows differ')
    sw.check_separation(old, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xo, mo = sw.features(body, old, device)
    pairmod.pair.masses = pairmod.guarded_masses
    coef, bias, _ = pairmod.pair.fit_pair(xo, mo, old)
    del xo, mo
    xt, mt = sw.features(body, test, device)
    scores = sw.score(xt, mt, coef, bias)
    low, high = plan['band_low'], plan['band_high']
    m = metrics(test, scores, low, high)
    boot = bootstrap(test, scores, low, high)
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=scores), allow_nan=False))
    criterion = dict(gap=m['gap'] >= plan['criterion_min_gap'] and boot['gap']['lo'] >= plan['criterion_min_gap_lower'],
                     hit_gap=m['hit_gap'] >= plan['criterion_min_hit_gap'] and boot['hit_gap']['lo'] > plan['criterion_min_hit_gap_lower'],
                     groups=len({r['group'] for r in test}) >= plan['criterion_min_groups'], defect_photos=sum(any(r['target'] for r in test if r['group'] == g) for g in {r['group'] for r in test}) >= plan['criterion_min_defect_photos'])
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, metrics=m, bootstrap=boot, auc=bag.auc(test, scores), same_photo=bag.auc(test, scores, True),
                   fn=sum(r['target'] == 1 and s < .5 for r, s in zip(test, scores)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(test, scores)),
                   holdout_positive=sum(r['target'] for r in test), holdout_normal=sum(1 - r['target'] for r in test), holdout_groups=len({r['group'] for r in test}),
                   band_low=low, band_high=high, device=device, typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
