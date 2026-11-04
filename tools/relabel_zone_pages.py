"""Blind zone-level surface re-judgment pages: top 20% model-scored 'normal' zones of the dev surface pool (excluding cards already re-judged in section 93), shuffled.
Pages show a zoomed crop with the zone outlined; no score, no earlier label, no title. Mapping stays in selection.json."""
import base64
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from card_condition.label_instructions import SURFACE_INSTRUCTIONS

SEED, TOP, PER_PAGE = 20261104, 0.20, 20
STYLE = """body{font:17px/1.5 system-ui;margin:0 auto;max-width:640px;padding:12px}article{border-top:2px solid #888;margin-top:14px;padding-top:4px}
img{width:100%;display:block}.row{display:flex;gap:8px;margin:6px 0}.row button,#copy,#alln{flex:1;font-size:18px;min-height:48px}
.row button.on[data-v=정상]{background:#1a9e4a;color:#fff}.row button.on[data-v=결함]{background:#e02828;color:#fff}.row button.on[data-v=불가]{background:#777;color:#fff}
textarea{width:100%;height:220px;font-size:15px}h2{font-size:16px;margin:4px 0}#copy,#alln{width:100%;margin-top:8px}"""
SCRIPT = """
const arts=[...document.querySelectorAll('article')];
function build(){return arts.map(a=>a.dataset.id+'='+(a.dataset.v||'미확인')).join('\\n')}
function show(){document.getElementById('out').value=build()}
function pick(a,v){a.dataset.v=v;a.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.v===v))}
arts.forEach(a=>a.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{pick(a,b.dataset.v);show()})));
document.getElementById('alln').onclick=()=>{arts.forEach(a=>{if(!a.dataset.v)pick(a,'정상')});show()};
show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def select(rows, scores, exclude_groups):
    normals = sorted((s, r) for r, s in zip(rows, scores) if r['target'] == 0)
    cut = normals[int(len(normals)*(1-TOP)):]
    chosen = [dict(id=r['id'], group=r['group'], area=r['area'], image=r['image'], box=r['box'], score=s) for s, r in cut if r['group'] not in exclude_groups]
    random.Random(SEED).shuffle(chosen)
    return chosen


def crop(z):
    with Image.open(z['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    l, t, r, b = z['box']
    mx, my = (r-l)*0.25, (b-t)*0.25
    box = [max(0, (l-mx)*w), max(0, (t-my)*h), min(w, (r+mx)*w), min(h, (b+my)*h)]
    out = image.crop([int(v) for v in box])
    draw = ImageDraw.Draw(out)
    draw.rectangle([l*w-box[0], t*h-box[1], r*w-box[0], b*h-box[1]], outline=(30, 90, 255), width=max(2, w//300))
    out.thumbnail((420, 420))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=62, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, z):
    return (f'<article data-id="z{number}"><h2>구역 {number}</h2><img alt="" src="data:image/jpeg;base64,{crop(z)}">'
            '<div class="row"><button data-v="정상">정상</button><button data-v="결함">결함</button><button data-v="불가">판단 불가</button></div></article>')


def page(n, total, start, zones):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>구역 재판정 {n}/{total}</title><style>{STYLE}</style><h1>구역 재판정 {n}/{total}</h1>'
            + SURFACE_INSTRUCTIONS +
            '<p>이전 판정·모델 점수는 보이지 않습니다. 파란 사각형 안 구역만 판정하세요. '
            '확신이 없으면 판단 불가로 두세요. “안 누른 곳 전부 정상”은 남은 구역도 실제 확인했을 때만 누르세요. '
            '자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + ''.join(article(start + k, z) for k, z in enumerate(zones)) +
            '<button id="alln">안 누른 곳 전부 정상</button><h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{SCRIPT}</script></html>')


def main(observations, relabeled, out):
    obs = json.loads(Path(observations).read_text())
    done = {c['group'] for c in json.loads(Path(relabeled).read_text())}
    chosen = select(obs['rows'], obs['scores'], done)
    out = Path(out)
    (out/'selection.json').write_text(json.dumps([dict(n=i, **z) for i, z in enumerate(chosen, 1)], ensure_ascii=False))
    batches = [chosen[i:i+PER_PAGE] for i in range(0, len(chosen), PER_PAGE)]
    for n, batch in enumerate(batches, 1):
        (out/f'zones-{n}.html').write_text(page(n, len(batches), (n-1)*PER_PAGE + 1, batch))
    print(len(chosen), 'zones,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
