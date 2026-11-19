"""Phone page: a human checks a sample of AI back-eligibility verdicts. Never writes labels or confirmations itself.
Sample = all AI '불확실' + items with unviewed photos + seeded 20% of '적합' and '부적합' (rest stay unchecked AI verdicts).
Answer line: '<id>=ok|no|?' where ok = single card back with all four edges in frame, no = not that, ? = cannot tell."""
import html
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mobile_visibility_label_pages import STYLE as BASE_STYLE, encode  # noqa: E402

CHOICES = (('ok', '맞음: 카드 한 장 뒷면, 네 변이 다 보임'), ('no', '아님'), ('?', '모르겠음'))
STYLE = BASE_STYLE + "label{display:block;border:1px solid #888;border-radius:8px;padding:10px;margin:6px 0;font-size:18px}input:checked+span{font-weight:700;color:#1e5aff}textarea{width:100%;height:220px;font-size:16px}"
CHUNK = 10
SCRIPT = """const arts=[...document.querySelectorAll('article')];
function show(){document.getElementById('out').value=arts.map(a=>{const c=a.querySelector('input:checked');return a.dataset.id+'='+(c?c.value:'미확인')}).join('\\n')}
arts.forEach(a=>a.querySelectorAll('input').forEach(i=>i.addEventListener('change',show)));show();"""


def pick(items, seed=20261119, rate=0.2):
    """Return (selected ids, reason by id). Forced: 불확실 and any note mentioning 미열람; others sampled by rate."""
    rng, chosen = random.Random(seed), {}
    for item in items:
        if item['verdict'] == '불확실':
            chosen[item['id']] = 'ai_uncertain'
        elif '미열람' in item.get('note', ''):
            chosen[item['id']] = 'partly_unviewed'
    for verdict in ('적합', '부적합'):
        pool = sorted(i['id'] for i in items if i['verdict'] == verdict and i['id'] not in chosen)
        for ident in rng.sample(pool, round(len(pool) * rate)):
            chosen[ident] = 'sample_' + verdict
    return chosen


def photo_path(catalog_items, item):
    photos = catalog_items[item['id']]['photos']
    index = item['back_index'] if item.get('back_index') is not None else 0
    return photos[index]['path'], index


def article(item, path, index, reason):
    boxes = ''.join(f'<label><input type="radio" name="{html.escape(item["id"])}" value="{v}" hidden><span>{html.escape(w)}</span></label>' for v, w in CHOICES)
    return (f'<article data-id="{html.escape(item["id"])}"><h3>{html.escape(item["id"][-6:])} · 사진 {index + 1}번</h3>'
            f'<img src="data:image/jpeg;base64,{encode(path, 520)}">{boxes}</article>')


def main(merged_json, catalog_glob_dir, out_html, out_manifest):
    items = json.loads(Path(merged_json).read_text(encoding='utf-8'))['items']
    catalog = {}
    for path in sorted(Path(catalog_glob_dir).glob('ebay-independent-20261119-*/catalog.json')):
        catalog.update({i['id']: i for i in json.loads(path.read_text(encoding='utf-8'))['items']})
    chosen = pick(items)
    selected = [i for i in items if i['id'] in chosen]
    guide = ('<p>AI가 고른 뒷면 사진입니다. <b>카드 한 장의 뒷면이고 네 변이 모두 사진 안에 보이면 맞음</b>, 아니면 아님, 판단이 어렵다면 모르겠음. '
             '빛반사·그림자·살짝 비스듬함은 맞음/아님에 영향을 주지 않습니다. 맨 아래 결과를 복사해 붙여 주세요.</p>')
    pages = [selected[k:k + CHUNK] for k in range(0, len(selected), CHUNK)]
    for number, group in enumerate(pages, 1):
        body = (guide + f'<p><b>{number}/{len(pages)}쪽</b></p>' + ''.join(article(i, *photo_path(catalog, i), chosen[i['id']]) for i in group)
                + '<textarea id="out" readonly></textarea>')
        name = Path(out_html).with_name(f'{Path(out_html).stem}-{number}.html')
        name.write_text(f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{STYLE}</style>{body}<script>{SCRIPT}</script>', encoding='utf-8')
    manifest = dict(seed=20261119, rate=0.2, total_items=len(items), selected=len(selected), reasons=chosen,
                    ai_verdict={i['id']: i['verdict'] for i in items})
    Path(out_manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return len(selected)


if __name__ == '__main__':
    print(main(*sys.argv[1:5]))
