# 하네스 1단계 — 큐·상태·장부 (2026-11-27)

```text
task_id: harness-stage1-queue-state-ledger-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet High 하위 에이전트, 독립 검증은 Opus 하위 에이전트)
status: ready_for_review
base_sha: c480d890bce6788d0f4342e35555044f4ed73925 (D-1~D-3 기록 커밋 c6530db이 그 위에 있음)
branch: claude/harness-stage1-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 1단계 완료 기준을 실제 시험으로 통과한다.
  (a) 5개 상태(VERIFIED·RUNNING·INTERRUPTED·FAILED·CORRUPT)가 DESIGN 9절대로 처리됨
  (b) 같은 작업을 동시에 claim하면 한쪽만 RUNNING이 됨
  (c) 빠진 작업이 의존 그래프 대조로 자동 등록됨
  (d) 장부 한 줄 변조·삭제·순서 변경이 감지됨
allowed_files:
  - harness/__init__.py, harness/contract.py, harness/cas.py, harness/lease.py,
    harness/ledger.py, harness/states.py, harness/queue.py, harness/graph.py
  - (구현 중 함수 수 제한 때문에 추가한 파일) harness/jsonio.py, harness/manifest.py,
    harness/checkpoint.py, harness/recovery.py, tests/test_harness_support.py(시험 공용 도구),
    tests/test_harness_claim_churn.py, test_harness_paths.py, test_harness_state_guards.py(독립 검증 반영으로 추가)
  - (재검증 반영으로 추가) harness/holder.py, tests/test_harness_claim_holder.py
  - tests/test_harness_*.py (신규만)
  - 이 task 문서
forbidden_files: card_condition/**, tools/**, 기존 tests/**, AGENTS.md, artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**
contract:
  입력: 작업 계약(dict) — task_type, inputs(경로·SHA), outputs(상대 경로 목록), depends_on(task_key 목록),
        needs_llm, needs_vision, risk, retry_policy, escalation_level, expected_minutes(선택)
  출력: 런타임 상태는 호출자가 준 root 아래에만 쓴다(기본값 없음, 테스트는 임시 디렉터리).
  보존할 조건: 외부 의존성 없음(stdlib만, Python 3.9+ 문법). 네트워크·LLM·`claude` 실행 없음.
  기존 `./develop` 잠금·`./experiment`·card_condition 모듈을 import하거나 바꾸지 않는다.
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩 포함), 호출 깊이 ≤4(전이 수). 구현 후 아래 표를 채운다.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0
    (`-t .`는 `tests/`에 `__init__.py`가 없어 ImportError이므로 쓰지 않는다)
  - 아래 "필수 시험" 전부 포함
  - `git diff --check`, 허용 파일 대조, 파일별 함수 수·호출 경로 표
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: 아래 "구조 표 / 인계" 절(독립 검증 1·2차 반영 포함). 최종 시험 대상 SHA는 그 절의 표.
```

## 설계 근거(원문)

- DESIGN.md 9절 상태표·멱등성·누락 방지·잠금·장부, 14절 작업 계약 필드, 12절 상태 우선순위(이 단계 범위 밖).
- 설계에 없는 기능을 넣지 않는다. Supervisor·한도·훅·Gold·평가기·레지스트리·Silver는 후속 단계다.

## 구현 명세

모든 경로·시각·pid 조회는 주입 가능하게 만든다(시험에서 합성 상황을 만들기 위해). 저장은 임시 파일 + `os.replace` 원자 교체.

