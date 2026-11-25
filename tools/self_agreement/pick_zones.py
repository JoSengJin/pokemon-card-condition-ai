"""시드 구역 선정 (계약 A).

실행: schema 1: python -m tools.self_agreement.pick_zones PLAN POPULATION EXCLUDE ERROR_LAYER|- OUT
      schema 2: ... PLAN POPULATION EXCLUDE ERROR_LAYER|- FP_LAYER|- OUT
종료 0 = 새 selection.json 1개, 2 = 아무것도 쓰지 않음. 사진 파일은 열지 않는다
(image는 경로 문자열일 뿐). 시드·수 같은 값은 plan.json에서만 읽는다.
난수는 random()만 쓴다(샘플·섞기 함수는 파이썬 버전에 따라 달라질 수 있어 쓰지 않음).
"""
import json
import random
import sys
from operator import itemgetter

from . import plan as cfg

ROW_KEYS = {'id', 'group', 'area', 'image', 'box'}


def rows(path, sha, kind):
    """해시가 plan의 값과 같은 파일만 읽는다. kind='rows'면 행 목록, 'groups'면 group 문자열 목록."""
    if cfg.file_sha(path) != sha:
        raise ValueError('%s: SHA-256이 plan.json과 다름' % path)
    with open(path, 'rb') as f:
        data = json.loads(f.read().decode('utf-8'))
    if not isinstance(data, list):
        raise ValueError('%s: 목록이 아님' % path)
    if kind == 'groups':
        if not all(isinstance(g, str) for g in data):
            raise ValueError('%s: group 문자열 목록이 아님' % path)
        return data
    owner, ids = {}, set()
    for r in data:
        if not isinstance(r, dict) or r.keys() != ROW_KEYS:
            raise ValueError('%s: 행 열쇠가 정확히 %s가 아님' % (path, sorted(ROW_KEYS)))
        if not all(isinstance(r[k], str) and r[k] != '' for k in ('id', 'group', 'image')):
            raise ValueError('%s: id·group·image는 비지 않은 문자열이어야 함' % path)
        if r['id'] in ids:
            raise ValueError('%s: id 중복 %s' % (path, r['id']))
        ids.add(r['id'])
        if owner.setdefault(r['image'], r['group']) != r['group']:
            raise ValueError('%s: 같은 image가 다른 group으로 들어옴 %s' % (path, r['image']))
    return data


def layer_rows(path, sha, excluded):
    """오류 층·오탐 층 파일을 읽고 모든 카드가 제외 목록에 있는지 본다."""
    got = rows(path, sha, 'rows')
    if any(r['group'] not in excluded for r in got):
        raise ValueError('%s: 층 카드가 제외 목록에 없음' % path)
    return got


def choose(rows_, excluded, count, rng):
    """제외 카드를 뺀 카드 count장을 같은 확률로 고르고, 카드마다 구역 하나를 고른다."""
    by_group = {}
    for r in sorted(rows_, key=itemgetter('id')):
        if r['group'] not in excluded:
            by_group.setdefault(r['group'], []).append(r)
    if len(by_group) < count:
        raise ValueError('선정 가능한 카드 %d장이 main_count %d보다 적음' % (len(by_group), count))
    drawn = sorted((rng.random(), g) for g in sorted(by_group))[:count]
    picked = [by_group[g] for _, g in sorted(drawn, key=itemgetter(1))]
    return [zs[int(rng.random() * len(zs))] for zs in picked]


def number(main_rows, error_rows, fp_rows, rng):
    """주·오류·오탐 층을 이어 붙여 섞은 순서로 번호 n=1..을 매긴다."""
    items = ([('main', r) for r in main_rows] + [('error', r) for r in error_rows]
             + [('fp', r) for r in fp_rows])
    owner, ids = {}, set()
    for _, r in items:
        if owner.setdefault(r['image'], r['group']) != r['group']:
            raise ValueError('같은 image가 다른 group으로 두 번 들어옴 %s' % r['image'])
        if r['id'] in ids:
            raise ValueError('층을 합쳐 id 중복 %s' % r['id'])
        ids.add(r['id'])
    order = sorted((rng.random(), i) for i in range(len(items)))
    return [dict(n=n, layer=items[i][0], **items[i][1]) for n, (_, i) in enumerate(order, 1)]


def main(argv):
    """종료 코드를 돌려준다. 0=selection.json 1개 작성, 2=아무것도 쓰지 않음."""
    try:
        if len(argv) not in (5, 6):
            raise ValueError('인자: PLAN POPULATION EXCLUDE ERROR_LAYER|- [FP_LAYER|-] OUT')
        p, sha = cfg.load(argv[0])
        if len(argv) != 4 + p['schema']:
            raise ValueError('인자 수가 plan.json의 schema와 다름(schema 1은 5개, 2는 6개)')
        fp_sha, fp_count = (p['fp_layer_sha256'], p['fp_count']) if p['schema'] == 2 else (None, 0)
        pop = rows(argv[1], p['population_sha256'], 'rows')
        excluded = set(rows(argv[2], p['exclude_sha256'], 'groups'))
        if (argv[3] == '-') != (p['error_layer_sha256'] is None):
            raise ValueError('ERROR_LAYER 인자와 plan.json의 error_layer_sha256 null 여부가 다름')
        if (argv[-2] == '-') != (fp_sha is None) and p['schema'] == 2:
            raise ValueError('FP_LAYER 인자와 plan.json의 fp_layer_sha256 null 여부가 다름')
        err = [] if argv[3] == '-' else layer_rows(argv[3], p['error_layer_sha256'], excluded)
        if len(err) < p['error_count']:
            raise ValueError('오류 층 행 %d개가 error_count %d보다 적음' % (len(err), p['error_count']))
        err = err[:p['error_count']]
        fp = [] if fp_sha is None else layer_rows(argv[4], fp_sha, excluded)
        cards = {}
        for r in fp:
            cards.setdefault(r['group'], []).append(r)
        if len(fp) != fp_count:
            raise ValueError('오탐 층 행 %d개가 fp_count %d와 다름' % (len(fp), fp_count))
        if any(len(z) != p['fp_zones_per_card'] or len({r['area'] for r in z}) != len(z)
               or len({r['image'] for r in z}) != 1 for z in cards.values()):
            raise ValueError('오탐 층 카드는 구역 수가 fp_zones_per_card이고 area가 서로 다르며 사진이 하나여야 함')
        if cards.keys() & {r['group'] for r in err}:
            raise ValueError('오류 층과 오탐 층이 같은 카드를 가짐')
        rng = random.Random(p['seed_selection'])
        main_rows = choose(pop, excluded, p['main_count'], rng)
        zones = number(main_rows, err, fp, rng)
        cfg.write_new(argv[-1], {'plan_sha256': sha, 'zones': zones})
    except (ValueError, OSError) as e:
        print('오류: ' + str(e).replace('\n', ' '), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
