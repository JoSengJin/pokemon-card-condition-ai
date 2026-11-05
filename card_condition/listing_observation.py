"""Optional face-level observation evidence; never changes region truth or routing."""
import math

from .visibility_model import VisibilityAnalyzer


def observation_evidence(records, checkpoint, device, *, analyzer=None, expected_model_sha256=None):
    if analyzer is None:
        analyzer = VisibilityAnalyzer(checkpoint, device)
    if expected_model_sha256 is not None and analyzer.model_sha256 != expected_model_sha256:
        raise ValueError('Observation analyzer loaded a different checkpoint; no listing report saved')
    faces = []
    for row in records:
        for side in ('front', 'back'):
            annotation = row.get('side_annotations', {}).get(side)
            face = dict(card_id=row['id'], group=row['group'], side=side,
                image=row.get(side), human_visibility_issues=annotation.get('visibility_issues') if annotation else None,
                human_glare_areas=annotation.get('glare_areas') if annotation else None,
                observation_limit_score=None, decision='review_required', reason=None)
            if not row.get(side):
                face['reason'] = 'missing_photo'
            elif not annotation or annotation['box'] is None:
                face['reason'] = 'missing_card_region'
            else:
                prediction = analyzer.analyze(row[side], annotation['box'], side=side)
                value = prediction['observation_limit_score']
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError('Invalid observation score; no listing report saved')
                face['observation_limit_score'] = value
                face['reason'] = 'uncalibrated_model_signal'
            faces.append(face)
    return dict(model_sha256=analyzer.model_sha256, records=faces,
        inferred_faces=sum(r['observation_limit_score'] is not None for r in faces),
        routing_changed=False, human_annotations_changed=False, region_predictions_changed=False,
        production_ready=False, requires_gemini=True, actual_calls_saved=0,
        limitations=['Face-level uncalibrated signal cannot locate a restricted region or establish card damage.',
            'Low scores cannot clear human restrictions; high scores cannot reject a listing.',
            'Missing photos/regions remain unknown. Region masking uses human annotations only.',
            'Observation evidence alone does not establish independent accuracy.'])
