# 자기 일치도 측정 도구 — 설계와 개발 계약 초안 (2026-11-25)

**설계 초안이며 어떤 승인도 아니다.** 재판정 요청·구역 목록·화면·수집·실험의 승인이 아니고, 아래 개발 계약은 배정 전 초안이다. 정확도 변화 없음, 진척 변화 없음. 기존 규칙과 부딪히면 기존 규칙이 우선한다.

task_id `self-agreement-tooling-design-20261125` / owner Claude Opus 5.5(설계만) / base_sha `e578301c910e725db9ebaed55024b6e55079cab8` / 근거 제안서 `docs/collaboration/plans/label-self-agreement-prereg-20261125.md`(아래 "제안서 N절").

**`<사람>` 값은 도구의 입력 인자로만 받는다.** 칸·시작 수·간격·시드·주체 확인 문장·쏠림 문턱 등은 사전 고정 파일 `plan.json` 한 곳에서 읽고, 코드·이 설계·시험의 기본값에 박지 않는다. 시험의 숫자는 모두 합성 입력이며 제안값이 아니다. 사용자가 지시한 방향(칸=모서리, 간격 2주, 1차도 새로 받음)도 확정 전에는 `plan.json`에 적을 후보일 뿐이다.

적용 규칙: `short-request-reading`, `label-agreement-watch`, `can-this-experiment-tell`, `label-provenance`, `single-source-criteria`, `explicit-verdict-merge`, `label-screen-round-trip`, `regression-for-every-fix`(시험 계획), `chance-check`. 스킬: `verification-before-completion`, `writing-plans`(이 계약 안에서만. 별도 계획 파일과 실행 스킬 연결은 하지 않음).

## 1. 구성 요소와 재사용

새 파일은 `tools/self_agreement/` 아래에만 둔다. 기존 파일은 하나도 고치지 않는다.

| 구성 요소(계약) | 하는 일 | 재사용(수정 없음) | 새로 짜는 부분과 이유 |
|---|---|---|---|
| A 사전 고정·구역 선정 | `plan.json` 검사, 모집단·제외·오류 층 파일의 SHA-256 대조, 시드 선정, 중립 번호 `n` | 없음 | `relabel_corner_*_pages.py`의 `select`는 시드·층별 수가 상수로 박혀 있고 이전 라벨 `target`을 읽는다. 제안서 6절(층화 없으면 정답을 읽을 필요 없음)과 맞지 않는다 |
| B 두 회차 화면 | 같은 크롭·같은 문구로 화면 생성, 2차는 다른 시드 순서와 새 번호, 제출 시각 줄, 회차 대응표 | `relabel_corner_highres_pages.crop` 또는 `relabel_zone_pages.crop`(값은 `plan.crop`), `relabel_corner_blind_pages.INSTRUCTIONS`, `relabel_zone_pages.STYLE`, `label_criteria.write_page`, `label_criteria.sidecar` | `zp.SCRIPT`에는 제출 시각·화면 식별 줄이 없다. `zp.article`은 전역 `zp.crop`을 바꿔 끼우는 방식이라 다른 도구의 크롭이 섞일 수 있다 |
| C 답 가져오기 | 원본 보존, 문장·시각·화면 식별·번호 전수 검사, 회차 기록 작성 | `label_criteria.check`(기록 형식·번호 대조·출력 경로 비어 있음) | `score.parse`는 모르는 줄과 중복을 조용히 버려 쓸 수 없다. `mobile_corner_label_import`는 사람 정답을 쓰는 도구라 이 측정에 쓰면 안 된다 |
| D 점수·다음 행동 | 제안서 10·11절 지표와 표 6행 | `score.py`의 `wilson`, `corner-chance-check-20261124/check.py`의 `mcnemar`(아래) | `score.py`의 `flip`은 함수 안 식이라 부를 수 없다. `ebay_back_retest.kappa`는 `정상/제한` 두 값 고정이고 소수 계산이다(경계 문제는 3절) |

`check.mcnemar(control, candidate)`에 {n: 1차가 결함인가}, {n: 2차가 결함인가}를 주면 `worse_b`=1차 정상→2차 결함=제안서의 b, `better_c`=c, `exact_two_sided_p`=같은 정확 양측식이다(`check.py:48-54`). b+c=0이면 p=1이 된다. "worse/better"라는 이름은 이 측정에서 뜻이 없으므로 출력에는 b·c로만 쓴다. 두 진단 파일은 폴더 이름에 `-`가 있어 `importlib.util.spec_from_file_location`으로 읽는다(`tests/test_corner_rejudge.py:8-12` 선례).

화면을 만드는 기존 스크립트 조사:

| 파일 | 재사용 가능성 |
|---|---|
| `tools/relabel_corner_repro_pages.py` | 두 회차·다른 순서의 가장 가까운 선례. 시드·30+30이 상수, 회차 사이 번호가 같음(`r1..r60` 유지), `zp.crop` 전역 교체, 기록 파일·시각 없음, 기존 화면을 덮어씀 → 틀만 참고 |
| `tools/relabel_corner_blind_pages.py` | `INSTRUCTIONS`만 재사용. 모서리 재판정 문구 중 `tests/test_label_criteria_source.py`가 정본과 대조하는 유일한 문구다 |
| `tools/relabel_corner_highres_pages.py` | `crop`(1000px, 품질 88) 재사용 |
| `tools/relabel_zone_pages.py` | `STYLE`, `crop`(420px, 품질 62) 재사용. 420px는 11-21 판단 불가 비율의 해상도 교란 의심이 기록돼 있다(`corner-blind-rejudge-20261121.md:18`) |
| `tools/relabel_corner_consensus_pages.py`, `tools/relabel_consistency_page.py` | 재사용 안 함(합의 라벨·표면 카드용) |
| `tools/mobile_corner_label_pages.py` | 카드 전체 800px 화면에서 네 칸을 누르는 라벨용. 구역 하나씩 보는 이 측정과 조작이 달라 재사용 안 함 |
| `tools/mobile_visibility_rejudge_pages.py` | 관찰 제한용. "대상 전수 일치 아니면 거절" 방식만 참고 |
| W1 B의 `build.py`·`analyze_b.py` | Git 제외 `artifacts/`에 있어 열지 않았다. 문서(`w1-selfagree-b-20261123.md:9`)의 시각 줄 형식만 참고 |

