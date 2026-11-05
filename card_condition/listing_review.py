"""Human review of one listing-predict result: photos, evidence regions, release, verdicts and hold reasons.

Optional observation and recall evidence is shown next to the region verdicts as uncalibrated signals.
The review record is a separate audit file. It is never a label, never training/evaluation truth and
never changes the model verdict.
"""
import hashlib
import html
import json
import math
from pathlib import Path

from .performance_view import photo
from .review import atomic_write
from .regions import GLARE_AREAS, region_box

DECISIONS = ('confirmed', 'corrected_defect', 'corrected_normal', 'undecidable')
STATES = dict(normal='정상', defect='결함 의심', unknown='보류')
esc = html.escape
FACE_OPTIONS = {
    'centering_defect': dict(confirmed='보류 사유 확인', corrected_defect='센터링 이상 확인',
                             corrected_normal='센터링 이상 없음 확인', undecidable='판단 불가'),
    'observation_limited': dict(confirmed_limited='관찰 제한 확인', confirmed_observable='관찰 가능한 사진',
                                undecidable='판단 불가'),
}
FACE_NAMES = dict(centering_defect='센터링', observation_limited='관찰 제한')


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


def recall_cells(report, keys):
    """Recall candidates by result cell; every candidate must be one distinct, finite cell of this result."""
    block = report.get('recall_review')
    if block is None:
        return {}
    candidates = block.get('candidates') if isinstance(block, dict) else None
    if not isinstance(candidates, list):
        raise ValueError('Invalid recall review block')
    found = {}
    for item in candidates:
        key = tuple(item.get(f) for f in ('side', 'area', 'label')) if isinstance(item, dict) else None
        if key is None or not all(type(v) is str for v in key) or key not in keys or key in found:
            raise ValueError('Recall candidate matches no result cell')
        scores = [item.get('primary_score')] + ([] if item.get('secondary_score') is None else [item['secondary_score']])
        if not all(type(v) in (int, float) and math.isfinite(v) for v in scores):
            raise ValueError('Recall candidate has an invalid score')
        found[key] = item
    return found


def evidence_view(report, keys):
    """Validate optional observation/recall blocks; return per-cell recall notes and their HTML section."""
    found, notes, parts = recall_cells(report, set(keys)), {}, []
    for key, item in found.items():
        second = '-' if item.get('secondary_score') is None else format(item['secondary_score'], '.3f')
        notes[key] = f"recall 후보 · primary {item['primary_score']:.3f} / secondary {second}"
    observation = report.get('observation_evidence')
    if observation is not None:
        records = observation.get('records') if isinstance(observation, dict) else None
        if not isinstance(records, list) or any(
                not isinstance(r, dict) or r.get('side') not in ('front', 'back')
                or any(r.get(f) is not None and not isinstance(r[f], list) for f in ('human_visibility_issues', 'human_glare_areas'))
                or r.get('observation_limit_score') is not None and not (
                    type(r['observation_limit_score']) in (int, float) and 0 <= r['observation_limit_score'] <= 1)
                for r in records):
            raise ValueError('Invalid observation evidence block')
        rows = ''.join(
            f"<tr><td>{esc(r['side'])}</td>"
            f"<td>{'미검토' if r.get('human_visibility_issues') is None else esc(', '.join(map(str, r['human_visibility_issues'])) or '없음(호출자 주장)')}</td>"
            f"<td>{esc(', '.join(map(str, r.get('human_glare_areas') or [])) or '-')}</td>"
            f"<td>{'-' if r['observation_limit_score'] is None else format(r['observation_limit_score'], '.3f')}</td>"
            f"<td>{esc(str(r.get('reason') or '-'))}</td></tr>" for r in records)
        parts.append(f"<h3>관찰 모델 <code>{esc(str(observation.get('model_sha256')))}</code></h3>"
                     '<p class="warn">면 전체의 보정되지 않은 신호다. 낮아도 사람 관찰 제한을 해제하지 못하고 높아도 결함·거절을 뜻하지 않는다.'
                     f" {esc(' '.join(map(str, observation.get('limitations') or [])))}</p><div class=\"wrap\"><table><tr><th>면</th>"
                     f"<th>사람 관찰 제한</th><th>사람 글레어 구역</th><th>모델 신호</th><th>이유</th></tr>{rows}</table></div>")
    block = report.get('recall_review')
    if block is not None:
        rows = ''.join(f"<tr><td>{esc(k[0])}</td><td>{esc(k[1])}</td><td>{esc(k[2])}</td>"
                       f"<td>{esc(notes[k])}</td><td>{esc(str(i.get('reason')))}</td></tr>" for k, i in found.items())
        parts.append(f"<h3>Recall 모델 <code>{esc(str(block.get('model_sha256')))}</code></h3>"
                     f"<p class=\"warn\">정책 {esc(str(block.get('policy')))} · 판정 {esc(str(block.get('verdict')))} · 후보 {len(found)}칸. "
                     '두 모델 중 하나라도 의심하면 사람 검토를 요청할 뿐 결함을 확정하거나 거절하지 않는다.</p>'
                     f"<div class=\"wrap\"><table><tr><th>면</th><th>구역</th><th>종류</th><th>점수</th><th>사유</th></tr>{rows}</table></div>")
    return notes, '<h2>추가 근거 (보조 신호)</h2>' + ''.join(parts) if parts else ''


