"""Candidate E group OOF with only ambiguous training zones excluded."""
import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
TEMPLATE = 'tools/experiments/corner-mlp-head-20261121/worker.py'
spec = importlib.util.spec_from_file_location('corner_template', ROOT / TEMPLATE)
template = importlib.util.module_from_spec(spec)
spec.loader.exec_module(template)
corner = template.corner
bag, cv, sw, pool, pair = corner.bag, corner.cv, corner.sw, corner.pool, corner.pair


def inputs(plan, ref):
    if plan['hypothesis_id'] != 'corner-consensus-experiment-20261121':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT / plan['tracked_directory'] / 'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    stored = json.loads((ROOT / plan['e_observations']).read_text())
    rows = stored['rows']
    fixed_rows = json.loads((ROOT / plan['rows']).read_text())
    if rows != fixed_rows or rows != ref['rows'] or stored['scores'] != ref['before_scores']:
        raise ValueError('Candidate E rows or scores differ from frozen reference')
    status = json.loads((ROOT / plan['consensus_status']).read_text())
    counts = Counter(f"{status[r['id']]}:{r['target']}" for r in rows)
    if (len(rows) != len(status) or status.keys() != {r['id'] for r in rows}
            or counts != plan['status_counts']):
        raise ValueError('Unexpected status IDs or denominators')
    return rows, status


def folds(rows, status):
    fold = cv.fold_of(rows)
    for f in range(cv.FOLDS):
        eligible = [i for i, r in enumerate(rows) if fold[r['group']] != f]
        holdout = [i for i, r in enumerate(rows) if fold[r['group']] == f]
        sw.check_separation([rows[i] for i in eligible], [rows[i] for i in holdout])
        train = [i for i in eligible if status[rows[i]['id']] != 'ambiguous']
        yield train, holdout, len(eligible) - len(train)


def evaluate(plan, rows, status, scores, old):
    indices = [i for i, r in enumerate(rows) if status[r['id']] == 'consensus']
    agreed = [rows[i] for i in indices]
    new_agreed, old_agreed = ([values[i] for i in indices] for values in (scores, old))
    budget = template.card_miss(agreed, old_agreed, 0, fixed=plan['budget_threshold'])['false_alarm']
    matched = {name: template.card_miss(agreed, values, budget)
               for name, values in (('control', old_agreed), ('candidate', new_agreed))}
    for name, values in (('control', old_agreed), ('candidate', new_agreed)):
        counts = matched[name]
        counts['zone_fn'] = sum(r['target'] == 1 and v < counts['threshold'] for r, v in zip(agreed, values))
        counts['zone_fp'] = sum(r['target'] == 0 and v >= counts['threshold'] for r, v in zip(agreed, values))
    consensus_auc = {'control': bag.auc(agreed, old_agreed), 'candidate': bag.auc(agreed, new_agreed)}
    full_auc = {'control': bag.auc(rows, old), 'candidate': bag.auc(rows, scores)}
    boot = pool.paired_bootstrap(agreed, new_agreed, old_agreed)
    gain = consensus_auc['candidate'] - consensus_auc['control']
    criteria = dict(consensus_auc=gain >= plan['min_auc_gain'],
                    bootstrap_lower=boot['lo'] > plan['min_auc_gain_lower'],
                    matched_miss=matched['candidate']['miss'] <= matched['control']['miss'],
                    full_auc=full_auc['control'] - full_auc['candidate'] <= plan['max_full_auc_drop'])
    return dict(criterion_met=all(criteria.values()), criterion=criteria, consensus_auc=consensus_auc,
                consensus_gain=gain, consensus_bootstrap=boot, full_auc=full_auc, matched=matched,
                false_alarm_budget=budget, status_counts=plan['status_counts'])


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    rows, status = inputs(plan, ref)
    splits = list(folds(rows, status))
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT / plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    weights = torch.load(ROOT / plan['backbone_weights'], map_location='cpu', weights_only=True)
    body.load_state_dict(weights, strict=True)
    print(f'Extracting frozen 448px features for {len(rows)} zones on {device}', flush=True)
    x, masks = sw.features(body.to(device), rows, device)
    pair.masses = corner.guarded_masses
    scores, converge = [None] * len(rows), []
    for f, (train, holdout, excluded) in enumerate(splits):
        t, h = torch.tensor(train), torch.tensor(holdout)
        print(f'Fold {f + 1}: train={len(train)}, excluded={excluded}, holdout={len(holdout)}', flush=True)
        coef, bias, convergence = pair.fit_pair(x[t], masks[t], [rows[i] for i in train])
        converge.append(dict(fold=f, train=len(train), excluded=excluded, holdout=len(holdout), **convergence))
        for i, score in zip(holdout, sw.score(x[h], masks[h], coef, bias), strict=True):
            scores[i] = score
    summary = evaluate(plan, rows, status, scores, ref['before_scores'])
    summary.update(device=device, convergence=converge, training_calls=len(converge), external_ai_calls=0)
    (out / 'evaluation.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    (out / 'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores), allow_nan=False))
    print(json.dumps(summary, allow_nan=False), flush=True)


if __name__ == '__main__':
    run()
