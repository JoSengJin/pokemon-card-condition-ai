# 자기 일치도 도구 2판 — 오탐 층·카드 단위 계산의 설계와 개발 계약 초안 (2026-11-25)

**설계 초안이며 어떤 승인도 아니다.** 재판정 요청·구역 목록·화면·수집·실험의 승인이 아니고 아래 계약은 배정 전 초안이다. 완료 라벨 재요청을 포함한 전체 승인은 아직 없다. 정확도 변화 없음, 진척 변화 없음. 기존 규칙과 부딪히면 기존 규칙이 우선한다.

**`<사람>` 값은 `plan.json` 인자로만 받는다.** 코드·이 문서·시험의 기본값에 박지 않는다. 아래 손계산의 숫자는 모두 합성 입력이며 제안값이 아니다.

task_id `self-agreement-tooling-v2-design-20261125` / owner Claude Opus 5.5(설계만) / base_sha `e91a8182031116c2edba0a840fda0ecb626f03fd`. 시작 한 줄: 목표=설계 문서 4개 도구에 층 태그와 카드 단위 계산을 더하는 변경의 설계와 분할된 개발 계약 / 하지 않을 것=코드 작성·재판정 요청·실제 화면·구역 목록·사진·라벨·artifacts 열람·실험·승인 / 완료 기준=허용 파일 1개 커밋 / 확인 방법=checks.

가리키는 문서: "1판"=`docs/collaboration/tasks/self-agreement-tooling-design-20261125.md`, "제안서"=`docs/collaboration/plans/label-self-agreement-prereg-20261125.md`, 도구 A=선정, B=화면, C=가져오기, D=점수. 오탐=정상 카드를 모델이 결함으로 잘못 표시한 것. 회차=같은 판정자의 1차·2차 판정.

적용 규칙: `short-request-reading`, `label-agreement-watch`, `can-this-experiment-tell`, `label-provenance`, `single-source-criteria`, `explicit-verdict-merge`, `label-screen-round-trip`, `regression-for-every-fix`, `chance-check`. 스킬: `verification-before-completion`, `writing-plans`(이 계약 안에서만).

## 1. 변경 요약

| 보강(2026-11-25 사용자 채택) | 결론 |
|---|---|
| (가) 주 층과 오탐 층의 층 태그 | 새 열쇠와 새 태그 `fp`를 둔다. 기존 `error` 층은 그대로 둔다. A와 D만 바뀐다 |
| (나) 시작 구역 80 | **코드 변경 없음.** `main_count`는 1 이상 정수를 받는 plan 값이고(`plan.py:19` `pos`, `pick_zones.py:44-54`), 코드에 다른 수가 박혀 있지 않다 |
| (다) 카드 단위 판정 | 새 파일 `cards.py`. 오탐 층의 카드에서만 직접 계산한다. 구역 e를 카드 장수로 곱해 옮기지 않는다 |

간격(중심 10일, 허용창 7~14일)도 **코드 변경 없음**이다. `min_interval_hours`=168, `max_interval_hours`=336이 plan에 적을 후보이고 "중심 10일"은 2차를 여는 날의 안내일 뿐 열쇠가 아니다. 하한은 1차의 가장 늦은 제출, 상한은 1차의 가장 이른 제출부터 재므로(1판 1.3의 5번) 한 회차를 여러 날에 나눠 제출하면 허용창이 그만큼 좁아진다. 제안서 13절의 2주 제안은 이 값으로 대체됐다.

80이 뜻하는 것: 카드마다 구역 하나이므로 제외 카드를 뺀 **카드 80장**이 모집단에 있어야 하며 모자라면 A가 거절한다(모집단 크기는 열지 않아 미확인). 확정 쌍 30을 채우려면 확정 비율이 30/80=0.375 이상이어야 한다(계산일 뿐 예상치가 아니다).

### 1.1 왜 `error_layer`를 다시 쓰지 않고 새 열쇠를 두는가

| | 기존 `error` (1판 1.1·1.3의 3·9번, 제안서 6절) | 새 `fp` |
|---|---|---|
| 대상 | 고정된 오류 구역(오탐 11구역·놓침 6구역) | 오탐 9장의 결정 구역과 주변 구역. 주변의 범위는 `<사람>` |
| 자르기 | 파일 앞에서 `error_count`행 | 자르지 않음. 카드가 일부만 들어가면 카드 판정이 틀려지므로 파일 행 수와 `fp_count`가 같아야 함 |
| 보고 | 확정 쌍 중 같은 답 건수만 | 구역 건수·방향과 카드 판정·뒤집힘을 별도 보고 |
| 주 지표 | 들어가지 않음 | 들어가지 않음(아래 1.2) |

같은 열쇠를 다시 쓰면 "건수만 보고"라는 사전 약속의 뜻이 바뀌고 같은 이름의 결과를 비교할 수 없게 된다. 두 층을 함께 쓸 때는 **카드가 겹치면 거절**한다(`explicit-verdict-merge`: 같은 구역을 두 번 세지 않음). 오탐 카드는 `fp`에, 놓침 카드는 원하면 `error`에 둔다.

층 태그는 `strata`와 다르다. `strata`는 이전 라벨로 무작위 층을 나누는 열쇠이고 null만 구현된 상태를 유지한다.

### 1.2 오탐 층이 주 지표에 섞이지 않게 하는 방식

