task_id: harness-vs2-experiment-20261128
owner: Claude
status: ready_for_review (합성 검증까지, 실제 ./experiment 연결 미완료)
base_sha: ab9bf2d
branch: claude/harness-vs2-experiment-20261128
goal: VS2(실험 실행 연결) — (1) experiment_exec(B5-8 어댑터)를 실제 진입점의 executor 표로 쓸 수 있게 등록, (2) B5-4 실행 시작 시 실험 예산 차감(runner.drain, 키 = 논리 실험 키)과 실행되지 않음이 확인된 경우의 취소.
decisions: artifacts/harness-resume-20261127/decisions-b5-b6-20261128.md B5 결정 1·3(원문)
not_touched: harness/supervisor.py(VS6 담당), 자동 재개 목록·재실행 안전 목록(빈 상태 유지), sandbox 쓰기·네트워크 허용 범위

# 상태 구분

- 구현·합성 검증 완료: 예산 차감·취소(runner.drain), cancel 장부 이벤트, experiment_exec executor 표 등록, 어댑터 종류·상태의 sandbox 전달.
- 연결(C): 실제 진입점 `python -m harness.supervisor` 1회차(합성 root, 가짜 experiment, 실제 sandbox-exec)에서 등록한 어댑터가 불리고 예산 장부·작업 장부에 결과가 남는 것을 확인했다(아래 C 증거). 실환경·활성화는 주장하지 않는다.
- **실제 ./experiment 연결: 미완료.** sandbox가 원본 저장소 쓰기를 막아 실험 기록(record.json)을 남기는 실행은 진입점에서 결과 불명이 된다. 완료 기록 해석은 sandbox 없는 drain(같은 runner 코드) 합성 시험으로만 확인했다(아래 "사용자 확인 필요" 1).
- 합성 시험 통과는 실제 실험 실행·다음 가설 생성 검증이 아니고 자율 루프 완료가 아니다. 모델 정확도(누락·오탐) 변화 없음.

# 커밋

| 커밋 | 내용 | 바꾼 파일 | 함수 수(전→후, lambda 포함) |
|---|---|---|---|
| 69dc729 | cancel 이벤트, 취소 대조, 취소된 차감은 멱등 근거 아님, charge 결과 seq, 꼬리 맞춤 | harness/budget.py, tests/test_harness_b5_budget_cancel.py(새), tests/test_harness_b5_budget_cancel_abuse.py(새) | budget 4→5, 새 시험 5·6 |
| 15d8f01 | runner 차감·취소 연결, executor 표 등록, 어댑터 종류·상태 전달, not_started 폴더 목록 확인 | harness/runner.py, experiment_exec.py, recovery.py, sandbox.py, sandbox_child.py, tests/test_harness_b5_experiment_run.py(새), tests/test_harness_b5_experiment_run_faults.py(새), tests/test_harness_b5_experiment_exec.py, tests/test_harness_exec_boundary.py | runner 6→6, experiment_exec 3→5, recovery 7→7, sandbox 5→5, sandbox_child 2→2, 새 시험 7·4 |
| d8f91a5 | bool 차감 번호 위조 취소 줄 시험(변이 B11 보강) | tests/test_harness_b5_budget_cancel_abuse.py | 6→6 |
| (이 문서) | 인계 | docs/collaboration/tasks/harness-vs2-experiment-20261128.md | — |

# 동작(결정 3 대응)

