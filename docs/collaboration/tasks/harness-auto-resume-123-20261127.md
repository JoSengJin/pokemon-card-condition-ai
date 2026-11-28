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

### 검증 결함 수정

작성: Claude(Opus 하위 에이전트), 2026-11-27. 근거: 독립 검증 `verify-auto-resume-123.md`(F1~F13·N1), 실환경 `c-realenv.md`. 대상 `de6286b..` 이 절의 커밋.
push·main 통합 안 함. 실제 claude 실행·모델·네트워크 호출·설치·시스템 설정 변경 0회. 자동 재개 목록 `claude_perm.AUTO_RESUME`·재실행 안전 목록
`recovery.RERUN_SAFE_TYPES`는 계속 비어 있다(어떤 유형도 켜지 않음). 회귀 시험은 모두 수정 전에 실패를 확인했다(수정 전 결과 열).

#### 커밋

| 묶음 | SHA | 결함 |
|---|---|---|
| 1 | `e367c83` | F1·F2 |
| 2 | `d4140d9` | F3 |
| 3 | `fe2b440` | F4·F5·N1·4단계 세션 복원 불가 확인, F13(시험 도구) |
| 4 | `92c9d04` | F6~F12 |
| 인계 | 이 문서 커밋 | 이 절, 시험 열린 파일 경고 정리, 3.9에서 site-packages 폴더가 없으면 그 항목을 absent로 기록 |

#### 결함별 조치·회귀 시험·남은 한계

| # | 조치 | 회귀 시험 | 수정 전 | 남은 한계 |
|---|---|---|---|---|
| F1·F2 | `sandbox.profile`을 쓰기 기본 거절로: 허용은 그 작업 `out/`, 실행별 전용 임시 폴더(`run_one`이 시스템 임시 폴더 아래 새로 만들어 TMPDIR로 넘기고 끝나면 삭제), `/dev/null`뿐. `launchctl`·`open`·`osascript` 실행과 Apple Event 거절. `out_dir`은 root/tasks 아래, 임시 폴더는 root 밖이 아니면 ValueError | `test_harness_sandbox_writes`(실제 `sandbox.run_one` → sandbox-exec): 하네스 상태·다른 작업 out·저장소 소스·site-packages·홈·/private/tmp 쓰기, 상위 폴더 rename, 세 실행 파일 실행이 모두 `denied:1`, 자기 out·임시 폴더·/dev/null만 ok(`/usr/bin/python3` 3.9는 purelib `/Library/Python/3.9/site-packages`가 없어 그 항목만 absent, venv에서는 실제로 거절 확인). 임시 폴더는 실행마다 새것이고 끝나면 없다 | 실패: rename_parent·repo_source·site_packages·home·system_tmp·세 실행 파일 모두 ok | executor가 실행 파일 없이 launchd에 직접 XPC/mach 요청을 보내는 경로는 막지 못함(시스템 상태를 바꾸는 시험이라 하지 않음). 읽기·네트워크·신호는 막지 않음. 홈 캐시(~/.cache 등)에 쓰는 라이브러리는 sandbox 안에서 실패. sandbox-exec 전에 열린 fd로는 쓸 수 있음(runner는 close_fds라 넘기지 않음, `sbx_case_probe` inherited_fd) |
| F3 | 등록 유형 고정 목록: `dedupe.CONDITION_TYPES`(experiment·training·evaluation 정확히)와 `PLAIN_TYPES`(권한 묶음 유형 + deterministic). 그 밖·변형 이름은 run_conditions 유무와 관계없이 ContractError, 실행 조건을 가진 비실험 유형도 거절. `run_conditions.input_roles`({입력 경로: 역할}, 역할 train·val·test·model·config·data) 필수. 키 = 유형·정규화 조건·needs_*·(역할, 입력 SHA) 쌍. 정규화: config 생략·null = {}, seed 생략 = null, 1.0 → 1(JSON 왕복), SHA 소문자·형식 검사(입력 64자, code_sha 40/64자), `--opt=value` → 두 토큰, `/` 든 토큰 normpath. 입력 SHA를 등록(`queue.enqueue`·`graph.register_missing`, `source_root` 기본 저장소)과 executor 실행 직전(`runner._execute`, `--source-root`)에 실제 파일과 대조 | `test_harness_dedupe_conditions` 4개: 변형 유형 5종(enqueue·graph) 거절, 같은 조건 다른 표기 11종 중복, 역할 맞바꿈·입력 내용·입력 추가·needs_vision·seed 다름 등록, SHA 형식·불일치·없는 파일·폴더 밖 거절과 등록 뒤 입력이 바뀌면 executor 0회·결정적 실패 | 실패: 유형 시험은 `Experiment` 등록됨, 나머지 3개는 `source_root` API 없음. 논리 실패는 `dedupe_probe.py` 원본 결과(검증 보고) | command의 인자 순서, python·python3·절대 경로 별칭, 문자열 숫자(0.1·0.10), 짧은 옵션 결합은 다르게 본다(같은 실험을 다른 조건으로 볼 수 있음 = 중복 등록 통과 가능). 역할 이름 6개는 임시값. 실험 외 Python 작업 입력은 원본 위치가 계약에 없어 대조하지 않는다. 큰 입력은 실행마다 해시 시간이 든다. 새 Python 작업 유형은 코드 목록에 추가해야 등록된다 |
| F4 | 매 실행(새 세션·재개·복원 불가 뒤 새 세션) 직전에 `out/.harness_complete.json` 삭제, 프롬프트에 `실행 토큰: <run_token>`과 선언 형식 `{"task_key","run_token","outputs"}`, `evidence.outcome_of`는 이번 run_token이 맞을 때만 completed | `test_harness_resume_fixes.test_f4_stale_or_foreign_declaration_is_not_accepted`: 낡은 선언 + 반쯤 쓴 산출물 + 아무것도 안 하고 성공 종료(noop) / 다른 토큰 선언 → PENDING·blocked(`completion_marker_missing`), 선언 삭제 확인 | 실패: VERIFIED·done | Claude가 이번 실행에서 선언을 쓰고 일부 산출물이 이전 실행의 것이어도 해시가 맞으면 완료된다(선언은 Claude의 주장이다). 실환경 Supervisor 전체 경로로는 확인 안 함 |
| F5 | 시각 미상 한도 시도 횟수를 작업 상태가 아니라 `supervisor/claude_unknown_limit.json`(전체)에서 센다. 처음 1회 + 3회(900초·5시간·8일) 뒤 exhausted, claude 성공 종료(settle kind=success)면 0. 시각을 아는 한도는 횟수를 바꾸지 않는다. 기록이 이상하면 소진으로 본다. 작업 상태의 `unknown_attempts` 필드는 없앴다 | 같은 파일 `test_f5_..._counted_across_tasks_and_reset_by_success`: 독립 작업 6개에서 claude 4회, 간격 900·18000·691200초, 알림 1회. 성공 뒤 0 | 실패: 6회(작업마다 0부터) | 자동 재개가 꺼진 유형은 한도에 걸린 작업이 대기가 되고 다음 시도는 다른 독립 작업이 쓴다(최대 4개 작업이 사람 대기). 횟수 3은 그대로 |
| F6 | `default_runner`: 프로세스 종료 뒤 읽기 스레드를 총 시간 안에서 최대 `KILL_GRACE_S`만 기다리고, 남아 있으면 원인 `timeout_total`. `run_once`는 timeout 원인이 있으면 success=False | `test_harness_evidence_fixes.test_f6_...`: setsid 손자가 stdout을 쥔 채 20초 → 9초 안에 반환, cause timeout_total, run_once success False | 실패: 손자 수명까지 반환 안 함 | 남은 읽기 스레드(daemon)와 파이프 fd는 그 자손이 끝날 때까지 남는다(pid를 몰라 죽이지 못함, 코드에 `shortcut:` 표시) |
| F7 | `evidence.mask`: 이름=값(따옴표·JSON, `aws_secret_access_key` 같은 긴 이름), `sk-`·`gh[opsur]_`·`github_pat_`·`AKIA/ASIA`·`xox?-` 접두어, `Authorization: Bearer`. 끝부분 `STDERR_TAIL + MASK_MARGIN(500)`자를 먼저 가린 뒤 자른다. 이름 부분 반복을 40자로 제한(30만 자 stderr에서 이차 시간 방지) | `test_f7_...` 9종 + 경계 잘림 | 실패: JSON 토큰 등 노출 | 최선 노력: 형식이 다른 비밀, 500자보다 긴 비밀 값이 경계에 걸린 경우는 남을 수 있다 |
| F8 | 코드 변경 없음(시험 공백) | `test_harness_claude_perm`: A 옵션을 시험에 문자 그대로 고정(`A_PINNED`), 재개 실행 argv에도 같은 옵션 | 통과(코드는 맞았음). 변이 M34(dontAsk→acceptEdits)·M35(재개 때 옵션 제거)가 이제 잡힘 | 옵션의 실제 효과는 c-realenv 범위만 확인 |
| F9 | 권한 거절 기록은 `tool_name`·`tool_use_id`·`tool_input.file_path`만(가림 적용, 200자) | `test_f9_f12_...` | 실패: content 본문 기록 | Glob·Grep의 pattern·path는 남기지 않는다(필요하면 추가 결정) |
| F10 | `budget.charge` 멱등 비교를 `(kind, key)`로 | `test_f10_...` | 실패: 다른 종류 차감이 already로 빠짐 | 호출부 연결은 5단계 |
| F11 | `stage_inputs`가 `st_nlink > 1` 입력 거절 | `test_existing_gold_named_or_hard_linked_inputs_are_refused`: 실제로 있는 gold·sealed 이름 파일(M23 공백 메움), 봉인 파일·하네스 root 파일의 하드 링크 거절, 일반 파일은 복사 | 실패: notes.txt 복사됨 | 원본을 복사한 파일(링크 아님)은 내용으로 봉인 여부를 알 수 없다 |
| F12 | 코드 변경 없음(시험 공백) | 입력 SHA만 다른 실험 등록(`test_real_differences_are_registered`), 증거 options에 -p 본문·`--append-system-prompt`·`--settings` 없음(`test_f9_f12_...`) | 변이 M10·M28이 이제 잡힘 | - |
| F13 | `llm_task` 이름을 산출물 이름(`<name>.md`)에 넣음 | F5 시험이 이름이 다른 6개 작업의 task_key가 모두 다름을 단언 | 수정 전 같은 키 | - |
| N1 | `recovery.decide`: 재실행 안전 미등록 유형의 복구 불가 CORRUPT는 완료 기록을 보관(history)하지 않고 `await_result`(사유 `corrupt_unrecoverable`, 장부·알림 한 번) | `test_n1_...`: 두 번 claim 모두 await_result, done.json 유지, 상태 CORRUPT, 대기 기록 1개 | 실패: rerun claim 성공 | 해제는 수동(사람 확인) |
| 4단계 | `claude_run.session_unrecoverable(found, resumed)`: 종료 코드 1, 한도 아님, result subtype `error_during_execution`, is_error true, num_turns 정수 0, errors가 정확히 `["No conversation found with session ID: <resumed>"]`일 때만 True. True면 장부 프롬프트로 새 세션 1회(같은 execute 안이라 실행 직전 정지 확인·선언 삭제·완료 표시 검사·crash_resumes 상한 그대로) | `test_session_unrecoverable_accepts_only_the_exact_real_output`(실환경 `t4-bogus-resume.jsonl` 줄을 그대로 넣고 ID만 바꿈, 비슷한 11종 False, 다른 ID False), `test_confirmed_unrecoverable_session_opens_a_new_session_once`(한도 → 재개 실패(실제 형식) → 새 세션 → VERIFIED) | 실패: 인자 형식 없음·새 세션 없음 | 실환경 형식은 2.1.310 하나뿐. 버전이 바뀌어 문구가 달라지면 False(대기)로 떨어진다. 자동 재개 목록이 비어 있어 운영에서는 이 경로가 아직 쓰이지 않는다 |

