"""Overlay HTML: heuristic card hull (green) over photos with the saved top-patch boxes of FP (red) and TN (blue)."""
import base64, io, json, random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
OUT = Path('artifacts/card-foreground-diagnostic-20261111')


def tile(path, hull, patches, size=300):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
    im.thumbnail((size, size)); w, h = im.size; d = ImageDraw.Draw(im)
    if len(hull) >= 3:
        d.polygon([(x * w, y * h) for x, y in hull], outline=(0, 255, 0), width=2)
    for box, color in patches:
        d.rectangle([box[0] * w, box[1] * h, box[2] * w, box[3] * h], outline=color, width=2)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def main(count, suffix=''):
    rows = json.load(open(OUT / f'rows{suffix}.json')); hulls = json.load(open(OUT / f'hulls{suffix}.json'))
    packet = {e['row']['id']: e for e in json.load(open('artifacts/surface-grounding-20261110/packet.json'))['entries']}
    photos = sorted(hulls); random.Random(7).shuffle(photos); cells = []
    for path in photos[:count]:
        patches = [(packet[r['id']]['evidence']['top_geometry']['box'], (255, 0, 0) if r['outcome'] == 'FP' else (0, 120, 255))
                   for r in rows if r['image'] == path and r['outcome'] in ('FP', 'TN')]
        cells.append(f'<figure><img src="data:image/jpeg;base64,{tile(path, hulls[path], patches)}"><figcaption>{Path(path).parent.name}</figcaption></figure>')
    html = ('<!doctype html><meta charset=utf-8><title>카드 전경 마스크 오버레이</title><style>body{font:13px system-ui;margin:12px}figure{display:inline-block;margin:4px}</style>'
            '<h2>카드 전경 마스크(초록 껍질) · 최고 패치 FP(빨강)/TN(파랑)</h2><p>휴리스틱 마스크이며 정답 윤곽이 아님. 잘못된 마스크를 확인해 주세요.</p>' + ''.join(cells))
    (OUT / f'overlay{suffix}.html').write_text(html)


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else '')
