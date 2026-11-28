"""Corner answer import keeps 판단 불가 apart from 미확인 without touching the 0/1 label format (accuracy-expert-chain 01 G1, 07 X4)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from card_condition.data import LABELS
from tools import label_criteria, mobile_corner_label_import as importer

AREAS = importer.AREAS
BOX = '0.1000,0.1000,0.9000,0.9000'


def line(rid, states):
    return f'{rid}/back=확인;box:{BOX};' + ';'.join(f'{a}:{s}' for a, s in zip(AREAS, states))


class CornerImportStatesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        image = str(self.dir / 'a.png')
        Image.new('RGB', (40, 60), (128, 128, 128)).save(image)
        rows = [dict(id=i, title='t', back=image, side_annotations=dict(back=dict(image=image, box=[.1, .1, .9, .9], labels=dict.fromkeys(LABELS)))) for i in ('a', 'b')]
        self.review = self.dir / 'rows.jsonl'
        self.review.write_text('\n'.join(map(json.dumps, rows)), encoding='utf-8')

    def run_import(self, text, name='out.jsonl'):
        (self.dir / 'answers.txt').write_text(text, encoding='utf-8')
        importer.main(self.review, self.dir / 'answers.txt', self.dir / name)
        return {r['id']: r['side_annotations']['back'] for r in map(json.loads, (self.dir / name).read_text(encoding='utf-8').splitlines())}

    def test_undecidable_is_not_stored_as_a_label_but_is_recorded_apart_from_unchecked(self):
        stored = self.run_import(line('a', ('정상', '판단 불가', '미확인', '결함')) + '\n' + line('b', ('정상', '정상', '정상', '판단 불가')))
        a, b = stored['a'], stored['b']
        self.assertEqual({k: v['corner_defect'] for k, v in a['region_labels'].items()}, dict(upper_left=0, lower_right=1))
        self.assertEqual(a['labels']['corner_defect'], 1)
        self.assertEqual(set(b['region_labels']), {'upper_left', 'upper_right', 'lower_left'})
        self.assertIsNone(b['labels']['corner_defect'])  # three normal + one undecidable is not "all normal"
        states = json.loads((self.dir / 'out.jsonl.states.json').read_text(encoding='utf-8'))
        self.assertEqual(states['counts'], {'정상': 4, '결함': 1, '판단 불가': 2, '미확인': 1})
        self.assertEqual(states['states'], {'a/back/upper_right': '판단 불가', 'a/back/lower_left': '미확인', 'b/back/lower_right': '판단 불가'})

    def test_unknown_state_or_taken_states_file_refuses_before_any_output(self):
        (self.dir / 'answers.txt').write_text(line('a', ('정상', '불가', '정상', '정상')), encoding='utf-8')
        with self.assertRaises(ValueError):
            importer.main(self.review, self.dir / 'answers.txt', self.dir / 'bad.jsonl')
        self.assertEqual(list(self.dir.glob('bad.jsonl*')), [])
        (self.dir / 'answers.txt').write_text(line('a', ('정상',) * 4), encoding='utf-8')
        (self.dir / 'taken.jsonl.states.json').write_text('keep', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            importer.main(self.review, self.dir / 'answers.txt', self.dir / 'taken.jsonl')
        self.assertFalse((self.dir / 'taken.jsonl').exists())
        self.assertEqual((self.dir / 'taken.jsonl.states.json').read_text(encoding='utf-8'), 'keep')

    def test_failed_states_write_leaves_no_labels_or_provenance_so_a_retry_works(self):
        (self.dir / 'answers.txt').write_text(line('a', ('정상', '판단 불가', '결함', '결함')), encoding='utf-8')
        record = self.dir / 'p.html.criteria.json'
        label_criteria.write_page(self.dir / 'p.html', 'page', 'rules', '<article data-id="a/back" x><img src="data:image/jpeg;base64,QUJD"></article>')
        with mock.patch.object(importer, 'write_states', side_effect=OSError):
            with self.assertRaises(OSError):
                importer.main(self.review, self.dir / 'answers.txt', self.dir / 'f.jsonl', record)
        self.assertEqual(list(self.dir.glob('f.jsonl*')), [])
        importer.main(self.review, self.dir / 'answers.txt', self.dir / 'f.jsonl', record)
        self.assertEqual(len(list(self.dir.glob('f.jsonl*'))), 3)

    def test_page_screen_conditions_reach_the_label_provenance(self):
        body = '<article data-id="a/back" x><img src="data:image/jpeg;base64,QUJD"></article>'
        screen = dict(display_px_per_mm={'a/back': 15.5})
        label_criteria.write_page(self.dir / 'p.html', 'page', 'rules', body, screen)
        record = json.loads((self.dir / 'p.html.criteria.json').read_text(encoding='utf-8'))
        self.assertEqual(record['screen'], screen)
        (self.dir / 'answers.txt').write_text(line('a', ('정상',) * 4), encoding='utf-8')
        importer.main(self.review, self.dir / 'answers.txt', self.dir / 'with.jsonl', self.dir / 'p.html.criteria.json')
        provenance = json.loads((self.dir / 'with.jsonl.criteria.json').read_text(encoding='utf-8'))
        self.assertEqual(provenance['a/back']['display_px_per_mm'], 15.5)
        label_criteria.write_page(self.dir / 'q.html', 'page', 'rules', body)  # a page without screen conditions: unchanged record and provenance
        importer.main(self.review, self.dir / 'answers.txt', self.dir / 'plain.jsonl', self.dir / 'q.html.criteria.json')
        self.assertNotIn('screen', json.loads((self.dir / 'q.html.criteria.json').read_text(encoding='utf-8')))
        self.assertEqual(set(json.loads((self.dir / 'plain.jsonl.criteria.json').read_text(encoding='utf-8'))['a/back']), {'criteria_sha256', 'crop_sha256'})


if __name__ == '__main__':
    unittest.main()