변이 확인(수정본 복사본, 해당 시험 모듈만): M34·M35·M10·M28·M23, F11·N1·F4·F5·복원 불가 판정·F1 기본 거절 제거 변이 11개 모두 잡힘.

#### 바꾼 기존 시험(기대값은 같고 준비만 바꿈, 삭제·완화·skip 없음)

- sandbox 기본 쓰기 거절 때문에 시험 executor의 실행 표식 폴더(`HARNESS_MARK_DIR`, 하네스 root·저장소 밖 임시 폴더) 쓰기가 막힌다. 시험 래퍼 `RUNNER_WRAP`(runner_kit)가
  그 시험 프로세스의 프로필에만 표식 폴더 허용을 덧붙인다. 실제 `python -m harness.runner` 프로필은 그대로이고 `test_harness_sandbox_writes`가 실제 프로필을 본다.
  Supervisor가 띄우는 runner는 `supervisor.RUNNER` 상수(새로 둠)를 `WRAPPED_RUNNER`로 patch(`run_evidence`·`supervisor_contracts`·`supervisor_halt`·`supervisor_resume`),
  하위 프로세스 Supervisor는 `SUPERVISOR_MARKED`(`supervisor_halt`). 근거: F1·F2.
- F3 고정 목록: `test_harness_support`가 시험용 합성 유형(`TEST_TYPES`: RERUN_SAFE 목록·unit-r1·unit-r1b·시험 executor 이름)을 그 시험 프로세스의 `dedupe.PLAIN_TYPES`에 더한다(정확한 이름만, 변형은 그대로 거절).
- F3 입력 역할·실제 파일: `policy_guards.experiment(src, …)`, `policy_regress.test_r2…`가 입력 파일을 만들고 `input_roles`·`source_root`를 넘긴다. R2의 경로 철자 변형은 inputs와 input_roles를 함께 바꿨다.
- N1: `test_harness_paths.PathSafetyTest`에 `RERUN_SAFE` patch(손상 뒤 재실행 절차 시험. 미등록 유형의 대기는 N1 시험이 본다). 이전 기대 rerun 그대로.
- F4: 가짜 claude 선언에 실행 토큰(프롬프트에서 읽음), 시나리오 `noop`·`raw` 추가. F13: `llm_task` 산출물 이름.
- 강화: `test_only_bundle_a_runs…`의 옵션 비교를 `claude_perm.A_OPTIONS` 대신 고정 목록으로.

#### 구조(함수 수·호출 깊이)

harness 함수 정의 수 전→후(`de6286b` 기준): `dedupe` 2→5, `sandbox` 4→4, `claude_job` 6→6, `claude_run` 6→6, `evidence` 4→4(λ1), `recovery` 7→7, `budget` 3→3,
`claude_perm` 4→4, `queue` 6→6, `graph` 3→3, `runner` 5→5, `supervisor` 4→4. 새 시험: `sandbox_writes` 5, `dedupe_conditions` 6, `resume_fixes` 7, `evidence_fixes` 4+λ2.
고친 시험: `claude_perm` 5→7, 그 밖은 함수 수 그대로. 7 초과 시험 파일 14개는 `de6286b`와 같은 수(검증 `structure_measure.py`로 재측정).
최대 호출 깊이 4, 초과 0. 새·바뀐 경로: `supervisor.run → graph.register_missing → dedupe.find_duplicate → logical_key → _command`(4),
`runner.main → drain → _execute → dedupe.verify_inputs → cas.sha_file`(4), `supervisor.run → claude_job.settle → read_json/write_json`(2),
`supervisor.run → claude_job.execute → claude_run.session_unrecoverable`(2), `sandbox.run_one → profile`(1). `json.loads(parse_float=_number)`의 `_number`는 표준 라이브러리 콜백(정적 미집계, 말단).

#### 검사 결과(인계 커밋 직전 작업 트리)

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"`: 377개 OK, 종료 코드 0
- 같은 명령 `/usr/bin/python3`(3.9): 377개 OK, 종료 코드 0(두 실행을 동시에 돌렸다)
- `git diff --check de6286b`: 문제 없음
- 검증 스크립트 재실행(수정본 `git archive` 복사본, scratchpad): `sbx_attack` 17종 중 out/ 정상 쓰기만 성공, rename_parent·tamper_harness_code 거절. `r6_e2e rename`·`tamper`
  (공격 executor 유형 2개를 그 프로세스에서만 등록하는 래퍼): rename 거절 → 결정적 실패, USER_STOPPED 유지 / 소스 쓰기 거절, 다음 프로세스의 RERUN_SAFE_TYPES `[]`.
  `stale_declaration` → PENDING·blocked. `unknown_reset_cascade`(원본 400회차·60초 poll은 8일에 못 미쳐 3회에서 끝남, poll 10**6으로 다시) → claude 4회, 간격 900·18000·691200초, 5번째 작업 미실행.
  `runner_evidence_probe` → 2.0초 반환, 가림 7종 모두 [가림], 거절 기록 3필드, options에 프롬프트 없음. `stage_probe` → 하드 링크 2종·봉인 이름 3종 거절. `budget_key_probe` → promotion 사용량 1.
  `dedupe_probe`는 새 계약(input_roles·실제 파일)에 맞춘 사본 `dedupe_probe_roles.py`로 같은 14종 + graph 2종 모두 기대대로. `sbx_case_probe` → 대소문자·..·/tmp 별칭 거절, 상속 fd만 쓰기(위 한계).

#### 롤백

- 전체: `git revert 92c9d04 fe2b440 d4140d9 e367c83`(역순). 운영 상태 형식 변화: `supervisor/claude_unknown_limit.json` 새 파일(되돌리면 읽히지 않음), 실험 계약에 `input_roles` 필수
  (되돌리면 다시 선택 아님·모르는 키로 거절). 실운영 root는 아직 없다.

### 2차 결함 수정

작성: Claude(Opus 하위 에이전트), 2026-11-28. 근거: 독립 재검증 `verify-auto-resume-123-r2.md`(G1~G12, 생존 변이 7개), 실환경 `c-realenv/t4-bogus-resume.jsonl`.
대상 `d564d21..` 이 절의 커밋. push·main 통합 안 함. 실제 claude 실행·모델·네트워크 호출·설치·시스템 설정 변경 0회. 자동 재개 목록
`claude_perm.AUTO_RESUME`·재실행 안전 목록 `recovery.RERUN_SAFE_TYPES`는 계속 비어 있다(어떤 유형도 켜지 않음). 새 회귀 시험은 수정 전 코드에서
실패를 확인했다(아래 "수정 전"). 변이 공백(N03·N06·N07·N17·N20·N24·N37)용 단언은 수정 전에도 통과하는 시험이며 변이로 확인했다.

#### 커밋

| 묶음 | SHA | 결함 |
|---|---|---|
| 1 | `1c62133` | G1·G2·G6·G7 실행기 경계(+ G4 일부: 감싼 executor 표 거절) |
| 2 | `442884f` | G4 논리 중복 키·등록 잠금 |
| 3 | `8020053` | G3·G5·G8·G9·G10·G11·G12 |
| 인계 | 이 문서 커밋 | 이 절, G3 새 세션 상한 단언 추가(변이 X09 공백) |

#### 경계 설계(메인 지시 1~5: `briefs/brief-fix2.md`. 4차에 출처 정정, 이전 표기 "사용자 지시"는 오표기)

1. 실행기 경계: executor가 쓸 수 있는 곳은 `sandbox.run_one`이 실행마다 하네스 root·저장소 밖에 새로 만드는 실행 폴더의 `out/`(staging)·`tmp/`(TMPDIR)뿐이다.
   확정 `out/`(root/tasks/<키>/out)에는 executor 쓰기 권한이 한 번도 없다(프로필이 실행 폴더 자체·`in/`·root 전체를 거절). 실행 뒤 하네스가 실행 전에 연
   staging 폴더 fd에서 계약 outputs만 조각마다 O_NOFOLLOW로 열고 fstat으로 일반 파일·링크 수 1을 확인해(링크·하드 링크·FIFO·폴더 거절) 확정 out/에 새
   파일로 복사한다(`safefs.open_regular`·`replace_new`). executor 자식은 새 세션으로 띄워 끝나면 그룹째 KILL하고, runner가 죽으면 자식이 그룹째 끝낸다.
   표준 출력은 이름 없는 임시 파일로 받아 출력을 쥔 자손 때문에 runner가 멈추지 않는다. 하네스의 모든 파일 쓰기(`cas.put·restore·get`, `jsonio.write_json`,
   `claude_perm.stage_inputs`, 확정 out 복사)는 mkstemp(O_EXCL 임의 이름) 새 파일 + fsync + os.replace이고 대상·대상 폴더 링크를 거절한다(grep으로 `.tmp.%d`·
   `copyfile`·`os.replace` 전수 확인: 남은 os.replace는 `recovery._archive`(하네스 소유 done.json 이동)뿐, pointer는 jsonio를 쓴다). 실험·학습·평가 executor는
   runner가 실행 직전 SHA를 확인해 작업 폴더 `in/`에 복사한 사본(sandbox 쓰기 불가)을 `HARNESS_INPUT_DIR`로 받는다.
   Claude 작업 out/ 점검: Claude는 A 옵션(`Edit(./out/**)`, 명령 실행 도구 없음)으로 out/에 직접 쓴다. staging으로 바꾸면 실환경 확인한 A 옵션을 바꿔야 해서
   하지 않았다(한계). 대신 하네스는 선언 파일을 O_NOFOLLOW·O_NONBLOCK·일반 파일만 읽고(`evidence.outcome_of`), 산출물 해시는 일반 파일만(`manifest.build`),
   선언 자리가 폴더면 그 작업만 대기(G11), CORRUPT 복구는 위 안전 쓰기다. Claude에는 명령 실행 도구가 없어 늦게 남는 자손이 없고 프로세스 그룹은 종료 뒤 KILL한다.