- 차감 시점·키: 실험·학습·평가(dedupe.CONDITION_TYPES) 작업을 claim한 뒤, adopt(완료 표시 반영만)가 아니면 executor 직전에 `budget.charge(root, "experiment", 1, now, key=dedupe.logical_key(task))`. 확인과 기록은 charge 한 번(예산 잠금 안)이라 "확인과 차감이 일관"된다. 정지 상태도 charge가 같은 잠금 안에서 다시 본다(Supervisor의 `_live` 확인과 runner claim 사이에 건 정지도 실험은 막는다).
- 중복 차감 없음: 같은 논리 실험의 재개(사람이 결과 확인 대기를 푼 뒤 이어 실행, 체크포인트 재개, 한도 뒤 재개, 인프라 장애 뒤)는 같은 키라 `already`. 실험은 기존 정책상 자동 재시도·재실행되지 않는다(await_result). 키는 커밋 SHA 기준 논리 키(trees 없이)다: 코드가 같은 새 커밋은 다른 키가 되어 다시 차감될 수 있다(보수적 방향, 중복 등록은 dedupe가 tree 기준으로 막는다).
- 거절: 한도(BUDGET_EXCEEDED가 켜짐)·정지 상태면 작업권 파일을 지우고(PENDING) 실행하지 않는다. 요약 `stopped: budget_refused:<사유>`. 예산 장부·운영 상태 손상(BudgetError·OpStateError·LedgerError)은 사용량을 모르므로 실행하지 않고 종료 코드 3(무결성) → Supervisor가 INTEGRITY_HALT.
- 취소: **이번 시도가 새로 한 차감(charge가 돌려준 seq)만**, 결정적 실패이면서 상태가 실행 안 됨일 때만 `budget.cancel`. 실행 안 됨 = executor를 부르기 전 대조·사본 실패(runner가 not_started로 표시), 어댑터 not_started(안내문 + 기록 줄 없음 + **실행 전후 실험 폴더 목록이 같음**), 어댑터 refused(계약 거절, 실험 프로세스를 띄우기 전). 결과 불명(interrupted: 기록 불일치·안내문 없는 1·시간 초과·신호·새 폴더가 생긴 안내문)·실험 실패(failed)·출력 불일치는 차감 유지. 재개 시도(`already`)의 not_started는 앞선 시도의 차감을 취소하지 않는다.
- 취소는 실패 기록보다 먼저 한다. 취소 실패는 경고만 남기고 차감 유지(보수적).
- cancel 장부 규칙(budget.py): 앞선 줄의 같은 (kind, key, period, amount) 차감을 가리키고, 같은 차감을 두 번 되돌리지 않아야 한다. 아니면 위조·손상으로 BudgetError(모든 차감 거절). 되돌리는 기간은 그 차감의 주다(다음 주에 지난주 차감을 취소해도 이번 주 한도는 그대로). 취소된 차감은 key 멱등 근거가 아니다(같은 키를 다시 시작하면 새로 차감). 같은 차감의 두 번째 cancel 호출은 `already`.
- 꼬리 맞춤(새 보호 분기): charge·cancel이 "꼬리 기록 전에 죽은 한 줄"을 인정할 때 꼬리 파일을 그 줄로 맞춘다. 없으면 (가) 차감 직후 kill → 재시작 `already` → 취소 직후 kill이 두 줄 차이가 되어 예산이 잠기고, (나) 꼬리 없는 그 줄을 지워 사용량을 되돌릴 수 있었다.
- 어댑터 등록: `harness.experiment_exec:EXECUTORS = {"experiment": execute}`. execute의 workdir은 runner가 대조한 source_root(runner가 환경변수 `HARNESS_SOURCE_ROOT`에 넣고 sandbox 자식이 물려받는다). 없으면 refused.
- 종류·상태 전달: recovery.kind_of가 ExperimentError의 종류(deterministic|interrupted)를 따른다. sandbox_child 결과 줄에 status를 싣고 sandbox.run_one이 `ChildError.status`로 넘긴다. 자식이 알린 interrupted도 받는다(executor가 스스로 신호로 죽어 얻던 종류라 권한이 넓어지지 않는다. 실험은 재실행 안전 목록에 없어 결과 확인 대기). sandbox 쓰기·실행·네트워크 허용 범위는 바꾸지 않았다.

# 구조(AST, tests/harness_depth_kit.py)

- runner.main 4(`main → drain → budget.cancel → ledger.verify → _check_line`, charge도 같은 4), budget.charge·cancel 2, experiment_exec.execute 3, recovery.kind_of 0. harness 정적 그래프 전체에서 깊이 4 초과 0개.
- 정적으로 확정할 수 없는 경로(동적 호출): runner._execute → executor(표의 함수). 운영 경로는 sandbox 자식 프로세스(`sandbox_child.main → execute → run → interpret → cas.sha_file` = 4)라 runner 깊이에 합산되지 않는다. sandbox 없이 drain에 dict를 넘기는 시험 경로는 같은 프로세스에서 이어진다(`main → drain → _execute → execute → run → interpret → sha_file` = 6, 시험 전용 경로).

# 시험

- 새 시험(합성): test_harness_b5_budget_cancel(4), test_harness_b5_budget_cancel_abuse(3: 위조·중복 취소 줄 10종, 실제 SIGKILL 차감 직후·취소 직전·취소 직후, 꼬리 맞춘 뒤 줄 삭제 탐지, 반쯤 쓴 취소 줄, 6프로세스 동시 취소 → 한 줄, 8프로세스 동시 차감 → 한도 안), test_harness_b5_experiment_run(4: 완료 실험 1회 차감·키, 실행 안 됨만 취소·실패/결과 불명 유지·대조 실패 취소, 한도·사용자 중단·깨진 상태·반쯤 쓴 장부 줄에서 실행 안 함, 등록·깊이), test_harness_b5_experiment_run_faults(3: 재시도 중복 차감·취소 없음, 실제 SIGKILL 차감 직후·취소 직전·직후 뒤 재시작으로 우회 불가와 사람이 대기를 푼 뒤 이어 실행 `already`, 실제 진입점 sandbox 1회차).
- 기존 시험 변경(완화 아님): test_harness_b5_experiment_exec의 가짜 experiment가 호출 기록 쓰기 실패(sandbox 안)를 무시하고, 모드 `setup_after_folder`(새 실험 폴더 뒤 안내문 → 결과 불명)를 추가. test_harness_exec_boundary의 입력 사본 시험 한 개에서 깨진 상태 표식 파일 `supervisor/opstate.json("ORIG")`을 지운다: runner가 이제 실험 전에 운영 상태를 읽고 깨진 상태(INTEGRITY_HALT)면 실험을 시작하지 않기 때문이다(그 거절 자체는 새 시험이 본다). 기대값은 바꾸지 않았다.
- 개발 중 관련 모듈 45개(173개 시험) 3.12 통과(위 exec_boundary 1개 실패를 고친 뒤).
- 전체 시험(대상 d8f91a5, full-suite.lock 아래 순차, `python -m unittest discover -s tests -p "test_harness_*.py"`): Python 3.12(.venv) 491개 OK, Python 3.9(/usr/bin/python3) 491개 OK. 기존 477 + 새 14.

