import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_cross_review_auto as fixture
import test_cross_review_nemotron as native_fixture
from card_condition import cross_review_auto as auto
from card_condition import cross_review_nemotron as native
from card_condition.cross_review import CRITIC_VERSION, execute, digest
from card_condition.cross_review_adversarial import build, measurement_claim_text
from card_condition.experiment_record import read,save,sha


class HighFixTest(unittest.TestCase):
    def setUp(self):
        fixture.AutoReviewTest.setUp(self)
        native_fixture.NemotronTest.configure(self)
        self.config['prompt_version']=CRITIC_VERSION
        save(self.folder/'config.json',self.config)
        self.verdict['critique_responses']=[]
        self.implementation.update(final_decision='proceed',final_rationale='반론과 독립 심판을 대조해 고정 실험을 진행합니다.')
        self.response.update(critique_status='objection',counter_evidence='선행 설명 '*50+'핵심 반증: 학습 집계와 실제 점수의 인과가 아직 확인되지 않았습니다.')
        self.order=[];self.inputs=[];self.n_calls=0
        self.result=dict(packet=self.packet,config=self.config,status='proposal_pending',attempts=[],pending=[])
        save(self.folder/'result.json',self.result)
        self.reply_action='select';self.judge_action='approve_experiment'
        self.judge_human=None;self.judge_issues=[];self.critic_status='propose';self.critic_human=''

    def gemini(self,prompt,timeout):
        self.gemini_calls+=1;self.order.append('Gemini')
        self.inputs.append(('Gemini',prompt))
        response=dict(self.response,proposal_status=self.critic_status,human_confirmation=self.critic_human)
        if self.gemini_calls==2:response['counter_evidence']='수정된 배율을 전달받아 검토했습니다. 실측 전 인과 미확인.'
        return json.dumps(response),dict(prompt_token_count=20,candidates_token_count=10,total_token_count=30)

    def backend(self,root,phase,prompt,directory,thread):
        self.codex_calls.append((phase,thread));self.order.append('Codex:'+phase)
        context=read(directory/'input.json');self.inputs.append((phase,context))
        value=copy.deepcopy(self.implementation if phase=='implement' else self.verdict)
        if phase=='correct' and context.get('critiques'):
            value['critique_responses']=[dict(critique_id=c['id'],disposition='accept',rationale='인과 미확인을 수용하고 고정 배율 하나의 검증으로 한정합니다.',evidence_ids=['latest_result']) for c in context['critiques']]
            value['experiment']['cause']='반론을 수용한 제한된 실험 가설'
            value['experiment_parameter']['value']=.25
            value['action']=self.reply_action
            if self.reply_action=='second':value['new_question']='수정된 고정 배율 .25의 실패 조건을 다시 대조하세요.'
        return value,dict(self.usage),'mock-thread'

    def judge(self,payload,timeout,root):
        self.n_calls+=1;self.order.append('NVIDIA:judge')
        from card_condition.cross_review_evidence import expand_evidence
        data=expand_evidence(json.loads(payload['messages'][1]['content']))
        self.inputs.append(('judge',data))
        ratings=dict(reliability=90,logic=80,response=80,independence=60,evidence_ids=['latest_result'])
        value=dict(reviewed_hypothesis_id=data['debate']['judging_target']['hypothesis_id'],decision=self.judge_action,rationale='정답 확정 없이 반증 가능한 실험 계획만 검토했습니다.',
            evidence_ids=['latest_result'],unresolved_issues=self.judge_issues,human_confirmation_required=bool(self.critic_human) if self.judge_human is None else self.judge_human,advocate=ratings,skeptic=ratings,
            criticism_checks=[dict(critique_id=c['id'],status='addressed',rationale='답변과 원문 반증을 대조했습니다.') for c in data['debate']['critiques']])
        return json.dumps(value),dict(prompt_tokens=30,completion_tokens=20,total_tokens=50)

    def run_flow(self,**kwargs):
        class Response:
            text='<span>Free Endpoint</span><span>Available</span>'
            def raise_for_status(self):pass
        with patch.object(native,'http_call',side_effect=self.judge),patch('httpx.get',return_value=Response()),contextlib.redirect_stdout(io.StringIO()):
            return auto.run_auto(self.root,self.folder,self.result,backend=self.backend,gemini_caller=self.gemini,**kwargs)

    def test_existing_auto_cli_starts_with_proposal_not_gemini(self):
        import hashlib
        import os
        from card_condition import cross_review_manual as manual
        config=copy.deepcopy(self.config)
        config['free_tier_verification']=dict(tier='Free',project_id='test',verified_at='test',evidence='mock',key_sha256=hashlib.sha256(b'test-key').hexdigest())
        config_path=self.root/'artifacts/cross-review-20261019/local-config.json';config_path.parent.mkdir()
        save(config_path,config)
        def route(root,folder,result,**kwargs):
            self.assertEqual(result['status'],'proposal_pending')
            self.assertEqual(result['attempts'],[])
            self.assertEqual(result['config']['prompt_version'],CRITIC_VERSION)
            return 0
        with patch.object(manual,'ROOT',self.root),patch.dict(os.environ,{'POKEMON_CARD_CONDITION_GEMINI_API_KEY':'test-key'}),patch.object(auto,'run_auto',side_effect=route) as routed,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manual.main(['--auto']),0)
            routed.assert_called_once()
        self.assertFalse(self.order)

    def test_proposal_critique_reply_independent_judge_and_staged_only(self):
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(self.order,['Codex:verify','Gemini','Codex:correct','NVIDIA:judge','Codex:implement'])
        self.assertIn('advocate_proposal',self.inputs[1][1])
        corrected=dict(self.inputs)['correct']
        self.assertIn('핵심 반증',corrected['critiques'][0]['response']['counter_evidence'])
        data=dict(self.inputs)['judge']['debate']
        self.assertIn('superseded',data['original_proposal']['status'])
        self.assertNotIn('experiment_parameter',data['original_proposal'])
        self.assertEqual(data['revised_proposal']['experiment_parameter']['value'],.25)
        self.assertIn('핵심 반증',data['critiques'][0]['response']['counter_evidence'])
        state=read(self.folder/'automation.json')
        self.assertEqual(state['status'],'trusted_execution_required')
        self.assertFalse(state['code_applied']);self.assertFalse(state['worker_executed'])
        self.assertIsNone(state['performance_improved_on_same_cohort'])
        self.assertEqual(self.source.read_text(),self.original)
        self.assertFalse((self.root/'artifacts/experiments').exists())
        self.assertEqual(read(self.folder/'adversarial.json')['decision'],'UNCERTAIN')
        saved=read(self.folder/'result.json');self.assertFalse(saved['pending'])
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(len(self.codex_calls),3);self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,1)
        report=read(self.folder/'token_report.json')
        self.assertEqual(report['codex_usage']['total_tokens'],330)
        self.assertEqual(report['gemini_usage']['total_token_count'],30)
        self.assertEqual(report['nemotron_usage']['total_tokens'],50)
        self.assertIsNone(report['codex_usage']['reasoning_output_tokens'])
        self.assertEqual([e['agent'] for e in read(self.folder/'debate.json')['events']],['Codex','Gemini','Codex','NVIDIA','Codex'])

    def test_gemini_stop_does_not_override_independent_judge(self):
        self.critic_status='stop'
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(self.n_calls,1)
        self.assertEqual(dict(self.inputs)['judge']['debate']['critiques'][0]['response']['proposal_status'],'stop')

    def test_judge_rejection_or_unresolved_objection_blocks_implementation(self):
        self.judge_action='reject_experiment'
        self.assertEqual(self.run_flow(),0)
        self.assertNotIn('Codex:implement',self.order)
        self.assertEqual(read(self.folder/'automation.json')['status'],'stopped')

    def test_high_judge_scores_with_unresolved_issue_cannot_approve(self):
        self.judge_issues=['실제 사람 정답이 필요한 쟁점']
        self.assertEqual(self.run_flow(),0)
        self.assertEqual([x for x in self.order if x=='Codex:implement'],[])

    def test_revised_proposal_reaches_second_critic_with_caps(self):
        self.reply_action='second'
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(self.gemini_calls,2);self.assertEqual(len(self.codex_calls),3);self.assertEqual(self.n_calls,1)
        second=[p for who,p in self.inputs if who=='Gemini'][1]
        self.assertIn('0.25',second);self.assertIn('반론을 수용한 제한된 실험 가설',second)
        self.assertIn('수정된 고정 배율',second)
        self.assertEqual(len(dict(self.inputs)['judge']['debate']['critiques']),2)
        self.assertEqual(self.run_flow(),2);self.assertEqual(self.gemini_calls,2)

    def test_invocation_one_call_cap_blocks_second_and_implementation(self):
        self.reply_action='second'
        self.assertEqual(self.run_flow(call_ceiling=1),0)
        self.assertEqual(self.gemini_calls,1);self.assertEqual(len(self.codex_calls),2)
        self.assertEqual(self.run_flow(call_ceiling=1),0);self.assertEqual(self.gemini_calls,1)

    def test_missing_critique_reply_cannot_reach_judge_or_implementation(self):
        original=self.backend
        def backend(*args):
            value,usage,thread=original(*args)
            if args[1]=='correct':value['critique_responses']=[]
            return value,usage,thread
        with patch.object(self,'backend',side_effect=backend):self.assertEqual(self.run_flow(),1)
        self.assertEqual(self.n_calls,0);self.assertEqual(len(self.codex_calls),2)
        self.assertEqual(self.run_flow(),1);self.assertEqual(len(self.codex_calls),2)

    def test_human_truth_is_not_overridden_by_judge(self):
        self.critic_human='정상인지 결함인지 실제 라벨 확인 필요'
        self.assertEqual(self.run_flow(),0)
        self.assertEqual(read(self.folder/'automation.json')['status'],'needs_human')
        self.assertNotIn('Codex:implement',self.order)

    def test_role_endorsement_is_not_a_human_question(self):
        self.critic_human='수석 개발자의 관점에서 코드 계약 준수를 확인했습니다.'
        self.judge_human=False
        self.assertEqual(self.run_flow(),2)
        self.assertIn('Codex:implement',self.order)
        self.assertEqual(read(self.folder/'automation.json')['critiques'][0]['response']['human_confirmation'],self.critic_human)

    def test_invalid_human_dependency_flag_fails_closed(self):
        self.judge_human='false'
        self.assertEqual(self.run_flow(),1)
        self.assertNotIn('Codex:implement',self.order)

    def test_unknown_usage_stops_before_next_model_and_remains_unknown(self):
        self.usage={}
        self.assertEqual(self.run_flow(),1)
        self.assertEqual(self.gemini_calls,0);self.assertEqual(self.n_calls,0)
        self.assertIsNone(read(self.folder/'token_report.json')['codex_usage']['total_tokens'])

    def test_oversize_input_is_not_silently_truncated_or_sent(self):
        (self.root/'AGENTS.md').write_text('- 실험 전에 '+'x'*auto.CODEX_PROMPT_BYTES['verify'])
        self.assertEqual(self.run_flow(),1)
        self.assertFalse(self.order)
        self.assertEqual(read(next(self.folder.glob('codex/*/preflight.json')))['blocked'],'input_size')

    def test_failed_hypothesis_cannot_be_reopened_without_new_refutation(self):
        self.verdict['experiment']['hypothesis_id']=next(iter(self.packet['failed_hypotheses']))
        self.assertEqual(self.run_flow(),1)
        self.assertEqual(len(self.codex_calls),2);self.assertEqual(self.gemini_calls,0)

    def test_execution_failure_is_not_a_failed_hypothesis(self):
        self.verdict['failed_hypotheses_checked'].append('execution-failed-only')
        with self.assertRaisesRegex(ValueError,'unexpected=execution-failed-only'):
            auto.validate_verdict(self.root,dict(packet=self.packet),self.verdict,require_parameter=True)

    def test_no_fresh_sources_no_requests(self):
        self.packet['fresh_evidence_ids']=[];save(self.folder/'result.json',self.result)
        self.assertEqual(self.run_flow(),0);self.assertEqual(self.order,[])

    def test_no_legacy_journal_or_provider_replay(self):
        self.config['prompt_version']='cross-review-ko-v5-role-prompts';save(self.folder/'result.json',self.result)
        self.assertEqual(self.run_flow(),1);self.assertFalse(self.order)
        self.assertEqual(read(self.folder/'automation.json')['status'],'legacy_run_read_only')

    def test_malicious_perfect_worker_is_never_executed_or_applied(self):
        marker=self.root/'outside-experiment-marker'
        self.implementation['worker']=f"from pathlib import Path\nPath({str(marker)!r}).write_text('secret')\nscores=[float(row['target']) for row in []]\n"
        self.assertEqual(self.run_flow(),2)
        self.assertFalse(marker.exists());self.assertEqual(self.source.read_text(),self.original)
        proposal=read(self.folder/'implementation-proposal.json')
        self.assertFalse(proposal['applied']);self.assertFalse(proposal['executed'])
        self.assertEqual(proposal['worker'],self.implementation['worker'])
        self.assertFalse(auto.measured_gain(dict(acceptance_passed=True,comparison={'after':{'fp':0,'fn':0}})))
        with self.assertRaises(auto.UntrustedExecutionError):auto.implement(self.root,self.folder,{},self.verdict,self.implementation)

    def test_stage_source_conflict_and_invalid_syntax_do_not_write_source(self):
        self.implementation['worker']='if broken'
        self.assertEqual(self.run_flow(),1);self.assertEqual(self.source.read_text(),self.original)
        self.assertFalse((self.folder/'implementation-proposal.json').exists())

    def test_critic_crash_checkpoint_does_not_repeat_completed_codex(self):
        original=self.gemini
        def crash(*args):raise KeyboardInterrupt
        with patch.object(self,'gemini',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.run_flow()
        self.assertEqual(self.run_flow(),1)
        self.assertEqual(len(self.codex_calls),1);self.assertEqual(self.gemini_calls,0)
        self.assertEqual(read(self.folder/'automation.json')['status'],'critic_error')

    def test_correction_crash_never_retries_uncertain_codex_request(self):
        original=self.backend
        def crash(*args):
            if args[1]=='correct':raise KeyboardInterrupt
            return original(*args)
        with patch.object(self,'backend',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.run_flow()
        self.assertEqual(self.run_flow(),1)
        self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,0)
        self.assertEqual(len(list(self.folder.glob('codex/correct-*/call.json'))),1)

    def test_native_error_records_unknown_usage_without_retry(self):
        def error(*args):raise TimeoutError('secret-do-not-log')
        with patch.object(self,'judge',side_effect=error):self.assertEqual(self.run_flow(),1)
        self.assertEqual(self.run_flow(),1)
        self.assertEqual(len(self.codex_calls),2)
        self.assertIsNone(read(self.folder/'token_report.json')['nemotron_usage']['total_tokens'])
        self.assertNotIn('secret-do-not-log',(self.folder/'automation.json').read_text())

    def test_judge_unknown_source_or_incomplete_criticism_contract_rejected(self):
        raw_judge=self.judge
        def invalid(*args):
            raw,usage=raw_judge(*args);value=json.loads(raw);value['criticism_checks']=[]
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=invalid):self.assertEqual(self.run_flow(),1)
        self.assertNotIn('Codex:implement',self.order)

    def test_full_critic_is_preserved_or_budget_blocked_never_sliced(self):
        entry=dict(status='complete',response=dict(stance='object',support_score=0,opposition_score=2,evidence_ids=['latest_result'],rationale='앞말 '*70+'핵심 반증 반드시 보존',proposal=self.response))
        self.assertIsNone(native.compact(entry,max_bytes=60))
        text=json.dumps(native.compact(entry,max_bytes=10000),ensure_ascii=False)
        self.assertIn('핵심 반증 반드시 보존',text);self.assertIn('인과가 아직 확인',text)


