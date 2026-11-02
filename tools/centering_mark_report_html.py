"""On-photo report: the human edge marks drawn on each crop with border widths, asymmetry ratios and the human centering label."""
import html
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
from mobile_centering_mark_pages import window  # noqa: E402
from mobile_visibility_label_pages import encode  # noqa: E402
import io, base64  # noqa: E402,E401


def card(item, select, marks):
    v = marks[item['id']]
    win = window(select[item['id']]['box'])
    with Image.open(select[item['id']]['image']) as src:
        img = ImageOps.exif_transpose(src).convert('RGB')
    W, H = img.size
    crop = img.crop((round(win[0]*W), round(win[1]*H), round(win[2]*W), round(win[3]*H)))
    crop.thumbnail((520, 800))
    d, (w, h) = ImageDraw.Draw(crop), crop.size
    for k, p in enumerate(v):
        vertical = (k % 4) < 2
        color = (230, 40, 40) if k < 4 else (30, 80, 255)
        if vertical:
            x = (p-win[0])/(win[2]-win[0])*w
            d.line([(x, 0), (x, h)], fill=color, width=2)
        else:
            y = (p-win[1])/(win[3]-win[1])*h
            d.line([(0, y), (w, y)], fill=color, width=2)
    buf = io.BytesIO()
    crop.save(buf, 'JPEG', quality=80)
    label = '결함(사람)' if item['target'] else '정상(사람)'
    return (f'<div class="c"><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"><b>{label}</b><br>좌우 비대칭 {item["lr"]:.2f} · 상하 {item["tb"]:.2f}<br>'
            f'<small>{html.escape(item["id"][-8:])}</small></div>')


def main(analysis, selection, answers, out_path, label='뒷면'):
    a = json.loads(Path(analysis).read_text())
    select = {s['id']: s for s in json.loads(Path(selection).read_text())}
    marks = {l.split('|')[0]: [float(x) for x in l.split('|')[3].split(',')] for l in Path(answers).read_text().splitlines() if '미확인' not in l}
    head = (f'<h2>센터링 표시 시범({label}) 표시값 vs 사람 라벨</h2><p>사용 {a["n"]}장(결함 {a["positive"]}), 건너뜀·미응답 {a["skipped"]}장 분모 밖. 좌우 비대칭 AUC {a["lr"]["auc"]:.2f} '
            f'[{a["lr"]["ci"][0]:.2f},{a["lr"]["ci"][1]:.2f}], 상하 {a["tb"]["auc"]:.2f} [{a["tb"]["ci"][0]:.2f},{a["tb"]["ci"][1]:.2f}]. 빨강=카드 바깥, 파랑=인쇄 틀.</p>')
    css = 'body{font:14px system-ui;margin:8px}.c{display:inline-block;width:260px;margin:6px;vertical-align:top}.c img{width:100%}'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{css}</style>{head}{"".join(card(i, select, marks) for i in sorted(a["items"], key=lambda i: -i["worst"]))}', encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:6])
