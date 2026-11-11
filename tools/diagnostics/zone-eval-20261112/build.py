"""구역 단위 평가 전용 표본(prereg zone-eval-set-20261112) 추출과 판정 페이지 생성. 학습·추론·라벨 변경 0. 모델 점수·기존 라벨은 페이지에 없음."""
import base64
import html
import io
import json
import random
from collections import defaultdict
from pathlib import Path
from PIL import Image
OUT = Path('artifacts/zone-eval-set-20261112'); SEED, PER_CELL, PER_FILE = 20261112, 25, 5
KO = {'defect': '결함 있음', 'normal': '결함 없음', 'unknown': '판단 불가'}
CRIT = ('<p><b>기준:</b> ① 긁힘·점·주변과 구분되는 색 차이가 한눈에 보이면 <b>결함</b> ② 흰 기운이 보여도 확신이 없거나 구분이 안 되면 <b>판단 불가</b> '
        '③ 카드 밖이거나 판단할 표면이 없으면 <b>판단 불가</b> ④ <b>정상</b>은 충분히 보이는데 아무것도 없을 때만.</p>')
SCRIPT = '''<section><h2>전체 답 · 여기서 한 번만 복사</h2><p>이 칸을 길게 눌러 전체 선택 후 복사해 채팅에 붙여넣으세요.</p><textarea id="out" rows="12" style="width:100%" readonly></textarea></section><script>
function g(){var r=[];document.querySelectorAll('.zc').forEach(function(d){var c=d.querySelector('input:checked');r.push({id:d.dataset.id,judgment:c?c.value:null})});document.getElementById('out').value=JSON.stringify({kind:'zone_eval_judgments',responses:r},null,1)}
document.addEventListener('input',g);g();</script>'''


def frame():
    obs = json.load(open('artifacts/experiments/20261108T215307-941b3aaa/observations.json'))
    mask = {r['id']: bool(r['bad'] or r['center_out']) for r in json.load(open('artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    pk = {e['row']['id']: e['row'] for e in json.load(open('artifacts/surface-grounding-20261110/packet.json'))['entries']}
    cells = defaultdict(list)
    for r, s in zip(obs['rows'], obs['scores']):
        if mask.get(r['id'], False): continue
        cells[(r['target'], int(s >= 0.5))].append(dict(id=r['id'], group=r['group'], score=s, target=r['target'], row=pk[r['id']]))
    return cells


def sample(cells):
    rng = random.Random(SEED); used, chosen, sizes = set(), [], {}
    for key in sorted(cells):
        pool = sorted(cells[key], key=lambda x: x['id']); rng.shuffle(pool); sizes[key] = len(pool); n = 0; fallback = []
        for z in pool:
            if n == PER_CELL: break
            if z['group'] in used: fallback.append(z); continue
            used.add(z['group']); chosen.append(dict(z, cell=f'{key[0]}/{key[1]}', weight=len(pool) / PER_CELL)); n += 1
        for z in fallback:
            if n == PER_CELL: break
            chosen.append(dict(z, cell=f'{key[0]}/{key[1]}', weight=len(pool) / PER_CELL, group_repeat=True)); n += 1
        assert n == PER_CELL, (key, n)
    rng.shuffle(chosen); return chosen, {f'{k[0]}/{k[1]}': v for k, v in sizes.items()}


def crop(z):
    row = z['row']; im = Image.open(row['image']).convert('RGB'); w, h = im.size; x0, y0, x1, y1 = row['box']
    c = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))); c.thumbnail((900, 900)); b = io.BytesIO(); c.save(b, 'JPEG', quality=90)
    return base64.b64encode(b.getvalue()).decode()


def page(zs, k, total):
    cards = []
    for n, z in enumerate(zs, 1):
        radios = ''.join(f'<label style="display:block;padding:8px 0"><input type="radio" name="r{z["id"].__hash__() & 0xffffff}" value="{v}"> {t}</label>' for v, t in KO.items())
        cards.append(f'<article class="zc" data-id="{html.escape(z["id"])}"><h2>{n}. {html.escape(z["row"]["area"])}</h2><img style="width:100%" src="data:image/jpeg;base64,{crop(z)}"><h3>이 구역에 결함이 보이나요?</h3>{radios}</article>')
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>구역 판정 %d/%d</title><body style="font-family:sans-serif;max-width:720px;margin:auto;padding:0 16px">' % (k, total)
            + f'<h1>구역 판정 {k}/{total}</h1>' + CRIT + '<p>구역 전체를 보고 판단합니다. 이전 라벨·모델 점수는 표시하지 않습니다.</p>' + ''.join(cards) + SCRIPT + '</body></html>')


def main():
    chosen, sizes = sample(frame()); assert len(chosen) == 100
    (OUT / 'sample.json').write_text(json.dumps(dict(seed=SEED, cell_sizes=sizes, per_cell=PER_CELL, zones=[{k: v for k, v in z.items() if k != 'row'} for z in chosen]), ensure_ascii=False, indent=1))
    files = []
    for k in range(0, 100, PER_FILE):
        zs = chosen[k:k + PER_FILE]; name = f'zone-{k // PER_FILE + 1:02d}.html'; (OUT / 'pages' / name).write_text(page(zs, k // PER_FILE + 1, 100 // PER_FILE))
        files.append(dict(file=name, ids=[z['id'] for z in zs], bytes=(OUT / 'pages' / name).stat().st_size))
    (OUT / 'manifest.json').write_text(json.dumps(dict(files=files), indent=1)); print(sizes, sum(1 for z in chosen if z.get('group_repeat')), 'group repeats', [f['bytes'] // 1024 for f in files][:6])


if __name__ == '__main__':
    main()
