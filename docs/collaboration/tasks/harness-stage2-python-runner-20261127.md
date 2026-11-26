# 하네스 2단계 — 한도 중 Python 계속 (2026-11-27)

```text
task_id: harness-stage2-python-runner-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet High 하위 에이전트)
status: assigned
base_sha: e1cafcfcfc6b2f8971186259c6eff73c3e79c79b (1단계 3차 Opus 재검증 통과 SHA)
branch: claude/harness-stage1-20261127 (같은 브랜치에서 직렬 진행, 동시 편집 없음)
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 2행 "Claude 작업이 멈춘 상태에서 사전 등록 실험 2건이 완료되고 기록이 정상"을
  합성 작업으로 시험한다. 실제 ./experiment 실행은 이번 단계에 포함하지 않는다(아래 "설계와 환경의 차이").
allowed_files:
  - harness/runner.py (신규, 필요 시 harness/executors.py 등 신규 파일 — 함수 수 제한 때문이며 이 문서에 기록)
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
handoff: (구현 후 채움)
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

(구현 후 채움: 평탄화 전후 파일별 함수 수·호출 깊이, 명령·종료 코드·SHA, 미검증, 가정, 리스크, 롤백)

롤백: `git revert <구현 커밋들>`. 런타임 상태는 호출자가 지정한 root에만 있다.
