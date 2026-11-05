"""Blind surface re-judgment pages for a label-consistency measurement: 3x3 tap cells on the card box (center included), no model score, no earlier label, no title.
Selection is deterministic (seeded): half cards with at least one earlier defect zone, half with none; mapping to earlier labels stays in selection.json (not shown)."""
import base64
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from card_condition.label_instructions import SURFACE_INSTRUCTIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebay_region_review_pages as base  # noqa: E402

AREAS = base.AREAS + [('center', 1, 1)]
SEED, PER_SIDE, BATCH = 20261104, 15, 15


def select(rows):
    by = {}
    for r in rows:
        by.setdefault(r['group'], {})[r['area']] = r
    cards = []
    for g, zones in sorted(by.items()):
        if 'upper_left' in zones and 'lower_right' in zones and Path(zones['upper_left']['image']).exists():
            ul, lr = zones['upper_left']['box'], zones['lower_right']['box']
            cards.append(dict(group=g, image=zones['upper_left']['image'], box=[ul[0], ul[1], lr[2], lr[3]],
                              labels={a: z['target'] for a, z in zones.items()}, defect=any(z['target'] for z in zones.values())))
    rng = random.Random(SEED)
    pos = rng.sample([c for c in cards if c['defect']], PER_SIDE)
    neg = rng.sample([c for c in cards if not c['defect']], PER_SIDE)
    chosen = pos + neg
    rng.shuffle(chosen)
    return chosen


def photo(card):
    with Image.open(card['image']) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    left, top, right, bottom = card['box']
    ImageDraw.Draw(image).rectangle([left*w, top*h, right*w, bottom*h], outline=(30, 90, 255), width=max(3, w // 220))
    image.thumbnail((760, 760))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=72)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, card):
    left, top, right, bottom = card['box']
    bw, bh = (right-left)/3, (bottom-top)/3
    cells = ''.join(f'<div class="c" data-a="{a}" data-s="미확인" style="left:{(left+x*bw)*100:.3f}%;top:{(top+y*bh)*100:.3f}%;'
                    f'width:{bw*100:.3f}%;height:{bh*100:.3f}%"><i></i></div>' for a, x, y in AREAS)
    return (f'<article data-id="c{number}"><h2>카드 {number}</h2>'
            f'<div class="ph"><img alt="" src="data:image/jpeg;base64,{photo(card)}">{cells}</div>'
            '<div class="row"><button data-box="맞음">상자 맞음</button><button data-box="잘림">상자 밖으로 잘림</button></div>'
            '<div class="row"><button class="allnormal">9구역 전부 정상</button><button class="reset">되돌리기</button></div></article>')


def page(n, total, start, cards):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>표면 재판정 {n}/{total}</title><style>{base.STYLE}</style><h1>표면 재판정 {n}/{total}</h1>'
            + SURFACE_INSTRUCTIONS +
            '<p>이전 판정·모델 점수는 보이지 않습니다. 파란 상자에 카드가 다 들어오면 “상자 맞음”을 누르세요. '
            '구역을 터치하면 정상 → 결함 → 판단 불가 → 미확인 순으로 바뀝니다. '
            '자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + ''.join(article(start + k, c) for k, c in enumerate(cards, 1)) +
            '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{base.SCRIPT}</script></html>')


def main(rows_path, out):
    out = Path(out)
    chosen = select(json.loads(Path(rows_path).read_text()))
    (out/'selection.json').write_text(json.dumps([dict(id=f'c{i}', **c) for i, c in enumerate(chosen, 1)], ensure_ascii=False))
    batches = [chosen[i:i+BATCH] for i in range(0, len(chosen), BATCH)]
    for n, batch in enumerate(batches, 1):
        (out/f'relabel-{n}.html').write_text(page(n, len(batches), (n-1)*BATCH + 1, batch))
    print(len(chosen), 'cards,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
