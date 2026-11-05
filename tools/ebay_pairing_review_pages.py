"""Static phone pages for front/back photo choice of an eBay intake; writes no labels or condition truth."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

BATCH = 6
SCRIPT = """
const rows=[...document.querySelectorAll('article')];
function val(a,n){return a.querySelector('select[name='+n+']').value}
function build(){return rows.map(a=>a.dataset.id+'='+(val(a,'d')==='pair'?val(a,'f')+','+val(a,'b'):val(a,'d'))).join('\\n')}
function show(){document.getElementById('out').value=build()}
document.querySelectorAll('select').forEach(s=>s.addEventListener('change',show));show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def thumb(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    image.thumbnail((420, 420))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=60)
    return base64.b64encode(buffer.getvalue()).decode()


def article(item):
    count = len(item['photos'])
    shots = ''.join(f'<figure><img alt="" src="data:image/jpeg;base64,{thumb(p["path"])}"><figcaption>사진 {n}</figcaption></figure>'
                    for n, p in enumerate(item['photos'], 1))
    nums = ''.join(f'<option value="{n}">{n}</option>' for n in range(1, count + 1))
    back_default = 2 if count > 1 else 1
    back = nums.replace(f'value="{back_default}"', f'value="{back_default}" selected')
    return (f'<article data-id="{html.escape(item["id"])}"><h2>{html.escape(item["title"])}</h2><div class="shots">{shots}</div>'
            f'<label>판단<select name="d"><option value="pair">앞/뒤 선택</option><option value="제외">같은 카드 아님·제외</option></select></label>'
            f'<label>앞면 사진<select name="f">{nums}</select></label><label>뒷면 사진<select name="b">{back}</select></label></article>')


def page(number, total, items):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>앞뒤 사진 선택 {number}/{total}</title><style>body{{font:17px/1.6 system-ui;margin:0 auto;max-width:760px;padding:16px}}'
            '.shots{display:flex;flex-wrap:wrap;gap:6px}figure{margin:0;width:48%}img{width:100%}figcaption{text-align:center}'
            'select,button{font-size:18px;min-height:44px;width:100%;margin:6px 0}textarea{width:100%;height:220px;font-size:15px}'
            'article{border-top:1px solid #aaa;margin-top:22px}</style>'
            f'<h1>앞뒤 사진 선택 {number}/{total}</h1><p>매물마다 같은 카드의 앞면·뒷면 사진 번호를 고르세요. 한 카드가 아니거나 쓸 수 없으면 “제외”입니다. '
            '사진이 앞뒤로 안 보이면 제외하세요. 상태 정답은 묻지 않으며 자동 저장하지 않습니다.</p>'
            + ''.join(article(i) for i in items) +
            '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{SCRIPT}</script></html>')


def main(intake_dir):
    root = Path(intake_dir)
    items = json.loads((root / 'catalog.json').read_text())['items']
    out = root / 'pairing'
    out.mkdir(exist_ok=False)
    batches = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    for number, batch in enumerate(batches, 1):
        (out / f'pairing-{number}.html').write_text(page(number, len(batches), batch))
    print(len(items), 'listings,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    main(sys.argv[1])
