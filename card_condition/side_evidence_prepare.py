"""Opt-in scaffold of an all not_reviewed v0.1 sidecar for one explicitly chosen inventory.

Only inventory id, image_sha256 and side are read. Creating a scaffold is not a review
and never adds evidence, promotes a row or copies defect truth.

Exit codes: 0 written, 1 input rejected, 2 usage error, 3 file system error.
"""
import argparse
import os
import sys

from .side_evidence import (SCHEMA, SIDES, EvidenceFiles, check_structure, fail, file_kind, parse_pointer,
                            relative_parts, resolve, sha)
from .side_evidence_cli import write_new


def scaffold_row(item, where):
    if type(item) is not dict:
        fail('F', f'{where} must be an object')
    if type(item.get('id')) is not str or not item['id']:
        fail('F', f'{where}.id must be a non-empty string')
    sha(item.get('image_sha256'), f'{where}.image_sha256')
    side = item.get('side')
    if side not in (None, *SIDES):
        fail('F', f'{where}.side must be front, back or null')
    return dict(row_id=item['id'], image_sha256=item['image_sha256'], side_claim=side,
                review=dict(status='not_reviewed'), evidence=[], missing_sources=[],
                searched_no_side_evidence=False, summary=dict(human_side_origins=0, side_basis='not_reviewed'))


def prepare_sidecar(inventory_path, evidence_root, rows_pointer, search_index=None):
    """Return a v0.1 sidecar whose rows are all not_reviewed; raise ValueError or OSError."""
    relative_parts(inventory_path, 'inventory')
    if file_kind(inventory_path, 'inventory') != 'json':
        fail('J', 'inventory must be a .json file')
    tokens = parse_pointer(rows_pointer, 'rows_pointer')
    files = EvidenceFiles(evidence_root)
    digest, parsed = files.read(inventory_path, 'R1', 'inventory')
    try:
        rows = resolve(parsed, tokens)
    except LookupError:
        fail('R1', 'rows_pointer selects nothing in the inventory')
    if type(rows) is not list or not rows:
        fail('F', 'rows_pointer must select a non-empty list')
    scaffold, seen = [], set()
    for number, item in enumerate(rows):
        row = scaffold_row(item, f'inventory rows[{number}]')
        if row['row_id'] in seen:
            fail('R2', f'inventory rows[{number}].id is duplicated')
        seen.add(row['row_id'])
        scaffold.append(row)
    doc = dict(schema=SCHEMA, inventory=dict(path=inventory_path, sha256=digest, rows_pointer=rows_pointer), rows=scaffold)
    if search_index is not None:
        # Only the index identity is recorded; nothing is searched or filled in.
        doc['search_scope'] = dict(path=search_index, sha256=files.read(search_index, 'R11', 'search_index')[0])
    check_structure(doc)
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m card_condition.side_evidence_prepare',
                                     description='Write an all not_reviewed side-evidence sidecar; inputs are never modified.')
    parser.add_argument('--inventory', required=True, help='inventory .json path relative to the evidence root')
    parser.add_argument('--evidence-root', required=True)
    parser.add_argument('--rows-pointer', required=True, help='JSON Pointer to the inventory row list')
    parser.add_argument('--search-index', help='optional index path relative to the evidence root; only its SHA is recorded')
    parser.add_argument('--output', required=True, help='new JSON path; an existing file is never replaced')
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError('output already exists; choose a new path')
        sidecar = prepare_sidecar(args.inventory, args.evidence_root, args.rows_pointer, args.search_index)
        write_new(args.output, sidecar)
    except ValueError as error:
        print(f'side-evidence-prepare: rejected: {error}', file=sys.stderr)
        return 1
    except OSError as error:
        # The message omits file names so local absolute paths are not echoed.
        print(f'side-evidence-prepare: file error: {type(error).__name__}: {error.strerror or error}', file=sys.stderr)
        return 3
    print(f'side-evidence-prepare: wrote {len(sidecar["rows"])} not_reviewed rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
