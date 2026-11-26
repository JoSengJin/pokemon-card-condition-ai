# 하네스 1단계 — 큐·상태·장부 (2026-11-27)

```text
task_id: harness-stage1-queue-state-ledger-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet High 하위 에이전트, 독립 검증은 Opus 하위 에이전트)
status: assigned
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
handoff: (구현 후 채움)
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

(구현 후 채움: 파일별 함수 수, 주요 호출 경로 전이 수, 실행한 명령·종료 코드·대상 SHA, 미검증, 리스크, 롤백)

롤백: `git revert <구현 커밋>`. 런타임 상태는 호출자가 지정한 root에만 있으므로 저장소 데이터·artifacts에 영향 없음.
