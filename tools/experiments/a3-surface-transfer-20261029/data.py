"""Frozen surface units and photo provenance; no model or invented labels."""
import hashlib
from pathlib import Path
from card_condition.regions import GLARE_AREAS, region_box
from card_condition.ebay_dataset import decoded_hash
from card_condition.local_wear_cnn import point_input_pixel, physical_pixel_mask


def surface_rows(coverage):
    rows, points, unsupported = [], [], []
    for item in coverage['units']:
        if item['split'] != 'val' or item['label'] != 'surface_defect' or item['target'] is None:
            continue
        row = dict(item, id=f"{item['card_id']}/{item['side']}/{item['area']}",
                   box=region_box(item['card_box'], item['area']))
        if item['box_reviewed'] is not True:
            unsupported.append(dict(row, kind='region', reason='unreviewed_box'))
        else:
            rows.append(row)
    index = {(r['image_sha256'], r['side'], r['area']): i for i, r in enumerate(rows)}
    for number, item in enumerate(coverage['typed_points']):
        if item['split'] != 'val' or item['label'] != 'surface_defect':
            continue
        point = dict(item, id=f"{item['card_id']}/{item['side']}/surface-point/{number}")
        if item['box_reviewed'] is not True:
            unsupported.append(dict(point, kind='point', reason='unreviewed_box'))
            continue
        p = item['point']; left, top, right, bottom = item['card_box']
        col = sum(p['x'] >= left + n * (right-left)/3 for n in (1, 2))
        line = sum(p['y'] >= top + n * (bottom-top)/3 for n in (1, 2))
        parent = index.get((item['image_sha256'], item['side'], GLARE_AREAS[line*3+col]))
        if p['label'] != 'surface_defect' or parent is None or rows[parent]['target'] != 1:
            raise ValueError('Typed point lacks its same-kind positive region')
        points.append(dict(point, parent_index=parent))
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate surface identity')
    return rows, points, unsupported


def photo_identities(rows):
    identities, raw = {}, {}
    for row in rows:
        path = str(Path(row['image']).resolve())
        if path not in identities:
            data = Path(path).read_bytes()
            raw[path] = hashlib.sha256(data).hexdigest()
            identities[path] = {raw[path], decoded_hash(data)[0]}
        if row['image_sha256'] not in identities[path]:
            raise ValueError('Photo content no longer matches the frozen identity')
    return identities, raw


def check_separation(heads, training, evaluation, identities):
    by_id = {r['id']: r for r in training}
    if len(by_id) != len(training):
        raise ValueError('Duplicate training identity')
    eval_groups = {r['group'] for r in evaluation}
    eval_photos = {s for r in evaluation for s in identities[str(Path(r['image']).resolve())]}
    for head in heads:
        ids = head['train_ids']
        if not ids or len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
            raise ValueError('Unresolved or duplicate head training IDs')
        selected = [by_id[i] for i in ids]
        photos = {s for r in selected for s in identities[str(Path(r['image']).resolve())]}
        if eval_groups & {r['group'] for r in selected} or eval_photos & photos:
            raise ValueError('Head training and evaluation overlap')
    return dict(heads=len(heads), unresolved_ids=0, group_overlap=0, photo_overlap=0)


def point_tokens(rows, points):
    masks = [physical_pixel_mask(r['image'], r['box'], halo=0).reshape(16,14,16,14).any(3).any(1).flatten() for r in rows]
    mapped = []
    for point in points:
        parent = point['parent_index']; row = rows[parent]
        x, y = point_input_pixel(row['image'], row['box'], point['point'])
        token = int(y // 14) * 16 + int(x // 14)
        if not masks[parent][token]:
            raise ValueError('Typed point falls outside physical tokens')
        mapped.append(dict(point, human_token=token, input_pixel=[x,y]))
    return masks, mapped
