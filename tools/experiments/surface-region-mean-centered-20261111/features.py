"""Frozen same-crop patch features and same-region valid-token mean; expand only bounded chunks."""
import torch
from card_condition.local_wear_cnn import physical_pixel_mask
from card_condition.side_experiment import view_tensors


def backbone_features(body,rows,device):
    cache={}
    for i,r in enumerate(rows):
        cache.setdefault(r['image'],[]).append((i,r))
    x=torch.empty((len(rows),1024,384),dtype=torch.float32)
    cls=torch.empty((len(rows),384),dtype=torch.float32)
    masks=torch.empty((len(rows),1024),dtype=torch.bool)
    with torch.inference_mode():
        for path,items in cache.items():
            for (i,r),tensor in zip(items,view_tensors(path,[r['box'] for _,r in items],448)):
                output=body.forward_features(tensor[None].to(device))
                z=output['x_norm_patchtokens'].cpu()[0]
                if z.shape!=(1024,384) or z.dtype!=torch.float32 or not torch.isfinite(z).all():
                    raise ValueError('Finite float32 final patch features required')
                masks[i]=physical_pixel_mask(path,r['box'],halo=0,image_size=448).reshape(32,14,32,14).any(3).any(1).flatten()
                x[i]=z;cls[i]=z[masks[i]].double().mean(0).float() if masks[i].any() else 0
    if not masks.any(1).all():raise ValueError('Every bag must contain valid physical pixels')
    return x,masks,cls


def expand_tokens(x,cls,valid):
    expected=(x.shape[0],384) if x.ndim==3 else (384,)
    if (x.ndim not in (1,2,3) or x.shape[-1]!=384 or x.dtype!=torch.float32
            or cls.shape!=expected or cls.dtype!=torch.float32 or valid.shape!=x.shape[:-1]
            or valid.dtype!=torch.bool or not torch.isfinite(x).all() or not torch.isfinite(cls).all()):
        raise ValueError('Finite float32 patch384, matching same-region mean and boolean mask required')
    context=cls[:,None,:] if x.ndim==3 else cls
    return torch.cat((x,(x-context).masked_fill(~valid[...,None],0)),dim=-1)


def score_cls(features,masks,cls,coef,bias):
    if (features.ndim!=3 or features.shape[-1]!=384 or cls.shape!=(len(features),384)
            or coef.shape!=(768,) or masks.shape!=features.shape[:2] or masks.dtype!=torch.bool
            or not masks.any(1).all() or not torch.isfinite(coef).all() or not torch.isfinite(bias).all()):
        raise ValueError('Finite768D coefficients and aligned patch/CLS/mask bags required')
    result=[]
    with torch.inference_mode():
        for start in range(0,len(features),8):
            dense=expand_tokens(features[start:start+8],cls[start:start+8],masks[start:start+8])
            logits=dense@coef+bias
            result.extend(logits.masked_fill(~masks[start:start+len(dense)],-torch.inf).amax(1).sigmoid().tolist())
    return result
