"""Human review of one listing-predict result: photos, evidence regions, release, verdicts and hold reasons.

The review record is a separate audit file. It is never a label, never training/evaluation truth and
never changes the model verdict.
"""
import hashlib
import html
import json
from pathlib import Path

from .performance_view import photo
from .review import atomic_write
from .regions import GLARE_AREAS, region_box

DECISIONS = ('confirmed', 'corrected_defect', 'corrected_normal', 'undecidable')
STATES = dict(normal='정상', defect='결함 의심', unknown='보류')


def checked_inputs(report_path, request_path):
    """Load the report and request; reject when photos changed since inference or ids differ."""
    raw = Path(report_path).read_bytes()
    report, request = json.loads(raw), json.loads(Path(request_path).read_text())
    if (not isinstance(report, dict) or not isinstance(request, dict) or report.get('id') != request.get('id')
            or len(report.get('listing_readiness', {}).get('records', [])) != 1):
        raise ValueError('Report and request must describe the same single listing')
    for side in ('front', 'back'):
        face = request.get(side)
        if face is None:
            continue
        expected = report['input_photo_sha256'].get(face['image'])
        if expected is None or hashlib.sha256(Path(face['image']).read_bytes()).hexdigest() != expected:
            raise ValueError(f'{side} photo differs from the analyzed photo; rerun analysis')
    return report, request, hashlib.sha256(raw).hexdigest()


def side_view(side, face, cells):
    """One face: photo with the human card box and a 3x3 evidence grid, or an explicit missing notice."""
    if face is None or face.get('box') is None:
        reason = '사진 없음' if face is None else '카드 영역 없음'
        return f'<section><h2>{side}</h2><p class="missing">{reason} — 이 면의 모든 칸은 보류</p></section>'
    left, top, right, bottom = face['box']
    marks = []
    for area in GLARE_AREAS:
        x0, y0, x1, y1 = region_box(face['box'], area)
        summary = ' / '.join(f"{c['label'].split('_')[0]}:{STATES[c['state']]}" for c in cells if c['area'] == area)
        held = all(c['state'] == 'unknown' for c in cells if c['area'] == area)
        marks.append(f'<div class="cell{" held" if held else ""}" style="left:{(x0-left)/(right-left)*100:.2f}%;'
                     f'top:{(y0-top)/(bottom-top)*100:.2f}%;width:{(x1-x0)/(right-left)*100:.2f}%;'
                     f'height:{(y1-y0)/(bottom-top)*100:.2f}%" title="{html.escape(summary, quote=True)}">'
                     f'<small>{area}</small></div>')
    box = f'left:{left*100:.2f}%;top:{top*100:.2f}%;width:{(right-left)*100:.2f}%;height:{(bottom-top)*100:.2f}%'
    return (f'<section><h2>{side}</h2><div class="photo"><img alt="{side} 원본" '
            f'src="data:image/jpeg;base64,{photo(face["image"])}"><div class="card" style="{box}">'
            + ''.join(marks) + '</div></div></section>')


def review_page(report_path, request_path, output):
    report, request, report_sha = checked_inputs(report_path, request_path)
    record = report['listing_readiness']['records'][0]
    release = report.get('release')
    identity = (f"릴리스 {html.escape(release['release_id'])} · 패키지 {html.escape(release['package_version'])}"
                if release else '고정 릴리스 아님(직접 checkpoint 실행) — 운영 검토 근거로 쓰지 않는다')
    rows = ''.join(
        f"<tr data-key='{c['side']}|{c['area']}|{c['label']}'><td>{c['side']}</td><td>{c['area']}</td>"
        f"<td>{c['label']}</td><td class='{c['state']}'>{STATES[c['state']]}</td>"
        f"<td>{'-' if c['score'] is None else format(c['score'], '.3f')}</td><td>{c['reason'] or '-'}</td>"
        "<td><select>" + ''.join(f'<option>{d}</option>' for d in ('', *DECISIONS)) + "</select></td></tr>"
        for c in record['cells'])
    payload = json.dumps(dict(report_sha256=report_sha, id=report['id'], release=release,
                              cells=[[c['side'], c['area'], c['label']] for c in record['cells']])).replace('</', '<\\/')
    page = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Listing Result Review</title><style>
