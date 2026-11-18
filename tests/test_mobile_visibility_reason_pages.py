import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import mobile_visibility_reason_pages as pages  # noqa: E402


class ReasonPagesTest(unittest.TestCase):
    def test_only_answered_limit_rows_are_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            Image.new('RGB', (20, 20), 'white').save(tmp / 'a.jpg')
            rows = [dict(group=g, side='back', target=t, image=str(tmp / 'a.jpg')) for g, t in (('g1', 1), ('g0', 0), ('g2', 1))]
            (tmp / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
            self.assertEqual(pages.main(tmp / 'rows.json', tmp / 'out.html'), 2)
            page = (tmp / 'out.html').read_text(encoding='utf-8')
        self.assertIn('data-id="g1"', page)
        self.assertIn('data-id="g2"', page)
        self.assertNotIn('data-id="g0"', page)
        self.assertEqual(page.count('type="checkbox"'), 2 * len(pages.REASONS))
        self.assertIn("'미확인'", page)

    def test_vocabulary_matches_stored_reasons(self):
        self.assertTrue({'perspective', 'glare', 'shadow', 'obstruction', 'cropped', 'blur'} <= {k for k, _ in pages.REASONS})


if __name__ == '__main__':
    unittest.main()
