# 하네스 자동 재개 정책 B 1~3단계 (2026-11-27)

```text
task_id: harness-auto-resume-123-20261127
owner: Claude (메인 세션 배정, 구현은 Opus 하위 에이전트)
status: ready_for_review
base_sha: 09983ec51dcbdfc180e50391c47a0d5d182ca6c9
branch: claude/harness-auto-resume-123-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: 아래 1~3단계가 합성 시험(가짜 claude 실제 하위 프로세스, kill 주입)으로 확인되고,
  재현된 정책 위반 R1·R2·R3·R5·R6가 회귀 시험(수정 전 실패 확인)으로 막힌다. R4는 4단계지만
  "복원 불가 확인" 없이 새 세션을 열지 않는 것은 이번에 막는다.
allowed_files: harness/**, tests/test_harness_*.py, 이 task 문서
forbidden_files: AGENTS.md, docs/agent/**, docs/collaboration/plans/**, card_condition/**, tools/**, artifacts/**, data/**,
  .claude/**, 라벨·사진·모델·비밀 설정
checks:
  - PYTHONDONTWRITEBYTECODE=1 <기본 checkout>/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"
  - 같은 명령을 /usr/bin/python3(3.9)로
  - git diff --check <base_sha>
  - 파일당 함수 정의 ≤7(시험 파일 포함), 시험 제외 공개 진입 함수 호출 깊이 ≤4를 ast로 재측정
experiment: 없음. 실제 claude 실행, 모델 호출, 네트워크 호출, 설치, 시스템 설정 변경, push 없음.
handoff: 이 문서 아래 "인계" 절
```

## 정본

- 승인 원문: 사용자 "최종 의사결정 및 개발 승인"(2026-11-27). 요지는 `docs/agent/HARNESS_RULES.md`와 `DECISIONS.md`.
- 설계: `docs/collaboration/plans/autonomous-harness-20261127/DESIGN.md` 9·12절.

## 보존 조건

기존 큐·작업권·장부·Supervisor·실행기를 재사용한다. 전체 재설계, 새 서버·DB·알림·패치 시스템, 재시도 횟수 확대,
병렬 실행, 설계에 없는 기능은 금지한다. 기존 시험을 삭제·완화·건너뛰지 않는다. 승인된 정책 변경 때문에 기존 시험의
기대값이 달라져야 하면, 시험마다 이전 기대·새 기대·근거 규칙 문장을 인계에 적는다. 확인하지 않은 Claude Code 출력
형식을 가정해 자동 복구 조건을 만들지 않는다.

## 1단계 — 증거 수집과 실행 상태

- stdout·stderr를 교착 없이 함께 읽는다. 실패·성공 실행마다 장부에 허용 필드만 크기 제한해 남긴다: 종료 코드, 신호,
  result subtype·is_error, 권한 거절, 한도 이벤트(원문 값), stderr 끝부분(비밀 패턴 가림), CLI 인자 중 모델·effort·권한
  옵션(프롬프트 본문 제외), cwd, 실행 시간, 마지막 이벤트 종류. 전체 프롬프트·Gold 정답·도구 출력은 남기지 않는다.
- 장애 **원인**과 실행 **결과**를 별도 필드로 둔다. 원인: 근거가 있는 것만(rate_limit, timeout_idle, timeout_total,
  signal, spawn_error, 그 밖은 unknown). 결과: not_started | completed | checkpoint | partial | unknown.
- 실행 정지 감시: claude(무출력 시간 + 총 시간)와 Python runner 하위 프로세스(총 시간)에 제한을 두고 프로세스 그룹을
  종료한다. 값은 설정 가능하게 하고 기본값은 임시값으로 문서화한다. 기존 실험 최대 113분을 정상 종료시키면 안 된다.

## 2단계 — 단계 완료 기록과 중복 방지

- 단계 = 큐 작업 1개. 새 단계 체계를 만들지 않는다.
- 완료 판정: 산출물 존재만으로는 완료가 아니다. LLM 작업은 Claude가 마지막에 쓰는 완료 표시(산출물 상대 경로와
  sha256, task_key)가 산출물과 일치할 때만, Python 작업은 executor가 정상 반환한 뒤 runner가 남기는 같은 형식의
  표시가 일치할 때만 완료다. 완료 표시는 원자적으로 쓴다.
