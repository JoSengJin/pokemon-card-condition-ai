# 하네스 2단계 — 한도 중 Python 계속 (2026-11-27)

```text
task_id: harness-stage2-python-runner-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet High 하위 에이전트)
status: ready_for_review
base_sha: e1cafcfcfc6b2f8971186259c6eff73c3e79c79b (1단계 3차 Opus 재검증 통과 SHA)
branch: claude/harness-stage1-20261127 (같은 브랜치에서 직렬 진행, 동시 편집 없음)
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 2행 "Claude 작업이 멈춘 상태에서 사전 등록 실험 2건이 완료되고 기록이 정상"을
  합성 작업으로 시험한다. 실제 ./experiment 실행은 이번 단계에 포함하지 않는다(아래 "설계와 환경의 차이").
allowed_files:
  - harness/runner.py (신규, 필요 시 harness/executors.py 등 신규 파일 — 함수 수 제한 때문이며 이 문서에 기록)
  - (구현 중 추가) tests/test_harness_executors.py(시험용 executor), tests/test_harness_runner_kit.py(runner 시험 공용 도구), tests/test_harness_runner.py, tests/test_harness_runner_procs.py
  - 1단계 파일의 호출 깊이 평탄화·G 수정에 필요한 harness/{queue,states,holder,recovery,lease,ledger,manifest,checkpoint,graph,contract,cas,jsonio}.py
  - tests/test_harness_*.py (신규·기존 harness 시험 조정)
  - 이 task 문서
forbidden_files: card_condition/**, tools/**, 기존 비-harness tests/**, AGENTS.md, docs/agent/**, artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**, 다른 plan 문서
contract:
  보존: 1단계 55개 시험의 의미(시험 조정은 호출 형태 변경에 한정, 검증 강도를 낮추지 않는다). 상태 5개 처리, 이중 실행 방지, 장부 무결성.
  제약: stdlib만, 네트워크·LLM·`claude` 실행·학습·추론 없음. 런타임 상태는 호출자가 준 root에만.
structure: 파일당 함수 정의 ≤7, 공개 진입 함수 호출 깊이 ≤4(아래 S2-0 이유). 구현 후 표를 채운다.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0 (3.12, /usr/bin/python3 3.9 둘 다)
  - 변이 시험: 검증자 변이 스크립트(scratchpad/stage1-verify/mutate3.py)를 복사본으로 재실행해 새로 놓치는 변이가 없음을 확인(원본 수정 금지)
  - ast 재측정(함수 수·호출 깊이), `git diff --check`, 허용 파일 대조
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: 아래 "구조 표 / 인계" 절. 최종 시험 대상 SHA dac25beb61d3b837e6db99d225ce432e543864c4(시험 커밋), 문서 커밋은 그 위.
```

## 이유와 범위

### S2-0. 호출 깊이 평탄화 + 1단계 잔여 경미 G (동작 보존)

1단계의 공개 진입 함수 `claim`·`recover`·`register_missing`은 이미 호출 깊이 4(한도)다
(`claim → decide → _interrupted → check → read_json`, `register_missing → enqueue → _log → append → _hash_entry`).
PAIR_CODING §2.1은 다른 파일의 함수로 이어지는 호출도 합산하므로, 이들을 부르는 runner는 5~6이 되어 한도를 넘는다.
책임을 합치지 않고, 1단계 공개 API의 호출 깊이를 **각각 2 이하**로 낮춘다(호출 경로를 다시 설계. 파일 분리만으로 깊이를 감추지 않는다).
runner → run_one → (1단계 공개 API ≤2) 로 4를 지키기 위함이다. 동작은 바꾸지 않는다. 55개 시험이 안전망이다.

G(경미): `claim`의 `boot` 인자를 호출자 값 그대로 쓰지 말고 `lease.boot_id()`와 같아야 한다(pid처럼). 시험은 부팅 식별자를 주입 함수로 바꾼다.
이 두 변경은 별도 커밋(`refactor(harness)`, `fix(harness)`)으로 나누고, 평탄화 전후 55개 시험·변이 결과를 비교해 인계에 적는다. 평탄화가 의미를 바꾸면 시험이 실패해야 한다.

