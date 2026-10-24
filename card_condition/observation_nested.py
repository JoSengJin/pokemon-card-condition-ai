"""Single-side glare threshold research with inner/outer group exclusion."""
import math
import torch
from torch import nn
from .model import checked_sigmoid
from .observation_glare import glare_cohort
from .quality_rates import rate_change
from .visibility_model import TARGET, class_group_weights, fit_centroid


def fitted_head(features, rows, indices):
    part = [rows[i] for i in indices]
    weights = features.new_tensor(class_group_weights(part))
    labels = features.new_tensor([r['labels'][TARGET] for r in part])
    head = nn.Linear(features.shape[1],1).to(features.device)
    fit_centroid(head,features[indices],labels,weights)
    return head


def nested_back_glare(features, rows):
    return nested_glare(features, rows, side='back')


def nested_glare(features, rows, *, side):
    if side not in ('front', 'back'):
        raise ValueError('Front or back side required')
    if (features.ndim != 2 or len(features) != len(rows) or not torch.isfinite(features).all()
            or any(r['split'] != 'train' for r in rows)):
        raise ValueError('Finite matching training-only features are required')
    eligible = [i for i,r in enumerate(rows) if r['side']==side and glare_cohort(r)]
    groups = sorted({rows[i]['group'] for i in eligible})
    counts = [dict(tp=0,tn=0,fp=0,fn=0) for _ in range(2)]
    predictions, folds = [], []
    with torch.no_grad():
        for group in groups:
            train = [i for i in eligible if rows[i]['group'] != group]
            held = [i for i in eligible if rows[i]['group'] == group]
            inner, audit = [], []
            for inner_group in sorted({rows[i]['group'] for i in train}):
                fit = [i for i in train if rows[i]['group'] != inner_group]
                probe = [i for i in train if rows[i]['group'] == inner_group]
                head = fitted_head(features,rows,fit)
                scores = checked_sigmoid(head(features[probe])).flatten().cpu().tolist()
                inner.extend((rows[i]['labels'][TARGET],p) for i,p in zip(probe,scores))
                audit.append(dict(held_group=inner_group,fit_groups=sorted({rows[i]['group'] for i in fit})))
            clear_scores = [p for t,p in inner if t == 0]
            if not clear_scores:
                raise ValueError('Inner clear support missing; no partial result')
            threshold = math.nextafter(max(clear_scores),math.inf)
            head = fitted_head(features,rows,train)
            scores = checked_sigmoid(head(features[held])).flatten().cpu().tolist()
            for i,p in zip(held,scores):
                truth = rows[i]['labels'][TARGET]
                for matrix,guess in zip(counts,(int(p>=.5),int(p>=threshold))):
                    matrix[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
                predictions.append(dict(card_id=rows[i]['card_id'],group=group,side=side,
                    truth=truth,score=p,threshold=threshold,fixed_prediction=int(p>=.5),
                    nested_prediction=int(p>=threshold)))
            folds.append(dict(held_group=group,fit_groups=sorted({rows[i]['group'] for i in train}),
                inner_folds=audit,threshold=threshold,inner_clear_faces=len(clear_scores),
                inner_fp=sum(t==0 and p>=threshold for t,p in inner),inner_fn=sum(t==1 and p<threshold for t,p in inner)))
    if not predictions:
        raise ValueError('No eligible '+side+'-glare training faces')
    comparison=rate_change(*counts)
    return dict(evaluation_kind='nested_training_'+side+'_glare',faces=len(predictions),groups=len(groups),
        threshold_policy='zero inner-held clear FP; nextafter(max clear score,+inf)',
        fixed_counts=counts[0],nested_counts=counts[1],rate_comparison=comparison,
        folds=folds,predictions=predictions,
        research_direction_supported=comparison['errors_jointly_improved'],
        production_ready=False,requires_gemini=True,actual_calls_saved=0,checkpoint_saved=False,
        limitations=['Reused training groups; not independent final performance.',
            side.capitalize()+' glare versus explicitly clear only; other side and restrictions excluded.',
            'Threshold selection changes decisions, not ranking or probability calibration.',
            'Zero inner FP does not guarantee zero errors on unseen groups.'])
