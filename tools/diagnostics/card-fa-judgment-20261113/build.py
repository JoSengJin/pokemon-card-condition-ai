"""정상 카드 오경보 31장의 최고 점수 구역과 대조 31장(발견된 결함 카드의 최고 점수 구역)을 A 문턱 판정용으로 생성. 학습·추론 0."""
import collections, json, random, sys
from pathlib import Path
sys.path.insert(0, 'tools/diagnostics/independent-judgment-20261112')
from build_pilot import load, crop
OUT = Path('artifacts/card-fa-judgment-20261113'); SEED = 20261113; ABS = Path.cwd() / OUT
rows = load(); by = {r['id']: r for r in rows}
g = collections.defaultdict(list)
for r in rows: g[r['group']].append(r)
fa, ctl = [], []
for k, v in sorted(g.items()):
    top = max(v, key=lambda r: (r['score'], r['id']))
    if top['score'] < .5: continue
    (fa if not any(r['target'] for r in v) else ctl).append(top)
rng = random.Random(SEED); ctl_s = rng.sample(ctl, len(fa))
old = json.load(open('artifacts/independent-judgment-20261112/sample.json')); used = {z['id'] for z in old['pilot'] + old['main']}
zones = [dict(z, set='fa') for z in fa] + [dict(z, set='ctl') for z in ctl_s]
for i, z in enumerate(sorted(zones, key=lambda z: z['id'])): z['code'] = 'c' + __import__('hashlib').sha256(f"{SEED}:{z['id']}".encode()).hexdigest()[:8]
(OUT / 'crops').mkdir(parents=True, exist_ok=True)
for z in zones: crop(z['row'], OUT / 'crops' / f"{z['code']}.jpg")
meta = [dict(id=z['id'], group=z['group'], set=z['set'], score=z['score'], target=z['target'], card_off=z['card_off'], code=z['code'], overlap_prior_sample=z['id'] in used) for z in zones]
json.dump(meta, open(OUT / 'sample_meta.json', 'w'), indent=1)
codes = [z['code'] for z in zones]; random.Random(SEED + 1).shuffle(codes)
for n in (1, 2, 3):
    cs = codes[:]; random.Random(SEED + 10 + n).shuffle(cs)
    for b, part in enumerate((cs[:31], cs[31:])):
        json.dump(dict(rater=f'R{n}', batch=b + 1, items=[str(ABS / 'crops' / f'{c}.jpg') for c in part], codes=part), open(OUT / f'R{n}_b{b + 1}.json', 'w'), indent=1)
(OUT / 'responses').mkdir(exist_ok=True)
ins = open('artifacts/independent-judgment-20261112/rater_instructions_v2.txt').read().replace('40개', '31개 이하').replace('x 40', 'x 배치 항목 수')
open(OUT / 'rater_instructions.txt', 'w').write(ins)
print(len(fa), len(ctl), 'fa/ctl pool; sampled', len(zones), 'overlap prior', sum(m['overlap_prior_sample'] for m in meta), 'fa card_off', sum(z['card_off'] for z in fa), 'ctl card_off', sum(z['card_off'] for z in ctl_s))
