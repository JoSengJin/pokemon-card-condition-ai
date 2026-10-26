# Codex 연속 개발 체크포인트 — 2026-10-26~27

개발 진척률 **30/100 (usable-card-analysis-v1.0), 이번 +0점**. 데이터 확보를 기다리며 독립시험·실사용 검토·운영 측정의 검증 공백을 보완했다. 모델 정확도·실사용 승인 조건의 달성을 주장하지 않는다.

검증 소스 최종 SHA: `c9e96079b5f885a2c155d800dec5cd761ec1e177`. 당시 origin/main과 일치하고 기본 checkout clean 확인. 세션 시작 기준 `d7adcf8` 이후 기능16묶음, 변경소스25개 모두 AST 함수<=7. 실제 코드별 근거/리스크/롤백은 아래 보고서에 기록했다.

## 개발 묶음과 근거

| 작업 | 주요 main 구현 | 결과 |
|---|---|---|
| [frozen-test-use](frozen-test-use-20261026.md) | `6694634` | 독립시험 입력 봉인과 실물/픽셀 사용 영수증. 재시도·다른 후보 재사용 차단. |
| [frozen-candidate-plan](frozen-candidate-plan-20261026.md) | `7900818` | 모델 묶음·소스·환경·device 고정과 사전계획 역할별 단일 평가. |
| [frozen-suite-assessment](frozen-suite-assessment-20261026.md) | `3553c49` | 고정 후보의 저장된 앞뒤/다섯질문 결과 결속과 C/D1/D3 수치 재집계. 인증은 false. |
| [release-null-checkpoint](release-null-checkpoint-20261026.md) | `66fd35c` | 명시 null release 항목을 모델 로딩 전에 구조화 오류로 거절. |
| [checkpoint-loaded-bytes](checkpoint-loaded-bytes-20261026.md) | `df72abf` | 구역/면별 모델의 실제 deserialize 바이트 SHA 기록. |
| [observation-loaded-bytes](observation-loaded-bytes-20261026.md) | `9e361e2` | 관찰모델 동일바이트 SHA 및 기존 학습계산 최소 분리, 이름 재노출 유지. |
| [listing-whole-scope-review](listing-whole-scope-review-20261026.md) | `28f3135` | 기존42구역 외 센터링/관찰제한4질문 검토와 별도 완료상태. |
| [pilot-short-write](pilot-short-write-20261026.md) | `72c7854` | 로그 부분쓰기를 성공계수에 넣지 않고 실패·증거 보존. |
| [pilot-fixed-cohort](pilot-fixed-cohort-20261026.md) | `27c6f20` | 동일 release 명칭의 다른 SHA와 혼합 실행구성의 F2 거짓통과 차단. |
| [frozen-judgment-identity](frozen-judgment-identity-20261026.md) | `91b8647` | 사진·면·구역·질문 중복 정답 단위와 동일사진 양면충돌 거절. |
| [observation-evaluation-model-sha](observation-evaluation-model-sha-20261026.md) | `c37dd49` | 관찰 독립평가의 실제 모델 SHA 대조와 alias 누락 검증오류. |
| [question-area-scope](question-area-scope-20261026.md) | `c103450` | 비해당 미확인과 해당 미확인 분리, 미지원 모델의 source 정답 수량 보존. |
| [pilot-review-conflicts](pilot-review-conflicts-20261026.md) | `225cce0` | 상충 완료 검토의 입력 순서 의존과 음수/bool/누락 수정 수량 차단. |
| [listing-loaded-checkpoint](listing-loaded-checkpoint-20261026.md) | `95eb546` | 검증용 매물 probe도 고정바이트 로딩, 관찰 모델 mismatch는 사진 analyze 전 거절. |
| [unsupported-truth-identity](unsupported-truth-identity-20261026.md) | `cc376c9` | 모델 미지원 질문에도 known source 단위 중복 수량 방지. |
| [frozen-report-loaded-bytes](frozen-report-loaded-bytes-20261026.md) | `ddd93db` | candidate/report/receipt의 hash와 JSON을 동일 snapshot으로 해석. fault 검사 독립화. |

