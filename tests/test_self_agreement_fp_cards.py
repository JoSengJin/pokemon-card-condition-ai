"""계약 V2-D(self-agreement-v2-cards) 시험: 오탐 층의 카드 판정·뒤집힘·부트스트랩·컷 상태. 합성 fixture만 쓴다.

이 파일의 숫자·문장·시드는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
가짜 해시·가짜 ID만 쓰고 사진·라벨·artifacts는 열지 않는다.
"""
import ast
import contextlib
import io
import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.self_agreement import cards, plan as cfg, score_rounds  # noqa: E402

SRC = {n: ROOT / ('tools/self_agreement/%s.py' % n) for n in ('cards', 'score_rounds')}
PSHA, SSHA = 'a' * 64, 'b' * 64
T1, T2 = '2026-03-01T10:00:00+09:00', '2026-03-15T10:00:00+09:00'
CH = {'정': '정상', '결': '결함', '불': '불가', '미': '미확인'}
NN, DD, B, C = ('정상', '정상'), ('결함', '결함'), ('정상', '결함'), ('결함', '정상')
# 설계 5.1 표: 카드당 4구역, (1차, 2차)
K = [('정정정결', '정정정정'), ('정정정정', '정결정정'), ('결정정정', '정정결정'),
     ('정정불결', '정정불정'), ('결불정정', '결정정미'), ('정정정정', '정정정정')]

PLAN1 = dict(schema=1, approval_ref='synthetic', cell='모서리', new_first_round=True,
             population_sha256='c' * 64, exclude_sha256='d' * 64, error_layer_sha256=None,
             main_count=30, error_count=0, strata=None, per_page=10, crop='highres',
             seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=300,
             min_interval_hours=10, max_interval_hours=None, judge_statement='합성 문장',
             p_min='0.1', direction_min_count=6, direction_alpha='0.05', reference_zone_count=100)


def plan2(fp=True, cut=3, count=24, per=4, **kw):
    base = dict(PLAN1, schema=2, layers=['main', 'fp'] if fp else ['main'],
                fp_layer_sha256='9' * 64 if fp else None, fp_count=count if fp else 0,
                fp_zones_per_card=per if fp else None,
                card_rule='any_defect_unknown_blocks' if fp else None, card_flip_cut=cut if fp else None)
    return {**base, **kw}


def pairs_of(nn, dd, b, c):
    return [NN] * nn + [DD] * dd + [B] * b + [C] * c


def fp_rows(cds):
    """cds=[(1차 글자열, 2차 글자열)] -> [(카드 번호, 1차 값, 2차 값)] 구역 단위."""
    return [(i, CH[a], CH[b]) for i, (x, y) in enumerate(cds) for a, b in zip(x, y)]


def make(main, fp=(), tag='fp', **over):
    """합성 selection과 두 회차. 구역 번호는 main 먼저, 오탐 구역은 카드가 떨어지도록 번호를 한 칸씩 건너뛴다."""
    zs = [('main', 'm%d' % i, a, b) for i, (a, b) in enumerate(main)]
    fz = fp_rows(fp)
    order = sorted(range(len(fz)), key=lambda j: (j % 4, j))  # 같은 카드의 구역을 서로 떨어뜨림
    zs += [(tag, 'f%d' % fz[j][0], fz[j][1], fz[j][2]) for j in order]
    zones = [dict(n=i + 1, layer=l, id='x%d' % i, group=g, area='a%d' % i, image='i%d' % i, box=[0, 0, 1, 1])
             for i, (l, g, _, _) in enumerate(zs)]

    def rd(k, t, idx):
        return dict(plan_sha256=PSHA, selection_sha256=SSHA, round=k, judge_confirmed=True, statement='합성',
                    submitted={'p%d' % k: t}, criteria_sha256='e' * 64, screen_sha256='f' * 64,
                    crops={'1': '1' * 64}, answers={str(i + 1): z[2 + idx] for i, z in enumerate(zs)}, raw=[])
    first, second = rd(1, T1, 0), rd(2, T2, 1)
    first.update(over.get('first', {}))
    second.update(over.get('second', {}))
    return {'plan_sha256': PSHA, 'zones': zones}, first, second


def run(main, fp=(), plan=None, **over):
    sel, first, second = make(main, fp, **over)
    return score_rounds.report(plan or plan2(count=4 * len(fp)), (PSHA, SSHA), sel, first, second)


def fp_zone_dicts(fp):
    sel, first, second = make([], fp)
    return [z for z in sel['zones'] if z['layer'] == 'fp'], first, second


