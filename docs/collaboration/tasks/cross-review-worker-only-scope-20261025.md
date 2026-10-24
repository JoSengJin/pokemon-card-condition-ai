# 교차 검토 worker-only 실험의 사전 탈락 수정

- task_id: `cross-review-worker-only-scope-20261025`
- owner: Claude
- status: ready_for_review
- base_sha: `aa3e745` (main, 시작 시점)
- branch: `claude/cross-review-worker-only-scope-20261025`
- worktree: 세션 전달 메시지에서만 로컬 경로 제공

## 목표

`artifacts/manual-cross-review/978cc047dc49/`처럼 격리 worker만으로 적용 가능한 단일 변수 실험(penalty 1.0→0.5)이
"허용된 모델 파일을 수정할 수 없음"이라는 이유만으로 Gemini·NVIDIA 단계 전에 stop되지 않도록,
검증 오류와 Codex 검토 입력에 worker-only 경로를 명확히 전달한다.

## allowed_files

- `card_condition/cross_review_auto.py`
- `tests/test_cross_review_worker_only_scope.py` (신규, 검증·입력)
- `tests/test_cross_review_worker_only_flow.py` (신규, mock 흐름)
- `docs/collaboration/tasks/cross-review-worker-only-scope-20261025.md` (신규)

그 외는 읽기 전용이다. `cross_review_flow.py`, `cross_review_execution.py`, `trusted-experiment.json`, `nemotron-review.json`, 라벨·사진·모델·artifacts 변경 금지.

## contract

- Codex의 stop/wait를 프로그램이 select로 바꾸지 않는다. 정당한 stop/wait, 개발 승인 게이트, 호출 상한(Codex verify·correct·implement 각 1회, Gemini 상한), 실패 가설 반복 거절, 롤백은 그대로 둔다.
- `implementation_files`는 계속 기존 `card_condition` 모델 소스만 허용한다(새 worker 경로는 여전히 오류). 바뀌는 것은 오류 문구와 검토 입력의 설명뿐이다.
- 수정 불가(`editable=false`) 소스는 수정 대상이 아니라는 뜻이며 worker import·인자 지정 가능 여부를 부정하지 않는다는 사실을 입력에 명시한다.
- correct 입력은 기존 32,000 bytes 상한 안에 있어야 한다(상한 값 변경 금지).

## structure

- `card_condition/cross_review_auto.py` 함수 수 45 → 45(신규 함수 없음). 바뀐 호출: `review_context → read(trusted-experiment.json)` 1회 전이 추가, `verdict_errors.check_code_sources → model_file` 기존 전이 유지(예외 문구만 교체).
- 신규 테스트 파일 함수 수: scope 5, flow 5(중첩 backend 포함). 기본 checkout의 미커밋 PAIR_CODING 2.1 초안(함수 ≤7·깊이 ≤4) 기준으로 확인했다. 기존 `cross_review_auto.py`의 45개는 이번 작업 전부터의 상태다.

## checks

- 저장 기록 대조: 978cc047dc49 `automation.json`, `codex/*/input.json`.
- 신규 mock 테스트가 수정 전 실패·수정 후 통과.
- 관련 기존 테스트: `test_cross_review_auto`, `test_cross_review_contract_errors`, `test_cross_review_high_fixes`.
- 실제 Codex·Gemini·NVIDIA 호출, 학습, 사진 추론, 라벨 변경 없음.

## experiment

없음. 성능 변화 주장 없음.

## Claude 실행 결과 (2026-10-25)

### 원인 (저장 기록 근거)

1. `codex/verify-d3b7859615c01c97/call.json`: Codex가 penalty 1.0→0.5를 `select`하면서 새 worker 경로 `artifacts/surface-penalty-half-20261024/worker.py`를 `implementation_files`에 넣었다.
2. `verdict_errors.check_code_sources`(수정 전 `cross_review_auto.py:678-679`)가 `model_file`(`:59-65`)의 일반 문구 `Only existing model Python files are editable`만 반환했다. 어떤 파일이 왜 틀렸는지, worker는 별도 출력이고 빈 목록이 가능하다는 정보가 없었다.
3. `codex/correct-01e63b4f631387af/input.json`: `correction.errors`의 위 문구, `source_context`의 `confounder_head.py editable=false`만 전달됐다. 실제 격리 실행은 `trusted-experiment.json`의 `trainer_sources`(confounder_head.py)를 복사·import 가능하게 하지만(`cross_review_execution.py:227-228`), 이 사실은 implement 단계 `isolated_execution`에만 있고 verify/correct 입력에는 없었다(`execution_inputs: {}`).
4. Codex는 이를 "새 worker는 허용 파일이 아니고 confounder_head.py는 수정 불가"로 해석해 `stop`(`automation.json` correct rationale). stop은 검증을 통과하므로 `cross_review_flow.py`의 `proposal['action']!='select'` 분기에서 Gemini·NVIDIA 0회로 종료했다.
5. 프롬프트의 "빈 목록도 가능" 문장이 당시 호출에 있었는지는 `call.json`에 프롬프트 원문이 없어 확인 불가(초기 커밋이 실행 이후). 저장 응답 형태로는 verify가 그 지시를 따르지 않았다.

