"""On-photo face-level HTML for the C5 holdout: score, human label and error flag per back photo, sorted by score."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mobile_visibility_label_pages import encode  # noqa: E402


def main(observations, evaluation, out_path):
    obs = json.loads(Path(observations).read_text())
    ev = json.loads(Path(evaluation).read_text())
    items = sorted(zip(obs['rows'], obs['scores']), key=lambda t: -t[1])
    cards = []
    for r, s in items:
        mark = '제한(사람)' if r['target'] else '정상(사람)'
        cls = 'hit' if r['target'] else 'ok'
        cards.append(f'<div class="c {cls}"><img src="data:image/jpeg;base64,{encode(r["image"], 360)}"><b>{s:.3f}</b> {mark}<br><small>{html.escape(r["group"][-8:])}</small></div>')
    head = (f'<h2>C5 v1.8 후면 관찰제한 보류 평가 — 미충족</h2><p>AUC {ev["auc"]:.3f} [{ev["bootstrap"]["lo"]:.3f}, {ev["bootstrap"]["hi"]:.3f}] (기준 ≥0.75, 하한 ≥0.60). '
            f'후면 {ev["holdout_rows"]}장 중 제한 {ev["holdout_positive"]}장, 미확인 5장 분모 밖. 점수 높은 순; 빨강=사람이 제한이라 한 사진.</p>')
    css = 'body{font:15px system-ui;margin:8px}.c{display:inline-block;width:170px;margin:4px;vertical-align:top}.c img{width:100%}.hit{outline:3px solid #d33}.ok{outline:1px solid #ccc}'
    Path(out_path).write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{css}</style>{head}{"".join(cards)}', encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:4])