# 변이 시험(scratchpad 복사본, 원본 미수정)

스크립트: scratchpad `vs2-mut/mutate.py`(HEAD 복사본에 변이 하나씩, 새 시험 6개 모듈 실행). 결과 `vs2-mut/run.log`.

| 묶음 | 변이 | 결과 |
|---|---|---|
| budget | B1 같은 차감 두 번 취소 허용, B2 기간 대조 제거, B3 금액 대조 제거, B4 모르는 이벤트 허용, B5 already가 취소를 무시, B6 현재 주로 취소, B7 꼬리 맞춤 제거, B8 cancel 잠금 제거, B9 다른 키 취소 허용, B10 합계가 취소 무시, B11 bool·문자열 차감 번호 허용 | 처음 10/11(B11 생존: False == 0 위조 시험 없음) → bool 번호 위조 시험 추가(d8f91a5) 뒤 11/11 |
| runner | R1 차감 제거, R2 키를 task_key로, R3 거절 무시, R5 모든 결정적 실패에서 취소, R6 대조 실패를 취소 안 함, R9 예산 손상을 무결성 정지 대신 건너뜀, R10 거절 때 작업권 파일 남김, R12 결과 불명도 취소 | 8/8 |
| 어댑터·전달 | E1 실험 폴더 목록 확인 제거, E2 status 항상 None, E3 workdir를 cwd로, S1 자식 interrupted 거절(옛 동작), S2 자식이 status를 안 실음, K1 kind_of가 어댑터 종류 무시 | 6/6 |

시험하지 않은 변이: R8 adopt에서도 차감(같은 키라 already, 무해), 차감을 executor 뒤로 옮기기·취소를 실패 기록 뒤로 옮기기(문자열 치환으로 만들기 어려워 하지 않음. 앞쪽은 실행 안 함·거절 시험, 뒤쪽은 kill 시험이 간접으로 본다).

# C 증거 (연결, 합성 root, 대상 15d8f01)

명령(두 합성 root, 각 1회차): `python -m harness.supervisor --root <root> --executors harness.experiment_exec:EXECUTORS --source-root <가짜 experiment를 커밋한 임시 git 원본> --max-cycles 1 --poll 0`, cwd=저장소, 실제 sandbox-exec. 원본 기록: scratchpad `vs2-c-evidence/c-evidence.json`.

- 가짜 모드 busy(잠금 사용 중 안내문, 종료 1, 실행 안 함): 종료 코드 0. 작업 장부 `claimed` → `failed`(kind deterministic, error `ExperimentError: ('deterministic', {'status': 'not_started', 'return_code': 1, ...})`) → `python_drain`(summary failed). 예산 장부 seq 0 `charge`(kind experiment, key = 논리 키 e3f357d0…, period week:2026-W48) → seq 1 `cancel`(charge_seq 0, reason not_started). 작업 FAILED.
- 가짜 모드 completed(기록을 쓰려 함): sandbox가 원본 저장소 쓰기를 막아 원본에 artifacts/가 생기지 않았다 → 어댑터 결과 불명(interrupted) → 작업권을 남겨 INTERRUPTED. 예산 장부 seq 0 `charge`만(차감 유지). 작업 장부는 `claimed`까지(아래 한계 3).
- 같은 내용을 tests/test_harness_b5_experiment_run_faults의 진입점 시험이 고정한다.

# 한계·리스크