결론: 구현 가능성 검사 자체는 정상(새 worker는 계속 거절)이었고, 오판은 **검증 오류 문구 + verify/correct 입력에서 worker import 경로 누락**에서 생겼다.

### 변경

- `check_code_sources`: 비모델 파일 거절 시 `Not an editable model source: <path>. New worker is separate output: omit it; [] is valid if worker passes experiment_parameter to worker_importable code`. 거절 동작은 동일.
- `review_context`(verify/correct): `trusted-experiment.json`의 `trainer_sources`에 해당하는 `source_context` 항목에 `worker_importable: true` 표시.
- 프롬프트 한 문장: "worker가 worker_importable 함수 인자로 고정 실험 변수를 적용할 수 있으면 빈 목록도 가능".
- 바이트 상쇄: correct(advocate) 입력의 이전 응답에서 심판 전 항상 0인 `debate_assessment.advocate/skeptic` rating만 제외(`unresolved_issues`·`revision_required` 유지).

### 검사

- 978cc 재생(가짜 backend, 모델 호출 없음, scratchpad 출력): 같은 payload digest `correct-01e63b4f631387af` 재현. main 코드 31,925 bytes, 첫 수정안(별도 dict) 33,041 bytes로 `input_size` 차단 → 압축안 31,963/32,000 bytes 통과, confounder_head.py `editable=false, worker_importable=true`.
- 신규 7개: main 코드로 3개 실패(오류 문구 2, 입력 표시 1) → 수정 후 7/7 통과. 4개(worker-only select 통과, 읽기 전용 trainer 편집 거절 유지, 정정 시 Gemini 1회, 정상 worker-only는 교정 없이 Gemini)는 수정 전에도 통과하는 회귀 보호.
- 관련 기존: cross_review·auto·contract_errors·high_fixes·adversarial·app_server·evidence·manual·nemotron·isolated_execution·review_contract·training_diagnostics 전부 OK.
- 전체 717개 중 3 error: `test_gradient_conflict_audit`, `test_performance_view`, `test_val_input_review` — worktree에 없는 Git 제외 artifacts 파일 의존(FileNotFoundError), 변경과 무관.
- 실행 방식: Git 제외 `nemotron-review.json`을 복사·링크하지 않으려고 cwd=기본 checkout, `python -P`로 worktree 코드 import(읽기 전용).
- 실제 Codex·Gemini·NVIDIA 호출, 학습, 사진 추론, 라벨 변경 없음.

### 유지된 계약

- Codex stop/wait를 select로 바꾸지 않음(mock: verify 오류 → correct stop → `stopped`, Gemini 0·NVIDIA 0).
- Codex verify·correct 각 1회 상한, 저장 응답 재사용, 실패 가설 반복 거절, numeric acceptance 완화 금지, 개발 승인 게이트, snapshot 롤백 코드 미변경.

### 미검증·리스크

- 실제 Codex가 새 입력에서 worker-only select를 할지는 미확인(모델 호출 금지). 실제 토론·심판·학습·성능 변화도 미확인.
- correct 입력 여유가 37 bytes뿐이다. 증거가 조금만 늘어도 `input_size`로 막힌다(이번 변경 전에도 75 bytes). 상한 조정은 별도 승인 필요.
- 978cc는 `correction_spent=true`라 같은 폴더 재개로는 재교정되지 않는다. 같은 자료 재검토는 `./review --auto --fresh`(새 모델 요청 발생)가 필요하며 이번에 실행하지 않았다.

### 롤백

미통합이면 브랜치 폐기, 통합 후면 `./develop -- git revert <SHA>`.
