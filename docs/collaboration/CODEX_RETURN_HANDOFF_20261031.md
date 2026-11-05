# Codex 복귀 인계 — Claude가 Codex 토큰 만료 기간에 한 일 (2026-10-31)

이 문서는 사실 기록이다. 새 개발·실험·외부 호출 승인이 아니며, `AGENTS.md`·`PAIR_CODING.md`·현재 배정 task가 우선한다. 아래 수치는 모두 해당 기록 파일에서 확인한 값이고, 확인하지 못한 것은 "미확인"으로 적었다.

## Codex에게 줄 첫 프롬프트 (사용자가 전달)
> `docs/collaboration/CODEX_RETURN_HANDOFF_20261031.md`를 먼저 읽고, §6 "Codex가 결정·확인할 것" 순서대로 이어가라. Claude가 만든 `main` 커밋 28개와 미통합 브랜치 `claude/card-corner-click-review-20261031`(`f44896f`)을 검토하고, 승인된 범위에서만 개발을 계속하라.

## 1. 경계
- Codex의 마지막 커밋: `64f998b` (2026-10-30 `docs(rollback)`).
- Claude 커밋: `9af3d3b` ~ `9742511` 28개(`Co-Authored-By: Claude` 트레일러로 식별). 모두 `main`에 직접 커밋했다(`PAIR_CODING.md` §1과 다름, §4 참고). 문서 작성 시점에 `origin/main`보다 로컬 `main`이 8커밋 앞서 있다(push 안 함).
- 미통합 브랜치: `claude/card-corner-click-review-20261031`, tip `f44896f64b8eaa6b24e8a97eaac6d63938cb7c5c`, 작업 계약 `docs/collaboration/tasks/card-corner-click-review-20261031.md`, 로컬 worktree `../pokemon-card-condition-claude-card-corner-click-20261031`(상태 ready_for_review).
- 기본 checkout에서 추적되지 않는 파일 5개는 Claude가 만든 것이 아니다: `docs/collaboration/DATA_INVENTORY_20261028.md`, `docs/collaboration/reports/corner-rectify-plan-20261030.md`, `tools/corner_review_pages.py`, `tools/ebay_back_edge_review_pages.py`, `tools/ebay_pairing_review_pages.py`. 건드리지 않았다.

## 2. 한 일 요약
| 묶음 | 근거 파일 |
|---|---|
| 뒷면 엣지 구역 head(3차 = 현재 기준선) | `docs/collaboration/reports/edge-back-diagnosis-20261030.md`, 기록 `20261030T113857-2deb9558` |
| 성능 저하 요인 top3 합의(모의 협의, 합의 문서에 모의라고 표시)와 후속 실험 | `docs/collaboration/reports/performance-top3-consensus-20261030.md` |
| 같은 사진 AUC 평가 도구 | `tools/within_photo_auc.py` |
| 상자 어긋남 민감도 | `docs/collaboration/tasks/card-box-sensitivity-20261031.md` |
| 카드 찾기 기준선과 후보 계획 | `card-localization-baseline-20261031.md`, `card-localization-widen-20261031.md` |
| eBay f·g·h 수집과 검토 화면 | `tools/ebay_region_review_pages.py`(추적), g·h 검토 서버(§5) |
| 검토 화면 모서리 4점 클릭 | 미통합 브랜치(위) |