### 1.1 `plan.json` (A가 검사, 네 도구가 모두 읽음)

모든 열쇠가 필수이고 모르는 열쇠가 있으면 거절한다. `null`은 표시한 것만 명시적으로 허용한다. 도구는 파일의 SHA-256(`plan_sha256`)을 모든 산출물에 적고, 다음 단계는 다르면 종료 코드 2로 멈춘다. 결과를 본 뒤 값을 바꾸면 앞 단계 산출물과 맞지 않게 된다.

| 열쇠 | 뜻(제안서 근거) | null |
|---|---|---|
| `schema` | 1 | 불가 |
| `approval_ref` | 전체 승인 기록의 문서 경로와 커밋(13절). 비어 있으면 거절. 문자열이 있다는 것은 승인의 증명이 아니다 | 불가 |
| `cell` | 대상 칸. 지금 `모서리`만 받고 나머지는 거절(기준 기록이 모서리 문구만 지원) | 불가 |
| `new_first_round` | 1차도 새로 받는가. `true`가 아니면 거절(3절) | 불가 |
| `population_sha256`, `exclude_sha256`, `error_layer_sha256` | 입력 파일 해시(6절) | 오류 층만 |
| `main_count`, `error_count` | 주 층 시작 수, 오류 층 수 | 오류 층이 null이면 `error_count`는 0 |
| `strata` | 층화. null만 구현. null이 아니면 거절(새 계약 필요) | 예 |
| `per_page` | 한 화면의 구역 수(피로, 13절) | 불가 |
| `crop` | `highres` 또는 `thumbnail` | 불가 |
| `seed_selection`, `seed_order2`, `seed_bootstrap` | 서로 다른 정수 | 불가 |
| `bootstrap_draws` | 반복 수(10절, 2000은 제안일 뿐 코드에 없음) | 불가 |
| `min_interval_hours`, `max_interval_hours` | 두 회차 간격의 허용 하한·상한 | 상한만 |
| `judge_statement` | 주체 확인 문장 | 불가 |
| `p_min` | 값 쏠림 정의(10절 3번). 0 초과 0.5 미만의 **문자열** 소수 | 불가 |
| `direction_min_count`, `direction_alpha` | 3행 문턱. 둘 다 있거나 둘 다 null. `direction_alpha`는 문자열 소수. null이면 3행을 적용하지 않고 출력에 "3행 미적용"을 적는다(13절) | 둘 다 함께 |
| `reference_zone_count` | 참고 폭 ±(e 상한 × N)의 N(11절 c) | 예 |

`p_min`이 없으면 제안서는 "11절 2행을 정의대로 적용 못 함"이라고 하므로 측정을 시작하지 않는 쪽(거절)으로 정했다.

기존 값 최소 분모 30·경고선 0.60·목표선 0.80은 `<사람>` 값이 아니라 발효된 값이다(`LABELING_PROTOCOL.md:89`). `decide.py` 상수로 두고, 시험이 `LABELING_PROTOCOL.md`에서 "최소 분모 30, 목표선 카파 0.80, 경고선 카파 0.60" 문구를 읽어 상수와 대조한다.

### 1.2 산출물 형식 (고정)

모든 쓰기는 새 파일만(`open('x')`), 덮어쓰기 없음. 실패는 종료 코드 2와 이유 한 줄.

- **입력 행**(모집단·오류 층 JSON 목록): 열쇠가 정확히 `id, group, area, image, box`. `target`·점수 등 다른 열쇠가 있으면 거절해 정답·점수가 선정에 들어오지 못하게 한다. 제외 파일: `group` 문자열 목록.
- **`selection.json`**(A): `{plan_sha256, zones:[{n, layer:'main'|'error', id, group, area, image, box}]}`. 화면에는 절대 넣지 않는다.
- **`<회차 폴더>/key.json`**(B): `{plan_sha256, selection_sha256, round, criteria_sha256, screen_sha256, crops:{n: crop_sha256}, pages:[{page_id, file, zones:{"z1": n}}]}`. 각 화면 옆에는 `label_criteria`의 `<화면>.criteria.json`.
- **답 글**(화면이 만드는 글): 첫 줄 `# 화면=<page_id>`, 둘째 줄 `# 제출시각=<ISO8601 +09:00>`, 이어 `z1=정상|결함|불가|미확인` 전수.
- **`round<k>.json`**(C): `{plan_sha256, selection_sha256, round, judge_confirmed:true, statement, submitted:{page_id: 시각}, criteria_sha256, screen_sha256, crops, answers:{n: 값}, raw:[원본 SHA-256]}`.
- **`result.json`**(D): 3절의 수와 `row`(1~6), `reasons`, 한계 문장.

### 1.3 동작 결정 (제안서에 없어 이 설계가 정한 것 — 사용자 확인 대상)

