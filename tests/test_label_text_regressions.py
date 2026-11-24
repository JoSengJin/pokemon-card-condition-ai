"""Wrong label instructions that recurred must never return (docs/agent/QUALITY_RULES.md regression-for-every-fix)."""
import re
import unittest
from pathlib import Path

from card_condition.label_instructions import SURFACE_INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[1]
# Verbatim wrong copy: tools/relabel_consistency_page.py (5782606), tools/relabel_zone_pages.py (0d55bab, fixed by de3ce08),
# performance-top3-consensus-20261030.md sections 59/62 and SURFACE_HOLDOUT2_PLAN_20261103.md. See LABELING_PROTOCOL.md.
REAL_WRONG = (
    '② 표면(면 위 긁힘·뜯김·접힘·눌림·얼룩, 화이트닝은 정상)이 다 정상이면 “9구역 전부 정상”. ',
    '파란 사각형 안 구역의 표면(면 위 긁힘·뜯김·접힘·눌림·얼룩, 화이트닝은 정상)을 평소 확대 기준으로 판정하세요. ',
    '정의: 면 위 긁힘·뜯김·접힘·눌림·얼룩은 결함, 화이트닝은 정상(사용자 확인 2026-11-02), 모르면 미확인.',
    '안쪽 인쇄면의 긁힘·눌림·구김·얼룩·인쇄 외 자국만 결함; 엣지·모서리 마모·화이트닝 제외',
)
WRONG = re.compile(r'화이트닝(?:은|는|이|만|도)?(?:면|있어도)?(?:무조건|모두|전부|항상)?'
                   r'(?:정상|제외|무시|결함이?아[니닙])')


def wrong_phrase(text):
    """First location-free 'whitening is normal/excluded' phrase, ignoring markup and spacing."""
    found = WRONG.search(re.sub(r'<[^>]+>|[\s*`"\'‘’“”]', '', text))
    return found and found.group(0)


class LabelTextRegressionsTest(unittest.TestCase):
    def test_every_recorded_wrong_text_is_caught(self):
        for text in REAL_WRONG:
            with self.subTest(text=text):
                self.assertTrue(wrong_phrase(text))
                self.assertTrue(wrong_phrase(text.replace('화이트닝', '<b>화이트닝</b>')))

    def test_current_location_specific_exclusion_is_allowed(self):
        self.assertIsNone(wrong_phrase('<b>옆면 테두리의 백화나 둥근 모서리 끝의 마모만</b> 있다면 표면 결함으로 표시하지 마세요.'))

    def test_canonical_and_every_label_tool_are_free_of_wrong_text(self):
        tools = sorted(ROOT.glob('tools/*label*.py'))
        self.assertGreaterEqual(len(tools), 6)
        self.assertIsNone(wrong_phrase(SURFACE_INSTRUCTIONS))
        for path in tools:
            with self.subTest(tool=path.name):
                self.assertIsNone(wrong_phrase(path.read_text(encoding='utf-8')))

    def test_canonical_still_calls_face_whitening_a_defect(self):
        plain = re.sub(r'<[^>]+>', '', SURFACE_INSTRUCTIONS)
        self.assertRegex(plain, r'면 위의 흰 마모 자국\(화이트닝\)은 표면 결함입니다')


if __name__ == '__main__':
    unittest.main()
