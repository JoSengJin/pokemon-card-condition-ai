"""Opt-in point crops and explicitly normal regions for a future experiment."""
import hashlib
import json
from pathlib import Path

from .data import load_manifest
from .regions import GLARE_AREAS, REGION_LABELS, region_box, validate_annotations


def point_box(card_box, point):
    """Use a third of the card per axis, shifting inward at the card boundary."""
    left, top, right, bottom = card_box
    width, height = (right-left)/3, (bottom-top)/3
    x = max(left, min(point['x']-width/2, right-width))
    y = max(top, min(point['y']-height/2, bottom-height))
    return [x, y, x+width, y+height]


def point_for_label(row, label):
    """A positive region label does not make another defect kind's click valid."""
    if label not in REGION_LABELS:
        raise ValueError('Unknown region label')
    point = row.get('point_by_label', {}).get(label)
    if point is None:
        point = row.get('point')
        if point is None or point.get('label') != label:
            return None
    if point.get('label') != label or row['labels'].get(label) != 1:
        raise ValueError('Human point must match the positive defect kind')
    return point


def point_rows(manifest, grid=False, splits=('train', 'val')):
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    patches, skipped, targets = [], [], set()
    # Localized observed defects do not establish whole-card gradability.
    for row in load_manifest(manifest, splits=set(splits), require_gradable=False):
        if row.get('excluded'):
            continue
        hashes = dict(zip([side for side in ('front','back') if row.get(side)], row['_image_hashes']))
        for side, annotation in validate_annotations(row.get('side_annotations', {}), row).items():
            base = dict(card_id=row['id'], group=row['group'], split=row['split'], side=side,
                        image=annotation['image'], image_sha256=hashes[side], card_box=annotation['box'])
            seen = set()
            for number, point in enumerate(annotation.get('defect_points', []), 1):
                key = point['label']; targets.add(key)
                if annotation['labels'][key] != 1:
                    skipped.append(dict(card=row['id'],side=side,point_number=number,reason='face_not_positive'))
                    continue
                left, top, right, bottom = annotation['box']
                col = sum(point['x'] >= left+i*((right-left)/3) for i in (1,2))
                line = sum(point['y'] >= top+i*((bottom-top)/3) for i in (1,2))
                area = GLARE_AREAS[line*3+col]
                box = region_box(annotation['box'],area) if grid else point_box(annotation['box'], point)
                identity = (key, *box)
                if identity in seen:
                    skipped.append(dict(card=row['id'],side=side,point_number=number,reason='duplicate_crop'))
                    continue
                seen.add(identity)
                patches.append({**base, 'id': f"{row['id']}/{side}/point/{number}",
                    'source': 'human_point', 'point': point, 'area':area, 'box': box,
                    'labels': {k: 1 if k == key else None for k in REGION_LABELS}})
            for area, labels in annotation.get('region_labels', {}).items():
                box = region_box(annotation['box'], area)
                normal = {k: None for k in REGION_LABELS}
                for key, value in labels.items():
                    if grid and value == 1:
                        normal[key] = 1
                        continue
                    if value != 0:
                        continue
                    overlaps = any(p['label'] == key and box[0] <= p['x'] <= box[2]
                                   and box[1] <= p['y'] <= box[3] for p in annotation.get('defect_points', []))
                    if grid and overlaps:
                        raise ValueError('Conflicting human point and normal region labels')
                    limited = (area in annotation.get('glare_areas', [])
                        or bool(set(annotation.get('visibility_issues', [])) - {'glare', 'perspective'})
                        or 'perspective' in annotation.get('visibility_issues', []) and not annotation.get('box_reviewed', False)
                        or 'glare' in annotation.get('visibility_issues', []) and not annotation.get('glare_areas'))
                    if overlaps or limited:
                        skipped.append(dict(card=row['id'],side=side,area=area,label=key,
                                            reason='point_in_normal_region' if overlaps else 'observation_limited'))
                    else:
                        normal[key] = 0
                if any(v is not None for v in normal.values()):
                    patches.append({**base, 'id': f"{row['id']}/{side}/normal/{area}",
                                    'source':'human_region' if grid else 'human_normal_region',
                                    'area':area, 'box':box, 'labels':normal})
    if grid:
        # Preserve existing human positives; points supplement missing location labels.
        merged = {}
        for patch in patches:
            identity = (patch['card_id'],patch['side'],patch['area'])
            if identity not in merged:
                merged[identity] = {**patch,'labels':dict(patch['labels']), 'point_by_label':{}}
            else:
                for key, value in patch['labels'].items():
                    previous = merged[identity]['labels'][key]
                    if previous is not None and value is not None and previous != value:
                        raise ValueError('Conflicting human point and region labels')
                    if value is not None:
                        merged[identity]['labels'][key] = value
            if patch.get('point'):
                point = patch['point']
                merged[identity]['point_by_label'].setdefault(point['label'], point)
        patches = list(merged.values())
    counts = {split: {key: {str(v): sum(p['split']==split and p['labels'][key]==v for p in patches)
                           for v in (0,1)} for key in REGION_LABELS} for split in ('train','val')}
    groups = {split: {key: {str(v): len({p['group'] for p in patches
                    if p['split']==split and p['labels'][key]==v}) for v in (0,1)}
                      for key in REGION_LABELS} for split in ('train','val')}
    missing = [dict(split=split,label=key,value=v) for key in sorted(targets)
               for split in ('train','val') for v in (0,1) if not groups[split][key][str(v)]]
    if hashlib.sha256(Path(manifest).read_bytes()).hexdigest() != digest:
        raise ValueError('Manifest changed during dataset generation')
    result = dict(evaluation_kind='point_crop_dataset', manifest_sha256=digest,
        crop_policy='fixed_3x3' if grid else 'point_centered_third',
        patches=len(patches), counts=counts, group_class_counts=groups, point_targets=sorted(targets),
        missing_classes=missing, ready_for_experiment=bool(targets) and not missing, skipped=skipped,
        labels_modified=False, requires_gemini=True, production_ready=False, actual_calls_saved=0,
        limitations=['Opt-in alternative inputs; existing region training remains unchanged.',
            'Fixed grid mode preserves explicit human region positives and adds point location evidence.',
            'Point crops inherit only their explicitly selected defect kind; all other targets stay null.',
            'Normal crops require an explicit region zero; unknowns and face zeros never generate negatives.',
            'Several points on one card are not independent cards; any future loss must balance physical groups.',
            'Different point/normal crop selection can introduce bias; class presence is not sufficient quality.',
            'No training or model selection is performed; test is not read.'])
    return patches, result


def point_dataset(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new directory')
    patches, result = point_rows(manifest)
    output.mkdir(parents=True)
    (output/'patches.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in patches))
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return result
