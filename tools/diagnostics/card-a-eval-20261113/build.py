"""A 기준 카드 단위 평가 표본: 사람 결함 카드 40 + 사람 정상 카드 30(갤러리 그룹 제외, 시드 고정)의 전 구역. 이미 같은 지시문으로 판정된 구역(본 160·오경보 62)은 재사용. 학습·추론 0."""
import collections, hashlib, json, random, sys
from pathlib import Path
sys.path.insert(0, 'tools/diagnostics/independent-judgment-20261112')
from build_pilot import load, crop
from collections import Counter
OUT = Path('artifacts/card-a-eval-20261113'); SEED = 20261113; ABS = Path.cwd() / OUT; NDEF, NNOR = 40, 30
rows = load(); by = {r['id']: r for r in rows}; g = collections.defaultdict(list)
for r in rows: g[r['group']].append(r)
old = json.load(open('artifacts/independent-judgment-20261112/sample.json')); gal = {by[e['id']]['group'] for v in old['gallery'].values() for e in v if e['id'] in by}
def cons(js):
    v = Counter(js).most_common(); return v[0][0] if v[0][1] >= 2 else 'split'
ex = {}  # zone id -> consensus (같은 지시문 amendment_3/오경보 판정)
M = {m['code']: m['id'] for m in json.load(open('artifacts/card-fa-judgment-20261113/sample_meta.json'))}; J = collections.defaultdict(list)
for n in (1, 2, 3):
    for b in (1, 2):
        for r in json.load(open(f'artifacts/card-fa-judgment-20261113/responses/R{n}_b{b}.json'))['responses']: J[M[r['code']]].append(r['judgment'])
code_main = {z['code']: z['id'] for z in old['main']}; JM = collections.defaultdict(list)
for n in (1, 2, 3):
    for b in (1, 2, 3, 4):
        for r in json.load(open(f'artifacts/independent-judgment-20261112/main_responses/R{n}_b{b}.json'))['responses']: JM[code_main[r['code']]].append(r['judgment'])
for src in (J, JM):
    for i, js in src.items():
        if len(js) == 3: ex.setdefault(i, cons(js))
defc = sorted(k for k, v in g.items() if any(r['target'] for r in v) and k not in gal); norc = sorted(k for k, v in g.items() if not any(r['target'] for r in v) and k not in gal)
rng = random.Random(SEED); sd = rng.sample(defc, NDEF); sn = rng.sample(norc, NNOR)
cards = [dict(group=k, stratum='defect', stratum_size=len(defc)) for k in sd] + [dict(group=k, stratum='normal', stratum_size=len(norc)) for k in sn]
zones = [dict(id=r['id'], group=k, score=r['score'], target=r['target'], card_off=r['card_off']) for c in cards for k in [c['group']] for r in g[k]]
code = lambda i: 'a' + hashlib.sha256(f'{SEED}:{i}'.encode()).hexdigest()[:8]
todo = [z for z in zones if z['id'] not in ex]
(OUT / 'crops').mkdir(parents=True, exist_ok=True)
for z in zones: z['code'] = code(z['id']); z['existing'] = ex.get(z['id'])
for z in todo: crop(by[z['id']]['row'], OUT / 'crops' / f"{z['code']}.jpg")
json.dump(dict(cards=cards, zones=zones, gallery_excluded=len(gal)), open(OUT / 'sample_meta.json', 'w'), indent=1)
codes = [z['code'] for z in todo]; random.Random(SEED + 1).shuffle(codes); nb = (len(codes) + 39) // 40; per = (len(codes) + nb - 1) // nb
for n in (1, 2, 3):
    cs = codes[:]; random.Random(SEED + 10 + n).shuffle(cs)
    for b in range(nb): part = cs[b * per:(b + 1) * per]; json.dump(dict(rater=f'R{n}', batch=b + 1, items=[str(ABS / 'crops' / f'{c}.jpg') for c in part], codes=part), open(OUT / f'R{n}_b{b + 1}.json', 'w'), indent=1)
(OUT / 'responses').mkdir(exist_ok=True)
open(OUT / 'rater_instructions.txt', 'w').write(open('artifacts/card-fa-judgment-20261113/rater_instructions.txt').read())
print('cards', len(cards), 'zones', len(zones), 'reused', len(zones) - len(todo), 'to judge', len(todo), 'batches/rater', nb, 'per', per, 'strata', len(defc), len(norc), 'gallery groups excluded', len(gal))
