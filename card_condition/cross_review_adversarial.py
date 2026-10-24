"""Evidence policy over existing agent calls; scores never prove causal claims."""
from pathlib import Path
from typing import TypedDict

from .cross_review import digest, encoded
from .experiment_record import read, save, sha, project_file

WEIGHTS = dict(reliability=.35, logic=.25, response=.20, independence=.20)
from .cross_review_roles import ADVOCATE_SYSTEM,SKEPTIC_SYSTEM,JUDGE_SYSTEM
ROLE_PROMPTS = dict(advocate=ADVOCATE_SYSTEM,skeptic=SKEPTIC_SYSTEM,judge=JUDGE_SYSTEM)


class DebateState(TypedDict, total=False):
    input_key: str
    original_question: str
    current_claim: str
    round_number: int
    max_rounds: int
    advocate_arguments: dict
    skeptic_arguments: dict
    evidence_registry: dict
    verified_measurements: list
    verified_facts: list
    disputed_claims: list
    judge_feedback: dict
    judge_scores: dict
    unresolved_issues: list
    information_gain: list
    stagnation_count: int
    decision: str
    final_report: dict
    history: list
    root: str
    packet: dict
    judge: dict
    prior: dict
    errors: list
    experiment_action: str
    signature: str
    stop_reason: str


def evidence_registry(root, packet):
    root = root.resolve()
    registry = {}
    for key, item in packet.get('evidence', {}).items():
        entry = dict(status='UNVERIFIED', source_group=None, note='출처 미확인. 해석은 사실로 확정하지 않음.')
        if isinstance(item, dict) and item.get('path') and item.get('sha256'):
            try:
                path = project_file(root, item['path'])
                if sha(path) == item['sha256']:
                    entry.update(status='SOURCE_VERIFIED', path=item['path'], sha256=item['sha256'],
                                 source_group=item['sha256'], note='파일 SHA 확인. 요약·인과 해석의 참을 증명하지 않음.')
            except (OSError, ValueError):
                pass
        registry[key] = entry
    return registry


def score_arguments(assessment, registry):
    """Retain judge opinions, cap unsupported scores; missing ratings stay unknown."""
    scores = {}
    for side in ('advocate', 'skeptic'):
        supplied = assessment.get(side, {})
        refs = supplied.get('evidence_ids', [])
        valid = isinstance(refs, list) and bool(refs) and all(
            isinstance(ref, str) and registry.get(ref, {}).get('status') == 'SOURCE_VERIFIED' for ref in refs)
        groups = {registry[ref]['source_group'] for ref in refs} if valid else set()
        axes = {}
        for axis in WEIGHTS:
            value = supplied.get(axis)
            axes[axis] = min(value, 49 if not valid else 100, 49 if axis == 'independence' and len(groups) < 2 else 100) if type(value) is int and 0 <= value <= 100 else None
        total = round(sum(axes[k]*w for k, w in WEIGHTS.items()), 2) if all(v is not None for v in axes.values()) else None
        scores[side] = dict(raw=supplied, adjusted=axes, weighted_total=total,
                            reason='심판의 품질 의견. 출처 미확인/단일 원자료 점수 상한49. 사실 확률 아님.')
    return scores


def measurement_claim_text(claim):
    return '동결 JSON 명제: '+encoded({k:claim[k] for k in ('evidence_id','field','expected')})


def measured_claim(root, packet, registry):
    """Only a program-authored exact JSON-field claim can yield ACCEPT/REJECT.

    LLM causal prose never enters this predicate, and a source hash alone proves no claim.
    """
    root = root.resolve()
    claim = packet.get('machine_claim')
    if not isinstance(claim, dict) or set(claim) != {'evidence_id', 'field', 'expected'}:
        return None
    source = registry.get(claim['evidence_id'], {})
    if source.get('status') != 'SOURCE_VERIFIED' or not isinstance(claim['field'], list) or not claim['field']:
        return None
    try:
        value = read(project_file(root, source['path']))
        for key in claim['field']:
            if not isinstance(value, dict) or not isinstance(key, str) or key not in value:
                return None
            value = value[key]
        if type(value) not in (str, bool, int, float) or type(value) is not type(claim['expected']):
            return None
        return dict(evidence_id=claim['evidence_id'], field=claim['field'], expected=claim['expected'],
                    observed=value, matches=value == claim['expected'], scope='지정한 동결 JSON 필드만 판정. 인과·일반화 미검증.')
    except (OSError, ValueError, KeyError, TypeError):
        return None


