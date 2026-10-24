"""Fixed-penalty train-only side ridge; crossfit research, not probability calibration."""
import torch

from .visibility_model import TARGET, class_group_weights

RIDGE_PENALTY = 1.0


def fit_side_ridge(head, features, rows):
    if (features.ndim != 2 or len(rows) != len(features) or head.in_features != features.shape[1]
            or head.out_features != 2 or not torch.isfinite(features).all().item()):
        raise ValueError('Invalid side ridge training features')
    with torch.no_grad():
        for number, side in enumerate(('front','back')):
            indices=[i for i,r in enumerate(rows) if r['side']==side]
            part=[rows[i] for i in indices]
            weights=torch.tensor(class_group_weights(part),dtype=torch.float64)
            weights=weights/weights.sum()
            x=features[indices].detach().cpu().to(torch.float64)
            design=torch.cat((x,torch.ones(len(x),1,dtype=torch.float64)),dim=1)
            targets=torch.tensor([2*r['labels'][TARGET]-1 for r in part],dtype=torch.float64)
            penalty=torch.eye(design.shape[1],dtype=torch.float64)*RIDGE_PENALTY
            penalty[-1,-1]=0  # The intercept is not regularized.
            solution=torch.linalg.solve(design.T@(weights[:,None]*design)+penalty,
                                        design.T@(weights*targets))
            if not torch.isfinite(solution).all().item():
                raise ValueError('Non-finite side ridge fit')
            head.weight[number].copy_(solution[:-1])
            head.bias[number].copy_(solution[-1])
