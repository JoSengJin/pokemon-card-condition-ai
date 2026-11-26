# 판정 일관성 확인 사전 등록 (2026-11-24 작성, Claude, 선정 결과 전 고정)

**결론: 설계 `cohort2-judge-consistency-design-20261124.md`(커밋 `f644bba`)를 사용자가 승인했다(2026-11-24, 이 세션 채팅 "설계 승인"). 그 §3 표본, §4 절차, §5 지표·판정 규칙, §6 다음 단계를 수치 그대로 고정하며 커밋 뒤 바꾸지 않는다.** 화면을 여는 것과 판정 요청은 별도 승인이다. 점수·추론·학습·외부 호출 0, 봉인 파일·1단계 응답·라벨 수정 0, push 0.

## 구현 세부 (설계에서 정하지 않은 것)
- 시드 `20261125`. 난수 순서는 부록 A 스크립트 그대로다: 화면 1의 정상·눈가림 결함·기준점, 화면 2~5 정상(12·12·13·13), 화면 2~5 눈가림 결함 10·기준점 4, 묶음 안 섞기, 새 화면 A2·B2 순으로 배치(같은 카드 10칸 이상은 1단계 `select.py`의 `spread` 재사용). 입력은 1단계 `mapping.json`뿐이며 응답을 읽지 않는다.
- 새 화면마다 원래 화면 1 구역 32(정상 25·눈가림 결함 5·기준점 2), 화면 2~5 구역 32(같은 구성). 번호 z2001~z2128.
- 첫 회차 값은 `artifacts/cohort2-label-check-20261124/responses/input-1~5.txt`(부록 C의 SHA256으로 확인, 화면 1 문서 `cohort2-normal-label-check-prereg-20261124.md`).
- Fisher·McNemar는 양측 정확 검정, 구간은 양측 95% Wilson(반올림하지 않은 값). 주 2의 p는 변경 장수(b, c)로 `min(1, 2·P[Bin(b+c,0.5) ≤ min(b,c)])`, 변경 0이면 1.
- 미측정은 설계 §5 그대로(주 1 판정 가능 30 미만, 주 2 공통 25 미만; 어느 하나라도 해당하면 판정은 "미측정"이다).
- 판정 주체·제출 줄 확인은 설계 §4 그대로이고 기준은 1단계와 같다(문장 없으면 "미확인"으로 기록하고 한 줄 확인).

## 부록 A. 선정 스크립트 전문 (SHA256 `956d3b6a05479a2dcfc04f9ff0b05e29c7377177de3077a457977051306537e4`)
```python
"""Retest sample for judge consistency. Reads only the stage-1 mapping (no answers, no scores).
Run from repo root: .venv/bin/python artifacts/cohort2-retest-20261125/select.py"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != HERE]  # select.py would shadow stdlib select
import hashlib, importlib.util, json, random
from pathlib import Path

SEED = 20261125
S1 = Path('artifacts/cohort2-label-check-20261124')
MAP_SHA = '9adc30d5866b127f1b5dea7afca2d6828bf1c0f8d583c301848816ea5d3c6228'
SEL_SHA = '2d07e3c5af188e348d54d43c5a35d833490ed8a4d154e74a0ec0de7bf125d9d9'
NORMAL_PER_SCREEN = {'2': 12, '3': 12, '4': 13, '5': 13}
REST = {'defect_mix': 10, 'anchor': 4}


def stage1_select():
    """The committed stage-1 select.py as a module (its main() is guarded)."""
    if hashlib.sha256((S1 / 'select.py').read_bytes()).hexdigest() != SEL_SHA:
        raise ValueError('stage-1 select.py changed')
    spec = importlib.util.spec_from_file_location('stage1_select', S1 / 'select.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def draw(mapping, rng, n, keep):
    pool = sorted((z for z, m in mapping.items() if keep(m)), key=lambda z: int(z[1:]))
    rng.shuffle(pool)
    assert len(pool) >= n, (len(pool), n)
    return pool[:n]


def sample(mapping, rng):
    """{(origin, stratum): zone ids}"""
    out = {('s1', st): draw(mapping, rng, n, lambda m: m['screen'] == '1' and m['stratum'] == st)
           for st, n in (('normal', 50), *REST.items())}
    out[('rest', 'normal')] = [z for s, n in NORMAL_PER_SCREEN.items()
                               for z in draw(mapping, rng, n, lambda m: m['screen'] == s and m['stratum'] == 'normal')]
    for st, n in REST.items():
        out[('rest', st)] = draw(mapping, rng, n, lambda m: m['screen'] != '1' and m['stratum'] == st)
    for ids in out.values():
        rng.shuffle(ids)
    return out


def main():
    mod, rng = stage1_select(), random.Random(SEED)
    raw = (S1 / 'mapping.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MAP_SHA:
        raise ValueError('stage-1 mapping changed')
    mapping = json.loads(raw)
    groups = sample(mapping, rng)
    rows, n = [], 2000
    for half, screen in enumerate(('A2', 'B2')):
        items = [dict(card=mapping[z]['card'], zone=z, origin=o) for (o, st), ids in groups.items()
                 for z in (ids[:len(ids) // 2] if half == 0 else ids[len(ids) // 2:])]
        for it in mod.spread(items, rng):
            n += 1; rows.append(dict(n=n, screen=screen, old=it['zone'], origin=it['origin']))
    assert len(rows) == 128 and len({r['old'] for r in rows}) == 128
    Path(HERE, 'selection.json').write_text(json.dumps(dict(seed=SEED, mapping_sha256=MAP_SHA, zones=rows), ensure_ascii=False, indent=1))
    print('selection sha256', hashlib.sha256(Path(HERE, 'selection.json').read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
```

