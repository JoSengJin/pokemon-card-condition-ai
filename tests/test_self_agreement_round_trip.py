"""계약 C(self-agreement-import) 시험: 누른 것 = 가져온 것(두 회차), 거절 시 원본 보존. 합성 fixture만 쓴다.

숫자·문장·ID는 모두 합성값이며 제안값이나 사람이 정한 값이 아니다. 실제 사진·라벨·artifacts는 열지 않는다.
왕복 시험은 B가 만든 화면의 실제 screen.js를 node로 돌린다. node가 없으면 그 시험은 건너뛰고 "미검증"이다.
"""
import contextlib
import io
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from test_relabel_zone_round_trip import run  # noqa: E402
from test_self_agreement_pages import Base  # noqa: E402
from tools.self_agreement import answers, import_round  # noqa: E402

NODE = shutil.which('node')
WANT = {7001: '정상', 7002: '결함', 7003: '불가', 7004: '미확인', 7005: '결함'}  # n -> 누른 최종 값(합성). 7005는 정상을 먼저 눌러 바꿈
STATEMENT = '합성 문장'  # Base의 SYN_PLAN judge_statement와 같다


class ImportBase(Base):
    def setUp(self):
        super().setUp()
        self.statement = self.tmp / 'statement.txt'
        self.statement.write_text(STATEMENT + '\n', encoding='utf-8')

    def importing(self, folder, out, files, statement=None):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = import_round.main([str(self.plan_path), str(folder), str(statement or self.statement), str(out)] + [str(f) for f in files])
        return code, err.getvalue()

    def typed(self, folder, tweak=None):
        """회차 폴더의 쪽마다 화면이 만드는 꼴의 글을 직접 만들어 파일로 쓴다(node 불필요). tweak(page_no, lines) -> lines."""
        files = []
        for i, page in enumerate(self.key(folder)['pages']):
            lines = [f'# 화면={page["page_id"]}', '# 제출시각=2026-12-01T10:00:00+09:00'] + [f'{z}={WANT[n]}' for z, n in page['zones'].items()]
            path = self.tmp / f'typed-{len(list(self.tmp.iterdir()))}-{i}.txt'  # 호출마다 새 파일(앞 호출의 파일을 덮지 않음)
            path.write_bytes(('\n'.join(tweak(i, lines) if tweak else lines) + '\n').encode())
            files.append(path)
        return files

    def assert_kept(self, out, files):
        for f in files:
            raw = out / 'raw' / f'{answers.hashlib.sha256(Path(f).read_bytes()).hexdigest()}.txt'
            self.assertEqual(raw.read_bytes(), Path(f).read_bytes())
            self.assertEqual(raw.stat().st_mode & 0o777, 0o444)

    def reject(self, folder, files, needle=None, statement=None):
        out = self.tmp / f'out-{len(list(self.tmp.iterdir()))}'
        code, err = self.importing(folder, out, files, statement)
        self.assertEqual(code, 2, err)
        self.assertEqual(list(out.glob('round*.json')), [])
        self.assert_kept(out, files)
        if needle:
            self.assertIn(needle, err)
        return out


