"""AI 앞/뒤 분류 집계(후보 목록 생성). 사람 확인용 무작위 30그룹 추출(시드 고정). 새 추론 0."""
import json, random
from collections import Counter
O = 'artifacts/unused-pairing-20261113'; meta = {m['code']: m for m in json.load(open(f'{O}/sample_meta.json'))}; R = {}
for b in range(1, 11):
    d = json.load(open(f'{O}/responses/batch_{b}.json')); exp = json.load(open(f'{O}/batch_{b}.json'))['codes']
    assert [r['code'] for r in d['responses']] == exp, b
    for r in d['responses']: R[r['code']] = r
assert set(R) == set(meta)
def ok(r, n): return r['back_index'] is not None and 1 <= r['back_index'] <= n
bad = [c for c, r in R.items() if r['back_index'] is not None and not ok(r, len(meta[c]['photos']))]
cand = [c for c, r in R.items() if ok(r, len(meta[c]['photos'])) and r['single_card'] == 'yes' and r['front_index'] is not None and r['same_card'] == 'yes']
back_only = [c for c, r in R.items() if ok(r, len(meta[c]['photos'])) and c not in cand]
out = dict(n=len(R), with_back=sum(r['back_index'] is not None for r in R.values()), invalid_index=len(bad), single_card=dict(Counter(r['single_card'] for r in R.values())),
           same_card=dict(Counter(r['same_card'] for r in R.values())), candidates_full_pair=len(cand), back_only_not_pair=len(back_only), no_back=sum(r['back_index'] is None for r in R.values()))
rng = random.Random(20261113); out['human_check_sample_30'] = sorted(rng.sample(cand, min(30, len(cand))))
json.dump(dict(out, candidates=sorted(cand)), open(f'{O}/results.json', 'w'), indent=1); print(json.dumps({k: v for k, v in out.items() if k != 'human_check_sample_30'}, ensure_ascii=False))
