"""Static phone pages, corner criteria v2 (LABELING_PROTOCOL.md 모서리 개정 2026-11-28, decision D-3): confirm the card box, tap the 4 CORNER areas
(미확인>정상>결함>판단 불가), whole photo at original resolution, screen conditions in <page>.criteria.json. Writes no labels. Never shows earlier answers.
The v1 page tool (mobile_corner_label_pages.py) and everything made with it stay as they were."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import label_criteria
from tools import mobile_corner_label_pages as v1

STATES = ['미확인', '정상', '결함', '판단 불가']
CARD_MM, MODEL_PX_MM, QUALITY = (63, 88), 15.27, 92
SCALE = 1.0  # shortcut: never downscale; a smaller value must still pass display_ok or the page is refused
STYLE = v1.STYLE + '.c[data-s="판단 불가"]{background:#e8a600aa}.c[data-s="미확인"] i::after{content:"탭";font-weight:400;opacity:.8}'
STYLE += '.tip{margin:4px 0;font-weight:700}'  # 2026-11-29 phone test: the cells were not tapped (the person judged by eye only)
OLD_NEXT = "const NEXT={'미확인':'정상','정상':'결함','결함':'미확인'};"
SCRIPT = v1.SCRIPT.replace(OLD_NEXT, "const NEXT={'미확인':'정상','정상':'결함','결함':'판단 불가','판단 불가':'미확인'};")
assert SCRIPT != v1.SCRIPT  # the v1 script text changed: refuse to run on a mismatch instead of silently showing 3 states
# Drag dots sit on the box SIDES, not its corners: a dot on a box corner covered the card corner being judged and caught the tap
# (2026-11-29 phone test). Each dot moves one side.
SIDE_DOTS = (("a.querySelectorAll('.h').forEach(e=>{e.style.left=(e.dataset.k.includes('l')?l:r)*100+'%';e.style.top=(e.dataset.k.includes('t')?t:b)*100+'%'})}",
              "a.querySelectorAll('.h').forEach(e=>{const k=e.dataset.k;e.style.left=(k==='l'?l:k==='r'?r:(l+r)/2)*100+'%';e.style.top=(k==='t'?t:k==='b'?b:(t+b)/2)*100+'%'})}"),
             ("if(k.includes('l'))a.b[0]=Math.min(x,a.b[2]-.05);else a.b[2]=Math.max(x,a.b[0]+.05);",
              "if(k==='l')a.b[0]=Math.min(x,a.b[2]-.05);if(k==='r')a.b[2]=Math.max(x,a.b[0]+.05);"),
             ("if(k.includes('t'))a.b[1]=Math.min(y,a.b[3]-.05);else a.b[3]=Math.max(y,a.b[1]+.05);",
              "if(k==='t')a.b[1]=Math.min(y,a.b[3]-.05);if(k==='b')a.b[3]=Math.max(y,a.b[1]+.05);"))
for _old, _new in SIDE_DOTS:
    assert SCRIPT.count(_old) == 1  # refuse to run if the v1 script text moved
    SCRIPT = SCRIPT.replace(_old, _new)
INSTRUCTIONS = (
    '<p><b>이 페이지의 판정은 모서리(카드 네 귀퉁이의 둥근 끝: 뭉개짐·찍힘·백화·접힘)만입니다.</b> 근처 직선 테두리만의 마모·백화, 면 안쪽 기스·오염은 이 항목이 아니므로 결함으로 누르지 마세요. 이 페이지에는 네 모서리 칸만 있습니다.</p>'
    '<p>빨간 점 4개를 끌어 파란 상자가 <b>카드가 전부 안에 들어오게</b> 맞추세요(딱 맞을 필요 없음). 상자를 고쳤다면 마지막에 “상자 확인”을 누르세요. '
    '사진은 원본 해상도 그대로입니다. 두 손가락으로 확대해서 보세요. 자동 저장하지 않습니다.</p>'
    '<p>모서리 결함 수준: 모서리의 둥근 끝에서 뭉개짐·찍힘·백화·접힘이 사진을 확대하여 명확히 구분되면 크기와 관계없이 결함으로 판정한다. 확대해도 반사인지 실제 마모인지 구분되지 않거나 가림·흐림 등으로 판별할 수 없으면 판단 불가로 처리하며, 원본 사진에 없는 세부정보는 추정하지 않는다. '
    '둥근 끝 = 둥글게 굽은 모서리 선이 직선 테두리와 만나는 두 지점(호 접점) 사이의 구간. 이 구간에 닿은 자국은 모서리 결함이다. 직선 테두리에만 있는 자국은 제외한다. '
    '한 자국이 둥근 끝과 직선 엣지에 걸쳐 있으면 걸친 두 위치 모두 결함입니다.</p>'
    '<p>각 모서리 칸은 탭할 때마다 미확인→정상→결함→판단 불가→미확인으로 바뀝니다. 미확인은 아직 판정하지 않은 칸, 판단 불가는 위 기준대로 봤지만 구분이 안 되는 칸입니다.</p>')


def display_ok(original, display):
    """03 I2: the screen must be at least as fine as min(original, model input) px/mm."""
    return display >= min(original, MODEL_PX_MM) - 1e-9


def photo(path, box):
    """(base64 JPEG of the whole photo, original px/mm, display px/mm). px/mm from the initial card box on a 63x88 mm card, the smaller side (03 M1)."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    width, height = image.size
    original = min((box[2] - box[0]) * width / CARD_MM[0], (box[3] - box[1]) * height / CARD_MM[1])
    if SCALE != 1.0:
        image = image.resize((round(width * SCALE), round(height * SCALE)))
    display = original * image.size[0] / width
    if not display_ok(original, display):
        raise ValueError(f'Screen too coarse for {path}: {display:.2f} px/mm vs original {original:.2f}')
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=QUALITY)
    return base64.b64encode(buffer.getvalue()).decode(), original, display


