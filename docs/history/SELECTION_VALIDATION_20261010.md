# 검증 모델 선택 기준 진단·대안 — 2026-10-10 (0.4.31)

## 완료 결과와 근거

round20 tiles의 ‘정상12개 전부 결함’ 현상을 같은 설정으로 재현했다. val class별 가중 BCE/유효 가중치/오탐·누락을 epoch마다 기록하도록 보완하고, 정상·결함과 각 class 안의 실물을 동등하게 반영하는 별도 선택 실험을 추가했다. 기존 선택 방식은 기본값으로 유지한다. 학습 라벨/학습 가중치/optimizer/lr/seed/입력/판정0.5는 변경하지 않았다.

기존 val은 정상12/결함15구역이지만 실물별 균등 가중 후 정상 질량1.1875, 결함5.8125(각 약17%/83%)다. 정상 구역이 특정 실물에 모여 있어서 구역 클래스 개수와 선택 loss의 비중은 다르다. 기존 목적은 실물 균등이므로 구현 오류로 단정하지 않는다. 원래 기준은 다음 중 epoch3을 선택했다:

|시점|정상 weighted BCE|결함 weighted BCE|기존 val loss|FP/FN|
|---|---:|---:|---:|---:|
|epoch3|0.9338|0.4854|0.5614|12/0|
|epoch20|0.7623|0.5545|0.5897|5/3|

정상 쪽 오류를 줄이는 변화가 기존 가중 목표에서는 선택되지 않는다는 점을 확인했다. 이는 원인 중 한 가지이며 데이터/특징/사진 편향 문제까지 해결했다는 뜻이 아니다. trace를 추가한 재현에서 기존 선택 epoch·혼동행렬 유지, 모든 점수 차이1e-6 미만을 확인했다.

## 선택 실험의 규칙

`point-experiment ... --balanced-selection`은 각 label의 val에서 정상/결함 질량을 각각1로 만들고, 각 class 내부에서는 실물 그룹을 균등화하며 같은 실물의 구역끼리 나눈다. 예를 들어 한 카드의 정상3구역이 다른 카드의 정상1구역보다3배 영향을 주지 않는다. 이 가중치는 val 모델선택 loss에만 적용하고 train 가중치는 그대로 둔다. 모델 업데이트는 train 단계에서만 수행한다. val 라벨로 선택 지표를 계산하는 것이며 전처리/모델 파라미터를 val에 맞춰 fit하지 않는다. test 사진은 읽지 않는다. 양쪽 val class가 없는 조합은 거부한다.

기본 선택은 기존 equal-group BCE다. 새 선택은 실험용으로 명시해야 하며 report와 checkpoint에 balanced_selection/selection_metric을 기록한다. 비교 보고서에도 선택 정책을 표시한다. val 정상/결함 비중이나 모델 결과를 보고 판정 임계값을 바꾸지 않는다. 새 클래스 가중치는 0.5 판정의 확률 보정/운영 승인과 다르다.

## 실제 결과

같은 round20-fixed-val/20epoch/MPS/seed42/224px/tiles/고정 MobileNet/균형 train head를 사용했다. 두 실행의 epoch별 train loss 최대 차이1e-6 미만, 선택용 val의 두 class 질량은 모든 epoch에서 각각1(오차1e-6 미만)이다.

|모델|선택 epoch|FP|FN|AUROC|AP|별도ㅅ FP/8|
|---|---:|---:|---:|---:|---:|---:|
|round19 tiles 기존 선택|16|6|2|0.8000|0.8455|1|
|round20 tiles 기존 선택|3|12|0|0.7556|0.8250|5|
|round20 tiles 균형 선택|20|5|3|0.8278|0.8771|1|

정답 엣지는 val50입력 구역 중27개/7실물(정상12·결함15)다. round20의 한쪽 판정 실패는 해소됐으나 round19보다 누락이1개 늘었다. 따라서 모든 지표 우월이나 최종 성능 향상을 주장하지 않고 후보로 보존한다. 별도ㅅ은 반복 개발 진단이며 학습/선택에 넣지 않았다.

고정 탐색 normal<0.3/defect≥0.7에서 정답 있는27구역 중7구역(2실물)에만 판정이 나오고 이7개 오류0/나머지20개 보류다. 이 작은 개발 결과는 안전성 증명/임계값 승인 근거가 아니다. 같은 checkpoint로 listing-infer 실행도 완료:14매물·152관찰가능 엣지구역. 전체 로컬 완료 후보0/실제Gemini절감0. 센터링·전체 관찰 가능성·모서리/표면 지원 부족을 그대로 보존한다.

## 변경 파일·핵심 diff

- card_condition/region_experiment.py: class_group_validation_weights, validation_diagnostics; point-grid 각 epoch의 class별 가중 BCE/질량/오탐·누락 기록; 기본False balanced_selection을 val에만 적용, metadata와 선택 모델 저장.
- card_condition/cli.py: point-experiment --balanced-selection 연결.
- card_condition/comparison.py: selection_metric/balanced_selection을 비교 보고서에 표시.
- tests/test_validation_trace.py 신규: 가중 BCE 재계산/unknown 제외/gradient 미발생, class·그룹 가중 합/반복 구역 영향/train 제외/부족 class 거부, 실제 두 학습의 train history 일치·선택 checkpoint 직접 추론 일치·test 미접근·원본 라벨 불변.
- pyproject.toml0.4.31, README, 본 보고서, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 진행 기록.
- artifacts/point-edge-tiles-20261010-round20-epoch-trace/ 및 point-edge-tiles-20261010-round20-balanced-selection/, balanced-selection-round20-comparison-20261010.json, balanced-selection-round20-s-probe-20261010.json, balanced-selection-round20-listing-inference-20261010.json.

## 검증·리스크·다음 진행

전체71테스트 통과(21.636초). 첫 통합 테스트 fixture에 point-grid 준비 조건인 결함 점이 빠져 실패했고 fixture를 수정한 후 전체 재검증했다. 기존 제품 학습 로직을 이 테스트 통과용으로 완화하지 않았다. wheel0.4.31 빌드 및 포함32개 source/HTML byte 일치. live 라벨 SHA256은 사용자ㅇ 확인 반영 시점과 동일하다.

반복 val로 선택 기준을 설계·비교한 개발 결과다. 기준을 고정하고 미사용 실물 최종시험을 수행하기 전 운영 교체/자동Gemini생략은 금지한다. 정상 구형 일본 뒷면은 여전히ㅇ1실물이다. 선택 epoch20이 학습 예산 끝이지만 성능을 올리기 위해 같은 val을 보며 epoch를 계속 늘리지는 않았다. 다음 사람 자료는 완료 카드 재확인이 아니라 구형 일본 POCKET MONSTERS 뒷면의 다른 실물1장, 확인 가능한 정상 테두리 구역이다. 실제 사진 다양성과 최종시험이 추가되기 전 데이터 일반화를 확정하지 않는다.

## 롤백

`/private/tmp/condition-epoch-trace-before/`의 region_experiment.py/cli.py/comparison.py/pyproject.toml/README.md를 각 원래 위치로 복원하고 신규 tests/test_validation_trace.py를 제거하면0.4.30으로 돌아간다. 새 모델·진단 artifacts만 별도 보관/제거한다. 학습 자료/라벨/운영DB는 이번 턴에 수정하지 않아 데이터 복원은 필요 없다. 임시 코드 백업은 장기 보관을 보장하지 않는다.
