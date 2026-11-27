# 하네스 3단계 — Supervisor·한도 재개 (2026-11-27)

```text
task_id: harness-stage3-supervisor-20261127
owner: Claude (메인 세션이 배정, 구현은 Opus 하위 에이전트)
status: implementing
base_sha: 5705371 (1·2·6·7단계와 route()를 통합한 브랜치의 merge 커밋, 전체 SHA는 인계 절)
branch: claude/harness-supervisor-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 3행의 완료 기준 중 합성 신호로 시험할 수 있는 것
  (프로세스 재시작, resetsAt 뒤 재개, --resume 실패 시 새 세션, 시각 미상 시 3회 후 정지,
  USER_STOPPED 재개 안 함, 상태 우선순위)을 가짜 claude 실행 파일(실제 하위 프로세스)로 통과한다.
  실제 단기 한도 1회 시험·구독 로그인 인증·실제 rate_limit_event 형태 확인은 이번 범위 밖(미검증으로 인계).
allowed_files:
  - harness/supervisor.py, harness/opstate.py, harness/ratelimit.py, harness/claude_run.py,
    harness/budget.py, harness/unlock.py (모두 신규)
  - 함수 수 제한 때문에 추가하는 harness/ 아래 신규 파일: harness/claude_job.py
    (Claude 작업 칸: 고르기·실행·결과 반영. 추가 시 이 목록에 기록)
  - harness/launchd/*.plist.template (템플릿 파일만, 설치·로드하지 않음)
  - tests/test_harness_supervisor_*.py (신규)
  - 이 task 문서
forbidden_files: 1단계(queue·states·recovery·lease·holder·ledger·cas·manifest·checkpoint·graph·contract·jsonio)·
  2단계(runner)·route*·routing_policy.json·Champion(champion·pointer·registry·gate·lineage·promotion*)·scoring* 파일,
  5단계 파일(harness/active_learning*·silver*·audit*), card_condition/**, tools/**, 다른 tests/**, AGENTS.md, docs/agent/**,
  artifacts/**, data/**, .claude/**, 다른 plan 문서, 라벨·사진·모델·비밀 설정
contract:
  호출만 하는 기존 공개 함수: runner(`python -m harness.runner`, 종료 코드 3), graph.register_missing,
    queue.claim/complete/fail, states.facts/state_of, lease.lock/stamp/release/read/boot_id/pid_alive, holder.verdict,
    ledger.append/verify, jsonio.read_json/write_json, route.route/load_policy/probe_cli_support/with_support/record_decision.
  보존: 1·2·6·7단계와 route 시험 177개 통과, 기존 파일 무수정.
  제약: stdlib만. 실제 `claude` 실행·모델 호출·네트워크·푸시·텔레그램·launchd 설치·시스템 설정 변경 없음.
    `--continue`·`/low-priority`·`/rate-limit-options`는 쓰지 않는다. 런타임 상태는 호출자가 준 root 아래에만.
  설계에 없는 기능 금지: 자율 루프 템플릿(4단계), 능동 학습(5단계), Gold 훅(8단계), 라우팅 정책 변경.
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩·lambda 포함), 공개 진입 함수 호출 깊이 ≤4
  (1·2단계·route 호출까지 합산, ast로 재측정). 구현 후 인계 절에 파일별 표를 채운다. 모두 신규 파일이라 변경 전 함수 수는 0.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 /Users/.../.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0
    (3.12와 /usr/bin/python3 3.9 둘 다, 기존 177개 포함)
  - 변이 시험(임시 복사본, 원본 수정 금지): 상태 우선순위 반전, 해제 경로 자동화, 3회 한도 제거, resetsAt 이전 재개,
    재시작 상태 손실, 종료 코드 3 미승격, 예산 한도 무시, --continue 사용, T7 통과 주장 → 시험이 잡는지
  - ast 함수 수·호출 깊이, `git diff --check`, `git diff --name-only <base> HEAD`가 허용 파일 안, git status 깨끗
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: 아래 "인계" 절(구현 후 작성)
```

## 구현 명세 (배정 프롬프트 A~G 요약, 설계에 있는 것만)

| 항목 | 내용 | 설계 근거 |
|---|---|---|
| A 운영 상태 `opstate` | INTEGRITY_HALT > USER_STOPPED > DONE > BUDGET_EXCEEDED > RATE_LIMITED_SHORT/WEEKLY(/미상) > RUNNING. 여러 조건이 함께 있으면 가장 높은 것이 유효 상태. 원자 저장(임시 파일+fsync+os.replace), 전이마다 ledger 기록. 위 네 상태는 자동 해제 금지(사용자 해제 함수만, Supervisor 루프에 호출 경로 없음). runner 종료 코드 3 → INTEGRITY_HALT | DESIGN 12절 |
| B 한도 `ratelimit`·`claude_run` | stream-json 줄 단위 JSON에서 `rate_limit_event`·`resetsAt`/`resetsAtSeconds` 파싱(초·밀리초·ISO 허용, 해석 불가 None). 단기/주간은 이벤트 필드로, 구분 불가면 '미상'. 재개는 저장 시각 이후 `--resume <id>`, 실패하면 장부 상태로 새 세션. 시각 미상이면 60·300·900초 간격 최대 3회 후 정지·`notifications.jsonl` 기록. `--continue`(약 4시간 제한)는 상수·문서로만 적고 쓰지 않는다. 한도 중 Python 작업은 runner로 계속 | DESIGN 12·13절, EVIDENCE 6·7절 |
| C 모델·Effort | route()(정책 v1)로 정한 값을 `--model`·`--effort`로 넘기고, 요청값·init 이벤트 관찰값(없으면 미확인)·제한 사항을 route_record로 장부에 남긴다. T7은 통과 주장 금지(verified=false) | DESIGN 14절, model-routing-design 1-4·2절 |
| D 예산 `budget` | 주당 실험 20건·비전 호출 300구역·봉인 교체 주기당 승격 2건(D-2). 추가 전용 장부, 주 경계는 호출자가 준 시각, 초과 시 BUDGET_EXCEEDED(자동 재개 금지) | DECISIONS D-2, DESIGN 12절 |
| E 정지 해제 `unlock` | too_many_interrupts·holder_alive_without_lock으로 멈춘 작업을 사람/Supervisor 확인 뒤 푸는 명시적 함수. 사유·실행자·시각을 장부에. 자동 호출 경로 없음 | 1·2단계 인계 "3단계 몫" |
| F Supervisor 루프 | 상태 확인 → register_missing → Python drain → 한도면 재개 시각까지 대기(sleep·시계 주입) → 재개. 파일 상태만으로 재시작 이어짐. launchd는 템플릿만 | DESIGN 3·9·12절 |

## 인계

(구현 후 작성)
