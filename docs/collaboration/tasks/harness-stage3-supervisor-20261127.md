# 하네스 3단계 — Supervisor·한도 재개 (2026-11-27)

```text
task_id: harness-stage3-supervisor-20261127
owner: Claude (메인 세션이 배정, 구현은 Opus 하위 에이전트)
status: ready_for_review
base_sha: 5705371a5078a83d010160a67cce2016a6e1153f (1·2·6·7단계와 route()를 통합한 브랜치의 merge 커밋)
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
handoff: 아래 "인계" 절. 최종 시험 대상 SHA 46eb92d99e3802c45fc521f7dfc3b986b5f0a375, 문서 커밋은 그 위
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

### 결과

배정 명세 A~F를 구현했고 필수 시험을 합성 신호(가짜 claude 실행 파일 = 실제 하위 프로세스, 모델 호출 없음)로 실행해 통과했다.
**실제 `claude -p` 실행·실제 한도 1회 시험·구독 로그인 인증은 하지 않았다(범위 밖, 아래 미검증).** T7은 통과로 주장하지 않는다.
하네스 동작의 시험이며 모델 정확도 근거가 아니다.

### 커밋

| 종류 | 전체 SHA | 내용 |
|---|---|---|
| docs | `b62d18d0a305d34cf9c52226c32393d7d5f0027f` | 작업 계약 |
| feat | `ae5a3a1fac8531914e7ded9f15ef75411b5c0610` | harness/{supervisor,opstate,ratelimit,claude_run,claude_job,budget,unlock}.py, harness/launchd/harness-supervisor.plist.template |
| **test(최종 시험 대상)** | `46eb92d99e3802c45fc521f7dfc3b986b5f0a375` | tests/test_harness_supervisor_{kit,opstate,ratelimit,resume,procs,contracts,budget,unlock}.py (33개) |
| docs | 이 문서 커밋(그 위) | 인계 |

### 실행한 검사 (cwd=worktree, 대상 46eb92d)

| 명령 | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py" > 파일 2>&1; echo rc=$?` (3.12) | rc=0, 210개 통과(기존 177 + 신규 33) |
| 같은 명령, `/usr/bin/python3` (3.9.6) | rc=0, 210개 통과 |
| 신규 33개를 `-W error::ResourceWarning`으로 (3.12) | rc=0 |
| 시작 전 기준선(5705371, 3.12) | rc=0, 177개 |
| `git diff --cached --check` (각 커밋 직전) | 0 |
| 변이 시험(임시 복사본, 원본 무수정, scratchpad `s3/mutate3.py`) | 28종 모두 잡음(1차 27/28: M3b "간격을 늘리지 않음"을 놓쳐 시험의 기대 간격을 모듈 상수 대신 (60, 300, 900)으로 고정한 뒤 잡음. M17 "원자 저장 대신 직접 쓰기"는 1차 변이가 다른 이유로 실패해 폴더를 만드는 변이로 다시 확인) |

변이 목록(모두 해당 시험 실패 확인): 우선순위 반전·USER_STOPPED/DONE 순서 교환, Supervisor의 USER_STOPPED 자동 해제·clear_auto가 정지 상태 해제·unlock 자동 import, 3회 한도 제거·간격 고정, resetsAt 이전 재개, 재시작 시 claude.json 무시·opstate를 프로세스별 파일로·실행 전 세션 ID 미저장·고아 claude 확인 제거, 종료 코드 3 미승격, 예산 한도 +1·정지 중 charge 허용, `--continue` 추가, verified=True·t7 제한 사항 누락, `--resume` 실패 시 새 세션 안 엶, 미상 종류를 단기로, 시간대 없는 ISO·상대 초 수용, 한도 중 Python 멈춤, 정지 상태에서 Python drain, 해제 장부 누락·confirm 불필요, 원자 저장 대신 직접 쓰기, 전이 장부 누락.

### 필수 시험 대응