2. 상한: 한도 해제 뒤 재개·실행 중 사망 뒤 재개·복원 불가 뒤 새 세션을 합쳐 기존 `crash_resumes`(이름 그대로, 뜻은 자동 재개 합계)로 세고 `recovery.MAX_INTERRUPTS`(2)를
   넘으면 그 작업만 대기(`too_many_interrupts`). 새 횟수를 만들지 않았다. 값이 정수가 아니면 넘은 것으로 본다. 시각 미상 한도의 전체 3회는 따로 센다.
3. 중복 판정: command가 입력을 `{input:<inputs의 경로>}`로 참조하고 키는 자리표시자를 입력 SHA로 바꾼 명령(+ code_sha·config·seed·needs_*)으로 만든다.
   `input_roles`는 설명 키(키에서 뺌), 세 유형은 키에서 한 부류(`"class": "condition"`). 참조하지 않는 입력·없는 입력 자리표시자는 등록 거절(실행에 어떻게
   쓰이는지 판별할 수 없어 키를 정할 수 없다). 정규화(중복 쪽만): `--opt=value`, 경로 normpath, 저장소 아래 절대 경로, 첫 토큰 python 별칭, 숫자 토큰,
   config 안 seed(seed 키와 다르면 거절), config 1 = 1.0(유지 이유: 같다고 봐서 생기는 손해는 등록 거절 + 기존 작업 안내, 다르다고 봐서 생기는 손해는 같은 실험
   중복 실행). deterministic으로 감싸기: 실행 조건을 가진 비실험 유형은 거절(기존), 실험 executor 함수를 다른 유형 이름에도 등록한 executor 표는
   `sandbox_child list`가 거절(종료 코드 2 → `sandbox.sandboxed` ChildError → runner 실행 0). enqueue와 graph 등록의 검사·저장은 `root/enqueue.lock` flock 안.
4. 작업별 대기: 선언 하나의 문제(계약 형식·키 불일치·모르는 유형·입력 SHA 불일치)는 그 선언만 거절하고 장부 `declaration_rejected` + 알림을 같은 사유당 한 번
   (`supervisor/declared_rejected.json`). 선언 파일 자체(깨진 JSON·dict 아님·순환)는 그 회차 그래프 등록만 건너뛰고 한 번 알림. 선언 자리가 폴더면 그 작업만 대기.
   깨진 시각 미상 횟수 기록은 소진(Claude만 멈춤). 장부·상태 무결성 오류의 INTEGRITY_HALT는 그대로다.
5. G8: 복원 불가는 `type(returncode) is int`이고 1, stdout의 비어 있지 않은 줄이 그 result 하나(scan의 events 1·bad_lines 0)일 때만. 실환경 파일과 대조:
   `t4-bogus-resume.jsonl`은 비어 있지 않은 줄 1개이고 시험 상수 `REAL_NO_SESSION`(ID 자리만 바꿈)과 같다(직접 비교 True).
   G10: 이스케이프된 JSON 따옴표, Authorization Basic, URL `user:pass@`, 공백이 든 따옴표 값(닫는 따옴표까지), PEM 블록, 쿠키 헤더 줄 끝까지 가림.
   G12: 정상 종료 뒤 출력 읽기 대기는 총 시간과 무관하게 KILL_GRACE_S(두 스트림 합쳐 한 기한).

#### 결함별 조치·회귀 시험

| # | 회귀 시험 | 수정 전 |
|---|---|---|
| G1 | `test_harness_safe_writes`(옛 임시 이름 링크를 깔아도 cas·jsonio·입력 복사가 피해 파일을 안 바꿈, 대상·폴더 링크 거절, claim 복구 경로), `test_harness_exec_boundary.test_late_descendants…` | 실패: 피해 파일 덮어씀, 링크 대상에 씀, 확정 out 쓰기 ok |
| G2 | `test_link_hardlink_fifo_dir_outputs_and_a_swapped_out_folder_are_refused`, `test_profile_grants_only_a_run_folder_outside_root_and_repo` | 실패: 링크 산출물 통과, 프로필 API |
| G6 | `test_experiment_executor_reads_the_verified_input_copy`(대조 뒤 원본을 바꿔도 사본 SHA로 실행, 사본 쓰기 거절) | 실패: 사본 없음 |
| G7 | `test_late_descendants…`(같은 그룹 자식은 실행 뒤 죽음, setsid 손자도 확정 out 못 씀) | 실패 |
| G3 | `test_harness_resume_caps.test_all_automatic_resumes…`(한도→복원 불가 반복: 실행 3회 뒤 대기, 1회 재개한 작업의 복원 불가는 새 세션 없이 대기) | 실패: 7회 실행 |
| G4 | `test_harness_dedupe_keys`(표기 9종·seed·config 중복, 맞바꿈 등록, 미참조·없는 입력·seed 충돌·실행 조건 가진 deterministic 거절, 동시 등록 5회 모두 1개, 감싼 표 거절) | 실패: 동시 등록 10/10 이중 등록(별도 재현), 감싼 표 사용 |
| G5 | `test_harness_task_isolation`(선언 SHA 불일치·깨진 선언 파일 3종 → 정지 없음·독립 작업 완료·알림 1번) | 실패: INTEGRITY_HALT |
| G8 | `test_unrecoverable_needs_a_single_result_line_and_an_int_exit_code`(init 앞 줄·두 result·나쁜 줄·True·1.0) | 실패: 모두 True |
| G9 | `test_broken_unknown_limit_counter…`(깨진 JSON·-1·"1"·true → claude 1회 뒤 소진, 정지 없음) | 실패: INTEGRITY_HALT |
| G10 | `test_more_secret_forms_are_masked`(8종) | 실패 |
| G11 | `test_declaration_path_that_is_a_folder_holds_only_that_task` | 실패: INTEGRITY_HALT |
| G12 | `test_output_finishing_right_after_an_exit_near_the_total_limit_is_not_a_timeout` | 실패: timeout_total |
| N03·N06·N07 | `test_profile_grants_only…`(Apple Event 거절·실행 파일 거절 문자열, 실행 폴더가 root·root/tasks·저장소 안이면 ValueError) | 변이로 확인 |
| N17 | `test_inputs_outside_the_source_folder…`(SHA가 맞는 `../` 입력: 등록·실행 직전 복사 모두 거절, executor 0회) | 변이로 확인 |
| N20 | G5 첫 시험(그래프 등록의 입력 대조가 없으면 등록돼 실패) | 변이로 확인 |
| N24 | G9 시험 | 변이로 확인 |
| N37 | `test_stop_during_an_unrecoverable_resume_opens_no_new_session` | 변이로 확인 |

#### 변이 확인(수정본 `8020053`, 변이마다 새 복사본 + 전체 harness 시험 -f, .venv Python)

r2 생존 7개(새 코드 위치로 옮김: N03·N06 실행 폴더 root 안 허용·N07 저장소 안 허용·N17·N20·N24·N37)와 2차 수정 핵심 X01~X19(예측 가능한 임시 이름 2곳,
링크 대상 허용, 하드 링크·링크 따라가기 허용, executor에 확정 out 직접, 그룹 정리 제거, 입력 사본 대신 원본 대조, 새 세션 상한 제거, 한도 재개 미집계, 등록 잠금 제거,
키에 유형 이름, 미참조 입력 허용, 감싼 표 허용, 선언 거절 대신 예외, 선언 자리 오류 전파, 복원 불가 줄 수 무시, 읽기 대기 총 시간 기준, 깨진 카운터 전파):
26개 중 25개 잡힘. X09(새 세션 직전 상한 검사 제거)는 처음에 살아남아 G3 시험에 "이미 1회 재개한 작업의 복원 불가는 새 세션 없이 대기" 단언을 더했고,
인계 커밋 상태(수정본 + 새 단언) 복사본에서 그 변이가 잡히는 것을 확인했다(그 시험 모듈만). 다른 25개는 `8020053` 그대로에서 전체 시험으로 잡혔다.

#### 재현 스크립트 재실행(수정본 `git archive 8020053` 복사본, scratchpad. 원본 스크립트는 고치지 않고 사본만 고침)

- `r2_sbx_drive.py` links·swap·linger·normal(원본 그대로): links 하드 링크 4종 거절·피해 파일·opstate 그대로, swap 1회차 산출물 거절(ChildError)·2회차 다른 작업 done.json 쓰기 거절(`other_done_written: false`),
  linger 확정 out은 `result.txt`("x")만, normal 중첩 산출물 2개 정상.
- `plant`: 새 계약에서는 executor가 확정 out/에 링크를 심지 못해(거절, `final_links: []`) 손자가 확정 산출물을 바꾸지 못하고(VERIFIED) 원래 공격 지점에 닿지 않는다. 그래서 사본
  구동기 `r2_plant_fix.py`가 같은 사용자의 다른 프로세스를 가정해 확정 산출물을 직접 바꾸고 옛 임시 이름 `result.txt.tmp.1`~`.99998` 링크를 깐 뒤 2회차 runner를 돌렸다:
  CAS 복구 성공(VERIFIED), 피해 파일 그대로. `R2_TARGET=<복사본>/harness/recovery.py`: 소스 그대로, 다음 프로세스 `RERUN_SAFE_TYPES` `[]`.