1. `contract.py` — `task_key(contract)`(정규화한 입력 JSON의 sha256), `new_run_id()`, `validate_contract(contract)`(필수 필드·타입, 알 수 없는 필드 거절).
2. `cas.py` — 내용 주소 저장소: `put(root, path) -> sha256`, `get(root, sha, dest)`, `has`. CORRUPT 복구에만 쓴다.
3. `lease.py` — 작업권: `acquire(path, pid, boot_id)`는 `fcntl.flock(LOCK_EX|LOCK_NB)`로 한 쪽만 성공, 내용에 pid·부팅 식별자·획득 시각 기록. `is_alive(lease)`는 pid 생존(`os.kill(pid,0)`)과 부팅 식별자 일치로 판정. 부팅 식별자 조회 함수는 주입 가능(기본은 `sysctl -n kern.boottime` 파싱, 실패 시 명시적 오류, 추정 금지).
4. `ledger.py` — 해시 체인 JSONL: 각 줄 `{seq, prev, ts, event, data, hash}`, `hash = sha256(prev + canonical(seq,ts,event,data))`. `append`는 flock 아래 직전 줄 해시를 읽어 잇는다. `verify(path, expected_tail=None)`은 줄 변조·삭제·중복·순서 변경·prev 불일치를 위치(seq)와 함께 보고하고, `expected_tail`(외부 복제한 마지막 해시)이 주어지면 꼬리 잘림도 감지한다. `tail()`로 끝 해시를 내보낸다. 실패·중단 기록은 덮어쓰지 않는다(추가만).
5. `states.py` — 상태 상수 5개와 `classify(task_dir, now, is_alive)`: 
   - 완료 기록(`done.json`)이 있고 출력 manifest의 모든 해시가 일치 → VERIFIED, 하나라도 불일치·삭제 → CORRUPT
   - 작업권 파일 존재: 생존 → RUNNING, 사망 → INTERRUPTED
   - 실패 기록 → FAILED(`failure_kind`: transient|deterministic, `attempts`)
   - 입력 해시가 같다는 것만으로 VERIFIED로 보지 않는다(출력 해시 검증 필수).
6. `queue.py` — `enqueue`, `claim(root, task_key)`(상태에 따라 실행 가능 여부·run_id 부여, 동시 claim은 한쪽만 성공), `complete(...)`(출력 manifest 해시 기록 후 `done.json`, CAS에 출력 보관), `fail(..., kind)`, `recover(root, task_key, now)`:
   - VERIFIED: 재실행 안 함 / CORRUPT: CAS에서 복구 시도, 성공하면 검증 후 VERIFIED 유지, 실패하면 재실행 대상(새 run_id)
   - INTERRUPTED: 실행 시간 ≥30분이고 유효한 체크포인트(코드 SHA·자료 SHA·seed·난수·옵티마이저·데이터 순서 일치)가 있으면 `resumed=true`, 아니면 새 run_id 재실행
   - FAILED: transient는 최대 2회 재시도, deterministic(코드 오류·기준 미달)은 재시도 없이 `needs_failure_policy`로 표시
   - 모든 전이는 장부에 기록
7. `graph.py` — `reconcile(declared_tasks, state_of)`: 선언된 의존 그래프에서 의존 작업이 모두 VERIFIED이고 자신은 VERIFIED·RUNNING·대기 중이 아닌 작업을 반환/등록한다. 순환 의존은 오류로 거절한다.

함수 수 제한 때문에 파일을 더 쪼갤 수 있다(예: `manifest.py`, `checkpoint.py`). 새 파일은 allowed_files에 추가하고 이 문서에 기록한다.

## 필수 시험 (IMPLEMENTATION 2절 1단계)

시험 파일당 테스트 ≤7개로 나눈다(`tests/test_harness_*.py`).

| 시험 | 방법 | 기대 |
|---|---|---|
| T-kill | 하위 프로세스가 claim 후 `kill -9` → recover | RUNNING → INTERRUPTED(작업권 사망), 새 run_id 또는 체크포인트 복원 |
| T-live | 살아 있는 프로세스의 작업권 | RUNNING 유지, 두 번째 claim 거절 |
| T-race | 여러 프로세스가 동시에 같은 task_key claim | 정확히 1개만 성공 |
| T-delete | 완료 뒤 산출물 삭제 | CORRUPT → CAS 복구 → VERIFIED |
| T-tamper | 산출물 한 바이트 변조(CAS도 손상된 경우 포함) | CORRUPT, 복구 불가 시 재실행 대상 |
| T-transient | `ConnectionError` 주입(네트워크 차단 모사) | FAILED(transient), 최대 2회 재시도 후 정지 |
| T-code | `TypeError` 등 코드 오류 주입 | FAILED(deterministic), 재시도 없음 |
| T-30min | 29분/31분 중단 + 체크포인트 일치·불일치 | 31분+일치만 `resumed=true`, 나머지 새 run_id |
| T-dep | 의존 작업은 VERIFIED, 자신은 미등록인 상태로 시작 | reconcile이 등록, 순환 의존은 오류 |
| T-ledger | 줄 변조 / 중간 삭제 / 순서 바꿈 / 꼬리 잘림(`expected_tail`) | 모두 위치와 함께 감지 |
| T-same-hash | 입력 해시 동일하지만 출력 없음 | VERIFIED 아님(건너뛰지 않음) |

