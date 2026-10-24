"""978cc047dc49 흐름 재현(mock): Codex stop은 유지하고, worker-only 정정은 Gemini 단계까지 간다."""
import copy
import unittest

from card_condition.cross_review_evidence import expand_evidence
from card_condition.experiment_record import read
import test_cross_review_high_fixes as high_fixture
from test_cross_review_worker_only_scope import configure_trainer, TRAINER, WORKER


class WorkerOnlyFlowTest(unittest.TestCase):
    setUp = high_fixture.HighFixTest.setUp
    run_flow = high_fixture.HighFixTest.run_flow
    gemini = high_fixture.HighFixTest.gemini
    judge = high_fixture.HighFixTest.judge

    def flow(self, verify, correct=None):
        def backend(root, phase, prompt, directory, thread):
            self.codex_calls.append((phase, thread)); self.order.append('Codex:'+phase)
            self.inputs.append((phase, read(directory/'input.json')))
            value = verify if phase == 'verify' else correct if phase == 'correct' and not self.gemini_calls else self.implementation
            return copy.deepcopy(value), dict(self.usage), 'mock-thread'
        self.backend = backend
        return self.run_flow()

    def test_recorded_misclassification_keeps_codex_stop_but_receives_worker_only_guidance(self):
        worker_only = configure_trainer(self)
        listed = dict(worker_only, implementation_files=[WORKER])
        stop = dict(worker_only, action='stop', rationale='허용된 모델 파일을 수정할 수 없어 구현 불가로 중단한다.')
        self.flow(listed, stop)
        self.assertEqual(self.order, ['Codex:verify', 'Codex:correct'])
        self.assertEqual(self.gemini_calls, 0); self.assertEqual(self.n_calls, 0)
        self.assertEqual(read(self.folder/'automation.json')['status'], 'stopped')  # Codex stop is never flipped.
        corrected = expand_evidence(dict(self.inputs)['correct'])
        message = next(e['error'] for e in corrected['correction']['errors'] if e['check'] == 'code_sources')
        self.assertIn(WORKER, message); self.assertIn('[] is valid', message)
        cited = {v['path']: v for v in corrected['source_context']['sources']}
        self.assertTrue(cited[TRAINER]['worker_importable'])
        self.assertNotIn('advocate', corrected['response']['debate_assessment'])  # Pre-judge zero ratings only.
        self.assertIn('unresolved_issues', corrected['response']['debate_assessment'])

    def test_corrected_worker_only_select_reaches_gemini_once(self):
        worker_only = configure_trainer(self)
        self.flow(dict(worker_only, implementation_files=[WORKER]), worker_only)
        self.assertEqual(self.order[:3], ['Codex:verify', 'Codex:correct', 'Gemini'])
        self.assertEqual(self.gemini_calls, 1)
        self.assertEqual(len([c for c in self.codex_calls if c[0] == 'correct']), 1)

    def test_valid_worker_only_select_needs_no_correction(self):
        worker_only = configure_trainer(self)
        self.flow(worker_only)
        self.assertEqual(self.order[:2], ['Codex:verify', 'Gemini'])
        self.assertEqual(self.gemini_calls, 1)


if __name__ == '__main__':
    unittest.main()
