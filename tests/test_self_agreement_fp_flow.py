"""끝에서 끝까지 시험 2판(self-agreement-v2-flow): schema 2 plan -> 오탐 층 선정 -> 두 회차 화면 -> 누르기 -> 가져오기 -> 점수.

시험의 숫자·문장·시드·ID는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다(설계 5.1의 손계산 표를 쓴다).
PIL로 만든 격자 그림과 가짜 ID만 쓰고 실제 사진·라벨·artifacts는 열지 않는다. 누르기는 실제 screen.js를 node로 돌린다.
node가 없으면 건너뛰며 그 경우는 "미검증"이다. schema 1 흐름은 test_self_agreement_flow.py가 그대로 맡는다.
"""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from test_relabel_zone_round_trip import run  # noqa: E402
from tools.self_agreement import import_round, make_round, pick_zones, plan as cfg, score_rounds  # noqa: E402

CH = {'정': '정상', '결': '결함', '불': '불가', '미': '미확인'}
# 설계 5.1 표: 카드별 (1차, 2차) 네 구역 값
K = [('정정정결', '정정정정'), ('정정정정', '정결정정'), ('결정정정', '정정결정'),
     ('정정불결', '정정불정'), ('결불정정', '결정정미'), ('정정정정', '정정정정')]
FP_ZONES = dict(start=24, first_unusable=2, second_unusable=2, one_round_only=2, confirmed_pairs=21, same_answer=16, b=2, c=3)
FP_CARDS = dict(start=6, zones_per_card=4, rule='any_defect_unknown_blocks', first={'정상': 2, '결함': 4, '불확정': 0},
                second={'정상': 2, '결함': 3, '불확정': 1}, confirmed_pairs=5, unchanged=3, b=1, c=1, flips=2, unknown_pairs=1)
MAIN = (14, 13, 2, 1)  # 정상-정상, 결함-결함, b, c -> 6행·이진 카파 4/5
CUT_STATUS = {None: '컷 미정, 판정 없음', 2: '컷 이상', 3: '판정 불가(불확정 카드)', 4: '컷 미만', 9: '컷 미만'}  # 9 = 확정 카드 쌍(5)보다 큼


