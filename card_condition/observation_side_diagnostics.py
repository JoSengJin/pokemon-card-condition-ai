"""Existing side-by-side observation diagnostics, without changing group or class denominators."""
from .observation_fitting import TARGET
from .score_diagnostics import score_diagnostics


def side_diagnostics(predictions, training):
    result={}
    for side in ('front','back'):
        part=[r for r in predictions if r['side']==side]
        train=[r for r in training if r['side']==side]
        metrics=dict(tp=0,tn=0,fp=0,fn=0)
        for row in part:
            truth=row['labels'][TARGET]; guess=int(row['probabilities'][TARGET]>=.5)
            metrics[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
        ranking=score_diagnostics(part,[TARGET])[TARGET] if part else None
        result[side]=dict(train_faces=len(train),train_groups=len({r['group'] for r in train}),
            train_clear=sum(r['labels'][TARGET]==0 for r in train),train_limited=sum(r['labels'][TARGET]==1 for r in train),
            validation_faces=len(part),validation_groups=len({r['group'] for r in part}),metrics_at_05=metrics,
            ranking={k:ranking[k] for k in ('known','positive','negative','groups','auroc','average_precision','balanced_accuracy_at_05')} if ranking else None,
            warning='missing_validation_class' if len({r['labels'][TARGET] for r in part})<2 else None)
    return result
