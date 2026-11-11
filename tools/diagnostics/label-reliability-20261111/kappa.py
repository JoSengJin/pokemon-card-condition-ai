"""재판정 40곳 일치도(Cohen kappa, Gwet AC1, 이진 일치율, 부트스트랩). 학습·추론·라벨 변경 0. 기준은 prereg.json 고정."""
import glob
import json
import random
from collections import Counter
R = 'artifacts/label-reliability-20261111/'
C = ('defect', 'normal', 'unknown')
SEED, B = 20261111, 5000


def stats(pairs):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    ma, mb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ma[c] * mb[c] for c in C) / n ** 2
    kappa = (po - pe) / (1 - pe) if pe < 1 else float('nan')
    pi = [(ma[c] + mb[c]) / (2 * n) for c in C]
    pg = sum(p * (1 - p) for p in pi) / (len(C) - 1)
    ac1 = (po - pg) / (1 - pg)
    bin_ = sum((a == 'defect') == (b == 'defect') for a, b in pairs) / n
    return dict(n=n, agree=round(po, 4), kappa=round(kappa, 4), ac1=round(ac1, 4), binary_agree=round(bin_, 4))


def boot(pairs):
    rng = random.Random(SEED); ks, ac = [], []
    for _ in range(B):
        s = stats([rng.choice(pairs) for _ in pairs])
        if s['kappa'] == s['kappa']: ks.append(s['kappa'])
        ac.append(s['ac1'])
    q = lambda v: [round(sorted(v)[int(len(v) * p)], 3) for p in (0.025, 0.975)]
    return dict(kappa_ci=q(ks), ac1_ci=q(ac))


def main():
    orig = json.load(open(R + 'original_judgments_hidden.json')); new = {}
    for f in sorted(glob.glob(R + 'responses/batch0*.json')):
        for r in json.load(open(f))['responses']: new[r['id']] = r['judgment']
    assert set(new) == set(orig) and len(new) == 40, (len(new), len(orig))
    pairs = [(orig[i], new[i]) for i in orig]
    art = 'ebay-pair-28771349820995/back/surface/lower_left/point-review/262'
    res = dict(all=dict(**stats(pairs), **boot(pairs)),
               excl_artifact=stats([(orig[i], new[i]) for i in orig if i != art]),
               confusion={f'{a}->{b}': c for (a, b), c in sorted(Counter(pairs).items())},
               changed=[dict(id=i, orig=orig[i], retest=new[i]) for i in orig if orig[i] != new[i]],
               by_orig={c: dict(n=sum(o == c for o, _ in pairs), same=sum(o == c and n == c for o, n in pairs)) for c in C})
    json.dump(res, open(R + 'results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
