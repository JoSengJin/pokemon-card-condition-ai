"""Synthetic tensors only: no photos, frozen caches, models, worker or experiment runner."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import torch
from torch.nn import functional as F

FOLDER=Path(__file__).resolve().parent
BASE=FOLDER.parent/'surface-global-rank-globalmix-console-20261108'
sys.path.insert(0,str(FOLDER))
import objective as m


def load_reference():
    spec=importlib.util.spec_from_file_location('unchanged_globalmix',BASE/'objective.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def independent_terms(theta,x,valid,y,points,mass,penalty,reduction):
    logits=x@theta[:-1]+theta[-1];parts={0:[],1:[]}
    for i in range(len(x)):
        values=logits[i,valid[i]]
        if points[i]>=0:
            value=F.softplus(logits[i,points[i]] if y[i]==0 else -logits[i,points[i]])
        elif y[i]==0:
            value=F.softplus(.1*torch.logsumexp(values/.1,0) if reduction=='max_bound'
                             else torch.logsumexp(values,0)-torch.tensor(float(len(values))).double().log())
        else:value=F.softplus(-values.max())
        parts[int(y[i])].append(mass[i]*value)
    normals=torch.stack([.1*torch.logsumexp(logits[i,valid[i]]/.1,0) for i in range(len(x)) if y[i]==0])
    defects=torch.stack([logits[i,valid[i]].max() for i in range(len(x)) if y[i]==1])
    pairs=torch.stack([F.softplus(n-d) for d in defects for n in normals])
    return dict(normal_bag=sum(parts[0]),defect_bag=sum(parts[1]),arithmetic_rank=.5*pairs.mean(),
        global_pair_lme=.5*(torch.logsumexp(pairs,0)-torch.tensor(float(len(pairs))).double().log()),
        l2=.5*penalty*theta[:-1].square().sum())


def fit_case(module,x,valid,y,points,mass,folder):
    os.environ['CARD_CONDITION_EXPERIMENT_DIR']=str(folder);os.environ['SURFACE_RANK_FOLD']='2'
    result=module.fit_detail_head(x,valid,y,points,mass,normal_reduction='max_bound')
    diag=json.loads((folder/'fit-diagnostics-fold2.json').read_text())
    trace=[json.loads(line) for line in (folder/'armijo-fold2.jsonl').read_text().splitlines()]
    assert diag['total_evaluations']==1+sum(e['event']=='trial' for e in trace)
    return result,diag,trace


def rejected_trial(*args):
    global calls,initial_loss,rejected_hash
    calls+=1;result=original_eval(*args)
    if calls==1:initial_loss=result[0]
    if calls==2:
        rejected_hash=hashlib.sha256(args[0].numpy().tobytes()).hexdigest()
        return initial_loss+10.,torch.zeros_like(result[1]),result[2],result[3]
    return result


def boundary_direction(gradient,state):
    if 1e-7<float(gradient.abs().max())<=1e-5:return gradient.clone()
    return original_direction(gradient,state)


def corrupt_terms(*args):
    result=original_eval(*args);result[3][1]['arithmetic_rank']*=2
    return result


reference=load_reference();torch.set_num_threads(2)
max_gradient_error=0.;max_loss_error=0.
# The unmodified objective is the oracle; the component formula is independently rebuilt.
for seed in range(7):
    torch.manual_seed(seed);x=torch.randn(4,3,3,dtype=torch.float64)
    valid=torch.tensor([[1,1,0],[1,0,1],[1,1,1],[0,1,1]],dtype=torch.bool)
    y=torch.tensor([0,1,0,1]);points=torch.tensor([-1,-1,1,2]);mass=torch.tensor([.1,.2,.3,.4],dtype=torch.float64)
    theta=torch.randn(4,dtype=torch.float64)*.2
    for reduction in ['max_bound','mean_odds']:
        before=reference.loss_and_grad(theta,x,valid,y,points,mass,1.,reduction)
        after=m.loss_and_grad(theta,x,valid,y,points,mass,1.,reduction)
        assert before[0]==after[0] and torch.equal(before[1],after[1]) and torch.equal(before[2],after[2])
        audit_theta,terms=after[3];probe=theta.clone().requires_grad_()
        expected=independent_terms(probe,x,valid,y,points,mass,1.,reduction);summed=torch.zeros_like(theta)
        for name,value in terms.items():
            g=torch.autograd.grad(value,audit_theta,retain_graph=True)[0]
            oracle=torch.autograd.grad(expected[name],probe,retain_graph=True)[0]
            max_gradient_error=max(max_gradient_error,float((g-oracle).abs().max()))
            max_loss_error=max(max_loss_error,abs(float(value.detach()-expected[name].detach())))
            assert torch.allclose(g,oracle,atol=1e-13,rtol=1e-13)
            assert abs(float(value.detach()-expected[name].detach()))<1e-13
            if name in ['arithmetic_rank','global_pair_lme','l2']:assert abs(float(g[-1]))<1e-13
            summed+=g
        assert torch.allclose(summed,after[1],atol=1e-13,rtol=1e-13)
print('PASS:14 direct objective cases: exact original loss/gradient/active parity; five independent derivatives; rank/L2 bias0')
# Independent central finite differences of each diagnostic component, away from max ties.
for name in terms:
    for j in range(len(theta)):
        plus=theta.clone();minus=theta.clone();plus[j]+=1e-6;minus[j]-=1e-6
        numeric=float((independent_terms(plus,x,valid,y,points,mass,1.,reduction)[name]
                      -independent_terms(minus,x,valid,y,points,mass,1.,reduction)[name])/2e-6)
        exact=float(torch.autograd.grad(terms[name],audit_theta,retain_graph=True)[0][j])
        assert abs(numeric-exact)<1e-8,(name,j,numeric,exact)
print('PASS:20 component-wise finite difference checks')
# Three actual synthetic fit paths, including zero-mass removal and point/presence roles.
fixtures=[
 (torch.tensor([[[-1.],[-1.]],[[1.],[1.]]]),torch.ones((2,2),dtype=torch.bool),torch.tensor([0,1]),torch.tensor([-1,-1]),torch.ones(2)),
 (torch.tensor([[[-2.],[-2.],[-2.]],[[-1.],[-1.],[-1.]],[[1.],[1.],[1.]],[[2.],[2.],[2.]]]),torch.tensor([[1,1,0],[1,0,1],[1,1,1],[0,1,1]],dtype=torch.bool),torch.tensor([0,0,1,1]),torch.tensor([-1,0,-1,2]),torch.tensor([1.,2.,3.,4.])),
 (torch.tensor([[[-1.,.2]],[[1.,-.2]],[[99.,99.]]]),torch.ones((3,1),dtype=torch.bool),torch.tensor([0,1,0]),torch.tensor([-1,0,-1]),torch.tensor([1.,1.,0.])),
]
fit_summaries=[]
for number,args in enumerate(fixtures):
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);(root/'before').mkdir();(root/'after').mkdir()
        b,bd,bt=fit_case(reference,*args,root/'before');c,cd,ct=fit_case(m,*args,root/'after')
        assert torch.equal(b[0],c[0]) and torch.equal(b[1],c[1]) and b[2]==c[2] and bd==cd and bt==ct
        record=json.loads((root/'after/component-gradients-fold2.json').read_text())
        assert record['parameter_sha256']==cd['parameter_sha256'] and record['total_evaluations']==cd['total_evaluations']
        assert record['extra_objective_evaluations']==record['extra_optimizer_steps']==0
        assert record['gradient_sum_max_error']<=1e-10 and record['loss_sum_abs_error']<=1e-10
        assert record['training']['bags']==int((args[-1]>0).sum())
        keep=args[-1]>0;normalized=args[-1].double()[keep];normalized=normalized/normalized.sum()
        assert record['training']['mass_sha256']==hashlib.sha256(normalized.numpy().tobytes()).hexdigest()
        assert record['training']['target_sha256']==hashlib.sha256(args[2][keep].numpy().tobytes()).hexdigest()
        assert record['training']['mask_sha256']==hashlib.sha256(args[1][keep].numpy().tobytes()).hexdigest()
        grads=torch.tensor([v['gradient'] for v in record['components'].values()],dtype=torch.float64)
        assert torch.allclose(grads.sum(0),torch.tensor(record['total']['gradient'],dtype=torch.float64),atol=1e-10,rtol=0)
        # Output expression stays masked max -> sigmoid; exact fitted weights/bias give exact scores.
        logits=args[0]@c[0]+c[1];old_logits=args[0]@b[0]+b[1]
        assert torch.equal(logits.masked_fill(~args[1],-torch.inf).amax(1).sigmoid(),old_logits.masked_fill(~args[1],-torch.inf).amax(1).sigmoid())
        fit_summaries.append(dict(fixture=number,evaluations=cd['total_evaluations'],iterations=cd['n_iter'],gradient=cd['max_gradient']))
print('PASS:3 synthetic fits: bit-identical coefficients/bias/scores/full Armijo traces/diagnostics; evaluations counted; zero-mass filtering')
# Already converged at initial evaluation; no unbound previous trial/audit.
zero=torch.zeros((2,1,2));mask=torch.ones((2,1),dtype=torch.bool);labels=torch.tensor([0,1]);points=torch.tensor([-1,-1]);mass=torch.ones(2)
with tempfile.TemporaryDirectory() as directory:
    _,diag,trace=fit_case(m,zero,mask,labels,points,mass,Path(directory))
    rec=json.loads(Path(directory,'component-gradients-fold2.json').read_text())
    assert diag['total_evaluations']==1 and not trace and rec['reason']=='gradient_target'
print('PASS: initially converged graph recorded without an extra evaluation')
# A rejected candidate pretends to have zero gradient: it must never become the recorded state.
original_eval=m.loss_and_grad;m.loss_and_grad=rejected_trial;calls=0
with tempfile.TemporaryDirectory() as directory:
    os.environ['CARD_CONDITION_EXPERIMENT_DIR']=directory
    try:m.fit_detail_head(*fixtures[0],normal_reduction='max_bound')
    finally:m.loss_and_grad=original_eval
    rec=json.loads(Path(directory,'component-gradients-fold2.json').read_text());diag=json.loads(Path(directory,'fit-diagnostics-fold2.json').read_text())
    logs=[json.loads(line) for line in Path(directory,'armijo-fold2.jsonl').read_text().splitlines()]
    assert not next(e for e in logs if e['event']=='trial')['armijo_passed']
    assert rec['parameter_sha256']==diag['parameter_sha256']!=rejected_hash and calls==diag['total_evaluations']
print('PASS: rejected zero-gradient trial excluded; final accepted hash and evaluation count verified')
# Existing success threshold accepts <=1e-5 even if the internal target was not reached.
original_direction=m.lbfgs_direction;m.lbfgs_direction=boundary_direction
with tempfile.TemporaryDirectory() as directory:
    try:_,diag,_=fit_case(m,*fixtures[0],Path(directory))
    finally:m.lbfgs_direction=original_direction
    assert diag['reason']=='non_descent_direction' and 1e-7<diag['max_gradient']<=1e-5
    assert Path(directory,'component-gradients-fold2.json').is_file()
print('PASS: accepted termination between1e-7 and1e-5 audited without changing the success gate')
# Exclusive create must retain existing evidence byte-for-byte.
with tempfile.TemporaryDirectory() as directory:
    dest=Path(directory,'component-gradients-fold2.json');dest.write_text('KEEP_EXISTING_EVIDENCE')
    try:fit_case(m,zero,mask,labels,points,mass,Path(directory))
    except FileExistsError:pass
    else:raise AssertionError('Existing component evidence must not be overwritten')
    assert dest.read_text()=='KEEP_EXISTING_EVIDENCE'
print('PASS: existing sidecar refused without overwrite')
# A corrupt component decomposition is rejected, not emitted as valid training evidence.
m.loss_and_grad=corrupt_terms
with tempfile.TemporaryDirectory() as directory:
    os.environ['CARD_CONDITION_EXPERIMENT_DIR']=directory
    try:
        m.fit_detail_head(zero,mask,labels,points,mass,normal_reduction='max_bound')
    except ValueError as error:assert 'does not reproduce' in str(error)
    else:raise AssertionError('Must reject inconsistent decomposition')
    finally:m.loss_and_grad=original_eval
    assert not Path(directory,'component-gradients-fold2.json').exists()
print('PASS: inconsistent component sum rejected before evidence write')
# Static isolation: untouched runtime ingredients and evaluation/output contract.
for name in ['armijo_direction.py','metrics.py']:assert (FOLDER/name).read_bytes()==(BASE/name).read_bytes()
old_worker=(BASE/'worker.py').read_text();worker=(FOLDER/'worker.py').read_text()
assert worker[worker.index("    scores['original']"):]==old_worker[old_worker.index("    scores['original']"):]
assert "normal_reduction='max_bound'" in worker and 'penalty=1.' in worker
assert ".open('x')" in worker and "component-gradient-rows-fold" in worker
# Execute only the worker's new sidecar-writing AST node with fabricated row identities.
write_nodes=[n for n in ast.walk(ast.parse(worker)) if isinstance(n,ast.With)
             and 'component-gradient-rows-fold' in ast.unparse(n.items[0].context_expr)]
assert len(write_nodes)==1
with tempfile.TemporaryDirectory() as directory:
    fake_rows=[dict(id='synthetic-'+str(i),group='synthetic-photo-'+str(i),image_sha256='0'*64,target=i) for i in range(2)]
    context=dict(out=Path(directory),f=2,train_rows=fake_rows,json=json)
    statement=compile(ast.Module(body=write_nodes,type_ignores=[]),'<synthetic-worker-row-sidecar>','exec')
    exec(statement,context)
    sidecar=Path(directory,'component-gradient-rows-fold2.json');unchanged=sidecar.read_bytes()
    assert json.loads(unchanged)==dict(fold=2,rows=fake_rows)
    try:exec(statement,context)
    except FileExistsError:pass
    else:raise AssertionError('Training provenance must not overwrite existing rows')
    assert sidecar.read_bytes()==unchanged
print('PASS: worker row-writing block executed on fabricated IDs only; order/fold/labels preserved; exclusive-create refusal')
counts={}
for path in FOLDER.glob('*.py'):
    counts[path.name]=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for n in ast.walk(ast.parse(path.read_text())))
    assert counts[path.name]<=7
assert counts['objective.py']==3 and counts['worker.py']==0
# Only initial/trial objective calls remain; component recording adds no fit-time forward call site.
fit_node=next(n for n in ast.parse((FOLDER/'objective.py').read_text()).body
              if isinstance(n,ast.FunctionDef) and n.name=='fit_detail_head')
evaluation_calls=[n for n in ast.walk(fit_node) if isinstance(n,ast.Call)
                  and isinstance(n.func,ast.Name) and n.func.id=='loss_and_grad']
assert len(evaluation_calls)==2
print('PASS: unchanged direction/metrics/evaluation block/output recipe; exclusive training-row provenance; function limits',counts)
summary=dict(kind='synthetic_only',real_training_runs=0,experiment_runs=0,photo_inference_calls=0,
    direct_objective_cases=14,finite_difference_cases=20,fit_parity_cases=fit_summaries,
    independent_component_gradient_max_error=max_gradient_error,independent_component_loss_max_error=max_loss_error,
    function_counts=counts,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FOLDER.glob('*.py')})
print('RESULT_JSON='+json.dumps(summary,allow_nan=False))
