"""Fixed spatial contrast: original tokens plus masked 3x3 absolute residual."""
import torch
from torch.nn import functional as F


def augment_local_contrast(features, masks):
    if (features.ndim != 3 or features.shape[1:] != (1024, 384)
            or masks.shape != features.shape[:2] or masks.dtype != torch.bool
            or features.device != masks.device or not features.is_floating_point()
            or not torch.isfinite(features).all() or not masks.any(1).all()):
        raise ValueError('Finite 32x32x384 tokens and nonempty Boolean masks required')
    result = features.new_empty((len(features), 1024, 768))
    for start in range(0, len(features), 16):
        x = features[start:start+16]
        valid = masks[start:start+16].reshape(-1, 1, 32, 32)
        grid = x.transpose(1, 2).reshape(-1, 384, 32, 32)
        count = F.avg_pool2d(valid.to(x.dtype), 3, stride=1, padding=1, divisor_override=1)
        local_sum = F.avg_pool2d(grid * valid, 3, stride=1, padding=1, divisor_override=1)
        mean = local_sum / count.clamp_min(1)
        residual = ((grid - mean).abs() * valid).flatten(2).transpose(1, 2)
        result[start:start+len(x)] = torch.cat((x, residual), dim=2)
    return result
