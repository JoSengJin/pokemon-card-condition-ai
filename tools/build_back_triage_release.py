"""Assemble a pinned back triage release folder: heads + backbone weights + hub code copied next to a manifest holding SHA256 values. Copies and hashes only; no model run."""
import json
import shutil
import sys
from pathlib import Path

from card_condition.back_triage_release import CONTRACT, sha256, tree_sha256

HEADS = dict(edge='artifacts/triage-edge-back-candidate-20261101/head.pt', corner='artifacts/triage-back-candidates-20261103/corner-head.pt',
             surface='artifacts/triage-back-candidates-20261103/surface-head.pt', observation_limit='artifacts/triage-back-candidates-20261103/observation_limit-head.pt')
HUB = 'artifacts/torch-cache/hub/facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8'
WEIGHTS = 'artifacts/torch-cache/hub/checkpoints/dinov2_vits14_pretrain.pth'


def build(out, release_id, package_version):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    heads = {}
    for name, src in HEADS.items():
        shutil.copy2(src, out/f'{name}-head.pt')
        heads[name] = dict(file=f'{name}-head.pt', sha256=sha256(out/f'{name}-head.pt'))
    shutil.copy2(WEIGHTS, out/'dinov2_vits14_pretrain.pth')
    if (out/'hub').exists():
        shutil.rmtree(out/'hub')
    shutil.copytree(HUB, out/'hub', ignore=shutil.ignore_patterns('__pycache__', '.git'))
    manifest = dict(release_id=release_id, package_version=package_version, input_contract=CONTRACT,
                    backbone=dict(weights=dict(file='dinov2_vits14_pretrain.pth', sha256=sha256(out/'dinov2_vits14_pretrain.pth')), hub_dir=dict(file='hub', sha256=tree_sha256(out/'hub'))), heads=heads)
    (out/'release.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(*sys.argv[1:4])['heads'], indent=1)[:200])
