"""D2 evaluation rows from the sealed D1 test set (corner/surface per-zone, observation-limit per back face). Reads sealed labels only; no model, no training."""
import hashlib
import json
import re
import sys
from pathlib import Path

from card_condition.regions import region_box

LABELS = Path('artifacts/d1-labels-20261103')
INTAKES = 'ax az ba bb bc bd'.split()
TARGET = {'정상': 0, '결함': 1, '제한': 1}


def backs():
    """id -> (back image path, intake, review box) from the sealed intakes' review files."""
    out = {}
    for k in INTAKES:
        for line in Path(f'artifacts/ebay-intake-20261103-{k}/review/labels-review.jsonl').read_text(encoding='utf-8').splitlines():
            r = json.loads(line) if line.strip() else None
            if r:
                out[r['id']] = (r['back'], k, r['side_annotations']['back']['box'])
    return out


def zone_rows(answers, kind):
    """One row per zone with a 정상/결함 answer on a 확인 box; 미확인 zones and cards are left out (counts in the summary)."""
    info, rows = backs(), []
    for line in (LABELS/answers).read_text(encoding='utf-8').splitlines():
        ident, rest = line.split('/back=', 1)
        if not rest.startswith('확인'):
            continue
        box = [float(v) for v in re.search(r'box:([\d.,]+)', rest).group(1).split(',')]
        image, intake, _ = info[ident]
        sha = hashlib.sha256(Path(image).read_bytes()).hexdigest()
        for area, state in re.findall(r';([a-z_]+):(정상|결함)', rest):
            rows.append(dict(id=f'{ident}/back/{kind}/{area}', group=ident, split='test', image=image, image_sha256=sha, area=area,
                             target=TARGET[state], box=region_box(box, area), intake=intake))
    return rows


def confirmed_boxes():
    """id -> human-confirmed card box from the corner/surface pages (corner page wins)."""
    out = {}
    for name in ('sur-answers.txt', 'cor-answers.txt'):
        for line in (LABELS/name).read_text(encoding='utf-8').splitlines():
            ident, rest = line.split('/back=', 1)
            if rest.startswith('확인'):
                out[ident] = [float(v) for v in re.search(r'box:([\d.,]+)', rest).group(1).split(',')]
    return out


def obs_rows():
    """Back faces with a 정상/제한 answer and a human-confirmed box; others are left out (counted in the summary)."""
    info, boxes, rows = backs(), confirmed_boxes(), []
    for line in (LABELS/'obs-answers.txt').read_text(encoding='utf-8').splitlines():
        ident, value = line.strip().split('/back=')
        if value in TARGET and ident in boxes:
            image = info[ident][0]
            rows.append(dict(id=f'{ident}/back/observation_limited', group=ident, split='test', image=image, side='back', target=TARGET[value],
                             box=boxes[ident], image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(), box_reviewed=True))
    return rows


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sets = dict(corner=zone_rows('cor-answers.txt', 'corner'), surface=zone_rows('sur-answers.txt', 'surface'), obs=obs_rows())
    summary = {}
    for name, rows in sets.items():
        (out/f'{name}-rows.json').write_text(json.dumps(rows, ensure_ascii=False))
        summary[name] = dict(rows=len(rows), groups=len({r['group'] for r in rows}), positive=sum(r['target'] for r in rows),
                             defect_photos=len({r['group'] for r in rows if r['target']}))
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


if __name__ == '__main__':
    print(main(sys.argv[1]))