## 3. 실험 기록 (`artifacts/experiments/`, 모두 개발 val이며 독립 평가 아님)
| 기록 | 가설 ID | 상태/공통 판정 | 핵심 |
|---|---|---|---|
| `20261030T102223-16a27545`, `…111946-11f51a18` | edge-back-area-presence-head-20261030(b) | completed/false | 1·2차 head. `evaluation.json` 기준 val 놓침/오탐 각각 38/63, 54/80(AUC는 이 파일에 없어 미확인) |
| **`20261030T113857-2deb9558`** | edge-back-source-weight-20261030 | completed/false | **3차 head(현재 기준선)** val 275구역(결함 117·정상 158): AUC 0.804, 같은 사진 AUC 0.798, 놓침 18, 오탐 59. head: `…/head.pt` |
| `20261030T142049-6ad39ecf` | corner-rectify-edge-20261030 | completed/**true(주의)** | 정상 면이 없어 오탐 측정 불가. true는 placeholder 정수(max_fn 8, max_fp 0)에서 나온 값이라 **합격 근거 아님** |
| `20261030T144956-749bece0` | corner-rectify-batch-g-20261030 | completed/false | g 17면: 놓침 1/12, 오탐 3/5 (기준 미충족) |
| `20261030T145651-b091a73b` | normal-bank-knn-20261030 | completed/false | 정상 구역 kNN, AUC 0.498 |
| `…150154-816a3337`, `…150336-cd76aaed` | normal-faces-add / -tight-20261031 | completed/false | 정상 면 추가 두 번, AUC 0.387 / 0.362(우연 미만). add는 느슨한 자동 상자라 **구성 결함, 증거에서 제외** |
| `20261030T150929-22a6d616` | photo-centered-features-20261031 | completed/false | AUC 0.445, 같은 사진 AUC 0.496 |
| `20261030T155135-c160d610` | holdout-h-head3-20261031 | completed/**true(주의)** | placeholder 정수(105/73)에서 나온 true. **수치(AUC 0.813 등)는 정정됨, head 3 성능으로 인용 금지**(§4-1) |
| `20261030T222554-21e1a8d5` | box-perturbation-sensitivity-20261031 | completed/true | 상자 넓힘 10%: AUC 0.819, 놓침 19, 오탐 59(기준 충족). 보조: 넓힘 5%·20%는 AUC 0.799·0.824, 대각 이동 5% AUC 0.728(놓침 40), 안쪽 3% AUC 0.648(놓침 57) |
| `20261030T223207-41744088` | card-localization-baseline-20261031 | **failed** | worker의 JSON 왕복 비교 결함(점수 계산 전 중단). 기록 보존 |
| `20261030T223232-03b8fd5f` | card-localization-baseline-20261031 | completed/false | autobox가 사람 4점을 모두 포함하지 못한 면 16/29(55.2%, Wilson 37.5~71.6%), f 11/11·g 5/18. 신뢰도 0.7 미만 표시는 실패 16면 중 5면만 걸러냄 |

실행하지 않은 계획: `tools/experiments/card-localization-widen-20261031/plan.json`(status plan_only_not_run, 사용자 승인 대기).

## 4. 절차 이탈과 정정 (Codex가 알아야 할 것)
1. **g·h 라벨 저장 방식 이탈.** 기존 절차(`convert_pairs.py` → `build_inventory.py`+`autobox.py` → `review.html` → `freeze_dev_manifest.py`) 대신 `artifacts/ebay-intake-*/`에 텍스트 답 파일(`pairing-answers.txt`, `back-edge-answers.txt`, `region-answers.txt`, `corner-answers.txt`, `back-faces.json`)로 받았다. 이 답은 `point_dataset.py:58-72`가 요구하는 의미(빛 반사·관찰 제한 제외, 결함 종류, 결함 점)와 달라 **학습·평가 라벨로 변환하지 않는다**. 이 답으로 만든 h 홀드아웃 수치는 `performance-top3-consensus-20261030.md`에 정정(철회)을 적었다. 기존 manifest(`artifacts/development-manifest-20261030c`)는 바꾸지 않았다. 학습에 새 라벨을 쓴 실험은 위 두 건(정상 면 추가)이고 둘 다 미채택이다.
2. **`main` 직접 커밋.** `PAIR_CODING.md` §1은 `main` 통합을 Codex로 정했는데 Claude가 28개를 직접 커밋했다. 작업 계약·별도 브랜치 없이 한 실험도 있다. 이후 새 작업(`card-corner-click-review`)만 계약+브랜치+worktree로 했다.
3. **placeholder 합격 기록 2건**(`6ad39ecf`, `c160d610`): 덮어쓰지 않았다. 이 기록을 `./review`가 합격으로 읽지 않도록 주의가 필요하다.
4. **근거 부족 주장 정정.** "autobox가 f 뒷면 21면 중 12면을 잘랐다"는 말은 근거가 부족했다(해당 상자의 제안기가 autobox와 같은지 미확인). 실제 autobox 측정은 위 `…223232-03b8fd5f`(16/29)다.
5. **g·h 인벤토리 변환 도구를 새로 만들지 않았다.** Codex의 a~e 도구(`convert_pairs.py`, `build_inventory.py`, `autobox.py`)를 g·h 폴더에 복사만 했다(원본 불변).
6. 사용자 계정 지침(Claude 쪽): 모르는 건 가정하지 말고 근거 파일을 인용, 보고에 변경 파일·핵심 diff·리스크·롤백. 이미 반영했다.

## 5. 현재 데이터·서버 상태 (Git 제외 `artifacts/`, 실측)
- g: `artifacts/ebay-intake-20261030-g/`, 20쌍(`val-candidates-20261030-g.jsonl`, `review/labels-review.jsonl`). 검토 서버 `http://127.0.0.1:8797`. 상자 확인 0, 입력 라벨 0(문서 작성 시점).
- h: `artifacts/ebay-intake-20261031-h/`, 25쌍. `ebay-pair-270a6a12881028`은 g와 같은 사진이라 `pair-selection.20261031.dedup.json`에서 제외(원본 선택 파일 보존). 서버 `http://127.0.0.1:8798`. 상자 확인 0, 입력 라벨 0.
- 두 서버는 Claude 세션이 띄운 프로세스다. Codex 복귀 시 포트 점유를 확인하고 필요하면 종료한다.
- 신뢰도 낮은 상자(네 모서리 확대 확인 필수 결정): g `6b 12f 13b 14b`, h `2f 2b 15f 16b 17b 19b 20f 21f 21b`(`docs/collaboration/tasks/label-intake-adoption-fgh-20261031.md`).
- f·g 모서리 4점(`corner-answers.txt`, f 12·g 18 중 f의 `562d461bcf3f22`는 제외): manifest에 대응 필드가 없어 원본으로 보존. 카드 찾기 기준선 정답으로 사용(29면, f는 어려운 쪽으로 편향).
- `main`의 `review.html`을 서버가 요청 때마다 읽으므로, 브랜치를 통합하면 h 입력 중인 화면이 새로고침 시 바뀐다.

