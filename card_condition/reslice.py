"""Recount validation errors after diagnostic-only annotation edits."""
import hashlib
import json
from pathlib import Path

import torch

from .data import LABELS
from .side_experiment import score, side_rows, visibility_report


def reslice(reference, updated, report_path, checkpoint, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new report path')
    report = json.loads(Path(report_path).read_text())
    if report.get('evaluation_kind') != 'validation' or report.get('manifest_sha256') != hashlib.sha256(Path(reference).read_bytes()).hexdigest():
        raise ValueError('Expected a validation report from the reference snapshot')
    meta = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if meta.get('manifest_sha256') != report['manifest_sha256']:
        raise ValueError('Checkpoint does not match the validation report')
    old, old_skipped, _ = side_rows(reference, splits={'train', 'val'})
    new, new_skipped, _ = side_rows(updated, splits={'train', 'val'})
    if old_skipped != new_skipped:
        raise ValueError('Annotated side coverage changed; run a new experiment')
    def inputs(rows):
        return {r['id']: (r['split'], r['group'], r['image'], r['box'], r['labels'], r['_image_hashes']) for r in rows}
    if inputs(old) != inputs(new):
        raise ValueError('Training or validation inputs changed; run a new experiment')
    if sorted({h for r in new for h in r['_image_hashes']}) != sorted(meta.get('development_image_hashes', [])):
        raise ValueError('Image pixels differ from the checkpoint; run a new experiment')
    validation = [r for r in new if r['split'] == 'val']
    predictions = report['predictions']
    if len(predictions) != len(validation) or {p['id'] for p in predictions} != {r['id'] for r in validation}:
        raise ValueError('Validation predictions do not match the snapshot')
    by_id = {p['id']: p for p in predictions}
    if any(by_id[r['id']]['labels'] != r['labels'] for r in validation):
        raise ValueError('Validation labels changed; run a new experiment')
    supported = report['supported']
    probabilities = [[by_id[r['id']]['probabilities'][k] for k in LABELS] for r in validation]
    metrics, _ = score(validation, probabilities, supported)
    if metrics != report['metrics']:
        raise ValueError('Overall validation metrics changed; run a new experiment')
    diagnostics = visibility_report(new, probabilities, supported)
    updated_report = dict(report, **diagnostics,
                          manifest_sha256=hashlib.sha256(Path(updated).read_bytes()).hexdigest(),
                          resliced_from_report_sha256=hashlib.sha256(Path(report_path).read_bytes()).hexdigest(),
                          resliced_without_retraining=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(updated_report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return {'output': str(output), **diagnostics, 'resliced_without_retraining': True,
            'requires_gemini': True, 'production_ready': False}