1. A: 오탐 층 카드는 제외 목록에 있어야 하고 모집단에서 빠진다. 주 층 선정은 모델 출력과 무관한 시드 선정 그대로다.
2. D: 주 지표(`measures`)는 `layer == 'main'` 쌍만 받는다. `cards.py`는 `fp` 구역만 읽고 `decide.row`에 아무것도 넘기지 않는다.
3. 오탐 층에는 **카파·e·목표선·경고선을 내지 않는다.** 확정 쌍이 30을 넘어도 마찬가지다(모델 출력으로 고른 표본).
4. 시험: 오탐 층의 답을 모두 뒤집어도 `fp_layer`를 뺀 결과가 같다.

### 1.3 카드 단위를 어디에서 계산하는가

**주 층은 카드당 구역 1개라 카드 최댓값을 낼 수 없다**(제안서 6절 c, 1판 1.3의 1번). 한 구역이 정상이어도 나머지 모서리를 안 봤으므로 카드가 정상이라는 뜻이 아니다. 그래서 카드 판정은 카드의 정해진 구역을 모두 보는 오탐 층에서만 계산하고 주 층에는 "해당 없음(카드당 구역 1개)"이라고 적는다. 무작위 카드의 카드 단위 흔들림은 이 설계로도 **미측정**으로 남는다. 그것까지 원하면 주 층을 "카드당 전 구역"으로 바꾸거나 무작위 카드 층을 하나 더 두어야 하며 제안서 6절 c 변경과 새 계약이 필요하다(7절 미결정 1).

### 1.4 최댓값 규칙

구역 값 네 가지(정상·결함·불가·미확인) → 카드 값 세 가지:

| 카드 안의 구역 값 | 카드 판정 |
|---|---|
| 결함이 하나라도 있음(불가·미확인이 함께 있어도) | 결함 |
| 결함 없음, 모든 구역이 정상 | 정상 |
| 결함 없음, 불가 또는 미확인이 하나라도 있음 | 불확정 |

- 결함 우선의 근거: 기존 카드 평가는 구역 정답에 결함이 하나라도 있으면 결함 카드, 나머지를 정상 카드로 나누고 점수는 구역 최대를 쓴다(`tools/diagnostics/corner-chance-check-20261124/check.py:29-35`, `tools/experiments/corner-mlp-head-20261121/worker.py:34-44`, `corner-input-path-diagnosis-20261125.md:23`). 사용자가 채택한 문장과도 같다.
- 불확정의 근거: 미확인을 정상으로 자동 해석하지 않는다(`LABELING_PROTOCOL.md:21-22`). 불가 구역이 실제로 결함인지 모르므로 "정상"이 될 수 없고, 이미 결함이 있으면 나머지가 무엇이든 최댓값은 결함이다.
- **기존 평가와 다른 점(미결정 3)**: 기존 평가 행의 정답은 0·1뿐이라(`check.py:24`의 `r['target'] not in (0, 1)`) 미확인 구역은 행에 없고, 남은 행만으로 정상 카드가 된다. 이 설계의 "불확정"은 기존 평가보다 엄격하다. 그래서 규칙은 `plan.json`의 `card_rule`에 사용자가 확정해 적으며 `"any_defect_unknown_blocks"` 하나만 구현한다.
- 이 규칙은 `explicit-verdict-merge`의 "민감 병합"(한 대상을 여러 번 본 답을 합치는 것)이 아니다. 한 회차 안에서 서로 다른 구역을 카드로 묶는 것이고 두 회차의 답은 합치지 않는다.

뒤집힌 카드 = 두 회차 모두 정상 또는 결함인 카드(확정 카드 쌍) 중 값이 다른 카드. 한 회차라도 불확정이면 "불확정 쌍"으로 따로 세고 뒤집힘에도 안 뒤집힘에도 넣지 않는다.

### 1.5 카드 단위 부트스트랩

오탐 층 카드(`group`)를 복원 추출하고 뽑힌 카드의 구역을 모두 함께 가져온다. 같은 추출에서 두 값을 낸다: 뒤집힌 카드 / 확정 카드 쌍, 뒤집힌 구역 / 확정 구역 쌍. 반복 수·시드는 기존 `bootstrap_draws`·`seed_bootstrap`을 쓰되 `cards.py` 안에서 새 난수기를 만들어 주 층 구간을 바꾸지 않는다. 백분위 2.5·97.5, 분모 0인 재표집은 빼고 그 수를 적는다(1판 1.3의 10번과 같은 방식).

카드가 모두 안 뒤집히거나 모두 뒤집히면 이 구간의 폭은 0이 되며 **흔들림 없음의 증거가 아니다.** 그래서 윌슨 구간과, 0장일 때의 정확 양측 95% 상한 `1-0.025**(1/n)`을 함께 적는다(0/9이면 0.3363).

## 2. 영향받는 파일과 함수 분할

함수 수는 `e91a818`에서 다시 셌다(`ast`로 `FunctionDef`·`AsyncFunctionDef`·`Lambda`, JS는 `function` 5개와 화살표 1개). 프롬프트 값과 모두 같다.

