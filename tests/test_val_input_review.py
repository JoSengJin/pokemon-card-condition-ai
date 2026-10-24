import json
from pathlib import Path
import tempfile
import unittest

from card_condition.val_input_review import build


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'artifacts/kieuk14-train-20261013/combined.jsonl'
EARLIER = ROOT/'artifacts/kieuk14-train-20261013/candidate224/report.json'
LATER = ROOT/'artifacts/kieuk15-edge-views-trainval-20261013/candidate/report.json'


class ValInputReviewTest(unittest.TestCase):
    def test_frozen_validation_inputs_and_denominator(self):
        before = MANIFEST.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'review'
            result = build(MANIFEST, EARLIER, LATER, output)
            self.assertEqual([(3, 8), (7, 8)],
                             [(count['fp'], count['negative']) for count in result['counts']])
            self.assertEqual(9, result['regions'])
            self.assertFalse(result['independent_performance'])
            self.assertEqual(9, (output/'index.html').read_text().count('사람 정답:'))
            self.assertEqual(result, json.loads((output/'report.json').read_text()))
            self.assertEqual(before, MANIFEST.read_bytes())
            with self.assertRaisesRegex(ValueError, 'exists'):
                build(MANIFEST, EARLIER, LATER, output)
