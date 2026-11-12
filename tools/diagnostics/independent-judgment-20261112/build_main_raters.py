"""탐색 실행(amendment_3)용: 본 판정 표본 160곳 크롭과 판정자·배치별 파일 생성. 학습·추론 0."""
import json, random, sys
from pathlib import Path
sys.path.insert(0, 'tools/diagnostics/independent-judgment-20261112')
from build_pilot import OUT, load, crop, SEED
smp = json.load(open(OUT / 'sample.json')); by = {r['id']: r for r in load()}
main = smp['main']; ABS = Path.cwd() / OUT
for z in main: crop(by[z['id']]['row'], OUT / 'crops' / f"{z['code']}.jpg")
for n in (1, 2, 3):
    codes = [z['code'] for z in main]; random.Random(SEED + 200 + n).shuffle(codes)
    for b in range(4):
        cs = codes[b * 40:(b + 1) * 40]
        json.dump(dict(rater=f'R{n}', batch=b + 1, items=[str(ABS / 'crops' / f'{c}.jpg') for c in cs], codes=cs), open(OUT / f'main_R{n}_b{b + 1}.json', 'w'), indent=1)
(OUT / 'main_responses').mkdir(exist_ok=True); print(len(main), 'zones; card_off', sum(z['card_off'] for z in main), 'group_repeat', sum(z['group_repeat'] for z in main))