| 파일 | 함수 전→후 | 변경 | 최대 전이 |
|---|---|---|---|
| `plan.py` (A) | 4→4 | `SPEC`은 그대로 두고 `SPEC2` 추가, `check`가 schema로 고름, 열쇠 사이 조건 추가 | `pick_zones.main → load → check` 2 |
| `pick_zones.py` (A) | 4→5 | `layer_rows(path, sha, excluded)` 추가(`error`·`fp` 공통: 읽기와 제외 목록 대조), `number`에 `fp` 행, `main`에 인자 하나 | `main → layer_rows → rows → cfg.file_sha` 3 |
| `cards.py` (D, 새) | 0→5 | `judge(values)`, `by_card(zones, first, second)`, `boot(cards, draws, seed)`, `cut_status(flips, unknown, cut)`, `summary(selection, first, second, plan)` | `score_rounds.main → report → cards.summary → boot` 3 |
| `score_rounds.py` (D) | 4→4 | `pairs`의 허용 태그에 `fp`, `report`에서 층 대조와 `fp_layer` 붙이기 | `main → report → measures → stats.interval → stats.kappa` 4(변화 없음) |
| `stats.py` 5, `decide.py` 4, `screen.py` 4, `screen.js` 6, `make_round.py` 5, `answers.py` 2, `import_round.py` 3 | 변화 없음 | **변경 없음** | 변화 없음 |

- 카드 계산을 새 파일에 두는 이유: `tests/test_self_agreement_score.py:330-333`가 `stats=5, decide=4, score_rounds=4`를 정확히 고정하므로 기존 시험을 고치지 않으려면 함수를 더할 수 없고, 카드 계산은 책임도 다르다. 모든 파일이 7 이하라 더 쪼갤 것이 없다.
- `cards.py`는 `stats.WILSON`과 `stats.MCNEMAR`(모듈 상수)를 쓰고 자기 구간은 `boot`에서 낸다. `stats.interval`은 카파 전용이라 쓰지 않는다. 경로 `summary → WILSON`도 3이다. 재귀·클래스 없음.
- B·C가 안 바뀌는 근거: `make_round.py`는 구역 행의 열쇠 집합만 보고 `layer` 값을 화면에 쓰지 않으며, `import_round.py`는 `layer`를 읽지 않는다. 둘 다 `cfg.load`로 schema 2 plan을 읽을 뿐이다. 답 글·`key.json`·`round<k>.json` 형식도 그대로라 `label-screen-round-trip` 왕복 시험이 그대로 유효하다. 다만 B·C가 **schema 2 plan으로 도는 것**은 새 흐름 시험에서 확인해야 하며 그 전에는 미검증이다.
- 화면 문구는 건드리지 않는다(`single-source-criteria`). 기준·크롭 해시 기록도 그대로다(`label-provenance`).

기존 시험(합계 95: pick 33, pages 20, round_trip 11, score 31)은 **한 줄도 고치지 않고** 통과해야 한다. 흐름 시험 `tests/test_self_agreement_flow.py`(4개)는 base에 없고 커밋 `22aa32bca5eb8e293664059291f3f2160c5bec08`(부모=base)에 있으며 통합 전이다. 그 시험도 고치지 않고 schema 1 그대로 통과해야 한다.

## 3. 데이터 형식 변경

### 3.1 `plan.json`: schema로 가른다

지금 규칙은 "모든 열쇠 필수·모르는 열쇠 거절"이라 새 열쇠를 그냥 더하면 기존 plan과 시험이 모두 깨지고, 선택 열쇠로 두면 기본값 금지를 어긴다. 그래서 **`schema`가 1이면 기존 열쇠 집합 그대로, 2면 아래를 더한 집합**을 요구한다. 각 schema 안에서는 전부 필수이고 모르는 열쇠·허용 밖 null은 거절한다. `schema`가 없거나 1·2가 아니면 거절한다. schema 1에 새 열쇠가 있으면 모르는 열쇠로, schema 2에 빠지면 빠진 열쇠로 거절된다. 새 측정은 schema 2로만 시작한다(프로그램이 강제하지 않는 관리자 절차).

schema 2에 추가되는 열쇠:

| 열쇠 | 뜻 | null |
|---|---|---|
| `layers` | 이 측정에 있는 층 태그 목록. `["main"]`, `["main","error"]`, `["main","fp"]`, `["main","error","fp"]` 중 정확히 하나. 모르는 태그·중복·순서 다름·`main` 누락은 거절 | 불가 |
| `fp_layer_sha256` | 오탐 층 입력 파일의 해시 | 예 |
| `fp_count` | 오탐 층 구역 수. 파일 행 수와 같아야 함 | 불가(층이 없으면 0) |
| `fp_zones_per_card` | 오탐 층에서 카드당 구역 수. 모든 카드가 이 수여야 함 | 층이 없을 때만 |
| `card_rule` | `"any_defect_unknown_blocks"`만 받음(1.4) | 층이 없을 때만 |
| `card_flip_cut` | 뒤집힘 컷(장수, 1 이상 정수). null이면 컷 판정을 하지 않음(4절) | 예 |

열쇠 사이 조건: `layers`에 `fp`가 있음 ⇔ `fp_layer_sha256`이 null 아님 ⇔ `fp_count`>0 ⇔ `fp_zones_per_card`와 `card_rule`이 null 아님. 층이 없으면 `card_flip_cut`도 null. `fp_count`는 `fp_zones_per_card`의 배수. `layers`에 `error`가 있음 ⇔ `error_layer_sha256`이 null 아님. 나머지 열쇠와 조건은 1판 1.1 그대로다.

카드당 모서리는 네 곳이다(`LABELING_PROTOCOL.md:11`의 "네 귀퉁이", `card_condition/regions.py:11`의 `corner_defect` 네 area). 다만 주변 구역의 범위가 `<사람>`이라 값은 plan에만 적는다. 네 곳보다 적게 잡으면 카드 판정은 "제시한 구역 안의 판정"이고 출력의 구역 수로 드러난다.