## 구조 표 / 인계

### 결과

필수 시험 11종을 모두 실제로 실행해 통과했다(아래 대응표). 합성 시험이며 모델 성능·정확도 근거가 아니다. 이번 변경은 개발 진척 단계 1(큐·상태·장부)의 구현이며 실험·학습·외부 AI 호출은 없다.

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 1차 구현 / 1차 시험 | `e6da279a8f5396c44d722d41a5bf8830f1d55a90` / `19f343da2439bc81357e056cb8ce32294e87ec99` (독립 검증 전, 38개) |
| 독립 검증 반영 구현 (`fix(harness)`) | `014174c` (전체 SHA는 `git log`; 아래 표의 시험 대상 SHA의 조상) |
| 1차 검증 반영 시험 대상 | `9fc60f839874b38c450c7419f20c3a85929e9fbe` (51개) |
| 2차 검증 반영 구현 (`fix(harness)`) | `bc9624a436ada03f755a3b210e42fc7d52ec50f2` |
| **최종 시험 대상(2차 반영 구현 + 시험)** | `82870bd43ab704a21d1bf20cdceab6b81f15852b` (`test(harness)` 커밋, 55개) |
| 이 문서 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음). SHA는 커밋 후 `git log`로 확인 |

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14) | 0 (55개 통과, 연속 3회·`-W error::ResourceWarning` 포함 모두 통과) |
| `/usr/bin/python3 ... 같은 명령` (Python 3.9.6, 호환 확인) | 0 (55개 통과) |
| 검증자 적대 스크립트 `adv.py`·`race.py` (읽기·실행만, 저장소에 복사 안 함) | adv 항목 1·2·4a·4b·5a·6·7·10 해소 확인(아래 표), race16×200: 승 72·겹침 0·장부 문제 0, 장부 16×50 800줄 정상 |
| `git diff --check` (커밋 직전) | 0 |
| 지시 원 명령 `... -s tests -p "test_harness_*.py" -t .` | **실패**(ImportError: `tests/`에 `__init__.py`가 없음, 저장소 기존 상태). `-t .`를 뺀 명령을 쓴다. 시험은 `from tests.test_harness_support import ...`(cwd 기준 네임스페이스 패키지)로 공용 도구를 읽는다. |

시험에는 변이 확인도 했다(저장소에 남기지 않음). 1차: 잠금을 공유 잠금으로 바꾸기, 재개 임계값 0, 재시도 한도 +5, VERIFIED 무조건 반환, 장부 prev 검사 끄기, 일시적 실패 판정 뒤집기, 체크포인트 지문 비교 끄기 — 각각 1~6개 시험 실패.
독립 검증 반영 뒤: 검증자 `mutate.py`를 scratchpad에 복사해(원본 수정 안 함; M3의 대상 문자열이 코드 변경으로 달라져 M3만 새 코드에 맞게 고침) M1~M14와 추가 M15~M22를 돌렸다. M1(링크 파일 검사 제거)·M2(lease samestat 제거)·M3(실패 기록을 작업권보다 먼저 판정)·M15~M17·M19~M22를 포함해 모든 변이가 시험 실패로 잡혔다. 한 번은 M18(done 비객체 허용)이 살아남았으나 중복 코드라 제거했고, M19·M20은 처음엔 살아남아 시험(다른 필드 변조, 실제 부팅 식별자로 기록한 산 pid)을 보강해 잡히게 했다. M2는 반복 claim 경합 시험이 6회 연속 겹침(49~106건)으로 잡는다.

### 필수 시험 대응

