"""Existing train-only observation fitting; public names remain re-exported by visibility_model."""
from collections import Counter
import torch
from torch import nn

TARGET = 'observation_limited'


def class_group_weights(rows):
    counts = Counter((r['labels'][TARGET], r['group']) for r in rows)
    groups = Counter(label for label, group in counts)
    if set(groups) != {0, 1}:
        raise ValueError('Both observation-limited and explicitly clear examples are required in train and val')
    return [1 / (counts[r['labels'][TARGET], r['group']] * groups[r['labels'][TARGET]]) for r in rows]


def fit_centroid(head, features, labels, weights):
    """Train-only weighted means; squared-distance difference in mean feature units."""
    with torch.no_grad():
        means = [(features[labels == value] * weights[labels == value, None]).sum(0)
                 / weights[labels == value].sum() for value in (0, 1)]
        dimension = features.shape[1]
        head.weight.copy_((2 * (means[1] - means[0]) / dimension).unsqueeze(0))
        head.bias.copy_(((means[0].square().sum() - means[1].square().sum()) / dimension).reshape(1))


def fit_side_centroids(head, features, rows):
    for number, side in enumerate(('front','back')):
        selected=[i for i,r in enumerate(rows) if r['side']==side]
        part=[rows[i] for i in selected]
        weights=features.new_tensor(class_group_weights(part))
        labels=features.new_tensor([r['labels'][TARGET] for r in part])
        local=nn.Linear(features.shape[1],1).to(features.device)
        fit_centroid(local,features[selected],labels,weights)
        with torch.no_grad():
            head.weight[number].copy_(local.weight[0])
            head.bias[number].copy_(local.bias[0])
