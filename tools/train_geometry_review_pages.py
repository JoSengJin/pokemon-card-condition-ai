"""Static phone pages for human card-box confirmation of train sides; writes no labels."""
import base64
import collections
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

BATCH = 12
PRIORITY = {'edge_defect': 3, 'surface_defect': 2, 'corner_defect': 1}


def pending_faces(coverage):
    faces = {}
    for unit in coverage['units']:
        if unit['split'] != 'train' or unit['target'] is None or unit['box_reviewed'] is not False:
            continue
        key = (unit['card_id'], unit['side'])
        face = faces.setdefault(key, dict(card=key[0], side=key[1], image=unit['image'],
                                          sha=unit['image_sha256'], box=unit['card_box'],
                                          labels=collections.Counter()))
        if face['box'] != unit['card_box'] or face['sha'] != unit['image_sha256']:
            raise ValueError('Inconsistent face identity: ' + '/'.join(key))
        face['labels'][unit['label']] += 1
    ordered = sorted(faces.values(), key=lambda f: (-sum(PRIORITY.get(k, 0) * v for k, v in f['labels'].items()),
                                                    f['card'], f['side']))
    return ordered


def preview(face):
    with Image.open(face['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    left, top, right, bottom = face['box']
    draw = ImageDraw.Draw(image)
    draw.rectangle([left * w, top * h, right * w, bottom * h], outline=(30, 90, 255), width=max(3, w // 200))
    image.thumbnail((720, 720))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=72)
    return base64.b64encode(buffer.getvalue()).decode()


SCRIPT = """
const rows=[...document.querySelectorAll('select')];
function build(){return rows.map(s=>s.dataset.id+'='+s.value).join('\\n')}
function show(){document.getElementById('out').value=build()}
rows.forEach(s=>s.addEventListener('change',show));show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def page(number, total, faces):
    articles = []
    for face in faces:
        ident = f"{face['card']}/{face['side']}"
        kinds = ', '.join(f'{k.replace("_defect", "")} {v}' for k, v in sorted(face['labels'].items()))
        articles.append(
            f'<article><h2>{html.escape(ident)}</h2><img alt="" src="data:image/jpeg;base64,{preview(face)}">'
            f'<p>대상 정답 단위: {html.escape(kinds)}</p>'
            f'<select data-id="{html.escape(ident)}"><option value="미확인">미확인</option>'
            f'<option value="맞음">맞음</option><option value="잘림">카드가 상자 밖으로 잘림</option></select></article>')
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>카드 영역 확인 {number}/{total}</title><style>body{{font:17px/1.6 system-ui;margin:0 auto;max-width:760px;padding:16px}}'
            'img{width:100%}select,button{font-size:18px;min-height:44px;width:100%;margin:6px 0}textarea{width:100%;height:220px;font-size:15px}'
            'article{border-top:1px solid #aaa;margin-top:22px}</style>'
            f'<h1>카드 영역 확인 {number}/{total}</h1><p>파란 상자 안에 카드 네 변·모서리가 모두 들어오면 “맞음”입니다. '
            '상자가 넓거나 카드가 비스듬한 것은 괜찮고, 카드가 상자 밖으로 잘릴 때만 “잘림”입니다. 정상/손상 정답은 묻지 않으며 자동 저장하지 않습니다.</p>'
            + ''.join(articles) +
            '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{SCRIPT}</script></html>')


def main(coverage_path, out_dir):
    coverage = json.loads(Path(coverage_path).read_text())
    faces = pending_faces(coverage)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    batches = [faces[i:i + BATCH] for i in range(0, len(faces), BATCH)]
    for number, batch in enumerate(batches, 1):
        (out / f'train-geometry-{number}.html').write_text(page(number, len(batches), batch))
    (out / 'pending.json').write_text(json.dumps(
        [dict(id=f"{f['card']}/{f['side']}", box=f['box'], image_sha256=f['sha'], labels=dict(f['labels'])) for f in faces],
        ensure_ascii=False, indent=1))
    print(len(faces), 'faces,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
