from pathlib import Path
import sys,importlib.util,tempfile,os,json,torch,ast
folder=Path('tools/experiments/surface-global-rank-softnormal-20261108');sys.path.insert(0,str(folder.resolve()))
import objective as m
from armijo_direction import lbfgs_direction
# Direction parity, including history eviction, against actual installed PyTorch.
w=torch.linspace(-1,1,64,dtype=torch.float64).requires_grad_();diag=torch.arange(1,65,dtype=torch.float64)
o=torch.optim.LBFGS([w],max_iter=1,max_eval=1250,tolerance_grad=0,tolerance_change=0,history_size=20,line_search_fn=None)
state={}
def quadratic():
 o.zero_grad();loss=(diag*w.square()).sum()/2;loss.backward();return loss
for i in range(35):
 g=(diag*w.detach()).clone();expected=lbfgs_direction(g,state).clone()
 o.step(quadratic);actual=o.state[w]
 assert torch.allclose(expected,actual['d'],atol=1e-13,rtol=1e-13),(i,expected,actual['d'])
 state['t']=actual['t']
assert len(state['old_dirs'])==20
# Unchanged base bag/positive max, explicit normalized soft-normal pair objective parity.
torch.manual_seed(7);x=torch.randn(4,3,2,dtype=torch.float64);valid=torch.tensor([[1,1,0],[1,0,1],[1,1,1],[0,1,1]],dtype=torch.bool)
y=torch.tensor([0,1,0,1]);points=torch.full((4,),-1);mass=torch.full((4,),.25,dtype=torch.float64);theta=torch.tensor([.1,-.2,.01],dtype=torch.float64,requires_grad=True)
logits=x@theta[:-1]+theta[-1];loss=sum(mass[i]*m.detail_bag_loss(logits[i],int(y[i]),valid[i],None,'max_bound') for i in range(4))+.5*theta[:-1].square().sum();z=logits.masked_fill(~valid,-torch.inf).amax(1);nz=torch.stack([.1*(torch.logsumexp(logits[i,valid[i]]/.1,0)-torch.tensor(int(valid[i].sum()),dtype=torch.float64).log()) for i in range(4) if y[i]==0]);loss+=torch.nn.functional.softplus(nz[None,:]-z[y==1][:,None]).mean();loss.backward()
f,g,a=m.loss_and_grad(theta,x,valid,y,points,mass,1.,'max_bound');assert abs(f-float(loss.detach()))<1e-13 and torch.allclose(g,theta.grad,atol=1e-13,rtol=1e-13)
# Actual synthetic fit, direct-call Armijo logs and convergence.
with tempfile.TemporaryDirectory() as d:
 os.environ['CARD_CONDITION_EXPERIMENT_DIR']=d;os.environ['SURFACE_RANK_FOLD']='0'
 xx=torch.tensor([[[-1.],[-1.]],[[1.],[1.]]]);mask=torch.ones((2,2),dtype=torch.bool)
 coef,bias,c=m.fit_detail_head(xx,mask,torch.tensor([0,1]),torch.tensor([-1,-1]),torch.ones(2),normal_reduction='max_bound')
 logs=[json.loads(s) for s in Path(d,'armijo-fold0.jsonl').read_text().splitlines()];summary=json.loads(Path(d,'fit-diagnostics-fold0.json').read_text())
 assert c['max_gradient']<=1e-5 and summary['total_evaluations']==1+sum(a['event']=='trial' for a in logs)
 assert summary['n_iter']<=1000 and summary['total_evaluations']<=1250
 assert all('loss_decrease_ulps' in a and 'active_patch_change_indices' in a for a in logs if a['event']=='trial')
 assert all(a['loss_change']<0 and a['loss']<=a['armijo_bound'] for a in logs if a.get('armijo_passed'))
# Constant objective fixture forces no-progress duplicate guard without real model evaluation.
original=m.loss_and_grad;calls=0
def constant(theta,x,valid,y,points,mass,penalty,reduction):
 global calls
 calls+=1
 return 1.,torch.ones_like(theta),torch.zeros(len(x),dtype=torch.long)
m.loss_and_grad=constant
with tempfile.TemporaryDirectory() as d:
 os.environ['CARD_CONDITION_EXPERIMENT_DIR']=d
 try:m.fit_detail_head(xx,mask,torch.tensor([0,1]),torch.tensor([-1,-1]),torch.ones(2),normal_reduction='max_bound')
 except ValueError:pass
 else:raise AssertionError('Must fail constant objective')
 summary=json.loads(Path(d,'fit-diagnostics-fold0.json').read_text());assert summary['reason']=='identical_parameter_trial' and summary['duplicate_trials_blocked']==1 and calls==summary['total_evaluations']<=1250
