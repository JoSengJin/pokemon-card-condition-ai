"""Same recipe as section 42/53 (ViT-S/14 448 + control head, 411 back-surface zones, group folds). Only TRAINING labels of zones re-judged under the current definition change (old -> new); both arms scored against the NEW truth on those zones. Development only."""
import hashlib
import importlib.util
import json
import math
import os
import random
from pathlib import Path

import torch
from PIL import Image, ImageOps

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


others = _load('others', 'tools/experiments/edge-back-triage-others-20261101/worker.py')
cv, bag, sw = others.cv, others.bag, others.sw
MARGIN, DRAWS, SEED = 0.20, 2000, 20261101
CELL = {'upper_left': (0, 0), 'upper_center': (1, 0), 'upper_right': (2, 0), 'middle_left': (0, 1), 'center': (1, 1), 'middle_right': (2, 1),
        'lower_left': (0, 2), 'lower_center': (1, 2), 'lower_right': (2, 2)}


def paired_bootstrap(rows, new, old):
    keys = sorted({r['group'] for r in rows})
    idx = {}
    for i, r in enumerate(rows):
        idx.setdefault(r['group'], []).append(i)
    rng = random.Random(SEED)
    diffs = []
    for _ in range(DRAWS):
        pick = [i for g in (rng.choice(keys) for _ in keys) for i in idx[g]]
        sub = [rows[i] for i in pick]
        if len({r['target'] for r in sub}) < 2:
            continue
        diffs.append(bag.auc(sub, [new[i] for i in pick]) - bag.auc(sub, [old[i] for i in pick]))
    diffs.sort()
    return dict(lo=diffs[int(.025*(len(diffs)-1))], hi=diffs[int(.975*(len(diffs)-1))], draws=len(diffs))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-newdef-labels-cv-20261102':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    new = json.loads((ROOT/plan['new_labels']).read_text())
    if rows != ref['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    key = [r['id'].split('/')[0] + '|' + r['area'] for r in rows]
    ev = [i for i, k in enumerate(key) if k in new]
    if len(ev) != plan['expected_eval_zones']:
        raise ValueError('Eval zone count differs')
    rows_new = [dict(r, target=new[k]) if k in new else r for r, k in zip(rows, key)]
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    x, m = sw.features(body, rows, device)
    fold = cv.fold_of(rows)
    s_old = others.oof_scores(x, m, rows, fold)
    s_new = others.oof_scores(x, m, rows_new, fold)
    sub = [rows_new[i] for i in ev]
    a_old, a_new = bag.auc(sub, [s_old[i] for i in ev]), bag.auc(sub, [s_new[i] for i in ev])
    boot = paired_bootstrap(sub, [s_new[i] for i in ev], [s_old[i] for i in ev])
    crit = dict(diff=a_new-a_old >= plan['criterion_min_diff'] and boot['lo'] > plan['criterion_min_diff_lower'])
    (out/'observations.json').write_text(json.dumps(dict(rows=rows_new, scores=s_new, scores_old_labels=s_old, eval_index=ev), allow_nan=False))
    summary = dict(criterion_met=all(crit.values()), criterion=crit, auc_train_old_labels=a_old, auc_train_new_labels=a_new, diff=a_new-a_old, diff_bootstrap=boot,
                   eval_zones=len(ev), eval_positive_new_truth=sum(r['target'] for r in sub), eval_groups=len({r['group'] for r in sub}),
                   label_changed_in_eval=sum(rows[i]['target'] != rows_new[i]['target'] for i in ev), device=device,
                   typed_point_response='not_evaluated', training_calls=2*cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
