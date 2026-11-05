"""Static phone pages, tap-based: tap a cell on the photo to cycle its state (미확인 > 정상 > 결함 > 판단 불가), one button sets all 8 edge areas normal.
Per face: card box 맞음/잘림 buttons. Writes no labels; the user pastes the result back. Same-photo defect/normal areas supported."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

BATCH = 5
AREAS = [('upper_left', 0, 0), ('upper_center', 1, 0), ('upper_right', 2, 0), ('middle_left', 0, 1), ('middle_right', 2, 1),
         ('lower_left', 0, 2), ('lower_center', 1, 2), ('lower_right', 2, 2)]
STYLE = """body{font:17px/1.5 system-ui;margin:0 auto;max-width:720px;padding:12px}article{border-top:2px solid #888;margin-top:20px;padding-top:6px}
.ph{position:relative;line-height:0}.ph img{width:100%}.c{position:absolute;box-sizing:border-box;border:1px dashed #fff8;font:700 20px system-ui;color:#fff;
display:flex;align-items:center;justify-content:center;text-shadow:0 0 4px #000;line-height:1.2;user-select:none;-webkit-user-select:none;touch-action:manipulation}
.c[data-s=미확인]{background:#0000}.c[data-s=정상]{background:#1a9e4a88}.c[data-s=결함]{background:#e0282888}.c[data-s=불가]{background:#8888}
.row{display:flex;gap:8px;margin:8px 0}.row button,#copy{flex:1;font-size:18px;min-height:48px}.row button.on{background:#1e5aff;color:#fff}
textarea{width:100%;height:240px;font-size:15px}#copy{width:100%}h2{font-size:17px;margin:6px 0}"""
SCRIPT = """
const NEXT={'미확인':'정상','정상':'결함','결함':'불가','불가':'미확인'};
const arts=[...document.querySelectorAll('article')];
function build(){return arts.map(a=>a.dataset.id+'='+(a.dataset.box||'미확인')+';'+[...a.querySelectorAll('.c')].map(c=>c.dataset.a+':'+c.dataset.s).join(';')).join('\\n')}
function show(){document.getElementById('out').value=build()}
arts.forEach(a=>{
  a.querySelectorAll('.c').forEach(c=>c.addEventListener('click',()=>{c.dataset.s=NEXT[c.dataset.s];c.querySelector('i').textContent=c.dataset.s=='미확인'?'':c.dataset.s;show()}));
  a.querySelectorAll('[data-box]').forEach(b=>b.addEventListener('click',()=>{a.dataset.box=b.dataset.box;a.querySelectorAll('[data-box]').forEach(x=>x.classList.toggle('on',x===b));show()}));
  a.querySelector('.allnormal').addEventListener('click',()=>{a.querySelectorAll('.c').forEach(c=>{c.dataset.s='정상';c.querySelector('i').textContent='정상'});show()});
  a.querySelector('.reset').addEventListener('click',()=>{a.querySelectorAll('.c').forEach(c=>{c.dataset.s='미확인';c.querySelector('i').textContent=''});show()});
});
show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def photo(face):
    with Image.open(face['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    left, top, right, bottom = face['box']
    ImageDraw.Draw(image).rectangle([left*w, top*h, right*w, bottom*h], outline=(30, 90, 255), width=max(3, w // 220))
    image.thumbnail((760, 760))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=72)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, face):
    left, top, right, bottom = face['box']
    bw, bh = (right-left)/3, (bottom-top)/3
    cells = ''.join(f'<div class="c" data-a="{a}" data-s="미확인" style="left:{(left+x*bw)*100:.3f}%;top:{(top+y*bh)*100:.3f}%;'
                    f'width:{bw*100:.3f}%;height:{bh*100:.3f}%"><i></i></div>' for a, x, y in AREAS)
    return (f'<article data-id="{html.escape(face["id"])}"><h2>{number}. {html.escape(face["title"][:60])}</h2>'
            f'<div class="ph"><img alt="" src="data:image/jpeg;base64,{photo(face)}">{cells}</div>'
            '<div class="row"><button data-box="맞음">상자 맞음</button><button data-box="잘림">카드가 상자 밖으로 잘림</button></div>'
            '<div class="row"><button class="allnormal">8구역 전부 정상</button><button class="reset">되돌리기</button></div></article>')


def page(number, total, start, faces):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>엣지 구역 확인 {number}/{total}</title><style>{STYLE}</style><h1>엣지 구역 확인 {number}/{total}</h1>'
            '<p>① 파란 상자에 카드가 다 들어오면 “상자 맞음”(넓거나 비스듬해도 됩니다). ② 테두리가 다 정상이면 “8구역 전부 정상”을 누르세요. '
            '③ 구역을 터치하면 정상(초록) → 결함(빨강) → 판단 불가(회색) → 미확인 순으로 바뀝니다. 결함이 있는 구역만 터치하면 됩니다. '
            '가운데 칸은 확인하지 않습니다. 확신이 없으면 판단 불가, 안 본 구역은 미확인으로 두세요(정상으로 간주하지 않습니다). '
            '자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + ''.join(article(start + k, f) for k, f in enumerate(faces, 1)) +
            '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{SCRIPT}</script></html>')


def main(root):
    root = Path(root)
    faces = json.loads((root/'back-faces.json').read_text())
    out = root/'region-edge'
    out.mkdir(exist_ok=False)
    batches = [faces[i:i+BATCH] for i in range(0, len(faces), BATCH)]
    for n, batch in enumerate(batches, 1):
        (out/f'region-edge-{n}.html').write_text(page(n, len(batches), (n-1)*BATCH, batch))
    print(len(faces), 'faces,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    main(sys.argv[1])
