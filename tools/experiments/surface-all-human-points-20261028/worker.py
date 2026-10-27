"""Single frozen-fold all-existing-human-point comparison; default checkout/common runner only."""
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import torch

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    metrics['training_point_inventory']=ctx['point_inventory']
    metrics['typed_points'] = dict(points=len(typed_scores),
        before_missed=sum(float(base[r['parent_index'],r['human_token']]) < .5 for r in typed_ref['rows']),
        after_missed=sum(value < .5 for value in typed_scores))
    panels = front.render(ctx['out'], rows, ctx['all_rows'], maps, masks, ctx['tokens'], scores, before, metrics)
    metrics['before_joint_holdout'] = metrics.pop('before_single_group_heads')
    metrics['after_all_points'] = metrics.pop('joint_holdout')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ctx['tracked'].items())
    page = (ctx['out']/'index.html').read_text()
    page = page.replace('Front Joint Holdout','Existing Multiple Point Comparison').replace('앞면 표면 joint holdout 기준선','앞면 표면 · 기존 모든 클릭 활용')
    page = page.replace('before_single_group_heads','before_joint_holdout').replace('&quot;joint_holdout&quot;','&quot;after_all_points&quot;')
    page = page.replace('단독제외','기존 공동제외').replace('joint holdout:','후보:')
    page = page.replace('<h1>', '<p>진척30/100 (usable-card-analysis-v1.0, +0%p). 같은4-fold에서 기존 첫 표면점 대신 같은 구역의 모든 기존 고유 표면점 토큰 평균. 반복개발평가이며 독립시험/운영채택 아님. worker SHA256 '+ctx['worker_sha']+'</p><h1>',1)
    (ctx['out']/'index.html').write_text(page)
    torch.save(dict(heads=heads, maps=maps, objective='all_existing_same_kind_point_tokens',
                    production_adopted=False), ctx['out']/'fold-heads.pt')
    diagnostics = dict(metrics=metrics, fits=fits, panels=panels, source_sha256=ctx['tracked'],
        new_backbone_forwards=0, new_labels=0, gemini_calls=0, codex_model_calls=0, independent=False, production_adopted=False)
    (ctx['out']/'diagnostics.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, allow_nan=False))
    (ctx['out']/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, required_cohorts=required),allow_nan=False))
    print(json.dumps(metrics, ensure_ascii=False), flush=True)


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts')
    torch.set_num_threads(2)
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']).resolve()
    assert out.is_relative_to(ROOT/'artifacts/experiments')
    plan=json.loads((out/'plan.json').read_text())
    reference=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['hypothesis_id']=='surface-all-human-points-20261028'
    assert plan['gemini_calls_allowed']==0 and plan['independent'] is False
    assert plan['objective']==dict(positive='mean_unique_existing_human_tokens',normal='max_bound',penalty=1.,initialization='zero',center='unchanged_first_point')
    for change in plan['code_changes']:
        source=ROOT/'tools/experiments/surface-all-human-points-20261028'/Path(change['path']).name
        assert hashlib.sha256((ROOT/change['path']).read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
    coex=load('frozen_coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py')
    front=load('frozen_front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py')
    objective=load('all_point_objective',Path(__file__).with_name('objective.py'))
    ctx=coex.replay_baseline(ROOT,plan,reference)
    proposal=json.loads((ROOT/plan['proposal']).read_text())
    assert hashlib.sha256((ROOT/plan['proposal']).read_bytes()).hexdigest()==plan['proposal_sha256']
    folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    raw=[json.loads(s) for s in (ROOT/plan['point_source']).read_text().splitlines() if s.strip()]
    all_tokens=objective.existing_point_tokens(ctx['all_rows'],ctx['masks'],ctx['tokens'],raw)
    inventory={side:dict(bags=sum(bool(ts) for r,ts in zip(ctx['all_rows'],all_tokens) if r['side']==side),unique_tokens=sum(len(ts) for r,ts in zip(ctx['all_rows'],all_tokens) if r['side']==side)) for side in ('front','back')}
    assert inventory==dict(front=dict(bags=20,unique_tokens=39),back=dict(bags=33,unique_tokens=46))
    maps=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),map_location='cpu',weights_only=True)['maps'].clone()
    ctx.update(out=out,reference=reference,base=maps.clone(),point_inventory=inventory,
        fixed=torch.load(ROOT/coex.TYPED,map_location='cpu',weights_only=True),
        legacy=torch.load(ROOT/coex.LEGACY,map_location='cpu',weights_only=True),
        worker_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    fits,heads=[],[]
    for fold_id,train,held in folds:
        rows=[ctx['all_rows'][i] for i in train]
        counts=collections.Counter(r['group'] for r in rows)
        y=torch.tensor([r['target'] for r in rows])
        mass=torch.tensor([1/counts[r['group']] for r in rows])
        mass[y==1]*=mass[y==0].sum()/mass[y==1].sum()
        try:
            coef,bias,diag=objective.fit_all_point_head(ctx['x'][train],ctx['masks'][train],y,ctx['tokens'][train],mass,[all_tokens[i] for i in train],penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:
            (out/'failure-diagnostics.json').write_text(json.dumps(dict(fold=fold_id,error=str(exc),train_ids=[r['id'] for r in rows],held_ids=[ctx['rows'][i]['id'] for i in held],completed_folds=len(fits),performance_measured=False),ensure_ascii=False,indent=2))
            raise
        fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),**diag))
        heads.append(dict(fold=fold_id,coef=coef,bias=bias,train_ids=[r['id'] for r in rows]))
        maps[held]=(ctx['x'][held]@coef+bias).sigmoid()
    finish(ctx,maps,fits,heads,front)
