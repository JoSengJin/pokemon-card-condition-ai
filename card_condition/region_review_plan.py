"""Train-only normal-example review sampling; predictions never become labels."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from .data import load_manifest
from .region_model import RegionAnalyzer
from .regions import REGION_LABELS, REGION_TARGET_AREAS, validate_annotations


def review_plan(manifest, checkpoint, output, device='auto', skip_cards=()):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new plan path')
    rows = [row for row in load_manifest(manifest, splits={'train'}, require_gradable=False) if not row.get('excluded')]
    skip_cards = set(skip_cards)
    skip_groups = {row['group'] for row in rows if row['id'] in skip_cards}
    analyzer = RegionAnalyzer(checkpoint, device)
    coverage = {(side, key): set() for side in ('front', 'back') for key in REGION_LABELS}
    for row in rows:
        for side, annotation in validate_annotations(row.get('side_annotations', {}), row).items():
            for key in REGION_LABELS:
                if any(labels[key] == 0 for labels in annotation.get('region_labels', {}).values()):
                    coverage[side, key].add(row['group'])
    candidates = []
    for row in rows:
        if row['group'] in skip_groups:
            continue
        hashes = dict(zip([s for s in ('front', 'back') if row.get(s)], row['_image_hashes']))
        for side, annotation in row.get('side_annotations', {}).items():
            issues = set(annotation.get('visibility_issues', []))
            if (annotation['box'] is None or annotation['labels']['gradable'] != 1
                    or issues - {'glare'} or 'glare' in issues and not annotation.get('glare_areas')):
                continue
            keys = [key for key in analyzer.meta['supported'] if annotation['labels'][key] == 0
                    and not any(labels[key] == 0 for labels in annotation.get('region_labels', {}).values())
                    and not any(key in reviewed for reviewed in annotation.get('region_reviews', {}).values())]
            for area in dict.fromkeys(area for key in keys for area in REGION_TARGET_AREAS[key]):
                if area in annotation.get('glare_areas', []):
                    continue
                pending = [key for key in keys if area in REGION_TARGET_AREAS[key]
                           and annotation.get('region_labels', {}).get(area, {}).get(key) is None]
                if not pending:
                    continue
                result = analyzer.analyze(row[side], annotation['box'], area)
                for key in pending:
                    value = result['probabilities'][key]
                    if value is None:
                        continue
                    candidates.append({'id': row['id'], 'group': row['group'], 'side': side,
                        'area': area, 'label': key, 'image': row[side], 'image_sha256': hashes[side],
                        'card_box': annotation['box'], 'model_output': value,
                        'distance_from_05': abs(value - .5), 'normal_groups': len(coverage[side, key])})
    candidates.sort(key=lambda task: (task['normal_groups'], task['distance_from_05'],
                                      task['id'], task['side'], task['area'], task['label']))
    selected, groups = [], set()
    for task in candidates:
        if task['group'] not in groups:
            task['review_query'] = '?' + urlencode({'card': task['id'], 'side': task['side'],
                'area': task['area'], 'label': task['label'], 'image': task['image']})
            selected.append(task); groups.add(task['group'])
            if len(selected) == 3:
                break
    result = {'evaluation_kind': 'train_region_review_plan', 'selected': selected,
        'skip_cards': sorted(skip_cards), 'skip_groups': sorted(skip_groups),
        'candidate_targets': len(candidates), 'model_sha256': analyzer.model_sha256,
        'manifest_sha256': hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        'normal_group_counts': {side: {key: len(coverage[side, key]) for key in REGION_LABELS}
                                for side in ('front', 'back')},
        'labels_modified': False, 'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
        'limitations': ['Train-only sampling; val/test images and labels are not read.',
                       'Scarce side/target coverage first, then closeness to 0.5; scores are uncalibrated.',
                       'A face-level normal label nominates review, never establishes a normal region.',
                       'Known normal targets on a face are complete; visibility-limited areas are skipped.',
                       'Selection does not guarantee useful new labels or model improvement.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
