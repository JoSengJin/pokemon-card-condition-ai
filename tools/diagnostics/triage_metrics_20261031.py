"""Triage-use metrics from stored scores only (no training, no model call). Bands are fixed before looking at the holdout:
low < 0.31, high >= 0.54 (the thresholds where the pooled out-of-fold scores give ~10% / ~30% missed defects)."""
import collections
import json

LOW, HIGH = 0.31, 0.54


def groups(rows, scores):
    g = collections.defaultdict(list)
    for r, s in zip(rows, scores):
        g[r['group']].append((s, r['target']))
    return g


def bands(rows, scores):
    out = {}
    for name, lo, hi in (('low', -1, LOW), ('mid', LOW, HIGH), ('high', HIGH, 2)):
        sel = [r['target'] for r, s in zip(rows, scores) if lo <= s < hi]
        out[name] = dict(areas=len(sel), defect_rate=sum(sel)/len(sel) if sel else None)
    return out


def ranking(rows, scores):
    mixed = [v for v in groups(rows, scores).values() if any(t for _, t in v) and not all(t for _, t in v)]
    anyd = [v for v in groups(rows, scores).values() if any(t for _, t in v)]
    top1 = [sorted(v, key=lambda x: -x[0])[0][1] for v in mixed]
    p3 = [sum(t for _, t in sorted(v, key=lambda x: -x[0])[:3])/3 for v in mixed]
    base = [sum(t for _, t in v)/len(v) for v in mixed]
    return dict(photos_with_defect=len(anyd), photos_mixed=len(mixed), hit_at_1=sum(top1)/len(top1), precision_at_3=sum(p3)/len(p3), chance_precision=sum(base)/len(base))


def main():
    o = json.load(open('artifacts/experiments/20261031T070156-6a9907df/oof_scores.json'))
    h = json.load(open('artifacts/experiments/20261031T105833-2c72d505/scores.json'))
    print(json.dumps(dict(oof_788=dict(bands=bands(o['rows'], o['control']), ranking=ranking(o['rows'], o['control'])),
                          holdout_36=dict(bands=bands(h['holdout_rows'], h['holdout_base']), ranking=ranking(h['holdout_rows'], h['holdout_base']))), ensure_ascii=False, indent=1))


main()
