"""Codex proposal -> Gemini critique -> Codex response -> independent NVIDIA judge.

Generated implementation is staged, never executed without trusted isolated evaluation.
"""
from pathlib import Path
from time import time

from .cross_review import CRITIC_VERSION, execute, digest
from .experiment_record import read, save, sha

FLOW_VERSION='codex-first-v1'
# Failures that stored journals can resolve at zero model cost on the next invocation. Anything that
# needs a new or uncertain request stays blocked by the journals themselves (never auto-retried).
RESUMABLE={'validation_or_execution_error','judge_unavailable'}


def proposal_context(verdict):
    return {k:verdict[k] for k in ('experiment','experiment_parameter','acceptance','evidence_ids','implementation_files','critique_responses','code_checks')}


def run_codex_first(root,folder,result,backend=None,gemini_caller=None,token_budget=100000,call_ceiling=None,stored_resume=None):
    from . import cross_review_auto as auto
    from .cross_review_nemotron import review as judge_review
    from .cross_review_adversarial import evaluate,evidence_registry
    root,folder=root.resolve(),folder.resolve();path=folder/'automation.json'
    state=read(path) if path.exists() else dict(flow_version=FLOW_VERSION,status='verifying',selected=None,events=[],deadline=time()+result['config']['seconds'])
    if path.exists() and state.get('flow_version')!=FLOW_VERSION:
        print('이전 자동 검토는 기록만 유지합니다. 생성 worker를 재개·실행하지 않습니다.')
        return 1
    if (folder/'result.json').exists():result=read(folder/'result.json')
    packet=result['packet'];config=result['config']
    if path.exists():
        if state['status'] in RESUMABLE:
            # Re-entry replays stored model responses from their journals: no request is repeated, so a
            # deterministic validation/launch failure is no longer permanent once the program is fixed.
            state.setdefault('resumes',[]).append(dict(from_status=state['status'],reason=str(state.get('reason',''))[:300]))
            state.update(status='verifying',reason='')
            state.pop('error_kind',None)
        # The time budget belongs to one invocation, not to the whole life of the review folder.
        state['deadline']=time()+config['seconds'];save(path,state)

    def event(key,agent,phase,message,usage=None,reused=False):
        if any(e['id']==key for e in state['events']):return
        state['events'].append(dict(id=key,agent=agent,phase=phase,round=1,status='complete',message=message,
                                   usage=usage,reused=reused,source=str(path)))
        save(path,state)

    def finish(status,reason=''):
        nonlocal result
        if result.get('pending'):
            result=execute(packet,result['config'],folder/'state.sqlite',caller=gemini_caller,
                           decision=dict(action='stop',rationale=reason or status,evidence_ids=[]))
        if state.get('plan_approved'):
            result['selected']=state['selected']
            result['status']=('experiment_evaluated' if state.get('experiment_status')=='completed' else
                'experiment_execution_failed' if state.get('experiment_status') in ('failed','interrupted') else 'experiment_selected')
        state.update(status=status,reason=reason,debate_html=str(folder/'debate.html'))
        save(path,state);save(folder/'result.json',{k:v for k,v in result.items() if k!='__interrupt__'})
        report=auto.token_report(folder,result)
        from .cross_review_debate import render
        render(root,folder)
        print('자동 검토:',status,reason)
        print('호출 수: Codex',report['codex_calls'],'Gemini',report['gemini_calls'],'NVIDIA',report['nemotron_calls'])
        print('토론 HTML:',folder/'debate.html')
        return 2 if status=='trusted_execution_required' else 0 if status in ('stopped','needs_human','completed','experiment_rejected') else 1

    def codex(phase,payload,critiques=()):
        if time()>=state['deadline']:raise ValueError('Review time budget exhausted')
        auto.verify_sources(root,packet)
        entry=auto.codex_task(root,folder,phase,payload,backend=backend,token_budget=token_budget)
        usage=auto.token_report(folder,result)['codex_usage']
        if usage['input_tokens'] is None or usage['output_tokens'] is None:raise ValueError('Codex usage unknown; no retry')
        if usage['total_tokens']>=token_budget:raise auto.CodexBudgetExceeded('Codex token budget')
        frozen=read(Path(entry.get('directory') or folder/'codex'/(phase+'-'+digest(payload)[:16]))/'input.json')
        if frozen.get('context_reference_root')=='document':
            from .cross_review_evidence import expand_evidence
            frozen=expand_evidence(frozen)
        if frozen.get('shared_core')!=core:raise ValueError('Stored Codex response has a different shared core; no replay or retry')
        for source in auto.provided_code_sources(frozen):
            if sha(root/source['path'])!=source['sha256']:raise ValueError('Frozen code changed')
        if phase in ('verify','correct'):
            provided={v['path']:v for v in auto.provided_code_sources(frozen)}
            for citation in entry['data'].get('code_checks',[]):
                source=provided.get(citation['path'])
                if source is None or citation['quote'] not in source['excerpt']:
                    raise ValueError('Codex cited code not present in this phase input')
        data=entry['data']
        if phase in ('verify','correct'):
            # Program-owned bookkeeping is normalized, never judged; the raw response stays in the journal.
            from .cross_review_contract import canonicalize_verdict
            data,notes=canonicalize_verdict(packet,data,critiques)
            key=phase+('-reply' if critiques else '')
            if notes and state.setdefault('normalizations',{}).get(key)!=notes:
                state['normalizations'][key]=notes;save(path,state)
        event(phase,'Codex','개선안 작성' if phase=='verify' else '반론 답변·수정안' if phase=='correct' else '최종 판단·구현',data,entry.get('usage'))
        return data

    def validate(verdict,critiques=()):
        from .cross_review_contract import classify_history
        classification_error=None
        try:canonical,issue=classify_history(packet,verdict)
        except (ValueError,TypeError,KeyError) as error:
            canonical,issue=verdict,None;classification_error=str(error)
        if issue:
            phase='correct' if critiques else 'verify'
            state.setdefault('classification_issues',{})[phase]=issue;save(path,state)
        errors=auto.verdict_errors(root,dict(packet=packet),canonical,require_parameter=True)
        if classification_error and not any(e['check']=='failure_history' for e in errors):
            errors.append(dict(check='failure_history',error=classification_error))
        if not any(e['check']=='shape' for e in errors):
            if verdict['action']=='second':
                errors+=auto.verdict_errors(root,dict(packet=packet),dict(canonical,action='select'),require_parameter=True)
            replies=verdict.get('critique_responses')
            ids=[c['id'] for c in critiques]
            if not isinstance(replies,list) or any(not isinstance(v,dict) or 'critique_id' not in v for v in replies) or sorted(v['critique_id'] for v in replies)!=sorted(ids):
                errors.append(dict(check='critique_coverage',error='Each critique needs exactly one explicit response'))
            hypothesis=verdict['experiment']['hypothesis_id']
            if hypothesis in packet['failed_hypotheses'] and not packet.get('reopen_evidence',{}).get(hypothesis):
                errors.append(dict(check='failed_hypothesis',error='Previously failed hypothesis without new falsification evidence'))
        unique=[]
        for error in errors:
            if error not in unique:unique.append(error)
        if unique:raise auto.VerdictValidationError(unique)

    terminal={'stopped','needs_human','trusted_execution_required','judge_unavailable','validation_or_execution_error','legacy_run_read_only','critic_error','additional_call_limit','completed','experiment_rejected','execution_failed','execution_uncertain'}
    if state['status'] in terminal:return finish(state['status'],state.get('reason',''))
    execution_journal=folder/'execution.json'
    if execution_journal.exists():
        executed=read(execution_journal)
        if executed.get('status')!='finished':return finish('execution_uncertain','저장된 공통 실험의 결과가 불명확합니다. 모델·학습을 재시도하지 않습니다.')
        from .experiment_record import verify
        experiment=Path(executed['experiment_folder']);verify(experiment,read(experiment/'record.json'))
        state.update(executed)
        result['status']='experiment_evaluated' if executed.get('experiment_status')=='completed' else 'experiment_execution_failed'
        return finish('completed' if executed.get('outcome')=='accepted' else 'experiment_rejected' if executed.get('outcome')=='candidate_discarded' and executed.get('experiment_status')=='completed' else 'execution_failed','저장된 공통 실험 결과 복원; 추가 요청·학습 없음')
    if config.get('prompt_version')!=CRITIC_VERSION:
        return finish('legacy_run_read_only','과거 Gemini-first 검토는 추가 요청 없이 보존합니다. 새 자료의 Codex-first 검토부터 새 계약을 적용합니다.')
    if not packet.get('fresh_evidence_ids'):return finish('stopped','새 실행 근거 없음. 모델 요청을 보내지 않습니다.')
    try:
        from .cross_review_contract import shared_core,classify_history
        core=shared_core(root,folder,packet)
        if not state.get('proposal'):
            payload=dict(flow_role='advocate',round=1,remaining_gemini=0,failed_hypotheses=packet['failed_hypotheses'])
            verdict=codex('verify',payload)
            try:validate(verdict)
            except (ValueError,TypeError,KeyError) as error:
                payload=dict(payload,correction=dict(errors=getattr(error,'errors',[dict(check='validation',error=str(error))])),response=verdict)
                verdict=codex('correct',payload);validate(verdict)
                state['correction_spent']=True
            state['proposal']=verdict;save(path,state)
        proposal=state['proposal']
        if proposal['action']!='select':return finish('needs_human' if proposal['action']=='wait' else 'stopped',proposal['rationale'])
        if not state.get('critiques'):
            if call_ceiling is not None and len(result.get('attempts',[]))>=call_ceiling:
                return finish('additional_call_limit','이번 Gemini 추가 요청 상한')
            critic_config=dict(config,advocate_proposal=proposal_context(proposal),shared_core=core)
            state['critic_config']=critic_config;save(path,state)
            result=execute(packet,critic_config,folder/'state.sqlite',caller=gemini_caller)
            save(folder/'result.json',{k:v for k,v in result.items() if k!='__interrupt__'})
            if result.get('status') not in ('compare','awaiting_comparison') or not result.get('response'):
                return finish('critic_error',result.get('status','unknown'))
            critique=result['response'];critique_id='gemini-'+digest(critique)[:16]
            state['critiques']=[dict(id=critique_id,response=critique)]
            event(critique_id,'Gemini','독립 비판',critique,result['attempts'][-1].get('usage') if result.get('attempts') else None)
        if state.get('critic_config',{}).get('shared_core')!=core:
            if stored_resume is None:
                return finish('legacy_run_read_only','저장된 비판의 공통 근거가 일치하지 않아 새 호출 없이 보존합니다.')
            calls=list(folder.glob('codex/correct-*/call.json'))
            if (len(calls)!=1 or sha(calls[0])!=stored_resume.get('correction_sha256') or
                    read(calls[0]).get('status')!='complete' or read(calls[0]).get('data')!=state.get('reply') or
                    digest(state['critiques'])!=stored_resume.get('critiques_sha256') or
                    not stored_resume.get('authorization')):
                raise ValueError('Stored response provenance mismatch; no model retry')
            validate(state['reply'],state['critiques'])
            state['stored_response_reuse']=stored_resume;save(path,state)
        critiques=state['critiques']
        if not state.get('reply'):
            if state.get('correction_spent'):
                state['reply']=proposal
            else:
                remaining=max(0,min(config['max_calls'],call_ceiling if call_ceiling is not None else 3)-len(result.get('attempts',[])))
                payload=dict(flow_role='advocate',round=1,remaining_gemini=remaining,response=proposal_context(proposal),
                    critiques=critiques,failed_hypotheses=packet['failed_hypotheses'])
                reply=codex('correct',payload,critiques);validate(reply,critiques)
                state['reply']=reply
            save(path,state)
        reply=state['reply']
        rechecked=False
        if reply['action']=='second' and not state.get('correction_spent'):
            remaining=min(config['max_calls'],call_ceiling if call_ceiling is not None else 3)-len(result.get('attempts',[]))
            if remaining>0 or state.get('recheck_intent'):
                if not state.get('recheck_done'):
                    state['recheck_intent']=True;save(path,state)
                    inspected=execute(packet,state['critic_config'],folder/'state.sqlite',caller=gemini_caller)
                    if inspected.get('round',1)>=2:result=inspected
                    else:
                        result=execute(packet,state['critic_config'],folder/'state.sqlite',caller=gemini_caller,
                            decision=dict(action='second',rationale=reply['rationale'],new_question=reply['new_question'],
                                evidence_ids=reply['evidence_ids'],advocate_proposal=proposal_context(reply),shared_core=core))
                    if result.get('status') not in ('compare','awaiting_comparison'):
                        return finish('critic_error',result.get('status','unknown'))
                    response=result['response'];identifier='gemini-'+digest(response)[:16]
                    if not any(c['id']==identifier for c in state['critiques']):
                        state['critiques'].append(dict(id=identifier,response=response))
                    state['recheck_done']=True;save(path,state)
                    event(identifier,'Gemini','수정안 재비판',response,result['attempts'][-1].get('usage'))
                rechecked=True
        critiques=state['critiques']
        context=dict(original_proposal=proposal_context(proposal),revised_proposal=proposal_context(reply),critiques=critiques,
            shared_core=core,classification_issues=state.get('classification_issues',{}))
        if state.get('stored_response_reuse'):
            context['stored_review_notice']='Archived responses used earlier inputs, not this shared_core. Original critic opinions do not imply approval of the revision. Independently check the revised proposal.'
        # The complete critic text is retained. Oversize input blocks before calling the judge.
        from .cross_review_judge_projection import judge_packet
        context['evidence_scope_note']='최신 수치·기준·과거 실패 이유는 유지. 과거 코호트의 개별 대조 수치는 요약하고 미통과 ID·오류 건수만 전달함. 원본은 각 근거 path/SHA에 보존됨. No evidence omitted 문구는 $ref 대상이 누락되지 않았다는 뜻임.'
        entry=judge_review(root,folder,dict(result,packet=packet,judge_packet=judge_packet(packet),deadline=state['deadline']),role='judge',context=context)
        if not entry or entry.get('status')!='complete':
            if reply['action']=='select':
                # The debate itself finished; keep its outcome for the next development step. It is NOT
                # judged, so it is never executed automatically and never reported as approved.
                state['unjudged_candidate']=dict(plan=proposal_context(reply),critique_ids=[c['id'] for c in critiques],
                    note='독립 심판 없이 종료: Codex 수정안과 Gemini 비판만 있음. 승인·자동 실행·성능 개선 아님.')
            return finish('judge_unavailable',(entry or {}).get('reason',(entry or {}).get('error_kind','독립 심판 미설정')))
        judgment=entry['response'];state['independent_judgment']=judgment;state.pop('unjudged_candidate',None)
        event('judge','NVIDIA','독립 심판',judgment,entry.get('usage'),entry.get('reused',False))
        registry=evidence_registry(root,packet)
        if any(registry.get(k,{}).get('status')!='SOURCE_VERIFIED' for k in judgment['evidence_ids']):
            return finish('stopped','심판이 미검증 근거를 인용했습니다.')
        checks=judgment['criticism_checks']
        approvals=(judgment['decision']=='approve_experiment' and not judgment['unresolved_issues'] and
            all(v['status']=='addressed' for v in checks) and (reply['action']=='select' or reply['action']=='second' and rechecked) and
            sorted(v['critique_id'] for v in reply['critique_responses'])==sorted(c['id'] for c in critiques[:1]) and
            all(v['disposition']!='needs_evidence' for v in reply['critique_responses']))
        canonical,history_issue=classify_history(packet,reply)
        auto.validate_verdict(root,dict(packet=packet),canonical,require_parameter=True)
        gate=dict(allowed=bool(approvals and not judgment['human_confirmation_required']),
            strict_verdict_valid=True,history_resolution=history_issue,
            unresolved_issues=judgment['unresolved_issues'],human_required=judgment['human_confirmation_required'])
        save(folder/'development-gate.json',gate);state['development_gate']=gate;save(path,state)
        if judgment['human_confirmation_required']:
            return finish('needs_human','비판에서 실제 사람 확인이 필요합니다. 심판 의견으로 정답을 추정하지 않습니다.')
        verdict=dict(reply,action='select' if approvals else 'stop',rationale=judgment['rationale'],
            debate_assessment=dict(advocate=judgment['advocate'],skeptic=judgment['skeptic'],
                unresolved_issues=judgment['unresolved_issues'],revision_required=False))
        evaluate(root,folder,packet,reply['experiment'],critiques[0]['response'],verdict)
        adjudicate=(judgment['decision']=='needs_evidence' and not judgment['human_confirmation_required'] and reply['action']=='select' and all(v['disposition']!='needs_evidence' for v in reply['critique_responses']))
        if not gate['allowed'] and not adjudicate:return finish('stopped','Codex가 추가 검토를 요구했으나 이번 Gemini 호출 상한을 소진했습니다.' if reply['action']=='second' and not rechecked else judgment['rationale'])
        state['selected']=reply['experiment'];state['plan_approved']=gate['allowed'];save(path,state)
        result['selected']=reply['experiment'];result['status']='experiment_selected'
        payload=dict(selected=reply['experiment'],acceptance=reply['acceptance'],allowed_files=reply['implementation_files'],
            reference_result=packet['latest_result'],experiment_parameter=reply['experiment_parameter'],independent_judgment=judgment,
            critiques=critiques,codex_reply=proposal_context(reply),proposal_only=False)
        implementation=codex('implement',payload)
        if implementation.get('final_decision') not in ('proceed','stop','wait') or not isinstance(implementation.get('final_rationale'),str) or not implementation['final_rationale'].strip():
            return finish('stopped','Codex 최종 실행 판단이 없어 추가 요청 없이 종료합니다.')
        state['codex_final_decision']=dict(decision=implementation['final_decision'],rationale=implementation['final_rationale']);save(path,state)
        if implementation['final_decision']!='proceed':return finish('stopped',implementation['final_rationale'])
        if adjudicate:
            issues=list(dict.fromkeys(judgment['unresolved_issues']+[v['rationale'] for v in checks if v['status']=='unresolved']))
            responses=implementation.get('judge_issue_responses',[])
            from .cross_review import encoded
            plan=encoded(proposal_context(reply))
            if (not isinstance(responses,list) or len(responses)!=len(issues) or
                    any(not isinstance(v,dict) or set(v)!={'issue','plan_quote','rationale'} for v in responses) or
                    sorted(v['issue'] for v in responses)!=sorted(issues) or
                    any(not isinstance(v['plan_quote'],str) or len(v['plan_quote'].strip())<12 or v['plan_quote'] not in plan or
                        not isinstance(v['rationale'],str) or not v['rationale'].strip() for v in responses)):
                return finish('stopped','심판 쟁점별 기존 실험 계획의 정확한 인용이 없어 개발을 승인하지 않습니다.')
            gate.update(allowed=True,approval_source='codex_final_plan_citations',judge_disagreement_preserved=True,issue_responses=responses)
            state.update(development_gate=gate,plan_approved=True);save(folder/'development-gate.json',gate);save(path,state)
        staged=auto.stage_implementation(root,folder,reply,{k:implementation[k] for k in ('edits','worker')})
        state.update(implementation_proposal=str(staged),code_applied=False,worker_executed=False,
            acceptance_passed=None,performance_improved_on_same_cohort=None)
        from .cross_review_execution import execute_candidate
        if not (root/'trusted-experiment.json').exists():
            return finish('trusted_execution_required','신뢰된 평가 입력 계약이 없어 제안만 저장했습니다.')
        executed=execute_candidate(root,folder,reply);state.update(executed)
        result['status']='experiment_evaluated' if executed.get('experiment_status')=='completed' else 'experiment_execution_failed'
        outcome=executed.get('outcome')
        return finish('completed' if outcome=='accepted' else 'experiment_rejected' if executed.get('outcome')=='candidate_discarded' and executed.get('experiment_status')=='completed' else 'execution_failed',
                      '독립 평가 후 채택' if outcome=='accepted' else executed.get('reason',executed.get('rollback','격리 실행 실패; 재시도하지 않습니다.')))
    except (ValueError,TypeError,KeyError,OSError,StopIteration,SyntaxError) as error:
        state['error_kind']=type(error).__name__
        return finish('validation_or_execution_error',auto.diagnostic_text(error))
