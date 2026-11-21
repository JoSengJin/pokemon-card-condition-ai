"""Load the frozen two-arm research release from repo root; no inference on import."""
from hashlib import sha256
from pathlib import Path

import torch

from card_condition.back_triage_release import tree_sha256
from score import load_head
from trial import frozen_json


def load_release(path, expected_sha, device='mps'):
    freeze = frozen_json(path, expected_sha)
    for src, digest in freeze['file_sha256'].items():
        if sha256(Path(src).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen file changed: {src}')
    backbone = freeze['backbone']
    if tree_sha256(backbone['directory']) != backbone['tree_sha256']:
        raise ValueError('Frozen DINOv2 source differs')
    if device != 'mps' or not torch.backends.mps.is_available():
        raise ValueError('Frozen runtime requires MPS')
    from importlib.metadata import version
    import platform
    environment = dict(python=platform.python_version(), macos=platform.mac_ver()[0],
                       **{name:version(name) for name in ('torch','torchvision','Pillow')})
    if environment != freeze['environment']:
        raise ValueError('Frozen runtime versions differ')
    torch.set_num_threads(2)
    body = torch.hub.load(backbone['directory'], 'dinov2_vits14',
                          source='local', pretrained=False).eval().requires_grad_(False)
    weights = torch.load(backbone['weights'], map_location='cpu', weights_only=True)
    body.load_state_dict(weights, strict=True)
    heads = {a:load_head(m['path'], m['sha256']) for a,m in freeze['heads'].items()}
    return body.to(device), heads