class HandCalculation(unittest.TestCase):
    """설계 5.1 손계산 표."""

    def test_k_table(self):
        got = run(pairs_of(14, 13, 2, 1), K)['fp_layer']
        self.assertEqual(got['zones'], dict(start=24, first_unusable=2, second_unusable=2, one_round_only=2,
                                            confirmed_pairs=21, same_answer=16, b=2, c=3))
        c = got['cards']
        self.assertEqual((c['start'], c['zones_per_card'], c['rule']), (6, 4, 'any_defect_unknown_blocks'))
        self.assertEqual(c['first'], {'정상': 2, '결함': 4, '불확정': 0})
        self.assertEqual(c['second'], {'정상': 2, '결함': 3, '불확정': 1})
        self.assertEqual((c['confirmed_pairs'], c['unchanged'], c['b'], c['c'], c['flips'], c['unknown_pairs']),
                         (5, 3, 1, 1, 2, 1))
        self.assertAlmostEqual(c['wilson95'][0], .1176, places=4)
        self.assertAlmostEqual(c['wilson95'][1], .7693, places=4)
        self.assertEqual(c['exact_two_sided_p'], 1)
        self.assertIsNone(c['exact_upper'])
        self.assertEqual(got['main_layer_cards'], '해당 없음(카드당 구역 1개)')

    def test_zone_rate_times_cards_is_wrong(self):
        z = run(pairs_of(14, 13, 2, 1), K)['fp_layer']
        self.assertAlmostEqual(6 * (z['zones']['b'] + z['zones']['c']) / z['zones']['confirmed_pairs'], 1.43, places=2)
        self.assertEqual(z['cards']['flips'], 2)  # 곱으로 옮긴 1.43이 아니라 실제 뒤집힌 카드 수

    def test_cut_rows(self):
        for cut, want in ((2, '컷 이상'), (3, '판정 불가(불확정 카드)'), (4, '컷 미만'), (None, '컷 미정, 판정 없음')):
            with self.subTest(cut=cut):
                got = run(pairs_of(14, 13, 2, 1), K, plan2(cut=cut, count=24))['fp_layer']['flip_cut']
                self.assertEqual(got, dict(cut=cut, status=want))
                self.assertEqual(cards.cut_status(2, 1, cut), want)

    def test_cut_edges(self):
        self.assertEqual(cards.cut_status(0, 0, 1), '컷 미만')
        self.assertEqual(cards.cut_status(5, 0, 99), '컷 미만')  # 컷이 확정 쌍 수보다 커도 오류 아님
        self.assertEqual(cards.cut_status(1, 9, 99), '컷 미만')
        self.assertEqual(cards.cut_status(1, 9, 5), '판정 불가(불확정 카드)')

    def test_blocked_cards_are_not_flips_nor_unchanged(self):
        c = run(pairs_of(14, 13, 2, 1), K)['fp_layer']['cards']
        self.assertEqual(c['unchanged'] + c['flips'] + c['unknown_pairs'], c['start'])  # K4가 어느 쪽에도 안 들어감


class Judge(unittest.TestCase):
    def test_all_256_orders(self):
        for vals in itertools.product(cards.VALUES, repeat=4):
            want = '결함' if '결함' in vals else '정상' if set(vals) == {'정상'} else '불확정'
            self.assertEqual(cards.judge(list(vals)), want, vals)
            self.assertEqual(cards.judge(list(reversed(vals))), want)

    def test_empty_and_unknown_values(self):
        for bad in ([], ['정상', '모름']):
            with self.assertRaises(ValueError):
                cards.judge(bad)

    def test_mixed_defect_and_unusable_is_defect(self):
        self.assertEqual(cards.judge(['정상', '정상', '불가', '결함']), '결함')  # K4 1차
        self.assertEqual(cards.judge(['정상', '정상', '불가', '정상']), '불확정')


class ByCard(unittest.TestCase):
    def test_groups_scattered_zones_and_ignores_input_order(self):
        zones, first, second = fp_zone_dicts(K)
        self.assertNotEqual([z['group'] for z in zones][:2], ['f0', 'f0'])  # 같은 카드 구역이 떨어져 있음
        a, b = cards.by_card(zones, first, second), cards.by_card(list(reversed(zones)), first, second)
        self.assertEqual(len(a), 6)
        self.assertEqual({g: (c['first'], c['second'], sorted(c['pairs'])) for g, c in a.items()},
                         {g: (c['first'], c['second'], sorted(c['pairs'])) for g, c in b.items()})
        self.assertEqual((a['f3']['first'], a['f3']['second'], a['f3']['cc']), ('결함', '불확정', 0))