def build(checkpointer=None):
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import interrupt

    def initialize(s):
        return dict(original_question=s['packet'].get('stagnation_reason', ''),
                    current_claim=s['advocate_arguments'].get('cause', ''), errors=[],
                    round_number=len(s.get('prior', {}).get('history', []))+1)

    def verify(s):
        registry = evidence_registry(Path(s['root']), s['packet'])
        fact = measured_claim(Path(s['root']), s['packet'], registry)
        bound=bool(fact and s['current_claim']==measurement_claim_text(s['packet']['machine_claim']))
        return dict(evidence_registry=registry, verified_measurements=[fact] if fact else [], verified_facts=[fact] if bound else [],
                    disputed_claims=[s['current_claim']] if s['current_claim'] and not bound else [])

    def judge(s):
        verdict = s['judge']; assessment = verdict.get('debate_assessment', {})
        prior = s.get('prior', {})
        claims = dict(advocate=s['advocate_arguments'], skeptic=s['skeptic_arguments'])
        # Same text or reworded question without fresh source IDs is not informational progress.
        cited = set(verdict.get('evidence_ids', []))
        verified_ids = sorted(k for k in cited if s['evidence_registry'].get(k, {}).get('status') == 'SOURCE_VERIFIED')
        prior_ids = {i for r in prior.get('history', []) for i in r['verified_evidence_ids']}
        gain = sorted(set(verified_ids)-prior_ids)
        signature = digest(claims)
        repeated = any(r['signature'] == signature for r in prior.get('history', []))
        stagnant = prior.get('stagnation_count', 0)+1 if not gain else 0
        errors = list(s['errors'])
        if any(k not in s['evidence_registry'] for k in cited): errors.append('unknown_evidence_id')
        requested = verdict.get('action', 'stop')
        reason = '실험 전 인과 가설은 미검증'
        decision = 'UNCERTAIN'
        unresolved=assessment.get('unresolved_issues',[])
        if errors: reason='인용 출처 오류'
        elif unresolved: reason='핵심 미해결 쟁점이 있어 사실 판정 보류'
        elif s['verified_facts']:
            decision = 'ACCEPT' if s['verified_facts'][0]['matches'] else 'REJECT'
            reason = '동결 원자료의 지정 필드를 직접 대조'
        elif requested in ('select', 'stop', 'wait'): reason = {'select':'실험 하나와 기준 채택. 사실 판정은 보류', 'stop':'추가 검증 근거 없음', 'wait':'사람 확인·자료·권한 필요'}[requested]
        elif repeated or stagnant >= 2: reason = '반복 주장 또는 정보적 진전 정체'
        elif s['round_number'] >= s['max_rounds']: reason = '검토·교정 호출 상한'
        elif requested == 'second' and verdict.get('new_question', '').strip():
            decision = 'REVISE' if assessment.get('revision_required') else 'CONTINUE'
            reason = '새 반증 질문 하나를 다음 제한 라운드에 전달'
        unresolved = assessment.get('unresolved_issues', []) or ([s['current_claim']] if not s['verified_facts'] else [])
        return dict(decision=decision, stop_reason=reason, information_gain=gain, signature=signature,
                    stagnation_count=stagnant, errors=errors, unresolved_issues=unresolved,
                    experiment_action=requested if not errors else 'stop',
                    judge_scores=score_arguments(assessment, s['evidence_registry']),
                    judge_feedback=dict(question=verdict.get('new_question', ''), reason=reason,
                                        previous_feedback_received=prior.get('judge_feedback', {}).get('question', ''),
                                        external_verification='disabled: 동결 로컬 자료만 검증, 외부 지식·URL 미검증'))

    def report(s):
        prior = s.get('prior', {})
        entry = dict(round=s['round_number'], signature=s['signature'], decision=s['decision'],
            verified_evidence_ids=s['information_gain'] + [k for k in s['judge'].get('evidence_ids', []) if k in s['evidence_registry'] and k not in s['information_gain'] and s['evidence_registry'][k]['status']=='SOURCE_VERIFIED'],
            new_facts=s['verified_facts'], refuted_claims=[s['current_claim']] if s['decision']=='REJECT' else [],
            resolved_issues=[f['field'] for f in s['verified_facts']], remaining_uncertainty=s['unresolved_issues'],
            new_errors=s['errors'], information_gain=s['information_gain'], judge_feedback=s['judge_feedback'],
            arguments=dict(advocate=s['advocate_arguments'], skeptic=s['skeptic_arguments']), scores=s['judge_scores'])
        return dict(history=prior.get('history', [])+[entry], final_report=dict(
            decision=s['decision'], conclusion=s['stop_reason'], verified_facts=s['verified_facts'],
            rejected_claims=entry['refuted_claims'], unresolved_issues=s['unresolved_issues'],
            judge_scores=s['judge_scores'], experiment_action=s['experiment_action'],
            answer='실험 채택은 성능 개선이 아닙니다. 공통 실행기의 실제 결과로 별도 판정합니다.'))

    def feedback(s):
        # Provider adapters run outside this policy graph under their existing journals.
        return interrupt(dict(decision=s['decision'], judge_feedback=s['judge_feedback']))

    graph = StateGraph(DebateState)
    graph.add_node('Initialize', initialize)
    graph.add_node('Advocate', lambda s: {})
    graph.add_node('Skeptic', lambda s: {})
    graph.add_node('Evidence Verification', verify)
    graph.add_node('Judge', judge)
    graph.add_node('Decision Router', lambda s: {})
    graph.add_node('Judge Feedback', feedback)
    graph.add_node('Final Report', report)
    graph.add_edge(START, 'Initialize')
    for a, b in zip(['Initialize','Advocate','Skeptic','Evidence Verification','Judge'], ['Advocate','Skeptic','Evidence Verification','Judge','Decision Router']):
        graph.add_edge(a,b)
    graph.add_conditional_edges('Decision Router', lambda s: s['decision'],
        {k:'Final Report' for k in ('CONTINUE','REVISE','ACCEPT','REJECT','UNCERTAIN')})
    graph.add_conditional_edges('Final Report', lambda s: s['decision'] in ('CONTINUE','REVISE'), {True:'Judge Feedback',False:END})
    graph.add_edge('Judge Feedback', 'Initialize')
    return graph.compile(checkpointer=checkpointer)


