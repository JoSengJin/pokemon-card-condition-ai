"""Back corner (candidate E) and surface (candidate B) inspection-priority suggestions; same head format as back_edge_triage. Not a defect verdict: it only ranks the zones of a human-confirmed back photo."""
import math

import torch

from .back_edge_triage import LABELS, band, load_head
from .local_wear_cnn import physical_pixel_mask
from .regions import REGION_TARGET_AREAS, region_box
from .side_experiment import view_tensors

KINDS = dict(corner=('corner_defect', '후면 모서리 4구역'), surface=('surface_defect', '후면 표면 9구역'))


def zone_scores(body, image, box, head, device, areas):
    boxes = [region_box(box, area) for area in areas]
    scores = []
    with torch.inference_mode():
        for zone, tensor in zip(boxes, view_tensors(image, boxes, 448)):
            tokens = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
            mask = physical_pixel_mask(image, zone, halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
            scores.append(float((tokens @ head['coef'] + head['bias']).masked_fill(~mask, -torch.inf).amax().sigmoid()))
    return scores


class BackZoneTriage:
    def __init__(self, kind, head_path, body, device='cpu'):
        self.kind, self.areas = kind, REGION_TARGET_AREAS[KINDS[kind][0]]
        self.head, self.body, self.device = load_head(head_path), body, device

    def analyze(self, request):
        """request: dict(id, side='back', image, box, box_reviewed=True). Returns held (no scores) or ranked zones."""
        notice = f'점검 우선순위 제안이며 결함·정상 판정이 아닙니다. {KINDS[self.kind][1]}에만 적용됩니다.'
        base = dict(id=request.get('id'), kind=self.kind, purpose='inspection_priority', notice=notice, model_sha256=self.head['sha256'],
                    thresholds=dict(low=self.head['low'], high=self.head['high']))
        if request.get('side') != 'back' or request.get('box_reviewed') is not True:
            return dict(base, status='held', reason='back_photo_with_confirmed_box_required')
        try:
            scores = zone_scores(self.body, request['image'], request['box'], self.head, self.device, self.areas)
        except (OSError, ValueError, KeyError, TypeError):
            return dict(base, status='held', reason='invalid_box_or_unreadable_image')
        if not all(math.isfinite(s) for s in scores):
            return dict(base, status='held', reason='non_finite_score')
        zones = sorted(({'area': a, 'score': s, 'band': band(s, self.head['low'], self.head['high'])} for a, s in zip(self.areas, scores)), key=lambda z: -z['score'])
        for rank, zone in enumerate(zones, 1):
            zone.update(rank=rank, label=LABELS[zone['band']])
        return dict(base, status='ranked', zones=zones)
