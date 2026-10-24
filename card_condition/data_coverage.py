"""Read-only A3 data inventory. No inference, test labels, or new truth."""
import hashlib
import json
from pathlib import Path

from .data import load_manifest
from .point_dataset import point_rows
from .regions import GLARE_AREAS, REGION_LABELS, REGION_TARGET_AREAS, validate_annotations

QUESTIONS = ('centering_defect', *REGION_LABELS, 'observation_limited')


def coverage_report(manifest):
    manifest = Path(manifest).resolve()
    source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    records = load_manifest(manifest, splits={'train', 'val'}, require_gradable=False)
    patches, projection = point_rows(manifest, grid=True)
    if projection['manifest_sha256'] != source_sha:
        raise ValueError('Manifest changed between coverage audit passes')
    expected_images = {r['id']: dict(zip([s for s in ('front', 'back') if r.get(s)], r['_image_hashes']))
                       for r in records if not r.get('excluded')}
    if projection['input_image_hashes'] != expected_images:
        raise ValueError('Input photos changed between coverage audit passes')
    projected = {(p['card_id'], p['side'], p['area']): p for p in patches}
    units, points, owners, skipped = {}, {}, {}, []
    photo_sides = {}

    def put(store, identity, item):
        previous = store.get(identity)
        if previous and (previous['target'], previous['group'], previous['card_box']) != (item['target'], item['group'], item['card_box']):
            raise ValueError('Conflicting truth, geometry or physical group for the same judgment unit')
        store.setdefault(identity, item)

    for record in records:
        if record.get('excluded'):
            continue
        hashes = dict(zip([s for s in ('front', 'back') if record.get(s)], record['_image_hashes']))
        for side, digest in hashes.items():
            if photo_sides.setdefault(digest, side) != side:
                raise ValueError('Identical decoded photo is assigned to both front and back')
        annotations = validate_annotations(record.get('side_annotations', {}), record)
        for side in ('front', 'back'):
            annotation = annotations.get(side)
            if not annotation or annotation['box'] is None:
                skipped.append(dict(card_id=record['id'], side=side, reason='missing_annotation_or_box'))
                continue
            digest = hashes[side]
            if owners.setdefault(digest, record['group']) != record['group']:
                raise ValueError('Identical decoded photo has different physical-card groups')
            base = dict(card_id=record['id'], group=record['group'], split=record['split'],
                        side=side, image=annotation['image'], image_sha256=digest,
                        reviewed_by=record.get('reviewed_by'),
                        card_box=annotation['box'], box_reviewed=annotation.get('box_reviewed', False))
            for question in QUESTIONS:
                areas = REGION_TARGET_AREAS[question] if question in REGION_LABELS else ('face',)
                for area in areas:
                    if question in REGION_LABELS:
                        patch = projected.get((record['id'], side, area))
                        target = patch['labels'][question] if patch else None
                        source = 'explicit_region_or_same_kind_point' if target is not None else 'unknown'
                    elif question == 'centering_defect':
                        target = annotation['labels'][question]
                        source = 'explicit_side_label' if target is not None else 'unknown'
                    else:
                        issues = annotation.get('visibility_issues')
                        target = 1 if issues else 0 if issues == [] and annotation['labels']['gradable'] == 1 else None
                        source = 'explicit_visibility_issues' if target is not None else 'unknown'
                    identity = (base['split'], question, side, digest, area)
                    put(units, identity, dict(base, label=question, area=area, target=target, source=source))
            for point in annotation.get('defect_points', []):
                label = point['label']
                if annotation['labels'][label] != 1:
                    skipped.append(dict(card_id=record['id'], side=side, label=label,
                                        reason='point_face_not_positive'))
                    continue
                left, top, right, bottom = annotation['box']
                col = sum(point['x'] >= left+i*((right-left)/3) for i in (1, 2))
                line = sum(point['y'] >= top+i*((bottom-top)/3) for i in (1, 2))
                area = GLARE_AREAS[line*3+col]
                if area not in REGION_TARGET_AREAS[label]:
                    skipped.append(dict(card_id=record['id'], side=side, label=label, area=area,
                                        reason='point_outside_target_area'))
                identity = (base['split'], label, side, digest, point['x'], point['y'])
                put(points, identity, dict(base, label=label, point=point, target=1))
    cells = []
    for split in ('train', 'val'):
        for question in QUESTIONS:
            for side in ('front', 'back'):
                selected = [u for u in units.values() if (u['split'], u['label'], u['side']) == (split, question, side)]
                cell = dict(split=split, label=question, side=side,
                            unit='region' if question in REGION_LABELS else 'face',
                            unknown_units=sum(u['target'] is None for u in selected))
                for target, name in ((1, 'positive'), (0, 'negative')):
                    rows = [u for u in selected if u['target'] == target]
                    groups = sorted({u['group'] for u in rows})
                    cell[name] = dict(units=len(rows), groups=len(groups), group_ids=groups,
                                      missing_units=max(0, 20-len(rows)), missing_groups=max(0, 5-len(groups)),
                                      unreviewed_box_units=sum(not u['box_reviewed'] for u in rows))
                typed = [p for p in points.values() if (p['split'], p['label'], p['side']) == (split, question, side)]
                cell['typed_positive_points'] = dict(points=len(typed), groups=len({p['group'] for p in typed}))
                cell['quantity_met'] = all(cell[k]['missing_units'] == cell[k]['missing_groups'] == 0
                                           for k in ('positive', 'negative'))
                cells.append(cell)
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != source_sha:
        raise ValueError('Manifest changed during coverage audit')
    return dict(schema_version=1, evaluation_kind='data_coverage_audit', manifest=str(manifest),
                manifest_sha256=source_sha, criteria=dict(units_per_class=20, groups_per_class=5),
                cells=cells, units=list(units.values()), typed_points=list(points.values()),
                skipped=skipped, projection_skipped=projection['skipped'], labels_modified=False,
                training_calls=0, inference_calls=0, independent=False, a3_verified=False,
                limitations=['Train and validation remain separate; train requires held-group crossfit to evaluate.',
                             'Final-test rows and images are not parsed. This is not a D1 independent-test census.',
                             'Quantity alone is not A3 completion; source/scope/geometry and evaluation support need review.',
                             'Face centering labels do not establish measured centering ratios.',
                             'No normal point truth is inferred from a region zero or an unclicked pixel.',
                             'Detailed supplemental photos require explicit source and side mapping; not silently merged.'])


def data_coverage(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    result = coverage_report(manifest)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
