# 봉인 468장 정상 라벨 점검 사전 등록 (2026-11-24, Claude, 선정 결과 전 고정)

**결론: 봉인 코호트의 정상 206장을 새 기준(확대해서 보이면 결함)으로 다시 볼 순서·눈가림·지표·계속 규칙을 선정 실행 전에 고정한다. 1단계는 320구역(정상 60장×4모서리 240 + 눈가림 결함 60 + 기준점 20), 화면 5개다.** 이 문서를 커밋한 뒤 선정 스크립트를 처음 실행하며, 커밋 뒤 수치 기준을 바꾸지 않는다. 모델 점수 생성·열람, 추론, 학습, 외부 모델 호출 0. 봉인 파일·기존 라벨·응답·selection 수정 0. 고정 기준 진척 78/100(v1.14) 불변, D3 pending. 화면을 사용자에게 열거나 판정을 요청하는 것은 이 문서로 승인되지 않는다.

설계: `cohort2-normal-label-check-design-20261124.md`(커밋 `4c5bf4f`). 화면·안내문의 원형: `dev-normal-rejudge-100-20261124.md`.

## 0. 사용자 승인과 봉인 문서 보충
- 승인: 사용자(2026-11-24, 이 세션 채팅에 직접 붙여넣음)가 설계 §2의 추천안을 승인했다. 봉인 기준 문서 §1과 표준 초안 §4 Q4("봉인 유지, 재라벨 없음")를 **"원본 보존 + 별도 층"으로 다시 연다.** 다른 세션이 전한 승인은 근거로 쓰지 않는다.
- 보충의 범위: 봉인 파일 `artifacts/cohort2-seal-20261123/cohort2-seal.json`(SHA256 `e0ba2d897b907c5d8abb57d974972c5247db6867d171708a3b5d9086002e07b7`, 읽기 전용)은 그대로다. v2는 정상 206장만 대상으로 하는 별도 파일이다. `corner-cohort2-seal-criteria-20261123.md`와 `t5-eval-criteria-20261123.md`의 원문은 고치지 않는다. 두 문서의 작동점(0.20/0.60)·v1 분모(262/206)·통과선·1회 소진은 그대로다. 달라지는 것은 T5 §2·§6에 v2 병행 지표 하나가 더해지는 점뿐이다(§9).

## 1. 표본 규칙·시드
- 풀: 봉인 파일의 정상 206장. 묶음은 예비분 134(`pool`=`spare-of-first-seal`)와 새 라운드 72(next4 15·next5 2·next6 55).
- `random.Random(20261124)` 하나를 순서대로 쓴다. 예비분, 새 라운드 순으로 각각 `(collection_order, id)` 정렬 뒤 섞는다. 그 순서가 고정 순서다. 앞 39장(예비)·21장(새)이 1단계 60장, 나머지 95·51장이 확장 146장이다. 카드마다 네 모서리 전부.
- 읽는 것: 정상 카드는 `cls`·`pool`·`collection_order`·`id`. 결함 카드는 눈가림 모서리를 정하려고 사람 정답 `corners`를 더 읽는다(결함 모서리를 골라야 하므로 불가피하다). 카드 상자·후면 번호는 크롭을 만들 때만 읽는다. 점수는 봉인 파일에 없고 읽지도 만들지도 않는다.
- 선정 스크립트 전문은 부록 A, 파일 `artifacts/cohort2-label-check-20261124/select.py`(Git 제외) SHA256 `2d07e3c5af188e348d54d43c5a35d833490ed8a4d154e74a0ec0de7bf125d9d9`. `artifacts/`가 Git 제외라 부록으로 커밋한다. 결과 `selection.json`의 SHA256은 실행 뒤 별도 보충 기록으로 남기고 이 문서의 규칙은 고치지 않는다.

## 2. 눈가림·기준점
| | 1단계 | 확장 | 합 |
|---|---:|---:|---:|
| 정상 카드 / 구역 | 60 / 240 | 146 / 584 | 206 / 824 |
| 눈가림 결함 구역(정상 구역의 25%, 서로 다른 결함 카드의 결함 모서리 1개) | 60 | 146 | 206(결함 262장 중 중복 없음) |
| 기준점(개발 재판정에서 새 기준 `정상`이던 구역) | 20 | 39 | 59 |
| 합계 구역 | 320 | 769 | 1,089 |
| 화면 | 5(각 64구역) | 12(64구역 11·65구역 1) | 17 |

