"""Corner label page -> pasted answer -> import: what was pressed is what is stored (docs/agent/QUALITY_RULES.md label-screen-round-trip)."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html import unescape
from pathlib import Path

from PIL import Image

from card_condition.data import LABELS
from tools import mobile_corner_label_import as importer, mobile_corner_label_pages as pages

ROOT = Path(__file__).resolve().parents[1]
AREAS = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
BOX = [.1, .1, .9, .9]


def press(page, presses):
    """Replay presses on the generated page's real script; returns the text a person would copy."""
    articles = []
    for block in re.findall(r'<article .*?</article>', page, re.S):
        tags = [(re.search(r'class="([^"]*)"', t), dict(re.findall(r'data-(\w+)="([^"]*)"', t))) for t in re.findall(r'<(?:article|div|button)\b[^>]*>', block)]
        nodes = [dict(names=c.group(1).split() if c else [], data={k: unescape(v) for k, v in d.items()}) for c, d in tags]
        articles.append(dict(data=nodes[0]['data'], kids=nodes[1:]))
    script = re.search(r'<script>(.*)</script>', page, re.S).group(1)
    done = subprocess.run([shutil.which('node'), str(ROOT / 'tests/corner_page_press.js')], capture_output=True, text=True, timeout=30,
                          check=True, input=json.dumps(dict(script=script, articles=articles, presses=presses)))
    return done.stdout


@unittest.skipUnless(shutil.which('node'), 'node unavailable: round trip UNVERIFIED')
class CornerLabelRoundTripTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder, self.ids = Path(temp.name), ('ebay/a:1', 'r<2>')
        image = str(self.folder / 'a.png')
        Image.new('RGB', (40, 60), (128, 128, 128)).save(image)
        self.rows = [dict(id=i, title='t', back=image, side_annotations=dict(
            back=dict(image=image, box=list(BOX), labels=dict.fromkeys(LABELS)))) for i in self.ids]
        self.review = self.folder / 'rows.jsonl'
        self.review.write_text('\n'.join(map(json.dumps, self.rows)), encoding='utf-8')
        self.page = self.build('page.html')

    def build(self, name, answers=None):
        pages.main(self.review, ' '.join(self.ids), self.folder / name, 'back', answers)
        return (self.folder / name).read_text(encoding='utf-8')

    def store(self, text):
        """Pasted text -> the real import entry point -> {row id: back annotation}."""
        (self.folder / 'answers.txt').write_text(text, encoding='utf-8')
        out = self.folder / 'out.jsonl'
        importer.main(self.review, self.folder / 'answers.txt', out)
        return {r['id']: r['side_annotations']['back'] for r in map(json.loads, out.read_text(encoding='utf-8').splitlines())}

    def test_pressed_states_ids_and_box_reach_the_stored_annotation(self):
        taps = dict(upper_left=1, upper_right=2, lower_left=3, lower_right=5)
        presses = ([dict(card=0, cell=a) for a, times in taps.items() for _ in range(times)]
                   + [dict(card=0, button='ok'), dict(card=1, button='alln'),
                      dict(card=1, handle='lt', to=[.25, .2]), dict(card=1, button='ok')])
        text = press(self.page, presses)
        self.assertEqual([line.split('=')[0] for line in text.splitlines()], [i + '/back' for i in self.ids])
        stored = self.store(text)
        first, second = (stored[i] for i in self.ids)
        self.assertEqual({a: v['corner_defect'] for a, v in first['region_labels'].items()},
                         dict(upper_left=0, upper_right=1, lower_right=1))  # 3 taps = back to 미확인 = not stored
        self.assertEqual((first['labels']['corner_defect'], first['box'], first['box_reviewed']), (1, BOX, True))
        self.assertEqual({a: v['corner_defect'] for a, v in second['region_labels'].items()}, dict.fromkeys(AREAS, 0))
        self.assertEqual((second['labels']['corner_defect'], second['box'], second['box_reviewed']), (0, [.25, .2, .9, .9], True))
        self.assertTrue(all(v[k] is None for a in (first, second) for v in a['region_labels'].values() for k in ('edge_defect', 'surface_defect')))

    def test_untouched_reset_and_unconfirmed_box_are_never_stored_as_normal(self):
        text = press(self.page, [dict(card=1, button='alln'), dict(card=1, button='ok'), dict(card=1, button='reset'),
                                 dict(card=1, handle='rb', to=[.8, .8])])
        for annotation in self.store(text).values():
            self.assertEqual(annotation['region_labels'], {})
            self.assertIsNone(annotation['labels']['corner_defect'])
            self.assertFalse(annotation['box_reviewed'])  # moving the box after confirming cancels the confirmation

    def test_reopening_with_the_pasted_answer_shows_the_same_answer(self):
        text = press(self.page, [dict(card=0, cell='upper_right'), dict(card=0, button='ok'), dict(card=1, button='alln')])
        (self.folder / 'pasted.txt').write_text(text, encoding='utf-8')
        self.assertEqual(press(self.build('again.html', self.folder / 'pasted.txt'), []), text)


if __name__ == '__main__':
    unittest.main()