| 요구 | 시험 |
|---|---|
| rate_limit_event(+2초 resetsAt) → 대기 후 `--resume` | resume `test_known_reset_waits_then_resumes_same_session`(재개 실행 시각 ≥ resetsAt, 같은 세션 ID) |
| `--resume` 실패 → 새 세션 | resume `test_resume_failure_opens_new_session_from_ledger_state` |
| resetsAt 해석 불가 → 60·300·900초 3회 뒤 정지·알림 | resume `test_unknown_reset_backs_off_three_times_then_stops_and_notifies`(가짜 시계, 실행 4회, exhausted, notifications.jsonl, clear_auto 거절) |
| USER_STOPPED면 한도가 지나도 재개 안 됨 | resume `test_user_stopped_blocks_resume_after_reset_passes`(사용자 해제 뒤에만 재개) |
| 상태 우선순위 모든 쌍 | opstate `test_priority_every_pair_both_orders_and_exclusive_limits`(36조합) |
| kill -9 뒤 재시작해 이어감 | procs `test_kill9_while_waiting_then_restart_resumes`, `test_kill9_during_claude_run_does_not_double_run` |
| 한도 중 Python 작업 계속 | resume `test_python_tasks_continue_while_rate_limited` |
| 예산 초과 BUDGET_EXCEEDED·자동 재개 금지 | budget 6개(20·300·2, 주 경계, 재승인 경로, 동시 charge, 장부 변조), opstate `test_supervisor_starts_nothing_in_halting_states` |
| runner 종료 코드 3 → INTEGRITY_HALT | procs `test_runner_exit3_becomes_integrity_halt` |
| 정지 해제 함수와 장부 기록 | unlock 4개(자동 호출 경로 없음을 ast로 확인 포함) |
| route 결정 장부 기록, T7 통과 주장 안 함 | contracts `test_route_decision_recorded_without_claiming_t7` |
| `--continue` 안 씀 | ratelimit `test_argv_has_no_continue_and_refuses_forbidden_commands`, `test_forbidden_strings_only_in_guard_constants`, resume 시험의 실제 argv 대조 |

### 구조 (ast 재측정, scratchpad `s3/depth3.py`: 모듈 경계를 넘어 합산, `functools.partial`·`(a or b)(...)`·주입 콜백 `probe_cli_support → help_text`도 호출로 셈)

모두 신규 파일이라 변경 전 함수 수는 0이다. 함수 수는 일반 함수·메서드·중첩 함수 합계이며 lambda는 0개다.

| 파일 | 함수 수 | 공개 진입 함수 깊이(최대 경로) |
|---|---|---|
| supervisor.py | 3 | run 4 (run → claude_job.execute → route.route → route._base → route._choose; run → execute → claude_run.run_once → ratelimit.scan → _lookup; run → settle → queue.claim → states.facts → lease.read) |
| opstate.py | 7 | set_condition 2, notify 2, clear_auto 3, clear_by_user 3, load 1, effective 0 |
| ratelimit.py | 4 | scan 1, parse_reset 0, classify_kind 0 |
| claude_run.py | 4 | run_once 2, default_runner 1, build_argv 0, help_text 0(주입 runner는 동적) |
| claude_job.py | 4 | execute 3, settle 3, pick 2 |
| budget.py | 3 | charge 4 (charge → usage → ledger.verify → _check_line → _hash_entry), usage 3, period_of 0 |
| unlock.py | 4 | release_interrupts 2, release_holder 2 |

- `supervisor.run`의 Python drain은 `python -m harness.runner`를 **별도 프로세스**로 실행하므로 호출 깊이에 넣지 않았다(종료 코드와 마지막 줄 JSON만 읽음). executor의 강제 종료가 Supervisor를 죽이지 않게 하려는 선택이기도 하다.
- `python -m harness.supervisor`의 모듈 맨 아래 `__main__` 블록은 `_args`(말단)와 `run`만 부른다(함수가 아니라 깊이 시작점에서 제외).
- 동적 경로: `claude_run.run_once`가 부르는 runner는 주입값이다. 운영 기본값은 `functools.partial(default_runner, pidfile=…)`(→ write_json)이라 run 기준 깊이 4이고, 시험은 runner를 주입하지 않고 실제 기본 경로를 쓴다. `help_text`는 runner가 없으면 subprocess.run을 직접 써서 깊이를 늘리지 않는다.
- 시험 파일: 함수 정의 ≤7(setUp·도우미 포함), 테스트 ≤7(6·3·6·3·6·5·4).

### 공개 API (4단계 이후 호출자용)