1. **주 층 뽑기**: 카드(`group`)를 정렬·섞어 `main_count`장을 고르고, 카드마다 구역 하나를 같은 확률로 고른다. 카드 확률이 같고 구역 확률은 카드별 구역 수에 따라 다르다. 카드가 모자라면 거절(줄여서 진행하지 않음).
2. **번호 `n`**: 주 층과 오류 층을 합쳐 `seed_selection`으로 섞은 순서. 1차는 이 순서, 2차는 `seed_order2`로 섞고 `z1..`을 새로 매긴다. 두 순서가 같으면 거절.
3. **오류 층**: 파일에 있는 행을 순서대로 `error_count`개. 초과하면 거절. 점수로 고르거나 순위를 매기지 않는다. 오류 층 카드가 모집단의 제외 목록에 없으면 거절(제안서 6절 b).
4. **크롭 동일성**: 2차 생성 때 크롭을 다시 만들어 1차 `key.json`의 해시·문구·화면 해시와 대조하고, 하나라도 다르면 화면을 쓰기 전에 거절한다. 원본 사진이나 Pillow 판이 바뀌면 여기서 멈춘다.
5. **간격 계산**: 하한 = (2차에서 가장 이른 제출) − (1차에서 가장 늦은 제출) ≥ `min_interval_hours`. 상한 = (2차에서 가장 늦은 제출) − (1차에서 가장 이른 제출) ≤ `max_interval_hours`. 경계값은 허용. 시각은 기기 시계이며 마지막으로 버튼을 누르거나 복사한 순간이다.
6. **주체 문장**: 화면이 문장을 자동으로 넣지 않는다(자동 문장은 확인이 아니다). 사용자가 채팅에 적은 문장을 회차별 파일로 받아 `judge_statement`와 글자 단위로 같은지 본다(앞뒤 공백만 무시). 프로그램은 그 문장을 사람이 썼는지 증명하지 못한다.
7. **문장·시각 누락**: C는 원본을 먼저 보존한 뒤 종료 코드 2로 멈추고 `round<k>.json`을 만들지 않는다(상태 "주체 미확인"). D도 `judge_confirmed`가 참이 아닌 회차 기록을 받으면 1행으로 보낸다(이중 방어). 문장이 나중에 오면 같은 원본으로 다시 가져올 수 있다.
8. **3분류 표**: 정상·결함·판단 불가 세 값만. 어느 회차든 미확인이면 3분류에서 빼고 건수를 따로 적는다(미확인은 판정이 아님). 카파는 이진과 3분류 모두 낸다.
9. **주 층만** 모든 지표에 쓰고 오류 층은 "확정 쌍 m 중 같은 답 k" 건수만 낸다. 분모·e·표의 행에 쓰지 않는다.
10. **부트스트랩**: 카드 단위 재표집(주 층은 카드당 구역 1개라 구역 재표집과 같다). 백분위 2.5·97.5. 카파가 정의되지 않은 재표집은 빼고 그 수를 함께 적는다. 모두 정의되지 않으면 구간 null.
11. **1행·2행의 출력**: 건수와 이유만. 카파·e·구간은 null(미측정). 3행은 카파·b·c·p를 내고 e는 null. 4~6행은 전부 낸다.
12. **e의 구간**: 선례 `score.py:26`대로 d 상한을 0.5에서 자르고 `upper_clipped: true`를 적는다. d ≥ 0.5이면 e와 구간 모두 null. 불일치 0이면 정확 양측 95% 상한 `1-0.025**(1/n)`을 d의 추가 줄로 적는다(윌슨 값과 다른 값임을 표시).

## 2. 파일·함수 분할

기준: 파일당 함수 정의 ≤ 7(중첩·메서드·`lambda`까지 보수적으로 셈, 컴프리헨션은 제외), 호출 전이 ≤ 4. 표준 라이브러리·Pillow 내부는 전이로 세지 않는다(이 해석은 리뷰어 확인 대상). 재귀·클래스 없음. 화면 스크립트는 JS 파일로 분리하고 화살표 함수까지 센다. 기존 파일의 함수 수는 변하지 않는다.

| 새 파일 | 함수 | 수 |
|---|---|---|
| `tools/self_agreement/plan.py` (A) | `load(path) -> (dict, sha)`, `check(plan)`, `file_sha(path)`, `write_new(path, data)` | 4 |
| `tools/self_agreement/pick_zones.py` (A) | `rows(path, sha)`, `choose(rows, excluded, count, rng)`, `number(main, error, rng)`, `main(argv)` | 4 |
| `tools/self_agreement/screen.js` (B) | `now`, `build`, `show`, `pick`, `copy`, 버튼 연결 화살표 1 | 6 |
| `tools/self_agreement/screen.py` (B) | `article(z, jpeg_b64)`, `page_id(round_no, page_no, crops)`, `page_text(title, pid, body)`, `screen_sha(crop_name)` | 4 |
| `tools/self_agreement/make_round.py` (B) | `ordered(zones, round_no, seed)`, `shoot(zones, crop_name)`, `same_screen(first_key, key)`, `write(out, key, zones, shots)`, `main(argv)` | 5 |
| `tools/self_agreement/answers.py` (C) | `parse(text)`, `keep_raw(folder, data)` | 2 |
| `tools/self_agreement/import_round.py` (C) | `confirmed(path, plan)`, `collect(folder, key, raws, out)`, `main(argv)` | 3 |
| `tools/self_agreement/stats.py` (D) | `borrow(rel, name)`(진단 파일 읽기), `table(pairs)`, `kappa(pairs, classes)`, `interval(pairs, draws, seed)`, `error_rate(k, n)` | 5 |
| `tools/self_agreement/decide.py` (D) | `invalid(plan, plan_sha, first, second)`, `skewed(table, p_min)`, `direction(b, c, p, plan)`, `row(reasons, table, k, plan, p)` | 4 |
| `tools/self_agreement/score_rounds.py` (D) | `pairs(selection, first, second, layer)`, `measures(pairs, plan)`, `report(...)`, `main(argv)` | 4 |

주요 호출 경로(가장 긴 것):

