"""C5 v1.8 independent holdout: back-face observation-limit score from ViT-S/14 448 patch mean pooling (§57 recipe), standardized L2 logistic fit once on the 147 development back faces (obslimit-meanstd-20261101 rows), evaluated once on the labeled holdout back faces (AUC + photo-group bootstrap). Common-runner only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ms = _load('obsms', 'tools/experiments/obslimit-meanstd-20261101/worker.py')
bag, sw = ms.bag, ms.sw


def pooled(body, rows, device):
    x, m = sw.features(body, rows, device)
    return (x*m[..., None]).sum(1)/m.sum(1, keepdim=True)


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'obslimit-back-holdout-20261103':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    dev = [r for r in json.loads((ROOT/plan['train_rows']).read_text()) if r['side'] == 'back']
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if len(dev) != plan['expected_train_rows'] or test != ref['rows']:
        raise ValueError('Frozen rows differ')
    if {r['side'] for r in test} != {'back'}:
        raise ValueError('Holdout must be back faces only')
    sw.check_separation(dev, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    scores = ms.fit_predict(pooled(body, dev, device), torch.tensor([r['target'] for r in dev]), pooled(body, test, device))
    auc, boot = bag.auc(test, scores), ms.auc_ci(test, scores)
    positive = sum(r['target'] for r in test)
    criterion = dict(auc=auc >= plan['criterion_min_auc'], auc_lower=boot['lo'] >= plan['criterion_min_auc_lower'],
                     rows=len(test) >= plan['criterion_min_rows'], positives=positive >= plan['criterion_min_positive'])
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=scores), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, auc=auc, bootstrap=boot, holdout_rows=len(test), holdout_positive=positive,
                   holdout_groups=len({r['group'] for r in test}), train_rows=len(dev), device=device, typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
