"""Freeze the back-edge inspection-priority candidate that passed C1 (section 41): retrain once with the identical recipe, save the head (coef, bias) with SHA-256, reload it, rescore the same 360 holdout zones and compare against the stored section-41 scores. Reproducibility/replay check only; not a new performance claim. Common-runner only."""
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


base = _load('base', 'tools/experiments/edge-back-triage-holdout-20261031/worker.py')
sw, bag = base.sw, base.bag

if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'edge-back-triage-freeze-20261101':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    old = sw.edge_rows(json.loads((ROOT/plan['coverage']).read_text()))
    test = json.loads((ROOT/plan['holdout_rows']).read_text())
    if test != ref['rows'] or len({r['group'] for r in test}) != plan['expected_holdout_groups']:
        raise ValueError('Frozen holdout rows differ')
    stored = json.loads((ROOT/plan['stored_observations']).read_text())
    if stored['rows'] != test:
        raise ValueError('Stored observations rows differ')
    sw.check_separation(old, test)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    xo, mo = sw.features(body, old, device)
    coef, bias, _ = sw.fit(xo, mo, old)
    del xo, mo
    head_path = ROOT/plan['head_path']
    head_path.parent.mkdir(parents=True, exist_ok=True)
    if head_path.exists():
        raise ValueError('Head file already exists; refuse to overwrite')
    torch.save(dict(coef=coef.detach().cpu(), bias=bias.detach().cpu() if torch.is_tensor(bias) else torch.tensor(float(bias)), band_low=plan['band_low'], band_high=plan['band_high'],
                    recipe='ViT-S/14 448 tokens + control head (section 23)', train_rows=len(old), source_record=plan['stored_record']), head_path)
    head_sha = hashlib.sha256(head_path.read_bytes()).hexdigest()
    saved = torch.load(head_path, map_location='cpu', weights_only=True)
    xt, mt = sw.features(body, test, device)
    fresh = sw.score(xt, mt, coef, bias)
    replay = sw.score(xt, mt, saved['coef'].to(coef.device), saved['bias'].to(coef.device) if torch.is_tensor(saved['bias']) else saved['bias'])
    old_scores = stored['scores']
    save_reload_diff = max(abs(a - b) for a, b in zip(fresh, replay))
    retrain_diff = max(abs(a - b) for a, b in zip(replay, old_scores))
    low, high = plan['band_low'], plan['band_high']
    band = lambda s: 0 if s < low else (2 if s >= high else 1)
    band_changes = sum(band(a) != band(b) for a, b in zip(replay, old_scores))
    m_new, m_old = base.metrics(test, replay, low, high), base.metrics(test, old_scores, low, high)
    criterion = dict(save_reload=save_reload_diff <= plan['criterion_save_reload_max'], retrain=retrain_diff <= plan['criterion_retrain_max'], bands=band_changes <= plan['criterion_band_changes_max'])
    (out/'observations.json').write_text(json.dumps(dict(rows=test, scores=replay), allow_nan=False))
    summary = dict(criterion_met=all(criterion.values()), criterion=criterion, head_path=plan['head_path'], head_sha256=head_sha, save_reload_max_abs_diff=save_reload_diff,
                   retrain_max_abs_diff=retrain_diff, band_changes=band_changes, rows=len(test), metrics_replay=m_new, metrics_stored=m_old, auc_replay=bag.auc(test, replay), device=device,
                   typed_point_response='not_evaluated', training_calls=1, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
