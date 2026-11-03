"""Pinned release of the back triage suite: package version, request contract and every model file SHA256 are checked before any inference."""
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import torch

CONTRACT = 'back-triage-request-v1'
PARTS = ('edge', 'corner', 'surface', 'observation_limit')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_sha256(folder):
    """Digest of every .py file (relative path + bytes) under the backbone hub folder."""
    h = hashlib.sha256()
    for f in sorted(Path(folder).rglob('*.py')):
        h.update(str(f.relative_to(folder)).encode() + b'\0' + f.read_bytes())
    return h.hexdigest()


def read_release(path):
    """Verified release: manifest keys, package version, contract and the SHA256 of heads, backbone weights and backbone hub file. Files are resolved next to the manifest; nothing is searched."""
    path = Path(path)
    m = json.loads(path.read_bytes())
    if not isinstance(m, dict) or set(m) != {'release_id', 'package_version', 'input_contract', 'backbone', 'heads'} or m['input_contract'] != CONTRACT:
        raise ValueError('release_manifest_invalid')
    if m['package_version'] != version('pokemon-card-condition'):
        raise ValueError('package_version_mismatch')
    files = dict(m['heads'], backbone_weights=m['backbone']['weights'], backbone_hub=m['backbone']['hub_dir'])
    if set(m['heads']) != set(PARTS) or any(set(v) != {'file', 'sha256'} for v in files.values()):
        raise ValueError('release_manifest_invalid')
    for name, spec in files.items():
        target = path.parent/spec['file']
        digest = tree_sha256(target) if name == 'backbone_hub' and target.is_dir() else sha256(target) if target.is_file() else None
        if digest != spec['sha256']:
            raise ValueError(f'checksum_mismatch:{name}')
    return dict(m, root=path.parent, manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def load_suite(release, device='cpu'):
    from .back_triage_suite import BackTriageSuite
    root = release['root']
    hub = root/release['backbone']['hub_dir']['file']
    body = torch.hub.load(str(hub), 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(root/release['backbone']['weights']['file'], map_location='cpu', weights_only=True), strict=True)
    return BackTriageSuite({k: root/v['file'] for k, v in release['heads'].items()}, body.to(device), device)
