"""Offline completeness of verified patch predictions, never a bypass policy."""
from .regions import REGION_LABELS, REGION_TARGET_AREAS, validate_annotations


def listing_readiness(records, predictions, supported, *, unreviewed_sides=()):
    # Called only after comparison has validated image identity, scores and labels.
    by_cell = {(p['card_id'], p['side'], p['area']): p for p in predictions}
    listings = []
    for row in records:
        if row.get('excluded'):
            continue
        annotations = validate_annotations(row.get('side_annotations', {}), row)
        cells = []
        for side in ('front', 'back'):
            annotation = annotations.get(side)
            issues = annotation.get('visibility_issues', []) if annotation else []
            glare = annotation.get('glare_areas', []) if annotation else []
            for label in REGION_LABELS:
                for area in REGION_TARGET_AREAS[label]:
                    prediction = by_cell.get((row['id'], side, area))
                    reason = ('missing_photo' if not row.get(side) else
                              'missing_card_region' if not annotation or annotation['box'] is None else
                              'observation_not_reviewed' if side in unreviewed_sides or
                              'visibility_issues' not in annotation else
                              'observation_limited' if set(issues) - {'glare'} or
                              'glare' in issues and (not glare or area in glare) else
                              'unsupported' if label not in supported else
                              'not_evaluated' if prediction is None else None)
                    value = prediction['probabilities'][label] if prediction and not reason else None
                    state = 'unknown'
                    if value is not None:
                        state = 'normal' if value < .3 else 'defect' if value >= .7 else 'unknown'
                        if state == 'unknown':
                            reason = 'score_deferred'
                    cells.append(dict(side=side, area=area, label=label, state=state,
                                      reason=reason, score=value))
        photo_reasons = {'missing_photo', 'observation_limited'}
        unknown = [c for c in cells if c['state'] == 'unknown']
        needs_photos = any(c['reason'] in photo_reasons for c in unknown)
        needs_model = any(c['reason'] not in photo_reasons for c in unknown)
        # Patch heads do not provide centering or whole-listing observability.
        blockers = ['centering_not_evaluated', 'whole_listing_observability_not_validated']
        actions = (['additional_photos_required'] if needs_photos else []) + ['gemini_review']
        listings.append(dict(id=row['id'], group=row['group'], cells=cells,
            required_region_cells=len(cells), accepted_region_cells=len(cells)-len(unknown),
            region_scope_complete=not unknown, additional_photos_required=needs_photos,
            region_model_review_required=needs_model, whole_listing_blockers=blockers,
            actions=actions, local_complete_candidate=False))
    return dict(listings=len(listings), physical_groups=len({r['group'] for r in listings}),
        region_scope_complete=sum(r['region_scope_complete'] for r in listings),
        local_complete_candidates=0, local_completion_rate=0.0 if listings else None,
        additional_photos_required=sum(r['additional_photos_required'] for r in listings),
        normal_below=.3, defect_at_least=.7, records=listings,
        production_ready=False, requires_gemini=True, actual_calls_saved=0,
        limitations=['Patch coverage alone does not establish whole-card condition; missing predictions remain unknown.',
                    'Human observation annotations mask scores; automatic glare detection is not implemented.',
                    'Missing observations never imply poor condition or a purchase rejection.',
                    'Fixed exploratory thresholds are not calibrated or approved for routing.',
                    'No centering, whole-listing observability or same-object verification is supplied.',
                    'Region-scope completion is not whole-listing completion or calls saved.'])
