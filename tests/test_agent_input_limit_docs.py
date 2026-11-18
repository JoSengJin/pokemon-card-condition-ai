import re
import unittest
from pathlib import Path

from card_condition.cross_review_auto_contract import CODEX_PROMPT_BYTES, CODEX_TIMEOUT, CODEX_TOKEN_BUDGET, EXPERIMENT_TIMEOUT

ROOT = Path(__file__).resolve().parents[1]


class AgentInputLimitDocsTest(unittest.TestCase):
    def test_active_guide_links_current_contract_instead_of_obsolete_limits(self):
        guide = (ROOT/'AUTO_DEVELOPMENT_20261020.md').read_text()
        self.assertNotRegex(guide, r'48\s*KB|48,?000|검증\s*3작업')
        self.assertIn('docs/agent/AUTO_REVIEW_CONTRACT.md#현재-입력호출-계약', guide)
        self.assertIn('docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md', guide)

    def test_current_contract_has_one_authoritative_limit_matching_runtime(self):
        text = (ROOT/'docs/agent/AUTO_REVIEW_CONTRACT.md').read_text()
        self.assertEqual(text.count('## 현재 입력·호출 계약'), 1)
        section = text.split('## 현재 입력·호출 계약\n', 1)[1].split('\n## ', 1)[0]
        self.assertEqual(CODEX_PROMPT_BYTES, dict(verify=32000, correct=32000, implement=32000))
        self.assertIn('모든 단계32,000 bytes 이하', section)
        self.assertEqual(text.count('모든 단계32,000 bytes 이하'), 1)
        self.assertIn('검토1회·교정 최대1회·구현1회', section)
        self.assertEqual((CODEX_TIMEOUT, CODEX_TOKEN_BUDGET, EXPERIMENT_TIMEOUT), (600, 100000, 1800))
        self.assertNotRegex(text, r'48\s*KB|48,?000')

    def test_old_guide_is_preserved_as_explicit_history(self):
        text = (ROOT/'docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md').read_text()
        self.assertIn('현재 실행 지침이 아니다', text)
        self.assertIn('검증32KB·구현48KB', text)
        self.assertIn('검증 3작업+구현 1작업', text)

    def test_current_and_history_links_resolve(self):
        for name in ('AUTO_DEVELOPMENT_20261020.md', 'docs/agent/AUTO_REVIEW_CONTRACT.md',
                     'docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md'):
            path = ROOT/name
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if link.startswith(('http:', 'https:', '#')):
                    continue
                target = (path.parent/link.split('#')[0]).resolve()
                if target.is_relative_to(ROOT/'artifacts'):
                    continue
                with self.subTest(name=name, link=link):
                    self.assertTrue(target.is_file())
