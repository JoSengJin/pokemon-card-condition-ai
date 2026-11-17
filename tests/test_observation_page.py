import base64
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from observation_loop_fixture import fixture


class ObservationPageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_page"), "page renderer missing")
        self.page = importlib.import_module("card_condition.observation_page")

    def test_renders_checked_bytes_and_escaped_public_payload(self):
        for mode in ("H", "A"):
            packet, assets = fixture(mode, '</script><img src=x onerror="sentinel"> 원문')
            before = copy.deepcopy(packet)
            page = self.page.render_page(packet, assets)
            encoded = re.search(r'<script id="assets" type="application/json">(.*?)</script>', page, re.S)[1]
            self.assertEqual({ref: base64.b64decode(value) for ref, value in json.loads(encoded).items()}, assets)
            body = json.loads(re.search(r'<script id="packet" type="application/json">(.*?)</script>', page, re.S)[1])
            self.assertEqual(body, packet)
            self.assertNotIn('<img src=x', page)
            self.assertIn('&lt;/script&gt;', page)
            self.assertIn('id="r1-context"', page)
            self.assertIn('id="r1-region"', page)
            self.assertNotIn('src="assets/', page)
            self.assertNotIn('https://', page)
            self.assertEqual(packet, before)

    def test_rejects_invalid_asset_packet_and_unsupported_profile(self):
        packet, assets = fixture()
        assets['assets/a1.png'] = assets['assets/a2.png']
        with self.assertRaises(ValueError):
            self.page.render_page(packet, assets)
        packet, assets = fixture()
        packet['score'] = {'region_target': 1}
        with self.assertRaises(ValueError):
            self.page.render_page(packet, assets)
        for key, value in (("renderer_version", "other"), ("resize", "contain"), ("interpolation", "unknown")):
            packet, assets = fixture()
            packet['profile'][key] = value
            from card_condition.observation_packet import packet_digest
            packet['packet_id'] = packet_digest(packet)
            with self.assertRaises(ValueError):
                self.page.render_page(packet, assets)

    def test_browser_hash_blob_decode_and_invalidation_with_synthetic_dom(self):
        packet, assets = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic.html'
            path.write_text(self.page.render_page(packet, assets))
            for scenario in ('baseline', 'initial', 'ref'):
                with self.subTest(scenario=scenario):
                    result = subprocess.run(['node', 'tests/observation_display.test.cjs', str(path), scenario], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('display synthetic checks passed', result.stdout)
