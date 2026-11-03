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
CHOICES = ['(선택 안 함)', '문제가 보인다', '문제가 안 보인다', '모르겠다']


def crop_img(im, box):
    w, h = im.size
    x0, y0, x1, y1 = box
    c = im.crop((int(x0*w), int(y0*h), int(x1*w), int(y1*h)))
    c.thumbnail((560, 560))
    buf = io.BytesIO()
    c.save(buf, 'JPEG', quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def card_html(request, res):
    """One enlarged crop per part (its highest-scored zone); one question per crop."""
    im = Image.open(request['image']).convert('RGB')
    full = im.copy()
    d = ImageDraw.Draw(full)
    items = []
    for part in ('edge', 'corner', 'surface'):
        zones = res['results'][part].get('zones') or []
        if not zones or res['results'][part].get('status') != 'ranked':
            items.append(f"<p>{PART[part]}: 점수를 못 냈습니다({html.escape(res['results'][part].get('reason', ''))}). 사람이 직접 확인하세요.</p>")
            continue
        z = zones[0]
        box = region_box(request['box'], z['area'])
        d.rectangle([box[0]*im.size[0], box[1]*im.size[1], box[2]*im.size[0], box[3]*im.size[1]], outline=PCOLOR[part], width=max(5, im.size[0]//200))
        opts = ''.join(f'<option>{c}</option>' for c in CHOICES)
        items.append(f'<div class="z"><img src="data:image/jpeg;base64,{crop_img(im, box)}"><p><b>{PNAME[part]} · {PART[part]} · {KO[z["area"]]}</b> (AI 점검 우선순위: {z["label"]})</p>'
                     f'<select name="{part}">{opts}</select></div>')
    full.thumbnail((360, 480))
    buf = io.BytesIO()
    full.save(buf, 'JPEG', quality=70)
    sha = ' · '.join(f'{k} {v["model_sha256"][:8]}' for k, v in res['results'].items())
    return (f'<article data-id="{html.escape(request["id"])}"><h2>카드 {html.escape(request["id"][-8:])}</h2><img class="f" src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'
            f'<p>위 사진에서 색 상자가 아래 확대 사진의 위치입니다.</p>{"".join(items)}<p style="font-size:12px;color:#555">모델 버전: {sha}</p><input name="n" placeholder="메모(선택)"></article>')


def main(out, requests_path, known_path, backbone, weights):
    requests = json.loads(Path(requests_path).read_text())
    results = run_suite(requests, backbone, weights)
    known = {k: {p: set(a) for p, a in v.items()} for k, v in json.loads(Path(known_path).read_text()).items()}
    cov = coverage(results, known)
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, 'results.json').write_text(json.dumps(dict(coverage=cov, results=results), ensure_ascii=False))
    for n in range(0, len(requests), 4):
        body = ''.join(card_html(r, x) for r, x in zip(requests[n:n+4], results[n:n+4]))
        script = "function b(){return [...document.querySelectorAll('article')].map(a=>a.dataset.id+'='+[...a.querySelectorAll('select')].map(s=>s.name+':'+s.value).join(',')+';'+a.querySelector('[name=n]').value).join('\\n')}document.querySelectorAll('select,input').forEach(e=>e.addEventListener('input',()=>document.getElementById('o').value=b()));document.getElementById('o').value=b();"
        Path(out, f'review-{n//4+1:02d}.html').write_text(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>후면 점검 검토</title><style>body{{font:15px system-ui;max-width:640px;margin:8px auto;padding:8px;background:#fff;color:#111}}img{{width:100%}}td,th{{border:1px solid #999;padding:2px 5px;font-size:13px}}article{{border-top:2px solid #888;margin-top:16px}}textarea{{width:100%;height:120px}}</style><h1>후면 사진 검토 연습</h1><div style="background:#f3f3f3;padding:8px;border-radius:6px"><p><b>이게 뭔가요?</b> AI가 카드 뒷면 사진에서 <b>먼저 확인해 보라고 짚은 칸(종류마다 점수 높은 순 최대 2칸)</b>을 색 사각형(빨강=가장자리, 파랑=모서리, 노랑=안쪽 면)으로 보여줍니다. 결함이 있다고 확정하는 게 아니라 “여기부터 보세요”라는 추천입니다.</p><p><b>하실 일</b>: 아래 <b>확대된 작은 사진</b>(AI가 짚은 한 곳)을 보고, 그 사진 안에서 긁힘·마모·구김·얼룩 같은 문제가 <b>보이는지</b> 고릅니다. AI가 맞았는지 따지지 않고 사진에 보이는 대로만 고르시면 됩니다. 모르겠으면 ‘모르겠다’.</p><p>센터링(좌우 치우침)과 앞면은 AI가 지원하지 않아 여기서 보지 않습니다.</p></div>{body}<h3>결과(복사해서 채팅에 붙여넣기)</h3><textarea id="o" readonly></textarea><script>{script}</script>', encoding='utf-8')
    return cov


if __name__ == '__main__':
    print(main(*sys.argv[1:]))
