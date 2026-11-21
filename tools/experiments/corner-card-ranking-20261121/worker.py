"""Score the unchanged Candidate E development folds with one new loss term."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('card_rank_head', Path(__file__).with_name('head.py'))
head = importlib.util.module_from_spec(spec)
spec.loader.exec_module(head)
corner = head.corner
bag, cv, sw = corner.bag, corner.cv, corner.sw


def inputs(plan, ref):
    for name in ('worker.py', 'head.py'):
        if Path(__file__).with_name(name).read_bytes() != (ROOT / plan['tracked_directory'] / name).read_bytes():
            raise ValueError('Experiment mirror differs: ' + name)
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    original = json.loads((ROOT / plan['e_observations']).read_text())
    rows = json.loads((ROOT / plan['rows']).read_text())
    if rows != original['rows'] or rows != ref['rows'] or original['scores'] != ref['before_scores']:
        raise ValueError('Candidate E reference differs')
    return rows


def summarize(rows, scores, plan):
    card_miss = head.template.card_miss
    positive_scores, normal_scores = {}, {}
    for row, score in zip(rows, scores, strict=True):
        dest = positive_scores if row['target'] else normal_scores
        group = row['group']
        dest[group] = max(dest.get(group, 0.0), score)
    max_threshold = sorted(positive_scores.values())[plan['matched_miss_budget']]
    matched_miss = card_miss(rows, scores, plan['matched_fp_budget'])
    return dict(
        auc=bag.auc(rows, scores),
        same_photo_auc=bag.auc(rows, scores, True),
        card_auc=sum((p > n) + .5*(p == n) for p in positive_scores.values()
                     for g, n in normal_scores.items() if g not in positive_scores)
                 / len(positive_scores) / matched_miss['normals'],
        fixed_miss=card_miss(rows, scores, 0, fixed=plan['fixed_low'])['miss'],
        fixed_fp=card_miss(rows, scores, 0, fixed=plan['fixed_high'])['false_alarm'],
        matched=matched_miss,
        fp_at_matched_miss=card_miss(rows, scores, 0, fixed=max_threshold)['false_alarm'],
    )


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    rows = inputs(plan, ref)
    folds = cv.fold_of(rows)
    splits = [([i for i, r in enumerate(rows) if folds[r['group']] != f],
               [i for i, r in enumerate(rows) if folds[r['group']] == f]) for f in range(cv.FOLDS)]
    for train, holdout in splits:
        sw.check_separation([rows[i] for i in train], [rows[i] for i in holdout])
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT / plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT / plan['backbone_weights'], map_location='cpu', weights_only=True))
    print(f'Extracting 448px features for {len(rows)} zones on {device}', flush=True)
    x, masks = sw.features(body.to(device), rows, device)
    scores, convergence = [None]*len(rows), []
    for f, (train, holdout) in enumerate(splits):
        t, h = torch.tensor(train), torch.tensor(holdout)
        print(f'Fold {f + 1}: train={len(train)}, holdout={len(holdout)}', flush=True)
        coef, bias, done = head.fit(x[t], masks[t], [rows[i] for i in train], plan['card_pair_weight'])
        convergence.append(done)
        for i, score in zip(holdout, sw.score(x[h], masks[h], coef, bias), strict=True):
            scores[i] = score
    candidate = summarize(rows, scores, plan)
    control = summarize(rows, ref['before_scores'], plan)
    gate = plan['card_gate']
    criterion = dict(matched_miss=candidate['matched']['miss'] <= gate['max_matched_miss'],
                     matched_fp=candidate['fp_at_matched_miss'] <= gate['max_matched_fp'],
                     fixed_miss=candidate['fixed_miss'] <= gate['max_fixed_miss'],
                     fixed_fp=candidate['fixed_fp'] <= gate['max_fixed_fp'],
                     within_photo=candidate['same_photo_auc'] >= control['same_photo_auc'] - gate['max_within_auc_drop'])
    evaluation = dict(control=control, candidate=candidate, criterion=criterion,
                      criterion_met=all(criterion.values()), device=device, convergence=convergence,
                      training_calls=len(convergence), external_ai_calls=0)
    (out / 'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    (out / 'evaluation.json').write_text(json.dumps(evaluation, allow_nan=False, indent=2))
    print(json.dumps(evaluation, allow_nan=False), flush=True)


if __name__ == '__main__':
    run()
