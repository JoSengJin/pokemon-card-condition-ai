"""Two frozen diagnostics and one conditional relative-feature comparison."""
import collections,hashlib,html,importlib.util,json,os,sys
from pathlib import Path
import torch
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))
TASK='surface-feature-conflict-relative-20261028'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def finish_relative(ctx, maps, fits, heads, front):
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
    metrics['after_relative'] = metrics.pop('joint_holdout')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ctx['tracked'].items())
    page = (ctx['out']/'index.html').read_text()
    page = page.replace('Front Joint Holdout','Crop Relative Input').replace('앞면 표면 joint holdout 기준선','앞면 crop 내 상대 특징 입력')
    page = page.replace('before_single_group_heads','before_joint_holdout').replace('&quot;joint_holdout&quot;','&quot;after_relative&quot;')
    page = page.replace('단독제외','기존 공동제외').replace('joint holdout:','후보:')
    page = page.replace('<h1>', '<p>진척30/100 (usable-card-analysis-v1.0, +0%p). 같은4-fold의입력특징에서해당crop valid token평균만제거. 손실·초기값·정답·기준은기존그대로. 반복개발평가이며 독립시험/운영채택 아님. worker SHA256 '+ctx['worker_sha']+'</p><h1>',1)
    (ctx['out']/'index.html').write_text(page)
    torch.save(dict(heads=heads, maps=maps, objective='per_crop_valid_token_mean_subtraction',
                    production_adopted=False), ctx['out']/'fold-heads.pt')
    diagnostics = dict(metrics=metrics, fits=fits, panels=panels, source_sha256=ctx['tracked'],
        new_backbone_forwards=0, new_labels=0, gemini_calls=0, codex_model_calls=0, independent=False, production_adopted=False)
    (ctx['out']/'diagnostics.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, allow_nan=False))
    (ctx['out']/'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, required_cohorts=required),allow_nan=False))
    print(json.dumps(metrics, ensure_ascii=False), flush=True)



def finish_diagnostic(out,details,ctx):
    panels=[]
    for r in details['cases']:
        if r['index'] not in (9,21,42,46,60,69):continue
        panels.append('<article><h3>'+html.escape(r['id'])+'</h3><img src="../20261027T222515-1d33d82d/images/'+str(r['index'])+'.png"><pre>'+html.escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></article>')
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>특징 혼동·손실 충돌</title><style>body{font:15px/1.6 system-ui;padding:20px;background:#f3f5fa}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}article,section{background:white;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}img{max-width:100%}</style><h1>특징 혼동·손실 충돌 · 진척30/100</h1><section><p>usable-card-analysis-v1.0,+0%p. 고정 모델 진단/학습0. 기존147 FN16/94·FP18/53,다중점후보FN12/94(-4.26%p)·FP20/53(+3.77%p),실제점21/51동일. 이전 결과 재인용이며 이번 진단으로 정확도 개선 없음. 독립평가 아님. 최근접 후보는training만,점pool과정상pool크기가다르므로 cosine을정확도로해석하지않음. 사진의 파랑은이전후보peak이지위치정답아님. 국소gradient는최종재학습인과효과아님.</p></section><section><h2>네 손실 분해</h2><pre>'+html.escape(json.dumps(details['fold_losses'],ensure_ascii=False,indent=2))+'</pre></section><div class="grid">'+''.join(panels)+'</div></html>'
    (out/'index.html').write_text(page)
    details['source_sha256']=ctx['tracked'];(out/'diagnostics.json').write_text(json.dumps(details,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts')
    torch.set_num_threads(2);out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']).resolve()
    plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['gemini_calls_allowed']==0 and not plan['independent']
    for change in plan['code_changes']:
        source=ROOT/'tools/experiments'/TASK/Path(change['path']).name
        assert hashlib.sha256((ROOT/change['path']).read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest()
    coex=load('frozen_coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py')
    front=load('frozen_front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py')
    multi=load('frozen_multi',ROOT/'tools/experiments/surface-all-human-points-20261028/objective.py')
    cause=load('frozen_cause',ROOT/'tools/experiments/surface-ranking-regression-cause-20261028/worker.py')
    analysis=load('feature_analysis',Path(__file__).with_name('analysis.py'))
    transform=load('relative_transform',Path(__file__).with_name('transform.py'))
    ctx=coex.replay_baseline(ROOT,plan,ref)
    proposal=json.loads((ROOT/plan['proposal']).read_text());folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    old=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),map_location='cpu',weights_only=True)
    if plan['phase']=='diagnostic':
        assert plan['hypothesis_id']=='surface-feature-conflict-diagnostic-20261028'
        new=torch.load(ROOT/'artifacts/experiments/20261027T222515-1d33d82d/fold-heads.pt',map_location='cpu',weights_only=True)
        raw=[json.loads(s) for s in (ROOT/plan['point_source']).read_text().splitlines() if s.strip()]
        points=multi.existing_point_tokens(ctx['all_rows'],ctx['masks'],ctx['tokens'],raw)
        details=analysis.diagnose(ctx,folds,old,new,points,multi.all_point_loss,cause.training_state)
        replay=load('frozen_protected_replay',ROOT/'tools/experiments/region-photo-decode-once-20261028/worker.py')
        obs=replay.protected_replay(ctx,ref,front,proposal)
        obs['diagnostic_evidence']=dict(relative_input_evidence_gate=details['relative_input_evidence_gate'],focus=[{k:r[k] for k in ('index','common_delta','residual_delta','delta_logit','extra_click_local_descent')} for r in details['cases'] if r['index'] in (9,21)],gradient_sum_error=max(s['sum_error'] for fold in details['fold_losses'] for s in (fold['baseline_first'],fold['baseline_all'],fold['final_all'])))
        finish_diagnostic(out,details,ctx)
        (out/'observations.json').write_text(json.dumps(obs,allow_nan=False))
        print(json.dumps(obs['diagnostic_evidence']),flush=True)
    else:
        assert plan['phase']=='relative' and plan['hypothesis_id']=='surface-crop-relative-input-20261028'
        evidence=json.loads((ROOT/plan['diagnostic_result']).read_text());assert evidence['relative_input_evidence_gate']
        from card_condition.detail_bag import fit_detail_head
        x=ctx['x'].clone();indices=[i for i,r in enumerate(ctx['all_rows']) if r['side']=='front']
        x[indices]=transform.relative_tokens(x[indices],ctx['masks'][indices])
        assert torch.equal(x[[i for i,r in enumerate(ctx['all_rows']) if r['side']=='back']],ctx['x'][[i for i,r in enumerate(ctx['all_rows']) if r['side']=='back']])
        maps=old['maps'].clone();fits=[];heads=[]
        ctx.update(out=out,reference=ref,base=maps.clone(),fixed=torch.load(ROOT/coex.TYPED,map_location='cpu',weights_only=True),legacy=torch.load(ROOT/coex.LEGACY,map_location='cpu',weights_only=True),worker_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        for fold_id,train,held in folds:
            rows=[ctx['all_rows'][i] for i in train];counts=collections.Counter(r['group'] for r in rows)
            y=torch.tensor([r['target'] for r in rows]);mass=torch.tensor([1/counts[r['group']] for r in rows]);mass[y==1]*=mass[y==0].sum()/mass[y==1].sum()
            try:coef,bias,diag=fit_detail_head(x[train],ctx['masks'][train],y,ctx['tokens'][train],mass,penalty=1.,normal_reduction='max_bound')
            except ValueError as exc:
                (out/'failure-diagnostics.json').write_text(json.dumps(dict(fold=fold_id,error=str(exc),completed_folds=len(fits),performance_measured=False),indent=2));raise
            fits.append(dict(fold=fold_id,train_rows=len(train),held_rows=len(held),**diag));heads.append(dict(fold=fold_id,coef=coef,bias=bias,train_ids=[r['id'] for r in rows]))
            maps[held]=(x[held]@coef+bias).sigmoid()
        finish_relative(ctx,maps,fits,heads,front)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ctx['tracked'].items())
