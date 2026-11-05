"""Independent single-side inference; no automatic production bypass."""
import hashlib
import io
import math
from pathlib import Path
import time

import torch
from torch import nn
from torchvision.models import (mobilenet_v3_small, MobileNet_V3_Small_Weights,
                                resnet18, ResNet18_Weights)

from .data import LABELS
from .model import checked_sigmoid, device_for


def backbone_for(name, pretrained=False):
    if name == 'mobilenet_v3_small':
        features = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT if pretrained else None).features
        dimension = 576
    elif name == 'resnet18':
        model = resnet18(weights=ResNet18_Weights.DEFAULT if pretrained else None)
        features = nn.Sequential(*list(model.children())[:-2])
        dimension = 512
    else:
        raise ValueError('Unsupported backbone')
    return features.requires_grad_(False).eval(), dimension


class SideAnalyzer:
    def __init__(self, checkpoint, device='auto'):
        self.device = device_for(device)
        checkpoint_bytes = Path(checkpoint).read_bytes()
        self.meta = torch.load(io.BytesIO(checkpoint_bytes), map_location='cpu', weights_only=True)
        if not isinstance(self.meta, dict):
            raise ValueError('Unsupported single-side checkpoint')
        name = self.meta.get('backbone_name', 'mobilenet_v3_small')
        supported = self.meta.get('supported')
        if (name not in ('mobilenet_v3_small', 'resnet18')
                or self.meta.get('architecture') != name + '_single_side_v1'
                or self.meta.get('labels') != list(LABELS)
                or not isinstance(supported, list)
                or any(type(k) is not str or k not in LABELS for k in supported)
                or len(supported) != len(set(supported))
                or not {'backbone', 'head'} <= set(self.meta)
                or type(self.meta.get('crop')) is not bool
                or type(self.meta.get('tiles', False)) is not bool
                or self.meta['crop'] and self.meta.get('tiles', False)):
            raise ValueError('Unsupported single-side checkpoint')
        self.backbone, dimension = backbone_for(name)
        self.backbone.to(self.device).load_state_dict(self.meta['backbone'], strict=True)
        self.head = nn.Linear(dimension * (5 if self.meta.get('tiles', False) else 1), len(LABELS)).to(self.device).eval()
        self.head.load_state_dict(self.meta['head'], strict=True)
        self.model_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()

    def predict(self, image, box=None):
        from .side_experiment import side_views
        if box is None:
            if self.meta['crop'] or self.meta.get('tiles', False):
                raise ValueError('Crop/tile inference requires a human-verified card box')
            box = [0, 0, 1, 1]
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
                or not (box[0] < box[2] and box[1] < box[3])):
            raise ValueError('Card box must be normalized left/top/right/bottom coordinates')
        views = side_views(image, box, self.meta['crop'], self.meta.get('tiles', False)).to(self.device)
        with torch.inference_mode():
            values = checked_sigmoid(self.head(self.backbone(views).mean((2, 3)).flatten().unsqueeze(0)))[0].cpu().tolist()
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite model output; use Gemini fallback')
        return {k: values[i] if k in self.meta['supported'] else None for i, k in enumerate(LABELS)}

    def analyze(self, front=None, back=None, front_box=None, back_box=None):
        if front is None and back is None:
            raise ValueError('At least one image is required')
        started = time.perf_counter()
        sides = {side: self.predict(image, box) if image is not None else None
                 for side, image, box in (('front', front, front_box), ('back', back, back_box))}
        return {'sides': sides, 'missing_sides': [s for s, value in sides.items() if value is None],
                'model_sha256': self.model_sha256, 'backbone_name': self.meta.get('backbone_name', 'mobilenet_v3_small'),
                'elapsed_seconds': time.perf_counter() - started, 'device': str(self.device),
                'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
                'limitations': ['Outputs are uncalibrated model scores, not condition grades.',
                               'Glare and missing views do not establish a defect or a clean card.']}
