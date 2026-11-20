"""Back-corner development CV: candidate-E recipe (same-photo pair ranking head, DINOv2 ViT-S/14) with the corner input size changed 448 -> 224 (16x16 patches); only that variable changes. Same 946 zones and group folds as candidate E, whose stored out-of-fold scores are the control. Reports photo-level miss/false-alarm events at the frozen thresholds. Common-runner only."""
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
LOW, HIGH, SIZE, GRID = .281, .509, 224, 16


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


corner = _load('corner', 'tools/experiments/corner-same-photo-pair-cv-20261102/worker.py')
pair, bag, cv, sw = corner.pair, corner.bag, corner.cv, corner.sw


def features224(body, rows, device):
    """sw.features with the input size 224: (n, 256, 384) patch tokens and the physical-pixel patch mask (resize padding excluded)."""
    by_image, done = defaultdict(list), {}
    for r in rows:
        by_image[r['image']].append(r)
    with torch.inference_mode():
        for path, items in by_image.items():
            for r, tensor in zip(items, sw.view_tensors(path, [i['box'] for i in items], SIZE)):
                z = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
                if z.shape != (GRID*GRID, 384) or not torch.isfinite(z).all():
                    raise ValueError('Unexpected feature tensor')
                m = sw.physical_pixel_mask(path, r['box'], halo=0, image_size=SIZE).reshape(GRID, 14, GRID, 14).any(3).any(1).flatten()
                done[r['id']] = (z, m)
    return torch.stack([done[r['id']][0] for r in rows]), torch.stack([done[r['id']][1] for r in rows])


def l_events(rows, scores):
    """Photo-level events (D3 definition L): a positive photo is missed when any defect zone scores < LOW; a normal photo is a false alarm when any zone scores >= HIGH."""
    groups = defaultdict(list)
    for r, s in zip(rows, scores):
        groups[r['group']].append((r['target'], s))
    pos = [v for v in groups.values() if any(t for t, _ in v)]
    neg = [v for v in groups.values() if not any(t for t, _ in v)]
    return dict(miss=sum(any(t and s < LOW for t, s in v) for v in pos), positives=len(pos),
                false_alarm=sum(any(s >= HIGH for _, s in v) for v in neg), normals=len(neg))


def verify(plan, ref, rows):
    """Refuse to run when the plan, mirrored source, frozen inputs or frozen rows differ."""
    if plan['hypothesis_id'] != 'corner-input224-cv-20261120':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    rows = json.loads((ROOT/plan['rows']).read_text())
    e_obs = json.loads((ROOT/plan['e_observations']).read_text())
    verify(plan, ref, rows)
    if rows != e_obs['rows']:
        raise ValueError('Control rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    x, m = features224(body.to(device), rows, device)
    pair.masses = corner.guarded_masses
    scores, e_scores = corner.oof(x, m, rows, pair.fit_pair), e_obs['scores']
    new, old = l_events(rows, scores), l_events(rows, e_scores)
    auc_new, auc_old = bag.auc(rows, scores), bag.auc(rows, e_scores)
    crit = dict(miss=new['miss'] <= plan['max_miss'], false_alarm=new['false_alarm'] <= plan['max_false_alarm'], auc=auc_new >= plan['min_auc'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, e448_scores=e_scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, events_224=new, events_e448=old, auc_224=auc_new, auc_e448=auc_old,
                   same_photo_auc_224=bag.auc(rows, scores, True), same_photo_auc_e448=bag.auc(rows, e_scores, True),
                   delta_miss=new['miss'] - old['miss'], delta_false_alarm=new['false_alarm'] - old['false_alarm'],
                   rows=len(rows), groups=len({r['group'] for r in rows}), device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)


if __name__ == '__main__':
    run()
