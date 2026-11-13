"""P0b: (1) FN<=67 허용 시 FP 최소(임계 이동), (2) 사진당 상위k 규칙을 사진 절반에서 고르고 나머지 절반에서 평가(100회 분할). 새 추론 0, 게이트 미변경."""
import json, collections, numpy as np
obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
sc = np.array(obs['scores']); y = np.array([r['target'] for r in obs['rows']]); grp = np.array([r['group'] for r in obs['rows']])
out = {}
best = None
for t in np.unique(sc):
    p = sc >= t; fn = int(y[~p].sum()); fp = int((p & (y == 0)).sum())
    if fn <= 67: best = (float(t), fn, fp)
    else: break
out['thr_move_FN<=67'] = dict(thr=round(best[0], 3), FN=best[1], FP=best[2], FP_limit=112, passes=best[2] <= 112)
g = collections.defaultdict(list)
for i, k in enumerate(grp): g[k].append(i)
ks = sorted(g)
def rule(photos, k):  # 사진당 상위 k칸 점검 → FN, 점검 칸 수
    ck = fn = 0
    for p in photos:
        v = sorted(g[p], key=lambda i: -sc[i]); ck += min(k, len(v)); fn += y[v[k:]].sum()
    return int(fn), ck
res = {}
for k in (2, 3, 4, 5):
    fn, ck = rule(ks, k); P = int(y.sum())
    res[k] = dict(recall=round(1 - fn / P, 3), checked=ck, checked_share=round(ck / len(y), 3), FP_equiv=int(ck - (P - fn)))
out['per_photo_topk_all'] = res
rng = np.random.default_rng(20261113); sel = []
for _ in range(100):
    perm = rng.permutation(len(ks)); a, b = [ks[i] for i in perm[:len(ks) // 2]], [ks[i] for i in perm[len(ks) // 2:]]
    # 선택: A에서 재현율>=0.8을 만족하는 최소 k, 평가: B 재현율
    for k in range(1, 9):
        fn, _ = rule(a, k); Pa = sum(y[g[p]].sum() for p in a)
        if 1 - fn / Pa >= .8: break
    fnb, ckb = rule(b, k); Pb = sum(y[g[p]].sum() for p in b); sel.append((k, 1 - fnb / Pb, ckb / sum(len(g[p]) for p in b)))
s = np.array(sel); out['split_half_recall>=0.8'] = dict(k_mode=int(np.bincount(s[:, 0].astype(int)).argmax()), heldout_recall_mean=round(float(s[:, 1].mean()), 3), heldout_recall_p5=round(float(np.percentile(s[:, 1], 5)), 3), checked_share_mean=round(float(s[:, 2].mean()), 3))
json.dump(out, open('artifacts/rank-budget-20261113/gate_floor.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
