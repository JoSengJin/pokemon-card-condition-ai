"""사람 확인용 정적 페이지(휴대폰): AI가 고른 앞/뒤 사진을 보고 맞는지 선택. 상태는 메모리에만 두고 결과 JSON을 복사해 붙여넣는다. 학습·추론 0."""
import base64, glob, io, json, os
from PIL import Image, ImageOps
O = 'artifacts/unused-pairing-20261113'; res = json.load(open(f'{O}/results.json')); meta = {m['code']: m for m in json.load(open(f'{O}/sample_meta.json'))}
R = {}
for b in range(1, 11):
    for r in json.load(open(f'{O}/responses/batch_{b}.json'))['responses']: R[r['code']] = r
def uri(path):
    with Image.open(path) as im: im = ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((360, 360)); b = io.BytesIO(); im.save(b, 'JPEG', quality=60)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
cards = []
for i, c in enumerate(__import__('random').Random(20261114).sample(sorted(set(res['candidates']) - set(res['human_check_sample_30'])), len(set(res['candidates']) - set(res['human_check_sample_30'])))):
    m = meta[c]; d = [x for x in sorted(glob.glob(f'artifacts/ebay-intake-*/{m["group"]}')) if 2 <= len(glob.glob(x + '/photo-*.jpg')) <= 12][-1]; r = R[c]  # build.py와 같은 규칙
    cards.append(dict(code=c, front=uri(f'{d}/{m["photos"][r["front_index"] - 1]}'), back=uri(f'{d}/{m["photos"][r["back_index"] - 1]}')))
html = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>앞뒤 쌍 확인</title>
<style>body{font:16px system-ui;margin:0;padding:12px;background:#fff;color:#111}.c{border:1px solid #bbb;border-radius:8px;margin:0 0 14px;padding:8px}.r{display:flex;gap:6px}.r div{flex:1;text-align:center;font-size:13px}.r img{width:100%;border:1px solid #ddd}select{font-size:16px;width:100%;padding:8px;margin-top:6px}textarea{width:100%;height:120px;font-size:13px}button{font-size:16px;padding:10px 14px}.s{position:sticky;top:0;background:#fff;padding:6px 0;border-bottom:1px solid #ccc;z-index:2}</style></head><body>
<div class="s"><b>앞뒤 쌍 확인 __PART__</b> · 완료 <span id="n">0</span>/__CNT__<br><small>왼쪽=AI가 고른 앞면, 오른쪽=뒷면. 같은 카드의 앞·뒤가 맞는지만 보세요. 상태는 판단하지 않습니다.</small></div>
<div id="list"></div><h3>결과</h3><button onclick="out()">결과 만들기</button> <button onclick="cp()">복사</button><textarea id="o" readonly></textarea>
<script>const D=__DATA__;const A={};const L=document.getElementById("list");
D.forEach((d,i)=>{const e=document.createElement("div");e.className="c";e.innerHTML="<b>"+(i+1)+"</b><div class=r><div>앞<img src='"+d.front+"'></div><div>뒤<img src='"+d.back+"'></div></div><select onchange=\\"A['"+d.code+"']=this.value;u()\\"><option value=''>선택</option><option value='ok'>맞음: 같은 카드의 앞·뒤</option><option value='swap'>앞뒤가 바뀜</option><option value='other_card'>서로 다른 카드</option><option value='not_card_side'>앞/뒤 사진이 아님</option><option value='unsure'>확신 못 함</option></select>";L.appendChild(e)});
function u(){document.getElementById("n").textContent=Object.keys(A).filter(k=>A[k]).length}
function out(){document.getElementById("o").value=JSON.stringify(A)}
function cp(){out();const t=document.getElementById("o");t.select();try{document.execCommand("copy")}catch(e){}}
</script></body></html>'''
for k in range((len(cards) + 9) // 10):
    f = f'{O}/human_check_rest_{k + 1}.html'; open(f, 'w').write(html.replace('__DATA__', json.dumps(cards[k * 10:(k + 1) * 10])).replace('__CNT__', str(len(cards[k * 10:(k + 1) * 10]))).replace('__PART__', f'{k + 1}/' + str((len(cards) + 9) // 10) + f'({len(cards[k * 10:(k + 1) * 10])}곳)'))
    print(f, os.path.getsize(f) // 1024, 'KB')
