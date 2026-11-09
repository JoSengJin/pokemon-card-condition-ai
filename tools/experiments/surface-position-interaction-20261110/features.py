"""Fixed area interactions stored as384D tokens plus two masked coordinates."""
import torch
from card_condition.regions import GLARE_AREAS


def position_features(features,masks,rows):
    if (features.ndim!=3 or features.shape[2]!=384 or len(rows)!=len(features)
            or features.device.type!='cpu' or not features.is_floating_point()
            or masks.shape!=features.shape[:2] or masks.dtype!=torch.bool
            or not masks.any(1).all() or not torch.isfinite(features).all()
            or any(r.get('area') not in GLARE_AREAS for r in rows)):
        raise ValueError('Finite384D bags, valid masks and existing3x3 areas required')
    coordinates=[]
    for r in rows:
        row,column=divmod(GLARE_AREAS.index(r['area']),3)
        coordinates.append((column-1,row-1))
    uv=features.new_tensor(coordinates)[:,None,:]*masks[:,:,None]
    return torch.cat((features,uv),dim=2)


def expand_tokens(compact):
    if compact.shape[-1]!=386:raise ValueError('Compact384D+u+v input required')
    x=compact[...,:384]
    return torch.cat((x,x*compact[...,384:385],x*compact[...,385:386]),dim=-1)


def score_position(features,masks,coef,bias):
    if (features.ndim!=3 or features.shape[-1]!=386 or coef.shape!=(1152,)
            or masks.shape!=features.shape[:2] or masks.dtype!=torch.bool
            or not masks.any(1).all() or not torch.isfinite(coef).all()
            or not torch.isfinite(bias).all()):
        raise ValueError('Finite1152D coefficients and compact masked bags required')
    result=[]
    with torch.inference_mode():
        for start in range(0,len(features),8):
            # Keep the original float32 masked-max/sigmoid scoring formula.
            dense=expand_tokens(features[start:start+8])
            logits=dense@coef+bias
            result.extend(logits.masked_fill(~masks[start:start+len(dense)],-torch.inf).amax(1).sigmoid().tolist())
    return result
