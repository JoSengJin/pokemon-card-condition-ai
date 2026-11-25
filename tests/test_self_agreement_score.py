"""계약 D(self-agreement-score) 시험. 합성 입력만 쓴다.

이 파일의 숫자·문장·시각·시드는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
가짜 해시·가짜 ID만 쓰고 사진·라벨·artifacts는 열지 않는다.
"""
import ast
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.self_agreement import decide, plan as cfg, score_rounds, stats  # noqa: E402

SRC = {n: ROOT / ('tools/self_agreement/%s.py' % n) for n in ('stats', 'decide', 'score_rounds')}
PSHA, SSHA = 'a' * 64, 'b' * 64
T1, T2 = '2026-03-01T10:00:00+09:00', '2026-03-15T10:00:00+09:00'
NN, DD = ('정상', '정상'), ('결함', '결함')
B, C = ('정상', '결함'), ('결함', '정상')  # b=1차 정상→2차 결함, c=1차 결함→2차 정상

# 합성 plan. 값은 시험용이며 제안값이 아니다.
PLAN = dict(schema=1, approval_ref='synthetic', cell='모서리', new_first_round=True,
            population_sha256='c' * 64, exclude_sha256='d' * 64, error_layer_sha256=None,
            main_count=30, error_count=0, strata=None, per_page=10, crop='highres',
            seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=200,
            min_interval_hours=10, max_interval_hours=None, judge_statement='합성 문장',
            p_min='0.1', direction_min_count=6, direction_alpha='0.05', reference_zone_count=100)


def plan_with(**kw):
    return {**PLAN, **kw}


def pairs_of(nn, dd, b, c):
    return [NN] * nn + [DD] * dd + [B] * b + [C] * c


def rounds(main, err=(), **over):
    """합성 selection과 두 회차 기록. over['first'/'second']는 회차 기록 덮어쓰기."""
    allp = [('main', p) for p in main] + [('error', p) for p in err]
    zones = [dict(n=i + 1, layer=l, id='x%d' % i, group='g%d' % i, area='a', image='i%d' % i, box=[0, 0, 1, 1])
             for i, (l, _) in enumerate(allp)]
    sel = {'plan_sha256': PSHA, 'zones': zones}

    def rd(k, t, idx):
        return dict(plan_sha256=PSHA, selection_sha256=SSHA, round=k, judge_confirmed=True, statement='합성',
                    submitted={'p%d' % k: t}, criteria_sha256='e' * 64, screen_sha256='f' * 64,
                    crops={'1': '1' * 64}, answers={str(i + 1): p[idx] for i, (_, p) in enumerate(allp)}, raw=[])
    first, second = rd(1, T1, 0), rd(2, T2, 1)
    first.update(over.get('first', {}))
    second.update(over.get('second', {}))
    return sel, first, second


def run(main, plan=PLAN, err=(), **over):
    sel, first, second = rounds(main, err, **over)
    return score_rounds.report(plan, (PSHA, SSHA), sel, first, second)


def tables30():
    return [(a, b, c, 30 - a - b - c) for a in range(31) for b in range(31 - a)
            for c in range(31 - a - b)]


