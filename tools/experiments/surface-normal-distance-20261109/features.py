"""Fold-local normal moments and a single diagonal standardized radius."""
import torch


def fit_normal_distribution(features, masks, targets, weights):
    if (features.ndim != 3 or features.shape[2] != 384 or not features.is_floating_point()
            or features.device.type != 'cpu' or masks.shape != features.shape[:2]
            or masks.dtype != torch.bool or not masks.any(1).all()
            or targets.shape != (len(features),) or targets.dtype != torch.long
            or weights.shape != targets.shape or not torch.isfinite(features).all()
            or not torch.isfinite(weights).all() or (weights <= 0).any()
            or not ((targets == 0) | (targets == 1)).all() or not (targets == 0).any()):
        raise ValueError('Explicit training labels, finite384D bags, masks and positive masses required')
    normal = (targets == 0).nonzero().flatten()
    mass = weights[normal].double();mass = mass / mass.sum()
    mean = torch.zeros(384, dtype=torch.float64)
    second = torch.zeros_like(mean)
    for i, weight in zip(normal, mass):
        valid = features[i, masks[i]].double()
        mean += weight * valid.mean(0)
        second += weight * valid.square().mean(0)
    variance = (second - mean.square()).clamp_min(1e-6)
    if not torch.isfinite(mean).all() or not torch.isfinite(variance).all():
        raise ValueError('Non-finite normal distribution')
    return mean, variance


def append_normal_distance(features, masks, mean, variance):
    if (features.ndim != 3 or features.shape[2] != 384 or not features.is_floating_point()
            or features.device.type != 'cpu' or masks.shape != features.shape[:2]
            or masks.dtype != torch.bool or not masks.any(1).all()
            or mean.shape != (384,) or variance.shape != (384,)
            or mean.dtype != torch.float64 or variance.dtype != torch.float64
            or not torch.isfinite(features).all() or not torch.isfinite(mean).all()
            or not torch.isfinite(variance).all() or (variance < 1e-6).any()):
        raise ValueError('Finite384D bags and frozen float64 normal moments required')
    result = features.new_empty((*features.shape[:2], 385))
    result[:, :, :384] = features
    for start in range(0, len(features), 8):
        x = features[start:start+8].double()
        distance = ((x-mean).square()/variance).mean(2).sqrt()
        distance = distance.masked_fill(~masks[start:start+len(x)], 0)
        result[start:start+len(x), :, 384] = distance.to(features.dtype)
    if not torch.isfinite(result).all():
        raise ValueError('Non-finite normal distance representation')
    return result
