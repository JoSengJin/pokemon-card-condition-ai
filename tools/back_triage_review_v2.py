"""Back-triage review pages v2: same questions and the same answer string as tools/back_triage_review.py, but lower-fatigue display (big buttons, progress badges, explicit 'no missed zone', tap-to-select result box). Reuses stored results; no model run, no Gemini."""
import base64
import html
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from card_condition.regions import region_box
from tools.back_triage_review import CHOICES, KO, PART, PCOLOR, PNAME, crop_img

CARDS_PER_PAGE = 2  # 2 cards keep each phone page under 0.7MB at crop 560px / quality 80
ID_LINE = re.compile(r'^([^\s=#]+)=')
SHORT = {CHOICES[1]: '보임', CHOICES[2]: '안 보임', CHOICES[3]: '모름'}

CSS = ('body{font:16px system-ui;max-width:640px;margin:0 auto;padding:8px;background:#fff;color:#111}img{width:100%}'
       '.top{position:sticky;top:0;background:#222;color:#fff;padding:8px;z-index:5;font-weight:700;border-radius:0 0 8px 8px}'
       '.intro{background:#f3f3f3;padding:10px;border-radius:8px}'
       'article{margin-top:56px;padding:12px 4px 4px;border-top:8px solid #444;border-radius:6px}article.done{border-top-color:#1a9a3a;background:#f2fbf4}'
       '.bd{display:inline-block;padding:3px 10px;border-radius:12px;background:#d33;color:#fff;font-weight:700;margin:2px 4px 2px 0}.bd.ok{background:#1a9a3a}'
       '.q{display:flex;gap:8px;margin:6px 0 18px}.bt{flex:1;min-height:56px;font-size:18px;border:3px solid #888;border-radius:12px;background:#fff;touch-action:manipulation}'
       '.bt[data-v$="보인다"].on{background:#d33;border-color:#900;color:#fff}.bt[data-v$="안 보인다"].on{background:#1a9a3a;border-color:#075;color:#fff}'
       '.bt[data-v="모르겠다"].on{background:#555;border-color:#222;color:#fff}'
       '.ph{position:relative;line-height:0;margin:10px 0}.c{position:absolute;box-sizing:border-box;border:2px dashed #fffb;touch-action:manipulation;-webkit-user-select:none;user-select:none}'
       '.c.on{background:#ff000077;border:5px solid #f00}.nmb{display:block;padding:14px;margin:8px 0;border:3px solid #888;border-radius:12px;font-size:18px}'
       '.nmb input{width:26px;height:26px;vertical-align:middle;margin-right:8px}.z img.big{position:fixed;inset:0;width:100vw;height:100vh;object-fit:contain;background:#000;z-index:9}'
       'textarea{width:100%;height:180px;font-size:14px}input[name=n]{width:100%;font-size:16px;padding:8px;box-sizing:border-box}')