## 이번 세션의 검증 범위

- 최근 기본 회귀129 PASS24.427s + 별도 확장34 PASS2.069s = 서로 다른163검사 통과. 단일163 runner를 실행한 것은 아니다. 신규3검사 worktree0.344s, 출력안전5검사0.139s도 별도 수행했다.
- 확장34 최초실행2오류: NaN mock을 복구하지 않아 디스크 오류 주입 전에 유효성 검사에서 중단. source guard를 완화하지 않고 정상 mock 복구/실제 json.dump 호출 검증/직접 부분 NaN쓰기 정리 검사로 보완한 뒤34 통과.
- 합성 이미지/랜덤 초기화 모델 forward 및 mock metadata/파일 오류 검사 포함. 실제사진 새추론0, 새학습0, 외부AI0. 기존 legacy 학습 실행 테스트는 선택하지 않았다.
- 실제 모델 결함 누락률/오탐률·실분모의 이전 대비 %p·독립 일반화 개선·Gemini 절감·속도 개선은 이번 세션에서 측정하지 않았다. 합성 fixture의 0오류는 품질 근거가 아니다.
- 모델 바이트/소스 SHA를 고정하므로 코드 변경 후 예전 candidate를 그대로 재사용하면 거절하는 것이 정상이다. 새 실제 시험은 사람 provenance/미사용/고정후보·기준을 먼저 확인해야 한다.
- 변경 소스 AST25개 확인, task별 compileall/diff PASS. 실제 changed path는 아래에 고정.

재현 명령 형식: `PYTHONPATH=tests .venv/bin/python`에서 `torch.set_num_threads(1)` 후 `unittest.defaultTestLoader.loadTestsFromNames(modules)`를 실행한다. 아래 두 배열은 각각 실행한 검사 목록이다.

기본129 모듈:
```json
[
  "test_frozen_report_loaded_bytes",
  "test_unsupported_truth_identity",
  "test_listing_loaded_checkpoint",
  "test_listing_inference",
  "test_listing_observation",
  "test_pilot_review_conflicts",
  "test_question_area_scope",
  "test_observation_evaluation_model_sha",
  "test_frozen_judgment_identity",
  "test_pilot_fixed_cohort",
  "test_pilot_short_write",
  "test_pilot_record",
  "test_pilot_summary",
  "test_listing_review_whole_scope",
  "test_listing_review",
  "test_listing_review_evidence",
  "test_observation_loaded_bytes",
  "test_checkpoint_loaded_bytes",
  "test_release_null_entries",
  "test_finite_logits",
  "test_frozen_candidate",
  "test_frozen_candidate_evaluation",
  "test_frozen_test",
  "test_frozen_test_evaluation",
  "test_evaluation_suite_inputs",
  "test_evaluation_suite",
  "test_evaluation_suite_safety",
  "test_physical_uncertainty",
  "test_physical_uncertainty_evaluation",
  "test_evaluation_inputs"
]
```

별도34 모듈:
```json
[
  "test_release",
  "test_listing_model",
  "test_listing_readiness",
  "test_inference_memory",
  "test_evaluation_consistency_contract",
  "test_evaluation_provenance_contract",
  "test_evaluation_identity_contract",
  "test_evaluation_output_safety",
  "test_evaluation_point_probe_compatibility",
  "test_benchmark_inputs"
]
```

## UI와 HTML의 실제 확인 범위

