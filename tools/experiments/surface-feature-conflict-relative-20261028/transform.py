"""One label-free per-crop transform; no cross-photo or cross-fold statistics."""
import torch


def relative_tokens(x,mask):
    if x.ndim!=3 or mask.shape!=x.shape[:2] or mask.dtype!=torch.bool or not mask.any(1).all() or not torch.isfinite(x).all():
        raise ValueError('Finite token bags with valid physical masks required')
    mean=(x*mask[:,:,None]).sum(1)/mask.sum(1)[:,None]
    return torch.where(mask[:,:,None],x-mean[:,None,:],x)
