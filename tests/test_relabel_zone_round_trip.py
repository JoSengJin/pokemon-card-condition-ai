"""Shared zone-page script: with or without the 안 누른 곳 전부 정상 button, pressed words reach the result text and 결과 복사 is wired (QUALITY_RULES label-screen-round-trip)."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from html import unescape
from pathlib import Path

from PIL import Image

from tools import relabel_corner_blind_pages as blind, relabel_corner_highres_pages as highres, relabel_zone_pages as zp

ROOT = Path(__file__).resolve().parents[1]


def run(page, presses, alln):
    """Replay presses on the generated page's real script; returns (result text, copy message, script error)."""
    attrs = lambda tag: {k: unescape(v) for k, v in re.findall(r'data-(\w+)="([^"]*)"', tag)}
    articles = [dict(data=attrs(re.match(r'<article[^>]*>', b).group(0)), kids=[dict(data=attrs(t)) for t in re.findall(r'<button\b[^>]*>', b)])
                for b in re.findall(r'<article .*?</article>', page, re.S)]
    script = re.search(r'<script>(.*)</script>', page, re.S).group(1)
    done = subprocess.run([shutil.which('node'), str(ROOT / 'tests/label_page_press.js')], capture_output=True, text=True, timeout=30,
                          input=json.dumps(dict(script=script, articles=articles, presses=presses, alln=alln, full=True)))
    if done.returncode:
        raise AssertionError(done.stderr.strip())
    return json.loads(done.stdout), done.stderr.strip()


@unittest.skipUnless(shutil.which('node'), 'node unavailable: round trip UNVERIFIED')
class ZoneScriptRoundTripTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.image = str(Path(temp.name) / 'a.png')
        Image.new('RGB', (40, 60), (128, 128, 128)).save(self.image)
        self.zones = [dict(image=self.image, box=[.1, .1, .5, .5], area='a', group='g', n=i) for i in (1, 2, 3)]

    def test_pages_without_alln_button_wire_copy_and_results(self):
        for name, page in (('blind', blind.page(1, 1, 1, self.zones)), ('highres', highres.page(1, 1, self.zones))):
            with self.subTest(name):
                self.assertNotIn('id="alln"', page)
                got, error = run(page, [dict(card=0, v='결함'), dict(card=1, v='정상'), dict(id='copy')], alln=False)
                self.assertEqual(error, '')
                self.assertEqual([l.split('=')[1] for l in got['out'].splitlines()], ['결함', '정상', '미확인'])
                self.assertIn('복사됨', got['msg'])

    def test_zone_page_with_alln_keeps_old_behavior(self):
        got, error = run(zp.page(1, 1, 1, self.zones), [dict(card=0, v='결함'), dict(id='alln'), dict(id='copy')], alln=True)
        self.assertEqual(error, '')
        self.assertEqual([l.split('=')[1] for l in got['out'].splitlines()], ['결함', '정상', '정상'])  # pressed stays, untouched becomes 정상
        self.assertIn('복사됨', got['msg'])


if __name__ == '__main__':
    unittest.main()