### 3.2 입력 행, 선정, 회차, 결과

- **오탐 층 파일**: 모집단과 같은 다섯 열쇠(`id, group, area, image, box`)만. 점수·이전 라벨·결정 구역 표시가 있으면 거절한다(판정자와 선정에 모델 출력을 넣지 않음). 카드 안에서 `area`가 서로 다르고 `image`가 하나여야 한다. 사진 두 장짜리 카드는 거절하며 필요하면 새 계약이다.
- **A 명령**: schema 1은 기존 인자 5개 그대로. schema 2는 `PLAN POPULATION EXCLUDE ERROR_LAYER|- FP_LAYER|- OUT` 6개. schema와 인자 수가 안 맞거나 `-`와 해시 null 여부가 다르면 거절.
- **A 검사**: 오탐 층 행 전부의 `group`이 제외 목록에 있음, `error`와 `fp`의 `group`이 안 겹침, 세 층을 합쳐 `id` 중복 없음, 행 수 = `fp_count`, 카드당 행 수 = `fp_zones_per_card`.
- **`selection.json`**: 모양은 그대로이고 `layer` 값에 `'fp'`가 더해진다. 번호 섞기는 `main → error → fp` 순으로 이어 붙인 뒤 같은 난수기를 쓰므로 `fp`가 없으면 기존과 **바이트가 같다**(회귀 시험).
- **`key.json`·답 글·`round<k>.json`**: 변경 없음. 층은 `selection.json`에만 있고 화면에는 없다.
- **`result.json`**: schema 1이면 지금과 열쇠가 같다. schema 2면 최상위 열쇠 `fp_layer` 하나만 더한다. `card_conversion`은 `'미측정'` 그대로다(구역 폭을 카드로 바꾸지 않음).

`fp_layer`(층이 없거나 1행이면 null):

```text
zones: {start, first_unusable, second_unusable, one_round_only, confirmed_pairs, same_answer, b, c}
cards: {start, zones_per_card, rule, first:{정상,결함,불확정}, second:{정상,결함,불확정},
        confirmed_pairs, unchanged, b, c, flips, unknown_pairs,
        wilson95, exact_upper(0장일 때만), exact_two_sided_p}
bootstrap: {draws, card_flip_rate:{lo,hi,undefined}, zone_flip_rate:{lo,hi,undefined}}
flip_cut: {cut, status}
main_layer_cards: '해당 없음(카드당 구역 1개)'
limits: [4절의 한계 문장]
```

`b`=1차 정상→2차 결함, `c`=반대. D는 이전 정답을 읽지 않으므로 "이전 라벨과 비교해 몇 장이 바뀌었다"는 내지 않는다.

## 4. 판정 규칙과의 관계

- **다음 행동 표 6행(제안서 11절 d)은 바꾸지 않는다.** 오탐 층·카드 결과는 어느 행의 조건에도 들어가지 않고 `fp_layer`로만 낸다. `decide.py`도 안 바뀐다. 1행(주체·간격·기준·화면·크롭)은 회차 전체가 무효라 `fp_layer`도 null이다. 2~6행은 주 층 이야기이므로 `fp_layer`를 그대로 낸다.
- 어느 행도, 컷 상태도 **개선·실험·라벨 변경·재요청을 자동 승인하지 않는다.** 기존 `not_approval` 문장을 유지하고 `fp_layer.limits`에도 "컷 상태는 어떤 것도 승인하지 않는다"를 넣는다.
- **뒤집힘 컷은 `plan.json`의 `card_flip_cut`에만 적는다**(`<사람>`, 미정). 결과를 본 뒤 바꾸면 `plan_sha256`이 달라져 앞 단계 산출물과 어긋난다. 세는 값은 카드 뒤집힘 총수 `flips = b + c`이며 불확정을 버리지 않는다:

| 조건(위에서부터) | `status` |
|---|---|
| 컷이 null | `컷 미정, 판정 없음` |
| `flips` ≥ 컷 | `컷 이상` |
| `flips` + `unknown_pairs` < 컷 | `컷 미만` |
| 그 밖 | `판정 불가(불확정 카드)` |

- 오탐 장수의 2장 차이는 **순변화**이고 `flips`는 **총변화**라 같은 수가 아니다. 그래서 b와 c를 함께 낸다. 컷을 총수로 할지 `|b−c|`로 할지는 사용자가 정한다. 총수가 아니면 계약 D를 고친다. 도구는 "2장이 흔들림 안이다/밖이다"라는 문장을 내지 않고 건수와 컷 상태만 낸다.
- `fp_layer.limits`에 넣을 한계:
  1. 모델이 틀렸다고 본 카드를 골라 잰 것이다. 이전 라벨의 실수가 섞여 있으면 다시 재는 것만으로 값이 옮겨 갈 수 있고, 무작위 카드의 흔들림이 아니다. 불일치 건만 다시 본 결과로 정답표를 고치지 않는다(지식 문서 §2의 불일치 재판정 행).
  2. 지금 오탐인 카드만 본다. 다른 정상 카드에서 새 오탐이 생기거나 결함 카드가 바뀌는 크기는 보이지 않는다.
  3. 카드 수가 작다. 카드 9장이면 2/9의 윌슨 95%가 0.0632~0.5474이고, 한쪽으로만 2장이 뒤집혀도 정확 양측 p=0.5다(표본 크기에 관한 계산이며 예상치가 아님).
  4. 카드 값은 제시한 구역 안의 최댓값이고 불확정 카드는 빠진다.
  5. 컷 상태는 어떤 것도 승인하지 않는다.
