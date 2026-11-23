"""W2: corner candidate E recipe (946 zones, same-photo pair term lambda=1) with the token scorer changed from linear to a hidden-1-layer MLP (width 64, dropout 0). Only the scorer differs; control = stored candidate E OOF scores (frozen). Development OOF, not an independent test. Common-runner only."""
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


cs = _load('cs', 'tools/experiments/corner-same-photo-pair-cv-20261102/worker.py')
head = _load('head', Path(__file__).resolve().relative_to(ROOT).with_name('head.py'))
cv, bag, sw, pair, pool = cs.cv, cs.bag, cs.sw, cs.pair, cs.pool


def oof_mlp(x, m, rows):
    fold, scores, conv = cv.fold_of(rows), [0.]*len(rows), []
    for f in range(cv.FOLDS):
        tr = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        ho = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in tr], [rows[i] for i in ho])  # photo-group disjoint train/held-out, raises otherwise
        t, h = torch.tensor(tr), torch.tensor(ho)
        fit = head.fit_mlp(x[t], m[t], [rows[i] for i in tr], cs.guarded_masses, pair.photo_pairs, pair.detail_bag_loss)
        conv.append(fit['convergence'])
        for i, s in zip(ho, head.score_mlp(x[h], m[h], fit)):
            scores[i] = s
    return scores, conv


def cards(rows, scores):
    """Per photo (= card): (defect-zone scores, all-zone scores); a card is defective when any zone has target 1."""
    by = {}
    for r, s in zip(rows, scores):
        by.setdefault(r['image'], ([], []))
        by[r['image']][1].append(s)
        if r['target']:
            by[r['image']][0].append(s)
    return [v for v in by.values() if v[0]], [v for v in by.values() if not v[0]]


def card_counts(rows, scores, low=None, high=None, fp_budget=None):
    """Card-level miss/false alarm. Fixed thresholds (v1.14: miss = all defect zones < low, alarm = any zone >= high), or
    matched mode: the alarm threshold is the (fp_budget+1)-th largest normal-card maximum and alarms need a score strictly above it;
    a defect card is missed when no defect zone exceeds that threshold."""
    pos, neg = cards(rows, scores)
    if fp_budget is not None:
        cut = sorted((max(a) for _, a in neg), reverse=True)[fp_budget]
        return dict(miss=sum(max(d) <= cut for d, _ in pos), fp=sum(max(a) > cut for _, a in neg), threshold=cut, defect_cards=len(pos), normal_cards=len(neg))
    return dict(miss=sum(max(d) < low for d, _ in pos), fp=sum(max(a) >= high for _, a in neg), defect_cards=len(pos), normal_cards=len(neg))


def control_check(rows, control, claimed):
    """Re-derive the control's stored numbers from the original file (not copied constants)."""
    got = dict(auc=round(bag.auc(rows, control), 4), same=round(bag.auc(rows, control, True), 3), v114=card_counts(rows, control, .2, .6))
    if got['auc'] != claimed['auc'] or got['same'] != claimed['same'] or (got['v114']['miss'], got['v114']['fp']) != tuple(claimed['v114']):
        raise ValueError(f'Control differs from the frozen record: {got}')
    return got


def evaluate(rows, mlp, control, plan):
    boot, boot_same = pool.paired_bootstrap(rows, mlp, control), cs.paired_same_photo(rows, mlp, control)
    ctrl_v114 = card_counts(rows, control, .2, .6)
    ctrl_m = card_counts(rows, control, fp_budget=ctrl_v114['fp'])
    new_m = card_counts(rows, mlp, fp_budget=ctrl_v114['fp'])
    d_auc, same_m, same_c = bag.auc(rows, mlp) - bag.auc(rows, control), bag.auc(rows, mlp, True), bag.auc(rows, control, True)
    crit = dict(pooled_auc=d_auc >= plan['criterion_min_auc_diff'] and boot['lo'] > plan['criterion_min_auc_diff_lower'], same_photo_not_lower=same_m >= same_c, matched_card_miss_not_more=new_m['miss'] <= ctrl_m['miss'])
    return dict(criterion_met=all(crit.values()), criterion=crit, auc_mlp=bag.auc(rows, mlp), auc_control=bag.auc(rows, control), auc_diff=d_auc, auc_bootstrap=boot,
                same_photo_auc_mlp=same_m, same_photo_auc_control=same_c, same_photo_bootstrap=boot_same, matched_control=ctrl_m, matched_mlp=new_m,
                v114_control=ctrl_v114, v114_mlp=card_counts(rows, mlp, .2, .6))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'corner-mlp-token-head-w2-20261123':
        raise ValueError('Wrong hypothesis')
    if any((Path(__file__).parent/n).read_bytes() != (ROOT/plan['tracked_directory']/n).read_bytes() for n in ('worker.py', 'head.py')):
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    rows = json.loads((ROOT/plan['rows']).read_text())
    old = json.loads((ROOT/plan['control_observations']).read_text())
    if rows != ref['rows'] or rows != old['rows'] or len(rows) != plan['expected_rows']:
        raise ValueError('Frozen rows differ')
    control = old['scores']
    got = control_check(rows, control, plan['control_claimed'])
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    x, m = sw.features(body.to(device), rows, device)
    mlp, conv = oof_mlp(x, m, rows)
    (out/'observations.json').write_text(json.dumps(dict(rows=rows, scores=mlp, control_scores=control), allow_nan=False))
    summary = dict(**evaluate(rows, mlp, control, plan), control_rederived=got, convergence=conv, rows=len(rows), groups=len({r['group'] for r in rows}), device=device,
                   hidden=head.HIDDEN, max_iter=head.MAX_ITER, grad_tol=head.GRAD_TOL, typed_point_response='not_evaluated', training_calls=cv.FOLDS, external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
