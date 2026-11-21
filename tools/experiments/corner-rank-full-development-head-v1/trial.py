"""Independent worker entry point is provided by the future sealed cohort plan."""
from hashlib import sha256
import json
from pathlib import Path

from card_condition.regions import region_box
from evaluate import ARMS, compare
from score import identity, score_card
from timing import PHASES, benchmark


def frozen_json(path, expected_sha):
    data = Path(path).read_bytes()
    if sha256(data).hexdigest() != expected_sha:
        raise ValueError('Manifest SHA256 mismatch')
    return json.loads(data)


def check_requests(requests):
    required = {'id','side','image','box','box_reviewed','raw_sha256','decoded_sha256'}
    ids, raw, decoded = set(), set(), set()
    for request in requests:
        if set(request) != required or request['side'] != 'back' or request['box_reviewed'] is not True:
            raise ValueError('Invalid frozen request fields')
        region_box(request['box'], 'upper_left')
        actual = identity(request['image'])
        if any(request[k] != v for k,v in actual.items()):
            raise ValueError('Frozen image mismatch')
        if (request['id'] in ids or actual['raw_sha256'] in raw or actual['decoded_sha256'] in decoded):
            raise ValueError('Duplicate physical/request or photo ID')
        ids.add(request['id'])
        raw.add(actual['raw_sha256'])
        decoded.add(actual['decoded_sha256'])


def score_pairs(body, requests, heads, device):
    results = []
    for request in requests:
        row = dict(id=request['id'], identity={k:request[k] for k in ('raw_sha256','decoded_sha256','box')}, failures={})
        for name in ARMS:
            try:
                row[name] = score_card(body,request,heads[name],device,PHASES[name])
            except (OSError, ValueError, RuntimeError) as exc:
                row[name] = {}
                row['failures'][name] = type(exc).__name__
        results.append(row)
    return results


def run_sealed(body, heads, device, files, out):
    """Files holds path/expected_sha for requests, answers, warm and exclusions. The worker supplies verified models."""
    requests = frozen_json(**files['requests'])
    warm = frozen_json(**files['warm'])
    if len(requests) not in (350, 6900):
        raise ValueError('Expected the declared 350- or 6900-card cohort')
    check_requests(requests)
    check_requests(warm)
    exclusions = frozen_json(**files['exclusions'])
    forbidden_ids = set(exclusions['physical_ids']) | {r['id'] for r in warm}
    forbidden_photos = set(exclusions['photo_sha256']) | {
        r[field] for r in warm for field in ('raw_sha256','decoded_sha256')}
    if any(r['id'] in forbidden_ids or r['raw_sha256'] in forbidden_photos
           or r['decoded_sha256'] in forbidden_photos for r in requests):
        raise ValueError('Prior development/evaluation card or photo overlaps independent trial')
    if len(warm) != 20:
        raise ValueError('Expected 20 frozen warm-up cards')
    predictions = score_pairs(body,requests,heads,device)
    out = Path(out)
    (out/'predictions.json').write_text(json.dumps(predictions, allow_nan=False)+'\n')
    answers = frozen_json(**files['answers'])
    grades = compare(predictions,answers)
    counts = tuple(sum(any(t['corners'].values()) == positive for t in answers) for positive in (True,False))
    if counts not in ((150,200),(3200,3700)):
        raise ValueError('Independent sample counts differ from the declared recruitment design')
    timing = None if grades['held'] else benchmark(body,requests,answers,warm,heads,device)
    result = dict(grades, timing=timing,
                  replacement_review=bool(grades['d3'] and grades['superiority'] and timing and timing['valid']))
    (out/'independent-result.json').write_text(json.dumps(result, allow_nan=False)+'\n')
    return result