- 판별 가능성(`can-this-experiment-tell`)의 세 장수: ① 0(입력 경로 진단 한정, 다른 가설에서는 미측정) ② 카드 2장 ③ 라벨 흔들림 **미측정**은 제안서 12절 그대로다. 측정이 끝나도 오탐 층의 `flips`는 선택된 카드의 값이라 ③을 채운 것으로 쓰지 않고 참고로만 적는다.
- 제안서 6절 보조 층은 "건수만 보고"이고 카드 단위 계산이 없다. 오탐 층은 그보다 많이 보고하므로 **측정 시작 전에 제안서를 개정해 사전 고정해야 한다.** 이 문서는 제안서를 고치지 않는다(관리자 작업).

## 5. 시험 계획 (합성만)

가짜 ID와 시험 안에서 만든 그림만 쓴다. 새 시험은 모두 새 파일이다. node가 없어 건너뛰면 "미검증"이다.

### 5.1 카드 손계산 대조

정=정상, 결=결함, 불=불가, 미=미확인. 카드당 4구역, 6장. 계산은 손과 `python3 -I`로 했다(저장소 코드는 실행하지 않음).

| 카드 | 1차 | 2차 | 카드 1차→2차 | 확정 구역 쌍 / 구역 b / c |
|---|---|---|---|---|
| K1 | 정정정결 | 정정정정 | 결함→정상 (c) | 4 / 0 / 1 |
| K2 | 정정정정 | 정결정정 | 정상→결함 (b) | 4 / 1 / 0 |
| K3 | 결정정정 | 정정결정 | 결함→결함, **구역 2개가 뒤집혀도 카드는 그대로** | 4 / 1 / 1 |
| K4 | 정정불결 | 정정불정 | 결함→불확정 (불확정 쌍) | 3 / 0 / 1 |
| K5 | 결불정정 | 결정정미 | 결함→결함 | 2 / 0 / 0 |
| K6 | 정정정정 | 정정정정 | 정상→정상 | 4 / 0 / 0 |

- 카드 기대값: start 6, first 정상 2·결함 4·불확정 0, second 정상 2·결함 3·불확정 1, 확정 카드 쌍 5, unchanged 3, b=1, c=1, flips=2, unknown_pairs=1, 2/5 윌슨 0.1176~0.7693, p=1.
- 구역 기대값: start 24, first_unusable 2, second_unusable 2, one_round_only 2, 확정 쌍 21, same_answer 16, b=2, c=3.
- 컷: 2→`컷 이상`, 3→`판정 불가(불확정 카드)`(2+1=3이 3 미만이 아님), 4→`컷 미만`(3<4), null→`컷 미정, 판정 없음`.
- 구역 뒤집힘률 5/21에 카드 6장을 곱하면 약 1.43인데 실제 뒤집힌 카드는 2다. 곱으로 옮기면 틀린다는 회귀 입력으로 남긴다.
- `judge`: 네 값에서 4개를 중복 허용해 뽑은 모든 순서(256가지)를 돌려 1.4의 표와 대조하고 순서를 바꿔도 같은지 본다. 빈 목록은 `ValueError`(빈 카드를 정상으로 만들지 않음).
- 0/9: 윌슨 상한 0.2991과 정확 양측 상한 0.3363을 섞어 쓰지 않는다. 0장이면 부트스트랩은 [0, 0]이고 윌슨이 함께 있다.
- 부트스트랩: 확정 카드 2장(하나만 뒤집힘)의 재표집 분포는 0(1/4), 0.5(1/2), 1(1/4)이라 반복이 충분하면 구간이 [0, 1]이다. 같은 시드 같은 값, 카드 입력 순서를 바꿔도 같은 값, 전부 불확정이면 lo·hi null과 undefined=draws. 카드의 구역이 통째로 함께 뽑히는지 구역 수가 다른 합성 카드로 확인.

### 5.2 주 지표 불변과 층 대조 (D)

- 오탐 층의 답을 모두 뒤집거나 `fp` 카드를 늘려도 `fp_layer`를 뺀 `result.json` 내용이 같다(행·카파·구간 포함).
- 주 층이 2행(확정 쌍 29)이어도 `fp_layer`는 나온다. 1행이면 null.
- `fp` 확정 구역 쌍이 30을 넘어도 카파·e·목표·경고 낱말이 `fp_layer`에 없다.
- schema 1 selection에 `fp` 태그, schema 2에서 `layers`와 selection의 태그 집합이 다름, 모르는 태그(`'x'`) → 모두 종료 2. schema 1 result의 열쇠 집합은 기존 그대로.
- 출력·소스에 "정확도"·"개선"·`plan.get(`·`default=`가 없고, `cards.py` 함수 수 5, `score_rounds.py` 4.

### 5.3 선정 (A)