| 경로 | 전이 |
|---|---|
| `pick_zones.main → plan.load → plan.check` | 2 |
| `pick_zones.main → rows → plan.file_sha` | 2 |
| `make_round.main → shoot → (highres.crop 또는 zone.crop)` — 후보가 둘뿐인 고정 표 | 2 |
| `make_round.main → write → label_criteria.write_page → label_criteria.sha` | 3 |
| `make_round.main → write → page_text` / `→ article` | 2 |
| `screen.js`: 버튼 화살표 → `pick → show → build → now` | 4 |
| `screen.js`: `copy → show → build → now` | 3 |
| `import_round.main → collect → label_criteria.check → label_criteria.sidecar` | 3 |
| `score_rounds.main → report → measures → stats.interval → stats.kappa` | 4 |
| `score_rounds.main → report → measures → stats.error_rate → score.wilson` | 4 |
| `score_rounds.main → report → decide.row → decide.skewed` / `→ decide.direction` | 3 |

`stats.error_rate`는 `borrow`를 부르지 않고 모듈 상수로 한 번 읽은 `score.wilson`을 쓴다(`measures → error_rate → borrow → …`로 깊어지지 않게). 구현이 이 표와 달라지면 계약을 갱신하고 리뷰에서 다시 센다.

`screen.js`는 `document`만 인자로 받는 환경(`tests/label_page_press.js`)에서 돌아야 한다: `querySelectorAll('article')`, 각 `article.querySelectorAll('button')`, `addEventListener('click', …)` 한 번, `#out`·`#copy`·`#msg`만 사용. 같은 버튼에 리스너를 두 번 붙이면 시험 환경이 앞의 것을 덮으므로 금지. "안 누른 곳 전부 정상" 버튼은 두지 않는다.

## 3. 시험 계획 (합성 fixture만)

사진은 `PIL.Image.new`로 만든 단색·격자 그림, 행은 시험 안에서 만든 가짜 ID. 실제 사진·라벨·`artifacts/`를 열지 않는다. node가 없으면 왕복 시험은 건너뛰고 "미검증"으로 보고한다(통과로 쓰지 않음).

### 3.1 순서

A 시험 → B 시험 → **C의 왕복 시험(누른 것=가져온 것)** → D 시험 → 끝에서 끝까지 시험. **왕복 시험이 main의 통합 코드에서 통과했다는 로그(대상 SHA 포함)가 있기 전에는 진짜 화면을 만들지 않는다.** B만 통합된 상태는 화면 생성 조건을 채우지 못한다.

### 3.2 점수 손계산 대조 (정상-정상 / 결함-결함 / b / c)

계산은 `python3 -I`의 `Fraction`과 `score.py:13-16`의 윌슨 식(Z=1.96)으로 이 세션에서 했다(저장소 코드는 실행하지 않음). 값은 합성 예이며 예상치가 아니다.

| 표 | 확정 쌍 | 일치율 | 이진 카파 | d 윌슨 95% | e [하한, 상한] | 정확 양측 p |
|---|---|---|---|---|---|---|
| 14/13/2/1, 14/13/1/2 | 30 | 0.9 | **정확히 4/5** | 0.0346~0.2562 | 0.0528 [0.0176, 0.1509] | 1 |
| 14/13/3/0, 14/13/0/3 | 30 | 0.9 | 182/227 = 0.8018 | 같음 | 같음 | 0.25 |
| 26/1/2/1, 26/1/1/2 | 30 | 0.9 | 8/23 = **0.3478** | 같음 | 같음 | 1 |
| 26/1/3/0 | 30 | 0.9 | 26/71 = 0.3662 | 같음 | 같음 | 0.25 |
| 12/12/3/3 | 30 | 0.8 | 정확히 3/5 | 0.0950~0.3731 | 0.1127 [0.0500, 0.2481] | 1 |
| 13/11/6/0 | 30 | 0.8 | 143/233 = 0.6137 | 같음 | 같음 | 0.03125 |
| 13/12/5/0 | 30 | 0.8333 | 52/77 = 0.6753 | 0.0734~0.3356 | 0.0918 [0.0381, 0.2133] | 0.0625 |
| 15/15/0/0 | 30 | 1 | 1 | 0~0.1135 | 0 [0, 0.0604] | 1(비율은 "해당 없음") |
| 8/7/8/7 | 30 | 0.5 | 0 | 0.3315~0.6685 | null(d=0.5) | 1 |
| 30/0/0/0 | 30 | 1 | 정의 불가 | — | — | 1 |

0/30의 정확 양측 95% 상한 `1-0.025**(1/30)` = 0.1157(약 11.6%), 같은 자리 윌슨 상한은 0.1135(약 11.4%)다. 두 식을 섞어 쓰지 않는지 시험한다.

**경계값을 소수로 비교하면 틀린다.** 확정 쌍 30~40의 모든 표를 정수로 확인했더니 카파가 정확히 0.8인데 소수 식(이진 `pa`,`pe`)이 0.7999999999999999로 나오는 표가 14개(예 10/20/1/2), 정확히 0.6인데 0.5999999999999999 등으로 나오는 표가 14개(예 4/27/1/3) 있었다. 소수로 비교하면 6행이 5행, 5행이 4행이 된다. 그래서 `kappa`는 `fractions.Fraction`을 돌려주고 비교도 `Fraction`으로 한다(`p_min`·`direction_alpha`를 문자열로 받는 이유). 위 두 표를 회귀 입력 원문 그대로 남긴다(`regression-for-every-fix`).

### 3.3 다음 행동 표가 정확히 한 행으로 가는지

시험용 `plan`(합성): `p_min="0.1"`, `direction_min_count=6`, `direction_alpha="0.05"`, 간격 하한 10시간·상한 null. 제안값이 아니다.

