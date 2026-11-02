"""Static phone pages: per BACK photo mark 정상 / 제한 / 미확인 for whole-face observation limits (glare, blur, obstruction, cropped, low resolution, perspective, shadow). Writes no labels; the answer text is pasted back."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

STYLE = """body{font:17px/1.5 system-ui;margin:0 auto;max-width:720px;padding:12px}article{border-top:2px solid #888;margin-top:20px;padding-top:6px}
img{width:100%;display:block}.row{display:flex;gap:8px;margin:8px 0}.row button,#out{font-size:18px;min-height:48px}.row button{flex:1}button.on{background:#1e5aff;color:#fff}
textarea{width:100%;height:240px;font-size:15px}h2{font-size:17px;margin:6px 0}"""
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>a.dataset.id+'/back='+a.dataset.s).join('\\n')}
arts.forEach(a=>{a.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{a.dataset.s=b.dataset.v;a.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));show()}))});show();"""


def encode(path, size=900):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((size, size))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=80)
    return base64.b64encode(buffer.getvalue()).decode()


def article(item):
    buttons = ''.join(f'<button data-v="{v}">{v}</button>' for v in ('정상', '제한', '미확인'))
    return (f'<article data-id="{html.escape(item["id"])}" data-s="미확인"><h2>{html.escape(item["id"])} (back)</h2>'
            f'<img src="data:image/jpeg;base64,{encode(item["image"])}"><div class="row">{buttons}</div></article>')


def main(review_jsonl, ids_text, out_path):
    """ids_text: whitespace-separated row ids; each page shows the row's back photo."""
    rows = {r['id']: r for r in map(json.loads, Path(review_jsonl).read_text(encoding='utf-8').splitlines()) if r.get('id')}
    items = [dict(id=i, image=rows[i]['side_annotations']['back']['image']) for i in ids_text.split()]
    guide = '<p>뒷면 사진 전체에서 <b>관찰 제한</b>(빛반사·흐림·가림·잘림·저해상도·심한 각도·그림자로 카드 상태를 볼 수 없음)이면 제한, 문제없이 볼 수 있으면 정상, 모르면 미확인.</p>'
    body = guide + ''.join(article(i) for i in items) + '<textarea id="out" readonly></textarea>'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