- 재개·재실행 전에 완료 표시를 검사한다. 일치하면 다시 실행하지 않고 반영만 한다. 완료 표시 직후, done.json 직후,
  장부 기록 직전·직후의 각 중단 지점에서 kill을 주입해 복구를 확인한다.
- R1: 중단·실패한 작업의 자동 재개·재실행은 **코드에 재실행 안전으로 등록한 작업 유형**만. 기본 등록은 비어 있다.
  그 밖은 결과 확인 대기(원인·결과 기록 + 알림). Python 일시 실패 자동 재시도에도 같은 조건. 외부 요청 뒤 결과를
  모르는 실패는 일시 원인이 아니다. 정상(첫) 실행은 막지 않는다.
- R2: 논리 중복 키. 실험·학습·평가는 실제 실행 조건과 입력 내용(SHA)으로만 계산한다. 가설 ID, 설명 문구, risk,
  retry_policy, escalation_level, 입력 경로 철자가 달라도 같은 조건이면 중복 등록을 거절(기존 작업을 알려 줌)한다.
  실행 조건이 계약에 없어 판별할 수 없는 실험·학습·평가 작업은 등록을 거절한다. 조건 하나라도 실제로 다르면
  통과해야 한다. task_key·run_id는 유지한다.
- 예산 차감(budget.charge)에 멱등 키를 두어 같은 단계의 반영·복구에서 두 번 차감되지 않게 한다. 단, 언어 모델
  재개로 실제 사용이 더 생기는 경우는 승인 예산 안에서 차감해야 한다(실제 호출 시도 단위). 루프 호출부 연결은 5단계.
- 산출물 반영(complete)은 한 번만. 이미 VERIFIED면 다시 반영하지 않는다.
- Claude 작업이 실행 중 죽은 뒤의 재개에 기존 상한 2회를 적용한다.
- R5: claude.json 한 칸 구조를 바꿔(작업별 상태) 대기 작업이 다른 독립 작업을 막지 않게 한다. 그 작업과 의존 작업만
  대기한다. 공통 장애 근거(현재는 한도 이벤트)만 Claude 실행 전체를 멈춘다. 미분류 실패 횟수로 전체를 멈추지 않는다.
  작업당 자동 실행은 위 규칙대로 제한된다.
- R4(부분): 한도가 아닌 --resume 실패는 새 세션을 열지 않고 그 작업을 대기시킨다. "세션 복원 불가 확인" 판정
  함수는 두되 실제 출력 근거를 확보하기 전에는 어떤 출력도 복원 불가로 판정하지 않는다.
- 한도 초기화 시각을 못 읽는 경우: 현재 60·300·900초 뒤 정지(약 21분)라 한도 뒤 무인 재개와 충돌한다. 재시도
  **횟수 3은 유지**하고 간격만 기존 값·창 길이로 바꾼다: 900초, 5시간(five_hour 창), MAX_RESET_AHEAD_S(8일). 새 출력
  형식 해석을 추가하지 않는다. 주간 한도에서 마지막 시도까지 늦어질 수 있음(최대 약 8일 지연)과 이후는 사람
  확인이라는 한계를 문서에 남긴다.

## 3단계 — 작업 유형별 권한의 코드 강제

- task_type → 권한 묶음을 코드가 정한다(계약 필드로 넓힐 수 없다). `routing_policy.json`의 유형 기준:
  A = experiment_log_summary, misanalysis_general, repeated_failure_analysis (입력 읽기 + 산출물 폴더 쓰기만).
  B = image_analysis_general, silver_labeling, defect_analysis_precise, label_cross_validation, label_disagreement.
  C = general_dev, complex_algorithm, model_redesign. 묶음이 없거나 아직 정의하지 않은 유형은 제한 없이 실행하지 않고
  대기시킨다. B·C는 필요한 통제가 구현되지 않았으면 실행하지 않는다.
