"""계약 B(self-agreement-round-pages) 시험. 합성 fixture만 쓴다.

숫자·문장·시드·경로는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다.
PIL로 만든 격자 그림과 가짜 ID만 쓰고 실제 사진·라벨·artifacts는 열지 않는다.
"""
import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from tools import relabel_corner_blind_pages as blind, relabel_corner_highres_pages as highres, relabel_zone_pages as zp  # noqa: E402
from tools.self_agreement import make_round, plan as cfg, screen  # noqa: E402

NODE = shutil.which('node')
JS = ROOT / 'tools/self_agreement/screen.js'
SYN_PLAN = dict(
    schema=1, approval_ref='합성 시험용', cell='모서리', new_first_round=True, population_sha256='a' * 64, exclude_sha256='b' * 64,
    error_layer_sha256=None, main_count=5, error_count=0, strata=None, per_page=2, crop='highres', seed_selection=11, seed_order2=22,
    seed_bootstrap=33, bootstrap_draws=10, min_interval_hours=1, max_interval_hours=None, judge_statement='합성 문장', p_min='0.1',
    direction_min_count=None, direction_alpha=None, reference_zone_count=None)


def grid(path, shift):
    image = Image.new('RGB', (200, 300), (230, 230, 230))
    draw = ImageDraw.Draw(image)
    for x in range(0, 200, 20):
        draw.line([(x + shift, 0), (x + shift, 300)], fill=(40, 40 + shift * 5, 90), width=2)
    for y in range(0, 300, 25):
        draw.line([(0, y), (200, y + shift)], fill=(90, 40, 40), width=2)
    image.save(path)


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.zones = []
        for i in range(5):
            image = self.tmp / f'secret_photo_{i}.png'
            grid(image, i + 1)
            self.zones.append(dict(n=7001 + i, layer='error' if i == 4 else 'main', id=f'FAKE-ID-{i}', group=f'FAKE-GROUP-{i}',
                                   area=f'FAKE-AREA-{i}', image=str(image), box=[.1, .1, .5, .5]))
        self.write_inputs(SYN_PLAN)

    def write_inputs(self, plan, zones=None):
        self.plan_path = self.tmp / 'plan.json'
        self.plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        sha = cfg.file_sha(self.plan_path)
        self.sel_path = self.tmp / 'selection.json'
        self.sel_path.write_text(json.dumps(dict(plan_sha256=sha, zones=zones or self.zones), ensure_ascii=False), encoding='utf-8')

    def run_main(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = make_round.main([str(a) for a in argv])
        return code, err.getvalue()

    def make(self, round_no, name, first=None):
        out = self.tmp / name
        args = [self.plan_path, self.sel_path, round_no, out] + ([first] if first else [])
        code, err = self.run_main(*args)
        self.assertEqual(code, 0, err)
        return out

    def rounds(self):
        one = self.make(1, 'r1')
        two = self.make(2, 'r2', one / 'key.json')
        return one, two

    @staticmethod
    def key(folder):
        return json.loads((folder / 'key.json').read_text(encoding='utf-8'))

    @staticmethod
    def tree(folder):
        return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


class ScreenContentTest(Base):
    def test_no_identity_or_layer_in_page_text_and_instructions_kept(self):
        for folder in self.rounds():
            for page in sorted(folder.glob('zones-*.html')):
                text = re.sub(r'base64,[A-Za-z0-9+/=]+', 'base64,X', page.read_text(encoding='utf-8'))
                for banned in ('FAKE-ID', 'FAKE-GROUP', 'FAKE-AREA', 'secret_photo', str(self.tmp), 'layer', 'error', '오류', 'main', '1차', '2차', 'data-n'):
                    self.assertNotIn(banned, text)
                for z in self.zones:
                    self.assertIsNone(re.search(rf'\b{z["n"]}\b', text))
                self.assertIn(blind.INSTRUCTIONS, text)
                self.assertNotIn('id="alln"', text)
                self.assertNotIn('안 누른 곳', text)

    def test_two_rounds_share_criteria_screen_and_crops(self):
        one, two = self.rounds()
        a, b = self.key(one), self.key(two)
        for name in ('plan_sha256', 'selection_sha256', 'criteria_sha256', 'screen_sha256', 'crops'):
            self.assertEqual(a[name], b[name])
        self.assertEqual((a['round'], b['round']), (1, 2))
        self.assertEqual(sorted(a['crops']), [str(z['n']) for z in self.zones])
        self.assertNotIn('crop_name', a)
        for folder, key in ((one, a), (two, b)):
            for page in key['pages']:
                record = json.loads((folder / (page['file'] + '.criteria.json')).read_text(encoding='utf-8'))
                self.assertEqual(record['criteria_sha256'], key['criteria_sha256'])
                self.assertEqual(sorted(record['items'].values()), sorted(key['crops'][str(n)] for n in page['zones'].values()))

    def test_second_round_has_other_order_and_new_numbers(self):
        one, two = self.rounds()
        first = [n for p in self.key(one)['pages'] for n in p['zones'].values()]
        second = [n for p in self.key(two)['pages'] for n in p['zones'].values()]
        self.assertEqual(sorted(first), sorted(second))
        self.assertNotEqual(first, second)
        ids = {p['page_id'] for p in self.key(one)['pages']} | {p['page_id'] for p in self.key(two)['pages']}
        self.assertEqual(len(ids), 6)  # 쪽 3개 x 회차 2, 모두 다름

    def test_page_id_formula(self):
        key = self.key(self.make(1, 'r1'))
        page = key['pages'][0]
        hashes = [key['crops'][str(n)] for n in page['zones'].values()]
        text = '|'.join(['1', '1', key['criteria_sha256'], key['screen_sha256'], ','.join(hashes)])
        self.assertEqual(page['page_id'], hashlib.sha256(text.encode()).hexdigest()[:16])

    def test_same_input_same_bytes(self):
        self.assertEqual(self.tree(self.make(1, 'a')), self.tree(self.make(1, 'b')))
        one = self.make(1, 'c')
        self.assertEqual(self.tree(self.make(2, 'd', one / 'key.json')), self.tree(self.make(2, 'e', one / 'key.json')))

    def test_thumbnail_crop_table_and_globals_untouched(self):
        before = (zp.crop, highres.crop, zp.article, zp.SCRIPT)
        self.write_inputs(dict(SYN_PLAN, crop='thumbnail'))
        key = self.key(self.make(1, 't'))
        self.assertEqual(len(key['crops']), 5)
        self.assertEqual(before, (zp.crop, highres.crop, zp.article, zp.SCRIPT))
        self.assertIs(make_round.CROPS['thumbnail'], zp.crop)
        self.assertIs(make_round.CROPS['highres'], highres.crop)


class RejectTest(Base):
    def assert_rejected(self, out, *args):
        code, err = self.run_main(*args)
        self.assertEqual(code, 2, err)
        self.assertFalse(out.exists())

    def test_changed_crop_rejects_second_round_before_writing(self):
        one = self.make(1, 'r1')
        image = Image.open(self.zones[1]['image']).convert('RGB')
        ImageDraw.Draw(image).rectangle([30, 40, 90, 120], fill=(200, 10, 10))  # 크롭 영역 안
        image.save(self.zones[1]['image'])
        out = self.tmp / 'r2'
        self.assert_rejected(out, self.plan_path, self.sel_path, 2, out, one / 'key.json')

    def test_pillow_change_rejects_second_round(self):
        one = self.make(1, 'r1')
        other = lambda z: highres.crop(z)[:-8] + 'AAAAAAAA'
        out = self.tmp / 'r2'
        with mock.patch.dict(make_round.CROPS, {'highres': other}):
            self.assert_rejected(out, self.plan_path, self.sel_path, 2, out, one / 'key.json')

    def test_moved_photo_rejects_second_round(self):
        one = self.make(1, 'r1')
        Path(self.zones[2]['image']).rename(self.tmp / 'moved.png')
        out = self.tmp / 'r2'
        self.assert_rejected(out, self.plan_path, self.sel_path, 2, out, one / 'key.json')

    def test_existing_folder_rejected_and_left_alone(self):
        out = self.tmp / 'taken'
        out.mkdir()
        (out / 'keep.txt').write_text('x')
        code, _ = self.run_main(self.plan_path, self.sel_path, 1, out)
        self.assertEqual(code, 2)
        self.assertEqual([p.name for p in out.iterdir()], ['keep.txt'])

    def test_argument_shape(self):
        one = self.make(1, 'r1')
        out = self.tmp / 'x'
        self.assert_rejected(out, self.plan_path, self.sel_path, 2, out)  # FIRST_KEY 없는 2차
        self.assert_rejected(out, self.plan_path, self.sel_path, 1, out, one / 'key.json')  # 1차에 FIRST_KEY
        self.assert_rejected(out, self.plan_path, self.sel_path, 3, out)

    def test_same_order_rejected(self):
        self.write_inputs(SYN_PLAN, zones=self.zones[:1])  # 구역 하나는 섞어도 같은 순서
        one = self.make(1, 'r1')
        out = self.tmp / 'r2'
        code, err = self.run_main(self.plan_path, self.sel_path, 2, out, one / 'key.json')
        self.assertEqual(code, 2)
        self.assertIn('순서가 같음', err)
        self.assertFalse(out.exists())

    def test_first_key_must_match(self):
        one = self.make(1, 'r1')
        out = self.tmp / 'r2'
        for field, value in (('criteria_sha256', '0' * 64), ('screen_sha256', '0' * 64), ('plan_sha256', '0' * 64), ('selection_sha256', '0' * 64), ('round', 2)):
            key = self.key(one)
            key[field] = value
            tampered = self.tmp / f'k_{field}.json'
            tampered.write_text(json.dumps(key))
            self.assert_rejected(out, self.plan_path, self.sel_path, 2, out, tampered)
        key = self.key(one)
        key['crops']['7001'] = '0' * 64
        tampered = self.tmp / 'k_crop.json'
        tampered.write_text(json.dumps(key))
        self.assert_rejected(out, self.plan_path, self.sel_path, 2, out, tampered)

    def test_selection_must_match_plan_and_rows(self):
        out = self.tmp / 'r1'
        sel = json.loads(self.sel_path.read_text())
        sel['plan_sha256'] = '0' * 64
        self.sel_path.write_text(json.dumps(sel))
        self.assert_rejected(out, self.plan_path, self.sel_path, 1, out)
        self.write_inputs(SYN_PLAN, zones=[dict(self.zones[0], target=1)])  # 정답 열쇠가 섞인 행
        self.assert_rejected(out, self.plan_path, self.sel_path, 1, out)
        self.write_inputs(SYN_PLAN, zones=[self.zones[0], dict(self.zones[1], n=self.zones[0]['n'])])
        self.assert_rejected(out, self.plan_path, self.sel_path, 1, out)

    def test_no_key_json_when_page_write_fails(self):
        out = self.tmp / 'r1'
        with mock.patch('tools.label_criteria.write_page', side_effect=OSError('디스크')):
            code, _ = self.run_main(self.plan_path, self.sel_path, 1, out)
        self.assertEqual(code, 2)
        self.assertFalse((out / 'key.json').exists())


class SourceTest(unittest.TestCase):
    def test_no_defaults_and_no_other_tool_edits(self):
        for name in ('screen.py', 'make_round.py'):
            text = (ROOT / 'tools/self_agreement' / name).read_text(encoding='utf-8')
            self.assertNotIn('default=', text)
            self.assertNotIn('plan.get(', text)
            self.assertNotIn('zp.crop =', text)
            self.assertIsNone(re.search(r'\b(zp|highres|blind)\.\w+\s*=[^=]', text))

    def test_one_listener_per_button(self):
        self.assertEqual(JS.read_text(encoding='utf-8').count('addEventListener'), 1)

    @unittest.skipUnless(NODE, 'node unavailable: UNVERIFIED')
    def test_node_check(self):
        done = subprocess.run([NODE, '--check', str(JS)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


@unittest.skipUnless(NODE, 'node unavailable: answer text UNVERIFIED')
class AnswerTextTest(Base):
    def press(self, page_file, presses):
        from test_relabel_zone_round_trip import run
        return run(page_file.read_text(encoding='utf-8'), presses, alln=False)

    def test_header_lines_and_answers(self):
        one = self.make(1, 'r1')
        key = self.key(one)
        page = key['pages'][0]
        got, error = self.press(one / page['file'], [dict(card=0, v='결함'), dict(card=1, v='불가'), dict(card=0, v='정상'), dict(id='copy')])
        self.assertEqual(error, '')
        lines = got['out'].split('\n')
        self.assertEqual(lines[0], '# 화면=' + page['page_id'])
        self.assertRegex(lines[1], r'^# 제출시각=\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+09:00$')
        self.assertEqual(lines[2:], ['z1=정상', 'z2=불가'])
        self.assertIn('복사됨', got['msg'])

    def test_untouched_stays_unconfirmed_and_second_round_page(self):
        one, two = self.rounds()
        key = self.key(two)
        page = key['pages'][2]  # 마지막 쪽은 구역 하나
        got, _ = self.press(two / page['file'], [])
        lines = got['out'].split('\n')
        self.assertEqual(lines[0], '# 화면=' + page['page_id'])
        self.assertEqual(lines[2:], ['z5=미확인'])
        self.assertNotEqual(page['page_id'], self.key(one)['pages'][2]['page_id'])


if __name__ == '__main__':
    unittest.main()