- `r2_toctou_inputs.py`(사본: command 자리표시자, executor가 `HARNESS_INPUT_DIR` 읽기): 계약 SHA == executor가 본 SHA True. executor가 사본을 무시하고 원본을 직접 읽으면(`R2_READ=source`) False(한계: 읽기는 막지 않는다).
- `r2_declared_mismatch.py`(사본: 자리표시자): 상태 RUNNING, 독립 작업 완료. `r2_decl_dir.py`(원본): RUNNING, claude 0회(두 작업 모두 대기).
- `r2_session_probe.py`(원본): 변형 18종 중 True는 exact와 `errors_upper_id`뿐(이 시험 SID는 숫자·하이픈뿐이라 upper()가 같은 문자열, 실제 변형 아님). 반복: claude 3회, 새 세션 2회, outcomes rate_limited·rate_limited·blocked.
- `r2_counter_probe.py`(원본): 1) 4회 뒤 정지, 2) 깨진 JSON·음수·문자열·bool 모두 claude 1회 뒤 소진(정지 아님), 4) 사용자 해제 뒤 기록 3 유지(아래 한계).
- `r2_mask_probe.py`(원본): 10종 모두 가림(500자 초과 경계 값 포함).
- `r2_dedupe_probe.py`(사본: 경로 순서 자리표시자): 역할 바꾸기·python3·1.0·training·config seed·./·--a=1 중복, 맞바꿈 다른 키, lr 다름 등록, 동시 등록 20회 이중 0회.
  남는 것: 인자 순서·저장소 밖 절대 경로 등록(한계), config 1 vs 1.0 중복(설계), deterministic 감싸기(실행 조건 없음) 등록됨(아래 한계).
- 1차 `dedupe_probe.py`는 새 계약(자리표시자)에서 등록 단계에 막혀 그 적응본 `r2_dedupe_old_adapted.py`를 다시 자리표시자로 고쳐 돌렸다: 16종 모두 기대대로, graph 설명만 다름 → duplicates, 변형 유형 → rejected, training → duplicates.
- 1차 `sbx_attack.py`(사본: 새 프로필 API, 실행 폴더 out, 확정 out 쓰기 항목 추가): 18종 중 staging 정상 쓰기만 성공. `sbx_case_probe.py`(사본): 대소문자·..·/tmp 별칭 거절, 상속 fd만 쓰기(기존 한계).
  `r2_profile_inject.py`(사본): 괄호·줄바꿈·세미콜론·`#|` root에서 쓰기 거절, 따옴표·역슬래시 ValueError. `r6_e2e`(사본 래퍼, root를 R2_ROOT로): rename 거절 → 결정적 실패·USER_STOPPED 유지,
  tamper 소스 쓰기 거절·다음 프로세스 `[]`. `stage_probe.py`(원본): 하드 링크 2종·봉인 이름 3종 거절.

#### 바꾼 기존 시험

| 시험 | 이전 기대 | 새 기대 | 근거 |
|---|---|---|---|
| `test_harness_supervisor_resume.test_unknown_reset_backs_off_three_times_then_stops_and_notifies` | 작업 1개로 claude 4회, 알림 `[rate_limit_unknown_exhausted]` | 작업 2개: 같은 작업 3회(새·재개·재개) 뒤 `too_many_interrupts` 대기, 4번째 시도는 다른 작업 첫 실행. 간격 900초·5시간·8일·횟수 4 그대로, 알림 `[claude_job_blocked, rate_limit_unknown_exhausted]` | 메인 지시 2(`brief-fix2.md`: 모든 자동 재개 합계 ≤ MAX_INTERRUPTS), 승인 원문 "기존 재시도 상한 2회 안" |
| `test_harness_graph.test_declared_key_must_match_the_contract_hash` | GraphError | 그 선언만 `rejected`(GraphError 사유), 등록 없음 | 메인 지시 4(`brief-fix2.md`), HARNESS_RULES "그 작업과 의존 작업만 대기" |
| `test_harness_graph.test_register_missing_validates_each_contract_before_writing_it` | ContractError | `rejected`(ContractError 사유), 쓰지 않음(그대로) | 같음(메인 지시 4) |
| `test_harness_dedupe_conditions.test_unknown_or_variant_task_types…`의 graph 부분 | ContractError | `rejected`(ContractError 사유) | 같음 |

기대값은 같고 준비만 바꾼 시험(삭제·완화·skip 없음):
- 자리표시자: `dedupe_conditions._exp`(역할 순서로 `--<역할> {input:<경로>}`를 붙임: 역할 맞바꿈은 명령 자리가 바뀌어 여전히 등록), `policy_guards.experiment`, `policy_regress` R2 기본 계약.
- 실행기 경계: `test_harness_executors.intruder`·`sandbox_writes.attacker`가 root를 `HARNESS_TEST_ROOT`에서 읽음(out_dir이 staging이라), `runner_kit.spawn_runner`가 그 값을 넘김,
  `sandbox_writes`가 계약 outputs를 넘김. 강화: `sandbox_writes`에 자기 작업 확정 out/ 쓰기 거절 항목과 확정 out/에 계약 outputs만 있다는 단언.

#### 구조(함수 수·호출 깊이)

harness 함수 정의 수 전→후(`d564d21` 기준): 새 `safefs` 2(λ1), `cas` 6→6, `jsonio` 2→2, `claude_perm` 4→4, `sandbox` 4→4, `sandbox_child` 2→2, `runner` 5→5, `manifest` 2→2, `evidence` 4→4,
`dedupe` 5→5, `contract` 5→5, `queue` 6→6, `graph` 3→4, `supervisor` 4→4, `claude_job` 6→6, `claude_run` 6→6. 새 시험: `boundary_kit` 6(λ1), `exec_boundary` 6, `safe_writes` 5, `dedupe_keys` 7,
`task_isolation` 7, `resume_caps` 7. 고친 시험은 함수 수 그대로(`dedupe_conditions` 6, `graph` 7+λ1, `supervisor_resume` 7, `sandbox_writes` 5, `executors` 7, `runner_kit` 7). 7 초과 시험 파일은 기존 것뿐(route_* 등, 이번에 안 고침).
최대 호출 깊이 4, 초과 0(`structure_measure.py`). 새·바뀐 경로: `runner.main → drain → _execute → claude_perm.stage_inputs → safefs.replace_new`(4), `runner.main → drain → queue.claim → cas.restore → replace_new`(4),
`supervisor.run → claude_job.settle → queue.complete → cas.put → replace_new`(4), `supervisor.run → graph.register_missing → note_rejected → ledger.append`(3), `audit.record_verdicts → withdrawal.withdraw →
champion.restore_locked → cas.get → replace_new`(4). 동적 호출(정적 미집계): `_execute → executor 표 → sandbox.run_one → safefs.open_regular·replace_new·profile`(main부터 4). `jsonio.write_json`은 깊이 4
경로의 말단이라 safefs를 부르지 않고 같은 단계를 펼쳤다. 스레드 대상 `sandbox_child._watch`는 말단.

#### 검사 결과

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"`: 400개 OK(인계 커밋 직전 작업 트리)
- 같은 명령 `/usr/bin/python3`(3.9): 400개 OK, 종료 코드 0
- `git diff --check d564d21`: 문제 없음.

#### 남는 한계

- setsid로 새 세션을 만든 executor 자손은 그룹 정리 밖이라 남는다(pid를 모른다). sandbox를 물려받아 자기 실행 폴더 밖에는 쓰지 못하고, 실행 폴더는 실행 뒤 지워지며 다시 만들 권한이 없다. CPU는 계속 쓸 수 있다.
- executor가 사본 대신 원본을 직접 읽는 것은 막지 않는다(읽기 비거절). 실험 아닌 Python 작업은 입력 원본 위치가 계약에 없어 사본을 만들지 않는다.
- 실험 입력의 실행 직전 복사는 Claude 입력과 같은 규칙(링크·하드 링크·봉인/Gold 이름 거절)이라 등록 때 대조(`verify_inputs`, 원본 폴더 안 링크 허용)보다 엄격하다: 등록됐어도 실행 직전에 결정적 실패할 수 있다.
- Claude out/은 staging으로 바꾸지 않았다(위). `replace_new`는 대상과 바로 위 폴더만 링크 검사한다(더 위는 하네스 소유 경로 전제). sandbox 전에 열린 fd로는 쓸 수 있다(runner는 표준 입력 파이프와 출력 임시 파일만 넘김).
- 새 파일은 mkstemp 권한 0600으로 만든다(이전에는 umask 기본, 보통 0644). 같은 사용자만 읽는다.
- 중복 판정이 판별하지 못하는 표기: 인자 순서, 짧은 옵션 결합, 저장소 밖 절대 경로, config 안 경로 문자열, 명령 안 `--seed`와 seed 키. 실행 조건이 없는 deterministic 계약은 등록된다:
  실험 executor 함수 별칭 표는 거절하지만, 이름이 다른 함수가 안에서 실험을 돌리는 것은 코드 검토 몫이다. 자리표시자 없는 옛 실험 계약은 비교 대상에서 빠진다(실운영 root 없음).
- 시각 미상 한도 횟수는 claude 성공으로만 0이 된다: 사람이 소진 조건을 풀어도 3으로 남아 다음 미상 한도는 다시 시도 없이 소진된다(의도된 보수 동작, 다시 세려면 기록 파일 삭제).
- 비밀 가림은 최선 노력이다(꼬리 자르기로 PEM 머리가 잘리면 본문이 남을 수 있다). 정상 종료 뒤 출력 대기 때문에 총 시간을 최대 KILL_GRACE_S(5초) 넘길 수 있다.

#### 롤백

- 전체: `git revert <인계 커밋> 8020053 442884f 1c62133`(역순). 운영 상태 형식 변화: 새 파일 `root/enqueue.lock`·`supervisor/declared_rejected.json`, 실험 작업 폴더 `in/`, 실험 계약 command 자리표시자 필수
  (되돌리면 `input_roles`가 다시 필수), `crash_resumes` 뜻 확대. 실운영 root는 아직 없다.

### 3차 결함 수정

작성: Claude(Opus 하위 에이전트), 2026-11-28. 근거: 독립 재검증 `verify-auto-resume-123-r3.md`(H1~H11, T3, T4, 생존 변이 7개), 실환경 `c-realenv/t4-bogus-resume.jsonl`.
대상 `101bf8d..` 이 절의 커밋. push·main 통합 안 함. 실제 claude 실행·모델·외부 네트워크 호출·설치·시스템 설정 변경·사용자 서비스 접속·앱 실행 0회
(로컬 통신은 시험이 직접 연 대기 소켓에 sandbox 안에서 접속을 시도해 거절되는 것만 확인). 자동 재개 목록 `claude_perm.AUTO_RESUME`·재실행 안전 목록
`recovery.RERUN_SAFE_TYPES`는 계속 비어 있다(어떤 유형도 켜지 않음). 새 회귀 시험은 수정 전 코드에서 실패를 확인했고(아래 "수정 전"), 시험 공백(T3·T4)용
단언은 수정 전에도 통과하므로 변이로 확인했다.

#### 커밋

