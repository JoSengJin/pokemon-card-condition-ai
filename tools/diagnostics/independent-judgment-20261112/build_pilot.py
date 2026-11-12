"""독립(AI) 판정 파일럿 표본·갤러리·크롭 생성. 학습·추론·라벨 변경 0. 사전 등록: independent-surface-judgment-prereg-draft-20261112.md (+amendment_1: 판정자=서브에이전트)."""
import glob, hashlib, json, random
from collections import defaultdict
from pathlib import Path
from PIL import Image
OUT = Path('artifacts/independent-judgment-20261112'); SEED = 20261112
PILOT_PER_CELL, MAIN_PER_CELL, GAL = 10, 40, 6


def load():
    obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
    mask = {r['id']: bool(r['bad'] or r['center_out']) for r in json.load(open('artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    pk = {e['row']['id']: e['row'] for e in json.load(open('artifacts/surface-grounding-20261110/packet.json'))['entries']}
    return [dict(id=r['id'], group=r['group'], target=r['target'], score=s, cell=f"{r['target']}/{int(s >= .5)}", card_off=mask.get(r['id'], False), row=pk[r['id']]) for r, s in zip(obs['rows'], obs['scores'])]


def prior():  # id -> 같은 사람 판정 목록 [(출처, 값)]
    d = defaultdict(list)
    for f in sorted(glob.glob('artifacts/zone-eval-set-20261112/responses/*.json')):
        for r in json.load(open(f))['responses']:
            if r.get('judgment'): d[r['id']].append(('zone_eval', r['judgment']))
    for f in sorted(glob.glob('artifacts/severity-repro-20261112/responses/*.json')):
        for r in json.load(open(f))['responses']:
            if r.get('level') is not None: d[r['id']].append(('severity', str(r['level'])))
    for tag in ('normal-rejudge-20261112', 'normal-rejudge2-20261112'):
        for f in sorted(glob.glob(f'artifacts/{tag}/responses/*.json')):
            for r in json.load(open(f))['responses']:
                d[r['id'].split('/point-review/')[0]].append(('cand_box', r['judgment']))
    return d


def gallery(rows, pr, rng):
    by = {r['id']: r for r in rows}; pools = dict(defect=[], normal=[], boundary=[])
    for i, js in pr.items():
        if i not in by or by[i]['card_off']: continue
        c = [v for s, v in js if s == 'cand_box']; z = [v for s, v in js if s == 'zone_eval']; s2 = [v for s, v in js if s == 'severity']
        if len(z) >= 2 and len(set(z)) == 1 and z[0] in ('defect', 'normal'): pools[z[0]].append(i)
        elif len(s2) >= 2 and set(s2) == {'2'}: pools['defect'].append(i)
        elif len(s2) >= 2 and set(s2) == {'0'}: pools['normal'].append(i)
        elif len(c) >= 2 and set(c) == {'normal'} and 'normal' in z: pools['normal'].append(i)  # 후보 박스 2회 정상 + 구역 평가 정상
        elif len(s2) >= 2 and len(set(s2)) > 1: pools['boundary'].append(i)
        elif len(z) >= 2 and len(set(z)) > 1: pools['boundary'].append(i)
    gal = {}
    for k, v in pools.items():
        v = sorted(set(v)); rng.shuffle(v); gal[k] = v[:GAL]
    return gal, {k: len(set(v)) for k, v in pools.items()}


def crop(row, path):
    im = Image.open(row['image']).convert('RGB'); w, h = im.size; x0, y0, x1, y1 = row['box']
    c = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))); c.thumbnail((900, 900)); c.save(path, 'JPEG', quality=92)


def main():
    rng = random.Random(SEED); rows = load(); pr = prior(); gal, poolsz = gallery(rows, pr, rng)
    by = {r['id']: r for r in rows}; gal_ids = {i for v in gal.values() for i in v}; gal_groups = {by[i]['group'] for i in gal_ids}
    frame = [r for r in rows if r['group'] not in gal_groups]
    cells = defaultdict(list)
    for r in frame: cells[r['cell']].append(r)
    sizes = {c: len(cells[c]) for c in sorted(cells)}; sizes_all = {c: sum(1 for r in rows if r['cell'] == c) for c in sorted(cells)}
    pilot, main = [], []
    for c in sorted(cells):
        pool = sorted(cells[c], key=lambda r: r['id']); rng.shuffle(pool)
        for stage, n, dest in (('pilot', PILOT_PER_CELL, pilot), ('main', MAIN_PER_CELL, main)):
            used = set(); take = []
            for z in pool:
                if z in pilot or z in main: continue
                if len(take) == n: break
                if z['group'] in used: continue
                used.add(z['group']); take.append(z)
            for z in pool:  # group_repeat 보충
                if len(take) == n: break
                if z not in take and z not in pilot and z not in main: take.append(dict(z, group_repeat=True))
            for z in take: dest.append(dict(z, stage=stage, weight=sizes_all[c] / n if False else sizes[c] / n))
    for z in pilot + main: z['prior_used'] = [list(p) for p in pr.get(z['id'], [])]
    (OUT / 'crops').mkdir(parents=True, exist_ok=True)
    code = lambda i: 'z' + hashlib.sha256(f'{SEED}:{i}'.encode()).hexdigest()[:8]
    for i in gal_ids: crop(by[i]['row'], OUT / 'crops' / f'g_{code(i)}.jpg')
    for z in pilot: crop(z['row'], OUT / 'crops' / f'{code(z["id"])}.jpg')
    meta = lambda z: {k: z[k] for k in ('id', 'group', 'cell', 'card_off', 'weight', 'stage', 'prior_used') if k in z} | dict(code=code(z['id']), group_repeat=z.get('group_repeat', False))
    json.dump(dict(seed=SEED, cell_sizes_all=sizes_all, cell_sizes_after_gallery=sizes, gallery_pool_sizes=poolsz,
                   gallery={k: [dict(id=i, code=code(i), prior=pr[i]) for i in v] for k, v in gal.items()},
                   pilot=[meta(z) for z in pilot], main=[meta(z) for z in main]), open(OUT / 'sample.json', 'w'), ensure_ascii=False, indent=1)
    for n in (1, 2, 3):  # 판정자별 무작위 순서, 코드만 노출
        order = [code(z['id']) for z in pilot]; random.Random(SEED + n).shuffle(order)
        json.dump(dict(rater=f'R{n}', items=[str(OUT.resolve() / 'crops' / f'{c}.jpg') for c in order], codes=order), open(OUT / f'rater_R{n}.json', 'w'), indent=1)
    gcodes = {k: [str((OUT / 'crops' / f"g_{code(i)}.jpg").resolve()) for i in v] for k, v in gal.items()}
    json.dump(gcodes, open(OUT / 'gallery_paths.json', 'w'), indent=1)
    print('sizes_all', sizes_all, 'after_gallery', sizes, 'pools', poolsz, 'gallery', {k: len(v) for k, v in gal.items()}, 'pilot', len(pilot), 'main', len(main),
          'group_repeat pilot/main', sum(1 for z in pilot if z.get('group_repeat')), sum(1 for z in main if z.get('group_repeat')), 'card_off pilot', sum(z['card_off'] for z in pilot))


if __name__ == '__main__':
    main()
