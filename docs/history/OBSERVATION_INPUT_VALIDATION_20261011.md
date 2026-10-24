# 관찰 제한 입력 보완 개발 — 0.4.39 / 2026-10-11

## 완료 결과

관찰 제한 모델에 고정 전처리 비교 경로와 제한 사유별 누락 진단을 구현했다. 같은 사진·라벨·고정 특징 추출기·centroid 분류 방식에서 입력만 바꿔 실제 비교했다. 전처리 후보는 성능이 악화해 채택하지 않았다. 사람 라벨과 운영 경로는 수정하지 않았으며 실제 Gemini 절감은 0건이다.

## 가설과 설계

사진 바깥 배경·카드 테두리가 제한 여부보다 강한 단서로 작용하는지 확인하기 위해 정답과 무관한 중앙90% crop을 사전 고정했다. 각 축 양 끝5%를 제거한다. baseline은 기존 전체 box다. 동일 snapshot/46학습면/24검증면, frozen MobileNetV3 Small, 동일 train-only weighted centroid를 사용한다. 최종 test는 사용하지 않는다.

이것은 자동 배경 분할이나 정확한 카드 검출이 아니다. 카드 box 자체가 사진 전체인 신규 사진에서는 배경이 남을 수도 있다. 테두리의 실제 제한 단서도 제거하므로 실패를 배경 혼동의 인과 증명으로 해석하지 않는다. 카드 손상 판정에 사용하거나 낮은 점수로 사람 관찰 제한을 해제할 수 없다. 고해상도 원본/같은 실물의 비교 사진이 없다는 기존 응답을 유지하며 완료 라벨을 다시 요청하지 않는다.

## 실제 비교

| 입력 | 오탐 / 누락 | AUROC | AP | balanced BCE |
|---|---|---|---|---|
| 전체 box | 7 / 4 | .4874 | .4262 | .6984 |
| 중앙90% | 7 / 4 | .3950 | .3738 | .7016 |

무정보 balanced BCE 기준은 .6931이다. 두 후보 모두 기준 미달이고 전처리 후보는 순위 지표도 악화했다. 운영 후보로 채택하지 않는다. 전체 혼동행렬이 같다는 이유로 개별 사진 판정까지 동일하다고 해석하지 않는다. 동일 FP 예산의 탐지 결과는 `artifacts/observation-input-comparison-20261011.json`에 저장했다.

새 `reason_diagnostics`는 사람 정답 사유로 검증 결과를 나눈 진단이다. 모델이 glare/blur 등을 종류별로 예측하는 다중 분류 기능은 아니다. 여러 사유가 있는 사진은 중복 집계한다. glare는 검증4면 중2면 누락, blur1/1 누락, obstruction1/1 누락, perspective1/2 누락이다. cropped는1면 탐지했다. 사유별 표본이 작으므로 일반 성능으로 확대하지 않는다.

blur 학습0면에는 `no_training_support`, shadow 검증0면에는 `no_validation_support`를 기록한다. 검증 사례가 없는 recall은0이 아니라 null이다. 사진 부족과 실패를 구분한다.

## 변경 파일

- `card_condition/visibility_model.py`: 기존 이미지 특징 함수 재사용, 선택 interior90 전처리, checkpoint 저장/추론 동일 적용, 구형 기본box 호환, 사유별 진단.
- `card_condition/cli.py`: `visibility-experiment --interior` 옵션.
- `tests/test_visibility_model.py`: 실제 crop 좌표, 원본 row 불변, checkpoint roundtrip, 정책 검증, 검증 사례 없는 사유의 null 유지.
- `pyproject.toml`0.4.39, `README.md`, 본 보고서, 마스터 TODO.
- `artifacts/observation-interior-20261011/`, `artifacts/observation-input-comparison-20261011.json`.

새 외부 의존성은 추가하지 않았다. PyTorch·torchvision·Pillow와 기존 전처리/추론 경로로 구현했다.

## 사용법

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition visibility-experiment artifacts/observation-jieut-20261011-source.jsonl artifacts/NEW-DIRECTORY --centroid --interior --device mps
.venv/bin/card-condition visibility-compare artifacts/observation-centroid-20261011/report.json artifacts/observation-interior-20261011/report.json
```

기본 옵션은 전체 box를 유지한다. 새로운 실험 디렉토리를 사용해야 한다.

## 추가 설계·기술 판단

단순 crop이 충분하다는 가설은 지지되지 않았다. 다음 입력 실험에는 카드 윤곽을 보존하면서 배경만 다루는 경로가 더 적합한 후보지만, 정밀 윤곽 정답이 없는 사진에 임의의 box를 정답으로 만들면 안 된다. 카드 검출·분할 또는 촬영 제한의 위치별 분석은 별도 검증 대상이다. 이번 결과만으로 OpenCV·검출 모델·대형 VLM 도입이 필수라고 결론내리지 않는다.

그늘·흐림처럼 종류별 자료 공백을 먼저 보존하고 독립 검증 자료가 확보될 때 일반화 판단을 한다. 새 프레임워크나 학습 반복만으로 현재 문제를 해결할 근거는 없다. 정확도 개선은 이번에 달성하지 못했지만, 입력 가설의 실패와 종류별 지원 공백을 재현 가능하게 확인했다.

## 검증·리스크·롤백

새 checkpoint의 실제24면 MPS 재추론을 확인했고 원본/동결 snapshot 해시와 live 라벨이 불변임을 검증했다. 전처리로 제한 위치가 사라질 수 있으므로 탐색 전용이며 Gemini fallback을 유지한다. 서버/UI 재시작이 필요한 변경은 없다.

코드 롤백은 `.backups/observation-input-0439/`의5파일을 이후 변경 여부 확인 후 복원한다. 새 artifacts는 기록으로 보존할 수 있다. 사람 데이터는 수정하지 않아 데이터 롤백이 필요 없다.

최종 검증 기록: 전체84테스트 통과. wheel0.4.39 빌드 성공 및 Python/HTML34파일 소스 byte 일치. 24면 checkpoint 재추론 최대오차0.0. 실제 라벨 UI 저장은 이번 변경 범위가 아니므로 재검증하지 않았다.
