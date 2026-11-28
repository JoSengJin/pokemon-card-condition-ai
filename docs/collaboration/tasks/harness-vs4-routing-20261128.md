task_id: harness-vs4-routing-20261128
owner: Claude
status: ready_for_review (합성 검증까지. 운영 경로에서 라우팅 이력은 아직 비어 있다: 아래 "사용자 확인 필요" 1)
base_sha: 1760219
branch: claude/harness-vs4-routing-20261128
goal: VS4 — (1) claude_job의 route 이력 연결(B5-6)과 pending·이력 오류 대기, (2) needs_vision 작업의 Claude 실행 직전 비전 구역 예산 차감(B5-5), (3) 진입점 C 증거에 필요한 검사 유형 3개 등록.
decisions: artifacts/harness-resume-20261127/decisions-b5-b6-20261128.md "B5-5·B5-6 결정"(원문)
not_touched: harness/runner.py·supervisor.py·route.py·route_escalate.py·routing_policy.json·claude_perm.py(RUNNABLE=("A",) 유지), 자동 재개·재실행 안전 목록(빈 상태 유지)

# 상태 구분

- 구현·합성 검증 완료: 위 (1)·(2)·(3).
- 연결(C): 실제 진입점 `python -m harness.supervisor`(합성 root, 가짜 claude)에서 이력 읽기 → 상향·대기, 비전 차감·한도 거절이 장부에 남는 것을 확인했다. **검사 작업의 완료만은 합성**이다(아래 한계 1).
- 검사 실행기, 비전 묶음(B) 실행, PLAN_GATE, 새 사용량 지표는 만들지 않았다. 실환경·활성화는 주장하지 않는다. 실제 claude·모델·네트워크·./experiment 실행 없음.
- 합성 시험 통과는 실제 Claude 실행 성공이나 카드 상태분석 모델의 누락·오탐 감소 근거가 아니다. 정확도 변화 없음.

# 커밋

| 커밋 | 내용 | 바꾼 파일 |
|---|---|---|
| 1995514 | 이력 연결 + pending·이력 오류는 그 작업만 대기 + 검사 유형 등록 | harness/claude_job.py, dedupe.py, route_history.py(설명만), tests/test_harness_vs4_route.py(새) |
| d82a8f3 | 비전 구역 차감 연결 | harness/claude_job.py, logical_zones.py·budget.py(설명만), tests/test_harness_vs4_vision.py·vision_faults.py(새) |
| (이 문서) | 인계 | docs/collaboration/tasks/harness-vs4-routing-20261128.md |

# 구조(AST, tests/harness_depth_kit.py)

- 함수 수(전→후, lambda 포함): claude_job 6→6, dedupe 6→6, route_history 2→2, logical_zones 2→2, budget 5→5. 새 시험 파일 6·7·3.
- 깊이: claude_job.execute 3→3, supervisor.run 4→4(`run → execute → budget.charge → ledger.verify → _check_line`). history 2, charge 2. harness 정적 그래프에서 4 초과 0개. count_logical_zones의 json 콜백(_unique_keys)과 executor 표는 정적 도구가 세지 않는다(전자는 execute 기준 2).

# 동작

- 순서: 완료 표시 반영(adopt) → 권한 묶음 → 자동 재개 확인·상한 → 이력·route → (pending이면 대기) → 입력 복사 → 구역 수 → [회차마다] 정지 확인 → 선언 삭제 → **비전 차감** → 작업 상태 running 저장 → claude 실행.
- 이력 오류 → 그 작업만 대기(`route_history_invalid`). pending → route_decision 한 줄(applied=null, 실행 안 함) + 대기(`route_pending`). pending이면 claude --help 확인도 하지 않는다. 해제는 기존 한 가지(사람이 작업 상태 파일 삭제)이며 지워도 이력이 같으면 다시 대기한다.
- 차감: key=task_key, 취소 없음(budget.cancel은 부르지 않는다). 재개·새 세션·사람 해제 뒤 재실행은 already.
  - 차감 전에 멈추는 경로(adopt, 권한 없음, 자동 재개 꺼짐·상한, 이력 오류, pending, 모델 없음, 입력 거절, 셀 수 없음, 정지, 선언 삭제 실패)는 차감하지 않는다(모델 없음은 시험 없음, 코드 순서).
  - 셀 수 없음 → 그 작업만 대기(`logical_zone_uncountable`).
  - 한도 거절(`limit`) → 그 작업만 대기(`vision_budget_refused`). BUDGET_EXCEEDED는 기존 budget 정책대로 전체 정지. 상태를 그대로 두면 사람이 정지를 풀 때마다 같은 작업을 먼저 골라 다시 전체를 멈추므로 대기로 정했다(담당 기본값, 확인 필요 3).
  - 정지 확인과 차감 사이에 걸린 정지(`halted:*`) → 작업 상태를 바꾸지 않고 halted.
  - 예산 장부 손상 → 예외 → INTEGRITY_HALT, 실행 안 함(VS2 실험 예산과 같은 방향).

