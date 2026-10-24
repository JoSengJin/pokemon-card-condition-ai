"""Local edge-mark research CNN; no downsampling and no automatic label propagation."""
import torch
from torch import nn
from torch.nn import functional as F


class LocalWearCNN(nn.Sequential):
    def __init__(self,dilation=1,leaky=False):
        if type(dilation) is not int or dilation not in (1,2):
            raise ValueError('Expected dilation1 or2 for the local context experiment')
        if type(leaky) is not bool:raise ValueError('Expected an explicit activation choice')
        activation=nn.LeakyReLU if leaky else nn.ReLU
        super().__init__(nn.Conv2d(3,8,3,padding=1),activation(),
                         nn.Conv2d(8,8,3,padding=dilation,dilation=dilation),activation(),nn.Conv2d(8,1,1))


def sparse_wear_loss(logits,target,point_xy=None,valid_mask=None,radius=1):
    if logits.ndim!=2 or not torch.isfinite(logits).all() or type(target) is not int or target not in (0,1):
        raise ValueError('Expected a finite local map and explicit human target')
    if valid_mask is not None and (valid_mask.shape!=logits.shape or valid_mask.dtype!=torch.bool or not valid_mask.any()):
        raise ValueError('Expected a nonempty physical-pixel mask')
    if type(radius) is not int or radius<1:raise ValueError('Expected a positive integer click radius')
    if target==0:
        # A confirmed normal edge crop contains no observed target damage.
        return F.softplus((logits[valid_mask] if valid_mask is not None else logits).amax())
    if point_xy is None:raise ValueError('Positive crops require a human location')
    x,y=point_xy
    if not 0<=x<logits.shape[1] or not 0<=y<logits.shape[0]:raise ValueError('Point outside local map')
    x,y=round(x),round(y);x=min(x,logits.shape[1]-1);y=min(y,logits.shape[0]-1)
    # Click tolerance is a positive bag, never individual fabricated neighbour labels.
    local=logits[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1]
    if valid_mask is not None:
        mask=valid_mask[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1]
        if not mask.any():raise ValueError('Human point outside physical-pixel mask')
        local=local[mask]
    return F.softplus(-local.amax())


def point_input_pixel(image_path,box,point):
    import math
    from PIL import Image,ImageOps
    if not(box[0]<=point['x']<=box[2] and box[1]<=point['y']<=box[3]):raise ValueError('Point outside crop')
    with Image.open(image_path) as image:w,h=ImageOps.exif_transpose(image).size
    l,t=math.floor(box[0]*w),math.floor(box[1]*h);cw,ch=math.ceil(box[2]*w)-l,math.ceil(box[3]*h)-t
    rw,rh=ImageOps.contain(Image.new('L',(cw,ch)),(224,224)).size
    return (min(223.,(point['x']*w-l)*rw/cw+round((224-rw)/2)),
            min(223.,(point['y']*h-t)*rh/ch+round((224-rh)/2)))


def physical_pixel_mask(image_path,box,halo=2,image_size=224):
    """Exclude resize padding and the specified convolution receptive-field halo."""
    if type(halo) is not int or halo<0:raise ValueError('Expected a nonnegative integer halo')
    if type(image_size) is not int or image_size not in (224,448):
        raise ValueError('Expected224 or448 input size')
    import math
    from PIL import Image,ImageOps
    with Image.open(image_path) as im:w,h=ImageOps.exif_transpose(im).size
    cw=math.ceil(box[2]*w)-math.floor(box[0]*w);ch=math.ceil(box[3]*h)-math.floor(box[1]*h)
    rw,rh=ImageOps.contain(Image.new('L',(cw,ch)),(image_size,image_size)).size
    left,top=round((image_size-rw)/2),round((image_size-rh)/2)
    mask=torch.zeros((image_size,image_size),dtype=torch.bool)
    mask[top+halo:top+rh-halo,left+halo:left+rw-halo]=True
    return mask


def native_click_radius(image_path,box):
    """One original-photo pixel of click uncertainty, in resized input pixels."""
    import math
    from PIL import Image,ImageOps
    with Image.open(image_path) as im:w,h=ImageOps.exif_transpose(im).size
    cw=math.ceil(box[2]*w)-math.floor(box[0]*w);ch=math.ceil(box[3]*h)-math.floor(box[1]*h)
    rw,rh=ImageOps.contain(Image.new('L',(cw,ch)),(224,224)).size
    return max(1,math.ceil(max(rw/cw,rh/ch)))
