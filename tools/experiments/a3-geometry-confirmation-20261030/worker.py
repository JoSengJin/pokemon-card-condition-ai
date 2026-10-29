"""Confirmed geometry extension: reuse frozen features, score newly supported rows only."""
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
    spec = importlib.util.spec_from_file_location('a3_'+name, ROOT/'tools/experiments/a3-surface-transfer-20261029'/(name+'.py'))
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


def reuse_features(rows, cached):
    old = {r['id']: (i,r) for i,r in enumerate(cached['rows'])}
    if len(old)!=len(cached['rows']) or len({r['id'] for r in rows})!=len(rows) or not set(old).issubset({r['id'] for r in rows}):
        raise ValueError('Duplicate or missing cached row identity')
    x = torch.empty((len(rows),*cached['features'].shape[1:]),dtype=cached['features'].dtype)
    reused, missing = [], []
    for i,row in enumerate(rows):
        if row['id'] not in old:
            missing.append(i);continue
        j, previous = old[row['id']]
        if any(row[k]!=previous[k] for k in ('group','image_sha256','box','card_box','target','side','split')):
            raise ValueError('Cached row identity, geometry or truth changed')
        x[i] = cached['features'][j];reused.append((i,j))
    return x,reused,missing


def extend_observations(reference, observations, rows, points, maps, masks):
    readout = module('readout')
    values = dict(zip((r['id'] for r in rows),readout.region_scores(maps,masks)))
    units = {r['id']:r for r in rows}
    for point in points:
        units[point['id']] = dict(point,box=rows[point['parent_index']]['box'])
        values[point['id']] = float(maps[point['parent_index'],point['human_token']])
    expected = {f'a3-reviewed-surface-{side}-{kind}' for side in ('front','back') for kind in ('regions','points')}
    extras = [c for c in reference['required_cohorts'] if c['id'] in expected]
    if len(extras)!=4 or {c['id'] for c in extras}!=expected:
        raise ValueError('Missing frozen A3 guard')
    for cohort in extras:
        for row in cohort['rows']:
            actual = units.get(row['id'])
            if actual is None or any(actual[k]!=row[k] for k in ('group','image_sha256','box','target','side','split')) or row.get('point')!=actual.get('point'):
                raise ValueError('Frozen A3 guard identity or point changed')
        scores = [values[r['id']] for r in cohort['rows']]
        observations['required_cohorts'].append(dict(id=cohort['id'],rows=cohort['rows'],scores=scores,point_ids=cohort['point_ids'],point_scores=[values[i] for i in cohort['point_ids']]))
    if [c['id'] for c in observations['required_cohorts']] != [c['id'] for c in reference['required_cohorts']]:
        raise ValueError('Required cohort ordering changed')
    return observations


if __name__ == '__main__':
    if not Path(__file__).resolve().is_relative_to(ROOT/'artifacts'):
        raise ValueError('Run the byte-identical artifact mirror through ./experiment')
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'a3-confirmed-geometry-back-point-transfer-20261030':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Mirror differs from tracked source')
    check_sources(plan['input_sha256'])
    data, readout, report = module('data'), module('readout'), module('report')
    torch.set_num_threads(2)
    coverage = coverage_report(ROOT/plan['manifest'])
    if coverage != json.loads((ROOT/plan['coverage']).read_text()):
        raise ValueError('Frozen coverage no longer reproduces')
    rows, points, unsupported = data.surface_rows(coverage)
    if (len(rows),len(points),len(unsupported)) != (758,648,0):
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
    original_ref = dict(ref,required_cohorts=[c for c in ref['required_cohorts'] if not c['id'].startswith('a3-reviewed-surface-')])
    if len(original_ref['required_cohorts'])!=11:
        raise ValueError('Original regression guards changed')
    replay_output = readout.observations(original_ref,fixed,legacy,replay,fixed['masks'][:147])
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
    cached = torch.load(ROOT/plan['previous_features'],map_location='cpu',weights_only=True)
    x,reused,missing = reuse_features(rows,cached)
    if (len(reused),len(missing))!=(719,39):
        raise ValueError('Unexpected feature-reuse split')
    x[missing] = features(body,[rows[i] for i in missing],device)
    maps = {name: torch.empty((len(rows),256)) for name in ('baseline','candidate')}
    for side in ('front','back'):
        indexes = [i for i,r in enumerate(rows) if r['side']==side]
        for name, heads in [('baseline',back),('candidate',candidate['heads'])]:
            maps[name][indexes] = readout.mean_maps(x[indexes],front['heads'] if side=='front' else heads)
    for name in ('baseline','candidate'):
        if any(not torch.equal(maps[name][i],cached['maps'][name][j]) for i,j in reused):
            raise ValueError('Cached A3 scores changed under fixed heads')
    replay_output = extend_observations(ref,replay_output,rows,points,maps['candidate'],masks)
    before, after = (readout.region_scores(maps[name],masks) for name in ('baseline','candidate'))
    bp, ap = ([float(maps[name][p['parent_index'],p['human_token']]) for p in points] for name in ('baseline','candidate'))
    metrics = report.compare(rows,points,before,after,bp,ap,unsupported)
    check_sources(plan['input_sha256']);check_sources(photo_hashes)
    torch.save(dict(rows=rows,features=x,masks=masks,points=points,maps=maps),out/'val-features.pt')
    evidence = dict(metrics=metrics,rows=rows,points=points,before=before,after=after,point_before=bp,point_after=ap,preflight=preflight,new_val_forwards=len(missing),reused_val_features=len(reused),control_forwards=2,training_calls=0,external_ai_calls=0)
    (out/'evaluation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False))
    progress = json.loads((ROOT/'development-progress.json').read_text())
    score = progress['score']
    report.render(out,rows,points,masks,maps,before,after,bp,ap,metrics,score,plan['source_sha'])
    (out/'observations.json').write_text(json.dumps(replay_output,allow_nan=False))
    (out/'input-hashes.json').write_text(json.dumps(dict(**plan['input_sha256'],**photo_hashes),indent=2))
    print(json.dumps({k:v for k,v in metrics.items() if k!='unsupported'},ensure_ascii=False),flush=True)