class HandCalculation(unittest.TestCase):
    """설계 3.2 표. 기대값은 설계 문서의 손계산 값이다."""
    CASES = [  # (표 nn/dd/b/c, 카파, d 윌슨, e·구간 또는 None, 정확 양측 p)
        ((14, 13, 2, 1), Fraction(4, 5), (.0346, .2562), (.0528, .0176, .1509), 1),
        ((14, 13, 1, 2), Fraction(4, 5), (.0346, .2562), (.0528, .0176, .1509), 1),
        ((14, 13, 3, 0), Fraction(182, 227), (.0346, .2562), (.0528, .0176, .1509), .25),
        ((14, 13, 0, 3), Fraction(182, 227), (.0346, .2562), (.0528, .0176, .1509), .25),
        ((26, 1, 2, 1), Fraction(8, 23), (.0346, .2562), (.0528, .0176, .1509), 1),
        ((26, 1, 1, 2), Fraction(8, 23), (.0346, .2562), (.0528, .0176, .1509), 1),
        ((26, 1, 3, 0), Fraction(26, 71), (.0346, .2562), (.0528, .0176, .1509), .25),
        ((12, 12, 3, 3), Fraction(3, 5), (.0950, .3731), (.1127, .0500, .2481), 1),
        ((13, 11, 6, 0), Fraction(143, 233), (.0950, .3731), (.1127, .0500, .2481), .03125),
        ((13, 12, 5, 0), Fraction(52, 77), (.0734, .3356), (.0918, .0381, .2133), .0625),
        ((15, 15, 0, 0), Fraction(1), (0, .1135), (0, 0, .0604), 1),
        ((8, 7, 8, 7), Fraction(0), (.3315, .6685), None, 1),
        ((30, 0, 0, 0), None, None, None, 1),
    ]

    def test_hand_table(self):
        for t, kappa, dw, e, p in self.CASES:
            with self.subTest(t=t):
                m = score_rounds.measures(pairs_of(*t), PLAN)
                self.assertEqual(m['table'], t)
                self.assertEqual(m['counts']['confirmed_pairs'], 30)
                self.assertEqual(m['kappa'], kappa)  # 정확한 분수. 근삿값 비교 아님
                self.assertEqual(m['p'], p)
                er = m['error']
                if dw:
                    for got, want in zip(er['d_wilson'], dw):
                        self.assertAlmostEqual(got, want, places=4)
                if e:
                    self.assertFalse(er['upper_clipped'])
                    for got, want in zip([er['e']] + er['e_interval'], e):
                        self.assertAlmostEqual(got, want, places=4)
                elif dw:
                    self.assertIsNone(er['e'])  # d=0.5
                    self.assertIsNone(er['e_interval'])

    def test_agreement_rate_values(self):
        self.assertAlmostEqual(stats.error_rate(3, 30)['d'], .1)
        self.assertEqual(Fraction(27, 30), Fraction(9, 10))

    def test_float_boundary_regression(self):
        """설계 3.2 회귀 입력 2종 원문 그대로: 소수 식은 경계에서 어긋난다."""
        for t, exact, row, plan in (((10, 20, 1, 2), Fraction(4, 5), 6, PLAN),
                                    ((4, 27, 1, 3), Fraction(3, 5), 5, plan_with(p_min='0.01'))):
            with self.subTest(t=t):
                nn, dd, b, c = t
                n = sum(t)
                pa, p1, p2 = (nn + dd) / n, (dd + c) / n, (dd + b) / n
                pe = p1 * p2 + (1 - p1) * (1 - p2)
                self.assertNotEqual((pa - pe) / (1 - pe), float(exact))  # 소수 비교는 틀린다
                m = score_rounds.measures(pairs_of(*t), plan)
                self.assertEqual(m['kappa'], exact)
                self.assertEqual(decide.row([], m['table'], m['kappa'], plan, m['p'])[0], row)

    def test_exact_upper_differs_from_wilson(self):
        er = stats.error_rate(0, 30)
        self.assertAlmostEqual(er['exact_upper'], 1 - 0.025 ** (1 / 30))
        self.assertAlmostEqual(er['exact_upper'], .1157, places=4)
        self.assertAlmostEqual(er['d_wilson'][1], .1135, places=4)
        self.assertNotAlmostEqual(er['exact_upper'], er['d_wilson'][1], places=3)
        self.assertIsNone(stats.error_rate(1, 30)['exact_upper'])


