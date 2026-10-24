"""Prepare explicit region labels; never derive normal patches from missing labels."""
import hashlib
import json
from pathlib import Path

from .data import load_manifest
from .regions import REGION_LABELS, region_box, validate_annotations


def region_rows(manifest, splits=None):
    patches, missing = [], []
    for row in load_manifest(manifest, splits={'train', 'val'} if splits is None else splits):
        if row.get('excluded'):
            continue
        for side, annotation in validate_annotations(row.get('side_annotations', {}), row).items():
            regions = annotation.get('region_labels', {})
            for key in REGION_LABELS:
                if annotation['labels'][key] == 1 and not any(labels[key] == 1 for labels in regions.values()):
                    missing.append(row['id']+'/'+side+':'+key)
            for area, labels in regions.items():
                if all(value is None for value in labels.values()):
                    continue
                patches.append({'id':row['id']+'/'+side+'/'+area,'group':row['group'],'split':row['split'],
                                'card_id':row['id'], 'side':side,
                                'image_sha256':dict(zip([s for s in ('front','back') if row.get(s)], row['_image_hashes']))[side],
                                'image':annotation['image'],'area':area,
                                'box':region_box(annotation['box'], area), 'card_box':annotation['box'],
                                'labels':dict(labels), 'glare_recorded':area in annotation.get('glare_areas', [])})
    return patches, missing


def region_audit(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    patches, missing = region_rows(manifest)
    counts = {split: {key: {str(value): sum(p['labels'][key] == value for p in patches if p['split'] == split)
                           for value in (0, 1, None)} for key in REGION_LABELS} for split in ('train', 'val')}
    supported = [key for key in REGION_LABELS if counts['train'][key]['0'] and counts['train'][key]['1']]
    validation_missing = [key for key in supported if not (counts['val'][key]['0'] and counts['val'][key]['1'])]
    group_counts = {split: {side: {key: {str(value): len({p['group'] for p in patches
                    if p['split'] == split and p['side'] == side and p['labels'][key] == value})
                    for value in (0, 1)} for key in REGION_LABELS} for side in ('front', 'back')}
                    for split in ('train', 'val')}
    coverage_gaps = [{'split': split, 'side': side, 'label': key, 'missing_value': value}
                     for split, sides in group_counts.items() for side, labels in sides.items()
                     for key, classes in labels.items() for value in (0, 1) if not classes[str(value)]]
    result = {'evaluation_kind':'region_data_audit','counts':counts,'supported':supported,
              'group_class_counts_by_side':group_counts,'coverage_gaps':coverage_gaps,
              'ready_for_experiment':bool(supported) and not validation_missing,
              'validation_missing_classes':validation_missing,'positive_faces_without_region_labels':missing,
              'patches':patches,'manifest_sha256':hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
              'requires_gemini':True,'production_ready':False,'actual_calls_saved':0,
              'limitations':['Only explicitly reviewed regions are emitted; missing labels are not negatives.',
                             '3x3 boxes are approximate, with no perspective correction; test is not read.',
                             'Class presence alone does not establish sufficient data or model quality.',
                             'Side/class gaps are diagnostic; no labels, splits or training gates are changed.']}
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return result