| 묶음 | SHA | 결함 |
|---|---|---|
| 1 | `3ac39c6` | H1 code_sha 실제 코드 대조·needs_vision 우회 |
| 2 | `9c21e8f` | H2 숫자 토큰 오거절 |
| 3 | `6f42eba` | H6·H8·S30 자동 재개 근거 fail-closed |
| 4 | `fe86096` | H9 sandbox 네트워크·lsopen·launchservicesd |
| 5 | `b776f74`, `8baa6af`, `7137726` | H4·H5·H7·H10, T3·T4(S09·S10·S18·S26·S39) 시험, 반영 시험 보강, S39 시험 표식 대기(부하 때 경합) |
| 6 | 이 문서 커밋 | 이 절 |

#### 결함별 조치·회귀 시험

| # | 조치 | 회귀 시험 | 수정 전 |
|---|---|---|---|
| H1 | `dedupe.verify_code`: 실험·학습·평가의 `code_sha`가 source_root(`git -C <source_root>`)의 최상위(`--show-toplevel` = source_root)·`rev-parse HEAD`(소문자)와 같고 `status --porcelain --untracked-files=no`가 비어 있어야(추적 파일 변경·스테이징 없음) 통과. git 실행 실패·저장소 아님·하위 폴더·다름은 ContractError(fail-closed, 그 작업만). 사용자 `GIT_*` 변수 제거, `GIT_OPTIONAL_LOCKS=0`(index 갱신 안 함), fsmonitor 끔. 등록(`verify_inputs` 안, enqueue·graph)과 `runner._execute` 실행 직전 둘 다. 64자는 HEAD가 64자(sha256 저장소)일 때만 같을 수 있다. 키의 code_sha = 대조한 HEAD. needs_llm=false면 needs_vision=true 거절, 키에서 needs_vision 제외 | `test_harness_code_sha`(다른 16진·64자·한 글자 다름·저장소 아님·추적 파일 변경·하위 폴더 → enqueue ContractError·graph rejected, 대문자 HEAD = 중복, 등록 뒤 새 커밋·변경 → executor 0회·결정적 실패, needs_vision) | 3개 모두 실패(등록됨·executor 1회) |
| H2 | 정수 모양(앞자리 0 없음)은 부호 표기만 정규화(+5 = 5, -0 = 0: int 정확 비교와 같고 자릿수 제한 없음), 소수·지수는 자릿수+2 정밀도 `decimal`로 normalize(.5 = 0.5, 1e-3 = 0.001), 앞자리 0(`01`)·소수점 끝 0(`1.10`·`0.10`·`1.0`)·끝 점(`1.`)은 문자열 그대로. float·1e15 경계 제거 | `test_harness_dedupe_numbers`(다른 값 9쌍 등록, 같은 값 7쌍 중복) | 실패(`12345678901234567`/`…568` 중복) |
| H6·S30 | `claude_job.pick`: 상태 파일이 깨진 JSON·dict 아님·`KNOWN`(new·running·rate_limited·blocked·done·failed·stale) 밖 status면 큐 PENDING일 때 그 작업만 `blocked`(`job_state_invalid: <앞 200자>`, crash_resumes 없음) + 장부 `claude_job_closed` + 알림 `claude_job_blocked` 한 번. `execute`: `crash_resumes` 없음·null·정수 아님(bool 포함)·음수는 상한 도달 | `test_harness_job_state` 1·2(5종 파일 × Supervisor 2회: 독립 작업만 실행·알림 1번, 7종 값 → held·claude 0회) | 둘 다 실패(새 세션 다시 열림, 키 없음 → --help 호출) |
| H8 | `session_unrecoverable`에 `result.session_id == resumed` 추가(실환경 t4는 같음: 직접 확인) | `test_harness_job_state` 3(다른 ID·키 없음 False) | 실패(True) |
| H9 | `sandbox.DENY_MORE`: `(deny network*)`, `(deny network-outbound (remote ip "localhost:*"))`, `(deny lsopen)`, `(deny mach-lookup (global-name "com.apple.coreservices.launchservicesd"))`. 외부 네트워크도 거절(executor 계약에 네트워크가 필요 없다) | `test_harness_sandbox_deny`(실제 sandbox-exec: 시험이 연 TCP 대기 소켓 접속·UDP·0.0.0.0 bind·시험이 연 유닉스 소켓 접속 EPERM, 처리할 앱이 없는 URL 체계 `LSOpenCFURLRef` -54(거절 없으면 -10814 = 앱 없음, 부작용 없음), launchservicesd `bootstrap_look_up` 1100(이름 조회만), 같은 실행에서 정상 산출물 생성, 대기 소켓에 들어온 접속 0) | 실패(규칙 없음). 규칙을 뺀 수동 실행: 접속·bind ok, -10814, 0 |
| H4 | `run_one`: 산출물을 연 순간의 fstat 크기까지만 복사(`safefs.replace_new(limit=)`), 크기가 `sandbox.MAX_OUTPUT_BYTES`(1 GiB) 초과 → EFBIG 결정적 실패, 표준 출력은 fstat 크기 기준 `MAX_STDOUT_BYTES`(16 MiB) 초과 → 결정적 실패·그만큼만 읽음, stderr는 끝 300바이트만 읽음 | `test_harness_output_commit` 4·5(상한 4096으로 1 MiB 희소 파일·100 KB 표준 출력 거절, 열어 잰 뒤 원본이 커져도 잰 크기만 복사(F_GETPATH로 원본에 덧붙이는 주입), replace_new limit) | 실패(속성·인자 없음) |
| H5·S09 | 확정 out/은 실행 전에 `O_NOFOLLOW|O_DIRECTORY`로 연 fd로만 반영(링크면 executor 실행 전 ChildError). 산출물을 모두 검사해 하네스 소유 `작업 폴더/.out-pending-*`에 복사한 뒤 `safefs.publish`가 중간 폴더를 모두 O_NOFOLLOW로 열고(없으면 만듦) 자리가 폴더가 아닌지 본 뒤에야 `os.replace(dst_dir_fd)`로 옮김. 실패하면 임시 폴더 삭제, 확정 out/ 그대로 | `test_harness_output_commit` 1·2(확정 out/ 자체·안의 중간 폴더가 링크 + `n/a.txt` → 피해 폴더 그대로, 출력 목록 불일치 → 비어 있음, 링크 하나 → 이전 `a_report.json` OLD 유지·임시 폴더 없음, 옮길 자리가 폴더 → 다른 산출물도 안 옮김) | 실패(NEW ≠ OLD). S09·S10은 수정 전 통과(시험 공백) |
| H10 | `runner.main`이 `sandbox.sandboxed`의 ChildError를 잡아 `{"executor_table_error", "executed": 0}` 한 줄과 종료 코드 `runner.EXECUTOR_TABLE_EXIT`(6) | `test_harness_sandbox.test_runner_killed_ends…`(감싼 표 → 6, traceback 없음) | 실패(JSON 없음) |
| H7 | `runner._execute`가 command의 `{input:<경로>}`를 작업 폴더 `in/` 사본 절대 경로로 바꾼 계약 사본을 executor에 넘김(계약 파일은 그대로) | `test_harness_code_sha.test_executor_gets_the_command…` | 실패(자리표시자 그대로) |
| S39 | 코드 변경 없음 | `test_harness_sandbox.test_runner_killed_ends…`(executor가 남긴 같은 그룹 자식이 runner kill -9 뒤 죽음. 시험 executor `slow`에 `hang_child` 모드) | 통과(시험 공백) |
| S26 | 코드 변경 없음 | `test_harness_register_race`(enqueue+graph·graph×2 각 5회, 항상 REG 1·DUP 1, 작업 폴더 1개) | 통과(시험 공백) |
| S18 | 코드 변경 없음 | `test_harness_output_commit` 5(해시 검사를 통과했다고 두고 보관본을 바꿈 → restore 실패 목록, 대상 그대로) | 통과(시험 공백) |

#### 변이 확인(수정본 `8baa6af`, 변이마다 새 복사본 + git init·커밋 + 전체 harness 시험 -f, .venv Python, 병렬 6)

변이 32개 모두 잡힘: r3 생존 S09(새 위치: 확정 out fd O_NOFOLLOW 제거)·S10·S18·S26·S30(새 위치)·S39, 새 경계 P1(publish 중간 폴더 NOFOLLOW 제거)·P2(폴더 자리 사전 검사 제거),
H1a~f(실행 직전 대조·등록 대조·추적 파일 검사·최상위 검사·needs_vision 거절·needs_vision 키 포함), H2a~c(문자열 숫자 보존·정수 float 경유·십진 16자리), H6a~c(형식 검사·깨진 JSON을 없음으로·음수 허용),
H8, H9a~d(규칙 하나씩 제거), H4a~d(잰 크기 제한·산출물 상한·표준 출력 상한·replace_new limit 무시), H5(확정 out에 바로 복사), H10, H7. r3의 S41·S42는 숫자 정규화를 다시 써서 원문이 없다(H2a~c로 대신).
변이 없는 기준(S00)이 그 병렬 실행(부하 평균 27)에서 내 새 S39 시험의 표식 경합으로 실패해 시험을 고쳤고(`7137726`: 자식 표식까지 기다림), 고친 `7137726`에서 S00·S39·H10·H6c를
해당 모듈만(sandbox·job_state·exec_boundary·output_commit) 다시 돌렸다: S00 통과, 셋 모두 의도한 시험으로 잡힘(H6c는 전체 실행 때 첫 실패가 기존 `exec_boundary` 늦은 자손 시험의
부하 시간 초과였다. 그 시험은 부하가 크면 불안정할 수 있다). 결과: scratchpad `fix3/mutants.log`·`mutants_targeted.log`(커밋하지 않음).

#### 재현 스크립트 재실행(수정본 `8baa6af` git archive 복사본을 git init·커밋, 사본 스크립트만 고침)

- `r3_dedupe_probe.py`(사본: 원본 폴더를 복사본 저장소의 clone으로, code_sha 기본값 = 그 HEAD, 추적 파일인 README.md 대신 `extra/r.md`): A의 `code_sha` 다른 16진·64자 → ContractError(HEAD와 다름),
  needs_vision 뒤집기 → ContractError. 남는 등록: 실행에 안 쓰는 config 키·`python -u`·인자 순서(한계 H3), `python3`+`0.10`(0.10 ≠ 0.1이 새 규칙). B의 큰 정수 seed·`1.10`/`1.1`·`01`/`1` → 등록,
  config 1/1.0 → 중복(설계 유지). C 동시 등록 20회 × 3종 이중 등록 0(이 스크립트는 multiprocessing spawn이라 자식이 모듈 머리를 다시 실행해 출발선이 맞지 않는다: 경합 확인은 `test_harness_register_race`가 한다). D 등록 뒤 원본 변경 5종 모두 거절.