# 시험

- 새 시험 9개(route 4, vision 2, vision_faults 3). 기존 시험은 바꾸거나 지우지 않았다.
- 수정 전 실패 확인: (a) 검사 유형 등록 거절 3건 실패, (b) 이력 `[]`에서 네 시도가 모두 sonnet/medium, (c) **이력만 연결하고 pending 대기가 없는 상태에서 4번째 시도가 opus/high로 실행**, (d) 비전 연결 전 차감 줄 0.
- 장애: 실제 SIGKILL 3지점(차감 전 / 장부·꼬리 기록 뒤 반환 전 / running 저장 뒤 claude 시작 전) 뒤 재시작에서 차감 1줄·claude 1회. 셋째 지점은 기존 규칙대로 pid_record_mismatch 대기 → 사람 해제 뒤 already. 차감 중간(장부 줄 뒤·꼬리 전) kill은 기존 B5-5 장부 시험이 본다.
- 개발 중 관련 모듈 9개 묶음 42개 시험 3.12 통과(1단계 커밋 전).
- 전체 시험(대상 d82a8f3, full-suite.lock 아래 순차, `python -m unittest discover -s tests -p "test_harness_*.py"`): Python 3.12(.venv) 505개 OK, Python 3.9(/usr/bin/python3) 505개 OK. 기존 496 + 새 9. 시험 뒤 잠금 해제 확인.

# 변이 시험(scratchpad 복사본, 원본 미수정)

`<SP>/vs4-mut/mutate.py`, 결과 `<SP>/vs4-mut/run.log`. 19/19 잡힘, 변이 없는 대조는 통과.
R1 이력 비움, R2 pending 대기 제거, R3 이력 오류 처리 제거, R4 이력 오류를 빈 이력으로, R5 pending 기록 제거, R6 pending 기록에 applied 주장, R7 검사 유형 미등록, V1 차감 제거, V2 호출마다 다른 키, V3 거절 무시, V4 한도 거절을 halted로, V5 경합 정지를 대기로, V6 running 저장 뒤 차감, V7 선언 삭제 전 차감, V8 needs_vision 무시, V9 셀 수 없으면 1구역, V10 셀 수 없음 처리 제거, V11 장부 손상 무시, V12 항상 1구역.

# C 증거 (연결, 합성 root, 대상 d82a8f3)

원본 기록: `<SP>/vs4-c-evidence/c-evidence.log`(수집 스크립트 collect.py, SP는 세션 scratchpad라 지워질 수 있다. 같은 내용을 새 시험이 고정한다).
SP=/private/tmp/claude-501/-Users-jueun--claude-spares-spare-gwvY5k/2447cc31-6b92-45b7-8b4a-bf072e0567dc/scratchpad

1. 라우팅: `python -m harness.supervisor --root R --claude-bin <가짜> --max-cycles 1 --poll 0`을 10번. 검사 작업 완료는 사이에서 합성.
   ```
   seq=2  claude_run_started sonnet/medium  ddd051d8a561 (시도 1)
   seq=13 claude_run_started sonnet/high    057af814f41d (시도 2)
   seq=24 claude_run_started opus/high      a8bbe0bf15f1 (시도 3)
   seq=36 route_decision pending=true applied=null requested opus/high escalations=2  7277fbb49751 (시도 4)
   seq=37 claude_job_finished blocked "route_pending: 최상위 모델로도 미해결: Pending 처리(사용자 요청 안 함)"
   seq=39 claude_run_started haiku/low      87518eebebf9 (같은 검사 작업에 의존한 다른 유형: 계속 실행)
   ```
2. 비전: 같은 진입점 `--max-cycles 4 --source-root S`.
   ```
   supervisor/budget.jsonl seq=0 charge vision_zone amount=3 key=6757c345f387 week:2026-W48
   ledger seq=4 claude_run_started 6757c345f387 → seq=9 done
   ledger seq=11 blocked "no_runnable_permission_bundle: silver_labeling(B)" d25bf06fa291 (차감 줄 없음)
   needs_vision=false 작업 fbf973e3429f 실행, 차감 줄 없음
   ```
3. 한도 거절: 299구역 선차감 뒤 2구역 작업, 1회차.
   ```
   budget.jsonl: 선차감 299 한 줄뿐
   ledger seq=2 opstate_transition set BUDGET_EXCEEDED
   ledger seq=3 claude_job_finished blocked "vision_budget_refused: limit(week:2026-W48, 요청 2, 사용 299/300)"
   claude_run_started 없음
   ```
   (이 회차 stdout의 state는 RUNNING이다: 요약 state는 execute 직전에 읽은 값이다. 기존 동작.)
4. runner 도달 확인(한계 1): 시도 1이 VERIFIED인데 `runner.drain` 요약이 executed=0, untouched.llm_dependents=[검사 작업 fc2a3a9da13f].

