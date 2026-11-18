"""Static phone page: re-judge BACK photos that were answered 제한 but flagged not_limited in the reason pass. Writes no labels; the answer text is pasted back
and validated by parse_rejudge. Earlier answers are never changed. Answer line: '<group>/back=제한|정상|미확인;확신|애매'."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE as BASE_STYLE, encode  # noqa: E402

VERDICTS = ('제한', '정상', '미확인')
CONFIDENCE = ('확신', '애매')
STYLE = BASE_STYLE + ".row{flex-wrap:wrap}.row.c button{font-size:16px}"
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>a.dataset.id+'/back='+(a.dataset.v||'미확인')+';'+(a.dataset.c||'애매')).join('\\n')}
arts.forEach(a=>a.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{a.dataset[b.dataset.k]=b.dataset.v;
a.querySelectorAll('button[data-k="'+b.dataset.k+'"]').forEach(x=>x.classList.toggle('on',x===b));show()})));show();"""


def select_candidates(answers_text):
    """Groups whose reason-pass line ticked not_limited, in file order."""
    pairs = (line.strip().rsplit('=', 1) for line in answers_text.splitlines() if '=' in line)
    return [key.split('/')[0] for key, value in pairs if 'not_limited' in value.split(',')]


def parse_rejudge(text, expected_groups):
    """Return {group: (verdict, confidence)}; raise ValueError unless exactly the expected groups answered with known words."""
    out = {}
    for line in filter(None, (l.strip() for l in text.splitlines())):
        key, _, value = line.partition('=')
        verdict, _, conf = value.partition(';')
        if verdict not in VERDICTS or conf not in CONFIDENCE or not key.endswith('/back'):
            raise ValueError(f'bad answer: {line}')
        out[key[:-5]] = (verdict, conf)
    if set(out) != set(expected_groups):
        raise ValueError('answered groups differ from candidates')
    return out


def article(item):
    def row(kind, words):
        return f'<div class="row c">' + ''.join(f'<button data-k="{kind}" data-v="{w}">{w}</button>' for w in words) + '</div>'
    return (f'<article data-id="{html.escape(item["group"])}"><h2>{html.escape(item["group"])} (back)</h2>'
            f'<img src="data:image/jpeg;base64,{encode(item["image"])}">{row("v", VERDICTS)}{row("c", CONFIDENCE)}</article>')


def main(answers_path, holdout_rows_json, out_path):
    wanted = select_candidates(Path(answers_path).read_text(encoding='utf-8'))
    rows = {r['group']: r for r in json.loads(Path(holdout_rows_json).read_text(encoding='utf-8')) if r['side'] == 'back'}
    guide = '<p>아래 사진은 이전에 <b>제한</b>으로 답했지만 요인이 안 보인다고 표시된 후면입니다. <b>지금 사진만 보고</b> 제한/정상/미확인과 확신/애매를 각각 고르세요. 기존 답은 바뀌지 않고 이 응답은 별도로 기록됩니다. 아무것도 안 누르면 미확인;애매입니다.</p>'
    body = guide + ''.join(article(rows[g]) for g in wanted) + '<textarea id="out" readonly></textarea>'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    return len(wanted)


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
