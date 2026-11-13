"""D3 실물 단위 사건률(누락/오탐)과 단측 95% Wilson 상한. D2 저장 점수·동결 임계만 사용, 새 추론 0.
사건 정의(결과 전에 고정, 두 변형을 모두 보고하고 고르지 않는다):
 - 관대(L): 누락=결함 구역 중 점수<낮음임계가 하나 이상, 오탐=정상 실물 구역 중 점수≥높음임계가 하나 이상.
 - 엄격(S): 단일 임계 t(=높음임계)로 누락=결함 구역 중 점수<t가 하나 이상, 오탐=점수≥t가 하나 이상.
 관찰제한은 실물(면)당 1행이므로 임계 0.5 단일."""
import json, math
Z = 1.6448536269514722
def upper(k, n):
    if n == 0: return None
    p = k / n; d = 1 + Z * Z / n; c = p + Z * Z / (2 * n); h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return (c + h) / d
E_ = 'artifacts/experiments/'
SETS = {'C1_edge': ('20261103T135058-2510aba4', .31, .54), 'C2_corner': ('20261103T131123-7fa5d398', .281, .509),
        'C3_surface_holdout2': ('20261103T212927-a5af889c', .213, .468), 'C5_obslimit': ('20261103T131822-ed39c990', .5, .5)}
out = {}
for name, (eid, lo, hi) in SETS.items():
    o = json.load(open(E_ + eid + '/observations.json')); g = {}
    for r, s in zip(o['rows'], o['scores']): g.setdefault(r['group'], []).append((r['target'], s))
    pos = {k: v for k, v in g.items() if any(t for t, _ in v)}; neg = {k: v for k, v in g.items() if not any(t for t, _ in v)}
    res = dict(objects=len(g), positive=len(pos), normal=len(neg), thresholds=dict(low=lo, high=hi))
    for tag, mt, ft in (('L', lo, hi), ('S', hi, hi)):
        miss = sum(any(t and s < mt for t, s in v) for v in pos.values()); fa = sum(any(s >= ft for _, s in v) for v in neg.values())
        res[tag] = dict(miss=f'{miss}/{len(pos)}', miss_upper95=round(upper(miss, len(pos)), 3), miss_pass_10=bool(upper(miss, len(pos)) <= .10),
                        false_alarm=f'{fa}/{len(neg)}', fa_upper95=round(upper(fa, len(neg)), 3) if neg else None, fa_pass_20=bool(neg and upper(fa, len(neg)) <= .20))
    out[name] = res
json.dump(out, open('artifacts/d3-event-rates-20261113/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