- `supervisor.run(root, claude_bin=None, executors=None, max_cycles=None, poll_s=60, now_fn, sleep_fn, runner=None, env=None)` → 요약. root당 하나만(이미 돌면 `{"already_running": True}`, 명령행 종료 코드 4).
- `opstate.load/effective/set_condition(root, name, now, actor, reason, extra)/clear_auto(한도만)/clear_by_user(actor="user")/notify`.
  상태 파일 `root/supervisor/opstate.json`, 알림 `root/supervisor/notifications.jsonl`(추가 전용 해시 체인).
- `budget.charge(root, kind, amount, now, seal_cycle=None, actor)`·`usage`·`period_of`. kind: experiment|vision_zone|promotion. 장부 `root/supervisor/budget.jsonl`.
- `unlock.release_interrupts(root, key, actor, reason, now, confirm=True)`, `unlock.release_holder(...)`. actor: user|supervisor.
- Claude 작업 칸 상태 `root/supervisor/claude.json`, 실행 중 claude pid `root/supervisor/claude.pid`, 의존 그래프 선언 `root/supervisor/declared.json`({task_key: 계약}, 4단계가 쓴다고 가정).
- 장부 이벤트(root/ledger.jsonl): opstate_transition, claude_job_picked, claude_run_started, route_decision, claude_resume_failed, claude_job_finished, claude_job_closed, python_drain(실행이 있었거나 비정상일 때만), unlock_too_many_interrupts, unlock_holder_alive.

### 가정 (설계에 값이 없어 정한 것, 검토 대상)

1. **RATE_LIMITED_UNKNOWN 상태를 추가**했다(DESIGN 12절 표에는 SHORT/WEEKLY만). 배정 명세 B의 "구분 불가면 SHORT로 두지 말고 미상"을 기록하기 위해서이며 SHORT/WEEKLY와 같은 우선순위·같은 처리(Claude만 멈춤, 재개 시각 뒤 자동 재개)다. 한도 조건은 한 번에 하나만 둔다(새 한도가 앞의 것을 대체).
2. 단기/주간 구분: `rateLimitType`(또는 `rate_limit_type`) 값 `five_hour` → 단기, `seven_day`·`seven_day_opus`·`seven_day_sonnet` → 주간, 그 밖·없음 → 미상. 실제 값 이름은 확인하지 않았다.
3. 한도 판정: status가 `rejected`이면 한도. status가 `allowed`·`allowed_warning`이면 한도가 아니다(실패면 일반 실패). status가 없으면 이벤트가 있고 실행이 성공하지 않았을 때만 한도. 성공 = 종료 코드 0 + `type=result`이고 `is_error`가 true가 아님.
4. 재개 시각: 1e11 초과 숫자는 밀리초, 2001-09-09(1e9) 이전·시간대 없는 ISO·bool·무한대·NaN은 None. `resetsAtSeconds`도 절대 epoch로만 해석한다(상대 초일 가능성은 추정하지 않고 작은 값은 None). 해석된 시각이 이미 지났으면 미상과 같이 간격 재시도로 처리한다(뜨거운 반복 방지).
5. 시각 미상 재시도: 처음 한도 뒤 60·300·900초에 한 번씩(모두 3회) 다시 시도하고, 3번째 재시도도 미상 한도면 `exhausted=true`로 멈추고 알림. 시도 횟수는 작업(claude.json) 단위로 누적한다. 사용자가 그 한도 조건을 `clear_by_user`로 풀어도 횟수는 초기화되지 않아, 다시 미상 한도면 곧바로 멈춘다.
6. `--verbose`를 붙인다(-p + stream-json 조합에 필요할 수 있음. 이 설치본에서 필요 여부 미확인). 새 세션은 `--session-id <uuid4>`로 시작해 실행 전에 세션 ID를 저장한다.
7. Claude 실행이 한도가 아닌 이유로 실패하면(새 세션 기준) 큐 작업을 `deterministic`으로 fail한다(자동 재시도 없음). claude 출력만으로 네트워크 장애(일시적)와 작업 실패를 구분할 근거가 없어 보수적으로 정했다. `--resume` 실패는 한 번만 새 세션으로 이어간다.
8. LLM 큐 작업은 Claude가 일하는 동안 작업권을 쥐지 않고 PENDING으로 둔다(한도 대기가 실패·중단 횟수로 세이지 않게). 끝나면 claim → complete/fail. Supervisor가 root당 하나라는 것(supervisor.lock)이 이중 실행 방지의 전제다.
9. 실행 중 Supervisor가 죽으면: `claude.pid`의 pid가 같은 부팅에서 살아 있는 동안 기다리고, 죽었으면 저장한 세션 ID로 `--resume`한다. pid 재사용 시 불필요하게 기다릴 수 있다(정지 방향의 오류).
10. 예상하지 못한 예외는 INTEGRITY_HALT로 멈춘다(fail-closed, 사람 확인). 일시적 디스크 오류도 정지시킬 수 있다.
11. 주 경계는 UTC ISO 주(월요일 00:00 UTC = 한국 시각 월요일 09:00). 예산 charge는 정지 상태(네 가지)에서 모두 거절하며, Supervisor 루프는 charge를 부르지 않는다(실험 시작·비전 작업을 만드는 4·5단계가 부른다).
12. Claude 프롬프트는 계약 파일·산출물 폴더·장부 경로를 알리는 고정 문구다(4단계 Skills가 대체할 자리). route()의 history는 빈 목록으로 넘긴다(상향은 4단계 실패 정책 몫).
13. 정지 해제: too_many_interrupts는 작업권 기록의 interrupts만 0으로 다시 쓰고(pid·부팅·시작 시각·run_id 유지) 정지 표식을 history/unlock-NNN.json에 보관한다. holder_alive_without_lock은 주인이 지금도 "alive"일 때만 기록을 보관하고 지운다. ps 판정 불가(blocked)는 해제 대상에 넣지 않았다(배정 명세에 없음).

