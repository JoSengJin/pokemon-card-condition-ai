"""Compare pasted answers with every stored AI judgment before import; write <answer>.provenance.json. Never edits answers.

verdict (fixed before use, 07 §4-4): any full-coverage AI file equal on every zone -> ai_identical; best k/n above the
Wilson 95% upper bound of the chance agreement -> ai_suspect; otherwise no_match_found (not proof of a human), or
unknown without the exact confirmation sentence, without any full-coverage AI file, or when any AI output (except
.log) was not read completely (comparison_complete=false; see incomplete). A cleanly stored partial AI file is not
"incomplete" and never decides. Limits: no per-screen value list or required-zone list exists, so values and missing
zones are not checked. Raw pastes with tags or prose are refused: keep the original and judge an extracted copy that
starts with '# 원문sha256=<hex>'.
ai_identical/ai_suspect state value agreement only, not proof of copying; no_match_found is not proof of a human.
python -m tools.rater_gate ANSWER [--ai DIR ...] [--statement FILE --expected FILE] [--out FILE]
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tools.self_agreement.import_round import confirmed
from tools.self_agreement.stats import WILSON

SECOND_ZONE = re.compile(r'z\s*\d+\s*[=:]', re.I)  # a second assignment swallowed into one value
PHONE = re.compile(r'[^\s#;=-][^;=]*/[^;=/]+=[^;=]+;box:[^;]*;.+')


def line_pairs(line):
    """[(zone key, value)] for one supported line, else None. Values are never repaired; NFKC is used only to detect."""
    numbered = re.fullmatch(r'(z[0-9]+)\s*=\s*([^#]+)', line)
    if numbered:
        return None if SECOND_ZONE.search(unicodedata.normalize('NFKC', numbered[2])) else [numbered.groups()]
    if not PHONE.fullmatch(line):
        return None
    head, _, *zones = line.split(';')
    pairs = []
    for zone in zones:
        area, _, value = zone.partition(':')
        seen = unicodedata.normalize('NFKC', value)
        if not area.strip() or not value.strip() or ':' in seen or SECOND_ZONE.search(seen):
            return None
        pairs.append((f"{head.split('=')[0]}/{area}", value))
    return pairs


def values(text, unread=None):
    """{zone key: value string} from 'zN=값' lines or phone lines 'id/side=..;box:..;구역:상태'. '#' lines are comments.

    Without `unread` (the human answer) any other line or a conflicting repeat is refused. With a list (AI files) the
    numbers of those lines are appended, a conflicting zone is dropped, and every other readable zone is kept.
    """
    out, clash = {}, set()
    for number, line in enumerate((l.strip() for l in text.splitlines()), 1):
        if not line or line.startswith('#'):
            continue
        pairs = line_pairs(line)
        if pairs is None:
            if unread is None:
                raise ValueError(f'읽을 수 없는 줄: {line}')
            unread.append(number)
            continue
        for key, value in pairs:
            if out.setdefault(key, value) != value:
                if unread is None:
                    raise ValueError(f'같은 구역에 다른 값이 두 번 있음: {key}')
                unread.append(number)
                clash.add(key)
    return {key: value for key, value in out.items() if key not in clash}


def compare(answer, folders, answered_at, screen):
    """Every AI file gets its own record (zero overlap included), whatever its name. Anything not fully read is listed in
    `incomplete`; only .log files may stay unread. Only OS metadata without a judgment line is excluded, with a reason."""
    records, unreadable, incomplete, excluded = [], [], [], []
    for path in sorted(p for folder in folders for p in Path(folder).rglob('*') if p.is_file()):
        data, unread = path.read_bytes(), []
        try:
            text = data.decode('utf-8-sig')
            found = values(text, unread)
        except UnicodeDecodeError:
            found = {}
        if not found and (path.name == '.DS_Store' or path.name.startswith('._')):
            excluded.append(dict(path=str(path), reason='OS 메타데이터 이름이고 판정 줄 없음'))
            continue
        if (unread or not found) and path.suffix != '.log':
            incomplete.append(dict(path=str(path), reason='읽지 못한 줄 있음' if found else '읽은 판정 줄 없음', unread_lines=unread))
        if not found:
            unreadable.append(str(path))
            continue
        shared = answer.keys() & found.keys()
        header = re.search(r'^#\s*화면=(\S+)', text, re.M)
        relation = 'unknown' if not (screen and header) else 'same' if header[1] == screen else 'other'
        modified = path.stat().st_mtime
        records.append(dict(path=str(path), matches=sum(answer[k] == found[k] for k in shared), total=len(shared),
                            answer_total=len(answer), full_coverage=len(shared) == len(answer), screen=relation,
                            other_screen=relation == 'other', unread_lines=unread, sha256=hashlib.sha256(data).hexdigest(),
                            mtime=datetime.fromtimestamp(modified, timezone.utc).isoformat(),
                            answer_modified_after=answered_at > modified))
    return records, unreadable, incomplete, excluded


def chance(answer):
    """Agreement expected by chance from this answer's own value distribution (sum p^2) and its Wilson 95% upper bound."""
    n = len(answer)
    expected = sum((count / n) ** 2 for count in Counter(answer.values()).values())
    return dict(expected=expected, wilson95_upper=min(1., WILSON(expected * n, n)[1]))


def verdict(records, baseline, statement_ok, incomplete):
    """A partial-coverage file never decides. Flags may come from any full file; 'no match' needs a same-screen full
    file and nothing left incompletely read. Evidence already found stays in the records."""
    full = [r for r in records if r['full_coverage']]
    if any(r['matches'] == r['total'] for r in full):
        return 'ai_identical'
    if any(r['matches'] / r['total'] > baseline['wilson95_upper'] for r in full):
        return 'ai_suspect'
    compared = any(not r['other_screen'] for r in full)
    return 'no_match_found' if compared and not incomplete and statement_ok else 'unknown'


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
        text = data.decode('utf-8-sig')
        answer = values(text)
        header = re.search(r'^#\s*화면=(\S+)', text, re.M)
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
        records, unreadable, incomplete, excluded = compare(answer, [f for f in folders if f.is_dir()], answered_at, header and header[1])
        baseline = chance(answer)
        result = dict(verdict=verdict(records, baseline, statement_ok, incomplete), answer_sha256=hashlib.sha256(data).hexdigest(),
                      answer_mtime=datetime.fromtimestamp(answered_at, timezone.utc).isoformat(), zones=len(answer),
                      statement_confirmed=statement_ok, chance=baseline, ai_folders=[str(f) for f in folders if f.is_dir()],
                      comparisons=records, unreadable_ai_files=unreadable, comparison_complete=not incomplete,
                      incomplete=incomplete, excluded_files=excluded)
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
