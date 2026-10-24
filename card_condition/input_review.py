"""Train-only original/224/448 input inspection, with no label inference."""
import hashlib
import html
import json
from pathlib import Path

from .edge_views import edge_view_boxes, fixed_tile_boxes
from .point_dataset import point_rows
from .side_experiment import side_image


def input_review(manifest, output, cards):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new directory')
    if not cards or len(cards) != len(set(cards)):
        raise ValueError('Provide distinct train --card IDs')
    before = Path(manifest).read_bytes()
    rows, _ = point_rows(manifest, grid=True, splits={'train'})
    rows = [r for r in rows if r['split'] == 'train' and r['card_id'] in cards]
    if {r['card_id'] for r in rows} != set(cards):
        raise ValueError('Every selected card needs annotated train patches; val/test are not input-review candidates')
    output.mkdir()
    samples, sections = [], []
    for i, row in enumerate(rows):
        views = ([('full', row['box'])] + [(f'edge-{n}', b) for n, b in enumerate(edge_view_boxes(row))]
                 + [(f'tile-{n}', b) for n, b in enumerate(fixed_tile_boxes(row))])
        figures = []
        source = side_image(row['image'], row['card_box'], False, None)
        source.save(output/f'{i}-source.png')
        for name, box in views:
            native = side_image(row['image'], box, True, None)
            width, height = native.size
            images = []
            for size in (None, 224, 448):
                filename = f'{i}-{name}-{size or "native"}.png'
                side_image(row['image'], box, True, size).save(output/filename)
                images.append(f'<figure><a href="{filename}"><img src="{filename}" alt="{name} {size or "native"}"></a><figcaption>{size or "원본 구역"}</figcaption></figure>')
            samples.append(dict(card=row['card_id'], side=row['side'], area=row['area'], labels=row['labels'],
                view=name, box=box, native_size=[width, height],
                content_fraction=min(width, height)/max(width, height),
                short_axis_224=224*min(width, height)/max(width, height),
                image_sha256=row['image_sha256']))
            figures.append(f'<h3>{name}: {width}×{height}px</h3><div class="views">{"".join(images)}</div>')
        title = html.escape(f"{row['card_id']} / {row['side']} / {row['area']}")
        labels = html.escape(json.dumps(row['labels'], ensure_ascii=False))
        sections.append(f'<section><h2>{title}</h2><p>{labels}</p><a href="{i}-source.png">전체 원본 사진</a>{"".join(figures)}</section>')
    if Path(manifest).read_bytes() != before:
        raise ValueError('Manifest changed; discard the incomplete review directory')
    result = dict(evaluation_kind='train_input_review', manifest_sha256=hashlib.sha256(before).hexdigest(),
        cards=cards, patches=len(rows), samples=samples, labels_modified=False, production_ready=False,
        limitations=['Train-only visual inspection; no automated judgment of defect visibility.',
                    'Upsampling does not restore missing original detail. Native crops include no human markup.',
                    'Open PNG links to inspect actual pixels; the HTML preview is scaled for layout.'])
    (output/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    document = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>모델 입력 진단</title><style>body{font:18px system-ui;margin:24px}section{border-top:2px solid #aaa;margin:32px 0}.views{display:flex;flex-wrap:wrap;gap:16px}figure{margin:0}img{width:224px;height:224px;object-fit:contain;background:#ddd}a:focus{outline:3px solid blue}</style><h1>학습 입력 진단</h1><p>전체 원본 · 원본 구역 · 테두리 띠 · 고정 2×2 타일의 224 · 448 입력을 비교합니다. 사진을 클릭하면 실제 픽셀 크기로 볼 수 있습니다. 결함/정상 라벨은 자동 변경하지 않습니다.</p>'+''.join(sections)+'</html>'
    (output/'index.html').write_text(document)
    return result
