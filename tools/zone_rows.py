"""Answers -> evaluation rows plus exclusions.json and row_facts.json. Nothing is dropped silently; labels are never written.

Contract: docs/collaboration/tasks/record-sidecars-20261127.md. Run from the checkout that holds artifacts/:
python -m tools.zone_rows ANSWERS --kind corner --box confirmed-only --out DIR [--provenance F] [--measures F]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from card_condition.regions import REGION_TARGET_AREAS, region_box
from tools.d2_rows import INTAKES, TARGET, backs
from tools.rater_gate import LIMIT, NOTICE

# T0 contract constants; card_condition/experiment_sidecars.py checks the same strings.
STATES = ('정상', '결함', '미확인', '판단 불가')
BOX = '상자 미확인'
MARKS = ('AI 동일', 'AI 의심', '기준 판본 불일치')  # shortcut: 기준 판본 비교 입력이 없어 항상 0 = 미측정
VERDICTS = ('ai_identical', 'ai_suspect', 'no_match_found', 'unknown')
BOX_OUT = '정상·결함만 행으로 둔다. 상자 미확인 사진의 구역은 행에서 뺀다'
BOX_IN = '정상·결함만 행으로 둔다. 상자 미확인 사진의 구역도 행에 포함한다'


def parse(text):
    """'id/side=확인|미확인;box:l,t,r,b;area:state;...' lines; '#' lines are comments, as in tools/rater_gate.py.
    An unknown state or shape is refused with its line number."""
    answers, seen = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.strip().startswith('#'):
            continue
        try:
            head, box, *zones = line.strip().split(';')
            ident, side_value = head.split('/')
            side, confirmed = side_value.split('=')
            pairs = [zone.split(':') for zone in zones]
            states = dict(pairs)
            numbers = [float(v) for v in box.removeprefix('box:').split(',')]
            if (side != 'back' or confirmed not in ('확인', '미확인') or not box.startswith('box:') or len(numbers) != 4 or not states
                    or len(states) != len(pairs) or set(states.values()) - set(STATES) or (ident, side) in seen):
                raise ValueError
        except ValueError:
            raise ValueError(f'{number}번째 줄: 모르는 상태·형식이거나 같은 대상이 겹침') from None
        seen.add((ident, side))
        answers.append(dict(line=number, id=ident, side=side, box_ok=confirmed == '확인', box=numbers, states=states))
    return answers


def build(answers, info, kind, need_ok, provenance=None):
    """Rows for 정상/결함 only; every other zone is counted in exactly one exclusions column. AI-identical files give no rows."""
    if provenance is not None and (not isinstance(provenance, dict) or provenance.get('verdict') not in VERDICTS):
        raise ValueError('provenance verdict가 계약의 네 값이 아님')
    verdict = None if provenance is None else provenance['verdict']
    rows, cell = [], {}
    for answer in answers:
        if answer['id'] not in info or set(answer['states']) - set(REGION_TARGET_AREAS[f'{kind}_defect']):
            raise ValueError(f"{answer['line']}번째 줄: 모르는 카드 id 또는 이 칸에 없는 구역")
        image = info[answer['id']][0]
        digest = None
        for area, state in answer['states'].items():
            counts = cell.setdefault(area, {**dict.fromkeys((*STATES, *MARKS), 0), BOX: dict.fromkeys(STATES, 0)})
            keep = state in TARGET and (answer['box_ok'] or not need_ok)
            if keep and verdict == 'ai_identical':
                counts['AI 동일'] += 1
                continue
            (counts if answer['box_ok'] else counts[BOX])[state] += 1
            if not keep:
                continue
            counts['AI 의심'] += verdict == 'ai_suspect'  # D-7 undecided: kept and only marked
            digest = digest or hashlib.sha256(Path(image).read_bytes()).hexdigest()
            rows.append(dict(id=f"{answer['id']}/{answer['side']}/{kind}/{area}", group=answer['id'], split='test', image=image,
                             image_sha256=digest, area=area, target=TARGET[state], box=region_box(answer['box'], area),
                             intake=info[answer['id']][1]))
    return rows, {kind: cell, 'kept_rule': BOX_OUT if need_ok else BOX_IN}


def facts(rows, measures, provenance=None):
    """One record per row. Missing measurement -> 'unmeasured'; no_match_found is not proof of a human, so it stays unknown."""
    verdict = provenance['verdict'] if provenance else None
    rater = verdict if verdict in ('ai_identical', 'ai_suspect') else 'unknown'
    out = {}
    if '_measure_sha256' in measures:
        out['_measure_sha256'] = measures['_measure_sha256']
    for row in rows:
        found = measures.get(f"{row['id']}|{row['image_sha256']}|{','.join(f'{v:.6f}' for v in row['box'])}", {})
        background, ppm = found.get('status', 'unmeasured'), found.get('ppm')
        if ppm is not None and (type(ppm) not in (int, float) or not 0 < ppm < float('inf')):
            raise ValueError(f"쓸 수 없는 ppm 측정값: {row['id']}")
        layer = 'unmeasured' if ppm is None else '<10' if ppm < 10 else '10-15.3' if ppm < 15.3 else '>=15.3'
        out[row['id']] = dict(background=background, px_per_mm_layer=layer, rater_kind=rater, criteria_sha256='버전 미상',
                              input_hold=background in ('corner_cut', 'no_blue_border') or layer == '<10')
    return out


def write_new(folder, files):
    """Never overwrite; if any file fails, remove the ones written by this call."""
    written = []
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        for name, value in files.items():
            with (Path(folder) / name).open('x', encoding='utf-8') as stream:
                written.append(Path(folder) / name)
                json.dump(value, stream, ensure_ascii=False, indent=1)
    except BaseException:
        for path in written:
            path.unlink()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('answers', type=Path)
    parser.add_argument('--kind', required=True, choices=('corner', 'edge', 'surface'))
    parser.add_argument('--box', required=True, choices=('confirmed-only', 'include-unconfirmed'))
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--provenance', type=Path, help='<answers>.provenance.json from tools/rater_gate.py')
    parser.add_argument('--measures', type=Path)
    parser.add_argument('--intakes', nargs='+', default=INTAKES)
    args = parser.parse_args(argv)
    try:
        data = args.answers.read_bytes()
        provenance = None
        if args.provenance is not None:  # once given, it is never silently ignored
            provenance = json.loads(args.provenance.read_text(encoding='utf-8'))
            if not isinstance(provenance, dict) or provenance.get('answer_sha256') != hashlib.sha256(data).hexdigest():
                raise ValueError('provenance 기록이 이 답 파일의 것이 아님')
            if provenance.get('comparison_complete') is not True:  # shown only; excluding such rows is undecided (D-7)
                print('주의: AI 대조가 완전하다고 기록되지 않음. 행은 빼지 않음. provenance의 incomplete를 확인할 것', file=sys.stderr)
        rows, exclusions = build(parse(data.decode('utf-8-sig')), backs(args.intakes), args.kind, args.box == 'confirmed-only', provenance)
        measures = json.loads(args.measures.read_text(encoding='utf-8')) if args.measures else {}
        write_new(args.out, {'rows.json': rows, 'exclusions.json': {**exclusions, 'notice': NOTICE, 'limitation': LIMIT}, 'row_facts.json': facts(rows, measures, provenance)})
    except (OSError, ValueError, KeyError) as error:
        print('거절:', error, file=sys.stderr)
        return 2
    print(f'rows={len(rows)}', json.dumps(exclusions, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