class ZeroOfNine(unittest.TestCase):
    def test_zero_flips(self):
        nine = [('정정정정', '정정정정')] * 9
        got = run(pairs_of(14, 13, 2, 1), nine, plan2(count=36))['fp_layer']
        c = got['cards']
        self.assertEqual((c['confirmed_pairs'], c['flips']), (9, 0))
        self.assertAlmostEqual(c['wilson95'][1], .2991, places=3)
        self.assertAlmostEqual(c['exact_upper'], .3363, places=4)  # 윌슨 상한과 섞어 쓰지 않는다
        self.assertEqual(got['bootstrap']['card_flip_rate'], dict(lo=0, hi=0, undefined=0))
        self.assertEqual(got['bootstrap']['zone_flip_rate'], dict(lo=0, hi=0, undefined=0))


class Bootstrap(unittest.TestCase):
    def cds(self, spec):
        zones, first, second = fp_zone_dicts(spec)
        return cards.by_card(zones, first, second)

    def test_two_cards_one_flipped_interval_is_0_to_1(self):
        got = cards.boot(self.cds([('정정정정', '결정정정'), ('정정정정', '정정정정')]), 2000, 5)
        self.assertEqual((got['card_flip_rate']['lo'], got['card_flip_rate']['hi']), (0, 1))
        self.assertEqual(got['draws'], 2000)

    def test_same_seed_same_value_other_seed_may_differ(self):
        c = self.cds(K)
        self.assertEqual(cards.boot(c, 300, 7), cards.boot(c, 300, 7))
        self.assertNotEqual(cards.boot(c, 300, 7), cards.boot(c, 300, 8))

    def test_card_order_does_not_matter(self):
        c = self.cds(K)
        self.assertEqual(cards.boot(c, 300, 7), cards.boot(dict(reversed(list(c.items()))), 300, 7))

    def test_all_unknown_cards(self):
        got = cards.boot(self.cds([('정정불정', '정정정정')] * 3), 50, 1)
        self.assertEqual(got['card_flip_rate'], dict(lo=None, hi=None, undefined=50))
        self.assertEqual(got['zone_flip_rate'], dict(lo=0, hi=0, undefined=0))  # 나머지 구역은 확정이라 구역 비율은 정의됨

    def test_whole_cards_are_drawn_together(self):
        """구역 수가 다른 카드: X는 3구역 모두 뒤집힘, Y는 1구역 그대로. 두 장을 뽑으면 구역 비율은 1, 3/4, 0 중 하나다."""
        cd = {'X': dict(pairs=[B] * 3, first='정상', second='결함', cc=1, cf=1, zc=3, zf=3),
              'Y': dict(pairs=[NN], first='정상', second='정상', cc=1, cf=0, zc=1, zf=0)}
        seen = []

        def spy(vals, n, method):
            seen.append(sorted(set(vals)))
            return [0.] * (n - 1)
        with mock.patch.object(cards.statistics, 'quantiles', spy):
            cards.boot(cd, 400, 3)
        self.assertEqual(seen[1], [0., .75, 1.])  # [0]=카드 비율 {0, .5, 1}, [1]=구역 비율
        self.assertEqual(seen[0], [0., .5, 1.])

    def test_does_not_touch_global_random(self):
        import random
        random.seed(99)
        want = random.random()
        random.seed(99)
        cards.boot(self.cds(K), 50, 1)
        self.assertEqual(random.random(), want)


class MainMetricsUnchanged(unittest.TestCase):
    def strip(self, res):
        return {k: v for k, v in res.items() if k != 'fp_layer'}

    def test_flipping_every_fp_answer_or_adding_cards_changes_nothing_else(self):
        main = pairs_of(14, 13, 2, 1)
        flipped = [(b, a) for a, b in K]
        more = K + [('정정정정', '결정정정')] * 3
        base = run(main, K)
        self.assertEqual(self.strip(base), self.strip(run(main, flipped)))
        self.assertEqual(self.strip(base), self.strip(run(main, more, plan2(count=36))))
        self.assertNotEqual(base['fp_layer'], run(main, flipped)['fp_layer'])

    def test_row_and_main_equal_to_layerless_run(self):
        main = pairs_of(14, 13, 2, 1)
        without = run(main, (), plan2(fp=False))
        self.assertEqual(self.strip(run(main, K)), self.strip(without))
        self.assertIsNone(without['fp_layer'])

    def test_row2_still_has_fp_layer_and_row1_is_null(self):
        row2 = run(pairs_of(14, 14, 0, 1), K)
        self.assertEqual(row2['row'], 2)
        self.assertEqual(row2['fp_layer']['cards']['flips'], 2)
        row1 = run(pairs_of(14, 13, 2, 1), K, first=dict(judge_confirmed=False))
        self.assertEqual(row1['row'], 1)
        self.assertIsNone(row1['fp_layer'])

    def test_schema1_keys_unchanged_schema2_adds_only_fp_layer(self):
        main = pairs_of(14, 13, 2, 1)
        s1 = run(main, (), PLAN1)
        s2 = run(main, K)
        self.assertNotIn('fp_layer', s1)
        self.assertEqual(set(s2) - set(s1), {'fp_layer'})
        self.assertEqual(set(s1) - set(s2), set())
        self.assertIn('error_layer', s1)

    def test_over_30_confirmed_fp_pairs_has_no_kappa_or_lines(self):
        many = [('정정정정', '결정정정')] * 8  # 구역 확정 쌍 32
        got = run(pairs_of(14, 13, 2, 1), many, plan2(count=32))['fp_layer']
        self.assertGreater(got['zones']['confirmed_pairs'], 30)
        text = json.dumps(got, ensure_ascii=False)
        for word in ('카파', 'kappa', '목표', '경고', '"e"', 'e_interval', '정확도', '개선'):
            self.assertNotIn(word, text)
        self.assertIn('컷 상태는 어떤 것도 승인하지 않는다', got['limits'][-1])
        self.assertEqual(len(got['limits']), 5)


