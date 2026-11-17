# 학습 데이터 불균형 보정 실험

## 결과
기존 전체 사진 기준선과 같은 train40면/val18면, seed42, MobileNetV3 Small 고정 특징, 5epochs, 학습률0.001, 임계값0.5로 비교했다. 이번 변경은 학습 BCE의 양성 가중치뿐이다. 최종평가·회귀 사진은 사용하지 않았다.

| 항목 | 기존 검출/양성 | 보정 검출/양성 | 기존 오탐/음성 | 보정 오탐/음성 |
|---|---:|---:|---:|---:|
| 센터링 결함 | 2/7 | 3/7 | 0/8 | 3/8 |
| 모서리 결함 | 0/3 | 2/3 | 0/11 | 4/11 |
| 엣지 결함 | 0/6 | 4/6 | 0/8 | 3/8 |
| 표면 결함 | 0/2 | 2/2 | 0/10 | 1/10 |
| 평가 가능 | 13/13 | 13/13 | 5/5 | 4/5 |

양성 가중치=학습의 음성 수/양성 수. 알려지지 않은 라벨은 양쪽 수와 loss에서 제외한다. gradable은 양성=평가 가능이므로 가중치0.1765이며, 센터링1.3125/모서리2.6/엣지1.7692/표면7.5다. 지원되지 않거나 한 클래스뿐인 항목은1로 둔다. 데이터 준비 검사는 기존대로 유지한다.

모델선택은 기존과 동일한 비보정 val BCE 최솟값을 사용한다. 최솟값은 기존0.6091, 보정0.6517로 악화했다. 따라서 검출 증가만으로 전체 성능 개선을 주장하거나 신규 모델을 기본값으로 선택하지 않는다. 같은 val를 반복 보는 개발 실험으로, 최종 일반화 성능이 아니다. 표면2/2도 작은 표본 결과일 뿐이다. sigmoid 출력은 보정 때문에 실제 확률로 해석할 수 없고 추가 검증 없이 자동 통과 임계값에 사용하면 안 된다.

운영 적용 보류: requires_gemini=true, production_ready=false, 호출 절감0. 기존 사용자 라벨/운영 코드/DB 변경 없음.

## 재현 / 증거
```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/balanced-new --balance --epochs 5 --device mps
.venv/bin/python -m unittest discover -s tests -q
```
20개 테스트 통과. train-only 가중치 계산, unknown 제외, test 이미지/라벨을 무효화해도 보정 학습 결과 동일, 체크포인트 저장 검증 포함. 실제 실행 약2.23초이며 서비스 지연 벤치마크가 아니다.

- 기준선: artifacts/validation-only-full/report.json
- 보정: artifacts/balanced-full-20261008/report.json 및 model.pt
- 다음 사람 검토용 오류 목록: artifacts/balanced-full-20261008/validation-errors.json
- 상세 train 클래스 수와 사용 가중치는 report.json에 저장된다.

## 변경 파일 / diff
- card_condition/side_experiment.py: training_balance, 선택적 학습 pos_weight, train 클래스 수/가중치 보고서 및 체크포인트 기록. val loss와 추론 방식 유지.
- card_condition/cli.py: --balance 추가, 기본 false.
- tests/test_balance.py: 두 회귀검증 추가.
- README.md: 실행 안내.
- PokeCollector/CONDITION_ANALYSIS_TODO.md: 결과와 다음 단계 갱신.

## 다음 단계
train 양성 사례의 실제 관찰 위치와 라벨 일관성을 사람이 검토하고, val 오류 목록에서 반사/배경/앞뒤 등 실패 유형을 기록한다. 라벨을 모델 출력에 맞춰 자동 수정하지 않는다. 이번 실험은 수치 불균형만 검증했으며 사람이 지정한 결함 위치나 라벨의 정답성 검토를 완료한 것은 아니다. 추가 학습 길이/특징 변경은 한 번에 한 변수만 검증한다. 최종 평가는 새 실물 그룹으로 별도 수행한다.

## 리스크 / 롤백
희소 양성에 높은 가중치를 주면 잘못된 라벨의 영향도 커지고 오탐이 늘 수 있다. 기본 옵션은 false라 기존 명령 동작을 유지한다. 옵션을 빼면 보정 없이 학습한다. 코드 롤백은 .backups/step9의 side_experiment.py와 cli.py를 card_condition/에, README.md를 루트에 복원하고 신규 tests/test_balance.py를 제거한다. 신규 산출물 폴더는 별도 보관/삭제 가능하다. 기존 모델/라벨 복원은 필요 없다.
