import base64
import hashlib
import html
import itertools
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.mobile_assisted_review_page import STATES, load_review, main, page

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII=")


def fixture():
    review = dict(request_id="synthetic-review", result_sha256=hashlib.sha256(b"{}").hexdigest(), selections=[
        dict(number=1, part="edge", area="middle_left", label="가장자리", human_label=None),
        dict(number=2, part="surface", area="center", label="안쪽 면", human_label=None),
        dict(number=3, part="corner", area="lower_left", label="모서리", human_label=None)])
    return review, {key: PNG for key in ["1", "2", "3", "overview"]}


class MobileAssistedReviewTest(unittest.TestCase):
    def test_radios_are_visible_in_their_own_questions_not_before_content(self):
        review, images = fixture()
        output = page(review, images)
        sections = re.findall(r'<section data-number="([123])">(.*?)</section>', output, re.S)
        self.assertEqual(3, len(sections))
        for number, section in sections:
            controls = re.findall(r'<input type="radio" id="([^"]+)" name="([^"]+)"', section)
            self.assertEqual(4, len(controls))
            self.assertEqual({"choice-" + number}, {name for _, name in controls})
            self.assertIn("<fieldset><legend>" + number, section)
            self.assertEqual(1, len(re.findall(r'<input[^>]* checked>', section)))
        self.assertEqual(12, output.count('type="radio"'))
        self.assertNotIn('type="radio"', output.split('<form class="review">')[0])
        self.assertIn(".choices input{position:static;", output)
        for absent in ("sr-radio", "autofocus", "scrollIntoView", "<script", "margin:-1px"):
            self.assertNotIn(absent, output)
        self.assertEqual(["#results"], re.findall(r'href="([^"]+)"', output))

    def test_all_64_script_free_outputs_match_the_frozen_mapping(self):
        review, images = fixture()
        output = page(review, images)
        payloads = dict(re.findall(r'<div class="result-case" id="result-([a-z-]+)">.*?<textarea[^>]*>(.*?)</textarea>', output, re.S))
        self.assertEqual(64, len(payloads))
        for combination in itertools.product(STATES, repeat=3):
            suffix = "-".join(key for key, _ in combination)
            payload = json.loads(html.unescape(payloads[suffix]))
            self.assertEqual(review["request_id"], payload["review_id"])
            self.assertEqual(review["result_sha256"], payload["result_sha256"])
            expected = {f'{item["number"]}.{item["part"]}.{item["area"]}': value
                        for item, (_, value) in zip(review["selections"], combination)}
            self.assertEqual(expected, payload["answers"])
            selector = "form.review" + "".join(f":has(#c{n}-{key}:checked)" for n, (key, _) in enumerate(combination, 1))
            self.assertIn(selector + " #result-" + suffix + "{display:block}", output)
            self.assertIn(selector + " #manual-fallback{display:none}", output)
        self.assertIn('id="manual-fallback"', output)
        self.assertIn("직접 입력:", output)

    def test_preserves_confirmed_answers_and_never_overwrites_prior_html(self):
        review, images = fixture()
        for item, value in zip(review["selections"], ["결함", "모르겠음", "정상"]):
            item["human_label"] = value
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "review-map.json").write_text(json.dumps(review))
            (root / "result.json").write_bytes(b"{}")
            for key, data in images.items():
                (root / ("priority-overview.png" if key == "overview" else f"zone-{key}.png")).write_bytes(data)
            target = root / "new.html"
            self.assertEqual(0, main([str(root), str(target)]))
            output = target.read_text()
            self.assertEqual(["결함", "모르겠음", "정상"], re.findall(r'<input[^>]* value="([^"]+)" checked>', output))
            frozen = target.read_bytes()
            with self.assertRaises(FileExistsError):
                main([str(root), str(target)])
            self.assertEqual(frozen, target.read_bytes())
            (root / "result.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "frozen model result"):
                load_review(root)
