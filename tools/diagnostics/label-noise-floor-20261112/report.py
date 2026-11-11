"""label-noise-floor-20261112 성과 HTML(정적, 외부 자원 없음). 진단 수치이며 모델 개선 아님. 출력은 Git 제외 artifacts."""
import html
import json
import subprocess
from pathlib import Path
OUT = Path('artifacts/label-noise-floor-20261112'); R = json.load(open(OUT / 'results.json'))
E = html.escape


def row(r):
    return f"<tr><td>{E(r['source'])}</td><td>{E(r['unknown'])}</td><td>{r['FP_floor']} {r['FP_ci95']}</td><td>{r['FN_floor']} {r['FN_ci95']}</td><td>{E(r['verdict']['FP'])}<br>{E(r['verdict']['FN'])}</td></tr>"


def zones():
    smp = json.load(open('artifacts/severity-repro-20261112/sample.json'))['zones']; lv = {}
    for f in sorted(Path('artifacts/severity-repro-20261112/responses').glob('sev*.json')):
        for r in json.load(open(f))['responses']: lv[r['id']] = r['level']
    out = []
    for z in sorted(smp, key=lambda z: (z['cell'], z['id'])):
        t = z['target']; d = lv[z['id']] in ('1', '2'); flip = (d if t == 0 else not d)
        out.append(f"<tr class={'flip' if flip else ''}><td>{z['cell']}</td><td>{E(z['id'].split('/')[0][-6:])}/{E(z['id'].split('/')[-1])}</td><td>{t}</td><td>{z['score']:.3f}</td><td>{lv[z['id']]}</td><td>{'뒤집힘' if flip else '-'}</td></tr>")
    return ''.join(out)


def main():
    sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip(); p = R['primary']
    cells = ''.join(f"<tr><td>{c}</td><td>{v['N']}</td><td>{v['flip']}/{v['n']}</td><td>{v['rate']}</td></tr>" for c, v in p['cell_flip'].items())
    doc = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>라벨 잡음 하한</title>
<style>:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd;--warn:#fff4e5;--flip:#fde8e8}}@media(prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--mut:#aaa;--line:#333;--warn:#3a2e14;--flip:#4a1f1f}}}}
body{{background:var(--bg);color:var(--fg);font-family:-apple-system,sans-serif;max-width:960px;margin:auto;padding:0 16px 40px;line-height:1.5}}table{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}}td,th{{border:1px solid var(--line);padding:4px 6px;text-align:left}}
.box{{background:var(--warn);padding:10px 12px;border-radius:6px}}.flip{{background:var(--flip)}}.mut{{color:var(--mut)}}.big{{font-size:28px;font-weight:700}}</style><body>
<h1>라벨 잡음 하한 (Q1) — 진단</h1>
<p class=box><b>진단 수치이며 모델 개선이 아니다.</b> 새 학습·추론 0, 저장 점수(직접 알파0 20261108T215307-941b3aaa)와 기존 사람 응답만 사용. <b>같은 사람 재판정 기반, 독립 검증 아님.</b></p>
<table><tr><th>작업</th><td>label-noise-floor-20261112</td></tr><tr><th>검증 코드 SHA</th><td>{sha} (prereg 고정 커밋 b91f0f5)</td></tr>
<tr><th>개발 진척률</th><td>78/100 불변 (usable-card-analysis-v1.13, development-progress.json)</td></tr>
<tr><th>이번 성과</th><td>FP 잡음 하한 <span class=big>{p['FP_floor']}</span> 95% {p['FP_ci95']} &gt; 게이트 112 → 사전 등록 판정: 현 라벨로 FP 게이트 달성 불가, 표현 가설 재개 금지. FN 하한 {p['FN_floor']} {p['FN_ci95']} &lt; 67.</td></tr></table>
<h2>주 결과: 심각도 60곳(표면만), 결함 = 단계 ≥1, 카드 위 1323곳 칸 가중</h2><table><tr><th>칸 target/예측</th><th>칸 크기</th><th>뒤집힘</th><th>비율</th></tr>{cells}</table>
<p class=mut>기준 모델 관측: FP 167/1406, FN 57/370. 카드 밖 453곳은 기여 0(하한). 칸별 사진 그룹 부트스트랩 10000회.</p>
<h2>주 결과 + 민감도</h2><table><tr><th>자료·정의</th><th>판단불가</th><th>FP 하한 [95%]</th><th>FN 하한 [95%]</th><th>판정</th></tr>{row(p)}{''.join(row(r) for r in R['sensitivity'])}</table>
<p class=box>결함을 "뚜렷(단계 2)"으로 좁히면 FP·FN 모두 판단 불가가 된다. 그런데 단계 1↔2 경계는 같은 사람 반복에서도 재현되지 않았다(가중 kappa 0.234). 실제 모델 FP 167이 하한 675보다 낮은 것은 모델이 진짜 상태가 아니라 원 라벨의 문턱을 학습했다는 뜻이다.</p>
<h2>구역별 사람 재판정·저장 점수 (60곳, 사진 없음: 새 추론 없음)</h2><table><tr><th>칸</th><th>구역</th><th>원 target</th><th>저장 점수</th><th>심각도</th><th>원 라벨 대비</th></tr>{zones()}</table>
<h2>원시 기록 감사</h2><p>응답 117파일: 응답 시각·확대 여부·번복 이력 필드 0. 독립 판정 화면에서 새로 기록할 필드: shown_at, answered_at, zoom_used, changes, gallery_viewed, rater_id.</p>
<h2>변경·검사·롤백</h2><ul><li>추가: tools/diagnostics/label-noise-floor-20261112/(prereg.json, floor.py, alpha_size.py, report.py), docs/collaboration/reports/label-noise-floor-20261112.md, independent-judgment-prereg-draft-20261112.md</li>
<li>실행: floor.py(입력 36파일 해시 대조 통과), alpha_size.py(합성 시뮬레이션)</li><li>미실행: 외부 판정(승인 대상), 독립 검증, 학습·추론</li><li>롤백: git revert, artifacts/label-noise-floor-20261112 삭제. 라벨·모델·게이트 변경 없음.</li></ul>
<p class=mut>근거: artifacts/label-noise-floor-20261112/results.json, docs/collaboration/reports/label-noise-floor-20261112.md</p></body></html>'''
    (OUT / 'report.html').write_text(doc); print(OUT / 'report.html')


if __name__ == '__main__':
    main()
