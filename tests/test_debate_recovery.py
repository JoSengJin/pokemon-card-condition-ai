import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from card_condition import cross_review as gemini,cross_review_nemotron as native
from card_condition.cross_review import digest
from card_condition.experiment_record import read,save
import test_cross_review_high_fixes as fixture
from test_free_api_dashboard import FreeOnlyTest


class JudgeRecoveryTest(unittest.TestCase):
    setUp=fixture.HighFixTest.setUp
    backend=fixture.HighFixTest.backend
    gemini=fixture.HighFixTest.gemini
    judge=fixture.HighFixTest.judge
    run_flow=fixture.HighFixTest.run_flow

    def test_current_plan_and_dynamic_ids_reach_judge_then_final_slot(self):
        self.assertEqual(self.run_flow(),2)
        data=dict(self.inputs)['judge'];d=data['debate']
        self.assertEqual(d['judging_target']['hypothesis_id'],d['revised_proposal']['experiment']['hypothesis_id'])
        self.assertEqual(d['revised_proposal']['experiment_parameter']['value'],.25)
        self.assertNotIn('experiment_parameter',d['original_proposal'])
        self.assertIn('superseded',d['original_proposal']['status'])
        self.assertEqual(d['critiques'][0]['response']['counter_evidence'],self.response['counter_evidence'])
        schema=data['required_response_schema']['properties']
        self.assertEqual(schema['evidence_ids']['items']['enum'],sorted(self.packet['evidence']))
        self.assertEqual(schema['criticism_checks']['type'],'array')
        self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,1)
        self.assertEqual([phase for phase,_ in self.codex_calls],['verify','correct','implement'])
        before=(self.gemini_calls,self.n_calls,len(self.codex_calls))
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(before,(self.gemini_calls,self.n_calls,len(self.codex_calls)))

    def test_judge_uses_active_flow_deadline_not_finished_critic_deadline(self):
        with patch.object(native,'review',return_value=None):self.assertEqual(self.run_flow(),1)
        saved=read(self.folder/'result.json');saved['deadline']=0;save(self.folder/'result.json',saved)
        state=read(self.folder/'automation.json');state['status']='verifying';save(self.folder/'automation.json',state)
        self.assertEqual(self.run_flow(),2)
        self.assertEqual(self.n_calls,1)

    def test_wrong_plan_cannot_reach_implementation(self):
        original=self.judge
        def wrong(*args):
            raw,usage=original(*args);value=json.loads(raw);value['reviewed_hypothesis_id']='withdrawn-plan'
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=wrong):self.assertEqual(self.run_flow(),1)
        self.assertNotIn('Codex:implement',self.order)
        entry=read(next((self.root/'artifacts/nemotron-cache').glob('*/call.json')))
        self.assertEqual(entry['validation_errors'],['judge_wrong_target'])
        # A delivered but malformed reply is not a provider outage: it must not latch the circuit
        # (that blocked every later review until someone edited the file by hand).
        self.assertFalse((self.root/'artifacts/provider-alerts/nemotron-disabled.json').exists())

    def test_dictionary_checks_and_context_names_still_rejected(self):
        original=self.judge
        def invalid(*args):
            raw,usage=original(*args);value=json.loads(raw)
            value['criticism_checks']={c['critique_id']:c for c in value['criticism_checks']}
            value['evidence_ids']=['shared_core','code_checks']
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=invalid):self.assertEqual(self.run_flow(),1)
        self.assertNotIn('Codex:implement',self.order)

    def test_extra_fields_quarantined_without_changing_core_or_usage(self):
        original=self.judge
        def extra(*args):
            raw,usage=original(*args);value=json.loads(raw)
            value['shared_core']={'fake_path':'invented.py','decision':'approve_experiment'}
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=extra):self.assertEqual(self.run_flow(),2)
        entry=read(next((self.root/'artifacts/nemotron-cache').glob('*/call.json')))
        self.assertEqual(entry['status'],'complete')
        self.assertNotIn('shared_core',entry['response'])
        self.assertIn('shared_core',entry['extra_fields'])
        self.assertIn('shared_core',json.loads(entry['raw_response']))
        self.assertEqual(entry['usage']['total_tokens'],50)
        self.assertIn('Codex:implement',self.order)

    def test_extras_cannot_repair_missing_required_field(self):
        original=self.judge
        def missing(*args):
            raw,usage=original(*args);value=json.loads(raw)
            value['shared_core']={'decision':value.pop('decision')}
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=missing):self.assertEqual(self.run_flow(),1)
        self.assertNotIn('Codex:implement',self.order)

    def test_valid_rejection_with_extras_remains_rejection(self):
        self.judge_action='reject_experiment';self.judge_issues=['실행 전 필요한 보호 기준 누락']
        original=self.judge
        def extra(*args):
            raw,usage=original(*args);value=json.loads(raw);value['approved']=True
            return json.dumps(value),usage
        with patch.object(self,'judge',side_effect=extra):self.assertEqual(self.run_flow(),0)
        self.assertNotIn('Codex:implement',self.order)
        self.assertFalse(read(self.folder/'development-gate.json')['allowed'])

    def test_needs_evidence_requires_final_plan_citations(self):
        self.judge_action='needs_evidence';self.judge_issues=['효과 입증 부족']
        self.assertEqual(self.run_flow(),0)
        state=read(self.folder/'automation.json')
        self.assertFalse(state['plan_approved'])
        self.assertIn('정확한 인용',state['reason'])
        self.assertFalse(state.get('code_applied',False))

    def test_final_codex_can_resolve_measurement_question_with_existing_plan(self):
        self.judge_action='needs_evidence';self.judge_issues=['효과 입증 부족']
        self.implementation['judge_issue_responses']=[dict(issue='효과 입증 부족',
            plan_quote=self.verdict['experiment']['success_criterion'],rationale='효과는 이 사전 기준으로 독립 평가하며 아직 입증됐다고 주장하지 않습니다.')]
        self.assertEqual(self.run_flow(),2)
        gate=read(self.folder/'development-gate.json')
        self.assertTrue(gate['allowed']);self.assertTrue(gate['judge_disagreement_preserved'])
        self.assertEqual(self.n_calls,1);self.assertEqual(len(self.codex_calls),3)

    def test_fabricated_plan_quote_cannot_resolve_judge(self):
        self.judge_action='needs_evidence';self.judge_issues=['효과 입증 부족']
        self.implementation['judge_issue_responses']=[dict(issue='효과 입증 부족',plan_quote='계획에 없는 성공 기준을 발명해서는 안 됩니다.',rationale='승인')]
        self.assertEqual(self.run_flow(),0)
        self.assertFalse(read(self.folder/'automation.json')['plan_approved'])

    def test_execution_boundary_shared_before_proposal_and_no_false_human_wait(self):
        self.implementation['final_decision']='wait'
        self.implementation['final_rationale']='지원하지 않는 worker 계측 계약 보완 필요'
        self.assertEqual(self.run_flow(),0)
        state=read(self.folder/'automation.json')
        self.assertEqual(state['status'],'stopped')
        proposal=dict(self.inputs)['verify']['shared_core']['execution_boundary']
        judge=dict(self.inputs)['judge']['debate']['shared_core']['execution_boundary']
        self.assertEqual(proposal,judge)
        self.assertIn('optimizer iterations',proposal['diagnostics'])


