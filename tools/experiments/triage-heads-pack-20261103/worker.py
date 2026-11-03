"""Package the frozen corner (E), surface (B) and observation-limit (F) candidates as head files, reload them through the card_condition modules and compare with the stored independent-holdout scores. No new evaluation data, no threshold or recipe change. Common-runner only."""
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))
from card_condition.back_obs_limit import load_head as load_obs, pooled_score  # noqa: E402
from card_condition.back_edge_triage import load_head as load_zone  # noqa: E402
from card_condition.back_zone_triage import zone_scores  # noqa: E402
from card_condition.regions import REGION_TARGET_AREAS  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pairmod = _load('pairmod', 'tools/experiments/corner-same-photo-pair-cv-20261102/worker.py')
pool = _load('pool', 'tools/experiments/surface-newdef-pool-cv-r2-20261102/worker.py')
ms = _load('obsms', 'tools/experiments/obslimit-meanstd-20261101/worker.py')
sw = pairmod.sw
KINDS = dict(corner=('corner_defect', 'corner'), surface=('surface_defect', 'surface'))


def obs_head(body, rows, device):
    """Same fit as ms.fit_predict (standardize + LBFGS L2 logistic), keeping the parameters."""
    x, m = sw.features(body, rows, device)
    a = (x*m[..., None]).sum(1)/m.sum(1, keepdim=True)
    mu, sd = a.mean(0), a.std(0) + 1e-6
    z, y = (a-mu)/sd, torch.tensor([r['target'] for r in rows]).float()
    w, b = torch.zeros(384, requires_grad=True), torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([w, b], max_iter=100, line_search_fn='strong_wolfe')

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(z @ w + b, y) + ms.LAM*(w**2).sum()
        loss.backward()
        return loss
    opt.step(closure)
    return dict(mean=mu, std=sd, coef=w.detach(), bias=b.detach()[0])


def card_boxes(rows):
    """Card box from the first and last 3x3 zone of each photo (needs upper_left and lower_right rows)."""
    by = {}
    for r in rows:
        by.setdefault(r['group'], {})[r['area']] = r['box']
    clamp = lambda v: min(1.0, max(0.0, v))
    return {g: [clamp(v) for v in (z['upper_left'][0], z['upper_left'][1], z['lower_right'][2], z['lower_right'][3])] for g, z in by.items() if 'upper_left' in z and 'lower_right' in z}


def zone_diff(body, rows, stored, head, kind, device):
    areas = REGION_TARGET_AREAS[KINDS[kind][0]]
    boxes, worst, n = card_boxes(rows), 0.0, 0
    ref = {r['id']: s for r, s in zip(rows, stored)}
    for g, box in boxes.items():
        image = next(r['image'] for r in rows if r['group'] == g)
        for area, s in zip(areas, zone_scores(body, image, box, head, device, areas)):
            key = f'{g}/back/{kind}/{area}'
            if key in ref:
                worst, n = max(worst, abs(s-ref[key])), n+1
    return dict(max_abs_diff=worst, zones_compared=n, photos=len(boxes))


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    if plan['hypothesis_id'] != 'triage-heads-pack-20261103':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + path)
    torch.set_num_threads(2)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'], map_location='cpu', weights_only=True), strict=True)
    body = body.to(device)
    dest, report = ROOT/plan['head_directory'], {}
    for kind, fitter in (('corner', lambda x, m, r: (pairmod.pair.fit_pair(x, m, r))), ('surface', lambda x, m, r: pool.fit_pool(x, m, r))):
        spec = plan['candidates'][kind]
        train = json.loads((ROOT/spec['train_rows']).read_text())
        if len(train) != spec['expected_train_rows']:
            raise ValueError('Training rows differ: ' + kind)
        if kind == 'corner':
            pairmod.pair.masses = pairmod.guarded_masses
        x, m = sw.features(body, train, device)
        coef, bias, _ = fitter(x, m, train)
        del x, m
        path = dest/f'{kind}-head.pt'
        torch.save(dict(coef=coef.float(), bias=bias.float().reshape(()), band_low=spec['band_low'], band_high=spec['band_high']), path)
        obs = json.loads((ROOT/spec['reference_observations']).read_text())
        report[kind] = dict(sha256=load_zone(path)['sha256'], **zone_diff(body, obs['rows'], obs['scores'], load_zone(path), kind, device))
    spec = plan['candidates']['observation_limit']
    train = json.loads((ROOT/spec['train_rows']).read_text())
    if len(train) != spec['expected_train_rows']:
        raise ValueError('Training rows differ: observation_limit')
    path = dest/'observation_limit-head.pt'
    torch.save(obs_head(body, train, device), path)
    obs = json.loads((ROOT/spec['reference_observations']).read_text())
    head = load_obs(path)
    repro = [pooled_score(body, r['image'], r['box'], head, device) for r in obs['rows']]
    worst = max(abs(a-s) for a, s in zip(repro, obs['scores']))
    report['observation_limit'] = dict(sha256=head['sha256'], max_abs_diff=worst, rows_compared=len(obs['rows']))
    ok = all(v['max_abs_diff'] <= plan['criterion_max_abs_diff'] for v in report.values())
    (out/'observations.json').write_text(json.dumps(dict(rows=obs['rows'], scores=repro), allow_nan=False))
    summary = dict(criterion_met=ok, heads=report, device=device, training_calls=3, external_ai_calls=0, typed_point_response='not_evaluated')
    (out/'evaluation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=float))
    print(json.dumps(summary, ensure_ascii=False, default=float), flush=True)
