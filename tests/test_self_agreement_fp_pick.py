"""계약 V2-A(self-agreement-v2-plan-pick) 시험: schema 2 plan과 오탐 층 선정. 합성 fixture만 쓴다.

이 파일의 숫자·문장·시드는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
가짜 ID·가짜 경로 문자열만 쓰고 사진·라벨·artifacts는 열지 않는다.
"""
import ast
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.self_agreement import pick_zones, plan as cfg  # noqa: E402

TOOLS = ROOT / 'tools/self_agreement'
# 변경 전 커밋 d057e56의 도구로 같은 합성 입력(schema1_inputs)에서 뽑은 selection.json의 SHA-256.
BASELINE_SELECTION_SHA = 'f0543ac6d1ce859cc3a502f13f9e337502ce5955d798376244f3cb337275c361'
NEW_KEYS = ['layers', 'fp_layer_sha256', 'fp_count', 'fp_zones_per_card', 'card_rule', 'card_flip_cut']


def zone(zid, group, area, image):
    return dict(id=zid, group=group, area=area, image=image, box=[0, 0, 10, 10])


def population():
    return [zone('g%03d-z%d' % (c, z), 'g%03d' % c, 'a%d' % z, 'fake/g%03d.jpg' % c)
            for c in range(40) for z in range(3)]


def fp_card(c):
    return [zone('f%d-z%d' % (c, z), 'g%03d' % c, 'c%d' % z, 'fake/f%d.jpg' % c) for z in range(4)]


def error_rows():
    return [zone('e%d' % c, 'g%03d' % c, 'a0', 'fake/e%d.jpg' % c) for c in (2, 3)]


