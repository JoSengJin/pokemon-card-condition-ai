"""Back-side only all-existing-point loss; frozen train groups, no new acquisition."""
import hashlib,html,importlib.util,json,os,sys
from pathlib import Path
import torch
from PIL import ImageDraw
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir());sys.path.insert(0,str(ROOT))
from card_condition.side_experiment import side_image
from card_condition.local_wear_cnn import point_input_pixel


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def render(ctx,maps,scores,metrics):
    out=ctx['out'];(out/'images').mkdir();panels=[]
    typed=ctx['fixed']['typed_point_reference']['rows']
    for i,r in enumerate(ctx['rows']):
        if r['side']!='back':continue
        im=side_image(r['image'],r['box'],True,224);draw=ImageDraw.Draw(im);values=maps[i].clone();values[~ctx['masks'][i]]=-1;top=int(values.argmax())
        draw.rectangle((top%16*14,top//16*14,top%16*14+13,top//16*14+13),outline='blue',width=2)
        for point in typed:
            if point['parent_index']==i:
                px,py=point_input_pixel(r['image'],r['box'],point['point']);draw.ellipse((px-4,py-4,px+4,py+4),outline='red',width=2)
        im.save(out/'images'/f'{i}.png');wrong=(scores[i]>=.5)!=bool(r['target']);state=('누락' if r['target'] else '오탐') if wrong else '정답'
        panels.append(f'<article><h3>{html.escape(r["id"])}</h3><img loading="lazy" src="images/{i}.png"><p>사람: {"표면손상" if r["target"] else "표면정상"} · 후보: {state}<br>기존 {ctx["replay"][i]:.4f} → 후보 {scores[i]:.4f}</p></article>')
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>뒷면 기존 전체점 비교</title><style>body{font:16px/1.6 system-ui;background:#f5f7fa;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}article,section{background:white;margin:8px;padding:12px}img{max-width:100%}pre{white-space:pre-wrap}</style><h1>진척30/100 · 뒷면 기존 실제점 활용</h1><section><p>반복 개발/모델선택 자료, 독립시험·운영채택 아님. 빨강=기존 typed 사람점, 파랑=모델최대반응(사람위치정답 아님). 앞면은원래대조그대로. 기존147구역/legacy51/typed51/11cohort·threshold0.5·정답유지. 관찰제한성능미평가.</p><pre>'+html.escape(json.dumps(metrics,ensure_ascii=False,indent=2))+'</pre><a href="result.json">공통판정</a></section><div class="grid">'+''.join(panels)+'</div></html>');return len(panels)


def finish(ctx,maps,fits,heads):
    rows=ctx['rows'];scores=[float(maps[i][ctx['masks'][i]].max()) for i in range(147)];front=[i for i,r in enumerate(rows) if r['side']=='front'];assert torch.equal(maps[front],ctx['base'][front])
    fixed,legacy=ctx['fixed'],ctx['legacy'];old=fixed['point_reference'];typed=fixed['typed_point_reference'];olds=[float(maps[r['parent_index'],int(legacy['point_tokens'][r['parent_index']])]) for r in old['rows']];ts=[float(maps[r['parent_index'],r['human_token']]) for r in typed['rows']];req=[]
    for c in ctx['reference']['required_cohorts']:
        assert c['rows'] in (rows,old['rows'],typed['rows']);v=ts if c['rows']==typed['rows'] else olds if c['rows']==old['rows'] else scores;req.append(dict(id=c['id'],rows=c['rows'],scores=v,point_ids=c['point_ids'],point_scores=v if c['point_ids'] else []))
    metrics=dict(typed_points=dict(points=51,before_missed=sum(float(ctx['base'][r['parent_index'],r['human_token']])<.5 for r in typed['rows']),after_missed=sum(v<.5 for v in ts)),back_typed_points=dict(points=33,before_missed=sum(r['side']=='back' and float(ctx['base'][r['parent_index'],r['human_token']])<.5 for r in typed['rows']),after_missed=sum(r['side']=='back' and v<.5 for r,v in zip(typed['rows'],ts))),point_inventory=ctx['point_inventory'])
    for name,vals in [('before',ctx['replay']),('after',scores)]:metrics[name]=dict(fn=sum(r['target']==1 and s<.5 for r,s in zip(rows,vals)),fp=sum(r['target']==0 and s>=.5 for r,s in zip(rows,vals)),positives=94,negatives=53)
    metrics['new_fn']=[r['id'] for r,b,s in zip(rows,ctx['replay'],scores) if r['target']==1 and b>=.5>s];metrics['new_fp']=[r['id'] for r,b,s in zip(rows,ctx['replay'],scores) if r['target']==0 and b<.5<=s]
    panels=render(ctx,maps,scores,metrics);torch.save(dict(heads=heads,maps=maps,objective='back_all_existing_points',production_adopted=False),ctx['out']/'fold-heads.pt')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in ctx['tracked'].items())
    (ctx['out']/'observations.json').write_text(json.dumps(dict(rows=rows,scores=scores,required_cohorts=req),allow_nan=False));(ctx['out']/'diagnostics.json').write_text(json.dumps(dict(metrics=metrics,fits=fits,panels=panels,source_sha256=ctx['tracked'],new_backbone_forwards=0,new_labels=0,independent=False,production_adopted=False),ensure_ascii=False,indent=2));print(json.dumps(metrics,ensure_ascii=False),flush=True)


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts');torch.set_num_threads(2);out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']);plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text());assert plan['hypothesis_id']=='surface-back-all-existing-points-20261028'
    assert Path(__file__).read_bytes()==(ROOT/plan['tracked_source']).read_bytes()
    coex=load('coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');shared=load('shared',ROOT/'tools/experiments/surface-preserved-heads-20261028/worker.py');objective=load('objective',ROOT/'tools/experiments/surface-all-human-points-20261028/objective.py')
    ctx=coex.replay_baseline(ROOT,plan,ref);base=torch.load(ROOT/(coex.BASE+'/fold-heads.pt'),weights_only=True,map_location='cpu');current=torch.load(ROOT/coex.CURRENT,weights_only=True,map_location='cpu');maps=base['maps'].clone();fixed=torch.load(ROOT/coex.TYPED,weights_only=True,map_location='cpu');legacy=torch.load(ROOT/coex.LEGACY,weights_only=True,map_location='cpu')
    raw=[json.loads(s) for s in (ROOT/plan['point_source']).read_text().splitlines() if s.strip()];points=objective.existing_point_tokens(ctx['all_rows'],ctx['masks'],ctx['tokens'],raw);inventory=dict(bags=sum(bool(ts) for r,ts in zip(ctx['all_rows'],points) if r['side']=='back'),unique_tokens=sum(len(ts) for r,ts in zip(ctx['all_rows'],points) if r['side']=='back'));assert inventory==dict(bags=33,unique_tokens=46)
    ctx.update(out=out,reference=ref,base=maps.clone(),fixed=fixed,legacy=legacy,point_inventory=inventory);fits=[];heads=[];seen=[]
    backheads=[h for h in current['heads'] if h['side']=='back'];assert len(backheads)==21
    for old in backheads:
        group=old['group'];train=[i for i,r in enumerate(ctx['all_rows']) if r['side']=='back' and r['group']!=group];held=[i for i,r in enumerate(ctx['rows']) if r['side']=='back' and r['group']==group]
        assert old['train_ids']==[ctx['all_rows'][i]['id'] for i in train] and held
        assert not ({v for i in train for v in ctx['identity'][ctx['all_rows'][i]['image']]} & {v for i in held for v in ctx['identity'][ctx['rows'][i]['image']]})
        assert torch.allclose((ctx['x'][held]@old['coef']+old['bias']).sigmoid(),maps[held],atol=2e-5,rtol=0)
        y,mass=shared.balanced([ctx['all_rows'][i] for i in train])
        try:coef,bias,diag=objective.fit_all_point_head(ctx['x'][train],ctx['masks'][train],y,ctx['tokens'][train],mass,[points[i] for i in train],penalty=1.,normal_reduction='max_bound')
        except ValueError as exc:
            (out/'failure-diagnostics.json').write_text(json.dumps(dict(group=group,error=str(exc),completed_folds=len(fits),performance_measured=False),indent=2));raise
        maps[held]=(ctx['x'][held]@coef+bias).sigmoid();fits.append(dict(group=group,side='back',train_rows=len(train),held_rows=len(held),**diag));heads.append(dict(group=group,side='back',coef=coef,bias=bias,train_ids=old['train_ids']));seen+=held
    assert sorted(seen)==[i for i,r in enumerate(ctx['rows']) if r['side']=='back'];finish(ctx,maps,fits,heads)
