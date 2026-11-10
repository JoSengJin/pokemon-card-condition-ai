"""Half-patch shifted lattice union bag, unchanged alpha0 objective and frozen group folds."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import resource

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    import torch
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id'] != 'surface-half-patch-lattice-20261111':
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
    sys.path.insert(0,str(ROOT/plan['tracked_directory']))
    if (ROOT/plan['tracked_directory']/'features.py').read_bytes() != (ROOT/plan['runtime_directory']/'features.py').read_bytes():
        raise ValueError('Tracked/mirror features differs')
    from features import backbone_features, score_tokens
    x,m = backbone_features(body,revised,device)
    del body
    assert x.shape==(1776,2048,384) and m.shape==(1776,2048) and torch.isfinite(x).all()
    rss_unit=1 if sys.platform=='darwin' else 1024
    memory=dict(physical_ram_bytes=plan['physical_ram_bytes'],raw_feature_bytes=x.numel()*x.element_size(),logical_dimensions=384,tokens_per_bag=2048,
        projection_chunk_rows=8,phases=[dict(stage='half_patch_features',process_peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_unit))])
    (out/'memory-audit.json').write_text(json.dumps(memory,indent=2))
    with (out/'representation-contract.json').open('x') as stream:
        json.dump(dict(formula='bag=original_lattice(1024)+lattice_shifted_7px_upleft(1024)',tokens_per_bag=2048,shift_px_448=7,feature_dimensions=384,
            patch_shape=list(x.shape),patch_sha256=hashlib.sha256(memoryview(x.numpy())).hexdigest(),mask_sha256=hashlib.sha256(m.numpy().tobytes()).hexdigest(),
            shifted_last_row_col_invalid=True,labels_or_scores_used_for_features=False,max_over_union=True),stream)
    print(json.dumps(dict(stage='half_patch_features_completed',memory=memory)),flush=True)
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
            # Ordered training provenance only; never select or weight rows by OOF errors.
            with (out/('component-gradient-rows-fold'+str(f)+'.json')).open('x') as stream:
                json.dump(dict(fold=f,rows=[dict(id=r['id'],group=r['group'],image_sha256=r['image_sha256'],target=r['target']) for r in train_rows]),stream,allow_nan=False)
            coef,bias,conv = prior.sw.fit_detail_head(x[tr],m[tr],targets,torch.full((len(tr),),-1,dtype=torch.long),mass,penalty=1.,normal_reduction='max_bound')
            for i,s in zip(ho,score_tokens(x[ho],m[ho],coef,bias)):
                predictions[i] = s
            memory['phases'].append(dict(stage='fit'+str(f)+'_completed',process_peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_unit)))
            memory['max_projection_chunk_rows']=objective.StreamedLinear.max_chunk_rows
            memory['max_projection_base_elements']=objective.StreamedLinear.max_base_elements
            (out/'memory-audit.json').write_text(json.dumps(memory,indent=2))
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
    evaluation = dict(criterion_met=gate,representation_gate=representation_gate,input_dimensions=384,tokens_per_bag=2048,comparisons=comparisons,rows=1776,groups=204,excluded_impossible=15,changed_label_count=191,newly_received_labels=0,training_fits=5,device=device,elapsed_seconds=time.monotonic()-started,external_ai_calls=0,independent=False,production_adopted=False,known_bias='section97 model-score-selected rejudgments; partial relabeling; repeated development CV, not independent evidence')
    (out/'evaluation.json').write_text(json.dumps(evaluation,ensure_ascii=False,indent=2,allow_nan=False))
    memory['phases'].append(dict(stage='metrics_completed',process_peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_unit)))
    (out/'memory-audit.json').write_text(json.dumps(memory,indent=2))
    print(json.dumps(evaluation,ensure_ascii=False),flush=True)
