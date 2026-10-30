"""Stage-2 sample for card localization: seeded random draw of back faces from the f/g/h pool; already-cornered faces reuse their human points."""
import hashlib
import json
import sys
from pathlib import Path

BATCHES = ('f', 'g', 'h')
SEED = 'card-localization-stage2-20261031'
SIZE, PAGE = 40, 20
NEUTRAL_BOX = [0.15, 0.15, 0.85, 0.85]  # fixed start points: the human is not anchored on autobox output


def pool(root):
    faces = []
    for b in BATCHES:
        path = next((root/'artifacts').glob(f'ebay-intake-2026*-{b}/back-faces.json'))
        answers = path.parent/'corner-answers.txt'
        done = {l.split('=')[0] for l in answers.read_text().splitlines() if '=' in l} if answers.exists() else set()
        faces += [dict(f, batch=b, has_corners=f['id'] in done) for f in json.loads(path.read_text())]
    return faces


def draw(faces):
    return sorted(faces, key=lambda f: hashlib.sha256((SEED + f['id']).encode()).hexdigest())[:SIZE]


if __name__ == '__main__':
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    faces = pool(root)
    sample = draw(faces)
    todo = [f for f in sample if not f['has_corners']]
    (out/'sample.json').write_text(json.dumps(dict(seed=SEED, pool_size=len(faces), pool_by_batch={b: sum(f['batch'] == b for f in faces) for b in BATCHES},
                                                    sample_ids=[f['id'] for f in sample], already_cornered=[f['id'] for f in sample if f['has_corners']],
                                                    to_click=[f['id'] for f in todo]), ensure_ascii=False, indent=1))
    (out/'faces.json').write_text(json.dumps([dict(f, box=NEUTRAL_BOX) for f in todo]))
    for n in range(0, len(todo), PAGE):
        (out/f'ids-{n//PAGE + 1}.txt').write_text('\n'.join(f['id'] for f in todo[n:n + PAGE]))
    print(len(faces), len(sample), len(todo), {b: sum(f['batch'] == b for f in sample) for b in BATCHES})
