"""Frozen-head replay only; no optimizer/training imports or calls."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import torch
from PIL import Image,ImageOps

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text())
    ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    for path,digest in plan['input_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    sys.path.insert(0,str(ROOT/plan['tracked_directory']))
    from patch_evidence import score_with_evidence
    from patch_geometry import token_box
    from patch_report import render_report
    spec=importlib.util.spec_from_file_location('prior','tools/experiments/surface-corrected-labels-cv-20261104/worker.py')
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    selected=json.loads((ROOT/plan['selection']).read_text())
    runs={key:json.loads((ROOT/'artifacts/experiments'/run/'result.json').read_text()) for key,run in plan['runs'].items()}
    rows=ref['rows'];full=runs['mixture']['rows'];assert len(rows)==len(selected)==172
    for row,item in zip(rows,selected):assert row==full[item['parent_index']]
    folds=json.loads((ROOT/plan['folds']).read_text())
    sizes={}
    for row in rows:
        path=row['image']
        if path not in sizes:
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==row['image_sha256']
            with Image.open(path) as im:sizes[path]=ImageOps.exif_transpose(im).size
    torch.set_num_threads(2);torch.manual_seed(20261031)
    print(json.dumps(dict(stage='frozen_feature_extraction',rows=len(rows),photos=len(sizes),device='cpu',training_calls=0)),flush=True)
    body=torch.hub.load(str(ROOT/plan['backbone_directory']),'dinov2_vits14',source='local',pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(ROOT/plan['backbone_weights'],map_location='cpu',weights_only=True),strict=True)
    x,m=prior.base.backbone_features(body,rows,'cpu');del body
    torch.save(dict(ids=[r['id'] for r in rows],features=x,masks=m),out/'frozen-features.pt')
    entries=[dict(row=row,parent_index=item['parent_index'],tags=item['tags'],fold=folds[row['group']],models={}) for row,item in zip(rows,selected)]
    replay={};patch_logits={}
    for key,run in plan['runs'].items():
        models=json.loads((ROOT/'artifacts/experiments'/run/'models.json').read_text())
        predictions=[None]*len(rows);all_logits=torch.empty(m.shape,dtype=x.dtype)
        for fold in range(5):
            ii=[i for i,row in enumerate(rows) if folds[row['group']]==fold]
            if not ii:continue
            model=next(model for model in models if model['arm']=='revised' and model['fold']==fold)
            coef=torch.tensor(model['coef'],dtype=torch.float32);bias=torch.tensor(model['bias'],dtype=torch.float32)
            original_ho=[j for j,row in enumerate(full) if folds[row['group']]==fold]
            positions={j:k for k,j in enumerate(original_ho)}
            slots=[positions[selected[i]['parent_index']] for i in ii]
            # Restore original matmul shape; unused rows are workspace, never evidence/truth.
            workspace=torch.zeros((len(original_ho),*x.shape[1:]),dtype=x.dtype)
            workspace[slots]=x[ii]
            workspace_masks=torch.ones((len(original_ho),m.shape[1]),dtype=torch.bool)
            workspace_masks[slots]=m[ii]
            with torch.inference_mode():batch_scores,batch_evidence,batch_logits=score_with_evidence(workspace,workspace_masks,coef,bias)
            all_logits[ii]=batch_logits[slots]
            for i,slot in zip(ii,slots):
                score=batch_scores[slot];detail=batch_evidence[slot]
                expected=runs[key]['scores'][selected[i]['parent_index']]
                assert abs(score-expected)<=1e-6,(key,rows[i]['id'],score,expected)
                assert (score>=.5)==(expected>=.5),(key,rows[i]['id'])
                predictions[i]=score;detail['saved_score']=expected;detail['replay_error']=abs(score-expected)
                detail['top_geometry']=token_box(sizes[rows[i]['image']],rows[i]['box'],detail['top_index'])
                detail['second_geometry']=token_box(sizes[rows[i]['image']],rows[i]['box'],detail['second_index']) if detail['second_index'] is not None else None
                entries[i]['models'][key]=detail
        replay[key]=dict(max_score_error=max(v['models'][key]['replay_error'] for v in entries),predictions_unchanged=True)
        patch_logits[key]=all_logits
        print(json.dumps(dict(stage='saved_head_replayed',model=key,rows=len(rows),**replay[key])),flush=True)
    summary=dict(original_scoring_batch_shape_restored=True,kind='frozen_patch_evidence_replay',rows=172,photos=len(sizes),tags=dict(common_fp=160,new_fn=6,new_fp=17),
        replay=replay,training_calls=0,optimizer_steps=0,new_labels=0,independent=False,quality_improvement=False)
    (out/'patch-evidence.json').write_text(json.dumps(entries,indent=2,allow_nan=False))
    torch.save(dict(ids=[row['id'] for row in rows],masks=m,logits=patch_logits),out/'patch-logits.pt')
    (out/'diagnostics.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    render_report(entries,summary,out,plan)
    (out/'observations.json').write_text(json.dumps(dict(rows=rows,scores=[e['models']['mixture']['score'] for e in entries],diagnostic_evidence=summary),allow_nan=False))
    print(json.dumps(summary),flush=True)
