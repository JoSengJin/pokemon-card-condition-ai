"""Same two-loop direction update as installed torch.optim.lbfgs (history20)."""
import torch


def lbfgs_direction(gradient,state):
    if not state:
        d=-gradient
        state.update(old_dirs=[],old_stps=[],ro=[],H_diag=1)
    else:
        y=gradient-state['prev_flat_grad'];s=state['d']*state['t'];ys=y.dot(s)
        if ys>1e-10:
            if len(state['old_dirs'])==20:
                state['old_dirs'].pop(0);state['old_stps'].pop(0);state['ro'].pop(0)
            state['old_dirs'].append(y);state['old_stps'].append(s);state['ro'].append(1./ys)
            state['H_diag']=ys/y.dot(y)
        q=-gradient;al=[None]*len(state['old_dirs'])
        for i in range(len(al)-1,-1,-1):
            al[i]=state['old_stps'][i].dot(q)*state['ro'][i]
            q.add_(state['old_dirs'][i],alpha=-al[i])
        d=q*state['H_diag']
        for i in range(len(al)):
            beta=state['old_dirs'][i].dot(d)*state['ro'][i]
            d.add_(state['old_stps'][i],alpha=al[i]-beta)
    state['prev_flat_grad']=gradient.clone();state['d']=d
    return d
