"""Frozen-checkpoint independent test evaluation; never model fitting."""
import json
from pathlib import Path
import torch
from .point_probe import digest
from .evaluation_inputs import development_sets
from .visibility_model import TARGET,VisibilityAnalyzer,visibility_rows
from .observation_crossfit import crossfit_summary,reject_duplicate_groups
from .score_diagnostics import score_diagnostics
from .regions import VISIBILITY_ISSUES
from .region_thresholds import group_error_rates


def evaluate_heldout(checkpoint, manifest, output, expected_sha256, device='auto'):
    output=Path(output); checkpoint=Path(checkpoint)
    if output.exists():raise ValueError('Output exists: choose a new heldout report directory')
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or any(c not in '0123456789abcdef' for c in expected_sha256):
        raise ValueError('Expected frozen checkpoint SHA256 required')
    if digest(checkpoint)!=expected_sha256:raise ValueError('Frozen checkpoint SHA256 mismatch')
    meta=torch.load(checkpoint,map_location='cpu',weights_only=True)
    development_sets(meta)
    hashes={str(Path(manifest).resolve()):digest(manifest),str(checkpoint.resolve()):expected_sha256}
    rows,skipped=visibility_rows(manifest,splits={'test'})
    if not rows:raise ValueError('No explicit heldout observation truth')
    reject_duplicate_groups(rows)
    for row in rows:
        if row['card_id'] in meta['development_ids'] or row['group'] in meta['development_groups']:
            raise ValueError('Heldout physical group or card was used in development')
        if set(row['image_hashes'])&set(meta['development_image_hashes']):
            raise ValueError('Heldout image pixels were used in development')
        hashes[row['image']]=digest(row['image'])
    if {r['labels'][TARGET] for r in rows}!={0,1}:
        raise ValueError('Both explicit heldout observation classes required')
    analyzer=VisibilityAnalyzer(checkpoint,device)
    predictions=[]
    for row in rows:
        result=analyzer.analyze(row['image'],row['box'],side=row['side'])
        predictions.append(dict(**row,probabilities={TARGET:result['observation_limit_score']}))
    summary=crossfit_summary(predictions)  # Metric-only helper; no fitting or split selection.
    by_side={side:score_diagnostics([r for r in predictions if r['side']==side],[TARGET])[TARGET]
             for side in ('front','back') if any(r['side']==side for r in predictions)}
    groups={}
    for row in predictions:
        counts=groups.setdefault(row['group'], {TARGET:dict(tp=0,tn=0,fp=0,fn=0)})[TARGET]
        truth=row['labels'][TARGET]; guess=int(row['probabilities'][TARGET]>=.5)
        counts[('t' if truth==guess else 'f')+('p' if guess else 'n')]+=1
    reasons={}
    for reason in VISIBILITY_ISSUES:
        part=[r for r in predictions if reason in r['visibility_issues']]
        detected=sum(r['probabilities'][TARGET]>=.5 for r in part)
        reasons[reason]=dict(test_faces=len(part),test_groups=len({r['group'] for r in part}),
                            detected=detected,missed=len(part)-detected,recall=detected/len(part) if part else None)
    if any(digest(p)!=h for p,h in hashes.items()):raise ValueError('Heldout evaluation inputs changed')
    report=dict(evaluation_kind='heldout_observation_test',split='test',target=TARGET,
        model_sha256=expected_sha256,summary=summary,by_side=by_side,
        reason_coverage=reasons,by_group=groups,
        group_error_rates_at_05=group_error_rates(groups,[TARGET]),
        predictions=predictions,skipped=skipped,
        input_hashes=hashes,development_overlap=False,fitted_model=False,selected_model=False,
        production_ready=False,requires_gemini=True,actual_calls_saved=0,
        limitations=['Independent only if human-confirmed new physical cards and untouched test assignment.',
            'A face may have multiple reasons; reason counts are not mutually exclusive.',
            'Small test sets cannot establish generalization; report reason and side coverage.',
            'No threshold tuning or checkpoint selection; do not repeatedly optimize against this test.',
            'Observation restriction is not card damage or a purchase rejection.'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    return report