def side_view(side, face, cells, notes):
    """One face: photo with the human card box and a 3x3 evidence grid, or an explicit missing notice."""
    if face is None or face.get('box') is None:
        reason = '사진 없음' if face is None else '카드 영역 없음'
        return f'<section><h2>{side}</h2><p class="missing">{reason} — 이 면의 모든 칸은 보류</p></section>'
    left, top, right, bottom = face['box']
    flagged = {key[1] for key in notes if key[0] == side}
    marks = []
    for area in GLARE_AREAS:
        x0, y0, x1, y1 = region_box(face['box'], area)
        summary = ' / '.join(f"{c['label'].split('_')[0]}:{STATES[c['state']]}" for c in cells if c['area'] == area)
        held = all(c['state'] == 'unknown' for c in cells if c['area'] == area)
        marks.append(f'<div class="cell{" held" if held else ""}{" recall" if area in flagged else ""}" style="left:{(x0-left)/(right-left)*100:.2f}%;'
                     f'top:{(y0-top)/(bottom-top)*100:.2f}%;width:{(x1-x0)/(right-left)*100:.2f}%;'
                     f'height:{(y1-y0)/(bottom-top)*100:.2f}%" title="{esc(summary, quote=True)}">'
                     f'<small>{area}</small></div>')
    box = f'left:{left*100:.2f}%;top:{top*100:.2f}%;width:{(right-left)*100:.2f}%;height:{(bottom-top)*100:.2f}%'
    return (f'<section><h2>{side}</h2><div class="photo"><img alt="{side} 원본" '
            f'src="data:image/jpeg;base64,{photo(face["image"])}"><div class="card" style="{box}">'
            + ''.join(marks) + '</div></div></section>')


def whole_face_cells(report):
    """Four manual audit questions; region results never supply a whole-face model verdict."""
    source = report['listing_readiness']['records'][0]['cells']
    cells = []
    for side in ('front', 'back'):
        reasons = {c['reason'] for c in source if c['side'] == side}
        missing = next((r for r in ('missing_photo', 'missing_card_region') if r in reasons), None)
        for label, reason in (('centering_defect', 'centering_not_evaluated'),
                              ('observation_limited', 'whole_listing_observability_not_validated')):
            cells.append(dict(side=side, area='face', label=label, state='unknown', score=None,
                              reason=missing or reason,
                              options=['undecidable'] if missing else list(FACE_OPTIONS[label])))
    return cells