| 입력 | 기대 행 |
|---|---|
| `judge_confirmed` 거짓 또는 없음(나머지 완벽) | 1 |
| 간격이 하한보다 1초 짧음 / 정확히 하한 | 1 / 1 아님 |
| 상한을 준 plan에서 상한 초과 | 1 |
| 기준 문구 해시·화면 해시·크롭 해시 중 하나만 다름(세 경우 각각) | 1 |
| 다른 `plan_sha256` 또는 `selection_sha256` | 1 (도구 종료 코드는 2) |
| 1행 조건 + 확정 쌍 29 | 1(위가 우선) |
| 확정 쌍 29(14/14/0/1, 카파 0.931이어도) / 30 | 2 / 2 아님 |
| 30/0/0/0, 0/30/0/0(카파 정의 불가) | 2 |
| 26/1/2/1(1차 결함 비율 2/30 < 0.1) | 2 |
| 결함 비율이 정확히 `p_min`(3/30) | 값 쏠림 아님(미만만) |
| 13/11/6/0 (b+c=6, p=0.03125) | 3, e는 null |
| 13/12/5/0 (b+c=5) | 3 아님 → 5 |
| 13/11/6/0 + 방향 문턱 둘 다 null | 5 + "3행 미적용" |
| 12/11/4/3(카파 8/15) | 4 |
| 8/7/8/7(d=0.5) | 4, e null |
| 12/12/3/3 (정확히 0.6) | 5 |
| 4/27/1/3(정확히 0.6, `p_min="0.01"`) | 5 |
| 13/13/2/2(카파 11/15) | 5 |
| 14/13/2/1 (정확히 0.8) / 10/20/1/2 | 6 / 6 |
| 15/15/0/0 (b+c=0) | 6, 쏠림 비율 "해당 없음" |

추가로 확정 쌍 30의 모든 2×2 표(5,456개)를 돌려 `row`가 항상 1~6 중 하나의 정수를 돌려주는지 확인한다. d ≥ 0.5면 일치율 ≤ 0.5라 5·6행이 나올 수 없다는 것도 함께 확인한다.

### 3.4 왕복과 나머지

- 왕복(C): 두 회차 각각, 화면 생성 → 실제 스크립트로 누르기(정상·결함·불가, 바꿔 누르기, 안 누름) → 나온 글 → `import_round` → `answers`가 누른 값·`n`과 같음. 2차는 순서가 다르고 같은 `n`에 같은 값이 돌아옴. 기존 `tests/test_relabel_zone_round_trip.py`의 `run(page, presses, alln=False)`을 불러 쓴다.
- 거절(C): 시각 줄 없음, 시간대 없음, 문장 파일 없음·한 글자 다름, 다른 화면의 글, 줄 하나 빠짐, 중복 번호, 모르는 값, 쪽 하나 빠짐, 같은 쪽 두 번, 1차 글을 2차로 넣음 → 모두 종료 코드 2, `round<k>.json` 없음, **원본은 보존됨**(권한 0444, 바이트 동일). 문장이 나중에 오면 같은 원본으로 성공.
- 판단 불가·미확인(C·D): 값 그대로 남고 확정 쌍에서만 빠짐. 제안서 9절의 다섯 수(시작 / 1차 불가·미확인 / 2차 불가·미확인 / 한 회차만 확정 / 확정 쌍)가 손으로 센 값과 같음.
- 화면(B): 화면 글에 `id`·`group`·`area`·`image` 경로·`layer`·오류 층 여부·1차 번호가 없음, `blind.INSTRUCTIONS`가 그대로 있음, 두 회차의 `criteria_sha256`·`screen_sha256`·`crops` 동일, 단색이 아닌 그림으로 크롭이 바뀌면 2차 거절, 이미 있는 폴더 거절. 같은 입력이면 같은 바이트.
- 선정(A): 같은 시드면 같은 목록, 입력 행 순서를 섞어도 같은 목록, 다른 시드면 다른 목록(합성 자료에서), 제외 카드가 없음, 카드당 1구역, 모집단 바이트 하나가 바뀌면 거절, `target`·`score` 열쇠가 있으면 거절, 오류 층 카드가 제외 목록에 없으면 거절.
- **기본값 금지(A)**: 모든 열쇠를 하나씩 빼 거절 확인, 모르는 열쇠 거절, 허용 표 밖의 null 거절, 소스에 `argparse`의 `default=`와 `plan.get(`이 없음을 문자열로 확인.
- D: `decide.py` 상수와 `LABELING_PROTOCOL.md` 문구 일치, 오류 층 값이 바뀌어도 주 지표가 안 바뀜, 같은 시드면 같은 부트스트랩 구간, 정의 불가 재표집 수 보고, 출력에 "정확도"라는 낱말과 "개선"이라는 낱말이 없음(`chance-check`, 제안서 1절 표기).
- 끝에서 끝까지(D): 합성 모집단 → 선정 → 두 회차 화면 → 누르기 → 가져오기 → 점수. 알려진 2×2와 행이 나옴.

### 3.5 Review Focus(빠지기 쉬운 입력)

1. 사용자가 글을 나눠 붙이거나 줄 끝 공백·CRLF가 섞임 → 값은 보존, 빠진 줄이면 거절(C).
2. 사용자가 `#` 줄을 지우고 붙임 → 거절하고 무엇이 빠졌는지 한 줄로 안내(C).
3. 기기 시계가 틀려 2차가 1차보다 이르게 나옴 → 1행(D). 시각을 고쳐 쓰지 않는다.
4. 2주 사이 원본 사진 이동·Pillow 갱신 → 2차 생성 거절(B).
5. 같은 사진이 다른 `group`으로 두 번 들어옴 → 두 행의 `image`가 같으면 선정에서 거절(A).

## 4. 개발 계약 초안 4개

