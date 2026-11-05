"""Report for v3/v4 dev runs: human marks (green), v2 (red), v3 (magenta, from detected outer edge), held rows (v4) flagged. Overlays embedded."""
import base64, io, json
from PIL import Image, ImageOps, ImageDraw
E3 = json.load(open('../experiments/20261103T071212-88d88c9e/evaluation.json')); E4 = json.load(open('../experiments/20261103T071302-40b98e09/evaluation.json')); E5 = json.load(open('../experiments/20261103T075859-0de16393/evaluation.json'))
rows = json.load(open('../centering-tb-measurer-v2-20261103/rows.json')); v2 = json.load(open('../experiments/20261102T223937-5d5c93aa/evaluation.json'))
def tile(i, r):
    im = ImageOps.exif_transpose(Image.open(r['image'])).convert('RGB'); w, h = im.size
    X0, Y0, X1, Y1 = round(r['box'][0]*w), round(r['box'][1]*h), round(r['box'][2]*w), round(r['box'][3]*h); bh = Y1-Y0
    d = ImageDraw.Draw(im); d.rectangle([X0, Y0, X1, Y1], outline=(255, 255, 0), width=3)
    m3, m2 = E3['measured'][i], v2['measured'][i]
    for y, c in ((Y0+r['human_top']*bh, (0, 255, 0)), (Y1-r['human_bottom']*bh, (0, 255, 0)), (Y0+m2['top']*bh, (255, 0, 0)), (Y1-m2['bottom']*bh, (255, 0, 0)),
                 (Y0+(m3['anchor_top']+m3['top'])*bh, (255, 0, 255)), (Y1-(m3['anchor_bottom']+m3['bottom'])*bh, (255, 0, 255))):
        d.line([X0, y, X1, y], fill=c, width=3)
    im = im.crop((X0-20, Y0-20, X1+20, Y1+20)); im.thumbnail((260, 380)); b = io.BytesIO(); im.save(b, 'JPEG', quality=55)
    return base64.b64encode(b.getvalue()).decode()
held = E4['measured']
fig = ''.join(f'<figure><img src="data:image/jpeg;base64,{tile(i, r)}"><figcaption>#{i} {"결함" if r["target"] else "정상"}{" · v4 보류" if held[i]["held"] else ""}<br>사람 {r["human_top"]:.3f}/{r["human_bottom"]:.3f} v2 {v2["measured"][i]["top"]:.3f}/{v2["measured"][i]["bottom"]:.3f} v3 {E3["measured"][i]["top"]:.3f}/{E3["measured"][i]["bottom"]:.3f}</figcaption></figure>' for i, r in enumerate(rows))
def row(n, e, extra): return f'<tr><td>{n}</td><td>{e["spearman_with_human_marks"]:.3f}</td><td>{e["auc_vs_label"]:.3f}</td><td>{extra}</td></tr>'
open('report_v3v4.html', 'w').write(f'''<!doctype html><meta charset=utf-8><title>C4 v3·v4·v5 개발 결과</title><style>body{{font:14px sans-serif;margin:16px}}figure{{display:inline-block;margin:4px;width:260px;vertical-align:top}}img{{width:100%}}figcaption{{font-size:11px}}td,th{{border:1px solid #888;padding:3px 8px}}</style>
<h1>C4 앞면 센터링 v3·v4 (개발 36장, 독립 아님)</h1>
<p>전체 실사용 진척 68/100(PROGRESS_CRITERIA v1.10) 불변, C4 pending. 외부 AI·학습 호출 없음. 개발 자료만 사용, 독립 일반화 미확인. 사람 표시 AUC 0.797(상한 참고).</p>
<table><tr><th>측정기</th><th>사람 표시 순위상관</th><th>센터링 AUC</th><th>비고(분모)</th></tr>
<tr><td>v2 20261102T223937-5d5c93aa</td><td>0.078</td><td>0.559</td><td>36장, 창 한계 붙음 22/72</td></tr>
{row('v3 20261103T071212-88d88c9e', E3, '36장, 창 한계 붙음 9/72, 보류 0%. 유효19장: 상관 0.170, AUC 0.667(기준 외)')}
{row('v4 20261103T071302-40b98e09', E4, '남은 28장(결함 14), 보류 8장 22.2%(>20% 기준 초과), 붙음 8/56')}<tr><td>v5 학습 순위기(36그룹 제외 교차검증) 20261103T075859-0de16393</td><td>{E5["spearman_with_human_marks"]:.3f}</td><td>{E5["auc_vs_label"]:.3f}</td><td>36장, 보류 0%. 경계 오차 sd 0.0077/경계, 사람 상하 차이 sd 0.0118 → 신호 대 잡음비 약 1</td></tr></table>
<p>사전 기준: 상관≥0.50, AUC≥0.70, 보류≤20%, 붙음 &lt; 22/72. v3·v4·v5 모두 criterion_met=false. 러너 acceptance_passed=true는 FP/FN 상한 999의 형식 값이며 성공을 뜻하지 않는다.</p>
<p>노랑=상자, 초록=사람 표시, 빨강=v2, 자홍=v3.</p>{fig}''')