def schema1_inputs(d):
    """schema 1 plan과 입력을 d에 쓰고 (plan 경로, 인자 목록)을 돌려준다. 베이스라인 스크립트도 쓴다."""
    d = Path(d)
    files = {'pop.json': population(), 'ex.json': ['g000', 'g001', 'g002', 'g003'],
             'err.json': error_rows()}
    for name, data in files.items():
        (d / name).write_bytes(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    plan = dict(
        schema=1, approval_ref='합성 문서 경로@합성 커밋', cell='모서리', new_first_round=True,
        population_sha256=cfg.file_sha(d / 'pop.json'), exclude_sha256=cfg.file_sha(d / 'ex.json'),
        error_layer_sha256=cfg.file_sha(d / 'err.json'), main_count=7, error_count=2,
        strata=None, per_page=5, crop='highres', seed_selection=11, seed_order2=22,
        seed_bootstrap=33, bootstrap_draws=50, min_interval_hours=3, max_interval_hours=None,
        judge_statement='합성 확인 문장', p_min='0.2', direction_min_count=4,
        direction_alpha='0.1', reference_zone_count=None)
    (d / 'plan.json').write_bytes(json.dumps(plan, ensure_ascii=False).encode('utf-8'))
    return [str(d / 'plan.json'), str(d / 'pop.json'), str(d / 'ex.json'), str(d / 'err.json'),
            str(d / 'out.json')]


class Fx:
    """schema 2 합성 입력. fp=오탐 층 행(수정 가능), over=plan 덮어쓰기."""

    def __init__(self, test, fp=None, error=True, **over):
        self.dir = Path(tempfile.mkdtemp())
        test.addCleanup(self._clean)
        self.fp = fp if fp is not None else fp_card(0) + fp_card(1)
        self.error = error_rows() if error else []
        self.over = over
        self.write()

    def _clean(self):
        for p in self.dir.glob('*'):
            p.unlink()
        self.dir.rmdir()

    def put(self, name, data):
        path = self.dir / name
        path.write_bytes(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        return path

    def write(self):
        pop = self.put('pop.json', population())
        ex = self.put('ex.json', ['g000', 'g001', 'g002', 'g003'])
        self.err = self.put('err.json', self.error) if self.error else None
        self.fpp = self.put('fp.json', self.fp) if self.fp else None
        layers = ['main'] + (['error'] if self.error else []) + (['fp'] if self.fp else [])
        plan = dict(
            schema=2, approval_ref='합성 문서 경로@합성 커밋', cell='모서리', new_first_round=True,
            population_sha256=cfg.file_sha(pop), exclude_sha256=cfg.file_sha(ex),
            error_layer_sha256=self.err and cfg.file_sha(self.err), main_count=7,
            error_count=len(self.error), strata=None, per_page=5, crop='highres',
            seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=50,
            min_interval_hours=3, max_interval_hours=None, judge_statement='합성 확인 문장',
            p_min='0.2', direction_min_count=4, direction_alpha='0.1', reference_zone_count=None,
            layers=layers, fp_layer_sha256=self.fpp and cfg.file_sha(self.fpp),
            fp_count=len(self.fp), fp_zones_per_card=4 if self.fp else None,
            card_rule='any_defect_unknown_blocks' if self.fp else None, card_flip_cut=None)
        plan.update(self.over)
        self.plan = plan
        self.plan_path = self.put('plan.json', plan)
        self.out = self.dir / 'out.json'

    def args(self):
        return [str(self.plan_path), str(self.dir / 'pop.json'), str(self.dir / 'ex.json'),
                '-' if self.err is None else str(self.err),
                '-' if self.fpp is None else str(self.fpp), str(self.out)]


def run(args):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = pick_zones.main(args)
    return code, err.getvalue()


class Base(unittest.TestCase):
    def rejected(self, fx, args=None, fragment=None):
        code, err = run(args or fx.args())
        self.assertEqual(code, 2, err)
        self.assertFalse(fx.out.exists())
        self.assertEqual(len(err.strip().splitlines()), 1)
        if fragment:
            self.assertIn(fragment, err)

    def pick(self, fx):
        code, err = run(fx.args())
        self.assertEqual(code, 0, err)
        return json.loads(fx.out.read_text(encoding='utf-8'))


class Schema1UnchangedTest(Base):
    def test_selection_bytes_equal_pre_change_commit(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [p.unlink() for p in Path(d).glob('*')] and Path(d).rmdir())
        args = schema1_inputs(d)
        self.assertEqual(run(args)[0], 0)
        self.assertEqual(cfg.file_sha(args[-1]), BASELINE_SELECTION_SHA)

    def test_schema1_rejects_each_new_key_and_sixth_argument(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [p.unlink() for p in Path(d).glob('*')] and Path(d).rmdir())
        args = schema1_inputs(d)
        plan = json.loads(Path(args[0]).read_text(encoding='utf-8'))
        for key in NEW_KEYS:
            with self.assertRaises(ValueError, msg=key):
                cfg.check(dict(plan, **{key: None}))
        code, err = run(args[:4] + ['-', args[4]])
        self.assertEqual(code, 2)
        self.assertFalse(Path(args[4]).exists())


class Schema2PlanTest(Base):
    def good(self):
        return copy.deepcopy(Fx(self).plan)

    def bad(self, p, msg=None):
        with self.assertRaises(ValueError, msg=msg):
            cfg.check(p)

    def test_good_plans_pass_for_every_layer_set(self):
        cfg.check(self.good())
        for fp, error in ((False, False), (False, True), (True, False)):
            cfg.check(Fx(self, fp=None if fp else [], error=error).plan)
        cfg.check(dict(self.good(), card_flip_cut=3))

    def test_each_missing_key_rejected(self):
        for key in cfg.SPEC2:
            p = self.good()
            del p[key]
            self.bad(p, key)

    def test_unknown_key_rejected(self):
        self.bad(dict(self.good(), extra=1))

    def test_null_outside_table_rejected(self):
        null_ok = {'error_layer_sha256', 'strata', 'max_interval_hours', 'direction_min_count',
                   'direction_alpha', 'reference_zone_count', 'fp_layer_sha256',
                   'fp_zones_per_card', 'card_rule', 'card_flip_cut'}
        for key in cfg.SPEC2:
            if key not in null_ok:
                self.bad(dict(self.good(), **{key: None}), key)

    def test_schema_value_rejected(self):
        p = self.good()
        del p['schema']
        self.bad(p)
        for v in (None, 0, 3, True, False, '2', 2.0, [2]):
            self.bad(dict(self.good(), schema=v), repr(v))

    def test_schema2_value_two_needed_for_new_keys(self):
        p = self.good()
        for key in NEW_KEYS:
            del p[key]
        self.bad(p)  # schema 2인데 새 열쇠가 없음
        self.bad(dict(p, schema=1, layers=['main']))

    def test_layers_rejected(self):
        for v in ([], ['fp'], ['main', 'x'], ['main', 'main'], ['fp', 'main'], ['error', 'main'],
                  ['main', 'fp', 'error'], 'main', ('main',), None, True):
            self.bad(dict(self.good(), layers=v), repr(v))

    def test_fp_conditions_one_at_a_time(self):
        sha = 'a' * 64
        cases = [
            dict(layers=['main', 'error']),                  # fp 열쇠는 값인데 layers에 fp 없음
            dict(fp_layer_sha256=None),
            dict(fp_count=0),
            dict(fp_zones_per_card=None),
            dict(card_rule=None),
            dict(fp_count=7),                                # 4의 배수 아님
            dict(card_rule='other'),
            dict(fp_zones_per_card=0),
            dict(fp_layer_sha256='xyz'),
            dict(card_flip_cut=0),
            dict(card_flip_cut=True),
            dict(card_flip_cut='3'),
            dict(layers=['main', 'fp'], error_layer_sha256=sha),   # layers에 error 없음
            dict(error_layer_sha256=None, error_count=0),          # layers에 error 있음
        ]
        for over in cases:
            self.bad(dict(self.good(), **over), repr(over))

    def test_no_fp_layer_conditions(self):
        p = Fx(self, fp=[]).plan
        for over in (dict(card_flip_cut=3), dict(fp_count=4), dict(fp_layer_sha256='a' * 64),
                     dict(fp_zones_per_card=4), dict(card_rule='any_defect_unknown_blocks')):
            self.bad(dict(p, **over), repr(over))

    def test_load_returns_pair(self):
        fx = Fx(self)
        plan, sha = cfg.load(fx.plan_path)
        self.assertEqual((plan, sha), (fx.plan, cfg.file_sha(fx.plan_path)))


class FpSelectionTest(Base):
    def test_fp_rows_selected_with_tag_and_count(self):
        sel = self.pick(Fx(self))
        tags = [z['layer'] for z in sel['zones']]
        self.assertEqual((tags.count('main'), tags.count('error'), tags.count('fp')), (7, 2, 8))
        self.assertEqual([z['n'] for z in sel['zones']], list(range(1, 18)))
        self.assertEqual({z['id'] for z in sel['zones'] if z['layer'] == 'fp'},
                         {r['id'] for r in fp_card(0) + fp_card(1)})
        for z in sel['zones']:
            self.assertEqual(set(z), {'n', 'layer', 'id', 'group', 'area', 'image', 'box'})

    def test_main_ids_same_with_or_without_fp(self):
        with_fp = self.pick(Fx(self))
        without = self.pick(Fx(self, fp=[]))
        ids = lambda s: {z['id'] for z in s['zones'] if z['layer'] == 'main'}  # noqa: E731
        self.assertEqual(ids(with_fp), ids(without))

    def test_no_fp_matches_schema1_zones(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [p.unlink() for p in Path(d).glob('*')] and Path(d).rmdir())
        a1 = schema1_inputs(d)
        self.assertEqual(run(a1)[0], 0)
        s1 = json.loads(Path(a1[-1]).read_text(encoding='utf-8'))
        s2 = self.pick(Fx(self, fp=[]))
        self.assertEqual(s1['zones'], s2['zones'])

    def test_fp_layer_only_without_error_layer(self):
        sel = self.pick(Fx(self, error=False))
        self.assertEqual({z['layer'] for z in sel['zones']}, {'main', 'fp'})

    def test_hash_mismatch_rejected(self):
        fx = Fx(self)
        fx.fpp.write_bytes(fx.fpp.read_bytes() + b' ')
        self.rejected(fx, fragment='SHA-256')

    def test_fp_count_mismatch_rejected(self):
        fx = Fx(self, fp_count=12)
        self.rejected(fx, fragment='fp_count')

    def test_zones_per_card_mismatch_rejected(self):
        rows = fp_card(0) + [zone('f0-z4', 'g000', 'c4', 'fake/f0.jpg')] + fp_card(1)[:3]
        self.rejected(Fx(self, fp=rows), fragment='구역 수')  # 5장+3장, 합은 8
        self.rejected(Fx(self, fp_zones_per_card=2), fragment='구역 수')

    def test_duplicate_area_in_card_rejected(self):
        rows = fp_card(0) + fp_card(1)
        rows[1]['area'] = rows[0]['area']
        self.rejected(Fx(self, fp=rows), fragment='area')

    def test_two_photos_in_card_rejected(self):
        rows = fp_card(0) + fp_card(1)
        rows[1]['image'] = 'fake/f0-b.jpg'
        self.rejected(Fx(self, fp=rows), fragment='사진')

    def test_card_not_in_exclude_rejected(self):
        rows = fp_card(0) + fp_card(10)
        self.rejected(Fx(self, fp=rows), fragment='제외 목록')

    def test_same_card_as_error_layer_rejected(self):
        rows = fp_card(0) + fp_card(2)  # g002는 오류 층 카드
        self.rejected(Fx(self, fp=rows), fragment='같은 카드')

    def test_duplicate_id_across_layers_rejected(self):
        rows = fp_card(0) + fp_card(1)
        rows[0]['id'] = 'e2'  # 오류 층 id
        self.rejected(Fx(self, fp=rows), fragment='id 중복')
        rows = fp_card(0) + fp_card(1)
        rows[0]['id'] = 'g010-z0'  # 모집단 id(주 층 후보)
        fx = Fx(self, fp=rows, main_count=36)
        self.rejected(fx, fragment='id 중복')

    def test_duplicate_id_inside_fp_rejected(self):
        rows = fp_card(0) + fp_card(1)
        rows[1]['id'] = rows[0]['id']
        self.rejected(Fx(self, fp=rows), fragment='중복')

    def test_target_and_score_keys_rejected(self):
        for key in ('target', 'score'):
            rows = fp_card(0) + fp_card(1)
            rows[0][key] = 1
            self.rejected(Fx(self, fp=rows), fragment='열쇠')

    def test_argument_count_and_dash_must_match_plan(self):
        fx = Fx(self)
        self.rejected(fx, args=fx.args()[:4] + [str(fx.out)], fragment='schema')
        args = fx.args()
        args[4] = '-'
        self.rejected(fx, args=args, fragment='FP_LAYER')
        none = Fx(self, fp=[])
        args = none.args()
        args[4] = str(fx.fpp)
        self.rejected(none, args=args, fragment='FP_LAYER')

    def test_out_exists_untouched(self):
        fx = Fx(self)
        fx.out.write_bytes(b'keep')
        code, _ = run(fx.args())
        self.assertEqual(code, 2)
        self.assertEqual(fx.out.read_bytes(), b'keep')


class SourceTest(unittest.TestCase):
    def count(self, path):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        return sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                   for n in ast.walk(tree))

    def test_function_counts(self):
        self.assertEqual(self.count(TOOLS / 'plan.py'), 4)
        self.assertEqual(self.count(TOOLS / 'pick_zones.py'), 5)

    def test_no_built_in_values(self):
        for name in ('plan.py', 'pick_zones.py'):
            text = (TOOLS / name).read_text(encoding='utf-8')
            for needle in ('default=', 'plan.get(', 'argparse'):
                self.assertNotIn(needle, text, '%s: %s' % (name, needle))


if __name__ == '__main__':
    unittest.main()
