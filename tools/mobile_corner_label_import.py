"""Apply pasted phone answers to a review jsonl as a NEW file: card box + CORNER-area truth (corner_defect), validated like review.html saves."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from card_condition.regions import REGION_LABELS, validate_annotations

AREAS = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
STATE = {'정상': 0, '결함': 1}


def parse(text):
    """Line: rowid/side=확인|미확인;box:l,t,r,b;area:state;... -> (rowid, side, confirmed, box, {area: 0/1})."""
    out = []
    for line in filter(None, (l.strip() for l in text.splitlines())):
        key, rest = line.split('=', 1)
        rid, side = key.rsplit('/', 1)
        head, *items = rest.split(';')
        box = [float(v) for v in items[0].removeprefix('box:').split(',')]
        states = dict(i.split(':') for i in items[1:])
        if head not in ('확인', '미확인') or set(states) != set(AREAS) or set(states.values()) - {'미확인', *STATE} or len(box) != 4:
            raise ValueError(f'Bad answer line: {key}')
        out.append((rid, side, head == '확인', box, {a: STATE[s] for a, s in states.items() if s in STATE}))
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


def main(review_jsonl, answers_txt, out_jsonl):
    rows = [json.loads(l) for l in Path(review_jsonl).read_text(encoding='utf-8').splitlines() if l.strip()]
    by_id = {r['id']: r for r in rows}
    for rid, side, confirmed, box, edges in parse(Path(answers_txt).read_text(encoding='utf-8')):
        apply(by_id[rid]['side_annotations'][side], confirmed, box, edges)
        validate_annotations(by_id[rid]['side_annotations'], by_id[rid])
    with Path(out_jsonl).open('x', encoding='utf-8') as stream:
        stream.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    return len(rows)


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
