"""Script-free phone page: for each photo answer one question - is the red ring on the card? (default 'on card'); one editable line lists the answers."""
import json
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from report import OUT, tile

RING = 0.018  # half-size of the visible red ring in normalized photo units
PER_GROUP = 15
CHOICES = (('in', '네', '네'), ('out', '아니요', '아니요'), ('unsure', '모르겠음', '모름'))


def ring(box):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return [cx - RING, cy - RING, cx + RING, cy + RING]


def pick():
    rows = [r for r in json.load(open(OUT / 'rows2.json')) if r['outcome'] == 'FP' and not r['bad']]
    rng = random.Random(20261111); chosen = []
    for out in (1, 0):
        pool = [r for r in rows if r['center_out'] == out]; rng.shuffle(pool); seen = set()
        for r in pool:
            if r['image'] not in seen and len(seen) < PER_GROUP:
                seen.add(r['image']); chosen.append(r)
    rng.shuffle(chosen)
    return chosen


def page(chosen):
    packet = {e['row']['id']: e for e in json.load(open('artifacts/surface-grounding-20261110/packet.json'))['entries']}
    cards, rules, spans = [], [], []
    for n, r in enumerate(chosen, 1):
        img = tile(r['image'], [], [(ring(packet[r['id']]['evidence']['top_geometry']['box']), (255, 0, 0))], 420)
        radios = ''.join(f'<input type="radio" id="r{n}{k}" name="p{n}"{" checked" if k == "in" else ""}><label for="r{n}{k}">{label}</label>' for k, label, _ in CHOICES)
        cards.append(f'<article><p><b>{n}.</b> 빨간 동그라미가 카드 위에 있나요?</p><img src="data:image/jpeg;base64,{img}"><div class="ch">{radios}</div></article>')
        for k, _, short in CHOICES:
            spans.append(f'<span class="n" id="s{n}{k}">{n}{short} </span>'); rules.append(f'body:has(#r{n}{k}:checked) #s{n}{k}{{display:inline}}')
    style = ('body{font:18px/1.5 system-ui;max-width:560px;margin:auto;padding:12px 12px 150px}article{border:1px solid #99a;margin:14px 0;padding:8px}'
             'img{max-width:100%;height:auto;display:block}.ch{display:flex;gap:8px;margin-top:8px}.ch input{position:absolute;opacity:0}'
             '.ch label{flex:1;text-align:center;padding:14px 0;border:2px solid #99a;border-radius:8px;font-size:18px}.ch input:checked+label{background:#14a;color:#fff;border-color:#14a}'
             '.n{display:none}#out{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:2px solid #14a;padding:10px;font-size:17px}'
             '.fb{display:none}@supports not selector(:has(*)){.fb{display:block}#out{display:none}}' + ''.join(rules))
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>빨간 고리 위치</title>'
            f'<style>{style}</style><h2>빨간 동그라미가 카드 위? ({len(chosen)}장)</h2><p>카드 위면 그대로 두고, 카드 밖이면 "아니요"를 누르세요.</p>'
            + ''.join(cards) + '<p class="fb">이 뷰어는 선택 연결을 지원하지 않습니다. "아니요"나 "모르겠음"인 사진 번호를 채팅에 적어 주세요.</p>'
            '<div id="out">아래 줄을 길게 눌러 복사해 채팅에 붙여넣기<br><span contenteditable="true">' + ''.join(spans) + '</span></div>')


def main():
    chosen = pick()
    (OUT / 'ring-review-30.html').write_text(page(chosen))
    (OUT / 'ring-review-30.map.json').write_text(json.dumps({n: dict(id=r['id'], mask_out=r['center_out']) for n, r in enumerate(chosen, 1)}))


if __name__ == '__main__':
    main()
