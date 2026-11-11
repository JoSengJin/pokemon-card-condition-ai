"""카드 위 정상↔결함 불일치 8곳을 이전/이번 답과 함께 보는 검토 화면(읽기 전용, 라벨 변경 0)."""
import glob
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/diagnostics/mobile-point-review-20261110'))
from ten import render_ten
R = ROOT / 'artifacts/label-reliability-20261111'
KO = {'defect': '결함 있음', 'normal': '결함 없음', 'unknown': '판단 불가'}


def form(i):
    n = re.sub(r'\W', '_', i)
    radios = ''.join(f'<label><input type="radio" name="{n}" value="{v}"> {t}</label> ' for v, t in KO.items())
    return f'<div class="fb" data-id="{i}"><p>이 점선 안의 최종 판단: {radios}</p><textarea rows="2" style="width:100%" placeholder="이유·경계 기준 (예: 화이트닝 점은 결함)"></textarea></div>'


SCRIPT = '''<section><h2>전체 답 · 여기서 한 번만 복사</h2><p>이 칸을 길게 눌러 전체 선택 후 복사해 채팅에 붙여넣으세요.</p><textarea id="out" rows="12" style="width:100%" readonly></textarea></section><script>
function g(){var r=[];document.querySelectorAll('.fb').forEach(function(d){var c=d.querySelector('input:checked');r.push({id:d.dataset.id,final:c?c.value:null,note:d.querySelector('textarea').value})});document.getElementById('out').value=JSON.stringify({kind:'label_boundary_notes',responses:r},null,1)}
document.addEventListener('input',g);g();</script>'''


def main():
    rows = {r['id']: r for r in json.load(open(ROOT / 'artifacts/card-foreground-diagnostic-20261111/rows2.json'))}
    orig = json.load(open(R / 'original_judgments_hidden.json')); new = {}
    for f in glob.glob(str(R / 'responses/batch0*.json')):
        for r in json.load(open(f))['responses']: new[r['id']] = r['judgment']
    pick = [i for i in orig if {orig[i], new[i]} == {'defect', 'normal'}
            and not (rows[i.split('/point-review/')[0]]['bad'] or rows[i.split('/point-review/')[0]]['center_out'])]
    pick = sys.argv[1:] or pick
    packet = json.load(open(ROOT / 'artifacts/mobile-point-review-20261110/packet.json')); idx = {e['id']: k for k, e in enumerate(packet['entries'])}
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(); name = 'disagree-on-card.html' if len(sys.argv) < 2 else 'recheck-' + sys.argv[1].split('/')[-1] + '.html'
    (R / name).unlink(missing_ok=True); render_ten(packet, [idx[i] for i in pick], R, name, sha); page = (R / name).read_text(); k = iter(pick)
    page = re.sub(r'<details class="original-context".*?</details>', '', page, flags=re.S)
    page = re.sub(r'<p><a href="#photo-\d+">.*?</a></p>', '', page)
    page = re.sub(r'<h3>점선 안에.*?</article>', lambda m: (lambda i: f'<h3>이전: {KO[orig[i]]} → 이번: {KO[new[i]]}</h3>' + form(i) + '</article>')(next(k)), page, flags=re.S)
    page = re.sub(r'<section id="results">.*?</section>', '', page, flags=re.S); page = re.sub(r'<div class="dock">.*?</div>', '', page, flags=re.S)
    page = re.sub(r'<h1>.*?<form class="review">', '<h1>카드 위 불일치 8곳 · 이전 답 vs 이번 답</h1><p>점선 안만 봅니다. 답을 받는 화면이 아니며 라벨은 바뀌지 않습니다.</p><form class="review">', page, count=1, flags=re.S)
    page = page.replace('</form>', '</form>' + SCRIPT, 1)
    (R / name).write_text(page); print(len(pick), (R / name).stat().st_size // 1024, 'KB')


if __name__ == '__main__':
    main()
