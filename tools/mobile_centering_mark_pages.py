"""Static phone pages: tap 8 edge positions per photo (card outer edge L,R,T,B then printed inner frame L,R,T,B) on a crop around the confirmed card box. Writes no labels; pasted-back lines hold crop window + 8 image fractions, with the human centering label NOT shown."""
import base64
import html
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageOps

STEPS = ['카드 바깥 왼쪽 가장자리', '카드 바깥 오른쪽 가장자리', '카드 바깥 위쪽 가장자리', '카드 바깥 아래쪽 가장자리',
         '인쇄 틀 안쪽 왼쪽 경계', '인쇄 틀 안쪽 오른쪽 경계', '인쇄 틀 안쪽 위쪽 경계', '인쇄 틀 안쪽 아래쪽 경계']
STYLE = """body{font:17px/1.5 system-ui;margin:0 auto;max-width:720px;padding:12px}article{border-top:2px solid #888;margin-top:20px;padding-top:6px}
canvas{width:100%;display:block;touch-action:manipulation}.row{display:flex;gap:8px;margin:8px 0}.row button{flex:1;font-size:18px;min-height:48px}
textarea{width:100%;height:240px;font-size:15px}.step{font-weight:700;color:#1e5aff}"""
SCRIPT = """const STEPS=%s;
document.querySelectorAll('article').forEach(a=>{const c=a.querySelector('canvas'),g=c.getContext('2d'),img=new Image(),w=a.dataset.w.split(',').map(Number);let pts=[],skip=false;
function draw(){g.drawImage(img,0,0,c.width,c.height);pts.forEach((p,i)=>{g.strokeStyle=i<4?'#e22':'#12c';g.lineWidth=2;g.beginPath();if(i<2){g.moveTo(p*c.width,0);g.lineTo(p*c.width,c.height)}else if(i<4){g.moveTo(0,(p)*c.height);g.lineTo(c.width,p*c.height)}else if(i<6){g.moveTo(p*c.width,0);g.lineTo(p*c.width,c.height)}else{g.moveTo(0,p*c.height);g.lineTo(c.width,p*c.height)}g.stroke()});
a.querySelector('.step').textContent=skip?'건너뜀(미확인)':pts.length<8?(pts.length+1)+'/8 '+STEPS[pts.length]+(pts.length%%4<2?' — 그 위치를 탭':' — 그 위치를 탭'):'완료';
a.dataset.s=skip?'미확인':pts.length==8?pts.map((p,i)=>{const horiz=(i%%4<2);return horiz?(w[0]+p*(w[2]-w[0])).toFixed(4):(w[1]+p*(w[3]-w[1])).toFixed(4)}).join(','):'';show()}
img.onload=()=>{c.width=img.width;c.height=img.height;draw()};img.src=a.dataset.src;
c.addEventListener('click',e=>{if(pts.length>=8||skip)return;const r=c.getBoundingClientRect(),i=pts.length;pts.push(i%%4<2?(e.clientX-r.left)/r.width:(e.clientY-r.top)/r.height);draw()});
a.querySelector('.undo').onclick=()=>{skip=false;pts.pop();draw()};a.querySelector('.skip').onclick=()=>{skip=true;pts=[];draw()}});
function show(){document.getElementById('out').value=[...document.querySelectorAll('article')].filter(a=>a.dataset.s).map(a=>a.dataset.id+'|'+a.dataset.side+'|'+a.dataset.w+'|'+a.dataset.s).join('\\n')}"""


def window(box, margin=.06):
    x0, y0, x1, y1 = box
    return [max(0., x0-margin), max(0., y0-margin), min(1., x1+margin), min(1., y1+margin)]


def crop_uri(path, win, width=900):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        w, h = image.size
        crop = image.crop((round(win[0]*w), round(win[1]*h), round(win[2]*w), round(win[3]*h)))
    crop.thumbnail((width, 1400))
    buffer = io.BytesIO()
    crop.save(buffer, 'JPEG', quality=82)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()


def article(item):
    win = window(item['box'])
    return (f'<article data-id="{html.escape(item["id"])}" data-side="{item["side"]}" data-w="{",".join(f"{v:.4f}" for v in win)}" data-s="" data-src="{crop_uri(item["image"], win)}">'
            f'<h2>{html.escape(item["id"])} ({item["side"]})</h2><div class="step"></div><canvas></canvas>'
            '<div class="row"><button class="undo">되돌리기</button><button class="skip">건너뜀</button></div></article>')


def main(items_json, out_path):
    items = json.loads(Path(items_json).read_text())
    guide = ('<p>사진마다 차례로 8곳을 탭합니다. 카드 바깥 가장자리 4곳(빨강: 왼·오·위·아래), 인쇄된 틀 안쪽 경계 4곳(파랑: 왼·오·위·아래). '
             '왼·오른쪽은 가로 위치만, 위·아래는 세로 위치만 쓰이니 해당 변 근처 아무 곳이나 탭하세요. 확실히 못 찾으면 건너뜀.</p>')
    body = guide + ''.join(article(i) for i in items) + '<textarea id="out" readonly></textarea>'
    script = SCRIPT % json.dumps(STEPS, ensure_ascii=False)
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{script}</script>', encoding='utf-8')
    return len(items)


def select(rows_jsonl, side, per_class, seed, exclude=()):
    """Seeded balanced pick of confirmed-box photos with a human centering label (label itself is not written to the page items)."""
    pool = {0: [], 1: []}
    for r in map(json.loads, Path(rows_jsonl).read_text(encoding='utf-8').splitlines()):
        b = (r.get('side_annotations') or {}).get(side) or {}
        v = (b.get('labels') or {}).get('centering_defect')
        if not r.get('excluded') and b.get('box_reviewed') and v in (0, 1) and r['id'] not in exclude:
            pool[v].append(dict(id=r['id'], side=side, image=b['image'], box=b['box']))
    rng = random.Random(seed)
    picked = [i for v in (0, 1) for i in rng.sample(sorted(pool[v], key=lambda i: i['id']), per_class)]
    rng.shuffle(picked)
    return picked


if __name__ == '__main__':
    print(main(*sys.argv[1:3]))
