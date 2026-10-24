# y 표면 결함 반영 재학습 — 2026-10-09

## 저장과 학습

`data/learn-review.jsonl`의 y/back/lower_left/surface_defect=1을 확인하고 새 고정 사본 `artifacts/regions-labeled-20261009-round2.jsonl`을 생성했다. 원본 SHA256은 `dff4be58e1329cdb38ccfbc2d28155127ac7a556b91d93a85e64d61333ef3d75`. 원본 라벨은 수정하지 않았다. 미지정 t는 복사에서 제외하고 원본 분할은 그대로 유지했다. 이전에도 미지정이던 t를 참조 사본에서 제외해 snapshot 검증을 수행했고, 기존 분할 이동은 0건이다. 전체 원본·참조 해시와 제외 목록은 `artifacts/region-round2-snapshot-receipt.json`에 기록했다.

train85/val38 구역, ImageNet MobileNetV3 Small 고정 특징+head, seed42, 224px, 20회, 기본 비가중 loss 조건으로 실행했다. 새 표면 양성 정답이 이미 다른 결함으로 사용하던 구역에 추가되어 구역 수는 그대로다. `artifacts/region-baseline-20261009-round2-epochs20/report.json`에 결과를 보존했다. y는 결함 정답을 저장했으므로 다시 같은 표면 확인을 요청하지 않는다.

## 동일 검증 자료 비교

새 `region-compare --reference`로 두 snapshot의 val 사진 픽셀·그룹·구역·카드 영역·정답이 동일함을 검사하고 보고서 혼동행렬을 재계산했다. 결과는 `artifacts/region-round2-comparison-20261009.json`.

| 항목 | 이전 오탐/누락 | 보강 후 오탐/누락 |
|---|---:|---:|
| 모서리 | 2 / 1 | 2 / 1 |
| 엣지 | 4 / 5 | 4 / 5 |
| 표면 | 9 / 2 | 11 / 2 |

새 정답은 학습에 반영됐으나 검증 성능 개선은 없었다. 정상 뒷면 구역의 실물 그룹 수는 여전히 0이다. val 정상 표본도 모서리1/엣지2/표면3 실물 그룹뿐이므로 일반화 성능을 확정하지 않는다. 기존 모델 교체·자동 제외·상태 점수 확정·Gemini 호출 경로 변경은 수행하지 않았다. 실제 호출 절감0건.

## 코드·검증·롤백

- 변경: `card_condition/comparison.py`, `card_condition/cli.py`에 명시적 과거 snapshot 등록 및 val 동일성 검증. `tests/test_region_experiment.py`에 참조 없을 때 차단·train-only 변경 허용·val 변경 차단 검사 추가.
- 문서/패키지: README와 이 기록, pyproject 0.4.6, 소비 프로젝트의 CONDITION_ANALYSIS_TODO.md 진행 현황.
- Python 전체39개, 구역 관련10개, JS 검토 화면 회귀검사 통과. 새 실험과 비교 명령 정상 종료. 독립 최종평가는 수행하지 않았다.
- 남은 사람 확인: ebay-50f5e8124d55bb/back/upper_right/edge_defect는 null이고 완료 기록도 없다. 이미 확인했다면 미확인을 그대로 두고 검토 완료만 저장할 수 있다. 정상/결함으로 강제 변경하지 않는다.
- 롤백: 기존0.4.5 wheel 및 이전 model.pt 유지. 새 비교 옵션과 관련 테스트/문서만 되돌릴 수 있다. 새 학습 산출물은 별도 경로라 이전 모델을 덮어쓰지 않았다. 사람 라벨 원본은 백업으로 덮어쓰지 않는다.
