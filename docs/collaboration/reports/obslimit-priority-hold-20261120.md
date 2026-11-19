# 후면 관찰 제한: 순위 점수 + 보류 표현 (2026-11-20)

- 승인: 2026-11-20 사용자 "예, 우선순위+보류". 근거는 누락 사유 분류의 사전 규칙이다(집중 사유가 없으면 이 방향을 제안).
- 진척: 78/100(v1.13) 변화 없음.
- 모델 성능: 새 평가 없음, 정확도 변화 없음.

## 무엇을 바꿨나

후보 F의 점수·head·입력(사람 확인 상자)·임계값 0.5는 그대로다. 바뀐 것은 출력의 **의미 표현**뿐이다.

| 출력 필드 | 값 |
|---|---|
| `priority` | 점수 ≥0.5이면 `high`, 아니면 `low`. 0.5는 기존 고정 평가 임계값이며 결과를 보고 고르지 않았다. |
| `label` | `high`: "재촬영 권고 우선순위 높음"<br>`low`: "…낮음 — 관찰 가능 여부는 확인되지 않았습니다(사람 확인 필요). 개발 자료에서 제한 사진의 약 41%(24/59)가 이 구간에 있었습니다." |
| `cleared` | 항상 `False`. 낮은 점수가 "관찰 가능"을 뜻하지 않는다. |
| `review` | `high` → `reshoot_suggested`, `low` → `human_check_required` |
| `held` 경로 | 그대로(상자 미확인·앞면·읽기 실패·비유한 점수). |

검토 화면(`tools/back_triage_review.py`)은 지금까지 관찰 제한 결과를 표시하지 않았다. 이제 카드마다 "사진 재촬영 권고: <label 또는 보류 사유>"를 한 줄로 보여 준다.

`label`의 41%(24/59)는 사진 전체 입력 F를 개발용 219건에 적용한 값이다. 운영 F(상자 입력)의 독립 수치가 아니며, 위험을 안내하는 문구로만 쓴다.

## 검증 (verification-before-completion)

| 검사 | 결과 |
|---|---|
| 새 테스트 `test_obs_priority_never_clears_low_scores` 구현 전 | 실패 1(오류), 기존 4 통과 |
| 같은 테스트 구현 후 | `unittest tests.test_back_triage_suite tests.test_back_triage_release tests.test_back_triage_usage` 13/13 통과 |
| 전체 | `unittest discover -s tests` 1118 통과(건너뜀 2) |
| 실제 head(`artifacts/triage-back-candidates-20261103/observation_limit-head.pt`) | 267행 중 6행에서 변경 전·후 점수 완전 동일, 모두 `cleared=False` |
| 검토 화면 | 가짜 결과로 `card_html`을 호출해 scored·held 두 경우 문구가 표시됨을 확인 |

검토 화면 전체 재생성(실사진 추론)은 하지 않았다.

## 구조 (PAIR_CODING)

| 파일 | 함수 수 | 호출 경로 |
|---|---|---|
| `card_condition/back_obs_limit.py` | 4 → 5 | `analyze → prioritized` (1회) |
| `tools/back_triage_review.py` | 변경 없음 | `card_html` 안 한 줄 |

## 리스크·롤백

- 출력 dict에 키가 늘었다. 키 집합을 엄격히 검사하는 소비자는 현재 테스트 안에 없다. 외부 PokeCollector 운영 코드는 바꾸지 않았다.
- 릴리스 manifest(F1, pending)는 head 파일만 고정한다. 이 모듈 소스는 고정 대상이 아니므로 다음 릴리스 후보에서 다시 묶어야 한다.
- 롤백: 이 커밋을 revert한다. 모델·라벨·실험 기록 변경은 없다.
