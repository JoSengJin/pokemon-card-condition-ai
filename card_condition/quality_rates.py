"""Unweighted rates on explicitly scored labels, never whole-card accuracy."""


def error_rates(counts):
    if (set(counts) != {'tp','tn','fp','fn'}
            or any(type(v) is not int or v < 0 for v in counts.values())):
        raise ValueError('Expected four non-negative integer confusion counts')
    positive, negative = counts['tp']+counts['fn'], counts['tn']+counts['fp']
    scored = positive+negative
    return dict(positive=positive,negative=negative,scored=scored,
        false_negative_rate=counts['fn']/positive if positive else None,
        false_positive_rate=counts['fp']/negative if negative else None,
        accuracy=(counts['tp']+counts['tn'])/scored if scored else None)


def rate_change(reference, candidate):
    """Caller must first verify identical scored photos/geometry/truth."""
    before, after = error_rates(reference), error_rates(candidate)
    if any(before[k] != after[k] for k in ('positive','negative')):
        raise ValueError('Scored class denominators differ; comparison refused')
    delta = {k:100*(after[k]-before[k]) if before[k] is not None else None
             for k in ('false_negative_rate','false_positive_rate','accuracy')}
    return dict(reference=before,candidate=after,change_percentage_points=delta,
        errors_jointly_improved=all(delta[k] is not None and delta[k] <= 0
            for k in ('false_negative_rate','false_positive_rate'))
            and any(delta[k] is not None and delta[k] < 0
                for k in ('false_negative_rate','false_positive_rate')))