- `r3_session_jobfile_probe.py`(원본 그대로): 판정 11종 중 True는 exact·빈 줄뿐(결과 session_id 다름 → False). 빈 AUTO_RESUME: claude 1회·resume 0. 상태 파일 변형 4종(`[]`·`"Blocked"`·crash_resumes 삭제·null)
  모두 변형 뒤 claude 추가 0회, 최종 blocked.
- `r3_runner_e2e.py`(사본: 원본 폴더를 git 저장소로 + code_sha = HEAD, `r3_exp_exec` 사본은 runner가 바꿔 넘긴 사본 절대 경로를 읽음): 실험 copy → VERIFIED·계약 SHA·사본 쓰기 EPERM·사본 0600,
  source(원본 직접 읽기) → VERIFIED·바뀐 내용(한계 H7), 감싼 표 → 종료 코드 6·요약 JSON·stderr 없음, 결정적 normal → VERIFIED, symlink → FAILED·확정 out/ 비어 있음(H5).
- `r3_sbx_drive.py`(사본: 늦은 자손 보고를 127.0.0.1 대신 구동기가 그 프로필에만 쓰기를 허용한 관찰 폴더 파일로, 실패 때 report.json도 그 폴더에서 읽음. 네트워크 거절 때문):
  symlink·hardlinks·fifo·dirlink·swap_after → ChildError, 확정 out/에는 이전 `prev.txt`뿐(관찰용 report.json도 남지 않음), sparse 2 GiB → EFBIG 거절(0.4초 안), grow(기본 1.5 GB) → 연 순간 1.15 GB라 EFBIG 거절
  (300 MB로 줄인 실행은 손자가 이미 다 쓴 뒤라 300 MB 복사, 상한 안), rmtree_trap·brokers(`defaults write` Could not write domain)·signals·normal → 정상, 모든 경우 피해 파일·피해 폴더·opstate·prev 그대로,
  남은 실행 폴더 0, swap_after 늦은 손자의 실행 폴더 재생성 EPERM.

#### 바꾼 기존 시험

| 시험 | 이전 기대 | 새 기대 | 근거 |
|---|---|---|---|
| `test_harness_dedupe_conditions.test_real_differences_are_registered` | `needs_vision=True`만 다른 실험이 등록(6번째 키) | ContractError, 키 5개 | 메인 지시 1(`briefs/brief-fix3.md` "메인 결정", 사용자 승인 원문 아님: needs_llm=false 대상 유형은 needs_vision=true 거절) |
| `test_harness_dedupe_keys.test_registrant_labels…` | 명령 `0.10` = `0.1` 중복 | 등록(다른 키) | 메인 지시 2(`briefs/brief-fix3.md`, 사용자 승인 원문 아님. 4차에 출처 정정)·승인 계약 "실행 조건이 하나라도 실제로 다르면 통과": 소수점 끝 0은 버전·ID 문자열일 수 있어 같은지 판별할 수 없다. 다르게 봐서 생기는 손해(같은 실험 중복 등록 가능)를 택했다 |

기대값은 같고 준비만 바꾼 시험(삭제·완화·skip 없음): 실험 계약을 만드는 `dedupe_conditions`·`dedupe_keys`·`exec_boundary`·`policy_guards`·`policy_regress`·`task_isolation`이 원본 폴더를
`test_harness_git_kit.git_source`로 git 저장소(고정 작성자·시각의 커밋 하나, 입력 자료는 추적 안 함)로 만들고 code_sha를 그 HEAD(`CODE`, 모든 폴더에서 같음)로 바꿨다(근거 H1: 이전 `"c"*40`은
이제 거절). `policy_guards`의 판별 불가 키(`lr`) 거절 시험은 code_sha 대조 전에 거절되므로 `"c"*40` 그대로. `test_harness_executors.slow`에 `hang_child` 모드 추가(기존 모드 동작 같음).
config 1 = 1.0(중복)은 유지: config 값은 계약 작성자가 숫자로 적은 JSON 숫자이고, 같다고 봐서 생기는 손해는 등록 거절(DuplicateTask가 기존 작업을 알려 줌)이다. 단 실행 코드가 정수만
받으면(`range(1.0)`) 실제로 다르게 동작할 수 있다(사용자 결정 후보).

#### 구조(함수 수·호출 깊이)

harness 함수 정의 수 전→후(`101bf8d` 기준): `dedupe` 5→6(verify_code), `safefs` 2+λ1→3(publish, λ 제거), `sandbox` 4→4, `runner` 5→5+λ1(H7 치환), `claude_job` 6→6, `claude_run` 6→6.
새 시험(def+λ): `git_kit` 2, `code_sha` 7, `dedupe_numbers` 4, `job_state` 4, `sandbox_deny` 3+λ4, `output_commit` 7, `register_race` 1. 고친 시험: `sandbox` 3→4, 나머지 함수 수 그대로.
최대 호출 깊이 4, 초과 0(`structure_measure.py`). 새·바뀐 경로: `supervisor.run → graph.register_missing → dedupe.verify_inputs → verify_code`(3), `runner.main → drain → _execute → dedupe.verify_code`(3),
동적 `runner.main → drain → _execute → sandbox.run_one → safefs.publish`(4), `supervisor.run → claude_job.pick → opstate.notify → ledger.append`(3).

#### 검사 결과(`7137726` 작업 트리)

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"`: 416개 OK, 종료 코드 0
- 같은 명령 `/usr/bin/python3`(3.9): 416개 OK, 종료 코드 0(두 실행 동시)
- `git diff --check 101bf8d`: 문제 없음

#### 남는 한계(판별 불가·fail-closed로 둔 것 포함)

- H1: code_sha는 source_root의 git HEAD와 비교한다. executor가 실제로 도는 코드는 runner의 저장소(`sandbox.REPO`)이고 기본 source_root도 같지만, 다른 source_root를 주면 그 폴더의 HEAD를 본다.
  추적하지 않는 파일(새 스크립트를 커밋하지 않고 실행)은 코드 변경으로 보지 않는다. 등록과 실행 사이에 커밋이 하나라도 생기면 그 실험은 실행 직전 결정적 실패다(다시 등록해야 한다).
  git이 없거나 실패하면 실험·학습·평가는 등록·실행되지 않는다(fail-closed).
- H3(판별 불가 표기, 같은 실험이 중복 등록될 수 있다): 인자 순서, 짧은 옵션 결합, 인터프리터 옵션(`python -u` 등), 실행에 쓰이지 않는 config 키, 저장소 밖 절대 경로 철자, config 안 경로 문자열 철자,
  명령 안 `--seed`와 seed 키, 그 밖의 실행 파일 별칭. 숫자: `1.0`과 `1`, `0.10`과 `0.1`처럼 소수점 끝 0은 이제 다르게 본다(같은 실험 중복 가능 쪽).
- H7: executor가 사본 대신 원본(또는 저장소 안 같은 내용의 다른 파일)을 직접 읽는 것은 막지 않는다(읽기 비거절). runner는 사본 경로로 바꾼 명령을 넘길 뿐이다.
- H9: sandbox는 네트워크 전부·lsopen·launchservicesd 조회를 막지만 그 밖의 mach/XPC 서비스(launchd bootstrap 자체 등)는 막지 않는다. 네트워크가 필요한 executor(모델 가중치 내려받기 등)는
  실패한다(켜려면 사용자 결정). 복사한 Apple 실행 파일(`/usr/bin/open` 사본)은 이 macOS에서 실행 즉시 SIGKILL됨을 확인했지만 그 밖의 경로 실행 거절은 DENY_EXEC 세 경로뿐이다.
- H4: 상한 1 GiB·16 MiB는 임시값(코드 상수 `sandbox.MAX_OUTPUT_BYTES`·`MAX_STDOUT_BYTES`, 명령행 설정은 없음). 산출물 수 × 1 GiB 합계 상한은 없다. 상한 안의 희소 파일은 실제 바이트로 복사된다.
- H5: 반영 도중 `os.replace`가 실패하면(같은 파일 시스템 rename 실패, 예외적) 일부만 옮겨질 수 있다. 사전 검사에서 실패해도 빈 중간 폴더는 남을 수 있다. runner가 반영 중 kill되면 `작업 폴더/.out-pending-*`가 남는다(다음 실행에 영향 없음, 수동 정리).
- H11: 하네스가 만드는 새 파일(확정 out/·입력 사본·CAS·JSON)은 mkstemp 0600이다. 실행 비트가 필요한 산출물, OS 사용자 분리(D-7) 때 다른 사용자 읽기는 별도 규칙이 필요하다(문서화만).
- 기존 한계 유지: setsid 자손 잔존(쓰기는 막힘), Claude out/ staging 아님, replace_new는 바로 위 폴더까지만 링크 검사, sandbox 전에 열린 fd, 비밀 가림 최선 노력, 시각 미상 한도 횟수는 성공으로만 0.
- 실환경 미검증 그대로: Supervisor → 실제 claude → 큐 반영 전체 경로, 실제 한도 거절 이벤트 형식, 무인 재개, A 옵션의 실제 효과.

#### 롤백

- 전체: `git revert <이 문서 커밋> 7137726 8baa6af b776f74 fe86096 6f42eba 9c21e8f 3ac39c6`(역순) 또는 `git reset --hard 101bf8d`(이 브랜치만, push 전). 운영 상태 형식 변화: 실험 계약의
  code_sha가 source_root HEAD여야 함(되돌리면 형식만 검사), 작업 폴더 `.out-pending-*` 임시 폴더, 상태 파일 `job_state_invalid` 대기, runner 종료 코드 6. 실운영 root는 아직 없다.

### 4차 결함 수정

작성: Claude(Opus 하위 에이전트), 2026-11-28. 근거: 독립 재검증 `verify-auto-resume-123-r4.md`(I1~I9, 생존 변이 V01·V21), 사용자 결정 원문
`decisions-b5-b6-20261128.md` "숫자 표기 결정"(2026-11-28). 대상 `df6b78b..` 이 절의 커밋. push·main 통합 안 함. 실제 claude 실행·모델·외부 네트워크 호출·설치·
시스템 설정 변경·사용자 서비스 접속·메시지 전송·앱 실행 0회(mach 서비스는 sandbox 안 이름 조회만, 메시지 없음). 자동 재개 목록 `claude_perm.AUTO_RESUME`·재실행 안전 목록
`recovery.RERUN_SAFE_TYPES`는 계속 비어 있다(어떤 유형도 켜지 않음). 새 회귀 시험은 수정 전 코드에서 실패를 확인했다(아래 "수정 전"). 시험 공백(V01·V21)용 단언은 수정 전에도
통과하므로 변이로 확인했다.

