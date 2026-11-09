"""Common-runner saved OOF diagnostic; deliberately no model imports."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir())
if __name__=='__main__':
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if plan['hypothesis_id']!='surface-saved-rank-partition-20261109':raise ValueError('Wrong diagnostic')
    for path,digest in plan['input_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen input changed: '+path)
    for name in ('worker.py','analysis.py'):
        if (ROOT/plan['tracked_directory']/name).read_bytes()!=(ROOT/plan['runtime_directory']/name).read_bytes():raise ValueError('Mirror differs')
    source=json.loads((ROOT/plan['source_observations']).read_text());rows=source['rows'];scores=source['scores']
    if rows!=ref['rows'] or scores!=ref['before_scores']:raise ValueError('Saved scores/labels are not the fixed reference')
    folds=json.loads((ROOT/plan['folds']).read_text())
    spec=importlib.util.spec_from_file_location('rank_partition',ROOT/plan['runtime_directory']/'analysis.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    total,buckets,examples=module.partition(rows,scores,folds)
    if len(rows)!=1776 or total['pairs']!=520220 or abs(total['auc']-0.931924954826804)>1e-12:raise ValueError('Frozen dimensions/AUC changed')
    report=dict(schema_version=1,kind='saved_oof_rank_partition',source_record=plan['source_record'],source_sha=plan['source_sha'],independent=False,new_training_calls=0,new_inference_calls=0,threshold=.5,rows_count=len(rows),groups_count=len({r['group'] for r in rows}),positive=sum(r['target'] for r in rows),negative=sum(1-r['target'] for r in rows),total=total,buckets=buckets,photos=module.photos(rows,scores,folds),examples=examples)
    (out/'rank_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    (out/'observations.json').write_text(json.dumps(dict(rows=rows,scores=scores),allow_nan=False))
    (out/'evaluation.json').write_text(json.dumps(dict(diagnostic_valid=True,model_performance_changed=False,production_adopted=False,independent=False,new_training_calls=0,new_inference_calls=0,total=total,buckets=buckets),indent=2,allow_nan=False))
    print(json.dumps(dict(diagnostic_valid=True,total=total,buckets=buckets),allow_nan=False),flush=True)
