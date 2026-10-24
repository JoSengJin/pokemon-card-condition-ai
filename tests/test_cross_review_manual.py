from datetime import datetime,timedelta,timezone
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import cross_review_manual as manual
from card_condition.cross_review import FIELDS


class ManualReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        from card_condition.regression_audit import compare_predictions
        config = json.loads(Path('examples/cross-review/config.json').read_text())
        config['free_tier_verification'] = dict(tier='Free', project_id='test-project',
            model=config['model'], billing_disabled=True, verified_at=datetime.now(timezone.utc).isoformat(), expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(), evidence='test evidence', key_sha256=hashlib.sha256(b'test-key').hexdigest())
        cp = self.root / 'artifacts/cross-review-20261019/local-config.json'
        cp.parent.mkdir(parents=True)
        cp.write_text(json.dumps(config))
        code = self.root / 'card_condition/model.py'
        code.parent.mkdir()
        code.write_text('def infer(logits):\n    return max(logits)\n')
        folder = self.root / 'artifacts/experiment-20261019'
        folder.mkdir()
        rows = [{'id': 'p', 'target': 1, 'group': 'p', 'image_sha256': 'p', 'box': [0,0,1,1]},
                {'id': 'n', 'target': 0, 'group': 'n', 'image_sha256': 'n', 'box': [0,0,1,1]}]
        self.source_result = folder / 'result.json'
        self.source_result.write_text(json.dumps(dict(rows=rows, before_scores=[.9,.8], scores=[.9,.8],
            comparison=compare_predictions([1,0],[.9,.8],[.9,.8]), independent=False)))
        (folder / 'plan.json').write_text(json.dumps({'hypothesis': 'test', 'tracked_sha256': {str(code): 'old-hash'}}))
        self.response = dict.fromkeys(FIELDS, '')
        self.response.update(proposal_status='propose',new_evidence_ids=['latest_result'],compared_failed_hypotheses=list(manual.latest_packet(self.root)['failed_hypotheses']),difference_from_failed='기존 실패 조건과 다른 집계 변수를 새 결과로 대조')
        self.response.update(hypothesis_id='test', cause='검증용 원인 가설', evidence='e1',
            human_confirmation='Need additional evidence, do not invent labels')
        self.usage = dict(prompt_token_count=20, candidates_token_count=30, total_token_count=50)
        patches = [patch.object(manual, 'ROOT', self.root),
                   patch.dict('os.environ', {'POKEMON_CARD_CONDITION_GEMINI_API_KEY': 'test-key'}, clear=True),
                   patch.object(manual.sys.stdin, 'isatty', return_value=True),
                   patch('card_condition.cross_review.Gemini.__call__', return_value=(json.dumps(self.response), self.usage)),
                   patch('httpx.Client.send', side_effect=AssertionError('No real API calls in tests'))]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.api = self.mocks[3]
        self.output = io.StringIO()

    def run_manual(self, answers, interactive=True):
        with patch('builtins.input', side_effect=answers), contextlib.redirect_stdout(self.output):
            return manual.main(['--interactive'] if interactive else [])

    def active(self):
        p = self.root / 'artifacts/manual-cross-review/active.json'
        value = json.loads(p.read_text())
        return value, Path(value['directory'])

    def test_one_command_call_pause_resume_end(self):
        self.assertEqual(self.run_manual(['']), 0)
        active, folder = self.active()
        self.assertTrue(active['finished'])
        result = json.loads((folder / 'result.json').read_text())
        self.assertEqual(result['status'], 'unresolved')
        self.assertFalse(result['pending'])
        self.assertEqual(len(result['attempts']), 1)
        self.assertEqual(json.loads((folder / 'config.json').read_text())['max_calls'], 3)
        self.assertIn('[LangGraph 중단]', self.output.getvalue())
        self.assertIn('합계 50', self.output.getvalue())
        self.assertNotIn('test-key', self.output.getvalue())
        self.api.assert_called_once()

    def test_q_then_same_command_resumes_without_second_api(self):
        self.assertEqual(self.run_manual(['q']), 0)
        before, folder = self.active()
        self.assertFalse(before['finished'])
        self.assertEqual(self.run_manual(['']), 0)
        after, resumed_folder = self.active()
        self.assertEqual(folder, resumed_folder)
        self.assertTrue(after['finished'])
        self.api.assert_called_once()

    def test_ctrl_c_at_prompt_can_resume_without_api(self):
        self.assertEqual(self.run_manual([KeyboardInterrupt()]), 130)
        self.assertFalse(self.active()[0]['finished'])
        self.assertEqual(self.run_manual(['']), 0)
        self.api.assert_called_once()

    def test_network_interruption_is_not_retried(self):
        self.api.side_effect = KeyboardInterrupt()
        self.assertEqual(self.run_manual([]), 130)
        self.api.side_effect = None
        self.assertEqual(self.run_manual([]), 1)
        result = json.loads((self.active()[1] / 'result.json').read_text())
        self.assertEqual(result['status'], 'prior_request_pending')
        self.api.assert_called_once()

    def test_invalid_choice_does_not_recall_api(self):
        self.assertEqual(self.run_manual(['second', '']), 0)
        self.api.assert_called_once()

    def test_next_completed_invocation_reuses_same_review(self):
        self.run_manual([''])
        first = self.active()[1]
        self.run_manual([''])
        self.assertEqual(first, self.active()[1])
        self.api.assert_called_once()

    def test_default_one_call_no_input_and_repeated_launch_no_api(self):
        self.assertEqual(self.run_manual([], interactive=False), 0)
        folder = self.active()[1]
        self.assertTrue((folder / 'next_steps.md').exists())
        self.assertTrue((folder / 'next_steps.json').exists())
        self.assertEqual(self.run_manual([], interactive=False), 0)
        self.assertEqual(folder, self.active()[1])
        self.api.assert_called_once()
        self.assertIn('이번 Gemini 추가 호출 0회', self.output.getvalue())

    def test_latest_failed_common_experiment_blocks_api_with_visible_status(self):
        from card_condition.experiment_record import LatestExperimentUnavailable
        with patch.object(manual,'latest_packet',side_effect=LatestExperimentUnavailable('최신 공통 실험 상태: failed')), contextlib.redirect_stderr(self.output):
            self.assertEqual(self.run_manual([],interactive=False),1)
        self.assertIn('최신 공통 실험 상태: failed',self.output.getvalue())
        self.assertIn('Gemini를 호출하지 않았습니다',self.output.getvalue())
        self.api.assert_not_called()

    def test_default_then_interactive_can_extend_to_three(self):
        self.api.side_effect = [(json.dumps(dict(self.response, human_confirmation='', cause=cause)), self.usage)
                                for cause in ('첫 가설', '두번째 가설', '세번째 가설')]
        self.assertEqual(self.run_manual([], interactive=False), 0)
        folder = self.active()[1]
        self.assertEqual(self.run_manual(['r', 'q']), 0)
        self.assertEqual(self.api.call_count, 2)
        self.assertEqual(self.run_manual([], interactive=False), 0)
        self.assertEqual(self.api.call_count, 2)
        self.assertEqual(self.run_manual(['r', 'r', '']), 0)
        self.assertEqual(self.api.call_count, 3)
        self.assertEqual(folder, self.active()[1])

    def test_changed_evidence_creates_new_run_and_old_response_is_reused_later(self):
        self.run_manual([], interactive=False)
        first = self.active()[1]
        code = self.root / 'card_condition/model.py'
        old = code.read_text()
        code.write_text(old + '\n# 새 진단 근거\n')
        self.run_manual([], interactive=False)
        self.assertNotEqual(first, self.active()[1])
        self.assertEqual(self.api.call_count, 2)
        code.write_text(old)
        self.run_manual([], interactive=False)
        self.assertEqual(first, self.active()[1])
        self.assertEqual(self.api.call_count, 2)

    def test_same_data_api_error_is_not_retried_on_new_invocation(self):
        class QuotaError(Exception):
            code = 429
        self.api.side_effect = QuotaError()
        self.assertEqual(self.run_manual([], interactive=False), 1)
        self.assertEqual(self.run_manual([], interactive=False), 1)
        self.api.assert_called_once()
        summary = json.loads((self.active()[1] / 'next_steps.json').read_text())
        self.assertEqual(summary['category'], 'check_error')
        text = (self.active()[1] / 'next_steps.md').read_text()
        self.assertIn('사용 가능한 반론: 없음', text)
        self.assertIn('프로그램이 만든 요약', text)
        self.assertNotIn('가설 ID(식별자): 미기재', text)
        self.assertNotIn('실험 하나와 판정 기준을 확정한 후 실행', text)
        self.assertIn('추가 Gemini 호출이나 제안 실험은 하지 마세요', text)

    def test_successful_saved_response_wins_over_newer_failure_without_api(self):
        import shutil
        import os
        self.run_manual([], interactive=False)
        success = self.active()[1]
        failed = success.parent / 'newer-failed'
        shutil.copytree(success, failed)
        result = json.loads((failed/'result.json').read_text())
        result.update(status='request_error', response=None, pending=[])
        (failed/'result.json').write_text(json.dumps(result))
        stamp = (success/'packet.json').stat().st_mtime + 100
        os.utime(failed/'packet.json', (stamp, stamp))
        manual.save(success.parent/'active.json', {'directory': str(failed), 'finished': True})
        self.assertEqual(self.run_manual([], interactive=False), 0)
        self.assertEqual(self.active()[1], success)
        self.assertIn('정상 응답이 저장된 검토를 우선', self.output.getvalue())
        self.assertIn('검증용 원인 가설', (success/'next_steps.md').read_text())
        self.api.assert_called_once()

    def test_incomplete_or_failed_response_is_not_preferred_over_valid_success(self):
        import shutil
        import os
        self.run_manual([], interactive=False)
        success = self.active()[1]
        for index, changes in enumerate([dict(response={'cause': '불완전 가설'}),
                                         dict(status='response_error'),
                                         dict(response=dict(self.response, cause='English only'))]):
            other = success.parent / ('bad-' + str(index))
            shutil.copytree(success, other)
            result = json.loads((other/'result.json').read_text())
            result.update(changes)
            (other/'result.json').write_text(json.dumps(result))
            stamp = (success/'packet.json').stat().st_mtime + 100 + index
            os.utime(other/'packet.json', (stamp, stamp))
        self.assertEqual(self.run_manual([], interactive=False), 0)
        self.assertEqual(self.active()[1], success)
        self.api.assert_called_once()

    def test_missing_database_never_repeats_saved_call(self):
        self.run_manual([], interactive=False)
        (self.active()[1] / 'state.sqlite').unlink()
        self.assertEqual(self.run_manual([], interactive=False), 0)
        with contextlib.redirect_stderr(self.output):
            self.assertEqual(self.run_manual([], interactive=True), 1)
        self.api.assert_called_once()

    def test_identity_ignores_run_names_but_includes_model_prompt_and_evidence(self):
        packet = {'topic': 'a', 'manual_run_purpose': 'a', 'evidence': {'e': 'same'}}
        config = {'model': 'm', 'prompt_version': 'p'}
        key = manual.review_identity(packet, config)
        self.assertEqual(key, manual.review_identity(dict(packet, topic='b', manual_run_purpose='b'), config))
        self.assertNotEqual(key, manual.review_identity(packet, dict(config, model='other')))
        self.assertNotEqual(key, manual.review_identity(packet, dict(config, prompt_version='other')))
        self.assertNotEqual(key, manual.review_identity(dict(packet, evidence={'e': 'changed'}), config))

    def test_next_steps_rejected_hypothesis_and_actionable_proposal(self):
        self.api.return_value = (json.dumps(dict(self.response, human_confirmation='', hypothesis_id='experiment-20261019')),
                                self.usage)
        self.run_manual([], interactive=False)
        folder = self.active()[1]
        self.assertEqual(json.loads((folder/'next_steps.json').read_text())['category'], 'reject_repeated_hypothesis')
        result = json.loads((folder/'result.json').read_text())
        result['status']='compare'
        result['response'].update(hypothesis_id='fresh', smallest_experiment='변수 하나만 바꾸기',
                                  success_criterion='동일 자료 FP 감소, FN 유지', failure_criterion='FP 유지 또는 FN 증가')
        with contextlib.redirect_stdout(self.output):
            manual.next_steps(folder, result)
        summary = json.loads((folder/'next_steps.json').read_text())
        self.assertEqual(summary['category'], 'check_experiment')
        self.assertFalse(summary['approved_experiment'])
        self.assertFalse(summary['performance_improvement_verified'])
        self.api.assert_called_once()

    def test_quota_error_stops_without_input_or_retry(self):
        class QuotaError(Exception):
            code = 429
        self.api.side_effect = QuotaError('must not print raw secret error')
        self.assertEqual(self.run_manual([]), 1)
        self.api.assert_called_once()
        self.assertIn('API 사용 한도 오류', self.output.getvalue())
        self.assertIn('합계 미확인', self.output.getvalue())
        self.assertNotIn('raw secret', self.output.getvalue())

    def test_response_schema_error_is_localized_without_retry(self):
        self.api.return_value = (json.dumps(dict(self.response, evidence=['latest_result'])), self.usage)
        self.assertEqual(self.run_manual([]), 1)
        self.api.assert_called_once()
        self.assertIn('Gemini 응답 수신 후', self.output.getvalue())
        self.assertIn('문자열 타입 불일치', self.output.getvalue())
        self.assertIn('합계 50', self.output.getvalue())
        self.assertTrue(self.active()[0]['finished'])

    def test_piped_input_never_starts_api(self):
        with patch.object(manual.sys.stdin, 'isatty', return_value=False), contextlib.redirect_stderr(self.output):
            self.assertEqual(manual.main(['--interactive']), 2)
        self.api.assert_not_called()
        self.assertFalse((self.root / 'artifacts/manual-cross-review').exists())

    def test_default_automation_does_not_require_tty_or_input(self):
        with patch.object(manual.sys.stdin, 'isatty', return_value=False):
            self.assertEqual(self.run_manual([], interactive=False), 0)
        self.api.assert_called_once()

    def test_default_next_steps_for_human_and_incomplete_plan(self):
        self.run_manual([], interactive=False)
        folder = self.active()[1]
        self.assertEqual(json.loads((folder/'next_steps.json').read_text())['category'], 'check_existing_evidence')
        result = json.loads((folder/'result.json').read_text())
        result['response']['human_confirmation'] = ''
        with contextlib.redirect_stdout(self.output):
            manual.next_steps(folder, result)
        self.assertEqual(json.loads((folder/'next_steps.json').read_text())['category'], 'complete_experiment_plan')

    def test_oversized_input_reports_bytes_and_safe_diagnostic_without_api(self):
        packet=manual.latest_packet(self.root);packet['padding']='x'*26000
        with patch.object(manual,'latest_packet',return_value=packet),contextlib.redirect_stderr(self.output):
            self.assertEqual(manual.main(['--auto']),1)
        self.api.assert_not_called()
        message=self.output.getvalue();self.assertIn('검토 입력 크기 초과',message)
        report=json.loads((self.root/'artifacts/manual-cross-review/last-error.json').read_text())
        self.assertEqual(report['limit_bytes'],24000)
        self.assertGreater(report['actual_bytes'],24000)
        self.assertEqual(report['kind'],'evidence_packet_too_large')
        self.assertNotIn('padding',json.dumps(report))

    def test_arbitrary_error_payload_is_never_printed_or_logged(self):
        secret='secret-key-do-not-print-123'
        with patch.object(manual,'latest_packet',side_effect=ValueError(secret)),contextlib.redirect_stderr(self.output):
            self.assertEqual(manual.main(['--auto']),1)
        self.api.assert_not_called()
        saved=(self.root/'artifacts/manual-cross-review/last-error.json').read_text()
        self.assertNotIn(secret,saved+self.output.getvalue())
        self.assertIn('last-error.json',self.output.getvalue())
        self.assertIn('ValueError',saved)

    def test_concurrent_terminal_does_not_start_another_review(self):
        import fcntl
        base = self.root / 'artifacts/manual-cross-review'
        base.mkdir(parents=True)
        with (base / 'session.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with contextlib.redirect_stderr(self.output):
                self.assertEqual(manual.main([]), 1)
        self.api.assert_not_called()

    def test_three_manual_rounds_and_total_usage(self):
        response = dict(self.response, human_confirmation='')
        replies = []
        for cause in ('첫 번째 가설', '두 번째 가설', '세 번째 가설'):
            response = dict(response, cause=cause)
            replies.append((json.dumps(response), self.usage))
        self.api.side_effect = replies
        self.assertEqual(self.run_manual(['r', 'r', 'r', '']), 0)
        self.assertEqual(self.api.call_count, 3)
        result = json.loads((self.active()[1] / 'result.json').read_text())
        self.assertEqual(len(result['attempts']), 3)
        self.assertIn('합계 150', self.output.getvalue())
        self.assertIn('호출 상한에 도달', self.output.getvalue())
        self.assertIn('반증 질문:', self.output.getvalue())
        self.assertIn('선택 근거:', self.output.getvalue())
        second_prompt = self.api.call_args_list[1].args[0]
        self.assertIn('현재 원인 가설과 관찰된 증상을 구분', second_prompt)
        self.assertIn('현재 응답의 최소 실험', self.api.call_args_list[2].args[0])

    def test_automatic_countercheck_tracks_response_and_valid_evidence(self):
        packet = dict(evidence={key: {} for key in ('latest_result', 'remaining_errors', 'related_code', 'latest_diagnostic')},
                      failed_hypotheses={'old': ['missing', 'latest_result']})
        response = dict(self.response, cause='logsumexp 손실과 공간 마스크', hypothesis_id='old')
        decision = manual.counter_review(packet, response, set())
        self.assertIn('학습 손실 함수와 추론', decision['new_question'])
        self.assertIn('공간 진단', decision['new_question'])
        self.assertIn('latest_diagnostic', decision['evidence_ids'])
        self.assertNotIn('missing', decision['evidence_ids'])
        self.assertEqual(decision['previous_proposal'], response)
        self.assertIsNone(manual.counter_review(packet, response, {'causal', 'falsification'}))
        self.assertIsNone(manual.counter_review({'evidence': {}}, response, set()))

    def test_r_waits_for_human_without_extra_api(self):
        self.assertEqual(self.run_manual(['r', '']), 0)
        self.api.assert_called_once()
        self.assertIn('사람 확인이 필요한 제안', self.output.getvalue())

    def test_auto_review_resume_uses_next_check_without_repeating_call(self):
        replies = [dict(self.response, human_confirmation='', cause=cause)
                   for cause in ('첫 가설', '수정 가설', '최종 가설')]
        self.api.side_effect = [(json.dumps(reply), self.usage) for reply in replies]
        self.assertEqual(self.run_manual(['r', 'q']), 0)
        self.assertEqual(self.api.call_count, 2)
        self.assertEqual(self.run_manual(['r', '']), 0)
        self.assertEqual(self.api.call_count, 3)
        folder = self.active()[1]
        first = json.loads((folder / 'decision-1.json').read_text())
        second = json.loads((folder / 'decision-2.json').read_text())
        self.assertEqual(first['countercheck_id'], 'causal')
        self.assertEqual(second['countercheck_id'], 'falsification')

    def test_auto_review_identical_claim_stops_before_third_call(self):
        self.api.return_value = (json.dumps(dict(self.response, human_confirmation='')), self.usage)
        self.assertEqual(self.run_manual(['r']), 0)
        self.assertEqual(self.api.call_count, 2)
        result = json.loads((self.active()[1] / 'result.json').read_text())
        self.assertEqual(result['status'], 'repeated_claim')

    def test_new_round_q_resume_freezes_evidence_and_avoids_extra_call(self):
        response = dict(self.response, human_confirmation='')
        self.api.return_value = (json.dumps(response), self.usage)
        self.run_manual(['q'])
        folder = self.active()[1]
        frozen = (folder / 'packet.json').read_bytes()
        self.source_result.write_text('broken newer source')
        self.assertEqual(self.run_manual(['']), 0)
        self.assertEqual((folder / 'packet.json').read_bytes(), frozen)
        self.api.assert_called_once()

    def test_pending_example_is_preserved_and_replaced_with_latest(self):
        self.run_manual(['q'])
        _, old = self.active()
        packet = json.loads((old / 'packet.json').read_text())
        packet.pop('source_mode')
        (old / 'packet.json').write_text(json.dumps(packet))
        self.run_manual([''])
        self.assertTrue((old / 'superseded.json').exists())
        self.assertNotEqual(old, self.active()[1])
        self.assertEqual(self.api.call_count, 1)
        self.assertEqual(json.loads((self.active()[1]/'result.json').read_text())['status'],'no_new_evidence')

    def test_role_upgrade_reuses_same_v4_evidence_without_new_call(self):
        self.run_manual([''])
        _,folder=self.active()
        config=json.loads((folder/'config.json').read_text())
        config['prompt_version']=manual.GROUNDED_KOREAN_VERSION
        (folder/'config.json').write_text(json.dumps(config))
        active_path=self.root/'artifacts/manual-cross-review/active.json'
        active=json.loads(active_path.read_text());active['finished']=True
        active_path.write_text(json.dumps(active))
        self.run_manual([''])
        self.assertEqual(self.active()[1],folder)
        self.assertEqual(self.api.call_count,1)
        self.assertEqual(json.loads((folder/'config.json').read_text())['prompt_version'],manual.GROUNDED_KOREAN_VERSION)

    def test_korean_prompt_and_stage_guidance(self):
        self.run_manual([''])
        _, folder = self.active()
        config = json.loads((folder/'config.json').read_text())
        self.assertEqual(config['prompt_version'], manual.KOREAN_VERSION)
        output = self.output.getvalue()
        for stage in ('[1/4 근거 준비]', '[2/4 Gemini 검토]', '[3/4 사용자 근거 대조]', '[4/4 기록 저장·종료]'):
            self.assertIn(stage, output)
        self.assertIn('실험을 실행하는 동작이 아닙니다', output)
        self.assertIn('원인 가설(미검증)', output)


if __name__ == '__main__':
    unittest.main()
