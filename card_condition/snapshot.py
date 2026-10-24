"""Freeze reviewed data without moving previously seen cards across splits."""
import hashlib
import json
from pathlib import Path
import tempfile

from .data import load_manifest, training_readiness
from .review import ReviewStore


def snapshot(inventory, output, reference, unassigned=None):
    store = ReviewStore(inventory)
    previous = load_manifest(reference)
    by_id = {r['id']: r['split'] for r in previous}
    by_group = {r['group']: r['split'] for r in previous}
    by_hash = {h: r['split'] for r in previous for h in r['_image_hashes']}
    rows, changes = [], []
    for row in store.rows:
        if row.get('excluded', False):
            continue
        if not row.get('reviewed_by', '').strip():
            raise ValueError(f"{row['id']}: 검토자 미입력")
        if row['labels']['gradable'] == 1 and not row.get('pair_verified', False):
            raise ValueError(f"{row['id']}: 앞뒤 동일 실물 확인 필요")
        known = {x for x in (by_id.get(row['id']), by_group.get(row['group'])) if x}
        # Decode separately to recognize copies even when a new id/group is assigned.
        from PIL import Image, ImageOps
        for side in ('front', 'back'):
            if row.get(side):
                with Image.open(row[side]) as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    digest = hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()
                if digest in by_hash:
                    known.add(by_hash[digest])
        if len(known) > 1:
            raise ValueError(f"{row['id']}: 이전 분할이 충돌합니다")
        split = next(iter(known)) if known else row.get('split') or unassigned
        if split != row.get('split'):
            changes.append({'id': row['id'], 'from': row.get('split'), 'to': split})
        row['split'] = split
        rows.append(row)
    content = ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'snapshot.jsonl'
        path.write_text(content)
        readiness = training_readiness(load_manifest(path))
    if hashlib.sha256(store.path.read_bytes()).hexdigest() != store.revision:
        raise ValueError('검토 파일이 변경되었습니다. 다시 실행하세요.')
    output = Path(output)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(content)
    return {'output': str(output), 'source_sha256': store.revision,
            'reference_sha256': hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
            'records': len(rows), 'excluded': len(store.rows)-len(rows),
            'split_changes': changes, 'readiness': readiness}
