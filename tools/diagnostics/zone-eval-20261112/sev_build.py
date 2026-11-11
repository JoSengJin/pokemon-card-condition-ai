"""심각도 재현성 표본(prereg severity-repro-20261112)과 판정 페이지. 학습·추론·라벨 변경 0. 이전 라벨·점수는 페이지에 없음."""
import html
import json
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build import frame, crop
OUT = Path('artifacts/severity-repro-20261112'); SEED, PER_CELL, PER_FILE = 20261114, 15, 5
LV = {'0': '0 없음 (인쇄면 안쪽 자국 없음)', '1': '1 경미 (자국은 확실하나 확대해야 보임)', '2': '2 뚜렷 (확대 없이 한눈에 보임)', 'unknown': '판단 불가 (자국인지 불확실·카드 밖)'}
CRIT = ('<p><b>인쇄면 안쪽 표면만</b> 봅니다. 엣지·모서리·카드 밖·홀로 반사·인쇄 무늬는 제외. 핀치 확대해서 봐도 됩니다. 한 구역에 여러 자국이면 가장 높은 단계 하나만 고릅니다. '
        '<b>1 경미</b>=자국이 있는 것은 확실하나 확대해야 보임, <b>2 뚜렷</b>=확대 없이 한눈에 보임. 자국인지 확신이 없으면 판단 불가(경미와 다름).</p>')
SCRIPT = '''<section><h2>전체 답 · 여기서 한 번만 복사</h2><p>이 칸을 길게 눌러 전체 선택 후 복사해 채팅에 붙여넣으세요.</p><textarea id="out" rows="12" style="width:100%" readonly></textarea></section><script>
function g(){var r=[];document.querySelectorAll('.zc').forEach(function(d){var c=d.querySelector('input:checked');r.push({id:d.dataset.id,level:c?c.value:null})});document.getElementById('out').value=JSON.stringify({kind:'severity_judgments',responses:r},null,1)}
document.addEventListener('input',g);g();</script>'''


def page(zs, k, total):
    cards = []
    for n, z in enumerate(zs, 1):
        nm = f'r{n}_{abs(hash(z["id"])) % 10**8}'
        radios = ''.join(f'<label style="display:block;padding:8px 0"><input type="radio" name="{nm}" value="{v}"> {t}</label>' for v, t in LV.items())
        cards.append(f'<article class="zc" data-id="{html.escape(z["id"])}"><h2>{n}. {html.escape(z["row"]["area"])}</h2><img style="width:100%" src="data:image/jpeg;base64,{crop(z)}"><h3>표면 결함 단계는?</h3>{radios}</article>')
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>심각도 %d/%d</title><body style="font-family:sans-serif;max-width:720px;margin:auto;padding:0 16px">' % (k, total)
            + f'<h1>심각도 판정 {k}/{total}</h1>' + CRIT + ''.join(cards) + SCRIPT + '</body></html>')


def main():
    used = {z['id'] for z in json.load(open('artifacts/zone-eval-set-20261112/sample.json'))['zones']}
    cand = {a['id'].split('/point-review/')[0] for a in json.load(open('artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json'))['responses']}  # amendment_1: 오류 칸(0/1, 1/0)은 후보 제외 해제
    cells = frame(); rng = random.Random(SEED); chosen, sizes, avail, gused = [], {}, {}, set()
    for key in sorted(cells):
        ex = used if key in ((0, 1), (1, 0)) else used | cand; pool = sorted([z for z in cells[key] if z['id'] not in ex], key=lambda x: x['id']); rng.shuffle(pool); sizes[f'{key[0]}/{key[1]}'] = len(cells[key]); avail[f'{key[0]}/{key[1]}'] = len(pool); n = 0; fb = []
        for z in pool:
            if n == PER_CELL: break
            if z['group'] in gused: fb.append(z); continue
            gused.add(z['group']); chosen.append(dict(z, cell=f'{key[0]}/{key[1]}')); n += 1
        for z in fb:
            if n == PER_CELL: break
            chosen.append(dict(z, cell=f'{key[0]}/{key[1]}', group_repeat=True)); n += 1
    per = {c: sum(1 for z in chosen if z['cell'] == c) for c in sizes}
    for z in chosen: z['weight'] = sizes[z['cell']] / per[z['cell']]
    rng.shuffle(chosen); rep = rng.sample([z['id'] for z in chosen], 12); byid = {z['id']: z for z in chosen}
    (OUT / 'sample.json').write_text(json.dumps(dict(seed=SEED, cell_sizes=sizes, available_after_exclusion=avail, per_cell=per, repeat_ids=rep, zones=[{k: v for k, v in z.items() if k != 'row'} for z in chosen]), ensure_ascii=False, indent=1))
    mf, mr = [], []
    for k in range(0, len(chosen), PER_FILE):
        zs = chosen[k:k + PER_FILE]; nm = f'sev-{k // PER_FILE + 1:02d}.html'; (OUT / 'pages' / nm).write_text(page(zs, k // PER_FILE + 1, -(-len(chosen) // PER_FILE))); mf.append(dict(file=nm, ids=[z['id'] for z in zs]))
    for k in range(0, 12, 4):
        zs = [byid[i] for i in rep[k:k + 4]]; nm = f'srep-{k // 4 + 1:02d}.html'; (OUT / 'pages' / nm).write_text(page(zs, k // 4 + 1, 3)); mr.append(dict(file=nm, ids=[z['id'] for z in zs]))
    (OUT / 'manifest.json').write_text(json.dumps(dict(files=mf), indent=1)); (OUT / 'manifest_repeat.json').write_text(json.dumps(dict(files=mr), indent=1)); print(sizes, avail, per, len(chosen))


if __name__ == '__main__':
    main()
