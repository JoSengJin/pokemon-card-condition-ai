"""v2 read-only analysis per prereg-v2.json: FP vs TN outside-card rate with v2 mask, bad masks excluded by the pre-fixed rule."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analysis import PACKET, OUT, photo_boxes, bootstrap
from mask2 import card_mask2


def patch_out(mask, box):
    h, w = mask.shape
    return int(not mask[min(h - 1, int((box[1] + box[3]) / 2 * h)), min(w - 1, int((box[0] + box[2]) / 2 * w))])


def verdict(rate, lo, hi, bad_share):
    if bad_share > .20:
        return 'inconclusive'
    diff = rate['FP'] - rate['TN']
    return 'support' if rate['FP'] >= 2 * rate['TN'] and diff >= .05 and lo > 0 else 'reject' if diff <= 0 or lo <= 0 <= hi else 'inconclusive'


def main():
    entries = json.load(open(PACKET))['entries']; masks = {p: card_mask2(p, b)[1:] for p, b in photo_boxes(entries).items()}
    bad = {p for p, v in masks.items() if v[2]}; rows = []
    for e in entries:
        r = e['row']; m = masks[r['image']][0]; ev = e['evidence']
        rows.append(dict(id=r['id'], group=r['group'], image=r['image'], outcome=e['outcome'], bad=r['image'] in bad,
                         center_out=patch_out(m, ev['top_geometry']['box']),
                         top2_out=int(patch_out(m, ev['top_geometry']['box']) or patch_out(m, ev['second_geometry']['box']))))
    good = [x for x in rows if not x['bad']]
    summary = {o: dict(n=sum(x['outcome'] == o for x in good), center_out=sum(x['center_out'] for x in good if x['outcome'] == o),
                       top2_out=sum(x['top2_out'] for x in good if x['outcome'] == o)) for o in ('FP', 'FN', 'TP', 'TN')}
    rate = {o: summary[o]['center_out'] / summary[o]['n'] for o in summary}
    lo, hi = bootstrap(good)
    result = dict(bad_mask_photos=len(bad), photos=len(masks), bad_share=len(bad) / len(masks), summary=summary, rates=rate,
                  fp_minus_tn=rate['FP'] - rate['TN'], ci95=[lo, hi],
                  secondary_top2={o: summary[o]['top2_out'] / summary[o]['n'] for o in summary}, verdict=verdict(rate, lo, hi, len(bad) / len(masks)))
    (OUT / 'rows2.json').write_text(json.dumps(rows)); (OUT / 'hulls2.json').write_text(json.dumps({k: v[1] for k, v in masks.items()}))
    (OUT / 'bad2.json').write_text(json.dumps(sorted(bad))); (OUT / 'results2.json').write_text(json.dumps(result, indent=1)); print(json.dumps(result))


if __name__ == '__main__':
    main()
