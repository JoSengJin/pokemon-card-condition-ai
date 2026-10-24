"""Regression tests: the multi-turn review loop used to dead-end before any debate output was usable.

Root causes covered (details: artifacts/claude-review-loop-fix-20261024/REPORT.md):
 1. Codex had to restate program-owned bookkeeping (real hypothesis ids, empty critique list) exactly.
 2. A stop issued before any critique existed failed with critique_coverage.
 3. Any failure was permanent: re-running reused the failed folder and returned the same error.
 4. A launch that never reached the model (sandboxed app-server) was recorded as an uncertain request.
 5. A malformed judge reply latched the provider circuit and discarded the reply for pseudo evidence ids.
 6. A finished debate was thrown away when the judge was unavailable.
No test calls a real model, network or Codex process.
"""
import contextlib
import copy
import io
import json
import unittest
from unittest.mock import patch

import test_cross_review_high_fixes as high
import test_cross_review_nemotron as native_fixture
from card_condition import cross_review_auto as auto
from card_condition import cross_review_contract as contract
from card_condition import cross_review_flow as flow
from card_condition import cross_review_manual as manual
from card_condition import cross_review_nemotron as native
from card_condition.experiment_record import read, save

PACKET = dict(
    failed_hypotheses={'h-failed-1': ['failed_0'], 'h-failed-2': ['failed_1']},
    failed_executions={'h-exec-1': ['failed_execution_0']},
    completed_diagnostics={'h-diag-1': ['completed_diagnostic_0']},
)


class CanonicalizeTest(unittest.TestCase):
    def verdict(self, **kwargs):
        value = dict(action='select', rationale='r', evidence_ids=['latest_result'], critique_responses=[],
                     failed_hypotheses_checked=['failed_0', 'failed_1'],
                     review_claims=dict(completed_diagnostic_ids=['completed_diagnostic_0'], missing_evidence_ids=[], gemini_required_for_select=False),
                     experiment=dict(hypothesis_id='new', cause='c'), acceptance=dict(max_fp=1))
        value.update(kwargs)
        return value

    def test_evidence_aliases_become_real_ids_and_nothing_else_changes(self):
        original = self.verdict()
        value, notes = contract.canonicalize_verdict(PACKET, original, ())
        self.assertEqual(value['failed_hypotheses_checked'], ['h-failed-1', 'h-failed-2'])
        self.assertEqual(value['review_claims']['completed_diagnostic_ids'], ['h-diag-1'])
        self.assertEqual({k: v for k, v in value.items() if k not in ('failed_hypotheses_checked', 'review_claims')},
                         {k: v for k, v in original.items() if k not in ('failed_hypotheses_checked', 'review_claims')})
        self.assertEqual(original['failed_hypotheses_checked'], ['failed_0', 'failed_1'], 'input must not be mutated')
        self.assertEqual({n['field'] for n in notes}, {'failed_hypotheses_checked', 'review_claims.completed_diagnostic_ids'})

    def test_real_ids_mixed_ids_and_duplicates_are_idempotent(self):
        value, notes = contract.canonicalize_verdict(PACKET, self.verdict(failed_hypotheses_checked=['h-failed-1', 'failed_0', 'failed_1']), ())
        self.assertEqual(value['failed_hypotheses_checked'], ['h-failed-1', 'h-failed-2'])
        again, more = contract.canonicalize_verdict(PACKET, value, ())
        self.assertEqual(again, value)
        self.assertEqual(more, [])

    def test_execution_alias_is_classified_as_execution_not_hypothesis(self):
        value, _ = contract.canonicalize_verdict(PACKET, self.verdict(failed_hypotheses_checked=['failed_0', 'failed_1', 'failed_execution_0']), ())
        canonical, warning = contract.classify_history(PACKET, value)
        self.assertEqual(canonical['failed_hypotheses_checked'], ['h-failed-1', 'h-failed-2'])
        self.assertEqual(warning['execution_failure_ids'], ['h-exec-1'])

    def test_completed_diagnostic_alias_cannot_pass_as_failed_hypothesis(self):
        value, _ = contract.canonicalize_verdict(PACKET, self.verdict(failed_hypotheses_checked=['failed_0', 'completed_diagnostic_0']), ())
        with self.assertRaisesRegex(ValueError, 'Failure history mismatch'):
            contract.classify_history(PACKET, value)

    def test_unknown_ids_stay_unknown(self):
        value, _ = contract.canonicalize_verdict(PACKET, self.verdict(failed_hypotheses_checked=['failed_0', 'invented']), ())
        self.assertIn('invented', value['failed_hypotheses_checked'])

    def test_critique_responses_are_dropped_only_while_no_critique_exists(self):
        reply = [dict(critique_id='x', disposition='accept', rationale='r', evidence_ids=['latest_result'])]
        dropped, notes = contract.canonicalize_verdict(PACKET, self.verdict(critique_responses=reply), ())
        self.assertEqual(dropped['critique_responses'], [])
        self.assertEqual([n['kind'] for n in notes if n['field'] == 'critique_responses'], ['dropped_no_critique_exists'])
        kept, notes = contract.canonicalize_verdict(PACKET, self.verdict(critique_responses=reply), [dict(id='x')])
        self.assertEqual(kept['critique_responses'], reply)
        self.assertEqual([n for n in notes if n['field'] == 'critique_responses'], [])

    def test_malformed_input_is_returned_untouched(self):
        self.assertEqual(contract.canonicalize_verdict(PACKET, 'text', ()), ('text', []))
        value, notes = contract.canonicalize_verdict(PACKET, self.verdict(failed_hypotheses_checked=[1, 2]), ())
        self.assertEqual(value['failed_hypotheses_checked'], [1, 2])


