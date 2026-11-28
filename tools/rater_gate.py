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
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tools.rater_gate_lines import values
from tools.self_agreement.import_round import confirmed
from tools.self_agreement.stats import WILSON


def walk(folders):
    """(every entry, [(path, reason)] for what the traversal cannot enter). Directory links are not followed."""
    entries, errors, links = [], [], []
    for folder in folders:
        for root, dirs, files in os.walk(folder, onerror=errors.append):
            links += [(os.path.join(root, d), '폴더 링크는 따라가지 않음') for d in dirs if os.path.islink(os.path.join(root, d))]
            entries += [Path(root, f) for f in files]
    return sorted(entries), links + [(str(e.filename), f'폴더를 읽을 수 없음: {e.strerror}') for e in errors]


def compare(answer, folders, answered_at, screen):
    """Every AI file gets its own record (zero overlap included), whatever its name. Anything not fully read is listed in
    `incomplete`; only .log files may stay unread. Only OS metadata without a judgment line is excluded, with a reason."""
    records, unreadable, excluded = [], [], []
    entries, blocked = walk(folders)
    incomplete = [dict(path=path, reason=reason, unread_lines=[]) for path, reason in blocked]
    for path in entries:
        unread = []
        try:
            if not path.is_file():  # broken link, pipe, socket: never opened
                raise OSError('일반 파일이 아님')
            data, modified = path.read_bytes(), path.stat().st_mtime
        except OSError as error:
            unreadable.append(str(path))
            if path.suffix != '.log':
                incomplete.append(dict(path=str(path), reason=f'파일을 읽을 수 없음: {error.strerror or error}', unread_lines=[]))
            continue
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
        records.append(dict(path=str(path), matches=sum(answer[k] == found[k] for k in shared), total=len(shared),
                            answer_total=len(answer), unread_zones=sum(found[k] is None for k in shared),
                            full_coverage=len(shared) == len(answer), screen=relation,
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
    file whose shared zones were all read, and nothing left incompletely read. Evidence already found stays in the records."""
    full = [r for r in records if r['full_coverage']]
    if any(r['matches'] == r['total'] for r in full):
        return 'ai_identical'
    if any(r['matches'] / r['total'] > baseline['wilson95_upper'] for r in full):
        return 'ai_suspect'
    compared = any(not r['other_screen'] and not r['unread_zones'] for r in full)
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
        records, unreadable, incomplete, excluded = compare(answer, [f for f in folders if f.is_dir() or f.is_symlink()], answered_at, header and header[1])
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
