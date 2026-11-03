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
COLOR = dict(high=(220, 40, 40), mid=(235, 170, 20), low=(40, 170, 70))


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


def card_html(request, res):
    im = Image.open(request['image']).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    for part in ('edge', 'corner', 'surface'):
        for z in res['results'][part].get('zones', []):
            x0, y0, x1, y1 = region_box(request['box'], z['area'])
            d.rectangle([x0*w, y0*h, x1*w, y1*h], outline=COLOR[z['band']], width=max(3, w//300))
    im.thumbnail((520, 700))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=70)
    rows = ''.join(f"<tr><td>{p}</td><td>{html.escape(str(r.get('status')))}</td><td>{html.escape(r.get('reason', ''))}{'; '.join(f'{z['area']} {z['score']:.2f}({z['band']})' for z in r.get('zones', [])[:3])}{'score %.2f' % r['score'] if 'score' in r else ''}</td><td>{html.escape(r['model_sha256'][:8])}</td></tr>" for p, r in res['results'].items())
    return (f'<article data-id="{html.escape(request["id"])}"><h2>{html.escape(request["id"])}</h2><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'
            f'<table><tr><th>항목</th><th>상태</th><th>근거(상위 3구역/점수/보류 이유)</th><th>모델 SHA</th></tr>{rows}</table>'
            '<p>센터링·앞면: 미지원(사람 검토). 점검 우선순위이며 결함 판정이 아닙니다. 빨강=높음 주황=중간 초록=낮음.</p>'
            '<label>정정/검토: <select name="r"><option>검토 안 함</option><option>모델 제안 타당</option><option>제안 부적절</option><option>사진 재촬영 필요</option></select></label> '
            '<input name="n" placeholder="메모(선택)"></article>')


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
        Path(out, f'review-{n//6+1:02d}.html').write_text(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>후면 점검 검토</title><style>body{{font:15px system-ui;max-width:640px;margin:8px auto;padding:8px;background:#fff;color:#111}}img{{width:100%}}td,th{{border:1px solid #999;padding:2px 5px;font-size:13px}}article{{border-top:2px solid #888;margin-top:16px}}textarea{{width:100%;height:120px}}</style><h1>후면 점검 우선순위 검토</h1>{body}<h3>결과(복사해서 채팅에 붙여넣기)</h3><textarea id="o" readonly></textarea><script>{script}</script>', encoding='utf-8')
    return cov


if __name__ == '__main__':
    print(main(*sys.argv[1:]))
