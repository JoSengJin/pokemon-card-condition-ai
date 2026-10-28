"""Explicit frozen-head readout and held-fold replay; never fits a head."""
import torch


def mean_maps(features, heads):
    if features.ndim != 3 or not heads or not torch.isfinite(features).all():
        raise ValueError('Expected finite bag/token/features and nonempty heads')
    maps = []
    for head in heads:
        coef, bias = head['coef'], head['bias']
        if coef.shape != (features.shape[-1],) or bias.numel() != 1 or not torch.isfinite(coef).all() or not torch.isfinite(bias).all():
            raise ValueError('Invalid head coefficients')
        logits = features @ coef + bias
        if not torch.isfinite(logits).all():
            raise ValueError('Nonfinite head output')
        maps.append(logits.sigmoid())
    return torch.stack(maps).mean(0)


def region_scores(maps, masks):
    if maps.shape != masks.shape or maps.ndim != 2 or masks.dtype != torch.bool or not masks.any(1).all():
        raise ValueError('Expected matching nonempty physical-token masks')
    if not torch.isfinite(maps).all() or not ((maps >= 0) & (maps <= 1)).all():
        raise ValueError('Expected finite probabilities')
    return maps.masked_fill(~masks, -torch.inf).amax(1).tolist()


def replay_maps(rows, training, features, front, back, proposal):
    plans = {p['id']: p for p in proposal['folds']}
    train_by_id = {r['id']: r for r in training}
    outputs = []
    for i, row in enumerate(rows):
        options = [h for h in front if row['id'] in plans[h['fold']]['held_ids']] if row['side'] == 'front' else [h for h in back if h['group'] == row['group']]
        if len(options) != 1:
            raise ValueError('Expected exactly one original held-fold head')
        head = options[0]
        if row['id'] in head['train_ids'] or row['group'] in {train_by_id[t]['group'] for t in head['train_ids']}:
            raise ValueError('Held-fold group leaked into training')
        if row['side'] == 'front' and head['train_ids'] != plans[head['fold']]['train_ids']:
            raise ValueError('Front fold provenance changed')
        outputs.append(mean_maps(features[i:i+1], [head])[0])
    return torch.stack(outputs)


def observations(reference, fixed, legacy, maps, masks):
    scores = region_scores(maps, masks)
    if len(scores) != len(reference['rows']):
        raise ValueError('Replay row count mismatch')
    old = fixed['point_reference']['rows']; typed = fixed['typed_point_reference']['rows']
    legacy_scores = [float(maps[r['parent_index'], int(legacy['point_tokens'][r['parent_index']])]) for r in old]
    typed_scores = [float(maps[r['parent_index'], r['human_token']]) for r in typed]
    required = []
    for cohort in reference['required_cohorts']:
        if cohort['rows'] == typed:
            values = typed_scores
        elif cohort['rows'] == old:
            values = legacy_scores
        elif cohort['rows'] == reference['rows']:
            values = scores
        else:
            raise ValueError('Unknown required cohort; cannot copy baseline scores')
        required.append(dict(id=cohort['id'], rows=cohort['rows'], scores=values,
                             point_ids=cohort['point_ids'], point_scores=values if cohort['point_ids'] else []))
    return dict(rows=reference['rows'], scores=scores, required_cohorts=required)