SCRIPT = ("const D='(선택 안 함)',P=document.body.dataset.page,O=document.getElementById('o'),A=[...document.querySelectorAll('article')];"
          "function b(){return A.map(a=>a.dataset.id+'='+[...a.querySelectorAll('.q')].map(q=>q.dataset.name+':'+q.dataset.val).join(',')+';miss:'+[...a.querySelectorAll('.c.on')].map(c=>c.dataset.a).join('|')+';'+a.querySelector('[name=n]').value).join('\\n')}"
          "function u(a){const q=[...a.querySelectorAll('.q')],n=q.filter(x=>x.dataset.val!==D).length,z=a.querySelectorAll('.c.on').length,m=a.querySelector('.nm').checked,"
          "bd=a.querySelector('.bd'),ms=a.querySelector('.ms');bd.textContent=q.length+'칸 중 '+n+'칸 답함';bd.classList.toggle('ok',n===q.length);"
          "ms.textContent=z?'놓친 곳 '+z+'곳 표시함':m?'놓친 곳 없음 확인함':'놓친 곳: 아직 확인 안 함';ms.classList.toggle('ok',z>0||m);a.classList.toggle('done',n===q.length&&(z>0||m));"
          "const k=A.filter(x=>x.classList.contains('done')).length;document.getElementById('pg').textContent='이 쪽 완료 '+k+'/'+A.length+' 카드';"
          "O.value='# v2 쪽 '+P+' · 답한 카드 '+k+'/'+A.length+'\\n'+b()}"
          "document.addEventListener('click',e=>{const t=e.target,a=t.closest('article');if(t.classList.contains('bt')){const q=t.parentNode,off=q.dataset.val===t.dataset.v;q.dataset.val=off?D:t.dataset.v;q.querySelectorAll('.bt').forEach(x=>x.classList.toggle('on',!off&&x===t))}"
          "else if(t.classList.contains('c')){t.classList.toggle('on');if(t.classList.contains('on'))a.querySelector('.nm').checked=false}"
          "else if(t.matches('.z img'))t.classList.toggle('big');else if(t.id==='o'){O.select();O.setSelectionRange(0,99999)}if(a)u(a)});"
          "document.addEventListener('change',e=>{const a=e.target.closest('article');if(e.target.classList.contains('nm')&&e.target.checked)a.querySelectorAll('.c.on').forEach(c=>c.classList.remove('on'));if(a)u(a)});"
          "document.addEventListener('input',e=>{const a=e.target.closest('article');if(a)u(a)});A.forEach(u);")


def answered_ids(dirs):
    """Card ids that already have a human answer in any answers*.txt / walkthrough*.txt of the given folders (comment and noise lines ignored)."""
    ids = set()
    for d in dirs:
        for path in [*Path(d).glob('answers*.txt'), *Path(d).glob('walkthrough*.txt')]:
            ids |= {m.group(1) for m in map(ID_LINE.match, path.read_text(encoding='utf-8').splitlines()) if m}
    return ids


def remaining(requests, results, answered):
    """Unanswered cards in request order as (request, result, n); results must align with requests."""
    pairs = [(r, x) for r, x in zip(requests, results) if r['id'] not in answered]
    assert all(r['id'] == x['id'] for r, x in pairs), 'results are not aligned with requests'
    return [(r, x, i + 1) for i, (r, x) in enumerate(pairs)]


def summary_comment(page, done, total):
    """First line of the result box; has no '=' so the answer reader (lines with id=...) skips it."""
    return f'# v2 쪽 {page} · 답한 카드 {done}/{total}'


