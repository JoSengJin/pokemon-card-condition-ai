# 데이터 누수 방지 적용 및 검증

## 변경 파일
- card_condition/data.py: split 선택 필터. 제외 split 사진/라벨 검사를 수행하지 않음.
- card_condition/model.py: pair 학습도 train/val만 로딩. 기존 evaluate 결과에 regression 및 최종 성능 아님 표시.
- card_condition/side_experiment.py: 자동 test 평가 제거, val 결과만 표시. development id/group/pixel hash를 모델에 저장.
- card_condition/side_evaluation.py (신규): 고정 모델의 명시적 회귀/최종 평가. 과거 manifest 및 checkpoint 이력과 겹치는 평가 자료 차단.
- card_condition/cli.py: side-evaluate --kind regression|final --history 도입.
- card_condition/review.html: test를 별도 평가 후보로 표시. 이미 본 자료는 회귀평가라는 설명.
- tests/test_side_experiment.py, tests/test_side_evaluation.py (신규), README.md.
- PokeCollector CONDITION_ANALYSIS_TODO.md: 최신 완료/미완료 정리. 운영 코드는 변경하지 않음.

## 테스트와 실제 실행
- unittest 17개 통과.
- 시험 사진 경로를 존재하지 않는 파일로 바꾸고 시험 정답을 잘못된 형식으로 바꿔도 train/val 가중치와 결과가 완전히 같음 확인.
- 회귀평가 명시 실행, 학습 그룹 거부, 과거 시험 id/group 변경 뒤 동일 픽셀 거부, history 미제공 거부, 독립 합성 final 수용, 보고서 덮어쓰기 거부 검증.
- 실제 g/r/z를 final 후보로 넣으면 예측 전에 차단됨. artifacts/final-leakage-guard-check.json 기록. final 결과 파일 미생성 확인.
- 실제 학습40면/val18면으로 원본/크롭 각5 epochs. artifacts/validation-only-full 및 validation-only-crop 생성. test 특징 추출/예측 없음.
- val 최저 loss full0.60910, crop0.61845. 센터링 full TP2/FN5/FP0, crop TP3/FN4/FP2. 모서리 FN3/엣지 FN6/표면 FN2는 두 모델 동일. val 수치이며 최종 성능이 아님.
- 가중치 학습은 train, epoch 선택은 val, 전처리는 고정 규칙, backbone eval+inference_mode로 고정.

## 리스크 및 경계
- 현재 최종평가용 새 실물 자료는 없음. 실제 최종평가를 수행했다고 주장하지 않음.
- 사용자가 제공한 history만 검사하므로 누락된 외부 실험 이력까지 추적하지 않음.
- 픽셀이 달라진 동일 실물은 그룹 수동 확인 필요. 자동 근접중복 검출은 미구현.
- 이미 본 최종결과로 재개발하는 사람의 행동을 코드가 완전히 막지는 못함. 보고서와 history를 보존하고 이후 새 final 사용.
- side-experiment 결과의 counts/metrics가 test에서 val로 바뀜. 기존 보고서 소비 스크립트는 evaluation_kind를 확인해야 함.
- 구형 side checkpoint는 새 평가 명령에서 거부함. 과거 결과와 파일은 보존.
- Gemini 호출 및 실제 절감은 0, production_ready=false 유지.

## 롤백
.backups/step7의 data.py, side_experiment.py, model.py, cli.py, review.html을 card_condition/로, test_side_experiment.py를 tests/로, README.md를 루트로 복원. 신규 side_evaluation.py와 test_side_evaluation.py, 이번 validation-only 산출물만 제거. 원본 라벨과 이전 학습 산출물은 수정하지 않음.
