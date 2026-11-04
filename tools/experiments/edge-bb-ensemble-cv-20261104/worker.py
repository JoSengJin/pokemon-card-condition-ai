"""Back-edge development CV: the frozen C1 candidate recipe (control head, final-layer 448px tokens, 788 pooled zones, 137 photo groups, same group folds) trained with DINOv2 ViT-B/14, then the mean of the stored ViT-S/14 out-of-fold control scores and the ViT-B/14 scores vs the ViT-S/14 scores. Common-runner only."""
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


gcv = _load('gcv', 'tools/experiments/edge-back-grouped-cv-20261031/worker.py')
vitb = _load('vitb', 'tools/experiments/surface-vitb14-cv-20261104/worker.py')
bag, sw = gcv.bag, gcv.sw


def control_oof(x, m, rows, fold):
    scores = [0.]*len(rows)
    for f in range(gcv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        t, h = torch.tensor(tr), torch.tensor(ho)
        coef, bias, _ = sw.fit(x[t], m[t], [rows[i] for i in tr])
        for i, s in zip(ho, sw.score(x[h], m[h], coef, bias)):
            scores[i] = s
    return scores


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'edge-bb-ensemble-cv-20261104':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    stored = json.loads((ROOT/plan['stored_oof']).read_text())
    rows, s_scores = stored['rows'], stored['control']
    fold = {g: int(f) for g, f in stored['fold'].items()}
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vitb14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = vitb.backbone_features(body, rows, device)
    b_scores = control_oof(x, m, rows, fold)
    scores = [(a+b)/2 for a, b in zip(s_scores, b_scores)]
    vitb.DRAWS = 2000
    boot = vitb.paired_bootstrap(rows, scores, s_scores)
    auc_e, auc_s, auc_b = bag.auc(rows, scores), bag.auc(rows, s_scores), bag.auc(rows, b_scores)
    crit = dict(diff=auc_e-auc_s >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, vits14_scores=s_scores, vitb14_scores=b_scores), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_ensemble=auc_e, auc_vits14=auc_s, auc_vitb14=auc_b, diff=auc_e-auc_s, diff_bootstrap=boot,
                   same_photo_auc_ensemble=bag.auc(rows, scores, True), same_photo_auc_vits14=bag.auc(rows, s_scores, True), same_photo_auc_vitb14=bag.auc(rows, b_scores, True),
                   positive=sum(r['target'] for r in rows), normal=sum(1 - r['target'] for r in rows), rows=len(rows), groups=len({r['group'] for r in rows}), device=device,
                   typed_point_response='not_evaluated', training_calls=gcv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