def review_page(report_path, request_path, output):
    report, request, report_sha = checked_inputs(report_path, request_path)
    record = report['listing_readiness']['records'][0]
    notes, evidence = evidence_view(report, [(c['side'], c['area'], c['label']) for c in record['cells']])
    release = report.get('release')
    identity = (f"릴리스 {esc(release['release_id'])} · 패키지 {esc(release['package_version'])} · 모델 {esc(', '.join(sorted(release['checkpoint_sha256'])))}"
                if release else '고정 릴리스 아님(직접 checkpoint 실행) — 운영 검토 근거로 쓰지 않는다')
    faces = whole_face_cells(report)
    face_rows = ''.join(
        f"<tr data-face-key='{c['side']}|face|{c['label']}'><td>{c['side']}</td>"
        f"<td>{FACE_NAMES[c['label']]}</td><td class='unknown'>모델 보류</td><td>{esc(c['reason'])}</td>"
        f"<td><select aria-label='{c['side']} {FACE_NAMES[c['label']]} 사람 확인'><option value=''>미검토</option>"
        + ''.join(f"<option value='{d}'>{FACE_OPTIONS[c['label']][d]}</option>" for d in c['options'])
        + '</select></td></tr>' for c in faces)
    rows = ''.join(
        f"<tr data-key='{esc(c['side'])}|{esc(c['area'])}|{esc(c['label'])}'><td>{esc(c['side'])}</td><td>{esc(c['area'])}</td>"
        f"<td>{esc(c['label'])}</td><td class='{esc(c['state'])}'>{STATES[c['state']]}</td>"
        f"<td>{'-' if c['score'] is None else format(c['score'], '.3f')}</td><td>{esc(c['reason'] or '-')}</td>"
        f"<td>{esc(notes.get((c['side'], c['area'], c['label']), '-'))}</td>"
        "<td><select>" + ''.join(f'<option>{d}</option>' for d in ('', *DECISIONS)) + "</select></td></tr>"
        for c in record['cells'])
    payload = json.dumps(dict(report_sha256=report_sha, id=report['id'], release=release,
                              cells=[[c['side'], c['area'], c['label']] for c in record['cells']],
                              face_cells=[[c['side'], c['area'], c['label']] for c in faces])).replace('</', '<\\/')
    page = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Listing Result Review</title><style>
