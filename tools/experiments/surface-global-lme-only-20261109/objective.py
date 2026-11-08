"""Isolated fixed-budget L-BFGS direction / Armijo fit; no optimizer callbacks."""
import math
import json
import os
import hashlib
from pathlib import Path
import torch
from torch.nn import functional as F
from card_condition.point_patch_head import point_bag_loss
from armijo_direction import lbfgs_direction

def detail_bag_loss(logits, target, valid_mask, point_token=None, normal_reduction='mean_odds'):
    if type(target) is not int or target not in (0, 1):
        raise ValueError('Explicit binary human truth is required')
    if target==0 and point_token is not None:
        if type(point_token) is not int or not 0<=point_token<len(logits) or not valid_mask[point_token]:
            raise ValueError('A known inner-surface confounder point must be a valid photo token')
        # This is a non-edge training role; original surface1 truth is retained separately.
        return F.softplus(logits[point_token])
    if point_token is not None:
        return point_bag_loss(logits, target, valid_mask, point_token, normal_reduction)
    normal_loss = point_bag_loss(logits, 0, valid_mask, normal_reduction=normal_reduction)
    if target == 0:
        return normal_loss
    # Only require a response somewhere in the confirmed bag. This maximum is not a human point.
    return F.softplus(-logits[valid_mask].max())


