"""Flip a corner zone so the card's corner apex sits at the upper left."""
import torch

# dims counted from the end, so they fit a (C,H,W) tensor and an (H,W) mask alike
FLIPS = {'upper_left': (), 'upper_right': (-1,), 'lower_left': (-2,), 'lower_right': (-2, -1)}


def canonical(tensor, mask, area):
    """Return new (tensor, mask) oriented apex-upper-left; inputs are never modified."""
    if area not in FLIPS:
        raise ValueError(f'Unknown corner area: {area!r}')
    dims = list(FLIPS[area])
    return torch.flip(tensor, dims), torch.flip(mask, dims)
