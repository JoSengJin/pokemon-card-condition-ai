"""Label-blind isolated training and trusted linear-patch inference, never generated scoring."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

from .experiment_record import read,save,sha,project_file,prepare,run,point_reference,freeze_required_cohorts
from .review import atomic_write

VERSION='isolated-linear-patch-v1'


def load_policy(root):
    path=root/'trusted-experiment.json'
    if not path.exists():raise ValueError('Trusted linear-patch evaluation contract is not configured')
    policy=read(path)
    if policy.get('adapter')!=VERSION:raise ValueError('Unsupported trusted evaluation adapter')
    for name,expected in policy['input_sha256'].items():
        if sha(project_file(root,name))!=expected:raise ValueError('Trusted input changed: '+name)
    return policy


def tensor_inputs(root,policy,reference):
    import torch
    metadata=read(project_file(root,policy['training_metadata']))
    rows=metadata['training_rows'];features={}
    for name in policy['feature_sources']:
        part=torch.load(project_file(root,name),weights_only=True,map_location='cpu')
        for i,identity in enumerate(part['ids']):
            if identity in features:raise ValueError('Duplicate training feature identity')
            features[identity]=(part['features'][i],part['masks'][i])
    if set(features)!={r['id'] for r in rows}:raise ValueError('Training feature identities differ from frozen metadata')
    for row in reference['rows']:
        if row not in rows:raise ValueError('Evaluation identity/truth differs from trusted metadata')
    x=torch.stack([features[r['id']][0] for r in rows]);masks=torch.stack([features[r['id']][1] for r in rows])
    if x.ndim!=3 or not torch.isfinite(x).all() or masks.dtype!=torch.bool or not masks.any(1).all():raise ValueError('Invalid frozen features')
    folds=metadata['folds'];seen=set()
    def identities(indices,key):
        return {policy['decoded_image_sha256'].get(rows[i]['id']) if key=='decoded_sha256' else rows[i].get(key) for i in indices}
    held_ids=set()
    for fold in folds:
        train,held=fold['train'],fold['held']
        if (not train or not held or len(set(train))!=len(train) or len(set(held))!=len(held)
                or any(type(i) is not int or not 0<=i<len(rows) for i in train+held)
                or set(train)&set(held) or seen&set(held)):
            raise ValueError('Invalid/disjoint frozen fold indices')
        for key in ('group','image_sha256','decoded_sha256'):
            if None in identities(train+held,key) or identities(train,key)&identities(held,key):raise ValueError('Training/evaluation group or photo overlap')
        seen.update(held);held_ids.update(rows[i]['id'] for i in held)
    if held_ids!={r['id'] for r in reference['rows']}:raise ValueError('Frozen folds must cover the paired reference exactly')
    return rows,x,masks,folds


def coefficients(path,dimension):
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size>2000000:raise ValueError('Unsafe candidate model output')
    value=read(path)
    if (set(value)!={'coef','bias'} or not isinstance(value['coef'],list) or len(value['coef'])!=dimension
            or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in [*value['coef'],value['bias']])):
        raise ValueError('Only finite linear coefficients and bias are accepted; scores are forbidden')
    return value


def predict(model,x,mask,point=None):
    import torch
    coef=torch.tensor(model['coef'],dtype=torch.float32)
    logits=x.to(dtype=torch.float32)@coef+model['bias']
    if not torch.isfinite(logits).all():raise ValueError('Nonfinite trusted inference')
    if point is not None:
        if not 0<=point<len(mask) or not mask[point]:raise ValueError('Invalid actual human point')
        return float(logits[point].sigmoid())
    return float(logits[mask].max().sigmoid())


def evaluate_models(root,policy,ref,models,inputs):
    import torch
    rows,x,masks,folds=inputs;by_id={r['id']:i for i,r in enumerate(rows)}
    scores={};point_scores={};point_by_row={}
    for identity in ref['point_ids']:
        row,token=identity.rsplit(':',1);point_by_row[row]=int(token)
    for fold,model in zip(folds,models,strict=True):
        for i in fold['held']:
            key=rows[i]['id'];scores[key]=predict(model,x[i],masks[i])
            if key in point_by_row:point_scores[key+':'+str(point_by_row[key])]=predict(model,x[i],masks[i],point_by_row[key])
    required=[];fresh={}
    for source in policy.get('required_features',[]):
        part=torch.load(project_file(root,source['features']),weights_only=True,map_location='cpu')
        cases=read(project_file(root,source['metadata']))['cases']
        if part['ids']!=[c['case']['id'] for c in cases]:raise ValueError('Required feature identities changed')
        for i,case in enumerate(cases):fresh[case['case']['id']]=(case['case'],part['features'][i],part['masks'][i])
    for cohort in ref['required_cohorts']:
        values=[];ps=[]
        for row in cohort['rows']:
            case,z,mask=fresh[row['id']]
            if row.get('image_sha256')!=case.get('decoded_sha256') or any(case.get(k)!=row.get(k) for k in ('id','group','target','box')):raise ValueError('Required truth/source mismatch')
            for key in ('group','image_sha256','decoded_sha256'):
                if case.get(key) is None or case[key] in {policy['decoded_image_sha256'].get(r['id']) if key=='decoded_sha256' else r.get(key) for r in rows}:raise ValueError('Required data leaked into training')
            values.append(sum(predict(m,z,mask) for m in models)/len(models))
        for identity in cohort['point_ids']:
            identity_row,token=identity.rsplit(':',1);_,z,mask=fresh[identity_row]
            ps.append(sum(predict(m,z,mask,int(token)) for m in models)/len(models))
        required.append(dict(id=cohort['id'],rows=cohort['rows'],scores=values,point_ids=cohort['point_ids'],point_scores=ps))
    return dict(rows=ref['rows'],scores=[scores[r['id']] for r in ref['rows']],point_ids=ref['point_ids'],
                point_scores=[point_scores[k] for k in ref['point_ids']],required_cohorts=required)


def verify_baseline(root,policy,ref,inputs):
    import torch
    models=[]
    for name in policy['baseline_models']:
        value=torch.load(project_file(root,name),weights_only=True,map_location='cpu')
        models.append(dict(coef=value['coef'].tolist(),bias=float(value['bias'])))
    if len(models)!=len(inputs[3]):raise ValueError('Baseline fold count mismatch')
    observation=evaluate_models(root,policy,ref,models,inputs)
    pairs=[(observation['scores'],ref['before_scores']),(observation['point_scores'],ref['point_scores'])]
    pairs += [(r['scores'],f['before_scores']) for r,f in zip(observation['required_cohorts'],ref['required_cohorts'],strict=True)]
    pairs += [(r['point_scores'],f['point_scores']) for r,f in zip(observation['required_cohorts'],ref['required_cohorts'],strict=True)]
    if any(len(a)!=len(b) or any(abs(x-y)>1e-6 for x,y in zip(a,b)) for a,b in pairs):raise ValueError('Trusted baseline replay differs from frozen reference')


def sandbox_profile(fold,project,python):
    if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').is_file():raise ValueError('macOS sandbox-exec is required; no unsandboxed fallback')
    quote=lambda p:json.dumps(str(Path(p).resolve()))
    reads=[fold,project,Path(sys.base_prefix),Path(sys.prefix)/'lib',Path('/usr/lib'),Path('/System/Library'),Path('/private/var/db/dyld')]
    rules=['(version 1)','(deny default)','(allow process-exec (literal '+quote(python)+'))','(allow sysctl-read)']
    rules += ['(allow file-read* (subpath '+quote(p)+'))' for p in reads]
    ancestors={a for p in reads for a in Path(p).resolve().parents}
    rules += ['(allow file-read* (literal '+quote(p)+'))' for p in sorted(ancestors)]
    rules += ['(allow file-read* (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))',
              '(allow file-write* (literal '+quote(fold/'output/model.json')+') (literal '+quote(fold/'output/stdout.log')+') (literal '+quote(fold/'output/training-diagnostics.json')+'))']
    return '\n'.join(rules)


def launch_worker(fold,project,timeout):
    """No credentials, live repository, evaluation inputs, network or child execution permission."""
    fold,project=fold.resolve(),project.resolve()
    python=Path(sys.executable).resolve();profile=sandbox_profile(fold,project,python)
    (fold/'sandbox.sb').write_text(profile)
    bootstrap="""import os,resource,sys
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_FSIZE,(67108864,67108864))
resource.setrlimit(resource.RLIMIT_CPU,(TIMEOUT,TIMEOUT))
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
sys.path.insert(0,PROJECT)
sys.path.append(SITE_PACKAGES)
os.chdir(FOLD)
OBSERVER_CODE
""".replace('TIMEOUT',str(int(timeout))).replace('SITE_PACKAGES',repr(str(Path(sys.prefix)/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages'))).replace('PROJECT',repr(str(project))).replace('FOLD',repr(str(fold)))
    from .training_diagnostics import OBSERVER
    bootstrap=bootstrap.replace('OBSERVER_CODE',OBSERVER)
    (fold/'bootstrap.py').write_text(bootstrap)
    out=fold/'output';out.mkdir(exist_ok=True)
    cache=fold/'torch-cache';(cache/'dynamo').mkdir(parents=True,exist_ok=True)
    env=dict(PATH='/usr/bin:/bin',HOME=str(out),TMPDIR=str(out),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',
             OPENBLAS_NUM_THREADS='2',TORCHINDUCTOR_CACHE_DIR=str(cache),TORCHINDUCTOR_FORCE_DISABLE_CACHES='1',CARD_CONDITION_TRAIN_INPUT=str(fold/'train.pt'),CARD_CONDITION_MODEL_OUTPUT=str(out/'model.json'),
             CARD_CONDITION_PROJECT_ROOT=str(project),CARD_CONDITION_EXPERIMENT_PARAMETER=str(fold/'parameter.json'))
    save(fold/'launch.json',dict(status='pending'))
    with (out/'stdout.log').open('wb') as log:  # The child receives only this write-only descriptor.
        child=subprocess.Popen(['/usr/bin/sandbox-exec','-f',str(fold/'sandbox.sb'),str(python),'-I','-B',str(fold/'bootstrap.py')],
            cwd=fold,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        save(fold/'launch.json',dict(status='running',pid=child.pid))
        try:code=child.wait(timeout=timeout)
        except BaseException:
            os.killpg(child.pid,signal.SIGKILL);child.wait();save(fold/'launch.json',dict(status='interrupted',return_code=child.returncode));raise
    save(fold/'launch.json',dict(status='finished',return_code=code))
    if code:raise ValueError('Isolated training failed (exit '+str(code)+'); see fold output/stdout.log; no retry')


def execute_request(request_path):
    import torch
    torch.set_num_threads(2)
    request=read(request_path);root=Path(request['root']);folder=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    ref=read(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']));policy=load_policy(root)
    if sha(root/'trusted-experiment.json')!=request['policy_sha256']:raise ValueError('Trusted policy changed')
    inputs=tensor_inputs(root,policy,ref);verify_baseline(root,policy,ref,inputs)
    rows,x,masks,folds=inputs;models=[];work=Path(request['work']);project=work/'project'
    for fold in folds:
        directory=work/('fold-'+str(fold['fold']))
        if directory.exists():raise ValueError('Previous isolated fold exists; uncertain training is never retried')
        directory.mkdir();train=fold['train'];targets=torch.tensor([rows[i]['target'] for i in train]);groups=[rows[i]['group'] for i in train]
        from collections import Counter
        counts=Counter(groups);weights=torch.tensor([1/counts[g] for g in groups]);weights[targets==1]*=weights[targets==0].sum()/weights[targets==1].sum()
        tokens=policy['point_tokens']
        if len(tokens)!=len(rows):raise ValueError('Frozen training point tokens missing')
        torch.save(dict(features=x[train],masks=masks[train],targets=targets,point_tokens=torch.tensor([tokens[i] for i in train]),weights=weights,
                        ids=[rows[i]['id'] for i in train]),directory/'train.pt')
        save(directory/'parameter.json',request['experiment_parameter'])
        (directory/'worker.py').write_text(Path(request['worker']).read_text())
        try:
            launch_worker(directory,project,min(policy.get('fold_timeout_seconds',180),300))
        finally:
            from .training_diagnostics import collect
            diagnostics=read(folder/'training-diagnostics.json') if (folder/'training-diagnostics.json').exists() else dict(version=1,folds=[])
            diagnostics['folds'].append(collect(directory))
            save(folder/'training-diagnostics.json',diagnostics)
        model=coefficients(directory/'output/model.json',x.shape[-1]);models.append(model)
        save(folder/('model-'+str(fold['fold'])+'.json'),model)
    observation=evaluate_models(root,policy,ref,models,inputs)
    # Never read generated observations.json or scores, even if the worker writes them.
    load_policy(root)
    save(folder/'observations.json',observation)
    save(folder/'evaluation-attestation.json',dict(version=VERSION,request_sha256=sha(request_path),policy_sha256=request['policy_sha256'],
        evaluator_sha256=sha(Path(__file__)),observations_sha256=sha(folder/'observations.json'),
        training_diagnostics_sha256=sha(folder/'training-diagnostics.json'),
        models={str(p.name):sha(p) for p in folder.glob('model-*.json')},label_blind_training=True,independent_inference=True,
        statistical_independence=False))


def execute_candidate(root,folder,verdict):
    """Run once through the existing common runner; apply to the live source only after acceptance."""
    from . import cross_review_auto as auto
    root,folder=root.resolve(),folder.resolve();journal=folder/'execution.json'
    if journal.exists():
        state=read(journal)
        if state['status']=='finished':return state
        raise ValueError('Previous automatic experiment is pending or uncertain; never retrain automatically')
    policy=load_policy(root)
    if not set(verdict['implementation_files'])<=set(policy['editable_sources']):raise ValueError('Unsupported source for the trusted evaluator')
    proposal=read(folder/'implementation-proposal.json');work=folder/'isolated';work.mkdir()
    project=work/'project';(project/'card_condition').mkdir(parents=True)
    for p in (root/'card_condition').glob('*.py'):shutil.copy2(p,project/'card_condition'/p.name)
    for name in policy.get('trainer_sources',[]):
        p=project_file(root,name);target=project/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    transaction=[]
    for edit in proposal['edits']:
        source=auto.model_file(root,edit['path']);target=project/edit['path']
        if sha(source)!=edit['before_sha256']:raise ValueError('User source changed before training')
        if not any(v['path']==edit['path'] for v in transaction):
            before=work/(str(len(transaction))+'-before.py');shutil.copy2(source,before)
            transaction.append(dict(path=edit['path'],before=str(before.relative_to(root)),before_sha256=sha(source)))
        content=target.read_text()
        if content.count(edit['old'])!=1:raise ValueError('Candidate edit anchor conflict')
        target.write_text(content.replace(edit['old'],edit['new'],1))
    for item in transaction:item['after_sha256']=sha(project/item['path'])
    worker=work/'worker.py';worker.write_text(proposal['worker'])
    selected=verdict['experiment'];previous=read(root/Path(read(folder/'packet.json')['latest_result']).parent/'plan.json')
    changes=[dict(path=str((project/i['path']).relative_to(root)),baseline=i['before']) for i in transaction]
    changes.append(dict(path=str(worker.relative_to(root)),baseline=None))
    plan=dict(hypothesis_id=selected['hypothesis_id'],hypothesis=selected['cause'],change=selected['smallest_experiment'],
        success_criterion=selected['success_criterion'],failure_criterion=selected['failure_criterion'],
        reference_result=read(folder/'packet.json')['latest_result'],acceptance=verdict['acceptance'],code_changes=changes,
        experiment_parameter=verdict['experiment_parameter'],required_cohorts=previous.get('required_cohorts',[]),gemini_calls_allowed=0)
    request=work/'request.json';save(request,dict(root=str(root),work=str(work),worker=str(worker),policy_sha256=sha(root/'trusted-experiment.json'),experiment_parameter=verdict['experiment_parameter']))
    command=[sys.executable,'-m','card_condition.cross_review_execution',str(request)]
    prepared=prepare(root,plan,command);experiment,item=prepared
    state=dict(status='running',experiment_folder=str(experiment),code_applied=False,worker_executed=False,transaction=transaction)
    save(journal,state)  # Before any child or training attempt.
    code=run(root,plan,command,prepared=prepared,timeout=auto.EXPERIMENT_TIMEOUT)
    record=read(experiment/'record.json');state.update(worker_executed=bool(list(work.glob('fold-*/launch.json'))),training_process_attempts=len(list(work.glob('fold-*/launch.json'))),experiment_status=record['status'])
    diagnostics=experiment/'training-diagnostics.json'
    if diagnostics.exists():
        record['files']['training-diagnostics.json']=sha(diagnostics);save(experiment/'record.json',record)
        state['training_diagnostics']=str(diagnostics)
    accepted=False
    if code==0:
        attestation=read(experiment/'evaluation-attestation.json');result=read(experiment/'result.json')
        if (attestation['evaluator_sha256']!=sha(Path(__file__)) or attestation['observations_sha256']!=sha(experiment/'observations.json')
                or attestation['training_diagnostics_sha256']!=sha(diagnostics)
                or attestation['request_sha256']!=sha(request) or attestation['policy_sha256']!=sha(root/'trusted-experiment.json')
                or any(sha(experiment/name)!=value for name,value in attestation['models'].items())):raise ValueError('Evaluation attestation mismatch')
        for name in ['evaluation-attestation.json',*attestation['models']]:record['files'][name]=sha(experiment/name)
        save(experiment/'record.json',record)
        result['trusted_evaluation']=attestation
        result['acceptance_passed']=bool(result['acceptance_passed'])
        accepted=auto.measured_gain(result,verified=True)
        state.update(acceptance_passed=result['acceptance_passed'],performance_improved_on_same_cohort=accepted)
        auto.render_result(root,experiment,verified_reference=read(experiment/'reference.json'))
        state['comparison_html']=str(experiment/'comparison.html')
    else:state.update(acceptance_passed=None,performance_improved_on_same_cohort=None)
    # Guard all files before any write. Candidate code never touched the live checkout during evaluation.
    if any(sha(root/i['path'])!=i['before_sha256'] for i in transaction):
        state.update(status='finished',outcome='source_conflict',reason='User source changed; no overwrite',source_restored=False)
        save(journal,state);return state
    if accepted:
        applied=[]
        try:
            for i in transaction:
                atomic_write(root/i['path'],(project/i['path']).read_text());applied.append(i)
            state.update(code_applied=True,outcome='accepted',source_restored=False)
        except BaseException:
            for i in transaction:
                if sha(root/i['path'])==i['after_sha256']:atomic_write(root/i['path'],(root/i['before']).read_text())
            state.update(status='finished',outcome='apply_failed_rolled_back',source_restored=True);save(journal,state);raise
    else:state.update(outcome='candidate_discarded',source_restored=False,rollback='Discarded isolated candidate; live source was unchanged')
    state['status']='finished';save(journal,state);return state


if __name__=='__main__':execute_request(Path(sys.argv[1]))