class NextAction(unittest.TestCase):
    """설계 3.3 표: 각 입력은 정확히 한 행으로 간다."""

    def row(self, t, plan=PLAN, **over):
        return run(pairs_of(*t), plan, **over)

    def test_table_rows(self):
        cases = [((13, 11, 6, 0), PLAN, 3), ((13, 12, 5, 0), PLAN, 5),
                 ((13, 11, 6, 0), plan_with(direction_min_count=None, direction_alpha=None), 5),
                 ((12, 11, 4, 3), PLAN, 4), ((8, 7, 8, 7), PLAN, 4), ((12, 12, 3, 3), PLAN, 5),
                 ((4, 27, 1, 3), plan_with(p_min='0.01'), 5), ((13, 13, 2, 2), PLAN, 5),
                 ((14, 13, 2, 1), PLAN, 6), ((10, 20, 1, 2), PLAN, 6), ((15, 15, 0, 0), PLAN, 6),
                 ((14, 14, 0, 1), PLAN, 2), ((30, 0, 0, 0), PLAN, 2), ((0, 30, 0, 0), PLAN, 2),
                 ((26, 1, 2, 1), PLAN, 2), ((14, 13, 2, 1), PLAN, 6)]
        for t, plan, want in cases:
            with self.subTest(t=t, want=want):
                res = self.row(t, plan)
                self.assertEqual(res['row'], want)
                self.assertEqual(sum(1 for r in range(1, 7) if r == res['row']), 1)

    def test_row2_edges(self):
        self.assertEqual(self.row((14, 14, 0, 1))['row'], 2)  # 카파 0.931이어도 29쌍
        self.assertNotEqual(self.row((14, 13, 2, 1))['row'], 2)  # 30쌍
        # 결함 비율이 정확히 p_min(3/30)이면 쏠림 아님: 미만만
        self.assertIsNone(decide.skewed((27, 3, 0, 0), '0.1'))  # 결함 3/30 = 0.1 = p_min
        self.assertIsNotNone(decide.skewed((28, 2, 0, 0), '0.1'))  # 2/30 < 0.1
        self.assertIsNone(decide.skewed((3, 27, 0, 0), '0.1'))  # 27/30 = 1-p_min, 초과 아님
        self.assertIsNotNone(decide.skewed((2, 28, 0, 0), '0.1'))

    def test_row3_has_no_e(self):
        res = self.row((13, 11, 6, 0))
        self.assertEqual(res['row'], 3)
        self.assertIsNone(res['e'])
        self.assertIsNone(res['e_interval'])
        self.assertEqual(res['b'], 6)
        self.assertEqual(res['c'], 0)
        self.assertEqual(res['exact_two_sided_p'], .03125)

    def test_row5_notes_direction_not_applied(self):
        res = self.row((13, 11, 6, 0), plan_with(direction_min_count=None, direction_alpha=None))
        self.assertEqual(res['row'], 5)
        self.assertIn('3행 미적용', res['reasons'])
        self.assertNotIn('3행 미적용', self.row((13, 12, 5, 0))['reasons'])

    def test_no_pairs_ratio_not_applicable(self):
        res = self.row((15, 15, 0, 0))
        self.assertEqual(res['row'], 6)
        self.assertEqual(res['b_ratio'], '해당 없음')

    def test_row1_conditions(self):
        good = (14, 13, 2, 1)
        for name, over in (('주체 거짓', dict(first=dict(judge_confirmed=False))),
                           ('주체 없음', dict(second={'judge_confirmed': None})),
                           ('기준 해시', dict(second=dict(criteria_sha256='0' * 64))),
                           ('화면 해시', dict(second=dict(screen_sha256='0' * 64))),
                           ('크롭 해시', dict(second=dict(crops={'1': '9' * 64})))):
            with self.subTest(name):
                res = self.row(good, **over)
                self.assertEqual(res['row'], 1)
                self.assertTrue(res['reasons'])
                self.assertIsNone(res['kappa'])
                self.assertIsNone(res['e'])
        miss = rounds(pairs_of(*good))
        del miss[2]['judge_confirmed']  # 열쇠 자체가 없음
        self.assertEqual(score_rounds.report(PLAN, (PSHA, SSHA), *miss)['row'], 1)

    def test_row1_beats_row2(self):
        self.assertEqual(self.row((14, 14, 0, 1), first=dict(judge_confirmed=False))['row'], 1)

    def test_interval_bounds(self):
        # 하한 = 2차 가장 이른 − 1차 가장 늦은 ≥ 10시간. 상한 = 2차 가장 늦은 − 1차 가장 이른.
        t = (14, 13, 2, 1)
        first = dict(submitted={'a': '2026-03-01T10:00:00+09:00', 'b': '2026-03-01T11:00:00+09:00'})

        def row(second_times, plan=PLAN):
            return self.row(t, plan, first=first, second=dict(submitted=second_times))['row']
        exact = {'c': '2026-03-01T21:00:00+09:00', 'd': '2026-03-01T23:00:00+09:00'}  # 21-11 = 10시간
        short = {'c': '2026-03-01T20:59:59+09:00', 'd': '2026-03-01T23:00:00+09:00'}
        self.assertNotEqual(row(exact), 1)
        self.assertEqual(row(short), 1)
        self.assertEqual(row({'c': '2026-03-01T10:30:00+09:00'}), 1)  # 기기 시계로 2차가 더 이름
        self.assertNotEqual(row(exact, plan_with(max_interval_hours=13)), 1)  # 상한 = 23-10 = 13시간, 경계 허용
        self.assertEqual(row(exact, plan_with(max_interval_hours=12.9)), 1)
        # 시간대가 다른 표기도 같은 순간으로 계산
        utc = {'c': '2026-03-01T12:00:00+00:00'}  # 21:00 KST
        self.assertNotEqual(row(utc), 1)

    def test_hash_mismatch_is_row1_in_decide(self):
        sel, first, second = rounds(pairs_of(14, 13, 2, 1))
        for who, key in ((first, 'plan_sha256'), (second, 'selection_sha256')):
            bad = dict(who, **{key: '0' * 64})
            args = (bad, second) if who is first else (first, bad)
            reasons = decide.invalid(PLAN, (PSHA, SSHA), *args)
            self.assertTrue(reasons and reasons[0].startswith('해시 불일치'), reasons)
            self.assertEqual(decide.row(reasons, (14, 13, 2, 1), Fraction(4, 5), PLAN, 1.)[0], 1)

    def test_row1_plus_29_pairs(self):
        self.assertEqual(decide.row(['x'], (14, 14, 0, 1), Fraction(1), PLAN, 1.)[0], 1)

    def test_every_30_table_gives_one_row(self):
        fast = plan_with(bootstrap_draws=2)
        seen = Counter()
        tables = tables30()
        self.assertEqual(len(tables), 5456)
        for t in tables:
            m = score_rounds.measures(pairs_of(*t), fast)
            row, why = decide.row([], m['table'], m['kappa'], fast, m['p'])
            self.assertIs(type(row), int)
            self.assertIn(row, range(1, 7))
            self.assertTrue(why)
            seen[row] += 1
            if (t[2] + t[3]) / 30 >= .5:  # d >= 0.5 -> 일치율 <= 0.5 -> 카파 < 0.6
                self.assertNotIn(row, (5, 6), t)
        self.assertEqual(set(seen), {2, 3, 4, 5, 6})  # 1행은 reasons로만 나옴


