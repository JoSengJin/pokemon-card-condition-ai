"""Common-runner-only deterministic output and decode/latency comparison; no fitting."""
import collections,hashlib,html,importlib.util,json,math,os,sys,time
from pathlib import Path
from unittest.mock import patch
import torch
from PIL import Image,ImageDraw
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))
from card_condition.region_model import RegionAnalyzer
from card_condition.regions import REGION_TARGET_AREAS
from card_condition.side_experiment import side_image


def measure(analyzer,groups,shared):
    started=time.perf_counter();results=[]
    for rows in groups:
        r=rows[0];areas=[x['area'] for x in rows]
        if shared:
            values=analyzer.analyze_regions(r['image'],r['card_box'],areas,batch_views=False)
        else:
            values=[analyzer.analyze(r['image'],r['card_box'],area,batch_views=False) for area in areas]
        results.extend(v['probabilities']['edge_defect'] for v in values)
    return time.perf_counter()-started,results


def protected_replay(ctx,reference,front,proposal):
    folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    joint=torch.load(ROOT/'artifacts/experiments/20261025T122011-647b0e9c/fold-heads.pt',weights_only=True,map_location='cpu')
    current=torch.load(ROOT/'artifacts/experiments/20261024T093945-04a7e5e8/local-heads.pt',weights_only=True,map_location='cpu')
    fixed=torch.load(ROOT/'artifacts/experiments/20261024T063834-3536c642/typed-training-tokens.pt',weights_only=True,map_location='cpu')
    legacy=torch.load(ROOT/'artifacts/experiments/20261024T060419-45e72d0a/training-tokens.pt',weights_only=True,map_location='cpu')
    maps=joint['maps'].clone()
    for fold_id,train,held in folds:
        head=next(h for h in joint['heads'] if h['fold']==fold_id)
        assert head['train_ids']==[ctx['all_rows'][i]['id'] for i in train]
        maps[held]=(ctx['x'][held]@head['coef']+head['bias']).sigmoid()
    for i,r in enumerate(ctx['rows']):
        if r['side']!='back':continue
        head=next(h for h in current['heads'] if h['side']=='back' and h['group']==r['group'])
        assert r['id'] not in head['train_ids']
        maps[i]=(ctx['x'][i]@head['coef']+head['bias']).sigmoid()
    assert float((maps-joint['maps']).abs().max())<=2e-5
    values=[float(maps[i,ctx['masks'][i]].max()) for i in range(147)]
    old=legacy['point_reference']['rows'];typed=fixed['typed_point_reference']['rows']
    old_scores=[float(maps[r['parent_index'],int(legacy['point_tokens'][r['parent_index']])]) for r in old]
    typed_scores=[float(maps[r['parent_index'],r['human_token']]) for r in typed]
    cohorts=[]
    for g in reference['required_cohorts']:
        assert g['rows'] in (ctx['rows'],old,typed)
        scores=typed_scores if g['rows']==typed else old_scores if g['rows']==old else values
        assert max(abs(a-b) for a,b in zip(scores,g['before_scores']))<=2e-5
        cohorts.append(dict(id=g['id'],rows=g['rows'],scores=scores,point_ids=g['point_ids'],point_scores=scores if g['point_ids'] else []))
    return dict(rows=ctx['rows'],scores=values,required_cohorts=cohorts)


