"""D2 report: per-zone human truth vs frozen-candidate score drawn on the sealed D1 photos (static HTML, no network). Reads experiment observations only."""
import base64
import html
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RUNS = dict(corner=('20261103T131123-7fa5d398', 'C2 후면 모서리 · 후보 E', 0.2808, 0.5093),
            surface=('20261103T131419-6451691e', 'C3 후면 표면 · 후보 B', 0.2129, 0.4682))


def card_image(rows, scores, low, high):
    """Draw each zone box: border colour = human truth (red defect / green normal), label = score and band."""
    im = Image.open(rows[0]['image']).convert('RGB')
    w, h = im.size
    d = ImageDraw.Draw(im)
    for r, s in zip(rows, scores):
        x0, y0, x1, y1 = r['box']
        d.rectangle([x0*w, y0*h, x1*w, y1*h], outline=(220, 40, 40) if r['target'] else (40, 170, 70), width=max(4, w//250))
        d.text((x0*w+8, y0*h+8), f"{s:.2f}{'H' if s >= high else 'L' if s < low else 'M'}", fill=(255, 255, 0))
    im.thumbnail((420, 560))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def section(key, limit=16):
    run, title, low, high = RUNS[key]
    obs = json.loads(Path(f'artifacts/experiments/{run}/observations.json').read_text())
    ev = json.loads(Path(f'artifacts/experiments/{run}/evaluation.json').read_text())
    by = {}
    for r, s in zip(obs['rows'], obs['scores']):
        by.setdefault(r['group'], []).append((r, s))
    shown = sorted(by.values(), key=lambda g: -sum(r['target'] for r, _ in g))[:limit]
    figs = ''.join(f'<figure><img src="data:image/jpeg;base64,{card_image([r for r, _ in g], [s for _, s in g], low, high)}"><figcaption>{html.escape(g[0][0]["group"][-8:])}</figcaption></figure>' for g in shown)
    m = ev['metrics']
    row = f"<tr><td>{title}</td><td>{'충족' if ev['criterion_met'] else '<b>미충족</b>'}</td><td>{m['gap']:.3f} [{ev['bootstrap']['gap']['lo']:.3f}, {ev['bootstrap']['gap']['hi']:.3f}]</td><td>{m['hit_gap']:.3f} [{ev['bootstrap']['hit_gap']['lo']:.3f}]</td><td>{ev['holdout_groups']} 그룹 · 구역 {ev['holdout_positive']+ev['holdout_normal']} (결함 {ev['holdout_positive']})</td></tr>"
    return row, f'<h2>{title}</h2><p>빨강=사람 결함, 초록=사람 정상, 숫자=모델 점수(H 높음 ≥{high}, L 낮음 &lt;{low}). 결함 구역이 많은 카드 {len(shown)}장.</p><div class="g">{figs}</div>'


def main(out):
    rows, secs = zip(*(section(k) for k in RUNS))
    page = ('<!doctype html><meta charset="utf-8"><title>D2 독립 시험 결과</title><style>body{font:14px sans-serif;margin:16px;background:#fff;color:#111}'
            'td,th{border:1px solid #999;padding:4px 8px}.g{display:flex;flex-wrap:wrap;gap:8px}figure{margin:0}img{width:200px}</style>'
            '<h1>D2: 동결 후보 → D1 봉인 시험셋 (1회 평가)</h1><p>진척 68/100(v1.11) 불변. 독립 시험(D1 봉인 138실물) 결과이며 모델 선택 자료가 아니다. 점검 우선순위 용도, 결함 판정 아님.</p>'
            '<table><tr><th>항목</th><th>판정</th><th>구간 격차 [95%]</th><th>1위 적중 격차 [하한]</th><th>분모</th></tr>' + ''.join(rows) + '</table>' + ''.join(secs))
    Path(out).write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
