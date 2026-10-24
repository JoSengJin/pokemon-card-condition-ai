# ㅇ 뒷면 엣지 반영·round20 검증 — 2026-10-10

## 사람 확인과 데이터 보존

사용자가 저장한 back/middle_right edge_defect=1을 확인했다. 추가로 나머지7개 테두리 구역을 충분히 확인했고 정상이라고 직접 응답했다. 그7구역만 edge_defect=0으로 반영했으며 앞면/모서리/표면/센터링/같은 실물 여부를 추정하지 않았다. 면 엣지1을 유지하고 reviewed_by=user와 확인 근거를 기록했다. 기존64개 다른 레코드는 의미상 동일하며 새 카드ㅇ 포함 총65개다.

학습 전 frozen round19-fixed-val에 train ㅇ만 추가한 round20-fixed-val snapshot을 만들었다. train151→159구역, val50/8실물 불변. 신규8구역은 엣지0×7/엣지1×1이며 다른 종류 정답은null이다. point_rows로 기존 구역/정답/사진/box/분할이 그대로인지 assertion을 통과했고 comparison이 validation identity를 재검산했다. 별도ㅅ은 학습·epoch선택에 사용하지 않았다. 기존 d를 train으로 이동하지 않았다.

## 실제 재학습 결과

같은 seed42/20epoch/224px/고정 backbone/균형 엣지 head 설정을 유지했다. train만 보강했고 positive weight는 기존 구현대로 train에서만 다시 계산됐다(0.5882→0.6408). val은 모델선택에 사용하므로 독립 최종 성능이 아니다.

|설정|선택 epoch|FP|FN|AUROC|AP|균형 정확도|별도ㅅ FP/8|
|---|---:|---:|---:|---:|---:|---:|---:|
|round19 context|20|6|3|0.6778|0.7424|0.6500|1|
|round19 tiles|16|6|2|0.8000|0.8455|0.6833|1|
|round20 context|20|5|7|0.6722|0.7387|0.5583|1|
|round20 tiles|3|12|0|0.7556|0.8250|0.5000|5|

엣지 정답 분모는 val50구역 중27개(정상12/결함15)다. d 오탐은 context5→4로 줄었지만 전체 누락이 증가했다. tiles는 val loss로 epoch3을 선택했고 27개를 모두 결함으로 분류해 정상12개가 전부 오탐이다. 점수가 동일한 것이 아니라 0.5 기준 분류가 한쪽으로 몰린 것이다. AUROC가 존재해도 현재 기준의 판정은 실패일 수 있다. 기존 기준을 조정해 개선으로 포장하거나 새 라벨을 변경하지 않았다. 두 새 모델 모두 채택 보류, 운영 모델 교체/실제Gemini절감0건이다.

## 비교 보고서 보강(0.4.30)

score_diagnostics에 정답 있는 항목의 prediction_distribution_at_05와 balanced_accuracy_at_05, warning_at_05를 추가했다. 양쪽 정답 클래스가 있는데 예측이 모두 결함/정상이면 all_known_predicted_defect/all_known_predicted_normal로 표시한다. 양쪽 정답이 없으면 both_truth_classes_required로 기록하고 균형 정확도는null이다. 미확인 정답은 이 진단에서 제외한다. 순위가 완벽해도0.5에서 전부 결함이면 경고하는 테스트를 추가했다. 이 경고는 오프라인 진단이며 자동 채택/자동차단/Gemini 라우팅 정책이 아니다. 기존 지표·모델선택·학습·추론·임계값은 바꾸지 않았다.

## 변경 파일·핵심 diff

- data/learn-review.jsonl: ㅇ 뒷면 정상 엣지7구역과 사람 확인 기록; 이미 저장된 우측 중간 결함1 유지.
- card_condition/score_diagnostics.py:0.5 기준 예측 분포·한쪽 판정 경고·균형 정확도.
- tests/test_score_diagnostics.py: 양쪽 상수 판정/순위와 분류 차이/정상 혼합 판정/정답 부족 검증.
- pyproject.toml0.4.30, README, 본 보고서와 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 진행 기록.
- artifacts/ieung-human-confirmation-20261010.json, point-evidence-20261010-round20-fixed-val.jsonl, 두 round20 모델 디렉토리, ieung-round20-comparison-20261010.json, ieung-round20-diagnostics-20261010.json, ieung-round20-s-probe-20261010.json.

## 검증·한계·다음 휴먼인루프

전체68테스트 통과(21.403초). wheel0.4.30 빌드 및 포함32개 소스/HTML byte 일치. 기존64개 레코드 보존·train/val 기존 입력 불변·학습 후 live 라벨 SHA 불변 확인. 신규 모델은 개발 비교로만 저장했다. 새로운 source가 바뀐 것은 진단뿐이므로 현재 모델 재학습을 같은 조건으로 반복하지 않았다.

정상 뒷면 엣지 학습 실물은 총6장, 구형 일본 디자인은ㅇ1장이다. 같은 사진의 정상7구역은7실물이 아니다. 한 장 추가가 성능 향상을 보장하지 않는 결과이며, 데이터 부족/촬영 편향/고정 특징/검증 모델선택의 영향 중 정확한 원인은 아직 분리하지 못했다. 다음에는 구형 일본 POCKET MONSTERS 뒷면의 다른 실물1장, 사람이 정상 테두리를 확인할 수 있는 사진을 보강하는 것이 우선이다. 전체 정상 또는 PSA10일 필요는 없고 관찰된 범위만 정상으로 기록한다. 완료한ㅇ 재라벨링은 필요 없다.

## 롤백

코드는 `/private/tmp/condition-collapse-before/`의 score_diagnostics.py·tests/test_score_diagnostics.py·pyproject.toml·README.md를 각 원래 경로로 복원하면0.4.29로 돌아간다. 새 artifacts/model 디렉토리는 별도 보관 또는 해당 경로만 제거한다. 데이터는 이후 사용자 저장이 없음을 확인한 경우 `data/learn-review-before-ieung-edge-confirm-20261010.jsonl.bak`를 복원하면 사용자 저장 우측 중간 결함1은 유지한 채 추가7개 정상 반영 전으로 돌아간다. 이후 저장이 있으면 전체 복원하지 말고ㅇ의7개 엣지0만 선택적으로 되돌린다. 임시 코드 백업은 장기 보관을 보장하지 않는다. 소비 앱/운영DB 변경은 없다.
