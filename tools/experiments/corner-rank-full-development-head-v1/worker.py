"""Fit once on the sealed development inputs and verify the single saved head."""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import torch

from score import identity, load_head

ROOT = Path.cwd()
OUT = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
PLAN = json.loads((OUT/'plan.json').read_text())
SOURCE = ROOT/PLAN['tracked_directory']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def verified_training_rows():
    for name, expected in PLAN['input_sha256'].items():
        if digest(ROOT/name) != expected:
            raise ValueError(f'Frozen input differs: {name}')
    for name in ('worker.py', 'score.py'):
        if digest(Path(__file__).with_name(name)) != digest(SOURCE/name):
            raise ValueError(f'Worker mirror differs: {name}')
    manifest = json.loads((ROOT/PLAN['training_manifest']).read_text())
    rows = json.loads((ROOT/PLAN['rows']).read_text())
    if rows != manifest['rows'] or len(rows) != 946 or len({r['id'] for r in rows}) != 946:
        raise ValueError('Frozen training rows differ')
    groups, images = {r['group'] for r in rows}, {r['image'] for r in rows}
    if len(groups) != 257 or len(images) != 257 or images != set(manifest['photo_identity']):
        raise ValueError('Frozen training denominators differ')
    for path in images:
        old = manifest['photo_identity'][path]
        if identity(path) != {k:old[k] for k in ('raw_sha256', 'decoded_sha256')}:
            raise ValueError('Frozen original/decoded photo mismatch')
    return rows


def verify_reload(head, recovered, ref):
    fixture = torch.zeros((3, 384))
    fixture[:, 0] = torch.tensor([-1., 0., 1.])
    before = (fixture@head['coef'] + head['bias']).sigmoid()
    after = (fixture@recovered['coef'] + recovered['bias']).sigmoid()
    if any(not torch.equal(head[k], recovered[k]) for k in head):
        raise ValueError('Reloaded parameters differ')
    delta = float((before-after).abs().max())
    if delta > 2e-6 or any(not torch.equal(before >= t, after >= t) for t in (.2, .6)):
        raise ValueError('Reloaded score or threshold decision differs')
    e = load_head(ROOT/PLAN['e_head'], PLAN['input_sha256'][PLAN['e_head']])
    control = (fixture@e['coef'] + e['bias']).sigmoid().tolist()
    if ref['before_scores'] != control:
        raise ValueError('Frozen synthetic control scores differ')
    return delta, after.tolist()


def main():
    if not torch.backends.mps.is_available():
        raise RuntimeError('The frozen device MPS is required')
    if subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip() != PLAN['code_sha']:
        raise ValueError('Unexpected source commit')
    rows = verified_training_rows()
    spec = importlib.util.spec_from_file_location('rank_head', ROOT/PLAN['rank_source'])
    rank = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rank)
    from card_condition.back_triage_release import tree_sha256
    if tree_sha256(ROOT/PLAN['backbone_directory']) != PLAN['backbone_tree_sha256']:
        raise ValueError('Backbone source tree differs')
    torch.set_num_threads(2)
    body = torch.hub.load(str(ROOT/PLAN['backbone_directory']), 'dinov2_vits14',
                          source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/PLAN['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    print('Extracting original 448px features from 257 development photos', flush=True)
    features, masks = rank.corner.sw.features(body.to('mps'), rows, 'mps')
    del body
    torch.mps.empty_cache()
    print('Fitting a single rank head to 946 development regions', flush=True)
    coef, bias, convergence = rank.fit(features, masks, rows, PLAN['card_pair_weight'])
    head = dict(coef=coef, bias=bias)
    path = OUT/'corner-card-rank-four-phase-head.pt'
    torch.save(head, path)
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    delta, scores = verify_reload(head, load_head(path), ref)
    evaluation = dict(criterion_met=True, checkpoint=path.name, head_sha256=digest(path),
                      rows=len(rows), physical_cards=257, development_photos=257, convergence=convergence,
                      fixture_max_abs_diff=delta, training_calls=1, external_ai_calls=0,
                      independent_inference_calls=0, torch=torch.__version__, device='mps', code_sha=PLAN['code_sha'])
    (OUT/'diagnostics.json').write_text(json.dumps(evaluation, indent=2, allow_nan=False)+'\n')
    (OUT/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores,
                         diagnostic_evidence=evaluation), allow_nan=False)+'\n')
    print(json.dumps(evaluation), flush=True)


if __name__ == '__main__':
    main()