### 미검증 (이번 범위 밖 또는 확인하지 못함)

- 실제 `claude -p --output-format stream-json`의 `rate_limit_event` 형태·필드 이름·`resetsAt` 단위·발생 시점(EVIDENCE 7절 1번). 가짜 claude는 위 가정의 형태를 흉내낼 뿐이다.
- LaunchAgent에서 실행한 `claude -p`의 구독 로그인(키체인) 인증(7절 2번), 재부팅·로그아웃 뒤 동작(12번). launchd 템플릿은 plist 형식만 시험했고 설치·로드하지 않았다.
- 실제 단기 한도 1회 시험(IMPLEMENTATION 2절 3행), 주간 한도(T4), `--resume` 실제 실패 조건과 `--session-id` 실제 동작(7절 6번), `--continue` 4시간 제한(쓰지 않으므로 시험 안 함).
- T7: init 이벤트에 effort가 있는지, 별칭(sonnet)과 init의 전체 모델 이름 대응. 장부에는 verified=false와 제한 사항만 남긴다.
- 한도 중 앱 푸시(T6). 알림은 notifications.jsonl 기록뿐이다.
- 1단계 인계의 "정책 필드만 바꿔 새 task_key로 우회 등록" 차단, DESIGN 8절의 Supervisor 자동 Champion 복원: 배정 명세(A~G)에 없어 하지 않았다.

### 리스크

- Claude 실행은 동기다: 긴 Claude 세션 동안에는 Python drain이 그 회차가 끝날 때까지 기다린다(한도 대기 중에는 계속 돈다). claude 실행에 시간 제한이 없어 멈춘 claude는 Supervisor를 붙잡는다.
- 한도 판정 규칙(가정 3)이 실제 출력과 다르면 정상 실행을 한도로 보거나 한도를 일반 실패로 처리해 큐 작업을 fail할 수 있다. 실제 출력 확인 전에는 운영에 쓰지 않는 것을 권한다.
- 실행 오류(예: claude 없음)도 deterministic fail이라 자동 재시도가 없다.

### 롤백

통합 전: 이 브랜치를 통합하지 않으면 된다. 통합 뒤: `git revert`로 문서·시험·구현 커밋(위 표의 SHA)을 되돌린다. 기존 파일은 수정하지 않았고 런타임 상태는 호출자가 준 root 아래 `supervisor/`에만 생기므로 그 폴더를 지우면 상태도 원래대로다(장부의 기록 줄은 남는다). launchd는 설치하지 않았으므로 되돌릴 시스템 설정이 없다.
