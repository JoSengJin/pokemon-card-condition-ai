"""One frozen4-fold normal-group objective comparison; common-runner only."""
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts')
    torch.set_num_threads(2)
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text())
    reference=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['hypothesis_id']=='surface-normal-group-objective-20261027'
    assert plan['gemini_calls_allowed']==0 and plan['independent'] is False
    assert plan['objective']==dict(temperature=.1,positive_mass=.5,normal_mass=.5,penalty=1.)
    for change in plan['code_changes']:
        source=ROOT/'tools/experiments/surface-normal-group-objective-20261027'/Path(change['path']).name
        assert hashlib.sha256((ROOT/change['path']).read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
    coex=load('frozen_coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py')
    front=load('frozen_front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py')
    objective=load('normal_group_objective',Path(__file__).with_name('objective.py'))
    ctx=coex.replay_baseline(ROOT,plan,reference)
    proposal=json.loads((ROOT/plan['proposal']).read_text())
    assert hashlib.sha256((ROOT/plan['proposal']).read_bytes()).hexdigest()==plan['proposal_sha256']
    folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    maps=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),map_location='cpu',weights_only=True)['maps'].clone()
    ctx.update(out=out,reference=reference,base=maps.clone(),before=ctx['replay'],
               fixed=torch.load(ROOT/coex.TYPED,map_location='cpu',weights_only=True),
               legacy=torch.load(ROOT/coex.LEGACY,map_location='cpu',weights_only=True),
               mask=ctx['masks'],contract=dict(proposal_sha256=plan['proposal_sha256']))
    fits,heads=[],[]
    for fold_id,train,held in folds:
        rows=[ctx['all_rows'][i] for i in train]
        counts=collections.Counter(r['group'] for r in rows)
        y=torch.tensor([r['target'] for r in rows])
        mass=torch.tensor([1/counts[r['group']] for r in rows])
        mass[y==1]*=mass[y==0].sum()/mass[y==1].sum()
        coef,bias,diag=objective.fit_normal_group_head(ctx['x'][train],ctx['masks'][train],y,ctx['tokens'][train],mass,
                                                       [r['group'] for r in rows],penalty=1.,normal_reduction='max_bound')
        assert diag['converged']
        fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),**diag))
        heads.append(dict(fold=fold_id,coef=coef,bias=bias,train_ids=[r['id'] for r in rows]))
        maps[held]=(ctx['x'][held]@coef+bias).sigmoid()
    front.finish(ctx,maps,fits,heads)
    page=(out/'index.html').read_text().replace('Front Joint Holdout','Normal Group Objective').replace(
        '앞면 표면 joint holdout 기준선','앞면 정상 실물 손실 집계 비교')
    page=page.replace('<h1>','<p>진척30/100 (usable-card-analysis-v1.0, +0%p). 정상 실물 평균 손실을 log-mean-exp로 변경한 반복개발 후보. 모델채택 없음.</p><h1>',1)
    (out/'index.html').write_text(page)
