"""Consensus-label pages for the corner dev zones: 240 zones never re-judged before (120 labelled defect + 120 normal, seeded, no model score), judged once more, blind, with the current strict criterion and high-resolution crops. A zone is 'consensus' when the blind answer equals the original label; any other answer is 'ambiguous'. Ids c1..c240; the mapping stays in selection-consensus.json."""
import json
import random
import sys
from pathlib import Path

from tools import relabel_corner_repro_pages as repro

SEED, PER_CLASS, PER_PAGE = 20261123, 120, 20


def select(rows, exclude_ids):
    rng, chosen = random.Random(SEED), []
    for target in (1, 0):
        pool = sorted((r for r in rows if r['target'] == target and r['id'] not in exclude_ids), key=lambda r: r['id'])
        rng.shuffle(pool)
        chosen += pool[:PER_CLASS]
    rng.shuffle(chosen)
    return [dict(n=i, **z) for i, z in enumerate(chosen, 1)]


def main(rows_path, out):
    out = Path(out)
    done = {z['id'] for name in ('selection.json', 'selection-repro.json') for z in json.loads((out/name).read_text())}
    chosen = select(json.loads(Path(rows_path).read_text()), done)
    (out/'selection-consensus.json').write_text(json.dumps(chosen, ensure_ascii=False))
    pages = [chosen[i:i + PER_PAGE] for i in range(0, len(chosen), PER_PAGE)]
    for n, zones in enumerate(pages, 1):
        html = repro.page(1, n, len(pages), zones).replace('data-id="r', 'data-id="c').replace('구역 r', '구역 c').replace('모서리 재현성 1차', '모서리 합의 판정')
        (out/f'consensus-{n:02d}.html').write_text(html)
    print(len(chosen), 'zones,', len(pages), 'pages')


if __name__ == '__main__':
    main(*sys.argv[1:3])
