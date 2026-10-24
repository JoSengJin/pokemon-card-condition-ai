"""Fixed-penalty BCE fit on frozen train features; no validation selection."""
import torch
from .visibility_model import TARGET,class_group_weights

PENALTY=1.0
GRADIENT_LIMIT=1e-6


def fit_side_logistic(head,features,rows):
    if (features.ndim!=2 or len(rows)!=len(features) or head.in_features!=features.shape[1]
            or head.out_features!=2 or not torch.isfinite(features).all().item()):
        raise ValueError('Invalid side logistic training features')
    diagnostics=[]
    # Crossfit's centroid code runs in no_grad; fitting this head needs local autograd.
    with torch.enable_grad():
        for number,side in enumerate(('front','back')):
            indices=[i for i,r in enumerate(rows) if r['side']==side]
            part=[rows[i] for i in indices]
            weights=torch.tensor(class_group_weights(part),dtype=torch.float64)
            weights=weights/weights.sum()
            x=features[indices].detach().cpu().to(torch.float64)
            # Weighted train centering reparameterizes the free intercept; the objective is unchanged.
            center=(weights[:,None]*x).sum(0)
            x=x-center
            targets=torch.tensor([r['labels'][TARGET] for r in part],dtype=torch.float64)
            weight=torch.zeros(x.shape[1],dtype=torch.float64,requires_grad=True)
            bias=torch.zeros((),dtype=torch.float64,requires_grad=True)
            optimizer=torch.optim.LBFGS([weight,bias],lr=1.,max_iter=100,
                tolerance_grad=1e-8,tolerance_change=1e-12,line_search_fn='strong_wolfe')
            def closure():
                optimizer.zero_grad()
                loss=(torch.nn.functional.binary_cross_entropy_with_logits(
                    x@weight+bias,targets,reduction='none')*weights).sum()+PENALTY*weight.square().sum()
                if not torch.isfinite(loss).item():
                    raise ValueError('Non-finite side logistic objective')
                loss.backward()
                return loss
            optimizer.step(closure)
            loss=closure()
            gradient=max(weight.grad.abs().max().item(),bias.grad.abs().item())
            if not torch.isfinite(weight).all().item() or not torch.isfinite(bias).item() or not gradient<=GRADIENT_LIMIT:
                raise ValueError(f'Side logistic fit did not converge: {side}, gradient={gradient}; no comparison report')
            with torch.no_grad():
                head.weight[number].copy_(weight)
                head.bias[number].copy_(bias-weight@center)
            diagnostics.append(dict(side=side,objective=loss.item(),gradient_max=gradient,
                iterations=optimizer.state[weight]['n_iter'],fit_faces=len(part),
                fit_groups=sorted({r['group'] for r in part}),
                solver_coordinates='weighted train-centered; intercept mapped back to original features'))
    return diagnostics
