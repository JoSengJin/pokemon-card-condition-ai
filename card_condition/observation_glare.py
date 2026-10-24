"""Glare-versus-explicitly-clear subset experiment; other reasons remain unknown."""
import torch
from torch import nn
from .model import checked_sigmoid
from .visibility_model import TARGET,class_group_weights,fit_side_centroids,observation_logits
from .observation_bootstrap import paired_group_bootstrap


def glare_cohort(row):
    return row['labels'][TARGET]==0 or 'glare' in row['visibility_issues']


def compare_glare(features,rows,folds,baseline):
    # Import locally: the general crossfit module calls this optional experiment.
    from .observation_crossfit import crossfit_summary
    eligible={i for i,row in enumerate(rows) if glare_cohort(row)}
    predictions=[];refused=[];fits=[]
    with torch.no_grad():
        for fold in folds:
            held=[i for i in fold['held_indices'] if i in eligible]
            if not held:
                continue
            train=[i for i in fold['train_indices'] if i in eligible]
            part=[rows[i] for i in train]
            try:
                for side in ('front','back'):
                    class_group_weights([r for r in part if r['side']==side])
            except ValueError:
                refused.append(dict(group=fold['group'],reason='missing_glare_or_clear_training_side_class',unscored_faces=len(held)))
                continue
            head=nn.Linear(features.shape[1],2).to(features.device)
            fit_side_centroids(head,features[train],part)
            sides=torch.tensor([int(rows[i]['side']=='back') for i in held],device=features.device)
            scores=checked_sigmoid(observation_logits(head,features[held],sides)).cpu().tolist()
            predictions.extend(dict(**rows[i],excluded_fit_group=fold['group'],probabilities={TARGET:p}) for i,p in zip(held,scores))
            fits.append(dict(excluded_group=fold['group'],fit_groups=sorted({r['group'] for r in part}),
                             train_indices=train,held_indices=held))
    keys={(r['card_id'],r['side']) for r in predictions}
    before=[r for r in baseline if (r['card_id'],r['side']) in keys]
    measurable=({r['labels'][TARGET] for r in predictions}=={0,1}
                and len({r['group'] for r in predictions})>=2)
    a=crossfit_summary(before) if measurable else None
    b=crossfit_summary(predictions) if measurable else None
    x=a['metrics_at_05'] if measurable else None
    y=b['metrics_at_05'] if measurable else None
    return dict(target='glare_vs_explicitly_clear',
        metric_target_alias='observation_limited equals glare on this selected cohort only',
        eligible_faces=len(eligible),scored_faces=len(predictions),refused_folds=refused,fit_folds=fits,
        other_restriction_faces=[dict(card_id=r['card_id'],group=r['group'],side=r['side'],reasons=r['visibility_issues'])
                                 for r in rows if not glare_cohort(r)],
        status='measured' if measurable else 'insufficient_scored_support',
        baseline=a,candidate=b,predictions=predictions,
        paired_group_sensitivity=paired_group_bootstrap(before,predictions) if measurable else None,
        research_direction_supported=(measurable and not refused and len(predictions)==len(eligible)
            and b['auroc']>a['auroc'] and b['average_precision']>a['average_precision']
            and y['fp']<=x['fp'] and y['fn']<=x['fn'] and (y['fp']<x['fp'] or y['fn']<x['fn'])),
        checkpoint_saved=False,production_model_changed=False,
        limitations=['Subset comparison only; not overall observation restriction performance.',
            'Only explicit glare is positive; explicit clear faces are negative.',
            'Other restricted faces remain unscored, not relabeled as clear.',
            'Both models scored on exactly the same eligible held physical faces.',
            'Refused folds are recorded and block research support; not counted as correct.',
            'Threshold and frozen features unchanged; no validation/test used.'])
