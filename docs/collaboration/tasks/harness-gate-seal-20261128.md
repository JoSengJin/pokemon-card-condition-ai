# harness-gate-seal-20261128 — PLAN_GATE가 봉인 실험 기록을 열지 않게 함

- 브랜치: `claude/harness-gate-seal-20261128`(분기 `3e77263`). main 미통합·push 안 함.
- 증거 수준: 구현 + 합성 시험(임시 원본·임시 봉인 목록). 실제 봉인 파일 열람·실험·claude·모델 호출 0건. 모델 성능 변화 없음.

## 확인한 사실

- Supervisor는 sandbox 밖에서 돈다. `plan_gate.gate`(`supervisor.py` 144행) → `_external`(`plan_gate.py`)이 원본 `artifacts/experiments/*/`의 `record.json`·`plan.json`을 읽고(`read_json`), `plan.json`의 SHA(`cas.sha_file`)와 `record.source_hashes`가 가리키는 원본 파일의 SHA를 계산했다. 봉인 목록(`harness/sealed_paths.json`)의 실험 폴더도 가리지 않았다.
- 내용의 흐름: 읽은 값은 메모리 안에서 `==`로 비교만 한다. 밖으로 나가는 것은 폴더 이름(`dup` 경로)과 예외 종류 이름뿐이며 `Hold` 사유 → `graph.note_rejected` → 장부·알림에 쓰인다. Claude 프롬프트·입력 사본으로 가는 경로는 찾지 못했다(`stage_inputs`가 봉인 경로 복사를 거절). 다만 봉인 파일을 열고 해시하는 것 자체가 D4("봉인 내용은 열람하지 않는다") 위반이었다.
- 같은 gate의 다른 외부 읽기: `dedupe.find_duplicate`는 하네스 root의 `tasks/*/contract.json`만, `_head`·`dedupe.verify_code`는 git 명령(커밋 SHA·트리 지문·변경 여부)만 읽는다. 봉인 파일 본문을 열지 않는다(git status의 작업 트리 변경 검사는 git 내부에서 파일 stat·해시를 보지만 내용을 우리 코드로 가져오지 않는다. 미검증 한계).

## 변경

| 파일 | 내용 | 함수 수(전→후) |
|---|---|---|
| `harness/seal_check.py`(새) | `load(bases)`: `claude_perm.sealed_paths` + `_ids`로 봉인 (장치, inode) 집합. `under(path, sealed)`: 실제 경로나 상위 폴더가 집합에 있는지(stat만). 목록 오류는 `ValueError`(fail-closed) | 0→2 |
| `harness/plan_gate.py` | `_external`: 시작 때 `seal_check.load([REPO, src])`. 폴더·`record.json`·`plan.json` 중 하나가 봉인이면 열지 않고 건너뜀. 열 수 있는 기록의 `source_hashes`가 봉인 경로를 가리키면 해시하지 않고 `ValueError`(→ 그 계획만 `waiting`). docstring에 한계 기록 | 7→7 |
| `tests/test_harness_vs3_seal.py`(새) | 시험 4개 | 5 |

`claude_perm.py`·`plan_gate.py`는 이미 함수 7개 한도여서 새 함수를 새 파일에 두었다. 호출 깊이: `gate → _external → seal_check.load → claude_perm.sealed_paths·_ids` = 3, `under → _ids` = 3(gate 기준 한도 3, `supervisor.run` 기준 4).

## 판단 공백 처리

- 봉인 폴더는 비교하지 않는다(건너뜀). 비교 불가 → 대기로 하면 봉인 폴더가 항상 존재해 모든 계획이 영구 대기가 되므로 택하지 않았다.
- 남는 위험: 봉인된 과거 `./experiment` 기록과 실행 조건이 같은 새 계획은 `_external`이 못 잡는다(통과 쪽 공백). 과거 기록의 `source_hashes`가 지금 코드와 같을 때만 중복이므로 오래된 봉인 기록은 실제로 겹칠 가능성이 낮지만 0은 아니다. 겹치면 같은 실험을 한 번 더 돌려 예산을 쓰는 비용이고 봉인 유출은 없다. 보완은 사용자가 봉인 실험의 요약(조건 해시 목록)을 별도로 승인할 때 한다.

