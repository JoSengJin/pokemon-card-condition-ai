# 평가 입력·결과 저장 안전성 — 2026-10-25

task `evaluation-input-output-safety-batch-20261025`. base `9369ea5ff2ea6f0a86181688afa27825658ded17`, 시작 HEAD `771a7a93a79b0f2c987f030f8a7d18c921c2d322`. 재사용한 최초 provenance worktree에서 새 브랜치로 진행한다.

이 묶음은 합성 사진·manifest·checkpoint metadata와 patch한 analyzer만 쓰는 **mock 소프트웨어 검증**이다. 실제 모델 학습·추론·성능 평가는 하지 않았다. 모델 품질 개선이나 전체 진척률 상승을 주장하지 않는다(진척률 30/100 그대로).

## 1. 입력·출력 계약과 정상 결과 기준

### 읽는 순서 (side `evaluate_sides` / region `evaluate_regions`)

| 순서 | region | side | 읽는 대상 |
|---|---|---|---|
| 1 | `input_hashes` | `input_hashes` | manifest·checkpoint·history 파일 바이트 SHA (가장 먼저) |
| 2 | `torch.load` | `load_manifest` | region은 checkpoint metadata, side는 평가 manifest(사진 디코드 해시 `_image_hashes` 계산) |
| 3 | `load_manifest` | `side_rows` | region은 평가 manifest, side는 manifest를 다시 읽음 |
| 4 | `track_photos` | `torch.load` | 평가 사진 바이트 SHA 기록 |
| 5 | `development_sets`, history 순회 | 〃 | history manifest 읽기와 사진 바이트 SHA 기록 |
| 6 | `region_rows`/`point_rows` | analyzer | 평가 manifest를 또 읽음 |
| 7 | analyzer 생성·추론 | 〃 | analyzer 생성자가 checkpoint를 다시 읽고 자체 `model_sha256` 계산 |
| 8 | `unchanged_inputs` | 〃 | 기록한 모든 바이트 SHA를 다시 계산해 비교 |
| 9 | 저장 | 〃 | 결과 JSON 저장 (`open('x')` → `json.dump`) |

세부 순서는 side에서 일부 다르다. 위 표는 두 경로의 읽기 경계를 합쳐 정리한 것이다.

### 의도된 차이 (통일하지 않음)

- region은 history가 필수다(`final` 개념 없음). side는 `final`에서만 history가 필수이고 `regression`은 history 없이도 가능하다.
  - 두 경우 모두 checkpoint metadata의 개발 이력은 검사한다.
- region은 point-grid 계열 checkpoint에서 gradable 요구를 해제한다. side는 항상 gradable을 요구한다.
- side `regression`은 평가 manifest에 test가 아닌 split이 섞여도 test 행만 평가한다. side `final`과 region은 test 외 split이 있으면 거절한다.
- 프로그램은 history가 실제로 완전하다는 것, 다른 사진이 같은 실물인지, 사람 정답이 맞는지를 증명하지 않는다. 제공된 범위의 ID·group·디코딩 사진 해시 충돌만 거절한다.

### 보존해야 할 출력 계약

- 보고서 필드·threshold 0.5·분모·`production_ready=false`·`actual_calls_saved=0`·`requires_gemini=true`는 그대로다.
- 기존 출력이 있으면 평가 전에 `ValueError('Output exists...')`로 거절하고, 평가 중 경쟁 출력이 생겨도 덮어쓰지 않는다.

### 수정 전 기준 보존 (ignored artifacts)

고정 경로에 합성 fixture를 만들고 mock analyzer로 두 평가기를 실행했다. 이 결과는 수정 후 같은 방법으로 다시 만들어 바이트 단위로 비교한다.

| 평가 | 수정 전 JSON SHA256 | 크기 | 권한 |
|---|---|---|---|
| region | `ebdb97798946afb53de995c3735cd25b764ebf8a499ffab47f8e1f11d4e5e516` | 10435 | 0644 |
| side | `4f30e222a5acc9c32cfe874356fdf04dbd17d1a4d2576f868752343d0413cc01` | 7989 | 0644 |

- 대상 source git blob: `evaluation_inputs.py` `854e0501…`, `region_evaluation.py` `24588de4…`, `side_evaluation.py` `7db7a7f6…`.
- 산출물은 Git 제외 경로 `artifacts/collaboration/evaluation-input-output-safety-batch-20261025/baseline/`에 있다.

## 구조 제한 (전)

| 파일 | 함수 정의 수 |
|---|---|
| card_condition/evaluation_inputs.py | 4 (`track_photos`, `reject_copied_test_groups`, `unchanged_inputs`, `development_sets`) |
| card_condition/region_evaluation.py | 1 (`evaluate_regions`) |
| card_condition/side_evaluation.py | 1 (`evaluate_sides`) |

호출 경로: `cli.main`(지연 import) → `evaluate_regions` / `evaluate_sides` → `evaluation_inputs.*` → `point_probe.digest`(전이 3). `evaluate_*` → `load_manifest`, `region_rows`/`side_rows` → `validate_annotations`는 기존 장거리 경로이며 이번 변경 범위가 아니다. 테스트는 analyzer 생성자를 patch한다.

## 2–6단계 결과

(단계별 커밋 후 기록한다.)