class FreeVerificationRefreshTest(FreeOnlyTest):
    def setUp(self):
        super().setUp()
        self.record=self.root/'verified.json'
        scope=patch.object(gemini,'FREE_VERIFICATION_FILE',self.record);scope.start();self.addCleanup(scope.stop)

    def test_refresh_does_not_mutate_frozen_config_or_request_digest(self):
        old=copy.deepcopy(self.config);old['free_tier_verification']['expires_at']=old['free_tier_verification']['verified_at']
        before=digest(old);save(self.record,self.proof)
        self.assertIsNone(gemini.free_project_reason(old));self.assertEqual(digest(old),before)

    def test_other_project_model_or_key_cannot_authorize_frozen_request(self):
        old=copy.deepcopy(self.config);old['free_tier_verification']['expires_at']=old['free_tier_verification']['verified_at']
        for change in ({'project_id':'other-project'},{'model':'paid-model'},{'key_sha256':'wrong'}):
            with self.subTest(change=change):
                save(self.record,dict(self.proof,**change))
                self.assertEqual(gemini.free_project_reason(old),'free_verification_expired')

    def test_expired_refresh_and_paid_refresh_still_block(self):
        for change in ({'expires_at':self.proof['verified_at']},{'billing_disabled':False}):
            with self.subTest(change=change),patch('google.genai.Client') as client:
                save(self.record,dict(self.proof,**change))
                with self.assertRaises(ValueError):gemini.Gemini(self.config)('prompt',1)
                client.assert_not_called()
