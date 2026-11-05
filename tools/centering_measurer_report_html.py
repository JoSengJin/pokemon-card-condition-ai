"""On-photo comparison of the automatic top/bottom measurer (green) with the human-marked top/bottom frame lines (blue) on each dev front."""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def card(row, found):
    with Image.open(row['image']) as src:
        img = ImageOps.exif_transpose(src).convert('RGB')
    W, H = img.size
    x0, y0, x1, y1 = row['box']
    crop = img.crop((round(x0*W), round(y0*H), round(x1*W), round(y1*H)))
    crop.thumbnail((300, 460))
    d, (w, h) = ImageDraw.Draw(crop), crop.size
    bh = y1-y0
    for frac, color in ((found['top'], (20, 180, 60)), (1-found['bottom'], (20, 180, 60)), (row['human_top']/bh, (30, 80, 255)), (1-row['human_bottom']/bh, (30, 80, 255))):
        d.line([(0, frac*h), (w, frac*h)], fill=color, width=2)
    buf = io.BytesIO()
    crop.save(buf, 'JPEG', quality=80)
    return f'<div class="c"><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"><small>{"결함" if row["target"] else "정상"}(사람) {row["id"][:14]}</small></div>'


def main(rows_path, evaluation, out_path):
    rows = json.loads(Path(rows_path).read_text())
    ev = json.loads(Path(evaluation).read_text())
    head = (f'<h2>자동 상하 측정기(초록) vs 사람 표시(파랑), 개발 앞면 {ev["rows"]}장</h2><p>사람 표시와의 순위상관 {ev["spearman_with_human_marks"]:.2f}, 사람 라벨 AUC {ev["auc_vs_label"]:.2f} '
            f'[{ev["bootstrap"]["lo"]:.2f},{ev["bootstrap"]["hi"]:.2f}] (사람 표시 자체 {ev["human_mark_auc"]:.2f}). 기준 미충족.</p>')
    css = 'body{font:13px system-ui;margin:8px}.c{display:inline-block;width:300px;margin:4px;vertical-align:top}.c img{width:100%}'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{css}</style>{head}{"".join(card(r, f) for r, f in zip(rows, ev["measured"]))}', encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:4])
