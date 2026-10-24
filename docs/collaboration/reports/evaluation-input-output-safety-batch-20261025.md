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

### 커밋 순서

| 단계 | 커밋 | 내용 |
|---|---|---|
| 1 | `ad83431f1b307aa418cbcbb0fed86060695d24f9` | 이 보고서 1절: 읽기 순서·출력 계약·수정 전 기준, task status `implementing` |
| 2 | `07d583b513878db64fb31dd5098dd0e90c9ecfe6` | `tests/test_evaluation_provenance_contract.py`, `tests/test_evaluation_identity_contract.py` (통과, source 변경 없음) |
| 3 | `b1a7ef36be19c97fa64619e0e86714a1b6b5f0a8` | `tests/test_evaluation_consistency_contract.py` (재현: 실패 4건) |
| 4 | `add4601ac4dc0ffa6eca0f1b7a427988589d77c8` | `tests/test_evaluation_output_safety.py` (재현: 실패 2건·import 오류 1건) |
| 5 | `f8463f54c74082068a657fce529780e1b89f9ca0` | **fix**: 허용 source 4개 최소 수정 (검증 코드 SHA) |
| 6 | 이 문서 커밋 | 최종 보고·HTML·task 기록, status `ready_for_review` |

### 재현된 결함과 수정

모두 먼저 실패하는 검사로 커밋(3·4단계)한 뒤 5단계에서 수정했다. side와 region에서 각각 재현됐다.

1. **사진 디코드 → 바이트 SHA 기록 사이의 변경**
   - 원인: `load_manifest`가 사진을 디코드해 `_image_hashes`(identity 검사에 쓰임)를 만든 뒤, `track_photos`가 파일을 다시 읽어 SHA를 기록했다. 그 사이에 사진이 바뀌면 identity는 원본 픽셀, 기록 SHA는 교체본에 대한 값이 되고, 이후 최종 SHA 대조는 교체본끼리 비교하므로 통과했다.
   - 수정: `track_photos`가 파일을 한 번만 읽고, 같은 바이트의 디코드 identity가 `_image_hashes`와 다르면 거절한다. SHA도 그 바이트에서 계산한다.
2. **analyzer가 기록과 다른 checkpoint를 읽어도 성공**
   - 원인: 평가기는 시작 시 checkpoint SHA를 기록했지만, analyzer 생성자가 checkpoint를 다시 읽어 계산한 `model_sha256`과 대조하지 않았다.
   - 수정: `matched_model`이 analyzer의 `model_sha256`과 기록 SHA를 대조한다.
3. **저장 중 실패하면 부분 보고서가 남음**
   - 원인: `open('x')` 뒤 `json.dump`가 쓰다 실패하면 최종 경로에 일부만 쓴 파일이 남아, 재시도도 'Output exists'로 막혔다.
   - 수정: 같은 폴더 임시 파일 → flush/fsync → `os.link`(덮어쓰기 없음)로 완성된 보고서만 공개한다. 평가 시작 전 기존 출력 거절은 그대로다.

### 정상 결과 동일성

수정 전 `HEAD`(`771a7a9`)와 수정 후(`f8463f5`)에서 같은 합성 fixture로 두 평가기를 mock analyzer로 실행해 비교했다. 고정 경로의 Git 제외 산출물(`artifacts/collaboration/evaluation-input-output-safety-batch-20261025/baseline/`)에 보존했다.

| 평가 | JSON SHA256 (수정 전 = 수정 후) | 바이트 비교 |
|---|---|---|
| region | `ebdb97798946afb53de995c3735cd25b764ebf8a499ffab47f8e1f11d4e5e516` | 동일 |
| side | `4f30e222a5acc9c32cfe874356fdf04dbd17d1a4d2576f868752343d0413cc01` | 동일 |

- 대상 source git blob: 수정 전 `854e0501…`, `24588de4…`, `7db7a7f6…` → 수정 후 `e24a08e6…`, `bce33a80…`, `09324499…`, 신규 `85ea1204…`.
- **차이 하나**: 새 파일 권한이 0644 → 0600이다(임시 파일 공개 방식). 기존 `data_coverage`·`side_evidence_cli`와 같은 방식이다. 유지할지는 Codex 결정이다.

### 사례별 검사 대응

