"""Optional side-evidence sidecar validator; standard library only.

It checks declared structure and file agreement. It never infers a side, human
meaning or independence, and never modifies any input.
"""
import re
from pathlib import PurePosixPath

SCHEMA = 'side_evidence_sidecar/v0.1'
SIDES = ('front', 'back')
# Each evidence type has one fixed meaning; a review slot never asserts a side.
ASSERTS_SIDE = {'human_statement': True, 'codex_anchor_eligibility': True, 'review_slot': False}
STATUSES = ('not_reviewed', 'reviewed')
BASES = ('not_reviewed', 'no_human_statement', 'human_statements_disagree', 'human_statement_without_claim',
         'human_statement_matches_claim', 'human_statement_conflicts_claim')
TRUTH_FIELDS = {'side', 'target', 'box', 'point', 'points', 'labels', 'region_labels', 'defect_points'}
ROW_KEYS = ('row_id', 'image_sha256', 'side_claim', 'review', 'evidence', 'missing_sources',
            'searched_no_side_evidence', 'summary')
EVIDENCE_KEYS = ('type', 'claim', 'value', 'asserts_side', 'source', 'origin')
REF_KEYS = ('path', 'sha256', 'row_id', 'pointer')
SHA = re.compile(r'[0-9a-f]{64}')
INDEX = re.compile(r'0|[1-9][0-9]*')


def fail(code, message):
    raise ValueError(f'{code}: {message}')


def keys(value, required, optional=(), where='value'):
    if type(value) is not dict:
        fail('F', f'{where} must be an object')
    missing, extra = set(required) - set(value), set(value) - set(required) - set(optional)
    if missing or extra:
        fail('F', f'{where} keys missing {sorted(missing)} unexpected {sorted(extra)}')


def text(value, where):
    if type(value) is not str or not value:
        fail('F', f'{where} must be a non-empty string')
    return value


def sha(value, where):
    if type(value) is not str or not SHA.fullmatch(value):
        fail('F', f'{where} must be 64 lowercase hex characters')
    return value