| 필수 | 시험 (파일 :: 이름) |
|---|---|
| T-kill | claim_processes :: test_kill9_makes_interrupted_then_new_run_id, test_kill9_after_30_minutes_with_matching_checkpoint_resumes_same_run (실제 subprocess + SIGKILL) |
| T-live | claim_processes :: test_live_process_keeps_running_and_second_claim_is_refused (실제 subprocess) |
| T-race | claim_processes :: test_race_exactly_one_of_many_processes_gets_running (실제 8개 subprocess 동시 출발, 승자 1·`locked` 7, 장부 `claimed` 1줄, 장부 검증 통과) |
| T-delete | recovery :: test_delete_after_complete_is_restored_from_cas_and_verified |
| T-tamper | recovery :: test_tampered_byte_is_restored_but_damaged_cas_forces_rerun (CAS 손상 포함), states :: test_corrupt_when_outputs_deleted_changed_or_done_record_damaged |
| T-transient | recovery :: test_transient_failure_retries_at_most_twice_then_stops (1회+재시도 2회=실패 기록 3건 뒤 정지) |
| T-code | recovery :: test_code_error_is_deterministic_and_never_retried |
| T-30min | recovery :: test_30_minute_threshold_and_checkpoint_fingerprint_decide_resume (29분/30분/31분, 지문 6개 항목 각각 불일치, 체크포인트·현재 지문 없음) |
| T-dep | graph :: test_verified_dependency_registers_the_missing_task_once, test_circular_dependencies_are_rejected 외 |
| T-ledger | ledger :: test_line_tamper…, test_middle_deletion_and_reordering…, test_tail_truncation_is_detected_only_with_an_external_tail |
| T-same-hash | states :: test_unregistered_pending_and_same_input_hash_is_not_verified |

### 파일별 함수 정의 수 (ast로 센 값: 일반·클래스 메서드·중첩 함수 포함, lambda 제외, 한도 ≤7)

| 파일 | 수 | 파일 | 수 |
|---|---|---|---|
| harness/cas.py | 5 | tests/test_harness_support.py (시험 아님) | 6 |
| harness/checkpoint.py | 2 | tests/test_harness_contract_cas.py | 6 |
| harness/contract.py | 6 | tests/test_harness_lease.py | 5 |
| harness/graph.py | 3 | tests/test_harness_ledger.py | 7 |
| harness/holder.py | 2 | tests/test_harness_claim_holder.py | 6 (시험 5 + 도우미 1) |
| harness/jsonio.py | 2 | tests/test_harness_states.py | 7 (시험 6 + 도우미 1) |
| harness/lease.py | 7 | tests/test_harness_claim_processes.py | 6 |
| harness/ledger.py | 6 | tests/test_harness_claim_churn.py | 1 |
| harness/manifest.py | 3 | tests/test_harness_recovery.py | 7 |
| harness/queue.py | 7 | tests/test_harness_graph.py | 6 (시험 5 + 도우미 1) |
| harness/recovery.py | 6 | tests/test_harness_paths.py | 4 |
| harness/states.py | 3 | tests/test_harness_state_guards.py | 5 |
| harness/__init__.py | 0 | | |

### 호출 깊이(전이 수, 한도 ≤4)

측정: ast로 이름 참조(호출뿐 아니라 인자로 넘긴 콜백·기본 인자 `is_alive=lease.is_alive`도 간선으로 계산하는 보수적 상한)로 간선을 만들어 공개 진입 함수별 최장 경로를 구했다. 측정 스크립트는 저장소에 두지 않았다(임시 파일). 순환 호출 없음.

| 진입 | 최장 경로 | 전이 수 |
|---|---|---|
| queue.claim | claim → decide → _corrupt → cas.get → sha_file (또는 → holder.verdict → lease.is_alive → _os_alive, → mismatches → sha_file, → decide → _failed → load_contract → read_json, → decide → _interrupted → checkpoint.check → read_json, → classify → load_contract → task_key) | 4 |
| queue.recover | 위 claim과 같은 경로 | 4 |
| graph.register_missing | register_missing → enqueue → _log → ledger.append → _hash_entry | 4 |
| queue.complete | complete → cas.put → has → sha_file / complete → _log → append → _hash_entry / → load_contract → task_key | 3 |
| queue.fail | fail → _log → append → _hash_entry | 3 |
| queue.enqueue | enqueue → _log → append → _hash_entry | 3 |
| ledger.verify | verify → _check_line → _hash_entry | 2 |
| states.classify | classify → load_contract → task_key / → mismatches → sha_file / → is_alive → boot_id | 2 |

공개 진입 함수 시작 기준 최대 4로 한도 이내이다. 단 시험 함수를 시작점으로 세면 시험 → claim(4) 또는 시험 → 도우미 → claim(4)이라 5~6이 된다(시험 쪽은 이번 한도 판정 대상에서 제외했다고 가정, 아래 가정 참조).