| 계약 항목 | 검사 | 결과 |
|---|---|---|
| checkpoint metadata와 ID·group·디코드 해시 겹침 → analyzer 생성 전 거절 | provenance::`test_checkpoint_metadata_overlap_by_id_group_or_decoded_pixels` | 통과 |
| history와 ID·group 겹침, 재인코딩 복사본(다른 id·group) 거절 | provenance::`test_history_overlap_by_id_group_or_pixels_under_another_identity` | 통과 |
| final의 history 누락, 잘못된 개발 metadata 7종 | provenance::`test_final_requires_history_and_valid_development_metadata` | 통과 |
| 혼합 split | provenance::`test_mixed_split_manifest_is_refused_before_the_analyzer` | 통과 |
| 서로 다른 group이 같은 픽셀을 복사(바이트가 다른 재인코딩 포함) 거절 | identity::`test_copied_pixels_under_two_groups_are_refused_even_when_reencoded` | 통과 |
| 같은 카드의 동일 픽셀 앞뒤는 허용, 바이트 SHA와 디코드 SHA 구분 | identity::`test_same_card_may_reuse_pixels_and_byte_hashes_stay_distinct` | 통과 |
| 서로 다른 group·픽셀은 배제하지 않음 | identity::`test_distinct_groups_with_distinct_pixels_are_not_excluded` | 통과 |
| 읽히기 전 manifest·history·checkpoint 변경 → 최종 SHA 대조로 거절 | consistency::`test_inputs_changed_after_the_first_hash_but_before_being_read_never_save` | 통과 |
| 사진 디코드 ↔ SHA 기록 사이 변경 | consistency::`test_photo_changed_between_decoding_and_hash_recording_is_not_recorded_as_read` | 수정 전 실패, 수정 후 통과 |
| analyzer가 다른 checkpoint를 읽음 | consistency::`test_analyzer_that_read_another_checkpoint_than_the_recorded_one_is_refused` | 수정 전 실패, 수정 후 통과 |
| 저장 JSON = 반환 보고서 | output::`test_saved_json_is_exactly_the_returned_report` | 통과 |
| 쓰기 실패(NaN 부분 쓰기, ENOSPC) 후 최종 파일·임시 파일 없음, 재시도 성공 | output::`test_failure_while_writing_leaves_no_report_and_the_retry_succeeds` | 수정 전 실패, 수정 후 통과 |
| 기존 출력·입력 파일·dangling symlink를 출력 경로로 쓸 수 없음 | output::`test_existing_output_is_refused_before_any_work_and_inputs_cannot_be_replaced` | 통과 |
| 평가 중 생긴 경쟁 출력 보존 | output::`test_competing_output_created_during_the_run_is_preserved` | 통과 |
| fsync·link 실패, 경쟁 파일 | output::`test_publisher_survives_sync_and_link_failures_without_clobbering` | 수정 전 import 오류, 수정 후 통과 |

- analyzer는 모두 `unittest.mock`으로 대체했다. 생성자를 patch하고, 거절 사례에서는 생성자·`analyze`·`predict`가 호출되지 않았음을 확인했다. 실제 backbone·feature·fit은 실행되지 않았다. checkpoint는 `torch.save`한 작은 metadata dict뿐이다.
- 지표 알고리즘과 geometry·unknown·supported label 분모 계산은 이번에 변경하지 않았다. 정상 입력에서 `rates_at_05.corner_defect.scored`가 4임을 기존 검사와 identity 검사가 확인한다.

### 보류·한계 (재현은 했으나 이 범위에서 해결하지 않음)

- **A→B→A**: 읽는 순간에만 바뀌고 되돌려지는 manifest·history·checkpoint는 최종 SHA 대조로 막을 수 없다. 해결에는 읽은 바이트를 그대로 쓰는 snapshot 구조가 필요하며, 계약상 범용 snapshot 체계는 만들지 않는다. 사진과 checkpoint는 이번 수정으로 좁혔지만 완전 해결은 아니다.
- **regression vs final**: side `regression`은 history 없이도 평가된다(의도된 차이). checkpoint metadata의 개발 이력 검사는 그대로 적용된다.
- 출력 폴더가 없으면 평가를 모두 마친 뒤에야 실패한다(부분 파일은 남지 않음).
- hardlink 미지원 파일 시스템에서는 저장이 실패한다. 강제 종료 시 `.<이름>.*.tmp`가 남을 수 있고, 전원 상실 내구성은 보장하지 않는다.
- `track_photos`의 다른 호출자 `point_probe`는 실제 모델이 필요해 실행하지 못했다. 같은 loader 행(`_image_hashes`)을 쓰는 것만 확인했다.

