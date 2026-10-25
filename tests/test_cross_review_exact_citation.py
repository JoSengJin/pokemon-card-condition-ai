"""Regression for source citations in bounded Codex review prompts."""
import unittest
from unittest.mock import patch

from card_condition import cross_review_auto as auto
from card_condition.experiment_record import read
from test_cross_review_auto import AutoReviewTest


class ExactCitationTest(unittest.TestCase):
    setUp = AutoReviewTest.setUp

    def test_prompt_requires_contiguous_quote_and_keeps_input_limit(self):
        calls = []

        def backend(root, phase, prompt, directory, thread_id):
            calls.append(prompt)
            return self.verdict, dict(input_tokens=100, output_tokens=10), 'mock'

        with patch('httpx.Client.send', side_effect=AssertionError('AI call')), patch('subprocess.Popen', side_effect=AssertionError('Codex call')):
            auto.codex_task(self.root, self.folder, 'verify', {'flow_role': 'advocate'}, backend=backend)
        self.assertEqual(len(calls), 1)
        self.assertIn('연속된 원문 한 구절', calls[0])
        self.assertIn('떨어진 줄 합성·생략 금지', calls[0])
        self.assertLessEqual(len(calls[0].encode()), 32000)
        self.assertEqual(read(next((self.folder / 'codex').glob('verify-*/preflight.json')))['blocked'], None)


if __name__ == '__main__':
    unittest.main()
