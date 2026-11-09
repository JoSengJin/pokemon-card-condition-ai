"""1152D linear projection factored into three384D products, float64."""
import torch


class PositionLinear(torch.autograd.Function):
    max_chunk_rows=0
    max_base_elements=0

    @staticmethod
    def forward(ctx,theta,features,center):
        ctx.save_for_backward(features,center)
        logits=features.new_empty(features.shape[:2],dtype=torch.float64)
        weights=theta[:-1].view(3,384)
        offset=theta[-1]-center@theta[:-1]
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            x=chunk[...,:384].double();uv=chunk[...,384:].double()
            projection=x@weights.T
            logits[start:start+len(chunk)]=projection[...,0]+uv[...,0]*projection[...,1]+uv[...,1]*projection[...,2]+offset
            PositionLinear.max_chunk_rows=max(PositionLinear.max_chunk_rows,len(chunk))
            PositionLinear.max_base_elements=max(PositionLinear.max_base_elements,x.numel())
        return logits

    @staticmethod
    def backward(ctx,upstream):
        features,center=ctx.saved_tensors
        gradient=center.new_zeros(1153)
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            x=chunk[...,:384].double().flatten(0,1)
            uv=chunk[...,384:].double().flatten(0,1)
            g=upstream[start:start+len(chunk)].flatten()
            gradient[:384]+=x.T@g
            gradient[384:768]+=x.T@(g*uv[:,0])
            gradient[768:1152]+=x.T@(g*uv[:,1])
        total=upstream.sum()
        gradient[:-1]-=center*total;gradient[-1]=total
        return gradient,None,None
