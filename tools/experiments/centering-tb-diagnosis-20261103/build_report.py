"""Diagnosis report builder: overlays embedded as data URIs (static render safe)."""
import base64, io, json
from PIL import Image
def small(p):
    im = Image.open(p); im.thumbnail((260, 400)); b = io.BytesIO(); im.save(b, 'JPEG', quality=55); return base64.b64encode(b.getvalue()).decode()
d = json.load(open('diag.json')); rows, v = d['rows'], d['slack_validity']; s = json.load(open('slack.json'))
fig = ''.join(f'<figure><img src="data:image/jpeg;base64,{small(f"img/{i:02d}.jpg")}"><figcaption>#{i} {"결함" if x["target"] else "정상"} 사람 {x["human"][0]:.3f}/{x["human"][1]:.3f} · v2 {x["v2"][0]:.3f}/{x["v2"][1]:.3f} · 여유분 {s[i]["slack_top"]:+.3f}/{s[i]["slack_bot"]:+.3f}</figcaption></figure>' for i, x in enumerate(rows))
a, b, c = v['all36'], v['valid'], v['valid_heuristic']
open('report.html', 'w').write(f'''<!doctype html><meta charset=utf-8><title>C4 센터링 진단</title><style>body{{font:14px sans-serif;margin:16px}}figure{{display:inline-block;margin:4px;width:300px;vertical-align:top}}img{{width:100%}}figcaption{{font-size:11px}}td,th{{border:1px solid #888;padding:3px 8px}}</style>
<h1>C4 앞면 센터링 진단 (개발 36장, 진단 전용)</h1>
<p>전체 실사용 진척 68/100(PROGRESS_CRITERIA v1.10, 불변), C4 pending. 모델 학습·추론·외부 AI 호출 없음. 개발 자료만 사용, 독립 일반화 미확인. 진단 전용(./experiment 기록 아님).</p>
<table><tr><th>분모</th><th>n</th><th>평균 오차(원래)</th><th>여유분 보정 후</th><th>오차~여유분 순위상관</th></tr>
<tr><td>전체</td><td>{a['n']}</td><td>{a['mean_err_raw']:.3f}</td><td>{a['mean_err_slack_corrected']:.3f}</td><td>{a['spearman_err_vs_total_slack']:.3f}</td></tr>
<tr><td>유효(탐색창 온전, 엄격)</td><td>{b['n']}</td><td>{b['mean_err_raw']:.3f}</td><td>{b['mean_err_slack_corrected']:.3f}</td><td>{b['spearman_err_vs_total_slack']:.3f}</td></tr>
<tr><td>유효(이전 휴리스틱)</td><td>{c['n']}</td><td>{c['mean_err_raw']:.3f}</td><td>{c['mean_err_slack_corrected']:.3f}</td><td>{c['spearman_err_vs_total_slack']:.3f}</td></tr></table>
<p><b>결론:</b> {v['conclusion']}. 노랑=확인 상자, 초록=사람 표시, 빨강=v2 경계, 파랑 눈금=상자 가장자리 근처 그래디언트 봉우리.</p>{fig}''')
