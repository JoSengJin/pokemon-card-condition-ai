"""Small opt-in QKV update for card-edge research; merged exports use ordinary DINO weights."""
import copy
import math
import torch
from torch import nn


class LowRankQKV(nn.Module):
    def __init__(self, linear, rank=4):
        super().__init__()
        if not isinstance(linear,nn.Linear) or type(rank) is not int or not 0 < rank <= min(linear.in_features,linear.out_features):
            raise ValueError('Expected linear QKV and valid positive rank')
        self.base=copy.deepcopy(linear).requires_grad_(False)
        self.a=nn.Parameter(torch.empty(rank,linear.in_features,device=linear.weight.device,dtype=linear.weight.dtype))
        self.b=nn.Parameter(torch.zeros(linear.out_features,rank,device=linear.weight.device,dtype=linear.weight.dtype))
        nn.init.kaiming_uniform_(self.a,a=math.sqrt(5))

    def forward(self,x):
        return self.base(x)+(x@self.a.T)@self.b.T

    def merged(self):
        result=copy.deepcopy(self.base)
        with torch.no_grad():result.weight.add_(self.b@self.a)
        return result


def wear_block(block,rank=4):
    result=copy.deepcopy(block).requires_grad_(False).eval()
    result.attn.qkv=LowRankQKV(result.attn.qkv,rank)
    return result


def merge_wear_block(block):
    result=copy.deepcopy(block)
    if not isinstance(result.attn.qkv,LowRankQKV):raise ValueError('Expected a low-rank research block')
    result.attn.qkv=result.attn.qkv.merged()
    return result.requires_grad_(False).eval()


def point_token_index(image_path,box,point,image_size=224):
    """Map an existing human point through the exact crop/pad to DINO's input patch grid."""
    from PIL import Image,ImageOps
    if type(image_size) is not int or image_size not in (224,448):
        raise ValueError('Expected224 or448 input size')
    if not (box[0]<=point['x']<=box[2] and box[1]<=point['y']<=box[3]):
        raise ValueError('Human point outside the input crop')
    with Image.open(image_path) as source:w,h=ImageOps.exif_transpose(source).size
    left,top=math.floor(box[0]*w),math.floor(box[1]*h)
    cw,ch=math.ceil(box[2]*w)-left,math.ceil(box[3]*h)-top
    resized=ImageOps.contain(Image.new('L',(cw,ch)),(image_size,image_size)).size
    x=(point['x']*w-left)*resized[0]/cw+round((image_size-resized[0])/2)
    y=(point['y']*h-top)*resized[1]/ch+round((image_size-resized[1])/2)
    grid=image_size//14
    col=max(0,min(grid-1,int(x//14)));row=max(0,min(grid-1,int(y//14)))
    return row*grid+col
