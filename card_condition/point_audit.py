"""Locate human points against coarse labels without creating training targets."""
import hashlib
import json
from pathlib import Path

from .data import load_manifest
from .regions import GLARE_AREAS, validate_annotations


def point_audit(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    points = []
    for row in load_manifest(manifest, splits={'train', 'val'}, require_gradable=False):
        if row.get('excluded'):
            continue
        for side, annotation in validate_annotations(row.get('side_annotations', {}), row).items():
            for number, point in enumerate(annotation.get('defect_points', []), 1):
                left, top, right, bottom = annotation['box']
                x = sum(point['x'] >= left + i * ((right - left) / 3) for i in (1, 2))
                y = sum(point['y'] >= top + i * ((bottom - top) / 3) for i in (1, 2))
                area = GLARE_AREAS[3 * y + x]
                label = point['label']
                truth = annotation.get('region_labels', {}).get(area, {}).get(label)
                status = 'matches_positive' if truth == 1 else 'conflicts_with_normal' if truth == 0 else 'region_unknown'
                points.append({'card': row['id'], 'group': row['group'], 'split': row['split'],
                    'side': side, 'image': annotation['image'], 'point_number': number,
                    **point, 'area': area, 'region_label': truth, 'status': status,
                    'face_label': annotation['labels'][label],
                    'glare_recorded': area in annotation.get('glare_areas', [])})
    if hashlib.sha256(Path(manifest).read_bytes()).hexdigest() != digest:
        raise ValueError('Manifest changed during audit; retry with a frozen snapshot')
    result = {'evaluation_kind': 'human_point_audit', 'manifest_sha256': digest,
        'points': points, 'counts': {status: sum(p['status'] == status for p in points) for status in
            ('matches_positive', 'conflicts_with_normal', 'region_unknown')},
        'labels_modified': False, 'training_targets_created': 0,
        'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
        'limitations': ['Train/val human evidence only; test annotations are not read.',
            'Points do not describe defect extent or severity and are not training targets.',
            'Unknown coarse labels are not normal; conflicts do not invalidate human observations.',
            'Exact internal grid boundaries belong to the right/bottom area; outer boundaries stay inside.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
