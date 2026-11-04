"""Static phone pages: confirm the card box, tap the 9 SURFACE areas (미확인>정상>결함), copy the answer text. Writes no labels."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

from card_condition.label_instructions import SURFACE_INSTRUCTIONS

AREAS = [('upper_left', 0, 0), ('upper_center', 1, 0), ('upper_right', 2, 0), ('middle_left', 0, 1), ('center', 1, 1), ('middle_right', 2, 1), ('lower_left', 0, 2), ('lower_center', 1, 2), ('lower_right', 2, 2)]
STYLE = """body{font:17px/1.5 system-ui;margin:0 auto;max-width:720px;padding:12px}article{border-top:2px solid #888;margin-top:20px;padding-top:6px}
.ph{position:relative;line-height:0}.ph img{width:100%;display:block}.c{position:absolute;box-sizing:border-box;border:1px dashed #fff9;font:700 18px system-ui;color:#fff;
display:flex;align-items:center;justify-content:center;text-shadow:0 0 4px #000;line-height:1.2;user-select:none;-webkit-user-select:none}
.c[data-s=정상]{background:#1a9e4a88}.c[data-s=결함]{background:#e0282888}.bx{position:absolute;border:3px solid #1e5aff;pointer-events:none;box-sizing:border-box}
.h{position:absolute;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;background:#ff3c3ccc;touch-action:none}
.row{display:flex;gap:8px;margin:8px 0}.row button,#copy{flex:1;font-size:18px;min-height:48px}button.on{background:#1e5aff;color:#fff}
textarea{width:100%;height:240px;font-size:15px}#copy{width:100%}h2{font-size:17px;margin:6px 0}"""
SCRIPT = """
const NEXT={'미확인':'정상','정상':'결함','결함':'미확인'};
const arts=[...document.querySelectorAll('article')];
const fmt=v=>v.toFixed(4);
function build(){return arts.map(a=>a.dataset.id+'='+(a.dataset.ok==='1'?'확인':'미확인')+';box:'+a.b.map(fmt).join(',')+';'+[...a.querySelectorAll('.c')].map(c=>c.dataset.a+':'+c.dataset.s).join(';')).join('\\n')}
function show(){document.getElementById('out').value=build()}
function layout(a){const[l,t,r,b]=a.b,w=(r-l)/3,h=(b-t)/3,bx=a.querySelector('.bx');
  bx.style.cssText='left:'+l*100+'%;top:'+t*100+'%;width:'+(r-l)*100+'%;height:'+(b-t)*100+'%';
  a.querySelectorAll('.c').forEach(c=>{c.style.cssText='left:'+(l+c.dataset.x*w)*100+'%;top:'+(t+c.dataset.y*h)*100+'%;width:'+w*100+'%;height:'+h*100+'%'});
  a.querySelectorAll('.h').forEach(e=>{e.style.left=(e.dataset.k.includes('l')?l:r)*100+'%';e.style.top=(e.dataset.k.includes('t')?t:b)*100+'%'})}
arts.forEach(a=>{a.b=JSON.parse(a.dataset.box);layout(a);
  a.querySelectorAll('.c').forEach(c=>c.addEventListener('click',()=>{c.dataset.s=NEXT[c.dataset.s];c.firstChild.textContent=c.dataset.s==='미확인'?'':c.dataset.s;show()}));
  a.querySelectorAll('.h').forEach(h=>{let on=false;
    h.addEventListener('pointerdown',e=>{on=true;h.setPointerCapture(e.pointerId);e.preventDefault()});
    h.addEventListener('pointerup',()=>{on=false});
    h.addEventListener('pointermove',e=>{if(!on)return;const r=a.querySelector('.ph').getBoundingClientRect();if(!r.width||!r.height)return;
      const x=Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),y=Math.min(1,Math.max(0,(e.clientY-r.top)/r.height)),k=h.dataset.k;
      if(k.includes('l'))a.b[0]=Math.min(x,a.b[2]-.05);else a.b[2]=Math.max(x,a.b[0]+.05);
      if(k.includes('t'))a.b[1]=Math.min(y,a.b[3]-.05);else a.b[3]=Math.max(y,a.b[1]+.05);
      a.dataset.ok='0';a.querySelector('.ok').classList.remove('on');layout(a);show()})});
  a.querySelector('.ok').addEventListener('click',e=>{const on=a.dataset.ok!=='1';a.dataset.ok=on?'1':'0';e.target.classList.toggle('on',on);show()});
  a.querySelector('.alln').addEventListener('click',()=>{a.querySelectorAll('.c').forEach(c=>{c.dataset.s='정상';c.firstChild.textContent='정상'});show()});
  a.querySelector('.reset').addEventListener('click',()=>{a.querySelectorAll('.c').forEach(c=>{c.dataset.s='미확인';c.firstChild.textContent=''});show()})});
show();
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def photo(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    image.thumbnail((800, 800))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=72)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, face):
    preset = face.get('preset') or {}
    states = preset.get('states', {})
    cells = ''.join(f'<div class="c" data-a="{a}" data-s="{states.get(a, "미확인")}" data-x="{x}" data-y="{y}"><i>{"" if states.get(a, "미확인") == "미확인" else states[a]}</i></div>' for a, x, y in AREAS)
    handles = ''.join(f'<div class="h" data-k="{k}"></div>' for k in ('lt', 'rt', 'rb', 'lb'))
    return (f'<article data-id="{html.escape(face["id"])}" data-ok="{1 if preset.get("ok") else 0}" data-box="{html.escape(json.dumps(preset.get("box") or face["box"]))}">'
            f'<h2>{number}. {html.escape(face["title"][:60])} ({face["id"].rsplit("/", 1)[-1]})</h2>'
            f'<div class="ph"><img alt="" src="data:image/jpeg;base64,{photo(face["image"])}"><div class="bx"></div>{cells}{handles}</div>'
            f'<div class="row"><button class="ok{" on" if preset.get("ok") else ""}">상자 확인(카드가 안에 들어옴)</button></div>'
            '<div class="row"><button class="alln">9칸 전부 정상</button><button class="reset">구역 초기화</button></div></article>')


def presets(answers_path):
    """Previous pasted answers -> {row id: dict(ok, box, states)} so a re-check page opens with the earlier input."""
    out = {}
    for line in filter(None, (l.strip() for l in Path(answers_path).read_text(encoding='utf-8').splitlines())):
        key, rest = line.split('=', 1)
        head, boxpart, *items = rest.split(';')
        out[key.rsplit('/', 1)[0]] = dict(ok=head == '확인', box=[float(v) for v in boxpart.removeprefix('box:').split(',')], states=dict(i.split(':') for i in items))
    return out


def main(review_jsonl, ids_text, out_path, side='back', answers_path=None):
    """ids_text: whitespace-separated row ids; each page face starts at the row's current card box for `side`."""
    rows = {r['id']: r for r in map(json.loads, Path(review_jsonl).read_text(encoding='utf-8').splitlines()) if r.get('id')}
    faces, pre = [], presets(answers_path) if answers_path else {}
    for rid in ids_text.split():
        annotation = rows[rid]['side_annotations'][side]
        faces.append(dict(id=f'{rid}/{side}', image=annotation['image'], box=annotation['box'], title=rows[rid].get('title') or rid, preset=pre.get(rid)))
    body = ''.join(article(n, f) for n, f in enumerate(faces, 1))
    Path(out_path).write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>표면 구역 라벨 입력</title><style>{STYLE}</style><h1>표면 구역 라벨</h1>'
        + SURFACE_INSTRUCTIONS +
        '<p>빨간 점 4개를 끌어 파란 상자가 <b>카드가 전부 안에 들어오게</b> 맞추세요(딱 맞을 필요 없음). 상자를 고쳤다면 마지막에 “상자 확인”을 누르세요. '
        '각 표면 칸은 탭할 때마다 미확인→정상→결함으로 바뀝니다. 모르면 미확인으로 두세요. 자동 저장하지 않습니다.</p>' + body +
        '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
        f'<script>{SCRIPT}</script></html>', encoding='utf-8')
    return len(faces)


if __name__ == '__main__':
    print(main(*sys.argv[1:4], *(['back', sys.argv[4]] if len(sys.argv) > 4 else [])))
