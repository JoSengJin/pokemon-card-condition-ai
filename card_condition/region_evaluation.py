"""Evaluate a frozen region model on unseen test cards; never fit or tune here."""
from pathlib import Path

import torch

from .evaluation_inputs import track_photos, reject_copied_test_groups, unchanged_inputs, development_sets, matched_model
from .evaluation_output import write_new_report
from .point_probe import digest
from .quality_rates import error_rates
from .physical_uncertainty import physical_uncertainty
from .data import load_manifest
from .region_dataset import region_rows
from .point_dataset import point_rows
from .region_model import RegionAnalyzer
from .region_thresholds import group_error_rates


def evaluate_regions(manifest, checkpoint, output, history, device='auto'):
    if not history:
        raise ValueError('최종평가에는 모든 이전 개발 manifest를 --history로 제공하세요.')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    input_hashes = {str(Path(path).resolve()):digest(path) for path in (manifest,checkpoint,*history)}
    meta = torch.load(checkpoint, map_location="cpu", weights_only=True)
    point_grid = isinstance(meta, dict) and meta.get("architecture") in tuple(
        name + suffix for name in ("mobilenet_v3_small", "resnet18")
        for suffix in ("_point_grid_v1", "_point_edge_views_v1",
                       "_point_edge_tiles_v1", "_point_edge_tiles_max_v1", "_point_surface_tiles_v1"))
    records = load_manifest(manifest, require_gradable=not point_grid)
    if any(row['split'] != 'test' for row in records):
        raise ValueError('Final evaluation requires a separate test-only manifest')
    reject_copied_test_groups(records)
    track_photos(records,input_hashes)
    groups, ids, hashes = development_sets(meta)
    receipts = []
    for path in history:
        previous = load_manifest(path, splits={'train', 'val'}, require_gradable=not point_grid)
        track_photos(previous,input_hashes)
        groups.update(row['group'] for row in previous)
        ids.update(row['id'] for row in previous)
        hashes.update(h for row in previous for h in row['_image_hashes'])
        receipts.append({'path':str(Path(path).resolve()),
                         'sha256':input_hashes[str(Path(path).resolve())]})
    conflicts = [row['id'] for row in records if row['id'] in ids or row['group'] in groups
                 or set(row['_image_hashes']) & hashes]
    if conflicts:
        raise ValueError('Development cards/images appear in test: '+', '.join(conflicts))
    skipped = []
    if point_grid:
        rows, audit = point_rows(manifest, grid=True, splits={'test'})
        missing, skipped = [], audit['skipped']
    else:
        rows, missing = region_rows(manifest, splits={'test'})
    if not rows:
        raise ValueError('No explicitly annotated test regions')
    analyzer = RegionAnalyzer(checkpoint, device)
    matched_model(analyzer, input_hashes, checkpoint)
    metrics = {key:dict(tp=0, tn=0, fp=0, fn=0) for key in meta['supported']}
    predictions, by_group, by_group_side = [], {}, {}
    for row in rows:
        result = analyzer.analyze(row['image'], row['card_box'], row['area'],
                                  [key for key, value in row['labels'].items() if value is None])
        group_counts = by_group.setdefault(row['group'], {
            key:dict(tp=0, tn=0, fp=0, fn=0) for key in metrics})
        side_counts = by_group_side.setdefault(row['group']+'/'+row['side'], {
            key:dict(tp=0, tn=0, fp=0, fn=0) for key in metrics})
        for key, counts in metrics.items():
            truth, probability = row['labels'][key], result['probabilities'][key]
            if truth is not None and probability is not None:
                pred = int(probability >= .5)
                outcome = ('t' if truth == pred else 'f')+('p' if pred else 'n')
                for cells in (counts, group_counts[key], side_counts[key]):
                    cells[outcome] += 1
        predictions.append({**row, 'probabilities':result['probabilities'], 'null_reasons':result['null_reasons']})
    if not any(sum(counts.values()) for counts in metrics.values()):
        raise ValueError("No scored supported test labels")
    unchanged_inputs(input_hashes)
    report = {'evaluation_kind':'point_final' if point_grid else 'region_final',
              'architecture':meta['architecture'], 'skipped_annotations':skipped, 'threshold':.5, 'metrics':metrics,
              'rates_at_05':{k:error_rates(v) for k,v in metrics.items()}, 'input_hashes':input_hashes,
              'n_cards':len({row['group'] for row in rows}), 'n_regions':len(rows),
              'by_group':by_group, 'by_group_side':by_group_side,
              'group_error_rates_at_05':group_error_rates(by_group, meta['supported']),
              'predictions':predictions, 'positive_faces_without_region_labels':missing,
              'history':receipts, 'model_sha256':input_hashes[str(Path(checkpoint).resolve())],
              'manifest_sha256':input_hashes[str(Path(manifest).resolve())],
              'physical_card_uncertainty':physical_uncertainty(predictions, meta['supported']),
              'requires_gemini':True, 'production_ready':False, 'actual_calls_saved':0,
              'limitations':['Caller must supply complete development history and group other photos of the same physical card.',
                             'Unknown labels are unscored; this measures labeled patches, not whole-card condition.',
                             'Do not reuse these test results for model selection or threshold tuning.']}
    write_new_report(output, report)
    return report
