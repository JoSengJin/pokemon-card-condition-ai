"""Union of model suspicions requests review, never declares a defect."""

def review_labels(primary, secondary):
    return [dict(label=key, primary_score=value, secondary_score=secondary.get(key),
                 reason='model_suspicion', action='review_required')
            for key,value in primary.items()
            if value is not None and (value >= .5 or secondary.get(key) is not None and secondary[key] >= .5)]