- 전체질문 검토 합성 UI의42+4행·옵션·가로 overflow 없음은 당시 브라우저 DOM/스크린샷으로 확인했다. JSON 다운로드 허용은 사용자가 거절하여 클릭/다운로드 파일의 CLI 결속은 미검증이며 우회·재시도하지 않았다. 관련 합성 CLI/기록 계약은 단위검사로 확인한 별개 근거다.
- 작업별 성과 HTML과 cleanup HTML 생성·내용 대조·open_in_codex 열기요청 수행. 도구결과 queued이며 실제 렌더 확인으로 보고하지 않는다. 보고 전용 서버는 시작하지 않았다. 당시 합성 UI 서버는 종료하고 해당 임시 탭도 닫았다.

## 고정 진척과 남은 의존

- PROGRESS_CRITERIA.md/development-progress.json 재확인: A1/A2/B1/B2/B3/E1 각각5점, 합계30. 기준/배점/점수/history를 변경하지 않았다. Git 비교에서 data/models/진척 두파일 변경0 확인.
- A3: Claude 확보자료의 출처·실물 그룹·split·사람 정답 및 전체셀의 양성/정상 수량 확인이 선행되어야 한다. 준비된 후보를 정답으로 추정하지 않는다.
- C: 동일 후보·동일 정답/분모의 앞뒤 다섯질문 품질 및 올바른 종류 실제점 응답 조건이 필요하다. 이번 개발로 실제품질 통과를 선언하지 않는다.
- D: 새 도구는 입력 무결성/사용기록/수치조건을 검사한다. D1/D2/D3 독립 인증은 여전히 false이며 실제 사람 provenance·이력 감사가 필요하다.
- E/F: 추가4질문 검토 구현만으로 E2 가점하지 않았다. 브라우저 다운로드 검증은 미완료이며 실사용7일/50카드/100요청·고정배포·정상카드오탐/복구 근거를 합성검사로 대체하지 않는다.

## 리스크·롤백·정리

- 모델/JSON snapshot은 실제 해석바이트와 SHA를 결속하지만 로딩 중 메모리를 추가 사용한다. 대형 실checkpoint/보고서 메모리 실측은 미수행.
- 미지원known 중복·불완전/상충 검토·혼합릴리스는 이제 보수적으로 거절하거나 unknown을 유지한다. 원본 데이터/기록을 자동 수정하지 않는다.
- 각 보고서의 main 구현 SHA를 `git revert <sha>`로 되돌리고 관련 회귀 후 일반push. 다파일 기능을 전체철회할 때는 후속 의존 커밋을 먼저 확인하고 최신부터 역순 검토한다. 임의 reset/force/rewrite 금지.
- 최신 완료 롤백 checkout: `codex/frozen-report-loaded-bytes-20261026` (tip bc24616). 이전 Codex 완료 checkout은 exact cherry-pick/clean/원격/배타lock 확인 후 일반 remove. lock metadata는 ignored cleanup artifact에 보존했다. Claude 및 사용·통합 불명확 checkout은 모두 보존했다.
- cleanup 근거: ignored artifacts/worktree-cleanup-session-20261026/index.html 및 task별record.json. 이번 체크포인트의 rollback 명령은 부작용 없는 자동 실행 약속이 아니다.

## 변경 파일 목록 (문서 체크포인트 작성 전)

