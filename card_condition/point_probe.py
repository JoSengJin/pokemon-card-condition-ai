"""Frozen-model diagnosis on new validation cards, not final evaluation."""
import hashlib
import json
import math
from pathlib import Path

import torch

from .data import load_manifest
from .model import checked_sigmoid
from .point_dataset import point_rows
from .regions import REGION_LABELS, REGION_TARGET_AREAS
from .side_model import backbone_for
from .edge_views import patch_features


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_probe_model(checkpoint, device='cpu'):
    from .evaluation_inputs import development_sets
    from .region_head import region_head

    meta = torch.load(checkpoint, map_location='cpu', weights_only=True)
    name = meta.get('backbone_name') if isinstance(meta, dict) else None
    supported = meta.get('supported') if isinstance(meta, dict) else None
    if (name not in ('mobilenet_v3_small', 'resnet18')
            or meta.get('architecture') not in (name+'_region_v1', name+'_point_grid_v1', name+'_point_edge_views_v1', name+'_point_edge_tiles_v1', name+'_point_edge_tiles_max_v1', name+'_point_surface_tiles_v1')
            or meta.get('labels') != list(REGION_LABELS)
            or not isinstance(supported, list) or not supported
            or any(type(k) is not str or k not in REGION_LABELS for k in supported)
            or len(supported) != len(set(supported)) or not {'backbone', 'head'} <= set(meta)):
        raise ValueError('Unsupported probe checkpoint')
    edge_views = 'tiles' if meta['architecture'] == name+'_point_edge_tiles_v1' else meta['architecture'] == name+'_point_edge_views_v1'
    if meta['architecture'] == name+'_point_edge_tiles_max_v1':
        edge_views = 'tiles-max'
    surface_tiles = meta['architecture'] == name+'_point_surface_tiles_v1'
    if surface_tiles:
        edge_views = 'tiles'
        if meta.get('surface_input') != 'tiles' or supported != ['surface_defect'] or meta.get('edge_input') is not None:
            raise ValueError('Invalid surface tile checkpoint policy')
    if not surface_tiles and edge_views in ('tiles', 'tiles-max') and (meta.get('edge_input') != edge_views or supported != ['edge_defect']):
        raise ValueError('Invalid tile checkpoint policy')
    if edge_views is True and (meta.get('edge_input') != 'views' or supported != ['edge_defect']):
        raise ValueError('Invalid edge-view checkpoint policy')
    if type(meta.get('image_size', 224)) is not int or meta.get('image_size', 224) not in (224, 448):
        raise ValueError('Invalid checkpoint image_size')
    development_sets(meta)
    backbone, dimension = backbone_for(name)
    if edge_views:
        dimension *= 2
    backbone.load_state_dict(meta['backbone'], strict=True)
    head = region_head(dimension,meta.get('head_hidden',0)).eval()
    head.load_state_dict(meta['head'], strict=True)
    return meta, backbone.to(device), head.to(device), edge_views


def probe_model(checkpoint, rows, previous):
    meta, backbone, head, edge_views = load_probe_model(checkpoint)
    supported = meta['supported']
    keys = ('development_ids', 'development_groups', 'development_image_hashes')
    ids, groups, hashes = (set(meta[k]) for k in keys)
    ids.update(r['id'] for r in previous)
    groups.update(r['group'] for r in previous)
    hashes.update(h for r in previous for h in r['_image_hashes'])
    if any(r['card_id'] in ids or r['group'] in groups or r['image_sha256'] in hashes for r in rows):
        raise ValueError('Development cards/images appear in new validation probe')
    metrics = {k: dict(tp=0, tn=0, fp=0, fn=0) for k in supported}
    predictions = []
    for row in rows:
        with torch.inference_mode():
            values = checked_sigmoid(head(patch_features(backbone, row, 'cpu', edge_views, meta.get('image_size', 224))))[0].tolist()
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite probe output')
        scores = {k: values[i] if k in supported and row['labels'][k] is not None
                  and row['area'] in REGION_TARGET_AREAS[k] else None for i, k in enumerate(REGION_LABELS)}
        for key, counts in metrics.items():
            if scores[key] is not None:
                pred = int(scores[key] >= .5)
                counts[('t' if pred == row['labels'][key] else 'f')+('p' if pred else 'n')] += 1
        predictions.append({**row, 'probabilities': scores})
    if not any(sum(counts.values()) for counts in metrics.values()):
        raise ValueError('No scored supported probe labels')
    return dict(checkpoint=str(Path(checkpoint).resolve()), checkpoint_sha256=digest(checkpoint),
                architecture=meta['architecture'], image_size=meta.get('image_size', 224), metrics=metrics, predictions=predictions)


def point_probe(manifest, checkpoints, output, cards, history):
    from .evaluation_inputs import track_photos, unchanged_inputs, reject_copied_test_groups

    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    if not cards or len(cards) != len(set(cards)) or not checkpoints or not history:
        raise ValueError('Provide distinct --card IDs, checkpoints and complete --history')
    paths = [manifest, *checkpoints, *history]
    before = {str(Path(p).resolve()): digest(p) for p in paths}
    records = load_manifest(manifest, splits={'train', 'val'}, require_gradable=False)
    selected = [r for r in records if r['id'] in cards]
    if {r['id'] for r in selected} != set(cards) or any(r['split'] != 'val' for r in selected):
        raise ValueError('Every selected card must exist in val; train/test/unassigned are not probe inputs')
    reject_copied_test_groups(selected)
    previous = [r for p in history for r in load_manifest(p, splits={'train', 'val'}, require_gradable=False)]
    track_photos(records, before)
    track_photos(previous, before)
    rows, audit = point_rows(manifest, grid=True)
    rows = [r for r in rows if r['card_id'] in cards]
    if {r['card_id'] for r in rows} != set(cards):
        raise ValueError('Every selected card needs explicit observable point/region labels')
    reports = [probe_model(p, rows, previous) for p in checkpoints]
    unchanged_inputs(before)
    result = dict(evaluation_kind='new_validation_point_probe', source_sha256=digest(manifest),
        threshold=.5, cards=cards, regions=len(rows), groups=len({r['group'] for r in rows}),
        reports=reports, history=[dict(path=str(Path(p).resolve()), sha256=digest(p)) for p in history],
        skipped=[r for r in audit['skipped'] if r['card'] in cards],
        training_performed=False, final_performance_claim=False, production_ready=False,
        requires_gemini=True, actual_calls_saved=0,
        limitations=['New development validation only; do not move these cards to final test.',
            'Supply complete past development history; same physical cards must share a group.',
            'Repeated regions are not independent cards. Unknown/limited normal labels are unscored.',
            'Uncalibrated scores; no whole-card grade, purchase decision or threshold tuning.'])
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
