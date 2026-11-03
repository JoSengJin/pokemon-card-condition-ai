"""C4 train 4-tap pages for fronts that already have a centering label: tap card outer TOP, card outer BOTTOM, printed frame inner TOP, inner BOTTOM (y only). Line: id|front|y_outer_top,y_outer_bottom,y_inner_top,y_inner_bottom (normalized on the full photo). Window = proposed box +8% (full photo where the box was judged wrong). No predictions shown. Optional 6th arg `x`: same page for card outer LEFT, outer RIGHT, inner LEFT, inner RIGHT (x only, vertical lines)."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_label_pages import COPY, PANEL, crop_uri  # noqa: E402
from mobile_centering_mark_pages import STYLE, window  # noqa: E402

STEPS = ['카드 바깥 위쪽 가장자리', '카드 바깥 아래쪽 가장자리', '인쇄 틀 안쪽 위 경계', '인쇄 틀 안쪽 아래 경계']
X_STEPS = ['카드 바깥 왼쪽 가장자리', '카드 바깥 오른쪽 가장자리', '인쇄 틀 안쪽 왼쪽 경계', '인쇄 틀 안쪽 오른쪽 경계']
X_SWAPS = [('g.moveTo(0,p*c.height);g.lineTo(c.width,p*c.height)', 'g.moveTo(p*c.width,0);g.lineTo(p*c.width,c.height)'),
           ('w[1]+p*(w[3]-w[1])', 'w[0]+p*(w[2]-w[0])'), ('(e.clientY-r.top)/r.height', '(e.clientX-r.left)/r.width')]
SCRIPT = """const STEPS=%s;const o=document.getElementById('out');
function sync(){const d=[...document.querySelectorAll('article')].filter(x=>x.dataset.s);o.value=d.map(x=>x.dataset.s).join('\\n');document.getElementById('cnt').textContent=d.length}
document.querySelectorAll('article').forEach(a=>{const c=a.querySelector('canvas'),g=c.getContext('2d'),img=new Image(),w=a.dataset.w.split(',').map(Number);let pts=[];
function draw(){g.drawImage(img,0,0,c.width,c.height);pts.forEach((p,i)=>{g.strokeStyle=i<2?'#e22':'#12c';g.lineWidth=2;g.beginPath();g.moveTo(0,p*c.height);g.lineTo(c.width,p*c.height);g.stroke()});
a.querySelector('.step').textContent=a.querySelector('.na').checked?'판정불가':pts.length<4?(pts.length+1)+'/4 '+STEPS[pts.length]+' — 탭':'완료';
a.dataset.s=a.querySelector('.na').checked?[a.dataset.id,'front','판정불가'].join('|'):pts.length==4?[a.dataset.id,'front',pts.map(p=>(w[1]+p*(w[3]-w[1])).toFixed(4)).join(',')].join('|'):'';sync()}
img.onload=()=>{c.width=img.width;c.height=img.height;draw()};img.src=a.dataset.src;
c.addEventListener('click',e=>{if(pts.length>=4)return;const r=c.getBoundingClientRect();pts.push((e.clientY-r.top)/r.height);draw()});
a.querySelector('.undo').onclick=()=>{pts.pop();draw()};a.querySelector('.na').addEventListener('change',draw);a._draw=draw});
setInterval(()=>document.querySelectorAll('article').forEach(a=>a._draw&&a._draw()),700);
%s"""


def main(pool_json, boxok_json, start, count, out_path, axis='y'):
    pool = {r['id']: r for r in json.loads(Path(pool_json).read_text())}
    boxok = json.loads(Path(boxok_json).read_text())
    arts = []
    for i in list(boxok)[start:start + count]:
        item = pool[i]
        win = window(item['box'], .08) if boxok[i] else [0, 0, 1, 1]
        arts.append(f'<article data-id="{html.escape(i)}" data-w="{",".join(f"{v:.4f}" for v in win)}" data-s="" data-src="{crop_uri(item["image"], win)}">'
                    f'<h2>{html.escape(i)}</h2><div class="step"></div><button class="undo">되돌리기</button><canvas></canvas>'
                    '<label><input type="checkbox" class="na"> 앞면 아님/판정불가</label></article>')
    guide = '<p>위 가장자리 → 아래 가장자리 → 인쇄 틀 안쪽 위 → 안쪽 아래 순서로 가로선 위치만 탭하세요(빨강 2, 파랑 2).</p>'
    script = SCRIPT % (json.dumps(X_STEPS if axis == 'x' else STEPS, ensure_ascii=False), COPY.split('\n', 1)[1])
    if axis == 'x':
        guide = '<p>왼쪽 가장자리 → 오른쪽 가장자리 → 인쇄 틀 안쪽 왼쪽 → 안쪽 오른쪽 순서로 세로선 위치만 탭하세요(빨강 2, 파랑 2).</p>'
        for old, new in X_SWAPS:
            assert old in script
            script = script.replace(old, new)
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{guide}{"".join(arts)}{PANEL}<script>{script}</script>', encoding='utf-8')
    return len(arts)


if __name__ == '__main__':
    print(main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], *sys.argv[6:7]))
