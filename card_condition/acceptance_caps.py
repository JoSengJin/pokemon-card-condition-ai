"""A cap whose denominator is zero is unmeasured, not passed (docs/agent/QUALITY_RULES.md zero-denominator-unmeasured)."""


def check_declared_counts(plan, rows, required):
    """Optional plan['evaluation_counts'] = {'primary': {'defect': n, 'normal': m}, <cohort id>: ...} must match frozen truth."""
    if 'evaluation_counts' not in plan:
        return  # Plans written before this field keep their behavior.
    actual = {'primary': rows}
    for cohort in required:
        if cohort['id'] == 'primary':
            raise ValueError('Cohort ID "primary" cannot be used with evaluation_counts')
        actual[cohort['id']] = cohort['rows']
    actual = {key: {'defect': sum(r['target'] == 1 for r in value), 'normal': sum(r['target'] == 0 for r in value)}
              for key, value in actual.items()}
    if plan['evaluation_counts'] != actual:
        raise ValueError('Declared defect/normal row counts do not match the frozen evaluation')


def cap_status(rules, counts):
    """counts: comparison['after']. Never changes acceptance_passed; it says which caps were really measured."""
    errors = {'max_fp': ('fp', 'tn'), 'max_fn': ('fn', 'tp')}
    return {cap: 'unmeasured' if counts[wrong] + counts[right] == 0 else 'passed' if counts[wrong] <= rules[cap] else 'failed'
            for cap, (wrong, right) in errors.items()}
