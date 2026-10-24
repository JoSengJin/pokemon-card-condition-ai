# 좌표 학습 클래스 비중 보정 — 2026-10-10

## 결과와 판단

ㄴ 정상 표면9구역과 결함3구역을 추가한 뒤에도 기본 좌표 모델이 모든 정상을 결함으로 판정하여, 데이터 추가 없이 학습 가중치 한 요소만 변경했다. 기존 코드의 실물 가중치를 기본으로 삼고 train의 양성/음성 유효 가중치 합을 같게 하는 선택적 --balance를 구현했다. 이 실험은 정상 오탐과 결함 누락의 교환을 확인했으며 운영 채택하지 않는다.

| 종류 | 기본 FP/FN | 보정 FP/FN |
|---|---|---|
| 모서리 |6/0|2/1|
| 엣지 |12/0|5/5|
| 표면 |19/0|11/9|

표면 검증 정답은 정상19/결함19, 각 실물3그룹. 보정 모델은 정상8구역을 올바르게 판정했으나 결함9구역을 놓쳤다. 누락 위치는 d/front6구역, w/front3구역이며 ㄱ/back 표면1구역은 검출했다. 사람이 저장한 d/w 라벨을 잘못됐다고 바꾸거나 재확인 요청하지 않는다. 실물별 동등 평균 표면 오탐률은1.0→0.7037, 누락률은0→0.3333. 반복 구역을 독립 카드 수로 해석하지 않는다.

오탐 감소만으로 개선 성공을 주장할 수 없다. 기존 모델 유지, 양 후보는 실험 산출물로 보관, 실제 Gemini 절감0건. 같은 자료에서 기준을 반복 조정해 운영 성공으로 해석하지 않는다.

## 구현 계약과 누수 방지

- train의 기존 실물별/종류별 기본 가중치로 정상 합 N, 결함 합 P 계산.
- 해당 종류의 train 양성 가중치에 N/P를 곱하고 실제 가중치 합으로 train BCE를 정규화.
- null/미지원 종류는 학습에서 제외, 비율을 계산할 때 val/test는 제외.
- val loss는 기존 실물 동등 가중 BCE 그대로 사용. --balance로 val 가중치나 판정 기준을 바꾸지 않는다.
- 클래스 보정 후 최종 train 실물 총합은 서로 다를 수 있다. 단순 구역 개수 N/P나 최종 실물 동등 가중이라고 표시하지 않는다.
- 기본 balance=False. point-experiment에서만 선택 가능하며 일반 region-experiment에 암묵 적용하지 않는다.
- 보고서/체크포인트에 balance와 positive_weights 기록, point-compare 출력에도 보존.

실제 train 양성 비율: 모서리0.5714286, 엣지0.3846154, 표면0.5757576. 데이터 라벨은 변경하지 않았으며 전체 평가 가능 여부/동일 실물 여부도 채우지 않았다.

## 실행과 검증

```sh
OMP_NUM_THREADS=1 TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition point-experiment artifacts/point-evidence-20261010-round10.jsonl artifacts/new-balanced --balance --epochs 20
.venv/bin/card-condition point-compare artifacts/point-evidence-20261010-round10.jsonl artifacts/new-balance-comparison.json artifacts/point-grid-augmented-20261010-round10-epochs20/report.json artifacts/new-balanced/report.json
```

MobileNetV3 Small ImageNet 고정 특징·head 학습, seed42,224px,20epochs,MPS. 동일 round10 snapshot, 동일 검증50구역/8실물, 동일 train103구역, 기준0.5. 기본 선택epoch10, 보정epoch8. 새로운 모델선택 결과이며 최종시험은 아니다.

- 후보: `artifacts/point-grid-balanced-20261010-round10-epochs20/`.
- 검산: `artifacts/point-grid-balance-comparison-20261010.json`.
- 전체 Python57개 통과: `/private/tmp/condition-point-balance-tests.log`.
- 후속 합성 회귀: 보정 비율1일 때 기본 학습과 예측 전체가 정확히 일치하는 단언 추가.
- 후속 위치 데이터 테스트6개 통과: `/private/tmp/condition-point-balance-focused.log`.
- 원본 라벨/snapshot SHA256 불변, 기본/보정 입력 JSONL 바이트 일치, 고정 backbone 텐서 전체 일치, 기존 round6/round8 체크포인트 SHA256 불변 assert 통과.
- 0.4.17 wheel 빌드 성공: `/private/tmp/condition-point-balance-wheel.log`. wheel의 region_experiment.py/comparison.py/cli.py 소스 바이트 일치 확인.
- 실제 실행 로그: `/private/tmp/condition-point-balance-run.log`, `/private/tmp/condition-point-balance-comparison.log`.

## 변경 파일·리스크·롤백

변경: card_condition/region_experiment.py(train 전용 비율·loss 옵션·metadata), cli.py(--balance), comparison.py(설정 표시), tests/test_point_dataset.py(train/val 격리·null·합성 학습 회귀), pyproject.toml0.4.17, README.md, 이 문서와 마스터 TODO. 신규 의존성 없음.

클래스 보정은 사진 다양성이나 특징 추출의 구별 능력을 보장하지 않는다. 현재 누락 증가로 운영 적용 보류. 새 라이브러리/프레임워크·실제 배포·미사용 최종평가는 진행하지 않았다.

롤백: --balance 옵션과 training_class_ratios/loss 선택 분기/추가 metadata·테스트·문서·버전을 되돌린다. 기존 모델·원본 라벨은 변경하지 않았으므로 데이터 복원이 필요 없다. 후보 디렉터리만 별도 보관하거나 제거하면 된다.