### 구조와 명세 대비 차이·추가 파일

- 새 파일(함수 수 제한 때문): `jsonio.py`(원자 저장·읽기), `manifest.py`(출력 manifest), `checkpoint.py`(체크포인트 지문), `recovery.py`(상태별 결정), 시험 공용 `tests/test_harness_support.py`. `queue.recover`는 명세대로 `queue.py`에 있고 결정 로직은 `recovery.py`에 둔다.
- `lease.acquire`는 `lock()`(잠금+이전 기록) → 판단 → `stamp()`(내 기록) 두 단계로 나눴다. 상태 분류·실행 여부 결정을 잠금 안에서 해야 동시 claim이 안전하기 때문이다. 콜백으로 넘기면 호출 깊이를 정적으로 확정할 수 없어 콜백 방식은 택하지 않았다.
- 보조 상태 2개 추가: `PENDING`(큐에 있고 기록 없음, 명세의 "대기 중"), `UNREGISTERED`(큐에 없음). 5개 상태 정의는 그대로다.
- 작업 폴더 구조: `root/ledger.jsonl`, `root/cas/`, `root/tasks/<task_key>/{contract.json, out/, lease.json, done.json, failures/NNN-<run_id>.json, checkpoint.json, history/}`.

### 가정 (명세가 모호해 가장 보수적으로 고른 해석)

(10~11은 독립 검증 반영에서 추가)

1. `task_key`는 계약 전체(expected_minutes만 제외)의 canonical JSON sha256이다. 필드를 바꾸면 새 키가 되어 이미 VERIFIED여도 다시 실행된다(거짓 건너뜀보다 낫다고 봄).
2. `outputs`는 비어 있을 수 없고 안전한 상대 경로여야 한다(출력 해시로만 완료를 인정하기 때문). 산출물은 `tasks/<key>/out/<상대경로>`에 쓴다. 심볼릭 링크 산출물·manifest의 선언 외 키·읽을 수 없는 `done.json`은 모두 CORRUPT다.
3. INTERRUPTED의 "실행 시간"은 `복구 판단 시각(now) - 작업권 획득 시각`이다. 사망 시각을 모르므로 실제 작업 시간보다 길게 잡힐 수 있다. 30분 정확히는 재개 가능(≥30).
4. 체크포인트 복원 조건: 같은 run_id의 체크포인트이고 지문 6개 항목(code_sha·data_sha·seed·rng·optimizer·data_order)이 호출자가 준 `current`와 모두 같음. `current`가 없으면 복원하지 않는다. 재개는 중단된 run_id를 그대로 쓰고 `resumed=true`, 아니면 새 run_id다.
5. 실패 종류: `ConnectionError`·`TimeoutError`·`socket.timeout`만 일시적, 그 밖(코드 오류 포함, 알 수 없는 예외)은 결정적이다. 재시도 한도는 `retry_policy.max_transient_retries`(0~2, 기본 2); 최초 1회 + 재시도 2회 = 실패 기록 3건 뒤 `needs_failure_policy`. 마지막 실패 기록의 종류를 기준으로 한다.
6. INTERRUPTED에서 새 실행(rerun)은 일시적 실패 한도에 세지 않는다(중단은 실패 기록이 아니므로). 반복 중단 한도는 후속 단계(Supervisor·한도)의 몫이다.
7. 빈(또는 공백) 작업권 파일은 "작업권 없음"(잠금만 잡고 기록 전에 죽은 경우)으로, 깨진 JSON은 "죽은 작업권"으로 본다.
8. `reconcile`은 VERIFIED·RUNNING·PENDING이 아니고 의존이 모두 VERIFIED인 작업을 모두 돌려주지만, `register_missing`은 그중 UNREGISTERED만 `enqueue`한다. FAILED·INTERRUPTED·CORRUPT는 이미 큐에 있으므로 등록하지 않고(특히 결정적 실패를 우회 재등록하지 않으려고) claim/recover의 판단에 맡긴다. 선언 키는 계약의 task_key와 같아야 한다. 해시 키는 순환이 불가능하므로 순환 시험은 임의 키 사전으로 reconcile을 직접 호출한다.
9. 장부는 상태 변경 뒤에 기록한다(일어나지 않은 일을 주장하지 않으려고). 비정상 종료 시 장부 줄이 빠질 수 있으며 상태 파일이 정본이다. 호출 깊이 한도는 공개 진입 함수 기준으로 판단했다(시험 함수 시작 기준은 위 표 참조).
10. (1차 반영 4 → 2차 반영 A로 수정) `claim` 안에서 `flock` 획득 성공은 "잠금을 쥔 프로세스가 없다"는 증거일 뿐 "주인 pid가 없다"는 증거는 아니다. 1차에서 이전 기록을 pid 무관하게 죽은 것으로 본 것은 구멍이었다: (a) 대리 pid(감독자가 작업자 pid로 claim한 뒤 감독자만 죽음), (b) exec(같은 pid가 계속 실행되지만 close-on-exec로 잠금 소실)에서 작업자가 살아 있는데 두 번째 claim이 성공했다. 지금 규칙(이중 실행 방지가 멈춤보다 우선): (1) claim의 pid는 `os.getpid()`여야 한다(아니면 QueueError). 작업권을 쥔 프로세스가 끝까지 실행하고 exec하지 않는다는 것이 전제이며 lease.py·queue.py·holder.py docstring에 적었다. (2) 상태가 INTERRUPTED일 때 이전 기록을 `holder.verdict`로 본다: 기록이 없거나 깨짐·부팅 식별자(claim의 `boot` 인자)가 다름·pid 죽음·기록 pid가 호출 프로세스 자신(같은 프로세스가 놓고 간 기록)·좀비(`ps -o stat= -p <pid>`가 Z로 시작)는 인수한다. 같은 부팅에서 살아 있고 좀비가 아니면 `ok=False, reason="holder_alive_without_lock"`으로 멈추고 장부에 사유를 남긴다(사람/Supervisor 확인 대기). `ps` 실패·해석 불가는 `reason="blocked"`(살아 있다고 추정하지도 죽었다고 추정하지도 않음). 관찰자용 `classify`/`recover`는 기존대로 pid·부팅 식별자 판정이다(그래서 좀비·잠금 없이 사는 프로세스는 관찰자에게 RUNNING이다). 정지한 뒤 자동으로 인수하는 경로는 없다.
11. (검증 반영 2) 작업권의 run_id가 마지막 실패 기록의 run_id와 같으면 작업권이 살아 있든 죽었든 FAILED다(그 실행은 이미 실패를 기록했다). 작업권이 없거나 run_id가 다르면 기존 규칙(재시도 실행 중 = RUNNING).

