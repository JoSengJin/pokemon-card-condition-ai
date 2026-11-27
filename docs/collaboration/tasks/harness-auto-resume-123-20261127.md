# 하네스 자동 재개 정책 B 1~3단계 (2026-11-27)

```text
task_id: harness-auto-resume-123-20261127
owner: Claude (메인 세션 배정, 구현은 Opus 하위 에이전트)
status: assigned
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
