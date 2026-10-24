"""Read-only validation error gallery; never generates training labels."""
import base64
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageOps
from .data import LABELS
from .side_experiment import side_rows


def error_review(manifest, report_path, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    report = json.loads(Path(report_path).read_text())
    if report.get('evaluation_kind') != 'validation':
        raise ValueError('Only validation reports may be reviewed during development')
    if report.get('manifest_sha256') != hashlib.sha256(Path(manifest).read_bytes()).hexdigest():
        raise ValueError('Manifest differs from the experiment snapshot')
    rows, _, _ = side_rows(manifest, splits={'val'})
    by_id = {r['id']:r for r in rows}
    predictions = report['predictions']
    if len(predictions) != len(by_id) or {p['id'] for p in predictions} != set(by_id):
        raise ValueError('Validation prediction IDs do not match')
    errors, cards = [], []
    for prediction in predictions:
        row = by_id[prediction['id']]
        if prediction['labels'] != row['labels']:
            raise ValueError('Report labels differ from snapshot')
        details = []
        for label in LABELS:
            value = prediction['probabilities'][label]
            if value is not None and (type(value) not in (float,int) or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('Invalid probability')
            truth = row['labels'][label]
            if truth is None or value is None or int(value >= .5) == truth:
                continue
            kind = '오탐' if value >= .5 else '누락'
            errors.append({'id':row['id'],'label':label,'human_label':truth,'model_output':value,
                           'error':kind,'cause':'','reviewer':'','notes':''})
            details.append(f'<li>{html.escape(label)}: 사람 {truth} / 모델 {int(value>=.5)} ({value:.3f}) — {kind}</li>')
        if not details:
            continue
        with Image.open(row['image']) as source:
            picture = ImageOps.exif_transpose(source).convert('RGB')
            picture.thumbnail((900,900))
            buffer = io.BytesIO(); picture.save(buffer,format='JPEG',quality=90)
        encoded = base64.b64encode(buffer.getvalue()).decode()
        issues = ', '.join(row.get('visibility_issues', [])) or '기록 없음'
        cards.append(f'<article><h2>{html.escape(row["id"])}</h2><p>관찰 제한: {html.escape(issues)}</p><img alt="검토할 카드 사진" src="data:image/jpeg;base64,{encoded}"><ul>{"".join(details)}</ul></article>')
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>카드 상태 오류 검토</title>
<style>body{font-family:system-ui;margin:24px;background:#f3f5f9;color:#182235}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}article{background:white;padding:20px;border-radius:12px}img{width:100%;max-height:650px;object-fit:contain}li{margin:12px 0}</style>
<h1>모델선택 사진 오류 검토</h1><p>사람 라벨과 모델 출력의 불일치이며 사람 라벨 오류라는 뜻은 아닙니다. 0=없음/불가, 1=있음/가능. 출력값은 보정된 확률이 아닙니다.</p>
<p>CSV의 cause/reviewer/notes를 기록하세요. 원인 예: 원근·경계 / 반사·흐림 / 작은 결함 / 라벨 재검토 / 판단 불가. 화면용 축소 사진으로 확정하기 어려우면 원본을 확인하세요. 원본 라벨은 자동 수정되지 않습니다.</p><main>''' + ''.join(cards) + '</main></html>'
    output.mkdir(parents=True)
    (output/'index.html').write_text(page,encoding='utf-8')
    with (output/'review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['id','label','human_label','model_output','error','cause','reviewer','notes'])
        writer.writeheader();writer.writerows(errors)
    receipt={'validation_sides':len(rows),'error_sides':len(cards),'error_labels':len(errors),
             'report_sha256':hashlib.sha256(Path(report_path).read_bytes()).hexdigest(),
             'manifest_sha256':report['manifest_sha256'],'labels_modified':False}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2))
    return receipt
