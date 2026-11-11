"""stdin 응답 JSON을 manifest 파일 번호(1부터)와 대조해 저장. 사용: save.py <번호> [repeat]"""
import json
import sys
D = 'artifacts/zone-eval-set-20261112/'
n = int(sys.argv[1]); mf = json.load(open(D + ('manifest_repeat.json' if len(sys.argv) > 2 else 'manifest.json')))['files'][n - 1]
a = json.load(sys.stdin); got = [r['id'] for r in a['responses']]
assert a['kind'] == 'zone_eval_judgments' and sorted(got) == sorted(mf['ids']) and len(set(got)) == len(got), 'ids differ'
assert all(r['judgment'] in ('defect', 'normal', 'unknown') for r in a['responses']), 'null or bad judgment'
json.dump(a, open(D + f'responses/{"repeat" if len(sys.argv) > 2 else "zone"}{n:02d}.json', 'w'), ensure_ascii=False, indent=1); print('ok', len(got))
