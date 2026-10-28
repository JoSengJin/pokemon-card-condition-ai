"""Independent preregistered surface candidates. Canonical checkout/common runner only."""
import collections,hashlib,importlib.util,json,os,sys
from pathlib import Path
import torch
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir());sys.path.insert(0,str(ROOT))
from card_condition.detail_bag import fit_detail_head
TASK='surface-preserved-heads-20261028'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def balanced(rows):
    counts=collections.Counter(r['group'] for r in rows);y=torch.tensor([r['target'] for r in rows]);mass=torch.tensor([1/counts[r['group']] for r in rows]);mass[y==1]*=mass[y==0].sum()/mass[y==1].sum();return y,mass


def fit_fold(ctx,train,held,phase,features,nonlinear):
    rows=[ctx['all_rows'][i] for i in train];y,mass=balanced(rows);first=ctx['tokens'][train];x=ctx['x'];mask=ctx['masks']
    if phase=='preserved':
        train_x=features.preserved_features(x[train],mask[train]);held_x=features.preserved_features(x[held],mask[held])
        coef,bias,diag=fit_detail_head(train_x,mask[train],y,first,mass,penalty=1.,normal_reduction='max_bound')
        logits=held_x@coef+bias;head=dict(coef=coef,bias=bias)
    elif phase=='separated':
        strong=[i for i in train if ctx['all_rows'][i]['target']==0 or ctx['tokens'][i]>=0]
        sy,sw=balanced([ctx['all_rows'][i] for i in strong])
        try:pw,pb,pd=fit_detail_head(x[strong],mask[strong],sy,ctx['tokens'][strong],sw,penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:raise ValueError('point role: '+str(exc)) from exc
        try:rw,rb,rd=fit_detail_head(x[train],mask[train],y,torch.full_like(first,-1),mass,penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:raise ValueError('presence role: '+str(exc)) from exc
        coef,bias=(pw+rw)/2,(pb+rb)/2;logits=x[held]@coef+bias
        head=dict(coef=coef,bias=bias,point_coef=pw,point_bias=pb,presence_coef=rw,presence_bias=rb,point_train_ids=[ctx['all_rows'][i]['id'] for i in strong])
        diag=dict(converged=True,point=pd,presence=rd,max_gradient=max(pd['max_gradient'],rd['max_gradient']),point_rows=len(strong),presence_rows=len(train),combination='fixed_half_raw_logits')
    elif phase=='nonlinear':
        state,diag=nonlinear.fit_nonlinear(x[train],mask[train],y,first,mass);logits=nonlinear.nonlinear_logits(x[held],state);head=dict(state=state)
    else:raise ValueError('Unknown frozen candidate')
    return logits.sigmoid(),head,diag


def finish(ctx, maps, fits, heads, front):
    rows, masks, before, base = ctx['rows'], ctx['masks'], ctx['replay'], ctx['base']
    scores = [float(maps[i][masks[i]].max()) for i in range(len(rows))]
    assert all(abs(scores[i]-before[i]) <= 2e-5 for i,r in enumerate(rows) if r['side']=='back')
    fixed, legacy = ctx['fixed'], ctx['legacy']
    old_ref, typed_ref = fixed['point_reference'], fixed['typed_point_reference']
    old_scores = [float(maps[r['parent_index'], int(legacy['point_tokens'][r['parent_index']])]) for r in old_ref['rows']]
    typed_scores = [float(maps[r['parent_index'], r['human_token']]) for r in typed_ref['rows']]
    required = []
    for cohort in ctx['reference']['required_cohorts']:
        assert cohort['rows'] in (rows, old_ref['rows'], typed_ref['rows'])
        values = typed_scores if cohort['rows']==typed_ref['rows'] else old_scores if cohort['rows']==old_ref['rows'] else scores
        required.append(dict(id=cohort['id'], rows=cohort['rows'], scores=values, point_ids=cohort['point_ids'],
                             point_scores=values if cohort['point_ids'] else []))
    metrics = front.front_metrics(rows, scores, before)
    metrics['typed_points'] = dict(points=len(typed_scores),
        before_missed=sum(float(base[r['parent_index'],r['human_token']]) < .5 for r in typed_ref['rows']),
        after_missed=sum(value < .5 for value in typed_scores))
    panels = front.render(ctx['out'], rows, ctx['all_rows'], maps, masks, ctx['tokens'], scores, before, metrics)
    metrics['before_joint_holdout'] = metrics.pop('before_single_group_heads')
    metrics['after_candidate'] = metrics.pop('joint_holdout')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ctx['tracked'].items())
    page = (ctx['out']/'index.html').read_text()
    page = page.replace('Front Joint Holdout','Independent Surface Head Comparison').replace('앞면 표면 joint holdout 기준선','앞면 표면 · 독립 head 가설 비교')
    page = page.replace('before_single_group_heads','before_joint_holdout').replace('&quot;joint_holdout&quot;','&quot;after_candidate&quot;')
    page = page.replace('단독제외','기존 공동제외').replace('joint holdout:','후보:')
    page = page.replace('<h1>', '<p>진척30/100 (usable-card-analysis-v1.0, +0%p). 같은기존4-fold/정답/기준선에서 ' + ctx['phase'] + ' 한변수비교. 다른후보와결합하지않음. 반복개발평가이며 독립시험/운영채택 아님. worker SHA256 '+ctx['worker_sha']+'</p><h1>',1)
    (ctx['out']/'index.html').write_text(page)
    torch.save(dict(heads=heads, maps=maps, objective='independent_preserved_separated_or_mlp',
                    production_adopted=False), ctx['out']/'fold-heads.pt')
    diagnostics = dict(phase=ctx['phase'], metrics=metrics, fits=fits, panels=panels, source_sha256=ctx['tracked'],
        new_backbone_forwards=0, new_labels=0, gemini_calls=0, codex_model_calls=0, independent=False, production_adopted=False)
    (ctx['out']/'diagnostics.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, allow_nan=False))
    (ctx['out']/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, required_cohorts=required),allow_nan=False))
    print(json.dumps(metrics, ensure_ascii=False), flush=True)