## 부록 B. 실행 기록 (커밋 `b8db577` 뒤 추가, 규칙·수치 변경 없음)
선정 2회·화면/대응표 2회의 SHA가 각각 같다. 새 화면의 크롭은 1단계 화면의 같은 구역 크롭과 바이트가 같다. 첫 회차 입력은 다섯 파일을 이어 붙인 SHA256으로 확인한다(`analyze_retest.py`의 `OLD_SHA`).
```text
abfb4af8895d9fc7831d72879b6d7cc4294d28156be3d537563bcd801e7e634e  analyze_retest.py
fa12b1ac6342310ab4252b60b98d3fe5f0d3b4a511037bce046276615ff78d31  build.py
47f2b88d6c8f06c36d1ffc44574e7df8f645c3f9c22b5b773314c06d9d661da5  check_screens.py
956d3b6a05479a2dcfc04f9ff0b05e29c7377177de3077a457977051306537e4  select.py
ac29e5f47b8f5c7871007a5d04bea4085f0d01ceb995b6a071fd47401473b2d8  test_analyze_retest.py
0ebace22fde11f0546ab6d821aa12cab8b78840afbf582a62ed4e672d833e541  pure.js
5eaf4b564bec3bd36d6ba3f2cc919b4a0da69e3c7e1a1d34c351a42662e5895a  test_screen.js
8bb29350420d15bf9e9b91900e2774a7464dca25bd5f22ecc1a4d8746650aec5  mapping.json
72967ba828a5a04ec7b456e8d696dd6e7049f2408952d02c6c9d78895510b02c  selection.json
496d8e4aa696ce95a63d064e246233e859d1ca35c6a287806566a36bf6b7fc26  screen-A2.html
5db568f1eb10482b93ed975a0f43984b8b349a33b212f742d0c10ee7aa8256ec  screen-B2.html
```

## 부록 C. 판정 시각 예외 (새 답을 받기 전 커밋)
- 설계 §4의 "24시간 이상 뒤"를 **2026-11-25 05:00(KST) 이후**로 바꾼다. 사용자 지시(2026-11-24, 이 세션 채팅 "25일 05시로 하고"). 마지막 1단계 응답 도착(11-24 07:35)에서 약 21시간 25분이다.
- 표본·지표·p값·최소 구역·판정 규칙은 그대로다. 24시간 미만이므로 판정 1을 보고할 때 기억 효과를 배제하지 못함을 적는다(원래 설계에서도 배제하지 못한다).
- 사용자 요청으로 화면 파일의 위치를 미리 알린다. 판정은 위 시각 이후에 한다.
