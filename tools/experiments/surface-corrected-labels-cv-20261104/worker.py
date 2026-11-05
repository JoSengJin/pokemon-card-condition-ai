"""Corrected-label training: surface dev pool (1791 zones, ViT-S/14 last layer, same head/folds/seeds). Arm B trains on labels where the 259 re-judged zones take the user's new judgment (section 97; unknown/impossible zones excluded from training and evaluation); control = earlier original-label out-of-fold scores. Both arms are scored on held-out cards and evaluated on the corrected labels (primary) and original labels (secondary). Development CV; the evaluation labels are only partly corrected, so this tests learnability of the new judgment pattern, not general accuracy."""
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


base = _load('base', 'tools/experiments/surface-negfilter-cv-20261104/worker.py')
cv, bag, sw, others = base.cv, base.bag, base.sw, base.others


def corrected_targets(rows, answers):
    """Per-row corrected target (1/0) or None when unknown; rows without a re-judgment keep their original target."""
    out = []
    for r in rows:
        a = answers.get(r['id'])
        out.append(r['target'] if a is None else (1 if a == '결함' else 0 if a == '정상' else None))
    return out


def train_oof(x, m, rows, targets):
    fold, scores = cv.fold_of(rows), [0.]*len(rows)
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f and targets[i] is not None]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])
        fit_rows = [dict(rows[i], target=targets[i]) for i in tr]
        coef, bias, _ = sw.fit(x[torch.tensor(tr)], m[torch.tensor(tr)], fit_rows)
        for i, s in zip(ho, sw.score(x[torch.tensor(ho)], m[torch.tensor(ho)], coef, bias)):
            scores[i] = s
    return scores


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-corrected-labels-cv-20261104':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    control = json.loads((ROOT/plan['vits14_scores']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows'] or len(control) != len(rows):
        raise ValueError('Frozen rows differ')
    sel = {z['n']: z['id'] for z in json.loads((ROOT/plan['selection']).read_text())}
    answers = {}
    for name in plan['answer_files']:
        for line in (ROOT/name).read_text().split():
            key, value = line.split('=')
            answers[sel[int(key[1:])]] = value
    targets = corrected_targets(rows, answers)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), base.BACKBONE, source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = base.backbone_features(body, rows, device)
    _lbfgs = torch.optim.LBFGS
    torch.optim.LBFGS = lambda params, **kw: _lbfgs(params, **{**kw, 'max_iter': 1000})
    sw.fit = base.fit_pool
    scores = train_oof(x, m, rows, targets)
    keep = [i for i, t in enumerate(targets) if t is not None]
    eval_rows = [dict(rows[i], target=targets[i]) for i in keep]
    new, old = [scores[i] for i in keep], [control[i] for i in keep]
    auc_new, auc_old = bag.auc(eval_rows, new), bag.auc(eval_rows, old)
    boot = base.paired_bootstrap(eval_rows, new, old)
    orig_rows = [rows[i] for i in keep]
    crit = dict(diff=auc_new-auc_old >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, vits14_scores=control, new_targets=targets), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_corrected_trained_on_corrected_labels=auc_new, auc_original_trained_on_corrected_labels=auc_old,
                   diff=auc_new-auc_old, diff_bootstrap=boot, auc_corrected_trained_on_original_labels=bag.auc(orig_rows, new), auc_original_trained_on_original_labels=bag.auc(orig_rows, old),
                   eval_rows=len(keep), eval_positive=sum(targets[i] for i in keep), excluded_unknown=len(rows)-len(keep), rejudged=len(answers),
                   original_positive=sum(r['target'] for r in rows), device=device, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
