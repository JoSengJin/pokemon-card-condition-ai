"""Train-only leave-one-physical-group-out comparison, never final evaluation."""
import json
import math
from pathlib import Path
import torch
from torch import nn
from .model import checked_sigmoid, device_for
from .point_probe import digest
from .side_model import backbone_for
from .side_experiment import side_tensor
from .score_diagnostics import score_diagnostics
from .quality_rates import error_rates
from .observation_support import fold_reason_support
from .observation_bootstrap import paired_group_bootstrap
from .visibility_model import (TARGET,visibility_rows,class_group_weights,fit_centroid,
    fit_side_centroids,observation_features,observation_logits)


def reject_duplicate_groups(rows):
    owners={}
    for row in rows:
        for value in row['image_hashes']:
            if owners.setdefault(value,row['group'])!=row['group']:
                raise ValueError('Identical decoded image assigned to different physical groups')


def crossfit_summary(rows):
    weights=class_group_weights(rows)
    losses=[]
    metrics=dict(tp=0,tn=0,fp=0,fn=0)
    for row in rows:
        truth=row['labels'][TARGET]; p=row['probabilities'][TARGET]; guess=int(p>=.5)
        metrics[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
        losses.append(-math.log(max(1e-15,p if truth else 1-p)))
    ranking=score_diagnostics(rows,[TARGET])[TARGET]
    return dict(faces=len(rows),groups=len({r['group'] for r in rows}),metrics_at_05=metrics,rates_at_05=error_rates(metrics),
        balanced_bce=sum(w*l for w,l in zip(weights,losses))/sum(weights),
        constant_half_bce=math.log(2),auroc=ranking['auroc'],average_precision=ranking['average_precision'])


def group_crossfit(manifest, output, device='auto', pretrained=True, *, compare_ridge=False, compare_context=False, compare_logistic=False, compare_glare_only=False):
    if type(compare_ridge) is not bool:
        raise ValueError('compare_ridge must be boolean')
    if type(compare_context) is not bool:
        raise ValueError('compare_context must be boolean')
    if type(compare_logistic) is not bool:
        raise ValueError('compare_logistic must be boolean')
    if type(compare_glare_only) is not bool:
        raise ValueError('compare_glare_only must be boolean')
    output=Path(output)
    if output.exists():raise ValueError('Output exists: choose a new crossfit directory')
    hashes={str(Path(manifest).resolve()):digest(manifest)}
    rows,skipped=visibility_rows(manifest,splits={'train'})
    reject_duplicate_groups(rows)
    groups=sorted({r['group'] for r in rows})
    folds=[]; refused=[]
    for group in groups:
        train=[i for i,r in enumerate(rows) if r['group']!=group]
        held=[i for i,r in enumerate(rows) if r['group']==group]
        try:
            class_group_weights([rows[i] for i in train])
            for side in ('front','back'):
                class_group_weights([rows[i] for i in train if rows[i]['side']==side])
        except ValueError:
            refused.append(dict(group=group,reason='missing_training_side_class'))
            continue
        folds.append(dict(group=group,train_indices=train,held_indices=held,
                          fit_groups=sorted({rows[i]['group'] for i in train})))
    if not folds:raise ValueError('No eligible group-exclusive crossfit folds')
    device=device_for(device);torch.manual_seed(42)
    backbone,dimension=backbone_for('mobilenet_v3_small',pretrained);backbone.to(device)
    for row in rows:hashes[row['image']]=digest(row['image'])
    with torch.inference_mode():
        features=torch.cat([observation_features(backbone,r,device) for r in rows])
        context_features=(torch.cat([backbone(side_tensor(r['image'],r['box'],False)
            .unsqueeze(0).to(device)).mean((2,3)) for r in rows]) if compare_context else None)
    features=features.clone()
    if compare_context:
        context_features=torch.cat((features,context_features.clone()),dim=1)
    predictions={name:[] for name in ('global','side_aware')}
    if compare_ridge:
        predictions['side_ridge']=[]
        from .observation_ridge import fit_side_ridge, RIDGE_PENALTY
    if compare_context:
        predictions['side_context']=[]
    logistic_fits=[]
    if compare_logistic:
        predictions['side_logistic']=[]
        from .observation_logistic import fit_side_logistic,PENALTY,GRADIENT_LIMIT
    with torch.no_grad():
        for fold in folds:
            train=fold['train_indices'];held=fold['held_indices'];part=[rows[i] for i in train]
            global_head=nn.Linear(dimension,1).to(device);side_head=nn.Linear(dimension,2).to(device)
            fit_centroid(global_head,features[train],features.new_tensor([r['labels'][TARGET] for r in part]),
                         features.new_tensor(class_group_weights(part)))
            fit_side_centroids(side_head,features[train],part)
            sides=torch.tensor([int(rows[i]['side']=='back') for i in held],device=device)
            candidates=[('global',global_head,features),('side_aware',side_head,features)]
            if compare_ridge:
                ridge_head=nn.Linear(dimension,2).to(device)
                fit_side_ridge(ridge_head,features[train],part)
                candidates.append(('side_ridge',ridge_head,features))
            if compare_context:
                context_head=nn.Linear(dimension*2,2).to(device)
                fit_side_centroids(context_head,context_features[train],part)
                candidates.append(('side_context',context_head,context_features))
            if compare_logistic:
                logistic_head=nn.Linear(dimension,2).to(device)
                diagnostic=fit_side_logistic(logistic_head,features[train],part)
                logistic_fits.append(dict(excluded_group=fold['group'],sides=diagnostic))
                candidates.append(('side_logistic',logistic_head,features))
            for name,head,candidate_features in candidates:
                values=checked_sigmoid(observation_logits(head,candidate_features[held],sides)).cpu().tolist()
                if not all(math.isfinite(v) for v in values):raise ValueError('Non-finite crossfit prediction')
                predictions[name].extend(dict(**rows[i],excluded_fit_group=fold['group'],probabilities={TARGET:v}) for i,v in zip(held,values))
    summaries={k:crossfit_summary(v) for k,v in predictions.items()}
    before=summaries['global'];after=summaries['side_aware'];b=before['metrics_at_05'];a=after['metrics_at_05']
    consistent=(after['auroc']>before['auroc'] and after['average_precision']>before['average_precision']
        and after['balanced_bce']<math.log(2) and a['fp']<=b['fp'] and a['fn']<=b['fn']
        and (a['fp']<b['fp'] or a['fn']<b['fn']))
    if any(digest(p)!=h for p,h in hashes.items()):raise ValueError('Crossfit inputs changed')
    report=dict(evaluation_kind='training_group_crossfit_observation',split='train',target=TARGET,
        input_faces=len(rows),input_groups=len(groups),folds=folds,refused_folds=refused,skipped=skipped,
        summaries=summaries,predictions=predictions,reason_support=fold_reason_support(rows,predictions),input_hashes=hashes,pretrained=pretrained,device=str(device),
        consistent_research_direction=consistent,production_ready=False,requires_gemini=True,actual_calls_saved=0,
        limitations=['Already-used training data; not independent final performance evidence.',
            'All photos of the held physical group excluded from both fit and group weighting.',
            'Same eligible folds compared; refused folds are not treated as correct predictions.',
            'No validation/test images or labels read, no threshold or epoch selection.',
            'Observation restriction is not card damage or a purchase rejection.'])
    report['paired_group_sensitivity']={name:paired_group_bootstrap(predictions['side_aware'],candidate)
        for name,candidate in predictions.items() if name!='side_aware'}
    if compare_ridge:
        baseline=summaries['side_aware'];candidate=summaries['side_ridge']
        b=baseline['metrics_at_05'];c=candidate['metrics_at_05']
        report['ridge_comparison']=dict(penalty=RIDGE_PENALTY,intercept_penalized=False,
            objective='class/group balanced mean squared error on targets -1/+1 plus lambda*weight_squared',
            solver='CPU float64 normal equations',feature_scaling='unchanged',
            probability_calibrated=False,hyperparameter_search=False,
            research_direction_supported=(candidate['auroc']>baseline['auroc']
                and candidate['average_precision']>baseline['average_precision']
                and c['fp']<=b['fp'] and c['fn']<=b['fn']
                and (c['fp']<b['fp'] or c['fn']<b['fn'])),
            criterion='AUROC/AP improve; FP/FN do not increase and at least one decreases at unchanged 0.5',
            checkpoint_saved=False,production_model_changed=False)
    if compare_context:
        baseline=summaries['side_aware'];candidate=summaries['side_context']
        b=baseline['metrics_at_05'];c=candidate['metrics_at_05']
        report['context_comparison']=dict(input='concat card crop and full source at 224px each',
            feature_dimensions=dimension*2,classifier='unchanged side-aware balanced centroid',
            probability_calibrated=False,hyperparameter_search=False,
            research_direction_supported=(candidate['auroc']>baseline['auroc']
                and candidate['average_precision']>baseline['average_precision']
                and c['fp']<=b['fp'] and c['fn']<=b['fn']
                and (c['fp']<b['fp'] or c['fn']<b['fn'])),
            criterion='AUROC/AP improve; FP/FN do not increase and at least one decreases at unchanged 0.5',
            background_shortcut_risk=True,checkpoint_saved=False,production_model_changed=False)
    if compare_logistic:
        baseline=summaries['side_aware'];candidate=summaries['side_logistic']
        b=baseline['metrics_at_05'];c=candidate['metrics_at_05']
        report['logistic_comparison']=dict(penalty=PENALTY,intercept_penalized=False,
            objective='class/group balanced mean BCE plus lambda*weight_squared',
            solver='CPU float64 LBFGS; zero initialization; max100; strong_wolfe',
            convergence_gradient_limit=GRADIENT_LIMIT,fit_diagnostics=logistic_fits,
            feature_scaling='unchanged',probability_calibrated=False,hyperparameter_search=False,
            research_direction_supported=(candidate['auroc']>baseline['auroc']
                and candidate['average_precision']>baseline['average_precision']
                and c['fp']<=b['fp'] and c['fn']<=b['fn']
                and (c['fp']<b['fp'] or c['fn']<b['fn'])),
            criterion='AUROC/AP improve; FP/FN do not increase and at least one decreases at unchanged 0.5',
            checkpoint_saved=False,production_model_changed=False)
    if compare_glare_only:
        from .observation_glare import compare_glare
        report['glare_comparison']=compare_glare(features,rows,folds,predictions['side_aware'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    return report
