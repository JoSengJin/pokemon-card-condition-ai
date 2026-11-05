"""Physical-card event uncertainty at fixed .5; diagnostic, never independent-test certification."""
import math

QUESTIONS = ('edge_defect', 'corner_defect', 'surface_defect', 'centering_defect', 'observation_limited')
Z = 1.6448536269514722


def wilson_upper(events, total):
    """One-sided 95% Wilson upper bound; no samples means no estimate."""
    if type(events) is not int or type(total) is not int or not 0 <= events <= total:
        raise ValueError('Expected integer events between zero and total')
    if not total:
        return None
    rate, z2 = events / total, Z * Z
    return (rate + z2 / (2 * total) + Z * math.sqrt(
        rate * (1 - rate) / total + z2 / (4 * total * total))) / (1 + z2 / total)


def event_summary(outcomes, limit):
    """An unavailable card outcome blocks the estimate, retaining the original denominator."""
    n, unavailable = len(outcomes), outcomes.count(None)
    events = outcomes.count(True)
    upper = wilson_upper(events, n) if not unavailable else None
    return dict(physical_cards=n, observed_events=events, unavailable_cards=unavailable,
                event_rate=events / n if n and not unavailable else None,
                upper_95=upper, upper_limit=limit,
                numeric_condition_met=n >= 30 and upper is not None and upper <= limit)


def physical_uncertainty(predictions, supported, *, question_areas=None):
    """Collapse supplied judgment units by group/side/question, never by patch or photo count.

    Normal means all supplied units for that question/side are known normal. It does not
    establish an entirely normal card or coverage of unannotated regions outside the input.
    """
    groups, out_of_scope = {}, {}
    canonical_areas = {area for areas in (question_areas or {}).values() for area in areas}
    for row in predictions:
        if (not isinstance(row, dict) or type(row.get('group')) is not str or not row['group'].strip()
                or row.get('side') not in ('front', 'back')
                or not isinstance(row.get('labels'), dict) or not isinstance(row.get('probabilities'), dict)):
            raise ValueError('Uncertainty needs physical group, side, labels and probabilities')
        for question in QUESTIONS:
            if question not in supported:
                continue
            if question not in row['labels'] or question not in row['probabilities']:
                raise ValueError('Supported question missing truth or raw score')
            truth, score = row['labels'][question], row['probabilities'][question]
            if truth is not None and (type(truth) is not int or truth not in (0, 1)):
                raise ValueError('Truth must be 0, 1 or None')
            if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                raise ValueError('Raw score must be finite within [0,1] or None')
            if (truth is None and question in (question_areas or {})
                    and row.get('area') in canonical_areas and row['area'] not in question_areas[question]):
                key = (question, row['side'])
                out_of_scope[key] = out_of_scope.get(key, 0) + 1
                continue
            groups.setdefault((question, row['side']), {}).setdefault(row['group'], []).append((truth, score))
    cells = []
    for question in QUESTIONS:
        for side in ('front', 'back'):
            positive, negative, unknown_units, unknown_cards = [], [], 0, 0
            for units in groups.get((question, side), {}).values():
                unknown = sum(t is None for t, _ in units)
                unknown_units += unknown
                unknown_cards += bool(unknown)
                positives = [s for t, s in units if t == 1]
                if positives:
                    # Missing any required raw score leaves the event unmeasured, never guessed.
                    positive.append(None if None in positives else any(s < .5 for s in positives))
                elif not unknown:
                    scores = [s for _, s in units]
                    negative.append(None if None in scores else any(s >= .5 for s in scores))
            miss, false_alarm = event_summary(positive, .10), event_summary(negative, .20)
            cells.append(dict(question=question, side=side, supported=question in supported,
                              miss=miss, false_alarm=false_alarm,
                              unknown_truth_units=unknown_units, cards_with_unknown_truth=unknown_cards,
                              out_of_scope_unknown_units=out_of_scope.get((question, side), 0),
                              numeric_conditions_met=miss['numeric_condition_met'] and false_alarm['numeric_condition_met']
                              and unknown_units == 0))
    return dict(schema_version=1, threshold=.5, confidence='one-sided 95% Wilson', z=Z, cells=cells,
                all_numeric_conditions_met=all(c['numeric_conditions_met'] for c in cells),
                milestone_verified=False,
                limitations=['Caller-supplied physical groups and input judgment-unit coverage are not independently verified.',
                             'D1 sealing, D2 candidate independence and language/edition/capture subgroups require separate evidence.',
                             'Unknown truth is unscored; a normal denominator requires all applicable supplied units known normal.',
                             'Only canonical non-applicable unknown regions are excluded when question area scope is supplied.',
                             'Raw scores retain held units; these rates do not measure whole-card normality or localization.'])