def render(out,rows,reports):
    images=out/'images';images.mkdir();panels=[]
    for i,r in enumerate(rows):
        image=side_image(r['image'],r['box'],True,224);draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,223,223),outline='red' if r['labels']['edge_defect'] else 'green',width=3)
        image.save(images/f'{i}.png')
        text=[]
        for model in reports:
            text.append(f"{model['name']}: {model['before_scores'][i]:.6f} → {model['after_scores'][i]:.6f}")
        panels.append('<article><h3>'+html.escape(r['id'])+'</h3><img src="images/'+str(i)+'.png"><p>사람 정답: 엣지 '+('손상' if r['labels']['edge_defect'] else '정상')+'<br>'+html.escape(' / '.join(text))+'</p></article>')
    stats=[{k:v for k,v in m.items() if k not in ('before_scores','after_scores')} for m in reports]
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>사진 디코딩 중복 제거 실측</title><style>body{font:16px/1.6 system-ui;background:#f4f6fa;padding:20px;color:#172537}section,article{background:white;padding:16px;margin:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}img{max-width:100%}h3{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>진척30/100 · 사진 디코딩 중복 제거</h1><section><p>usable-card-analysis-v1.0,+0%p. CPU2threads/동시성1,1warmup+7교대,동일27개발구역(손상15·정상12)/9면,2개 기존 연구checkpoint. 학습0/정답·평가기준변경0. 정확도 변화없음·독립일반화/운영 Gemini 절감 미확인. 빨강/초록 테두리는 사람의 해당구역 손상/정상 정답이며 모델 위치 출력이 아니다. 속도는 로딩제외·batch_views=False,표본 p95는 운영p95아님.</p><pre>'+html.escape(json.dumps(stats,ensure_ascii=False,indent=2))+'</pre></section><div class="grid">'+''.join(panels)+'</div></html>'
    (out/'index.html').write_text(page)


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts')
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']).resolve()
    plan=json.loads((out/'plan.json').read_text());reference=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['hypothesis_id']=='region-photo-decode-once-20261028' and plan['gemini_calls_allowed']==0
    assert plan['timing']==dict(device='cpu',threads=2,warmups=1,repeats=7,batch_views=False,min_median_reduction=.05,max_score_delta=1e-7)
    for path,digest in plan['input_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    torch.set_num_threads(2)
    spec=importlib.util.spec_from_file_location('frozen_coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');coex=importlib.util.module_from_spec(spec);spec.loader.exec_module(coex)
    spec=importlib.util.spec_from_file_location('frozen_front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py');front=importlib.util.module_from_spec(spec);spec.loader.exec_module(front)
    ctx=coex.replay_baseline(ROOT,plan,reference)
    proposal=json.loads((ROOT/plan['proposal']).read_text())
    observations=protected_replay(ctx,reference,front,proposal)
    reports=[];frozen_rows=None;timing_passed=True
    for model in plan['models']:
        saved=json.loads((ROOT/model['report']).read_text())
        rows=[r for r in saved['predictions'] if r['labels']['edge_defect'] in (0,1) and r['area'] in REGION_TARGET_AREAS['edge_defect']]
        assert len(rows)==27 and sum(r['labels']['edge_defect']==1 for r in rows)==15
        if frozen_rows is None:frozen_rows=rows
        else:assert [{k:r[k] for k in ('id','image','box','card_box','labels','group','side','area')} for r in rows]==[{k:r[k] for k in ('id','image','box','card_box','labels','group','side','area')} for r in frozen_rows]
        groups=collections.defaultdict(list)
        for r in rows:groups[r['image'],tuple(r['card_box'])].append(r)
        groups=list(groups.values());ordered=[r for group in groups for r in group]
        assert [r['id'] for r in ordered]==[r['id'] for r in rows] and len(groups)==9
        for r,photo in zip(rows,plan['timing_photo_sha256'],strict=True):
            assert photo['id']==r['id'] and hashlib.sha256(Path(r['image']).read_bytes()).hexdigest()==photo['sha256']
            ctx['tracked'][r['image']]=photo['sha256']
        analyzer=RegionAnalyzer(ROOT/model['checkpoint'],'cpu')
        with patch('PIL.Image.open',wraps=Image.open) as opened:
            _,before=measure(analyzer,groups,False);before_opens=opened.call_count
        with patch('PIL.Image.open',wraps=Image.open) as opened:
            _,after=measure(analyzer,groups,True);after_opens=opened.call_count
        assert before_opens==27 and after_opens==9
        samples={False:[],True:[]};score_delta=max(abs(a-b) for a,b in zip(before,after))
        for number in range(7):
            for shared in ((False,True) if number%2==0 else (True,False)):
                elapsed,values=measure(analyzer,groups,shared);samples[shared].append(elapsed)
                score_delta=max(score_delta,max(abs(a-b) for a,b in zip(before,values)))
                assert all((a>=.5)==(b>=.5) for a,b in zip(before,values))
        assert score_delta<=1e-7
        median_before=sorted(samples[False])[3];median_after=sorted(samples[True])[3]
        improvement=1-median_after/median_before;timing_passed &= improvement>=.05
        counts={}
        for name,values in (('before',before),('after',after)):
            counts[name]=dict(fn=sum(v<.5 for r,v in zip(rows,values) if r['labels']['edge_defect']==1),fp=sum(v>=.5 for r,v in zip(rows,values) if r['labels']['edge_defect']==0),positives=15,negatives=12)
        assert counts['before']==counts['after']
        reports.append(dict(name=model['name'],checkpoint_sha256=analyzer.model_sha256,regions=27,faces=9,photo_opens_before=before_opens,photo_opens_after=after_opens,samples_before=samples[False],samples_after=samples[True],median_before=median_before,median_after=median_after,p95_before=max(samples[False]),p95_after=max(samples[True]),median_reduction=improvement,max_score_delta=score_delta,metrics=counts,before_scores=before,after_scores=after))
        print(json.dumps({k:v for k,v in reports[-1].items() if k not in ('before_scores','after_scores','samples_before','samples_after')},ensure_ascii=False),flush=True)
    for p,digest in ctx['tracked'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest,p
    render(out,frozen_rows,reports)
    diagnostics=dict(reports=reports,timing_acceptance_passed=bool(timing_passed),training_fits=0,new_labels=0,claude_data_used=False,gemini_calls=0,codex_model_calls=0,independent=False,production_adopted=False,source_sha256=ctx['tracked'])
    (out/'speed.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2,allow_nan=False))
    observations['diagnostic_evidence']=dict(timing_acceptance_passed=bool(timing_passed),models=[dict(name=r['name'],max_score_delta=r['max_score_delta'],median_before=r['median_before'],median_after=r['median_after'],median_reduction=r['median_reduction'],photo_opens_before=27,photo_opens_after=9) for r in reports],accuracy_improved=False)
    (out/'observations.json').write_text(json.dumps(observations,ensure_ascii=False,allow_nan=False))
