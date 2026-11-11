"""임계 보정 진단(prereg threshold-calibration-20261112, 비채택 근거용). 저장 점수만 사용, 학습·라벨 변경 0.
폴드 k 임계 = 나머지 4폴드 점수로 FN률<=0.17을 만족하는 가장 큰 임계(중첩). 평가 폴드 정보 미사용."""
import json
import random
from collections import defaultdict
E = 'artifacts/experiments/20261108T215307-941b3aaa/observations.json'
G = 'artifacts/surface-grounding-20261110/packet.json'; OUT = 'artifacts/threshold-calibration-20261112/results.json'
FN_RATE, GATE_FN, GATE_FP, SEED, B = 0.17, 67, 112, 20261107, 2000


def pick(train):
    pos = sorted(s for s, t in train if t == 1); n = len(pos); allowed = int(FN_RATE * n)
    return pos[allowed] if allowed < n else 1.0     # score < t 이면 FN: t 미만 양성이 allowed 이하가 되는 가장 큰 t


def count(rows, th):
    fn = sum(1 for s, t, k, g in rows if t == 1 and s < th[k]); fp = sum(1 for s, t, k, g in rows if t == 0 and s >= th[k]); return fn, fp


def main():
    o = json.load(open(E)); fold = {e['row']['id']: e['fold'] for e in json.load(open(G))['entries']}
    rows = [(s, r['target'], fold[r['id']], r['group']) for r, s in zip(o['rows'], o['scores'])]; assert len(rows) == 1776
    th = {k: pick([(s, t) for s, t, kk, g in rows if kk != k]) for k in sorted({r[2] for r in rows})}
    fn0, fp0 = count(rows, {k: 0.5 for k in th}); fn, fp = count(rows, th)
    by = defaultdict(list)
    for r in rows: by[r[3]].append(r)
    groups = sorted(by); rng = random.Random(SEED); bs = []
    for _ in range(B):
        samp = [x for g in rng.choices(groups, k=len(groups)) for x in by[g]]; bs.append(count(samp, th))
    q = lambda v: [sorted(v)[int(len(v) * p)] for p in (0.025, 0.975)]
    res = dict(thresholds={str(k): round(v, 4) for k, v in th.items()}, control_at_0_5=dict(FN=fn0, FP=fp0), nested=dict(FN=fn, FP=fp, positives=sum(r[1] for r in rows), negatives=sum(1 - r[1] for r in rows)),
               bootstrap_ci=dict(FN=q([a for a, _ in bs]), FP=q([b for _, b in bs])), gates=dict(FN=GATE_FN, FP=GATE_FP, upper_limit_x1_15=dict(FN=round(GATE_FN * 1.15, 1), FP=round(GATE_FP * 1.15, 1))))
    res['success'] = fn <= GATE_FN and fp <= GATE_FP and res['bootstrap_ci']['FN'][1] <= GATE_FN * 1.15 and res['bootstrap_ci']['FP'][1] <= GATE_FP * 1.15
    open(OUT, 'w').write(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
