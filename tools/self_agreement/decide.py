"""제안서 11절 (d) 다음 행동 표: 위에서부터 먼저 맞는 한 행만 (계약 D).

사람이 정하는 값(p_min, 방향 문턱, 간격)은 plan 인자에서만 읽는다.
아래 세 상수는 사람 값이 아니라 발효된 기존 값이며 시험이 LABELING_PROTOCOL.md와 대조한다.
"""
from datetime import datetime, timedelta
from fractions import Fraction

MIN_N, WARN, GOAL = 30, Fraction('0.60'), Fraction('0.80')
ROW_TEXT = {
    1: '정식 값 없음. 이유 보고',
    2: '미측정. 자료 추가는 새 승인',
    3: '기준 이동 의심. 기준 문구·제시 방식 점검 제안. e를 쓰지 않음',
    4: '모델 가설 전에 기준 문구·제시 방식 점검',
    5: '경고선 위·목표선 아래로 보고. e 참고 폭을 다시 씀',
    6: '목표선 충족으로 보고. 기억·쉬운 구역·타당도 한계를 유지',
}


def invalid(plan, shas, first, second):
    """1행 조건의 이유 목록(빈 목록이면 해당 없음). shas=(plan_sha, selection_sha)."""
    out = []
    for name, rd in (('1차', first), ('2차', second)):
        for key, want in (('plan_sha256', shas[0]), ('selection_sha256', shas[1])):
            if rd[key] != want:
                out.append('해시 불일치: %s %s' % (name, key))
        if rd.get('judge_confirmed') is not True:
            out.append('주체 미확인: %s' % name)
    for key, label in (('criteria_sha256', '기준 문구 해시'), ('screen_sha256', '화면 해시'), ('crops', '크롭 해시')):
        if first[key] != second[key]:
            out.append('%s 불일치' % label)
    t1 = [datetime.fromisoformat(v) for v in first['submitted'].values()]
    t2 = [datetime.fromisoformat(v) for v in second['submitted'].values()]
    if not t1 or not t2 or any(t.tzinfo is None for t in t1 + t2):
        raise ValueError('제출 시각이 없거나 시간대가 없음')
    if min(t2) - max(t1) < timedelta(hours=plan['min_interval_hours']):
        out.append('간격 이탈: 하한 %s시간 미만' % plan['min_interval_hours'])
    top = plan['max_interval_hours']
    if top is not None and max(t2) - min(t1) > timedelta(hours=top):
        out.append('간격 이탈: 상한 %s시간 초과' % top)
    return out


def skewed(table, p_min):
    """한 회차의 결함 비율이 p_min 미만 또는 1-p_min 초과(경계는 쏠림 아님). 이유 문자열 또는 None."""
    nn, dd, b, c = table
    n, p = nn + dd + b + c, Fraction(p_min)
    for who, k in (('1차', dd + c), ('2차', dd + b)):
        if Fraction(k, n) < p or Fraction(k, n) > 1 - p:
            return '값 쏠림: %s 결함 %d/%d' % (who, k, n)
    return None


def direction(b, c, p, plan):
    """3행: 문턱이 있고 b+c가 최소 건수 이상이며 정확 양측 p가 alpha 미만. 문턱이 null이면 False."""
    if plan['direction_min_count'] is None:
        return False
    return b + c >= plan['direction_min_count'] and p < Fraction(plan['direction_alpha'])


def row(reasons, table, kappa, plan, p):
    """(행 번호, 이유 목록). reasons는 invalid의 결과, kappa는 Fraction 또는 None."""
    if reasons:
        return 1, list(reasons)
    n = sum(table)
    why = ['확정 쌍 %d < %d' % (n, MIN_N)] if n < MIN_N else []
    if kappa is None:
        why.append('카파 정의 불가')
    if n >= MIN_N and skewed(table, plan['p_min']):
        why.append(skewed(table, plan['p_min']))
    if why:
        return 2, why
    if direction(table[2], table[3], p, plan):
        return 3, ['불일치 방향 쏠림: b=%d c=%d p=%s' % (table[2], table[3], p)]
    note = ['3행 미적용'] if plan['direction_alpha'] is None else []
    if kappa < WARN:
        return 4, ['카파 %s < %s' % (kappa, WARN)] + note
    if kappa < GOAL:
        return 5, ['카파 %s: %s 이상 %s 미만' % (kappa, WARN, GOAL)] + note
    return 6, ['카파 %s ≥ %s' % (kappa, GOAL)] + note
