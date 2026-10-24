"""Native-pixel evidence for a local photo review; creates no condition labels."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw


def write_region_review(image_path, box, output):
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in box)
            or not (box[0] < box[2] and box[1] < box[3])):
        raise ValueError('Expected a normalized nonempty crop box')
    image_path, output = Path(image_path), Path(output)
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
    w, h = image.size
    bounds = (math.floor(box[0]*w), math.floor(box[1]*h),
              math.ceil(box[2]*w), math.ceil(box[3]*h))
    crop = image.crop(bounds)
    evidence = dict(source_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
        oriented_source_size=[w, h], normalized_box=list(box), pixel_box=list(bounds),
        native_crop_size=list(crop.size), default_display_scale=1, labels_created=0,
        quality_decision=None, context_marker='A', marker_is_condition_prediction=False, warning='Enlargement adds no source detail; native size alone does not establish judgeability.')
    output.mkdir(parents=True, exist_ok=False)
    crop.save(output/'native.png')
    image.save(output/'source.png')
    context = image.copy()
    draw = ImageDraw.Draw(context)
    draw.rectangle((bounds[0], bounds[1], bounds[2]-1, bounds[3]-1), outline='#ff8a00', width=2)
    draw.text((bounds[0], max(0, bounds[1]-14)), 'A', fill='#ff8a00')
    context.save(output/'context.png')
    (output/'evidence.json').write_text(json.dumps(evidence, indent=2))
    width, height = crop.size
    (output/'index.html').write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>원본 픽셀 검토</title>
<style>body{{font:18px/1.7 system-ui;max-width:1100px;margin:auto;padding:24px}}
.scroll{{overflow:auto}}.context{{max-width:100%;height:auto}}.note{{background:#fff0c5;padding:16px}}</style>
<h1>원본 픽셀 기준으로 보기</h1><p class="note">원본 구간 {width}×{height}px · 기본 표시 1:1.
확대는 새로운 세부 정보를 만들지 않습니다. 크기만으로 판독 가능 여부를 확정하지 않습니다.</p>
<h2>1:1 원본 구간</h2><div class="scroll"><img src="native.png" width="{width}" height="{height}" alt="원본 픽셀 구간"></div>
<details><summary>2배 보조 확대 · 추가 정보 없음</summary><div class="scroll"><img src="native.png" width="{width*2}" height="{height*2}" alt="보조 확대"></div></details>
<h2>전체 사진에서 확인할 위치</h2><p>주황색 A는 확인 구간입니다. 결함 예측이나 정상 표시가 아닙니다.</p>
<img class="context" src="context.png" alt="주황색 A로 확인 구간만 표시한 전체 사진">
<a href="source.png">표시 없는 전체 원본 파일 열기</a>
<p>정상·결함 라벨은 생성하지 않았습니다. 판단하기 어렵다면 미확인으로 남깁니다.</p>
<p><a href="evidence.json">원본 해상도와 좌표 근거</a></p></html>''')
    return evidence