:root{{--bg:#f4f6f9;--fg:#172537;--line:#c6cfdb;--held:#f1c75b;--defect:#d9534f;--normal:#3c8d5a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#11161d;--fg:#e4e9f0;--line:#3a4655}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
.faces{{display:flex;flex-wrap:wrap;gap:16px}}section{{flex:1 1 320px}}.photo{{position:relative}}img{{width:100%;display:block}}
.card{{position:absolute;outline:2px solid #2f7bf6}}.cell{{position:absolute;border:1px dashed #fff;box-sizing:border-box}}
.cell small{{background:#0008;color:#fff;font-size:10px;padding:0 2px}}.cell.held{{background:#f1c75b55}}.cell.recall{{border:2px solid #d9534f}}
.missing{{padding:24px;border:2px dashed var(--held)}}.warn{{border-left:4px solid var(--held);padding:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid var(--line);padding:4px}}
.defect{{color:var(--defect)}}.normal{{color:var(--normal)}}.unknown{{color:#b7861a}}.wrap{{overflow-x:auto}}code{{word-break:break-all}}</style>
<h1>매물 결과 검토 · {esc(report['id'])}</h1>
<p>{identity}<br>model_sha256 <code>{esc(report['model_sha256'])}</code> · 결과 SHA <code>{report_sha[:16]}</code></p>
<p class="warn">전체 판정 불가 사유: {esc(', '.join(record['whole_listing_blockers']))}. 칸 판정은 보조 근거이며 등급·구매 결정이 아니다. 검토 기록은 정답 라벨로 자동 사용하지 않는다.</p>
<div class="faces">{side_view('front', request.get('front'), [c for c in record['cells'] if c['side'] == 'front'], notes)}
{side_view('back', request.get('back'), [c for c in record['cells'] if c['side'] == 'back'], notes)}</div>
{evidence}
<h2>칸별 판정·보류 이유와 검토</h2><div class="wrap"><table><tr><th>면</th><th>구역</th><th>종류</th><th>판정</th><th>점수</th><th>보류 이유</th><th>추가 근거</th><th>검토</th></tr>{rows}</table></div>
<h2>전체 사진 질문 확인 · 센터링과 관찰 제한</h2>
<p class="warn">추가 4항목은 모델이 평가하지 못한 질문의 사람 검토 기록이다. 관찰 제한은 카드 손상을 뜻하지 않는다.
사진·영역이 없으면 판단 불가만 기록한다. 모든 항목 검토도 모델 전체 완료나 학습 정답을 뜻하지 않는다.</p>
<div class="wrap"><table><tr><th>면</th><th>질문</th><th>모델 상태</th><th>보류 이유</th><th>사람 확인</th></tr>{face_rows}</table></div>
<p><button id="export">검토 기록 내보내기</button> <span id="status"></span></p>
<script type="application/json" id="data">{payload}</script><script>
const data=JSON.parse(document.getElementById('data').textContent);
document.getElementById('export').onclick=()=>{{
 const decisions=[...document.querySelectorAll('tr[data-key]')].map(r=>{{const [side,area,label]=r.dataset.key.split('|');return {{side,area,label,decision:r.querySelector('select').value}}}});
 const face_decisions=[...document.querySelectorAll('tr[data-face-key]')].map(r=>{{const [side,area,label]=r.dataset.faceKey.split('|');return {{side,area,label,decision:r.querySelector('select').value}}}});
 const left=decisions.filter(d=>!d.decision).length, faceLeft=face_decisions.filter(d=>!d.decision).length;
 document.getElementById('status').textContent=left||faceLeft?`미검토: 구역 ${{left}}칸 · 전체 사진 질문 ${{faceLeft}}개`:'모든 질문 검토 — 모델 전체 완료나 학습 정답 아님';
 const blob=new Blob([JSON.stringify({{report_sha256:data.report_sha256,id:data.id,decisions,face_decisions}},null,2)],{{type:'application/json'}});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`review-${{data.id}}.json`;a.click();
}};</script></html>"""
    atomic_write(Path(output), page)
    return dict(output=str(output), report_sha256=report_sha, cells=len(record['cells']), release=release, manual_face_cells=len(faces),
                recall_candidates=len(notes), observation_faces=len((report.get('observation_evidence') or {}).get('records', [])))


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
    face_cells = whole_face_cells(report)
    face_values = {(c['side'], c['area'], c['label']): None for c in face_cells}
    if 'face_decisions' in decisions:
        supplied = decisions['face_decisions']
        if (not isinstance(supplied, list) or any(not isinstance(d, dict) or any(
                type(d.get(k)) is not str for k in ('side', 'area', 'label', 'decision')) for d in supplied)):
            raise ValueError('Invalid whole-face review decisions')
        given_faces = [(d['side'], d['area'], d['label']) for d in supplied]
        if len(given_faces) != len(face_values) or set(given_faces) != set(face_values):
            raise ValueError('Whole-face decisions must cover each manual question once')
        allowed = {(c['side'], c['area'], c['label']): c['options'] for c in face_cells}
        if any(d['decision'] not in ('', *allowed[key]) for key, d in zip(given_faces, supplied)):
            raise ValueError('Whole-face decision contradicts the question or missing input')
        face_values = {key: d['decision'] or None for key, d in zip(given_faces, supplied)}
    recalled = recall_cells(report, set(keys))
    by_key = {(d['side'], d['area'], d['label']): d['decision'] or None for d in decisions['decisions']}
    counts = {name: sum(v == name for v in by_key.values()) for name in DECISIONS}
    record = dict(id=report['id'], report_sha256=decisions['report_sha256'], release=report.get('release'),
                  model_sha256=report['model_sha256'], cells=len(keys), unreviewed=sum(v is None for v in by_key.values()),
                  observation_model_sha256=(report.get('observation_evidence') or {}).get('model_sha256'),
                  recall_model_sha256=(report.get('recall_review') or {}).get('model_sha256'),
                  recall_candidate_cells=[list(key) for key in keys if key in recalled],
                  decisions=[dict(side=s, area=a, label=l, model_state=c['state'], model_reason=c['reason'],
                                  decision=by_key[(s, a, l)]) for (s, a, l), c in zip(keys, cells)],
                  counts=counts, review_completed=all(v is not None for v in by_key.values()),
                  ground_truth=False, used_for_training=False, changes_model_verdict=False)
    record.update(region_review_completed=record['review_completed'],
                  face_review_completed=all(v is not None for v in face_values.values()),
                  full_scope_review_completed=record['review_completed'] and all(v is not None for v in face_values.values()),
                  manual_face_cells=len(face_cells), face_unreviewed=sum(v is None for v in face_values.values()),
                  face_decisions=[dict(side=c['side'], area=c['area'], label=c['label'], model_state=c['state'],
                                       model_reason=c['reason'], decision=face_values[(c['side'], c['area'], c['label'])])
                                  for c in face_cells],
                  face_counts={label: {name: sum(value == name for (side, area, key), value in face_values.items() if key == label)
                                      for name in choices} for label, choices in FACE_OPTIONS.items()},
                  face_decisions_are_model_predictions=False)
    atomic_write(output, json.dumps(record, ensure_ascii=False, indent=2))
    return {k: record[k] for k in ('id', 'cells', 'unreviewed', 'counts', 'review_completed', 'ground_truth',
                                         'region_review_completed', 'face_review_completed', 'full_scope_review_completed',
                                         'manual_face_cells', 'face_unreviewed')}