- A의 실행 옵션은 공식 문서(code.claude.com/docs: cli-reference, permissions, permission-modes, sandboxing)를 읽고
  정한다. 후보: --restricted, --tools(명령 실행·Agent 제외), --strict-mcp-config, --disallowedTools "mcp__*",
  --permission-mode dontAsk, 산출물 폴더만 쓰기 허용, --disable-slash-commands. 규칙 문법은 문서로 확인한 것만 쓰고
  실환경 미확인으로 표시한다. claude 바이너리는 실행하지 않는다(실환경 시험은 메인이 이후에 한다).
- cwd는 작업별 작업 폴더. 계약 입력은 SHA를 확인해 그 폴더로 복사한다(링크·폴더 밖 경로·봉인·Gold 경로 거절).
  환경변수는 허용 목록만 넘긴다(구독 인증에 필요한 최소: HOME, PATH, USER, LANG, TMPDIR 등. API 키류 제외).
  프로젝트 지침이 로드되지 않을 수 있으므로 필요한 규칙을 프롬프트에 넣는다.
- 자동 재개 활성화 목록(작업 유형)은 코드에 두고 **빈 집합**으로 시작한다. 목록에 없으면 한도 해제 뒤에도 자동
  재개하지 않고 대기한다. 첫 실행은 허용한다. 유형을 켜려면 실환경 증거 참조가 필요하게 한다.
- R6: 하네스가 띄운 실행기가 사용자를 사칭해 중단·정지를 해제하지 못하게 한다. 선언 문자열 검사는 강제로 보지
  않는다. 설치·시스템 설정·OS 사용자 분리 없이 가능한 실제 강제를 쓴다: claude 작업은 위 권한 옵션(명령 실행 없음,
  하네스 상태 폴더 쓰기 불가), Python executor 하위 프로세스는 macOS `sandbox-exec`로 하네스 상태 폴더(운영 상태·
  예산·작업 상태) 쓰기를 거절한다. 실제 sandbox-exec 하위 프로세스 시험으로 확인하고, executor의 정상 산출물 쓰기는
  유지한다. sandbox-exec를 쓸 수 없으면 실행하지 않는다(fail-closed). 같은 macOS 사용자의 다른 프로세스(Codex,
  대화형 Claude 등)는 막지 못한다는 한계를 문서에 남긴다.

## 인계

작성: Claude(Opus 하위 에이전트), 2026-11-27. status: ready_for_review. push·main 통합 안 함. 실제 claude 실행·모델 호출·설치 0회.

### 커밋

| 단계 | SHA | 내용 |
|---|---|---|
| 1 | `197b5dd` | 실행 증거 기록, claude·runner 시간 제한 |
| 2 | `a9e9b22` | 완료 표시, 중복 방지, 작업별 Claude 상태(R1·R2·R3·R4 일부·R5) |
| 3 | `e46a226` | 작업 유형별 권한 묶음, executor sandbox(R6) |
| 인계 | 이 문서 커밋 | 인계 기록, claude_job 대기 해제 설명 한 줄 |

### 변경 파일

- 새 파일(harness): `evidence.py`, `dedupe.py`, `claude_perm.py`, `sandbox.py`, `sandbox_child.py`
- 고친 파일(harness): `claude_run.py`, `claude_job.py`, `supervisor.py`, `ratelimit.py`(마지막 이벤트 종류), `contract.py`, `queue.py`, `states.py`,
  `recovery.py`, `runner.py`, `graph.py`, `budget.py`
- 새 시험: `test_harness_run_evidence.py`, `test_harness_policy_regress.py`(R1~R5), `test_harness_completion_kill.py`,
  `test_harness_claude_completion.py`, `test_harness_policy_guards.py`, `test_harness_claude_perm.py`, `test_harness_sandbox.py`(R6),
  `test_harness_resume_kit.py`(시험 도구)
- 고친 시험: 아래 "바꾼 기존 시험"

### R별 조치와 회귀 시험

