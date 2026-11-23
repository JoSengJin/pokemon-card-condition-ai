"""Train the corner linear head on two views per zone (phases (0,0) and (7,7)); score with the four-phase average."""
import gc
import importlib.util
import json
import os
import tempfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import numpy as np
import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grid = _load('grid_worker', ROOT / 'tools/experiments/corner-grid-average-20261121/worker.py')
transform = _load('phase_transform', Path(__file__).with_name('transform.py'))
rank, PHASES = grid.rank, grid.PHASES
TRAIN = [(0, 0), (7, 7)]


def verify(plan, ref):
    """Refuse to run when mirrors, frozen inputs or the frozen rows differ; returns replay rows, prior plan, kept indices."""
    for name in ('worker.py', 'transform.py'):
        if (Path(__file__).parent / name).read_bytes() != (ROOT / plan['tracked_directory'] / name).read_bytes():
            raise ValueError('Mirror mismatch: ' + name)
    for path, h in plan['input_sha256'].items():
        if sha256((ROOT / path).read_bytes()).hexdigest() != h:
            raise ValueError('Frozen input differs: ' + path)
    replay = json.loads((ROOT / plan['replayed_observations']).read_text())
    e = json.loads((ROOT / plan['e_observations']).read_text())
    prior = json.loads((ROOT / plan['original_plan']).read_text())
    keep = [i for i, r in enumerate(replay['rows']) if r['group'] != plan['excluded_group']]
    if ref['rows'] != [replay['rows'][i] for i in keep] or e['rows'] != replay['rows'] or len(ref['before_scores']) != len(keep):
        raise ValueError('Reference or exclusion differs')
    return replay, prior, keep


def extract(rows, body, folder):
    """Patch features and valid-patch masks of every phase, one photo decode per photo, written to disk-backed arrays."""
    xs = [np.lib.format.open_memmap(folder / f'x{k}.npy', mode='w+', dtype=np.float32, shape=(len(rows), 1024, 384)) for k in range(len(PHASES))]
    ms = [np.zeros((len(rows), 1024), dtype=bool) for _ in PHASES]
    by_image = defaultdict(list)
    for i, r in enumerate(rows):
        by_image[r['image']].append(i)
    with torch.inference_mode():
        for n, (image, inds) in enumerate(by_image.items(), 1):
            tensors = rank.sw.view_tensors(image, [rows[i]['box'] for i in inds], 448)
            for i, t in zip(inds, tensors, strict=True):
                mask = rank.sw.physical_pixel_mask(image, rows[i]['box'], halo=0, image_size=448)
                for k, (dx, dy) in enumerate(PHASES):
                    moved, real = grid.moved_input(t, mask, dx, dy)
                    z = body.forward_features(moved[None].to('mps'))['x_norm_patchtokens'].cpu()[0]
                    if z.shape != (1024, 384) or not torch.isfinite(z).all():
                        raise ValueError('Unexpected feature tensor')
                    xs[k][i] = z.numpy()
                    ms[k][i] = real.reshape(32, 14, 32, 14).any(3).any(1).flatten().numpy()
            if n % 50 == 0:
                print(f'Extracted {n}/{len(by_image)} photos', flush=True)
    for x in xs:
        x.flush()
    return xs, ms


def fit_fold(xs, ms, rows, train, weight):
    """Fit the unchanged card-ranking head on the training zones duplicated once per TRAIN phase (float64 up front, no extra copy)."""
    idx, used = np.array(train), [PHASES.index(p) for p in TRAIN]
    x = transform.stack_views([xs[k] for k in used], idx, torch.float64)
    m = transform.stack_views([ms[k] for k in used], idx, torch.bool)
    return rank.head.fit(x, m, transform.expand_rows([rows[i] for i in train], TRAIN), weight)


def score_fold(xs, ms, holdout, coef, bias):
    """Four-phase mean of the per-phase maximum patch probability, as the stored control."""
    idx = np.array(holdout)
    per = [rank.sw.score(torch.as_tensor(x[idx]), torch.as_tensor(m[idx]), coef, bias) for x, m in zip(xs, ms, strict=True)]
    return [sum(v) / len(PHASES) for v in zip(*per, strict=True)]


def evaluate(rows, candidate, control, prior, plan):
    a, b = [rank.summarize(rows, s, prior) for s in (control, candidate)]
    misses = grid.missed_cards(rows, candidate, prior['fixed_low']) - grid.missed_cards(rows, control, prior['fixed_low'])
    criterion = dict(fixed_fp=b['fixed_fp'] <= plan['max_fixed_fp'], fixed_miss=b['fixed_miss'] <= plan['max_fixed_miss'],
                     no_new_misses=not misses, matched_miss=b['matched']['miss'] <= plan['max_matched_miss'],
                     within_photo=b['same_photo_auc'] >= a['same_photo_auc'] - plan['max_within_auc_drop'])
    return dict(control=a, candidate=b, criterion=criterion, criterion_met=all(criterion.values()), new_missed_cards=sorted(misses))


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    replay, prior, keep = verify(plan, ref)
    rows = replay['rows']
    folds = rank.cv.fold_of(rows)
    splits = [([i for i, r in enumerate(rows) if folds[r['group']] != f], [i for i, r in enumerate(rows) if folds[r['group']] == f])
              for f in range(rank.cv.FOLDS)]
    for tr, ho in splits:
        rank.sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
    heads = torch.load(ROOT / plan['replayed_heads'], map_location='cpu', weights_only=True)
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    body = torch.hub.load(str(ROOT / prior['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT / prior['backbone_weights'], map_location='cpu', weights_only=True))
    scores, convergence, delta = [None] * len(rows), [], 0.
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        xs, ms = extract(rows, body.to('mps'), Path(tmp))
        del body
        for f, (tr, ho) in enumerate(splits):
            # Features must reproduce the stored single-view control head on the unshifted phase.
            idx, head = np.array(ho), heads[f]
            replayed = rank.sw.score(torch.as_tensor(xs[0][idx]), torch.as_tensor(ms[0][idx]), head['coef'], head['bias'])
            delta = max([delta] + [abs(s - replay['scores'][i]) for i, s in zip(ho, replayed, strict=True)])
            coef, bias, done = fit_fold(xs, ms, rows, tr, plan['card_pair_weight'])
            convergence.append(done)
            for i, s in zip(ho, score_fold(xs, ms, ho, coef, bias), strict=True):
                scores[i] = s
            gc.collect()
            print(f'Fold {f + 1} done', flush=True)
        del xs, ms
    if delta > 2e-6:
        raise ValueError(f'Unshifted replay differs: {delta:.8g}')
    candidate = [scores[i] for i in keep]
    report = dict(evaluate(ref['rows'], candidate, ref['before_scores'], prior, plan), replay_delta=delta, convergence=convergence,
                  train_phases=TRAIN, score_phases=PHASES, training_calls=len(convergence), external_ai_calls=0)
    (out / 'evaluation.json').write_text(json.dumps(report, allow_nan=False, indent=2))
    (out / 'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=candidate), allow_nan=False))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run()
