"""Verdict shape, critique, and assessment checks."""
from .cross_review_auto_contract import CRITIQUE_REPLY, RATINGS, VERDICT


def check_shape(root,result,verdict,require_parameter,allowed):
        if not isinstance(verdict,dict):raise ValueError('Invalid Codex verdict')
        keys=set(VERDICT['properties'])
        if not keys-{'experiment_parameter','review_claims','debate_assessment','critique_responses'} <= set(verdict) <= keys or verdict['action'] not in ('select', 'second', 'stop', 'wait'):
            raise ValueError('Invalid Codex verdict')
        if not isinstance(verdict['rationale'], str) or not verdict['rationale'].strip():
            raise ValueError('Codex must justify its verdict')


def check_critique_responses(root,result,verdict,require_parameter,allowed):
        if 'critique_responses' in verdict:
            replies=verdict['critique_responses']
            if (not isinstance(replies,list) or any(not isinstance(v,dict) or set(v)!=set(CRITIQUE_REPLY['properties'])
                    or v['disposition'] not in ('accept','reject','needs_evidence') or not isinstance(v['critique_id'],str)
                    or not isinstance(v['rationale'],str) or not v['rationale'].strip() or not isinstance(v['evidence_ids'],list)
                    or not v['evidence_ids'] or any(not isinstance(k,str) or k not in allowed for k in v['evidence_ids']) for v in replies)):
                raise ValueError('Invalid critique responses')


def check_debate_assessment(root,result,verdict,require_parameter,allowed):
        if 'debate_assessment' in verdict:
            from .cross_review_adversarial import WEIGHTS
            assessment=verdict['debate_assessment']
            if (not isinstance(assessment,dict) or set(assessment)!=set(VERDICT['properties']['debate_assessment']['properties'])
                    or type(assessment['revision_required']) is not bool
                    or not isinstance(assessment['unresolved_issues'],list)
                    or any(not isinstance(v,str) for v in assessment['unresolved_issues'])):
                raise ValueError('Invalid debate assessment')
            for side in ('advocate','skeptic'):
                rating=assessment[side]
                if (not isinstance(rating,dict) or set(rating)!=set(RATINGS['properties'])
                        or any(type(rating[k]) is not int or not 0<=rating[k]<=100 for k in WEIGHTS)
                        or not isinstance(rating['evidence_ids'],list)
                        or any(not isinstance(v,str) for v in rating['evidence_ids'])):
                    raise ValueError('Invalid independent judge ratings')


def check_claims_schema(root,result,verdict,require_parameter,allowed):
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if not isinstance(claims,dict) or set(claims)!=set(VERDICT['properties']['review_claims']['properties']):
                raise ValueError('Explicit review claims are required')


def check_claims_dependency(root,result,verdict,require_parameter,allowed):
        if require_parameter or 'review_claims' in verdict:
            claims=verdict.get('review_claims')
            if claims['gemini_required_for_select'] is not False:
                raise ValueError('Zero remaining Gemini calls does not prohibit experiment selection')
