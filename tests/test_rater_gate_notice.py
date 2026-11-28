"""D3 (2026-11-28): fixed wording in results; no_match_found is never promoted to a human-judgment confirmation."""
import random

from tests.test_rater_gate import VALUES, RaterGateBase
from tools import zone_rows

NOTICE = 'AI 판정과 일치하는 기록을 찾지 못했다는 사실은 사람이 직접 판정했다는 증거가 아니다.'


class NoticeTest(RaterGateBase):
    def no_match(self):
        self.ai('r.txt', [random.Random(2).choice(VALUES) for _ in range(64)])
        (self.root / 's.txt').write_text('직접 판정', encoding='utf-8')
        extra = ['--statement', str(self.root / 's.txt'), '--expected', str(self.root / 's.txt')]
        return self.run_gate(*extra)[1]

    def test_fixed_wording_is_in_result(self):
        result = self.no_match()
        self.assertEqual(result['notice'], NOTICE)
        self.assertIn('AI 사본 변형', result['limitation'])

    def test_no_match_is_never_a_human_label(self):
        result = self.no_match()
        self.assertEqual(result['verdict'], 'no_match_found')
        facts = zone_rows.facts([dict(id='a', image_sha256='x', box=[0, 0, 1, 1])], {}, result)
        self.assertEqual(facts['a']['rater_kind'], 'unknown')
        self.assertEqual(zone_rows.NOTICE, NOTICE)
