# train-only 특징 표준화 검증 — 0.4.45

사전 계획 TRAIN_SCALING_PLAN_20261011.md. 학습 실물별 총가중치를 같게 두고 차원별 mean/std를 train에서만 계산해 학습·val·추론에 고정 적용했다. 612차원·사진/라벨·centroid·0.5 기준 유지. 기본 꺼짐.

| 지표 | 기존576차원 | 표준화612차원 |
|---|---:|---:|
| 관찰 제한 FP/FN | 7/4 | 7/4 |
| AUROC | .487395 | .563025 |
| AP | .426233 | .451407 |
| 균등 BCE | .698560 | .726281 |

순위는 개선됐으나 오류 감소 없음·BCE 악화로 사전 조건 미달, 채택 보류. 검증 정답이나 사진을 바꿔도 scaler·centroid 값이 그대로인 테스트를 추가했다. 재사용 val의 성능이며 독립 일반화 근거 아님. 실제 호출 절감0, 사람 라벨 변경0, 운영 변경0.

변경: card_condition/observation_scaling.py 신규(실물 균등 train 통계·상수 차원 floor1e-6·통계 검증), visibility_model.py(checkpoint/추론 연결), cli.py(--standardize), tests/test_observation_scaling.py 신규3개, pyproject.toml0.4.45, README/본 문서/TODO. 기존 flag 없는 체크포인트도 scaling=None으로 동작한다.

근거: artifacts/observation-train-scaling-20261011/report.json·comparison.json·recovery.json·verify.py. 전체97테스트, 실제 후보/복귀24면 재추론, 원본/입력/합의문/live SHA 검산, wheel39파일 바이트 일치.

리스크: train에 거의 없는 변화는 작은 std로 과장될 수 있다. 관찰 제한은 카드 불량이 아니다. 모델 오답 때문에 완료 라벨을 다시 요청하지 않는다.

롤백: --standardize 생략, 기존 artifacts/observation-geometry-20261011/model.pt 사용. 코드 복원은 .backups/train-scaling-0445의 기존4파일을 원위치에 복원하고 observation_scaling.py·tests/test_observation_scaling.py 신규2개만 제거. 사람 라벨·기록은 보존한다.

다음 가설: 후보 오탐7개는 모두 back, 누락4개는 모두 front. 전체가 아닌 면별 학습·오류 분포를 확인한다. train front clear20/limited5, back clear12/limited9; val front clear9/limited4, back clear8/limited3. 앞뒤 각각 양쪽 클래스가 있어 학습 측 대표 기준을 분리하는 단일 실험이 가능하다.