수정 전 확인 방법: `197b5dd`(1단계, 2단계 수정 전) 복사본에 회귀 시험 파일만 넣고 실행(시험 도구 `allow_resume`은 그 실행에서만 빈 문맥으로 대체).
R6은 `a9e9b22`(3단계 수정 전) 작업 트리에서 실행.

| R | 조치 | 회귀 시험 | 수정 전 결과 |
|---|---|---|---|
| R1 | `recovery.RERUN_SAFE_TYPES`(빈 집합)에 등록한 유형만 INTERRUPTED 재개·재실행과 일시 실패 재시도. 실험·학습·평가(`dedupe.CONDITION_TYPES`)는 등록해도 제외. 그 밖은 `await_result`: `awaiting.json`·장부 `awaiting_result`(원인·결과)·알림 `task_awaiting_result`를 한 번만 | `test_harness_policy_regress.test_r1_interrupted_or_transient_failed_unregistered_task_is_not_rerun`, `test_harness_policy_guards.test_experiment_is_never_auto_rerun_even_if_registered_and_waits_once` | 실패 확인(끊긴 작업이 rerun으로 claim됨: `KeyError 'reason'`) |
| R2 | `dedupe.logical_key` = task_type·run_conditions(command·code_sha·config·seed)·needs_llm·needs_vision·입력 SHA 목록. 설명 키(hypothesis_id·description)·risk·retry_policy·escalation_level·expected_minutes·입력 경로 철자 제외. 같은 키면 `queue.DuplicateTask(.existing)`, 실행 조건 없음·모르는 키는 `ContractError`. `graph.register_missing`도 같은 거절(`duplicates`) | `test_r2_same_run_conditions_with_different_wording_is_refused`, `test_graph_registration_refuses_logical_duplicates` | 실패 확인(`run_conditions` 필드가 없어 거절). 별도 재현: risk만 다른 실험 계약이 서로 다른 task_key로 둘 다 등록됨 |
| R3 | 실행 전 완료 표시(`complete.json`)가 산출물 해시와 맞으면 claude를 부르지 않고 반영만(adopted) | `test_r3_finished_claude_work_is_not_resumed_after_supervisor_death` | 실패 확인(claude 2회 실행) |
| R4(부분) | 한도가 아닌 `--resume` 실패는 새 세션 없이 그 작업 대기. `claude_run.session_unrecoverable`는 두었지만 항상 False | `test_r4_resume_failure_without_rate_limit_does_not_open_a_new_session` | 실패 확인(새 세션 3번째 실행) |
| R5 | `supervisor/claude.json` 한 칸 → `supervisor/claude/<task_key>.json`·`.pid`. 대기 작업은 건너뛰고 독립 작업을 고른다. 전체 정지는 한도 조건(opstate)만 | `test_r5_unknown_failure_holds_only_that_task` | 실패 확인(독립 작업 PENDING). 처음 쓴 시험은 두 작업의 task_key가 같아 무효였고, 고친 시험으로 다시 확인했다 |
| R6 | runner는 executor 모듈을 가져오지 않고 `sandbox-exec` 하위 프로세스(`harness.sandbox_child`)로 실행. 프로필: 하네스 root 쓰기 거절, 그 작업 `out/`만 허용. sandbox-exec가 없으면 실행하지 않음(`runner.SANDBOX_EXIT`=5). runner가 죽으면 자식도 0.1초 안에 끝난다 | `test_harness_sandbox.test_r6_executor_cannot_lift_user_stop_or_write_harness_state` | 실패 확인(executor의 `clear_by_user` 사칭 해제·장부·예산·완료 표시 쓰기 모두 성공) |

