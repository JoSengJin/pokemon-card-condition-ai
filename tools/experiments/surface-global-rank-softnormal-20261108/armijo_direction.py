"""Relative-curvature L-BFGS direction with fixed0.01 alignment safeguard."""
import torch


def lbfgs_direction(gradient,state):
    if not state:
        d=-gradient
        state.update(old_dirs=[],old_stps=[],ro=[],H_diag=1,curvature=dict(
            s_dot_y=None,s_norm=None,y_norm=None,relative_floor=None,updated=False,H_diag='1'))
    else:
        y=gradient-state['prev_flat_grad'];s=state['d']*state['t'];ys=y.dot(s)
        s_norm=torch.linalg.vector_norm(s);y_norm=torch.linalg.vector_norm(y)
        relative_floor=y.numel()*torch.finfo(y.dtype).eps*y_norm*s_norm
        updated=bool(torch.isfinite(ys) and ys>relative_floor)
        if updated:
            if len(state['old_dirs'])==20:
                state['old_dirs'].pop(0);state['old_stps'].pop(0);state['ro'].pop(0)
            state['old_dirs'].append(y);state['old_stps'].append(s);state['ro'].append(1./ys)
            state['H_diag']=ys/y.dot(y)
        state['curvature']=dict(s_dot_y=repr(float(ys)),s_norm=repr(float(s_norm)),y_norm=repr(float(y_norm)),
            relative_floor=repr(float(relative_floor)),updated=updated,H_diag=repr(float(state['H_diag'])))
        q=-gradient;al=[None]*len(state['old_dirs'])
        for i in range(len(al)-1,-1,-1):
            al[i]=state['old_stps'][i].dot(q)*state['ro'][i]
            q.add_(state['old_dirs'][i],alpha=-al[i])
        d=q*state['H_diag']
        for i in range(len(al)):
            beta=state['old_dirs'][i].dot(d)*state['ro'][i]
            d.add_(state['old_stps'][i],alpha=al[i]-beta)
    alignment=float(-gradient.dot(d)/(gradient.norm()*d.norm()))
    reset=alignment<0.01
    pair_admitted=state['curvature']['updated']
    if reset:
        # Restart from this exact accepted point; the caller records the next accepted step.
        state['old_dirs']=[];state['old_stps']=[];state['ro']=[];state['H_diag']=1
        state.pop('t',None)
        d=-gradient
    state['curvature'].update(alignment_before=repr(alignment),
        alignment_after=repr(float(-gradient.dot(d)/(gradient.norm()*d.norm()))),
        reset=reset,pair_admitted_before_reset=pair_admitted,
        updated=pair_admitted and not reset,history_after=len(state['old_dirs']),H_diag=repr(float(state['H_diag'])))
    state['prev_flat_grad']=gradient.clone();state['d']=d
    return d