class Counts(unittest.TestCase):
    PAIRS = [NN] * 3 + [DD] * 3 + [('정상', '불가'), ('불가', '불가'), ('결함', '미확인'), ('미확인', '미확인')]

    def test_five_numbers_and_three_class(self):
        m = score_rounds.measures(self.PAIRS, PLAN)
        self.assertEqual(m['counts'], dict(start=10, first_unusable=2, second_unusable=4, one_round_only=2,
                                           confirmed_pairs=6, unconfirmed_excluded_from_three=2))
        self.assertEqual(m['kappa3'], Fraction(33, 41))  # 8쌍(미확인 제외) 손계산
        self.assertEqual(m['table3'][('정상', '불가')], 1)
        self.assertEqual(m['table'], (3, 3, 0, 0))

    def test_error_layer_does_not_change_main_metrics(self):
        main = pairs_of(14, 13, 2, 1)
        a = run(main, err=[NN, DD, B])
        b = run(main, err=[B, B, C, DD, NN, NN])
        keys = [k for k in a if k not in ('error_layer',)]
        self.assertEqual({k: a[k] for k in keys}, {k: b[k] for k in keys})
        self.assertEqual(a['error_layer'], dict(start=3, confirmed_pairs=3, same_answer=2))
        self.assertEqual(b['error_layer'], dict(start=6, confirmed_pairs=6, same_answer=3))


