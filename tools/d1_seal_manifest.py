"""D1 sealed test-set manifest: per-cell counts, photo/label/group SHA, use history, subtype/shooting-condition table. Writes no labels, trains nothing."""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

INTAKES = 'ax az ba bb bc bd'.split()
CELLS = ('edge', 'corner', 'surface', 'observation_limit', 'centering')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def corner_surface(path, normal_count):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            states = re.findall(r';[a-z_]+:(정상|결함|미확인)', line)
            out[line.split('/back=')[0]] = '결함' if '결함' in states else '정상' if states.count('정상') == normal_count else '제외'
    return out


def simple(path, sep):
    return {line.split(sep)[0]: line.strip().split('=')[1] for line in Path(path).read_text(encoding='utf-8').splitlines() if sep in line}


def edge_labels(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            ident, value = line.strip().split('=')
            box, label = value.split(',')
            out[ident] = label if box == '맞음' and label in ('정상', '결함') else '제외'
    return out


def main(root='artifacts', out_dir='artifacts/d1-testset-20261103'):
    labels = Path(root) / 'd1-labels-20261103'
    tables = dict(
        edge=edge_labels(labels / 'edge-answers.txt'), corner=corner_surface(labels / 'cor-answers.txt', 4),
        surface=corner_surface(labels / 'sur-answers.txt', 9),
        observation_limit={k: {'제한': '결함'}.get(v, v) for k, v in simple(labels / 'obs-answers.txt', '/back=').items()},
        centering={k: v for k, v in simple(labels / 'cen-answers.txt', '/front=').items()})
    cards = []
    for k in INTAKES:
        for line in (Path(root) / f'ebay-intake-20261103-{k}/review/labels-review.jsonl').read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            source = json.loads((Path(row['front']).parent / 'source.json').read_text(encoding='utf-8'))
            photos = {Path(p['path']).name: p for p in source['photos']}
            cards.append(dict(id=row['id'], group=row['group'], intake=k, query=source.get('query'), title=source.get('title'),
                              front_sha256=photos[Path(row['front']).name]['sha256'], back_sha256=photos[Path(row['back']).name]['sha256'],
                              front_size=photos[Path(row['front']).name]['size'], back_size=photos[Path(row['back']).name]['size'],
                              labels={c: tables[c].get(row['id'], '제외') for c in CELLS}))
    counts = {c: dict(collections.Counter(x['labels'][c] for x in cards)) for c in CELLS}
    by_query = collections.defaultdict(lambda: collections.Counter())
    for x in cards:
        for c in CELLS:
            by_query[x['query']][f"{c}:{x['labels'][c]}"] += 1
    shoot = collections.Counter(f"back_short_side<{b}" for x in cards for b in [min(x['back_size'])] and [(1000 if min(x['back_size']) < 1000 else 1500 if min(x['back_size']) < 1500 else 99999)])
    files = {n: sha(labels / n) for n in ('edge-answers.txt', 'cor-answers.txt', 'sur-answers.txt', 'obs-answers.txt', 'cen-answers.txt')}
    manifest = dict(
        version='d1-testset-20261103', cells=counts, n_cards=len(cards),
        meaning=dict(edge='box 맞음 + 결함/정상만 (불가·미확인·잘림 제외)', corner='4칸 중 결함 있으면 결함, 4칸 모두 정상이면 정상, 그 외 제외',
                     surface='9칸 중 결함 있으면 결함, 9칸 모두 정상이면 정상, 그 외 제외', observation_limit='제한=양성, 정상, 미확인 제외',
                     centering='앞면 결함/정상, 미확인 제외'),
        label_file_sha256=files, group_sha256=hashlib.sha256('\n'.join(sorted({x['group'] for x in cards})).encode()).hexdigest(),
        photo_sha256_all=hashlib.sha256('\n'.join(sorted(x['front_sha256'] + x['back_sha256'] for x in cards)).encode()).hexdigest(),
        use_history=dict(training=False, tuning=False, model_selection=False, threshold=False, prefill_predictions=False,
                         note='사람 라벨러(J)가 라벨 페이지에서 한 번 본 것 외 사용 없음. 봉인 후 개발·선택·임계·원인 분석 금지, 한 번 평가한 후보에 재사용 금지.'),
        subtype_table_by_search_query={q: dict(c) for q, c in by_query.items()}, shooting_condition_table_back_short_side_px=dict(shoot),
        limits=['세부유형은 카드 종류 라벨이 아니라 eBay 검색어(시대 프록시)로만 구분한다. 카드 종류·희귀도 라벨은 없다.',
                '라벨러 한 명, 같은 eBay 계열이라 일반화 한계가 있다.', '변조는 코드로 막지 못하고 SHA와 커밋으로 감지한다.',
                '표면 결함 카드 수가 기준 30에 근접한다(칸 수는 counts 참고).', '센터링 칸은 C4 미충족이라 후보 없음으로 보고한다.'],
        cards=cards)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir, 'SEALED.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return counts, manifest['group_sha256'], manifest['photo_sha256_all']


if __name__ == '__main__':
    print(json.dumps(main(*sys.argv[1:3]), ensure_ascii=False, indent=1))
