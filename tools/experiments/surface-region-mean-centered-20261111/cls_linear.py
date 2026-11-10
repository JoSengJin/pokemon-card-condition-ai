"""768D dense-equivalent projection: raw patches and (patch - same-region mean); `cls` argument is the region mean."""
import torch


class CLSLinear(torch.autograd.Function):
    max_chunk_rows=0
    max_base_elements=0

    @staticmethod
    def forward(ctx,theta,features,cls,valid,center):
        ctx.save_for_backward(features,cls,valid,center)
        logits=features.new_empty(features.shape[:2],dtype=torch.float64)
        weights=theta[:-1].view(2,384)
        offset=theta[-1]-center@theta[:-1]
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            # Multiply in float32 before conversion, matching explicit stored-feature semantics.
            product=(chunk-cls[start:start+8,None,:]).masked_fill(~valid[start:start+8,:,None],0).double()
            logits[start:start+len(chunk)]=chunk.double()@weights[0]+product@weights[1]+offset
            CLSLinear.max_chunk_rows=max(CLSLinear.max_chunk_rows,len(chunk))
            CLSLinear.max_base_elements=max(CLSLinear.max_base_elements,chunk.numel())
        return logits

    @staticmethod
    def backward(ctx,upstream):
        features,cls,valid,center=ctx.saved_tensors
        gradient=center.new_zeros(769)
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            product=(chunk-cls[start:start+8,None,:]).masked_fill(~valid[start:start+8,:,None],0).double().flatten(0,1)
            g=upstream[start:start+len(chunk)].flatten()
            gradient[:384]+=chunk.double().flatten(0,1).T@g
            gradient[384:768]+=product.T@g
        total=upstream.sum()
        gradient[:-1]-=center*total;gradient[-1]=total
        return gradient,None,None,None,None