- 눈가림 결함: 결함 카드를 `(collection_order, id)`로 정렬해 섞고 앞 60장/다음 146장에서 사람 정답 `결함` 모서리 하나를 같은 난수로 고른다.
- 기준점: `artifacts/dev-normal-rejudge-20261124/mapping.json`의 층 `normal` 중 `artifacts/label-v2-20261124/overlay-v2.json`(SHA256 `3d02be7b…0a31`) 값이 `정상`인 59구역을 id 정렬 뒤 섞어 앞 20개가 1단계, 나머지 39개 전부가 확장이다. **확장에서 1단계와 같은 비율(약 8%)이면 49개가 필요하지만 남은 것이 39개뿐이라 39개(약 7%)를 쓴다(다시 쓰지 않는다).**
- 섞기: 단계마다 세 층을 합쳐 섞되 같은 카드의 구역은 10칸 이상 떨어지게 한다(한 쪽이 10구역이므로 같은 쪽에 같은 카드가 두 번 나오지 않는다. 화면 경계를 넘는 간격도 같은 규칙).
- 눈가림·기준점은 주 지표에 합치지 않고 따로 보고한다.

## 3. 화면·입력
- 개발 재판정 화면 코드(`artifacts/dev-normal-rejudge-20261124/build.py`, SHA256 `41c9ba54f5c6755b6e5f849be591c7a2121a60bffdcfd74d367e6ad479544a45`)를 SHA로 고정해 그대로 쓴다. 안내문 문구, 입력(`정상`/`미세`/`뚜렷`/`판단 불가`+사유, 확신 1~3 선택), 한 쪽 10구역, 붙여넣기 방식(클립보드 API·localStorage 없음)이 같다. 달라지는 것은 화면 이름(1~5)과 구역 수뿐이다.
- 크롭: 후면 사진 = 카탈로그 `photos[int(back)-1].path`(원본 바이트 SHA256이 봉인 기록과 같을 때만), 상자 = `region_box(카드 box, 모서리)`, `tools/relabel_zone_pages.crop`. 기준점은 개발 `selection.json`의 `image`·`box`.
- 숨기는 것: 카드·구역 id, 이전 라벨, 층, 묶음, 사진 경로, 점수. 결과 끝에 `# 화면=`, `# 제출시각=`. 번호 z1~z1089는 전체 공통이다.
- 대응표 `mapping.json`: 번호별 screen·card·corner·stratum(normal/defect_mix/anchor)·bundle·pool. 화면·대응표 SHA256을 기록한다. 확장 화면은 계속이 정해진 뒤 같은 `selection.json`에서 만든다.

## 4. 카드 판정과 주 지표
- 카드 판정(정상 층 카드만, 네 모서리): 하나라도 `미세`/`뚜렷` → **결함 카드**. 넷 다 `정상` → **정상 카드**. 결함 없이 `불가`·`미판정`이 하나라도 있음 → **판단 불가 카드**(분모 제외, 장수 공개).
- **주 지표** = 결함 카드 / (결함 카드 + 정상 카드), 양측 95% Wilson(z=1.959963984540054, 반올림하지 않은 값으로 판정).
- 하한값 병기: 판단 불가 카드를 전부 정상으로 본 비율 = 결함 카드 / (결함+정상+판단 불가). 판단 불가 제외는 비율을 위로 밀기 때문이다. 이 값은 병기용이며 계속 규칙에는 쓰지 않는다.

## 5. 분모 하한·계속 규칙
- 판정 가능 카드(결함+정상) 30장 미만 → 주 지표 "미측정". 묶음·시기·화면·눈가림은 분모 15 미만, 기준점은 10 미만이면 장수만 적고 비율·구간을 내지 않는다.
- 1단계 뒤(주 지표로만, 위에서부터 첫 번째 해당): 미측정 → 사용자 결정 / 하한 ≥ 0.20 → 나머지 146장도 판정해 전수 완성(계속) / 상한 < 0.15 → 중단하고 v1 유지(v2 층을 만들지 않음) / 그 사이 → 사용자 결정.
- 판정 가능 카드가 60장이면 결함 19장 이상이 계속, 3장 이하가 중단, 4~18장이 사용자 결정이다(계산값, 새 기준 아님).
- 이 규칙은 모델 점수와 무관하다. 눈가림·기준점 결과는 규칙을 바꾸지 않고 함께 공개한다. "계속"도 확장 화면을 열기 전에 사용자에게 보고하고 승인받는다.
- 전수 완성 뒤의 주 지표는 1·2단계를 합친 206장 전체로 낸다. 이때 1단계 결과로 계속 여부를 정했으므로 구간은 근사다.