class ClaimBindingTest(unittest.TestCase):
    def test_unrelated_claim_conflict_and_bad_citation_cannot_inherit_measurement_truth(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'result.json';save(source,dict(run_completed=True))
            claim=dict(evidence_id='result',field=['run_completed'],expected=True)
            packet=dict(evidence=dict(result=dict(path='result.json',sha256=sha(source))),machine_claim=claim)
            base=dict(root=str(root),packet=packet,advocate_arguments=dict(cause='2+2=5'),skeptic_arguments={},judge=dict(action='stop',evidence_ids=['result']),prior={},max_rounds=2)
            for current,judge in [('2+2=5',base['judge']), (measurement_claim_text(claim),dict(action='stop',evidence_ids=['made-up'])),
                                  (measurement_claim_text(claim),dict(action='select',evidence_ids=['result'],debate_assessment=dict(unresolved_issues=['반대 근거 미해결'])))]:
                with self.subTest(current=current,judge=judge):
                    result=build().invoke(dict(base,advocate_arguments=dict(cause=current),judge=judge))
                    self.assertEqual(result['decision'],'UNCERTAIN')
                    self.assertTrue(result['verified_measurements'])


class CompletedDiagnosticTest(unittest.TestCase):
    from test_experiment_record import ExperimentRecordTest as Fixture
    setUp=Fixture.setUp
    run_case=Fixture.run_case

    def test_complete_measurements_survive_later_result_and_codex_context(self):
        self.plan['experiment_kind']='diagnostic'
        measurements=dict(kind='gradient_conflict',cosine_by_group={'normal':-.73},scales=[.125,.25],
                          delta={'fp':0,'fn':0},tensor_contract={'feature_shape':[3,4]})
        code,folder,item=self.run_case("o['diagnostic_evidence']="+repr(measurements))
        self.assertEqual(code,0)
        diagnostic=self.plan['hypothesis_id']
        self.plan.pop('experiment_kind');self.plan['hypothesis_id']='later-model'
        self.run_case()
        from card_condition.cross_review_evidence import latest_packet
        packet=latest_packet(self.root)
        key=packet['completed_diagnostics'][diagnostic][0]
        self.assertEqual(packet['evidence'][key]['summary']['measurements'],measurements)
        review=self.root/'review';review.mkdir();save(review/'packet.json',packet)
        context=auto.review_context(self.root,review,'verify',dict(flow_role='advocate'))
        self.assertEqual(context['evidence']['evidence'][key]['summary']['measurements'],measurements)


if __name__=='__main__':unittest.main()
