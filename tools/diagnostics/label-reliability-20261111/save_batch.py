"""stdin의 응답 JSON을 검증해 저장. 사용: save_batch.py <폴더> <파일번호0기반> <저장명>"""
import json
import sys
sys.path.insert(0, 'tools/diagnostics/mobile-point-review-20261110')
from candidate import validate_candidates
d, n, name = sys.argv[1], int(sys.argv[2]), sys.argv[3]
a = json.load(sys.stdin)
validate_candidates(json.load(open('artifacts/mobile-point-review-20261110/packet.json')), a)
ok = set(json.load(open(f'{d}/manifest.json'))['files'][n]['ids']) == {r['id'] for r in a['responses']}
assert ok, 'ids differ from manifest'
json.dump(a, open(f'{d}/responses/{name}', 'w'), ensure_ascii=False, indent=1); print('ok', len(a['responses']))