:root{{--bg:#f4f6f9;--fg:#172537;--line:#c6cfdb;--held:#f1c75b;--defect:#d9534f;--normal:#3c8d5a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#11161d;--fg:#e4e9f0;--line:#3a4655}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
.faces{{display:flex;flex-wrap:wrap;gap:16px}}section{{flex:1 1 320px}}.photo{{position:relative}}img{{width:100%;display:block}}
.card{{position:absolute;outline:2px solid #2f7bf6}}.cell{{position:absolute;border:1px dashed #fff;box-sizing:border-box}}
.cell small{{background:#0008;color:#fff;font-size:10px;padding:0 2px}}.cell.held{{background:#f1c75b55}}
.missing{{padding:24px;border:2px dashed var(--held)}}.warn{{border-left:4px solid var(--held);padding:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid var(--line);padding:4px}}
.defect{{color:var(--defect)}}.normal{{color:var(--normal)}}.unknown{{color:#b7861a}}.wrap{{overflow-x:auto}}code{{word-break:break-all}}</style>
<h1>매물 결과 검토 · {html.escape(report['id'])}</h1>
<p>{identity}<br>model_sha256 <code>{report['model_sha256']}</code> · 결과 SHA <code>{report_sha[:16]}</code></p>
<p class="warn">전체 판정 불가 사유: {html.escape(', '.join(record['whole_listing_blockers']))}. 칸 판정은 보조 근거이며 등급·구매 결정이 아니다. 검토 기록은 정답 라벨로 자동 사용하지 않는다.</p>
<div class="faces">{side_view('front', request.get('front'), [c for c in record['cells'] if c['side'] == 'front'])}
{side_view('back', request.get('back'), [c for c in record['cells'] if c['side'] == 'back'])}</div>
<h2>칸별 판정·보류 이유와 검토</h2><div class="wrap"><table><tr><th>면</th><th>구역</th><th>종류</th><th>판정</th><th>점수</th><th>보류 이유</th><th>검토</th></tr>{rows}</table></div>
<p><button id="export">검토 기록 내보내기</button> <span id="status"></span></p>
<script type="application/json" id="data">{payload}</script><script>
const data=JSON.parse(document.getElementById('data').textContent);
document.getElementById('export').onclick=()=>{{
 const decisions=[...document.querySelectorAll('tr[data-key]')].map(r=>{{const [side,area,label]=r.dataset.key.split('|');return {{side,area,label,decision:r.querySelector('select').value}}}});
 const left=decisions.filter(d=>!d.decision).length;
 document.getElementById('status').textContent=left?`미검토 ${{left}}칸 — 완료로 기록되지 않음`:'모든 칸 검토';
 const blob=new Blob([JSON.stringify({{report_sha256:data.report_sha256,id:data.id,decisions}},null,2)],{{type:'application/json'}});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`review-${{data.id}}.json`;a.click();
}};</script></html>"""
    atomic_write(Path(output), page)
    return dict(output=str(output), report_sha256=report_sha, cells=len(record['cells']), release=release)


def review_record(report_path, decisions_path, output):
    """Validate exported decisions against the exact report and write a separate review record."""
    output = Path(output)
    if output.exists():
        raise ValueError('Review record exists; keep it and choose a new output')
    raw = Path(report_path).read_bytes()
    report, decisions = json.loads(raw), json.loads(Path(decisions_path).read_text())
    if decisions.get('report_sha256') != hashlib.sha256(raw).hexdigest() or decisions.get('id') != report['id']:
        raise ValueError('Decisions belong to a different result; review the exact result again')
    cells = report['listing_readiness']['records'][0]['cells']
    keys = [(c['side'], c['area'], c['label']) for c in cells]
    given = [(d.get('side'), d.get('area'), d.get('label')) for d in decisions.get('decisions', [])]
    if sorted(given) != sorted(keys) or any(d.get('decision') not in ('', *DECISIONS) for d in decisions['decisions']):
        raise ValueError('Decisions must cover every result cell once with a known decision')
    by_key = {(d['side'], d['area'], d['label']): d['decision'] or None for d in decisions['decisions']}
    counts = {name: sum(v == name for v in by_key.values()) for name in DECISIONS}
    record = dict(id=report['id'], report_sha256=decisions['report_sha256'], release=report.get('release'),
                  model_sha256=report['model_sha256'], cells=len(keys), unreviewed=sum(v is None for v in by_key.values()),
                  decisions=[dict(side=s, area=a, label=l, model_state=c['state'], model_reason=c['reason'],
                                  decision=by_key[(s, a, l)]) for (s, a, l), c in zip(keys, cells)],
                  counts=counts, review_completed=all(v is not None for v in by_key.values()),
                  ground_truth=False, used_for_training=False, changes_model_verdict=False)
    atomic_write(output, json.dumps(record, ensure_ascii=False, indent=2))
    return {k: record[k] for k in ('id', 'cells', 'unreviewed', 'counts', 'review_completed', 'ground_truth')}
