"""Independent experimental patch inference with explicit observation limits."""
import hashlib
import math
from pathlib import Path
import time

import torch
from torch import nn

from .model import checked_sigmoid, device_for
from .regions import REGION_LABELS, REGION_TARGET_AREAS, region_box
from .edge_views import patch_features, batched_patch_features
from .point_probe import load_probe_model
from .side_model import backbone_for


class RegionAnalyzer:
    def __init__(self, checkpoint, device='auto'):
        self.device = device_for(device)
        self.meta = torch.load(checkpoint, map_location='cpu', weights_only=True)
        supported = self.meta.get('supported') if isinstance(self.meta, dict) else None
        name = self.meta.get('backbone_name', 'mobilenet_v3_small') if isinstance(self.meta, dict) else None
        self.policy = False
        point_architectures = tuple(name + suffix for suffix in (
            '_point_grid_v1', '_point_edge_views_v1', '_point_edge_tiles_v1',
            '_point_edge_tiles_max_v1', '_point_surface_tiles_v1')) if name in ('mobilenet_v3_small', 'resnet18') else ()
        if isinstance(self.meta, dict) and self.meta.get('architecture') in point_architectures:
            self.meta, self.backbone, self.head, self.policy = load_probe_model(checkpoint, self.device)
        else:
            if (not isinstance(self.meta, dict) or name not in ('mobilenet_v3_small', 'resnet18')
                    or self.meta.get('architecture') != name + '_region_v1'
                    or self.meta.get('labels') != list(REGION_LABELS) or not isinstance(supported, list)
                    or any(type(k) is not str or k not in REGION_LABELS for k in supported)
                    or len(supported) != len(set(supported)) or not {'backbone', 'head'} <= set(self.meta)):
                raise ValueError('Unsupported region checkpoint')
            self.backbone, dimension = backbone_for(name)
            self.backbone.to(self.device).load_state_dict(self.meta['backbone'], strict=True)
            self.head = nn.Linear(dimension, len(REGION_LABELS)).to(self.device).eval()
            self.head.load_state_dict(self.meta['head'], strict=True)
        self.image_size = self.meta.get('image_size', 224)
        if type(self.image_size) is not int or self.image_size not in (224, 448):
            raise ValueError('Invalid checkpoint image_size')
        self.model_sha256 = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()

    def analyze(self, image, card_box, area, unknown_labels=(), batch_views=False):
        if type(batch_views) is not bool:
            raise ValueError('batch_views must be boolean')
        box = region_box(card_box, area)
        if (not isinstance(unknown_labels, (list, tuple))
                or any(type(k) is not str or k not in REGION_LABELS for k in unknown_labels)
                or len(unknown_labels) != len(set(unknown_labels))):
            raise ValueError('unknown_labels must list distinct region defect labels')
        started = time.perf_counter()
        row = dict(image=image, card_box=card_box, box=box, area=area)
        features_for = batched_patch_features if batch_views else patch_features
        with torch.inference_mode():
            values = checked_sigmoid(self.head(features_for(self.backbone, row, self.device, self.policy,
                self.image_size)))[0].cpu().tolist()
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite region output; use Gemini fallback')
        scores, reasons = {}, {}
        for i, key in enumerate(REGION_LABELS):
            reason = ('observation_limited' if key in unknown_labels else
                      'not_applicable' if area not in REGION_TARGET_AREAS[key] else
                      'unsupported' if key not in self.meta['supported'] else None)
            scores[key] = None if reason else values[i]
            if reason:
                reasons[key] = reason
        return {'architecture': self.meta['architecture'], 'image_size': self.image_size,
                'input_policy': 'views' if self.policy is True else self.policy or 'context',
                'batched_views': batch_views, 'area': area, 'box': box, 'probabilities': scores, 'null_reasons': reasons,
                'model_sha256': self.model_sha256, 'manifest_sha256': self.meta.get('manifest_sha256'),
                'elapsed_seconds': time.perf_counter() - started, 'device': str(self.device),
                'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
                'limitations': ['Uncalibrated patch scores; no whole-card grade or purchase decision.',
                               'Caller must supply the card box and observation limits; glare is not auto-detected.',
                               'Null does not mean clean or defective; no perspective correction.']}
