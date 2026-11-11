"""재판정 40곳을 카드 마스크(rows2.bad|center_out) 기준 위/밖으로 나눈 탐색 분석. 사전 등록 외, 원인 진단용. 학습·라벨 변경 0."""
import glob
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from kappa import R, stats, boot


def main():
    rows = {r['id']: r for r in json.load(open('artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    orig = json.load(open(R + 'original_judgments_hidden.json')); new = {}
    for f in glob.glob(R + 'responses/batch0*.json'):
        for r in json.load(open(f))['responses']: new[r['id']] = r['judgment']
    off = lambda i: rows[i.split('/point-review/')[0]]['bad'] or rows[i.split('/point-review/')[0]]['center_out']
    out = {}
    for name, want in (('on_card', False), ('off_card', True)):
        p = [(orig[i], new[i]) for i in orig if bool(off(i)) == want]; s = stats(p)
        if name == 'on_card': s.update(boot(p))
        s['confusion'] = {f'{a}->{b}': c for (a, b), c in sorted(Counter(p).items())}; out[name] = s
    json.dump(out, open(R + 'results_on_card_subset.json', 'w'), indent=1); print(json.dumps(out))


if __name__ == '__main__':
    main()
