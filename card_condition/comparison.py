"""Compare frozen validation reports from the exact same dataset."""
import hashlib
import json
import math
from .score_diagnostics import score_diagnostics
from .quality_rates import error_rates, rate_change
from .defect_regressions import defect_regressions
from pathlib import Path

from .data import LABELS, load_manifest
from .listing_readiness import listing_readiness
from .routing_audit import threshold_analysis
from .side_experiment import score, side_rows
from .region_dataset import region_rows
from .regions import REGION_LABELS
from .region_thresholds import group_error_rates, region_threshold_analysis


def compare_validation(manifest, reports, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    if len(reports) < 2:
        raise ValueError('Provide at least two validation reports')
    rows, _, _ = side_rows(manifest, splits={'val'})
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    compared = []
    for path in reports:
        report = json.loads(Path(path).read_text())
        if report.get('evaluation_kind') != 'validation' or report.get('manifest_sha256') != digest:
            raise ValueError('Compare validation reports from the same snapshot only')
        if set(report.get('supported', [])) != set(LABELS):
            raise ValueError('All five outputs must be supported for this comparison')
        predictions = report['predictions']
        by_id = {p['id']: p for p in predictions}
        if len(predictions) != len(rows) or set(by_id) != {r['id'] for r in rows}:
            raise ValueError('Validation prediction IDs differ')
        ordered = [by_id[r['id']] for r in rows]
        for row, prediction in zip(rows, ordered):
            if prediction['labels'] != row['labels']:
                raise ValueError('Validation labels differ')
            values = prediction['probabilities']
            if set(values) != set(LABELS) or any(type(v) not in (float, int) or not math.isfinite(v)
                                               or not 0 <= v <= 1 for v in values.values()):
                raise ValueError('Invalid validation probabilities')
        metrics, _ = score(rows, [[p['probabilities'][k] for k in LABELS] for p in ordered], LABELS)
        if metrics != report['metrics']:
            raise ValueError('Reported metrics do not match predictions')
        compared.append({'report': str(Path(path).resolve()),
                         'report_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                         'backbone_name': report.get('backbone_name', 'mobilenet_v3_small'),
                         'mode': report['mode'], 'fine_tune_last': report.get('fine_tune_last', False),
                         'balance': report.get('balance', False),
                         'best_validation_loss': report['best_validation_loss'],
                         'metrics_at_05': metrics,
                         'rates_at_05': {k:error_rates(v) for k,v in metrics.items()},
                         'rate_change_from_reference_at_05': {k:rate_change(
                             compared[0]['metrics_at_05'][k] if compared else v,v) for k,v in metrics.items()}, 'threshold_analysis': threshold_analysis(ordered)})
    result = {'evaluation_kind': 'validation_comparison', 'manifest_sha256': digest,
              'n_sides': len(rows), 'models': compared, 'requires_gemini': True,
              'production_ready': False, 'actual_calls_saved': 0,
              'limitations': ['Reused model-selection cases; no final performance claim.',
                             'No automatic winner or production threshold is selected.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result


def compare_regions(manifest, reports, output, references=(), point_grid=False):
    """Verify patch identity and recalculate errors before comparing models."""
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    if len(reports) < 2:
        raise ValueError('Provide at least two region validation reports')
    def validation_rows(path):
        if point_grid:
            from .point_dataset import point_rows
            patches, _ = point_rows(path, grid=True)
            return [p for p in patches if p['split'] == 'val']
        return region_rows(path, splits={'val'})[0]
    rows = validation_rows(manifest)
    listings = load_manifest(manifest, splits={'val'}, require_gradable=False)
    by_id = {row['id']: row for row in rows}
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    manifests = {digest: str(Path(manifest).resolve())}
    identity = lambda patches: {p['id']: {k: p[k] for k in
        ('labels', 'group', 'side', 'area', 'box', 'card_box', 'image_sha256')} for p in patches}
    for reference in references:
        previous = validation_rows(reference)
        if identity(previous) != identity(rows):
            raise ValueError('Reference validation regions differ; training-only changes are required')
        manifests[hashlib.sha256(Path(reference).read_bytes()).hexdigest()] = str(Path(reference).resolve())
    compared, expected_supported = [], None
    for path in reports:
        report = json.loads(Path(path).read_text())
        supported = report.get('supported')
        if (report.get('evaluation_kind') != ('point_validation' if point_grid else 'region_validation') or report.get('manifest_sha256') not in manifests
                or not isinstance(supported, list) or not supported
                or any(type(key) is not str or key not in REGION_LABELS for key in supported) or len(set(supported)) != len(supported)):
            raise ValueError('Compare supported region validation reports from a registered snapshot only')
        if expected_supported is not None and set(supported) != expected_supported:
            raise ValueError('Supported region targets differ')
        expected_supported = set(supported)
        predictions = report['predictions']
        if len(predictions) != len(by_id) or {p['id'] for p in predictions} != set(by_id):
            raise ValueError('Validation region IDs differ')
        metrics = {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported}
        breakdown, groups, errors = {}, {}, []
        for prediction in predictions:
            row = by_id[prediction['id']]
            if any(prediction.get(key) != row[key] for key in
                   ('labels', 'group', 'side', 'area', 'box', 'card_box', 'image_sha256')):
                raise ValueError('Validation region labels, group or image geometry differ')
            values = prediction['probabilities']
            if set(values) != set(REGION_LABELS) or any(
                    (type(values[key]) not in (float, int) or not math.isfinite(values[key])
                     or not 0 <= values[key] <= 1) if key in supported else values[key] is not None
                    for key in REGION_LABELS):
                raise ValueError('Invalid region probabilities')
            group_side = row['group'] + '/' + row['side']
            cells = breakdown.setdefault(group_side, {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported})
            group_cells = groups.setdefault(row['group'], {key: dict(tp=0, tn=0, fp=0, fn=0) for key in supported})
            for key in supported:
                truth = row['labels'][key]
                if truth is None:
                    continue
                pred = int(values[key] >= .5)
                kind = ('t' if truth == pred else 'f') + ('p' if pred else 'n')
                metrics[key][kind] += 1
                cells[key][kind] += 1
                group_cells[key][kind] += 1
                if truth != pred:
                    errors.append({'id': row['id'], 'group': row['group'], 'side': row['side'],
                                   'area': row['area'], 'label': key, 'truth': truth,
                                   'probability': values[key], 'kind': kind})
        if metrics != report['metrics']:
            raise ValueError('Reported region metrics do not match predictions')
        compared.append({'report': str(Path(path).resolve()),
                         'manifest_sha256': report['manifest_sha256'],
                         'report_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                         'architecture': report['architecture'], 'group_balance': report.get('group_balance', False),
                         'balance': report.get('balance', False), 'positive_weights': report.get('positive_weights'),
                         'epochs': report['epochs'], 'selected_epoch': report['selected_epoch'],
                         'selection_metric': report.get('selection_metric'),
                         'balanced_selection': report.get('balanced_selection',False),
                         'elapsed_seconds': report['elapsed_seconds'], 'metrics_at_05': metrics,
                         'rates_at_05': {k:error_rates(v) for k,v in metrics.items()},
                         'rate_change_from_reference_at_05': {k:rate_change(
                             compared[0]['metrics_at_05'][k] if compared else v,v) for k,v in metrics.items()},
                         'defect_regressions_from_reference': defect_regressions(
                             compared[0]['errors'] if compared else errors, errors, supported),
                         'by_group_side': breakdown, 'by_group': groups,
                         'group_error_rates_at_05': group_error_rates(groups, supported), 'errors': errors,
                         'image_size': report.get('image_size', 224),
                         'fine_tune_spatial': report.get('fine_tune_spatial', False),
                         'score_diagnostics': score_diagnostics(predictions, supported),
                         'listing_readiness': listing_readiness(listings, predictions, supported),
                         'threshold_analysis': region_threshold_analysis(predictions, supported)})
    result = {'evaluation_kind': 'point_validation_comparison' if point_grid else 'region_validation_comparison', 'manifest_sha256': digest,
              'regions': len(rows), 'groups': len({r['group'] for r in rows}), 'models': compared,
              'validated_manifests': manifests,
              'requires_gemini': True, 'production_ready': False, 'actual_calls_saved': 0,
              'limitations': ['Reused model-selection data; no final performance claim.',
                             'Group rates average within-card patch errors, not whole-card grading accuracy.',
                             'Disagreement does not invalidate human labels; no automatic relabeling.',
                             'No winner, routing threshold or purchase decision is selected.',
                             'Ranking and abstention scores reuse validation; no calibration or statistical guarantee.',
                             'Coverage/risk are for known patch labels only, not whole listings or Gemini calls saved.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return result