if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts');torch.set_num_threads(2)
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']).resolve();plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    phase=plan['phase'];assert phase in ('preserved','separated','nonlinear') and plan['hypothesis_id']=='surface-'+phase+'-head-20261028'
    assert plan['gemini_calls_allowed']==0 and plan['independent'] is False
    assert plan['head_protocol']==dict(hidden_units=8,hidden_seed=0,activation='tanh',split_logit_weight=.5,max_iter=100,max_gradient=1e-5,penalty=1.,backbone_forwards=0)
    for c in plan['code_changes']:
        source=ROOT/'tools/experiments'/TASK/Path(c['path']).name;assert source.read_bytes()==(ROOT/c['path']).read_bytes()
    coex=load('frozen_coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');front=load('frozen_front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py')
    features=load('preserved_features',Path(__file__).with_name('features.py'));nonlinear=load('tiny_nonlinear',Path(__file__).with_name('nonlinear.py'))
    ctx=coex.replay_baseline(ROOT,plan,ref);proposal=json.loads((ROOT/plan['proposal']).read_text());folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    base=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),map_location='cpu',weights_only=True);maps=base['maps'].clone();fits=[];heads=[]
    ctx.update(out=out,reference=ref,phase=phase,base=maps.clone(),fixed=torch.load(ROOT/coex.TYPED,map_location='cpu',weights_only=True),legacy=torch.load(ROOT/coex.LEGACY,map_location='cpu',weights_only=True),worker_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for fold_id,train,held in folds:
        try:values,head,diag=fit_fold(ctx,train,held,phase,features,nonlinear)
        except ValueError as exc:
            (out/'failure-diagnostics.json').write_text(json.dumps(dict(phase=phase,fold=fold_id,error=str(exc),completed_folds=len(fits),performance_measured=False),ensure_ascii=False,indent=2));raise
        maps[held]=values;head.update(fold=fold_id,train_ids=[ctx['all_rows'][i]['id'] for i in train]);heads.append(head);fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),**diag))
    finish(ctx,maps,fits,heads,front)