### 독립 검증(Opus) 지적 반영 내역

| 번호 | 조치 | 내용 |
|---|---|---|
| 1 | 수정 | `manifest.safe_path`: out과 중간 폴더가 링크이거나 실제 위치가 out 밖이면 거절. `build`(완료)·`mismatches`(분류)·CAS 복구 쓰기 모두 거친다. 마지막 파일이 링크인 경우는 `islink`로 따로 본다. 시험: `test_harness_paths.py`(링크 폴더·링크 out 완료 거절, 완료 뒤 링크로 바꾸면 CORRUPT, 밖에 복구 쓰기 없음) |
| 2 | 수정 | classify: 작업권 run_id가 마지막 실패 기록 run_id와 같으면 FAILED. 시험: 실제 subprocess가 실패 기록 직후 kill -9(`test_death_right_after_writing_failure_record...`), 재시도 실행 중 RUNNING(`test_harness_state_guards.py`) |
| 3 | 수정 | `test_harness_claim_churn.py`: 12개 프로세스×150회 claim→해제 경합, 작업권을 쥔 동안 O_EXCL 표식으로 겹침 감지. samestat 검사를 끈 변이를 잡는다 |
| 4 | 수정 | claim은 flock을 잡은 뒤 이전 작업권을 pid 생존과 무관하게 죽은 것으로 분류한다(아래 가정 10). 시험: 좀비, 무관한 산 pid(실제 부팅 식별자) |
| 5 | 수정 | 같은 내용 파일을 가리키는 링크 시험(M1 변이를 잡음) |
| 6 | 수정 | 재시도 실행 중 RUNNING 시험(2번과 함께) |
| 7 | 수정 | `done.json`이 존재하나 객체가 아니면(null 등) CORRUPT, 재실행 계획 |
| 8 | 수정 | `states.load_contract`: task_key(계약)==폴더명, outputs 비어 있지 않음, 위반은 CORRUPT. CORRUPT 복구 단계에서 계약이 손상이면 재실행하지 않고 `blocked`로 멈춘다 |
| 9 | 수정 | `contract.check_key`: claim·recover·complete·fail 진입에서 소문자 16진 64자가 아니면 ContractError(`fullmatch`; 끝 개행 거절). 이 때문에 adv.py 3a·3b는 이제 오류를 낸다(의도) |
| 10 | 수정 | failures/에서 `\d{3}-[0-9a-f]+\.json`만 센다. `fail`의 번호 매김도 같은 규칙 |
| 11 | 설계 메모 | 아래 "다음 단계 메모" |
| 12 | 수정 | claim: stamp 뒤 로그 예외 시 작업권을 지우고 해제, 판단 중 예외 시 해제(이전 기록 보존). complete·fail: 로그가 실패해도 finally로 해제 |
| 13 | 수정 | `ledger.py` docstring에 전체 재계산 위조는 expected_tail 복제본 없이는 감지 불가 추가 |
| 14 | 문서만 | 아래 "사용자 결정 대기" |
| 15 | 수정 | checks 문구를 실제 동작 명령으로 |

