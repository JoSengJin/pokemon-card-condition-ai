"""Script-free phone page: tick photos whose green card outline is clearly wrong; one editable line lists the ticked numbers."""
import json
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from report import OUT, tile

COUNT = 30


def pick():
    rows = json.load(open(OUT / 'rows2.json'))
    photos = sorted({r['image'] for r in rows if r['outcome'] == 'FP' and r['center_out'] and not r['bad']})
    random.Random(20261111).shuffle(photos)
    return photos[:COUNT], rows


def page(photos, rows):
    hulls = json.load(open(OUT / 'hulls2.json')); packet = {e['row']['id']: e for e in json.load(open('artifacts/surface-grounding-20261110/packet.json'))['entries']}
    cards, rules, spans = [], [], []
    for n, path in enumerate(photos, 1):
        patches = [(packet[r['id']]['evidence']['top_geometry']['box'], (255, 0, 0)) for r in rows if r['image'] == path and r['outcome'] == 'FP' and r['center_out']]
        cards.append(f'<article><p><b>{n}</b></p><img src="data:image/jpeg;base64,{tile(path, hulls[path], patches, 420)}">'
                     f'<input type="checkbox" id="b{n}"><label for="b{n}">초록 선이 카드와 크게 다름</label></article>')
        spans.append(f'<span class="n" id="s{n}">{n}, </span>'); rules.append(f'body:has(#b{n}:checked) #s{n}{{display:inline}}')
    style = ('body{font:18px/1.5 system-ui;max-width:560px;margin:auto;padding:12px 12px 140px}article{border:1px solid #99a;margin:14px 0;padding:8px}'
             'img{max-width:100%;height:auto;display:block}label{display:block;padding:12px 0;font-size:18px}input[type=checkbox]{width:28px;height:28px;vertical-align:middle}'
             '.n{display:none}#out{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:2px solid #14a;padding:10px;font-size:17px}'
             '.fb{display:none}@supports not selector(:has(*)){.fb{display:block}#out{display:none}}' + ''.join(rules))
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>마스크 확인</title>'
            f'<style>{style}</style><h2>카드 윤곽(초록) 확인 · {len(photos)}장</h2><p>초록 선이 카드와 <b>크게</b> 다른 사진만 체크하세요. 조금 어긋난 건 무시. 빨강 상자는 모델 최고 패치입니다.</p>'
            + ''.join(cards) + '<p class="fb">이 뷰어는 체크 연결을 지원하지 않습니다. 틀린 사진의 번호를 채팅에 적어 주세요.</p>'
            '<div id="out">아래 줄을 길게 눌러 복사해 채팅에 붙여넣기<br><span contenteditable="true">마스크 틀림: ' + ''.join(spans) + '</span></div>')


def main():
    photos, rows = pick()
    (OUT / 'mask-review-30.html').write_text(page(photos, rows)); (OUT / 'mask-review-30.map.json').write_text(json.dumps(dict(enumerate(photos, 1))))


if __name__ == '__main__':
    main()