def zone_item(im, draw, request, part, res):
    """Question block for one part: its highest-ranked zone enlarged, three big buttons; a held part gets a notice and no question."""
    zones = res['results'][part].get('zones') or []
    if not zones or res['results'][part].get('status') != 'ranked':
        return f"<p>{PART[part]}: 점수를 못 냈습니다({html.escape(res['results'][part].get('reason', ''))}). 사람이 직접 확인하세요.</p>"
    z = zones[0]
    box = region_box(request['box'], z['area'])
    w, h = im.size
    draw.rectangle([box[0]*w, box[1]*h, box[2]*w, box[3]*h], outline=PCOLOR[part], width=max(5, w//200))
    buttons = ''.join(f'<button type="button" class="bt" data-v="{c}">{SHORT[c]}</button>' for c in CHOICES[1:])
    return (f'<div class="z"><img src="data:image/jpeg;base64,{crop_img(im, box)}"><p><b>{PNAME[part]} · {PART[part]} · {KO[z["area"]]}</b> (AI 점검 우선순위: {z["label"]})<br>이 사진에 문제가 보이나요? (사진을 탭하면 크게)</p>'
            f'<div class="q" data-name="{part}" data-val="{CHOICES[0]}">{buttons}</div></div>')


def card_v2(request, res, n, total):
    im = Image.open(request['image']).convert('RGB')
    full = im.copy()
    draw = ImageDraw.Draw(full)
    items = ''.join(zone_item(im, draw, request, p, res) for p in ('edge', 'corner', 'surface'))
    obs = res['results'].get('observation_limit', {})
    obs_text = obs.get('label') if obs.get('status') == 'scored' else f"보류({obs.get('reason', '결과 없음')}) — 사람이 직접 확인하세요."
    full.thumbnail((640, 860))
    buf = io.BytesIO()
    full.save(buf, 'JPEG', quality=70)
    left, top, right, bottom = request['box']
    cells = ''.join(f'<div class="c" data-a="{a}" style="left:{(left+(i%3)*(right-left)/3)*100:.2f}%;top:{(top+(i//3)*(bottom-top)/3)*100:.2f}%;width:{(right-left)/3*100:.2f}%;height:{(bottom-top)/3*100:.2f}%"></div>' for i, a in enumerate(KO))
    sha = ' · '.join(f'{k} {v["model_sha256"][:8]}' for k, v in res['results'].items())
    nq = items.count('class="q"')
    return (f'<article data-id="{html.escape(request["id"])}"><h2>카드 {n}/{total} · {html.escape(request["id"][-8:])}</h2>'
            f'<span class="bd">{nq}칸 중 0칸 답함</span><span class="bd ms">놓친 곳: 아직 확인 안 함</span>'
            f'<p><b>전체 사진</b>: 색 상자 = 아래 확대 사진 위치. AI가 <b>놓친 곳</b>(문제가 보이는데 상자가 없는 곳)은 여기서 탭(다시 탭하면 해제).</p>'
            f'<div class="ph"><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">{cells}</div>'
            f'<label class="nmb"><input type="checkbox" class="nm">놓친 곳 없음 (확인했음)</label>{items}'
            f'<p><b>사진 재촬영 권고</b>: {html.escape(str(obs_text))}</p><p style="font-size:12px;color:#555">모델 버전: {sha}</p><input name="n" placeholder="메모(선택)"></article>')


def page_v2(body, page, pages, ncards):
    intro = ('AI가 카드 뒷면에서 먼저 보라고 짚은 칸을 확대해 보여 줍니다(빨강=가장자리, 파랑=모서리, 노랑=안쪽 면). 사진에 보이는 대로 보임/안 보임/모름을 고르세요(AI가 맞았는지는 따지지 않습니다). '
             '그다음 전체 사진에서 AI가 놓친 곳을 탭하고, 없으면 \'놓친 곳 없음\'을 체크하세요. 재촬영 권고가 낮음이어도 사진이 괜찮다는 뜻은 아니며 사람이 확인해야 합니다.')
    return (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>후면 점검 검토 v2</title><style>{CSS}</style>'
            f'<body data-page="{page}"><div class="top">v2 쪽 {page}/{pages} · <span id="pg">이 쪽 완료 0/{ncards} 카드</span></div><p class="intro">{intro}</p>{body}'
            f'<h3>결과 (탭하면 전체 선택 → 복사해서 채팅에 붙여넣기)</h3><textarea id="o" readonly>{summary_comment(page, 0, ncards)}</textarea><script>{SCRIPT}</script>')


def main(out, requests_path, results_path, *answer_dirs):
    requests = json.loads(Path(requests_path).read_text())
    results = json.loads(Path(results_path).read_text())['results']
    cards = remaining(requests, results, answered_ids(answer_dirs))
    Path(out).mkdir(parents=True, exist_ok=True)
    pages = -(-len(cards) // CARDS_PER_PAGE)
    for p in range(pages):
        chunk = cards[p*CARDS_PER_PAGE:(p+1)*CARDS_PER_PAGE]
        body = ''.join(card_v2(r, x, n, len(cards)) for r, x, n in chunk)
        Path(out, f'review-v2-{p+1:02d}.html').write_text(page_v2(body, p + 1, pages, len(chunk)), encoding='utf-8')
    return dict(cards=len(cards), pages=pages, first_id=cards[0][0]['id'] if cards else None)


if __name__ == '__main__':
    print(main(*sys.argv[1:]))
