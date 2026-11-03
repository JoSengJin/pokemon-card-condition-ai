"""C4 expansion phone pages (blank, no prefill, no predictions). Per front: proposed box overlay -> box verdict, centering verdict, and for train items 8 taps (card outer L,R,T,B then printed inner frame L,R,T,B; same order and window format as mobile_centering_mark_pages). Pasted-back line: id|front|window|8 values or 미확인|centering|box."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_centering_mark_pages import STEPS, STYLE, crop_uri, window  # noqa: E402

SCRIPT = """const STEPS=%s;
document.querySelectorAll('article').forEach(a=>{const c=a.querySelector('canvas'),g=c.getContext('2d'),img=new Image(),w=a.dataset.w.split(',').map(Number),bx=a.dataset.b.split(',').map(Number),taps=a.dataset.taps=='1';let pts=[];
function draw(){g.drawImage(img,0,0,c.width,c.height);g.strokeStyle='#fa0';g.lineWidth=2;g.strokeRect((bx[0]-w[0])/(w[2]-w[0])*c.width,(bx[1]-w[1])/(w[3]-w[1])*c.height,(bx[2]-bx[0])/(w[2]-w[0])*c.width,(bx[3]-bx[1])/(w[3]-w[1])*c.height);
pts.forEach((p,i)=>{g.strokeStyle=i<4?'#e22':'#12c';g.beginPath();if(i%%4<2){g.moveTo(p*c.width,0);g.lineTo(p*c.width,c.height)}else{g.moveTo(0,p*c.height);g.lineTo(c.width,p*c.height)}g.stroke()});
const s=a.querySelector('.step');if(taps)s.textContent=pts.length<8?(pts.length+1)+'/8 '+STEPS[pts.length]+' — 탭':'표시 완료';update()}
function update(){const m=taps&&pts.length==8?pts.map((p,i)=>(i%%4<2?(w[0]+p*(w[2]-w[0])):(w[1]+p*(w[3]-w[1]))).toFixed(4)).join(','):'미확인';a.dataset.v=m;
const cen=a.querySelector('.cen').value,box=a.querySelector('.box').value;a.dataset.s=(cen&&box)?[a.dataset.id,'front',a.dataset.w,m,cen,box].join('|'):'';document.getElementById('out').value=[...document.querySelectorAll('article')].filter(x=>x.dataset.s).map(x=>x.dataset.s).join('\\n')}
img.onload=()=>{c.width=img.width;c.height=img.height;draw()};img.src=a.dataset.src;
if(taps)c.addEventListener('click',e=>{if(pts.length>=8)return;const r=c.getBoundingClientRect(),i=pts.length;pts.push(i%%4<2?(e.clientX-r.left)/r.width:(e.clientY-r.top)/r.height);draw()});
a.querySelector('.undo').onclick=()=>{pts.pop();draw()};a.querySelectorAll('select').forEach(s=>s.onchange=update)});"""
SELECT = '<label>{t} <select class="{c}"><option value="">선택</option>{o}</select></label>'


PANEL = ('<div id="bar" style="position:sticky;bottom:0;background:#fff;border-top:2px solid #333;padding:8px;z-index:9">'
         '<div><b id="cnt">0</b>/<span id="tot"></span> 완료 <button id="cp" style="font-size:17px;padding:6px 14px">전체 선택·복사</button> <span id="msg"></span></div>'
         '<textarea id="out" readonly style="width:100%;height:90px;font-size:12px"></textarea></div>')
COPY = ("""const o=document.getElementById('out');document.getElementById('tot').textContent=document.querySelectorAll('article').length;
function cnt(){document.getElementById('cnt').textContent=[...document.querySelectorAll('article')].filter(x=>x.dataset.s).length}
document.querySelectorAll('select').forEach(s=>s.addEventListener('change',()=>setTimeout(cnt,0)));document.querySelectorAll('canvas').forEach(c=>c.addEventListener('click',()=>setTimeout(cnt,0)));
function pick(){o.focus();o.select();o.setSelectionRange(0,99999);let ok=false;try{ok=document.execCommand('copy')}catch(e){}document.getElementById('msg').textContent=ok?'복사됨':'선택됨 — 길게 눌러 복사'}
document.getElementById('cp').onclick=pick;o.onclick=pick;""")


def options(values):
    return ''.join(f'<option value="{v}">{v}</option>' for v in values)


def article(item, taps):
    win = window(item['box'], .08)
    tool = ('<div class="step"></div><button class="undo">되돌리기</button>' if taps else '<div class="step">탭 없이 아래 두 항목만 선택</div><button class="undo" hidden></button>')
    return (f'<article data-id="{html.escape(item["id"])}" data-w="{",".join(f"{v:.4f}" for v in win)}" data-b="{",".join(f"{v:.4f}" for v in item["box"])}" data-taps="{int(taps)}" data-s="" data-src="{crop_uri(item["image"], win)}">'
            f'<h2>{html.escape(item["id"])}</h2>{tool}<canvas></canvas>'
            + SELECT.format(t='주황 상자 판정', c='box', o=options(['맞음', '카드가 상자 밖으로 나감', '앞면 아님/판정불가']))
            + SELECT.format(t='센터링(사람 판단)', c='cen', o=options(['결함', '정상', '미확인'])) + '</article>')


def main(pool_json, role, start, count, out_path):
    items = [i for i in json.loads(Path(pool_json).read_text()) if i['role'] == role][start:start+count]
    taps = role == 'train'
    guide = ('<p>주황 사각형은 자동 제안 상자입니다(정답 아님). 카드 전체가 상자 안에 들어오면 "맞음". '
             + ('카드 바깥 가장자리 4곳(빨강: 왼·오·위·아래)과 인쇄 틀 안쪽 경계 4곳(파랑)을 차례로 탭하세요. ' if taps else '')
             + '센터링은 사진에서 보이는 사람 판단입니다. 확실치 않으면 미확인.</p>')
    body = guide + ''.join(article(i, taps) for i in items) + PANEL
    script = SCRIPT % json.dumps(STEPS, ensure_ascii=False)
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}select{{font-size:17px;margin:6px 0;display:block}}</style>{body}<script>{script}{COPY}</script>', encoding='utf-8')
    return len(items)


if __name__ == '__main__':
    print(main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]))
