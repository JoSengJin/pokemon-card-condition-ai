"""F1 integration check: run the installed back triage CLI (from outside the repository) on normal and failure requests against a pinned release; write a JSON report. Inference on a few real photos only."""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(python, release, request, workdir, device='cpu'):
    path = Path(workdir)/'req.json'
    path.write_text(json.dumps(request))
    done = subprocess.run([python, '-m', 'card_condition.back_triage_cli', '--release', str(release), '--request', str(path), '--device', device], capture_output=True, text=True, cwd=workdir)
    return dict(exit=done.returncode, out=json.loads(done.stdout) if done.stdout.strip() else None)


def cases(base, scratch):
    bad = Path(scratch)/'corrupt.jpg'
    bad.write_bytes(b'not a jpeg')
    return {'normal': base, 'missing_photo': dict(base, image=str(Path(scratch)/'none.jpg')), 'corrupt_file': dict(base, image=str(bad)),
            'front_side': dict(base, side='front'), 'box_unconfirmed': dict(base, box_reviewed=False), 'invalid_box': dict(base, box=[0.9, 0.9, 0.1, 0.1]),
            'contract_violation': {k: v for k, v in base.items() if k != 'box'}}


def tampered(release, scratch, kind):
    """Copy of the release with one file changed (head) or removed (backbone weights)."""
    target = Path(scratch)/f'release-{kind}'
    shutil.copytree(release, target, symlinks=False)
    if kind == 'head_tampered':
        (target/'surface-head.pt').write_bytes((target/'surface-head.pt').read_bytes() + b'x')
    else:
        (target/'dinov2_vits14_pretrain.pth').unlink()
    return target


if __name__ == '__main__':
    python, release, request_path, scratch, report = sys.argv[1:6]
    base = json.loads(Path(request_path).read_text())
    results = {name: run(python, Path(release)/'release.json', req, scratch) for name, req in cases(base, scratch).items()}
    for kind in ('head_tampered', 'backbone_missing'):
        results[kind] = run(python, tampered(release, scratch, kind)/'release.json', base, scratch)
    Path(report).write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print({k: (v['exit'], (v['out'] or {}).get('status'), (v['out'] or {}).get('reason')) for k, v in results.items()})
