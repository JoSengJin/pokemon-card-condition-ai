"""Frozen-model explanation of four ranking regressions. No optimizer or fitting."""
import collections
import copy
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import sys

import torch
from torch.nn import functional as F

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))
BASE='artifacts/experiments/20261025T122011-647b0e9c'
RANK='artifacts/experiments/20261027T145641-21c22382'
CACHE='artifacts/experiments/20261024T063834-3536c642/typed-training-tokens.pt'
PROPOSAL='artifacts/experiments/20261024T103800-512a2260/joint-fold-proposal.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def training_state(x,masks,tokens,rows):
    x=x.double()
    y=torch.tensor([r['target'] for r in rows])
    counts=collections.Counter(r['group'] for r in rows)
    mass=torch.tensor([1/counts[r['group']] for r in rows])
    mass[y==1]*=mass[y==0].sum()/mass[y==1].sum()
    mass=mass.double();mass=mass/mass.sum()
    summaries=torch.stack([x[i,tokens[i]] if y[i]==1 and tokens[i]>=0 else x[i,masks[i]].mean(0) for i in range(len(x))])
    return (summaries*mass[:,None]).sum(0),mass


def components(x,mask,w0,b0,w1,b1,center):
    x,w0,w1,center=x.double(),w0.double(),w1.double(),center.double()
    b0,b1=float(b0),float(b1)
    z0=x@w0+b0;z1=x@w1+b1
    k0=int(z0.masked_fill(~mask,-torch.inf).argmax());k1=int(z1.masked_fill(~mask,-torch.inf).argmax())
    old,new=float(z0[k0]),float(z1[k1])
    intercept=float((b1+center@w1)-(b0+center@w0))
    direction=float((x[k0]-center)@(w1-w0))
    relocation=float((x[k1]-x[k0])@w1)
    error=abs(new-old-intercept-direction-relocation)
    assert error<=1e-8 and relocation>=-1e-8
    return dict(old_peak=k0,new_peak=k1,peak_changed=k0!=k1,old_max_logit=old,new_max_logit=new,
        delta_max_logit=new-old,raw_bias_delta=b1-b0,centered_bias_delta=intercept,
        coefficient_at_old_peak=direction,peak_relocation=relocation,additive_error=error,
        before_prediction=int(old>=0),after_prediction=int(new>=0),
        centered_bias_only_prediction=int(old+intercept>=0),coefficient_only_prediction=int(new-intercept>=0))


def pair_readout(x,masks,tokens,mass,rows,pairs,center,w0,b0,w1,b1,rank_module):
    x=x.double();xc=x-center
    w=w0.double().detach().clone().requires_grad_()
    bias=torch.tensor(float(b0+center@w0.double()),dtype=torch.float64,requires_grad=True)
    logits=xc@w+bias
    after=x@w1.double()+float(b1)
    info,gradients=[],[]
    for i,normal in pairs:
        loss=rank_module.same_photo_ranking_loss(logits,masks,tokens,mass,[(i,normal)])
        gw,gb=torch.autograd.grad(loss,(w,bias),retain_graph=True)
        point=logits[i,int(tokens[i])]
        analytic=torch.zeros_like(w);before_margin=[];after_margin=[]
        for j in normal:
            values=logits[j,masks[j]]
            bound=.1*torch.logsumexp(values/.1,0)
            gap=1+bound-point
            normal_feature=values.div(.1).softmax(0)@xc[j,masks[j]]
            analytic=analytic+mass[i]/len(normal)*gap.sigmoid()*(normal_feature-xc[i,int(tokens[i])])
            before_margin.append(float((point-bound).detach()))
            after_margin.append(float(after[i,int(tokens[i])]- .1*torch.logsumexp(after[j,masks[j]]/.1,0)))
        error=float((gw-analytic.detach()).abs().max())
        assert error<=1e-8 and abs(float(gb))<=1e-10
        delta=w1.double()-w0.double()
        alignment=float((-gw)@delta/(gw.norm()*delta.norm())) if float(gw.norm()*delta.norm())>0 else None
        info.append(dict(point_id=rows[i]['id'],group=rows[i]['group'],normal_ids=[rows[j]['id'] for j in normal],
            original_mass=float(mass[i]),before_margins=before_margin,after_margins=after_margin,
            before_margin_satisfied=all(v>=1 for v in before_margin),after_margin_satisfied=all(v>=1 for v in after_margin),
            weighted_rank_loss_before=float(loss.detach()),gradient_norm=float(gw.norm()),
            bias_gradient=float(gb),analytic_autograd_error=error,descent_update_cosine=alignment))
        gradients.append(gw.detach())
    return info,gradients


