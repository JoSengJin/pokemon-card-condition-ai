"""stdin 응답 JSON 검증·저장. 사용: sev_save.py <번호> [repeat]"""
import json
import sys
D = 'artifacts/severity-repro-20261112/'
n = int(sys.argv[1]); rep = len(sys.argv) > 2
mf = json.load(open(D + ('manifest_repeat.json' if rep else 'manifest.json')))['files'][n - 1]; a = json.load(sys.stdin); got = [r['id'] for r in a['responses']]
assert a['kind'] == 'severity_judgments' and sorted(got) == sorted(mf['ids']) and len(set(got)) == len(got), 'ids differ'
assert all(r['level'] in ('0', '1', '2', 'unknown') for r in a['responses']), 'null or bad level'
json.dump(a, open(D + f'responses/{"srep" if rep else "sev"}{n:02d}.json', 'w'), ensure_ascii=False, indent=1); print('ok', len(got))
