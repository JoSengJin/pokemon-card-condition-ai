"""Second independent evaluation of the back-CORNER inspection-priority use on NEW holdout photos (intakes aa, ab, ac; corner labels entered blind). Candidate = control head trained once on 338 pooled back-corner zones; paired control = the same recipe on the original 170 zones (the head judged in section 43). Only the training-set size differs. Band thresholds 0.41/0.63 are frozen from the development out-of-fold scores. Criterion is judged on the candidate only. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import random
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
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
    if plan['hypothesis_id'] != 'edge-back-corner-more-holdout-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    big = json.loads((ROOT/plan['train_rows']).read_text())
    old_ids = {r['id'] for r in json.loads((ROOT/plan['old_rows']).read_text()) if r['category'] == plan['train_category']}
    small = [r for r in big if r['id'] in old_ids]
    if len(big) != plan['expected_train_rows'] or len(small) != plan['expected_control_rows']:
        raise ValueError('Frozen training rows differ')
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows'] or len({r['group'] for r in test}) != plan['expected_holdout_groups'] or len(test) != plan['expected_holdout_rows']:
        raise ValueError('Frozen holdout rows differ')
    sw.check_separation(big, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xt, mt = sw.features(body, test, device)
    result = {}
    for name, rows in (('candidate', big), ('control', small)):
        x, m_ = sw.features(body, rows, device)
        coef, bias, _ = sw.fit(x, m_, rows)
        del x, m_
        scores = sw.score(xt, mt, coef, bias)
        low, high = plan['band_low'], plan['band_high']
        result[name] = dict(train_rows=len(rows), metrics=metrics(test, scores, low, high), bootstrap=bootstrap(test, scores, low, high), auc=bag.auc(test, scores),
                            same_photo=bag.auc(test, scores, True), fn=sum(r['target'] == 1 and s < .5 for r, s in zip(test, scores)), fp=sum(r['target'] == 0 and s >= .5 for r, s in zip(test, scores)), scores=scores)
    cand = result['candidate']
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=cand['scores']), allow_nan=False))
    m, boot = cand['metrics'], cand['bootstrap']
    groups = {r['group'] for r in test}
    criterion = dict(gap=m['gap'] >= plan['criterion_min_gap'] and boot['gap']['lo'] >= plan['criterion_min_gap_lower'],
                     hit_gap=m['hit_gap'] >= plan['criterion_min_hit_gap'] and boot['hit_gap']['lo'] > plan['criterion_min_hit_gap_lower'],
                     groups=len(groups) >= plan['criterion_min_groups'], defect_photos=sum(any(r['target'] for r in test if r['group'] == g) for g in groups) >= plan['criterion_min_defect_photos'])
    for v in result.values():
        v.pop('scores')
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, candidate=result['candidate'], control=result['control'], holdout_positive=sum(r['target'] for r in test),
                   holdout_normal=sum(1 - r['target'] for r in test), holdout_groups=len(groups), band_low=plan['band_low'], band_high=plan['band_high'], device=device,
                   typed_point_response='not_evaluated', training_calls=2, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
