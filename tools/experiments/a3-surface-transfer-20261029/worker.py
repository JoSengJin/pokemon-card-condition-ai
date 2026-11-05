"""One frozen A3 development comparison. Canonical common-runner only; no fit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import torch
from card_condition.data_coverage import coverage_report
from card_condition.side_experiment import side_tensor

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())


def module(name):
    spec = importlib.util.spec_from_file_location('a3_'+name, Path(__file__).with_name(name+'.py'))
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
    return loaded


def check_sources(expected):
    for path, digest in expected.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen source changed: '+path)


def features(body, rows, device):
    values = []
    with torch.inference_mode():
        for i, row in enumerate(rows):
            tensor = side_tensor(row['image'], row['box'], True, 224)
            value = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
            if value.shape != (256,384) or not torch.isfinite(value).all():
                raise ValueError('Unexpected backbone feature tensor')
            values.append(value)
            if (i+1)%50 == 0:
                print(f'backbone crops {i+1}/{len(rows)}',flush=True)
    return torch.stack(values)


if __name__ == '__main__':
    if not Path(__file__).resolve().is_relative_to(ROOT/'artifacts'):
        raise ValueError('Run the byte-identical artifact mirror through ./experiment')
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'a3-frozen-back-point-transfer-20261029':
        raise ValueError('Wrong hypothesis')
    for name in ('data','readout','report','worker'):
        if Path(__file__).with_name(name+'.py').read_bytes() != (ROOT/plan['tracked_directory']/(name+'.py')).read_bytes():
            raise ValueError('Mirror differs from tracked source')
    check_sources(plan['input_sha256'])
    data, readout, report = module('data'), module('readout'), module('report')
    torch.set_num_threads(2)
    coverage = coverage_report(ROOT/plan['manifest'])
    if coverage != json.loads((ROOT/plan['coverage']).read_text()):
        raise ValueError('Frozen coverage no longer reproduces')
    rows, points, unsupported = data.surface_rows(coverage)
    if (len(rows),len(points),len(unsupported)) != (719,643,44):
        raise ValueError('Frozen surface denominator changed')
    fixed = torch.load(ROOT/plan['models']['training_cache'],map_location='cpu',weights_only=True)
    legacy = torch.load(ROOT/plan['legacy_cache'],map_location='cpu',weights_only=True)
    front = torch.load(ROOT/plan['models']['front_heads'],map_location='cpu',weights_only=True)
    baseline = torch.load(ROOT/plan['models']['baseline_back_heads'],map_location='cpu',weights_only=True)
    candidate = torch.load(ROOT/plan['models']['candidate_back_heads'],map_location='cpu',weights_only=True)
    back = [h for h in baseline['heads'] if h['side']=='back']
    if (len(front['heads']),len(back),len(candidate['heads'])) != (4,21,21):
        raise ValueError('Head count changed')
    identity, photo_hashes = data.photo_identities(fixed['rows'] + rows + unsupported)
    separation = data.check_separation(front['heads']+back+candidate['heads'],fixed['rows'],rows+unsupported,identity)
    proposal = json.loads((ROOT/plan['proposal']).read_text())
    if ref['rows'] != legacy['rows'][:147] or not torch.equal(fixed['features'],legacy['features']):
        raise ValueError('Original cache rows/features changed')
    for head in front['heads']+candidate['heads']:
        held_ids = next(p['held_ids'] for p in proposal['folds'] if p['id']==head['fold']) if 'fold' in head else [r['id'] for r in ref['rows'] if r['side']=='back' and r['group']==head['group']]
        data.check_separation([head],fixed['rows'],[r for r in ref['rows'] if r['id'] in held_ids],identity)
    replay = readout.replay_maps(ref['rows'],fixed['rows'],fixed['features'],front['heads'],candidate['heads'],proposal)
    replay_error = float((replay-candidate['maps']).abs().max())
    replay_output = readout.observations(ref,fixed,legacy,replay,fixed['masks'][:147])
    if replay_error>plan['replay_tolerance'] or any(abs(a-b)>plan['replay_tolerance'] or (a>=.5)!=(b>=.5) for a,b in zip(replay_output['scores'],ref['before_scores'])):
        raise ValueError('Stored candidate does not replay')
    for current, old in zip(replay_output['required_cohorts'],ref['required_cohorts']):
        if any(abs(a-b)>plan['replay_tolerance'] or (a>=.5)!=(b>=.5) for a,b in zip(current['scores'],old['before_scores'])):
            raise ValueError('Required cohort does not replay')
    masks, points = data.point_tokens(rows,points); masks=torch.stack(masks)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    body = torch.hub.load(str(ROOT/plan['backbone_directory']),'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['models']['backbone'],map_location='cpu',weights_only=True),strict=True);body=body.to(device)
    controls = [next(i for i,r in enumerate(fixed['rows']) if r['side']==s) for s in ('front','back')]
    actual = features(body,[fixed['rows'][i] for i in controls],device)
    feature_errors = [float((actual[j]-fixed['features'][i]).abs().max()) for j,i in enumerate(controls)]
    preflight = dict(device=device, replay_max_error=replay_error,feature_max_errors=feature_errors,separation=separation,new_val_forwards=0,training_calls=0)
    (out/'preflight.json').write_text(json.dumps(preflight,indent=2))
    if max(feature_errors)>plan['feature_tolerance']:
        raise ValueError('Backbone control differs from original cache; no new-val scoring')
    x = features(body,rows,device)
    maps = {name: torch.empty((len(rows),256)) for name in ('baseline','candidate')}
    for side in ('front','back'):
        indexes = [i for i,r in enumerate(rows) if r['side']==side]
        for name, heads in [('baseline',back),('candidate',candidate['heads'])]:
            maps[name][indexes] = readout.mean_maps(x[indexes],front['heads'] if side=='front' else heads)
    before, after = (readout.region_scores(maps[name],masks) for name in ('baseline','candidate'))
    bp, ap = ([float(maps[name][p['parent_index'],p['human_token']]) for p in points] for name in ('baseline','candidate'))
    metrics = report.compare(rows,points,before,after,bp,ap,unsupported)
    check_sources(plan['input_sha256']);check_sources(photo_hashes)
    torch.save(dict(rows=rows,features=x,masks=masks,points=points,maps=maps),out/'val-features.pt')
    evidence = dict(metrics=metrics,rows=rows,points=points,before=before,after=after,point_before=bp,point_after=ap,preflight=preflight,new_val_forwards=len(rows),control_forwards=2,training_calls=0,external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False))
    progress = json.loads((ROOT/'development-progress.json').read_text())
    score = progress['score']
    report.render(out,rows,points,masks,maps,before,after,bp,ap,metrics,score,plan['source_sha'])
    (out/'observations.json').write_text(json.dumps(replay_output,allow_nan=False))
    (out/'input-hashes.json').write_text(json.dumps(dict(**plan['input_sha256'],**photo_hashes),indent=2))
    print(json.dumps({k:v for k,v in metrics.items() if k!='unsupported'},ensure_ascii=False),flush=True)