@unittest.skipUnless(shutil.which('node'), 'node unavailable: flow UNVERIFIED')
class FpFlowTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        pop, self.fp_rows = [], []
        for g in range(46):  # 가짜 카드 46장: 0~39 주 층 후보(구역 2개), 40~45(K1~K6)는 오탐 카드(구역 4개, 제외 목록)
            image = self.tmp / f'fake_photo_{g}.png'
            pic = Image.new('RGB', (200, 300), (230, 230, 230))
            draw = ImageDraw.Draw(pic)
            for x in range(0, 200, 20):
                draw.line([(x + g % 7, 0), (x, 300)], fill=(40, 40 + g * 4, 90), width=2)
            pic.save(image)
            fp = g >= 40
            rows = [dict(id=f'FAKE-ID-{g}-{a}', group=f'FAKE-GROUP-{g}', area=f'FAKE-AREA-{a}', image=str(image),
                         box=[.1 + .1 * (a % 2), .1 + .2 * (a // 2), .4 + .1 * (a % 2), .4 + .2 * (a // 2)]) for a in range(4 if fp else 2)]
            pop += rows
            self.fp_rows += rows if fp else []
        self.fp_rows.sort(key=lambda r: (r['area'], r['id']))  # 같은 카드의 구역이 파일에서 떨어져 있다(5.5의 3)
        self.pop, self.exc, self.fp, self.stmt = (self.tmp / n for n in ('pop.json', 'exc.json', 'fp.json', 'stmt.txt'))
        self.pop.write_text(json.dumps(pop), encoding='utf-8')
        self.exc.write_text(json.dumps([f'FAKE-GROUP-{g}' for g in range(40, 46)]), encoding='utf-8')
        self.fp.write_text(json.dumps(self.fp_rows), encoding='utf-8')
        self.stmt.write_text('합성 문장\n', encoding='utf-8')

    def make_plan(self, fp=True, cut=None):
        return dict(
            schema=2, approval_ref='합성 시험용', cell='모서리', new_first_round=True, population_sha256=cfg.file_sha(self.pop),
            exclude_sha256=cfg.file_sha(self.exc), error_layer_sha256=None, main_count=30, error_count=0, strata=None,
            per_page=8, crop='highres', seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=50, min_interval_hours=0,
            max_interval_hours=None, judge_statement='합성 문장', p_min='0.1', direction_min_count=6, direction_alpha='0.05',
            reference_zone_count=None, layers=['main', 'fp'] if fp else ['main'], fp_layer_sha256=cfg.file_sha(self.fp) if fp else None,
            fp_count=24 if fp else 0, fp_zones_per_card=4 if fp else None, card_rule='any_defect_unknown_blocks' if fp else None,
            card_flip_cut=cut if fp else None)

    def press(self, folder, vals, name):
        """쪽마다 실제 screen.js로 vals[n]을 누르고(미확인은 누르지 않음) 나온 글을 파일로 쓴다. 글 목록과 쪽 HTML 글도 돌려준다."""
        key = json.loads((folder / 'key.json').read_text(encoding='utf-8'))
        files, pages = [], []
        for i, page in enumerate(key['pages']):
            html = (folder / page['file']).read_text(encoding='utf-8')
            presses = [dict(card=c, v=vals[n]) for c, n in enumerate(page['zones'].values()) if vals[n] != '미확인'] + [dict(id='copy')]
            got, error = run(html, presses, alln=False)
            self.assertEqual(error, '')
            files.append(Path(f'{name}-{i}.txt'))
            files[-1].write_text(got['out'], encoding='utf-8')
            pages.append(html + got['out'])
        return files, pages

    def flow(self, name, fp=True, cut=None, flip_fp=False):
        """합성 손계산 답을 끝까지 돌리고 dict(res, sel, plan_path, recs, orders, pages, vals, w)를 돌려준다."""
        w = self.tmp / name
        w.mkdir()
        plan_path, sel, recs, orders, texts, buf = w / 'plan.json', w / 'selection.json', [], [], [], io.StringIO()
        plan_path.write_text(json.dumps(self.make_plan(fp, cut), ensure_ascii=False), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(buf):
            args = [plan_path, self.pop, self.exc, '-', self.fp if fp else '-', sel]
            self.assertEqual(pick_zones.main([str(a) for a in args]), 0, buf.getvalue())
            zones = json.loads(sel.read_text(encoding='utf-8'))['zones']
            main = sorted(z['n'] for z in zones if z['layer'] == 'main')
            fps = {z['id']: z['n'] for z in zones if z['layer'] == 'fp'}
            self.assertEqual((len(main), len(fps)), (30, 24 if fp else 0))
            pairs = [('정상', '정상')] * MAIN[0] + [('결함', '결함')] * MAIN[1] + [('정상', '결함')] * MAIN[2] + [('결함', '정상')] * MAIN[3]
            vals = [dict(zip(main, (p[i] for p in pairs))) for i in (0, 1)]
            for k, spec in enumerate(K if fp else ()):
                for a in range(4):
                    for i in (0, 1):
                        v = CH[spec[i][a]]
                        vals[i][fps[f'FAKE-ID-{40 + k}-{a}']] = {'정상': '결함', '결함': '정상'}.get(v, v) if flip_fp else v
            for r in (1, 2):
                folder, out = w / f'r{r}', w / f'out{r}'
                made = [plan_path, sel, r, folder] + ([w / 'r1' / 'key.json'] if r == 2 else [])
                self.assertEqual(make_round.main([str(a) for a in made]), 0, buf.getvalue())
                files, pages = self.press(folder, vals[r - 1], w / f'ans{r}')
                texts += pages
                imp = [plan_path, folder, self.stmt, out] + files
                self.assertEqual(import_round.main([str(a) for a in imp]), 0, buf.getvalue())
                recs.append(json.loads((out / f'round{r}.json').read_text(encoding='utf-8')))
                self.assertEqual(recs[-1]['answers'], {str(n): v for n, v in vals[r - 1].items()})  # 누른 것 = 가져온 것(불가·미확인 포함)
                orders.append([n for p in json.loads((folder / 'key.json').read_text(encoding='utf-8'))['pages'] for n in p['zones'].values()])
            self.assertNotEqual(orders[0], orders[1])  # 2차는 순서가 다른데도 같은 n에 같은 값
            res = self.score(w, plan_path, sel, recs, 'result.json', buf)
        return dict(res=res, sel=sel, plan_path=plan_path, recs=recs, orders=orders, pages=texts, vals=vals, w=w, buf=buf)

    def score(self, w, plan_path, sel, recs, out, buf):
        paths = [w / f'{out}.1.json', w / f'{out}.2.json']
        for path, rec in zip(paths, recs):
            path.write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
        code = score_rounds.main([str(a) for a in (plan_path, sel, *paths, w / out)])
        return json.loads((w / out).read_text(encoding='utf-8')) if code == 0 else code

    def test_table_survives_screen(self):
        # 설계 5.1: 화면·가져오기를 거쳐도 카드·구역 수가 손계산과 같다. 컷 3은 판정 불가
        r = self.flow('t1', cut=3)
        fp = r['res']['fp_layer']
        self.assertEqual(fp['zones'], FP_ZONES)
        cards = fp['cards']
        self.assertEqual({k: cards[k] for k in FP_CARDS}, FP_CARDS)
        self.assertAlmostEqual(cards['wilson95'][0], 0.1176, places=4)
        self.assertAlmostEqual(cards['wilson95'][1], 0.7693, places=4)
        self.assertAlmostEqual(cards['exact_two_sided_p'], 1)
        self.assertIsNone(cards['exact_upper'])
        self.assertEqual(fp['flip_cut'], dict(cut=3, status=CUT_STATUS[3]))
        self.assertEqual(fp['main_layer_cards'], '해당 없음(카드당 구역 1개)')
        self.assertNotRegex(json.dumps(fp, ensure_ascii=False).lower(), r'kappa|카파|e_interval|target|목표|경고')  # 카파·e·목표선 없음
        self.assertEqual(fp['bootstrap']['draws'], 50)

    def test_main_layer_unchanged(self):
        # 주 층 14/13/2/1 -> 6행·이진 카파 정확히 4/5. fp 답을 모두 뒤집어도 fp_layer 밖은 같고, fp 없는 plan의 지표도 같다
        a = self.flow('m1')
        res = a['res']
        self.assertEqual((res['row'], res['kappa']['binary']['fraction']), (6, '4/5'))
        self.assertEqual(res['table'], dict(normal_normal=14, defect_defect=13, b=2, c=1))
        self.assertEqual((res['b'], res['c'], res['exact_two_sided_p'], res['card_conversion']), (2, 1, 1, '미측정'))
        self.assertEqual((res['counts']['start'], res['counts']['confirmed_pairs']), (30, 30))
        flipped = self.flow('m2', flip_fp=True)['res']
        self.assertNotEqual(flipped['fp_layer'], res['fp_layer'])
        self.assertEqual({k: v for k, v in flipped.items() if k != 'fp_layer'}, {k: v for k, v in res.items() if k != 'fp_layer'})
        bare = self.flow('m3', fp=False)['res']
        self.assertIsNone(bare['fp_layer'])
        for k in ('row', 'kappa', 'table', 'table3', 'b', 'c', 'exact_two_sided_p', 'counts', 'd', 'e', '확정 쌍 일치율'):
            self.assertEqual(bare[k], res[k], k)

    def test_screen_hides_layer_and_identity(self):
        # 화면 글(base64 제거)과 답 글에 층·카드·구역 신원이 없다. 같은 카드 구역은 선정 순서에서 섞여 있다
        r = self.flow('s1')
        zones = json.loads(r['sel'].read_text(encoding='utf-8'))['zones']
        for text in r['pages']:
            text = re.sub(r'base64,[A-Za-z0-9+/=]+', 'base64,', text)
            low = text.lower()
            for word in ('fp', 'layer', 'main', 'error', 'group', 'fake', '.png'):
                self.assertNotIn(word, low, word)
            for z in zones:
                for field in ('id', 'group', 'area', 'image'):
                    self.assertNotIn(z[field], text)
        by_card = {}
        for z in zones:
            if z['layer'] == 'fp':
                by_card.setdefault(z['group'], []).append(z['n'])
        self.assertEqual(len(by_card), 6)
        self.assertTrue(all(max(ns) - min(ns) + 1 > len(ns) for ns in by_card.values()), by_card)  # 번호가 이어지지 않음(섞임)

    def test_cut_states_and_oversize_cut(self):
        # 설계 5.1·5.5의 5: 컷 2·3·4·null, 컷이 확정 카드 쌍 수(5)보다 커도(9) 오류가 아니라 컷 미만
        for cut, status in CUT_STATUS.items():
            fp = self.flow(f'c{cut}', cut=cut)['res']['fp_layer']
            self.assertEqual(fp['flip_cut'], dict(cut=cut, status=status))
            self.assertEqual(fp['cards']['flips'], 2)

    def test_fp_layer_without_fp_zones_is_refused(self):
        # 5.5의 4: plan layers에는 fp가 있는데 selection에 fp 구역이 하나도 없으면 거절(종료 2, 층 태그 이유)
        r = self.flow('n1')
        zones = [z for z in json.loads(r['sel'].read_text(encoding='utf-8'))['zones'] if z['layer'] != 'fp']
        sel = r['w'] / 'selection-nofp.json'
        sel.write_text(json.dumps(dict(plan_sha256=cfg.file_sha(r['plan_path']), zones=zones), ensure_ascii=False), encoding='utf-8')
        recs = [dict(rec, selection_sha256=cfg.file_sha(sel), answers={n: v for n, v in rec['answers'].items() if n in {str(z['n']) for z in zones}})
                for rec in r['recs']]
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertEqual(self.score(r['w'], r['plan_path'], sel, recs, 'refused.json', buf), 2)
        self.assertIn('layer 태그', buf.getvalue())
        self.assertFalse((r['w'] / 'refused.json').exists())


if __name__ == '__main__':
    unittest.main()