class Bootstrap(unittest.TestCase):
    def test_same_seed_same_interval_and_other_seed_differs(self):
        p = pairs_of(14, 13, 2, 1)
        one = stats.interval(p, 300, 7)
        self.assertEqual(one, stats.interval(p, 300, 7))
        self.assertNotEqual(one, stats.interval(p, 300, 8))
        self.assertEqual(one['draws'], 300)

    def test_undefined_resamples_are_reported(self):
        p = pairs_of(29, 0, 1, 0)  # 한 쌍이 빠지면 전부 정상-정상이라 카파 정의 불가
        got = stats.interval(p, 200, 5)
        self.assertGreater(got['undefined'], 0)
        self.assertLess(got['undefined'], 200)
        res = run(p)
        self.assertEqual(res['row'], 2)  # 결함 비율이 p_min 아래라 2행. 구간은 null(미측정)
        self.assertIsNone(res['kappa_interval'])

    def test_all_undefined(self):
        got = stats.interval(pairs_of(30, 0, 0, 0), 50, 1)
        self.assertEqual((got['lo'], got['hi'], got['undefined']), (None, None, 50))
        self.assertIsNone(score_rounds.measures(pairs_of(30, 0, 0, 0), PLAN)['kappa'])

    def test_interval_in_output_for_row6(self):
        res = run(pairs_of(14, 13, 2, 1))
        ci = res['kappa_interval']
        self.assertEqual(ci['draws'], PLAN['bootstrap_draws'])
        self.assertIn('undefined', ci)
        self.assertLessEqual(ci['lo'], ci['hi'])


class Wording(unittest.TestCase):
    def test_result_text(self):
        res = run(pairs_of(14, 13, 2, 1))
        text = json.dumps(res, ensure_ascii=False)
        for word in ('정확도', '개선'):
            self.assertNotIn(word, text)
        self.assertIn('확정 쌍 일치율', res)
        self.assertEqual(res['card_conversion'], '미측정')
        self.assertEqual(len(res['limits']), 5)
        self.assertIn('승인하지 않는다', res['not_approval'])
        self.assertIn('실험', res['not_approval'])
        self.assertIn('라벨 변경', res['not_approval'])
        self.assertIn('재요청', res['not_approval'])
        self.assertEqual(res['kappa']['binary']['fraction'], '4/5')
        # 11절 (b) 한계 다섯 줄이 모든 행에 붙는다
        self.assertEqual(run(pairs_of(14, 14, 0, 1))['limits'], res['limits'])

    def test_sources_have_no_forbidden_words_or_defaults(self):
        for name, path in SRC.items():
            text = path.read_text(encoding='utf-8')
            for word in ('정확도', '개선'):
                self.assertNotIn(word, text, name)
            self.assertNotIn('plan.get(', text, name)
            self.assertNotIn('default=', text, name)

    def test_structure_budget(self):
        counts = {n: sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                         for x in ast.walk(ast.parse(p.read_text(encoding='utf-8')))) for n, p in SRC.items()}
        self.assertEqual(counts, dict(stats=5, decide=4, score_rounds=4))


