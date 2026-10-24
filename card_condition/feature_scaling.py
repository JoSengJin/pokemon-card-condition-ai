"""Fit scaling on train evidence only; fold it into the existing inference head."""
import torch


def fit_train_scaler(features, weights):
    weights=torch.as_tensor(weights,dtype=features.dtype,device=features.device)
    if features.ndim!=2 or weights.shape!=(len(features),) or not torch.isfinite(weights).all() or (weights<0).any():
        raise ValueError('Finite nonnegative train feature weights required')
    known=weights>0
    if not known.any() or not torch.isfinite(features[known]).all():
        raise ValueError('Finite explicitly labelled train features required')
    values=features[known];mass=weights[known]/weights[known].sum()
    mean=(values*mass[:,None]).sum(0)
    scale=((values-mean).square()*mass[:,None]).sum(0).sqrt().clamp_min(.001)
    return mean,scale


def fold_scaler(state, mean, scale):
    """W((x-mean)/scale)+b == (W/scale)x + b - (W/scale)mean."""
    weight=state['weight']/scale.to(state['weight'])
    return {'weight':weight,'bias':state['bias']-weight@mean.to(weight)}
