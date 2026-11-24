"""Criteria/crop provenance for the corner label page + import (docs/agent/QUALITY_RULES.md label-provenance).
Known limit: a different page showing the same id set cannot be detected, because the pasted answer carries no page hash."""
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from card_condition.data import LABELS
from test_corner_label_round_trip import press
from tools import label_criteria, mobile_corner_label_import as importer, mobile_corner_label_pages as pages

IDS = ('ebay/a:1', 'r<2>')
ROOT = Path(__file__).resolve().parents[1]
# Output of the page tool at f37f2cb0 (tool file identical to e3587264), same input, photo mocked. Update when the approved wording changes.
FROZEN_PAGE = 'd74823c5c19a590767710d5c5f0765e3a580e585ea47765e4667298a2639eba7'


def record(path):
    return json.loads(Path(f'{path}.criteria.json').read_text(encoding='utf-8'))


class CriteriaRecordTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        image = str(self.dir / 'a.png')
        Image.new('RGB', (40, 60), (128, 128, 128)).save(image)
        rows = [dict(id=i, title='t', back=image, side_annotations=dict(back=dict(image=image, box=[.1, .1, .9, .9], labels=dict.fromkeys(LABELS)))) for i in IDS]
        self.review, self.page = self.dir / 'rows.jsonl', self.dir / 'page.html'
        self.review.write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
        pages.main(self.review, ' '.join(IDS), self.page)
        self.criteria = f'{self.page}.criteria.json'
        lines = (f'{i}/back=확인;box:0.1000,0.1000,0.9000,0.9000;' + ';'.join(f'{a}:정상' for a in importer.AREAS) for i in IDS)
        self.answers = self.dir / 'answers.txt'
        self.answers.write_text('\n'.join(lines), encoding='utf-8')

    def test_page_record_hashes_and_one_character_change(self):
        text, data = self.page.read_text(encoding='utf-8'), record(self.page)
        crops = [hashlib.sha256(base64.b64decode(b)).hexdigest() for b in re.findall(r'base64,([^"]*)"', text)]
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['page_sha256'], hashlib.sha256(self.page.read_bytes()).hexdigest())
        self.assertEqual(data['criteria_sha256'], hashlib.sha256(pages.INSTRUCTIONS.encode()).hexdigest())
        self.assertEqual(data['items'], {f'{i}/back': c for i, c in zip(IDS, crops)})
        self.assertIn('<h1>모서리 구역 라벨</h1>' + pages.INSTRUCTIONS, text)
        with mock.patch.object(pages, 'photo', return_value='QUJD'):  # whole-page identity with base e3587264
            pages.main(self.review, ' '.join(IDS), self.dir / 'f.html')
            self.assertEqual(hashlib.sha256((self.dir / 'f.html').read_bytes()).hexdigest(), FROZEN_PAGE)
            with self.assertRaises(ValueError):  # same id twice: refused before anything is written
                pages.main(self.review, IDS[0] + ' ' + IDS[0], self.dir / 'g.html')
        self.assertEqual(list(self.dir.glob('g.html*')), [])
        original = pages.INSTRUCTIONS
        self.addCleanup(setattr, pages, 'INSTRUCTIONS', original)
        pages.INSTRUCTIONS = original.replace('모르면', '모르면.', 1)
        pages.main(self.review, ' '.join(IDS), self.dir / 'b.html')
        self.assertNotEqual(record(self.dir / 'b.html')['criteria_sha256'], data['criteria_sha256'])

    def test_existing_record_keeps_the_original_page_and_failed_write_leaves_no_record(self):
        old = self.page.read_bytes()
        with self.assertRaises(FileExistsError):
            pages.main(self.review, ' '.join(IDS), self.page)
        self.assertEqual(self.page.read_bytes(), old)
        (self.dir / 'blocked.html').mkdir()
        with self.assertRaises(OSError):
            pages.main(self.review, ' '.join(IDS), self.dir / 'blocked.html')
        self.assertFalse((self.dir / 'blocked.html.criteria.json').exists())
        rows = [json.loads(line) for line in self.review.read_text(encoding='utf-8').splitlines()]
        rows[0]['title'] = 'x base64,AAAA "q"'  # title text must not be taken for the image
        (self.dir / 'rows2.jsonl').write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')
        pages.main(self.dir / 'rows2.jsonl', ' '.join(IDS), self.dir / 'c.html')
        self.assertEqual(record(self.dir / 'c.html')['items'], record(self.page)['items'])
        with self.assertRaises(ValueError):  # an article without an image: refuse before writing
            label_criteria.write_page(self.dir / 'd.html', 'x', 'y', '<article data-id="a"><h2>t</h2></article>')
        self.assertEqual(list(self.dir.glob('d.html*')), [])

    def test_import_with_record_keeps_label_bytes_and_writes_provenance(self):
        importer.main(self.review, self.answers, self.dir / 'plain.jsonl')
        importer.main(self.review, self.answers, self.dir / 'with.jsonl', self.criteria)
        self.assertEqual((self.dir / 'with.jsonl').read_bytes(), (self.dir / 'plain.jsonl').read_bytes())
        self.assertFalse((self.dir / 'plain.jsonl.criteria.json').exists())
        with mock.patch.object(label_criteria.json, 'dump', side_effect=OSError):  # provenance write fails: no labels left, retry possible
            with self.assertRaises(OSError):
                importer.main(self.review, self.answers, self.dir / 'f.jsonl', self.criteria)
        self.assertEqual(list(self.dir.glob('f.jsonl*')), [])
        (self.dir / 'h.jsonl').write_text('labels', encoding='utf-8')
        (self.dir / 'h.jsonl.criteria.json').write_text('foreign', encoding='utf-8')
        with self.assertRaises(FileExistsError):  # a record that already exists is not ours to delete
            label_criteria.write_import(self.dir / 'h.jsonl', {})
        self.assertEqual((self.dir / 'h.jsonl.criteria.json').read_text(encoding='utf-8'), 'foreign')
        self.assertFalse((self.dir / 'h.jsonl').exists())
        script = [sys.executable, str(ROOT / 'tools/mobile_corner_label_import.py'), str(self.review), str(self.answers)]
        subprocess.run(script + [str(self.dir / 'f.jsonl'), self.criteria], check=True, capture_output=True)  # CLI takes the 4th argument
        self.assertTrue((self.dir / 'f.jsonl.criteria.json').exists())
        shown = record(self.page)
        self.assertEqual(record(self.dir / 'with.jsonl'), {k: dict(criteria_sha256=shown['criteria_sha256'], crop_sha256=v) for k, v in shown['items'].items()})

    def test_foreign_schema_or_taken_output_refused_before_any_output(self):
        for name, edit in (('other', lambda d: d['items'].pop('r<2>/back')), ('schema', lambda d: d.update(schema_version=2))):
            shown = record(self.page)
            edit(shown)
            (self.dir / f'{name}.json').write_text(json.dumps(shown), encoding='utf-8')
            with self.assertRaises(ValueError):
                importer.main(self.review, self.answers, self.dir / f'{name}.jsonl', self.dir / f'{name}.json')
            self.assertEqual(list(self.dir.glob(f'{name}.jsonl*')), [])
        taken = self.dir / 'out.jsonl.criteria.json'
        taken.write_text('keep', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            importer.main(self.review, self.answers, self.dir / 'out.jsonl', self.criteria)
        self.assertFalse((self.dir / 'out.jsonl').exists())
        self.assertEqual(taken.read_text(encoding='utf-8'), 'keep')

    @unittest.skipUnless(shutil.which('node'), 'node unavailable: round trip UNVERIFIED')
    def test_round_trip_pressed_answer_imports_with_the_page_record(self):
        text = press(self.page.read_text(encoding='utf-8'), [dict(card=0, cell='upper_left'), dict(card=0, button='ok'), dict(card=1, button='alln')])
        (self.dir / 'pasted.txt').write_text(text, encoding='utf-8')
        importer.main(self.review, self.dir / 'pasted.txt', self.dir / 'out.jsonl', self.criteria)
        self.assertEqual(sorted(record(self.dir / 'out.jsonl')), sorted(f'{i}/back' for i in IDS))


if __name__ == '__main__':
    unittest.main()
