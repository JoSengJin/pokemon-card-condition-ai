"""Score the stored four-phase corner heads with a half-coverage patch validity rule."""
from collections import defaultdict
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grid = load('grid_worker', 'tools/experiments/corner-grid-average-20261121/worker.py')
rank = grid.rank


def phase_scores(body, tensor, mask, head, patch_valid):
    """Per phase (control any-rule, candidate coverage rule) max-patch probabilities from one feature pass."""
    control, candidate = [], []
    with torch.inference_mode():
        for dx, dy in grid.PHASES:
            image, real = grid.moved_input(tensor, mask, dx, dy)
            z = body.forward_features(image[None].to('mps'))['x_norm_patchtokens'].cpu()[0]
            logits = z @ head['coef'] + head['bias']
            for out, valid in ((control, real.reshape(32, 14, 32, 14).any(3).any(1).flatten()),
                               (candidate, patch_valid(real))):
                out.append(float(logits.masked_fill(~valid, -torch.inf).amax().sigmoid()))
    return control, candidate


def check_inputs(plan, ref):
    if Path(__file__).read_bytes() != (ROOT / plan['tracked_directory'] / 'worker.py').read_bytes():
        raise ValueError('Mirror mismatch')
    for path, digest in plan['input_sha256'].items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input differs: ' + path)
    replay = json.loads((ROOT / plan['replayed_observations']).read_text())
    keep = [i for i, r in enumerate(replay['rows']) if r['group'] != plan['excluded_group']]
    if ref['rows'] != [replay['rows'][i] for i in keep]:
        raise ValueError('Reference or exclusion differs')
    rank.sw.check_separation([], ref['rows'])
    return rank.cv.fold_of(replay['rows'])


def score_all(plan, rows, folds, patch_valid):
    prior = json.loads((ROOT / plan['original_plan']).read_text())
    heads = torch.load(ROOT / plan['replayed_heads'], map_location='cpu', weights_only=True)
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    body = torch.hub.load(str(ROOT / prior['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT / prior['backbone_weights'], map_location='cpu', weights_only=True))
    body = body.to('mps')
    by_image = defaultdict(list)
    for i, r in enumerate(rows):
        by_image[r['image']].append(i)
    values = [None] * len(rows)
    for n, (image, inds) in enumerate(by_image.items(), 1):
        views = rank.sw.view_tensors(image, [rows[i]['box'] for i in inds], 448)
        for i, t in zip(inds, views, strict=True):
            mask = rank.sw.physical_pixel_mask(image, rows[i]['box'], halo=0, image_size=448)
            values[i] = phase_scores(body, t, mask, heads[folds[rows[i]['group']]], patch_valid)
        if n % 50 == 0:
            print(f'Completed {n}/{len(by_image)} photos', flush=True)
    return values, prior


def evaluate(plan, prior, rows, old, candidate):
    a, b = rank.summarize(rows, old, prior), rank.summarize(rows, candidate, prior)
    misses = grid.missed_cards(rows, candidate, prior['fixed_low']) - grid.missed_cards(rows, old, prior['fixed_low'])
    criterion = dict(fixed_fp=b['fixed_fp'] <= plan['max_fixed_fp'],
                     fixed_miss=b['fixed_miss'] <= plan['max_fixed_miss'],
                     no_new_misses=not misses,
                     matched_miss=b['matched']['miss'] <= plan['max_matched_miss'],
                     within_photo=b['same_photo_auc'] >= a['same_photo_auc'] - plan['max_within_auc_drop'])
    return dict(control=a, candidate=b, criterion=criterion, criterion_met=all(criterion.values()),
                new_missed_cards=sorted(misses))


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    folds = check_inputs(plan, ref)
    rows, old = ref['rows'], ref['before_scores']
    transform = load('coverage_transform', plan['tracked_directory'] + '/transform.py')
    values, prior = score_all(plan, rows, folds, transform.patch_valid)
    control = [sum(v[0]) / len(v[0]) for v in values]
    delta = max(abs(c - s) for c, s in zip(control, old, strict=True))
    if delta > 2e-6:
        raise ValueError(f'Control replay differs: {delta:.8g}')
    candidate = [sum(v[1]) / len(v[1]) for v in values]
    report = dict(evaluate(plan, prior, rows, old, candidate), replay_delta=delta, phases=grid.PHASES,
                  training_calls=0, external_ai_calls=0)
    (out / 'phase-scores.json').write_text(json.dumps(values, allow_nan=False))
    (out / 'evaluation.json').write_text(json.dumps(report, allow_nan=False, indent=2))
    (out / 'observations.json').write_text(json.dumps(dict(rows=rows, scores=candidate), allow_nan=False))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
