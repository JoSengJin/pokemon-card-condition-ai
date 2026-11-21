"""Evaluate a single aggregation change on the replayed card-ranking head."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
module = ROOT / 'tools/experiments/corner-card-ranking-20261121/worker.py'
spec = importlib.util.spec_from_file_location('frozen_rank', module)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def missed_cards(rows, scores, low):
    best = {}
    for row, score in zip(rows, scores, strict=True):
        if row['target']:
            best[row['group']] = max(score, best.get(row['group'], 0.0))
    return {group for group, score in best.items() if score < low}


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if Path(__file__).read_bytes() != (ROOT / plan['tracked_directory'] / 'worker.py').read_bytes():
        raise ValueError('Mirror differs')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    prior = json.loads((ROOT / plan['original_plan']).read_text())
    replay = json.loads((ROOT / plan['replayed_observations']).read_text())
    rows, old = ref['rows'], ref['before_scores']
    if rows != replay['rows'] or old != replay['scores']:
        raise ValueError('Replay reference differs')
    heads = torch.load(ROOT / plan['replayed_heads'], map_location='cpu', weights_only=True)
    folds = frozen.cv.fold_of(rows)
    splits = [([i for i,r in enumerate(rows) if folds[r['group']] != f],
               [i for i,r in enumerate(rows) if folds[r['group']] == f]) for f in range(frozen.cv.FOLDS)]
    for train, holdout in splits:
        frozen.sw.check_separation([rows[i] for i in train], [rows[i] for i in holdout])
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS device required')
    body = torch.hub.load(str(ROOT / prior['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT / prior['backbone_weights'], map_location='cpu', weights_only=True))
    print('Extracting the original 448px features on MPS', flush=True)
    x, masks = frozen.sw.features(body.to('mps'), rows, 'mps')
    if len(heads) != len(splits) or not bool((masks.sum(1) >= 2).all()):
        raise ValueError('Fold head or eligible patches missing')

    top, second = [None]*len(rows), [None]*len(rows)
    for (_, holdout), head in zip(splits, heads, strict=True):
        h = torch.tensor(holdout)
        logits = (x[h] @ head['coef'] + head['bias']).masked_fill(~masks[h], -torch.inf)
        for i, (a,b) in zip(holdout, logits.topk(2, dim=1).values.sigmoid().tolist(), strict=True):
            top[i],second[i] = a,b
    max_diff = max(abs(a-b) for a,b in zip(top,old,strict=True))
    if max_diff > plan['max_score_delta'] or any(b > a for a,b in zip(top,second,strict=True)):
        raise ValueError('Baseline replay or score ordering disagrees')
    a = frozen.summarize(rows, old, prior)
    b = frozen.summarize(rows, second, prior)
    new_misses = missed_cards(rows, second, prior['fixed_low']) - missed_cards(rows, old, prior['fixed_low'])
    gates = plan['gate']
    criteria = dict(fewer_false_alarms=b['fixed_fp'] <= gates['max_fixed_fp'],
                    no_new_misses=not new_misses and b['fixed_miss'] <= gates['max_fixed_miss'],
                    within_photo=b['same_photo_auc'] >= a['same_photo_auc'] - gates['max_within_auc_drop'])
    metrics = dict(control=a,candidate=b,criterion=criteria,criterion_met=all(criteria.values()),
                   new_misses=sorted(new_misses),baseline_max_delta=max_diff,training_calls=0,external_ai_calls=0)
    (out / 'evaluation.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
    (out / 'observations.json').write_text(json.dumps(dict(rows=rows,scores=second),allow_nan=False))
    print(json.dumps(metrics,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    run()
