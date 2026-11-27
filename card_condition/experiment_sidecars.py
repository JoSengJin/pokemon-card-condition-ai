"""Optional plan['sidecars']: freeze exclusion counts and per-row facts, and tabulate strata. Record columns only; never changes a verdict.

Contract: docs/collaboration/tasks/record-sidecars-20261127.md. Every function here calls no other project function except
freeze -> check_* (PAIR_CODING depth limit).
"""
import hashlib
import json
import re
from collections import Counter

HEX = re.compile(r'[0-9a-f]{64}')
BANDS = [.2, .4, .5, .6]
STATES = ('정상', '결함', '미확인', '판단 불가')
BOX = '상자 미확인'
MARKS = ('AI 동일', 'AI 의심', '기준 판본 불일치')
BOX_OUT = '정상·결함만 행으로 둔다. 상자 미확인 사진의 구역은 행에서 뺀다'
BOX_IN = '정상·결함만 행으로 둔다. 상자 미확인 사진의 구역도 행에 포함한다'
FACTS = {'background': ('bg_bright', 'ok', 'corner_cut', 'no_blue_border', 'unmeasured'),
         'px_per_mm_layer': ('<10', '10-15.3', '>=15.3', 'unmeasured'),
         'rater_kind': ('human', 'ai_identical', 'ai_suspect', 'unknown')}


def freeze(root, plan, rows, required):
    """{} without plan['sidecars'] (reference.json stays unchanged), else {'sidecars': checked bodies} to embed in it."""
    if 'sidecars' not in plan:
        return {}
    block = plan['sidecars']
    if (not isinstance(block, dict) or not {'exclusions', 'row_facts'} <= set(block)
            or set(block) - {'exclusions', 'row_facts', 'bands', 'preregistration'}):
        raise ValueError('sidecars needs exclusions and row_facts; only bands and preregistration are optional')
    bodies, sources = {}, {}
    for name in ('exclusions', 'row_facts'):
        entry = block[name]
        if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'} or not isinstance(entry['path'], str):
            raise ValueError('A sidecar needs exactly path and sha256: ' + name)
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Sidecar must be an existing project file: ' + name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Sidecar SHA256 does not match: ' + name)
        bodies[name], sources[name] = json.loads(data), dict(entry)
    bands = block.get('bands', BANDS)
    if (not isinstance(bands, list) or not bands or any(type(b) not in (int, float) or not 0 < b < 1 for b in bands)
            or any(a >= b for a, b in zip(bands, bands[1:]))):
        raise ValueError('bands must be increasing numbers between 0 and 1')
    check_exclusions(bodies['exclusions'], rows)
    check_facts(bodies['row_facts'], {r['id'] for group in (rows, *(c['rows'] for c in required)) for r in group})
    if 'preregistration' in block:
        check_prereg(root, block['preregistration'])
    return {'sidecars': dict(bodies, bands=bands, preregistration=block.get('preregistration'), sources=sources)}


def check_exclusions(body, rows):
    """Per cell (second-to-last id segment), the kept 정상/결함 counts must equal the primary rows' targets."""
    if not isinstance(body, dict) or body.get('kept_rule') not in (BOX_OUT, BOX_IN):
        raise ValueError('exclusions needs one of the two fixed kept_rule sentences')
    declared = {}
    for cell, zones in body.items():
        if cell == 'kept_rule':
            continue
        if not isinstance(zones, dict):
            raise ValueError('exclusions cell must map zones to counts: ' + cell)
        total = [0, 0]  # target 0, target 1
        for counts in zones.values():
            if (not isinstance(counts, dict) or set(counts) != {*STATES, BOX, *MARKS}
                    or not isinstance(counts[BOX], dict) or set(counts[BOX]) != set(STATES)
                    or any(type(v) is not int or v < 0 for v in (*(counts[k] for k in (*STATES, *MARKS)), *counts[BOX].values()))):
                raise ValueError('exclusions zone has missing, extra or non-count fields: ' + cell)
            for target, state in enumerate(('정상', '결함')):
                total[target] += counts[state] + (counts[BOX][state] if body['kept_rule'] == BOX_IN else 0)
        declared[cell] = total
    actual = {}
    for row in rows:
        parts = row['id'].split('/')
        if len(parts) < 2 or row['target'] not in (0, 1):
            raise ValueError('Rows need cell/zone ids and 0/1 targets')
        actual.setdefault(parts[-2], [0, 0])[row['target']] += 1
    if any(declared.get(cell, [0, 0]) != actual.get(cell, [0, 0]) for cell in {*declared, *actual}):
        raise ValueError('exclusions kept counts do not match the primary evaluation rows')


def check_facts(body, ids):
    """Exactly one fact record per evaluated row id, so no row silently loses its stratum or rater."""
    if not isinstance(body, dict) or set(body) - {'_measure_sha256'} != ids:
        raise ValueError('row_facts keys must equal the evaluation row ids (none missing, none extra)')
    for ident in ids:
        fact = body[ident]
        if (not isinstance(fact, dict) or set(fact) != {*FACTS, 'criteria_sha256', 'input_hold'}
                or any(fact[key] not in allowed for key, allowed in FACTS.items())
                or type(fact['input_hold']) is not bool
                or fact['criteria_sha256'] != '버전 미상' and not HEX.fullmatch(str(fact['criteria_sha256']))):
            raise ValueError('Invalid row_facts record: ' + ident)


def check_prereg(root, block):
    """The branch has to be written, with its evidence file, before the child starts."""
    if (not isinstance(block, dict) or not HEX.fullmatch(str(block.get('rules_sha256')))
            or type(block.get('branch_dependent')) is not bool
            or set(block) - {'rules_sha256', 'rules_path', 'branch_dependent', 'branch_observed', 'branch_evidence'}):
        raise ValueError('preregistration needs rules_sha256 and a boolean branch_dependent')
    files = []
    if 'rules_path' in block:
        files.append((block['rules_path'], block['rules_sha256']))
    if block['branch_dependent']:
        evidence = block.get('branch_evidence')
        if block.get('branch_observed') not in ('A', 'B', 'C') or not isinstance(evidence, dict) or set(evidence) != {'path', 'sha256'}:
            raise ValueError('A branch-dependent plan needs branch_observed A/B/C and branch_evidence')
        files.append((evidence['path'], evidence['sha256']))
    for name, expected in files:
        path = (root / str(name)).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('preregistration file is missing or its SHA256 differs')


def tally(result, frozen):
    """{} without sidecars, else strata x score band x truth counts for candidate and control. Descriptive only."""
    if not frozen:
        return {}
    edges = frozen['bands']
    names = [f'<{edges[0]:g}', *(f'{a:g}-{b:g}' for a, b in zip(edges, edges[1:])), f'>={edges[-1]:g}']
    tables = {}
    for key, scores in (('after', result['scores']), ('before', result['before_scores'])):
        counts = Counter()
        for row, score in zip(result['rows'], scores, strict=True):
            fact = frozen['row_facts'][row['id']]
            counts[fact['background'], fact['px_per_mm_layer'], fact['rater_kind'],
                   sum(score >= e for e in edges), row['target']] += 1
        tables[key] = [dict(background=g, px_per_mm_layer=p, rater_kind=r, band=names[b], target=t, n=n)
                       for (g, p, r, b, t), n in sorted(counts.items())]
    return {'strata_table': tables}