### mutation 대조 (임시 복사본, 신규 4모듈 + 기존 1모듈)

11가지를 바꿔 돌렸고 모두 검출됐다: 디코드 대조 제거, 바이트 대조 제거, `matched_model` 무력화, region·side 각각의 호출 제거, 출력을 덮어쓰기로 변경, 임시 파일 없이 직접 쓰기, `unchanged_inputs` 제거(region·side), 개발 ID 충돌 검사 제거(region), 디코드 해시 충돌 검사 제거(side).

### 구조 제한

| 파일 | 함수 정의 수 (전 → 후) |
|---|---|
| card_condition/evaluation_inputs.py | 4 → 5 |
| card_condition/region_evaluation.py | 1 → 1 |
| card_condition/side_evaluation.py | 1 → 1 |
| card_condition/evaluation_output.py | 신규 1 |
| tests/test_evaluation_provenance_contract.py | 신규 6 |
| tests/test_evaluation_consistency_contract.py | 신규 6 (`Rewrite` 클래스의 메서드 2 포함) |
| tests/test_evaluation_output_safety.py | 신규 7 |
| tests/test_evaluation_identity_contract.py | 신규 7 |

- 모두 7개 이하이며 lambda는 없다. 중첩 함수를 피하려 mock의 `side_effect`·클래스 호출·SimpleNamespace를 썼고, 서로 다른 책임을 합치지 않았다.
- 주요 호출 경로:
  - 전: `evaluate_*` → `track_photos` → `digest` (전이 2), `evaluate_*` → `unchanged_inputs` → `digest` (2).
  - 후: 위와 같고 `evaluate_*` → `matched_model` (1), `evaluate_*` → `write_new_report` (1)이 추가됐다. 최대 전이 2로 제한 4 이내다.
- 동적 경로: `cli.main`이 평가기를 지연 import한다. 정적으로 추적되지 않는 호출은 이 import뿐이며 테스트는 모듈을 직접 호출했다.

### 검사 결과

- `PYTHONPATH=tests .venv/bin/python -m unittest test_evaluation_inputs test_evaluation_provenance_contract test_evaluation_consistency_contract test_evaluation_output_safety test_evaluation_identity_contract -v` → 20개 통과(기존 5, 신규 15), 종료코드 0.
- `compileall` 종료코드 0. `git diff --check` 통과.
- 실행하지 않음: test_side_evaluation, test_region_evaluation, test_point_final_evaluation, test_pipeline 전체(실제 학습·추론 포함), 실자료·실제 모델.
- 이 worktree의 `.venv`에서 `card_condition.__file__`가 이 worktree를 가리킨다.

### 성과·진척 HTML

`docs/collaboration/reports/evaluation-input-output-safety-batch-20261025.html`. 정적 HTML/CSS이며 외부 CDN·스크립트·개인 경로가 없다. 모델 성능을 평가하지 않았으므로 정확도 그래프는 없다. 열기: 내장 브라우저의 file:// 접근이 거절돼 macOS `open`으로 요청했고 종료코드 0이었다(열기 요청 성공, 화면 렌더는 확인하지 못함). 구조는 파서로 검사했다(태그 짝 오류 0, script·외부 링크·개인 경로 0).

### 미검증·리스크·롤백

- 미검증: `point_probe`의 `track_photos` 경로, 실제 모델·사진으로 한 평가, Codex의 main 통합 검사.
- 리스크:
  - mock 소프트웨어 검증이며 모델 성능이나 일반화를 말하지 않는다.
  - `track_photos`가 사진을 한 번 더 디코드하므로 평가 입력 로딩 시간이 늘어난다.
  - 새 파일 권한 0600.
  - A→B→A는 막지 못한다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 수정 커밋 `f8463f5…`를 revert하면 이전 동작으로 돌아가고, 테스트·문서 커밋은 따로 revert할 수 있다. 모델·라벨 복구는 필요 없고 진척 점수 30/100은 그대로다.
