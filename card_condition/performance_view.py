"""Standalone visual audit of frozen edge reports; never runs inference."""
import base64
import hashlib
import html
import io
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

from .data import load_manifest
from .point_dataset import point_rows
from .regions import GLARE_AREAS


ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ROOT / 'artifacts/kieuk13-independent-20261013'
EXPLORATORY = ROOT / 'artifacts/kieuk15-independent-20261013'
INTAKE = ROOT / 'data/kieuk15-surface-intake-20261013.jsonl'
NORMAL_ONLY = ROOT / 'artifacts/kieuk15-normal-only-20261013'
NAMES = dict(zip(GLARE_AREAS, ('좌상', '상단', '우상', '좌측', '중앙', '우측', '좌하', '하단', '우하')))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def photo(path):
    with Image.open(path) as source:
        picture = ImageOps.exif_transpose(source).convert('RGB')
        picture.thumbnail((900, 900))
        output = io.BytesIO()
        picture.save(output, 'JPEG', quality=88)
    return base64.b64encode(output.getvalue()).decode()


def counts(items):
    result = dict(tp=0, tn=0, fp=0, fn=0)
    for truth, predicted in items:
        result[('t' if truth == predicted else 'f') + ('p' if predicted else 'n')] += 1
    return result


def load_heldout():
    report = json.loads((HELDOUT / 'report.json').read_text())
    manifest = HELDOUT / 'frozen-test.jsonl'
    if report['source_sha256'] != digest(manifest):
        raise ValueError('ㅋ/13 frozen test differs from the report')
    rows = {row['id']: row for row in load_manifest(manifest, splits={'test'}, require_gradable=False)}
    for path, expected in report['image_sha256'].items():
        if digest(path) != expected:
            raise ValueError('ㅋ/13 image differs from the registered input')
    details = report['details']
    if len(details) != 9 or len({(d['card'], d['area']) for d in details}) != 9:
        raise ValueError('ㅋ/13 scored regions differ from the frozen plan')
    for detail in details:
        if rows[detail['card']]['side_annotations']['back']['region_labels'][detail['area']]['edge_defect'] != detail['truth']:
            raise ValueError('ㅋ/13 human truth differs from the frozen manifest')
    for model in ('primary', 'review_union'):
        value = [(d['truth'], int(d['primary_score'] >= .5) if model == 'primary' else int(d['review_union']))
                 for d in details]
        if counts(value) != report['counts'][model]:
            raise ValueError('ㅋ/13 report counts differ from region decisions')
    return rows, details, report


def load_exploratory():
    manifest = EXPLORATORY / 'frozen-test.jsonl'
    expected, _ = point_rows(manifest, grid=True, splits={'test'})
    truth = {row['id']: row for row in expected}
    rows = {row['id']: row for row in load_manifest(manifest, splits={'test'}, require_gradable=False)}
    reports = [json.loads((EXPLORATORY / name).read_text()) for name in
               ('baseline224-exploratory.json', 'quarantined-new224-report.json')]
    if len(truth) != 10:
        raise ValueError('ㅋ/15 exploratory score denominator changed')
    for report in reports:
        if report['manifest_sha256'] != digest(manifest):
            raise ValueError('ㅋ/15 report and frozen manifest differ')
        predictions = {p['id']: p for p in report['predictions']}
        if len(predictions) != 10 or set(predictions) != set(truth):
            raise ValueError('ㅋ/15 prediction regions differ')
        for key, prediction in predictions.items():
            original = truth[key]
            if any(prediction[field] != original[field] for field in ('area', 'box', 'card_box', 'labels', 'image_sha256')):
                raise ValueError('ㅋ/15 truth or region geometry differs')
        scored = [(p['labels']['edge_defect'], int(p['probabilities']['edge_defect'] >= .5))
                  for p in predictions.values()]
        if counts(scored) != report['metrics']['edge_defect']:
            raise ValueError('ㅋ/15 report counts differ from predictions')
    return rows, [{p['id']: p for p in report['predictions']} for report in reports], reports


