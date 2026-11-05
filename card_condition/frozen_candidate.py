"""Pin one candidate's models, source bytes, device and dependency versions before test use."""
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import sys

from .evaluation_output import write_new_report
from .frozen_test import read_seal, SHA
from .release import file_sha256

SOURCE_ROOT = Path(__file__).resolve().parent
OPERATIONS = ('region_final', 'side_final', 'observation_final')
PACKAGES = ('torch', 'torchvision', 'Pillow')


def pin_candidate(seal_path, seal_sha256, manifest, checkpoints, output, device):
    """Pin checkpoint bytes and current execution code; no checkpoint loading or model selection."""
    if (not isinstance(checkpoints, dict) or not checkpoints or set(checkpoints) - set(OPERATIONS)
            or device not in ('cpu', 'mps')):
        raise ValueError('Explicit final evaluation roles and a fixed cpu/mps device are required')
    read_seal(seal_path, seal_sha256, manifest)
    models = {op: dict(file=str(Path(path).resolve()), sha256=file_sha256(path)) for op, path in checkpoints.items()}
    code = {p.name: file_sha256(p) for p in sorted(SOURCE_ROOT.glob('*.py'))}
    report = dict(schema_version=1, kind='frozen_test_candidate', seal_sha256=seal_sha256, models=models,
                  code_sha256=code, runtime=dict(python=sys.version, packages={p: version(p) for p in PACKAGES}),
                  device=device, threshold=.5, d2_verified=False,
                  limitations=['Device selection is pinned; actual hardware identity and deterministic kernels are not attested.',
                               'This freezes bytes, not model quality, human grouping, data provenance or pre-selection history.'])
    # Recheck the model/source snapshots rather than accepting a mixed candidate if files changed while pinning.
    if (any(file_sha256(entry['file']) != entry['sha256'] for entry in models.values())
            or any(file_sha256(SOURCE_ROOT / name) != sha for name, sha in code.items())):
        raise ValueError('Candidate inputs changed while pinning')
    write_new_report(output, report)
    return report


def read_candidate(path, expected_sha256, seal_sha256, checkpoint, operation, device):
    """Return every pinned input for final race checks; an unplanned role is never inferred."""
    path = Path(path).resolve()
    if type(expected_sha256) is not str or not SHA.fullmatch(expected_sha256):
        raise ValueError('Expected candidate SHA256 is required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Candidate SHA256 mismatch')
    candidate = json.loads(raw)
    if (not isinstance(candidate, dict) or candidate.get('schema_version') != 1
            or candidate.get('kind') != 'frozen_test_candidate' or candidate.get('seal_sha256') != seal_sha256
            or candidate.get('threshold') != .5 or candidate.get('device') != device
            or device not in ('cpu', 'mps') or not isinstance(candidate.get('models'), dict)
            or not candidate['models'] or set(candidate['models']) - set(OPERATIONS)
            or operation not in candidate['models'] or not isinstance(candidate.get('code_sha256'), dict)):
        raise ValueError('Candidate does not match this seal, role, device or fixed threshold')
    runtime = dict(python=sys.version, packages={p: version(p) for p in PACKAGES})
    if candidate.get('runtime') != runtime:
        raise ValueError('Candidate runtime changed')
    if set(candidate['code_sha256']) != {p.name for p in SOURCE_ROOT.glob('*.py')}:
        raise ValueError('Candidate source file set changed')
    hashes = {str(path): expected_sha256}
    for name, expected in candidate['code_sha256'].items():
        if type(expected) is not str or not SHA.fullmatch(expected) or file_sha256(SOURCE_ROOT / name) != expected:
            raise ValueError('Candidate source changed')
        hashes[str((SOURCE_ROOT / name).resolve())] = expected
    for op, entry in candidate['models'].items():
        if (not isinstance(entry, dict) or set(entry) != {'file', 'sha256'}
                or type(entry['file']) is not str or not Path(entry['file']).is_absolute()
                or type(entry['sha256']) is not str or not SHA.fullmatch(entry['sha256'])
                or file_sha256(entry['file']) != entry['sha256']):
            raise ValueError('Candidate checkpoint changed or invalid')
        hashes[entry['file']] = entry['sha256']
    if candidate['models'][operation]['file'] != str(Path(checkpoint).resolve()):
        raise ValueError('Checkpoint path does not match the pinned role')
    return candidate, hashes