공통: 배정 때 관리자가 `base_sha`를 검증된 최신 `origin/main`으로, `branch`를 확정한다. owner는 배정 전이라 비운다. 4개면 충분하다(끝에서 끝까지 시험은 D에 넣음). **의존 순서 A → B → C → D, 앞 계약이 main에 통합된 뒤 다음 계약을 배정한다.** D의 계산 부분은 A 뒤에 시작할 수 있지만 형식 어긋남을 막으려고 직렬로 둔다. 파일 집합은 서로 겹치지 않는다. 공통 금지: 하위 에이전트, 학습·추론·실험·`./experiment`·`./review`, 외부 호출, 사람 재판정 요청, 통합·push, 기존 파일 수정, `data/`·`artifacts/`·사람 라벨·사진 열람, 봉인 468장·독립 350장·이름에 `cohort2`가 든 자료, 전체 시험 묶음 강제.

**각 계약 공통 문구: 진짜 구역 목록·화면·수집은 이 계약에 없다. 별도 단계이며 사용자의 `<사람>` 값 확정과 전체 승인(제안서 13절), 완료 라벨 재요청 승인 뒤에만 할 수 있다. 이 도구가 완성된 것은 그 승인이 아니다.**

공통 checks(계약마다 `B`=그 계약의 base_sha, `T`=커밋):
1. `git diff --check B T` 종료 0.
2. `git diff --name-status B T`의 모든 줄이 `A`이고 allowed_files와 같음.
3. 아래 계약별 시험 명령 종료 0(건너뜀 수를 보고).
4. 함수 수: `python3 -I -c "import ast,sys;[print(p,sum(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)) for x in ast.walk(ast.parse(open(p).read())))) for p in sys.argv[1:]]" <새 .py 파일들>` 각 7 이하. 호출 경로는 2절 표와 손으로 대조.
5. `git status --short` 빈 출력.

기존 회귀(계약마다): `.venv/bin/python -m unittest discover -s tests -p 'test_label_criteria_source.py'`, 같은 방식으로 `test_label_text_regressions.py`. 새 파일은 `tools/*label*.py` 조건에 안 걸려 과거 문구 시험이 덮지 않는다. 문구를 새로 쓰지 않고 `blind.INSTRUCTIONS`만 쓰는 것으로 지킨다.

### 계약 A

```text
task_id: self-agreement-plan-pick
owner:
status: assigned 전 (초안)
base_sha: 배정 때 확정
branch: 배정 때 확정
goal: plan.json 검사와 시드 구역 선정이 합성 입력에서 재현되고 기본값 없이만 동작한다
allowed_files:
  tools/self_agreement/plan.py (새)
  tools/self_agreement/pick_zones.py (새)
  tests/test_self_agreement_pick.py (새)
forbidden_files: 그 밖의 모든 파일
contract: 1.1, 1.2(입력 행·selection.json), 1.3의 1~3. 실행: python -m tools.self_agreement.pick_zones PLAN POPULATION EXCLUDE ERROR_LAYER|- OUT
  종료 0=새 selection.json 1개, 2=아무것도 쓰지 않음. 사진 파일은 열지 않는다(경로 문자열만)
structure: plan.py 0→4, pick_zones.py 0→4, 최대 전이 2
checks: 공통 + .venv/bin/python -m unittest discover -s tests -p 'test_self_agreement_pick.py' -v
experiment: 없음
handoff: 전체 SHA, 파일, 함수 수·경로, 시험 로그·종료 코드, 미검증, 위험, 롤백(revert)
```

### 계약 B

```text
task_id: self-agreement-round-pages
owner:
status: assigned 전 (초안, A 통합 뒤)
base_sha: A 통합 뒤 확정
branch: 배정 때 확정
goal: 같은 크롭·문구로 두 회차 화면이 만들어지고 2차가 어긋나면 쓰기 전에 거절한다
allowed_files:
  tools/self_agreement/screen.js (새)
  tools/self_agreement/screen.py (새)
  tools/self_agreement/make_round.py (새)
  tests/test_self_agreement_pages.py (새)
forbidden_files: 그 밖의 모든 파일(relabel_*·label_criteria·tests/*.js 포함)
contract: 1.2(key.json·답 글), 1.3의 2·4·6. 실행: python -m tools.self_agreement.make_round PLAN SELECTION ROUND OUT_DIR [FIRST_KEY]
  OUT_DIR은 새 폴더만. 쓰다가 실패하면 key.json이 없고, key.json 없는 폴더는 C가 거절한다. 2차는 FIRST_KEY 필수
  page_id = sha256(회차|쪽|기준 해시|화면 해시|그 쪽 크롭 해시 순서)의 앞 16자. write_page에 넘기는 문구 = blind.INSTRUCTIONS + 공통 안내(회차 번호 없음)
  relabel_* 의 crop은 import 시점 참조를 고정 표로 잡고 zp.crop 등 남의 전역을 바꾸지 않는다
structure: screen.js 0→6, screen.py 0→4, make_round.py 0→5, 최대 전이 4(screen.js)
checks: 공통 + .venv/bin/python -m unittest discover -s tests -p 'test_self_agreement_pages.py' -v
  + node --check tools/self_agreement/screen.js
experiment: 없음
handoff: 위와 같음 + "왕복 시험 전이라 진짜 화면 생성 조건 미충족"을 적음
```

### 계약 C