def article(number, face, data):
    cells = ''.join(f'<div class="c" data-a="{a}" data-s="미확인" data-x="{x}" data-y="{y}"><i></i></div>' for a, x, y in v1.AREAS)
    handles = ''.join(f'<div class="h" data-k="{k}"></div>' for k in ('t', 'r', 'b', 'l'))
    return (f'<article data-id="{html.escape(face["id"])}" data-ok="0" data-box="{html.escape(json.dumps(face["box"]))}">'
            f'<h2>{number}. {html.escape(face["title"][:60])} ({face["id"].rsplit("/", 1)[-1]})</h2>'
            '<p class="tip">점선 모서리 칸을 탭해 입력: 정상 → 결함 → 판단 불가</p>'
            f'<div class="ph"><img alt="" src="data:image/jpeg;base64,{data}"><div class="bx"></div>{cells}{handles}</div>'
            '<div class="row"><button class="ok">상자 확인(카드가 안에 들어옴)</button></div>'
            '<div class="row"><button class="alln">4모서리 전부 정상</button><button class="reset">구역 초기화</button></div></article>')


def split(sizes, per_page=None, max_bytes=None):
    """Card index lists, in order: a piece ends at per_page cards or before its photos would pass max_bytes. A photo bigger than max_bytes gets a piece of its own."""
    pieces = [[]]
    total = 0
    for n, size in enumerate(sizes):
        if pieces[-1] and ((per_page and len(pieces[-1]) >= per_page) or (max_bytes and total + size > max_bytes)):
            pieces.append([])
            total = 0
        pieces[-1].append(n)
        total += size
    return pieces if sizes else []


def main(review_jsonl, ids_text, out_path, side='back', per_page=None, max_mb=None):
    """ids_text: whitespace-separated row ids. per_page / max_mb: pieces of at most that many cards / that many MB of photos, written as <stem>-N<suffix>
    (phone viewers can fail on big files; photo size differs with resolution, so max_mb fits more small photos on a page)."""
    rows = {r['id']: r for r in map(json.loads, Path(review_jsonl).read_text(encoding='utf-8').splitlines()) if r.get('id')}
    ids, out = ids_text.split(), Path(out_path)
    faces = [dict(id=f'{i}/{side}', box=rows[i]['side_annotations'][side]['box'], title=rows[i].get('title') or i, image=rows[i]['side_annotations'][side]['image']) for i in ids]
    shots = [photo(f['image'], f['box']) for f in faces]  # every photo passes the resolution rule before anything is written
    groups = split([len(s[0]) for s in shots], per_page, max_mb and max_mb * 1e6)
    named = per_page or max_mb
    pieces = [(out if not named else out.with_name(f'{out.stem}-{n + 1}{out.suffix}'), group) for n, group in enumerate(groups)]
    for path, piece in pieces:
        part, taken = [faces[k] for k in piece], [shots[k] for k in piece]
        body = ''.join(article(n, f, s[0]) for n, (f, s) in enumerate(zip(part, taken), 1))
        text = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>구역 라벨 입력</title><style>{STYLE}</style><h1>모서리 구역 라벨 (기준 v2)</h1>' + INSTRUCTIONS + body +
                '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
                f'<script>{SCRIPT}</script></html>')
        screen = dict(screen='corner-v2', states=STATES, image=dict(format='JPEG', quality=QUALITY, scale=SCALE, crop='whole photo, no zone crop', min_px_per_mm_rule=f'display >= min(original, {MODEL_PX_MM})'),
                      px_per_mm_basis='initial card box, 63x88 mm card, smaller side', prefill='none',
                      original_px_per_mm={f['id']: round(s[1], 4) for f, s in zip(part, taken)}, display_px_per_mm={f['id']: round(s[2], 4) for f, s in zip(part, taken)})
        label_criteria.write_page(path, text, INSTRUCTIONS, body, screen)
    return [p for p, _ in pieces]


if __name__ == '__main__':
    # argv: review ids out [per_page or 0] [max_mb]
    for written in main(*sys.argv[1:4], 'back', int(sys.argv[4]) if len(sys.argv) > 4 and int(sys.argv[4]) else None, float(sys.argv[5]) if len(sys.argv) > 5 else None):
        print(written, written.stat().st_size)