class LoopResilienceTest(unittest.TestCase):
    setUp = high.HighFixTest.setUp
    gemini = high.HighFixTest.gemini
    backend = high.HighFixTest.backend
    judge = high.HighFixTest.judge
    run_flow = high.HighFixTest.run_flow

    def stop_verdict(self, **kwargs):
        value = copy.deepcopy(self.verdict)
        value.update(action='stop', rationale='근거 부족으로 중단합니다.', **kwargs)
        return value

    def stopping_backend(self, verdict, log=None):
        def backend(root, phase, prompt, directory, thread):
            self.codex_calls.append((phase, thread))
            return copy.deepcopy(verdict), dict(self.usage), 'mock-thread'
        return backend

    def run_with(self, backend, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return auto.run_auto(self.root, self.folder, self.result, backend=backend, gemini_caller=self.gemini, **kwargs)

    def state(self):
        return read(self.folder / 'automation.json')

    # 1+2: bookkeeping is program-owned, so a legitimate stop is a stop, not an error plus a wasted correction.
    def test_alias_ids_in_a_stop_need_no_correction_call(self):
        verdict = self.stop_verdict(failed_hypotheses_checked=['failed_0'])
        self.assertEqual(self.run_with(self.stopping_backend(verdict)), 0)
        self.assertEqual([phase for phase, _ in self.codex_calls], ['verify'])
        self.assertEqual(self.state()['status'], 'stopped')
        self.assertEqual(self.state()['normalizations']['verify'][0]['after'], ['reference-20261019'])

    def test_stray_critique_responses_before_any_critique_do_not_fail_a_stop(self):
        stray = [dict(critique_id='completed_diagnostics', disposition='accept', rationale='오류 목록에 답함', evidence_ids=['latest_result'])]
        verdict = self.stop_verdict(critique_responses=stray)
        self.assertEqual(self.run_with(self.stopping_backend(verdict)), 0)
        self.assertEqual(self.state()['status'], 'stopped')
        self.assertEqual(self.gemini_calls, 0)

    def test_raw_model_response_is_preserved_unmodified(self):
        verdict = self.stop_verdict(failed_hypotheses_checked=['failed_0'])
        self.run_with(self.stopping_backend(verdict))
        stored = read(next(self.folder.glob('codex/verify-*/call.json')))['data']
        self.assertEqual(stored['failed_hypotheses_checked'], ['failed_0'])

    def test_a_real_validation_error_is_still_an_error(self):
        verdict = self.stop_verdict(failed_hypotheses_checked=['failed_0', 'invented-id'])
        self.assertEqual(self.run_with(self.stopping_backend(verdict)), 1)
        self.assertEqual(self.state()['status'], 'validation_or_execution_error')

    # 4+3: a launch that never reached the model is retried from stored state; anything uncertain is not.
    def launch_failure_backend(self, turn_requests):
        def backend(root, phase, prompt, directory, thread):
            self.codex_calls.append((phase, thread))
            save(directory / 'execution.json', dict(transport='app-server', turn_requests=turn_requests, turn_completions=0,
                                                    blocked='ValueError', usage_known=False, usage=None))
            return None, None, None
        return backend

    def test_launch_that_never_reached_the_model_is_retried_on_the_next_invocation(self):
        self.assertEqual(self.run_with(self.launch_failure_backend(0)), 1)
        self.assertEqual(self.state()['status'], 'validation_or_execution_error')
        self.assertIn(auto.LAUNCH_BLOCKED, self.state()['reason'])
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 0)
        self.assertEqual(self.state()['status'], 'stopped')
        self.assertEqual(len(self.codex_calls), 2)
        self.assertEqual(len(list(self.folder.glob('codex/*/call.json'))), 1)
        self.assertEqual(len(list(self.folder.glob('superseded-codex/*/call.json'))), 1)
        self.assertEqual(self.state()['resumes'][0]['from_status'], 'validation_or_execution_error')
        self.assertIsNotNone(read(self.folder / 'token_report.json')['codex_usage']['total_tokens'])

    def test_request_that_may_have_reached_the_model_is_never_retried(self):
        self.assertEqual(self.run_with(self.launch_failure_backend(1)), 1)
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 1)
        self.assertEqual(len(self.codex_calls), 1)
        self.assertFalse((self.folder / 'superseded-codex').exists())

    def test_repeated_launch_failures_are_capped(self):
        backend = self.launch_failure_backend(0)
        for _ in range(auto.MAX_LAUNCH_RETRIES + 1):
            self.assertEqual(self.run_with(backend), 1)
        self.assertEqual(len(self.codex_calls), auto.MAX_LAUNCH_RETRIES + 1)
        self.assertEqual(self.run_with(backend), 1)
        self.assertEqual(len(self.codex_calls), auto.MAX_LAUNCH_RETRIES + 1, 'no new launch after the cap')

    def test_missing_codex_executable_counts_as_never_sent(self):
        def missing(root, phase, prompt, directory, thread):
            raise FileNotFoundError('codex')
        self.assertEqual(self.run_with(missing), 1)
        self.assertIn(auto.LAUNCH_BLOCKED, self.state()['reason'])
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 0)

    def test_time_budget_belongs_to_one_invocation(self):
        self.assertEqual(self.run_with(self.launch_failure_backend(0)), 1)
        state = self.state();state['deadline'] = 0;save(self.folder / 'automation.json', state)
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 0)

    def test_other_terminal_states_stay_terminal(self):
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 0)
        before = len(self.codex_calls)
        self.assertEqual(self.run_with(self.stopping_backend(self.stop_verdict())), 0)
        self.assertEqual(len(self.codex_calls), before)
        self.assertNotIn('resumes', self.state())

    # 6: the finished debate survives an unavailable judge, unapproved and unexecuted.
    def fake_execute(self, packet, config, database, caller=None, decision=None):
        raw, usage = self.gemini('', 0)
        return dict(packet=packet, config=config, status='awaiting_comparison', response=json.loads(raw),
                    attempts=[dict(usage=usage, status='complete')] * self.gemini_calls, pending=[], round=1)

    def run_debate(self, **kwargs):
        with patch('card_condition.cross_review_flow.execute', side_effect=self.fake_execute):
            return self.run_flow(**kwargs)

    def test_unavailable_judge_keeps_the_debate_outcome_without_approving_it(self):
        with patch.object(native, 'review', return_value=None):
            self.assertEqual(self.run_debate(), 1)
        state = self.state()
        self.assertEqual(state['status'], 'judge_unavailable')
        candidate = state['unjudged_candidate']
        self.assertEqual(candidate['plan']['experiment']['hypothesis_id'], 'new-cause')
        self.assertEqual(len(candidate['critique_ids']), 1)
        self.assertNotIn('Codex:implement', self.order)
        self.assertFalse(state.get('plan_approved'))
        self.assertNotIn('development_gate', state)

    def test_next_steps_surfaces_the_unjudged_candidate_as_not_approved(self):
        with patch.object(native, 'review', return_value=None):
            self.run_debate()
        result = read(self.folder / 'result.json')
        with contextlib.redirect_stdout(io.StringIO()), patch.object(manual, 'ROOT', self.root):
            manual.next_steps(self.folder, result)
        summary = read(self.folder / 'next_steps.json')
        self.assertEqual(summary['category'], 'review_unjudged_candidate')
        self.assertFalse(summary['approved_experiment'])
        text = (self.folder / 'next_steps.md').read_text()
        self.assertIn('심판 미승인 후보 계획', text)
        self.assertIn('new-cause', text)

    def test_judge_returning_later_resumes_without_repeating_codex_or_gemini(self):
        with patch.object(native, 'review', return_value=None):
            self.assertEqual(self.run_debate(), 1)
        codex_before, gemini_before = len(self.codex_calls), self.gemini_calls
        with patch('card_condition.cross_review_adversarial.evaluate', return_value=None):
            code = self.run_debate()
        self.assertEqual(code, 2)  # plan approved; no trusted execution contract in this fixture
        self.assertEqual(self.gemini_calls, gemini_before)
        self.assertEqual([c for c in self.codex_calls[codex_before:]], [('implement', None)])
        self.assertNotIn('unjudged_candidate', self.state())
        self.assertEqual(self.state()['resumes'][0]['from_status'], 'judge_unavailable')