m.loss_and_grad=original
for path in folder.glob('*.py'):
 count=sum(isinstance(a,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for a in ast.walk(ast.parse(path.read_text())));assert count<=7,(path,count)
print('PASS:35 L-BFGS direction parity steps/history20; exact loss/gradient; synthetic convergence; strict decrease; precise trace/count; duplicate guard; function limits')
# Budget fixture: rejection/acceptance alternation consumes1250 within1000 iterations.
calls=0;current=1000.
def budget_fixture(theta,x,valid,y,points,mass,penalty,reduction):
 global calls,current
 calls+=1
 if calls==1:value=current
 elif calls%2==0:value=current+1.
 else:current-=.01;value=current
 return value,torch.ones_like(theta),torch.zeros(len(x),dtype=torch.long)
m.loss_and_grad=budget_fixture
with tempfile.TemporaryDirectory() as d:
 os.environ['CARD_CONDITION_EXPERIMENT_DIR']=d
 try:m.fit_detail_head(xx,mask,torch.tensor([0,1]),torch.tensor([-1,-1]),torch.ones(2),normal_reduction='max_bound')
 except ValueError:pass
 else:raise AssertionError('Must stop budget fixture')
 snapshot=torch.load(Path(d,'failure-state-fold0.pt'),weights_only=True)
 assert snapshot['evaluations']==1250 and torch.isfinite(snapshot['gradient']).all() and snapshot['reason']=='evaluation_budget'
 summary=json.loads(Path(d,'fit-diagnostics-fold0.json').read_text());assert summary['reason']=='evaluation_budget' and summary['total_evaluations']==calls==1250 and summary['n_iter']<=1000
m.loss_and_grad=original
print('PASS: strict1250 evaluation budget fixture')
# Relative gate: small positive curvature, rejection cases and scale invariance.
for scale in [1e-4,1.,1e4]:
 test_state=dict(old_dirs=[],old_stps=[],ro=[],H_diag=1,prev_flat_grad=torch.zeros(2,dtype=torch.float64),d=torch.tensor([1e-8,0.],dtype=torch.float64)*scale,t=1.)
 lbfgs_direction(torch.tensor([1e-8,0.],dtype=torch.float64)*scale,test_state)
 assert test_state['curvature']['updated'] and float(test_state['curvature']['s_dot_y'])<1e-10 if scale<1e4 else test_state['curvature']['updated']
for yy,ss in [([-1e-8,0.],[1e-8,0.]),([1.,0.],[0.,0.]),([1e-20,1.],[1.,0.]),([float('inf'),0.],[1.,0.])]:
 test_state=dict(old_dirs=[],old_stps=[],ro=[],H_diag=1,prev_flat_grad=torch.zeros(2,dtype=torch.float64),d=torch.tensor(ss,dtype=torch.float64),t=1.)
 lbfgs_direction(torch.tensor(yy,dtype=torch.float64),test_state)
 assert not test_state['curvature']['updated']
print('PASS: relative small-positive/scale-invariance/negative/zero/nearly-orthogonal/nonfinite curvature cases')
# Fixed alignment gate and coherent restart state on synthetic curvature memory.
for expected_alignment in [.0099,.0101]:
 gg=torch.tensor([1.,0.],dtype=torch.float64)
 yy=torch.tensor([1.,0.],dtype=torch.float64)
 ss=torch.tensor([expected_alignment,(1-expected_alignment**2)**.5],dtype=torch.float64)
 test_state=dict(old_dirs=[yy],old_stps=[ss],ro=[1./yy.dot(ss)],H_diag=1.,prev_flat_grad=gg.clone(),d=-gg,t=.5)
 result=lbfgs_direction(gg,test_state)
 assert test_state['curvature']['reset']==(expected_alignment<.01)
 if expected_alignment<.01:
  assert torch.equal(result,-gg) and len(test_state['old_dirs'])==len(test_state['old_stps'])==len(test_state['ro'])==0 and test_state['H_diag']==1 and 't' not in test_state
  assert torch.equal(test_state['prev_flat_grad'],gg) and torch.equal(test_state['d'],-gg)
  test_state['t']=.1
  next_g=gg*.9
  lbfgs_direction(next_g,test_state)
  assert len(test_state['old_dirs'])==1 and torch.allclose(test_state['old_dirs'][0],next_g-gg) and not test_state['curvature']['reset']
 else:
  assert torch.allclose(result,-ss) and len(test_state['old_dirs'])==1
print('PASS:0.0099 reset/0.0101 preserved; memory/scale/step reset; fresh accepted-step curvature update')
# Normal-only masked normalized pooling: zeros, patch count, invalid padding and smooth switch.
for count in [1,2,3]:
 values=torch.tensor([[0.,0.,0.,1e6]],dtype=torch.float64,requires_grad=True)
 mask=torch.tensor([[i<count for i in range(4)]])
 nz=.1*(torch.logsumexp(values.masked_fill(~mask,-torch.inf)/.1,1)-mask.sum(1).double().log())
 nz.sum().backward()
 assert abs(nz.item())<1e-14 and torch.equal(values.grad[~mask],torch.zeros_like(values.grad[~mask]))
 assert torch.allclose(values.grad[mask],torch.full_like(values.grad[mask],1/count))
grads=[]
for delta in [-1e-7,1e-7]:
 values=torch.tensor([[delta,-delta,1e6]],dtype=torch.float64,requires_grad=True);mask=torch.tensor([[1,1,0]],dtype=torch.bool)
 nz=.1*(torch.logsumexp(values.masked_fill(~mask,-torch.inf)/.1,1)-mask.sum(1).double().log());nz.backward();grads.append(values.grad)
assert (grads[0]-grads[1]).abs().max()<2e-6
# Production scorer and positive detail loss were not edited; bag-positive fixture remains exact hardmax.
logits=torch.tensor([-.5,.2,9.],dtype=torch.float64);mask=torch.tensor([1,1,0],dtype=torch.bool)
assert torch.allclose(m.detail_bag_loss(logits,1,mask,None,'max_bound'),torch.nn.functional.softplus(-logits[mask].max()))
print('PASS: normalized zeros for1/2/3 patches; masked gradient0; continuous normal switch; positive hardmax preserved')
