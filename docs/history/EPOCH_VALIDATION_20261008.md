# 학습 횟수 비교: 5회 → 30회

## 결과와 결정
고정 MobileNetV3 Small 특징 + 선형 head, 전체 사진, balance 활성, seed42, 학습률0.001, train40면/val18면, 임계값0.5를 유지하고 epochs만5→30으로 변경했다. 선택된 모델은 비보정 val BCE가 가장 작은30회차였다. 기존5회 모델/라벨/운영 경로는 수정하지 않았다. 운영 채택 보류, requires_gemini=true, production_ready=false, actual_calls_saved=0.

| 모델선택 항목 | 5회 | 30회 |
|---|---:|---:|
| BCE | 0.6517 | 0.5839 |
| 센터링 검출/결함 | 3/7 | 3/7 |
| 센터링 오탐/정상 | 3/8 | 4/8 |
| 모서리 검출/결함 | 2/3 | 1/3 |
| 모서리 오탐/정상 | 4/11 | 2/11 |
| 엣지 검출/결함 | 4/6 | 4/6 |
| 엣지 오탐/정상 | 3/8 | 2/8 |
| 표면 검출/결함 | 2/2 | 1/2 |
| 표면 오탐/정상 | 1/10 | 0/10 |
| 평가 불가를 가능으로 오판 | 4/5 | 3/5 |
| 평가 가능을 불가로 오판 | 0/13 | 1/13 |

학습 자료에서는 모서리10/10·표면4/4를 검출했지만 val에서는 각각1/3·1/2다. 일반화 격차가 있으며 원인이 라벨·표본·특징·과적합 중 무엇인지는 이 실험만으로 확정할 수 없다. val 손실은 마지막까지 감소했고 이번 결과만으로 학습 횟수의 최적값도 확정할 수 없다. 손실 감소와 안전한 결함 검출을 구별해야 한다. 다음에는 반복적인 횟수 증가보다 사람이 확인한 라벨/오류 유형을 점검하고 결함 누락·오탐의 허용 기준을 먼저 정한다. 부분 미세조정은 그 뒤 별도 비교한다.

## 구현 및 검증
- card_condition/side_experiment.py: selected_epoch, best_validation_loss를 보고서/체크포인트에 기록. 선택된 모델의 training_metrics를 진단용으로 기록. 선택은 기존 val loss만 사용하며 training_metrics를 선택에 사용하지 않는다.
- tests/test_epoch_selection.py: 최저 val 회차까지 별도로 재실행한 모델과 저장 가중치/예측이 같은지 검증.
- README.md: 학습 횟수/기록 안내.
- PokeCollector/CONDITION_ANALYSIS_TODO.md: 결과 및 테스트셋 사용 원칙 정정.
- 21개 unittest 통과. 실제30회 학습 완료, 약2.44초(서비스 지연 벤치마크 아님). 실제 test 사진/정답은 학습·평가에 사용하지 않았다.

증거: artifacts/balanced-30epochs-20261008/report.json, model.pt. 비교: artifacts/balanced-full-20261008/report.json.

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/balanced-30-new --balance --epochs 30 --device mps
.venv/bin/python -m unittest discover -s tests -q
```

## 리스크와 롤백
반복적으로 같은 val를 보며 개발하면 val에도 과적합할 수 있다. 새 실물 최종평가셋은 계속 분리해야 한다. 표본이 작아 검출 한 건의 차이를 일반적 성능 변화로 단정하지 않는다. 이번 변경은 기록 필드 추가이며 기본 epochs5 유지. 롤백은 .backups/step10/side_experiment.py를 card_condition/에, README.md를 루트에 복원하고 tests/test_epoch_selection.py를 제거한다. 신규 실험 폴더는 격리 보관/삭제할 수 있다. 원본 데이터·운영 DB 복원 불필요.