그 밖의 계약 항목과 시험:
- 1단계: stdout·stderr 동시 읽기, 무출력·총 시간 초과 때 프로세스 그룹 종료, 원인(cause)·결과(outcome) 분리, 허용 필드·비밀 가림 증거(`claude_run_evidence`), runner 총 시간 제한 → `test_harness_run_evidence`(5개)
- 2단계 kill 주입: Python 작업은 완료 표시 직후·done.json 직후·장부 직전·직후(`test_harness_completion_kill`), Claude 작업은 하네스 표시 전·done.json 직후(`test_harness_claude_completion`), 완료 표시 직후는 R3 시험
- 반영 한 번, 이미 VERIFIED면 다시 반영 안 함, 예산 멱등 키, 실행 중 사망 재개 작업당 2회 → `test_harness_policy_guards`, `test_harness_claude_completion`
- 3단계: A만 실행·A 옵션·cwd·env, 자동 재개 기본 꺼짐·증거 해시, 입력 복사 검사 → `test_harness_claude_perm`. sandbox 없음 → 실행 안 함, runner 사망 → 자식 종료 → `test_harness_sandbox`

### 계약 충돌과 fail-closed

- **Claude 완료 표시의 sha256**: A 묶음에는 명령 실행 도구가 없어 Claude가 sha256을 계산할 수 없다. 그래서 Claude는 마지막에 `out/.harness_complete.json`
  (task_key·outputs 경로 목록)을 쓰고, 하네스가 claude 성공 종료를 본 직후 산출물 해시를 붙여 `complete.json`을 원자 저장한다.
  하네스가 해시를 붙이기 전에 죽은 경우(Claude 선언만 있음)는 완료로 보지 않는다. 선언만으로 하는 사후 반영 기능은 꺼 둔 상태다.
- 세션 복원 불가 판정: 실제 오류 출력 근거가 없어 항상 False(새 세션 경로는 사실상 꺼짐).
- B·C 묶음: 필요한 통제가 없어 실행하지 않음.

### 바꾼 기존 시험

| 시험 | 이전 기대 | 새 기대 | 근거 규칙 |
|---|---|---|---|
| `test_harness_supervisor_resume.test_resume_failure_opens_new_session_from_ledger_state` → 이름 `test_resume_failure_holds_the_task_without_opening_a_new_session` | `--resume` 실패 뒤 새 세션(3번째 실행), VERIFIED | 실행 2회, 작업 PENDING, 상태 blocked(`claude_failed_cause_unknown`), 세션 ID 유지 | HARNESS_RULES "세션 복원 불가가 확인된 경우에만 새 세션… 그 밖의 --resume 실패는 그 작업을 대기", 계약 R4 |
| `test_harness_supervisor_resume.test_unknown_reset_backs_off_three_times_then_stops_and_notifies` | 간격 60·300·900초, poll 120 | 간격 900초·5시간·8일, poll 10**6(가짜 시계라 실제 대기 없음). 횟수 3은 같음 | 계약 2단계 "재시도 횟수 3은 유지하고 간격만 900초, 5시간, MAX_RESET_AHEAD_S" |
| `test_harness_supervisor_reresume.test_stop_during_a_failing_resume_opens_no_new_session` | settle 결과 `halted` | `blocked`(새 세션 없음은 같음) | 계약 R4 |
| `test_harness_runner_procs.test_a_task_that_keeps_dying_stops_after_the_interrupt_limit_and_independent_tasks_still_run` | runner 종료 코드 [-9,-9,-9,0,0], 독립 작업은 4번째 runner에서 완료 | 종료 코드 [0]*5, 독립 작업은 첫 runner에서 완료, 독 작업은 `executor_killed` 뒤 4번째에서 `too_many_interrupts`. 실행 횟수 3·1은 같음 | 계약 3단계 R6(executor가 sandbox 하위 프로세스라 runner가 함께 죽지 않음) |
| `test_harness_supervisor_contracts.test_route_decision_recorded_without_claiming_t7` | 유형 general_dev(sonnet·medium)·label_disagreement(opus·high) | misanalysis_general(sonnet·medium)·repeated_failure_analysis(opus·high) | 계약 3단계: A 묶음만 실행(B·C 유형은 실행하지 않아 라우팅 기록이 안 생김) |

