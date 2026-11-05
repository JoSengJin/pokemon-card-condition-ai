import contextlib
import copy
from datetime import datetime,timezone,timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from card_condition import cross_review_nemotron as n
from card_condition import cross_review_auto as auto
from card_condition.cross_review_debate import render,quality
from card_condition.experiment_record import read,save
import test_cross_review_auto as fixture


class NemotronTest(unittest.TestCase):
    setUp=fixture.AutoReviewTest.setUp
    start=fixture.AutoReviewTest.start
    gemini=fixture.AutoReviewTest.gemini
    backend=fixture.AutoReviewTest.backend
    run_auto=fixture.AutoReviewTest.run_auto

    def configure(self):
        now=datetime.now(timezone.utc)
        setting=read(Path('nemotron-review.json'))
        setting['allow_project_evidence']=True
        setting['free_verification']=dict(billing_disabled=True,evidence='mock only',verified_at=now.isoformat(),expires_at=(now+timedelta(hours=1)).isoformat(),key_sha256=hashlib.sha256(b'fake-nvidia-key').hexdigest())
        save(self.root/'nemotron-review.json',setting)
        env=patch.dict(os.environ,{'POKEMON_CARD_CONDITION_NVIDIA_API_KEY':'fake-nvidia-key'})
        env.start();self.addCleanup(env.stop)
        return setting

    def answer(self, payload, timeout):
        self.n_calls+=1
        self.assertEqual(payload['model'],n.MODEL)
        self.assertLessEqual(payload['max_tokens'],1536)
        self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
        return json.dumps(dict(stance='object',support_score=0,opposition_score=2,rationale='실패 조건과 사람점 보호를 대조해야 합니다.',evidence_ids=['latest_result'],proposal=dict(self.response))),dict(prompt_tokens=30,completion_tokens=20,total_tokens=50)

    def call(self,result=None,question=''):
        if result is None:result=self.start()
        return n.review(self.root,self.folder,result,question=question,caller=self.answer,probe=lambda:'available')

    def test_eligible_mock_response_cached_without_losing_actual_attempt_count(self):
        self.configure();self.n_calls=0;result=self.start()
        first=self.call(result);again=self.call(result)
        self.assertEqual(first['status'],'complete');self.assertTrue(again['reused'])
        self.assertEqual(self.n_calls,1)
        report=auto.token_report(self.folder,result)
        self.assertEqual(report['nemotron_calls'],1);self.assertEqual(report['nemotron_usage']['total_tokens'],50)
        self.assertLessEqual(len(json.dumps(n.compact(first),ensure_ascii=False,separators=(',',':')).encode()),1000)

    def test_judge_projection_keeps_frozen_original_for_core_check(self):
        from card_condition.cross_review_contract import shared_core
        from card_condition.cross_review_judge_projection import judge_packet
        result=self.start()
        original=copy.deepcopy(result['packet'])
        original['evidence']['latest_result']['summary']['required_cohorts']=[
            dict(id='edge',acceptance_passed=False,error_count=1,errors=['sample'])]
        shared_core(self.root,self.folder,original)
        projected=judge_packet(original)
        self.assertNotEqual(original['evidence'],projected['evidence'])
        result.update(packet=original,judge_packet=projected,deadline=time.time()+45)
        with (patch.object(n,'policy',return_value={'enabled': True, 'max_calls': 2, 'max_output_tokens': 1536}),
              patch.object(n,'eligible',return_value=None),
              patch.object(n,'judge_input',return_value={'bounded': True}) as build):
            entry=n.review(self.root,self.folder,result,role='judge',context={},
                           caller=lambda *_: ('{}',None),probe=lambda:'available')
        self.assertEqual(entry['error_kind'],'response_error')
        self.assertEqual(build.call_args.args[0],projected)

    def test_different_folder_reuses_cache_with_no_extra_attempt(self):
        self.configure();self.n_calls=0;result=self.start();self.call(result)
        other=self.root/'artifacts/manual-cross-review/other';other.mkdir()
        entry=n.review(self.root,other,result,caller=self.answer,probe=lambda:'available')
        self.assertTrue(entry['reused']);self.assertFalse(entry['attempted']);self.assertEqual(self.n_calls,1)

    def test_consent_free_status_key_and_expiry_gate_before_any_request(self):
        setting=self.configure();self.n_calls=0;result=self.start()
        for change in (dict(allow_project_evidence=False),dict(free_endpoint_status='deprecated'),dict(model='paid/other'),dict(free_verification=None)):
            save(self.root/'nemotron-review.json',dict(setting,**change))
            self.assertEqual(self.call(result)['status'],'excluded')
        self.assertEqual(self.n_calls,0)
        self.assertTrue((self.root/'artifacts/provider-alerts/nemotron.json').exists())

    def test_official_status_change_or_unknown_excludes_provider_without_call(self):
        self.configure();self.n_calls=0;result=self.start()
        for status in ('deprecated','unknown','unavailable'):
            entry=n.review(self.root,self.folder,result,caller=self.answer,probe=lambda:status)
            self.assertEqual(entry['status'],'excluded')
        self.assertEqual(self.n_calls,0)

    def test_pending_journal_never_retries_after_interrupt(self):
        self.configure();result=self.start()
        def crash(*args):raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):n.review(self.root,self.folder,result,caller=crash,probe=lambda:'available')
        self.n_calls=0;entry=self.call(result)
        self.assertIn('pending',entry['reason']);self.assertEqual(self.n_calls,0)

    def test_error_disables_provider_and_logs_structure_without_secret(self):
        self.configure();result=self.start()
        def failure(*args):raise RuntimeError('secret-DO-NOT-LOG')
        entry=n.review(self.root,self.folder,result,caller=failure,probe=lambda:'available')
        self.assertEqual(entry['status'],'error');self.n_calls=0
        self.assertEqual(self.call(result)['reason'],'circuit_open_manual_recheck_required')
        self.assertEqual(self.n_calls,0)
        text=''.join(p.read_text() for p in (self.root/'artifacts/nemotron-cache').glob('*/call.json'))
        self.assertNotIn('secret-DO-NOT-LOG',text)
        self.assertIsNone(auto.token_report(self.folder,result)['nemotron_usage']['total_tokens'])

    def test_schema_failure_keeps_raw_response_usage_and_specific_errors(self):
        self.configure();result=self.start()
        raw='{"stance":"object"}'
        entry=n.review(self.root,self.folder,result,caller=lambda *args:(raw,dict(prompt_tokens=7,completion_tokens=3,total_tokens=10)),probe=lambda:'available')
        self.assertEqual(entry['raw_response'],raw)
        self.assertEqual(entry['validation_errors'],['top_level_fields'])
        self.assertEqual(entry['usage']['total_tokens'],10)
        self.assertEqual(entry['error_kind'],'response_error')
        render(self.root,self.folder)
        self.assertIn('top_level_fields',(self.folder/'debate.html').read_text())

    def test_truncated_http_response_preserves_usage_and_public_text(self):
        import httpx
        self.configure();result=self.start()
        body=dict(choices=[dict(message=dict(content='partial JSON'),finish_reason='length')],usage=dict(prompt_tokens=8,completion_tokens=5,total_tokens=13))
        response=httpx.Response(200,json=body,request=httpx.Request('POST',n.ENDPOINT))
        with patch('httpx.post',return_value=response), patch.object(n,'official_status',return_value='available'):
            entry=n.review(self.root,self.folder,result,probe=lambda:'available')
        self.assertEqual(entry['usage']['total_tokens'],13)
        self.assertEqual(entry['raw_response'],'partial JSON')
        self.assertEqual(entry['status'],'error')

    def test_payment_signal_stops_with_structural_log_and_no_key_leak(self):
        import httpx
        self.configure();result=self.start()
        response=httpx.Response(402,json={'error':'secret-DO-NOT-LOG'},request=httpx.Request('POST',n.ENDPOINT))
        with patch('httpx.post',return_value=response), patch.object(n,'official_status',return_value='available'):
            entry=n.review(self.root,self.folder,result,probe=lambda:'available')
        self.assertEqual(entry['error_kind'],'payment_required')
        self.assertNotIn('secret-DO-NOT-LOG',json.dumps(entry))
        self.assertEqual(entry['diagnostic']['exception_chain'][0]['http_status'],402)

    def test_free_probe_error_is_logged_without_model_request(self):
        self.configure();result=self.start();self.n_calls=0
        def failed_probe():raise TimeoutError('secret-DO-NOT-LOG')
        entry=n.review(self.root,self.folder,result,caller=self.answer,probe=failed_probe)
        self.assertEqual(entry['status'],'excluded');self.assertEqual(self.n_calls,0)
        log=read(self.root/'artifacts/provider-alerts/nemotron-free-check.json')
        self.assertNotIn('secret-DO-NOT-LOG',json.dumps(log))
        self.assertIn('TimeoutError',log['diagnostic']['exception_chain'][0]['type'])

    def test_stored_stop_is_read_only_even_if_model_copied_failed_experiment(self):
        self.configure();self.n_calls=0;result=self.start()
        raw,_=self.answer(dict(model=n.MODEL,max_tokens=100,chat_template_kwargs={'enable_thinking':False}),1)
        value=json.loads(raw);value['stance']='stop';value['proposal']['proposal_status']='stop'
        value['proposal']['compared_failed_hypotheses']=[]
        value['proposal']['smallest_experiment']='이미 실패한 복사된 실험'
        source=dict(status='error',error_kind='response_error',raw_response=json.dumps(value),usage={'total_tokens':9})
        recovered=n.safe_stored_stop(source,self.packet)
        self.assertEqual(source['status'],'error')
        self.assertEqual(recovered['status'],'reviewed_stop')
        self.assertEqual(set(recovered['warnings']),{'stop_experiment_ignored','failed_history_mismatch'})
        summary=n.compact(recovered,max_bytes=10000)
        self.assertEqual(summary['experiment'],'');self.assertEqual(summary['hypothesis_id'],'')
        self.assertEqual(summary['proposal_status'],'stop')
        self.assertIsNone(n.safe_stored_stop(dict(source,error_kind='quota_error'),self.packet))

    def test_total_two_call_cap_and_zero_thinking(self):
        self.configure();self.n_calls=0;result=self.start()
        self.assertEqual(self.call(result,'first')['status'],'complete')
        self.assertEqual(self.call(result,'second')['status'],'complete')
        self.assertEqual(self.call(result,'third')['reason'],'call_or_token_budget')
        self.assertEqual(self.n_calls,2)

    def test_input_and_time_budget_stop_before_request(self):
        setting=self.configure();self.n_calls=0;result=self.start()
        save(self.root/'nemotron-review.json',dict(setting,max_input_bytes=1))
        self.assertEqual(self.call(result)['reason'],'call_or_token_budget')
        save(self.root/'nemotron-review.json',setting);result['deadline']=0
        self.assertEqual(self.call(result)['reason'],'time_budget');self.assertEqual(self.n_calls,0)

    def test_invalid_scores_unknown_refs_or_failed_reproposal_rejected(self):
        self.configure();self.n_calls=0;result=self.start()
        raw,_=self.answer(dict(model=n.MODEL,max_tokens=100,chat_template_kwargs={'enable_thinking':False}),1)
        good=json.loads(raw)
        for update in (dict(support_score=3),dict(evidence_ids=['invented']),dict(proposal=dict(self.response,hypothesis_id=next(iter(self.packet['failed_hypotheses']))))):
            self.assertFalse(n.response_valid(dict(good,**update),self.packet))

    def test_html_uses_actual_public_messages_and_escapes_html(self):
        result=self.start();result['response']['cause']='<script>alert(1)</script>'
        save(self.folder/'result.json',{k:v for k,v in result.items() if k!='__interrupt__'})
        # Imported response without a database: no invented Codex/Nemotron messages.
        (self.folder/'state.sqlite').unlink()
        output=render(self.root,self.folder,provenance='mock')
        text=output.read_text();self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text)
        data=read(output.with_suffix('.json'));self.assertEqual([e['agent'] for e in data['events']],['Gemini'])
        self.assertIn('모의 예시',text)
        self.assertFalse(quality(self.packet,dict(self.response,hypothesis_id=next(iter(self.packet['failed_hypotheses']))))['repeat_avoided'])


if __name__=='__main__':unittest.main()