- 기존 `SPEC`(schema 1)으로 만든 선정이 변경 전과 바이트가 같다. 변경 전 커밋에서 같은 합성 입력으로 뽑은 선정의 SHA-256을 시험 상수로 둔다.
- schema 2 새 열쇠를 하나씩 빼면 거절, 모르는 열쇠 거절, 표 밖 null 거절, schema 1에 새 열쇠 거절, `schema` 없음·3·null·true·목록 거절.
- `layers`: 누락·빈 목록·`['fp']`·모르는 태그·중복·순서 다름·문자열 거절. 3.1의 조건을 하나씩 어긴 경우 거절.
- 오탐 층: 해시 다름, 행 수 ≠ `fp_count`, 카드당 수 다름, 카드 안 `area` 중복, 사진 두 장, 제외 목록에 없는 카드, `error`와 같은 카드, `id` 중복, `target`·`score` 열쇠 → 거절하고 출력 없음.
- 오탐 층이 있어도 주 층의 `id` 집합은 없을 때와 같다(선정 난수가 먼저 쓰임).

### 5.4 끝에서 끝까지

새 `tests/test_self_agreement_fp_flow.py`. 합성 모집단과 오탐 카드 → A(schema 2) → B 두 회차 → 실제 `screen.js` 누르기 → C → D. 기존 `tests/test_relabel_zone_round_trip.py`의 `run`을 부른다. 확인: 누른 것 = 가져온 것(불가·미확인 포함), 5.1 표가 화면을 거쳐 같은 수로 나옴, 주 층 14/13/2/1이 6행·카파 4/5 그대로, 화면 글(base64 제거)에 `fp`·`layer`·카드·구역 신원이 없음, 2차 순서가 다름. 기존 `test_self_agreement_flow.py`는 고치지 않으며 schema 1 하위 호환 시험으로 남는다.

### 5.5 빠지기 쉬운 입력

1. 결함과 불가가 섞인 카드를 불확정으로 잘못 떨어뜨림(K4의 1차).
2. 불확정 카드를 안 뒤집힘으로 셈(K4).
3. 같은 카드 구역이 입력에서 떨어져 있거나 화면 쪽이 갈려도 `group`으로 묶임.
4. `layers`에는 `fp`가 있으나 selection에 한 구역도 없음 → 거절.
5. 컷이 확정 카드 쌍 수보다 큼 → `컷 미만` 또는 `판정 불가`이며 오류가 아님.

## 6. 개발 계약 초안 3개

**의존 순서: V2-A → V2-D → V2-F. 앞 계약이 main에 통합된 뒤 다음 계약을 배정한다.** 흐름 시험 `22aa32bca5eb8e293664059291f3f2160c5bec08`의 통합이 먼저다(각 checks의 하위 호환 확인 대상). V2-D는 `cfg.load`가 schema 2를 읽어야 명령 시험을 할 수 있어 V2-A 뒤다. 파일 집합은 서로 겹치지 않는다. 배정 때 관리자가 base_sha(검증된 최신 origin/main)와 branch를 확정하며 owner는 비워 둔다.

**각 계약 공통 문구: 진짜 구역 목록·화면·수집은 이 계약에 없다. 별도 단계이며 사용자의 `<사람>` 값 확정과 전체 승인(완료 라벨 재요청 포함) 뒤에만 할 수 있다. 도구가 완성된 것은 그 승인이 아니다.**

공통 금지: 하위 에이전트, 학습·추론·실험·`./experiment`·`./review`, 외부 호출, 사람 재판정 요청, 통합·push, 허용 밖 파일 수정, 기존 시험 수정, `data/`·`artifacts/`·사람 라벨·사진 열람, 봉인 468장·독립 350장·이름에 `cohort2`가 든 자료, 전체 시험 묶음 강제.

공통 checks(`B`=그 계약의 base_sha, `T`=커밋):
1. `git diff --check B T` 종료 0.
2. `git diff --name-status B T`가 allowed_files와 같고 새 파일만 `A`, 표시한 기존 파일만 `M`.
3. 계약별 시험 종료 0(건너뜀 수 보고).
4. `.venv/bin/python -m unittest discover -s tests -p 'test_self_agreement_*.py'` 종료 0(기존 95개와 흐름 4개 포함, 건너뜀 수 보고).
5. 1판 공통 checks 4번의 함수 수 명령으로 바꾼 `.py`마다 7 이하. 호출 경로는 2절 표와 손으로 대조.
6. `.venv/bin/python -m unittest discover -s tests -p 'test_label_criteria_source.py'`와 `-p 'test_label_text_regressions.py'` 종료 0.
7. `git status --short` 빈 출력.

### 계약 V2-A

```text
task_id: self-agreement-v2-plan-pick
owner:
status: assigned 전 (초안)
base_sha: 흐름 시험 통합 뒤 확정
branch: 배정 때 확정
goal: schema 2 plan과 오탐 층 선정이 동작하고 schema 1의 결과는 바이트까지 그대로다
allowed_files:
  tools/self_agreement/plan.py (수정)
  tools/self_agreement/pick_zones.py (수정)
  tests/test_self_agreement_fp_pick.py (새)
forbidden_files: 그 밖의 모든 파일
contract: 3.1 전부, 3.2의 오탐 층 파일·A 명령·A 검사·selection.json. 호출자: make_round·import_round·score_rounds의 cfg.load(반환 형식 유지)
  SPEC은 schema 1 그대로 두고 SPEC2를 둔다. 실패는 지금처럼 종료 2와 이유 한 줄, 출력 파일 없음
structure: plan.py 4→4, pick_zones.py 4→5, 최대 전이 3(main → layer_rows → rows → cfg.file_sha)
checks: 공통 + 5.3 전부(-p 'test_self_agreement_fp_pick.py' -v)
experiment: 없음. 진짜 목록은 별도 단계(공통 문구)
handoff: 전체 SHA, 파일, 함수 수·경로, 시험 로그·종료 코드, 미검증, 위험, 롤백(revert)
```

