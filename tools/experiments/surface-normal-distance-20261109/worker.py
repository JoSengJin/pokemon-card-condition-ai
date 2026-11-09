"""Fold-local normal-distance input, unchanged alpha0 objective and frozen group folds."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    import torch
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-frozen-global-lme-normal-distance-20261109':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Tracked/mirror worker differs')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: '+path)
    modules = {}
    for name,path in [('prior','tools/experiments/surface-corrected-labels-cv-20261104/worker.py'), ('met',plan['metrics_source'])]:
        spec = importlib.util.spec_from_file_location(name,ROOT/path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    prior, met = modules['prior'], modules['met']
    rows = json.loads((ROOT/plan['rows']).read_text())
    judgments = json.loads((ROOT/plan['judgments']).read_text())
    keep, original, revised = met.label_rows(rows,judgments)
    assert revised == ref['rows'] and len(revised) == 1776
    assert [r['id'] for r in original] == [r['id'] for r in revised]
    assert sum(r['target'] for r in original)==179 and sum(r['target'] for r in revised)==370
    assert len([1 for a,b in zip(original,revised) if a['target'] != b['target']])==191
    fold = json.loads((ROOT/plan['folds']).read_text())
    assert fold == prior.cv.fold_of(rows)
    for path in plan['forbidden_evaluation_rows']:
        forbidden = json.loads((ROOT/path).read_text())
        assert not {r['group'] for r in revised} & {r['group'] for r in forbidden}
        assert not {r['image_sha256'] for r in revised} & {r['image_sha256'] for r in forbidden}
    torch.set_num_threads(2)
    torch.manual_seed(plan['seed'])
    device = 'cpu'
    started = time.monotonic()
    print(json.dumps(dict(stage='feature_extraction',rows=len(revised),device=device)),flush=True)
    body = torch.hub.load(str(ROOT/plan['backbone_directory']),'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'],map_location='cpu',weights_only=True),strict=True)
    body = body.to(device)
    x,m = prior.base.backbone_features(body,revised,device)
    del body
    sys.path.insert(0,str(ROOT/plan['tracked_directory']))
    if (ROOT/plan['tracked_directory']/'features.py').read_bytes() != (ROOT/plan['runtime_directory']/'features.py').read_bytes():
        raise ValueError('Tracked/mirror features differs')
    from features import fit_normal_distribution, append_normal_distance
    assert x.shape == (1776,1024,384) and torch.isfinite(x).all()
    if device == 'mps':
        torch.mps.empty_cache()
    sys.path.insert(0,str((ROOT/plan['objective_source']).parent))
    spec=importlib.util.spec_from_file_location('rank_objective',ROOT/plan['objective_source'])
    objective=importlib.util.module_from_spec(spec);spec.loader.exec_module(objective)
    prior.sw.fit_detail_head=objective.fit_detail_head
    scores, diagnostics, models = {}, [], []
    for arm,training_rows in [('revised',revised)]:
        predictions = [None]*len(revised)
        for f in range(5):
            os.environ['SURFACE_RANK_FOLD']=str(f)
            tr = [i for i,r in enumerate(training_rows) if fold[r['group']] != f]
            ho = [i for i,r in enumerate(training_rows) if fold[r['group']] == f]
            separation = prior.sw.check_separation([training_rows[i] for i in tr],[training_rows[i] for i in ho])
            # Same all-eBay mass recipe as fit_pool, directly calling the existing fitter.
            train_rows = [training_rows[i] for i in tr]
            targets = torch.tensor([r['target'] for r in train_rows])
            counts = {}
            for r in train_rows:
                counts[r['group']] = counts.get(r['group'],0)+1
            mass = torch.tensor([1/counts[r['group']] for r in train_rows])
            assert all(r['group'].startswith('ebay') for r in train_rows)
            mass[targets==1] *= mass[targets==0].sum()/mass[targets==1].sum()
            train_x, train_m = x[tr], m[tr]
            mean, variance = fit_normal_distribution(train_x,train_m,targets,mass)
            normal_indices = (targets==0).nonzero().flatten().tolist()
            normal_rows = [train_rows[i] for i in normal_indices]
            assert not {r['group'] for r in normal_rows} & {training_rows[i]['group'] for i in ho}
            assert not {r['image_sha256'] for r in normal_rows} & {training_rows[i]['image_sha256'] for i in ho}
            normal_mass = mass[normal_indices].double();normal_mass /= normal_mass.sum()
            with (out/('normal-statistics-fold'+str(f)+'.json')).open('x') as stream:
                json.dump(dict(fold=f,mean=mean.tolist(),variance=variance.tolist(),variance_floor=1e-6,
                    dimensions=384,formula='sqrt(mean((x-mean)^2/variance))',
                    normal_rows=[dict(id=r['id'],group=r['group'],image_sha256=r['image_sha256'],target=r['target']) for r in normal_rows],
                    normalized_normal_mass=normal_mass.tolist(),
                    normal_mass_sha256=hashlib.sha256(normal_mass.numpy().tobytes()).hexdigest(),
                    normal_mask_sha256=hashlib.sha256(train_m[normal_indices].numpy().tobytes()).hexdigest(),
                    evaluation_groups=sorted({training_rows[i]['group'] for i in ho}),evaluation_statistics_used=False),stream,allow_nan=False)
            train_x = append_normal_distance(train_x,train_m,mean,variance)
            print(json.dumps(dict(stage='normal_statistics_completed',fold=f,normal_regions=len(normal_rows))),flush=True)
            # Ordered training provenance only; never select or weight rows by OOF errors.
            with (out/('component-gradient-rows-fold'+str(f)+'.json')).open('x') as stream:
                json.dump(dict(fold=f,rows=[dict(id=r['id'],group=r['group'],image_sha256=r['image_sha256'],target=r['target']) for r in train_rows]),stream,allow_nan=False)
            coef,bias,conv = prior.sw.fit_detail_head(train_x,train_m,targets,torch.full((len(tr),),-1,dtype=torch.long),mass,penalty=1.,normal_reduction='max_bound')
            del train_x, train_m
            held_x = append_normal_distance(x[ho],m[ho],mean,variance)
            for i,s in zip(ho,prior.sw.score(held_x,m[ho],coef,bias)):
                predictions[i] = s
            del held_x
            diagnostics.append(dict(arm=arm,fold=f,train=len(tr),evaluation=len(ho),separation=separation,**conv))
            models.append(dict(arm=arm,fold=f,coef=coef.tolist(),bias=float(bias)))
            (out/'training-progress.json').write_text(json.dumps(dict(completed_fits=len(diagnostics),planned_fits=5,elapsed_seconds=time.monotonic()-started,latest=diagnostics[-1]),indent=2))
            print(json.dumps(dict(stage='fit_completed',arm=arm,fold=f,completed_fits=len(diagnostics))),flush=True)
        assert all(s is not None for s in predictions)
        scores[arm] = predictions
    scores['original']=ref['before_scores']
    comparisons = {}
    for name,evaluation_rows in [('original_labels',original),('revised_labels',revised)]:
        control = met.metrics(evaluation_rows,scores['original'])
        candidate = met.metrics(evaluation_rows,scores['revised'])
        bootstrap = met.paired_bootstrap(evaluation_rows,scores['revised'],scores['original'],plan['bootstrap_draws'],plan['bootstrap_seed'])
        comparisons[name] = dict(control=control,candidate=candidate,auc_difference=candidate['auc']-control['auc'],paired_bootstrap=bootstrap,fn_change_pp=100*(candidate['fn_rate']-control['fn_rate']),fp_change_pp=100*(candidate['fp_rate']-control['fp_rate']))
    direct = json.loads((ROOT/plan['direct_control_observations']).read_text())
    assert direct['rows'] == revised
    comparisons['direct_alpha0'] = dict(control=met.metrics(revised,direct['scores']),candidate=met.metrics(revised,scores['revised']),paired_bootstrap=met.paired_bootstrap(revised,scores['revised'],direct['scores'],plan['bootstrap_draws'],plan['bootstrap_seed']))
    comparisons['direct_alpha0']['auc_difference'] = comparisons['direct_alpha0']['candidate']['auc']-comparisons['direct_alpha0']['control']['auc']
    representation_gate = comparisons['direct_alpha0']['auc_difference'] > 0 and comparisons['direct_alpha0']['paired_bootstrap']['lo'] > 0
    primary = comparisons['revised_labels']
    gate = representation_gate and primary['auc_difference'] >= plan['criterion_min_diff'] and primary['paired_bootstrap']['lo'] > plan['criterion_min_diff_lower'] and primary['candidate']['fn']<=67 and primary['candidate']['fp']<=112
    (out/'observations.json').write_text(json.dumps(dict(rows=revised,scores=scores['revised'],control_scores=scores['original'],original_rows=original),allow_nan=False))
    (out/'models.json').write_text(json.dumps(models,allow_nan=False))
    (out/'training-diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    evaluation = dict(criterion_met=gate,representation_gate=representation_gate,input_dimensions=385,comparisons=comparisons,rows=1776,groups=204,excluded_impossible=15,changed_label_count=191,newly_received_labels=0,training_fits=5,device=device,elapsed_seconds=time.monotonic()-started,external_ai_calls=0,independent=False,production_adopted=False,known_bias='section97 model-score-selected rejudgments; partial relabeling; repeated development CV, not independent evidence')
    (out/'evaluation.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(evaluation,ensure_ascii=False),flush=True)
