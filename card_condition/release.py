"""Pinned release: package version, input contract and checkpoint SHA256 checked before inference."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re

PACKAGE = 'pokemon-card-condition'
INPUT_CONTRACT = 'listing-request-v1'
ROLES = ('region', 'observation', 'recall')


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_release(path):
    """Return the verified release identity and its checkpoint paths; never search for files."""
    path = Path(path)
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict)
            or set(manifest) != {'release_id', 'package_version', 'input_contract', 'checkpoints'}
            or type(manifest['release_id']) is not str or not manifest['release_id'].strip()
            or not isinstance(manifest['checkpoints'], dict) or 'region' not in manifest['checkpoints']
            or set(manifest['checkpoints']) - set(ROLES)):
        raise ValueError('Invalid release manifest')
    installed = version(PACKAGE)
    if manifest['package_version'] != installed:
        raise ValueError(f"Release package version {manifest['package_version']!r} != installed {installed!r}")
    if manifest['input_contract'] != INPUT_CONTRACT:
        raise ValueError('Unsupported release input contract')
    files, digests = {}, {}
    for role in ROLES:
        if role not in manifest['checkpoints']:
            continue
        entry = manifest['checkpoints'][role]
        if (not isinstance(entry, dict) or set(entry) != {'file', 'sha256'}
                or type(entry['file']) is not str or Path(entry['file']).is_absolute()
                or '..' in Path(entry['file']).parts
                or type(entry['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
            raise ValueError(f'Invalid release {role} checkpoint entry')
        files[role] = path.parent / entry['file']
        if file_sha256(files[role]) != entry['sha256']:
            raise ValueError(f'Release {role} checkpoint SHA256 mismatch')
        digests[role] = entry['sha256']
    release = dict(release_id=manifest['release_id'], package_version=installed,
                   input_contract=INPUT_CONTRACT, manifest_sha256=hashlib.sha256(raw).hexdigest(),
                   checkpoint_sha256=digests)
    return release, files


def check_loaded(release, loaded):
    """Reject when the weights actually loaded differ from the pinned release."""
    if {role: sha for role, sha in loaded.items() if sha is not None} != release['checkpoint_sha256']:
        raise ValueError('Loaded checkpoint differs from release; discard')
