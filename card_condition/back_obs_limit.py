"""Back observation-limit re-shoot priority score (candidate F): patch-mean DINOv2 features of the human-confirmed card box, standardized L2 logistic. Not a verdict of limited visibility."""
import hashlib
import math
from pathlib import Path

import torch

from .local_wear_cnn import physical_pixel_mask
from .side_experiment import view_tensors

NOTICE = '재촬영 권고 우선순위 점수이며 관찰 제한 판정이 아닙니다. 후면 사진에만 적용됩니다.'
PRIORITY_THRESHOLD = .5  # the fixed evaluation threshold; never tuned on results
LABELS = dict(high='재촬영 권고 우선순위 높음',
              low='재촬영 권고 우선순위 낮음 — 관찰 가능 여부는 확인되지 않았습니다(사람 확인 필요). 개발 자료에서 제한 사진의 약 41%(24/59)가 이 구간에 있었습니다.')


def load_head(path):
    data = Path(path).read_bytes()
    head = torch.load(Path(path), map_location='cpu', weights_only=True)
    if any(head[k].shape != (384,) for k in ('mean', 'std', 'coef')) or not (head['std'] > 0).all():
        raise ValueError('Unexpected observation-limit head')
    return dict(mean=head['mean'].float(), std=head['std'].float(), coef=head['coef'].float(), bias=head['bias'].float(), sha256=hashlib.sha256(data).hexdigest())


def pooled_score(body, image, box, head, device):
    with torch.inference_mode():
        tensor = next(view_tensors(image, [box], 448))
        tokens = body.forward_features(tensor[None].to(device))['x_norm_patchtokens'].cpu()[0]
        mask = physical_pixel_mask(image, box, halo=0, image_size=448).reshape(32, 14, 32, 14).any(3).any(1).flatten()
        mean = (tokens*mask[:, None]).sum(0)/mask.sum()
        return float((((mean-head['mean'])/head['std'])@head['coef']+head['bias']).sigmoid())


class BackObservationLimit:
    def __init__(self, head_path, body, device='cpu'):
        self.head, self.body, self.device = load_head(head_path), body, device

    def analyze(self, request):
        """request: dict(id, side='back', image, box, box_reviewed=True). Returns held or a re-shoot priority score in [0, 1]."""
        base = dict(id=request.get('id'), kind='observation_limit', purpose='reshoot_priority', notice=NOTICE, model_sha256=self.head['sha256'])
        if request.get('side') != 'back' or request.get('box_reviewed') is not True:
            return dict(base, status='held', reason='back_photo_with_confirmed_box_required')
        try:
            score = pooled_score(self.body, request['image'], request['box'], self.head, self.device)
        except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
            return dict(base, status='held', reason='invalid_box_or_unreadable_image')
        return prioritized(base, score) if math.isfinite(score) else dict(base, status='held', reason='non_finite_score')


def prioritized(base, score):
    """A scored photo is never cleared: a low score means lower re-shoot priority, not an observable photo."""
    priority = 'high' if score >= PRIORITY_THRESHOLD else 'low'
    return dict(base, status='scored', score=score, priority=priority, priority_threshold=PRIORITY_THRESHOLD, label=LABELS[priority],
                cleared=False, review='reshoot_suggested' if priority == 'high' else 'human_check_required')