@unittest.skipUnless(NODE, 'node unavailable: round trip UNVERIFIED')
class RoundTripTest(ImportBase):
    def pressed(self, folder):
        """실제 screen.js로 WANT를 누르고(7005는 바꿔 누름, 7004는 안 누름) 나온 글을 파일로 쓴다."""
        files = []
        for i, page in enumerate(self.key(folder)['pages']):
            presses = []
            for card, n in enumerate(page['zones'].values()):
                if WANT[n] == '결함' and n == 7005:
                    presses.append(dict(card=card, v='정상'))
                if WANT[n] != '미확인':
                    presses.append(dict(card=card, v=WANT[n]))
            presses.append(dict(id='copy'))
            got, error = run((folder / page['file']).read_text(encoding='utf-8'), presses, alln=False)
            self.assertEqual(error, '')
            self.assertIn('복사됨', got['msg'])
            path = self.tmp / f'press-{folder.name}-{i}.txt'
            path.write_text(got['out'], encoding='utf-8')
            files.append(path)
        return files

    def test_both_rounds_pressed_equals_imported(self):
        one, two = self.rounds()
        orders = []
        for folder in (one, two):
            files = self.pressed(folder)
            out = self.tmp / f'out-{folder.name}'
            code, err = self.importing(folder, out, files)
            self.assertEqual(code, 0, err)
            record = json.loads((out / f'round{self.key(folder)["round"]}.json').read_text(encoding='utf-8'))
            self.assertEqual(record['answers'], {str(n): v for n, v in WANT.items()})  # 누른 값·n이 그대로
            self.assertIs(record['judge_confirmed'], True)
            self.assertEqual(record['statement'], STATEMENT)
            key = self.key(folder)
            self.assertEqual({p['page_id'] for p in key['pages']}, set(record['submitted']))
            self.assertTrue(all(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+09:00', s) for s in record['submitted'].values()))
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['raw', f'round{key["round"]}.json'])
            self.assert_kept(out, files)
            orders.append([n for p in key['pages'] for n in p['zones'].values()])
        self.assertNotEqual(orders[0], orders[1])  # 2차는 순서가 다른데도 같은 n에 같은 값이 돌아옴

    def test_untouched_stays_unconfirmed_and_unavailable_kept(self):
        one = self.make(1, 'r1')
        out = self.tmp / 'o'
        self.assertEqual(self.importing(one, out, self.pressed(one))[0], 0)
        answers_ = json.loads((out / 'round1.json').read_text(encoding='utf-8'))['answers']
        self.assertEqual((answers_['7003'], answers_['7004']), ('불가', '미확인'))


class RejectTest(ImportBase):
    def test_header_lines(self):
        one = self.make(1, 'r1')
        self.reject(one, self.typed(one, lambda i, l: [l[0]] + l[2:]), '제출시각')  # 시각 줄 없음
        self.reject(one, self.typed(one, lambda i, l: [l[0], l[1].replace('+09:00', '')] + l[2:]), '시간대')
        self.reject(one, self.typed(one, lambda i, l: l[2:]), '"# 화면="')  # # 줄을 지우고 붙임: 무엇이 빠졌는지 안내
        out = self.reject(one, self.typed(one, lambda i, l: l[2:]), '"# 제출시각="')
        self.assertEqual(len(list((out / 'raw').iterdir())), 3)

    def test_statement_missing_or_one_char_off_then_later_succeeds(self):
        one = self.make(1, 'r1')
        files = self.typed(one)
        out = self.reject(one, files, '주체 확인 문장이 없음', statement='-')
        self.reject(one, files, 'No such file', statement=self.tmp / 'nowhere.txt')
        off = self.tmp / 'off.txt'
        off.write_text(STATEMENT + '。', encoding='utf-8')
        self.reject(one, files, '다름', statement=off)
        before = {p.name: p.read_bytes() for p in (out / 'raw').iterdir()}
        code, err = self.importing(one, out, files)  # 문장이 나중에 오면 같은 원본·같은 OUT으로 성공
        self.assertEqual(code, 0, err)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (out / 'raw').iterdir()})
        self.assertEqual(self.importing(one, out, files)[0], 2)  # 이미 있는 기록은 덮지 않음

    def test_surrounding_whitespace_of_statement_ignored(self):
        one = self.make(1, 'r1')
        padded = self.tmp / 'padded.txt'
        padded.write_text('\n  ' + STATEMENT + '  \r\n', encoding='utf-8')
        self.assertEqual(self.importing(one, self.tmp / 'ok', self.typed(one), padded)[0], 0)

    def test_wrong_content(self):
        one, two = self.rounds()
        files = self.typed(one)
        self.reject(one, [Path(f) for f in self.typed(one, lambda i, l: ['# 화면=' + 'f' * 16] + l[1:])], '화면의 글이 아님')  # 다른 화면
        self.reject(one, self.typed(one, lambda i, l: l[:-1]), '빠짐')  # 줄 하나 빠짐
        self.reject(one, self.typed(one, lambda i, l: l + [l[-1]]), '답 줄')  # 중복 번호
        self.reject(one, self.typed(one, lambda i, l: l[:-1] + [l[-1].split('=')[0] + '=모름']), '모르는 값')
        self.reject(one, self.typed(one, lambda i, l: l[:-1] + [l[-1].split('=')[0].replace('z', 'q') + '=정상']), '답 줄')
        self.reject(one, files[:-1], '넣지 않은 쪽')  # 쪽 하나 빠짐
        self.reject(one, files + [files[0]], '두 번')  # 같은 쪽 두 번
        self.reject(two, files, '화면의 글이 아님')  # 1차 글을 2차로
        self.reject(one, self.typed(two), '화면의 글이 아님')  # 2차 글을 1차로

    def test_crlf_and_trailing_spaces_keep_values(self):
        one = self.make(1, 'r1')
        files = self.typed(one)
        for f in files:
            f.write_bytes(re.sub(rb'\n', b'  \r\n', f.read_bytes()))
        out = self.tmp / 'crlf'
        self.assertEqual(self.importing(one, out, files)[0], 0)
        got = json.loads((out / 'round1.json').read_text(encoding='utf-8'))['answers']
        self.assertEqual(got, {str(n): v for n, v in WANT.items()})
        self.assert_kept(out, files)  # 원본은 CRLF·공백 그대로

    def test_changed_criteria_record_is_rejected(self):
        one = self.make(1, 'r1')
        record = one / (self.key(one)['pages'][0]['file'] + '.criteria.json')
        data = json.loads(record.read_text(encoding='utf-8'))
        data['criteria_sha256'] = '0' * 64
        record.write_text(json.dumps(data), encoding='utf-8')
        self.reject(one, self.typed(one), 'key.json과 다름')

    def test_other_plan_or_missing_key_rejected(self):
        one = self.make(1, 'r1')
        files = self.typed(one)
        (self.tmp / 'x').mkdir()
        self.reject(self.tmp / 'x', files, 'key.json')
        self.plan_path.write_text(self.plan_path.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        self.reject(one, files, 'plan_sha256')

    def test_argument_shape(self):
        self.assertEqual(self.importing(self.tmp, self.tmp / 'o', [])[0], 2)


class ParseTest(unittest.TestCase):
    def test_values_kept_as_is(self):
        head = '# 화면=abc\n# 제출시각=2026-12-01T10:00:00+09:00\n'
        self.assertEqual(answers.parse(head + 'z1=불가\nz2=미확인\n'), ('abc', '2026-12-01T10:00:00+09:00', {'z1': '불가', 'z2': '미확인'}))
        self.assertEqual(answers.parse(head.replace('\n', '  \r\n') + 'z1=정상 \r\n')[2], {'z1': '정상'})
        for bad in ('2026-13-01T10:00:00+09:00', '2026-12-01 10:00:00+09:00', '2026-12-01T10:00:00Z'):
            with self.assertRaises(ValueError):
                answers.parse(f'# 화면=abc\n# 제출시각={bad}\nz1=정상')


if __name__ == '__main__':
    unittest.main()
