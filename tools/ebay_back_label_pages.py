"""Phone label pages for the new eBay independent sample. Per back photo the human answers 제한 / 정상 / 자격아님 / 모름.
Writes no labels; the pasted answer text is the human record. AI only chose which photo to show (back_index), never a verdict.
Order is a seeded shuffle so source batch / AI verdict are not visible to the labeler. 'manifest' keeps the source of each id."""
import html
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE, encode  # noqa: E402

WORDS = ('제한', '정상', '자격아님', '모름')
CHUNK = 12
GUIDE = ('<p>뒷면 사진 전체에서 <b>관찰 제한</b>(빛반사·흐림·가림·잘림·저해상도·심한 각도·그림자로 카드 상태를 볼 수 없음)이면 <b>제한</b>, '
         '문제없이 볼 수 있으면 <b>정상</b>. 카드 한 장의 뒷면이 아니거나 네 변이 사진에 다 보이지 않으면 <b>자격아님</b>. 판단이 안 서면 <b>모름</b>.</p>')
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>a.dataset.id+'='+a.dataset.s).join('\\n')}
arts.forEach(a=>{a.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{a.dataset.s=b.dataset.v;a.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));show()}))});show();"""


def article(ident, path, index):
    buttons = ''.join(f'<button data-v="{w}">{w}</button>' for w in WORDS)
    return (f'<article data-id="{html.escape(ident)}" data-s="미확인"><h2>{html.escape(ident[-6:])} · 사진 {index + 1}번</h2>'
            f'<img src="data:image/jpeg;base64,{encode(path, 520)}"><div class="row">{buttons}</div></article>')


def candidates(screen_dir, check_dir):
    """(id -> (source, back_index)). Sources: human_ok (human said 맞음), ai_fit_unchecked (AI 적합, not human-checked), new_batch (back_index only)."""
    merged = {i['id']: i for i in json.loads((screen_dir / 'merged.json').read_text(encoding='utf-8'))['items']}
    manifest = json.loads((check_dir / 'manifest.json').read_text(encoding='utf-8'))
    answers = {}
    for path in sorted(check_dir.glob('answers-*.txt')):
        answers.update(line.strip().split('=') for line in path.read_text(encoding='utf-8').splitlines() if '=' in line)
    chosen = {}
    for ident, item in merged.items():
        if ident in answers:
            if answers[ident] == 'ok' and item['back_index'] is not None:
                chosen[ident] = ('human_ok', item['back_index'])
        elif item['verdict'] == '적합' and item['back_index'] is not None:
            chosen[ident] = ('ai_fit_unchecked', item['back_index'])
    for batch in 'hijk':
        for item in json.loads((screen_dir / f'{batch}-back.json').read_text(encoding='utf-8'))['items']:
            if item['back_index'] is not None:
                chosen[item['id']] = ('new_batch', item['back_index'])
    return chosen, manifest


def main(root, out_dir, seed=20261119):
    root, out_dir = Path(root), Path(out_dir)
    chosen, _ = candidates(root / 'artifacts/ebay-independent-20261119-screen', root / 'artifacts/ebay-independent-20261119-check')
    catalog = {}
    for path in sorted((root / 'artifacts').glob('ebay-independent-20261119-[a-k]/catalog.json')):
        catalog.update({i['id']: i for i in json.loads(path.read_text(encoding='utf-8'))['items']})
    ids = sorted(chosen)
    random.Random(seed).shuffle(ids)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = [ids[k:k + CHUNK] for k in range(0, len(ids), CHUNK)]
    for number, group in enumerate(pages, 1):
        body = (GUIDE + f'<p><b>{number}/{len(pages)}쪽</b></p>'
                + ''.join(article(i, catalog[i]['photos'][chosen[i][1]]['path'], chosen[i][1]) for i in group)
                + '<textarea id="out" readonly></textarea>')
        (out_dir / f'label-{number}.html').write_text(
            f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    (out_dir / 'label-manifest.json').write_text(json.dumps(dict(seed=seed, chunk=CHUNK, pages=[[(i, chosen[i][0], chosen[i][1]) for i in g] for g in pages]),
                                                            ensure_ascii=False, indent=1), encoding='utf-8')
    return len(ids), len(pages)


if __name__ == '__main__':
    print(main(*sys.argv[1:3]))