```text
task_id: self-agreement-import
owner:
status: assigned 전 (초안, B 통합 뒤)
base_sha: B 통합 뒤 확정
branch: 배정 때 확정
goal: 누른 것 = 가져온 것이 두 회차에서 시험되고, 문장·시각이 없으면 원본만 보존하고 종료 코드 2
allowed_files:
  tools/self_agreement/answers.py (새)
  tools/self_agreement/import_round.py (새)
  tests/test_self_agreement_round_trip.py (새)
forbidden_files: 그 밖의 모든 파일
contract: 1.2(round<k>.json), 1.3의 6·7. 실행: python -m tools.self_agreement.import_round PLAN ROUND_DIR STATEMENT|- OUT ANSWER...
  원본은 <OUT 폴더>/raw/<sha256>.txt, 0444, 같은 바이트가 이미 있으면 그대로 둠. 원본 보존 → 검사 → 기록 순서
  label_criteria.check(쪽의 .criteria.json, z 번호들, OUT)을 쪽마다 부른다. 사람 라벨 파일·정답 형식(mobile_corner_label_import)은 쓰지 않는다
  판단 불가·미확인은 값 그대로. 두 회차를 합치지 않는다(explicit-verdict-merge)
structure: answers.py 0→2, import_round.py 0→3, 최대 전이 3
checks: 공통 + .venv/bin/python -m unittest discover -s tests -p 'test_self_agreement_round_trip.py' -v (node 필요, 건너뛰면 "미검증")
experiment: 없음
handoff: 위와 같음 + 왕복 시험 로그의 대상 SHA
```

### 계약 D

```text
task_id: self-agreement-score
owner:
status: assigned 전 (초안, C 통합 뒤)
base_sha: C 통합 뒤 확정
branch: 배정 때 확정
goal: 제안서 10·11절의 수와 다음 행동 표가 3.2·3.3의 손계산과 같고 항상 한 행만 나온다
allowed_files:
  tools/self_agreement/stats.py (새)
  tools/self_agreement/decide.py (새)
  tools/self_agreement/score_rounds.py (새)
  tests/test_self_agreement_score.py (새)
  tests/test_self_agreement_flow.py (새, 끝에서 끝까지)
forbidden_files: 그 밖의 모든 파일(score.py·check.py 포함. 읽어 부르기만 함)
contract: 1.3의 5·7~12, 3.2, 3.3. 실행: python -m tools.self_agreement.score_rounds PLAN SELECTION ROUND1 ROUND2 OUT
  계산 종료 0, 입력 문제(파일 없음·형식·plan/selection 해시 불일치) 종료 2. 해시 불일치도 이유에 1행 조건으로 적되 result.json은 만들지 않는다
  그 밖의 1행(주체·간격·기준·화면·크롭)은 종료 0, result.json에 row=1과 이유
  출력 문구: "확정 쌍 일치율"(정확도라고 쓰지 않음), 구역 폭의 카드 환산은 "미측정"(제안서 11절 c), 11절 (b) 한계 다섯 줄 포함
  어느 행도 실험·라벨 변경·재요청을 승인하지 않는다는 문장을 result.json에 넣는다
structure: stats.py 0→5, decide.py 0→4, score_rounds.py 0→4, 최대 전이 4
checks: 공통 + .venv/bin/python -m unittest discover -s tests -p 'test_self_agreement_*.py' -v
  + 기존 tests/test_corner_rejudge.py, tests/test_corner_chance_check.py (재사용 식이 그대로인지)
experiment: 없음
handoff: 위와 같음 + 3.2 표 대조 결과
```

3.3 표의 "다른 `plan_sha256`" 줄은 `decide.row`를 직접 부른 단위 시험에서 1행, 명령 실행에서는 종료 2로 확인한다.

## 5. 위험·미결정·롤백

| 위험 | 완화 | 남는 한계 |
|---|---|---|
| 사용자 부담: 구역마다 2회(총 2 × 시작 수) | 시작 수·쪽당 수를 사용자가 정함. 도구는 권고 수를 내지 않음 | 줄이면 확정 쌍 30을 못 채워 미측정이 될 수 있다 |
| 완료 라벨 재요청 금지 | `approval_ref` 필수, 화면 생성 전 별도 승인(제안서 3·13절) | 프로그램은 승인 여부를 증명하지 못한다. 관리자 절차로 지킨다 |
| 모서리 기준 2026-11-24 개정 | 두 회차 모두 새로 받고 기준 해시를 대조. 과거 값과 합치지 않음 | 측정 중 정본 문구가 다시 바뀌면 `blind.INSTRUCTIONS`가 바뀌어 2차 생성이 거절되고 측정이 끝난다 |
| `<사람>` 값이 기본값으로 굳음 | 1.1의 필수 열쇠·모르는 열쇠 거절, 3.4의 기본값 금지 시험, 값은 `plan.json`에만 | 시험의 합성 값을 누가 그대로 베껴 쓰는 것은 막지 못한다. 파일에 "합성" 표시 |
| 작은 표본의 카파 | 일치율·2×2·구간과 함께만 출력. 값 쏠림은 2행. 30은 "미측정을 벗는 최소" | 30쌍이면 일치율 0.9의 윌슨 구간이 0.744~0.965다(3.2). 같은 일치율 0.9에서도 카파가 0.80과 0.35로 갈린다 |
| 부트스트랩 소표본 | 반복 수·시드 입력, 정의 불가 수 보고 | 덜 믿을 만하다(제안서 10절). 구간으로 판정하지 않음 |
| 기억·피로·확대 조건 | 순서·번호 재배열, 시각 기록 | 브라우저 확대 정도는 기록되지 않는다. 제안서 7절의 "확대 조건 동일"은 도구로 확인 불가 → 안내문 동일까지만 |
| 기기 시계 | 이상하면 1행 | 시계를 고친 것은 알 수 없다 |
| 주체 문장 | 글자 대조, 자동 삽입 없음 | AI가 문장을 넣어도 구별하지 못한다 |
| 진단 파일(`score.py`·`check.py`) 의존 | 기존 시험을 D checks에 포함 | 그 파일을 옮기거나 고치면 D가 깨진다 |

