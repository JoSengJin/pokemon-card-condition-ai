"""시드 구역 선정 (계약 A).

실행: python -m tools.self_agreement.pick_zones PLAN POPULATION EXCLUDE ERROR_LAYER|- OUT
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


def number(main_rows, error_rows, rng):
    """주 층과 오류 층을 합쳐 섞은 순서로 번호 n=1..을 매긴다."""
    items = [('main', r) for r in main_rows] + [('error', r) for r in error_rows]
    owner = {}
    for _, r in items:
        if owner.setdefault(r['image'], r['group']) != r['group']:
            raise ValueError('같은 image가 다른 group으로 두 번 들어옴 %s' % r['image'])
    order = sorted((rng.random(), i) for i in range(len(items)))
    return [dict(n=n, layer=items[i][0], **items[i][1]) for n, (_, i) in enumerate(order, 1)]


def main(argv):
    """종료 코드를 돌려준다. 0=selection.json 1개 작성, 2=아무것도 쓰지 않음."""
    try:
        if len(argv) != 5:
            raise ValueError('인자: PLAN POPULATION EXCLUDE ERROR_LAYER|- OUT')
        p, sha = cfg.load(argv[0])
        pop = rows(argv[1], p['population_sha256'], 'rows')
        excluded = set(rows(argv[2], p['exclude_sha256'], 'groups'))
        if (argv[3] == '-') != (p['error_layer_sha256'] is None):
            raise ValueError('ERROR_LAYER 인자와 plan.json의 error_layer_sha256 null 여부가 다름')
        err = [] if argv[3] == '-' else rows(argv[3], p['error_layer_sha256'], 'rows')
        if any(r['group'] not in excluded for r in err):
            raise ValueError('오류 층 카드가 제외 목록에 없음')
        if len(err) < p['error_count']:
            raise ValueError('오류 층 행 %d개가 error_count %d보다 적음' % (len(err), p['error_count']))
        rng = random.Random(p['seed_selection'])
        main_rows = choose(pop, excluded, p['main_count'], rng)
        zones = number(main_rows, err[:p['error_count']], rng)
        cfg.write_new(argv[4], {'plan_sha256': sha, 'zones': zones})
    except (ValueError, OSError) as e:
        print('오류: ' + str(e).replace('\n', ' '), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
