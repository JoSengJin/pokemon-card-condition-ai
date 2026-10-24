"""Diagnostic threshold sweep for already verified validation predictions."""


def group_error_rates(groups, supported):
    """Each physical card has equal weight; absent classes are not zero error."""
    summary = {}
    for key in supported:
        negatives = [c[key]['fp'] / (c[key]['fp'] + c[key]['tn']) for c in groups.values()
                     if c[key]['fp'] + c[key]['tn']]
        positives = [c[key]['fn'] / (c[key]['fn'] + c[key]['tp']) for c in groups.values()
                     if c[key]['fn'] + c[key]['tp']]
        summary[key] = {'negative_groups': len(negatives), 'positive_groups': len(positives),
                        'mean_false_positive_rate': sum(negatives) / len(negatives) if negatives else None,
                        'mean_miss_rate': sum(positives) / len(positives) if positives else None}
    return summary


def region_threshold_analysis(predictions, supported):
    """Unknown labels are excluded; thresholds never change a model or routing."""
    results = []
    for threshold in (i / 10 for i in range(1, 10)):
        groups, sides = {}, {}
        total = {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported}
        for prediction in predictions:
            group = groups.setdefault(prediction['group'],
                {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported})
            side = sides.setdefault(prediction['side'],
                {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported})
            for key in supported:
                truth = prediction['labels'][key]
                if truth is None:
                    continue
                positive = int(prediction['probabilities'][key] >= threshold)
                kind = ('t' if truth == positive else 'f') + ('p' if positive else 'n')
                for cells in (total, group, side):
                    cells[key][kind] += 1
        rates = {}
        for key, cells in total.items():
            tp, tn, fp, fn = (cells[k] for k in ('tp', 'tn', 'fp', 'fn'))
            rates[key] = {
                'precision': tp / (tp + fp) if tp + fp else None,
                'recall': tp / (tp + fn) if tp + fn else None,
                'false_positive_rate': fp / (fp + tn) if fp + tn else None,
                'miss_rate': fn / (tp + fn) if tp + fn else None}
        results.append({'threshold': threshold, 'metrics': total, 'rates': rates,
                        'by_side': sides, 'group_error_rates': group_error_rates(groups, supported)})
    return results
