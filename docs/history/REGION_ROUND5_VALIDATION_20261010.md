# b 정상 표면과 p 미확인 완료 반영 — 2026-10-10

## 사람 확인 결과

원본 learn-review.jsonl에서 b/back/lower_right/surface_defect=0, p/back/lower_right/surface_defect=null 및 region_reviews 완료를 확인했다. b의 모서리·엣지는 null 유지. p의 완료를 정상 정답으로 바꾸지 않았다. c의 사용자 확인 화이트닝 edge_defect=1도 유지했다. 이번 b/c/p 검토 묶음은 종료하며 동일 위치를 다시 요청하지 않는다.

`artifacts/regions-labeled-20261010-round5.jsonl`은 train88/val38구역이다. 원본 라벨과 분할을 수정하지 않았으며 미지정 t는 제외했다. 원본·참조 해시와 분할 변경0건은 `artifacts/region-round5-snapshot-receipt.json`에 보존했다. 기존과 동일한 seed42/224px/ImageNet MobileNetV3 Small 고정 특징+head/20회/비가중 loss로 재학습했다. p의 null은 학습 loss에서 제외된다.

## 검증 결과

산출물: `artifacts/region-baseline-20261010-round5-epochs20/`. 비교: `artifacts/region-round5-comparison-20261010.json`. 이전 사본을 참조로 등록해 val 사진·그룹·좌표·정답 동일성을 검증했다.

| 항목 | 이전 오탐/누락 | 새 오탐/누락 |
|---|---:|---:|
| 모서리 | 2/1 | 2/1 |
| 엣지 | 3/4 | 3/4 |
| 표면 | 11/2 | 9/2 |

반복 사용한 작은 val에서 표면 오탐2건이 감소했으나 독립 최종 성능이 아니다. val의 정상 표면은 뒷면만, 결함 표면은 앞면만이라는 편향이 남아 있다. 기존 운영 경로/모델 교체 없음, 실제 Gemini 호출 절감0건.

## 데이터 점검 보완

`region-audit` 출력에 group_class_counts_by_side와 coverage_gaps를 추가했다. train/val, 앞/뒷면, 종류, 정상0/결함1마다 고유 group 수를 센다. 같은 실물의 반복 구역은 하나로 계산하며 null/region_reviews는 정상으로 포함하지 않는다. 진단 필드만 추가하고 기존 ready_for_experiment 조건은 유지한다.

`artifacts/region-round5-data-audit-20261010.json`에서 train 뒷면 정상/결함 실물 수는 모서리0/5, 엣지0/9, 표면1/3이다. 현재 부족 클래스는4개이며, 다음 사람 자료 보강은 정상 뒷면 모서리·엣지 및 개발용 검증의 정상 앞면 표면/결함 뒷면 표면이다. 기존 완료 구역을 정상으로 강제하거나 기존 val/test를 train으로 옮기지 않는다. 새 자료 확보 전에는 동일 재학습을 반복하지 않는다.

## 변경·테스트·롤백

- 코드: card_condition/region_dataset.py. 테스트: tests/test_region_dataset.py. 문서: README, 이 기록, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md. 버전: pyproject.toml0.4.8.
- Python 전체42개 통과. 중복 구역의 실물 중복 제거, 미확인 제외, 앞뒷면 분리, 원본 불변 검사 포함. 기존 test 사진 격리 검사 유지.
- 0.4.8 wheel 빌드 완료. 새 가상환경 설치 검증은 미실행. 별도 최종평가는 미실행.
- 리스크: 클래스 존재와 실물1장은 일반화 성능 보장이 아니다. 보고서 보완은 모델의 자동 판단 능력을 추가하지 않는다.
- 롤백: 새 audit 필드·테스트·문서·버전 변경만 되돌릴 수 있다. 이전 모델과 실험은 보존됐다. 사용자 라벨은 되돌리지 않는다.
