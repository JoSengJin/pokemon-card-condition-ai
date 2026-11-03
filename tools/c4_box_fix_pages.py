"""C4 holdout box-fix phone pages: for fronts whose auto box was judged '카드가 상자 밖으로 나감', tap the card's outer edge 4 times on the full photo. Pasted-back line: id|front|x0,y0,x1,y1 (normalized, full image) or id|front|판정불가. No predictions, no measurer output."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_label_pages import PANEL  # noqa: E402
from mobile_centering_mark_pages import STYLE  # noqa: E402
import base64, io  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402


def small_uri(path, width=560):
    # kept small (about 60 KB per photo) so the page stays under 1 MB and the app preview can load it
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((width, 800))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=60, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()

STEPS = ['카드 바깥 왼쪽 가장자리', '카드 바깥 오른쪽 가장자리', '카드 바깥 위쪽 가장자리', '카드 바깥 아래쪽 가장자리']
SCRIPT = """const STEPS=%s;const o=document.getElementById('out');
function sync(){o.value=[...document.querySelectorAll('article')].filter(x=>x.dataset.s).map(x=>x.dataset.s).join('\\n');document.getElementById('cnt').textContent=[...document.querySelectorAll('article')].filter(x=>x.dataset.s).length}
document.getElementById('tot').textContent=document.querySelectorAll('article').length;
document.querySelectorAll('article').forEach(a=>{const c=a.querySelector('canvas'),g=c.getContext('2d'),img=new Image();let pts=[];
function draw(){g.drawImage(img,0,0,c.width,c.height);pts.forEach((p,i)=>{g.strokeStyle='#e22';g.lineWidth=2;g.beginPath();if(i<2){g.moveTo(p*c.width,0);g.lineTo(p*c.width,c.height)}else{g.moveTo(0,p*c.height);g.lineTo(c.width,p*c.height)}g.stroke()});
a.querySelector('.step').textContent=a.querySelector('.na').checked?'판정불가':pts.length<4?(pts.length+1)+'/4 '+STEPS[pts.length]+' — 탭':(a.querySelector('.cen')&&!a.querySelector('.cen').value)?'표시 완료 — 아래 센터링을 선택하세요':'완료';
const cen=a.querySelector('.cen'),cv=cen?cen.value:null;
a.dataset.s=a.querySelector('.na').checked?[a.dataset.id,'front','판정불가'].join('|'):(pts.length==4&&(!cen||cv))?[a.dataset.id,'front',pts.map(p=>p.toFixed(4)).join(','),...(cen?[cv]:[])].join('|'):'';sync()}
img.onload=()=>{c.width=img.width;c.height=img.height;draw()};img.src=a.dataset.src;
c.addEventListener('click',e=>{if(pts.length>=4)return;const r=c.getBoundingClientRect();pts.push(pts.length<2?(e.clientX-r.left)/r.width:(e.clientY-r.top)/r.height);draw()});
a.querySelector('.undo').onclick=()=>{pts.pop();draw()};a.querySelector('.na').onchange=draw;a.querySelectorAll('select,input').forEach(e=>['change','input','click','blur'].forEach(t=>e.addEventListener(t,()=>setTimeout(draw,50))));a._draw=draw});setInterval(()=>document.querySelectorAll('article').forEach(a=>a._draw&&a._draw()),700);
%s""" 


def article(item, cen=False):
    return (f'<article data-id="{html.escape(item["id"])}" data-s="" data-src="{small_uri(item["image"])}">'
            f'<h2>{html.escape(item["id"])}</h2><div class="step"></div><button class="undo">되돌리기</button><canvas></canvas>'
            '<label><input type="checkbox" class="na"> 앞면 아님/판정불가</label>'
            + ('<label>센터링(사람 판단) <select class="cen"><option value="">선택</option><option>결함</option><option>정상</option><option>미확인</option></select></label>' if cen else '') + '</article>')


def main(pool_json, ids_json, out_path, with_centering=False):
    ids = json.loads(Path(ids_json).read_text())
    items = [i for i in json.loads(Path(pool_json).read_text()) if i['id'] in set(ids)]
    from c4_label_pages import COPY
    guide = '<p>카드 전체(앞면)의 바깥 가장자리 4곳을 순서대로 탭하세요: 왼 → 오른 → 위 → 아래. 사진 전체가 보입니다.</p>'
    script = SCRIPT % (json.dumps(STEPS, ensure_ascii=False), COPY.split('\n', 1)[1])
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{guide}{"".join(article(i, with_centering) for i in items)}{PANEL}<script>{script}</script>', encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    print(main(*sys.argv[1:4], with_centering=len(sys.argv) > 4))
