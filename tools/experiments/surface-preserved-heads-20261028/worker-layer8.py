"""Front-surface block8 trial with same-tensor final-layer cache control."""
import hashlib,importlib.util,json,os,sys
from pathlib import Path
import torch
from torchvision.transforms.functional import to_tensor,normalize
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir());sys.path.insert(0,str(ROOT))
from card_condition.observation_backbone import DINOV2_REVISION
from card_condition.side_experiment import side_image
from card_condition.detail_bag import fit_detail_head
TASK='surface-preserved-heads-20261028'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def layer_pair(body,tensor):
    values=body.get_intermediate_layers(tensor,n=[7,11],reshape=False,return_class_token=False,norm=True)
    if len(values)!=2 or values[0].shape!=values[1].shape or values[0].ndim!=3 or not all(torch.isfinite(v).all() for v in values):
        raise ValueError('Two finite aligned normalized patch-token layers required')
    return values[0],values[1]


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts');torch.set_num_threads(2);out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text());assert plan['hypothesis_id']=='surface-front-block8-transfer-20261028'
    assert plan['layer_protocol']==dict(indices=[7,11],image_size=224,device='cpu',threads=2,feature_control_tolerance=.001,score_control_tolerance=2e-5)
    assert (ROOT/plan['code_changes'][0]['path']).read_bytes()==(ROOT/'tools/experiments'/TASK/'worker-layer8.py').read_bytes()
    coex=load('coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');front=load('front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py');shared=load('shared_worker',ROOT/'tools/experiments'/TASK/'worker.py');replay=load('protected_replay',ROOT/'tools/experiments/region-photo-decode-once-20261028/worker.py')
    ctx=coex.replay_baseline(ROOT,plan,ref);proposal=json.loads((ROOT/plan['proposal']).read_text());folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    body=torch.hub.load(str(ROOT/plan['vendor']), 'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['weights'],map_location='cpu',weights_only=True));body=body.to('cpu')
    indices=[i for i,r in enumerate(ctx['all_rows']) if r['side']=='front'];assert len(indices)==97
    middle=ctx['x'].clone();final=ctx['x'].clone()
    with torch.inference_mode():
        for i in indices:
            r=ctx['all_rows'][i];image=side_image(r['image'],r['box'],True,224);tensor=normalize(to_tensor(image),[.485,.456,.406],[.229,.224,.225])[None]
            a,b=layer_pair(body,tensor);assert a.shape==(1,256,384);middle[i]=a[0];final[i]=b[0]
    torch.save(dict(front_indices=indices,block8=middle[indices],final_cpu=final[indices],new_backbone_forwards=97),out/'front-layer-pair.pt')
    feature_error=float((final[indices]-ctx['x'][indices]).abs().max());control=dict(new_backbone_forwards=97,feature_control_error=feature_error,feature_control_limit=.001,control_passed=False)
    (out/'control.json').write_text(json.dumps(control,indent=2));assert feature_error<=.001
    cpu_ctx=dict(ctx,x=final);control_obs=replay.protected_replay(cpu_ctx,ref,front,proposal)
    assert all((s>=.5)==(b>=.5) for s,b in zip(control_obs['scores'],ref['before_scores']))
    for g,h in zip(control_obs['required_cohorts'],ref['required_cohorts'],strict=True):assert all((s>=.5)==(b>=.5) for s,b in zip(g['scores'],h['before_scores']))
    control.update(control_passed=True,max_control_score_error=max(abs(s-b) for s,b in zip(control_obs['scores'],ref['before_scores'])));(out/'control.json').write_text(json.dumps(control,indent=2))
    assert torch.equal(middle[[i for i,r in enumerate(ctx['all_rows']) if r['side']=='back']],ctx['x'][[i for i,r in enumerate(ctx['all_rows']) if r['side']=='back']])
    base=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),weights_only=True,map_location='cpu');maps=base['maps'].clone();fits=[];heads=[]
    ctx.update(out=out,reference=ref,phase='surface_block8_transfer',base=maps.clone(),fixed=torch.load(ROOT/coex.TYPED,weights_only=True,map_location='cpu'),legacy=torch.load(ROOT/coex.LEGACY,weights_only=True,map_location='cpu'),worker_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for fold_id,train,held in folds:
        rows=[ctx['all_rows'][i] for i in train];y,mass=shared.balanced(rows)
        try:coef,bias,diag=fit_detail_head(middle[train],ctx['masks'][train],y,ctx['tokens'][train],mass,penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:
            (out/'failure-diagnostics.json').write_text(json.dumps(dict(stage='head_fit',fold=fold_id,error=str(exc),completed_folds=len(fits),new_backbone_forwards=97,performance_measured=False),indent=2));raise
        maps[held]=(middle[held]@coef+bias).sigmoid();heads.append(dict(fold=fold_id,coef=coef,bias=bias,train_ids=[r['id'] for r in rows]));fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),**diag))
    shared.finish(ctx,maps,fits,heads,front)
    state=torch.load(out/'fold-heads.pt',weights_only=True,map_location='cpu');state['objective']='frozen_block8_front_surface';state['feature_layer']=8;torch.save(state,out/'fold-heads.pt')
    p=out/'diagnostics.json';d=json.loads(p.read_text());d['new_backbone_forwards']=97;d['control']=control;d['feature_layer']=8;p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
