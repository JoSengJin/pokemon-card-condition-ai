import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FROZEN = dict(  # sha256 of the tool constants before the 2026-11-24 text change
    SCRIPT='54eb97a53e79c7711eef325057aff8edd9a26d6827be965b829e6804b868bda2',
    STYLE='eb29bf196cda11322170f82697068caa01524880664308b40b0e0e9276224969',
    AREAS='512d2893f138655c17ff2f58c219e9bf6bae540be83c958b24bc3e68030b3f67')
spec = importlib.util.spec_from_file_location('mobile_corner_label_pages', ROOT / 'tools/mobile_corner_label_pages.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def build(folder, name='page.html'):
    """Synthetic 1-row review file + gray image in `folder`; returns the new html text and path."""
    Image.new('RGB', (40, 60), (128, 128, 128)).save(folder / 'a.png')
    row = dict(id='r1', title='t', side_annotations=dict(back=dict(image=str(folder / 'a.png'), box=[.1, .1, .9, .9])))
    (folder / 'rows.jsonl').write_text(json.dumps(row), encoding='utf-8')
    out = folder / name
    tool.main(folder / 'rows.jsonl', 'r1', out)
    return out.read_text(encoding='utf-8'), out


class CornerLabelPagesTest(unittest.TestCase):
    def test_new_and_existing_text(self):
        with tempfile.TemporaryDirectory() as d:
            text, _ = build(Path(d))
        for phrase in ('확대해서 보이면 크기와 관계없이 결함', 'mm 크기 문턱은 두지 않음',
                       '확대해도 반사인지 마모인지 구분 안 되면 추정하지 말고 이 화면에서는 미확인',
                       '옆면 테두리(엣지)의 마모·백화, 표면 기스·오염은 결함으로 누르지 마세요',
                       '모르면 미확인으로 두세요. 자동 저장하지 않습니다.'):
            self.assertIn(phrase, text)

    def test_frozen_constants(self):
        self.assertEqual(hashlib.sha256(tool.SCRIPT.encode()).hexdigest(), FROZEN['SCRIPT'])
        self.assertEqual(hashlib.sha256(tool.STYLE.encode()).hexdigest(), FROZEN['STYLE'])
        self.assertEqual(hashlib.sha256(repr(tool.AREAS).encode()).hexdigest(), FROZEN['AREAS'])

    def test_result_format_and_initial_state(self):
        with tempfile.TemporaryDirectory() as d:
            text, _ = build(Path(d))
        self.assertIn("a.dataset.id+'='+(a.dataset.ok==='1'?'확인':'미확인')+';box:'", tool.SCRIPT)
        self.assertIn("c.dataset.a+':'+c.dataset.s", tool.SCRIPT)
        self.assertEqual(text.count('data-s="미확인"'), 4)
        self.assertNotIn('data-s="정상"', text)
        self.assertNotIn('data-s="결함"', text)
        self.assertIn('data-ok="0"', text)

    def test_existing_html_untouched_on_new_path(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / 'old.html'
            old.write_bytes(b'<html>earlier screen</html>')
            _, new = build(Path(d), 'new.html')
            self.assertEqual(old.read_bytes(), b'<html>earlier screen</html>')
            self.assertNotEqual(new, old)


if __name__ == '__main__':
    unittest.main()