def render(out,cases,pairs,source_sha):
    panels=[]
    for c in cases:
        if c['change'] not in ('new_fn','new_fp','recovered'):
            continue
        details={k:c[k] for k in ('fold','truth','before_score','after_score','has_actual_point','old_peak','new_peak',
                   'centered_bias_delta','coefficient_at_old_peak','peak_relocation','centered_bias_only_prediction','coefficient_only_prediction','rank_directions')}
        panels.append('<article><h3>'+html.escape(c['change']+' '+c['id'])+'</h3><img src="../20261027T145641-21c22382/images/'+str(c['index'])+'.png">'
            '<pre>'+html.escape(json.dumps(details,ensure_ascii=False,indent=2))+'</pre></article>')
    summary=[{k:c[k] for k in ('id','fold','truth','before_score','after_score','centered_bias_delta','coefficient_at_old_peak','peak_relocation',
                              'centered_bias_only_prediction','coefficient_only_prediction')} for c in cases if c['change'] in ('new_fn','new_fp')]
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ranking 새 오류 원인 분해</title><style>body{font:15px/1.6 system-ui;margin:20px;background:#f3f5f9}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:12px}article{background:white;padding:14px}img{max-width:100%}h3,pre{overflow-wrap:anywhere;white-space:pre-wrap;font-size:12px}</style><h1>새 누락2·새 오탐2의 고정 모델 분해</h1><p>진척30/100 (usable-card-analysis-v1.0, +0%p) · worker SHA '+source_sha+'</p><p>동일147개발구역 baseline FN16/94(17.02%)→ranking15/94(15.96%,-1.06%p),FP18/53동일(33.96%),typed21/51동일(41.18%). 이번은고정모델readout이며학습0,성능변화추가측정/독립검증/모델채택아님.</p><p>가산성분은학습에사용한공통center좌표에서의원점수(logit)분해다. gradient방향은국소증거이며특정training쌍의인과효과로단정하지않는다. counterfactual은모델선택/threshold변경에사용하지않는다.</p><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre><h2>training쌍의margin/gradient</h2><pre>'+html.escape(json.dumps(pairs,ensure_ascii=False,indent=2))+'</pre><div class="grid">'+''.join(panels)+'</div></html>'
    (out/'index.html').write_text(page)


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts')
    torch.set_num_threads(2)
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text());reference=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['hypothesis_id']=='surface-ranking-regression-cause-20261028' and plan['experiment_kind']=='diagnostic'
    assert plan['gemini_calls_allowed']==0 and plan['independent'] is False
    assert all(sha(ROOT/p)==h for p,h in plan['input_sha256'].items())
    assert sha(__file__)==sha(ROOT/plan['tracked_source'])
    for name in (BASE,RANK):
        path=ROOT/name;record=json.loads((path/'record.json').read_text());assert record['status']=='completed'
        assert all(sha(path/p)==h for p,h in record['files'].items())
    previous=json.loads((ROOT/RANK/'result.json').read_text())
    observation=json.loads((ROOT/RANK/'observations.json').read_text())
    cache=torch.load(ROOT/CACHE,map_location='cpu',weights_only=True)
    old=torch.load(ROOT/BASE/'fold-heads.pt',map_location='cpu',weights_only=True)
    new=torch.load(ROOT/RANK/'fold-heads.pt',map_location='cpu',weights_only=True)
    rows=reference['rows'];all_rows=cache['rows'];x,masks,tokens=cache['features'],cache['masks'],cache['point_tokens']
    assert len(rows)==147 and len(all_rows)==153 and len(old['heads'])==len(new['heads'])==4
    assert all(all(a[k]==b[k] for k in ('id','group','target','box','image_sha256')) for a,b in zip(rows,all_rows))
    assert rows==previous['rows']==observation['rows'] and reference['before_scores']==previous['scores']==observation['scores']
    assert plan['required_cohorts']==json.loads((ROOT/RANK/'plan.json').read_text())['required_cohorts']
    for ref,cohort in zip(reference['required_cohorts'],observation['required_cohorts']):
        assert all(ref[k]==cohort[k] for k in ('id','rows','point_ids')) and ref['before_scores']==cohort['scores']
    modules={}
    for name,path in [('front','tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py'),('rank','tools/experiments/surface-same-photo-ranking-20261027/objective.py')]:
        spec=importlib.util.spec_from_file_location('frozen_'+name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules[name]=module
    source_hashes=json.loads((ROOT/RANK/'diagnostics.json').read_text())['source_sha256']
    assert all(sha(p)==h for p,h in source_hashes.items())
    from card_condition.ebay_dataset import decoded_hash
    identity={}
    for row in all_rows:
        if row['image'] not in identity:
            raw=Path(row['image']).read_bytes();identity[row['image']]={hashlib.sha256(raw).hexdigest(),decoded_hash(raw)[0]}
        assert row['image_sha256'] in identity[row['image']]
    proposal=json.loads((ROOT/PROPOSAL).read_text());folds=modules['front'].check_folds(proposal,all_rows,rows,identity)
    before_scores=json.loads((ROOT/BASE/'result.json').read_text())['scores']
    before_maps,after_maps=old['maps'],new['maps']
    assert before_maps.shape==after_maps.shape==masks[:147].shape
    assert max(abs(float(after_maps[i,masks[i]].max())-previous['scores'][i]) for i in range(147))<=2e-5
    assert max(abs(float(before_maps[i,masks[i]].max())-before_scores[i]) for i in range(147))<=2e-5
    assert previous['comparison']['new_misses']==[58,72] and previous['comparison']['new_false_positives']==[9,21]
    cases,pair_diagnostics=[],[];replay_error=0.
    for fold_id,train,held in folds:
        h0=next(h for h in old['heads'] if h['fold']==fold_id);h1=next(h for h in new['heads'] if h['fold']==fold_id)
        assert h0['train_ids']==h1['train_ids']==[all_rows[i]['id'] for i in train]
        local=[all_rows[i] for i in train];center,mass=training_state(x[train],masks[train],tokens[train],local)
        pairs=modules['rank'].training_pairs(local,tokens[train]);assert len(pairs) in (2,3)
        info,gradients=pair_readout(x[train],masks[train],tokens[train],mass,local,pairs,center,h0['coef'],h0['bias'],h1['coef'],h1['bias'],modules['rank'])
        pair_diagnostics.append(dict(fold=fold_id,pairs=info))
        for i in held:
            row=rows[i]
            for head,saved in ((h0,before_maps),(h1,after_maps)):
                replay=(x[i]@head['coef']+head['bias']).sigmoid()
                replay_error=max(replay_error,float((replay-saved[i]).abs().max()))
            item=components(x[i],masks[i],h0['coef'],h0['bias'],h1['coef'],h1['bias'],center)
            changed='new_fn' if i in previous['comparison']['new_misses'] else 'new_fp' if i in previous['comparison']['new_false_positives'] else 'recovered' if i in previous['comparison']['recovered'] else 'unchanged'
            if i in (58,72,9,21):
                assert item['before_prediction']==int(before_scores[i]>=.5) and item['after_prediction']==int(previous['scores'][i]>=.5)
            directions=[float(-(x[i,item['old_peak']].double()-center)@g) for g in gradients]
            item.update(index=i,id=row['id'],fold=fold_id,truth=row['target'],change=changed,
                before_score=before_scores[i],after_score=previous['scores'][i],has_actual_point=int(tokens[i])>=0,
                rank_directions=[dict(point_id=v['point_id'],local_logit_descent_direction=a) for v,a in zip(info,directions)])
            cases.append(item)
    assert replay_error<=2e-5 and len(cases)==91
    assert all(sha(ROOT/p)==h for p,h in plan['input_sha256'].items()) and all(sha(p)==h for p,h in source_hashes.items())
    evidence=dict(kind='ranking_regression_cause',fit_calls=0,backbone_calls=0,replay_max_abs_error=replay_error,
        focused=[{k:c[k] for k in ('index','fold','truth','centered_bias_delta','coefficient_at_old_peak','peak_relocation','centered_bias_only_prediction','coefficient_only_prediction')} for c in cases if c['change'] in ('new_fn','new_fp')],
        training_pair_exposures=sum(len(f['pairs']) for f in pair_diagnostics),
        initially_margin_satisfied=sum(p['before_margin_satisfied'] for f in pair_diagnostics for p in f['pairs']),
        causal_pair_attribution_verified=False,independent=False,production_adopted=False)
    assert len(json.dumps(evidence,allow_nan=False).encode())<=4000
    render(out,cases,pair_diagnostics,sha(__file__))
    (out/'diagnostics.json').write_text(json.dumps(dict(cases=cases,pair_diagnostics=pair_diagnostics,evidence=evidence,
        source_sha256={**source_hashes,**{str(ROOT/p):h for p,h in plan['input_sha256'].items()}},fit_calls=0,backbone_calls=0,
        gemini_calls=0,codex_model_calls=0,independent=False,production_adopted=False),ensure_ascii=False,indent=2,allow_nan=False))
    result=copy.deepcopy(observation);result['diagnostic_evidence']=evidence
    (out/'observations.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
    print(json.dumps(evidence,ensure_ascii=False),flush=True)
