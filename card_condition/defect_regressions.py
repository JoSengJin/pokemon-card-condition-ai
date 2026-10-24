"""Paired defect misses from identity-validated comparison errors only."""


def defect_regressions(reference_errors, candidate_errors, supported):
    result = {}
    for label in supported:
        old = {r['id']: r for r in reference_errors if r['label'] == label and r['kind'] == 'fn'}
        new = {r['id']: r for r in candidate_errors if r['label'] == label and r['kind'] == 'fn'}
        added, recovered, persistent = new.keys()-old.keys(), old.keys()-new.keys(), old.keys() & new.keys()
        fp_before = sum(r['label'] == label and r['kind'] == 'fp' for r in reference_errors)
        fp_after = sum(r['label'] == label and r['kind'] == 'fp' for r in candidate_errors)
        result[label] = dict(
            newly_missed=[new[k] for k in sorted(added)],
            recovered=[old[k] for k in sorted(recovered)],
            still_missed=[new[k] for k in sorted(persistent)],
            new_miss_count=len(added), recovered_count=len(recovered), persistent_miss_count=len(persistent),
            false_positive_change=fp_after-fp_before,
            recall_improvement_without_regression=bool(recovered and not added and fp_after <= fp_before),
            severity_known=False, production_ready=False)
    return result