## 6. 보조 지표 (설명용, 계속 규칙·채택에 쓰지 않음)
1. 묶음별 카드 비율(예비 134 / 새 72). 1단계는 39/21.
2. 판정 절차 시기별(예비+next4 149 / next5+next6 57). **시기 구분은 문서 근거의 가정**이다.
3. 결함 카드의 심각도: `뚜렷`이 하나라도 있으면 뚜렷, 아니면 미세. 구역의 정상/미세/뚜렷 장수.
4. 구역 단위(정상 층): (미세+뚜렷)/(정상+미세+뚜렷), 불가·미판정·사유별 건수. 같은 카드의 네 구역은 독립이 아니므로 Wilson 구간은 참고용이다. 분모 60 미만이면 미측정.
5. 화면별(정상 층 구역) 같은 비율. 차이는 단순 관찰이며 검정하지 않는다.
6. 눈가림 결함 구역 중 `정상` 판정 비율(놓치는 쪽 확인).
7. 기준점 구역 중 `정상` 판정 비율(과하게 부르는 쪽 확인. 이전 새 기준 판정과의 일치율). 같은 날 본 구역이라 기억 효과가 있고, 판정 주체는 개발 재판정 기록을 따른다.
8. 확신도 입력률. 확신도는 결과 판정에 쓰지 않는다.

## 7. 판정 주체 기록
- 사용자가 "사람이 직접 판정함"이라고 쓴 경우에만 사람 라벨로 기록한다. 그 문장이 없으면 "사용자 붙여넣기, 사람 직접 판정 미확인"으로 기록하고 한 줄 확인을 요청한다. AI 답은 사람 라벨과 섞지 않는다.
- 봉인 라벨의 원래 판정 주체·절차는 파일로 확정되지 않는다(설계 §1(a)). 주체를 다시 묻지 않으며, 결과를 "사람 라벨의 자기 일치"로 쓰지 않는다. 결과는 "봉인 라벨 대 이번 새 기준 판정"으로만 쓴다.
- 붙여넣은 원문은 화면마다 파일로 그대로 보존하고 SHA256을 남긴다. 화면 이름·제출시각 줄이 없거나, 줄 형식·중복·누락·화면 불일치가 있으면 분석은 종료 코드 2로 멈추고 임의로 고치지 않는다.

## 8. v2 동결
- 만들 조건: 206장 전수 판정이 끝난 경우만. 1단계만 있으면 v2 층을 만들지 않는다(한 분모 안에 두 기준을 섞지 않음).
- 위치: 봉인 폴더 밖 `artifacts/cohort2-label-v2-20261124/v2-normal-206.json`(Git 제외, 읽기 전용)과 `.sha256`.
- 값: 카드별 `{card: 정상|결함|판단 불가, corners: {네 모서리: 정상|결함|불가|미판정}, severity: {결함 모서리: 미세|뚜렷}}`. 미세·뚜렷은 모두 결함이다. `불가`·`미판정`은 정상이나 결함으로 채우지 않는다. 판단 불가 카드는 v2 분모에서 빼고 장수를 공개한다.
- 입력(응답·대응표·selection)과 분석 코드의 SHA256, 판정 주체 기록을 같은 폴더 meta에 적는다. 동결 뒤 수정 금지. 봉인 파일·v1 라벨에는 쓰지 않는다. 동결은 어떤 점수보다 먼저 끝나야 한다.

## 9. v1·v2 동시 보고 (D3 주 라벨은 v1)
- D3 통과 판정과 진척 점수는 v1(결함 262·정상 206)로만 낸다. v2는 사전 지정 병행 지표다. v2가 통과하고 v1이 미통과면 "v1 미통과, v2 병행 통과"로 쓰고 진척은 올리지 않는다.
- v2 분모: v2 정상 카드 = 잘못 표시 분모. v2 결함 분모 = 기존 결함 262 + v2에서 결함 카드가 된 이전 정상 카드(놓침은 새로 찾은 결함 모서리 기준, 기존 262장은 v1 모서리 기준). 판단 불가 카드는 어느 쪽에도 넣지 않는다. 작동점·통과선(놓침 상한 10%, 잘못 표시 상한 20%, 단측 95%)은 같다.
- v1·v2 수치는 %p 차이나 "개선·감소"로 쓰지 않는다. 각자 `k/n`과 Wilson 구간을 나란히 적는다. 허용하는 연결은 같은 206장의 재분류 장수뿐이다(v1 잘못 표시 k장 중 v2 결함 카드가 된 장수 등).
- 후보 간 비교는 같은 라벨 버전 안에서만 한다. 1차 350장·개발 자료와 비교하지 않는다.

