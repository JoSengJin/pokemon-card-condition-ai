"""Replay the frozen card-ranking OOF head and capture false-alarm patch scores."""
from collections import defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
module = ROOT / 'tools/experiments/corner-card-ranking-20261121/worker.py'
spec = importlib.util.spec_from_file_location('frozen_card_worker', module)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def alarms(rows, scores, cutoff):
    zones = defaultdict(list)
    for i, row in enumerate(rows):
        zones[row['group']].append(i)
    return {group: ids for group, ids in zones.items()
            if not any(rows[i]['target'] for i in ids) and max(scores[i] for i in ids) >= cutoff}


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out / 'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if Path(__file__).read_bytes() != (ROOT / plan['tracked_directory'] / 'worker.py').read_bytes():
        raise ValueError('Diagnostic mirror differs')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    prior = json.loads((ROOT / plan['original_plan']).read_text())
    baseline = json.loads((ROOT / prior['e_observations']).read_text())
    rows = frozen.inputs(prior, dict(rows=ref['rows'], before_scores=baseline['scores']))
    old = ref['before_scores']
    cutoff = prior['fixed_high']
    groups = alarms(rows, old, cutoff)
    new_groups = set(groups) - set(alarms(rows, baseline['scores'], cutoff))
    if (len(groups), len(new_groups)) != (16, 6):
        raise ValueError('Wrong archived false alarm denominator')

    folds = frozen.cv.fold_of(rows)
    splits = [([i for i,r in enumerate(rows) if folds[r['group']] != f],
               [i for i,r in enumerate(rows) if folds[r['group']] == f]) for f in range(frozen.cv.FOLDS)]
    for train, holdout in splits:
        frozen.sw.check_separation([rows[i] for i in train], [rows[i] for i in holdout])
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Replay requires the original MPS backend')
    body = torch.hub.load(str(ROOT / prior['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT / prior['backbone_weights'], map_location='cpu', weights_only=True))
    print('Extracting the original 448px features on MPS', flush=True)
    x, masks = frozen.sw.features(body.to('mps'), rows, 'mps')

    scores, fitted, patch_scores = [None] * len(rows), [], {}
    for f, (train, holdout) in enumerate(splits):
        t, h = torch.tensor(train), torch.tensor(holdout)
        print(f'Replaying fold {f + 1}/{len(splits)}', flush=True)
        coef, bias, _ = frozen.head.fit(x[t], masks[t], [rows[i] for i in train], prior['card_pair_weight'])
        for i, score in zip(holdout, frozen.sw.score(x[h], masks[h], coef, bias), strict=True):
            scores[i] = score
        for i in holdout:
            if rows[i]['group'] in groups:
                logits = x[i] @ coef + bias
                patch_scores[rows[i]['id']] = dict(
                    fold=f, logits=logits.tolist(), valid=masks[i].tolist())
        fitted.append(dict(coef=coef, bias=bias))

    max_diff = max(abs(a - b) for a,b in zip(scores, old, strict=True))
    if max_diff > plan['max_score_delta'] or set(alarms(rows, scores, cutoff)) != set(groups):
        raise ValueError(f'Replay disagrees with the archive (max delta {max_diff:.8g})')
    evidence = dict(max_score_delta=max_diff, cards=len(groups), new_cards=len(new_groups),
                    zones=len(patch_scores), training_replay_folds=len(fitted), external_ai_calls=0)
    torch.save(fitted, out / 'fold-heads.pt')
    (out / 'patch-scores.json').write_text(json.dumps(patch_scores, allow_nan=False))
    (out / 'diagnostics.json').write_text(json.dumps(dict(
        evidence=evidence, groups=groups, new_groups=sorted(new_groups),
        patch_sha256=hashlib.sha256((out / 'patch-scores.json').read_bytes()).hexdigest(),
        heads_sha256=hashlib.sha256((out / 'fold-heads.pt').read_bytes()).hexdigest()
    ), ensure_ascii=False, indent=2))
    (out / 'observations.json').write_text(json.dumps(dict(
        rows=rows, scores=scores, diagnostic_evidence=evidence), allow_nan=False))
    print(json.dumps(evidence), flush=True)


if __name__ == '__main__':
    run()