### S2-1. Python runner (DESIGN 4·12절의 "Python 작업은 한도 중 계속")

- `harness/runner.py`: LLM 없이 큐의 `needs_llm=false` 작업만 처리한다.
  - `drain(root, executors, now, max_tasks)`: 실행 가능한 작업(의존이 모두 VERIFIED, 상태가 PENDING·INTERRUPTED 재실행 대상·재시도 가능한 transient FAILED·복구 불가 CORRUPT)을 하나씩 claim → executor 실행 → complete 또는 fail(예외 종류로 transient/deterministic 분류, 1단계 규칙 재사용) → 다음. 요약(처리·건너뜀·정지 사유)을 반환한다.
  - `needs_llm=true` 작업과 그것에 의존하는 작업은 건드리지 않고 PENDING으로 남긴다. 건너뛴 사유로 장부를 반복해서 채우지 않는다.
  - executor는 `task_type → callable(contract, out_dir) -> 출력 상대 경로 목록`을 호출자가 주입한다. 실제 `./experiment` 래퍼는 이번 범위가 아니다.
  - `holder_alive_without_lock`·`needs_failure_policy`·`blocked`는 재시도·우회하지 않고 요약에 남기고 멈춘다.
  - 같은 root를 두 runner가 동시에 처리해도 작업은 한쪽만 실행된다(1단계 claim 의존, 시험 포함).
- 설계에 없는 기능(스케줄링 데몬, 예산, 한도 감지, launchd)은 넣지 않는다(3단계).

## 필수 시험

| 시험 | 방법 | 기대 |
|---|---|---|
| T2-main | 별도 프로세스로 runner 실행. 환경에서 `claude`를 PATH에서 제거하고 LLM 관련 환경변수 없음. 큐: Python 작업 2건, LLM 작업 1건, LLM 작업에 의존하는 Python 작업 1건 | Python 2건 VERIFIED(출력 manifest 검증), LLM 작업·의존 작업은 PENDING 그대로, 장부 해시 체인 검증 통과, 요약 일치 |
| T2-nollm | runner 소스에 `claude`·`anthropic`·네트워크 모듈 import·호출 없음 | ast 검사 |
| T2-crash | runner가 작업 실행 중 kill -9 → 새 runner | 1단계 규칙대로 INTERRUPTED 인수·재실행, 다른 작업 영향 없음 |
| T2-transient | executor가 ConnectionError를 2번 내고 3번째 성공 / 계속 실패 | 최대 재시도 뒤 `needs_failure_policy`로 정지, 이후 drain이 건드리지 않음 |
| T2-det | executor가 코드 오류 | 재시도 없이 정지, 다른 독립 작업은 계속 처리 |
| T2-twin | 두 runner 프로세스 동시 drain | 각 작업은 정확히 한 번 실행(표식 파일 수로 확인) |
| T2-stop | holder_alive_without_lock 상황 | 해당 작업만 정지·요약에 사유, 나머지는 계속 |
| S2-0 회귀 | 1단계 55개 + 기존 변이 | 모두 통과·모두 잡힘 |

시험 파일당 테스트 ≤7개.

## 설계와 환경의 차이 (보고 대상)

IMPLEMENTATION 2절의 2단계 완료 기준은 "사전 등록 실험 2건"이다. 실제 `./experiment --plan`은 가설 ID·사전 기준이 있는 승인된 계획과 기본 checkout의 단일 담당 실행이 필요하고 학습·추론을 포함한다.
승인 범위에 구체적 실험 2건이 지정돼 있지 않아 이번 단계는 합성 작업(결정론적 Python 계산)으로 시험하고, 실제 `./experiment` 연결은 **미검증**으로 남긴다(4단계 "자율 루프"에서 승인된 실험으로 연결).

## 구조 표 / 인계

### 결과

