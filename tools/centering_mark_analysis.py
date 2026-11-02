"""Border widths and centering ratios from the 8 human edge marks, related to the human centering_defect label. Label-vs-mark diagnostic only: no model, no learning. Each tapped pair is sorted (near, far) because the tap order was mixed."""
import json
import random
import sys
from pathlib import Path


def parse(text):
    rows = {}
    for line in text.splitlines():
        ident, side, window, values = line.split('|')
        rows[ident] = None if values == '미확인' else [float(v) for v in values.split(',')]
    return rows


def widths(v):
    ox, oy, ix, iy = sorted(v[0:2]), sorted(v[2:4]), sorted(v[4:6]), sorted(v[6:8])
    w = dict(left=ix[0]-ox[0], right=ox[1]-ix[1], top=iy[0]-oy[0], bottom=oy[1]-iy[1])
    w['valid'] = all(x > 0 for x in w.values())
    return w


def ratios(w):
    lr, tb = abs(w['left']-w['right'])/(w['left']+w['right']), abs(w['top']-w['bottom'])/(w['top']+w['bottom'])
    return dict(lr=lr, tb=tb, worst=max(lr, tb))


def auc(pos, neg):
    return sum((a > b) + .5*(a == b) for a in pos for b in neg)/(len(pos)*len(neg))


def bootstrap(items, key, draws=2000, seed=20261103):
    rng, vals = random.Random(seed), []
    for _ in range(draws):
        pick = [rng.choice(items) for _ in items]
        pos, neg = [key(i) for i in pick if i['target']], [key(i) for i in pick if not i['target']]
        if pos and neg:
            vals.append(auc(pos, neg))
    vals.sort()
    return vals[int(.025*(len(vals)-1))], vals[int(.975*(len(vals)-1))]


def main(answers, selection, manifest):
    marks = parse(Path(answers).read_text(encoding='utf-8'))
    target = {}
    for r in map(json.loads, Path(manifest).read_text(encoding='utf-8').splitlines()):
        target[r['id']] = ((r.get('side_annotations') or {}).get('back') or {}).get('labels', {}).get('centering_defect')
    items, skipped, invalid = [], [], []
    for s in json.loads(Path(selection).read_text()):
        v = marks.get(s['id'])
        if v is None:
            skipped.append(s['id'])
            continue
        w = widths(v)
        if not w['valid']:
            invalid.append(s['id'])
            continue
        items.append(dict(id=s['id'], target=target[s['id']], widths=w, **ratios(w)))
    result = dict(n=len(items), positive=sum(i['target'] for i in items), skipped=len(skipped), invalid=invalid, items=items)
    for name in ('lr', 'tb', 'worst'):
        pos, neg = [i[name] for i in items if i['target']], [i[name] for i in items if not i['target']]
        result[name] = dict(auc=auc(pos, neg), ci=bootstrap(items, lambda i, n=name: i[n]), mean_defect=sum(pos)/len(pos), mean_normal=sum(neg)/len(neg))
    return result


if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:4]), ensure_ascii=False, indent=1, default=float))
