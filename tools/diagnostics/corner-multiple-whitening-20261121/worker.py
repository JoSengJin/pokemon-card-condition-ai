"""Replay unchanged patch maps on a small visually selected development sample."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
source = ROOT / 'tools/experiments/corner-card-ranking-20261121/worker.py'
spec = importlib.util.spec_from_file_location('frozen_rank_worker', source)
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)


def peak(grid, box):
    y0,x0,y1,x1 = box
    if not (0 <= y0 <= y1 < 32 and 0 <= x0 <= x1 < 32):
        raise ValueError('Invalid visual box')
    return float(grid[y0:y1+1, x0:x1+1].amax())


def inspect_marks(grid, marks, min_gap):
    observations = []
    for mark in marks:
        at = peak(grid, mark['patch_box'])
        nearby = peak(grid, mark['nearby_box'])
        if min(at, nearby) < 0:
            raise ValueError('Visual box does not overlap a real patch')
        observations.append(dict(**mark, peak=at, nearby_peak=nearby,
                                 raises_local_score=at-nearby >= min_gap))
    return observations


def run():
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Diagnostic mirror differs')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    archive = json.loads((ROOT/plan['replayed_observations']).read_text())
    full = {r['id']:(r,s) for r,s in zip(archive['rows'],archive['scores'],strict=True)}
    design = json.loads((ROOT/plan['probes']).read_text())
    selection = json.loads((ROOT/plan['blind_selection']).read_text())
    people = [full[selection[p['number']-1]['id']] for p in design]
    rows, baseline = [r for r,_ in people], [s for _,s in people]
    if rows != ref['rows'] or baseline != ref['before_scores'] or len({r['group'] for r in rows}) != 4:
        raise ValueError('Frozen sample mismatch')
    frozen.sw.check_separation([], rows)
    prior = json.loads((ROOT/plan['original_plan']).read_text())
    heads = torch.load(ROOT/plan['replayed_heads'],map_location='cpu',weights_only=True)
    folds = frozen.cv.fold_of(archive['rows'])
    if not torch.backends.mps.is_available():
        raise RuntimeError('Original MPS backend required')
    torch.set_num_threads(2)
    body = torch.hub.load(str(ROOT/prior['backbone_directory']),'dinov2_vits14',source='local',pretrained=False)
    body.eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/prior['backbone_weights'],map_location='cpu',weights_only=True))
    features,masks = frozen.sw.features(body.to('mps'),rows,'mps')

    scores, maps = [], []
    for probe,r,x,mask in zip(design,rows,features,masks,strict=True):
        fold = folds[r['group']]
        head = heads[fold]
        grid = (x @ head['coef'] + head['bias']).sigmoid().masked_fill(~mask,-1).view(32,32)
        top = float(grid.max())
        scores.append(top)
        maps.append(dict(number=probe['number'],id=r['id'],fold=fold,top=top,
                         top_patch=list(divmod(int(grid.argmax()),32)),grid=grid.tolist(),
                         marks=inspect_marks(grid,probe['marks'],plan['min_local_gap'])))
    delta = max(abs(a-b) for a,b in zip(scores,baseline,strict=True))
    if delta > plan['max_score_delta']:
        raise ValueError(f'Archived scores did not match: {delta:.8g}')
    path = out/'patch-comparison.json'
    path.write_text(json.dumps(maps,ensure_ascii=False,allow_nan=False))
    summary = dict(cases=len(maps), marks=sum(len(m['marks']) for m in maps), max_score_delta=delta,
                   local_responses_per_case=[sum(m['raises_local_score'] for m in d['marks']) for d in maps],
                   patch_comparison_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   training_calls=0,external_ai_calls=0)
    (out/'diagnostics.json').write_text(json.dumps(summary,ensure_ascii=False))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows,scores=scores,diagnostic_evidence=summary),allow_nan=False))
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    run()
