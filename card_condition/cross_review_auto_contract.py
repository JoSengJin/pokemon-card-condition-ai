"""Shared bounded-review schema and immutable limits."""

CODEX_TOKEN_BUDGET = 100000
CODEX_TIMEOUT = 600
EXPERIMENT_TIMEOUT = 1800
CODEX_PROMPT_BYTES = {'verify': 32000, 'correct': 32000, 'implement': 32000}
CODEX_CONTEXT_VERSION = 'bounded-v10-app-server'
class CodexBudgetExceeded(ValueError):
    pass


TEXT = {'type': 'string'}


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def array(items):
    return dict(type='array', items=items)


EXPERIMENT = obj({k: TEXT for k in ('hypothesis_id', 'cause', 'smallest_experiment', 'success_criterion', 'failure_criterion')})
ACCEPTANCE = obj(dict(max_fp={'type': 'integer', 'minimum': 0}, max_fn={'type': 'integer', 'minimum': 0},
                      no_new_errors={'type': 'boolean'}, require_actual_point_guard={'type': 'boolean'}))
PARAMETER = obj(dict(name=TEXT, baseline={'type':'number'}, value={'type':'number'}, scope=TEXT))
CRITIQUE_REPLY=obj(dict(critique_id=TEXT,disposition={'type':'string','enum':['accept','reject','needs_evidence']},rationale=TEXT,evidence_ids=array(TEXT)))
RATINGS = obj(dict(**{k:{'type':'integer','minimum':0,'maximum':100} for k in ('reliability','logic','response','independence')}, evidence_ids=array(TEXT)))
VERDICT = obj(dict(critique_responses=array(CRITIQUE_REPLY),action={'type': 'string', 'enum': ['select', 'second', 'stop', 'wait']}, rationale=TEXT,
                   evidence_ids=array(TEXT), new_question=TEXT, failed_hypotheses_checked=array(TEXT),
                   code_checks=array(obj({k: TEXT for k in ('path', 'sha256', 'quote', 'conclusion')})),
                   implementation_files=array(TEXT), experiment=EXPERIMENT, acceptance=ACCEPTANCE,
                   experiment_parameter=PARAMETER,
                   debate_assessment=obj(dict(advocate=RATINGS,skeptic=RATINGS,unresolved_issues=array(TEXT),revision_required={'type':'boolean'})),
                   review_claims=obj(dict(completed_diagnostic_ids=array(TEXT),missing_evidence_ids=array(TEXT),gemini_required_for_select={'type':'boolean'}))))
IMPLEMENTATION = obj(dict(judge_issue_responses=array(obj(dict(issue=TEXT,plan_quote=TEXT,rationale=TEXT))),final_decision={'type':'string','enum':['proceed','stop','wait']},final_rationale=TEXT,edits=array(obj({k: TEXT for k in ('path', 'before_sha256', 'old', 'new')})), worker=TEXT))
PROTECTED = {'experiment_record.py', 'regression_audit.py', 'review.py'}


class VerdictValidationError(ValueError):
    def __init__(self,errors):
        self.errors=errors
        super().__init__('; '.join(item['check']+': '+item['error'] for item in errors))


class UntrustedExecutionError(ValueError):
    pass
