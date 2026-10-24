"""Read-only visual diagnosis of two frozen validation reports."""
import hashlib
import html
import json
from pathlib import Path

from PIL import Image, ImageOps

from .edge_views import edge_view_boxes, fixed_tile_boxes
from .side_experiment import side_image


def build(manifest, earlier, later, output, card='d', side='front', label='edge_defect'):
    if (card, side, label) != ('d', 'front', 'edge_defect'):
        raise ValueError('This frozen visual audit is for d/front edge_defect only')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    source = Path(manifest).read_bytes()
    reports = [json.loads(Path(path).read_text()) for path in (earlier, later)]
    digest = hashlib.sha256(source).hexdigest()
    if any(report['manifest_sha256'] != digest for report in reports):
        raise ValueError('The reports do not use this frozen manifest')
    chosen = [{p['id']: p for p in report['predictions'] if p['card_id'] == card and p['side'] == side}
              for report in reports]
    if not chosen[0] or set(chosen[0]) != set(chosen[1]):
        raise ValueError('The reports score different card regions')
    rows = []
    for key, row in chosen[0].items():
        other = chosen[1][key]
        if row['split'] != 'val' or any(row[field] != other[field] for field in
                ('image', 'image_sha256', 'box', 'card_box', 'area', 'labels')):
            raise ValueError('Validation truth or image geometry differs')
        with Image.open(row['image']) as source_image:
            pixels = ImageOps.exif_transpose(source_image).convert('RGB')
            pixel_hash = hashlib.sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
        if pixel_hash != row['image_sha256']:
            raise ValueError('Source image changed')
        rows.append((row, other))
    rows.sort(key=lambda pair: ('upper_left upper_center upper_right middle_left center middle_right '
                                'lower_left lower_center lower_right').split().index(pair[0]['area']))
    output.mkdir(parents=True)
    side_image(rows[0][0]['image'], rows[0][0]['card_box'], True, None).save(output/'card.png')
    cards, counts, maps = [], [], []
    for name, selected in (('기존 타일', 0), ('새 엣지 띠', 1)):
        scored = [(pair[0]['labels'][label], pair[selected]['probabilities'][label]) for pair in rows
                  if pair[0]['labels'][label] is not None]
        counts.append(dict(model=name, positive=sum(truth == 1 for truth, _ in scored),
                           negative=sum(truth == 0 for truth, _ in scored),
                           fp=sum(truth == 0 and score >= .5 for truth, score in scored),
                           fn=sum(truth == 1 and score < .5 for truth, score in scored)))
        cells = []
        for row, other in rows:
            truth, score = row['labels'][label], (row, other)[selected]['probabilities'][label]
            state = 'unknown' if truth is None else 'false' if truth == 0 and score >= .5 else 'correct'
            cells.append(f'<div class="cell {state}"><small>{html.escape(row["area"])}</small><b>{score:.3f}</b></div>')
        maps.append(f'<div class="map"><h3>{name}</h3><div class="cardmap"><img src="card.png" alt="d/front 카드"><div class="grid">{"".join(cells)}</div></div></div>')
    for index, (row, other) in enumerate(rows):
        views = [('전체 구역', row['box'])]
        views += [('타일 '+str(n+1), box) for n, box in enumerate(fixed_tile_boxes(row))]
        views += [('엣지 띠 '+str(n+1), box) for n, box in enumerate(edge_view_boxes(row))]
        tiles = []
        for number, (title, box) in enumerate(views):
            filename = f'{index}-{number}.png'
            side_image(row['image'], box, True, 224).save(output/filename)
            tiles.append(f'<figure><a href="{filename}"><img src="{filename}" alt="{html.escape(title)} 224px"></a><figcaption>{html.escape(title)}</figcaption></figure>')
        scores = [row['probabilities'][label], other['probabilities'][label]]
        truth = row['labels'][label]
        status = '미확인' if truth is None else ('결함' if truth else '정상')
        cards.append('<section><h2>'+html.escape(row['area'])+'</h2><p>사람 정답: '+status+
                     ' · 기존 '+f'{scores[0]:.3f}'+' · 새 '+f'{scores[1]:.3f}'+'</p><div class="views">'+
                     ''.join(tiles)+'</div></section>')
    if Path(manifest).read_bytes() != source:
        raise ValueError('Manifest changed during diagnosis')
    overall = [report['metrics'][label] for report in reports]
    if (overall[0]['tp'] + overall[0]['fn'] != overall[1]['tp'] + overall[1]['fn'] or
            overall[0]['tn'] + overall[0]['fp'] != overall[1]['tn'] + overall[1]['fp']):
        raise ValueError('Validation denominators differ')
    if counts != [dict(model='기존 타일', positive=0, negative=8, fp=3, fn=0),
                  dict(model='새 엣지 띠', positive=0, negative=8, fp=7, fn=0)]:
        raise ValueError('d/front frozen scores differ from the recorded comparison')
    evidence = dict(kind='read_only_val_input_diagnosis', card=card, side=side, label=label,
                    manifest_sha256=digest, image_sha256=rows[0][0]['image_sha256'],
                    counts=counts, overall_validation=overall, regions=len(rows), labels_modified=False, model_modified=False,
                    independent_performance=False, actual_gemini_calls_saved=0)
    (output/'report.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    stats = ''.join(f'<div><b>{html.escape(c["model"])}</b><br>정상 오탐 {c["fp"]}/{c["negative"]}'
                    f'<br>결함 누락 {c["fn"]}/{c["positive"] if c["positive"] else "측정 불가"}</div>' for c in counts)
    page = ('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>d/front 입력·오탐 진단</title><style>
body{font:17px/1.5 system-ui;background:#f4f6fa;color:#172439;margin:0}main{max-width:1150px;margin:auto;padding:24px}section,header{background:white;padding:18px;margin:16px 0;border-radius:12px}h1{margin:0}.stats,.views,.maps{display:flex;gap:14px;flex-wrap:wrap}.stats div{padding:12px;background:#e9efff;border-radius:8px}.views figure{margin:0}.views img{width:144px;height:144px;object-fit:contain;background:#ddd}.views figcaption{text-align:center;font-size:14px}.card{max-width:600px;width:100%}.note{border-left:4px solid #e49a30;padding-left:12px}.map{flex:1 1 280px;max-width:440px}.cardmap{position:relative}.cardmap img{width:100%;display:block}.grid{position:absolute;inset:0;display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,1fr)}.cell{border:1px solid #ffffff90;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;text-shadow:0 1px white;font-size:13px}.cell small{font-size:11px}.false{background:#f5a62399}.correct{background:#39b97b55}.unknown{background:#a8b2c533}a:focus{outline:3px solid blue}</style><main><header><h1>d/front 입력·오탐 진단</h1><p>같은 사람 정답·같은 사진·같은 224px 입력 크기의 두 저장 모델을 비교합니다. 숫자는 보정된 확률이 아닌 모델 점수입니다.</p><div class="stats">'''+stats+'''</div><p class="note">기존 val을 다시 읽은 원인 진단입니다. 독립 성능 개선 수치가 아니며 새 모델을 채택하지 않았습니다. 빛과 그림자는 의심 원인일 뿐, 픽셀과 점수만으로 원인을 확정할 수 없습니다.</p><p>주황: 정상 엣지 오탐 · 초록: 정답 일치 · 회색: 정답 미확인. 3×3 색상은 결함의 정확한 픽셀 위치가 아닙니다.</p><div class="maps">'''+''.join(maps)+'''</div></header>'''+''.join(cards)+'''<section><h2>전후 판단</h2><p>새 엣지 띠 입력은 d/front 정상 엣지 오탐을 3/8→7/8로 악화했습니다(+50%p). 같은 전체 val에서도 5/12→10/12(+41.7%p), 결함 누락 0/15→1/15(+6.7%p)였습니다. 그림·그림자와 실제 바깥 테두리를 구별하는 근거가 더 필요합니다. 타일과 띠는 입력이며, 그림의 어느 픽셀이 예측에 기여했는지는 이 화면만으로 알 수 없습니다.</p><p>개발 진척률 4/6(약 67%), 독립 정확도 변화 미확인, 실제 Gemini 절감 0건.</p></section></main></html>''')
    (output/'index.html').write_text(page)
    return evidence
