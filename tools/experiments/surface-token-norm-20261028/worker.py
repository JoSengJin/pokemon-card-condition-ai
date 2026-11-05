"""One frozen front-token direction trial; canonical common runner only."""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
import torch
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir());sys.path.insert(0,str(ROOT))
from card_condition.detail_bag import fit_detail_head
TASK='surface-token-norm-20261028'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts');torch.set_num_threads(2);out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text());assert plan['hypothesis_id']=='surface-front-token-direction-20261028'
    assert plan['norm_protocol']==dict(dimensions=384,radius='sqrt_dimension',padding='preserve',statistics='per_token_only')
    for c in plan['code_changes']:assert (ROOT/c['path']).read_bytes()==(ROOT/'tools/experiments'/TASK/Path(c['path']).name).read_bytes()
    coex=load('coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');front=load('front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py');shared=load('shared',ROOT/'tools/experiments/surface-preserved-heads-20261028/worker.py');transform=load('transform',Path(__file__).with_name('transform.py'))
    ctx=coex.replay_baseline(ROOT,plan,ref);proposal=json.loads((ROOT/plan['proposal']).read_text());folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    base=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),weights_only=True,map_location='cpu');maps=base['maps'].clone();fits=[];heads=[]
    indices=[i for i,r in enumerate(ctx['all_rows']) if r['side']=='front'];assert len(indices)==97
    x=ctx['x'].clone();x[indices]=transform.direction_features(x[indices],ctx['masks'][indices])
    assert torch.equal(x[~ctx['masks']],ctx['x'][~ctx['masks']])
    controls=dict(max_norm_error=float((torch.linalg.vector_norm(x[indices][ctx['masks'][indices]],dim=-1)-384**.5).abs().max()),new_backbone_forwards=0)
    assert controls['max_norm_error']<=1e-5
    ctx.update(out=out,reference=ref,phase='front_token_direction',base=maps.clone(),fixed=torch.load(ROOT/coex.TYPED,weights_only=True,map_location='cpu'),legacy=torch.load(ROOT/coex.LEGACY,weights_only=True,map_location='cpu'),worker_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for fold_id,train,held in folds:
        y,mass=shared.balanced([ctx['all_rows'][i] for i in train]);norms=torch.linalg.vector_norm(ctx['x'][train][ctx['masks'][train]],dim=-1)
        try:coef,bias,diag=fit_detail_head(x[train],ctx['masks'][train],y,ctx['tokens'][train],mass,penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:
            (out/'failure-diagnostics.json').write_text(json.dumps(dict(fold=fold_id,error=str(exc),completed_folds=len(fits),controls=controls,performance_measured=False),indent=2));raise
        maps[held]=(x[held]@coef+bias).sigmoid();heads.append(dict(fold=fold_id,coef=coef,bias=bias,train_ids=[ctx['all_rows'][i]['id'] for i in train]));fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),training_norm_min=float(norms.min()),training_norm_median=float(norms.median()),training_norm_max=float(norms.max()),**diag))
    shared.finish(ctx,maps,fits,heads,front)
    state=torch.load(out/'fold-heads.pt',weights_only=True,map_location='cpu');state.update(objective='original_max_bound',feature_transform='sqrt384_times_unit_token',production_adopted=False);torch.save(state,out/'fold-heads.pt')
    p=out/'diagnostics.json';data=json.loads(p.read_text());data['transform_controls']=controls;p.write_text(json.dumps(data,ensure_ascii=False,indent=2))