```text
card_condition/cli.py
card_condition/evaluation_inputs.py
card_condition/evaluation_suite.py
card_condition/evaluation_suite_cli.py
card_condition/evaluation_suite_inputs.py
card_condition/evaluation_suite_metrics.py
card_condition/frozen_candidate.py
card_condition/frozen_candidate_cli.py
card_condition/frozen_test.py
card_condition/frozen_test_cli.py
card_condition/listing_inference.py
card_condition/listing_observation.py
card_condition/listing_review.py
card_condition/observation_fitting.py
card_condition/observation_heldout.py
card_condition/observation_side_diagnostics.py
card_condition/physical_uncertainty.py
card_condition/pilot_record.py
card_condition/pilot_summary.py
card_condition/region_evaluation.py
card_condition/region_model.py
card_condition/release.py
card_condition/side_evaluation.py
card_condition/side_model.py
card_condition/visibility_model.py
docs/collaboration/reports/checkpoint-loaded-bytes-20261026.md
docs/collaboration/reports/frozen-candidate-plan-20261026.md
docs/collaboration/reports/frozen-judgment-identity-20261026.md
docs/collaboration/reports/frozen-report-loaded-bytes-20261026.md
docs/collaboration/reports/frozen-suite-assessment-20261026.md
docs/collaboration/reports/frozen-test-use-20261026.md
docs/collaboration/reports/listing-loaded-checkpoint-20261026.md
docs/collaboration/reports/listing-whole-scope-review-20261026.md
docs/collaboration/reports/observation-evaluation-model-sha-20261026.md
docs/collaboration/reports/observation-loaded-bytes-20261026.md
docs/collaboration/reports/pilot-fixed-cohort-20261026.md
docs/collaboration/reports/pilot-review-conflicts-20261026.md
docs/collaboration/reports/pilot-short-write-20261026.md
docs/collaboration/reports/question-area-scope-20261026.md
docs/collaboration/reports/release-null-checkpoint-20261026.md
docs/collaboration/reports/unsupported-truth-identity-20261026.md
docs/collaboration/tasks/checkpoint-loaded-bytes-20261026.md
docs/collaboration/tasks/frozen-candidate-plan-20261026.md
docs/collaboration/tasks/frozen-judgment-identity-20261026.md
docs/collaboration/tasks/frozen-report-loaded-bytes-20261026.md
docs/collaboration/tasks/frozen-suite-assessment-20261026.md
docs/collaboration/tasks/frozen-test-use-20261026.md
docs/collaboration/tasks/listing-loaded-checkpoint-20261026.md
docs/collaboration/tasks/listing-whole-scope-review-20261026.md
docs/collaboration/tasks/observation-evaluation-model-sha-20261026.md
docs/collaboration/tasks/observation-loaded-bytes-20261026.md
docs/collaboration/tasks/pilot-fixed-cohort-20261026.md
docs/collaboration/tasks/pilot-review-conflicts-20261026.md
docs/collaboration/tasks/pilot-short-write-20261026.md
docs/collaboration/tasks/question-area-scope-20261026.md
docs/collaboration/tasks/release-null-checkpoint-20261026.md
docs/collaboration/tasks/unsupported-truth-identity-20261026.md
tests/test_checkpoint_loaded_bytes.py
tests/test_evaluation_output_safety.py
tests/test_evaluation_suite.py
tests/test_evaluation_suite_inputs.py
tests/test_evaluation_suite_safety.py
tests/test_frozen_candidate.py
tests/test_frozen_candidate_evaluation.py
tests/test_frozen_judgment_identity.py
tests/test_frozen_report_loaded_bytes.py
tests/test_frozen_test.py
tests/test_frozen_test_evaluation.py
tests/test_listing_inference.py
tests/test_listing_loaded_checkpoint.py
tests/test_listing_review_whole_scope.py
tests/test_observation_evaluation_model_sha.py
tests/test_observation_heldout.py
tests/test_observation_loaded_bytes.py
tests/test_physical_uncertainty_evaluation.py
tests/test_pilot_fixed_cohort.py
tests/test_pilot_review_conflicts.py
tests/test_pilot_short_write.py
tests/test_pilot_summary.py
tests/test_question_area_scope.py
tests/test_release_null_entries.py
tests/test_unsupported_truth_identity.py
```

최종 보고서 전 원격 SHA/사용량을 다시 조회한다. 마지막 실제 확인 사용량은99%이며 한도 도달을 미리 주장하지 않는다. 상시 승인에 따라 검증한 변경은 재확인 없이 main 일반push를 계속 적용한다.

종합 HTML도 열기도구queued: 요청 전달, 실제 렌더 미확인.