판별 가능성(`can-this-experiment-tell`): 이 도구는 라벨 진단이고 모델 가설이 아니다. ① 겨냥 묶음 0(입력 경로 진단에 한정), ② 필요 개선 카드 2장, ③ 라벨 흔들림 **미측정**(0으로 치지 않음)은 제안서 12절 그대로이며 도구를 만든다고 바뀌지 않는다.

### 사용자가 정해야 할 값

제안서 13절 표의 값 전부: 대상 칸, 모집단과 층 비율, 주 층 시작 수, 오류 층 포함과 수, 간격, 1차 새로 받기, 시드, 화면 형식, 주체 문장, `p_min`, 방향 문턱, 전체 승인. 이 설계가 더 드러낸 것:

1. **크롭**: `highres`(1000px)와 `thumbnail`(420px) 중. 제안서의 "현행 모서리 판정 화면과 같은 크롭"이 어느 화면을 뜻하는지 저장소에서 하나로 정해지지 않는다(라벨 화면은 카드 전체 800px). 추천: `highres`. 세 번째 형식이면 계약 B를 고친다.
2. 간격 상한을 둘지와 1.3의 5번 계산법.
3. 1.3의 1번 뽑기 방식(카드 같은 확률), 8번 3분류에서 미확인 제외, 11번 행별 출력.
4. 이전에 재판정했던 카드(11-21 60·60·240구역, W1 45구역 등)를 제외할지. 제안서는 정하지 않았다. 기억 효과를 줄이려면 제외가 낫지만 모집단이 줄어든다. 제외하면 제외 파일에 넣기만 하면 되고 코드 변경은 없다.
5. 쪽당 구역 수, 2차 화면을 간격 전에 만들어 둘지(도구는 막지 않고 점수 단계에서만 간격을 본다).
6. 제외 파일(봉인·독립·오류 층 카드)과 오류 층 파일을 누가 만드는지. 해당 자료를 열어야 하므로 구현 세션이 만들 수 없다.

롤백: 이 문서 커밋 revert. 구현 뒤에는 계약별 커밋을 D → C → B → A 순서로 revert(새 파일만이라 기존 기능 영향 없음). 이미 받은 답의 원본은 지우지 않는다.

## 6. 읽은 범위와 차이

**끝까지 읽음**: `AGENTS.md`(세션에 전달된 전문), `docs/AGENT_START.md`, `PAIR_CODING.md`, `docs/agent/QUALITY_RULES.md`, `LABELING_PROTOCOL.md`, 제안서, `docs/knowledge/accuracy-evidence-methods-20261125.md`, `docs/collaboration/plans/quality-threshold-proposal-20261125.md`, `docs/collaboration/plans/w1-selfagree-b-20261123.md`, `docs/collaboration/reports/w1-selfagree-b-result-20261124.md`, `docs/collaboration/tasks/label-criteria-version-20261125.md`, `tools/label_criteria.py`, `tools/mobile_corner_label_import.py`, `tools/mobile_corner_label_pages.py`, `tools/relabel_zone_pages.py`, `tools/relabel_corner_{blind,highres,repro,consensus}_pages.py`, `score.py`, `model_vs_rejudge.py`, `label-ceiling-20261121/ceiling.py`, `label-reliability-20261111/kappa.py`, `tests/test_corner_label_round_trip.py`, `tests/test_label_criteria_record.py`, `tests/test_relabel_zone_round_trip.py`, `tests/test_label_criteria_source.py`, `tests/test_label_text_regressions.py`, `tests/test_corner_rejudge.py`, `tests/label_page_press.js`, `tests/corner_page_press.js`. 공유 폴더의 R2 조사 보고서(자료로만).

**일부만**: `tools/mobile_visibility_rejudge_pages.py`(25행~끝과 앞 24행), `corner-chance-check-20261124/check.py`(1~64행), `tools/ebay_back_retest.py`(1~60행), `tests/test_corner_chance_check.py`(1~40행), `corner-blind-rejudge-20261121.md`(앞 50행, 긴 줄은 900자까지), `corner-error14-breakdown-20261124.md`(앞 40행).

**안 읽음**: 사진·라벨·`artifacts/` 전체, 봉인·독립·`cohort2` 자료, `tests/test_visibility_blind_round_trip.py`, `tools/relabel_consistency_page.py` 본문, `COMMON_EXPERIMENT_RECORDS.md`(실험 아님), `HTML_REPORTING.md`·`PROGRESS_CRITERIA.md`(성과 보고 아님). 저장소 코드와 시험은 실행하지 않았다(계산은 `python3 -I`에서 식을 다시 써서 함).

**원문과 배정 프롬프트의 차이(원문·계산을 따름)**:
1. 프롬프트의 "26/1/불일치 3 → 카파 약 0.34"는 계산값과 다르다. 불일치가 2:1이면 8/23=0.3478, 3:0이면 26/71=0.3662다. 시험에는 정확한 분수를 쓴다.
2. "14/13/불일치 3 → 카파 0.8"은 불일치가 2:1일 때만 정확히 0.8이고 3:0이면 0.8018이다.
3. 프롬프트는 문장·시각이 없으면 가져오기가 종료 코드 2로 중단, 제안서 8절은 "주체 미확인, 참고로만"이다. 1.3의 7번처럼 가져오기는 멈추고 점수도 1행으로 보내 둘을 함께 지킨다. 문장 없는 답의 참고용 일치율은 이 도구가 내지 않는다.
4. 프롬프트는 기존 도구 `mobile_corner_label_import.py`를 읽기 대상에 넣었지만 정답을 쓰는 도구라 재사용하지 않는다.
5. 프롬프트의 "다음 행동 표 6행"은 제안서 11절 (d)와 같다.

기존 규칙과의 충돌은 찾지 못했다. HTML 없음: 새 평가·추론이 없고 화면도 만들지 않아 `AGENTS.md`의 성능 평가 HTML 조건에 해당하지 않는다.