## 10. 금지 재확인
봉인 파일·기존 라벨·selection·응답 수정, 점수 생성·열람, 추론·학습·외부 모델 호출, 468장을 학습·튜닝·임계 선택에 사용, 점수를 본 뒤 기준·후보·층 변경, 모델 오답을 이유로 사람 정답 변경, 승인된 이 재판정 밖의 완료 라벨 재요청, 이 문서 커밋 뒤 수치 기준 변경, push.

## 11. 한계
- 한 명의 판정, 목적을 아는 판정. 이전 화면과 제시 방식이 다르다(확대 크롭). 이전 라벨의 느슨함과 기준 변화를 가를 수 없다.
- 눈가림은 완전하지 않다. 결함 262장은 영어/표준이 86%라 일본어 판본의 뒷면은 이전 정상일 가능성이 높고, 기준점은 개발 사진이라 해상도·촬영이 다르며 사용자가 오늘 이미 본 구역이다. 이전에 본 카드를 알아볼 수도 있다. 층 비율을 아는 판정이다.
- 묶음과 판정 절차·언어·판본·촬영 제한이 교락한다. 묶음 차이의 원인을 단정하지 않는다.
- 분모 하한·구간 수치는 사전 근거 없는 임의 값이며 방향 표지다.

## 12. 변경·롤백
변경: 이 문서 1개(추적), 산출물은 `artifacts/cohort2-label-check-20261124/`(Git 제외). 롤백: 이 커밋 revert와 폴더 삭제.

## 부록 A. 선정 스크립트 전문 (SHA256 `2d07e3c5af188e348d54d43c5a35d833490ed8a4d154e74a0ec0de7bf125d9d9`)
```python
"""Fixed order of the sealed-cohort normal-label check. No scores read or made; the seal file is read only.
Run from repo root: .venv/bin/python artifacts/cohort2-label-check-20261124/select.py"""
import sys, os
sys.path[:] = [p for p in sys.path if os.path.abspath(p or '.') != os.path.dirname(os.path.abspath(__file__))]  # select.py would shadow stdlib select
import hashlib, json, random
from pathlib import Path

SEED, GAP = 20261124, 10
OUT = Path('artifacts/cohort2-label-check-20261124')
SEAL = 'artifacts/cohort2-seal-20261123/cohort2-seal.json'
SEAL_SHA = 'e0ba2d897b907c5d8abb57d974972c5247db6867d171708a3b5d9086002e07b7'
DEV_MAP, DEV_V2 = 'artifacts/dev-normal-rejudge-20261124/mapping.json', 'artifacts/label-v2-20261124/overlay-v2.json'
DEV_MAP_SHA = '3621b7693568f8800187e544f09795384001008a24ed1ca8d477edcb3780f14a'
DEV_V2_SHA = '3d02be7be0099f6fa32788432fe40ad9296a434a9b22d8396a04286bafee0a31'
CORNERS = ('upper_left', 'upper_right', 'lower_left', 'lower_right')
STAGE1 = {'spare': 39, 'new': 21}
BLIND, ANCHOR = (60, 146), (20, 39)  # (stage 1, expansion)


def load_pinned(path, sha):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f'sha mismatch: {path}')
    return json.loads(raw)


def normals(cards, rng):
    """[(stage 1 cards), (expansion cards)], each bundle shuffled separately."""
    parts = ([], [])
    for bundle, n1 in STAGE1.items():
        pool = [c for c in cards if c['cls'] == 'normal' and (c['pool'] == 'spare-of-first-seal') == (bundle == 'spare')]
        pool.sort(key=lambda c: (c['collection_order'], c['id'])); rng.shuffle(pool)
        parts[0].extend((c, bundle) for c in pool[:n1]); parts[1].extend((c, bundle) for c in pool[n1:])
    return parts


def blinds(cards, rng):
    """One defect corner from each of distinct defect cards, stage 1 then expansion."""
    pool = sorted((c for c in cards if c['cls'] == 'defect'), key=lambda c: (c['collection_order'], c['id']))
    rng.shuffle(pool)
    zones = [dict(card=c['id'], corner=rng.choice([k for k in CORNERS if c['corners'][k] == '결함']), stratum='defect_mix',
                  bundle='defect', pool=c['pool']) for c in pool[:sum(BLIND)]]
    return zones[:BLIND[0]], zones[BLIND[0]:]


def anchors(rng):
    """Dev zones that the 2026-11-24 rejudge called normal under the new standard (one zone per card)."""
    v2 = load_pinned(DEV_V2, DEV_V2_SHA)
    pool = sorted((m for m in load_pinned(DEV_MAP, DEV_MAP_SHA).values() if m['stratum'] == 'normal' and v2.get(m['id']) == '정상'), key=lambda m: m['id'])
    assert len(pool) == sum(ANCHOR), len(pool)
    rng.shuffle(pool)
    zones = [dict(card=m['group'], corner=m['area'], stratum='anchor', bundle='anchor', pool='dev', dev_id=m['id']) for m in pool]
    return zones[:ANCHOR[0]], zones[ANCHOR[0]:]


def spread(zones, rng):
    """Shuffle so that zones of one card are at least GAP positions apart."""
    for _ in range(10000):
        rest, out = list(zones), []
        rng.shuffle(rest)
        while rest:
            recent = {z['card'] for z in out[-(GAP - 1):]}
            i = next((i for i, z in enumerate(rest) if z['card'] not in recent), None)
            if i is None:
                break
            out.append(rest.pop(i))
        if not rest:
            return out
    raise ValueError('no order with the required gap')


def main():
    cards, rng = load_pinned(SEAL, SEAL_SHA)['cards'], random.Random(SEED)
    norm, blind, anch = normals(cards, rng), blinds(cards, rng), anchors(rng)
    ids = {c['id'] for c in cards}
    sel, n = [], 0
    for s in (0, 1):
        part = [dict(card=c['id'], corner=k, stratum='normal', bundle=b, pool=c['pool']) for c, b in norm[s] for k in CORNERS]
        for z in spread(part + blind[s] + anch[s], rng):
            n += 1; sel.append(dict(n=n, stage=s + 1, **z))
    assert len({(z['card'], z['corner']) for z in sel}) == len(sel) == 320 + 769
    assert not {z['card'] for z in sel if z['stratum'] == 'anchor'} & ids
    assert len({z['card'] for z in sel if z['stratum'] == 'normal'}) == 206 and len({z['card'] for z in sel if z['stratum'] == 'defect_mix'}) == 206
    meta = dict(seed=SEED, gap=GAP, seal_sha256=SEAL_SHA, dev_v2_sha256=DEV_V2_SHA,
                normal_order=[[dict(card=c['id'], bundle=b) for c, b in norm[s]] for s in (0, 1)])
    (OUT / 'selection.json').write_text(json.dumps(dict(meta=meta, zones=sel), ensure_ascii=False, indent=1))
    print('selection sha256', hashlib.sha256((OUT / 'selection.json').read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
```

