"""Chunked 384D projection over long token bags (no full double copy of the bags)."""
import torch


class TokLinear(torch.autograd.Function):
    max_chunk_rows=0
    max_base_elements=0

    @staticmethod
    def forward(ctx,theta,features,valid,center):
        ctx.save_for_backward(features,center)
        logits=features.new_empty(features.shape[:2],dtype=torch.float64)
        offset=theta[-1]-center@theta[:-1]
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            logits[start:start+len(chunk)]=chunk.double()@theta[:-1]+offset
            TokLinear.max_chunk_rows=max(TokLinear.max_chunk_rows,len(chunk))
            TokLinear.max_base_elements=max(TokLinear.max_base_elements,chunk.numel())
        return logits

    @staticmethod
    def backward(ctx,upstream):
        features,center=ctx.saved_tensors
        gradient=center.new_zeros(385)
        for start in range(0,len(features),8):
            chunk=features[start:start+8]
            gradient[:384]+=chunk.double().flatten(0,1).T@upstream[start:start+len(chunk)].flatten()
        total=upstream.sum()
        gradient[:-1]-=center*total;gradient[-1]=total
        return gradient,None,None,None