#### 커밋

| 묶음 | SHA | 결함 |
|---|---|---|
| 1 | `d53ed63` | I1·I2·I3 숫자 표기(사용자 결정), 등록 경로 예외 = ContractError, task 문서 출처 오표기 정정 |
| 2 | `ded8e03` | I4 키에 HEAD^{tree}, I5 skip-worktree·assume-unchanged·추적 안 하는 command 파일 거절, V01 시험 |
| 3 | `4c2995f` | I6 모순된 작업 상태 파일 대기 |
| 4 | `1b611f3` | I7 sandbox mach-lookup 기본 거절 |
| 5 | `4c55c81` | I8(V21) 표준 출력 상한 사유, I9 산출물 합계 상한·kill 잔여물 정리 |
| 5' | `cd4db59` | I2 시험 보강(선언 파일 거대 정수 4400자리: 변이 "선언 parse_int 제거"가 처음에 살아남아 고침) |
| 6 | 이 문서 커밋 | 이 절 |

#### 결함별 조치·회귀 시험

| # | 조치 | 회귀 시험 | 수정 전 |
|---|---|---|---|
| I1·I3 | command 토큰은 숫자로 바꾸지 않는다(글자 그대로). 3차의 decimal 정규화·`_LITERAL`·`_INTEGER` 제거. 숫자 외 정규화(`--opt=value`, `/` 든 토큰 normpath, 저장소 아래 절대 경로, 첫 토큰 python 별칭, config 안 seed)는 그대로다: 숫자 변환에 기대는 부분이 없었다(숫자 모양 토큰에는 `/`가 없어 경로 분기에 닿지 않고, 별칭은 첫 토큰 이름만 본다). config·seed는 `json.dumps` → `json.loads(parse_int=parse_float=dedupe.json_number)` 왕복으로 자료형을 유지하고 같은 자료형 안에서 값으로 본다(1 ≠ 1.0, true ≠ 1, false ≠ 0, [1] ≠ [1.0], -0.0 = 0.0, 0.1 = 1e-1, 문자열 그대로). seed는 정수 필드 그대로(bool·실수 거절은 기존) | `test_harness_dedupe_numbers` 1·2(명령 21쌍 모두 등록, 같은 글자 3종 중복, config 같은 값 5쌍 중복·다른 자료형/값 8쌍 등록) | 실패(`2.5e1`/`25` 중복, config 1/1.0 중복) |
| I2 | `contract.task_key`·`dedupe.logical_key`·`verify_inputs`가 TypeError·ValueError·RecursionError 등을 ContractError로 바꾼다. NaN·무한대·`MAX_INT_DIGITS`(4000)자리 넘는 정수·JSON 아닌 값·너무 깊은 중첩은 ContractError. Supervisor는 선언 파일을 `parse_int=dedupe.json_number`로 읽어(4000자리 초과 정수 → NaN → 그 선언만 거절: Python 3.12의 정수 변환 상한 ValueError가 파일 전체를 깨지 않고 3.9와 결과가 같다) `RecursionError`도 파일 단위 문제로 처리한다 | `test_harness_dedupe_numbers` 3·4(NaN·±무한대·10^4001·set·5만 단 중첩·거대 seed → ContractError, 등록 없음 / 거대 지수 토큰 graph 등록, 선언 파일의 `1e1000000000000000000`·4001자리 config 선언만 거절·나머지 등록·INTEGRITY_HALT 아님, 10만 단 중첩 선언 파일 → 정지 아님) | 실패(`decimal.InvalidOperation`, 속성 없음) |
| I4 | 대조는 그대로 HEAD(커밋 SHA, 등록·실행 직전). `verify_code(task, source_root, others)`가 `rev-parse --show-toplevel HEAD HEAD^{tree}`로 tree를 같이 읽고, 다른 등록 계약의 커밋은 `cat-file --batch-check`(한 번)로 tree로 바꿔 `{커밋: tree}`를 돌려준다. `find_duplicate(root, task, key, source_root)`가 먼저 verify_code를 하고 키의 코드 자리(`code`)에 tree를 넣어 비교한다. 이 저장소에 없는 커밋의 계약은 비교하지 않는다. `verify_inputs`는 입력만 본다(git 두 번 부르지 않게) | `test_harness_code_tree` 1(빈 커밋·amend·같은 tree 부모 없는 새 커밋 → enqueue DuplicateTask·graph duplicates, 실제 코드 변경 커밋 → 새 키) | 실패(등록됨) |
| I5 | `git ls-files -v -z`에서 `H ` 아닌 표시(skip-worktree `S`, assume-unchanged 소문자, 그 밖)가 하나라도 있으면 거절. command 토큰(`--opt=value`의 값 포함, 자리표시자 제외)을 source_root 기준 글자 경로·실제 경로로 보고, source_root 안의 실제 파일인데 추적 목록에 없으면 거절. 등록·실행 직전 모두 | `test_harness_code_tree` 2·3(두 표시 각각: status는 깨끗한데 enqueue·graph 거절, 표시 전 등록한 작업은 executor 0회·결정적 실패 / `new_exp.py`·`./`·절대 경로·`--run=`·`x/..` 5종 거절, 추적 파일·없는 파일 통과, 커밋 뒤 등록) | 실패(등록됨) |
| V01 | 코드 변경 없음(시험 공백) | `test_harness_code_tree` 4(`GIT_DIR`·`GIT_INDEX_FILE` = 다른 저장소, `GIT_WORK_TREE` = source_root: 다른 저장소 HEAD 거절·자기 HEAD 등록·실행 직전 대조 통과 executor 1회) | 통과(변이로 확인) |
| I6 | `claude_job.pick`: 큐 PENDING인데 status `done`·`failed`·`stale`, 또는 status `new`인데 `crash_resumes`가 정수 0이 아니거나(없음·bool 포함) `session_id`가 있으면 기존 `job_state_invalid` 대기·장부·알림 한 번. 사람 해제는 그 작업의 상태 파일 삭제 한 가지(status를 new·done 등으로 고쳐 쓰는 것은 해제가 아니다: 다시 모순으로 대기). rate_limited로 고치는 재개는 기존 규칙대로 AUTO_RESUME(빈 목록)·crash_resumes 상한을 따른다 | `test_harness_job_state` 2(변형 8종 × Supervisor 2회: 독립 작업만 실행·알림 1번·blocked, 파일 삭제 뒤 다시 골라 VERIFIED, 정상 new(0·null)는 첫 실행) | 실패(새 세션 열림, claude 2회) |
| I7 | `sandbox.DENY_MORE`에 `(deny mach-lookup)` + `MACH_ALLOW`(= `com.apple.system.opendirectoryd.libinfo`)만 허용. 허용 이름 근거: 빈 허용 목록에서 정상 executor 시험은 모두 통과했지만 표준 라이브러리 `pwd.getpwuid`가 KeyError(사용자 정보 조회 불가)라 그 읽기 전용 조회만 허용했다. 같은 프로필에서 사용자·시각·로케일·임시 파일·하위 프로세스·sqlite·ssl 문맥·uuid1·numpy 동작 확인(.venv·/usr/bin/python3) | `test_harness_sandbox_deny`(r4가 조회 성공을 본 18개 이름 조회 1100, 허용 이름만 0, 규칙 문자열, 정상 산출물 생성. lsopen은 -54 또는 -10661: 기본 거절 뒤에는 LaunchServices 서버에 닿지 못해 -10661이 나온다. 둘 다 열리지 않음, 앱 없음 -10814·열림 0이 아님) | 규칙 없음(변이로 확인) |
| V21 | 코드 변경 없음(시험 공백) | `test_harness_output_limits` 1(표준 출력 상한 → 사유 "표준 출력이 상한") | 통과(변이로 확인) |
| I9 | `sandbox.MAX_TOTAL_OUTPUT_BYTES`(임시 4 GiB) 넘으면 EFBIG 결정적 실패. 실행 폴더 이름을 `harness-exec-<task_key>-*`로. `sandbox.sweep(task_dir)`: `queue.claim`이 잠금을 잡고 이전 주인이 죽었다고 판정한(`who == "dead"`) 뒤에만 작업 폴더 `.out-pending-*`와 시스템 임시 폴더 `harness-exec-<task_key>-*`를 지운다(링크·폴더 아닌 항목 제외) | `test_harness_output_limits` 1~3(합계 5바이트 상한 → 거절·확정 out/ 비어 있음, 6이면 정상 / 실행 폴더 이름·실행 뒤 없음 / 다른 runner가 잠금을 쥐면 그대로, 잠금을 잡은 뒤 정리, 다른 작업 실행 폴더·링크 대상 그대로) | 실패(속성 없음, 정리 안 됨, 이름에 키 없음) |

#### 바꾼 기존 시험(기대값 변경)

| 시험 | 이전 기대 | 새 기대 | 근거 |
|---|---|---|---|
| `test_harness_dedupe_numbers`(파일 다시 씀) | 명령 토큰 `5`/`+5`·`0`/`-0`·`0.5`/`.5`·`0.001`/`1e-3`·`1e-3`/`1E-3`·`2.5e3`/`2.5E+3`·긴 정수/`+`긴 정수 7쌍 = 중복 | 7쌍 모두 등록(다른 키). 다른 값 9쌍은 그대로 등록, I1 쌍(`1e3`/`1000` 등 5쌍)도 등록 | 사용자 결정 2026-11-28 숫자 표기("자료형을 확인할 수 없는 경우 임의로 숫자로 변환하지 않는다", "실험 명령 문자열 전체에 일괄적인 숫자 정규화를 적용하지 않는다") |
| `test_harness_dedupe_keys.test_registrant_labels…` | config `{"epochs": 1.0}` = `{"epochs": 1}` 중복 | 등록(다른 키). config 안 seed = seed 키 중복은 그대로 | 사용자 결정 2026-11-28 숫자 표기("수치형 파라미터는 자료형과 실제 값을 기준으로 정규화") |
| `test_harness_dedupe_conditions.test_same_conditions…` | config `{"lr": 1.0}`가 `{"lr": 1}` 작업의 중복 | 등록(다른 키). 같은 자료형(`{"lr": 1}`, risk만 다름)은 중복 | 같음 |
| `test_harness_sandbox_deny` | lsopen 결과 정확히 -54 | -54 또는 -10661(둘 다 열리지 않음), 그 대신 mach 이름 19개 단언 추가 | I7 기본 거절 뒤에는 LaunchServices 서버 조회가 먼저 막혀 -10661이 나온다(이 macOS에서 직접 확인). 앱 없음(-10814)·열림(0)은 여전히 실패다 |

