"""One common-runner experiment, two matched group-CV arms differing only in training labels."""
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
    if plan['hypothesis_id'] != 'surface-frozen-global-region-rank-armijo-20261107':
        raise ValueError('Wrong hypothesis')
    if Path(__file__).read_bytes() != (ROOT/plan['tracked_directory']/'worker.py').read_bytes():
        raise ValueError('Tracked/mirror worker differs')
    for path, digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: '+path)
    modules = {}
    for name,path in [('prior','tools/experiments/surface-corrected-labels-cv-20261104/worker.py'), ('met',plan['tracked_directory']+'/metrics.py')]:
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
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    started = time.monotonic()
    print(json.dumps(dict(stage='feature_extraction',rows=len(revised),device=device)),flush=True)
    body = torch.hub.load(str(ROOT/plan['backbone_directory']),'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'],map_location='cpu',weights_only=True),strict=True)
    body = body.to(device)
    x,m = prior.base.backbone_features(body,revised,device)
    del body
    if device == 'mps':
        torch.mps.empty_cache()
    sys.path.insert(0,str(ROOT/plan['tracked_directory']))
    spec=importlib.util.spec_from_file_location('rank_objective',ROOT/plan['tracked_directory']/'objective.py')
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
            coef,bias,conv = prior.sw.fit_detail_head(x[tr],m[tr],targets,torch.full((len(tr),),-1,dtype=torch.long),mass,penalty=1.,normal_reduction='max_bound')
            for i,s in zip(ho,prior.sw.score(x[ho],m[ho],coef,bias)):
                predictions[i] = s
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
    primary = comparisons['revised_labels']
    gate = primary['auc_difference'] >= plan['criterion_min_diff'] and primary['paired_bootstrap']['lo'] > plan['criterion_min_diff_lower'] and primary['candidate']['fn']<=67 and primary['candidate']['fp']<=112
    (out/'observations.json').write_text(json.dumps(dict(rows=revised,scores=scores['revised'],control_scores=scores['original'],original_rows=original),allow_nan=False))
    (out/'models.json').write_text(json.dumps(models,allow_nan=False))
    (out/'training-diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    evaluation = dict(criterion_met=gate,comparisons=comparisons,rows=1776,groups=204,excluded_impossible=15,changed_label_count=191,newly_received_labels=0,training_fits=5,device=device,elapsed_seconds=time.monotonic()-started,external_ai_calls=0,independent=False,production_adopted=False,known_bias='section97 model-score-selected rejudgments; partial relabeling; repeated development CV, not independent evidence')
    (out/'evaluation.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(evaluation,ensure_ascii=False),flush=True)