1. 실제 ./experiment는 sandbox 안에서 workspace.lock·artifacts/experiments 쓰기가 막힌다. 그 경우 ./experiment가 잠금 단계 OSError로 2 안내문을 내고 실험 폴더가 생기지 않으면 not_started(취소)가 된다(실제로 실행 안 됨). 실험 폴더를 만든 뒤의 오류는 결과 불명(차감 유지).
2. not_started 판정은 ./experiment가 내는 안내문과 실험 폴더 목록에 기대며, 실험 명령(자식)이 안내문을 출력하고 부모 ./experiment를 이상 종료시키는 경우 같은 극단은 결과 불명으로 떨어지는지 시험하지 않았다. 같은 시각 다른 실험이 폴더를 지우는 경우는 확인 불가(그 경우만 오판 가능).
3. Supervisor는 runner가 실행 0건으로 끝나면 `python_drain`을 장부에 남기지 않는다(supervisor._python, 기존 동작). 그래서 결과 불명 실험의 첫 회차 사유(어댑터 상태 unknown)는 장부에 없고 작업권 기록만 남는다(다음 claim이 `awaiting_result`를 남긴다). supervisor.py는 VS6 담당이라 고치지 않았다. 필요한 변경: `_python`의 기록 조건에 `summary.get("stopped")`가 비지 않은 경우를 더한다(한 줄).
4. 예산 장부 손상 시 runner가 종료 코드 3을 내므로 Supervisor 전체가 INTEGRITY_HALT(Claude 작업 포함)로 멈춘다(사용량을 모르는 상태에서 아무것도 시작하지 않는 fail-closed). 대기 중 실험이 없으면 손상이 있어도 정지하지 않는다.
5. 학습·평가 작업도 실험 예산 1건으로 센다(dedupe.CONDITION_TYPES 전체, pre-b5 단계 4 안. AGENTS의 "새 학습·성능 실험은 ./experiment로"를 근거로 한 기본값). 학습·평가 executor는 아직 없다.
6. refused(계약 거절)도 취소 대상에 넣었다(실험 프로세스를 띄우기 전이라 객관적 미실행). 지시문의 "어댑터의 not_started"보다 한 가지 넓다.
7. runner가 `os.environ["HARNESS_SOURCE_ROOT"]`를 바꾼다(실행 중 프로세스 환경 변경, sandbox 자식 전달용). executor 표 이름(spec)은 Supervisor 인자라 신뢰 설정이며, 표에서 experiment 이름에 등록한 executor가 status not_started를 내면 runner는 그대로 취소한다.
8. adopt 경로는 차감하지 않는다(변이 R8: 시험 없음, 같은 키라 차감해도 already로 무해).
9. 실험 결과 불명·취소 직전 kill 등에서 실제로는 실행되지 않은 실험의 차감이 남을 수 있다(예산 누수, 우회 아님). 자동 환불 없음(사람 확인).

# 미검증

- 실제 ./experiment·학습·평가·모델·네트워크 호출(실행하지 않음), 실제 workspace.lock·./develop 잠금과의 직렬화, launchd 상시 실행, 전원 장애 수준 부분 쓰기, 수일에 걸친 주 경계.
- 다음 가설 생성(ANALYZE 입력 development_handoff.json)까지의 연결(사용자 결정 1: 최종 완료 조건).

# 사용자 확인 필요

1. **진입점에서 완료 기록 해석을 보이려면 sandbox 밖 실행 경로 또는 sandbox 허용 확대가 필요하다(구현하지 않고 멈춤).** 선택지:
   - (가) 첫 실험 후보 승인 때 sandbox 밖 실험 전용 신뢰 실행기(어댑터 고정 경로 `<저장소>/experiment`, 쓰기 = artifacts/experiments·workspace.lock·작업 staging). b5-indep 문서의 최소 권한 초안과 같다. 권장(실제 연결과 같이 검토).
   - (나) sandbox 프로필에 실험 작업만 `<source_root>/artifacts/experiments`와 `artifacts/development-cycle/workspace.lock` 쓰기 허용 추가(sandbox 완화라 결정 필요, 저장소 쓰기 경계가 넓어진다).
   - (다) 어댑터가 sandbox 안 임시 폴더에 원본을 git clone해 그 안에서 실행(sandbox 유지). 실제 ./experiment는 추적하지 않는 .venv·자료가 필요해 쓸 수 없어 가짜 전용 경로가 된다(비권장).
   - (라) 현 상태 유지: 진입점 C는 실행 안 됨·결과 불명까지, 완료 해석은 sandbox 없는 drain 합성 시험으로만.
2. 위 한계 5(학습·평가도 실험 1건)·6(refused 취소)의 기본값이 맞는지.
3. 한계 3의 supervisor.py 한 줄 변경을 VS6가 반영할지.

# 롤백

`git revert d8f91a5 15d8f01 69dc729`(역순). 15d8f01만 되돌리면 runner는 예산을 쓰지 않고 cancel 이벤트는 쓰이지 않는다. 69dc729를 되돌리면 이미 cancel 줄이 있는 합성 장부는 옛 _tally가 cancel 줄의 amount를 차감으로 더한다(합성 root에만 있으며 운영 장부에는 없다).
