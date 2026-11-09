"""Stream frozen alpha0 OOF replay; expose missing human grounding, never fit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time
import torch
from PIL import Image,ImageOps

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']);plan=json.loads((out/'plan.json').read_text())
    ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id']!='surface-alpha0-grounding-diagnostic-20261110':raise ValueError('Wrong diagnostic')
    for path,digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen input changed: '+path)
    for name in ('worker.py','audit.py','answers.py','report.py','checks.py','review.js','review_checks.cjs'):
        if (ROOT/plan['tracked_directory']/name).read_bytes()!=(ROOT/plan['runtime_directory']/name).read_bytes():raise ValueError('Tracked/runtime source mismatch')
    sys.path.insert(0,str(ROOT/plan['runtime_directory']))
    from audit import make_packet,packet_digest
    from patch_evidence import score_with_evidence
    from patch_geometry import token_box
    from report import render_report
    control=ROOT/plan['control_directory'];old_record=json.loads((control/'record.json').read_text())
    if old_record['status']!='completed':raise ValueError('Frozen control incomplete')
    for name,digest in old_record['files'].items():
        if hashlib.sha256((control/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen control evidence changed')
    old=json.loads((control/'observations.json').read_text())
    if ref['rows']!=old['rows'] or ref['before_scores']!=old['scores']:raise ValueError('Fixed alpha0 reference mismatch')
    rows=ref['rows'];folds=json.loads((ROOT/plan['folds']).read_text());locations=json.loads((ROOT/plan['location_audit']).read_text())
    packet=make_packet(rows,ref['before_scores'],folds,locations['locations'],plan['packet_source'])
    if [e['row']['id'] for e in packet['entries'] if e['selected']]!=json.loads((ROOT/plan['selection']).read_text())['ids']:raise ValueError('Predeclared selection changed')
    models=json.loads((control/'models.json').read_text());heads={};groups={}
    for f in range(5):
        model=next(m for m in models if m['arm']=='revised' and m['fold']==f)
        coef=torch.tensor(model['coef'],dtype=torch.float32);bias=torch.tensor(model['bias'],dtype=torch.float32)
        if coef.shape!=(384,) or not torch.isfinite(coef).all() or not torch.isfinite(bias):raise ValueError('Finite frozen384D head required')
        trained=json.loads((control/('component-gradient-rows-fold'+str(f)+'.json')).read_text())['rows']
        held=[r for r in rows if folds[r['group']]==f]
        if {r['group'] for r in held}&{r['group'] for r in trained} or {r['image_sha256'] for r in held}&{r['image_sha256'] for r in trained}:raise ValueError('OOF photo/group overlap')
        heads[f]=(coef,bias)
    for i,row in enumerate(rows):groups.setdefault(row['image'],[]).append(i)
    spec=importlib.util.spec_from_file_location('prior','tools/experiments/surface-corrected-labels-cv-20261104/worker.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    torch.set_num_threads(2);torch.manual_seed(20261031);started=time.monotonic()
    body=torch.hub.load(str(ROOT/plan['backbone_directory']),'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'],map_location='cpu',weights_only=True),strict=True)
    predictions=[None]*len(rows);all_logits=torch.empty((len(rows),1024));all_masks=torch.empty((len(rows),1024),dtype=torch.bool)
    max_error=0.;max_feature_rows=0
    for number,(path,indices) in enumerate(groups.items(),1):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=rows[indices[0]]['image_sha256']:raise ValueError('Photo hash mismatch')
        with Image.open(path) as im:size=ImageOps.exif_transpose(im).size
        subset=[rows[i] for i in indices];x,m=prior.base.backbone_features(body,subset,'cpu');max_feature_rows=max(max_feature_rows,len(x))
        if len({folds[r['group']] for r in subset})!=1:raise ValueError('One photo crosses folds')
        coef,bias=heads[folds[subset[0]['group']]]
        with torch.inference_mode():scores,details,logits=score_with_evidence(x,m,coef,bias)
        all_logits[indices]=logits;all_masks[indices]=m
        for local,i in enumerate(indices):
            expected=ref['before_scores'][i];score=scores[local];error=abs(score-expected)
            if error>plan['replay_tolerance'] or (score>=.5)!=(expected>=.5):raise ValueError('Frozen score/prediction replay mismatch')
            max_error=max(max_error,error);predictions[i]=score;entry=packet['entries'][i]
            entry['image_size']=list(size);detail=details[local];detail['saved_score']=expected;detail['replay_error']=error
            detail['top_geometry']=token_box(size,rows[i]['box'],detail['top_index'])
            detail['second_geometry']=token_box(size,rows[i]['box'],detail['second_index']) if detail['second_index'] is not None else None
            entry['evidence']=detail
            if entry['selected']:entry['patch_scores']=[round(float(v),6) if valid else None for v,valid in zip(logits[local].sigmoid(),m[local])]
        del x,m,logits
        if number%20==0 or number==len(groups):print(json.dumps(dict(stage='frozen_replay',photos_done=number,photos_total=len(groups),training_calls=0,max_replay_error=max_error)),flush=True)
    del body
    packet['packet_id']=packet_digest(packet)
    summary=dict(kind='alpha0_visual_grounding_diagnostic',source_sha=plan['source_sha'],record_directory=str(out.relative_to(ROOT)),**packet['summary'],
        reusable_existing_points=locations['reusable_points'],regions_with_existing_points=locations['regions_with_points'],max_replay_error=max_error,
        predictions_unchanged=True,training_calls=0,optimizer_steps=0,new_labels=0,independent=False,quality_improvement=False,
        original_quality_acceptance_passed=False,original_quality_gates_unchanged=True,observation_limit_not_evaluated=True,
        max_streamed_feature_rows=max_feature_rows,all_region_logits_bytes=all_logits.numel()*all_logits.element_size(),
        worker_peak_rss_bytes_before_report=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
        replay_elapsed_seconds=time.monotonic()-started,heatmap_rounding_digits=6,visual_causes_human_unreviewed=True)
    with (out/'packet.json').open('x') as stream:json.dump(packet,stream,ensure_ascii=False,allow_nan=False)
    pending=[dict(id=e['row']['id'],image_sha256=e['row']['image_sha256'],target=e['row']['target'],outcome=e['outcome'],status='missing_location_or_explanation') for e in packet['entries'] if e['selected'] and not e['known_points']]
    with (out/'pending.json').open('x') as stream:json.dump(pending,stream,indent=2,ensure_ascii=False)
    torch.save(dict(ids=[r['id'] for r in rows],masks=all_masks,logits=all_logits),out/'patch-logits.pt')
    (out/'ui-source.js').write_bytes((ROOT/plan['runtime_directory']/'review.js').read_bytes())
    render_report(packet,summary,out,ROOT/plan['runtime_directory']/'review.js')
    summary['worker_peak_rss_bytes_after_report']=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)
    (out/'diagnostics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows,scores=predictions,diagnostic_evidence=summary),allow_nan=False))
    print(json.dumps(summary,ensure_ascii=False),flush=True)
