import contextlib
import io
import json
import os
import unittest

from tests.test_zone_rows import ANSWERS, D2, DATA, LINE, ZoneBase, runner_check
from tools import zone_rows
from tools.d2_rows import backs
from tools.zone_rows import BOX, BOX_IN

class ZoneRowsTestMore(ZoneBase):
    def test_measure_layers(self):
        rows, _ = self.build()
        key = f"{rows[0]['id']}|{rows[0]['image_sha256']}|{','.join(f'{v:.6f}' for v in rows[0]['box'])}"
        for ppm, layer, hold in ((9.9, '<10', True), (10, '10-15.3', False), (15.3, '>=15.3', False)):
            fact = zone_rows.facts(rows, {key: dict(status='ok', ppm=ppm)})
            self.assertEqual((fact[rows[0]['id']]['px_per_mm_layer'], fact[rows[0]['id']]['input_hold']), (layer, hold))
            self.assertEqual(fact[rows[1]['id']]['background'], 'unmeasured')

    def test_write_new_never_overwrites_and_removes_partial_output(self):
        (self.root / 'row_facts.json').write_text('old')
        with self.assertRaises(FileExistsError):
            zone_rows.write_new(self.root, {'rows.json': [], 'row_facts.json': {}})
        self.assertEqual(((self.root / 'rows.json').exists(), (self.root / 'row_facts.json').read_text()), (False, 'old'))

    def test_provenance_of_another_file_is_refused(self):
        (self.root / 'answers.txt').write_text(LINE, encoding='utf-8')
        (self.root / 'prov.json').write_text(json.dumps(dict(verdict='unknown', answer_sha256='0' * 64)))
        with contextlib.redirect_stderr(io.StringIO()):
            code = zone_rows.main([str(self.root / 'answers.txt'), '--kind', 'corner', '--box', 'confirmed-only',
                                   '--out', str(self.root / 'out'), '--provenance', str(self.root / 'prov.json')])
        self.assertEqual((code, (self.root / 'out').exists()), (2, False))


@unittest.skipUnless(ANSWERS.is_dir() and D2.is_file(), '미검증: 실자료 없음')
class RealAnswersTest(ZoneBase):
    def run_file(self, name, kind, need_ok):
        before = os.getcwd()
        os.chdir(DATA)  # review files and photos are addressed relative to the data checkout
        try:
            answers = zone_rows.parse((ANSWERS / name).read_text(encoding='utf-8'))
            rows, exclusions = zone_rows.build(answers, backs(), kind, need_ok)
        finally:
            os.chdir(before)
        runner_check(rows, exclusions)
        cells = exclusions[kind].values()
        return rows, exclusions, {s: sum(c[s] for c in cells) for s in ('정상', '결함', '미확인')}, \
            {s: sum(c[BOX][s] for c in cells) for s in ('정상', '결함', '미확인')}

    def test_d1_corner_matches_d2_rows(self):
        rows, _, top, unboxed = self.run_file('cor-answers.txt', 'corner', True)
        self.assertEqual(len(rows), 508)
        recorded = json.loads(D2.read_text())['rows']
        self.assertEqual([(r['id'], r['target'], r['box']) for r in rows], [(r['id'], r['target'], r['box']) for r in recorded])
        self.assertEqual((top['미확인'], unboxed), (16, {'정상': 3, '결함': 5, '미확인': 20}))

    def test_edge_zone_keeps_unconfirmed_boxes(self):
        rows, exclusions, top, unboxed = self.run_file('edge-zone-answers.txt', 'edge', False)
        self.assertEqual((len(rows), sum(r['target'] for r in rows)), (942, 282))
        self.assertEqual((top['미확인'], unboxed, exclusions['kept_rule']), (2, {'정상': 14, '결함': 10, '미확인': 0}, BOX_IN))


if __name__ == '__main__':
    unittest.main()
