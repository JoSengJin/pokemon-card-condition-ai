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


class ZoneBase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'p.jpg').write_bytes(b'photo')
        self.info = {i: (str(self.root / 'p.jpg'), 'ax', None) for i in 'ab'}

    def build(self, need_ok=True, provenance=None):
        return zone_rows.build(zone_rows.parse(LINE + '\n' + UNBOXED), self.info, 'corner', need_ok, provenance)


class ZoneRowsTest(ZoneBase):
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


if __name__ == '__main__':
    unittest.main()
