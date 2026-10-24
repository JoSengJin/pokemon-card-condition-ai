"""Research-only frozen-feature prototypes; never an adoption or routing policy."""
import torch
from .visibility_model import TARGET


def prototype_scores(features, training_rows, query_features, query_rows):
    """Nearest squared distance per class; query labels never enter the calculation."""
    if (features.ndim != 2 or query_features.ndim != 2
            or len(features) != len(training_rows) or len(query_features) != len(query_rows)
            or not len(features) or not len(query_features) or not features.shape[1]
            or features.shape[1] != query_features.shape[1]
            or features.device != query_features.device or features.dtype != query_features.dtype
            or not features.is_floating_point() or not query_features.is_floating_point()
            or not torch.isfinite(features).all() or not torch.isfinite(query_features).all()):
        raise ValueError('Finite matching training and query feature matrices required')
    for row in training_rows + query_rows:
        if not isinstance(row.get('group'),str) or not row['group'].strip():
            raise ValueError('Explicit physical groups required')
    if any(r.get('split') != 'train' for r in training_rows):
        raise ValueError('Prototype fitting requires training-only rows')
    if {r['group'] for r in training_rows} & {r['group'] for r in query_rows}:
        raise ValueError('Query physical groups must be excluded from prototype fitting')
    targets=[r.get('labels',{}).get(TARGET) for r in training_rows]
    if any(type(t) is not int or t not in (0,1) for t in targets) or set(targets)!={0,1}:
        raise ValueError('Both explicit prototype training classes required')
    with torch.no_grad():
        distances=[]
        for target in (0,1):
            selected=features[[i for i,t in enumerate(targets) if t==target]]
            distances.append(((query_features[:,None,:]-selected[None,:,:])**2).mean(2).min(1).values)
        logits=distances[0]-distances[1]
        if not torch.isfinite(logits).all():
            raise ValueError('Non-finite prototype distances; discard predictions')
        return torch.sigmoid(logits)