기대값은 같고 준비(fixture)만 바꾼 시험(삭제·완화·skip 없음):
- 재실행 절차 시험 클래스에 `@mock.patch.object(recovery, "RERUN_SAFE_TYPES", RERUN_SAFE)`: `test_harness_claim_holder`, `claim_processes`, `interrupts`, `recovery`,
  `state_guards`, `states`, `supervisor_unlock`. `test_harness_support.WORKER` 스크립트와 `test_harness_runner_kit.spawn_runner`(하위 프로세스 runner를
  `-c` 래퍼로 띄우고 `TEST_RERUN_SAFE`로 목록 지정)도 같은 목적. 근거: R1(실제 목록은 비어 있음).
- 자동 재개 절차 시험에 `allow_resume`(합성 증거 파일로 그 유형만 켬): `supervisor_resume`(3개), `supervisor_hold.test_session_id_from_init_is_followed`,
  `supervisor_reresume`, `supervisor_procs`(하위 프로세스는 `resumable_supervisor` 래퍼). 근거: 3단계 활성화 목록 빈 집합.
- 완료 표시 기록 추가: `test_harness_support.finish`, `test_harness_recovery.test_tampered_byte_is_restored_but_damaged_cas_forces_rerun`. 근거: 완료 표시 일치 때만 완료.
- 작업별 상태 경로(`claude_job.JOB`/`PIDFILE` → `paths()`·`JOBS`): `supervisor_hold`, `supervisor_halt`.
- `test_harness_supervisor_kit`: `llm_task` 기본 유형 general_dev → misanalysis_general(라우팅 값 같음), 계약 입력 `{}`(복사할 파일 없음), 가짜 claude가
  설정을 실행 파일 옆 파일에서 읽음(env 허용 목록 때문), 성공 때 Claude 선언을 씀, 시나리오 추가(noisy·hang·trickle·selfkill·declare).
- `test_harness_executors`: R6용 `intruder` executor 추가.

### 임시 기본값(사용자 확정 전)

| 값 | 위치 | 기본 |
|---|---|---|
| claude 무출력 제한 | `claude_run.IDLE_S` | 30분 |
| claude 총 시간 제한 | `claude_run.TOTAL_S` | 3시간 |
| runner(작업 1개) 총 시간 | `supervisor.PYTHON_TOTAL_S` | 3시간(113분 실험보다 김, 시험으로 대조) |
| 종료 유예 | `claude_run.KILL_GRACE_S` | TERM 뒤 5초 KILL |
| stderr 끝부분 | `evidence.STDERR_TAIL` | 2000자 |
| 실험·학습·평가 유형 이름 | `dedupe.CONDITION_TYPES` | experiment·training·evaluation |
| 실행 조건 키 | `dedupe.CONDITION_KEYS`/`NOTE_KEYS` | command·code_sha·config·seed / hypothesis_id·description |
| 봉인·Gold 경로 판별 | `claude_perm.FORBIDDEN_PARTS` | 경로 조각에 gold·seal(대소문자 무시) |
| 허용 env | `claude_perm.ENV_ALLOW` | HOME·PATH·USER·LOGNAME·SHELL·LANG·LC_ALL·LC_CTYPE·TMPDIR |
| 재실행 안전 목록 / 자동 재개 목록 | `recovery.RERUN_SAFE_TYPES` / `claude_perm.AUTO_RESUME` | 둘 다 비어 있음 |
| 시각 미상 재시도 간격 | `claude_job.UNKNOWN_BACKOFF_S` | 900초·5시간·8일(3회) |

설정: `supervisor.run(limits={...}, source_root=...)`, 명령행 `--claude-idle-s`·`--claude-total-s`·`--python-total-s`·`--source-root`.

### 구조(함수 수·호출 깊이)

