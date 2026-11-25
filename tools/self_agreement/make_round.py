"""두 회차 화면 만들기 (계약 B). python -m tools.self_agreement.make_round PLAN SELECTION ROUND OUT_DIR [FIRST_KEY]

2차는 FIRST_KEY가 필수이고, 크롭·기준 문구·화면 틀이 1차와 다르면 아무것도 쓰기 전에 거절한다(종료 2).
key.json은 마지막에 쓴다. 없는 폴더는 가져오기(C)가 거절한다.
"""
import base64
import json
import random
import sys
from operator import itemgetter
from pathlib import Path

from tools import label_criteria as lc
from tools import relabel_corner_highres_pages as highres
from tools import relabel_zone_pages as zp
from tools.self_agreement import plan as cfg
from tools.self_agreement import screen

CROPS = {'highres': highres.crop, 'thumbnail': zp.crop}  # import 시점 참조. 남의 전역은 바꾸지 않는다
ZONE_KEYS = {'n', 'layer', 'id', 'group', 'area', 'image', 'box'}


def ordered(zones, round_no, seed):
    """1차는 번호 순, 2차는 seed로 섞은 순서. 구역 행 형식도 여기서 검사한다."""
    if not zones or any(set(z) != ZONE_KEYS or type(z['n']) is not int for z in zones) or len({z['n'] for z in zones}) != len(zones):
        raise ValueError('selection.json: 구역 행 형식 또는 번호가 어긋남')
    rows = sorted(zones, key=itemgetter('n'))
    if round_no == 2:
        random.Random(seed).shuffle(rows)
    return rows


def shoot(zones, crop_name):
    """{n: (jpeg base64, 디코딩한 바이트의 SHA-256)}. 사진을 여는 곳은 여기뿐이다."""
    shots = {}
    for z in zones:
        b64 = CROPS[crop_name](z)
        shots[z['n']] = (b64, lc.sha(base64.b64decode(b64)))
    return shots


def same_screen(first_key, key, order):
    """2차 열쇠가 1차와 같은 입력·기준·화면·크롭이고 순서만 다른지. 어긋나면 ValueError."""
    for name in ('plan_sha256', 'selection_sha256', 'criteria_sha256', 'screen_sha256', 'crops'):
        if first_key.get(name) != key[name]:
            raise ValueError(f'2차 거절: 1차와 {name}가 다름')
    if first_key.get('round') != 1:
        raise ValueError('2차 거절: FIRST_KEY가 1차 열쇠가 아님')
    first = [n for p in first_key['pages'] for n in p['zones'].values()]
    if sorted(first) != sorted(order):
        raise ValueError('2차 거절: 구역 집합이 1차와 다름')
    if first == order:
        raise ValueError('2차 거절: 1차와 순서가 같음')


def write(out, key, zones, shots, per_page):
    """새 폴더에 쪽(+기준 기록)을 쓰고 key.json을 마지막에 쓴다. 이미 있는 폴더면 아무것도 쓰기 전에 FileExistsError."""
    out = Path(out)
    out.mkdir()
    chunks = [zones[i:i + per_page] for i in range(0, len(zones), per_page)]
    for page_no, chunk in enumerate(chunks, 1):
        start = (page_no - 1) * per_page + 1
        pid = screen.page_id(key['round'], page_no, key['crop_name'], [shots[z['n']][1] for z in chunk])
        body = ''.join(screen.article(start + k, shots[z['n']][0]) for k, z in enumerate(chunk))
        text = screen.page_text(f'구역 판정 {page_no}/{len(chunks)}', pid, body)
        lc.write_page(out / f'zones-{page_no}.html', text, screen.INSTRUCTIONS, body)
        key['pages'].append(dict(page_id=pid, file=f'zones-{page_no}.html', zones={f'z{start + k}': z['n'] for k, z in enumerate(chunk)}))
    del key['crop_name']
    cfg.write_new(out / 'key.json', key)


def main(argv):
    try:
        if len(argv) not in (4, 5) or argv[2] not in ('1', '2') or (len(argv) == 5) != (argv[2] == '2'):
            raise ValueError('사용법: PLAN SELECTION ROUND(1|2) OUT_DIR [FIRST_KEY: 2차만, 필수]')
        plan, plan_sha = cfg.load(argv[0])
        selection = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
        if selection.get('plan_sha256') != plan_sha:
            raise ValueError('selection.json의 plan_sha256이 plan.json과 다름')
        round_no = int(argv[2])
        zones = ordered(selection['zones'], round_no, plan['seed_order2'])
        shots = shoot(zones, plan['crop'])
        key = dict(plan_sha256=plan_sha, selection_sha256=cfg.file_sha(argv[1]), round=round_no, criteria_sha256=screen.CRITERIA_SHA,
                   screen_sha256=screen.screen_sha(plan['crop']), crops={str(n): s[1] for n, s in sorted(shots.items())}, pages=[], crop_name=plan['crop'])
        if round_no == 2:
            first = json.loads(Path(argv[4]).read_text(encoding='utf-8'))
            same_screen(first, key, [z['n'] for z in zones])
        write(argv[3], key, zones, shots, plan['per_page'])
    except (ValueError, KeyError, TypeError, OSError) as error:
        print('거절:', error, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