def loss_and_grad(theta,x,valid,y,points,mass,penalty,normal_reduction):
    theta=theta.detach().requires_grad_(True)
    logits=x@theta[:-1]+theta[-1]
    # Preserve the original summation order; grouped terms are diagnostic views only.
    bags=[mass[i]*detail_bag_loss(logits[i],int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
          for i in range(len(x))]
    l2=.5*penalty*theta[:-1].square().sum()
    loss=sum(bags)+l2
    z=logits.masked_fill(~valid,-torch.inf).amax(dim=1)
    normal_logits=logits[y==0].masked_fill(~valid[y==0],-torch.inf)
    normal_z=.1*torch.logsumexp(normal_logits/.1,dim=1)
    pair_loss=F.softplus(normal_z[None,:]-z[y==1][:,None])
    arithmetic=pair_loss.mean()
    lme=torch.logsumexp(pair_loss.reshape(-1),dim=0)-math.log(pair_loss.numel())
    alpha=0.0
    loss=loss+alpha*arithmetic+(1-alpha)*lme
    if not torch.isfinite(loss):raise ValueError('Non-finite Armijo objective')
    loss.backward(retain_graph=True)
    gradient=theta.grad.detach().clone()
    if not torch.isfinite(gradient).all():raise ValueError('Non-finite Armijo gradient')
    active=logits.detach().masked_fill(~valid,-torch.inf).argmax(dim=1)
    components=dict(normal_bag=sum(bags[i] for i in range(len(y)) if y[i]==0),
        defect_bag=sum(bags[i] for i in range(len(y)) if y[i]==1),
        arithmetic_rank=alpha*arithmetic,global_pair_lme=(1-alpha)*lme,l2=l2)
    return float(loss.detach()),gradient,active,(theta,components)

def fit_detail_head(features, masks, targets, point_tokens, weights, penalty=1.0, normal_reduction='mean_odds'):
    if normal_reduction not in ('mean_odds','max_bound'):
        raise ValueError('Unknown normal bag objective')
    if type(penalty) not in (int,float) or not math.isfinite(penalty) or penalty<=0:
        raise ValueError('Positive finite regularization is required')
    x=torch.as_tensor(features).detach().to(device='cpu',dtype=torch.float64)
    valid=torch.as_tensor(masks,device='cpu');y=torch.as_tensor(targets,device='cpu')
    points=torch.as_tensor(point_tokens,device='cpu');mass=torch.as_tensor(weights,device='cpu',dtype=torch.float64)
    if (x.ndim!=3 or not x.shape[2] or valid.shape!=x.shape[:2] or valid.dtype!=torch.bool
            or y.shape!=(len(x),) or y.dtype==torch.bool or points.shape!=y.shape or points.dtype!=torch.long
            or mass.shape!=y.shape or not torch.isfinite(x).all() or not valid.any(1).all()
            or not torch.isfinite(mass).all() or (mass<0).any() or not ((y==0)|(y==1)).all()):
        raise ValueError('Finite labelled patch bags, integer points and valid masses are required')
    keep=mass>0;x,valid,y,points,mass=x[keep],valid[keep],y[keep],points[keep],mass[keep]
    if len(y.unique())!=2 or not torch.isfinite(mass.sum()):
        raise ValueError('Both confirmed human classes are required before fitting')
    mass=mass/mass.sum()
    for i in range(len(x)):
        detail_bag_loss(torch.zeros(x.shape[1]),int(y[i]),valid[i],None if points[i]<0 else int(points[i]),normal_reduction)
    # Numerical centering of bags is not a point target for weak presence labels.
    summaries=torch.stack([x[i,points[i]] if y[i]==1 and points[i]>=0 else x[i,valid[i]].mean(0)
                           for i in range(len(x))])
    center=(summaries*mass[:,None]).sum(0)
    x=x-center;coef=torch.zeros(x.shape[2],dtype=x.dtype,requires_grad=True)
    bias=torch.zeros((),dtype=x.dtype,requires_grad=True)
    theta=torch.cat((coef.detach(),bias.detach()[None]))
    loss,gradient,active,audit=loss_and_grad(theta,x,valid,y,points,mass,penalty,normal_reduction)
    evaluations=1;state={};reason='max_iterations';iteration=0;duplicates=0
    out=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    fold=int(os.environ['SURFACE_RANK_FOLD'])
    with (out/('armijo-fold'+str(fold)+'.jsonl')).open('w') as trace:
        for iteration in range(1,1001):
            if gradient.abs().max()<=1e-7:
                reason='gradient_target';break
            d=lbfgs_direction(gradient,state)
            trace.write(json.dumps(dict(event='curvature',iteration=iteration,evaluations=evaluations,
                **state['curvature']))+'\n');trace.flush()
            gtd=float(gradient.dot(d))
            if not math.isfinite(gtd) or gtd>=0:
                reason='non_descent_direction';break
            step=min(1.,1./float(gradient.abs().sum())) if iteration==1 else 1.
            previous_trial=None;accepted=False;prev_loss=loss
            trace.write(json.dumps(dict(event='start',iteration=iteration,evaluations=evaluations,
                loss=loss,gradient_max=float(gradient.abs().max()),directional_derivative=gtd))+'\n');trace.flush()
            while evaluations<1250:
                candidate=theta+step*d
                if torch.equal(candidate,theta) or (previous_trial is not None and torch.equal(candidate,previous_trial)):
                    reason='identical_parameter_trial';duplicates+=1;break
                previous_trial=candidate.clone()
                trial_loss,trial_gradient,trial_active,trial_audit=loss_and_grad(candidate,x,valid,y,points,mass,penalty,normal_reduction)
                evaluations+=1
                bound=loss+1e-4*step*gtd
                # A rounded Armijo bound must not silently accept a non-decreasing trial.
                accepted=trial_loss<=bound and trial_loss<loss
                trace.write(json.dumps(dict(event='trial',iteration=iteration,evaluations=evaluations,
                    step=step,step_hex=step.hex(),parameter_sha256=hashlib.sha256(candidate.numpy().tobytes()).hexdigest(),
                    parameter_step_max=float((candidate-theta).abs().max()),loss=trial_loss,loss_hex=trial_loss.hex(),
                    loss_change=trial_loss-loss,loss_ulp=math.ulp(loss),
                    loss_decrease_ulps=(loss-trial_loss)/math.ulp(loss),
                    armijo_required_decrease=-1e-4*step*gtd,armijo_bound_rounded_to_loss=bound==loss,
                    armijo_bound=bound,armijo_passed=accepted,
                    directional_derivative=float(trial_gradient.dot(d)),gradient_max=float(trial_gradient.abs().max()),
                    active_patch_change_indices=(trial_active!=active).nonzero().flatten().tolist(),
                    active_patch_changes=int((trial_active!=active).sum())))+'\n');trace.flush()
                if accepted:
                    state['t']=step
                    theta,loss,gradient,active,audit=candidate,trial_loss,trial_gradient,trial_active,trial_audit
                    break
                step*=.5
            if not accepted:
                if evaluations>=1250:reason='evaluation_budget'
                break
        max_gradient=float(gradient.abs().max())
        diagnostics=dict(reason=reason,fold=fold,n_iter=iteration,total_evaluations=evaluations,
            max_iter=1000,max_eval=1250,max_gradient=max_gradient,gradient_limit=1e-5,
            loss=loss,prev_loss=prev_loss if 'prev_loss' in locals() else None,
            duplicate_trials_blocked=duplicates,converged=max_gradient<=1e-5,
            parameter_sha256=hashlib.sha256(theta.numpy().tobytes()).hexdigest())
        (out/('fit-diagnostics-fold'+str(fold)+'.json')).write_text(json.dumps(diagnostics,indent=2,allow_nan=False))
    if max_gradient>1e-5:
        # Diagnostic state only: not an adopted model or permission to resume training.
        torch.save(dict(theta=theta,center=center,gradient=gradient,active=active,lbfgs_state=state,
            iteration=iteration,evaluations=evaluations,reason=reason),out/('failure-state-fold'+str(fold)+'.pt'))
        raise ValueError('Armijo detail head did not converge')
    # Only the last accepted (or initially converged) graph is audited; no new forward/evaluation.
    audit_theta,terms=audit
    if not torch.equal(audit_theta.detach(),theta):
        raise ValueError('Component audit is not the final accepted parameter state')
    components={};gradient_sum=torch.zeros_like(gradient)
    for name,value in terms.items():
        part=torch.autograd.grad(value,audit_theta,retain_graph=True)[0].detach()
        if not torch.isfinite(part).all():raise ValueError('Non-finite component gradient')
        gradient_sum+=part
        components[name]=dict(loss=float(value.detach()),gradient=part.tolist(),
            l2_norm=float(part.norm()),linf_norm=float(part.abs().max()),bias_gradient=float(part[-1]))
    error=float((gradient_sum-gradient).abs().max())
    loss_error=abs(sum(component['loss'] for component in components.values())-loss)
    if error>1e-10 or loss_error>1e-10:
        raise ValueError('Component audit does not reproduce final total loss/gradient')
    component_record=dict(schema_version=1,kind='actual_final_training_objective_components',
        fold=fold,parameter_sha256=diagnostics['parameter_sha256'],reason=reason,
        total_evaluations=evaluations,extra_objective_evaluations=0,extra_optimizer_steps=0,
        normal_reduction=normal_reduction,penalty=penalty,
        training=dict(bags=len(y),normal_bags=int((y==0).sum()),defect_bags=int((y==1).sum()),
            normalized_mass_sum=float(mass.sum()),
            target_sha256=hashlib.sha256(y.numpy().tobytes()).hexdigest(),
            mass_sha256=hashlib.sha256(mass.numpy().tobytes()).hexdigest(),
            mask_sha256=hashlib.sha256(valid.numpy().tobytes()).hexdigest()),
        components=components,total=dict(loss=loss,gradient=gradient.tolist(),linf_norm=max_gradient),
        gradient_sum_max_error=error,loss_sum_abs_error=loss_error)
    with (out/('component-gradients-fold'+str(fold)+'.json')).open('x') as stream:
        json.dump(component_record,stream,indent=2,allow_nan=False)
    weight=theta[:-1].float();intercept=(theta[-1]-center@theta[:-1]).float()
    return weight,intercept,dict(converged=True,train_objective=loss,max_gradient=max_gradient,
        point_positive_bags=int(((y==1)&(points>=0)).sum()),presence_positive_bags=int(((y==1)&(points<0)).sum()))
