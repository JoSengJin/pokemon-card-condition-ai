"""자기 일치도 측정의 plan.json 검사와 새 파일 쓰기 (계약 A).

값은 모두 plan.json에서만 온다. 이 파일에는 기본값이 없고, 열쇠가 없거나
모르는 열쇠가 있으면 거절한다. 실패는 ValueError/OSError로 알린다.
"""
import hashlib
import json
import math
import re
from fractions import Fraction

HEX = re.compile(r'[0-9a-f]{64}')
DEC = re.compile(r'[0-9]+(\.[0-9]+)?')
# 열쇠: (종류, null 허용). 설계 1.1 표와 같다. 종류 뜻은 check 안에 있다.
SPEC = {
    'schema': ('one', False), 'approval_ref': ('text', False),
    'cell': ('cell', False), 'new_first_round': ('true', False),
    'population_sha256': ('sha', False), 'exclude_sha256': ('sha', False),
    'error_layer_sha256': ('sha', True), 'main_count': ('pos', False),
    'error_count': ('nonneg', False), 'strata': ('none', True),
    'per_page': ('pos', False), 'crop': ('crop', False),
    'seed_selection': ('int', False), 'seed_order2': ('int', False),
    'seed_bootstrap': ('int', False), 'bootstrap_draws': ('pos', False),
    'min_interval_hours': ('hours', False),
    'max_interval_hours': ('hours', True), 'judge_statement': ('text', False),
    'p_min': ('p', False), 'direction_min_count': ('pos', True),
    'direction_alpha': ('alpha', True), 'reference_zone_count': ('pos', True),
}
# schema 2: 오탐 층·카드 단위 열쇠를 더한 집합(설계 3.1). schema 1의 SPEC은 그대로 둔다.
SPEC2 = dict(SPEC, schema=('two', False), layers=('layers', False),
             fp_layer_sha256=('sha', True), fp_count=('nonneg', False),
             fp_zones_per_card=('pos', True), card_rule=('rule', True),
             card_flip_cut=('pos', True))
INT_MIN = {'pos': 1, 'nonneg': 0}
ONE = {'one': 1, 'two': 2}
LAYERS = (['main'], ['main', 'error'], ['main', 'fp'], ['main', 'error', 'fp'])


def check(plan):
    """plan 사전 전체를 검사한다. 어긋나면 ValueError(이유 한 줄)."""
    if not isinstance(plan, dict):
        raise ValueError('plan.json: 최상위가 객체가 아님')
    ver = plan['schema'] if 'schema' in plan else None
    if type(ver) is not int or ver not in (1, 2):  # true는 int가 아니라 여기서 걸린다
        raise ValueError('plan.json: schema가 1 또는 2가 아님')
    spec = SPEC if ver == 1 else SPEC2
    if spec.keys() - plan.keys():
        raise ValueError('plan.json: 빠진 열쇠 %s' % sorted(spec.keys() - plan.keys()))
    if plan.keys() - spec.keys():
        raise ValueError('plan.json: 모르는 열쇠 %s' % sorted(plan.keys() - spec.keys()))
    for key, (kind, null_ok) in spec.items():
        v = plan[key]
        if v is None:
            if not null_ok:
                raise ValueError('plan.json: %s는 null 불가' % key)
            continue
        if kind in INT_MIN:
            good = type(v) is int and v >= INT_MIN[kind]
        elif kind in ONE:
            good = type(v) is int and v == ONE[kind]
        elif kind == 'layers':
            good = v in LAYERS
        elif kind == 'rule':
            good = v == 'any_defect_unknown_blocks'
        elif kind == 'int':
            good = type(v) is int
        elif kind == 'text':
            good = isinstance(v, str) and v.strip() != ''
        elif kind == 'cell':
            good = v == '모서리'
        elif kind == 'true':
            good = v is True
        elif kind == 'sha':
            good = isinstance(v, str) and HEX.fullmatch(v) is not None
        elif kind == 'crop':
            good = v in ('highres', 'thumbnail')
        elif kind == 'hours':
            good = type(v) in (int, float) and math.isfinite(v) and v >= 0
        elif kind == 'p':
            good = isinstance(v, str) and DEC.fullmatch(v) is not None and 0 < Fraction(v) < Fraction(1, 2)
        elif kind == 'alpha':
            good = isinstance(v, str) and DEC.fullmatch(v) is not None and 0 < Fraction(v) < 1
        else:  # 'none': strata는 null만 구현
            good = False
        if not good:
            raise ValueError('plan.json: %s 값이 허용 범위 밖' % key)
    seeds = [plan['seed_selection'], plan['seed_order2'], plan['seed_bootstrap']]
    if len(set(seeds)) != 3:
        raise ValueError('plan.json: 세 시드가 서로 달라야 함')
    if (plan['error_layer_sha256'] is None) != (plan['error_count'] == 0):
        raise ValueError('plan.json: error_layer_sha256 null과 error_count 0은 함께여야 함')
    if (plan['direction_min_count'] is None) != (plan['direction_alpha'] is None):
        raise ValueError('plan.json: direction_min_count와 direction_alpha는 함께 null이거나 함께 값')
    if ver == 2:
        fp, per = 'fp' in plan['layers'], plan['fp_zones_per_card']
        if any(f != fp for f in (plan['fp_layer_sha256'] is not None, plan['fp_count'] > 0,
                                 per is not None, plan['card_rule'] is not None)):
            raise ValueError('plan.json: layers의 fp와 fp_layer_sha256·fp_count·fp_zones_per_card·card_rule의 null 여부가 어긋남')
        if not fp and plan['card_flip_cut'] is not None:
            raise ValueError('plan.json: fp 층이 없으면 card_flip_cut은 null이어야 함')
        if fp and plan['fp_count'] % per:
            raise ValueError('plan.json: fp_count는 fp_zones_per_card의 배수여야 함')
        if ('error' in plan['layers']) != (plan['error_layer_sha256'] is not None):
            raise ValueError('plan.json: layers의 error와 error_layer_sha256 null 여부가 어긋남')
    top = plan['max_interval_hours']
    if top is not None and top < plan['min_interval_hours']:
        raise ValueError('plan.json: max_interval_hours가 min_interval_hours보다 작음')


def load(path):
    """plan.json을 한 번 읽어 검사하고 (plan, 파일 SHA-256)을 돌려준다."""
    with open(path, 'rb') as f:
        data = f.read()
    plan = json.loads(data.decode('utf-8'))
    check(plan)
    return plan, hashlib.sha256(data).hexdigest()


def file_sha(path):
    """파일 바이트의 SHA-256(16진 소문자)."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def write_new(path, data):
    """data를 JSON으로 새 파일에만 쓴다. 이미 있으면 FileExistsError."""
    text = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
    with open(path, 'x', encoding='utf-8') as f:
        f.write(text)
