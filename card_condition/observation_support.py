"""Post-prediction fold support audit; labels never enter held-group fitting."""
from .visibility_model import TARGET


def fold_reason_support(rows, predictions):
    result={}
    for name, candidate in predictions.items():
        sides={}
        details=[]
        for side in ('front','back'):
            part=[r for r in candidate if r['side']==side]
            metrics=dict(tp=0,tn=0,fp=0,fn=0)
            for row in part:
                truth=row['labels'][TARGET]; guess=int(row['probabilities'][TARGET]>=.5)
                metrics[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
                if not truth:
                    continue
                fit=[r for r in rows if r['side']==side and r['group']!=row['group']]
                for reason in sorted(set(row['visibility_issues'])):
                    support=[r for r in fit if reason in r['visibility_issues']]
                    details.append(dict(card_id=row['card_id'],group=row['group'],side=side,
                        reason=reason,detected=bool(guess),
                        other_fit_groups=sorted({r['group'] for r in support}),
                        other_fit_faces=len(support)))
            sides[side]=metrics
        reasons=[]
        for side,reason in sorted({(r['side'],r['reason']) for r in details}):
            part=[r for r in details if r['side']==side and r['reason']==reason]
            strata={}
            for key, supported in (('no_other_group',False),('has_other_group',True)):
                selected=[r for r in part if bool(r['other_fit_groups'])==supported]
                detected=sum(r['detected'] for r in selected)
                strata[key]=dict(faces=len(selected),groups=len({r['group'] for r in selected}),
                    detected=detected,missed=len(selected)-detected,
                    recall=detected/len(selected) if selected else None)
            reasons.append(dict(side=side,reason=reason,support_strata=strata))
        result[name]=dict(metrics_by_side=sides,reasons=reasons,positive_face_reasons=details)
    return dict(candidates=result,threshold=.5,affects_predictions=False,
        limitations=['Train-only diagnostic, not independent final evaluation.',
            'Support means another physical group with the same side and human restriction reason.',
            'Reason tags audit the binary classifier; no reason-specific model is trained.',
            'A multi-reason face appears in multiple reason counts; these counts cannot be summed as total errors.',
            'Unsupported folds remain in all original metrics; lack of support does not excuse an error.',
            'Presence of support does not establish adequate diversity or generalization.'])
