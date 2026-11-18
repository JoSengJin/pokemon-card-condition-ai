import re
import unittest

from card_condition.observation_evidence import R1_SCENARIOS
from tools.mobile_r1_check_page import page


class R1CheckPageTest(unittest.TestCase):
    def test_every_r1_scenario_has_exactly_one_card(self):
        # Breaks if a scenario is added/removed in the evidence contract but the phone page drifts.
        found = re.findall(r'<article data-s="([a-z_0-9]+)"', page())
        self.assertEqual(sorted(found), sorted(R1_SCENARIOS))

    def test_page_script_is_syntactically_valid_js(self):
        import shutil, subprocess, tempfile, pathlib
        node = shutil.which('node')
        if not node:
            self.skipTest('node unavailable')
        script = re.search(r'<script>(.*)</script>', page(), re.S).group(1)
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 's.js'
            p.write_text(script, encoding='utf-8')
            self.assertEqual(subprocess.run([node, '--check', str(p)], capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
