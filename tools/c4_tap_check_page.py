"""C4 tap check page: for train fronts where the human centering label and the human-tapped border asymmetry disagree, show the card with all 8 tap lines (red = card outer, blue = printed frame inner) and the four border strips enlarged. Asks only: do the lines sit on the real edges, and which side looked narrow. No model output, no ratios shown. Line: id|front|lines=<맞음|틀림|모름>|narrow=<위,아래,왼쪽,오른쪽 or 없음>."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_label_pages import COPY, PANEL  # noqa: E402
from mobile_centering_mark_pages import STYLE  # noqa: E402

SIDES = ['위', '아래', '왼쪽', '오른쪽']
SCRIPT = """function sync(){const d=[...document.querySelectorAll('article')].filter(x=>x.dataset.s);document.getElementById('out').value=d.map(x=>x.dataset.s).join('\\n');document.getElementById('cnt').textContent=d.length}
document.querySelectorAll('article').forEach(a=>{const f=()=>{const l=a.querySelector('select').value,n=[...a.querySelectorAll('.nw:checked')].map(x=>x.value);
a.dataset.s=l?[a.dataset.id,'front','lines='+l,'narrow='+(n.length?n.join(','):'없음')].join('|'):'';sync()};a.querySelectorAll('select,input').forEach(x=>x.addEventListener('change',f));a._f=f});
setInterval(()=>document.querySelectorAll('article').forEach(a=>a._f()),700);
"""


def uri(im, width):
    im = im.copy()
    im.thumbnail((width, 10 ** 5))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=78)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def card_html(row, image_path):
    im = ImageOps.exif_transpose(Image.open(image_path)).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    lw = max(1, h // 700)
    for k in ('outer_top', 'outer_bottom', 'inner_top', 'inner_bottom'):
        d.line([0, row[k] * h, w, row[k] * h], fill='red' if k.startswith('outer') else 'blue', width=lw)
    for k in ('outer_left', 'outer_right', 'inner_left', 'inner_right'):
        d.line([row[k] * w, 0, row[k] * w, h], fill='red' if k.startswith('outer') else 'blue', width=lw)
    m = .02
    L, R, T, B = row['outer_left'] - m, row['outer_right'] + m, row['outer_top'] - m, row['outer_bottom'] + m
    box = lambda x0, y0, x1, y1: im.crop((round(max(0, x0) * w), round(max(0, y0) * h), round(min(1, x1) * w), round(min(1, y1) * h)))
    card = box(L, T, R, B)
    top = box(L, T, R, row['inner_top'] + m)
    bot = box(L, row['inner_bottom'] - m, R, B)
    left = box(L, T, row['inner_left'] + m, B)
    right = box(row['inner_right'] - m, T, R, B)
    # left/right strips are turned so the card outer edge is at the bottom, like the bottom strip
    strips = [('위', top), ('아래', bot), ('왼쪽(90° 회전, 아래가 카드 바깥)', left.rotate(90, expand=True)), ('오른쪽(90° 회전, 아래가 카드 바깥)', right.rotate(-90, expand=True))]
    zoom = ''.join(f'<p>{name} 테두리 — 앞/뒤 절반 확대</p>' + ''.join(f'<img src="{uri(s.crop((k * s.width // 2, 0, (k + 1) * s.width // 2, s.height)), 680)}" style="width:100%">' for k in (0, 1))
                   for name, s in strips)
    checks = ''.join(f'<label><input type="checkbox" class="nw" value="{s}"> {s}</label> ' for s in SIDES)
    return (f'<article data-id="{html.escape(row["id"])}" data-s=""><h2>{html.escape(row["id"])}</h2><p>내 라벨: <b>{html.escape(row["label"])}</b></p>'
            f'<img src="{uri(card, 640)}" style="width:100%">{zoom}'
            '<p>선(빨강=카드 바깥, 파랑=인쇄 틀 안쪽)이 실제 경계에 맞나요? <select><option value="">선택</option><option>맞음</option><option>틀림</option><option>모름</option></select></p>'
            f'<p>센터링 판단 때 좁다고 본 쪽(없으면 비움): {checks}</p></article>')


def main(pool_json, rows_json, out_path):
    pool = {r['id']: r for r in json.loads(Path(pool_json).read_text())}
    rows = json.loads(Path(rows_json).read_text())
    guide = '<p>라벨과 탭 폭이 어긋난 카드입니다. 라벨을 다시 정하는 페이지가 아닙니다. 선 위치가 맞는지와, 판단할 때 좁다고 본 쪽만 골라 주세요.</p>'
    arts = ''.join(card_html(r, pool[r['id']]['image']) for r in rows)
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}body{{background:#fff;color:#111}}</style>{guide}{arts}{PANEL}<script>{SCRIPT}{COPY}</script>', encoding='utf-8')
    return len(rows)


if __name__ == '__main__':
    print(main(sys.argv[1], sys.argv[2], sys.argv[3]))
