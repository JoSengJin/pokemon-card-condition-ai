import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools import zone_rows
from tools.d2_rows import backs
from tools.zone_rows import BOX, BOX_IN, BOX_OUT

# The runner side (T2) is a separate branch; its checks run only where both are present.
SIDECARS = None
if importlib.util.find_spec('card_condition.experiment_sidecars'):
    from card_condition import experiment_sidecars as SIDECARS


def runner_check(rows, exclusions):
    if SIDECARS:
        SIDECARS.check_exclusions(exclusions, rows)
        SIDECARS.check_facts(zone_rows.facts(rows, {}), {r['id'] for r in rows})

DATA = Path(os.environ.get('CARD_CONDITION_DATA_ROOT', Path(__file__).resolve().parents[1]))
ANSWERS = DATA / 'artifacts/d1-labels-20261103'
D2 = DATA / 'artifacts/experiments/20261103T131123-7fa5d398/observations.json'
LINE = 'a/back=확인;box:0.1,0.1,0.9,0.9;upper_left:정상;upper_right:결함;lower_left:미확인;lower_right:판단 불가'
UNBOXED = 'b/back=미확인;box:0.1,0.1,0.9,0.9;upper_left:결함;upper_right:미확인'


class ZoneRowsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'p.jpg').write_bytes(b'photo')
        self.info = {i: (str(self.root / 'p.jpg'), 'ax', None) for i in 'ab'}

    def build(self, need_ok=True, provenance=None):
        return zone_rows.build(zone_rows.parse(LINE + '\n' + UNBOXED), self.info, 'corner', need_ok, provenance)

    def test_undecidable_is_counted_not_a_row(self):
        rows, exclusions = self.build()
        self.assertEqual([r['target'] for r in rows], [0, 1])
        cell = exclusions['corner']
        self.assertEqual((cell['lower_right']['판단 불가'], cell['lower_left']['미확인']), (1, 1))
        self.assertEqual((cell['upper_left'][BOX]['결함'], cell['upper_right'][BOX]['미확인']), (1, 1))
        self.assertEqual(exclusions['kept_rule'], BOX_OUT)

    @unittest.skipUnless(SIDECARS, '미검증: 실행기 사이드카 모듈 없음')
    def test_outputs_pass_the_runner_checks_with_and_without_unconfirmed_boxes(self):
        for need_ok, count, rule in ((True, 2, BOX_OUT), (False, 3, BOX_IN)):
            rows, exclusions = self.build(need_ok)
            self.assertEqual((len(rows), exclusions['kept_rule']), (count, rule))
            runner_check(rows, exclusions)

    def test_unknown_state_is_refused_with_line_number(self):
        for bad in (LINE.replace('정상', '애매'), LINE + ';upper_left:결함', LINE.replace('=확인', '=애매'), LINE + ';x'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, '2번째 줄'):
                zone_rows.parse(UNBOXED + '\n' + bad)

    def test_provenance_removes_identical_and_only_marks_suspect(self):
        rows, exclusions = self.build(provenance=dict(verdict='ai_identical'))
        self.assertEqual((rows, sum(c['AI 동일'] for c in exclusions['corner'].values())), ([], 2))
        runner_check(rows, exclusions)
        rows, exclusions = self.build(provenance=dict(verdict='ai_suspect'))
        self.assertEqual((len(rows), sum(c['AI 의심'] for c in exclusions['corner'].values())), (2, 2))
        self.assertEqual({f['rater_kind'] for f in zone_rows.facts(rows, {}, dict(verdict='ai_suspect')).values()}, {'ai_suspect'})
        self.assertEqual({f['rater_kind'] for f in zone_rows.facts(rows, {}, dict(verdict='no_match_found')).values()}, {'unknown'})

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
class RealAnswersTest(unittest.TestCase):
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
