"""D3 하위군 분모 공개(건수만). 같은 D2 시험 실물을 D1 봉인 메타(촬영 해상도·eBay 검색어 프록시)에 붙여 양성/정상 실물 수를 센다.
언어·판본 라벨은 없어 미지원이다. 비율·성능은 계산하지 않는다."""
SET_QUERIES = ('expedition', 'legendary collection', 'evolutions', 'hidden fates', 'base set 2')


def bucket(back_size):
    short = min(back_size)
    return '<1000' if short < 1000 else '1000-1499' if short < 1500 else '>=1500'


def query_group(query):
    return 'set' if any(name in query for name in SET_QUERIES) else 'character'


def tally(objects, meta):
    """objects: {group: is_positive}. Returns counts per bucket/query_group plus unmatched objects (no D1 metadata)."""
    empty = lambda: dict(positive=0, normal=0)
    out = dict(bucket={}, query_group={}, unmatched=empty())
    for group, positive in objects.items():
        key = 'positive' if positive else 'normal'
        if group not in meta:
            out['unmatched'][key] += 1
            continue
        for kind, name in (('bucket', bucket(meta[group]['back_size'])), ('query_group', query_group(meta[group]['query']))):
            out[kind].setdefault(name, empty())[key] += 1
    return out
