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
    harness/checkpoint.py, harness/recovery.py, tests/test_harness_support.py(시험 공용 도구)
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
  - `.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py" -t .` 종료 코드 0
  - 아래 "필수 시험" 전부 포함
  - `git diff --check`, 허용 파일 대조, 파일별 함수 수·호출 경로 표
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: 아래 "구조 표 / 인계" 절. 구현 e6da279a8f5396c44d722d41a5bf8830f1d55a90, 시험 대상 19f343da2439bc81357e056cb8ce32294e87ec99.
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
| 시험 대상(구현 e6da279 + 시험 19f343d) | `19f343da2439bc81357e056cb8ce32294e87ec99` |
| 구현 커밋 | `e6da279a8f5396c44d722d41a5bf8830f1d55a90` (`feat(harness)`) |
| 이 문서 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음) |

| 명령 (cwd = worktree) | 종료 코드 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14) | 0 (38개 통과) |
| `/usr/bin/python3 -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.9.6, 호환 확인) | 0 (38개 통과) |
| 위 두 명령에 `-W error::ResourceWarning` 추가(파일·파이프 누수 확인) | 0 |
| `git diff --cached --check` (두 커밋 직전) | 0 |
| 작업 지시의 원 명령 `... -s tests -p "test_harness_*.py" -t .` | **실패**(ImportError: `tests/`에 `__init__.py`가 없어 시작 폴더를 가져올 수 없음). 저장소의 기존 상태이며 이번 허용 범위에서 `tests/__init__.py`를 만들 수 없어 `-t .`를 뺀 명령으로 실행했다. 시험은 `from tests.test_harness_support import ...`(cwd 기준 네임스페이스 패키지)로 공용 도구를 읽는다. |

시험에는 변이 확인도 했다(저장소에 남기지 않음): 잠금을 공유 잠금으로 바꾸기, 재개 임계값 0으로, 재시도 한도 +5, VERIFIED 무조건 반환, 장부 prev 검사 끄기, 일시적 실패 판정 뒤집기, 체크포인트 지문 비교 끄기 — 각각 1~6개 시험이 실패했다(원복 뒤 전체 통과).

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
| harness/contract.py | 5 | tests/test_harness_lease.py | 5 |
| harness/graph.py | 3 | tests/test_harness_ledger.py | 7 |
| harness/jsonio.py | 2 | tests/test_harness_states.py | 7 (시험 6 + 도우미 1) |
| harness/lease.py | 7 | tests/test_harness_claim_processes.py | 5 (시험 4 + 도우미 1) |
| harness/ledger.py | 6 | tests/test_harness_recovery.py | 7 |
| harness/manifest.py | 2 | tests/test_harness_graph.py | 6 (시험 5 + 도우미 1) |
| harness/queue.py | 7 | | |
| harness/recovery.py | 6 | | |
| harness/states.py | 2 | | |
| harness/__init__.py | 0 | | |

### 호출 깊이(전이 수, 한도 ≤4)

측정: ast로 이름 참조(호출뿐 아니라 인자로 넘긴 콜백·기본 인자 `is_alive=lease.is_alive`도 간선으로 계산하는 보수적 상한)로 간선을 만들어 공개 진입 함수별 최장 경로를 구했다. 측정 스크립트는 저장소에 두지 않았다(임시 파일). 순환 호출 없음.

| 진입 | 최장 경로 | 전이 수 |
|---|---|---|
| queue.claim | claim → decide → _corrupt → cas.get → sha_file (또는 → mismatches → sha_file, → decide → _interrupted → _plan → new_run_id, → classify → is_alive → boot_id) | 4 |
| queue.recover | 위 claim과 같은 경로 | 4 |
| graph.register_missing | register_missing → enqueue → _log → ledger.append → _hash_entry | 4 |
| queue.complete | complete → cas.put → has → sha_file / complete → _log → append → _hash_entry | 3 |
| queue.fail | fail → _log → append → _hash_entry | 3 |
| queue.enqueue | enqueue → _log → append → _hash_entry | 3 |
| ledger.verify | verify → _check_line → _hash_entry | 2 |
| states.classify | classify → is_alive → boot_id / → mismatches → sha_file | 2 |

공개 진입 함수 시작 기준 최대 4로 한도 이내이다. 단 시험 함수를 시작점으로 세면 시험 → claim(4) 또는 시험 → 도우미 → claim(4)이라 5~6이 된다(시험 쪽은 이번 한도 판정 대상에서 제외했다고 가정, 아래 가정 참조).

### 구조와 명세 대비 차이·추가 파일

- 새 파일(함수 수 제한 때문): `jsonio.py`(원자 저장·읽기), `manifest.py`(출력 manifest), `checkpoint.py`(체크포인트 지문), `recovery.py`(상태별 결정), 시험 공용 `tests/test_harness_support.py`. `queue.recover`는 명세대로 `queue.py`에 있고 결정 로직은 `recovery.py`에 둔다.
- `lease.acquire`는 `lock()`(잠금+이전 기록) → 판단 → `stamp()`(내 기록) 두 단계로 나눴다. 상태 분류·실행 여부 결정을 잠금 안에서 해야 동시 claim이 안전하기 때문이다. 콜백으로 넘기면 호출 깊이를 정적으로 확정할 수 없어 콜백 방식은 택하지 않았다.
- 보조 상태 2개 추가: `PENDING`(큐에 있고 기록 없음, 명세의 "대기 중"), `UNREGISTERED`(큐에 없음). 5개 상태 정의는 그대로다.
- 작업 폴더 구조: `root/ledger.jsonl`, `root/cas/`, `root/tasks/<task_key>/{contract.json, out/, lease.json, done.json, failures/NNN-<run_id>.json, checkpoint.json, history/}`.

### 가정 (명세가 모호해 가장 보수적으로 고른 해석)

1. `task_key`는 계약 전체(expected_minutes만 제외)의 canonical JSON sha256이다. 필드를 바꾸면 새 키가 되어 이미 VERIFIED여도 다시 실행된다(거짓 건너뜀보다 낫다고 봄).
2. `outputs`는 비어 있을 수 없고 안전한 상대 경로여야 한다(출력 해시로만 완료를 인정하기 때문). 산출물은 `tasks/<key>/out/<상대경로>`에 쓴다. 심볼릭 링크 산출물·manifest의 선언 외 키·읽을 수 없는 `done.json`은 모두 CORRUPT다.
3. INTERRUPTED의 "실행 시간"은 `복구 판단 시각(now) - 작업권 획득 시각`이다. 사망 시각을 모르므로 실제 작업 시간보다 길게 잡힐 수 있다. 30분 정확히는 재개 가능(≥30).
4. 체크포인트 복원 조건: 같은 run_id의 체크포인트이고 지문 6개 항목(code_sha·data_sha·seed·rng·optimizer·data_order)이 호출자가 준 `current`와 모두 같음. `current`가 없으면 복원하지 않는다. 재개는 중단된 run_id를 그대로 쓰고 `resumed=true`, 아니면 새 run_id다.
5. 실패 종류: `ConnectionError`·`TimeoutError`·`socket.timeout`만 일시적, 그 밖(코드 오류 포함, 알 수 없는 예외)은 결정적이다. 재시도 한도는 `retry_policy.max_transient_retries`(0~2, 기본 2); 최초 1회 + 재시도 2회 = 실패 기록 3건 뒤 `needs_failure_policy`. 마지막 실패 기록의 종류를 기준으로 한다.
6. INTERRUPTED에서 새 실행(rerun)은 일시적 실패 한도에 세지 않는다(중단은 실패 기록이 아니므로). 반복 중단 한도는 후속 단계(Supervisor·한도)의 몫이다.
7. 빈(또는 공백) 작업권 파일은 "작업권 없음"(잠금만 잡고 기록 전에 죽은 경우)으로, 깨진 JSON은 "죽은 작업권"으로 본다.
8. `reconcile`은 VERIFIED·RUNNING·PENDING이 아니고 의존이 모두 VERIFIED인 작업을 모두 돌려주지만, `register_missing`은 그중 UNREGISTERED만 `enqueue`한다. FAILED·INTERRUPTED·CORRUPT는 이미 큐에 있으므로 등록하지 않고(특히 결정적 실패를 우회 재등록하지 않으려고) claim/recover의 판단에 맡긴다. 선언 키는 계약의 task_key와 같아야 한다. 해시 키는 순환이 불가능하므로 순환 시험은 임의 키 사전으로 reconcile을 직접 호출한다.
9. 장부는 상태 변경 뒤에 기록한다(일어나지 않은 일을 주장하지 않으려고). 비정상 종료 시 장부 줄이 빠질 수 있으며 상태 파일이 정본이다. 호출 깊이 한도는 공개 진입 함수 기준으로 판단했다(시험 함수 시작 기준은 위 표 참조).

### 미검증

- 다른 OS(Linux 등): `boot_id()`는 macOS `sysctl kern.boottime`만 지원하며 다른 곳에서는 명시적 `LeaseError`다. 실제 sysctl 호출 시험은 darwin에서만 실행된다(이번 실행은 darwin).
- 재부팅 직후 시나리오, 시스템 시계 조정으로 `kern.boottime`이 바뀌는 상황, pid 재사용(같은 부팅 안에서 죽은 pid가 다른 프로세스에 재할당)은 합성 주입 시험만 했고 실제로 겪지 않았다.
- NFS·다른 파일시스템에서의 `flock` 동작, 디스크 가득참·전원 차단 중 `fsync`/`os.replace` 내구성은 시험하지 않았다.
- 장부 동시 추가는 8개 프로세스 claim 시험에서 일부만 검증했다(대량 경쟁·대용량 장부 성능 미시험; `append`는 매번 장부 전체를 읽는다).
- `./develop` 잠금·`./experiment`와의 통합은 후속 단계이며 이번에 만들지 않았다.
- 독립 검증(Opus 하위 에이전트)과 `main` 통합·원격 반영은 하지 않았다.

### 리스크

- `kern.boottime` 초 단위 값이 시계 조정으로 달라지면 살아 있는 작업권을 관찰자(classify/recover)가 INTERRUPTED로 잘못 볼 수 있다. 실행권은 `flock`이 보호하므로 claim 단계의 이중 실행은 막지만, 감독 쪽 표시가 틀릴 수 있다.
- 같은 부팅에서 pid가 재사용되면 죽은 작업이 RUNNING으로 보여 대기할 수 있다(이중 실행 방향이 아니라 정지 방향의 오류).
- 비정상 종료 시 장부 줄 누락 가능(가정 9). 장부 꼬리 잘림은 외부 복제 해시(`expected_tail`) 없이는 감지되지 않는다.
- `recover()`는 잠금 없이 상태를 읽고 CORRUPT 복구(CAS 복사·완료 기록 보관)를 수행한다. 단일 감독자 전제이며 동시 복구는 막지 않는다(claim 안의 결정은 잠금 아래).

롤백: `git revert <구현 커밋>`. 런타임 상태는 호출자가 지정한 root에만 있으므로 저장소 데이터·artifacts에 영향 없음.