def evaluate(root, folder, packet, advocate, skeptic, judge):
    """No inference here. Existing request journals own all paid/free LLM attempts."""
    target = folder/'adversarial.json'
    previous = read(target) if target.exists() else {}
    key = digest([packet, advocate, skeptic, judge])
    if previous.get('input_key') == key:
        return previous
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(folder/'adversarial.sqlite')) as saver:
        from langgraph.types import Command
        graph=build(saver)
        config=dict(configurable=dict(thread_id='bounded-adversarial-v1'),recursion_limit=16)
        snapshot=graph.get_state(config)
        checkpoint=snapshot.values
        if len(checkpoint.get('history',[]))>len(previous.get('history',[])):
            previous={k:v for k,v in checkpoint.items() if k not in ('root','packet','prior')}
        inputs=dict(input_key=key,root=str(root),packet=packet,advocate_arguments=advocate,
                    skeptic_arguments=skeptic or {},judge=judge,prior=previous,max_rounds=2)
        result=checkpoint if checkpoint.get('input_key')==key and checkpoint.get('history') else graph.invoke(
            Command(resume=inputs) if snapshot.interrupts else inputs,config)
    # Frozen packet is already saved; avoid duplicating it in every review context.
    result = {k:v for k,v in result.items() if k not in ('root','packet','prior','__interrupt__')}
    result['input_key'] = key
    save(target, result)
    print('증거 심판:', result['decision'], '/', result['stop_reason'])
    return result
