# 매물 단위 Gemini 생략 가능성 검증

`data/learn-review.jsonl` 저장본을 이전 분할대로 고정한 `artifacts/visibility-complete-20261009.jsonl`과 기존 모델선택 예측 `artifacts/visibility-resliced-20261009.json`을 사용했다. 추가 저장 뒤 학습·검증 이미지/영역/정답은 이전과 같아 재학습하지 않았다. `routing-audit`는 검증 자료만 읽고 모델이나 서비스 경로를 바꾸지 않는다.

조건은 앞·뒷면 모두 있고, 양면의 평가 가능 예측이 문턱값 이상이며, 양면의 네 가지 결함 예측이 모두 0.5 미만인 경우다. 아래 수치는 검증 10매물(양면 8매물)에서만 계산한 가상 후보 수다.

| 평가 가능 문턱값 | 가상 후보 | 사람 라벨상 위험 | 사람 라벨 미확인 | 사진상 결함 없음 |
|---:|---:|---:|---:|---:|
| 0.5 | 5 | 3 | 1 | 1 |
| 0.6 | 4 | 3 | 0 | 1 |
| 0.7–0.9 | 0 | 0 | 0 | 0 |

0.5에서 위험으로 확인된 후보는 `u`, `x`, `ebay-86a98a94850103`이다. 사진상 결함 없음 1건도 숨은 흠집까지 안전하다는 증거는 아니다. 현재 예측값으로는 위험 후보를 없애면서 의미 있는 호출 절감을 보여주지 못했다. 검증 예측을 재사용한 개발 진단이며 독립 최종평가가 아니다. 운영 라우팅은 계속 꺼두고 `requires_gemini=true`, 실제 절감 0건을 유지한다.

재현: `.venv/bin/card-condition routing-audit artifacts/visibility-complete-20261009.jsonl artifacts/visibility-resliced-20261009.json artifacts/routing-audit-20261009.json`. 전체 unittest 25개 통과. 정답이 바뀌거나 새 실물이 추가되면 새 snapshot 및 학습 실험을 먼저 수행해야 한다. 롤백은 `card_condition/routing_audit.py`와 CLI 등록, 테스트, 이 보고서 및 결과 JSON을 제거하면 된다. 원본 라벨·모델·PokeCollector 코드는 변경하지 않았다.
