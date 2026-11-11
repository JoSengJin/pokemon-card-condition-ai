"""새 기준 1차(normal-rejudge) vs 2차(normal-rejudge2) 재현성. 기준은 normal-rejudge2 prereg.json 고정. 학습·라벨 변경 0."""
import glob
import json
import random
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from kappa import stats, boot, C


def load(d):
    out = {}
    for f in sorted(glob.glob(f'artifacts/{d}/responses/batch0*.json')):
        for r in json.load(open(f))['responses']: out[r['id']] = r['judgment']
    return out


def main():
    a, b = load('normal-rejudge-20261112'), load('normal-rejudge2-20261112'); assert set(a) == set(b) and len(a) == 30
    pairs = [(a[i], b[i]) for i in a]; res = dict(**stats(pairs), **boot(pairs))
    res['confusion'] = {f'{x}->{y}': c for (x, y), c in sorted(Counter(pairs).items())}
    res['pass1_dist'] = dict(Counter(a.values())); res['pass2_dist'] = dict(Counter(b.values()))
    res['changed'] = [dict(id=i, p1=a[i], p2=b[i]) for i in a if a[i] != b[i]]
    json.dump(res, open('artifacts/normal-rejudge2-20261112/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
