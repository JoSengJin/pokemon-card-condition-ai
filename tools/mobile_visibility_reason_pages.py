"""Static phone page: for BACK photos already answered '제한', tick the visible reason(s). Writes no labels; the answer text is pasted back.
Answer line: '<group>/back=glare,perspective' or '<group>/back=미확인' (nothing ticked). Reasons use the existing visibility_issues vocabulary.
Ticks mean factors VISIBLE NOW, not a recalled cause of the earlier 제한 answer; 'not_limited' only flags a re-judge need and never changes the earlier answer."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE as BASE_STYLE, encode  # noqa: E402

REASONS = (('perspective', '심한 각도'), ('glare', '빛반사'), ('shadow', '그림자'), ('obstruction', '가림'),
           ('cropped', '잘림'), ('blur', '흐림'), ('low_resolution', '저해상도'), ('other', '기타'), ('not_limited', '이 사진은 제한이 아닌 듯'))
STYLE = BASE_STYLE + "label{display:inline-block;border:1px solid #888;border-radius:8px;padding:10px 12px;margin:4px 4px 0 0;font-size:18px}input:checked+span{font-weight:700;color:#1e5aff}"
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>{const v=[...a.querySelectorAll('input:checked')].map(i=>i.value);return a.dataset.id+'/'+a.dataset.side+'='+(v.length?v.join(','):'미확인')}).join('\\n')}
arts.forEach(a=>a.querySelectorAll('input').forEach(i=>i.addEventListener('change',show)));show();"""


def article(item):
    boxes = ''.join(f'<label><input type="checkbox" value="{k}" hidden><span>{html.escape(w)}</span></label>' for k, w in REASONS)
    return (f'<article data-id="{html.escape(item["group"])}" data-side="{item["side"]}"><h2>{html.escape(item["group"])} ({item["side"]})</h2>'
            f'<img src="data:image/jpeg;base64,{encode(item["image"])}"><div>{boxes}</div></article>')


def positives(holdout_rows_json):
    """Rows the human already answered 제한 (target 1); unanswered/정상 rows are never shown."""
    rows = json.loads(Path(holdout_rows_json).read_text(encoding='utf-8'))
    return [r for r in rows if r['target'] == 1 and r['side'] == 'back']


def main(holdout_rows_json, out_path):
    guide = '<p>이미 <b>제한</b>으로 답한 뒷면 사진입니다. 기억할 필요 없이 <b>지금 이 사진에서 카드 상태를 보기 어렵게 하는 요인이 보이면</b> 모두 누르세요(복수 가능). 모르겠으면 아무것도 누르지 않으면 미확인입니다. 제한이 아니라고 느껴지면 맨 아래 항목만 누르세요(기존 답은 바뀌지 않고 재판정 후보로만 표시).</p>'
    items = positives(holdout_rows_json)
    body = guide + ''.join(article(i) for i in items) + '<textarea id="out" readonly></textarea>'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    print(main(*sys.argv[1:3]))
