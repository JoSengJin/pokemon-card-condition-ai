"""C4 label expansion: draw front photos from human-paired intakes (D1 intakes ax/az/ba-bd, dev-36 and D1 photo SHAs excluded), seeded split into holdout (label only, never marked or used in development) and train (8-tap marks + label). Auto box proposals only; nothing is labeled or prefilled. Reads photo files only to decode and propose a box."""
import glob
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'artifacts/ebay-intake-20261103-ax'))  # autobox.py lives in an intake folder (read-only import)
from autobox import propose  # noqa: E402

SEED, N_HOLDOUT, N_TRAIN = 20261103, 90, 150


def excluded():
    sealed = json.loads((ROOT/'artifacts/d1-testset-20261103/SEALED.json').read_text())
    shas = {c[k] for c in sealed['cards'] for k in ('front_sha256', 'back_sha256')}
    dev = {r['image_sha256'] for r in json.loads((ROOT/'artifacts/centering-tb-measurer-v2-20261103/rows.json').read_text())}
    return {c['intake'] for c in sealed['cards']}, shas | dev


def candidates():
    intakes, shas = excluded()
    seen, pool = set(), []
    for sel in sorted(glob.glob(str(ROOT/'artifacts/ebay-intake-*/pair-selection*.json'))):
        name = Path(sel).parent.name
        if name.rsplit('-', 1)[-1] in intakes:
            continue
        catalog = {i['id']: i for i in json.loads((Path(sel).parent/'catalog.json').read_text())['items']}
        for item in json.loads(Path(sel).read_text())['items']:
            sha = item['photo_sha256'][item['front']] if item.get('decision') == 'pair' else None
            if sha and sha not in shas and sha not in seen:
                photo = next((p for p in catalog[item['id']]['photos'] if p['sha256'] == sha), None)
                if photo and Path(photo['path']).exists():
                    seen.add(sha)
                    pool.append(dict(id=item['id'], intake=name, image=photo['path'], image_sha256=sha, size=photo['size']))
    return pool


def main(out_dir):
    pool = candidates()
    random.Random(SEED).shuffle(pool)
    chosen = pool[:N_HOLDOUT+N_TRAIN]
    for k, row in enumerate(chosen):
        row['role'] = 'holdout' if k < N_HOLDOUT else 'train'
        row['box'], row['box_confidence'] = (lambda b: ([round(float(v), 4) for v in b[0]], round(float(b[1]), 3)))(propose(row['image']))
        row['side'] = 'front'
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out/'pool.json').write_text(json.dumps(chosen, ensure_ascii=False, indent=1))
    manifest = dict(seed=SEED, available=len(pool), holdout=N_HOLDOUT, train=N_TRAIN, pool_sha256=hashlib.sha256((out/'pool.json').read_bytes()).hexdigest(),
                    rule='holdout is label-only and must not be marked, viewed for tuning or used in development until the measurer is frozen')
    (out/'MANIFEST.json').write_text(json.dumps(manifest, indent=1))
    return manifest


if __name__ == '__main__':
    print(main(sys.argv[1]))
