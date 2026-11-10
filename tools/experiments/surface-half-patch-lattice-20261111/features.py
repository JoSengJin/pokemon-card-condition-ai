"""Frozen DINO features on the original and half-patch (7px) shifted lattices, concatenated into one 2048-token bag."""
import torch
from card_condition.local_wear_cnn import physical_pixel_mask
from card_condition.side_experiment import view_tensors
SHIFT=7


def shifted(array,shift):
    """Move content up-left by `shift` px; zero-fill the vacated right/bottom band (works for bool masks and images)."""
    out=torch.zeros_like(array);size=array.shape[-1]
    out[...,:size-shift,:size-shift]=array[...,shift:,shift:]
    return out


def backbone_features(body,rows,device):
    cache={}
    for i,r in enumerate(rows):
        cache.setdefault(r['image'],[]).append((i,r))
    x=torch.empty((len(rows),2048,384),dtype=torch.float32)
    masks=torch.zeros((len(rows),2048),dtype=torch.bool)
    with torch.inference_mode():
        for path,items in cache.items():
            for (i,r),tensor in zip(items,view_tensors(path,[r['box'] for _,r in items],448)):
                physical=physical_pixel_mask(path,r['box'],halo=0,image_size=448)
                for k,shift in enumerate((0,SHIFT)):
                    z=body.forward_features((shifted(tensor,shift) if shift else tensor)[None].to(device))['x_norm_patchtokens'].cpu()[0]
                    if z.shape!=(1024,384) or z.dtype!=torch.float32 or not torch.isfinite(z).all():
                        raise ValueError('Finite float32 final patch features required')
                    grid=(shifted(physical,shift) if shift else physical).reshape(32,14,32,14).any(3).any(1)
                    if shift:
                        grid[31,:]=False;grid[:,31]=False  # last row/column contain artificial zero padding
                    x[i,k*1024:(k+1)*1024]=z;masks[i,k*1024:(k+1)*1024]=grid.flatten()
    if not masks.any(1).all():raise ValueError('Every bag must contain valid physical pixels')
    return x,masks


def score_tokens(features,masks,coef,bias):
    if (features.ndim!=3 or features.shape[-1]!=384 or coef.shape!=(384,) or masks.shape!=features.shape[:2]
            or masks.dtype!=torch.bool or not masks.any(1).all() or not torch.isfinite(coef).all() or not torch.isfinite(bias).all()):
        raise ValueError('Finite384D coefficients and aligned patch/mask bags required')
    result=[]
    with torch.inference_mode():
        for start in range(0,len(features),8):
            logits=features[start:start+8]@coef+bias
            result.extend(logits.masked_fill(~masks[start:start+len(logits)],-torch.inf).amax(1).sigmoid().tolist())
    return result