# 한계·리스크

1. **진입점에서 검사 작업이 실행될 수 없다(이번에 발견, 고치지 않음).** `runner._scan`은 needs_llm 작업에 직접·간접으로 의존하는 Python 작업을 그 LLM 작업이 VERIFIED여도 실행하지 않는다(2단계 계약 "LLM 작업과 의존 작업은 건드리지 않는다", 기존 시험은 LLM이 PENDING인 경우만 본다). 귀속 규칙상 검사 작업은 반드시 LLM 대상에 의존하므로, 검사 실행기를 만들어도 이력은 생기지 않는다. DESIGN 4절의 ANALYZE(Claude) → PLAN_GATE(결정론) → EXPERIMENT 연쇄(VS3·VS8)도 같은 이유로 막힌다. 실패 방향은 상향 없음(기본 모델)이다.
2. **비전 차감은 실제 비전 작업 유형에서는 도달하지 않는다.** 이미지 유형(B 묶음)은 RUNNABLE 밖이라 차감 전에 대기한다(권한을 넓히지 않았다). 닿는 것은 A 묶음 유형에 needs_vision=true를 선언한 계약뿐이며 지금 그런 작업을 만드는 호출부는 없다. C 증거 2·3은 그런 합성 계약이다.
3. needs_vision은 계약의 자기 선언이다: false로 선언하면 차감하지 않고, A 묶음 작업이 입력 이미지를 읽는 것도 막지 않는다.
4. 논리 구역 수는 실제 AI 사용량이 아니다. 같은 task_key의 재실행은 AI가 다시 봐도 추가 차감이 없다.
5. 차감 뒤 claude가 시작하지 못해도(실행 파일 없음, 상태 저장 실패, running 저장 뒤 사망) 차감은 남는다. 취소를 새 용도로 쓰지 않았다. 같은 task_key의 다음 실행은 추가 차감이 없다. 다시 실행하지 않으면 그 주 한도는 그만큼 줄어든 채다.
6. 한 작업의 301구역 이상, 또는 남은 한도를 넘는 요청은 기존 정책대로 전체 정지(BUDGET_EXCEEDED)를 켠다.
7. 정지 확인과 차감 사이에 걸린 사용자 중단은 비전 작업만 막는다. 그 밖의 작업은 기존의 틈(확인 직후 정지는 그 1개를 못 막음)이 그대로다.
8. B5-6의 기존 한계(의존·task_type·입력을 바꾸면 기본 모델부터, 원인 분리는 검사기의 자기 선언)는 그대로다. 사람이 pending 작업의 상태 파일을 지워도 이력이 같아 다시 대기한다: 진행하려면 사람이 새 계약을 등록해야 한다.
9. RouteHistoryError가 아닌 OSError(의존 작업 파일 권한 등)는 기존처럼 Supervisor의 INTEGRITY_HALT로 간다(pick도 같은 파일을 읽는다).
10. 낡은 설명: tests/test_harness_b5_zone_budget.py·budget_depth.py의 "연결 전" 문구는 시험 파일을 건드리지 않아 남아 있다. 설계 문서는 고치지 않았다.

# 미검증

실제 claude·비전 호출, 실환경의 모델·effort 적용(T7), 검사 executor와 그 판정 근거, sandbox 안에서 검사 executor 실행, launchd 상시 실행, 주 경계에 걸친 실환경 재개, 전원 장애 수준의 부분 쓰기.

# 사용자 확인 필요

1. runner가 **의존하는 LLM 작업이 VERIFIED이면** 그 Python 의존 작업을 실행하게 바꿀지. 최소 변경: `_scan`의 `llm = {k for k, c in contracts.items() if c["needs_llm"] and state[k] != states.VERIFIED}`(요약의 untouched.llm 의미가 바뀌므로 시험 대조 필요). 그러면 Claude 결과 뒤의 검사·PLAN_GATE·실험이 자동 실행된다(실험은 예산 차감 대상). 2단계 계약의 실행 정책 변경이고 이번 배정 범위 밖이라 고치지 않았다. VS3·합성 종단(VS8)의 선행 조건이다. 권장: VS3 담당 범위에 넣어 함께 검증.
2. 비전 차감의 실제 도달은 B 묶음 실행 허용(미승인)이 필요하다.
3. 한도 거절을 "그 작업 대기(사람이 상태 파일 삭제로 해제)"로 둔 기본값. 대안은 작업 상태를 유지해 정지 해제 뒤 자동으로 다시 시도(같은 작업이 계속 전체를 멈출 수 있다).

# 롤백

`git revert d82a8f3 1995514`(역순). d82a8f3만 되돌리면 비전 차감이 사라지고 합성 장부의 vision_zone 줄은 합계에만 남는다. 1995514를 되돌리면 이력이 다시 `[]`가 되고 검사 유형 등록이 거절된다(이미 등록한 검사 계약은 합성 root에만 있다).
