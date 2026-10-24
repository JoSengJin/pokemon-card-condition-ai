"""Train-only human geometry review; never turns model proposals into labels."""
import html
import json
from pathlib import Path
from urllib.parse import urlencode

from PIL import ImageDraw

from .data import load_manifest
from .point_probe import digest
from .regions import validate_annotations
from .side_experiment import side_image


def geometry_tasks(records):
    tasks, groups = [], set()
    for row in records:
        if row['split'] != 'train' or row.get('excluded'):
            continue
        annotations = validate_annotations(row.get('side_annotations',{}),row)
        for side,a in annotations.items():
            if (a.get('box_reviewed') is True or (a['box'] != [0,0,1,1] and a.get('box_reviewed') is not False)
                    or not a.get('visibility_issues') or a.get('region_labels')):
                continue
            if row['group'] not in groups and len(groups) == 3:
                continue
            groups.add(row['group'])
            tasks.append(dict(card=row['id'],group=row['group'],side=side,image=row[side],box=a['box'],
                review_url='http://127.0.0.1:8766/?'+urlencode(dict(card=row['id'],geometry=side,image=row[side]))))
    return tasks


def prepare_geometry_review(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists: choose a new geometry review directory')
    before = digest(manifest)
    records = load_manifest(manifest,splits={'train'},require_gradable=False)
    tasks = geometry_tasks(records)
    hashes = {t['image']:digest(t['image']) for t in tasks}
    output.mkdir(parents=True,exist_ok=False)
    sections=[]
    for i,task in enumerate(tasks):
        image=side_image(task['image'],task['box'],False,None)
        draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,image.width-1,image.height-1),outline='red',width=2)
        image.save(output/f'{i}.png')
        title=html.escape(task['card']+' / '+task['side'])
        sections.append(f'<section><h2>{title}</h2><img src="{i}.png" alt="{title}"><p><a href="{html.escape(task["review_url"],quote=True)}">카드 영역 확인하기</a></p></section>')
    if digest(manifest)!=before or any(digest(p)!=h for p,h in hashes.items()):
        raise ValueError('Review inputs changed; discard output')
    result=dict(tasks=tasks,physical_groups=len({t['group'] for t in tasks}),manifest_sha256=before,
        image_hashes=hashes,labels_modified=False,split='train',production_ready=False,
        instruction='결함 라벨은 유지하고 네 변/모서리를 포함하는 카드 영역만 확인하세요. 전체 사진이 맞으면 그대로 확인 체크하세요.')
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>카드 영역 확인</title><style>body{font:18px system-ui;margin:24px}img{max-width:600px;width:100%}section{border-top:1px solid #ccc;margin:24px 0}</style><h1>카드 영역만 확인 · 최대3실물</h1><p>'+result['instruction']+'</p>'+''.join(sections)+'</html>')
    return result
