"""Static phone pages: drag four card corners (TL,TR,BR,BL) over a photo; writes no labels."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

SCRIPT = """
const faces=[...document.querySelectorAll('article')];
faces.forEach(a=>{a.pts=JSON.parse(a.dataset.pts)});
function out(){document.getElementById('out').value=faces.map(a=>a.dataset.id+'='+a.pts.map(p=>p[0].toFixed(4)+':'+p[1].toFixed(4)).join(';')).join('\\n')}
faces.forEach(a=>{
  const c=a.querySelector('canvas'),x=c.getContext('2d'),img=a.querySelector('img');
  let drag=-1;
  function draw(){x.clearRect(0,0,c.width,c.height);x.drawImage(img,0,0,c.width,c.height);
    x.lineWidth=3;x.strokeStyle='#1e5aff';x.beginPath();a.pts.forEach((p,i)=>x[i?'lineTo':'moveTo'](p[0]*c.width,p[1]*c.height));x.closePath();x.stroke();
    a.pts.forEach((p,i)=>{x.fillStyle='rgba(255,60,60,.85)';x.beginPath();x.arc(p[0]*c.width,p[1]*c.height,16,0,7);x.fill();x.fillStyle='#fff';x.font='16px sans-serif';x.fillText(['1','2','3','4'][i],p[0]*c.width-5,p[1]*c.height+5)})}
  function pos(e){const r=c.getBoundingClientRect(),t=e.touches?e.touches[0]:e;return[(t.clientX-r.left)/r.width,(t.clientY-r.top)/r.height]}
  function down(e){const q=pos(e);let best=-1,bd=0.08;a.pts.forEach((p,i)=>{const d=Math.hypot(p[0]-q[0],p[1]-q[1]);if(d<bd){bd=d;best=i}});drag=best;if(best>=0)e.preventDefault()}
  function move(e){if(drag<0)return;e.preventDefault();const q=pos(e);a.pts[drag]=[Math.min(1,Math.max(0,q[0])),Math.min(1,Math.max(0,q[1]))];draw();out()}
  function up(){drag=-1}
  c.addEventListener('mousedown',down);c.addEventListener('mousemove',move);window.addEventListener('mouseup',up);
  c.addEventListener('touchstart',down,{passive:false});c.addEventListener('touchmove',move,{passive:false});c.addEventListener('touchend',up);
  img.onload=()=>{c.width=img.naturalWidth;c.height=img.naturalHeight;draw();out()};if(img.complete)img.onload();
});
document.getElementById('copy').onclick=()=>{const t=document.getElementById('out');t.focus();t.select();
try{document.execCommand('copy');document.getElementById('msg').textContent='복사됨. 채팅에 붙여넣으세요.'}
catch(e){document.getElementById('msg').textContent='아래 칸을 길게 눌러 직접 복사하세요.'}};
"""


def image_data(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    image.thumbnail((900, 900))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=75)
    return base64.b64encode(buffer.getvalue()).decode()


def article(number, face):
    left, top, right, bottom = face['box']
    pts = [[left, top], [right, top], [right, bottom], [left, bottom]]
    return (f'<article data-id="{html.escape(face["id"])}" data-pts="{html.escape(json.dumps(pts))}">'
            f'<h2>{number}. {html.escape(face["title"][:60])}</h2>'
            f'<img alt="" hidden src="data:image/jpeg;base64,{image_data(face["image"])}">'
            '<canvas style="width:100%;touch-action:none"></canvas></article>')


def main(faces_path, ids_path, out_path):
    faces = {f['id']: f for f in json.loads(Path(faces_path).read_text())}
    ids = [i.strip() for i in Path(ids_path).read_text().split() if i.strip()]
    body = ''.join(article(n, faces[i]) for n, i in enumerate(ids, 1))
    Path(out_path).write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>카드 모서리 보정</title><style>body{font:17px/1.6 system-ui;margin:0 auto;max-width:760px;padding:16px}'
        'button{font-size:18px;min-height:44px;width:100%;margin:6px 0}textarea{width:100%;height:220px;font-size:15px}'
        'article{border-top:1px solid #aaa;margin-top:22px}</style><h1>카드 모서리 보정</h1>'
        '<p>빨간 점 1~4(왼위→오른위→오른아래→왼아래)를 카드의 실제 네 모서리로 끌어 맞추세요. 이미 맞으면 그대로 두세요. '
        '카드가 사진 밖으로 잘려 모서리가 없으면 점을 사진 가장자리에 두지 말고 결과에 “불가”라고 적어 알려 주세요. '
        '자동 저장하지 않습니다.</p>' + body +
        '<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea>'
        f'<script>{SCRIPT}</script></html>')


if __name__ == '__main__':
    main(*sys.argv[1:4])