S2-0(평탄화·G)과 S2-1(runner)을 모두 구현했고 필수 시험 7종(T2-main·nollm·crash·transient·det·twin·stop)과 S2-0 회귀를 실제로 실행해 통과했다. 합성 작업(결정론적 Python 계산)이며 모델 성능 근거가 아니다. **실제 `./experiment` 연결은 이번 범위가 아니며 미검증이다**(4단계 "자율 루프"에서 승인된 실험으로 연결).

### 커밋과 시험 결과

| 커밋 | SHA | 내용 |
|---|---|---|
| `refactor(harness)` | `5a60464121684de382a60d8638a5568b0417fd4e` | 1단계 공개 함수 호출 깊이 2 이하 평탄화(동작 보존) |
| `fix(harness)` | `e89d0bb85fe4a1f344c07f01b7ff5227b772570f` | G: claim의 boot는 `lease.boot_id()`와 같아야 함 |
| `feat(harness)` | `eddc20d5e32f623b0128cae36e2e0ea13beccdd0` | `harness/runner.py` |
| **`test(harness)`(시험 대상)** | `dac25beb61d3b837e6db99d225ce432e543864c4` | runner 시험·executor·공용 도구 |
| 문서 | 이 문서 커밋(그 위) | 문서만 |

| 명령(cwd=worktree) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -p "test_harness_*.py" > file 2>&1; echo rc=$?` (3.12.14) | rc=0, 65개 통과(연속 3회 모두) |
| `... /usr/bin/python3 ...` (3.9.6) | rc=0, 65개 통과(연속 3회 모두) |
| `git diff --check` (각 커밋 직전) | 0 |
| `git diff --name-only d582cc2 HEAD` | harness/{cas,checkpoint,contract,graph,holder,lease,manifest,queue,recovery,runner,states}.py, tests/test_harness_*.py, 이 문서. 허용 범위 안 |

1단계 55개 시험은 평탄화 뒤에도 의미 그대로 통과한다(시험 조정은 호출 형태: `mock.patch` 대상 `states.classify`→`states.facts`·`queue._log`→`queue.ledger.append`, claim 호출에 `boot_id_fn` 주입용 `claim` 도우미(functools.partial). 단언 강도는 낮추지 않았고 오히려 4개를 추가했다: claim의 CAS 복구 뒤 재검증, ps 종료 코드 실패 무시, boot 검증, 비16진 run_id 등).

### S2-0: 호출 깊이 전후(공개 진입 함수 기준, 이름 참조 기반 정적 상한)

| 함수 | 전 | 후 | 후 대표 경로 |
|---|---|---|---|
| queue.claim | 4 | 2 | claim → facts/decide/restore/append → 말단 |
| queue.recover | 4 | 2 | recover → facts/decide/restore/append → 말단 |
| graph.register_missing | 4 | 2 | → facts/reconcile/append → 말단(queue.enqueue를 거치지 않고 같은 3단계를 직접 수행) |
| queue.enqueue | 3 | 2 | enqueue → append → _hash_entry |
| queue.complete | 3 | 2 | complete → build/put/append → 말단 |
| queue.fail | 3 | 2 | fail → failures/append → 말단 |
| states.classify | 2 | 2 | classify → facts → 말단 |
| runner.main(CLI) | - | 4 | main → drain → claim/complete → append/decide/put → 말단(최대 4) |
| runner.drain | - | 3 | |

재설계 요지(파일 분리로 깊이를 감추지 않음): (1) `states.facts`(읽기만, 말단 함수만 호출)로 사실을 모으고 `states.state_of`(아무것도 부르지 않는 순수 판정)가 상태를 정한다. `classify`는 이 둘을 감싼 관찰자용 진입점. (2) `recovery.decide`는 순수 계획 함수(`_plan`·`_interrupted`·`_failed`·`_archive`·`checkpoint.check`는 서로 호출하지 않는 말단). CAS 복구(부수 효과)는 호출자(claim/recover)가 `cas.restore`로 먼저 하고 다시 `facts`를 읽는다. (3) `ledger.append`·`cas.put`·`manifest.build` 등은 말단만 부르고, `queue._log`·`states.load_contract`·`manifest.mismatches`·`contract._check_values`·`contract.canonical`은 없앴다(호출을 펼침). 비용: 같은 순서(사실 수집→복구→재수집→판정→기록)가 claim과 recover에 한 번씩 보이고, register_missing이 enqueue의 3단계를 직접 수행하며, `cas.restore`는 `put`과 같은 해시 검사를 가진다(약 5줄 중복). `claim`·`recover`는 길다(함수 수 제한은 지킴).

### 파일별 함수 정의 수(ast, 한도 ≤7)

harness: cas 6, checkpoint 2, contract 5, graph 3, holder 2, jsonio 2, lease 7, ledger 6, manifest 2, queue 6, recovery 6, **runner 5**, states 4. tests: claim_churn 1, claim_holder 6, claim_processes 6, contract_cas 6, executors 6, graph 6, lease 5, ledger 7, paths 4, recovery 7, **runner 7**, runner_kit 5(시험 아님), runner_procs 2, state_guards 6, states 7, support 7(시험 아님). 시험 파일당 테스트 ≤7개. 새 파일(함수 수 제한 때문): tests/test_harness_executors.py, runner_kit.py.

### 변이 비교(검증자 mutate3.py 복사본, 새 구조에 맞게 대상 문자열을 옮기고 추가)

- 전(e1cafcf, 원본 mutate3.py 그대로): 29개 중 27개 시험 실패로 잡힘, 생존 2(M16 realpath 검사 제거는 동등 변이, H6 ps 종료 코드 무시).
- 후(구조가 바뀌어 대상 문자열을 같은 의미로 옮긴 복사본, 46개 변이): 43개 잡힘. 생존 3개는 모두 동등 변이다: M16(realpath/commonpath 검사는 중간 폴더 링크 검사와 겹침), M23(done 비객체: 이제 `recorded=None`이 산출물 전체를 어긋남으로 만들어 중복), X10(이미 VERIFIED인 작업을 후보로 두어도 claim이 `skip`으로 막음). 전 단계의 H6은 이번에 ps 종료 코드 시험을 추가해 잡힌다. 새로 추가한 M8a(claim의 복구 뒤 재검증 생략)도 시험을 추가해 잡힌다.
- 새 방어 변이(모두 잡힘): G1 boot 검사 제거, X1 LLM 작업도 실행, X2 LLM 간접 의존, X3 의존 VERIFIED 확인 제거, X4 executor 출력 목록 대조 제거, X5·X11 정지·결정적 실패 재시도, X7 모든 예외를 결정적으로, X8 max_tasks 무시, X9 executor 없는 작업 후보, X12 완료 오류를 실패로 안 바꿈.

### S2-1 runner 구현 요약

- `harness/runner.py`: `_scan`(읽기만: 후보와 건드리지 않는 작업 사유), `_execute`(executor 실행·오류 분류), `_note`(요약 반영), `drain`, `main`(`python -m harness.runner <root> <module:EXECUTORS> [--max N]`, JSON 한 줄 출력).
- 작업 후보: LLM(needs_llm=true)·그 직간접 의존 작업·executor 없음·의존 미완료·읽을 수 없는 계약은 건드리지 않고(claim 호출 없음 = 장부에 안 남음) 요약 `untouched`에만 적는다. 나머지는 claim → executor → complete/fail. executor 출력 목록이 계약 outputs와 다르거나 산출물을 완료할 수 없으면(링크 등) 결정적 실패.
- 정지 사유(`locked`·`needs_failure_policy`·`blocked`·`holder_alive_without_lock`)는 우회하지 않고 요약에 남기며 그 작업만 이번 drain에서 다시 시도하지 않는다. 일시적 실패는 다음 회차에서 곧바로 재시도(대기·백오프 없음, 3단계).
- 시험 대응: T2-main(실제 subprocess, PATH에 claude 없음·모델 환경변수 없음: Python 2건 VERIFIED·manifest 검증, LLM 작업·직접/간접 의존 작업 PENDING, 장부 검증·claimed 이벤트 일치), T2-nollm(ast: 금지 import·호출·문자열 없음), T2-crash(kill -9 뒤 새 runner: S 시작 표식 2·실행 표식 1, 다른 작업 표식 각 1, `interrupted_rerun` 1건, 새 run_id), T2-transient(2번 실패 뒤 성공: 표식 3 / 계속 실패: 3회 뒤 `needs_failure_policy`, 이후 drain은 표식·장부 크기 불변), T2-det(결정적 오류 1회 실행·독립 작업 계속·의존 작업 대기), T2-twin(두 runner 동시 drain: 10개 작업 각 표식 1, claimed 이벤트 정확히 1, 실제 충돌 `locked` 4~5건/runner 확인), T2-stop(잠금 없이 산 pid → 그 작업만 `holder_alive_without_lock`, 장부 정지 사유 1줄, 나머지 완료).

### 가정

1. runner(와 claim)는 macOS 전용이다: 실제 `lease.boot_id()`(sysctl)를 쓰며 runner 시험은 darwin에서만 실행된다(`skipUnless`). 시험 PATH에 `/usr/sbin`(sysctl)은 포함하고 claude는 없다.
2. runner는 체크포인트 지문(`current`)을 공급하지 않으므로 중단된 작업은 항상 새 run_id로 재실행한다(체크포인트 복원은 executor 계약에 없는 기능이라 넣지 않았다).
3. executor는 호출자 코드(동적 호출)다. 호출 깊이 ≤4는 runner·1단계 함수 기준이며 executor 안쪽은 포함하지 않는다.
4. `harness/runner.py`는 모델·네트워크·하위 프로세스를 쓰지 않지만 import하는 `recovery`(socket.timeout 분류용)와 `holder`(ps 조회용 subprocess)는 쓴다. T2-nollm은 runner.py 소스만 검사한다.
5. 검증자 스크립트(adv.py·adv3.py·race.py·race3.py 등) 중 `claim(..., is_alive=)` 또는 지어낸 boot 값을 넘기는 것은 G·B로 의도적으로 TypeError/QueueError가 난다. proxy3.py(대리 pid 거절)와 holder_adv.py(죽은 pid 인수 1승·exec 정지·산 pid 정지·스레드 경합 겹침 0)는 새 코드에서 기대대로 동작했다.

### 미검증

- 실제 `./experiment --plan` 연결: 이번 범위 아님(승인된 구체 실험 2건이 없고 기본 checkout 단일 담당 실행이 필요). 합성 executor만 시험했다.
- Linux·NFS·전원 차단 내구성, 시계 조정·pid 재사용 같은 1단계의 미검증 항목은 그대로다.
- executor가 매우 오래 걸리는 작업 중 runner를 정상 종료(SIGTERM)하는 경로는 시험하지 않았다(SIGKILL만).
- 대량 작업(수천 건)에서 `_scan`이 매 회차 모든 작업을 `facts`로 읽는 비용·장부 전체를 읽는 `append` 비용은 측정하지 않았다.

### 리스크

- `_scan`은 매 회차 모든 작업 폴더를 읽는다(O(작업 수)·회차). 작업이 많아지면 느려질 수 있다.
- 일시적 실패를 대기 없이 즉시 재시도하므로 실제 네트워크 장애에서는 3회가 순식간에 소진될 수 있다(백오프는 3단계).
- 평탄화로 claim/recover가 길어졌고 같은 순서가 두 곳에 있다. 한쪽만 고치면 어긋날 수 있다(시험이 양쪽을 덮는다: M8a·M8b).
- CLI의 최상위 호출(`main`→`drain`) 깊이는 4로 한도에 닿는다. 앞으로 runner 위에 계층을 더하려면 drain의 깊이를 먼저 줄여야 한다.

롤백: `git revert <구현 커밋들>`. 런타임 상태는 호출자가 지정한 root에만 있다.
