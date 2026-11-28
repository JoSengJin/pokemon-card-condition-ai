# harness-seal-read-20261128 — executor sandbox의 봉인 자료 읽기 차단

- 브랜치: `claude/harness-seal-read-20261128`(분기 `0da3cb7`, 하네스 통합 브랜치). main 미통합·push 안 함.
- 증거 수준: **구현 완료 + 합성 시험**(임시 폴더의 가짜 봉인 파일, 실제 `sandbox-exec` 하위 프로세스). 실제 실험·학습·평가 실행 0건, 모델 누락·오탐 변화 없음.
- 봉인 자료 내용(이미지·JSON)은 열지 않았다. 목록은 파일 이름만으로 만들었다.

## 문제(변경 전)

1. `harness/sandbox.py` 프로필이 `(allow default)` + `(deny file-write*)`라서 실험·학습·평가 executor가 저장소의 봉인 자료를 읽을 수 있었다.
2. `harness/claude_perm.py` `FORBIDDEN_PARTS=("gold","seal")`은 입력 복사(stage_inputs)에만, 이름 기준으로만 걸려 holdout·independent·d1 등은 못 막았다.

## 변경

| 파일 | 내용 | 함수 수(전→후) |
|---|---|---|
| `harness/sealed_paths.json`(새 파일) | 봉인 경로 목록 44개(저장소 기준 상대 경로). `status`: 자동 추정 초안, 사용자 확인 전(완전성 미확인) | — |
| `harness/claude_perm.py` | `SEALED_LIST`, `sealed_paths(bases)`(O_NOFOLLOW로 열고 일반 파일·형식 검사, bases 기준 realpath 목록, 오류는 ValueError). `stage_inputs`가 시작할 때 목록을 읽고(저장소·source_root 기준) 그 아래 실제 경로 입력을 거절. 이름 규칙 유지(이중 차단) | 4→5 |
| `harness/sandbox.py` | `profile`이 목록 경로마다 `(deny file-read* (subpath "<realpath>"))`(저장소와 runner가 넣은 `HARNESS_SOURCE_ROOT` 기준). 목록 오류면 ValueError → `available()` False(executor 실행 안 함) | 5→5 |
| `tests/test_harness_sandbox_read.py`(새 파일) | 아래 시험 4개 | 7 |

호출 경로: `available`·`sandboxed`·`run_one` → `profile` → `claude_perm.sealed_paths`(말단) = 2. `stage_inputs` → `sealed_paths`(말단) = 1. 한도 4 안.
`subpath`는 파일 하나에도 적용된다(파일 항목도 막힘을 실측). 그래서 `literal`은 따로 쓰지 않았다.

## 목록 생성(파일 내용을 열지 않음)

worktree 루트에서:

```sh
git ls-files | python3 -I gen.py > paths.json
```

`gen.py`(scratchpad `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/seal-read/gen.py`) 규칙:
- `SEALED.json`·`HOLDOUT.md`가 있는 폴더를 넣는다.
- 경로 조각 이름에 `sealed|holdout|independent|gold|seal`(대소문자 무시)이 든 가장 얕은 경로를 넣는다.
- 소스·문서(`card_condition/ harness/ tests/ tools/ docs/`)는 뺀다. 이 경로들은 봉인 자료가 아니고(예: `harness/gold_*.py`, `card_condition/observation_seal.py`), 막으면 executor·시험이 import하다 깨진다.
- 다른 항목 아래에 있는 항목은 합친다. 결과는 44개(그중 폴더 35개, 파일 9개, 모두 존재), 모두 `artifacts/` 아래.

## 시험

| 시험 | 확인한 것 |
|---|---|
| `test_sealed_reads_are_refused_in_sandbox_but_normal_reads_and_stdlib_work` | 실제 sandbox 안 executor: 봉인 폴더 파일 읽기·stat·목록, 파일 항목 읽기, 링크인 항목의 실제 경로 읽기, 저장소 안 심볼릭 링크 경유 읽기, 하드 링크 만들기 모두 `EPERM`(1). 정상 파일 읽기, `sqlite3`·`ssl` import, `sys.executable` 읽기는 성공. 대조: 같은 프로필에서 `deny file-read*` 줄만 빼면 앞 6가지 읽기가 성공(막는 것은 규칙이다) |
| `test_stage_inputs_refuses_listed_paths_by_real_path_and_keeps_name_rule` | 이름에 봉인 표시가 없는 `vault/a.json`·`loose.json`·링크 항목 아래 `hidden/b.json` 입력 거절, 정상 입력 복사, `gold/` 이름 규칙 유지 |
| `test_missing_linked_or_malformed_list_fails_closed` | 목록 없음·링크·JSON 아님·목록 형식 아님·빈 목록·절대 경로·`..`·따옴표·숫자·문자열·`a//b` 11종: `profile` ValueError, `available()` False, `stage_inputs` ValueError |
| `test_tracked_list_loads_and_holds_only_data_paths` | 추적 목록이 읽히고 소스·문서 경로가 없으며, 실제 목록으로 만든 프로필이 이 macOS에서 적용됨(`available()` True) |

