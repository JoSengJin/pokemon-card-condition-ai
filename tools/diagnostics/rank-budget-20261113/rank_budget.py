"""P0: 기존 저장 점수·사람 target으로 순위/예산 지표 계산. 새 추론·학습·게이트 변경 0. 사람 target=확대 기준 라벨(탐색)."""
import json, collections, numpy as np
O = 'artifacts/rank-budget-20261113'
obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
rows = obs['rows']; sc = np.array(obs['scores']); y = np.array([r['target'] for r in rows]); grp = np.array([r['group'] for r in rows])
n, P = len(y), int(y.sum()); order = np.argsort(-sc, kind='stable')
def auc():
    r = np.empty(n); r[np.argsort(sc, kind='stable')] = np.arange(1, n + 1)
    return (r[y == 1].sum() - P * (P + 1) / 2) / (P * (n - P))
out = dict(n=n, defects=P, base_rate=round(P / n, 4), auc_all=round(float(auc()), 3))
# 전체 예산: 점수 상위 f 비율을 점검했을 때 재현율/정밀도
out['global_budget'] = {}
for f in (.05, .1, .2, .3, .5):
    k = int(round(n * f)); h = int(y[order[:k]].sum())
    out['global_budget'][f] = dict(k=k, hits=h, recall=round(h / P, 3), precision=round(h / k, 3), lift=round(h / k / (P / n), 2))
# 게이트 기준 (score>=0.5) 병기
pred = sc >= .5; out['gate_0.5'] = dict(FN=int((y[~pred]).sum()), defects=P, FP=int((~y.astype(bool))[pred].sum()), normals=n - P, flagged=int(pred.sum()))
# 사진별: 결함·정상이 섞인 사진만 대상
g = collections.defaultdict(list)
for i in range(n): g[grp[i]].append(i)
mixed = [v for v in g.values() if 0 < y[v].sum() < len(v)]
def per_photo(k):
    hit, rec, prec, ch = [], [], [], []
    for v in mixed:
        s = sorted(v, key=lambda i: -sc[i])[:k]; t = y[v].sum(); h = y[s].sum()
        hit.append(h > 0); rec.append(h / t); prec.append(h / k); ch.append(t / len(v))
    return dict(hit_rate=round(float(np.mean(hit)), 3), recall=round(float(np.mean(rec)), 3), precision=round(float(np.mean(prec)), 3), chance_precision=round(float(np.mean(ch)), 3))
out['photos'] = dict(total=len(g), with_defect=sum(1 for v in g.values() if y[v].sum() > 0), mixed=len(mixed))
out['per_photo_topk'] = {k: per_photo(k) for k in (1, 2, 3, 5)}
# 사진 단위 부트스트랩 (precision@3, recall@3, 전체 상위10% 재현율)
rng = np.random.default_rng(20261113); ks = sorted(g); bs = []
for _ in range(1000):
    idx = np.concatenate([g[k] for k in rng.choice(ks, len(ks))]); s2, y2 = sc[idx], y[idx]; o2 = np.argsort(-s2, kind='stable'); k = int(len(idx) * .1)
    bs.append(y2[o2[:k]].sum() / max(y2.sum(), 1))
out['recall_top10pct_ci95'] = [round(float(x), 3) for x in np.percentile(bs, [2.5, 97.5])]
import os; os.makedirs(O, exist_ok=True); json.dump(out, open(f'{O}/results.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
