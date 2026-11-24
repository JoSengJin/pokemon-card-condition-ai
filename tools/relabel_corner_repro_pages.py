"""Reproducibility gate for the current (strict) corner criterion: 60 corner zones never re-judged before (30 labelled defect + 30 normal, distinct photo groups, seeded, no model score), high-resolution crops, judged twice on different days in a different order. Ids r1..r60 stay fixed across rounds; the mapping stays in selection-repro.json."""
import json
import random
import sys
from pathlib import Path

from tools import relabel_corner_highres_pages as hi
from tools import relabel_zone_pages as zp

SEED, PER_CLASS, PER_PAGE = 20261122, 30, 20
INSTRUCTIONS = ('<p><b>모서리(현행 기준)</b>: 카드 네 귀퉁이의 둥근 끝을 <b>확대해서</b> 봅니다. 뭉개짐·찍힘·백화·접힘은 '
                '확대해서 보이면 <b>크기와 관계없이 결함</b>이며, 확대해야 보이는 <b>미세한 백화</b>도 결함입니다. 충분히 확인했는데 없으면 정상입니다. '
                '근처 직선 테두리만의 마모·백화, 면 안쪽 기스·오염, 카드 밖 배경은 이 항목이 아닙니다. 확대해도 반사·인쇄와 구분되지 않거나 가림·흐림·잘림이면 판단 불가입니다.</p>')


def select(rows, exclude_groups):
    rng, chosen, used = random.Random(SEED), [], set(exclude_groups)
    for target in (1, 0):
        pool = sorted((r for r in rows if r['target'] == target), key=lambda r: r['id'])
        rng.shuffle(pool)
        got = []
        for r in pool:
            if r['group'] not in used and len(got) < PER_CLASS:
                used.add(r['group'])
                got.append(r)
        chosen += got
    return [dict(n=i, **z) for i, z in enumerate(chosen, 1)]


def page(round_no, n, total, zones):
    zp.crop = hi.crop
    arts = ''.join(zp.article(z['n'], z).replace(f'data-id="z{z["n"]}"', f'data-id="r{z["n"]}"').replace(f'구역 {z["n"]}<', f'구역 r{z["n"]}<') for z in zones)
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>모서리 재현성 {round_no}차 {n}/{total}</title><style>{zp.STYLE}</style><h1>모서리 재현성 {round_no}차 {n}/{total}</h1>' + INSTRUCTIONS +
            '<p>이전 판정·모델 점수는 보이지 않습니다. 사진을 두 손가락으로 확대해 파란 사각형 안 구역만 판정하세요. 자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + arts + f'<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea><script>{zp.SCRIPT}</script></html>')


def main(rows_path, previous_selection, out, round_no):
    out, round_no = Path(out), int(round_no)
    path = out/'selection-repro.json'
    if round_no == 1:
        done = {z['group'] for z in json.loads(Path(previous_selection).read_text())}
        path.write_text(json.dumps(select(json.loads(Path(rows_path).read_text()), done), ensure_ascii=False))
    chosen = json.loads(path.read_text())
    order = sorted(chosen, key=lambda z: z['n'])
    random.Random(SEED*10 + round_no).shuffle(order)
    pages = [order[i:i + PER_PAGE] for i in range(0, len(order), PER_PAGE)]
    for n, zones in enumerate(pages, 1):
        (out/f'repro{round_no}-{n}.html').write_text(page(round_no, n, len(pages), zones))
    print(len(order), 'zones round', round_no)


if __name__ == '__main__':
    main(*sys.argv[1:5])