추가 변경: `contract.canonical`을 없애고 `task_key`에 인라인(호출 깊이 한도 유지), `queue.claim`의 `is_alive` 인자는 이전 호출 형식과 검증자 스크립트 호환을 위해 받되 무시한다.

### 2차 독립 검증 반영 내역 (조건부 통과, 중요 1건)

| 항목 | 조치 | 내용 |
|---|---|---|
| A 이중 실행 회귀 | 수정 | 위 가정 10. 시험 `test_harness_claim_holder.py`: 대리 pid 거절(상태·장부 불변), 실제 subprocess가 claim 후 `os.execv`한 뒤 두 번째 claim이 `holder_alive_without_lock`으로 정지(장부 기록, 관찰자는 RUNNING, 죽은 뒤 인수), 무관한 산 pid 정지·다른 부팅 식별자 인수·죽은 pid 인수, `ps` 결과(좀비/산/판정 불가)별 인수·정지·blocked, `holder.verdict`·`is_zombie` 파싱. 1차의 좀비 시험은 실제 좀비를 `ps`로 확인해 인수하도록 유지했고, 무관한 산 pid 시험은 정지로 갱신했다 |
| B 무시되던 `is_alive` | 수정(의도적 호환 파괴) | `claim`에서 `is_alive` 인자를 제거했다. 검증자 스크립트 adv.py·race.py·regress.py 일부가 `claim(..., is_alive=...)`을 넘기므로 이제 TypeError다(의도). 시험·호출처는 이미 넘기지 않는다. `recover`·`register_missing`의 `is_alive`(관찰자용)는 그대로다 |
| C run_id 형식 | 수정 | `contract.check_run_id`/`RUN_ID`(소문자 16진)를 failures 파일 필터와 공유한다. `fail`은 형식 위반이면 ContractError, 재개(`_interrupted`)는 16진이 아닌 이전 run_id를 이어받지 않고 새 run_id로 재실행한다. 시험은 recovery 시험에 추가(비16진 재개 거절·실패 기록이 세어짐·fail 형식 거절) |
| D 경합 시험 안정화 | 수정 | 모든 프로세스가 READY를 출력한 뒤 동시에 출발시키고 `wins` 하한을 `> 1`로 낮췄다. M2(samestat 제거)는 15/15 실패, 정상 코드는 15/15 통과 |
| E·F | 손대지 않음 | 이미 문서에 있는 항목 |

변이(검증자 mutate2.py를 scratchpad에 복사, 사라진 대상 문자열은 STALE로 표시하게 하고 M22를 새 구조에 맞게 바꿨으며 M24~M29를 추가): 모두 시험 실패로 잡혔다(M22′ claim이 pid 무관 인수, M24 pid==getpid 검사 제거, M25 좀비도 정지, M26 판정 불가를 인수, M27 내 pid 예외 제거, M28 fail run_id 검사 제거, M29 재개 run_id 검사 제거 포함). **예외 1건**: 검증자 M16(`safe_path`의 realpath/commonpath 검사 제거)은 시험을 통과한다. 중간 폴더 링크 검사(M15)와 `islink`가 같은 경우를 이미 막아 이 검사는 현재 경로에서 중복(동등 변이)이며 방어 심층으로 남겼다.

