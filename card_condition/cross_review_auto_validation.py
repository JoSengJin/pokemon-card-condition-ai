"""Ordered verdict checks; shape errors stop dependent validation."""
from .cross_review_auto_contract import VerdictValidationError
from .cross_review_auto_sources import verify_sources
from .cross_review_auto_validation_basic import check_shape, check_critique_responses, check_debate_assessment, check_claims_schema, check_claims_dependency
from .cross_review_auto_validation_evidence import check_completed_diagnostics, check_missing_evidence, check_evidence_ids, check_failure_history, check_code_sources
from .cross_review_auto_validation_plan import check_acceptance, check_actual_point_guard, check_experiment_parameter, check_numeric_acceptance, check_second_question


def verdict_errors(root,result,verdict,require_parameter=False):
    root=root.resolve()
    verify_sources(root,result['packet'])
    from .cross_review_contract import registered_evidence
    allowed=registered_evidence(root,result['packet'])
    errors=[]
    checks=(('shape',check_shape),('critique_responses',check_critique_responses),('debate_assessment',check_debate_assessment),('claims_schema',check_claims_schema),('claims_dependency',check_claims_dependency),('completed_diagnostics',check_completed_diagnostics),('missing_evidence',check_missing_evidence),('evidence_ids',check_evidence_ids),('failure_history',check_failure_history),('code_sources',check_code_sources),('acceptance',check_acceptance),('actual_point_guard',check_actual_point_guard),('experiment_parameter',check_experiment_parameter),('numeric_acceptance',check_numeric_acceptance),('second_question',check_second_question))
    for name,check in checks:
        try:check(root,result,verdict,require_parameter,allowed)
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            errors.append(dict(check=name,error=str(error)))
            if name=='shape':break
    return errors


def validate_verdict(root,result,verdict,require_parameter=False):
    errors=verdict_errors(root,result,verdict,require_parameter=require_parameter)
    if errors:raise VerdictValidationError(errors)
