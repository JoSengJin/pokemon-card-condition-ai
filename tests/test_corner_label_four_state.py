"""New corner screen (v2): 4 states round trip, original resolution gate, no prefill (accuracy-expert-chain R9, D-3). Synthetic photos only."""
import base64
import inspect
import json
import re
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

from card_condition.data import LABELS
from test_corner_label_round_trip import AREAS, press
from tools import mobile_corner_label_import as importer, mobile_corner_label_pages_v2 as v2

STATES = ('미확인', '정상', '결함', '판단 불가')  # tap order of the page
IDS = ('r1', 'r2', 'r3', 'r4', 'r5')


@unittest.skipUnless(shutil.which('node'), 'node unavailable: round trip UNVERIFIED')
class FourStateScreenTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        Image.new('RGB', (1200, 1600), (128, 128, 128)).save(self.dir / 'a.png')
        # Rows carry earlier answers and a model score: none of it may reach the page.
        labelled = dict(labels=dict.fromkeys(LABELS, 1), region_labels={a: dict(corner_defect=1) for a in AREAS})
        self.rows = [dict(id=i, title='t', model_score=0.987654, back=str(self.dir / 'a.png'), side_annotations=dict(back=dict(
            image=str(self.dir / 'a.png'), box=[.1, .1, .9, .9], **labelled))) for i in IDS]
        self.review = self.dir / 'rows.jsonl'
        self.review.write_text('\n'.join(map(json.dumps, self.rows)), encoding='utf-8')

    def build(self, name='page.html', ids=IDS, **kwargs):
        v2.main(self.review, ' '.join(ids), self.dir / name, 'back', **kwargs)
        return (self.dir / name).read_text(encoding='utf-8') if (self.dir / name).exists() else ''

    def record(self, name='page.html'):
        return json.loads((self.dir / f'{name}.criteria.json').read_text(encoding='utf-8'))

    def test_every_state_in_every_area_is_stored_as_pressed(self):
        ids = IDS[:4]
        taps = {i: {a: (n + k) % 4 for n, a in enumerate(AREAS)} for k, i in enumerate(ids)}  # latin square: each state meets each area
        presses = [dict(card=c, cell=a) for c, i in enumerate(ids) for a, t in taps[i].items() for _ in range(t)] + [dict(card=c, button='ok') for c in range(4)]
        text = press(self.build(ids=ids), presses)
        self.assertEqual({(i, a): STATES[t] for i in ids for a, t in taps[i].items()},
                         {(line.split('/')[0], area.split(':')[0]): area.split(':')[1] for line in text.splitlines() for area in line.split(';')[2:]})

    def test_import_of_the_pressed_answer_matches_each_state(self):
        ids = IDS[:4]
        taps = {i: {a: (n + k) % 4 for n, a in enumerate(AREAS)} for k, i in enumerate(ids)}
        presses = [dict(card=c, cell=a) for c, i in enumerate(ids) for a, t in taps[i].items() for _ in range(t)]
        clean = [dict(r, side_annotations=dict(back=dict(r['side_annotations']['back'], labels=dict.fromkeys(LABELS), region_labels={}))) for r in self.rows]
        self.review.write_text('\n'.join(map(json.dumps, clean)), encoding='utf-8')
        (self.dir / 'answers.txt').write_text(press(self.build(ids=ids), presses), encoding='utf-8')
        importer.main(self.review, self.dir / 'answers.txt', self.dir / 'out.jsonl', self.dir / 'page.html.criteria.json')
        stored = {r['id']: r['side_annotations']['back'] for r in map(json.loads, (self.dir / 'out.jsonl').read_text(encoding='utf-8').splitlines())}
        states = json.loads((self.dir / 'out.jsonl.states.json').read_text(encoding='utf-8'))
        for i in ids:
            for area, t in taps[i].items():
                with self.subTest(card=i, area=area, state=STATES[t]):
                    got = (stored[i]['region_labels'].get(area) or {}).get('corner_defect')
                    self.assertEqual(got, {1: 0, 2: 1}.get(t))
                    self.assertEqual(states['states'].get(f'{i}/back/{area}'), STATES[t] if t in (0, 3) else None)
        self.assertEqual(states['counts'], dict.fromkeys(STATES, 4))

    def test_nothing_earlier_is_shown_on_the_page(self):
        text = self.build()
        cells = re.findall(r'<div class="c"[^>]*data-s="([^"]*)"', text)
        self.assertEqual(cells, ['미확인'] * (4 * len(IDS)))
        for shown in ('data-ok="1"', '0.9876'):
            self.assertNotIn(shown, text)
        self.assertNotIn('answers_path', inspect.signature(v2.main).parameters)  # no way to reopen a page with earlier answers
        self.assertIn('data-ok="0"', text)

    def test_original_resolution_is_kept_and_recorded(self):
        Image.new('RGB', (3000, 4000), (90, 90, 90)).save(self.dir / 'big.png')
        self.rows[1]['side_annotations']['back']['image'] = str(self.dir / 'big.png')
        self.review.write_text('\n'.join(map(json.dumps, self.rows)), encoding='utf-8')
        text = self.build(ids=IDS[:2])
        shown = self.record()['screen']
        sizes = [Image.open(BytesIO(base64.b64decode(b))).size for b in re.findall(r'base64,([^"]*)"', text)]
        self.assertEqual(sizes, [(1200, 1600), (3000, 4000)])  # no downscale
        for rid, (orig, display) in zip(IDS, ((14.5454, 14.5454), (36.3636, 36.3636))):
            self.assertAlmostEqual(shown['original_px_per_mm'][f'{rid}/back'], orig, places=3)
            self.assertAlmostEqual(shown['display_px_per_mm'][f'{rid}/back'], display, places=3)
            self.assertGreaterEqual(shown['display_px_per_mm'][f'{rid}/back'], min(shown['original_px_per_mm'][f'{rid}/back'], 15.27))
        self.assertEqual((shown['image']['format'], shown['image']['quality'] >= 90, shown['image']['scale']), ('JPEG', True, 1.0))
        self.assertEqual(shown['states'], list(STATES))
        with Image.open(BytesIO(base64.b64decode(re.search(r'base64,([^"]*)"', text).group(1)))) as jpeg:
            self.assertLessEqual(jpeg.quantization[0][0], 3)  # quality >= 90 really used

    def test_a_screen_below_the_resolution_rule_is_not_written(self):
        with mock.patch.object(v2, 'SCALE', 0.5):
            with self.assertRaises(ValueError):
                self.build('low.html')
        self.assertEqual(list(self.dir.glob('low.html*')), [])

    def test_pieces_each_get_their_own_page_and_record(self):
        self.build('set.html', per_page=2)
        pieces = sorted(self.dir.glob('set-*.html'))
        self.assertEqual([p.name for p in pieces], ['set-1.html', 'set-2.html', 'set-3.html'])
        shown = [sorted(self.record(p.name)['items']) for p in pieces]
        self.assertEqual(shown, [['r1/back', 'r2/back'], ['r3/back', 'r4/back'], ['r5/back']])
        self.assertEqual(len({self.record(p.name)['criteria_sha256'] for p in pieces}), 1)
        with self.assertRaises(FileExistsError):  # an existing piece is never replaced
            self.build('set.html', per_page=2)


if __name__ == '__main__':
    unittest.main()
