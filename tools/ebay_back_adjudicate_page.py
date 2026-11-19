"""Adjudication page for the step-0 disagreements: one phone page, two people decide together per photo (answer + reason).
Shows the photo only (900px), no first/second answers. Writes no labels; the pasted text is the human record."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE, encode  # noqa: E402

CHOICES = ('제한-반사', '제한-잘림', '제한-흐림', '제한-가림·기타', '정상', '자격아님-카드아님', '자격아님-프레임', '모름')
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>a.dataset.id+'='+a.dataset.s).join('\\n')}
arts.forEach(a=>{a.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{a.dataset.s=b.dataset.v;a.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));show()}))});show();"""


def article(item):
    buttons = ''.join(f'<button data-v="{c}">{c}</button>' for c in CHOICES)
    return (f'<article data-id="{html.escape(item["id"])}" data-s="미확인"><h2>{html.escape(item["id"][-6:])}</h2>'
            f'<img src="data:image/jpeg;base64,{encode(item["path"], 900)}"><div class="row">{buttons}</div></article>')


def main(disagree_json, out_path):
    items = json.loads(Path(disagree_json).read_text(encoding='utf-8'))
    body = ('<p>두 사람이 <b>함께</b> 사진을 보고 한 가지 답을 고르세요. 확대해서 봐도 됩니다. 이전 답은 알려 주지 않습니다. '
            '<b>제한-*</b>: 카드 상태를 볼 수 없음(이유 선택). <b>정상</b>: 문제없이 볼 수 있음. '
            '<b>자격아님-카드아님</b>: 실제 카드 뒷면이 아님(금속·복제 등). <b>자격아님-프레임</b>: 네 변이 다 안 보임. 안 서면 <b>모름</b>.</p>'
            + ''.join(article(i) for i in items) + '<textarea id="out" readonly></textarea>')
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    print(main(*sys.argv[1:3]))
