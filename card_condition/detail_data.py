"""Confirmed local detail bags; never manufacture points or whole-card labels."""
import hashlib
from pathlib import Path
from .ebay_dataset import decoded_hash
from .regions import REGION_LABELS, region_box


def confirmed_detail_rows(catalog, proposals, authorization, existing=()):
    if authorization.get('allowed_confirmed_detail_training') is not True:
        raise ValueError('Human authorization for local detail training is required')
    photos = {}
    for item in catalog['items']:
        for photo in item['photos']:
            path = str(Path(photo['path']).resolve())
            if path in photos:
                raise ValueError('Duplicate photo identity in catalog')
            photos[path] = (item['id'], photo)
    groups, hashes = {}, {}
    for row in existing:
        groups.setdefault(row['group'], set()).add(row['split'])
        for digest in row.get('_image_hashes', []):
            hashes.setdefault(digest, set()).add(row['split'])
    rows, skipped, ids = [], [], set()
    for proposal in proposals:
        if proposal['id'] in ids:
            raise ValueError('Duplicate detail ID')
        ids.add(proposal['id'])
        image = str(Path(proposal['image']).resolve())
        anchor = str(Path(proposal['full_back_anchor']).resolve())
        if image not in photos or anchor not in photos or photos[image][0] != photos[anchor][0]:
            raise ValueError('Detail and complete-back anchor must belong to the same listing')
        group = photos[image][0]
        split = proposal['split']
        if split not in ('train', 'val', 'test') or proposal['group'] != group:
            raise ValueError('Invalid split or listing group')
        evidence = proposal['human_evidence']
        label = proposal['label']
        if label not in REGION_LABELS:
            raise ValueError('Unknown detail target')
        target = evidence.get(label)
        if target is None:
            skipped.append(dict(id=proposal['id'], reason='human truth unknown'))
            continue
        if (type(target) is not int or target not in (0, 1)
                or evidence.get('source') != 'direct user reply' or not evidence.get('user_quote')
                or str(Path(evidence['source_image']).resolve()) != image):
            raise ValueError('Explicit human truth tied to the detail photo is required')
        data = Path(image).read_bytes()
        if hashlib.sha256(data).hexdigest() != evidence['source_image_sha256']:
            raise ValueError('Human detail image changed')
        digest, size = decoded_hash(data)
        if digest != photos[image][1]['sha256']:
            raise ValueError('Catalog detail image changed')
        eligibility = proposal.get('full_back_eligibility', {})
        checks = ('single_card', 'logo_visible', 'all_edges_visible', 'corners_visible', 'unobstructed')
        if (not isinstance(eligibility.get('image'), str)
                or str(Path(eligibility['image']).resolve()) != anchor or not eligibility.get('reviewed_by')
                or any(eligibility.get(key) is not True for key in checks)
                or eligibility.get('image_sha256') != hashlib.sha256(Path(anchor).read_bytes()).hexdigest()):
            raise ValueError('Reviewed complete-back photo eligibility is required')
        anchor_hash, _ = decoded_hash(Path(anchor).read_bytes())
        if anchor_hash != photos[anchor][1]['sha256']:
            raise ValueError('Complete-back anchor changed')
        # Use standard normalized-box validation; no card geometry approval is inferred.
        region_box(proposal['box'], 'center')
        groups.setdefault(group, set()).add(split)
        hashes.setdefault(digest, set()).add(split)
        hashes.setdefault(anchor_hash, set()).add(split)
        if len(groups[group]) != 1 or len(hashes[digest]) != 1 or len(hashes[anchor_hash]) != 1:
            raise ValueError('Same listing or decoded photo appears across splits')
        rows.append(dict(id=proposal['id'], group=group, split=split, image=image,
            image_sha256=hashlib.sha256(data).hexdigest(), decoded_sha256=digest,
            source_size=size, box=proposal['box'], label=label, target=target,
            supervision='region_presence', point=None, full_back_anchor=anchor,
            anchor_decoded_sha256=anchor_hash, human_evidence=evidence))
    counts = {key: {str(value): sum(r['split']=='train' and r['label']==key and r['target']==value for r in rows)
                   for value in (0, 1)} for key in REGION_LABELS}
    return rows, dict(rows=len(rows), counts=counts, skipped=skipped,
        ready_labels=[key for key in REGION_LABELS if all(counts[key][str(v)] for v in (0, 1))],
        exact_points_created=0, whole_card_labels_created=0, training_started=False)