class Rejections(unittest.TestCase):
    def test_tag_mismatches(self):
        main = pairs_of(14, 13, 2, 1)
        with self.assertRaises(ValueError):  # schema 1 selection에 fp 태그
            run(main, K, PLAN1)
        with self.assertRaises(ValueError):  # schema 2 layers에는 fp가 있는데 selection에 없음
            run(main, (), plan2(count=24))
        with self.assertRaises(ValueError):  # selection에는 fp가 있는데 layers에는 없음
            run(main, K, plan2(fp=False))
        with self.assertRaises(ValueError):  # 모르는 태그
            run(main, K, tag='x')
        with self.assertRaises(ValueError):  # 오탐 구역 수가 fp_count와 다름
            run(main, K, plan2(count=20))
        with self.assertRaises(ValueError):  # 카드당 구역 수가 plan과 다름
            run(main, K, plan2(per=2, count=24))

    def test_error_layer_still_works_with_schema1(self):
        sel, first, second = make(pairs_of(14, 13, 2, 1), (), )
        sel['zones'].append(dict(n=999, layer='error', id='e', group='ge', area='a', image='i', box=[0, 0, 1, 1]))
        for rd in (first, second):
            rd['answers']['999'] = '정상'
        res = score_rounds.report(PLAN1, (PSHA, SSHA), sel, first, second)
        self.assertEqual(res['error_layer'], dict(start=1, confirmed_pairs=1, same_answer=1))


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def files(self, plan, main, fp, tag='fp'):
        pp = self.dir / 'plan.json'
        pp.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        psha = cfg.file_sha(pp)
        sel, first, second = make(main, fp, tag=tag)
        sel['plan_sha256'] = psha
        sp = self.dir / 'selection.json'
        sp.write_text(json.dumps(sel), encoding='utf-8')
        out = [str(pp), str(sp)]
        for name, rd in (('r1.json', first), ('r2.json', second)):
            rd.update(plan_sha256=psha, selection_sha256=cfg.file_sha(sp))
            (self.dir / name).write_text(json.dumps(rd), encoding='utf-8')
            out.append(str(self.dir / name))
        return out + [str(self.dir / 'result.json')]

    def call(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            return score_rounds.main(argv), err.getvalue()

    def test_schema2_writes_fp_layer(self):
        argv = self.files(plan2(), pairs_of(14, 13, 2, 1), K)
        self.assertEqual(self.call(argv)[0], 0)
        res = json.loads(Path(argv[4]).read_text(encoding='utf-8'))
        self.assertEqual(res['fp_layer']['cards']['flips'], 2)
        self.assertEqual(res['row'], 6)

    def test_mismatch_exits_2_without_result(self):
        for name, plan, tag in (('schema1에 fp', PLAN1, 'fp'), ('layers 다름', plan2(fp=False), 'fp'),
                                ('모르는 태그', plan2(), 'x')):
            with self.subTest(name):
                self.setUp()
                argv = self.files(plan, pairs_of(14, 13, 2, 1), K, tag=tag)
                code, err = self.call(argv)
                self.assertEqual(code, 2)
                self.assertTrue(err)
                self.assertFalse(Path(argv[4]).exists())


class Wording(unittest.TestCase):
    def test_sources_have_no_forbidden_words_or_defaults(self):
        for name, path in SRC.items():
            text = path.read_text(encoding='utf-8')
            for word in ('정확도', '개선', 'plan.get(', 'default='):
                self.assertNotIn(word, text, name)

    def test_function_counts(self):
        counts = {n: sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                         for x in ast.walk(ast.parse(p.read_text(encoding='utf-8')))) for n, p in SRC.items()}
        self.assertEqual(counts, dict(cards=5, score_rounds=4))

    def test_output_text(self):
        text = json.dumps(run(pairs_of(14, 13, 2, 1), K), ensure_ascii=False)
        for word in ('정확도', '개선'):
            self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