### 다음 단계 메모 (3~4단계: Supervisor·실패 정책)

- 결정적으로 실패한 계약의 정책 필드(`escalation_level` 등)를 바꿔 새 `task_key`로 우회 등록하는 경로가 있다(adv.py 8번: 실패한 계약의 escalation_level만 바꿔도 새 작업으로 등록되어 실행됨). 이 단계는 설계 범위 밖이라 막지 않았다. Supervisor/실패 정책 단계에서 task_type·입력 기준의 동일 작업 식별과 실패 이력 연동으로 막아야 한다.
- `tail()`은 마지막 줄을 검증하지 않고 해시를 그대로 내보낸다(검증은 `verify`·`append`). 외부 복제 지점은 verify 통과 직후 값을 쓰도록 한다.

### 사용자 결정 대기

- 호출 깊이 ≤4를 "공개 진입 함수 시작 기준"으로 판정하고 시험 함수는 판정에서 제외했다(시험 함수를 시작점으로 세면 5~6). 이 해석이 PAIR_CODING.md §2.1에 부합하는지는 사용자 결정 대기 항목이다. 코드 변경 없음.

### 미검증

- 다른 OS(Linux 등): `boot_id()`는 macOS `sysctl kern.boottime`만 지원하며 다른 곳에서는 명시적 `LeaseError`다. 실제 sysctl 호출 시험은 darwin에서만 실행된다(이번 실행은 darwin).
- 재부팅 직후 시나리오, 시스템 시계 조정으로 `kern.boottime`이 바뀌는 상황, pid 재사용(같은 부팅 안에서 죽은 pid가 다른 프로세스에 재할당)은 합성 주입 시험만 했고 실제로 겪지 않았다.
- NFS·다른 파일시스템에서의 `flock` 동작, 디스크 가득참·전원 차단 중 `fsync`/`os.replace` 내구성은 시험하지 않았다.
- 장부 동시 추가는 8개 프로세스 claim 시험에서 일부만 검증했다(대량 경쟁·대용량 장부 성능 미시험; `append`는 매번 장부 전체를 읽는다).
- `./develop` 잠금·`./experiment`와의 통합은 후속 단계이며 이번에 만들지 않았다.
- 독립 검증(Opus 하위 에이전트)과 `main` 통합·원격 반영은 하지 않았다.

### 리스크

- `kern.boottime` 초 단위 값이 시계 조정으로 달라지면 살아 있는 작업권을 관찰자(classify/recover)가 INTERRUPTED로 잘못 볼 수 있다. 실행권은 `flock`이 보호하므로 claim 단계의 이중 실행은 막지만, 감독 쪽 표시가 틀릴 수 있다.
- 같은 부팅에서 pid가 재사용되면 죽은 작업이 RUNNING으로 보여 대기할 수 있고, claim도 `holder_alive_without_lock`으로 정지한다(이중 실행 방향이 아니라 정지 방향의 오류). 이 정지에서 벗어나는 자동 경로는 없다: 사람/Supervisor가 확인해야 한다(3단계 몫).
- claim의 인수 판정은 `ps` 출력과 `os.kill(pid, 0)`에 의존한다. 기록된 pid가 판정 사이에 사라지면 `ps`가 실패해 일시적으로 `blocked`가 날 수 있다(재호출로 풀림). 대리 pid claim은 거절하지만, 작업권 보유 프로세스가 호출 규약(끝까지 실행·exec 금지)을 어기는 것 자체를 막을 수는 없다.
- 비정상 종료 시 장부 줄 누락 가능(가정 9). 장부 꼬리 잘림은 외부 복제 해시(`expected_tail`) 없이는 감지되지 않는다.
- `recover()`는 잠금 없이 상태를 읽고 CORRUPT 복구(CAS 복사·완료 기록 보관)를 수행한다. 단일 감독자 전제이며 동시 복구는 막지 않는다(claim 안의 결정은 잠금 아래).

롤백: `git revert <구현 커밋>`. 런타임 상태는 호출자가 지정한 root에만 있으므로 저장소 데이터·artifacts에 영향 없음.
