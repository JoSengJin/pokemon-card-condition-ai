"""Phone pages: why was this back photo judged '제한'? Asks only the reason(s) and extent for photos the human already labeled 제한 (the label itself is not re-asked).
Set = restricted photos missed by both candidate F and top-k (score < 0.5 in both) + an equal-size seeded sample of restricted photos both caught.
Blind: no model score, no group membership, seeded shuffle. Group membership is written only to manifest.json (not shown). Pasted text is the human record."""
import html
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE, encode  # noqa: E402

REASONS = ('빛반사', '흐림', '가림', '잘림', '저해상도', '심한각도', '그림자', '기타', '모름')
EXTENT = ('일부', '대부분', '모름')
PER_PAGE = 7
SEED = 20261120
GUIDE = ('<p>아래 사진은 모두 이미 <b>제한</b>으로 판정한 뒷면 사진입니다. 판정은 바꾸지 않고, <b>무엇 때문에 카드 상태를 볼 수 없었는지</b>만 고릅니다. '
         '이유는 여러 개 고를 수 있고(다시 누르면 해제), 그 문제가 카드의 <b>일부</b>인지 <b>대부분</b>인지 하나 고릅니다. 기억나지 않거나 안 보이면 <b>모름</b>.</p>')
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>a.dataset.id+'='+([...a.querySelectorAll('.r button.on')].map(b=>b.dataset.v).join('+')||'미확인')+'|'+(a.dataset.e||'미확인')).join('\\n')}
arts.forEach(a=>{a.querySelectorAll('.r button').forEach(b=>b.addEventListener('click',()=>{b.classList.toggle('on');show()}));
a.querySelectorAll('.e button').forEach(b=>b.addEventListener('click',()=>{a.dataset.e=b.dataset.v;a.querySelectorAll('.e button').forEach(x=>x.classList.toggle('on',x===b));show()}))});show();"""
EXTRA = '.r{flex-wrap:wrap}.r button{flex:1 0 30%}'


def select(rows, f_scores, k_scores, seed=SEED):
    missed = [r['group'] for r, f, k in zip(rows, f_scores, k_scores) if r['target'] == 1 and f < .5 and k < .5]
    caught = sorted(r['group'] for r, f, k in zip(rows, f_scores, k_scores) if r['target'] == 1 and f >= .5 and k >= .5)
    if len(caught) < len(missed):
        raise ValueError('Not enough caught restricted photos for a matched comparison')
    rng = random.Random(seed)
    comparison = rng.sample(caught, len(missed))
    order = sorted(missed) + sorted(comparison)
    rng.shuffle(order)
    return order, {g: ('missed' if g in missed else 'caught') for g in order}


def article(group, image):
    reasons = ''.join(f'<button data-v="{w}">{w}</button>' for w in REASONS)
    extent = ''.join(f'<button data-v="{w}">{w}</button>' for w in EXTENT)
    return (f'<article data-id="{html.escape(group)}"><h2>{html.escape(group[-6:])}</h2><img src="data:image/jpeg;base64,{encode(image, 520)}">'
            f'<div class="row r">{reasons}</div><div class="row e">{extent}</div></article>')


def main(root, out_dir):
    root, out_dir = Path(root), Path(out_dir)
    exp = root/'artifacts/experiments'
    f = json.loads((exp/'20261119T150351-39395830/observations.json').read_text())
    k = json.loads((exp/'20261119T151512-f229d500/observations.json').read_text())
    if [r['id'] for r in f['rows']] != [r['id'] for r in k['rows']]:
        raise ValueError('Row order differs between F and top-k observations')
    order, membership = select(f['rows'], f['scores'], k['scores'])
    image = {r['group']: r['image'] for r in f['rows']}
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = [order[i:i + PER_PAGE] for i in range(0, len(order), PER_PAGE)]
    for n, group in enumerate(pages, 1):
        body = GUIDE + f'<p><b>{n}/{len(pages)}쪽</b></p>' + ''.join(article(g, image[g]) for g in group) + '<textarea id="out" readonly></textarea>'
        (out_dir/f'reason-{n}.html').write_text(
            f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}{EXTRA}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    (out_dir/'manifest.json').write_text(json.dumps(dict(seed=SEED, per_page=PER_PAGE, membership=membership, pages=pages,
                                                         sources=['20261119T150351-39395830', '20261119T151512-f229d500']), ensure_ascii=False, indent=1), encoding='utf-8')
    return len(order), len(pages)


if __name__ == '__main__':
    print(main(*sys.argv[1:3]))
