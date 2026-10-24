# ㄴ 라벨 반영·동일 검증셋 대조 — 2026-10-10

## 결과

ㄴ의 앞뒤 영역과 뒷면 표면 결함3점 저장을 확인했다. 사용자가 앞면 표면 전체를 충분히 확인했고 정상이라고 추가로 명시하여 앞면 표면9구역0을 기록했다. 다른 결함 종류는 null 유지, 전체 gradable·pair_verified도 추정하지 않았다. ㄴ의 기존 기스/화이트닝/자국 표시는 사람이 선택한 표면 종류 그대로 보존했다. ㄴ은 모델 출력 확인 전에 train으로 지정했고 기존 val/test는 이동하지 않았다.

학습 입력은91→103구역, 실물1개 추가. 검증50구역·실물8그룹은 사진 해시·좌표·종류별 정답 모두 동일하게 유지했다. val의 표면 정상19구역은 실물3그룹, 표면 결함19구역도 실물3그룹이다. 구역 수를 독립 카드 수로 해석하지 않는다.

| 종류 | 보강 전 FP/FN | ㄴ 보강 후 FP/FN |
|---|---|---|
| 모서리 | 6/0 | 6/0 |
| 엣지 | 12/0 | 12/0 |
| 표면 | 19/0 | 19/0 |

모든 알려진 정상 항목을 결함으로 판정해 후보 채택은 계속 보류한다. 같은 기준0.5에서 지표가 개선되지 않았으며 확률이 같다는 뜻은 아니다. ㄴ 자체에 대한 학습 성능을 검증 성능으로 사용하지 않았다. ㄴ 라벨 재확인 요청 없이 완료 처리하며, 새 라벨이 들어오기 전 같은 재학습을 반복하지 않는다. Gemini 호출 절감0건, 운영 모델 변경 없음.

## 재현과 산출물

- 변경 전 라벨 백업: `data/learn-review-before-n-front-normal-20261010.jsonl.bak`.
- 사람 확인/원본 해시/기존 train·val 불변 영수증: `artifacts/point-evidence-round10-receipt.json`.
- snapshot: `artifacts/point-evidence-20261010-round9.jsonl` / `artifacts/point-evidence-20261010-round10.jsonl`.
- 대조 모델: `artifacts/point-grid-control-20261010-round9-epochs20/model.pt`, 선택 epoch9.
- 보강 모델: `artifacts/point-grid-augmented-20261010-round10-epochs20/model.pt`, 선택 epoch10.
- 비교: `artifacts/point-grid-round10-comparison-20261010.json`.

양쪽 모두 MobileNetV3 Small ImageNet 고정 특징, head 학습, seed42·224px·20epochs·MPS·실물 동등 가중치 설정. val에 ㄱ이 추가됐으므로 옛 round8 val38구역 지표와 직접 전후 비교하지 않고 round9 대조 모델을 별도로 학습했다.

```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition point-experiment artifacts/point-evidence-20261010-round9.jsonl artifacts/new-control --epochs 20
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition point-experiment artifacts/point-evidence-20261010-round10.jsonl artifacts/new-augmented --epochs 20
.venv/bin/card-condition point-compare artifacts/point-evidence-20261010-round10.jsonl artifacts/new-comparison.json artifacts/new-control/report.json artifacts/new-augmented/report.json --reference artifacts/point-evidence-20261010-round9.jsonl
```

## 코드·검증

- `card_condition/comparison.py`: 기존 검산기를 재사용하는 선택적 point_grid 입력/보고서 종류 처리. 기본 region 비교 동작 유지.
- `card_condition/cli.py`: 별도 point-compare 명령.
- `tests/test_point_comparison.py`: train만 변경한 비교 허용, val 영역 변경/위조 혼동행렬/산출물 덮어쓰기 차단, test 사진 미열람 검증.
- `README.md`, `pyproject.toml`0.4.16, 이 문서, 마스터 TODO 갱신.
- 원본 라벨 `data/learn-review.jsonl`: ㄴ 앞면 명시적 표면9구역0과 확인 근거만 추가. 다른 항목 불변 assert 통과.

전체 Python56개 통과(`/private/tmp/condition-point-comparison-tests.log`). 실제 학습 두 번 및 point-compare 실행 완료. 로그: `/private/tmp/condition-round9-control.log`, `/private/tmp/condition-round10-train.log`, `/private/tmp/condition-round10-comparison.log`.

후속 assert 검증 통과: 학습 중 원본 라벨 SHA256 불변, 기존 train/val 입력 전체 동일, 기존 round6/round8 체크포인트 SHA256 불변. 0.4.16 wheel 빌드 성공(`/private/tmp/condition-round10-wheel.log`), wheel의 cli.py/comparison.py가 현재 소스와 바이트 단위 일치. 새 환경 설치·미사용 최종시험·소비 앱 통합은 미실행.

## 리스크·롤백

이 검증셋은 모델선택에 노출된 개발 자료이며 최종시험이 아니다. 신규 실물1개 보강만으로 디자인·관찰 조건 다양성이 충분해졌다고 주장할 수 없다. 정상 과탐이 계속돼 구매 판단이나 Gemini 생략에 사용하지 않는다. 필요한 다음 자료는 서로 다른 실물의 정상 앞면과 정상 뒷면 엣지이며, 완료한 ㄴ을 같은 이유로 재요청하지 않는다.

코드 롤백은 compare_regions의 point_grid 선택 분기와 신규 CLI/테스트/문서/버전을 되돌린다. 모델은 별도 디렉터리라 기존 파일 복구가 필요 없다. 데이터 롤백이 꼭 필요하면 백업에서 ㄴ의 이번 추가 필드만 복원하고 이후 사람 저장을 덮어쓰지 않는다. 사람 확인 라벨은 모델 성능이 나쁘다는 이유로 삭제/변경하지 않는다.