## 6. Codex가 결정·확인할 것 (제안 순서)
1. **h(25)·g(20) 라벨 입력 완료 대기**(사람 입력). 완료 후 저장 라벨을 `validate_annotations`로 검증하고 `tools/freeze_dev_manifest.py`로 새 manifest 폴더에 채택(기존 폴더 덮어쓰기 금지).
2. **브랜치 `f44896f` 검토·통합**: `git diff 9742511 f44896f`로 파일 범위(`regions.py`, `review.html`, 테스트, 문서)를 확인하고 `./develop -- git cherry-pick -x ...`로 통합. 통합 후 기본 checkout에서 `tests/point3_save.test.cjs`, `tests/test_review_contract.py`, `tests/test_review_loop_resilience.py`를 재실행해야 한다(worktree에서는 Git 제외 파일 부재로 미실행, 수정 전 기본 checkout에서는 통과).
3. **원격 반영**: `main`이 `origin/main`보다 8커밋 앞서 있다(위 일반 push 상시 승인은 Codex 직접·검증 통합 변경 기준이므로 Claude 커밋 28개를 검토 후 push할지 결정).
4. **진척 기준 범위**: 사용자는 2026-10-31 "카드 찾기 개발 범위 추가"를 승인했다(운영 입력은 배경이 섞인 원본 사진). 그러나 `PROGRESS_CRITERIA.md`·`development-progress.json`의 배점·완료 조건은 바꾸지 않았다. 배점 변경은 사용자 명시 승인이 필요하다. 현재 진척 35/100 유지.
5. **placeholder 합격 기록 2건 처리**(주의 표기 또는 기록 정정 방식 결정).
6. **카드 찾기 후보 `card-localization-widen-20261031`**(autobox 출력 10% 넓힘): 사전 기준이 plan.json에 고정돼 있고 사용자 승인 후 worker 작성·`./experiment` 실행. 같은 29면 재사용이라 독립 평가가 아니며 통과해도 채택하지 않고 편향 없는 무작위 표본(예: 40면)에 사람 4점을 받는 2단계가 필요하다.
7. **UX 후보(기록만)**: "사진 클릭으로 라벨 입력 켜기"가 켜져 있으면 클릭이 상자가 아니라 결함 점으로 들어가 영역 재지정이 불편하다.
8. **정리**: worktree `../pokemon-card-condition-claude-card-corner-click-20261031`은 통합 후 `PAIR_CODING.md` 정리 절차로, 오래된 `claude/task-*` worktree도 같은 절차로 판단.

## 7. 설계상 확인된 사실 (근거)
- 현재 추론은 사람이 준 카드 상자를 입력으로 받고 자동 카드 검출이 없다(`card_condition/listing_inference.py:99`). 진척 기준 100%의 의미도 수동 영역 보조 흐름이다(`PROGRESS_CRITERIA.md` 8행). 운영 입력은 원본 사진이라는 사용자 설명과 어긋나므로 §6-4가 필요하다.
- 상자를 안쪽으로 줄이면 크게 나빠지고(3%에서 AUC 0.648) 넓히는 것은 안전했다(5~20%에서 AUC 0.80~0.82). 사람 상자 기준 "카드가 안에 들어오면 통과"는 안전한 쪽이다.
- 기존 b~e 배치 box_reviewed 144면 중 65면(45%)이 autobox 제안을 그대로 승인했다(`artifacts/ebay-intake-*/review/`). 눈 승인이 1~5% 잘림을 놓칠 수 있으나 4점이 없어 실제 비율은 미확인.
- 3차 head의 순위 신호는 불안정할 수 있다: 정상 면을 더하면 AUC가 우연 미만으로 뒤집혔고, 사진 단위 통계가 학습·검증에서 반대 방향으로 라벨과 얽혀 있다(`performance-top3-consensus-20261030.md` §6~§8). 같은 사진 안 결함·정상 비교 학습이 유력 후보였으나 혼합 그룹 자료가 부족하다(학습 4그룹).

## 8. 롤백
이 문서와 위 문서 커밋은 `git revert`로 되돌린다. 브랜치는 삭제하면 되고 기존 라벨·manifest는 바뀌지 않았다.

## 9. 갱신 이력 (Claude는 작업을 이어갈 때 아래에 날짜와 변경을 추가한다)
- 2026-10-31: 최초 작성.
- 2026-10-31(후속): 카드 찾기 후속 실험 3건(widen `c1993f4a`, stage2 `856c9c5d`, refit `3d1ff1f9`) 모두 기준 미달. 사용자 승인으로 "사람 상자 입력 기본, 자동 찾기 보류"로 정리(`DECISION_CARD_LOCALIZATION_20261031.md`). §6-6(widen 후보)은 실행·종료됨. 배점·진척은 변경 없음.