class JudgeToleranceTest(unittest.TestCase):
    setUp = native_fixture.NemotronTest.setUp
    start = native_fixture.NemotronTest.start
    configure = native_fixture.NemotronTest.configure
    gemini = native_fixture.NemotronTest.gemini
    backend = native_fixture.NemotronTest.backend
    run_auto = native_fixture.NemotronTest.run_auto

    PACKET = dict(evidence={'latest_result': {}, 'failed_0': {}})
    CONTEXT = dict(revised_proposal=dict(experiment=dict(hypothesis_id='h')), critiques=[dict(id='c1')])

    def reply(self, **kwargs):
        ratings = dict(reliability=80, logic=80, response=80, independence=50, evidence_ids=['latest_result'])
        value = dict(reviewed_hypothesis_id='h', decision='reject_experiment', rationale='근거 대조', evidence_ids=['latest_result'],
                     unresolved_issues=[], human_confirmation_required=False, advocate=dict(ratings), skeptic=dict(ratings),
                     criticism_checks=[dict(critique_id='c1', status='addressed', rationale='답변 대조')])
        value.update(kwargs)
        return value

    def test_pseudo_evidence_ids_are_dropped_not_fatal(self):
        value = self.reply(evidence_ids=['gemini-abc', 'latest_result', 'shared_core', 'code_checks'])
        value['skeptic']['evidence_ids'] = ['failed_0', 'critique-x']
        cleaned, dropped = native.drop_unknown_evidence(value, self.PACKET)
        self.assertEqual(cleaned['evidence_ids'], ['latest_result'])
        self.assertEqual(cleaned['skeptic']['evidence_ids'], ['failed_0'])
        self.assertEqual(dropped, {'evidence_ids': ['gemini-abc', 'shared_core', 'code_checks'], 'skeptic.evidence_ids': ['critique-x']})
        self.assertEqual(native.judge_errors(cleaned, self.PACKET, self.CONTEXT), [])
        self.assertEqual(value['evidence_ids'][0], 'gemini-abc', 'input must not be mutated')

    def test_reply_with_no_valid_evidence_id_is_still_rejected(self):
        cleaned, _ = native.drop_unknown_evidence(self.reply(evidence_ids=['shared_core', 'code_checks']), self.PACKET)
        self.assertEqual(native.judge_errors(cleaned, self.PACKET, self.CONTEXT), ['judge_evidence'])

    def test_stored_error_reply_is_recovered_without_a_request(self):
        raw = json.dumps(self.reply(evidence_ids=['gemini-abc', 'latest_result']))
        entry = dict(status='error', error_kind='response_error', raw_response=raw, usage=dict(total_tokens=9), attempted=True,
                     diagnostic=dict(x=1), validation_errors=['judge_evidence'])
        recovered = native.recover_stored_judge(entry, self.PACKET, self.CONTEXT)
        self.assertEqual(recovered['status'], 'complete')
        self.assertEqual(recovered['response']['evidence_ids'], ['latest_result'])
        self.assertEqual(recovered['dropped_evidence_ids'], {'evidence_ids': ['gemini-abc']})
        self.assertIn('stored_response_revalidated', recovered['warnings'])
        self.assertEqual(recovered['usage'], dict(total_tokens=9))
        self.assertNotIn('error_kind', recovered)
        self.assertEqual(entry['status'], 'error', 'original journal entry is not rewritten')

    def test_structurally_broken_stored_reply_is_not_recovered(self):
        for raw in ('not json', json.dumps(dict(decision='approve_experiment')),
                    json.dumps(self.reply(reviewed_hypothesis_id='withdrawn-plan'))):
            entry = dict(status='error', error_kind='response_error', raw_response=raw)
            self.assertIsNone(native.recover_stored_judge(entry, self.PACKET, self.CONTEXT), raw)

    def test_malformed_reply_does_not_latch_the_provider_but_an_outage_still_does(self):
        self.configure()
        result = dict(packet=self.packet, config=self.config, status='awaiting_comparison', response=dict(self.response),
                      attempts=[], pending=[], round=1)
        circuit = self.root / 'artifacts/provider-alerts/nemotron-disabled.json'
        entry = native.review(self.root, self.folder, result, caller=lambda *a: ('{"stance":"object"}', dict(total_tokens=5)),
                              probe=lambda: 'available')
        self.assertEqual(entry['error_kind'], 'response_error')
        self.assertFalse(circuit.exists(), 'a delivered but malformed reply is not a provider outage')

        def outage(*args):
            raise RuntimeError('network down')
        other = native.review(self.root, self.folder, dict(result, round=2), question='again', caller=outage, probe=lambda: 'available')
        self.assertEqual(other['status'], 'error')
        self.assertTrue(read(circuit)['disabled'], 'real outages keep the manual-recheck latch')


if __name__ == '__main__':
    unittest.main()
