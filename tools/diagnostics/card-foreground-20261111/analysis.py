"""Read-only: join saved top-patch geometry with the heuristic card mask; FP vs TN outside-card rates with group bootstrap."""
import json
import random
import sys
from pathlib import Path
import numpy as np
from mask import card_mask

PACKET = 'artifacts/surface-grounding-20261110/packet.json'
JUDGED = 'artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json'
OUT = Path('artifacts/card-foreground-diagnostic-20261111')


def photo_boxes(entries):
    boxes = {}
    for e in entries:
        r = e['row']; b = boxes.setdefault(r['image'], [9, 9, -9, -9])
        b[0], b[1], b[2], b[3] = min(b[0], r['box'][0]), min(b[1], r['box'][1]), max(b[2], r['box'][2]), max(b[3], r['box'][3])
    return boxes


def outside_rates(mask, box):
    h, w = mask.shape
    xs = np.linspace(box[0], box[2], 5); ys = np.linspace(box[1], box[3], 5)
    samples = [mask[min(h - 1, int(y * h)), min(w - 1, int(x * w))] for y in ys for x in xs]
    center = mask[min(h - 1, int((box[1] + box[3]) / 2 * h)), min(w - 1, int((box[0] + box[2]) / 2 * w))]
    return int(not center), int(sum(not s for s in samples) >= 13)


def bootstrap(rows, kinds=('FP', 'TN'), draws=2000, seed=20261111):
    groups = sorted({r['group'] for r in rows}); by = {g: [r for r in rows if r['group'] == g] for g in groups}
    rng = random.Random(seed); diffs = []
    for _ in range(draws):
        pick = [x for g in (rng.choice(groups) for _ in groups) for x in by[g]]
        a = [r['center_out'] for r in pick if r['outcome'] == kinds[0]]; b = [r['center_out'] for r in pick if r['outcome'] == kinds[1]]
        if a and b:
            diffs.append(sum(a) / len(a) - sum(b) / len(b))
    diffs.sort()
    return diffs[int(.025 * len(diffs))], diffs[int(.975 * len(diffs)) - 1]


def main():
    entries = json.load(open(PACKET))['entries']; boxes = photo_boxes(entries); masks = {}
    for path, box in boxes.items():
        _, m, hull = card_mask(path, box); masks[path] = (m, hull)
    rows = []
    for e in entries:
        r = e['row']; c, s = outside_rates(masks[r['image']][0], e['evidence']['top_geometry']['box'])
        rows.append(dict(id=r['id'], group=r['group'], image=r['image'], outcome=e['outcome'], center_out=c, half_out=s))
    summary = {o: dict(n=sum(x['outcome'] == o for x in rows), center_out=sum(x['center_out'] for x in rows if x['outcome'] == o),
                       half_out=sum(x['half_out'] for x in rows if x['outcome'] == o)) for o in ('FP', 'FN', 'TP', 'TN')}
    lo, hi = bootstrap(rows)
    rate = lambda o: summary[o]['center_out'] / summary[o]['n']
    verdict = 'support' if rate('FP') >= 2 * rate('TN') and rate('FP') - rate('TN') >= .05 and lo > 0 else 'reject' if rate('FP') - rate('TN') <= 0 or lo <= 0 <= hi else 'inconclusive'
    result = dict(summary=summary, fp_minus_tn=rate('FP') - rate('TN'), ci95=[lo, hi], verdict_before_user_mask_review=verdict,
                  hull_area_share={k: float(v[0].mean()) for k, v in list(masks.items())[:0]},
                  empty_hull_photos=sum(1 for v in masks.values() if len(v[1]) < 3))
    (OUT / 'rows.json').write_text(json.dumps(rows)); (OUT / 'hulls.json').write_text(json.dumps({k: v[1] for k, v in masks.items()}))
    (OUT / 'results.json').write_text(json.dumps(result, indent=1)); print(json.dumps(result))


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent)); main()