### 계약 V2-D

```text
task_id: self-agreement-v2-cards
owner:
status: assigned 전 (초안, V2-A 통합 뒤)
base_sha: V2-A 통합 뒤 확정
branch: 배정 때 확정
goal: 오탐 층의 카드 판정·뒤집힘·부트스트랩·컷 상태가 5.1 손계산과 같고 주 지표와 행은 바뀌지 않는다
allowed_files:
  tools/self_agreement/cards.py (새)
  tools/self_agreement/score_rounds.py (수정)
  tests/test_self_agreement_fp_cards.py (새)
forbidden_files: 그 밖의 모든 파일(stats.py·decide.py 포함. 읽어 부르기만 함)
contract: 1.2~1.5, 3.2의 result.json, 4절. 명령과 종료 코드는 그대로(PLAN SELECTION ROUND1 ROUND2 OUT)
  schema 1이면 result.json 열쇠가 지금과 같다. schema 2면 fp_layer 하나만 더한다. decide.row에 넘기는 값은 그대로다
  사람 라벨·이전 정답을 읽지 않는다
structure: cards.py 0→5, score_rounds.py 4→4, 최대 전이 4(기존 경로). 새 경로는 3(main → report → cards.summary → boot)
checks: 공통 + 5.1·5.2 전부(-p 'test_self_agreement_fp_cards.py' -v) + 기존 tests/test_corner_rejudge.py, tests/test_corner_chance_check.py
experiment: 없음. 진짜 답의 점수는 별도 단계(공통 문구)
handoff: 위와 같음 + 5.1 표 대조 결과
```

### 계약 V2-F

```text
task_id: self-agreement-v2-flow
owner:
status: assigned 전 (초안, V2-D 통합 뒤)
base_sha: V2-D 통합 뒤 확정
branch: 배정 때 확정
goal: schema 2 흐름이 합성 자료에서 A→B→C→D로 끝까지 돌고 화면에 층·신원이 드러나지 않는다
allowed_files:
  tests/test_self_agreement_fp_flow.py (새)
forbidden_files: 그 밖의 모든 파일(도구 포함. 결함을 찾으면 고치지 말고 실패 입력과 함께 보고)
contract: 5.4. B·C의 코드는 바꾸지 않는다
structure: 도구 변경 없음
checks: 공통 + -p 'test_self_agreement_fp_flow.py' -v (node 필요, 건너뛰면 "미검증")
experiment: 없음. 왕복 시험이 main에서 통과했다는 로그(대상 SHA 포함)가 있기 전에는 진짜 화면을 만들지 않는다(공통 문구)
handoff: 위와 같음 + 왕복 시험 로그의 대상 SHA
```

## 7. 위험·미결정·롤백

| 위험 | 완화 | 남는 한계 |
|---|---|---|
| 오탐 층은 모델 출력으로 고른 표본 | 주 지표와 분리(1.2), 카파·e 없음, 한계 문장 | 결과를 본 사람이 "2장은 흔들림"이라고 읽는 것은 막지 못한다 |
| 카드 9장 | 윌슨·정확 상한·정확 검정을 함께 보고 | 판정력이 매우 낮다. 5대0도 p=0.0625, 6대0이어야 0.03125다 |
| 무작위 카드의 카드 흔들림 미측정 | 주 층에 "해당 없음" 명시 | 새 계약 없이는 모른다(미결정 1) |
| 같은 카드 구역 여러 개를 한 회차에 봄 | 번호·순서 섞기 | 같은 카드임을 알아볼 수 있고 앞 구역 답이 뒤에 영향을 줄 수 있다. 떨어뜨려 놓지는 않는다 |
| 오탐 구역이 주 층과 같은 화면에 섞임 | 층을 숨김 | 판정자가 오탐 구역을 기억할 수 있다(제안서 6절 선행 노출). 주 층의 답도 구역 구성에 영향받을 수 있다 |
| 사용자 부담 | 총 판정 수 = 2 × (`main_count` + `error_count` + `fp_count`) | 예: 80에 카드 9장 × 모서리 4구역이면 2 × 116 = 232회(식의 예, 제안 아님) |
| 오탐 층 사진 하나가 바뀌어도 2차 생성이 거절됨 | 1판과 같은 안전 쪽 | 주 층까지 함께 멈춘다 |
| schema 1 plan도 계속 동작 | 새 측정은 schema 2만(관리자 확인) | 프로그램이 강제하지 않는다 |
| 완료 라벨 재요청 | 별도 승인 전 요청 금지 | 프로그램은 승인을 증명하지 못한다 |

### 사용자가 정해야 할 값