결함 주입(일부러 고친 뒤 시험 실행, 끝나면 `git checkout`으로 되돌림). 로그: scratchpad `logs/seal-read-fault-F1..F4.log`

| 주입 | 잡은 시험 |
|---|---|
| F1 프로필에서 `deny file-read*` 줄 제거 | sandbox 읽기 시험 실패 |
| F2 `stage_inputs`의 목록 검사 제거 | stage_inputs 시험 실패 |
| F3 목록 없음을 빈 목록으로(fail-open) | fail-closed 시험 실패 |
| F4 realpath 대신 normpath | sandbox 읽기 시험·stage_inputs 시험 실패 |

수정 전 실패 로그: `logs/seal-read-before-fix.log`(4개 오류: `SEALED_LIST` 없음).

전체 하네스 시험(대상 `740c90f`, `full-suite.lock` 획득 뒤 1회씩, `python -m unittest discover -s tests -p "test_harness_*.py"`):

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 555 통과, 실패 0 (340초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-venv312.log` |
| `/usr/bin/python3`(3.9) | 555 통과, 실패 0 (382초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-py39.log` |

분기 `0da3cb7`의 시험 정의 551개(`git grep -c "    def test_"`) + 새 시험 4개 = 555. 기존 시험은 고치거나 지우지 않았다.

## 한계·미확인

- **같은 macOS 사용자의 sandbox 밖 프로세스**(Codex·대화형 Claude·사용자 셸)는 여전히 봉인 자료를 읽을 수 있다(OS 사용자 분리 D-7 범위).
- **sandbox 밖에서 미리 만든 하드 링크**는 목록 밖 이름으로 sandbox 안에서도 읽힌다(scratchpad 실측). sandbox 안에서 새로 만드는 하드 링크는 거절된다. stage_inputs는 링크 수 2 이상을 원래대로 거절한다.
- **목록 완전성 미확인.** 추적 파일 이름만 봤다. 기본 checkout의 추적 안 되는(gitignore) 자료 중 같은 이름 규칙에 걸리는 후보가 65개 더 있다(이름만 확인, 예: `artifacts/cohort-seal-20261123`, `artifacts/cohort2-seal-20261123`, `artifacts/chieut-independent-20261012`, `artifacts/ebay-independent-20261119-*`, `artifacts/corner-rank-independent-*`). 목록에 넣지 않았다. 후보 이름 목록: scratchpad `seal-read/untracked-main-candidates.json`(79개 중 추적 목록 밖 65개).
- 이름 규칙에 안 걸리는 봉인 자료(예: 봉인 350·468장이 다른 이름 폴더에 있다면)는 목록에 없다.
- `tools/experiments/*holdout*/`의 `plan.json`·`worker.py`는 코드로 보고 뺐다(봉인 자료 여부 사용자 확인 필요).
- sandbox는 경로 문자열(실제 경로) 기준이다. 목록 항목이 나중에 생긴 경로면 그때 실제 경로로 다시 계산된다(프로필은 실행마다 만든다).
- 실제 runner로 실험 executor를 돌린 확인은 하지 않았다(합성 executor만).

## 사용자 확인 필요

1. 목록 44개 확인·수정(특히 빠진 추적 안 된 자료 65개 후보와 이름 규칙에 안 걸리는 봉인 자료 위치). 확인 뒤 `status`를 바꾼다.
2. `tools/experiments/*holdout*/` 같은 코드 폴더를 목록에 넣을지.

## 롤백

`git revert 740c90f f13531d`(이 task 문서 커밋도 함께 되돌리려면 그 SHA 추가). 되돌리면 sandbox는 봉인 경로를 다시 읽을 수 있다(이전 상태).
