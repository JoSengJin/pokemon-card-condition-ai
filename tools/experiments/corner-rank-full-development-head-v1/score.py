"""Frozen back-corner score path for Candidate E and the single rank head."""
from hashlib import sha256
from pathlib import Path

import torch

from card_condition.ebay_dataset import decoded_hash
from card_condition.regions import REGION_TARGET_AREAS, region_box
from card_condition.side_experiment import view_tensors
from card_condition.local_wear_cnn import physical_pixel_mask

AREAS = REGION_TARGET_AREAS['corner_defect']
OFFSETS = ((0, 0), (7, 0), (0, 7), (7, 7))


def identity(path):
    data = Path(path).read_bytes()
    return {'raw_sha256': sha256(data).hexdigest(), 'decoded_sha256': decoded_hash(data)[0]}


def translated(tensor, mask, dx, dy):
    gray = tensor.new_tensor([(128/255 - m)/s for m, s in
                              zip((.485, .456, .406), (.229, .224, .225), strict=True)])
    shifted = gray[:, None, None].expand_as(tensor).clone()
    shifted[:, dy:, dx:] = tensor[:, :448-dy, :448-dx]
    real = torch.zeros_like(mask)
    real[dy:, dx:] = mask[:448-dy, :448-dx]
    return shifted, real


def zone_score(body, tensor, mask, head, device):
    pooled = mask.reshape(32, 14, 32, 14).any(3).any(1).flatten()
    if not pooled.any():
        raise ValueError('No valid picture pixels')
    tokens = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'][0].cpu()
    logits = (tokens @ head['coef'] + head['bias'])[pooled]
    if not torch.isfinite(logits).all():
        raise ValueError('Non-finite patch score')
    return float(logits.amax().sigmoid())


def score_card(body, request, head, device, offsets, calls=None):
    if request['side'] != 'back' or request['box_reviewed'] is not True:
        raise ValueError('back_photo_with_confirmed_box_required')
    image = request['image']
    boxes = [region_box(request['box'], area) for area in AREAS]
    scores = {}
    with torch.inference_mode():
        for area, box, tensor in zip(AREAS, boxes, view_tensors(image, boxes, 448), strict=True):
            mask = physical_pixel_mask(image, box, halo=0, image_size=448)
            phases = []
            for dx, dy in offsets:
                moved, real = translated(tensor, mask, dx, dy) if dx or dy else (tensor, mask)
                if calls is not None:
                    calls['backbone'] += 1
                phases.append(zone_score(body, moved, real, head, device))
            scores[area] = sum(phases)/len(phases)
    return scores


def load_head(path, expected_sha=None):
    data = Path(path).read_bytes()
    if expected_sha is not None and sha256(data).hexdigest() != expected_sha:
        raise ValueError('Head SHA256 mismatch')
    from io import BytesIO
    head = torch.load(BytesIO(data), map_location='cpu', weights_only=True)
    for key, shape in [('coef', (384,)), ('bias', ())]:
        value = head[key]
        if value.shape != shape or value.dtype != torch.float32 or not torch.isfinite(value).all():
            raise ValueError('Unexpected head coefficient')
    return {k: head[k] for k in ('coef', 'bias')}


def events(scores, truth):
    if set(scores) != set(AREAS) or set(truth) != set(AREAS):
        raise ValueError('Exactly four fixed corner IDs are required')
    if any(type(v) is not int or v not in (0, 1) for v in truth.values()):
        raise ValueError('Every corner needs frozen human truth')
    defects = [scores[a] for a in AREAS if truth[a]]
    return ('miss', max(defects) < .20, max(defects)) if defects else (
        'false_alarm', max(scores.values()) >= .60, max(scores.values()))
