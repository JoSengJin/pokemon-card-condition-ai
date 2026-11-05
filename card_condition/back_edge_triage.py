"""Back-edge inspection-priority suggestion (frozen candidate of section 41). Not a defect verdict: it only ranks the 8 edge zones of a human-confirmed back photo."""
import hashlib
import math
from pathlib import Path

import torch

from .local_wear_cnn import physical_pixel_mask
from .regions import REGION_TARGET_AREAS, region_box
from .side_experiment import view_tensors

EDGE_AREAS = REGION_TARGET_AREAS['edge_defect']
LABELS = dict(high='점검 우선순위 높음', mid='점검 우선순위 중간', low='점검 우선순위 낮음')
NOTICE = '점검 우선순위 제안이며 결함·정상 판정이 아닙니다. 후면 엣지 8구역에만 적용됩니다.'


def band(score, low, high):
    return 'low' if score < low else ('high' if score >= high else 'mid')


def load_head(path):
    data = Path(path).read_bytes()
    head = torch.load(Path(path), map_location='cpu', weights_only=True)
    if head['coef'].shape != (384,) or not (0 < head['band_low'] < head['band_high'] < 1):
        raise ValueError('Unexpected triage head')
    return dict(coef=head['coef'].float(), bias=head['bias'].float(), low=head['band_low'], high=head['band_high'], sha256=hashlib.sha256(data).hexdigest())


def zone_scores(body, image, box, head, device):
    boxes = [region_box(box, area) for area in EDGE_AREAS]
    scores = []
    with torch.inference_mode():
        for zone, tensor in zip(boxes, view_tensors(image, boxes, 448)):
            tokens = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
            mask = physical_pixel_mask(image, zone, halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
            logits = (tokens @ head['coef'] + head['bias']).masked_fill(~mask, -torch.inf)
            scores.append(float(logits.amax().sigmoid()))
    return scores


class BackEdgeTriage:
    def __init__(self, head_path, body, device='cpu'):
        self.head, self.body, self.device = load_head(head_path), body, device

    def analyze(self, request):
        """request: dict(id, side='back', image, box, box_reviewed=True). Returns held (no scores) or ranked edge zones."""
        base = dict(id=request.get('id'), purpose='inspection_priority', notice=NOTICE, model_sha256=self.head['sha256'], thresholds=dict(low=self.head['low'], high=self.head['high']))
        if request.get('side') != 'back' or request.get('box_reviewed') is not True:
            return dict(base, status='held', reason='back_photo_with_confirmed_box_required')
        try:
            scores = zone_scores(self.body, request['image'], request['box'], self.head, self.device)
        except (OSError, ValueError, KeyError, TypeError):
            return dict(base, status='held', reason='invalid_box_or_unreadable_image')
        if not all(math.isfinite(s) for s in scores):
            return dict(base, status='held', reason='non_finite_score')
        zones = sorted(({'area': a, 'score': s, 'band': band(s, self.head['low'], self.head['high'])} for a, s in zip(EDGE_AREAS, scores)), key=lambda z: -z['score'])
        for rank, zone in enumerate(zones, 1):
            zone.update(rank=rank, label=LABELS[zone['band']])
        return dict(base, status='ranked', zones=zones)
