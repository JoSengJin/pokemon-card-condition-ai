"""[2차 재현성] 카드 위 정상 30곳 순서 무작위 재판정 페이지(5곳 x 6). 이전 답 미표시, 크롭만. 학습·추론·라벨 변경 0."""
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/diagnostics/mobile-point-review-20261110'))
from ten import render_ten
OUT = ROOT / 'artifacts/normal-rejudge2-20261112'
CRIT = ('<p><b>확정 기준:</b> ① 긁힘·점·주변과 구분되는 색 차이가 한눈에 보이면 결함 ② 흰 기운이 보여도 확신이 없거나 점선 밖과 구분이 안 되면 판단 불가 '
        '③ 카드 밖이거나 판단할 표면이 없으면 판단 불가 ④ 정상은 충분히 보이는데 아무것도 없을 때만.</p>')


def main():
    ans = {a['id']: a['judgment'] for a in json.load(open(ROOT / 'artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json'))['responses']}
    mask = {r['id']: bool(r['bad'] or r['center_out']) for r in json.load(open(ROOT / 'artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    packet = json.load(open(ROOT / 'artifacts/mobile-point-review-20261110/packet.json')); idx = {e['id']: k for k, e in enumerate(packet['entries'])}
    import random; ids = sorted(i for i, v in ans.items() if v == 'normal' and not mask[i.split('/point-review/')[0]]); assert len(ids) == 30, len(ids); random.Random(20261112).shuffle(ids)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(); files = []
    for k in range(0, 30, 5):
        name = f're-{k // 5 + 1:02d}.html'; (OUT / name).unlink(missing_ok=True); render_ten(packet, [idx[i] for i in ids[k:k + 5]], OUT, name, sha)
        page = (OUT / name).read_text(); page = re.sub(r'<details class="original-context".*?</details>', '', page, flags=re.S)
        page = re.sub(r'<p><a href="#photo-\d+">.*?</a></p>', '', page).replace('<form class="review">', CRIT + '<form class="review">', 1)
        (OUT / name).write_text(page); files.append(dict(file=name, ids=ids[k:k + 5], bytes=len(page.encode())))
    (OUT / 'manifest.json').write_text(json.dumps(dict(packet_id=packet['packet_id'], files=files, source_sha=sha), indent=1))
    print([(f['file'], f['bytes'] // 1024) for f in files])


if __name__ == '__main__':
    main()
