"""Preserve original descriptors and append label-free local residuals."""
import torch


def preserved_features(x,mask):
    if x.ndim!=3 or mask.shape!=x.shape[:2] or mask.dtype!=torch.bool or not mask.any(1).all() or not torch.isfinite(x).all():
        raise ValueError('Finite aligned token bags and physical masks required')
    mean=(x*mask[:,:,None]).sum(1)/mask.sum(1)[:,None]
    residual=torch.where(mask[:,:,None],x-mean[:,None,:],torch.zeros_like(x))
    return torch.cat((x,residual),dim=2)
