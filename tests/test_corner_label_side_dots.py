"""Corner screen v2 (2026-11-29 phone test): the drag dots sit on the box sides, never on its corners, and each moves one side; the cells say 탭. Synthetic photos only."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from test_corner_label_round_trip import press
from tools import mobile_corner_label_pages_v2 as v2

BOX = [.1, .1, .9, .9]


@unittest.skipUnless(shutil.which('node'), 'node unavailable: drag replay UNVERIFIED')
class SideDotsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        Image.new('RGB', (1200, 1600), (128, 128, 128)).save(folder / 'a.png')
        row = dict(id='r1', title='t', side_annotations=dict(back=dict(image=str(folder / 'a.png'), box=BOX)))
        (folder / 'rows.jsonl').write_text(json.dumps(row), encoding='utf-8')
        v2.main(folder / 'rows.jsonl', 'r1', folder / 'page.html', 'back')
        self.page = (folder / 'page.html').read_text(encoding='utf-8')

    def test_each_side_dot_moves_only_its_side_and_no_dot_is_on_a_corner(self):
        self.assertEqual(re.findall(r'class="h" data-k="([^"]*)"', self.page), ['t', 'r', 'b', 'l'])
        moves = {'l': ([.2, .5], [.2, .1, .9, .9]), 'r': ([.7, .5], [.1, .1, .7, .9]),
                 't': ([.5, .3], [.1, .3, .9, .9]), 'b': ([.5, .6], [.1, .1, .9, .6])}
        for dot, (to, box) in moves.items():
            with self.subTest(dot=dot):
                text = press(self.page, [dict(card=0, handle=dot, to=to)])
                self.assertEqual(text.split(';')[1], 'box:' + ','.join(f'{v:.4f}' for v in box))
        layout = re.search(r"querySelectorAll\('\.h'\)\.forEach\(e=>\{(.*?)\}\)\}", self.page).group(1)
        self.assertIn('(l+r)/2', layout)  # top/bottom dots at the middle of the side, not at a corner
        self.assertIn('(t+b)/2', layout)

    def test_cells_tell_to_tap_until_answered(self):
        self.assertIn('.c[data-s="미확인"] i::after{content:"탭"', self.page)
        self.assertIn('점선 모서리 칸을 탭해 입력', self.page)
        text = press(self.page, [dict(card=0, cell='upper_left'), dict(card=0, cell='upper_left')])
        self.assertIn('upper_left:결함', text)


if __name__ == '__main__':
    unittest.main()
