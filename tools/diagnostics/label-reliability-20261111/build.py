"""재판정 40곳(결함15/정상15/판단불가10) 5곳 단위 크롭 전용 페이지. 이전 답은 표시하지 않음. 학습·추론 0."""
import json
import random
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/diagnostics/mobile-point-review-20261110'))
from review import digest
from ten import render_ten
OUT = ROOT / 'artifacts/label-reliability-20261111'
QUOTA = {'defect': 15, 'normal': 15, 'unknown': 10}


def pick(packet):
    ans = {a['id']: a['judgment'] for a in json.load(open(ROOT / 'artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json'))['responses']}
    idx = {e['id']: i for i, e in enumerate(packet['entries'])}; rng = random.Random(20261111); chosen = []
    for j, n in QUOTA.items():
        pool = sorted(i for i, v in ans.items() if v == j); rng.shuffle(pool); chosen += pool[:n]
    rng.shuffle(chosen); return chosen, ans, idx


def main():
    packet = json.load(open(ROOT / 'artifacts/mobile-point-review-20261110/packet.json'))
    assert packet['packet_id'] == digest(packet)
    chosen, ans, idx = pick(packet); sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(); files = []
    for k in range(0, 40, 5):
        name = f'retest-{k // 5 + 1:02d}.html'; (OUT / name).unlink(missing_ok=True)
        render_ten(packet, [idx[i] for i in chosen[k:k + 5]], OUT, name, sha)
        page = (OUT / name).read_text()
        page = re.sub(r'<details class="original-context".*?</details>', '', page, flags=re.S)
        page = re.sub(r'<p><a href="#photo-\d+">.*?</a></p>', '', page)
        (OUT / name).write_text(page); files.append(dict(file=name, ids=chosen[k:k + 5], bytes=len(page.encode())))
    (OUT / 'original_judgments_hidden.json').write_text(json.dumps({i: ans[i] for i in chosen}))
    (OUT / 'manifest.json').write_text(json.dumps(dict(packet_id=packet['packet_id'], files=files, source_sha=sha, responses=0), indent=1))
    print([(f['file'], f['bytes'] // 1024) for f in files])


if __name__ == '__main__':
    main()
