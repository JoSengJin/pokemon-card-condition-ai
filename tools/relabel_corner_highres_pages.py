"""High-resolution blind re-judgment of the corner zones that were 'unknown' or flipped defect->normal in the thumbnail round. Same zone outline, native-resolution crop (<=1000px, JPEG q88); no earlier answer or label shown. Zone numbers keep the first round's z-ids."""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from tools import relabel_corner_blind_pages as blind
from tools import relabel_zone_pages as zp

SIDE, QUALITY, PER_PAGE = 1000, 88, 13


def pick(selection, answers):
    """Zones answered unknown (불가) plus zones labelled defect that were answered normal, in first-round order."""
    return [z for z in selection if answers[z['n']] == '불가' or (z['target'] == 1 and answers[z['n']] == '정상')]


def crop(z):
    with Image.open(z['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    l, t, r, b = z['box']
    mx, my = (r - l)*.25, (b - t)*.25
    box = [max(0, (l - mx)*w), max(0, (t - my)*h), min(w, (r + mx)*w), min(h, (b + my)*h)]
    out = image.crop([int(v) for v in box])
    ImageDraw.Draw(out).rectangle([l*w - box[0], t*h - box[1], r*w - box[0], b*h - box[1]], outline=(30, 90, 255), width=max(2, w//400))
    out.thumbnail((SIDE, SIDE))
    buffer = io.BytesIO()
    out.save(buffer, 'JPEG', quality=QUALITY, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


def page(n, total, zones):
    zp.crop = crop
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>모서리 고해상도 재판정 {n}/{total}</title><style>{zp.STYLE}</style><h1>모서리 고해상도 재판정 {n}/{total}</h1>' + blind.INSTRUCTIONS +
            '<p>이전 판정·모델 점수는 보이지 않습니다. 이번 화면은 원본 해상도에 가깝게 보여 줍니다. 파란 사각형 안 구역만 판정하세요. 자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + ''.join(zp.article(z['n'], z) for z in zones) +
            f'<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea><script>{zp.SCRIPT}</script></html>')


def main(selection_path, answers_path, out):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/diagnostics/corner-rejudge-20261121'))
    import score
    chosen = pick(json.loads(Path(selection_path).read_text()), score.parse(Path(answers_path).read_text()))
    out = Path(out)
    (out/'selection-hi.json').write_text(json.dumps([z['n'] for z in chosen]))
    pages = [chosen[i:i + PER_PAGE] for i in range(0, len(chosen), PER_PAGE)]
    for n, zones in enumerate(pages, 1):
        (out/f'hires-{n}.html').write_text(page(n, len(pages), zones))
    print(len(chosen), 'zones,', len(pages), 'pages')


if __name__ == '__main__':
    main(*sys.argv[1:4])
