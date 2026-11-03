"""E2 scenario build: run BackTriageSuite end to end on human-confirmed back photos, report coverage of known cells, and write a review page (photo, zones, model versions, hold reasons, correction export). Inference only; no training, no metrics beyond coverage."""
import base64
import html
import io
import json
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw

from card_condition.back_triage_suite import BackTriageSuite
from card_condition.regions import REGION_TARGET_AREAS, region_box

HEADS = dict(edge='artifacts/triage-edge-back-candidate-20261101/head.pt', corner='artifacts/triage-back-candidates-20261103/corner-head.pt',
             surface='artifacts/triage-back-candidates-20261103/surface-head.pt', observation_limit='artifacts/triage-back-candidates-20261103/observation_limit-head.pt')
PCOLOR = dict(edge=(220, 40, 40), corner=(30, 90, 255), surface=(235, 170, 0))
PNAME = dict(edge='빨강', corner='파랑', surface='노랑')


def run_suite(requests, backbone, weights):
    torch.set_num_threads(2)
    body = torch.hub.load(backbone, 'dinov2_vits14', source='local', pretrained=False).eval().requires_grad_(False)
    body.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True), strict=True)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    suite = BackTriageSuite(HEADS, body.to(device), device)
    return [suite.analyze(r) for r in requests]


def coverage(results, known):
    """known: {card id: {part: set of zone areas with a human 정상/결함 answer}}. Coverage = known cells that received a score."""
    got = total = 0
    for res in results:
        for part, areas in known.get(res['id'], {}).items():
            scored = {z['area'] for z in res['results'][part].get('zones', [])} if part != 'observation_limit' else ({'face'} if res['results'][part].get('status') == 'scored' else set())
            total += len(areas)
            got += len(areas & scored)
    return dict(known_cells=total, scored_cells=got, coverage=got/total if total else None)


KO = dict(upper_left='왼쪽 위', upper_center='위 가운데', upper_right='오른쪽 위', middle_left='왼쪽 가운데', center='가운데', middle_right='오른쪽 가운데',
          lower_left='왼쪽 아래', lower_center='아래 가운데', lower_right='오른쪽 아래')
PART = dict(edge='가장자리', corner='모서리', surface='안쪽 면')
CHOICES = ['(선택 안 함)', '맞게 짚음: 색 칸에 실제로 문제가 보인다', '틀리게 짚음: 색 칸에 문제가 안 보인다', '놓침: 색 칸이 없는데 다른 곳에 문제가 보인다', '판단 불가: 사진이 흐리거나 가려서 못 보겠다']


def card_html(request, res):
    """Only the 'high priority' zones are drawn (red) and listed in plain Korean; one question per card."""
    im = Image.open(request['image']).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    lines = []
    for part in ('edge', 'corner', 'surface'):
        zones = [z for z in res['results'][part].get('zones', []) if z['band'] == 'high'][:2]
        for z in zones:
            x0, y0, x1, y1 = region_box(request['box'], z['area'])
            d.rectangle([x0*w, y0*h, x1*w, y1*h], outline=PCOLOR[part], width=max(4, w//250))
        lines.append(f"<li><b>{PNAME[part]}</b> · {PART[part]}: " + (', '.join(KO[z['area']] for z in zones) if zones else '의심 높은 칸 없음') + '</li>' if res['results'][part].get('status') == 'ranked' else f"<li>{PART[part]}: 점수 못 냄({html.escape(res['results'][part].get('reason', ''))})</li>")
    obs = res['results']['observation_limit']
    lines.append('<li>사진 상태: ' + (f"재촬영 권고 점수 {obs['score']:.2f}(0~1, 높을수록 사진이 보기 어렵다)" if obs.get('status') == 'scored' else '점수 못 냄') + '</li>')
    im.thumbnail((520, 700))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=70)
    opts = ''.join(f'<option>{c}</option>' for c in CHOICES)
    return (f'<article data-id="{html.escape(request["id"])}"><h2>{html.escape(request["id"][-8:])}</h2><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'
            f'<p><b>모델이 먼저 보라고 한 곳</b> (사진의 색 칸: 빨강=가장자리, 파랑=모서리, 노랑=안쪽 면)</p><ul>{"".join(lines)}</ul>'
            f'<p style="font-size:12px;color:#555">모델 버전: '+' · '.join(f'{k} {v["model_sha256"][:8]}' for k,v in res['results'].items())+'</p>'
            f'<p>질문: 색 칸을 직접 확대해서 보세요.</p><select name="r">{opts}</select> <input name="n" placeholder="메모(선택)"></article>')


def main(out, requests_path, known_path, backbone, weights):
    requests = json.loads(Path(requests_path).read_text())
    results = run_suite(requests, backbone, weights)
    known = {k: {p: set(a) for p, a in v.items()} for k, v in json.loads(Path(known_path).read_text()).items()}
    cov = coverage(results, known)
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, 'results.json').write_text(json.dumps(dict(coverage=cov, results=results), ensure_ascii=False))
    for n in range(0, len(requests), 6):
        body = ''.join(card_html(r, x) for r, x in zip(requests[n:n+6], results[n:n+6]))
        script = "function b(){return [...document.querySelectorAll('article')].map(a=>a.dataset.id+'='+a.querySelector('[name=r]').value+';'+a.querySelector('[name=n]').value).join('\\n')}document.querySelectorAll('select,input').forEach(e=>e.addEventListener('input',()=>document.getElementById('o').value=b()));document.getElementById('o').value=b();"
        Path(out, f'review-{n//6+1:02d}.html').write_text(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>후면 점검 검토</title><style>body{{font:15px system-ui;max-width:640px;margin:8px auto;padding:8px;background:#fff;color:#111}}img{{width:100%}}td,th{{border:1px solid #999;padding:2px 5px;font-size:13px}}article{{border-top:2px solid #888;margin-top:16px}}textarea{{width:100%;height:120px}}</style><h1>후면 사진 검토 연습</h1><div style="background:#f3f3f3;padding:8px;border-radius:6px"><p><b>이게 뭔가요?</b> AI가 카드 뒷면 사진에서 <b>먼저 확인해 보라고 짚은 칸</b>을 색 사각형(빨강=가장자리, 파랑=모서리, 노랑=안쪽 면)으로 보여줍니다. 결함이 있다고 확정하는 게 아니라 “여기부터 보세요”라는 추천입니다.</p><p><b>하실 일</b>: 카드마다 색 칸을 확대해 보고, 아래 선택 칸에서 AI가 맞았는지 하나만 고르면 됩니다. 정답이 정해져 있지 않고 보이는 대로 고르시면 됩니다. 모르겠으면 ‘판단 불가’를 고르세요.</p><p>센터링(좌우 치우침)과 앞면은 AI가 지원하지 않아 여기서 보지 않습니다.</p></div>{body}<h3>결과(복사해서 채팅에 붙여넣기)</h3><textarea id="o" readonly></textarea><script>{script}</script>', encoding='utf-8')
    return cov


if __name__ == '__main__':
    print(main(*sys.argv[1:]))
