"""Exact linear projection in bounded float64 chunks; no full feature clone."""
import torch


class StreamedLinear(torch.autograd.Function):
    @staticmethod
    def forward(ctx, theta, features, center):
        ctx.save_for_backward(features, center)
        logits = features.new_empty(features.shape[:2], dtype=torch.float64)
        for start in range(0, len(features), 8):
            x = features[start:start+8].double() - center
            logits[start:start+len(x)] = x @ theta[:-1] + theta[-1]
        return logits

    @staticmethod
    def backward(ctx, upstream):
        features, center = ctx.saved_tensors
        gradient = center.new_zeros(len(center)+1)
        for start in range(0, len(features), 8):
            x = features[start:start+8].double() - center
            gradient[:-1] += x.flatten(0, 1).T @ upstream[start:start+len(x)].flatten()
        gradient[-1] = upstream.sum()
        return gradient, None, None
