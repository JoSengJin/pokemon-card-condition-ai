"""Load only the preregistered sources, from the data checkout (cwd)."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def check(key, expected, observed):
    if expected != observed:
        if isinstance(expected, set) and isinstance(observed, set):
            expected, observed = sorted(expected - observed), sorted(observed - expected)
        raise ValueError(f"{key}: expected={expected!r}; observed={observed!r}")


def read(path, hashes):
    data = Path(path).read_bytes()
    hashes[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


def index(rows, field, candidate=False):
    result = {}
    for row in rows:
        key = row[field].split('/point-review/')[0] if candidate else row[field]
        check(f"duplicate {field} {key}", False, key in result)
        result[key] = row
    return result


def votes(folder, zones, hashes):
    pending = {z['code'] for z in zones if z['existing'] is None}
    ballots = defaultdict(list)
    for r in range(1, 4):
        seen = set()
        for b in range(1, 15):
            name = f'R{r}_b{b}.json'
            batch = read(folder / name, hashes)
            reply = read(folder / 'responses' / name, hashes)
            for payload in (batch, reply):
                check(name, (f'R{r}', b), (payload['rater'], payload['batch']))
            check(name, batch['codes'], [v['code'] for v in reply['responses']])
            for v in reply['responses']:
                code, value = v['code'], v['judgment']
                check(f'{name} duplicate {code}', False, code in seen)
                check(f'{name} {code} {value}', True, value in ('normal', 'defect', 'unknown'))
                ballots[code].append(value)
                seen.add(code)
        check(f'R{r} code differences', pending, seen)
    return ballots


def load_cards(plan, hashes):
    paths = plan['inputs']
    folder = Path(paths['a'])
    meta = read(folder / 'sample_meta.json', hashes)
    groups = set(index(meta['cards'], 'group'))
    zones = index(meta['zones'], 'id')
    index(meta['zones'], 'code')
    saved = read(paths['oof'], hashes)
    check('OOF scores length', len(saved['rows']), len(saved['scores']))
    paired = [dict(row, score=score) for row, score in zip(saved['rows'], saved['scores'])]
    oof = index(paired, 'id')
    check('OOF sample IDs', set(zones), {k for k, v in oof.items() if v['group'] in groups})
    foreground = index(read(paths['foreground'], hashes), 'id')
    candidates = index(read(paths['candidate'], hashes)['rows'], 'id', candidate=True)
    check('candidate sample IDs outside sample', set(), {k for k,v in candidates.items()
          if v['group'] in groups and k not in zones})
    ballots = votes(folder, meta['zones'], hashes)
    cards = defaultdict(list)
    for key, z in zones.items():
        row = oof[key]
        group, area = z['group'], row['area']
        check(key, f'{group}/back/surface/{area}', key)
        check(key, (group, z['target'], z['score']), (row['group'], row['target'], row['score']))
        check(key + ' score/target', True, 0 <= row['score'] <= 1 and row['target'] in (0, 1))
        check(key + ' foreground', True, key in foreground)
        fg = foreground[key]
        check(key, group, fg['group'])
        off = fg['bad'] or fg['center_out'] > 0
        check(key + ' card_off', z['card_off'], off)
        candidate = candidates.get(key)
        if candidate:
            check(candidate['id'], (group, area, row['target'], row['score']),
                  tuple(candidate[k] for k in ('group', 'area', 'target', 'score')))
            check(key + ' candidate', True, candidate['judgment'] in ('normal','unknown','defect'))
        a = z['existing']
        if a is None:
            value, count = Counter(ballots[z['code']]).most_common(1)[0]
            a = value if count >= 2 else 'split'
        check(key + ' consensus', True, a in ('normal','unknown','defect','split'))
        cards[group].append(dict(id=key, area=area, score=row['score'], human=('defect' if row['target'] else 'normal'),
                                 a=a, off=off, candidate=candidate['judgment'] if candidate else None))
    check('card IDs', groups, set(cards))
    return cards