def load_normal_only():
    plan = json.loads((NORMAL_ONLY / 'plan.json').read_text())
    manifest = NORMAL_ONLY / 'frozen-test.jsonl'
    if plan['frozen_sha256'] != digest(manifest) or plan['source_sha256'] != digest(INTAKE):
        raise ValueError('Normal-only test registration differs from the source')
    rows = load_manifest(manifest, splits={'test'}, require_gradable=False)
    if len(rows) != 1 or rows[0]['id'] != plan['card_id'] or digest(rows[0]['back']) != plan['image_sha256']:
        raise ValueError('Normal-only test card or image differs from registration')
    expected, _ = point_rows(manifest, grid=True, splits={'test'})
    if (len(expected) != 8 or plan['scored_edge_normal_regions'] != 8 or
            any(p['labels']['edge_defect'] != 0 for p in expected)):
        raise ValueError('Normal-only test truth or denominator changed')
    reports = []
    for name, checkpoint in (
            ('baseline224-report.json', 'artifacts/kieuk-integration-20261012/revised-with-normals-224/model.pt'),
            ('candidate224-report.json', 'artifacts/kieuk14-train-20261013/candidate224/model.pt')):
        report = json.loads((NORMAL_ONLY / name).read_text())
        if (report['manifest_sha256'] != digest(manifest) or
                report['model_sha256'] != plan['model_sha256'][checkpoint] or
                digest(ROOT / checkpoint) != plan['model_sha256'][checkpoint] or
                report['input_hashes'][str((ROOT / checkpoint).resolve())] != plan['model_sha256'][checkpoint] or
                report['input_hashes'][str(Path(rows[0]['back']).resolve())] != plan['image_sha256']):
            raise ValueError('Normal-only model or image differs from frozen evaluation')
        predictions = {p['id']: p for p in report['predictions']}
        if len(predictions) != 8 or set(predictions) != {p['id'] for p in expected}:
            raise ValueError('Normal-only scored regions differ from registration')
        for truth in expected:
            prediction = predictions[truth['id']]
            if any(prediction[key] != truth[key] for key in ('area', 'box', 'card_box', 'labels', 'image_sha256')):
                raise ValueError('Normal-only prediction geometry or truth differs')
        scored = [(0, int(p['probabilities']['edge_defect'] >= .5)) for p in predictions.values()]
        if counts(scored) != report['metrics']['edge_defect']:
            raise ValueError('Normal-only report counts differ from scores')
        reports.append(predictions)
    return rows[0], reports


def card_view(row, cells, caption, human_marks=None):
    face = row['side_annotations']['back']
    if face.get('box_reviewed') is not True:
        raise ValueError('Card box must be reviewed before drawing a grid')
    left, top, right, bottom = face['box']
    marks = []
    human_marks = human_marks or {}
    for area in GLARE_AREAS:
        item = cells.get(area)
        if item is None:
            marks.append('<div class="cell unknown"><small>' + NAMES[area] + '</small></div>')
            continue
        truth, prediction, score = item
        state = 'pending' if prediction is None else ('correct' if truth == prediction else 'miss' if truth else 'false')
        label = '정답 ' + ('결함' if truth else '정상')
        if prediction is not None:
            label += ' · 모델 ' + ('의심' if prediction else '정상') + ' · 출력 ' + f'{score:.3f}'
        extra = '<small>' + html.escape(human_marks[area]) + '</small>' if area in human_marks else ''
        marks.append('<div class="cell ' + state + '" title="' + html.escape(label, quote=True) + '"><small>'
                     + NAMES[area] + '</small><strong>' + ('대기' if prediction is None else f'{score:.3f}')
                     + '</strong>' + extra + '</div>')
    box = f'left:{left*100:.3f}%;top:{top*100:.3f}%;width:{(right-left)*100:.3f}%;height:{(bottom-top)*100:.3f}%'
    image = photo(row['back'])
    return ('<article><h3>' + html.escape(row['id']) + '</h3><p>' + html.escape(caption)
            + '</p><div class="photo"><img alt="' + html.escape(row['id'], quote=True)
            + ' 뒷면" src="data:image/jpeg;base64,' + image + '"><div class="overlay" style="'
            + box + '">' + ''.join(marks) + '</div></div></article>')


def table(details, exploratory=False):
    lines = []
    for item in details:
        truth = item['truth']
        values = ((item['primary_score'], '의심' if item['primary_score'] >= .5 else '정상'),
                  (item['new_score'], '의심' if item['new_score'] >= .5 else '정상')) if exploratory else (
                  (item['primary_score'], '의심' if item['primary_score'] >= .5 else '정상'),
                  (None, '의심' if item['review_union'] else '정상'))
        shown = [(f'{score:.3f}' if score is not None else '점수 미저장') + ' · ' + decision for score, decision in values]
        lines.append('<tr><td>' + html.escape(item['card']) + '</td><td>' + NAMES[item['area']]
                     + '</td><td>' + ('결함' if truth else '정상') + '</td><td>' + shown[0]
                     + '</td><td>' + shown[1] + '</td></tr>')
    second = '새 224' if exploratory else '224+448 재검토'
    return ('<details><summary>구역별 근거 ' + str(len(details)) + '개 보기</summary><div class="scroll"><table><thead><tr>'
            '<th>실물</th><th>구역</th><th>사람 정답</th><th>기존 224</th><th>' + second
            + '</th></tr></thead><tbody>' + ''.join(lines) + '</tbody></table></div></details>')


