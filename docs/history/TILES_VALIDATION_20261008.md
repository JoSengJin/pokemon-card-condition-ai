# 카드 전체 + 확대 타일 실험 (2026-10-08)

## 결과
운영 채택 보류. train 40면 / val 18면만 사용했고 실제 회귀·최종평가 사진은 이번 실행에서 평가하지 않았다. 기존 수작업 카드 영역 전체와 60% 크기의 네 사분면(20% 중첩)을 각각 224px로 입력한다. 고정 MobileNetV3 Small 특징을 연결해 선형 head를 학습한다. 시드42, 5 epochs, MPS, 임계값0.5.

| val 항목 | 원본 | 카드 crop | 전체+타일 |
|---|---:|---:|---:|
| 센터링 결함 검출/실제 결함 | 2/7 | 3/7 | 0/7 |
| 센터링 오탐/정상 | 0/8 | 2/8 | 0/8 |
| 모서리 결함 검출 | 0/3 | 0/3 | 0/3 |
| 엣지 결함 검출 | 0/6 | 0/6 | 0/6 |
| 표면 결함 검출 | 0/2 | 0/2 | 0/2 |
| 평가 불가인데 가능으로 판정 | 5/5 | 5/5 | 5/5 |
| 최소 val loss | 0.6091 | 0.6184 | 0.6223 |

타일 실행 전체 소요 약6.55초(서비스 호출 지연 벤치마크 아님). 원본/크롭 수치는 artifacts/validation-only-{full,crop}/report.json, 신규 수치는 artifacts/tiles-20261008/report.json. 호출 절감0, requires_gemini=true, production_ready=false 유지.

확대만으로 현재 기준선의 결함 누락을 해결하지 못했다. 비교는 이미 반복 관찰한 모델선택 자료이며 최종 성능 추정이 아니다. 특징 차원576→2880으로 head 용량도 바뀌므로 해상도만의 효과로 해석할 수 없다. 사람 box 의존, 원근 보정 없음, 반사/작은 흠집 검출 보장 없음. 작은 양성 표본과 고정 특징/짧은 학습 등의 원인은 아직 분리 검증하지 않았다.

## 변경 파일 / 핵심 diff
- card_condition/side_experiment.py: side_views 및 tiles 옵션, 5개 보기 특징 연결, 보고서/모델에 tiles 설정 저장.
- card_condition/side_evaluation.py: 동일 전처리 복원과 타일 head 크기 지원. 이전 tiles 필드 없는 모델은 한 보기로 복원.
- card_condition/cli.py: --crop / --tiles 상호 배타 옵션.
- tests/test_side_experiment.py: 세 입력 모드 복원 일치, 타일 학습에서 시험 자료 변경 불변, 네 모서리 픽셀 보존.
- tests/test_side_evaluation.py: 타일 모델 회귀/최종 명령과 누수 차단 검증(합성 자료만).
- README.md: 실행 방법. PokeCollector/CONDITION_ANALYSIS_TODO.md: 완료·다음 단계 갱신.

## 검증
18개 unittest 통과. 실제 학습/val 실행 완료. 실제 test 평가 및 운영 Gemini 경로 변경 없음. 기존 사람 라벨/사진 수정 없음.

## 실행
```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition side-experiment data/sides-20261008.jsonl artifacts/tiles-new --tiles --epochs 5 --device mps
```
출력 폴더가 존재하면 덮어쓰기를 거부한다.

## 다음 단계
1. train에서 사람이 확인한 결함 양성 사례 및 실제 관찰 위치를 검토하고 관측 불가/결함 없음 혼동을 점검한다.
2. 같은 val만 사용해 학습 불균형 대응 등 가설 하나씩 비교한다. 현 결과만으로 특정 원인이 입증되지는 않았다.
3. 모델·임계값 고정 후 개발에 사용하지 않은 새 실물 그룹으로 최종평가한다. 운영 분기는 그 뒤 결정한다.

## 리스크 / 롤백
한 면당 backbone 입력이1→5개라 연산·메모리 사용 증가. 기본값은 기존 full이며 기존 실험 산출물은 유지했다. .backups/step8의 side_experiment.py, side_evaluation.py, cli.py를 card_condition/에, 두 test 파일을 tests/에, README.md를 루트에 복원하면 코드 롤백 가능. 이번 tiles-20261008 산출물은 격리 보관하거나 삭제하면 된다. 데이터/운영 DB 롤백 불필요. TODO에는 실험을 되돌렸다는 이력을 남긴다.
