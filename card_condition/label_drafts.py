"""Separate AI proposals from human truth; only explicit reviewed decisions promote labels."""
import copy
import hashlib
import json
from pathlib import Path

from .regions import REGION_LABELS, REGION_TARGET_AREAS, region_box, validate_annotations


def draft_status(rows, path):
    if not path.exists():
        return []
    proposals = json.loads(path.read_text())
    if not isinstance(proposals, list):
        raise ValueError('AI 초안 파일은 목록이어야 합니다.')
    by_id = {row['id']: row for row in rows}
    seen, slots, hashes, result = set(), set(), {}, []
    for proposal in proposals:
        if (not isinstance(proposal, dict) or set(proposal) != {'id','card','side','image_sha256','box','area','label','value','reason','author'}
                or any(not isinstance(proposal[k], str) or not proposal[k].strip() or len(proposal[k]) > 2000
                       for k in ('id','card','side','image_sha256','area','label','reason','author'))
                or proposal['id'] in seen or proposal['card'] not in by_id
                or proposal['side'] not in ('front','back') or proposal['label'] not in REGION_LABELS
                or proposal['area'] not in REGION_TARGET_AREAS[proposal['label']]
                or type(proposal['value']) is not int or proposal['value'] not in (0,1)):
            raise ValueError('AI 초안 형식·대상·구역이 올바르지 않습니다.')
        region_box(proposal['box'], proposal['area'])
        slot = (proposal['card'],proposal['side'],proposal['area'],proposal['label'])
        if slot in slots:
            raise ValueError('동일 구역·종류의 초안은 하나만 허용됩니다.')
        slots.add(slot)
        seen.add(proposal['id'])
        fingerprint = hashlib.sha256(json.dumps(proposal, sort_keys=True).encode()).hexdigest()
        row = by_id[proposal['card']]
        annotation = row.get('side_annotations', {}).get(proposal['side'], {})
        image = row.get(proposal['side'])
        if image not in hashes:
            hashes[image] = hashlib.sha256(Path(image).read_bytes()).hexdigest() if image else None
        reason = ''
        if any(r.get('fingerprint') == fingerprint for r in row.get('ai_draft_reviews', [])):
            reason = '이미 검토한 초안'
        elif row.get('split') != 'train' or row.get('excluded'):
            reason = '학습용 카드만 제안 승인 가능'
        elif annotation.get('image') != image or hashes[image] != proposal['image_sha256'] or annotation.get('box') != proposal['box']:
            reason = '사진 또는 카드 영역이 변경됨'
        elif annotation.get('box_reviewed') is not True:
            reason = '카드 영역 확인 필요'
        else:
            area, key, value = proposal['area'], proposal['label'], proposal['value']
            existing = annotation.get('region_labels', {}).get(area, {}).get(key)
            box = region_box(annotation['box'], area)
            overlap = any(p['label'] == key and box[0] <= p['x'] <= box[2] and box[1] <= p['y'] <= box[3]
                          for p in annotation.get('defect_points', []))
            limited = (area in annotation.get('glare_areas', [])
                or bool(set(annotation.get('visibility_issues', [])) - {'glare','perspective'})
                or 'glare' in annotation.get('visibility_issues', []) and not annotation.get('glare_areas'))
            if existing is not None:
                reason = '이미 사람이 기록한 구역'
            elif value == 0 and (overlap or limited):
                reason = '결함점 또는 관찰 제한과 정상 제안이 충돌함'
            elif value == 1 and (annotation['labels'].get(key) == 0 or row['labels'].get(key) == 0):
                reason = '사람이 기록한 면 정상과 충돌함'
        result.append({**proposal, 'fingerprint': fingerprint, 'available': not reason, 'blocked_reason': reason})
    return result


def review_drafts(rows, path, ids, decision, reviewer):
    if (not isinstance(ids, list) or not ids or any(not isinstance(i,str) for i in ids)
            or len(ids) != len(set(ids)) or decision not in ('approve','reject')
            or not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer) > 100):
        raise ValueError('선택한 초안·승인/거절·검토자 입력이 필요합니다.')
    updates = copy.deepcopy(rows)
    candidates = {p['id']: p for p in draft_status(updates, path)}
    if any(identity not in candidates or not candidates[identity]['available'] for identity in ids):
        raise ValueError('초안이 변경되었거나 이미 검토됐습니다. 최신 화면에서 다시 확인하세요.')
    reviews = {}
    for identity in ids:
        proposal = candidates[identity]
        row = next(r for r in updates if r['id'] == proposal['card'])
        if decision == 'approve':
            annotation = row['side_annotations'][proposal['side']]
            region = annotation.setdefault('region_labels', {}).setdefault(proposal['area'], {k:None for k in REGION_LABELS})
            region[proposal['label']] = proposal['value']
            if proposal['value'] == 1:
                annotation['labels'][proposal['label']] = 1
                row['labels'][proposal['label']] = 1
            validate_annotations(row['side_annotations'], row)
        row['reviewed_by'] = reviewer.strip()
        records = reviews.setdefault(row['id'], copy.deepcopy(row.get('ai_draft_reviews', [])))
        records.append(dict(id=identity, fingerprint=proposal['fingerprint'], decision=decision,
                            reviewed_by=reviewer.strip(), author=proposal['author'], proposal=proposal))
    return updates, reviews
