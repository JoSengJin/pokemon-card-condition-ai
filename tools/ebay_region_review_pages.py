"""Static phone pages: per face, confirm the card box and label each of the 8 edge areas (normal / defect / unknown) on a 3x3 grid overlay.
Writes no labels; the user pastes the result back. Region labels let one photo hold both defect and normal areas."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

BATCH = 5
AREAS = [('upper_left', 1), ('upper_center', 2), ('upper_right', 3), ('middle_left', 4), ('middle_right', 5),
         ('lower_left', 6), ('lower_center', 7), ('lower_right', 8)]
CELL = {'upper_left': (0, 0), 'upper_center': (1, 0), 'upper_right': (2, 0), 'middle_left': (0, 1), 'middle_right': (2, 1),
        'lower_left': (0, 2), 'lower_center': (1, 2), 'lower_right': (2, 2)}
SCRIPT = """
const rows=[...document.querySelectorAll('article')];
function build(){return rows.map(a=>a.dataset.id+'='+a.querySelector('[name=box]').value+';'+[...a.querySelectorAll('select.r')].map(s=>s.name+':'+s.value).join(';')).join('\\n')}
function show(){document.getElementById('out').value=build()}
document.querySelectorAll('select').forEach(s=>s.addEventListener('change',show));show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def overlay(face):
    with Image.open(face['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    left, top, right, bottom = face['box']
    draw = ImageDraw.Draw(image)
    width = max(3, w // 220)
    draw.rectangle([left*w, top*h, right*w, bottom*h], outline=(30, 90, 255), width=width)
    cw, ch = (right-left)*w/3, (bottom-top)*h/3
    for k in (1, 2):
        draw.line([(left*w+k*cw, top*h), (left*w+k*cw, bottom*h)], fill=(255, 160, 0), width=max(2, width//2))
        draw.line([(left*w, top*h+k*ch), (right*w, top*h+k*ch)], fill=(255, 160, 0), width=max(2, width//2))
    size = max(24, w // 18)
    for area, number in AREAS:
        x, y = CELL[area]
        draw.rectangle([left*w+x*cw+4, top*h+y*ch+4, left*w+x*cw+4+size, top*h+y*ch+4+size], fill=(255, 160, 0))
        draw.text((left*w+x*cw+4+size//4, top*h+y*ch+4+size//6), str(number), fill=(0, 0, 0))
    image.thumbnail((760, 760))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=72)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, face):
    selects = ''.join(f'<label>{n}. {a}<select class="r" name="{a}"><option value="미확인">미확인</option><option value="정상">정상</option>'
                      f'<option value="결함">결함</option><option value="불가">판단 불가</option></select></label>' for a, n in AREAS)
    return (f'<article data-id="{html.escape(face["id"])}"><h2>{number}. {html.escape(face["title"][:60])}</h2>'
            f'<img alt="" src="data:image/jpeg;base64,{overlay(face)}">'
            '<label>파란 상자<select name="box"><option value="미확인">미확인</option><option value="맞음">맞음</option>'
            '<option value="잘림">카드가 상자 밖으로 잘림</option></select></label>' + selects + '</article>')


def page(number, total, start, faces):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>엣지 구역 확인 {number}/{total}</title><style>body{{font:17px/1.6 system-ui;margin:0 auto;max-width:760px;padding:16px}}'
            'img{width:100%}select,button{font-size:18px;min-height:44px;width:100%;margin:4px 0}textarea{width:100%;height:240px;font-size:15px}'
            'article{border-top:1px solid #aaa;margin-top:22px}</style>'
            f'<h1>엣지 구역 확인 {number}/{total}</h1><p>파란 상자 안에 카드가 다 들어오면 “맞음”(넓거나 비스듬해도 됩니다). 주황 번호 1~8 구역마다 '
            '카드 테두리가 정상이면 “정상”, 흰 벗겨짐·눌림·갈라짐이 보이면 “결함”, 사진으로 알 수 없으면 “판단 불가”, 아직 안 봤으면 “미확인”으로 두세요. '
            '가운데 칸은 확인하지 않습니다. 확신이 없으면 “판단 불가”입니다. 자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
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
