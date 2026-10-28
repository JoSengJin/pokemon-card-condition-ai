"""Frozen head audit through the common experiment runner only."""
import hashlib,html,importlib.util,json,os,sys
from pathlib import Path
import torch
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'card_condition').is_dir());sys.path.insert(0,str(ROOT))
TASK='surface-preserved-heads-20261028'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


if __name__=='__main__':
    assert Path(__file__).resolve().is_relative_to(ROOT/'artifacts');torch.set_num_threads(2);out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan=json.loads((out/'plan.json').read_text());ref=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text());assert plan['hypothesis_id']=='surface-preserved-heads-generalization-audit-20261028'
    for c in plan['code_changes']:assert (ROOT/c['path']).read_bytes()==(ROOT/'tools/experiments'/TASK/Path(c['path']).name).read_bytes()
    coex=load('coex',ROOT/'tools/experiments/surface-normal-coexclusion-20261025/worker.py');front=load('front',ROOT/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py');worker=load('candidate_worker',ROOT/'tools/experiments'/TASK/'worker.py');features=load('features',ROOT/'tools/experiments'/TASK/'features.py');audit=load('audit',Path(__file__).with_name('audit.py'))
    ctx=coex.replay_baseline(ROOT,plan,ref);proposal=json.loads((ROOT/plan['proposal']).read_text());folds=front.check_folds(proposal,ctx['all_rows'],ctx['rows'],ctx['identity'])
    states={k:torch.load(ROOT/v/'fold-heads.pt',weights_only=True,map_location='cpu') for k,v in plan['audit_models'].items()}
    fitref={k:{f['fold']:f['train_objective'] for f in json.loads((ROOT/v/'diagnostics.json').read_text())['fits']} for k,v in plan['audit_models'].items() if k in ('baseline','preserved')}
    details=audit.run_audit(ctx,folds,states,features,worker.balanced,fitref);details['source_sha256']=ctx['tracked']
    replay=load('replay',ROOT/'tools/experiments/region-photo-decode-once-20261028/worker.py');obs=replay.protected_replay(ctx,ref,front,proposal)
    obs['diagnostic_evidence']=dict(new_fits=0,lower_training_objective_all_folds=all(r['objective_certificate']['candidate_minus_embedded']<0 for r in details['folds']),max_held_map_error=max(r['max_held_map_error'] for r in details['folds']),role_selection=False)
    (out/'diagnostics.json').write_text(json.dumps(details,ensure_ascii=False,indent=2));(out/'observations.json').write_text(json.dumps(obs,allow_nan=False))
    tables=[]
    for fold in details['folds']:
        rows=[]
        for name,parts in fold['models'].items():
            for part,c in parts.items():rows.append('<tr><td>'+name+'</td><td>'+part+f'</td><td>{c["fn"]}/{c["positives"]}</td><td>{c["fp"]}/{c["negatives"]}</td><td>{c["point_fn"]}/{c["points"]}</td><td>{c["weak_fn"]}/{c["weak_positives"]}</td></tr>')
        tables.append('<section><h2>'+fold['fold']+'</h2><table><tr><th>固定head</th><th>資料</th><th>FN</th><th>FP</th><th>実際点FN</th><th>弱い陽性FN</th></tr>'+''.join(rows)+'</table><pre>'+html.escape(json.dumps(fold['objective_certificate'],indent=2))+'</pre></section>')
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>저장 head training/held 진단</title><style>body{font:15px/1.6 system-ui;padding:20px;background:#f4f6fa}section{background:white;padding:16px;margin:12px}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:6px}pre{white-space:pre-wrap}</style><h1>진척30/100 · 학습0 · 고정head training/held 진단</h1><p>usable-card-analysis-v1.0,+0%p. training행은fold간반복되므로합산정확도/독립표본아님. 역할head는diagnostic만이며후보선택/혼합비율조정0. 기존147/11cohort는원래checkpoint/cache재생보호,FN16/94·FP18/53·typed21/51동일(각0%p). H1/H2전체사진은../20261028T101236-890223b7/index.html 및../20261028T101319-9e1f577e/index.html. 점/구역라벨·분모·.5유지.</p>'+''.join(tables)+'</html>'
    for a,b in {'固定head':'고정 head','資料':'자료','実際点FN':'실제점 FN','弱い陽性FN':'구역 양성 FN'}.items():page=page.replace(a,b)
    (out/'index.html').write_text(page)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in ctx['tracked'].items());print(json.dumps(obs['diagnostic_evidence']),flush=True)
