import tempfile
import unittest
from pathlib import Path

from card_condition.performance_view import build, counts


class PerformanceViewTest(unittest.TestCase):
    def test_confusion_counts(self):
        self.assertEqual(counts([(1, 1), (0, 0), (0, 1), (1, 0)]),
                         dict(tp=1, tn=1, fp=1, fn=1))

    def test_builds_separate_evidence_tiers_without_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'index.html'
            result = build(path)
            page = path.read_text()
            self.assertEqual(result['heldout']['primary'], dict(tp=0, tn=8, fp=0, fn=1))
            self.assertEqual(len(result['exploratory']), 2)
            self.assertEqual(page.count('data:image/jpeg;base64,'), 6)
            self.assertEqual(result['normal_only'], [dict(tp=0, tn=2, fp=6, fn=0)] * 2)
            self.assertIn('정상 엣지만 독립 확인', page)
            self.assertIn('독립 시험', page)
            self.assertIn('탐색용 비교', page)
            self.assertIn('모델 추론 전', page)
            self.assertIn('일반화 정확도가 아닙니다', page)
            with self.assertRaisesRegex(ValueError, 'Output exists'):
                build(path)


if __name__ == '__main__':
    unittest.main()
