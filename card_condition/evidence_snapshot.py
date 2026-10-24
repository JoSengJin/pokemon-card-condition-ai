"""Byte-integrity audit of an evidence snapshot index; payload contents are never parsed.

Passing means each listed payload is a regular file below the root whose bytes match the
recorded SHA256. It is not proof of truth, search completeness or independence.
"""
from collections import Counter
import hashlib
import os
from pathlib import PurePosixPath
import stat

from .side_evidence import fail, keys, parse_bytes, relative_parts, sha

REPORT_SCHEMA = 'evidence_snapshot_audit/v0.1'
ENTRY_KEYS = ('original_relative_path', 'snapshot_path', 'sha256', 'kind')
PAYLOAD_SUFFIXES = ('.json', '.jsonl', '.md')


def read_regular(path, where):
    """Bytes of one regular file, or None when absent; FIFOs and devices are never opened."""
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode):
        fail('P', f'{where} is not a regular file')
    with open(path, 'rb') as stream:
        return stream.read(), (info.st_dev, info.st_ino)


def check_entry(entry, where):
    keys(entry, ENTRY_KEYS, where=where)
    relative_parts(entry['original_relative_path'], f'{where}.original_relative_path')
    relative_parts(entry['snapshot_path'], f'{where}.snapshot_path')
    sha(entry['sha256'], f'{where}.sha256')
    if type(entry['kind']) is not str or not entry['kind']:
        fail('F', f'{where}.kind must be a non-empty string')
    # Unsupported payloads (photos, models, keys) are refused before any file access.
    if PurePosixPath(entry['snapshot_path']).suffix not in PAYLOAD_SUFFIXES:
        fail('U', f'{where}.snapshot_path must be a .json, .jsonl or .md payload')


def audit_snapshot(index_path, evidence_root):
    """Return an integrity report or raise ValueError (contract) / OSError (file system)."""
    info = os.stat(index_path)
    if not stat.S_ISREG(info.st_mode):
        fail('P', 'index is not a regular file')
    with open(index_path, 'rb') as stream:
        data = stream.read()
    index = parse_bytes(data, 'json', 'index')
    if type(index) is not dict:
        fail('F', 'index must be an object')
    entries = index.get('entries')
    if type(entries) is not list or not entries:
        fail('F', 'index.entries must be a non-empty list')
    declared_missing = index.get('missing', [])
    if type(declared_missing) is not list:
        fail('F', 'index.missing must be a list when present')
    root = os.path.realpath(evidence_root)
    if not os.path.isdir(root):
        raise NotADirectoryError('evidence root is not a directory')
    index_real = os.path.realpath(index_path)
    originals, snapshots, reals = set(), set(), {}
    inodes = {(info.st_dev, info.st_ino): 'the index'}
    for number, entry in enumerate(entries):
        where = f'entries[{number}]'
        check_entry(entry, where)
        # Repeats are refused, not collapsed, so one payload never counts as two sources.
        if entry['original_relative_path'] in originals:
            fail('D', f'{where}.original_relative_path is listed more than once')
        if entry['snapshot_path'] in snapshots:
            fail('D', f'{where}.snapshot_path is linked to more than one entry')
        originals.add(entry['original_relative_path'])
        snapshots.add(entry['snapshot_path'])
        real = os.path.realpath(os.path.join(root, *relative_parts(entry['snapshot_path'], where)))
        if os.path.commonpath([root, real]) != root:
            fail('P', f'{where}.snapshot_path leaves the evidence root')
        if real == index_real:
            fail('A', f'{where}.snapshot_path is the index itself')
        if real in reals:
            fail('A', f'{where}.snapshot_path aliases {reals[real]}')
        payload, inode = read_regular(real, where)
        if payload is None:
            fail('M', f'{where}.snapshot_path payload is missing')
        if inode in inodes:
            fail('A', f'{where}.snapshot_path is a hard link of {inodes[inode]}')
        reals[real] = inodes[inode] = f'entries[{number}]'
        if hashlib.sha256(payload).hexdigest() != entry['sha256']:
            fail('S', f'{where}.sha256 does not match the payload bytes')
    return dict(schema=REPORT_SCHEMA, index=dict(sha256=hashlib.sha256(data).hexdigest(), entries=len(entries)),
                entries_verified=len(entries),
                kinds=dict(sorted(Counter(e['kind'] for e in entries).items())),
                suffixes=dict(sorted(Counter(PurePosixPath(e['snapshot_path']).suffix for e in entries).items())),
                declared_missing=dict(count=len(declared_missing), resolved=False),
                ignored_metadata_keys=sorted(set(index) - {'entries', 'missing'}),
                entries=[dict(original_relative_path=e['original_relative_path'], snapshot_path=e['snapshot_path'],
                              sha256=e['sha256'], kind=e['kind']) for e in entries],
                integrity_only=True, payload_parsed=False, semantic_verification=False, independence_verified=False)