명령 `0.10`/`0.1` 등록(3차 기대)은 그대로다: 3차 표의 근거 "사용자 지시 2"는 메인 지시(`brief-fix3.md`)의 오표기라 정정했고, 이 기대는 이제 사용자 결정 2026-11-28 숫자 표기가 근거다.
기대값은 같고 준비만 바꾼 시험: 없음(단언 삭제·약화·skip 없음).

#### 변이 확인(수정본 `4c55c81`, 변이마다 git archive 새 복사본 + 관련 시험 모듈, .venv Python, scratchpad `fix4/mutants4.py`·`mutants4.log`)

r4 생존 V01(verify_code가 사용자 GIT_* 환경을 넘김)·V21(표준 출력 상한 분기 제거) 둘 다 잡힘. 4차 수정 핵심 17개(키에 커밋 SHA·다른 계약 tree 안 구함·skip-worktree 검사·미추적 command 파일 검사·
종료 status+PENDING·new 모순·정수 자릿수 상한·task_key/logical_key 예외 변환·Supervisor RecursionError·config float 정규화·config 1.0→1 옛 규칙·mach 기본 거절·합계 상한·claim의 sweep·실행 폴더 이름) 중
16개 잡힘. "Supervisor 선언 parse_int 제거"는 처음 시험의 4001자리가 Python 3.12 정수 변환 상한(4300) 안이라 살아남았고, 시험을 4400자리로 바꿔(`cd4db59`) 그 변이가 잡히는 것을 확인했다
(/usr/bin/python3 3.9에는 상한이 없어 이 변이는 3.12에서만 드러난다).

#### 재현 스크립트 재실행(수정본 `4c55c81` git archive 복사본, 사본 스크립트만 고침)

- `r4_numbers_probe.py`(원본 그대로): 명령 10쌍 모두 등록(사용자 결정: 글자 그대로), 거대 지수 enqueue 등록, graph 두 선언 모두 등록, Supervisor RUNNING·정상 선언 등록(I2 해결).
- `r4_code_sha_probe.py`: A 빈 커밋 뒤 같은 실험 → DUP·executor 0회(I4 해결, tree 같음 True). B(추적 안 하는 스크립트 등록)는 이제 등록 단계에서 ContractError라 원래 지점(실행)에 닿지 않아,
  사본에 B2(등록 때 파일 없음 → 등록 뒤 추적하지 않는 `new_exp.py` 생성)를 더했다: 실행 직전 결정적 실패·executor 0회. A2 amend·같은 tree 새 이력 → DUP. C(표시 전 등록 + skip-worktree) →
  executor 0회·결정적 실패, C2(표시 뒤 등록: skip-worktree·assume-unchanged) → ContractError(I5 해결). D 같은 크기·mtime 되돌림 → 결정적 실패, E 사용자 GIT_DIR·GIT_WORK_TREE → ContractError,
  F 링크 source_root 등록·하위 폴더 거절, G 등록 뒤 커밋 → 결정적 실패(모두 r4와 같음).
- `r4_session_jobfile_probe.py`(원본 그대로): 2) 빈 AUTO_RESUME claude 1회·resume 0. 3) 상한 대기 파일 변형 10종(`[]`·모르는 status·crash_resumes 삭제·null·status done·failed·stale·new·
  crash_resumes true·session_id 숫자) 모두 변형 뒤 claude 추가 0회·최종 blocked(I6 해결: r4에서는 done·failed·stale·new가 새 세션 1회).
- `r4_declared_mismatch.py`(원본 그대로, PYTHONPATH에 r3 폴더): 기본·`big` 모두 RUNNING·독립 작업 완료. `big`의 거대 지수 선언은 이제 숫자 단계가 아니라 원래 공격 지점(입력 SHA 대조)까지 가서
  그 선언만 거절된다(거절 3건·알림 3번, I2 해결).
- `r4_pending_kill.py`(사본: 두 번째 runner 뒤 잔여물 확인 항목 추가): 복사 중 kill -9 → `.out-pending-*` 75 MB와 `harness-exec-<키>-*` 남음, complete.json 없음, INTERRUPTED. 두 번째 runner는
  await_result(실행 0)이면서 잠금을 잡은 뒤 두 잔여물을 지웠다(I9 해결, 남은 것 0).

#### 구조(함수 수·호출 깊이)

harness 함수 정의 수 전→후(`df6b78b` 기준): `dedupe` 6→6(`_number` → `json_number`), `sandbox` 4→5(`sweep`), `queue` 6→6, `contract` 5→5, `jsonio` 2→2, `supervisor` 4→4, `claude_job` 6→6, `graph` 4→4.
새 시험: `code_tree` 5, `output_limits` 5. 고친 시험: `dedupe_numbers` 4→7(+λ2), `job_state` 4→5, `sandbox_deny` 3+λ4 그대로, `dedupe_keys` 7, `dedupe_conditions` 6. 7 초과 시험 파일은 기존 것뿐.
최대 호출 깊이 4, 초과 0(`structure_measure.py`). 새·바뀐 경로: `supervisor.run → graph.register_missing → dedupe.find_duplicate → verify_code`(3)·`→ logical_key → _command`(4), `queue.enqueue → find_duplicate → verify_code`(2),
`runner.main → drain → queue.claim → sandbox.sweep`(3). `json_number`는 json 콜백(정적 미집계, 말단).

#### 검사 결과

- 전체 시험(`PYTHONDONTWRITEBYTECODE=1 <python> -m unittest discover -s tests -p "test_harness_*.py"`, 공용 잠금 안, git archive 복사본): `d53ed63` 작업 트리 418개 OK(두 Python),
  `ded8e03` OK(두 Python), `4c55c81` 426개 OK·종료 코드 0(.venv 3.12, /usr/bin/python3 3.9).
- `cd4db59`(시험 한 줄 변경)은 `test_harness_dedupe_numbers` 모듈만 두 Python으로 OK. 이 문서 커밋은 문서만 바꿨다.
- `git diff --check df6b78b`: 문제 없음.
- **미완료**: 최종 HEAD(`cd4db59`·이 문서 커밋) 기준 전체 시험 재실행은 하지 않았다(사용자 체크포인트 지시 2026-11-28: 새 작업 보류, 새로 시작하지 않음). r4 재현 스크립트 5종은 위대로 `4c55c81`에서 실행했다.

#### 남는 한계(판별 불가·fail-closed로 둔 것 포함)

- I1·I3(사용자 결정에 따른 한계): 명령 토큰은 자료형을 알 수 없어 `1e3`과 `1000`, `0.10`과 `0.1`, `+5`와 `5`를 다르게 본다. 같은 실험이 명령 안 숫자 표기만 바꿔 다시 등록·실행될 수 있다
  (같은 실험인지 확정할 수 없다). **운영 안내: 수치 파라미터(학습률·에폭·임계값 등)는 command가 아니라 run_conditions.config로 넘겨라. config는 JSON 자료형이 있어 같은 값이면 중복으로 판정된다.**
  config에서도 int 1과 float 1.0은 다르다(실행 코드가 둘을 같게 써도 다른 실험으로 등록될 수 있다). config 정수는 4000자리, 선언 파일 정수도 4000자리까지만 받는다.
- I4: 다른 등록 계약의 커밋을 source_root 저장소에서 찾지 못하면(다른 저장소에서 등록, gc로 사라진 커밋) 그 계약과는 비교하지 않는다(같은 실험이 다시 등록될 수 있다). 대조는 여전히 커밋 SHA라
  등록과 실행 사이에 문서 커밋이 하나라도 생기면 그 작업은 실행 직전 결정적 실패이고, 같은 tree로 다시 등록하면 그 실패 작업의 중복으로 거절된다(사람이 실패 작업을 정리해야 다시 돈다: 중복 실행보다
  거절 쪽, 지시대로 대조는 HEAD).
- I5: command 토큰이 이름으로 가리키는 파일만 본다. 폴더 토큰 안 파일, 스크립트가 import하는 추적하지 않는 모듈, 하위 모듈의 `ignore=all` 설정은 보지 않는다. 상대 토큰은 source_root 기준으로 본다
  (executor의 실제 cwd와 다를 수 있다). sparse-checkout(skip-worktree 사용)을 쓰는 저장소는 실험·학습·평가가 모두 거절된다(fail-closed).
- I6: 사람 해제는 상태 파일 삭제뿐이다. 같은 사용자 프로세스가 rate_limited·crash_resumes를 함께 고쳐 쓰는 것은 막지 못한다(자동 재개 목록이 비어 있어 지금은 대기로 떨어진다).
- I7: mach-lookup은 이름 조회만 거절한다. 이미 가진 포트(bootstrap 포트 자체, 상속 포트)로 보내는 요청과 허용 이름(opendirectoryd libinfo) 요청은 막지 않는다(메시지 전송 시험은 하지 않았다).
  GPU(Metal)·키체인·DNS·cfprefsd 등 mach 서비스가 필요한 executor(실제 학습 라이브러리 일부 가능)는 sandbox 안에서 실패한다. 허용 목록을 넓히려면 사용자 결정이 필요하다(fail-closed로 둠).
- I9: 정리는 그 작업의 claim에서만 한다(이전 주인이 죽었다고 판정한 뒤). 다시 claim되지 않는 작업(VERIFIED 뒤 등)의 잔여물과 시스템 임시 폴더 위치가 바뀐 경우(TMPDIR 다름)는 남는다.
  합계 상한 4 GiB는 임시값이다(코드 상수, 명령행 설정 없음).
- 기존 한계 유지: 3차 절의 H3(인자 순서 등)·H7·H11, setsid 자손, Claude out/ staging 아님, 실환경 미검증(Supervisor → 실제 claude → 큐 반영, 실제 한도 거절 이벤트, 무인 재개, A 옵션 효과).

#### 롤백

- 전체: `git revert <이 문서 커밋> cd4db59 4c55c81 1b611f3 4c2995f ded8e03 d53ed63`(역순) 또는 `git reset --hard df6b78b`(이 브랜치만, push 전).
- 운영 상태 형식 변화: 실험 논리 키의 코드 자리가 커밋 → tree(되돌리면 이전 키로 다시 계산될 뿐, 저장 형식 변화 없음), 실행 폴더 이름 `harness-exec-<task_key>-*`, sweep이 claim 때 잔여물 삭제,
  config 1/1.0·명령 숫자 표기 키 변화(같은 계약이 이전 코드와 다른 키를 가질 수 있음). 실운영 root는 아직 없다.
