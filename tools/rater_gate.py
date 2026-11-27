"""Compare pasted answers with every stored AI judgment before import; write <answer>.provenance.json. Never edits answers.

verdict (fixed before use, 07 §4-4): any full-coverage AI file equal on every zone -> ai_identical; best k/n above the
Wilson 95% upper bound of the chance agreement -> ai_suspect; otherwise no_match_found (not proof of a human), or
unknown without the exact confirmation sentence or without any full-coverage AI file.
python -m tools.rater_gate ANSWER [--ai DIR ...] [--statement FILE --expected FILE] [--out FILE]
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tools.self_agreement.import_round import confirmed
from tools.self_agreement.stats import WILSON


def values(text):
    """{zone key: value string} from 'zN=값' lines or phone lines 'id/side=..;box:..;구역:상태'. Conflicting repeats are refused."""
    out = {}
    for line in (l.strip() for l in text.splitlines()):
        numbered = re.fullmatch(r'(z\d+)\s*=\s*(.+)', line)
        if numbered:
            pairs = [numbered.groups()]
        elif ';box:' in line:
            head, _, *zones = line.split(';')
            pairs = [(f"{head.split('=')[0]}/{zone.split(':')[0]}", zone.partition(':')[2]) for zone in zones]
        else:
            continue
        for key, value in pairs:
            if out.setdefault(key, value) != value:
                raise ValueError(f'같은 구역에 다른 값이 두 번 있음: {key}')
    return out


def compare(answer, folders, answered_at):
    """Every AI file gets its own record (not only the best one). Files without a readable answer line are listed too."""
    records, unreadable = [], []
    for path in sorted(p for folder in folders for p in Path(folder).rglob('*') if p.is_file()):
        data = path.read_bytes()
        try:
            found = values(data.decode('utf-8'))
        except ValueError:  # includes UnicodeDecodeError
            found = {}
        if not found:
            unreadable.append(str(path))
            continue
        shared = answer.keys() & found.keys()
        if shared:
            modified = path.stat().st_mtime
            records.append(dict(path=str(path), matches=sum(answer[k] == found[k] for k in shared), total=len(shared),
                                full_coverage=len(shared) == len(answer), sha256=hashlib.sha256(data).hexdigest(),
                                mtime=datetime.fromtimestamp(modified, timezone.utc).isoformat(),
                                answer_modified_after=answered_at > modified))
    return records, unreadable


def chance(answer):
    """Agreement expected by chance from this answer's own value distribution (sum p^2) and its Wilson 95% upper bound."""
    n = len(answer)
    expected = sum((count / n) ** 2 for count in Counter(answer.values()).values())
    return dict(expected=expected, wilson95_upper=min(1., WILSON(expected * n, n)[1]))


def verdict(records, baseline, statement_ok):
    """A partial-coverage file is recorded but never decides: one equal zone must not read as identical."""
    full = [r for r in records if r['full_coverage']]
    if any(r['matches'] == r['total'] for r in full):
        return 'ai_identical'
    if any(r['matches'] / r['total'] > baseline['wilson95_upper'] for r in full):
        return 'ai_suspect'
    return 'no_match_found' if full and statement_ok else 'unknown'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('answer', type=Path)
    parser.add_argument('--ai', nargs='+', type=Path, help='default: ai-responses/ and ai-reference/ beside the answer folder')
    parser.add_argument('--statement', help='confirmation sentence received from the judge')
    parser.add_argument('--expected', type=Path, help='the exact sentence that was asked for')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        data = args.answer.read_bytes()
        answer = values(data.decode('utf-8'))
        if not answer:
            raise ValueError('답에서 읽을 수 있는 구역 값이 없음')
        folders = args.ai or [args.answer.resolve().parent.parent / name for name in ('ai-responses', 'ai-reference')]
        if args.ai and (missing := [str(f) for f in folders if not f.is_dir()]):
            raise ValueError(f'AI 폴더가 없음: {missing}')
        try:
            statement_ok = bool(args.expected) and bool(confirmed(args.statement, {'judge_statement': args.expected.read_text(encoding='utf-8')}))
        except ValueError:
            statement_ok = False
        answered_at = args.answer.stat().st_mtime
        records, unreadable = compare(answer, [f for f in folders if f.is_dir()], answered_at)
        baseline = chance(answer)
        result = dict(verdict=verdict(records, baseline, statement_ok), answer_sha256=hashlib.sha256(data).hexdigest(),
                      answer_mtime=datetime.fromtimestamp(answered_at, timezone.utc).isoformat(), zones=len(answer),
                      statement_confirmed=statement_ok, chance=baseline, ai_folders=[str(f) for f in folders if f.is_dir()],
                      comparisons=records, unreadable_ai_files=unreadable)
        with (args.out or Path(f'{args.answer}.provenance.json')).open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=1)
    except (OSError, ValueError) as error:
        print('거절:', error, file=sys.stderr)
        return 2
    print(result['verdict'], f"AI 파일 {len(records)}개 대조",
          *(f"{Path(r['path']).name} {r['matches']}/{r['total']}" for r in records), sep='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
