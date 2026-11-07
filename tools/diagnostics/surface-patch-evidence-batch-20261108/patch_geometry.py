"""Invert the existing EXIF-oriented crop/448px pad/14px token geometry."""
import math
from PIL import Image,ImageOps


def token_box(image_size,box,index):
    w,h=image_size
    if not 0<=index<1024:raise ValueError('Token index outside32x32 grid')
    left,top=math.floor(box[0]*w),math.floor(box[1]*h)
    cw=math.ceil(box[2]*w)-left;ch=math.ceil(box[3]*h)-top
    rw,rh=ImageOps.contain(Image.new('L',(cw,ch)),(448,448)).size
    px,py=round((448-rw)/2),round((448-rh)/2)
    col,row=index%32,index//32
    x0,y0=max(col*14,px),max(row*14,py)
    x1,y1=min((col+1)*14,px+rw),min((row+1)*14,py+rh)
    if x1<=x0 or y1<=y0:raise ValueError('Padding-only token has no photo box')
    return dict(box=[(left+(x0-px)*cw/rw)/w,(top+(y0-py)*ch/rh)/h,
        (left+(x1-px)*cw/rw)/w,(top+(y1-py)*ch/rh)/h],
        coverage=(x1-x0)*(y1-y0)/196,grid=[row,col],crop_pixels=[left,top,cw,ch],
        resized=[rw,rh],pad=[px,py])
