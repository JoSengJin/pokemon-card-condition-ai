"""Train and score the card-ranking corner head on apex-upper-left oriented zones."""
from collections import defaultdict
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
spec = importlib.util.spec_from_file_location('grid_worker', ROOT / 'tools/experiments/corner-grid-average-20261121/worker.py')
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)
spec = importlib.util.spec_from_file_location('orient_transform', Path(__file__).with_name('transform.py'))
orient = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orient)
rank, PHASES = grid.rank, grid.PHASES
sw = rank.sw


def oriented_views(rows, indices):
    """Decode each photo once; yield (row index, flipped tensor, flipped pixel mask)."""
    by_image = defaultdict(list)
    for i in indices:
        by_image[rows[i]['image']].append(i)
    for n, (image, inds) in enumerate(by_image.items(), 1):
        views = sw.view_tensors(image, [rows[i]['box'] for i in inds], 448)
        for i, t in zip(inds, views, strict=True):
            mask = sw.physical_pixel_mask(image, rows[i]['box'], halo=0, image_size=448)
            yield (i, *orient.canonical(t, mask, rows[i]['area']))
        if n % 50 == 0:
            print(f'Decoded {n}/{len(by_image)} photos', flush=True)


def patch_features(body, tensor, mask, device):
    z = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
    return z, mask.reshape(32, 14, 32, 14).any(3).any(1).flatten()


def extract_train(body, rows, device):
    """Unshifted oriented features for every fitting row, as the control's training view."""
    x, masks = [None]*len(rows), [None]*len(rows)
    with torch.inference_mode():
        for i, t, m in oriented_views(rows, range(len(rows))):
            x[i], masks[i] = patch_features(body, t, m, device)
    return torch.stack(x), torch.stack(masks)


def score_four_phases(body, rows, keep, heads, folds, device):
    """Each phase shifts the already-flipped input; every row uses its own fold's head."""
    values = {}
    with torch.inference_mode():
        for i, t, m in oriented_views(rows, keep):
            head = heads[folds[rows[i]['group']]]
            scores = []
            for dx, dy in PHASES:
                image, real = grid.moved_input(t, m, dx, dy)
                z, valid = patch_features(body, image, real, device)
                logits = (z@head['coef'] + head['bias']).masked_fill(~valid, -torch.inf)
                scores.append(float(logits.amax().sigmoid()))
            values[i] = scores
    return [values[i] for i in keep]


def verify(plan, ref):
    for name in ('worker.py', 'transform.py'):
        if Path(__file__).with_name(name).read_bytes() != (ROOT/plan['tracked_directory']/name).read_bytes():
            raise ValueError('Mirror mismatch: ' + name)
    for path, h in plan['input_sha256'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest() != h:
            raise ValueError('Frozen input differs: ' + path)
    replay = json.loads((ROOT/plan['replayed_observations']).read_text())
    keep = [i for i, r in enumerate(replay['rows']) if r['group'] != plan['excluded_group']]
    if ref['rows'] != [replay['rows'][i] for i in keep] or len(keep) != plan['expected_rows']:
        raise ValueError('Reference or exclusion differs')
    return replay['rows'], keep


def fit_folds(x, masks, rows, folds, weight):
    heads = []
    for f in range(rank.cv.FOLDS):
        train = [i for i, r in enumerate(rows) if folds[r['group']] != f]
        hold = [i for i, r in enumerate(rows) if folds[r['group']] == f]
        sw.check_separation([rows[i] for i in train], [rows[i] for i in hold])
        t = torch.tensor(train)
        coef, bias, done = rank.head.fit(x[t], masks[t], [rows[i] for i in train], weight)
        heads.append(dict(coef=coef, bias=bias, convergence=done))
        print(f'Fold {f+1} fitted on {len(train)} rows', flush=True)
    return heads


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    all_rows, keep = verify(plan, ref)
    prior = json.loads((ROOT/plan['original_plan']).read_text())
    rows, control = ref['rows'], ref['before_scores']
    folds = rank.cv.fold_of(all_rows)
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    device = 'mps'
    body = torch.hub.load(str(ROOT/prior['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/prior['backbone_weights'], map_location='cpu', weights_only=True))
    body = body.to(device)
    x, masks = extract_train(body, all_rows, device)
    heads = fit_folds(x, masks, all_rows, folds, prior['card_pair_weight'])
    values = score_four_phases(body, all_rows, keep, heads, folds, device)
    candidate = [sum(v)/len(PHASES) for v in values]
    a, b = rank.summarize(rows, control, prior), rank.summarize(rows, candidate, prior)
    misses = grid.missed_cards(rows, candidate, prior['fixed_low']) - grid.missed_cards(rows, control, prior['fixed_low'])
    gate = plan['gate']
    criterion = dict(fixed_fp=b['fixed_fp'] <= gate['max_fixed_fp'], fixed_miss=b['fixed_miss'] <= gate['max_fixed_miss'],
                     no_new_misses=not misses, matched_miss=b['matched']['miss'] <= gate['max_matched_miss'],
                     within_photo=b['same_photo_auc'] >= a['same_photo_auc'] - gate['max_within_auc_drop'])
    report = dict(control=a, candidate=b, criterion=criterion, criterion_met=all(criterion.values()),
                  new_missed_cards=sorted(misses), phases=PHASES, device=device,
                  convergence=[h['convergence'] for h in heads], training_calls=len(heads), external_ai_calls=0)
    (out/'phase-scores.json').write_text(json.dumps(values, allow_nan=False))
    (out/'evaluation.json').write_text(json.dumps(report, allow_nan=False, indent=2))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=candidate), allow_nan=False))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