def build(output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new HTML path')
    held_rows, held, held_report = load_heldout()
    explore_rows, predictions, explore_reports = load_exploratory()
    normal_row, normal_predictions = load_normal_only()
    intake_rows = {row['id']: row for row in load_manifest(INTAKE, splits={'test'}, require_gradable=False)}
    recent = intake_rows['ㅋ-15-surface-4']
    recent_face = recent['side_annotations']['back']
    if (recent_face.get('box_reviewed') is not True or
            sum(labels['edge_defect'] == 0 for labels in recent_face['region_labels'].values()) != 8 or
            recent_face['region_labels']['lower_left']['surface_defect'] != 1):
        raise ValueError('Latest human labels are incomplete or changed')
    held_cards = []
    for row in held_rows.values():
        cells = {d['area']: (d['truth'], int(d['primary_score'] >= .5), d['primary_score'])
                 for d in held if d['card'] == row['id']}
        held_cards.append(card_view(row, cells, '기존 224 · 사람 정답과 비교'))
    explore_cards, explore_details = [], []
    old, new = predictions
    for row in explore_rows.values():
        matched = [p for p in new.values() if p['card_id'] == row['id']]
        cells = {p['area']: (p['labels']['edge_defect'], int(p['probabilities']['edge_defect'] >= .5),
                            p['probabilities']['edge_defect']) for p in matched}
        explore_cards.append(card_view(row, cells, '새 224 · 탐색용, 성능 근거 아님'))
        for p in matched:
            explore_details.append(dict(card=row['id'], area=p['area'], truth=p['labels']['edge_defect'],
                                        primary_score=old[p['id']]['probabilities']['edge_defect'],
                                        new_score=p['probabilities']['edge_defect']))
    normal_cards = []
    normal_details = []
    for label, model in zip(('이전 224', '새 224'), normal_predictions):
        cells = {p['area']: (0, int(p['probabilities']['edge_defect'] >= .5), p['probabilities']['edge_defect'])
                 for p in model.values()}
        normal_cards.append(card_view(normal_row, cells, label + ' · 정상 엣지 8구역'))
    for key, earlier in normal_predictions[0].items():
        newer = normal_predictions[1][key]
        normal_details.append(dict(card=normal_row['id'], area=earlier['area'], truth=0,
                                   primary_score=earlier['probabilities']['edge_defect'],
                                   new_score=newer['probabilities']['edge_defect']))
    normal_counts = [counts([(0, int(p['probabilities']['edge_defect'] >= .5)) for p in model.values()])
                     for model in normal_predictions]
    html_page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>카드 상태 AI · 시각 성능 검토</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#172537;font:16px/1.5 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:clamp(28px,4vw,42px);margin:0}h2{margin:0 0 8px}.intro,.section,article{background:#fff;border:1px solid #dce2eb;border-radius:14px;padding:20px;margin-bottom:18px}.intro{border-top:6px solid #164bd8}.muted{color:#4b5b70}.warn{border-left:4px solid #d97706;padding-left:12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.cards article{margin:0}.photo{position:relative;line-height:0;max-width:520px;margin:auto}.photo img{width:100%;height:auto;display:block}.overlay{position:absolute;display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,1fr);border:2px solid #164bd8}.cell{border:1px solid #64748b60;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;line-height:1.1;color:#102036;text-shadow:0 1px #fff;font-size:13px}.cell small{font-size:11px}.cell strong{font-size:12px}.correct{background:#33bd7b55}.miss{background:#e85c5c99}.false{background:#f2a64799}.pending{background:#498de560}.unknown{background:#aeb6c529}.stats{display:flex;flex-wrap:wrap;gap:12px}.stat{min-width:145px;padding:12px 16px;background:#eaf0ff;border-radius:10px}.stat strong{display:block;font-size:24px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:600px}th,td{border-bottom:1px solid #dce2eb;text-align:left;padding:8px}summary{cursor:pointer;font-weight:600;margin:12px 0}.legend{display:flex;flex-wrap:wrap;gap:12px}.swatch{display:inline-block;width:14px;height:14px;margin-right:5px;border:1px solid #64748b;vertical-align:middle}.source{overflow-wrap:anywhere;font-size:13px}@media(max-width:600px){main{padding:12px}.section,.intro,article{padding:14px}}
</style><main><header class="intro"><h1>카드 상태 AI · 시각 성능 검토</h1><p>사람이 확인한 정답과 저장된 모델 출력을 뒷면 사진의 3×3 구역에 표시했습니다. 색은 구역별 비교 결과이며 결함의 정확한 점 위치가 아닙니다.</p><div class="legend"><span><i class="swatch" style="background:#33bd7b55"></i>일치</span><span><i class="swatch" style="background:#e85c5c99"></i>결함 누락</span><span><i class="swatch" style="background:#f2a64799"></i>정상 오탐</span><span><i class="swatch" style="background:#aeb6c529"></i>정답 미확인</span><span><i class="swatch" style="background:#498de560"></i>추론 전</span></div><p class="muted">판정 기준 0.5. 숫자는 모델 출력 점수이며 보정된 확률이 아닙니다. 미확인 구역은 성능 분모에서 제외합니다.</p></header>
<section class="section"><h2>1 · 독립 시험: ㅋ/13, 이미 사용한 시험 자료</h2><div class="stats"><div class="stat">결함 탐지<strong>0/1</strong>누락 1/1</div><div class="stat">정상 판정<strong>8/8</strong>오탐 0/8</div><div class="stat">실물 수<strong>2장</strong>정답 구역 9개</div></div><p class="warn">하단 중앙 미세 엣지 화이트닝을 기존 224와 224+448 재검토 모두 놓쳤습니다. 결함 한 구역의 사례 결과이며 일반화 정확도가 아닙니다. 이 시험은 다시 모델 선택에 쓰지 않습니다.</p><div class="cards">''' + ''.join(held_cards) + '</div>' + table(held) + '''</section>
<section class="section"><h2>2 · 탐색용 비교: ㅋ/15</h2><div class="stats"><div class="stat">이전 224<strong>누락 0/2</strong>오탐 0/8</div><div class="stat">새 224<strong>누락 0/2</strong>오탐 0/8</div><div class="stat">전후 차이<strong>0%p</strong>같은 10구역</div></div><p class="warn">첫 추론 전 등록한 결함 구역 수와 실제 저장된 결함점의 구역 수가 달라 독립 성능 증거에서 제외했습니다. 아래는 원인 검토용이며 새 모델의 개선으로 해석하지 않습니다.</p><div class="cards">''' + ''.join(explore_cards) + '</div>' + table(explore_details, True) + '''</section>
<section class="section"><h2>3 · 새 실물의 정상 엣지만 독립 확인: ㅋ/15 img_4</h2><div class="stats"><div class="stat">이전 224<strong>오탐 ''' + str(normal_counts[0]['fp']) + '''/8</strong>결함 정답 0</div><div class="stat">새 224<strong>오탐 ''' + str(normal_counts[1]['fp']) + '''/8</strong>전후 ''' + str((normal_counts[1]['fp'] - normal_counts[0]['fp']) * 12.5) + '''%p</div><div class="stat">실물 수<strong>1장</strong>정상 구역 8개</div></div><p class="warn">두 모델 모두 정상 테두리에서 여러 곳을 결함으로 의심했습니다. 실제 엣지 결함 정답은 없으므로 누락률은 계산할 수 없습니다. 이 실물은 이후 모델 선택·재시험에 쓰지 않습니다.</p><div class="cards">''' + ''.join(normal_cards) + '</div>' + table(normal_details, True) + '''<p>좌하단 빨간 선 안쪽 화이트닝은 <b>표면 결함</b>입니다. 이 엣지 전용 모델은 표면 결함을 판정하지 않았습니다.</p></section>
<section class="section"><h2>4 · 아직 모델 추론 전인 새 사례</h2><p>ㅋ/15 img_3은 사용자 확인상 안쪽 인쇄면에 화이트닝이 있지만 카드 영역 확인 전입니다. 정확한 위치 점이나 엣지 정상 여부를 추정하지 않습니다.</p></section>
<section class="section"><h2>현재 판단</h2><p>독립 시험 ㅋ/13에서는 미세 엣지 결함을 놓쳤고, 별도 새 실물 ㅋ/15 img_4에서는 두 모델 모두 정상 엣지를 여러 곳 오탐했습니다. 서로 다른 정답·실물·분모의 수치를 합쳐 정확도를 계산하지 않습니다. 개발 진척률은 4/6(약 67%)이며 실제 Gemini 호출 절감은 0건입니다. 운영 모델과 Gemini fallback은 그대로입니다.</p><details><summary>입력 출처와 검증 상태</summary><p class="source">ㅋ/13: frozen-test.jsonl + report.json · SHA 검증 · 독립 시험. 기존 ㅋ/15: frozen-test.jsonl + 두 report.json · SHA/정답/채점수 검증 · 탐색용. 새 정상 엣지: kieuk15-normal-only-20261013/frozen-test.jsonl + 두 report.json · 사전 등록/정답/모델 SHA 검증 · 정상만 독립 확인.</p></details></section></main></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_page, encoding='utf-8')
    return dict(output=str(output), heldout=held_report['counts'], exploratory=[r['metrics']['edge_defect'] for r in explore_reports], normal_only=normal_counts,
                inputs={str(p): digest(p) for p in (HELDOUT / 'frozen-test.jsonl', HELDOUT / 'report.json',
                        EXPLORATORY / 'frozen-test.jsonl', EXPLORATORY / 'baseline224-exploratory.json',
                        EXPLORATORY / 'quarantined-new224-report.json', INTAKE)})