| # | 값 | 추천 | 정하지 않으면 |
|---|---|---|---|
| 1 | 카드 단위 계산을 오탐 층에만 둘지, 무작위 카드에도 할지 | 이번에는 오탐 층만(제안서 6절 c 유지) | 이 설계대로 오탐 층만. 무작위 카드 흔들림은 미측정 |
| 2 | 주변 구역의 범위와 `fp_zones_per_card` | 같은 카드의 네 모서리 전부. 카드 최댓값의 근거가 되는 유일한 범위 | 오탐 층 파일을 못 만들어 schema 2 측정 불가 |
| 3 | 최댓값 규칙(1.4) 확정. 기존 평가보다 엄격한 "불확정" 포함 | 그대로 확정 | `card_rule`을 못 적어 오탐 층 사용 불가 |
| 4 | 뒤집힘 컷 값과 세는 방식(총수 b+c 또는 순변화 `\|b−c\|`) | 값은 근거 없음. 방식은 총수(b·c를 함께 봄) | null로 적으면 건수만 보고하고 컷 판정 없음. 결과 뒤에 정한 컷은 소급하지 않음 |
| 5 | 층 비율(주 층 80 대 오탐 층 수)과 오탐 층의 최종 카드 목록 | 고정된 9장(`corner-error14-breakdown-20261124.md`) | 해시를 못 고정해 선정 불가 |
| 6 | 놓침 카드를 `error` 층으로 함께 둘지 | 이번 질문과 달라 두지 않음 | `layers`에서 `error`를 빼고 `error_layer_sha256` null |
| 7 | 오탐 층·제외·모집단 파일을 만들 담당 | 관리자가 지정 | 측정 시작 안 함. 구현 세션은 자료를 열 수 없다 |
| 8 | 제안서 개정(6·11·12절)과 전체 승인 | 측정 전에 개정 후 승인 | 어떤 요청·화면·수집도 하지 않음 |

그 밖의 1판·제안서의 `<사람>` 값(시드 3개, 크롭, 쪽당 구역 수, 주체 문장, `p_min`, 방향 문턱, 간격 계산법, 이전 재판정 카드 제외 등)은 그대로 남아 있다.

롤백: 이 문서 커밋 revert. 구현 뒤에는 V2-F → V2-D → V2-A 순서로 revert하면 schema 1 도구로 돌아간다. 이미 받은 답의 원본은 지우지 않는다.

## 8. 읽은 범위와 차이

**끝까지 읽음**: `AGENTS.md`(세션에 전달된 전문), `docs/AGENT_START.md`, `PAIR_CODING.md`, `docs/agent/QUALITY_RULES.md`, `LABELING_PROTOCOL.md`, 1판, 제안서, 지식 문서(`docs/knowledge/accuracy-evidence-methods-20261125.md`), `tools/self_agreement/`의 모든 `.py`와 `screen.js`, `tests/test_self_agreement_*.py` 네 파일, 커밋 `22aa32bca5eb8e293664059291f3f2160c5bec08`의 `tests/test_self_agreement_flow.py`, `tools/diagnostics/corner-chance-check-20261124/check.py`, `docs/collaboration/reports/corner-error14-breakdown-20261124.md`.

**일부만**: `docs/collaboration/reports/corner-input-path-diagnosis-20261125.md`(15~30행, 85~120행), `tools/experiments/corner-mlp-head-20261121/worker.py`(34~48행), `tools/experiments/corner-card-ranking-20261121/worker.py`(32~46행), `card_condition/regions.py`(1~45행), `tools/diagnostics/corner-rejudge-20261121/score.py`(10~30행), `tools/mobile_corner_label_pages.py`·`tools/mobile_corner_label_import.py`(검색 결과), 공유 노트의 R2 보고서(앞 60행, 자료로만).

**안 읽음**: 사진·라벨·`artifacts/` 전체, 봉인·독립·`cohort2` 자료, `size.py`, `COMMON_EXPERIMENT_RECORDS.md`(실험 아님), `docs/collaboration/HTML_REPORTING.md`·`PROGRESS_CRITERIA.md`(성과 보고 아님), Superpowers 스킬 본문. 저장소 코드와 시험은 실행하지 않았다(이 worktree에 `.venv` 없음). 손계산은 `python3 -I`에서 식을 다시 써서 했다.

**원문과 배정 프롬프트의 차이(원문을 따름)**:
1. 프롬프트는 카드 판정을 어느 층에서 낼지 정하지 않았다. 원문의 주 층은 카드당 구역 1개라 카드 최댓값이 성립하지 않아 오탐 층에만 두었다(1.3, 미결정 1).
2. 프롬프트의 "하위 호환(기존 시험 통과)"과 "기본값 금지·모르는 열쇠 거절"은 열쇠를 그냥 더하면 함께 지킬 수 없다. `schema` 2로 풀었다(3.1).
3. 프롬프트의 "95개 + flow 시험"에서 flow 시험은 base에 없고 `22aa32bca5eb8e293664059291f3f2160c5bec08`에만 있다. 95개는 확인했다.
4. 제안서의 간격 2주 제안과 채택된 중심 10일·허용창 7~14일이 다르다. 사용자 결정이 뒤라 그쪽을 따르며 값은 plan에만 둔다.
5. 제안서 6절 보조 층 "건수만"은 `error` 층 그대로 두고, 더 많이 보고하는 오탐 층은 새 층으로 나눴다. 제안서 개정이 필요하다(4절).
6. 제안서 11절 c의 "카드 폭 미측정"은 유지한다. 카드 판정을 직접 세는 것이지 구역 폭을 환산하는 것이 아니다.
7. 배정 프롬프트 checks의 "B=e8..."은 오타라는 관리자 알림을 받았고 B=base_sha로 했다.

개발을 막는 기존 규칙과의 충돌은 찾지 못했다. HTML 없음: 새 평가·추론이 없고 화면도 만들지 않아 `AGENTS.md`의 성능 평가 HTML 조건에 해당하지 않는다.