class Constants(unittest.TestCase):
    def test_match_labeling_protocol(self):
        text = (ROOT / 'LABELING_PROTOCOL.md').read_text(encoding='utf-8')
        m = re.search(r'최소 분모 (\d+), 목표선 카파 ([0-9]+\.[0-9]+), 경고선 카파 ([0-9]+\.[0-9]+)', text)
        self.assertIsNotNone(m)
        self.assertEqual(decide.MIN_N, int(m.group(1)))
        self.assertEqual(decide.GOAL, Fraction(m.group(2)))
        self.assertEqual(decide.WARN, Fraction(m.group(3)))
        self.assertIs(type(decide.GOAL), Fraction)

    def test_reused_functions_come_from_the_diagnostic_files(self):
        self.assertTrue(stats.WILSON.__code__.co_filename.endswith('corner-rejudge-20261121/score.py'))
        self.assertTrue(stats.MCNEMAR.__code__.co_filename.endswith('corner-chance-check-20261124/check.py'))
        self.assertEqual(stats.MCNEMAR({1: False, 2: True}, {1: True, 2: False}),
                         dict(worse_b=1, better_c=1, exact_two_sided_p=1.))


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.plan_path = self.dir / 'plan.json'
        self.plan_path.write_text(json.dumps(PLAN, ensure_ascii=False), encoding='utf-8')
        self.psha = cfg.file_sha(self.plan_path)
        self.sel_path = self.dir / 'selection.json'

    def files(self, sel_plan_sha=None, round_sel_sha=None, round_plan_sha=None):
        sel, first, second = rounds(pairs_of(14, 13, 2, 1))
        sel['plan_sha256'] = sel_plan_sha or self.psha
        self.sel_path.write_text(json.dumps(sel), encoding='utf-8')
        ssha = cfg.file_sha(self.sel_path)
        out = [str(self.plan_path), str(self.sel_path)]
        for name, rd in (('r1.json', first), ('r2.json', second)):
            rd.update(plan_sha256=round_plan_sha or self.psha, selection_sha256=round_sel_sha or ssha)
            (self.dir / name).write_text(json.dumps(rd), encoding='utf-8')
            out.append(str(self.dir / name))
        return out + [str(self.dir / 'result.json')]

    def call(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = score_rounds.main(argv)
        return code, err.getvalue()

    def test_success_writes_result(self):
        argv = self.files()
        self.assertEqual(self.call(argv)[0], 0)
        res = json.loads(Path(argv[4]).read_text(encoding='utf-8'))
        self.assertEqual(res['row'], 6)
        self.assertEqual(res['plan_sha256'], self.psha)
        self.assertEqual(self.call(argv)[0], 2)  # 이미 있으면 덮어쓰지 않음

    def test_hash_mismatch_exits_2_without_result(self):
        for kw in (dict(sel_plan_sha='0' * 64), dict(round_sel_sha='0' * 64), dict(round_plan_sha='0' * 64)):
            with self.subTest(kw=kw):
                argv = self.files(**kw)
                code, err = self.call(argv)
                self.assertEqual(code, 2)
                self.assertIn('1행 조건', err)
                self.assertFalse(Path(argv[4]).exists())

    def test_input_problems_exit_2(self):
        argv = self.files()
        self.assertEqual(self.call(argv[:4])[0], 2)  # 인자 수
        for i in (0, 1, 2, 3):
            with self.subTest(i=i):
                bad = list(argv)
                bad[i] = str(self.dir / 'none.json')
                self.assertEqual(self.call(bad)[0], 2)
        broken = self.dir / 'broken.json'
        broken.write_text('{', encoding='utf-8')
        self.assertEqual(self.call(argv[:2] + [str(broken)] + argv[3:])[0], 2)
        sel, first, second = rounds(pairs_of(14, 13, 2, 1))
        first['answers']['1'] = '모름'
        (self.dir / 'r1.json').write_text(json.dumps(first), encoding='utf-8')
        code, err = self.call(argv)
        self.assertEqual(code, 2)
        self.assertFalse(Path(argv[4]).exists())

    def test_other_row1_reasons_exit_0(self):
        argv = self.files()
        first = json.loads((self.dir / 'r1.json').read_text(encoding='utf-8'))
        first['judge_confirmed'] = False
        (self.dir / 'r1.json').write_text(json.dumps(first), encoding='utf-8')
        self.assertEqual(self.call(argv)[0], 0)
        self.assertEqual(json.loads(Path(argv[4]).read_text(encoding='utf-8'))['row'], 1)

    def test_module_entry(self):
        import subprocess
        argv = self.files()
        r = subprocess.run([sys.executable, '-m', 'tools.self_agreement.score_rounds'] + argv,
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('정확도', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
