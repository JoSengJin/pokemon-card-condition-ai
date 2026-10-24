"""Optional small nonlinear head; default checkpoint behavior stays linear."""
from torch import nn
from .regions import REGION_LABELS


def region_head(dimension, hidden=0):
    if type(hidden) is not int or hidden not in (0,8):
        raise ValueError('Unsupported region head size')
    if not hidden:
        return nn.Linear(dimension,len(REGION_LABELS))
    return nn.Sequential(nn.Linear(dimension,8),nn.Tanh(),nn.Linear(8,len(REGION_LABELS)))
