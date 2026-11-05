"""Keep judge evidence bounded without changing the frozen experiment packet."""
from copy import deepcopy

from .cross_review_evidence import expand_evidence


def judge_packet(packet):
    view = deepcopy(packet)
    view['evidence'] = expand_evidence(packet['evidence'])
    for evidence_id, entry in view['evidence'].items():
        if not isinstance(entry, dict) or not isinstance(entry.get('summary'), dict):
            continue
        summary = entry['summary']
        cohorts = summary.get('required_cohorts')
        if not isinstance(cohorts, list):
            continue
        if evidence_id == 'latest_plan':
            fields = ('id', 'acceptance')
            selected = cohorts
        elif evidence_id == 'latest_result':
            fields = ('id', 'comparison', 'point_comparison', 'acceptance_passed', 'error_count')
            selected = cohorts
        elif evidence_id.startswith('failed_'):
            fields = ('id', 'acceptance_passed', 'error_count')
            selected = [cohort for cohort in cohorts if cohort.get('acceptance_passed') is not True]
        else:
            continue
        summary['required_cohorts'] = [{key: cohort[key] for key in fields if key in cohort} for cohort in selected]
    return view
