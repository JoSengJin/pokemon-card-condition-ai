"""Saved actual-point responses, bound to validated frozen manifest annotations."""
import json
import math

from .regions import REGION_LABELS, validate_annotations


def checked_typed_points(report, records, supported):
    """Never substitute a region maximum for a response at a human click."""
    if 'typed_point_predictions' not in report:
        return None
    expected, photos = {}, set()
    for row in records:
        if row.get('excluded'):
            continue
        if row['split'] != 'test':
            raise ValueError('Actual-point assessment requires the sealed test split')
        hashes = dict(zip((s for s in ('front', 'back') if row.get(s)), row['_image_hashes']))
        for side, annotation in validate_annotations(row.get('side_annotations', {}), row).items():
            for point in annotation.get('defect_points', []):
                label = point['label']
                if annotation['labels'][label] != 1:
                    continue
                geometry = json.dumps(point, sort_keys=True, allow_nan=False)
                key = (row['id'], side, label, geometry)
                physical_point = (hashes[side], label, point['x'], point['y'])
                if key in expected or physical_point in photos:
                    raise ValueError('Duplicate actual point or aliased source photo')
                photos.add(physical_point)
                expected[key] = dict(side=side, label=label, group=row['group'])
    items = report['typed_point_predictions']
    if not isinstance(items, list):
        raise ValueError('Actual-point predictions must be a list')
    normalized, seen = [], set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'card_id', 'side', 'label', 'point', 'score'}
                or any(type(item[k]) is not str for k in ('card_id', 'side', 'label'))):
            raise ValueError('Invalid actual-point prediction')
        key = (item['card_id'], item['side'], item['label'], json.dumps(item['point'], sort_keys=True, allow_nan=False))
        if key not in expected or key in seen:
            raise ValueError('Actual-point identity, kind or geometry differs from sealed source')
        score = item['score']
        if (score is not None and (type(score) not in (int, float) or not math.isfinite(score)
                                  or not 0 <= score <= 1 or item['label'] not in supported)):
            raise ValueError('Invalid or unsupported actual-point score')
        normalized.append(dict(expected[key], score=score))
        seen.add(key)
    if seen != set(expected):
        raise ValueError('Actual-point predictions omitted sealed human points')
    return normalized


def typed_point_cells(report, records, supported):
    rows = checked_typed_points(report, records, supported)
    cells = {}
    for label in REGION_LABELS:
        for side in ('front', 'back'):
            part = [r for r in rows or [] if r['label'] == label and r['side'] == side]
            missing = sum(r['score'] is None for r in part)
            missed = sum(r['score'] is not None and r['score'] < .5 for r in part)
            groups = len({r['group'] for r in part})
            rate = missed / len(part) if part and not missing else None
            cells[label, side] = dict(status='unmeasured' if rows is None else 'measured',
                points=None if rows is None else len(part), missed_points=None if rows is None else missed,
                unavailable_scores=None if rows is None else missing, physical_cards=None if rows is None else groups,
                false_negative_rate=rate,
                numeric_condition_met=bool(len(part) >= 20 and groups >= 5 and rate is not None and rate <= .05))
    return cells