## 부록 B. 실행 기록 (커밋 `56f6a4b` 뒤 추가, 위 규칙·수치 변경 없음)
선정은 규칙 커밋 뒤 처음 실행했고 같은 시드 2회 실행의 SHA가 같다. 화면·대응표도 2회 생성 SHA가 같다. 기준점 사진의 `image_sha256`은 원본 바이트 해시 또는 복호 해시(`decoded_hash`)로 기록돼 있어(개발 125장 중 110/15) 둘 중 하나와 맞는지 확인한다.
```text
f551e4aebe709816cd9b7124a536b15e320444d22b6134298d0cba8352ac6deb  analyze_cards.py
95c09481af4ac46f5acc8dc5a6c0ec4d861ce56ade66a104507fc7c8707a9458  build.py
ccc198f9f92e774756eb0c054d8739b44733e93c9b25b28121c835f0b2ee2568  check_screens.py
2d07e3c5af188e348d54d43c5a35d833490ed8a4d154e74a0ec0de7bf125d9d9  select.py
577630021cb80e6ee83a702051ddab4fa31d107e1d6577a8b99e72cc3ad7de31  test_analyze_cards.py
0ebace22fde11f0546ab6d821aa12cab8b78840afbf582a62ed4e672d833e541  pure.js
aa372a9d323bbe406f134e8df8994f4c061a96ff8a37737aa3dd9ba994e68521  test_screen.js
9adc30d5866b127f1b5dea7afca2d6828bf1c0f8d583c301848816ea5d3c6228  mapping.json
da8b2f88444ac83ed398f951fe8f022dcc0c6639ceeacda79e9c7e1ae4904fb6  selection.json
59297cc0cd67f75385065a1b7251155bdac7f24581d1d8a6193e9bce737ccc6a  screen-1.html
5b71b8d7bda510855195cf347526a979e96dbc241f1afa7e88fbc4f375383664  screen-2.html
19ba845e14a9c120d5a932f2f15ee37e7c4ce54a47fa318ffeef9ceab5225be1  screen-3.html
55a797682d06e2f971c3b687dafa4a530e7b95ad380f9958886de86b4e11a778  screen-4.html
84401584ccb7505d03ca65b687a3b7ea3d93b1876692f76f2f85dfd7a1bc1cd8  screen-5.html
```
