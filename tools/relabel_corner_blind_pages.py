"""Blind corner-zone re-judgment pages (measures label flip rate f). 60 zones from the 946 corner zones: 30 labelled defect + 30 labelled normal, distinct photo groups, seeded, model scores never used. Pages show the crop with the zone outlined only; mapping stays in selection.json. INSTRUCTIONS follows the canonical 후면 모서리 결함 수준 (LABELING_PROTOCOL.md) for pages made from 2026-11-25; the 2026-11-21 re-judgment used the earlier wording (d1e2197)."""
import json
import random
import sys
from pathlib import Path

from tools import relabel_zone_pages as zp

SEED, PER_CLASS, PER_PAGE = 20261121, 30, 20
INSTRUCTIONS = ('<p><b>모서리</b>: 카드 네 귀퉁이의 둥근 끝을 봅니다. 뭉개짐·찍힘·백화·접힘이 확대해서 보이면 크기와 관계없이 <b>결함</b>이고 mm 크기 문턱은 두지 않습니다. 충분히 확인했는데 없으면 <b>정상</b>입니다. '
                '근처 직선 테두리만의 마모·백화나 면 안쪽 기스·오염, 카드 밖 배경은 이 항목이 아닙니다. 확대해도 반사인지 마모인지 구분되지 않으면 추정하지 말고 <b>판단 불가</b>입니다(가림·흐림으로 구분이 안 될 때도 같습니다).</p>')


def select(rows):
    """30 defect + 30 normal zones from distinct groups, deterministic, no score used; shuffled."""
    rng, chosen, used = random.Random(SEED), [], set()
    for target in (1, 0):
        pool = sorted((r for r in rows if r['target'] == target), key=lambda r: r['id'])
        rng.shuffle(pool)
        got = []
        for r in pool:
            if r['group'] not in used and len(got) < PER_CLASS:
                used.add(r['group'])
                got.append(r)
        chosen += got
    rng.shuffle(chosen)
    return chosen


def page(n, total, start, zones):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>모서리 재판정 {n}/{total}</title><style>{zp.STYLE}</style><h1>모서리 재판정 {n}/{total}</h1>' + INSTRUCTIONS +
            '<p>이전 판정·모델 점수는 보이지 않습니다. 파란 사각형 안 구역만 판정하세요. 확신이 없으면 판단 불가로 두세요. 자동 저장하지 않으며 결과를 채팅에 붙여넣어야 반영됩니다.</p>'
            + ''.join(zp.article(start + k, z) for k, z in enumerate(zones)) +
            f'<h2>결과</h2><button id="copy">결과 복사</button><p id="msg"></p><textarea id="out" readonly></textarea><script>{zp.SCRIPT}</script></html>')


def main(rows_path, out):
    chosen, out = select(json.loads(Path(rows_path).read_text())), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'selection.json').write_text(json.dumps([dict(n=i, **z) for i, z in enumerate(chosen, 1)], ensure_ascii=False))
    for n in range(3):
        (out/f'zones-{n + 1}.html').write_text(page(n + 1, 3, n*PER_PAGE + 1, chosen[n*PER_PAGE:(n + 1)*PER_PAGE]))
    print(len(chosen), 'zones ->', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
