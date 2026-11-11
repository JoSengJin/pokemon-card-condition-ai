"""반복 판정(prereg repeat_check): 100곳 중 무작위 20곳을 순서 섞어 5곳 x 4파일. 학습·추론·라벨 변경 0."""
import json
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build import OUT, SEED, frame, page


def main():
    ids = [z['id'] for z in json.load(open(OUT / 'sample.json'))['zones']]; rng = random.Random(SEED + 1)
    pick = rng.sample(ids, 20); allz = {z['id']: z for cell in frame().values() for z in cell}; files = []
    for k in range(0, 20, 5):
        zs = [allz[i] for i in pick[k:k + 5]]; name = f'repeat-{k // 5 + 1:02d}.html'; (OUT / 'pages' / name).write_text(page(zs, k // 5 + 1, 4))
        files.append(dict(file=name, ids=[z['id'] for z in zs]))
    (OUT / 'manifest_repeat.json').write_text(json.dumps(dict(files=files), indent=1)); print(len(pick))


if __name__ == '__main__':
    main()
