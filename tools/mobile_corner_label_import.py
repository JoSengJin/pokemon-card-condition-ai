"""Apply pasted phone answers to a review jsonl as a NEW file: card box + CORNER-area truth (corner_defect), validated like review.html saves."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.regions import REGION_LABELS, validate_annotations
from tools import label_criteria

AREAS = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
STATE = {'정상': 0, '결함': 1}
UNJUDGED = ('미확인', '판단 불가')  # kept out of region_labels; 판단 불가 is recorded apart from 미확인 in <out>.states.json


def parse(text):
    """Line: rowid/side=확인|미확인;box:l,t,r,b;area:state;... -> (rowid, side, confirmed, box, {area: 0/1}, {area: 미확인|판단 불가})."""
    out = []
    for line in filter(None, (l.strip() for l in text.splitlines())):
        key, rest = line.split('=', 1)
        rid, side = key.rsplit('/', 1)
        head, *items = rest.split(';')
        box = [float(v) for v in items[0].removeprefix('box:').split(',')]
        states = dict(i.split(':') for i in items[1:])
        if head not in ('확인', '미확인') or set(states) != set(AREAS) or set(states.values()) - {*UNJUDGED, *STATE} or len(box) != 4:
            raise ValueError(f'Bad answer line: {key}')
        out.append((rid, side, head == '확인', box, {a: STATE[s] for a, s in states.items() if s in STATE}, {a: s for a, s in states.items() if s in UNJUDGED}))
    return out


def apply(annotation, confirmed, box, edges):
    """Corner truth only; other kinds, gradable and points stay untouched. Refuses to overwrite existing edge truth."""
    if any((v or {}).get('corner_defect') is not None for v in annotation.get('region_labels', {}).values()) or annotation['labels'].get('corner_defect') is not None:
        raise ValueError('Corner truth already stored for this face')
    annotation['box'], annotation['box_reviewed'] = box, confirmed
    regions = annotation.setdefault('region_labels', {})
    for area, value in edges.items():
        regions.setdefault(area, {k: None for k in REGION_LABELS})['corner_defect'] = value
    if any(edges.values()):
        annotation['labels']['corner_defect'] = 1
    elif len(edges) == len(AREAS):
        annotation['labels']['corner_defect'] = 0


def write_states(out_jsonl, answers):
    """<out>.states.json: counts of all four states plus every zone that is not 0/1 (판단 불가 stays apart from 미확인). Never overwrites."""
    counts, states = dict.fromkeys(('정상', '결함', *UNJUDGED), 0), {}
    for rid, side, _, _, edges, unjudged in answers:
        for value in (*('결함' if v else '정상' for v in edges.values()), *unjudged.values()):
            counts[value] += 1
        states.update({f'{rid}/{side}/{a}': s for a, s in unjudged.items()})
    with Path(f'{out_jsonl}.states.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(schema_version=1, counts=counts, states=states), stream, ensure_ascii=False)


def main(review_jsonl, answers_txt, out_jsonl, criteria_json=None):
    """With criteria_json (the page's .criteria.json): refuse before writing unless every answer id is on that page; also writes <out_jsonl>.criteria.json. Always writes <out_jsonl>.states.json."""
    rows = [json.loads(l) for l in Path(review_jsonl).read_text(encoding='utf-8').splitlines() if l.strip()]
    by_id = {r['id']: r for r in rows}
    answers = parse(Path(answers_txt).read_text(encoding='utf-8'))
    shown = criteria_json and label_criteria.check(criteria_json, [f'{a[0]}/{a[1]}' for a in answers], out_jsonl)
    if Path(f'{out_jsonl}.states.json').exists():
        raise FileExistsError(f'{out_jsonl}.states.json')  # shortcut: checked up front, not atomic against a concurrent writer
    for rid, side, confirmed, box, edges, _ in answers:
        apply(by_id[rid]['side_annotations'][side], confirmed, box, edges)
        validate_annotations(by_id[rid]['side_annotations'], by_id[rid])
    with Path(out_jsonl).open('x', encoding='utf-8') as stream:
        stream.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    if criteria_json:
        label_criteria.write_import(out_jsonl, shown)
    try:
        write_states(out_jsonl, answers)
    except BaseException:  # leave nothing half-written so a retry with the same output path works
        for leftover in (out_jsonl, f'{out_jsonl}.states.json', *([label_criteria.sidecar(out_jsonl)] if criteria_json else [])):
            Path(leftover).unlink(missing_ok=True)
        raise
    return len(rows)


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
