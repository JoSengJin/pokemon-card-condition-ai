import json
import random
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools import back_triage_review_v2 as v2
from tools.back_triage_review import CHOICES

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'artifacts/e2-scenario-20261120'
REQ = ROOT / 'artifacts/e2-scenario-20261104/requests.json'


def synthetic(folder, noisy=False):
    path = Path(folder) / 'c.jpg'
    if noisy:
        rnd = random.Random(1)
        im = Image.frombytes('RGB', (1400, 1900), bytes(rnd.randrange(256) for _ in range(1400 * 1900 * 3)))
    else:
        im = Image.new('RGB', (1400, 1900), (120, 130, 140))
    im.save(path, 'JPEG', quality=90)
    req = dict(id='ebay-pair-abcdef0123456789', side='back', image=str(path), box=[.1, .1, .9, .9], box_reviewed=True)
    zone = lambda a: dict(area=a, score=.9, band='high', rank=1, label='점검 우선순위 높음')
    part = lambda a: dict(status='ranked', zones=[zone(a)], model_sha256='ab' * 32)
    res = dict(id=req['id'], results=dict(edge=part('upper_left'), corner=part('lower_right'), surface=part('center'),
                                          observation_limit=dict(status='scored', label='낮음', model_sha256='cd' * 32)))
    return req, res


class AnsweredIdsTest(unittest.TestCase):
    def test_reads_answers_and_walkthrough_ignores_comments(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'answers-1-5.txt').write_text('# 쪽 1 · 답한 카드 1/1\nebay-pair-a=edge:문제가 보인다;miss:;\n\n')
            Path(d, 'walkthrough-x.txt').write_text('ebay-pair-b=edge:모르겠다;miss:upper_left;memo\nnoise line\n')
            Path(d, 'other.txt').write_text('ebay-pair-c=edge:x;miss:;\n')
            self.assertEqual({'ebay-pair-a', 'ebay-pair-b'}, v2.answered_ids([d]))

    def test_comment_line_has_no_equals_so_old_parse_skips_it(self):
        line = v2.summary_comment(41, 2, 2)
        self.assertTrue(line.startswith('#') and '=' not in line)

    def test_remaining_is_requests_80_to_138_on_real_data(self):
        if not (REQ.exists() and OLD.exists()):
            self.skipTest('artifacts not present')
        reqs = json.loads(REQ.read_text())
        ans = v2.answered_ids([OLD, REQ.parent])
        results = json.loads((OLD / 'results.json').read_text())['results']
        left = v2.remaining(reqs, results, ans)
        self.assertEqual([r['id'] for r in reqs[80:]], [r['id'] for r, _, _ in left])
        self.assertEqual(58, len(left))
        self.assertTrue(all(r['id'] == x['id'] for r, x, _ in left))
        self.assertFalse({r['id'] for r, _, _ in left} & ans)
        self.assertEqual(list(range(1, 59)), [n for _, _, n in left])


class CardTest(unittest.TestCase):
    def test_card_has_big_buttons_with_old_values_and_explicit_no_miss(self):
        with tempfile.TemporaryDirectory() as d:
            req, res = synthetic(d)
            html = v2.card_v2(req, res, 1, 58)
        self.assertEqual(3, html.count('class="q"'))
        for part in ('edge', 'corner', 'surface'):
            self.assertIn(f'data-name="{part}"', html)
        self.assertEqual(3, html.count(f'data-v="{CHOICES[1]}"'))
        self.assertEqual(3, html.count(f'data-v="{CHOICES[2]}"'))
        self.assertEqual(3, html.count(f'data-v="{CHOICES[3]}"'))
        self.assertEqual(9, html.count('class="c"'))
        self.assertIn('class="nm"', html)
        self.assertIn('1/58', html)
        self.assertIn('3칸 중 0칸 답함', html)

    def test_held_part_has_no_question(self):
        with tempfile.TemporaryDirectory() as d:
            req, res = synthetic(d)
            res['results']['corner'] = dict(status='held', reason='x', model_sha256='ab' * 32)
            html = v2.card_v2(req, res, 2, 58)
        self.assertEqual(2, html.count('class="q"'))
        self.assertIn('2칸 중 0칸 답함', html)
        self.assertIn('사람이 직접 확인', html)


class PageTest(unittest.TestCase):
    def page(self):
        with tempfile.TemporaryDirectory() as d:
            req, res = synthetic(d)
            body = v2.card_v2(req, res, 1, 58) + v2.card_v2(req, res, 2, 58)
        return v2.page_v2(body, 1, 29, 2)

    def test_output_expression_matches_old_format(self):
        page = self.page()
        self.assertIn("a.dataset.id+'='", page)
        self.assertIn("+':'+", page)
        self.assertIn("+';miss:'+", page)
        self.assertIn("(선택 안 함)", page)
        self.assertIn("[name=n]", page)

    def test_phone_constraints(self):
        page = self.page()
        for banned in ('localStorage', 'sessionStorage', 'clipboard', 'http://', 'https://'):
            self.assertNotIn(banned, page)
        self.assertIn('select()', page)
        self.assertIn('이 쪽 완료 0/2', page)
        self.assertIn('낮음이어도 사진이 괜찮다는 뜻', page)

    def test_real_pages_stay_under_limit(self):
        if not (REQ.exists() and OLD.exists()):
            self.skipTest('artifacts not present')
        with tempfile.TemporaryDirectory() as d:
            info = v2.main(d, REQ, OLD / 'results.json', OLD, REQ.parent)
            sizes = [p.stat().st_size for p in Path(d).glob('review-v2-*.html')]
        self.assertEqual((58, 29), (info['cards'], info['pages']))
        self.assertEqual(29, len(sizes))
        self.assertLessEqual(max(sizes), 700_000)

    def test_summary_comment_format(self):
        self.assertEqual('# v2 쪽 3 · 답한 카드 1/2', v2.summary_comment(3, 1, 2))
        self.assertTrue(re.search(r'summary_comment|# v2 쪽', self.page()))


if __name__ == '__main__':
    unittest.main()