파일별 함수 정의 수 전→후(λ는 lambda 수, 기준 `bc0ee35`): `claude_job` 4→6, `claude_run` 4→6, `queue` 6→6, `recovery` 7→7, `runner` 5→5, `states` 4→5+λ1,
`supervisor` 4→4, `budget` 3→3, `contract` 5→5, `graph` 3→3, `ratelimit` 4→4, 새 `evidence` 4+λ1, `dedupe` 2, `claude_perm` 4, `sandbox` 4, `sandbox_child` 2.
새 시험 파일: `run_evidence` 7, `policy_regress` 6, `completion_kill` 4, `claude_completion` 6, `policy_guards` 5, `claude_perm` 5, `sandbox` 3, `resume_kit` 3.
고친 시험 파일은 함수 수가 늘지 않았다(`executors` 6→7, `supervisor_kit` 7→7). 7개 초과 시험 파일 14개(claim_holder·graph·lease·ledger·recovery·
route_*·runner·runner_errors·state_guards·states·support, lambda 포함 집계)는 `bc0ee35`에도 같은 수로 있던 것이다.
최대 호출 깊이 4(`supervisor.run`), harness 공개 함수 중 4 초과 없음(ast 정적 호출 그래프, functools.partial 포함). 주요 경로: run → execute → _record_run →
record_decision → append(4), run → settle → claim → decide(3)/facts → _completion(4), runner.main → drain → _execute → sandbox.run_one → profile(4, executor 표는
동적 호출). 정적으로 확정 못 한 경로: 스레드 대상 `claude_run._pump`·`sandbox_child._watch`(말단), sandbox 자식 안의 executor(사용자 코드).

### 검사 결과

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"`: 360개 OK, 종료 코드 0 (3단계 커밋 상태)
- 같은 명령 `/usr/bin/python3`(3.9): 360개 OK, 종료 코드 0
- `git diff --check bc0ee35`: 문제 없음

### 미검증(특히 실환경)

- 실제 claude: A 옵션의 효과(도구·MCP·쓰기 범위·하위 에이전트·훅·플러그인·mod 차단), `--restricted` 설치본 지원(문서: 2.1.248+), 허용 env만으로 구독 인증이
  되는지, `--restricted`에서 `--resume`·모델 지정이 되는지, 프로젝트 지침 로드 여부, stream-json의 `permission_denials`·한도 이벤트 형식, `--resume` 실패 출력.
- LaunchAgent 실행, 실제 한도 초기화 뒤 무인 재개, macOS 다른 버전의 sandbox-exec 동작.
- 체크포인트 재개는 여전히 연결되지 않았다(runner가 현재 지문을 넘기지 않음, 이번 범위 밖). `budget.charge` 호출부는 5단계.

### 리스크

- 자동 재개·재실행 목록이 비어 있어 한도·중단 뒤 Claude·Python 작업은 모두 사람 확인 대기다(의도된 fail-closed). 대기 해제는 수동(Claude: 작업 상태 파일 삭제,
  Python: `lease.json`·`awaiting.json` 정리)이며 전용 해제 함수는 만들지 않았다.
- sandbox는 하네스 root 쓰기만 막는다. 읽기·네트워크·다른 프로세스 신호는 막지 않고, 같은 macOS 사용자의 다른 프로세스(Codex·대화형 Claude·셸)는 막지 못한다.
  sandbox-exec는 Apple이 폐기 예정으로 표시한 도구다.
- 비밀 가림은 정규식 최선 노력이다(형식이 다른 비밀은 남을 수 있다).
- claude 정상 종료 뒤 같은 프로세스 그룹에 남은 하위 프로세스를 KILL한다(파이프 교착 방지). 그룹 ID 재사용 경합은 이론상 남는다.
- runner가 sandbox-exec 없이 실행되는 환경이면 Python 작업이 하나도 돌지 않고 매 회차 `python_drain`(종료 코드 5)이 장부에 남는다.
- 완료 표시 검사로 `queue.complete`가 엄격해져, 표시를 쓰지 않는 호출자(향후 코드)는 완료할 수 없다.

### 롤백

- 전체: `git revert e46a226 a9e9b22 197b5dd`(역순) 또는 브랜치 폐기. main·원격에는 반영하지 않았다.
- 단계별: 3단계만 되돌리면 2단계 상태(권한 묶음·sandbox 없음), 2단계까지 되돌리면 1단계 상태. 운영 상태 파일 형식이 바뀐 곳은 Claude 작업 상태
  (`supervisor/claude.json` → `supervisor/claude/<task_key>.json`)이며, 되돌리면 새 형식 파일은 읽히지 않으니 지워야 한다(실운영 root는 아직 없음).
