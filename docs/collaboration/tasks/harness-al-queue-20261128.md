# 하네스 — VERIFIED al_select → 사람 대기열 기록 연결 (2026-11-28)

```text
task_id: harness-al-queue-20261128
owner: Claude (하위 에이전트, 구현·시험. 독립 검증·통합은 메인이 따로 수행)
status: ready_for_review (기본 꺼짐, 실제 선별·사람 화면 발급 0건)
base_sha: 3e77263
branch: claude/harness-al-queue-20261128
changed_files: harness/al_cycle.py, harness/supervisor.py, tests/test_harness_al_queue_wiring.py(신규), 이 문서
forbidden_touched: 없음(plan_gate·runner·sandbox·AGENTS.md·docs/agent·artifacts·data 미수정)
```

## 변경

- `al_cycle.pending_queue(root)`(읽기만): VERIFIED `al_select` 작업 중 장부 줄 `al_queue_recorded`가 없는 것의 `out/human_queue.json`과, 읽기 실패 사유 `{"al_queue:<task_key>": 사유}`를 돌려준다. `NEED_LABEL_CODES`·`APPROVED_INPUTS`·`CRITERIA_VERSION` 중 하나라도 비면(기본) 아무것도 읽지 않고 `({}, {})`.
- `al_cycle.CRITERIA_VERSION = ""`(신규 빈 상수), `QUEUED`, `QUEUE_ERRORS`: 대기열 키의 기준 판본 출처가 미정이라 비워 두었다(Q1~Q3와 같은 취급, 사용자 결정 전).
- `supervisor.run`: `_apply` 반영 직후에 `pending_queue` → 작업마다 `al_cycle.record_queue` → 장부 줄 `al_queue_recorded`. 거절(형식 오류·모델 필드·출력 없음)은 `QUEUE_ERRORS`로 그 작업만 `graph.note_rejected`(같은 사유는 한 번). 장부·Silver 체인 오류는 잡지 않아 기존대로 INTEGRITY_HALT.
- 사람 화면 발급(`gold_issue.issue`·`relabel.request_relabel`)은 부르지 않는다(시험이 호출 시 실패하게 막고 확인).
- 멱등: 장부 줄이 있으면 건너뛰고, 기록과 줄 사이에서 죽어도 다음 회차에 `record_queue`가 `duplicate_request`로 거절해 중복 없이 줄만 채운다.

## 함수 수·호출 깊이 (PAIR_CODING 2.1)

| 파일 | 함수 수 전 → 후 |
|---|---|
| `harness/al_cycle.py` | 5 → 6 (`pending_queue`) |
| `harness/supervisor.py` | 5 → 5 (run 본문만) |

`supervisor.run → al_cycle.record_queue → silver_store.load → ledger.verify → ledger._check_line` 4, `run → pending_queue → states.facts → …` 3. `record_queue`는 아래 깊이가 이미 3이라 래퍼 함수를 두지 못하고 run 안에서 직접 부른다(기존 시험 `DepthTest`가 run ≤ 4를 확인).

## 검증

- 새 시험 `tests/test_harness_al_queue_wiring.py` 5건: 한 번만 기록·재실행 중복 없음 / 기록-표시 사이 중단 복구 / 기본 꺼짐(조건 6가지 조합) / 미승인·형식 오류·모델 필드·출력 없음 거절·정지 아님 / 출력 파일 삭제.
- 결함 주입: `supervisor.py` 연결을 되돌리면 새 시험 3건 실패(한 번만 기록 시험 포함), 복원 후 통과.
- 하네스 전체 결과는 아래 "전체 시험" 절.

## 롤백

`git revert <커밋>` 또는 브랜치 폐기. 기본값에서 새 동작이 없으므로 운영 영향은 없다.

## 미확인·남은 결정

- `CRITERIA_VERSION` 출처(gold_store는 기준 문구 SHA-256을 요구, 시험은 "v2" 합성값): 사용자 결정 필요.
- 실제 runner 경로에서 al_select 입력 사본이 없어 실행이 실패하는 기존 한계(al_cycle 문서)는 그대로다. 이 연결은 합성 작업으로만 확인했다.
- `completed`(사람 Gold가 끝낸 키 목록)는 넘기지 않는다: 연결 출처가 없어 `already_completed` 거절은 이 경로에서 작동하지 않는다.
- HTML 보고(성능 평가 아님)·모델 성능 주장 없음.

## 전체 시험 (한 번에 하나씩, 병행 없음)

- `.venv/bin/python -m unittest discover -s tests -p 'test_harness_*.py'`: 603건 모두 통과.
- `/usr/bin/python3`(3.9.6): 603건 중 2회 연속 실행에서 `test_harness_analyze_input.AnalyzeEntryTest.test_prompt_only_fake_claude_...`와 `test_harness_b5_e2e_synthetic...test_one_supervisor_run_chains_...`가 간헐 실패(1회차 failures=1, 2회차 failures=1·errors=1). 변경 전 기준(3e77263) 깨끗한 worktree에서도 같은 두 시험이 실패했고, 이 브랜치에서 두 시험만 다시 돌리면 3회 중 2회 통과·1회 실패라 이번 변경과 무관한 기존 불안정으로 판단한다(원인은 조사하지 않음, claude_runs 0 = 가짜 Claude 작업이 그 회차에 실행되지 않음). 새 시험·al_cycle 시험 29건은 3.9에서도 통과.
