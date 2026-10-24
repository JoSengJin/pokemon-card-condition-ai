# 좌표 보강 학습 및 대조 실험 — 2026-10-10

## 저장 확인과 입력

w/front surface_defect 지점3개, val 분할 유지 확인. s/back 지점4개 유지. 원본 수정 없이 round8 snapshot과 receipt 생성. 분할 변경0, 미지정 t 제외 유지. round8 source SHA256은 receipt에 기록했다.

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition point-experiment artifacts/regions-labeled-20261010-round8.jsonl artifacts/new-point-experiment --epochs 20
```

새 CLI는 기존 region-experiment 기본값을 유지한다. MobileNetV3 Small ImageNet 고정 특징 + head, seed42,224px,20회. 정상/결함 모두 고정3×3 구역을 사용하여 중심 crop과 고정 crop의 형상 차이를 제거한다. 이는 정확한 점 크기의 검출이나 segmentation 학습은 아니다.

- 기존 사람 구역0/1 보존. 점은 해당 종류의1만 보강하고 다른 항목은 기존 명시 라벨 또는 null이다.
- s의 upper_left는 기존1과 합쳐지고 middle_right/upper_center 두 표면1구역이 추가됐다. 상단 중앙 점2개는 한 구역이다.
- w의3점은 lower_left 한 구역이며 기존 구역1과 합쳐진다. w를 train에 넣지 않는다.
- train91/val38구역. 관찰 제한 정상 e/back 표면2항목은 제외; 다른 종류의 명시 라벨은 유지. 점과 정상0이 충돌하면 학습 중단.
- train 가중치와 val 모델선택 loss 모두 종류별 실물 총합 동등 가중. 구역 수가 많아도 새 실물이 되지 않는다. 클래스 자체의 균형이나 독립 자료 충분성까지 보장하지 않는다.

## 결과와 채택 여부

1. 초기 점 전용 후보 실험: 기존 구역 결함 양성을 제외하는 방식은 점 검증 표면 TP0/TN10/FP0/FN1, 전체 알려진 val 표면30구역에서는 TP2/TN11/FP1/FN16. 기존 사람 양성을 버리는 방식은 폐기. 기록은 point-grid-baseline-20261010-round8-epochs20에 보존.
2. 최종 구현은 기존 사람 양성을 유지하고 점을 보강. point-grid-augmented-20261010-round8-epochs20에 별도 저장. 선택 epoch9. 지원 모서리/엣지/표면. 학습에 실제 새 s 결함 구역2개가 들어갔다.
3. 같은 val 표면30구역(4실물)·기준0.5로 기존 round6 모델과 비교:

| 모델 | TP | TN | FP 정상 오탐 | FN 결함 누락 |
|---|---:|---:|---:|---:|
| 기존 round6 |16|2|10|2|
| 좌표 보강 |18|0|12|0|

정상12구역 모두 결함으로 판정하므로 운영 채택하지 않는다. 신규 점 모델의 모서리/엣지 개발 지표도 정상 전부 오탐(FP6/12)이다. 점 기반 검증 표면에서는 관찰 제한 정상2항목 제외로 FP10이지만, 같은 기존30구역에 대한 비교에서는 FP12다. 분모를 혼동하지 않는다.

4. 원본을 보존한 대조 사본 point-grid-ablation-20261010-round8.jsonl에서 s의 새 구역을 만드는 점3개만 제거(기존 upper_left 점1개·기존 구역 라벨·모든 val 유지). 같은 설정으로 학습하니 역시 epoch9, 검증 지표 동일. 구역별 확률은 같다고 주장하지 않으며 현재 판정 기준에서 좌표 보강의 검출 개선 근거는 없었다.

표면 val 정상은 뒷면, 결함은 앞면에 편중. 기존 val은 모델선택에 이미 사용했으므로 최종평가가 아니다. s/w는 다시 라벨 재확인을 요청하지 않는다. 다음 성능 개선에는 서로 다른 실물의 정상 앞면·손상 뒷면과 미사용 최종평가 자료가 필요하다. 동일 데이터 반복 재학습이나 자동 Gemini 생략으로 진행하지 않는다.

## 변경 파일과 검증

- card_condition/point_dataset.py: 읽기/진단 공통 함수, 고정 구역 결합·중복 제거·사람 라벨 충돌 차단.
- card_condition/region_experiment.py: opt-in point_grid 분기, train/val 실물 가중치, manifest 변경 검사, 입력 기록 및 별도 체크포인트 종류.
- card_condition/cli.py: point-experiment 등록.
- tests/test_point_dataset.py: 지점 중복·기존 양성 보존·충돌 차단·val 격리·부족 클래스 중단·전처리·모델 종류 격리.
- README.md, pyproject.toml0.4.13, 이 문서, 마스터 CONDITION_ANALYSIS_TODO.md.
- Python 전체50개 통과(/private/tmp/condition-point-grid-tests-final.log). 실제 MPS 학습·대조 완료. 기존 점 중앙 crop 생성 회귀도 통과. 0.4.13 wheel 빌드 및 point_dataset.py/region_experiment.py/cli.py 소스 일치 확인. 대조 val 입력 전체 동일·혼동행렬 동일·원본 라벨 SHA256 불변을 별도 assert 검증했다.

독립 프로젝트에만 코드 적용. UI/라벨 서버 변경 없음. 기존 모델/소비 앱/Gemini 호출 경로 변경 없음, actual_calls_saved=0. 새로운 point_grid_v1은 운영 추론/최종평가 API에 아직 연결하지 않아 기존 RegionAnalyzer가 거부한다. 신규 환경 설치와 미사용 최종평가는 미실행.

롤백: 신규 point-experiment CLI 및 point_grid 선택 분기·point_rows grid 처리·테스트/문서/버전 변경을 제거한다. 기존 region-experiment 기본 동작, 원본 좌표와 기존 모델은 보존한다. 실험 산출물은 다른 디렉터리라 기존 체크포인트를 덮어쓰지 않았다.
