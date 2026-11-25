"""계약 A(self-agreement-plan-pick) 시험. 합성 fixture만 쓴다.

이 파일의 숫자·문장·시드는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
가짜 ID·가짜 경로 문자열만 쓰고 사진·라벨·artifacts는 열지 않는다.
"""
import contextlib
import io
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.self_agreement import pick_zones, plan as cfg  # noqa: E402

PLAN_PATH = ROOT / 'tools/self_agreement/plan.py'
PICK_PATH = ROOT / 'tools/self_agreement/pick_zones.py'


def make_rows(cards=40, per_card=3):
    """합성 모집단: 카드 g000.., 카드마다 구역 per_card개."""
    return [dict(id='g%03d-z%d' % (c, z), group='g%03d' % c, area='a%d' % z,
                 image='fake/g%03d.jpg' % c, box=[0, 0, 10, 10])
            for c in range(cards) for z in range(per_card)]


class Fixture:
    """임시 폴더에 합성 입력과 plan.json을 만든다."""

    def __init__(self, test, pop=None, exclude=None, error=None, **over):
        self.dir = Path(tempfile.mkdtemp())
        test.addCleanup(self._clean)
        self.pop = make_rows() if pop is None else pop
        self.exclude = ['g000', 'g001', 'g002'] if exclude is None else exclude
        self.error = error
        self.over = over
        self.out = self.dir / 'selection.json'
        self.write_all()

    def _clean(self):
        for p in self.dir.glob('*'):
            p.unlink()
        self.dir.rmdir()

    def put(self, name, data):
        path = self.dir / name
        path.write_bytes(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        return path

    def write_all(self):
        self.pop_path = self.put('pop.json', self.pop)
        self.ex_path = self.put('ex.json', self.exclude)
        self.err_path = None if self.error is None else self.put('err.json', self.error)
        plan = dict(
            schema=1, approval_ref='합성 문서 경로@합성 커밋', cell='모서리', new_first_round=True,
            population_sha256=cfg.file_sha(self.pop_path), exclude_sha256=cfg.file_sha(self.ex_path),
            error_layer_sha256=None if self.err_path is None else cfg.file_sha(self.err_path),
            main_count=7, error_count=0 if self.error is None else len(self.error),
            strata=None, per_page=5, crop='highres',
            seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=50,
            min_interval_hours=3, max_interval_hours=None, judge_statement='합성 확인 문장',
            p_min='0.2', direction_min_count=4, direction_alpha='0.1', reference_zone_count=None)
        plan.update(self.over)
        self.plan = plan
        self.plan_path = self.put('plan.json', plan)

    def args(self, out=None):
        err = '-' if self.err_path is None else str(self.err_path)
        return [str(self.plan_path), str(self.pop_path), str(self.ex_path), err,
                str(out or self.out)]


def run(args):
    """main을 직접 불러 (종료 코드, stderr)를 돌려준다."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = pick_zones.main(args)
    return code, err.getvalue()


class SelectionTest(unittest.TestCase):
    def pick(self, fx, name='selection.json'):
        out = fx.dir / name
        self.assertEqual(run(fx.args(out))[0], 0)
        return json.loads(out.read_text(encoding='utf-8'))

    def test_same_seed_same_list_and_bytes(self):
        fx = Fixture(self)
        a, b = fx.dir / 'a.json', fx.dir / 'b.json'
        self.assertEqual(run(fx.args(a))[0], 0)
        self.assertEqual(run(fx.args(b))[0], 0)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        sel = json.loads(a.read_text(encoding='utf-8'))
        self.assertEqual(sel['plan_sha256'], cfg.file_sha(fx.plan_path))
        self.assertEqual([z['n'] for z in sel['zones']], list(range(1, 8)))

    def test_input_order_does_not_matter(self):
        fx = Fixture(self)
        base = self.pick(fx, 'a.json')
        shuffled = make_rows()
        random.Random(5).shuffle(shuffled)
        fx2 = Fixture(self, pop=shuffled)
        # 모집단 해시가 달라 plan이 다르므로 plan_sha256만 빼고 같은 목록이어야 한다
        other = self.pick(fx2)
        self.assertEqual(base['zones'], other['zones'])

    def test_different_seed_different_list(self):
        a = self.pick(Fixture(self))
        b = self.pick(Fixture(self, seed_selection=12))
        self.assertNotEqual(a['zones'], b['zones'])

    def test_no_excluded_card_and_one_zone_per_card(self):
        sel = self.pick(Fixture(self, exclude=['g000', 'g001', 'g002', 'g003']))
        groups = [z['group'] for z in sel['zones']]
        self.assertEqual(len(groups), len(set(groups)))
        self.assertFalse({'g000', 'g001', 'g002', 'g003'} & set(groups))
        self.assertEqual({z['layer'] for z in sel['zones']}, {'main'})

    def test_error_layer_included_and_ordered(self):
        err = [dict(id='e%d' % i, group='g00%d' % i, area='a0', image='fake/e%d.jpg' % i,
                    box=[1, 2, 3, 4]) for i in range(3)]
        sel = self.pick(Fixture(self, error=err))
        self.assertEqual(len(sel['zones']), 10)
        self.assertEqual({z['id'] for z in sel['zones'] if z['layer'] == 'error'}, {'e0', 'e1', 'e2'})
        for z in sel['zones']:
            self.assertEqual(set(z), {'n', 'layer', 'id', 'group', 'area', 'image', 'box'})

    def test_error_count_takes_first_rows_in_file_order(self):
        err = [dict(id='e%d' % i, group='g00%d' % i, area='a0', image='fake/e%d.jpg' % i,
                    box=[1, 2, 3, 4]) for i in range(3)]
        sel = self.pick(Fixture(self, error=err, error_count=2))
        self.assertEqual({z['id'] for z in sel['zones'] if z['layer'] == 'error'}, {'e0', 'e1'})

    def test_same_image_same_group_allowed(self):
        rows = make_rows()
        rows[4]['image'] = rows[3]['image']  # 같은 카드의 두 구역이 같은 사진
        self.pick(Fixture(self, pop=rows))

    def assert_rejected(self, fx, fragment=None):
        code, err = run(fx.args())
        self.assertEqual(code, 2)
        self.assertFalse(fx.out.exists())
        self.assertEqual(len(err.strip().splitlines()), 1)
        if fragment:
            self.assertIn(fragment, err)

    def test_population_byte_change_rejected(self):
        fx = Fixture(self)
        fx.pop_path.write_bytes(fx.pop_path.read_bytes() + b' ')
        self.assert_rejected(fx, 'SHA-256')

    def test_exclude_byte_change_rejected(self):
        fx = Fixture(self)
        fx.ex_path.write_bytes(fx.ex_path.read_bytes() + b' ')
        self.assert_rejected(fx, 'SHA-256')

    def test_target_and_score_keys_rejected(self):
        for key in ('target', 'score'):
            rows = make_rows()
            rows[0][key] = 1
            self.assert_rejected(Fixture(self, pop=rows), '열쇠')

    def test_missing_row_key_rejected(self):
        rows = make_rows()
        del rows[0]['box']
        self.assert_rejected(Fixture(self, pop=rows), '열쇠')

    def test_error_layer_card_not_in_exclude_rejected(self):
        err = [dict(id='e0', group='g010', area='a0', image='fake/e0.jpg', box=[1, 2, 3, 4])]
        self.assert_rejected(Fixture(self, error=err), '제외 목록')

    def test_too_few_cards_rejected(self):
        self.assert_rejected(Fixture(self, pop=make_rows(cards=8)), '적음')

    def test_too_few_error_rows_rejected(self):
        err = [dict(id='e0', group='g000', area='a0', image='fake/e0.jpg', box=[1, 2, 3, 4])]
        self.assert_rejected(Fixture(self, error=err, error_count=2), '적음')

    def test_same_image_different_group_rejected(self):
        rows = make_rows()
        rows[10]['image'] = rows[0]['image']
        self.assert_rejected(Fixture(self, pop=rows), '다른 group')

    def test_same_image_across_error_and_main_rejected(self):
        # 오류 층 사진이 뽑힌 주 층 카드의 사진과 같은 경로(다른 카드)
        rows = make_rows()
        err = [dict(id='e0', group='g000', area='a0', image=rows[20]['image'], box=[1, 2, 3, 4])]
        fx = Fixture(self, pop=rows, error=err, main_count=40 - 3)
        self.assert_rejected(fx, '다른 group')

    def test_duplicate_id_rejected(self):
        rows = make_rows()
        rows[1]['id'] = rows[0]['id']
        self.assert_rejected(Fixture(self, pop=rows), '중복')

    def test_error_layer_argument_must_match_plan(self):
        fx = Fixture(self)
        args = fx.args()
        args[3] = str(fx.ex_path)
        code, _ = run(args)
        self.assertEqual(code, 2)
        self.assertFalse(fx.out.exists())

    def test_existing_out_rejected_and_untouched(self):
        fx = Fixture(self)
        fx.out.write_bytes(b'keep')
        self.assert_rejected_existing(fx)

    def assert_rejected_existing(self, fx):
        code, err = run(fx.args())
        self.assertEqual(code, 2)
        self.assertEqual(fx.out.read_bytes(), b'keep')
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_bad_argument_count_rejected(self):
        self.assertEqual(run(['x'])[0], 2)

    def test_command_line_exit_codes(self):
        fx = Fixture(self)
        cmd = [sys.executable, '-m', 'tools.self_agreement.pick_zones']
        ok = subprocess.run(cmd + fx.args(), cwd=ROOT, capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stderr), (0, ''))
        again = subprocess.run(cmd + fx.args(), cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(again.returncode, 2)
        self.assertEqual(len(again.stderr.strip().splitlines()), 1)


class PlanTest(unittest.TestCase):
    def good(self):
        return Fixture(self).plan

    def test_good_plan_passes_and_nulls_allowed_where_listed(self):
        p = self.good()
        cfg.check(p)
        p.update(max_interval_hours=None, direction_min_count=None, direction_alpha=None,
                 reference_zone_count=None)
        cfg.check(p)
        p.update(error_layer_sha256=None, error_count=0)
        cfg.check(p)

    def test_each_missing_key_rejected(self):
        for key in cfg.SPEC:
            p = self.good()
            del p[key]
            with self.assertRaises(ValueError, msg=key):
                cfg.check(p)

    def test_unknown_key_rejected(self):
        p = self.good()
        p['extra'] = 1
        with self.assertRaises(ValueError):
            cfg.check(p)

    def test_null_outside_allowed_table_rejected(self):
        null_ok = {'error_layer_sha256', 'strata', 'max_interval_hours', 'direction_min_count',
                   'direction_alpha', 'reference_zone_count'}
        for key in cfg.SPEC:
            if key in null_ok:
                continue
            p = self.good()
            p[key] = None
            with self.assertRaises(ValueError, msg=key):
                cfg.check(p)

    def test_bad_values_rejected(self):
        bad = dict(schema=2, approval_ref='  ', cell='표면', new_first_round=False,
                   population_sha256='abc', main_count=0, error_count=-1, strata={'a': 1},
                   per_page=0, crop='full', seed_selection=True, bootstrap_draws=0,
                   min_interval_hours=-1, judge_statement='', p_min='0', direction_min_count=0,
                   direction_alpha='1', reference_zone_count=0)
        for key, value in bad.items():
            p = self.good()
            p[key] = value
            with self.assertRaises(ValueError, msg=key):
                cfg.check(p)
        for value in ('0.5', '0.7', 0.2, '1e-1', '-0.1', 'nan'):
            p = self.good()
            p['p_min'] = value
            with self.assertRaises(ValueError, msg=repr(value)):
                cfg.check(p)

    def test_equal_seeds_rejected(self):
        for a, b in (('seed_selection', 'seed_order2'), ('seed_selection', 'seed_bootstrap'),
                     ('seed_order2', 'seed_bootstrap')):
            p = self.good()
            p[a] = p[b]
            with self.assertRaises(ValueError, msg=(a, b)):
                cfg.check(p)

    def test_paired_nulls_enforced(self):
        p = self.good()
        p['direction_alpha'] = None
        with self.assertRaises(ValueError):
            cfg.check(p)
        p = self.good()
        p['error_layer_sha256'] = None  # error_count는 0이 아님
        p['error_count'] = 2
        with self.assertRaises(ValueError):
            cfg.check(p)

    def test_max_interval_below_min_rejected(self):
        p = self.good()
        p['max_interval_hours'] = p['min_interval_hours'] - 1
        with self.assertRaises(ValueError):
            cfg.check(p)

    def test_load_returns_file_sha_and_rejects_non_object(self):
        fx = Fixture(self)
        plan, sha = cfg.load(fx.plan_path)
        self.assertEqual((plan, sha), (fx.plan, cfg.file_sha(fx.plan_path)))
        fx.plan_path.write_text('[]', encoding='utf-8')
        with self.assertRaises(ValueError):
            cfg.load(fx.plan_path)

    def test_write_new_refuses_overwrite(self):
        fx = Fixture(self)
        with self.assertRaises(FileExistsError):
            cfg.write_new(fx.plan_path, {})

    def test_plan_json_bad_in_main_writes_nothing(self):
        fx = Fixture(self)
        fx.plan['extra'] = 1
        fx.plan_path.write_text(json.dumps(fx.plan), encoding='utf-8')
        code, _ = run(fx.args())
        self.assertEqual(code, 2)
        self.assertFalse(fx.out.exists())


class NoBuiltInValuesTest(unittest.TestCase):
    def test_source_has_no_argparse_default_or_plan_get(self):
        for path in (PLAN_PATH, PICK_PATH):
            text = path.read_text(encoding='utf-8')
            for needle in ('default=', 'plan.get(', 'argparse'):
                self.assertNotIn(needle, text, '%s: %s' % (path.name, needle))


if __name__ == '__main__':
    unittest.main()
