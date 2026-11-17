import tempfile
import unittest
from pathlib import Path

from card_condition.cross_review_auto_sources import review_rules

IDS = ('project-scope', 'human-truth', 'single-variable', 'experiment-plan',
       'evaluation-boundary', 'bounded-edits', 'one-experiment', 'isolated-child')


class AgentReviewRulesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'AGENTS.md'
        self.rules = {key: '- 규칙 ' + key for key in IDS}
        self.text = '\n\n'.join(f'<!-- review-rule:{key}:start -->\n{value}\n<!-- review-rule:{key}:end -->'
                                 for key, value in self.rules.items())

    def test_rewording_and_wrapping_keep_all_identified_rules(self):
        self.text = self.text.replace('- 규칙 single-variable', '- 학습/검증 입력 분리\n  한 변수만 변경')
        self.path.write_text(self.text)
        actual = review_rules(self.path)
        self.assertIn('학습/검증 입력 분리\n  한 변수만 변경', actual)
        self.assertEqual(actual.count('- '), 8)

    def test_missing_file_is_compatible_but_existing_unmarked_file_is_rejected(self):
        self.assertEqual(review_rules(self.path), '')
        self.path.write_text('- 학습과 검증 입력 분리')
        with self.assertRaisesRegex(ValueError, 'review-rule'):
            review_rules(self.path)

    def test_missing_duplicate_unknown_empty_and_malformed_blocks_are_rejected(self):
        first = '<!-- review-rule:project-scope:start -->\n- 규칙 project-scope\n<!-- review-rule:project-scope:end -->'
        cases = [self.text.replace(first, ''), self.text + '\n' + first,
                 self.text.replace('project-scope', 'unknown-rule'),
                 self.text.replace('- 규칙 project-scope', '  '),
                 self.text.replace('project-scope:end', 'human-truth:end'),
                 self.text + '\n<!-- review-rule:broken -->']
        for text in cases:
            with self.subTest(text=text[:80]):
                self.path.write_text(text)
                with self.assertRaisesRegex(ValueError, 'review-rule'):
                    review_rules(self.path)

    def test_unselected_parent_instructions_and_markers_do_not_leak(self):
        self.path.write_text('- 부모만 읽는 승인\n' + self.text + '\n- 별도 부모 작업')
        self.assertEqual(review_rules(self.path), '\n'.join(self.rules.values()))

    def test_document_order_does_not_change_canonical_child_input(self):
        self.path.write_text('\n\n'.join(reversed(self.text.split('\n\n'))))
        self.assertEqual(review_rules(self.path), '\n'.join(self.rules.values()))

    def test_incomplete_rules_stop_before_backend_or_call_journal(self):
        import test_cross_review_auto as fixture
        from unittest.mock import Mock
        from card_condition import cross_review_auto as auto
        case = fixture.AutoReviewTest('runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        (case.root/'AGENTS.md').write_text(self.text.replace('human-truth', 'unknown-rule'))
        backend = Mock()
        with self.assertRaisesRegex(ValueError, 'review-rule'):
            auto.codex_task(case.root, case.folder, 'verify', {}, backend=backend)
        backend.assert_not_called()
        self.assertFalse(list((case.folder/'codex').glob('*/call.json')))