## 검증

- `tests.test_harness_vs3_seal` 4개: ① 봉인 폴더·봉인 `record.json`을 열려는 시도 0건(`builtins.open` 감시), 정상 계획이 거절·대기 없이 통과 ② 개발 폴더의 같은 조건 기록은 봉인 폴더가 있어도 여전히 `refused: 기각·중복 가설` ③ `source_hashes`가 봉인 파일을 가리키면 해시하지 않고 `waiting` ④ 봉인 목록 오류면 `_external`이 `ValueError`(fail-closed).
- 결함 주입: 건너뛰는 `continue`를 `pass`로 바꾸면 ①②③④가 실패(봉인 기록을 열어 기각 거절로 바뀜), `source_hashes` 검사를 끄면 ③이 실패. 원복 확인.
- 하네스 전체 시험 결과는 아래 "실행 기록".

## 실행 기록

- `.venv/bin/python -m unittest discover -s tests -p 'test_harness_*.py'`: 602개 OK(391초, 새 시험 4개 포함).
- `/usr/bin/python3`로 같은 명령: 602개 OK(421초).
- 한 번에 하나씩 실행. 로그: scratchpad `gate-seal/venv.log`·`sys.log`.

## 독립 검증 반영 (e4c15c8 이후)

- F1(필수, 하드 링크 우회): 봉인 폴더의 `record.json`·`plan.json`을 개발 폴더에 하드 링크하면 (장치, inode)·상위 폴더 검사를 피해 열렸다. `seal_check.under`가 봉인이 아닌 일반 파일이 `st_nlink > 1`이면 `ValueError`를 낸다(`stage_inputs` F11과 같은 처리) → 그 계획만 `waiting`. 봉인 판정이 먼저라 봉인 폴더 안의 파일은 그대로 건너뛴다. 시험 `test_hard_link_to_a_sealed_record_waits_without_opening_it`, 결함 주입(`> 1`을 `> 99`로)하면 이 시험이 실패.
- 권고 1: 같은 조건 기록의 `source_hashes` 키가 절대 경로이거나 `..` 조각이 있으면 해시하지 않고 `ValueError`(대기). 시험 `test_absolute_or_parent_source_hash_keys_wait_without_hashing`, 검사를 빼면 실패.
- 권고 2: `source_hashes` 검사를 plan·command 동등 비교 뒤로 옮겼다(해시가 실제로 필요할 때만). 조건이 다른 기록 하나가 새 계획을 대기시키지 않는다. 시험 `test_a_record_with_another_condition_is_not_hashed_and_does_not_hold_the_plan`.
- 하지 않음(메인이 사용자 결정으로 처리): 권고 3(load 이후 경로·심볼릭 링크 경쟁 조건), 권고 4(git status의 봉인 추적 파일 재해시).
- 앞 절의 "하드 링크는 막지 않는다" 미확인 항목은 이 수정으로 해소됐다.
- 시험: `test_harness_vs3*` 28개 OK, `test_harness_seal*` 12개 OK, 전체 `.venv/bin/python` 605개 OK(355초, 3.9 전체 실행은 메모리 때문에 생략).

## 롤백

`git revert <커밋>` 또는 브랜치 폐기. `plan_gate._external`의 `seal_check` 3줄과 새 파일 2개뿐이다.

## 미확인

- 실제 `artifacts/experiments`(272개 폴더)에서의 동작·성능은 실행하지 않았다(합성 시험만).
- 하드 링크로 봉인 파일을 가리키는 `record.json`은 막지 않는다(`stage_inputs`는 막음). 원본 저장소 쓰기 권한이 필요한 위협이라 범위 밖으로 뒀다.
- `sealed_paths.json`은 여전히 "사용자 확인 전·완전성 미확인" 초안이다.
