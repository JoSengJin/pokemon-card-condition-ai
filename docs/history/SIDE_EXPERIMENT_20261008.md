# 면별 라벨 및 카드 영역 학습 비교

## 변경
- 추가: card_condition/side_experiment.py, tests/test_side_experiment.py.
- 수정: card_condition/cli.py (`side-experiment`).
- 원본 라벨은 보존. data/sides-20261008.jsonl 스냅샷 사용, 이전 expanded 실험의 분할을 우선 고정. UI에서 바꾼 분할과 차이는 artifacts/sides-20261008-snapshot.json에 기록.
- 실제 side_annotations의 정답과 box 사용. 전체 카드 라벨을 면별 정답으로 복사하지 않음. 같은 카드 앞뒤는 동일 분할.
- 원본/크롭 모두 영역과 gradable 라벨이 있는 동일한 64면 사용. 8개 누락/미준비 면은 두 실험에서 동일하게 제외. 정답 null 항목은 loss/지표에서 제외.

## 실행 및 검증
- MobileNetV3 Small 사전학습 특징 고정 + 면별 linear head, seed42, 5 epochs, 224px, MPS.
- backbone 특징을 한 번 계산하고 head만 학습. 두 실험은 같은 학습 방식과 초기화이며 crop 유무만 다름.
- 학습40면 / 모델선택18면 / 회귀평가6면(3개 실물).
- 테스트15개 통과: 저장 모델 복원 추론, 실제 crop 픽셀 변화, 면별 unknown 유지, 이전 테스트 포함.
- 결과: 원본과 크롭 모두 센터링 TP2/FN2, 모서리 TP0/FN2, 엣지 TP0/FN1, 표면 TP0/FN1. 평가불가2면을 가능으로 오판.
- val 최저 loss: 원본0.60910, crop0.61845. crop 개선 근거 없음.
- 6면은 독립 6개 실물이 아님. 이미 관찰한 회귀셋이며 일반 정확도·최종검증으로 해석하지 않음.
- 지난 전체 카드 모델과 라벨/학습 단위가 달라 수치 직접 비교 금지.
- 모델은 단면 실험 전용 형식. 기존 pair Analyzer와 호환되지 않으며 운영 API에 연결하지 않음.
- 실제 Gemini 호출/절감 0. 사람 box가 필요하며 자동 카드 검출·원근 보정·결함 위치 탐지는 아직 없음.

## 재실행 (새 출력 폴더 필요)
```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/new-sides-full
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/new-sides-crop --crop
```

## 다음
모델선택 자료의 결함 누락을 분석한 뒤 카드 전체+모서리/엣지 확대 타일 가설을 검증한다. surface 양성은 학습4/val2면뿐이므로 다양한 실물 양성 자료가 필요하다. 최종 성능은 새 미사용 실물 자료로 검증한다.

## 롤백
.backups/step6/cli.py를 card_condition/cli.py로 복원. 신규 side_experiment.py와 test_side_experiment.py 및 sides-20261008 스냅샷/sides-full·sides-crop 산출물을 제거하면 된다. 기존 모델, 라벨 파일, PokeCollector 운영 코드에 영향 없음.
