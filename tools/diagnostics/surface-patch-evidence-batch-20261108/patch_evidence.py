"""Reuse the original affine patch computation; add sidecar evidence only."""
import torch


def score_with_evidence(x,masks,coef,bias):
    if x.ndim!=3 or masks.shape!=x.shape[:2] or masks.dtype!=torch.bool or not masks.any(1).all():
        raise ValueError('Expected nonempty valid patch bags')
    logits=x@coef+bias
    if not torch.isfinite(logits).all():raise ValueError('Nonfinite patch logits')
    masked=logits.masked_fill(~masks,-torch.inf)
    maximum=masked.amax(1)
    scores=maximum.sigmoid().tolist()  # Exact legacy scoring expression.
    first=masked.argmax(1)
    remaining=masked.clone().scatter(1,first[:,None],-torch.inf)
    second=remaining.argmax(1);second_value=remaining.amax(1)
    count=masks.sum(1)
    upper=.1*torch.logsumexp(masked.double()/.1,1)
    details=[]
    for i in range(len(x)):
        has_second=int(count[i])>1
        details.append(dict(score=scores[i],top_index=int(first[i]),top_logit=float(maximum[i]),
            second_index=int(second[i]) if has_second else None,
            second_logit=float(second_value[i]) if has_second else None,
            second_score=float(second_value[i].sigmoid()) if has_second else None,
            margin=float(maximum[i]-second_value[i]) if has_second else None,
            valid_tokens=int(count[i]),above_half_tokens=int(((logits[i]>=0)&masks[i]).sum()),
            upper_normal_logit=float(upper[i]),upper_gap=float(upper[i]-maximum[i].double()),
            top_soft_weight=float(torch.exp((maximum[i].double()-upper[i])/.1))))
    return scores,details,logits.detach().cpu()
