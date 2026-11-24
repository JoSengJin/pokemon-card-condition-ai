"""Every quality rule must be reachable from the selection table; nobody has to remember names."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = (ROOT / 'docs/agent/QUALITY_RULES.md').read_text(encoding='utf-8')
START = (ROOT / 'docs/AGENT_START.md').read_text(encoding='utf-8')
NAME = r'`([a-z]+(?:-[a-z]+)+)`'
HEADINGS = re.findall(rf'^### {NAME} · ', RULES, re.M)


class QualityRuleRoutesTest(unittest.TestCase):
    def test_rule_text_selection_table_and_status_table_name_the_same_rules(self):
        table = START.split('## 품질 규칙 선택표', 1)[1].split('\n## ', 1)[0]
        status = RULES.split('## 7. 적용 상태', 1)[1]
        self.assertEqual(len(HEADINGS), 16)
        self.assertEqual(len(set(HEADINGS)), 16)
        for text in (table, status):
            self.assertEqual(sorted(re.findall(rf'^\| {NAME}', text, re.M)), sorted(HEADINGS))

    def test_no_active_document_points_to_an_unknown_rule_or_an_old_number(self):
        for name in ('AGENTS.md', 'COMMON_EXPERIMENT_RECORDS.md', 'LABELING_PROTOCOL.md', 'docs/AGENT_START.md'):
            with self.subTest(name=name):
                self.assertNotRegex((ROOT / name).read_text(encoding='utf-8'), r'\bQ(?:0[1-9]|1[0-6])\b')
        for name in ('COMMON_EXPERIMENT_RECORDS.md', 'LABELING_PROTOCOL.md'):
            used = set(re.findall(NAME, (ROOT / name).read_text(encoding='utf-8').split('QUALITY_RULES.md', 1)[1]))
            self.assertLessEqual(used, set(HEADINGS))

    def test_one_phrase_and_no_phrase_both_reach_the_table(self):
        self.assertIn('품질 규칙 사용해서 처리해줘', START)
        self.assertIn('Superpowers 사용해서 처리해줘', START)
        agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertRegex(agents, r'이름을 부르지 않아도 `docs/AGENT_START\.md`의 품질 규칙 선택표')


if __name__ == '__main__':
    unittest.main()
