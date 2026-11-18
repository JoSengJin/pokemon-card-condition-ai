import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import mobile_visibility_rejudge_pages as pages  # noqa: E402

ANSWERS = 'g1/back=not_limited\ng2/back=glare,obstruction\ng3/back=not_limited\ng4/back=미확인\n'


class SelectCandidatesTest(unittest.TestCase):
    def test_only_not_limited_lines_are_candidates(self):
        self.assertEqual(pages.select_candidates(ANSWERS), ['g1', 'g3'])

    def test_reason_rows_are_never_candidates_even_if_mixed(self):
        self.assertEqual(pages.select_candidates('a/back=glare,not_limited\nb/back=blur\n'), ['a'])


class ParseRejudgeTest(unittest.TestCase):
    def test_valid_answers_parse_to_verdict_and_confidence(self):
        got = pages.parse_rejudge('g1/back=정상;확신\ng3/back=제한;애매\n', ['g1', 'g3'])
        self.assertEqual(got, {'g1': ('정상', '확신'), 'g3': ('제한', '애매')})

    def test_rejects_missing_unknown_or_extra_groups(self):
        for text in ('g1/back=정상;확신\n', 'g1/back=정상;확신\ng3/back=제한;애매\ngx/back=정상;확신\n', 'g1/back=정상;확신\ngz/back=제한;애매\n'):
            with self.assertRaises(ValueError):
                pages.parse_rejudge(text, ['g1', 'g3'])

    def test_rejects_values_outside_vocabulary_or_without_confidence(self):
        for text in ('g1/back=glare;확신\ng3/back=제한;애매\n', 'g1/back=정상\ng3/back=제한;애매\n', 'g1/back=정상;몰라\ng3/back=제한;애매\n'):
            with self.assertRaises(ValueError):
                pages.parse_rejudge(text, ['g1', 'g3'])


class PageTest(unittest.TestCase):
    def test_page_has_one_article_per_candidate_and_no_other_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            Image.new('RGB', (20, 20), 'white').save(tmp / 'a.jpg')
            rows = [dict(group=g, side='back', target=1, image=str(tmp / 'a.jpg')) for g in ('g1', 'g2', 'g3', 'g4')]
            (tmp / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
            (tmp / 'ans.txt').write_text(ANSWERS, encoding='utf-8')
            self.assertEqual(pages.main(tmp / 'ans.txt', tmp / 'rows.json', tmp / 'out.html'), 2)
            page = (tmp / 'out.html').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'<article data-id="([^"]+)"', page), ['g1', 'g3'])


if __name__ == '__main__':
    unittest.main()
