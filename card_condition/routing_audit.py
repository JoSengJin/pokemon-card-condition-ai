"""Offline listing-level check of a hypothetical Gemini bypass rule."""
import hashlib
import json
import math
from pathlib import Path

from .data import LABELS
from .side_experiment import side_rows


def threshold_analysis(predictions):
    """Validation-only operating points, never a production threshold selector."""
    result = {}
    for key in LABELS:
        known = [(p['labels'][key], p['probabilities'][key]) for p in predictions
                 if p['labels'][key] is not None]
        positives = sum(truth == 1 for truth, _ in known)
        negatives = len(known) - positives
        thresholds = sorted({0., .5, 1., *(value for _, value in known),
                             math.nextafter(max((value for _, value in known), default=1.), math.inf)})
        points = []
        for threshold in thresholds:
            tp = sum(truth == 1 and value >= threshold for truth, value in known)
            fp = sum(truth == 0 and value >= threshold for truth, value in known)
            fn, tn = positives - tp, negatives - fp
            points.append({'threshold': threshold, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
                           'precision': tp / (tp + fp) if tp + fp else None,
                           'recall': tp / positives if positives else None,
                           'false_positive_rate': fp / negatives if negatives else None,
                           'miss_rate': fn / positives if positives else None})
        both_classes = bool(positives and negatives)
        result[key] = {'positive': positives, 'negative': negatives,
                       'unknown': len(predictions) - len(known), 'both_classes_present': both_classes,
                       'points': points,
                       'zero_miss_candidate': min((p for p in points if p['fn'] == 0),
                                                  key=lambda p: (p['fp'], -p['threshold'])) if both_classes else None,
                       'zero_false_positive_candidate': min((p for p in points if p['fp'] == 0),
                                                            key=lambda p: (p['fn'], p['threshold'])) if both_classes else None}
    return result


def routing_audit(manifest, report_path, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    report = json.loads(Path(report_path).read_text())
    if report.get('evaluation_kind') != 'validation' or report.get('manifest_sha256') != hashlib.sha256(Path(manifest).read_bytes()).hexdigest():
        raise ValueError('Expected a validation report from this snapshot')
    if set(report.get('supported', [])) != set(LABELS):
        raise ValueError('All five condition outputs must be trained before routing analysis')
    rows, _, _ = side_rows(manifest, splits={'val'})
    predictions = report['predictions']
    if len(predictions) != len(rows) or {p['id'] for p in predictions} != {r['id'] for r in rows}:
        raise ValueError('Validation predictions do not match the snapshot')
    by_id = {p['id']: p for p in predictions}
    cards = {}
    for row in rows:
        prediction = by_id[row['id']]
        if prediction['labels'] != row['labels']:
            raise ValueError('Validation labels differ from the snapshot')
        values = prediction['probabilities']
        if set(values) != set(LABELS) or any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in values.values()):
            raise ValueError('Invalid validation probabilities')
        cards.setdefault(row['card_id'], {})[row['id'].rsplit('/', 1)[1]] = prediction
    thresholds = (.5, .6, .7, .8, .9)
    trials = []
    for threshold in thresholds:
        candidate_ids, known_unsafe, unknown, visibly_clean = [], [], [], []
        for card_id, sides in cards.items():
            if set(sides) != {'front', 'back'}:
                continue
            pair = tuple(sides.values())
            if any(p['probabilities']['gradable'] < threshold or
                   any(p['probabilities'][k] >= .5 for k in LABELS[1:]) for p in pair):
                continue
            candidate_ids.append(card_id)
            labels = [p['labels'] for p in pair]
            if any(l['gradable'] == 0 or any(l[k] == 1 for k in LABELS[1:]) for l in labels):
                known_unsafe.append(card_id)
            elif any(l[k] is None for l in labels for k in LABELS):
                unknown.append(card_id)
            else:
                visibly_clean.append(card_id)
        trials.append({'gradable_threshold': threshold, 'defect_threshold': .5,
                       'hypothetical_candidates': len(candidate_ids),
                       'known_unsafe': len(known_unsafe), 'unknown': len(unknown),
                       'visibly_clean': len(visibly_clean),
                       'candidate_ids': candidate_ids, 'known_unsafe_ids': known_unsafe})
    result = {'evaluation_kind': 'validation_routing_audit', 'validation_cards': len(cards),
              'two_sided_cards': sum(set(sides) == {'front', 'back'} for sides in cards.values()),
              'trials': trials, 'actual_calls_saved': 0, 'production_ready': False,
              'per_label_threshold_analysis': threshold_analysis(predictions),
              'requires_gemini': True,
              'limitations': ['These are reused model-selection cases, not an independent test.',
                              'Visible cleanliness does not establish hidden condition or card authenticity.',
                              'Threshold candidates reuse validation labels and require fresh final evaluation before adoption.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
