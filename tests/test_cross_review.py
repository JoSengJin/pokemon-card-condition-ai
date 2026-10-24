import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from card_condition.cross_review import execute, FIELDS, validate, digest, VERSION


class CrossReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'state.sqlite')
        self.key_file = Path(self.tmp.name) / 'cross-review-key.json'
        key_patch = patch('card_condition.cross_review.KEY_FILE', self.key_file)
        key_patch.start()
        self.addCleanup(key_patch.stop)
        self.config = json.loads(Path('examples/cross-review/config.json').read_text())
        self.packet = dict(stalled=True, stagnation_reason='Two identical outcomes', topic='test',
            error_cases=['e1'], code_excerpts=['e2'], same_evaluation_metrics={'FN': '0/4', 'FP': '5/22'},
            failed_hypotheses={'padding': ['e1']}, evidence={'e1': 'Same 26 regions unchanged', 'e2': 'max pooling'})
        self.response = dict.fromkeys(FIELDS, '')
        self.response.update(hypothesis_id='pooling', cause='pattern activation', evidence='e1',
            counter_evidence='e2', smallest_experiment='Change only pooling',
            success_criterion='FP below 5/22 with FN 0/4', failure_criterion='otherwise')
        self.calls = 0

    def caller(self, prompt, timeout):
        self.calls += 1
        return json.dumps(self.response), {'prompt_token_count': 20, 'candidates_token_count': 30, 'total_token_count': 50}

    def run_review(self, decision=None, caller=None):
        return execute(self.packet, self.config, self.db, caller=caller or self.caller, decision=decision)

    def decision(self, action='select', **kw):
        return dict(action=action, rationale='Compared local source to proposal', evidence_ids=['e1'], **kw)

    def test_select_resume_and_completed_run_never_recall(self):
        self.assertIn('__interrupt__', self.run_review())
        result = self.run_review(self.decision())
        self.assertEqual(result['status'], 'experiment_selected')
        self.assertEqual(result['selected']['hypothesis_id'], 'pooling')
        self.run_review()
        self.assertEqual(self.calls, 1)

    def test_repeated_claim_ends_second_call(self):
        self.run_review()
        r = self.run_review(self.decision('second', new_question='Could background explain it?'))
        self.assertEqual(r['status'], 'repeated_claim')
        self.assertEqual(self.calls, 2)

    def test_max_two_even_if_more_requested(self):
        self.run_review()
        self.response['cause'] = 'different cause'
        self.run_review(self.decision('second', new_question='Check a distinct cause'))
        r = self.run_review(self.decision('second', new_question='Third?'))
        self.assertEqual(r['status'], 'call_limit')
        self.assertEqual(self.calls, 2)

    def test_human_wait_resume_without_call(self):
        self.response['human_confirmation'] = 'Need a new source image'
        self.run_review()
        self.assertIn('__interrupt__', self.run_review(self.decision('wait')))
        r = self.run_review({'answer': 'Unavailable; keep unknown'})
        self.assertEqual(r['status'], 'human_answer_recorded')
        self.assertEqual(self.calls, 1)

    def test_cache_after_checkpoint_loss(self):
        self.run_review()
        with sqlite3.connect(self.db) as db:
            for table in ('checkpoints', 'writes'):
                db.execute('DELETE FROM ' + table)
        self.run_review()
        self.assertEqual(self.calls, 1)

    def test_error_stops_and_unknown_usage_remains_null(self):
        for code, status in [(429, 'quota_error'), (401, 'auth_error'), (403, 'auth_error'), (503, 'request_error')]:
            self.db = str(Path(self.tmp.name) / f'{code}.sqlite')
            class APIError(Exception):
                pass
            def fail(*args):
                self.calls += 1
                err = APIError('sensitive raw error must not persist')
                err.code = code
                raise err
            r = self.run_review(caller=fail)
            self.assertEqual(r['status'], status)
            self.assertIsNone(r['attempts'][0]['usage'])
            self.run_review(caller=fail)
            self.assertNotIn(b'sensitive raw error', Path(self.db).read_bytes())
        self.assertEqual(self.calls, 4)

    def test_pending_journal_does_not_retry_after_crash(self):
        def crash(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_review(caller=crash)
        r = self.run_review()
        self.assertEqual(r['status'], 'prior_request_pending')
        self.assertEqual(self.calls, 0)

    def test_missing_usage_not_zero(self):
        r = self.run_review(caller=lambda *args: (json.dumps(self.response), None))
        self.assertIsNone(r['attempts'][0]['usage'])

    def test_budget_blocks_before_call(self):
        self.config['input_budget'] = 1
        self.assertEqual(self.run_review()['status'], 'token_budget')
        self.assertEqual(self.calls, 0)

    def test_output_and_total_budget(self):
        for key in ('output_budget', 'total_budget'):
            self.config[key] = 1
            self.db = str(Path(self.tmp.name) / f'{key}.sqlite')
            self.assertEqual(self.run_review()['status'], 'token_budget')
            self.config[key] = 18048
        self.assertEqual(self.calls, 0)

    def test_time_budget_after_response(self):
        with patch('card_condition.cross_review.now', side_effect=[100, 101, 1000]):
            self.assertEqual(self.run_review()['status'], 'time_budget')

    def test_rejected_hypothesis_needs_new_evidence(self):
        self.response['hypothesis_id'] = 'padding'
        self.run_review()
        self.assertEqual(self.run_review(self.decision())['status'], 'rejected_hypothesis')

    def test_changed_input_requires_experiment_result(self):
        self.run_review()
        self.run_review(self.decision())
        self.packet['stagnation_reason'] += ' new'
        with self.assertRaisesRegex(ValueError, 'prior experiment result'):
            self.run_review()
        self.assertEqual(self.calls, 1)

    def test_bad_reference_cannot_select(self):
        self.run_review()
        with self.assertRaisesRegex(ValueError, 'Unknown evidence'):
            self.run_review(dict(action='select', rationale='test', evidence_ids=['invented']))
        self.assertEqual(self.calls, 1)

    def test_live_requires_free_verification_without_network(self):
        r = execute(self.packet, self.config, self.db)
        self.assertEqual(r['status'], 'live_blocked')

    def test_validates_call_cap_and_stagnation(self):
        self.config['max_calls'] = 4
        with self.assertRaises(ValueError):
            validate(self.packet, self.config)
        self.config['max_calls'] = 2
        self.packet['stalled'] = False
        with self.assertRaises(ValueError):
            validate(self.packet, self.config)

    def test_no_second_without_new_question(self):
        self.run_review()
        self.assertEqual(self.run_review(self.decision('second'))['status'], 'no_new_evidence_or_hypothesis')
        self.assertEqual(self.calls, 1)

    def test_invalid_model_json_stops(self):
        r = self.run_review(caller=lambda *args: ('{}', None))
        self.assertEqual(r['status'], 'response_error')
        self.assertEqual(r['error_kind'], 'invalid_schema')

    def test_response_errors_preserve_usage_and_never_retry(self):
        cases = [('not json secret-value', 'invalid_json'), ('[]', 'invalid_schema'),
                 (None, 'invalid_json'), (json.dumps(dict(self.response, evidence=['e1'])), 'invalid_schema')]
        for index, (raw, kind) in enumerate(cases):
            with self.subTest(kind=kind, raw=raw):
                database = str(Path(self.tmp.name) / ('invalid-' + str(index) + '.sqlite'))
                with patch.object(self, 'caller', return_value=(raw, {'total_token_count': 4667})) as caller:
                    result = execute(self.packet, self.config, database, caller=caller)
                    self.assertEqual(result['status'], 'response_error')
                    self.assertEqual(result['error_kind'], kind)
                    self.assertEqual(result['attempts'][0]['usage']['total_token_count'], 4667)
                    self.assertFalse(result['pending'])
                    execute(self.packet, self.config, database, caller=caller)
                    caller.assert_called_once()
                with sqlite3.connect(database) as db:
                    diagnostic = db.execute('SELECT result FROM calls').fetchone()[0]
                self.assertEqual(json.loads(diagnostic)['error_kind'], kind)
                self.assertTrue(json.loads(diagnostic)['exception_chain'])
                self.assertNotIn('secret-value', diagnostic)

    def test_request_error_preserves_safe_chain_and_checkpoint_without_retry(self):
        def fail(*args):
            try:
                raise PermissionError(1, 'secret-key https://private/request sensitive-packet')
            except PermissionError as cause:
                raise RuntimeError('secret-key sensitive-packet') from cause
        with patch.object(self, 'caller', side_effect=fail) as caller:
            result=self.run_review(caller=caller)
            chain=result['error_diagnostic']['exception_chain']
            self.assertEqual([x['type'] for x in chain],['builtins.RuntimeError','builtins.PermissionError'])
            self.assertEqual(chain[1]['errno'],1)
            self.assertTrue(chain[0]['frames'])
            resumed=self.run_review(caller=caller)
            caller.assert_called_once()
            self.assertEqual(resumed['error_diagnostic'],result['error_diagnostic'])
        with sqlite3.connect(self.db) as db:
            diagnostic=db.execute('SELECT result FROM calls').fetchone()[0]
        self.assertNotIn('secret-key',diagnostic)
        self.assertNotIn('sensitive-packet',diagnostic)
        self.assertNotIn('https://',diagnostic)

    def test_sdk_retry_thinking_and_timeout_configuration(self):
        from card_condition.cross_review import Gemini
        from unittest.mock import MagicMock
        from datetime import datetime,timedelta,timezone
        import hashlib
        current=datetime.now(timezone.utc)
        self.config['free_tier_verification']=dict(tier='Free',project_id='test-only',billing_disabled=True,model=self.config['model'],verified_at=current.isoformat(),expires_at=(current+timedelta(hours=1)).isoformat(),evidence='mock only',key_sha256=hashlib.sha256(b'test-only').hexdigest())
        response = MagicMock(text=json.dumps(self.response), usage_metadata=None)
        client = MagicMock()
        client.__enter__.return_value.models.generate_content.return_value = response
        with patch.dict('os.environ', {'POKEMON_CARD_CONDITION_GEMINI_API_KEY': 'test-only'}), patch('google.genai.Client', return_value=client) as factory:
            text, usage = Gemini(self.config)('bounded prompt', 2.5)
        self.assertIsNone(usage)
        options = factory.call_args.kwargs['http_options']
        self.assertEqual(options.retry_options.attempts, 1)
        self.assertEqual(options.timeout, 2500)
        args = client.__enter__.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(args['model'], self.config['model'])
        self.assertEqual(args['config'].thinking_config.thinking_level, 'MINIMAL')
        self.assertIsNone(args['config'].thinking_config.thinking_budget)
        self.assertEqual(args['config'].max_output_tokens, 1024)
        schema = args['config'].response_json_schema
        self.assertEqual(schema['required'], list(FIELDS))
        self.assertEqual(schema['properties'], {key: {'type': 'string'} for key in FIELDS})
        self.assertFalse(schema['additionalProperties'])

    def test_prior_result_allows_distinct_manual_run(self):
        old = self.run_review()['run']
        self.run_review(self.decision())
        self.packet['evidence']['result'] = 'Actual measured experiment failed'
        self.packet['previous_experiment_result'] = {'run': old, 'evidence_ids': ['result']}
        new = self.run_review()['run']
        self.assertNotEqual(old, new)
        self.assertEqual(self.calls, 2)

    def test_reopen_requires_distinct_evidence(self):
        self.packet['reopen_evidence'] = {'padding': ['e1']}
        with self.assertRaisesRegex(ValueError, 'new evidence'):
            self.run_review()
        self.packet['evidence']['new'] = 'New counter evidence'
        self.packet['reopen_evidence'] = {'padding': ['new']}
        self.response['hypothesis_id'] = 'padding'
        self.run_review()
        r = self.run_review(dict(action='select', rationale='Validated new counter evidence', evidence_ids=['new']))
        self.assertEqual(r['status'], 'experiment_selected')

    def test_cli_dry_run_never_constructs_client(self):
        from card_condition.cross_review import main
        from contextlib import redirect_stdout
        import io
        packet = Path(self.tmp.name) / 'packet.json'
        packet.write_text(json.dumps(self.packet))
        with patch('sys.argv', ['cross-review', str(packet), '--config', 'examples/cross-review/config.json']), patch('google.genai.Client') as client, redirect_stdout(io.StringIO()) as output:
            main()
        client.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['max_calls'], 2)

    def test_only_project_specific_key_is_used(self):
        from card_condition.cross_review import api_key
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'other-project-key'}, clear=True):
            self.assertEqual(api_key(self.config), '')
            self.assertEqual(execute(self.packet, self.config, self.db)['status'], 'live_blocked')
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'other-project-key',
                'POKEMON_CARD_CONDITION_GEMINI_API_KEY': 'this-project-key'}, clear=True):
            self.assertEqual(api_key(self.config), 'this-project-key')

    def test_other_project_secret_file_is_never_read(self):
        from card_condition.cross_review import api_key
        with patch.dict('os.environ', {}, clear=True), patch('pathlib.Path.read_text', return_value='{}') as read:
            self.assertEqual(api_key({'api_key_file': '/other-project/secrets.json'}), '')
        self.assertEqual(read.call_count, 1)

    def test_dedicated_local_key_and_environment_override(self):
        from card_condition.cross_review import api_key
        self.key_file.write_text(json.dumps({'api_key': 'dedicated-test-key'}))
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(api_key(self.config), 'dedicated-test-key')
        with patch.dict('os.environ', {'POKEMON_CARD_CONDITION_GEMINI_API_KEY': 'override-key'}):
            self.assertEqual(api_key(self.config), 'override-key')

    def test_model_specific_thinking_validation(self):
        config = dict(self.config, thinking_budget=0)
        with self.assertRaisesRegex(ValueError, 'without legacy budget'):
            validate(self.packet, config)
        config.pop('thinking_level')
        config['model'] = 'gemini-2.5-flash-lite'
        validate(self.packet, config)

    def test_explicit_stop_overrides_model_human_request(self):
        self.response['human_confirmation'] = 'Need new human labels'
        self.run_review()
        result = self.run_review(self.decision('stop'))
        self.assertEqual(result['status'], 'unresolved')
        self.assertFalse(result.get('pending'))
        self.assertEqual(self.calls, 1)

    def test_three_call_cap(self):
        self.config.update(max_calls=3, output_budget=4096, total_budget=24000)
        self.run_review()
        self.response['cause'] = 'second cause'
        self.run_review(self.decision('second', new_question='Question two'))
        self.response['cause'] = 'third cause'
        self.run_review(self.decision('second', new_question='Question three'))
        result = self.run_review(self.decision('second', new_question='Fourth question'))
        self.assertEqual(result['status'], 'call_limit')
        self.assertEqual(self.calls, 3)

    def test_same_question_and_refs_stop_even_with_changed_prior_proposal(self):
        self.config.update(max_calls=3, output_budget=4096, total_budget=24000)
        self.run_review()
        self.response['cause'] = 'second cause'
        self.run_review(self.decision('second', new_question='Same question', previous_proposal={'cause': 'first'}))
        result = self.run_review(self.decision('second', new_question='Same question', previous_proposal={'cause': 'second'}))
        self.assertEqual(result['status'], 'no_new_evidence_or_hypothesis')
        self.assertEqual(self.calls, 2)

    def test_korean_prompt_keeps_json_contract(self):
        from card_condition.cross_review import KOREAN_VERSION
        self.config['prompt_version'] = KOREAN_VERSION
        self.packet['fresh_evidence_ids']=['e1']
        self.response.update(proposal_status='propose',new_evidence_ids=['e1'],compared_failed_hypotheses=['padding'],difference_from_failed='집계 변수를 분리')
        self.response.update(cause='높은 반응의 원인을 분리해야 한다', smallest_experiment='변수 하나를 고정 대조한다')
        def caller(prompt, timeout):
            self.assertIn('모든 설명은 한국어로 작성한다', prompt)
            self.assertIn('수석 컴퓨터비전 개발자', prompt)
            self.assertIn('CGC 등급평가를 지원하는 AI', prompt)
            self.assertIn('제공된 코드·오류 사진 설명·실험 수치·실패 이력', prompt)
            return self.caller(prompt, timeout)
        result = self.run_review(caller=caller)
        self.assertIn('__interrupt__', result)
        self.assertEqual(self.run_review(self.decision())['status'], 'experiment_selected')
        self.assertEqual(self.calls, 1)

    def test_senior_role_versions_prompt_without_rewriting_legacy(self):
        from card_condition.cross_review import KOREAN_VERSION,LEGACY_KOREAN_VERSION,PROMPTS,korean_response_ok
        self.assertNotEqual(KOREAN_VERSION,LEGACY_KOREAN_VERSION)
        self.assertIn('수석 컴퓨터비전 개발자',PROMPTS[KOREAN_VERSION])
        self.assertNotIn('수석 컴퓨터비전 개발자',PROMPTS[LEGACY_KOREAN_VERSION])
        self.assertFalse(korean_response_ok(self.response,LEGACY_KOREAN_VERSION))

    def test_english_response_to_korean_prompt_does_not_retry_or_reappear_from_cache(self):
        from card_condition.cross_review import KOREAN_VERSION
        self.config['prompt_version'] = KOREAN_VERSION
        self.packet['fresh_evidence_ids']=['e1']
        self.response.update(proposal_status='propose',new_evidence_ids=['e1'],compared_failed_hypotheses=['padding'],difference_from_failed='집계 변수를 분리')
        self.assertEqual(self.run_review()['status'], 'response_language_mismatch')
        with sqlite3.connect(self.db) as db:
            for table in ('checkpoints', 'writes'):
                db.execute('DELETE FROM ' + table)
        self.assertEqual(self.run_review()['status'], 'response_language_mismatch')
        self.assertEqual(self.calls, 1)

    def grounded(self):
        from card_condition.cross_review import KOREAN_VERSION
        self.config['prompt_version']=KOREAN_VERSION
        self.packet['fresh_evidence_ids']=['e1']
        self.response.update(proposal_status='propose',new_evidence_ids=['e1'],compared_failed_hypotheses=['padding'],difference_from_failed='새 측정에 따른 집계 조건 변경',cause='원인 검토',smallest_experiment='집계 변수 하나 변경')

    def test_no_fresh_evidence_stops_before_model_call(self):
        self.grounded();self.packet['fresh_evidence_ids']=[]
        self.assertEqual(self.run_review()['status'],'no_new_evidence')
        self.assertEqual(self.calls,0)

    def test_explicit_stop_preserves_reason_without_selecting_experiment(self):
        self.grounded();self.response.update(proposal_status='stop',new_evidence_ids=[],smallest_experiment='',cause='새 근거가 부족함')
        result=self.run_review()
        self.assertEqual(result['status'],'no_new_evidence');self.assertNotIn('selected',result)
        self.assertEqual(self.calls,1)

    def test_execution_failure_is_not_fresh_measured_evidence(self):
        self.grounded();self.response['new_evidence_ids']=['failed_execution_0']
        self.assertEqual(self.run_review()['status'],'no_new_evidence');self.assertEqual(self.calls,1)

    def test_missing_failed_comparison_or_condition_difference_blocks(self):
        from card_condition.cross_review import proposal_gate,KOREAN_VERSION
        self.grounded()
        for update in (dict(compared_failed_hypotheses=[]),dict(difference_from_failed='')):
            self.assertEqual(proposal_gate(self.packet,dict(self.response,**update),KOREAN_VERSION),'unsupported_proposal')

    def test_failed_hypothesis_needs_explicit_reopen_evidence(self):
        from card_condition.cross_review import proposal_gate,KOREAN_VERSION
        self.grounded();self.response['hypothesis_id']='padding'
        self.assertEqual(proposal_gate(self.packet,self.response,KOREAN_VERSION),'rejected_hypothesis')
        self.packet['reopen_evidence']={'padding':['e1']}
        self.assertIsNone(proposal_gate(self.packet,self.response,KOREAN_VERSION))


if __name__ == '__main__':
    unittest.main()
