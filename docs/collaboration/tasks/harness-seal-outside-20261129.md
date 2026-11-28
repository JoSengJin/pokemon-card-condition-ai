# harness-seal-outside-20261129 — PLAN_GATE 저장소 밖 봉인 루트 차단 (독립 검증 D1)

- 브랜치 `claude/harness-seal-outside-20261129`, 기준 `caeea93`. 합성 시험만, 실제 `artifacts/`·봉인 자료·모델 호출 없음.

## 결함 D1

`seal_check.load`가 `claude_perm.sealed_paths`만 써서 `claude_perm.outside_roots`(`harness/sealed_outside_roots.json` + `git worktree list`)를 빠뜨렸다(`stage_inputs`는 둘 다 씀). 원본 `artifacts/experiments/<id>`가 바깥 봉인 루트로 가는 심볼릭 링크면 `plan_gate._external`(sandbox 밖 Supervisor)이 바깥 `record.json`·`plan.json`을 열고, `source_hashes` 키가 바깥 루트 파일 링크면 해시했다.

## 변경

| 파일 | 내용 | 함수 수(전→후) |
|---|---|---|
| `harness/seal_check.py` | `load`: `_ids(sealed_paths(bases) + outside_roots(bases))`. docstring | 2→2 |
| `harness/plan_gate.py` | `_external` docstring 한 줄(바깥 루트 포함 명시). 코드 변경 없음 | 7→7 |
| `tests/test_harness_vs3_seal_outside.py`(새) | 시험 3개(바깥 루트 링크 폴더 건너뜀·연 파일 0 / 바깥 루트 링크 `source_hashes` 해시 0회·waiting / 바깥 목록 없음 → `ValueError`) | 0→4 |

호출 경로: `gate → _external → seal_check.load → claude_perm.sealed_paths·outside_roots·_ids` = 3(새 전이는 `load → outside_roots` 1개, 깊이 변화 없음). `supervisor.run` 기준 4 이하 유지.

## 검증

- 수정 전 새 시험 3개 실패(바깥 `record.json`·`plan.json`·`code.py`를 엶, 목록 없음에도 `ValueError` 없음) → 수정 후 OK.
- 결함 주입: `+ claude_perm.outside_roots(bases)`를 빼면 3개 모두 실패, 원복 후 OK(`git diff`로 확인).
- 관련 32개 모듈(`ls tests | grep -i "seal\|vs3\|plan_gate\|supervisor\|al_"`의 `test_harness*`): 143개 OK(107초).
- 전체: `/Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness*"` — 결과는 아래 실행 기록.

## 실행 기록

- 전체 하네스 시험: 종료 코드 0, 613개 OK(350초, 새 시험 3개 포함). 한 번에 하나씩 실행, 로그는 scratchpad `full.log`.

## 리스크

- `_external`이 매 회차 `git worktree list`를 한 번 더 부른다(하위 프로세스 1회, 60초 timeout).
- fail-closed 범위가 넓어졌다: 바깥 목록 오류·git 실패·바깥 루트가 저장소/원본의 조상이면 `ValueError` → 그 계획 `waiting`. `_external`은 계획마다 같은 목록을 읽으므로 사실상 모든 계획이 대기한다.
- 기존(이번 변경 아님): 실험 폴더 안 `record.json`·`plan.json` 하나라도 하드 링크(nlink>1)면 `seal_check.under`가 `try` 밖에서 `ValueError` → 모든 계획이 `waiting`(진행 정지). 원본 쓰기 권한이 필요한 경우만 생긴다.
- 기존 한계 유지: `load` 이후 링크 교체 경쟁 조건(권고 3) 미처리.

## 롤백

`git revert <커밋>`. `seal_check.load` 한 줄과 새 시험 파일뿐이다.

## 미확인

- 실제 `artifacts/experiments`·실제 156개 바깥 루트에서의 동작·소요 시간(합성 시험만).
