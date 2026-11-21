"""Build corner zone consensus status from all blind answers (pre-registered in docs/superpowers/specs/2026-11-21-corner-label-definition-design.md):
consensus = every blind answer for the zone is 결함/정상 and equals the original label; ambiguous = any other answer (판단 불가 included); unjudged = no blind answer.
Writes artifacts/corner-rejudge-20261121/consensus-status.json {zone_id: status}. Labels are never changed."""
import collections
import json
import re
from pathlib import Path

D = Path('artifacts/corner-rejudge-20261121')
ROWS = Path('artifacts/corner-same-photo-pair-cv-20261102/rows.json')


def answers(name, prefix):
    return {int(m.group(1)): m.group(2) for m in re.finditer(rf'^{prefix}(\d+)=(정상|결함|불가|미확인)\s*$', (D/name).read_text(), re.M)}


def collect():
    """zone id -> list of blind answers. Round 1 thumbnail answers are replaced by the high-res answers where they exist (design: high-res supersedes)."""
    out = collections.defaultdict(list)
    first = answers('answers.txt', 'z')
    first.update(answers('answers-hi.txt', 'z'))
    for z in json.loads((D/'selection.json').read_text()):
        out[z['id']].append(first[z['n']])
    r1, r2 = answers('repro1-answers.txt', 'r'), answers('repro2-answers.txt', 'r')
    for z in json.loads((D/'selection-repro.json').read_text()):
        out[z['id']] += [r1[z['n']], r2[z['n']]]
    c = answers('consensus-answers.txt', 'c')
    for z in json.loads((D/'selection-consensus.json').read_text()):
        out[z['id']].append(c[z['n']])
    return out


def main():
    rows = json.loads(ROWS.read_text())
    blind = collect()
    status = {}
    for r in rows:
        got = blind.get(r['id'])
        want = '결함' if r['target'] else '정상'
        status[r['id']] = 'unjudged' if not got else 'consensus' if all(a == want for a in got) else 'ambiguous'
    (D/'consensus-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=0))
    t = {r['id']: r['target'] for r in rows}
    print(len(blind), 'judged;', dict(collections.Counter((status[i], t[i]) for i in status)))


if __name__ == '__main__':
    main()
