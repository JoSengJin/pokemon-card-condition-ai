"""끝에서 끝까지 시험(self-agreement-flow): 합성 모집단 -> 선정 -> 두 회차 화면 -> 누르기 -> 가져오기 -> 점수.

시험의 숫자·문장·시드·ID는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
PIL로 만든 격자 그림과 가짜 ID만 쓰고 실제 사진·라벨·artifacts는 열지 않는다. 누르기는 실제 screen.js를 node로 돌린다.
node가 없으면 건너뛰며 그 경우는 "미검증"이다.
"""
import contextlib
import io
import json
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

SAME = ('정상', '정상')


@unittest.skipUnless(shutil.which('node'), 'node unavailable: flow UNVERIFIED')
class FlowTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        rows = []
        for g in range(40):  # 가짜 카드 40장 x 구역 2개. 마지막 4장은 제외 카드(오류 층용)
            image = self.tmp / f'fake_photo_{g}.png'
            pic = Image.new('RGB', (200, 300), (230, 230, 230))
            draw = ImageDraw.Draw(pic)
            for x in range(0, 200, 20):
                draw.line([(x + g % 7, 0), (x, 300)], fill=(40, 40 + g * 5, 90), width=2)
            pic.save(image)
            rows += [dict(id=f'FAKE-ID-{g}-{a}', group=f'FAKE-GROUP-{g}', area=f'FAKE-AREA-{a}', image=str(image), box=[.1, .1, .5, .5]) for a in (0, 1)]
        self.pop, self.exc, self.err, self.stmt = (self.tmp / n for n in ('pop.json', 'exc.json', 'err.json', 'stmt.txt'))
        self.pop.write_text(json.dumps(rows), encoding='utf-8')
        self.exc.write_text(json.dumps([f'FAKE-GROUP-{g}' for g in range(36, 40)]), encoding='utf-8')
        self.err.write_text(json.dumps([r for r in rows if r['id'] in ('FAKE-ID-36-0', 'FAKE-ID-37-0')]), encoding='utf-8')
        self.stmt.write_text('합성 문장\n', encoding='utf-8')
        self.plan = dict(
            schema=1, approval_ref='합성 시험용', cell='모서리', new_first_round=True, population_sha256=cfg.file_sha(self.pop),
            exclude_sha256=cfg.file_sha(self.exc), error_layer_sha256=cfg.file_sha(self.err), main_count=30, error_count=2, strata=None,
            per_page=8, crop='highres', seed_selection=11, seed_order2=22, seed_bootstrap=33, bootstrap_draws=50, min_interval_hours=0,
            max_interval_hours=None, judge_statement='합성 문장', p_min='0.1', direction_min_count=6, direction_alpha='0.05',
            reference_zone_count=None)

    def press(self, folder, vals, name):
        """회차 폴더의 쪽마다 실제 screen.js로 vals[n]을 누르고 나온 글을 파일로 쓴다."""
        key = json.loads((folder / 'key.json').read_text(encoding='utf-8'))
        files = []
        for i, page in enumerate(key['pages']):
            presses = [dict(card=c, v=vals[n]) for c, n in enumerate(page['zones'].values())] + [dict(id='copy')]
            got, error = run((folder / page['file']).read_text(encoding='utf-8'), presses, alln=False)
            self.assertEqual(error, '')
            files.append(Path(f'{name}-{i}.txt'))
            files[-1].write_text(got['out'], encoding='utf-8')
        return files

    def flow(self, name, table, err=(SAME, SAME), statement=True, edit=None):
        """table=(정상-정상, 결함-결함, b, c)를 누르는 값으로 만들어 끝까지 돌리고 (result, selection 바이트)를 돌려준다.
        statement=False면 1차를 문장 없이 먼저 가져와 종료 2·기록 없음을 확인한 뒤 같은 원본으로 다시 가져온다.
        edit={회차: 기록에 덮어쓸 값}은 점수를 내기 전 복사본만 바꾼다(주체·제출 시각 조작)."""
        w = self.tmp / name
        w.mkdir()
        plan_path, sel, recs, orders, buf = w / 'plan.json', w / 'selection.json', [], [], io.StringIO()
        plan_path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(buf):
            self.assertEqual(pick_zones.main([str(a) for a in (plan_path, self.pop, self.exc, self.err, sel)]), 0, buf.getvalue())
            zones = json.loads(sel.read_text(encoding='utf-8'))['zones']
            main, errs = (sorted(z['n'] for z in zones if z['layer'] == k) for k in ('main', 'error'))
            pairs = [SAME] * table[0] + [('결함', '결함')] * table[1] + [('정상', '결함')] * table[2] + [('결함', '정상')] * table[3]
            self.assertEqual((len(main), len(errs), len(pairs)), (30, 2, 30))
            vals = [{**dict(zip(main, (p[i] for p in pairs))), **dict(zip(errs, (p[i] for p in err)))} for i in (0, 1)]
            for r in (1, 2):
                folder, out = w / f'r{r}', w / f'out{r}'
                made = [plan_path, sel, r, folder] + ([w / 'r1' / 'key.json'] if r == 2 else [])
                self.assertEqual(make_round.main([str(a) for a in made]), 0, buf.getvalue())
                files = self.press(folder, vals[r - 1], w / f'ans{r}')
                args = [str(plan_path), str(folder), str(self.stmt), str(out)] + [str(f) for f in files]
                if not statement and r == 1:
                    self.assertEqual(import_round.main(args[:2] + ['-'] + args[3:]), 2)
                    self.assertFalse((out / 'round1.json').exists())
                self.assertEqual(import_round.main(args), 0, buf.getvalue())
                recs.append(json.loads((out / f'round{r}.json').read_text(encoding='utf-8')))
                self.assertEqual(recs[-1]['answers'], {str(n): v for n, v in vals[r - 1].items()})  # 누른 것 = 가져온 것
                orders.append([n for p in json.loads((folder / 'key.json').read_text(encoding='utf-8'))['pages'] for n in p['zones'].values()])
            self.assertNotEqual(orders[0], orders[1])  # 2차는 순서가 다른데도 같은 n에 같은 값
            for r, update in (edit or {}).items():
                recs[r - 1].update(update)
            paths = [w / 'score1.json', w / 'score2.json']
            for path, rec in zip(paths, recs):
                path.write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(score_rounds.main([str(a) for a in (plan_path, sel, *paths, w / 'result.json')]), 0, buf.getvalue())
        return json.loads((w / 'result.json').read_text(encoding='utf-8')), sel.read_bytes()

    def test_known_2x2_row6(self):
        # 손계산(설계 3.2): 14/13/2/1 -> 일치 27/30=0.9, 이진 카파 정확히 4/5, 정확 양측 p=1, b=2·c=1, 6행
        res, _ = self.flow('t6', (14, 13, 2, 1))
        self.assertEqual((res['row'], res['kappa']['binary']['fraction']), (6, '4/5'))
        self.assertEqual(res['table'], dict(normal_normal=14, defect_defect=13, b=2, c=1))
        self.assertEqual((res['b'], res['c'], res['exact_two_sided_p']), (2, 1, 1))
        self.assertEqual((res['확정 쌍 일치율']['k'], res['확정 쌍 일치율']['n']), (27, 30))
        self.assertEqual((res['counts']['start'], res['counts']['confirmed_pairs']), (30, 30))
        self.assertIn('승인하지 않는다', res['not_approval'])
        self.assertEqual(res['card_conversion'], '미측정')

    def test_direction_row3(self):
        # 손계산: 13/11/6/0 -> b+c=6, p=0.03125 < 0.05(합성 문턱) -> 3행, e는 쓰지 않음, 이진 카파 143/233
        res, _ = self.flow('t3', (13, 11, 6, 0))
        self.assertEqual((res['row'], res['e'], res['e_interval']), (3, None, None))
        self.assertEqual((res['b'], res['c'], res['exact_two_sided_p']), (6, 0, 0.03125))
        self.assertEqual(res['kappa']['binary']['fraction'], '143/233')

    def test_guards_go_to_row1(self):
        # 문장 없이 먼저 가져오면 종료 2(flow 안), 나중에 같은 원본으로 성공. 그 위에서 주체·제출 시각 조작은 1행이고 지표는 비어 있다
        for name, edit, why in (('g1', {1: dict(judge_confirmed=False)}, '주체 미확인'),
                                ('g2', {2: dict(submitted={'x': '2000-01-01T00:00:00+09:00'})}, '간격 이탈')):
            res, _ = self.flow(name, (14, 13, 2, 1), statement=False, edit=edit)
            self.assertEqual(res['row'], 1)
            self.assertTrue(any(why in r for r in res['reasons']), res['reasons'])
            self.assertEqual((res['kappa'], res['table'], res['e']), (None, None, None))

    def test_error_layer_inert_and_same_seed(self):
        # 오류 층 값이 달라도 주 지표는 같고(오류 층 건수만 다름), 같은 시드 재실행은 선정·결과가 같다
        a, sel_a = self.flow('e1', (13, 12, 3, 2), err=(SAME, SAME))
        b, sel_b = self.flow('e2', (13, 12, 3, 2), err=(('정상', '결함'), ('결함', '정상')))
        c, sel_c = self.flow('e3', (13, 12, 3, 2), err=(SAME, SAME))
        self.assertEqual(({k: v for k, v in a.items() if k != 'error_layer'}), {k: v for k, v in b.items() if k != 'error_layer'})
        self.assertEqual((a['error_layer']['same_answer'], b['error_layer']['same_answer']), (2, 0))
        self.assertEqual((a, sel_a), (c, sel_c))
        self.assertEqual(sel_a, sel_b)


if __name__ == '__main__':
    unittest.main()
