"""Back-visibility and blind corner-zone label pages: what was pressed is what the result text says (docs/agent/QUALITY_RULES.md label-screen-round-trip).
No importer exists for the visibility page (answers are read by hand), so it is checked up to the result string; the blind page is also read back with score.parse."""
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html import unescape
from pathlib import Path

from PIL import Image

from tools import mobile_visibility_label_pages as visibility, relabel_corner_blind_pages as blind

ROOT = Path(__file__).resolve().parents[1]
# Known, unfixed defect (open item in docs/collaboration/tasks/quality-decisions-20261125.md 미해결, not part of this task): the shared zone script needs a #alln button the blind page does not have.
KNOWN_BLIND_ERROR = "script error: Cannot set properties of null (setting 'onclick')"
SCORE = ROOT / 'tools/diagnostics/corner-rejudge-20261121/score.py'


def press(page, presses, expected_error=''):
    """Replay presses on the generated page's real script; returns the text a person would copy."""
    attrs = lambda tag: {k: unescape(v) for k, v in re.findall(r'data-(\w+)="([^"]*)"', tag)}
    articles = [dict(data=attrs(re.match(r'<article[^>]*>', block).group(0)), kids=[dict(data=attrs(t)) for t in re.findall(r'<button\b[^>]*>', block)])
                for block in re.findall(r'<article .*?</article>', page, re.S)]
    script = re.search(r'<script>(.*)</script>', page, re.S).group(1)
    done = subprocess.run([shutil.which('node'), str(ROOT / 'tests/label_page_press.js')], capture_output=True, text=True, timeout=30, check=True,
                          input=json.dumps(dict(script=script, articles=articles, presses=presses)))
    if done.stderr.strip() != expected_error:  # any script error other than the one known error fails the test
        raise AssertionError(f'page script error: {done.stderr!r}')
    return done.stdout


@unittest.skipUnless(shutil.which('node'), 'node unavailable: round trip UNVERIFIED')
class VisibilityBlindRoundTripTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.image = str(self.folder / 'a.png')
        Image.new('RGB', (40, 60), (128, 128, 128)).save(self.image)

    def test_visibility_pressed_words_and_ids_reach_the_result_text(self):
        ids = ('ebay/a:1', 'r<2>', 'r3')
        rows = [dict(id=i, side_annotations=dict(back=dict(image=self.image))) for i in ids]
        (self.folder / 'rows.jsonl').write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
        visibility.main(self.folder / 'rows.jsonl', ' '.join(ids), self.folder / 'v.html')
        page = (self.folder / 'v.html').read_text(encoding='utf-8')
        self.assertIn('카드 상태를 일부라도 볼 수 없으면 <b>제한</b>', page)  # the generated page, not just the source, carries the canonical guide
        text = press(page, [dict(card=0, v='정상'), dict(card=0, v='제한'), dict(card=1, v='정상')])
        self.assertEqual(text.splitlines(), ['ebay/a:1/back=제한', 'r<2>/back=정상', 'r3/back=미확인'])  # last press wins; untouched stays 미확인
        self.assertEqual(press(page, [dict(card=2, v='미확인')]).splitlines()[2], 'r3/back=미확인')

    def test_blind_pressed_words_reach_score_parse(self):
        zones = [dict(image=self.image, box=[.1, .1, .5, .5]) for _ in range(4)]
        spec = importlib.util.spec_from_file_location('corner_rejudge_score', SCORE)
        score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(score)
        page = blind.page(1, 1, 1, zones)
        self.assertIn(blind.INSTRUCTIONS, page)
        text = press(page, [dict(card=0, v='결함'), dict(card=1, v='정상'), dict(card=2, v='불가'), dict(card=2, v='정상'), dict(card=2, v='불가')],
                     KNOWN_BLIND_ERROR)
        self.assertEqual(score.parse(text), {1: '결함', 2: '정상', 3: '불가', 4: '미확인'})


if __name__ == '__main__':
    unittest.main()
