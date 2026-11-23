"""Patch validity rule for corner scoring: coverage by resized-photo pixels (not a card outline)."""
import torch

MIN_PIXELS = 98  # half of a 14x14 patch


def patch_valid(real_mask, min_pixels=MIN_PIXELS):
    """Return the 1024 valid-patch flags of a 448x448 non-padding mask.

    A patch is valid with at least `min_pixels` non-padding pixels; if none
    qualifies, fall back to the control rule (any non-padding pixel).
    """
    counts = real_mask.bool().reshape(32, 14, 32, 14).sum((1, 3)).flatten()
    valid = counts >= min_pixels
    return valid if bool(valid.any()) else counts > 0
