"""Research-only clear/abstain decisions; deferral is never a correct detection."""
import math


def clearance_cutoff(inner_predictions):
    """Use inner out-of-group scores only; no unsupported or positive-side clearance."""
    for row in inner_predictions:
        if (type(row.get('truth')) is not int or row['truth'] not in (0, 1)
                or type(row.get('score')) not in (int, float)
                or not math.isfinite(row['score']) or not 0 <= row['score'] <= 1):
            raise ValueError('Explicit binary truth and finite probability required')
    if {r['truth'] for r in inner_predictions} != {0, 1}:
        return None
    return min(.5, min(r['score'] for r in inner_predictions if r['truth'] == 1))


def clearance_summary(predictions):
    counts = dict(limited_cleared=0, clear_cleared=0, limited_deferred=0, clear_deferred=0)
    for row in predictions:
        clearance_cutoff([row])  # Same truth/score validation; the single-row cutoff is unused.
        threshold = row.get('clearance_cutoff')
        if threshold is not None and (type(threshold) not in (int, float)
                or not math.isfinite(threshold) or not 0 <= threshold <= .5):
            raise ValueError('Clearance cutoff must be null or within [0, 0.5]')
        cleared = threshold is not None and row['score'] < threshold
        counts[('limited' if row['truth'] else 'clear') + ('_cleared' if cleared else '_deferred')] += 1
    positive = counts['limited_cleared'] + counts['limited_deferred']
    negative = counts['clear_cleared'] + counts['clear_deferred']
    total = positive + negative
    accepted = counts['limited_cleared'] + counts['clear_cleared']
    return dict(counts=counts, positive=positive, negative=negative, scored=total,
                unsafe_clearance_rate=counts['limited_cleared']/positive if positive else None,
                normal_clearance_rate=counts['clear_cleared']/negative if negative else None,
                clearance_coverage=accepted/total if total else None,
                deferred=total-accepted,
                nontrivial_research_support=bool(positive and negative and not counts['limited_cleared'] and counts['clear_cleared']),
                production_ready=False, actual_calls_saved=0)
