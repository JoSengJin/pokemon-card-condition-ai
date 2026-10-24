"""Train-only group-balanced feature units; no validation fitting."""
from collections import Counter
import torch


def fit_scaling(features, groups):
    if features.ndim != 2 or len(groups) != len(features) or not groups or not torch.isfinite(features).all():
        raise ValueError('Invalid training features for scaling')
    counts=Counter(groups)
    weights=features.new_tensor([1/counts[g] for g in groups])
    weights=weights/weights.sum()
    mean=(features*weights[:,None]).sum(0)
    variance=((features-mean).square()*weights[:,None]).sum(0)
    return dict(policy='train_group_standard_v1',mean=mean.detach().cpu(),
                scale=variance.sqrt().clamp_min(1e-6).detach().cpu())


def validate_scaling(scaling, dimension):
    if not isinstance(scaling,dict) or scaling.get('policy')!='train_group_standard_v1':
        raise ValueError('Unsupported observation feature scaling')
    for key in ('mean','scale'):
        value=scaling.get(key)
        if not isinstance(value,torch.Tensor) or not value.is_floating_point() or value.shape!=(dimension,) or not torch.isfinite(value).all():
            raise ValueError('Invalid observation scaling statistics')
    if (scaling['scale']<1e-6).any():
        raise ValueError('Invalid observation scaling statistics')


def apply_scaling(features, scaling):
    if scaling is None:
        return features
    validate_scaling(scaling,features.shape[-1])
    return (features-scaling['mean'].to(features))/scaling['scale'].to(features)
