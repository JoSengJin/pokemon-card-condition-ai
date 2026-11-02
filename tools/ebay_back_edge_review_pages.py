"""Static phone pages: confirm card box and whole-back-edge condition for chosen eBay back photos; writes no labels."""
import html
import json
import sys
from pathlib import Path

from train_geometry_review_pages import preview  # noqa: E402

BATCH = 7
NOTES = {
    'ebay-pair-c29f4cd0872f3d': '카드가 여러 장 겹쳐 보여 한 장 판단이 어려울 수 있음',
    'ebay-pair-2c47c2eb21aa47': '상자가 카드보다 많이 넓음(자동 제안)',
    'ebay-pair-4e888bacf2283d': '슬리브에 들어 있는 사진',
}
SCRIPT = """
const rows=[...document.querySelectorAll('article')];
function build(){return rows.map(a=>a.dataset.id+'='+a.querySelector('[name=b]').value+','+a.querySelector('[name=e]').value).join('\\n')}
function show(){document.getElementById('out').value=build()}
document.querySelectorAll('select').forEach(s=>s.addEventListener('change',show));show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def article(number, face):
    note = NOTES.get(face['id'], '')
    return (f'<article data-id="{html.escape(face["id"])}"><h2>{number}. {html.escape(face["title"][:60])}</h2>'
            f'<img alt="" src="data:image/jpeg;base64,{preview(dict(image=face["image"], box=face["box"]))}">'
            + (f'<p>Claude 참고(미확인): {html.escape(note)}</p>' if note else '') +
            '<label>파란 상자<select name="b"><option value="미확인">미확인</option><option value="맞음">맞음</option>'
            '<option value="잘림">카드가 상자 밖으로 잘림</option></select></label>'
            '<label>뒷면 8개 엣지 구역 전체<select name="e"><option value="미확인">미확인</option>'
            '<option value="정상">전부 정상</option><option value="결함">결함 있음</option>'
            '<option value="불가">판단 불가(흐림·가림)</option></select></label></article>')


def page(number, total, start, faces):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>뒷면 엣지 확인 {number}/{total}</title><style>body{{font:17px/1.6 system-ui;margin:0 auto;max-width:760px;padding:16px}}'
            'img{width:100%}select,button{font-size:18px;min-height:44px;width:100%;margin:6px 0}textarea{width:100%;height:220px;font-size:15px}'
            'article{border-top:1px solid #aaa;margin-top:22px}</style>'
            f'<h1>뒷면 엣지 확인 {number}/{total}</h1><p>1) 파란 상자 안에 카드가 다 들어오면 “맞음”입니다(넓거나 비스듬해도 됩니다). '
            '2) 뒷면 네 변 테두리에 흰 벗겨짐·눌림·갈라짐이 전혀 없으면 “전부 정상”, 하나라도 보이면 “결함 있음”, '
            '사진으로 판단이 어려우면 “판단 불가”입니다. 확신이 없으면 “판단 불가”로 두세요. 자동 저장하지 않으며 사용자가 고른 값만 기록합니다.</p>'
            + ''.join(article(start + k, f) for k, f in enumerate(faces, 1)) +
            '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
            f'<script>{SCRIPT}</script></html>')


def main(root):
    root = Path(root)
    faces = json.loads((root / 'back-faces.json').read_text())
    out = root / 'back-edge'
    out.mkdir(exist_ok=False)
    batches = [faces[i:i + BATCH] for i in range(0, len(faces), BATCH)]
    for n, batch in enumerate(batches, 1):
        (out / f'back-edge-{n}.html').write_text(page(n, len(batches), (n - 1) * BATCH, batch))
    print(len(faces), 'faces,', len(batches), 'pages ->', out)


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    main(sys.argv[1])