def relative_parts(value, where):
    """A root-relative POSIX path; absolute, parent and backslash forms are refused."""
    if type(value) is not str or not value or '\\' in value or '\x00' in value:
        fail('P', f'{where} must be a relative POSIX path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        fail('P', f'{where} must stay below the evidence root')
    return path.parts


def parse_pointer(value, where='pointer'):
    """RFC 6901 tokens; the empty pointer selects the document root."""
    if type(value) is not str:
        fail('F', f'{where} must be a string')
    if value == '':
        return []
    if not value.startswith('/'):
        fail('J', f'{where} must start with "/"')
    tokens = []
    for raw in value[1:].split('/'):
        if re.search(r'~(?![01])', raw):
            fail('J', f'{where} has an invalid "~" escape')
        tokens.append(raw.replace('~1', '/').replace('~0', '~'))
    return tokens


def resolve(document, tokens):
    """Return the selected value or raise LookupError; array index "-" is not allowed."""
    value = document
    for token in tokens:
        if type(value) is dict:
            if token not in value:
                raise LookupError(token)
            value = value[token]
        elif type(value) is list:
            if not INDEX.fullmatch(token) or int(token) >= len(value):
                raise LookupError(token)
            value = value[int(token)]
        else:
            raise LookupError(token)
    return value


def file_kind(path, where):
    suffix = PurePosixPath(path).suffix
    if suffix not in ('.json', '.jsonl'):
        fail('J', f'{where} must be a .json or .jsonl file')
    return suffix[1:]


def check_ref(ref, where):
    """Shape of a source/origin/referenced_by location; evidence must select a specific value."""
    keys(ref, REF_KEYS, where=where)
    relative_parts(ref['path'], f'{where}.path')
    sha(ref['sha256'], f'{where}.sha256')
    if file_kind(ref['path'], f'{where}.path') == 'json':
        if ref['row_id'] is not None:
            fail('J', f'{where}.row_id must be null for a .json file')
    elif type(ref['row_id']) is not str or not ref['row_id']:
        fail('J', f'{where}.row_id must name one row of a .jsonl file')
    if not parse_pointer(ref['pointer'], f'{where}.pointer'):
        fail('J', f'{where}.pointer must select a value, not the whole document')


def origin_key(ref):
    return (ref['path'], ref['sha256'], ref['row_id'], ref['pointer'])


def compute_summary(row):
    """Counts distinct declared origins; not proof of independent human judgments."""
    if row['review']['status'] == 'not_reviewed':
        return dict(human_side_origins=0, side_basis='not_reviewed')
    human = [e for e in row['evidence'] if e['type'] == 'human_statement']
    values = {e['value'] for e in human}
    if not human:
        basis = 'no_human_statement'
    elif len(values) > 1:
        basis = 'human_statements_disagree'
    elif row['side_claim'] is None:
        basis = 'human_statement_without_claim'
    else:
        basis = 'human_statement_matches_claim' if row['side_claim'] in values else 'human_statement_conflicts_claim'
    return dict(human_side_origins=len({origin_key(e['origin']) for e in human}), side_basis=basis)


def check_evidence(item, where):
    if type(item) is dict and 'claim' in item and item['claim'] != 'side':
        fail('R6', f'{where} is not side evidence')
    keys(item, EVIDENCE_KEYS, ('note',), where)
    if type(item['type']) is not str or item['type'] not in ASSERTS_SIDE:
        fail('R12', f'{where}.type is unsupported')
    if item['value'] not in SIDES:
        fail('F', f'{where}.value must be front or back')
    if type(item['asserts_side']) is not bool:
        fail('F', f'{where}.asserts_side must be a boolean')
    if item['asserts_side'] != ASSERTS_SIDE[item['type']]:
        fail('R7' if item['type'] == 'review_slot' else 'F', f'{where}.asserts_side does not match its type')
    if 'note' in item and type(item['note']) is not str:
        fail('F', f'{where}.note must be a string')
    check_ref(item['source'], f'{where}.source')
    check_ref(item['origin'], f'{where}.origin')


def check_row(row, where):
    if type(row) is dict and set(row) & TRUTH_FIELDS:
        fail('R6', f'{where} must not carry truth fields {sorted(set(row) & TRUTH_FIELDS)}')
    keys(row, ROW_KEYS, where=where)
    text(row['row_id'], f'{where}.row_id')
    sha(row['image_sha256'], f'{where}.image_sha256')
    if row['side_claim'] not in (None, *SIDES):
        fail('F', f'{where}.side_claim must be front, back or null')
    keys(row['review'], ('status',), where=f'{where}.review')
    if row['review']['status'] not in STATUSES:
        fail('R12', f'{where}.review.status is unsupported')
    for name in ('evidence', 'missing_sources'):
        if type(row[name]) is not list:
            fail('F', f'{where}.{name} must be a list')
    if type(row['searched_no_side_evidence']) is not bool:
        fail('F', f'{where}.searched_no_side_evidence must be a boolean')
    for number, item in enumerate(row['evidence']):
        check_evidence(item, f'{where}.evidence[{number}]')
    for number, item in enumerate(row['missing_sources']):
        keys(item, ('path', 'referenced_by'), where=f'{where}.missing_sources[{number}]')
        relative_parts(item['path'], f'{where}.missing_sources[{number}].path')
        check_ref(item['referenced_by'], f'{where}.missing_sources[{number}].referenced_by')
    found = row['evidence'] or row['missing_sources'] or row['searched_no_side_evidence']
    # Not yet investigated is never recorded as missing or as an empty search.
    if row['review']['status'] == 'not_reviewed' and found:
        fail('R4', f'{where} is not_reviewed but records findings')
    if row['review']['status'] == 'reviewed' and not found:
        fail('R5', f'{where} is reviewed without evidence, missing source or search result')
    if row['searched_no_side_evidence'] and any(e['asserts_side'] for e in row['evidence']):
        fail('S1', f'{where} reports no side evidence but lists side-asserting evidence')
    keys(row['summary'], ('human_side_origins', 'side_basis'), where=f'{where}.summary')
    if row['summary']['side_basis'] not in BASES:
        fail('R12', f'{where}.summary.side_basis is unsupported')
    if type(row['summary']['human_side_origins']) is not int:
        fail('F', f'{where}.summary.human_side_origins must be an integer')
    if row['summary'] != compute_summary(row):
        fail('R8', f'{where}.summary differs from the recomputed summary')


def check_structure(doc):
    """Validate a parsed sidecar without reading any referenced file."""
    keys(doc, ('schema', 'inventory', 'rows'), ('search_scope',), 'sidecar')
    if doc['schema'] != SCHEMA:
        fail('R12', 'unsupported sidecar schema')
    keys(doc['inventory'], ('path', 'sha256', 'rows_pointer'), where='inventory')
    relative_parts(doc['inventory']['path'], 'inventory.path')
    if file_kind(doc['inventory']['path'], 'inventory.path') != 'json':
        fail('J', 'inventory.path must be a .json file')
    sha(doc['inventory']['sha256'], 'inventory.sha256')
    parse_pointer(doc['inventory']['rows_pointer'], 'inventory.rows_pointer')
    scope = doc.get('search_scope')
    if scope is not None:
        keys(scope, ('path', 'sha256'), where='search_scope')
        relative_parts(scope['path'], 'search_scope.path')
        file_kind(scope['path'], 'search_scope.path')
        sha(scope['sha256'], 'search_scope.sha256')
    if type(doc['rows']) is not list or not doc['rows']:
        fail('F', 'rows must be a non-empty list')
    seen = set()
    for number, row in enumerate(doc['rows']):
        check_row(row, f'rows[{number}]')
        if row['row_id'] in seen:
            fail('R3', f'rows[{number}].row_id is duplicated')
        seen.add(row['row_id'])
    if scope is None and any(row['searched_no_side_evidence'] for row in doc['rows']):
        fail('S2', 'an empty search result requires search_scope')
    return [compute_summary(row) for row in doc['rows']]
