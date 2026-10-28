"""Direction-preserving token transform with a fixed dimension-derived radius."""
import math
import torch


def direction_features(features,masks):
    if (features.ndim!=3 or features.shape[2]!=384 or not features.is_floating_point()
        or masks.dtype!=torch.bool or masks.shape!=features.shape[:2]
        or not masks.any(1).all() or not torch.isfinite(features).all()):
        raise ValueError('Finite 384-dimensional token bags and nonempty boolean masks required')
    values=features[masks];norms=torch.linalg.vector_norm(values,dim=-1,keepdim=True)
    if (norms<=0).any() or not torch.isfinite(norms).all():
        raise ValueError('Positive finite valid-token norms required')
    result=features.clone();result[masks]=values/norms*math.sqrt(384)
    return result
