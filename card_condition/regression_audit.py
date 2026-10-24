"""Paired error transitions: aggregate gains do not erase newly introduced errors."""
import math


def compare_predictions(truth, before, after):
    if not truth or len(truth) != len(before) or len(truth) != len(after):
        raise ValueError('Paired predictions require equal nonempty lengths')
    if any(type(t) is not int or t not in (0, 1) for t in truth):
        raise ValueError('Only explicit binary human labels can be compared')
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
           for p in [*before, *after]):
        raise ValueError('Scores must be finite probabilities')
    counts = [dict(tp=0, tn=0, fp=0, fn=0) for _ in range(2)]
    new_misses, new_false_positives, recovered = [], [], []
    for i, (target, a, b) in enumerate(zip(truth, before, after)):
        for metrics, score in zip(counts, (a, b)):
            predicted = int(score >= .5)
            metrics[('t' if predicted == target else 'f') + ('p' if predicted else 'n')] += 1
        was, now = int(a >= .5) == target, int(b >= .5) == target
        if was and not now:
            (new_misses if target else new_false_positives).append(i)
        elif not was and now:
            recovered.append(i)
    a, b = counts
    predictions = {int(p >= .5) for p in after}
    constant = next(iter(predictions)) if len(predictions) == 1 else None
    both_classes = len(set(truth)) == 2
    improved = (b['fn'] <= a['fn'] and b['fp'] <= a['fp']
                and (b['fn'] < a['fn'] or b['fp'] < a['fp']))
    return dict(before=a, after=b, new_misses=new_misses,
                new_false_positives=new_false_positives, recovered=recovered,
                aggregate_improved=improved,
                both_classes_evaluated=both_classes,
                constant_prediction=constant,
                informative_improvement=improved and both_classes and constant is None,
                no_new_errors=not new_misses and not new_false_positives)


def compare_runs(before_rows, before_scores, after_rows, after_scores, label):
    """Compare identical evidence by ID; never silently drop newly labelled rows."""
    def index(rows, scores):
        if len(rows) != len(scores):
            raise ValueError('Row and score lengths differ')
        out = {}
        for row, score in zip(rows, scores):
            key = row['id']
            if key in out:
                raise ValueError('Duplicate comparison ID')
            out[key] = (row, score)
        return out
    a, b = index(before_rows, before_scores), index(after_rows, after_scores)
    if a.keys() != b.keys():
        raise ValueError('Comparison populations differ; freeze a shared cohort first')
    ids = sorted(a)
    for key in ids:
        old, new = a[key][0], b[key][0]
        fields = ('group', 'side', 'split', 'image_sha256', 'card_box', 'box')
        if any(old[field] != new[field] for field in fields):
            raise ValueError('Comparison evidence changed: ' + key)
        if old['labels'][label] != new['labels'][label]:
            raise ValueError('Human truth changed: ' + key)
    result = compare_predictions([a[k][0]['labels'][label] for k in ids],
                                 [a[k][1] for k in ids], [b[k][1] for k in ids])
    result['ids'] = ids
    return result
