"""Read-only assessment of one sealed candidate's saved evaluations; never fit or infer."""
import json
from pathlib import Path

from .evaluation_output import write_new_report
from .evaluation_suite_inputs import matched_reports, checked_predictions
from .evaluation_suite_metrics import ROLE_QUESTIONS, confusion_counts, question_cells
from .physical_uncertainty import QUESTIONS, physical_uncertainty


def assess_suite(manifest, seal, seal_sha256, candidate, candidate_sha256, reports, output):
    import torch
    from .data import LABELS, load_manifest
    from .evaluation_inputs import unchanged_inputs
    from .point_dataset import point_rows
    from .region_dataset import region_rows
    from .side_experiment import side_rows
    from .visibility_model import visibility_rows

    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new assessment path')
    plan, frozen, found, hashes = matched_reports(candidate, candidate_sha256, seal, seal_sha256, manifest, reports)
    records = load_manifest(manifest, require_gradable=False)
    metadata = {r['id']: r for r in records}
    photo_sha256 = {r['id']: dict(zip((s for s in ('front', 'back') if r.get(s)), r['_image_hashes'])) for r in records}
    cells, sources = [], {}
    for operation, questions in ROLE_QUESTIONS.items():
        normalized, supported = [], []
        if operation in found:
            report = found[operation]
            meta = torch.load(plan['models'][operation]['file'], map_location='cpu', weights_only=True)
            if not isinstance(meta, dict):
                raise ValueError('Invalid checkpoint metadata')
            if operation == 'region_final':
                supported = meta.get('supported')
                if report.get('architecture') != meta.get('architecture'):
                    raise ValueError('Region report architecture differs from candidate')
                expected, _ = point_rows(manifest, grid=True, splits={'test'}) if report['evaluation_kind'] == 'point_final' else region_rows(manifest, splits={'test'})
            elif operation == 'side_final':
                supported = meta.get('supported')
                expected, _, _ = side_rows(manifest, splits={'test'})
                expected = [dict(r, side=r['id'].rsplit('/', 1)[1]) for r in expected]
            else:
                if meta.get('target') != 'observation_limited':
                    raise ValueError('Observation candidate target mismatch')
                supported = ['observation_limited']
                expected, _ = visibility_rows(manifest, splits={'test'})
            allowed = set(LABELS) if operation == 'side_final' else set(questions)
            if (not isinstance(supported, list) or not supported or len(set(supported)) != len(supported)
                    or any(type(q) is not str or q not in allowed for q in supported)):
                raise ValueError('Invalid supported scope in candidate metadata')
            normalized = checked_predictions(report, expected, operation, supported, photo_sha256=photo_sha256)
            measured = confusion_counts(normalized, supported)
            recorded = ({'observation_limited': report.get('summary', {}).get('metrics_at_05')}
                        if operation == 'observation_final' else report.get('metrics'))
            if json.dumps(measured, sort_keys=True) != json.dumps(recorded, sort_keys=True):
                raise ValueError('Saved raw confusion counts differ from predictions')
            sources[operation] = dict(judgment_units=len(normalized), supported=supported,
                                      model_sha256=plan['models'][operation]['sha256'])
        local = question_cells(normalized, supported, questions, metadata)
        uncertainty = physical_uncertainty(normalized, supported)
        by_cell = {(c['question'], c['side']): c for c in uncertainty['cells']}
        for cell in local:
            key = (cell['question'], cell['side'])
            cell['physical_uncertainty'] = by_cell[key]
            cell['typed_point_response'] = dict(status='unmeasured', points=None, missed_points=None) if cell['question'] in ROLE_QUESTIONS['region_final'] else None
            cell['source_role'] = operation
        cells.extend(local)
    unchanged_inputs(hashes)
    result = dict(schema_version=1, evaluation_kind='frozen_candidate_assessment', threshold=.5,
        seal_sha256=seal_sha256, candidate_sha256=candidate_sha256, manifest_sha256=frozen['manifest_sha256'],
        sources=sources, missing_roles=sorted(set(ROLE_QUESTIONS) - set(found)), input_hashes=hashes, cells=cells,
        numeric_gates=dict(c_raw_all_questions=all(c['c_numeric_condition_met'] for c in cells),
                           d1_class_quantity=all(c['d1_class_quantity_met'] for c in cells),
                           d3_card_event_bounds=all(c['physical_uncertainty']['numeric_conditions_met'] for c in cells)),
        d1_verified=False, d2_verified=False, d3_verified=False, production_ready=False,
        required_evidence=['Correct-kind actual-point response remains unmeasured; region scores cannot substitute for click response.',
                           'Human provenance, complete prior usage and pre-selection independence need separate audit.',
                           'Required experiment/regression protections must be verified for this same candidate.',
                           'Unknown subgroup metadata is disclosed, never inferred from filenames or artwork.'],
        limitations=['Only source-declared judgment units are measured; unannotated areas are not normal.',
                     'A supplied source group is treated as a physical card; identity is not independently certified.',
                     'An exposure receipt records an attempted role, not a successful independent trial.',
                     'This recomputes saved scores without model fitting, inference or threshold selection.'])
    write_new_report(output, result)
    return result
