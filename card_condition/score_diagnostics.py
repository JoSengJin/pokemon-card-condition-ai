"""Ranking and abstention diagnostics on verified, reused validation labels."""

from .quality_rates import error_rates


def group_abstention(predictions, key, low, high):
    """Count physical cards even when every known region is deferred."""
    groups = {}
    for row in predictions:
        cells = groups.setdefault(row['group'], dict(known=0, unknown=0, deferred_known=0,
            tp=0, tn=0, fp=0, fn=0))
        truth = row['labels'][key]
        if truth is None:
            cells['unknown'] += 1
            continue
        cells['known'] += 1
        value = row['probabilities'][key]
        if low <= value < high:
            cells['deferred_known'] += 1
            continue
        prediction = int(value >= high)
        kind = ('t' if truth == prediction else 'f') + ('p' if prediction else 'n')
        cells[kind] += 1
    for cells in groups.values():
        accepted = sum(cells[k] for k in ('tp', 'tn', 'fp', 'fn'))
        cells.update(accepted=accepted,
            coverage_known=accepted/cells['known'] if cells['known'] else None,
            risk_known=(cells['fp']+cells['fn'])/accepted if accepted else None)
    return groups


def score_diagnostics(predictions, supported):
    results = {}
    for key in supported:
        known = [(p['labels'][key], p['probabilities'][key], p['group'])
                 for p in predictions if p['labels'][key] is not None]
        positive = sum(t == 1 for t, _, _ in known)
        negative = len(known) - positive
        tp = fp = 0
        points = [dict(threshold=None, precision=None, recall=0 if positive else None,
                       false_positive_rate=0 if negative else None)]
        average_precision = auc = previous_recall = previous_fpr = 0.0
        for threshold in sorted({v for _, v, _ in known}, reverse=True):
            tp += sum(t == 1 and v == threshold for t, v, _ in known)
            fp += sum(t == 0 and v == threshold for t, v, _ in known)
            recall = tp / positive if positive else 0
            fpr = fp / negative if negative else 0
            precision = tp / (tp + fp)
            average_precision += (recall - previous_recall) * precision
            auc += (fpr - previous_fpr) * (recall + previous_recall) / 2
            points.append(dict(threshold=threshold, precision=precision,
                recall=recall if positive else None, false_positive_rate=fpr if negative else None))
            previous_recall, previous_fpr = recall, fpr
        trials = []
        for low, high in ((.1, .9), (.2, .8), (.3, .7), (.4, .6), (.5, .5)):
            accepted = [(t, int(v >= high), g) for t, v, g in known if v < low or v >= high]
            groups = {}
            for truth, prediction, group in accepted:
                groups.setdefault(group, []).append(int(truth != prediction))
            errors = sum(t != p for t, p, _ in accepted)
            by_group = group_abstention(predictions, key, low, high)
            trials.append(dict(by_group=by_group,
                zero_accepted_known_groups=sum(c['known'] > 0 and c['accepted'] == 0 for c in by_group.values()),
                normal_below=low, defect_at_least=high, accepted=len(accepted),
                deferred_known=len(known)-len(accepted), coverage_known=len(accepted)/len(known) if known else None,
                errors=errors, risk_known=errors/len(accepted) if accepted else None,
                false_clean=sum(t == 1 and p == 0 for t, p, _ in accepted),
                false_defect=sum(t == 0 and p == 1 for t, p, _ in accepted),
                accepted_groups=len(groups),
                mean_group_risk=sum(sum(v)/len(v) for v in groups.values())/len(groups) if groups else None))
        predicted_defect = sum(v >= .5 for _, v, _ in known)
        correct_normal = sum(t == 0 and v < .5 for t, v, _ in known)
        correct_defect = sum(t == 1 and v >= .5 for t, v, _ in known)
        warning = ('both_truth_classes_required' if not positive or not negative else
                   'all_known_predicted_defect' if predicted_defect == len(known) else
                   'all_known_predicted_normal' if predicted_defect == 0 else None)
        results[key] = dict(rates_at_05=error_rates(dict(tp=correct_defect,tn=correct_normal,
            fp=negative-correct_normal,fn=positive-correct_defect)), prediction_distribution_at_05=dict(normal=len(known)-predicted_defect,
            defect=predicted_defect), warning_at_05=warning,
            balanced_accuracy_at_05=(correct_normal/negative+correct_defect/positive)/2
                if positive and negative else None,
            known=len(known), unknown=len(predictions)-len(known),
            positive=positive, negative=negative, groups=len({g for _, _, g in known}),
            auroc=auc if positive and negative else None,
            average_precision=average_precision if positive and negative else None,
            all_positive_baseline=dict(tp=positive, fp=negative, tn=0, fn=0),
            all_negative_baseline=dict(tp=0, fp=0, tn=negative, fn=positive),
            ranking_points=points, abstention_trials=trials)
    return results
