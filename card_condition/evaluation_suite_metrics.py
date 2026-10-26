"""Fixed role assignment and raw .5 gates; no tuning and no inferred human labels."""
from .physical_uncertainty import QUESTIONS

ROLE_QUESTIONS = dict(region_final=('edge_defect', 'corner_defect', 'surface_defect'),
                      side_final=('centering_defect',), observation_final=('observation_limited',))


def confusion_counts(rows, supported):
    counts = {q: dict(tp=0, tn=0, fp=0, fn=0) for q in supported}
    for row in rows:
        for question in supported:
            truth, score = row['labels'][question], row['probabilities'][question]
            if truth is None or score is None:
                continue
            pred = int(score >= .5)
            counts[question][('t' if truth == pred else 'f') + ('p' if pred else 'n')] += 1
    return counts


def subgroup_denominators(rows, metadata, question, side):
    groups = {}
    for row in rows:
        if row['side'] != side:
            continue
        record = metadata[row['card_id']]
        categories = {}
        for dimension in ('language', 'edition'):
            value = record.get(dimension)
            if value is not None and (type(value) is not str or not value.strip()):
                raise ValueError('Language/edition metadata must be explicit nonempty strings or None')
            categories[dimension] = [value if value is not None else 'unknown']
        issues = record.get('side_annotations', {}).get(side, {}).get('visibility_issues')
        categories['capture_issues'] = sorted(set(issues)) if issues else ['declared_none' if issues == [] else 'unknown']
        for dimension, values in categories.items():
            for value in values:
                group = groups.setdefault((dimension, value), dict(units=0, unknown_units=0, groups=set(), positive=set(), negative=set()))
                truth = row['labels'][question]
                group['units'] += 1
                group['unknown_units'] += truth is None
                group['groups'].add(row['group'])
                if truth is not None:
                    group['positive' if truth else 'negative'].add(row['group'])
    return [dict(dimension=dimension, value=value, units=g['units'], unknown_units=g['unknown_units'],
                 physical_cards=len(g['groups']), positive_physical_cards=len(g['positive']),
                 negative_physical_cards=len(g['negative'])) for (dimension, value), g in sorted(groups.items())]


def question_cells(rows, supported, questions, metadata):
    cells = []
    for question in questions:
        for side in ('front', 'back'):
            part = [r for r in rows if r['side'] == side]
            available = question in supported
            known = [r for r in part if r['labels'].get(question) is not None] if available else []
            positive = [r for r in known if r['labels'][question] == 1]
            negative = [r for r in known if r['labels'][question] == 0]
            missing_positive = sum(r['probabilities'][question] is None for r in positive)
            missing_negative = sum(r['probabilities'][question] is None for r in negative)
            counts = confusion_counts(part, [question])[question] if available else dict(tp=0, tn=0, fp=0, fn=0)
            fn = counts['fn'] / len(positive) if positive and not missing_positive else None
            fp = counts['fp'] / len(negative) if negative and not missing_negative else None
            pg, ng = len({r['group'] for r in positive}), len({r['group'] for r in negative})
            c_met = len(positive) >= 20 and len(negative) >= 20 and pg >= 5 and ng >= 5
            cells.append(dict(question=question, side=side, supported=available, raw_counts=counts,
                              positive_units=len(positive), negative_units=len(negative),
                              positive_physical_cards=pg, negative_physical_cards=ng,
                              unknown_truth_units=sum(r['labels'].get(question) is None for r in part),
                              unavailable_positive_scores=missing_positive, unavailable_negative_scores=missing_negative,
                              false_negative_rate=fn, false_positive_rate=fp,
                              c_numeric_condition_met=c_met and fn is not None and fp is not None and fn <= .05 and fp <= .10,
                              d1_class_quantity_met=pg >= 30 and ng >= 30,
                              subgroups=subgroup_denominators(part, metadata, question, side) if available else []))
    return cells
