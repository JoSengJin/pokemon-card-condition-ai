"""Step-0 reproducibility pilot: a second labeler re-judges a seeded subset of the 221 usable back labels.
Pages hide source, AI verdict and the first labeler's answer. Scoring reads two answer maps; it never writes labels."""
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebay_back_label_pages as base  # noqa: E402

SEED, PER_CLASS, CHUNK, ORDER_SEED = 20261120, 20, 10, 20261121
CLASSES = ('정상', '제한')


def draw(answers, seed=SEED, per_class=PER_CLASS):
    """Seeded stratified draw over usable (정상/제한) first labels; order is reshuffled with ORDER_SEED."""
    rng, ids = random.Random(seed), []
    for word in CLASSES:
        pool = sorted(i for i, v in answers.items() if v == word)
        if len(pool) < per_class:
            raise ValueError(f'{word}: {len(pool)} < {per_class}')
        ids += rng.sample(pool, per_class)
    random.Random(ORDER_SEED).shuffle(ids)
    return ids


def kappa(pairs):
    """Cohen's kappa over (a, b) pairs of 정상/제한; None when chance agreement is 1."""
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in CLASSES)
    return None if pe == 1 else (po - pe) / (1 - pe)


def score(first, second, boots=2000, seed=SEED):
    """Pairs with both usable answers feed kappa; 모름/자격아님/미확인 from either side are counted separately."""
    ids = sorted(set(first) & set(second))
    pairs = [(first[i], second[i]) for i in ids if first[i] in CLASSES and second[i] in CLASSES]
    rng, draws = random.Random(seed), []
    for _ in range(boots):
        k = kappa([rng.choice(pairs) for _ in pairs])
        if k is not None:
            draws.append(k)
    draws.sort()
    lo, hi = (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]) if draws else (None, None)
    miss = [i for i in ids if second[i] not in CLASSES]
    return dict(n=len(ids), used=len(pairs), unusable=len(miss), agree=sum(a == b for a, b in pairs),
                kappa=kappa(pairs) if pairs else None, kappa_ci=[lo, hi],
                first_limit_second_normal=sum(a == '제한' and b == '정상' for a, b in pairs),
                first_normal_second_limit=sum(a == '정상' and b == '제한' for a, b in pairs))


def build(root, answers_path, out_dir):
    root, out_dir = Path(root), Path(out_dir)
    answers = json.loads(Path(answers_path).read_text(encoding='utf-8'))
    chosen, _ = base.candidates(root / 'artifacts/ebay-independent-20261119-screen', root / 'artifacts/ebay-independent-20261119-check')
    catalog = {}
    for path in sorted((root / 'artifacts').glob('ebay-independent-20261119-[a-k]/catalog.json')):
        catalog.update({i['id']: i for i in json.loads(path.read_text(encoding='utf-8'))['items']})
    ids = draw(answers)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = [ids[k:k + CHUNK] for k in range(0, len(ids), CHUNK)]
    for number, group in enumerate(pages, 1):
        body = (base.GUIDE + f'<p><b>{number}/{len(pages)}쪽</b></p>'
                + ''.join(base.article(i, catalog[i]['photos'][chosen[i][1]]['path'], chosen[i][1]) for i in group)
                + '<textarea id="out" readonly></textarea>')
        (out_dir / f'retest-{number}.html').write_text(
            f'<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><style>{base.STYLE}</style>{body}<script>{base.SCRIPT}</script>', encoding='utf-8')
    (out_dir / 'retest-manifest.json').write_text(json.dumps(dict(seed=SEED, order_seed=ORDER_SEED, per_class=PER_CLASS, pages=pages), ensure_ascii=False, indent=1), encoding='utf-8')
    return len(ids), len(pages)


if __name__ == '__main__':
    if sys.argv[1] == 'score':
        first = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        second = dict(line.strip().split('=') for line in Path(sys.argv[3]).read_text(encoding='utf-8').splitlines() if '=' in line)
        print(json.dumps(score(first, second), ensure_ascii=False, indent=1))
    else:
        print(build('.', sys.argv[2], sys.argv[3]))
