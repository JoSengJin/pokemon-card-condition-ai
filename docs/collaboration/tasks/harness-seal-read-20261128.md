# harness-seal-read-20261128 — executor sandbox의 봉인 자료 읽기 차단

- 브랜치: `claude/harness-seal-read-20261128`(분기 `0da3cb7`, 하네스 통합 브랜치). main 미통합·push 안 함.
- 증거 수준: **구현 완료 + 합성 시험**(임시 폴더의 가짜 봉인 파일, 실제 `sandbox-exec` 하위 프로세스). 실제 실험·학습·평가 실행 0건, 모델 누락·오탐 변화 없음.
- 봉인 자료 내용(이미지·JSON)은 열지 않았다. 목록은 파일 이름만으로 만들었다.

## 문제(변경 전)

1. `harness/sandbox.py` 프로필이 `(allow default)` + `(deny file-write*)`라서 실험·학습·평가 executor가 저장소의 봉인 자료를 읽을 수 있었다.
2. `harness/claude_perm.py` `FORBIDDEN_PARTS=("gold","seal")`은 입력 복사(stage_inputs)에만, 이름 기준으로만 걸려 holdout·independent·d1 등은 못 막았다.

### 독립 검증 결함(2026-11-28, 1차 구현 `740c90f` 대상, 재현 스크립트 scratchpad `seal-verify/probe.py`·`probe2.py`)과 수정

| 결함 | 재현 | 수정 커밋 |
|---|---|---|
| 대소문자 우회(필수): stage_inputs의 경로 문자열 비교(commonpath)가 대소문자를 구분해 `VAULT/a.json`·`Vault/a.json`이 목록 `vault`를 통과해 복사됨(APFS 기본은 대소문자 무시). 원본 폴더·하네스 root 비교에도 같은 약점(기존 결함) | 내가 다시 실행해 재현(복사됨) | `cbe25fe`: 원본 폴더·하네스 root·봉인 경로 포함 여부를 (장치, inode)로 비교(`_ids`). sandbox 쪽은 대소문자·NFD 변형도 이미 거절됨을 실측(규칙 경로는 실제 경로와 대소문자가 달라도 맞음) |
| git 우회(필수): sandbox 안 `git -C <src> show HEAD:vault/a.json`이 봉인 파일 내용 출력(.git을 막지 않음) | 재현(내용 출력) | `6c564d4`: `sealed_paths`가 각 기준 폴더의 `.git`, worktree면 `.git` 파일의 gitdir와 그 안 commondir(공통 git 폴더)도 돌려준다. 형식을 모르는 `.git` 파일은 ValueError |
| 호출 깊이 5 > 4: `runner.main → drain → _execute → run_one → profile → sealed_paths` | — | `2e7c583`: `sealed_paths` 호출을 `profile` 밖(`available`·`sandboxed`·`run_one`)으로 올림. `profile(root, run_dir, sealed)`는 빈 목록이면 ValueError |

## 변경

| 파일 | 내용 | 함수 수(전→후) |
|---|---|---|
| `harness/sealed_paths.json`(새 파일) | 봉인 경로 목록 44개(저장소 기준 상대 경로). `status`: 자동 추정 초안, 사용자 확인 전(완전성 미확인) | — |
| `harness/claude_perm.py` | `SEALED_LIST`, `sealed_paths(bases)`(O_NOFOLLOW로 열고 일반 파일·형식 검사, bases 기준 realpath 목록 + 각 base의 git 폴더(.git, worktree면 gitdir·commondir), 오류는 ValueError). `_ids(paths)`((장치, inode) 집합). `stage_inputs`가 시작할 때 목록을 읽고(저장소·source_root 기준) 입력과 그 상위 폴더의 (장치, inode)가 목록·하네스 root와 겹치거나 원본 폴더와 안 겹치면 거절. 이름 규칙 유지(이중 차단) | 4→6 |
| `harness/sandbox.py` | `profile(root, run_dir, sealed)`가 넘겨받은 경로마다 `(deny file-read* (subpath "<realpath>"))`, 빈 목록이면 ValueError. `available`·`sandboxed`는 `sealed_paths([REPO])`, `run_one`은 시작할 때 `sealed_paths([REPO, HARNESS_SOURCE_ROOT])`(runner가 넣은 값)를 읽어 넘긴다. 목록 오류면 ValueError → `available()` False, `run_one`은 아무것도 만들거나 실행하지 않는다 | 5→5 |
| `tests/test_harness_sandbox_read.py`(새 파일) | 아래 시험 4개 | 7 |
| `tests/test_harness_sandbox_git.py`(새 파일) | 아래 git 시험 2개 | 4 |
| `tests/test_harness_sandbox.py`·`test_harness_sandbox_deny.py`·`test_harness_exec_boundary.py` | `profile` 직접 호출에 새 인자(실제 목록 `claude_perm.sealed_paths([sandbox.REPO])`)만 넘기도록 바꿈. 검사 내용은 그대로 | 변화 없음 |

호출 깊이(시작 함수 기준, 파일을 넘어 셈):
- `runner.main → drain → _execute → run_one → profile` = 4, `… → run_one → claude_perm.sealed_paths` = 4, `… → run_one → safefs.*` = 4(변경 전과 같음). `profile`은 말단이 됐다.
- `runner.main → sandbox.available → profile·sealed_paths` = 2, `runner.main → sandbox.sandboxed → profile·sealed_paths` = 2.
- `runner.main → drain → _execute → claude_perm.stage_inputs → sealed_paths·_ids·safefs.replace_new` = 4.
- `supervisor.run → claude_job.execute → claude_perm.stage_inputs → sealed_paths·_ids` = 3(`supervisor.py` 문서의 execute 최대 깊이 3은 그대로).
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
| (같은 시험, 검증 결함 뒤 추가) | sandbox 안 대소문자 변형 `VAULT/A.json` 읽기 `EPERM` |
| `test_stage_inputs_refuses_listed_paths_by_real_path_and_keeps_name_rule` | 이름에 봉인 표시가 없는 `vault/a.json`·`loose.json`·링크 항목 아래 `hidden/b.json` 입력 거절, 대소문자 변형 `VAULT/a.json`·`Vault/A.JSON`·`LOOSE.json`, NFC 목록 항목 `café`의 NFD 입력 거절, 대소문자만 바꾼 하네스 root 경로(`ROOT/tasks/k`) 입력 거절, 정상 입력 복사, `gold/` 이름 규칙 유지 |
| `test_missing_linked_or_malformed_list_fails_closed` | 목록 없음·링크·JSON 아님·목록 형식 아님·빈 목록·절대 경로·`..`·따옴표·숫자·문자열·`a//b` 11종: `sealed_paths` ValueError, `available()` False, `run_one` ValueError(산출물 없음), `stage_inputs` ValueError |
| `test_tracked_list_loads_and_holds_only_data_paths` | 추적 목록이 읽히고 소스·문서 경로가 없으며, 실제 목록으로 만든 프로필이 이 macOS에서 적용됨(`available()` True). `profile`은 빈 목록이면 ValueError |
| `test_git_show_and_direct_git_reads_are_refused_for_plain_repo_and_worktree` | 임시 git 저장소(main)와 그 worktree(wt, `.git`이 파일)를 각각 `HARNESS_SOURCE_ROOT`로 두고 sandbox 안에서 `git show HEAD:vault/a.json`(main·wt 둘 다), `.git/objects/<blob>` 직접 읽기, `.git/HEAD`, worktree gitdir의 `HEAD` 모두 거절, 정상 파일 읽기 성공 |
| `test_unknown_dot_git_file_fails_closed` | `gitdir: ` 줄이 아닌 `.git` 파일이면 `sealed_paths` ValueError |

결함 주입(일부러 고친 뒤 시험 실행, 끝나면 되돌림). 로그: scratchpad `logs/seal-read-fault-F1..F11.log`

| 주입 | 잡은 시험 |
|---|---|
| F1 프로필에서 `deny file-read*` 줄 제거 | sandbox 읽기 시험 실패 |
| F2 `stage_inputs`의 목록 검사 제거 | stage_inputs 시험 실패 |
| F3 목록 없음을 빈 목록으로(fail-open) | fail-closed 시험 실패 |
| F4 realpath 대신 normpath | sandbox 읽기 시험·stage_inputs 시험 실패 |
| F5 봉인 포함 비교를 경로 문자열(commonpath)로 되돌림 | stage_inputs 시험 실패(`VAULT/a.json` 통과) |
| F6 하네스 root 비교를 경로 문자열로 되돌림 | stage_inputs 시험 실패(`ROOT/tasks/k` 통과) |
| F7 `profile`의 빈 목록 거절 제거 | 추적 목록 시험 실패 |
| F8 `run_one`이 목록 오류를 무시 | fail-closed 시험 실패 |
| F9 git 폴더 추가 전부 제거(수정 전 상태) | git 시험 2개 실패(main·wt 모두 `git show` 내용 노출, 객체·HEAD 읽힘) |
| F10 commondir 처리 제거 | git 시험 실패(wt 기준일 때 main 객체 읽힘, `git show` 노출) |
| F11 `.git` 파일 형식 검사 제거 | `.git` 파일 fail-closed 시험 실패 |

수정 전 실패 로그: `logs/seal-read-before-fix.log`(4개 오류: `SEALED_LIST` 없음).

전체 하네스 시험(대상 `740c90f`, `full-suite.lock` 획득 뒤 1회씩, `python -m unittest discover -s tests -p "test_harness_*.py"`):

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 555 통과, 실패 0 (340초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-venv312.log` |
| `/usr/bin/python3`(3.9) | 555 통과, 실패 0 (382초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-py39.log` |

분기 `0da3cb7`의 시험 정의 551개(`git grep -c "    def test_"`) + 새 시험 4개 = 555. 기존 시험은 고치거나 지우지 않았다.

전체 하네스 시험 2회차(대상 `6c564d4`, 검증 결함 수정 뒤, `full-suite.lock` 획득 뒤 1회씩): **두 Python 모두 557개 중 실패 2**(나머지 통과).

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 557 실행, 실패 2 | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-r2-venv312.log` |
| `/usr/bin/python3`(3.9) | 557 실행, 실패 2 | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/harness-seal-read-r2-py39.log` |

실패: `test_harness_b5_e2e_synthetic…test_real_adapter_in_the_sandbox_cannot_record_so_the_chain_stops_at_the_first_experiment`(기대 INTERRUPTED, 실제 FAILED), `test_harness_b5_experiment_run_faults…test_supervisor_entry_point_runs_the_registered_adapter_in_the_sandbox`(completed 기대 charge·INTERRUPTED, 실제 charge·cancel·FAILED). 원인: 위 한계의 어댑터 안 git 대조(실패 기록 `code_sha를 판별할 수 없다`). 확인: `2e7c583`의 `claude_perm.py`(git 거절 전)로 두 모듈을 돌리면 6개 통과(`/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-read-git-conflict-without-gitdeny.log`). 두 시험은 고치지 않았다(완화 금지).

## (나) 적용: runner 검증 결과 전달 (2026-11-28, 커밋 `5f8f220` 구현 · `3c6840f` 시험 · `ac87afd` 문구)

증거 수준: **구현 완료 + 합성 시험**(가짜 저장소·가짜 봉인 목록·실제 `sandbox-exec`). 실제 실험·학습·평가 0건, 봉인 자료 내용 열람 0건, 모델 누락·오탐 변화 없음. 사용자 결정 원문 요약: `artifacts/harness-resume-20261127/decisions-integration-seal-20261128.md`.

방식: runner(sandbox 밖)가 기존 `dedupe.verify_code` 직후 `experiment_exec.record_code`로 **`code_sha` 커밋의 파일별 git blob SHA 목록**(`git ls-tree -r -z`, 추적 파일, 현재 2488개·모드 포함)을 `<작업 폴더>/code-check.json`에 쓴다. 어댑터(`execute`)는 `check_code`로 그 파일만 읽어 git 없이 각 파일의 blob SHA(`sha1(b"blob N\0"+내용)`, 링크는 `readlink`, 모드 비트 포함)를 다시 계산해 전부 같은지 본다. 하나라도 다르거나 읽을 수 없으면 `refused`(실행 안 함). 메인 권고의 `git ls-files -s` 대신 `ls-tree <code_sha>^{tree}`를 썼다: 인덱스가 아니라 계약의 `code_sha` 커밋에 직접 묶여서 같은 보장(검증 뒤 작업 트리 변경 차단)을 주고 `code_sha` 일치도 함께 성립한다.

- 고정 위치: 작업 폴더(`root/tasks/<키>/code-check.json`). sandbox는 쓰기 거절(덮어쓰기·새 파일·교체 모두 EPERM, 실제 sandbox 시험). 경로는 runner가 넣는 환경변수 `HARNESS_CODE_CHECK`(기존 `HARNESS_SOURCE_ROOT`와 같은 방식, 계약 작성자가 정할 수 없음). 어댑터는 `O_NOFOLLOW`·일반 파일·링크 수 1·파일 이름·`realpath(path)==path`를 확인한다. `run()`을 직접 부르는 경로(기존 시험)는 예전처럼 `verify_code`를 직접 한다(`checked=False` 기본).
- 대조 범위(기록 범위): 봉인 경로 목록(`harness/sealed_paths.json`) 아래 추적 파일은 sandbox가 읽을 수 없어 대조에서 빼고 `sealed_skipped`에 남긴다. **현재 목록(144항목, D4 반영 뒤) 기준 실측(HEAD `4a5a890`): 2488개 대조 + 134개 제외**(모두 `artifacts/` 아래, .json 56·.txt 50·.md 17·.py 8·.html 3; .py 8개는 옛 holdout 폴더의 worker). 그 파일은 sandbox 안에서 읽기·실행이 거절되어(`test_sealed_reads_are_refused_in_sandbox_…`) sandbox 안 어댑터·`./experiment`가 실행할 수 없다. 이 저장소에서 sandbox 안 `check_code` 0.35초(비 sandbox 기록 0.28초, 44항목 목록일 때 측정). (이전 문서의 2522/97은 44항목 목록 기준이었다.)
- 실행 파일 `experiment`가 목록에 없으면 거절(추적되지 않은 실행 파일 방지).

구조(`PAIR_CODING.md`): `harness/experiment_exec.py` 함수 5→7(`record_code`·`check_code` 추가, 람다 없음), `harness/runner.py` 5→5(한 줄 추가). 호출: `runner.main → drain → _execute → experiment_exec.record_code → claude_perm.sealed_paths·jsonio.write_json` = 4, `execute → check_code` = 2(말단). 시험 새 파일 3개(각 함수 3·4·3개).

### 변경 파일·커밋
| 커밋 | 내용 |
|---|---|
| `5f8f220` | `harness/experiment_exec.py`(record_code·check_code·run `checked`·execute), `harness/runner.py`(_execute가 record_code 호출·환경변수) |
| `3c6840f` | `tests/test_harness_code_check.py`(3)·`test_harness_code_check_run.py`(2)·`harness_code_check_kit.py` |
| `ac87afd` | experiment_exec 문서 문구 |

### 시험
- 기존 실패 2개를 **기대값 변경 없이** 통과: `test_harness_b5_e2e_synthetic…test_real_adapter_in_the_sandbox_cannot_record_so_the_chain_stops_at_the_first_experiment`, `test_harness_b5_experiment_run_faults…test_supervisor_entry_point_runs_the_registered_adapter_in_the_sandbox`. 기존 시험 파일은 하나도 고치지 않았다(`git diff 521cb6b HEAD --stat`: 새 시험 3개 + 소스 2개).
- 새 시험 5개: 기록·범위(`sealed_skipped`), 반례 19종(환경변수 없음·결과 파일 없음·JSON 아님·키 추가·링크·하드 링크·다른 이름·링크 폴더·code_sha 불일치·source_root 불일치·검증 뒤 파일 1개 내용 변경(같은 길이)·삭제·링크로 교체·모드 변경·링크 대상 변경·experiment 목록 누락·`..` 경로·잘못된 모드·잘못된 blob), 계약 필드·staging 폴더로 위조 결과 제공 시도(무시됨), runner가 기록 실패(submodule 항목) 시 executor를 부르지 않고 `not_started`, 실제 sandbox 안에서 작업 폴더 쓰기 거절 + git은 실패(`git rev-parse` 비0)인데 `check_code`는 통과 + 밖에서 파일 변경 뒤 거절.
- 결함 주입(고친 뒤 시험, 끝나면 `git checkout`으로 되돌림, 스크립트 `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/seal-nah-inject.py`, 로그 `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-nah-fault-*.log`): blob 대조 제거·code_sha 대조 제거·source_root 대조 제거·하드 링크 허용·`O_NOFOLLOW` 제거(단독은 `realpath` 검사가 겹쳐 잡지 못함 → 둘 다 제거하면 잡음)·realpath 검사 제거·파일 이름 검사 제거·experiment 필수 제거·모드 대조 제거·환경변수 없음 통과·봉인 제외를 전부로 확대·submodule 항목 허용·runner 기록 제거·sandbox가 root에 쓰기 허용 — 14개 모두 시험이 잡았다(N5 단독 제외, 조합으로 잡음).
- 전체 하네스 시험(대상 `ac87afd`, `full-suite.lock` 획득 뒤 1회씩, `python -m unittest discover -s tests -p "test_harness_*.py"`): **두 Python 모두 562 통과, 실패 0**(557 + 새 5).

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 562 통과 (345초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-nah-venv312.log` |
| `/usr/bin/python3`(3.9) | 562 통과 (411초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-nah-py39.log` |

### 한계·미확인(이번 변경)
- 환경변수 `HARNESS_CODE_CHECK`는 runner 프로세스가 정한다. sandbox 밖 같은 사용자 프로세스(Codex·셸·다른 runner)가 작업 폴더나 환경을 바꾸는 것은 막지 못한다(D-7 OS 사용자 분리 범위, 기존 `HARNESS_SOURCE_ROOT`와 같은 신뢰 수준).
- 대조는 어댑터 실행 직전 한 번이다. 대조와 `./experiment` 실행 사이에 sandbox 밖에서 파일을 바꾸는 것(같은 사용자)은 막지 못한다. sandbox 안 프로세스는 저장소에 쓸 수 없다.
- 줄바꿈 변환·`.gitattributes` 필터가 있는 저장소는 blob SHA가 어긋나 항상 거절된다(fail-closed, 이 저장소는 해당 설정 없음: `.gitattributes`·`core.autocrlf` 없음 확인).
- 추적되지 않은 파일(untracked)은 기존 `verify_code`처럼 대조하지 않는다(`experiment`가 import하는 untracked 파일은 막지 못함).
- 목록 완전성 미확인·미추적 후보 65개 보호 범위·AGENTS.md 별도 검토·최신 main 충돌 확인은 이 작업 범위 밖이라 하지 않았다(통합 전 필수 항목으로 남음). 실제 `./experiment`를 sandbox 안에서 돌려 보지 않았다(합성).
- 목록 완전성이 미확인이므로 봉인 읽기 차단을 완전 보호로 보고하지 않는다(위 기존 한계 유지).

### 롤백(이번 변경만)
`git revert ac87afd 3c6840f 5f8f220` → 어댑터의 sandbox 안 `verify_code`로 돌아가 실험 어댑터가 다시 모든 실험을 `refused`하고 위 2개 시험이 다시 실패한다(6c564d4 유지 시). 6c564d4·cbe25fe는 건드리지 않았다.

## D4 사용자 결정 반영: 봉인 범위 확대·저장소 밖 사본 차단 (2026-11-28 밤, 커밋 `29e2e0f`(구현)·`8670d3b`(시험)·`2fda4c1`(보강))

증거 수준: **구현 완료 + 합성 시험**(임시 git 저장소·가짜 목록·실제 `sandbox-exec`, 실제 목록으로는 이름·형식·실행 시간만). 봉인 내용 열람 0건, 실제 실험·학습·평가 0건, 모델 누락·오탐 변화 없음. 입력: `artifacts/harness-resume-20261127/session-6702a9/seal-scope/final-list.json`(140)·`outside-roots.txt`(153).

변경(최소):
1. `harness/sealed_paths.json`: 44 → **144항목**(468·C4·350·D1·D1b·11-19 포함, 소진만으로 해제하지 않음, 미확인 42개는 차단). final-list의 140개 중 **설명문이던 4항목은 실제 경로 규칙으로 풀었다**(그대로 쓰면 존재하지 않는 글자 그대로의 경로라 아무것도 막지 못한다): `artifacts/experiments/*/reference.json`·`.../observations.json`, 실험 폴더 `20261116T104632-5f5ebb42`·`20261116T131107-9c2af49d`(폴더 전체, "sealed-*.json" 용도 미확인), `data/*independent*-review-*.jsonl*`(.bak 포함), `artifacts/reports-20261031/holdout*.html`·`artifacts/edge-back-add*-20261031/holdout-rows.json`·`artifacts/experiments/20261031T093842-2ba28932/holdout_scores.json`. `*`가 든 항목은 `claude_perm.sealed_paths`가 실행 시점에 glob으로 풀어 그 시점에 있는 파일을 `stage_inputs`·`record_code`에 쓰고, sandbox 프로필에는 **regex 규칙**으로 넣는다(아래 "독립 검증 수정" F3, 프로필을 만든 뒤 sandbox 밖에서 생긴 파일도 막는 것을 실측). 새 항목 추가는 목록 갱신이다. (`?`·`[`는 형식 오류.) 
2. `harness/sealed_outside_roots.json`(새 파일, 루트 153개)과 `claude_perm.outside_roots`(함수 6→7): sandbox 프로필이 각 루트 **전체** 읽기를 거절한다(`sandbox.profile(..., outside)`, 140×153 규칙 대신 루트 단위). 현재 저장소(REPO)·`HARNESS_SOURCE_ROOT`와 같은 루트는 뺀다(조상인 루트는 아래 F1처럼 실행 차단). 실행 때마다(sandbox 밖) `git worktree list --porcelain`에 있는 worktree도 추가로 거절한다: **REPO 저장소는 등록된 모든 worktree, source_root는 그 폴더 안에 중첩된 worktree만**(다른 저장소의 형제 worktree는 모른다). 목록 파일 없음·링크·형식 오류·git worktree 목록 읽기 실패는 fail-closed(`available()` False, `run_one`·`sandboxed`는 ValueError, 아무것도 실행하지 않음). `sandbox.py` 함수 수 5→5(`profile`에 인자 1개 추가, 호출처 3곳).
3. 이 python의 prefix(`sys.prefix`·`sys.exec_prefix`, 예: 기본 checkout의 `.venv`)가 거절 루트 안에 있으면 그 폴더만 다시 허용한다(봉인 목록 거절이 그 뒤 규칙이라 우선). 이유: REPO가 기본 checkout이 아닌 worktree일 때 기본 checkout 전체가 거절 대상이 되어 python 자신을 못 읽는다. 하네스 root·실행 폴더가 거절 루트 안이면 프로필을 만들지 않는다(ValueError).
- 호출 깊이: `runner.main → drain → _execute → sandbox.run_one → claude_perm.outside_roots` = 4(말단). 기존 구조 유지.

실측: 프로필 14줄·약 40KB(봉인 경로 142 + 거절 루트 161개). `sandbox-exec` python 실행 0.09초(봉인만일 때 0.05초), 프로필 생성 0.04초, `sandbox.available()` 0.1초. 시험이 10초 상한으로 고정(`test_real_lists_keep_sandbox_exec_working_and_fast`).

시험(새 파일 `tests/test_harness_seal_scope.py`, 5개, 함수 7개): glob 풀이·나중에 생긴 파일 포함·`?`/`[` 거절 / 거절 루트 = 목록 + git worktree에서 온 것(목록에 없는 wt2)·자기 루트·조상 제외·기준을 바꾸면 자기 루트가 바뀜·목록 오류 12종·git 실패 단독 거절 / 실제 sandbox에서 다른 루트·worktree 읽기·stat·목록 거절, 자기 저장소 읽기 성공, 봉인 목록 거절, python 환경 예외, 하네스 root·실행 폴더가 거절 루트 안이면 프로필 거절, `run_one`이 거절 루트를 프로필에 넘김 / 실제 목록(144·153, 필수 항목 7종 포함, 소스·문서 경로 없음)으로 sandbox 실행 시간·기본 checkout 거절(이 worktree가 기본 checkout이 아닐 때) / 목록 없음이면 `available()` False·`run_one`·`sandboxed` ValueError·산출물 없음. 기존 시험 파일은 고치지 않았다.
결함 주입 14개(스크립트 `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/seal-d4-inject.py`, 로그 `logs/seal-d4-fault-*.log`) 전부 시험이 잡았다: glob 미풀이·목록 루트 무시·worktree 목록 무시·자기/조상 미제외·프로필 deny 제거·python 예외 제거·root가 거절 루트 안 허용·목록 없음 통과·git 실패 무시·`run_one`/`available`/`sandboxed`가 거절 루트 미전달·`?[` 허용·비정규 경로 허용. (처음 D9·D10은 못 잡아 시험을 보강한 뒤 다시 잡음.)

전체 하네스 시험(대상 `2fda4c1`, `full-suite.lock` 획득 뒤 1회씩): **두 Python 모두 567 통과, 실패 0**(562 + 새 5).

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 567 통과 (366초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-d4-venv312.log` |
| `/usr/bin/python3`(3.9) | 567 통과 (412초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-d4-py39.log` |

### D4 독립 검증 수정(Opus 신뢰 경계 검증 결과, 커밋 `ef6931f`(구현)·`4a5a890`(시험))

증거 수준: 합성 시험(임시 저장소·실제 `sandbox-exec`). 신뢰 경계 자체의 우회는 없었고 D4 범위 결함 4건 + 추가 1건을 고쳤다.

| 결함 | 수정 | 시험(`tests/test_harness_seal_scope_v2.py`) |
|---|---|---|
| F1 기준 폴더의 **조상** 루트를 뺐다 → REPO·source_root가 `main/.claude/worktrees/x`이면 기본 checkout 전체가 열림 | 루트가 기준 폴더와 같으면 빼고, **조상이면 ValueError**(`available()` False, `run_one`·`sandboxed`·`stage_inputs` 실행 안 함) | 목록·git worktree 조상 둘 다 거절, 같은 루트는 제외, 중첩 worktree를 REPO로 두면 `available()` False |
| F2 `stage_inputs` 봉인 집합에 저장소 밖 루트가 없어 차단된 worktree 안 사본이 `in/`으로 복사됨 | 봉인 집합에 `outside_roots([REPO, base])` 추가(호출 깊이 4, 함수 수 7 유지) | 목록 루트 안·source_root 안 중첩 worktree 안 입력 거절, 정상 입력은 복사 |
| F3 `*` glob이 프로필 생성 때 한 번만 풀려 실행 중 새로 생긴 파일(예: 새 실험 reference.json)이 읽힘 | `*`가 든 항목은 SBPL **regex 규칙**(`^<경로>(/.*)?$`, `*`는 슬래시 제외 한 조각, 나머지 정규식 문자는 이스케이프)으로 프로필에 넣는다. **실측**: sandbox 실행 중 밖에서 만든 `exp/new/ref.json`·대문자 변형 `EXP/NEW/REF.JSON`·`Ref.json` 변형 모두 EPERM, 같은 폴더의 다른 파일은 읽힘, 이름에 `(+)`가 든 경로도 글자 그대로 | 실시간 생성 시험(regex 이스케이프 포함) |
| F4 `available`·`sandboxed`가 `[REPO]`만 기준 | 둘 다 `HARNESS_SOURCE_ROOT`도 기준에 넣고, `runner.main`이 `--source-root`를 그 환경변수로 먼저 설정(최소 변경) | spy로 3회 호출 모두 source_root의 봉인 경로를 받음, main이 환경 설정 |
| F5(추가) 대화 기록에 봉인 경로 이름이 나옴 | 거절 루트에 `~/.claude/projects`·`~/.claude-mem`·`~/.codex/sessions` 추가(목록 153→156, 기본 차단·내용 미열람). sandbox 안 python·저장소 읽기는 이 폴더 없이 되고(시험, stat만 확인) 전체 하네스 시험도 통과 | 목록 포함·stat 거절·python/저장소 읽기 성공 |

source_root 쪽 worktree 목록은 **그 폴더 안에 중첩된 것만** 더한다. 이유: 기존 시험 `test_git_show_and_direct_git_reads_are_refused_for_plain_repo_and_worktree`가 source_root 저장소의 형제 worktree(`wt`) 읽기가 성공하는 것을 기대하며, 기대값은 바꾸지 않았다(바꾸려면 별도 승인).

결함 주입 11개(스크립트 `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/seal-v2-inject.py`, 로그 `logs/seal-v2-fault-*.log`): 조상 검사 제거·stage_inputs 거절 루트 제거·source_root 중첩 worktree 제거·`*`를 글자 그대로 subpath·패턴 문자열 미추가·`available`/`sandboxed`가 REPO만 기준·`runner.main`이 환경 미설정·대화 기록 루트 제거·regex 이스케이프 제거 모두 시험이 잡았다. 반환 필터에서 조상 제외를 되살리는 주입(V1b)은 위 검사가 먼저 막아 동치라 잡히지 않는다(중복 방어). V8은 처음 못 잡아 시험을 고친 뒤 잡았다.

전체 하네스 시험(대상 `4a5a890`, `full-suite.lock` 획득 뒤 1회씩): **두 Python 모두 572 통과, 실패 0**(567 + 새 5).

| Python | 결과 | 로그 |
|---|---|---|
| `.venv/bin/python`(3.12) | 572 통과 (375초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-v2-venv312.log` |
| `/usr/bin/python3`(3.9) | 572 통과 (470초) | `/private/tmp/claude-501/-Users-jueun-WebstormProjects-pokemon-card-condition/6702a9d6-a8c8-4aa0-96a9-bc66158eb3db/scratchpad/logs/seal-v2-py39.log` |

정정(과장 문구): "나중에 생긴 파일도 막는다"는 **프로필 regex로 sandbox 실행 중 생긴 파일에만** 해당한다. `stage_inputs`·`record_code`는 그 시점의 glob 결과만 쓴다(입력은 존재해야 복사하므로 영향 없음). "다른 worktree 거절"은 **`git worktree list`에 등록된 것**(REPO 저장소 전부, source_root 안 중첩분)과 목록의 153+3개뿐이다. 등록 안 된 복제본·`cp -r`·압축 해제본은 막지 못한다.

### 한계·실제 실행 전 사람이 확인할 것(보장 못 하면 실행 보류)
- **목록에 없는 새 사본은 자동으로 막을 수 없다.** 막히는 것은 (a) `sealed_outside_roots.json`의 153개, (b) 실행 시점 `git worktree list`에 등록된 worktree, (c) `sealed_paths.json`이 가리키는 REPO·source_root 아래 경로뿐이다. git에 등록되지 않은 `cp -r`·clone·scratchpad 복제본·압축 해제본은 `git worktree list`에 없어 자동으로 못 잡는다. **실제 실험을 시작하기 전에 사람이 확인할 항목**: 마지막 조사(2026-11-28) 이후 새로 만든 복제본·worktree가 있는지(`outside-roots.txt` 조사를 다시 돌려 목록과 대조), 있으면 이 파일에 추가하고 커밋. 이 확인 없이는 "저장소 밖 사본까지 차단"이라고 보고하지 않는다. 사본 삭제·새 관리 시스템은 만들지 않았다.
- worktree 목록은 REPO 저장소는 전부, `HARNESS_SOURCE_ROOT`는 그 폴더 안에 중첩된 것만 읽는다. source_root가 다른 저장소면 그 저장소의 형제 worktree(폴더 밖)는 모른다.
- **실제 실행(C 트랙) 전 필수 확인**: (1) 사본 조사 갱신(등록 안 된 새 복제본), (2) REPO·source_root가 기본 작업 폴더인지(조상 루트가 있으면 실행이 차단된다), (3) `artifacts/experiments/*/reference.json` 항목 처리 결정, (4) 목록 완전성(이름·문서 기준, 내용 미확인) 사용자 확인.
- 이 worktree가 기본 checkout이 아니므로 시험은 기본 checkout을 "다른 worktree"로 거절한다. **기본 checkout에서 돌릴 때** 봉인 경로는 REPO 기준 `sealed_paths.json`으로 막히고(아직 이 환경에서 실행해 보지 않음), 기본 checkout 안의 추적되지 않는 봉인 자료는 목록의 glob·경로가 이름으로 맞아야 막힌다.
- **`artifacts/experiments/*/reference.json`·`observations.json` 전체 차단(미확인 42개의 한 항목)은 나중에 연결할 sandbox 안 실제 `./experiment` worker가 자신의 실험 폴더 reference.json·이전 실험 결과를 읽는 것도 막는다**(worker가 `CARD_CONDITION_EXPERIMENT_REFERENCE` 정답을 읽음). C 트랙 연결 전에 사용자가 이 항목을 정해야 한다(내가 풀지 않았다).
- final-list의 `dropped`(편입 기록 확인 2개: `artifacts/holdout-h-head3-20261031`, `artifacts/surface-spotcheck-20261101/key-sealed.json`)는 넣지 않았다. 목록 완전성은 이름·문서 기준이고 파일 내용은 열지 않았으므로 완전 보호로 보고하지 않는다.
- 같은 사용자의 sandbox 밖 프로세스는 여전히 막지 못한다(D-7).

### 롤백(D4만)
`git revert 4a5a890 ef6931f 2fda4c1 8670d3b 29e2e0f`(검증 수정 F1~F5 포함) → 봉인 목록 44항목·저장소 밖 루트 차단 없음으로 돌아간다(위 (나) 변경은 유지).

### 부록: 목록 항목 분류와 근거(final-list.json, 이름·문서 기준; 항목 수는 조사 proposal 기준 140, 위 설명문 4항목은 실제 경로로 풀어 144)
| 구분 | 분류 | 항목 수 | 근거(조사 proposal 첫 항목, 문서·키 이름만) |
|---|---|---|---|
| keep | 미소진 봉인(C4 보류 정답) | 7 | artifacts/c4-expansion-20261103/MANIFEST.json 키 rule: holdout은 측정기 동결 전 개발 사용 금지; CLAUDE_HANDOFF_20261104.md:7 (C4 포기 → 보류 미사용) |
| keep | 소진된 독립 보류 또는 그 평가 행(답·점수) | 24 | docs/collaboration/CLAUDE_HANDOFF_20261103.md:53, CLAUDE_HANDOFF_20261104.md:44 (소비된 보류, 재사용 금지); 정책 확인 필요: 소진된 옛 보류를 계속 막을지(HOLDOUT.md는 학습·튜닝 금지, 일부는 학습 편입 기록 있음) |
| keep | 봉인(D1, 1회 평가했지만 개발 사용 영구 금지) | 2 | docs/collaboration/D1_TESTSET_PLAN_20261103.md:21,25 (ax+새 intake, 봉인 뒤 개발·선택·임계·원인분석 금지); artifacts/ebay-intake-20261103-{ax,az,ba..bd}/HOLDOUT.md:1 |
| keep | 봉인(D1b 표면 보충, 후보 B 1회 평가 뒤 소진) | 2 | artifacts/d1b-surface-20261104/SEALED.json 키 label_file_sha256=surface-holdout2-20261103/answers.txt; docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | 미소진 C4 보류 라벨 화면 | 11 | artifacts/c4-expansion-20261103/MANIFEST.json 키 rule: holdout은 측정기 동결 전 개발 사용 금지; CLAUDE_HANDOFF_20261104.md:7 (C4 포기 → 보류 미사용) |
| add | 350장 봉인(소진, 학습 금지 유지) | 1 | docs/collaboration/reports/label-provenance-correction-20261126.md:25 (1차 독립 시험 350장 = cohort-seal-20261123, 정답 corner-independent-eval-20261123/answers.json); t5-eval-criteria-20261123.md:64,86 (소진 뒤에도 학습·튜닝 금지) |
| add | 미소진 봉인 468장 정답 파일 | 1 | docs/collaboration/plans/corner-cohort2-seal-criteria-20261123.md:3,5,21 (468장 봉인, 평가 전, 학습·튜닝 금지) |
| add | 350장 정답·평가 | 1 | docs/collaboration/reports/label-provenance-correction-20261126.md:25 (1차 독립 시험 350장 = cohort-seal-20261123, 정답 corner-independent-eval-20261123/answers.json); t5-eval-criteria-20261123.md:64,86 (소진 뒤에도 학습·튜닝 금지) |
| add | 350·468(예비분) 사진·라벨 원천 | 4 | artifacts/cohort-seal-20261123/seal-cohort.py:11 (v1·next·next2·next3 에서 구성; 경로 줄만 확인) |
| add | 468장 사진·라벨 원천 | 3 | artifacts/cohort2-seal-20261123/seal-cohort2.py:10-13,31 (1차 봉인 예비분 + corner-rank-independent-next[456] 에서 구성; 경로 줄만 확인) |
| add | 11-19 독립 평가 수집(사진·라벨), 평가 실행 여부 미확인 | 15 | docs/collaboration/tasks/ebay-independent-collection-plan-20261119.md:11 (새 독립 평가 수집, 봉인→동결→라벨 순서); reports/ebay-independent-back-labels-20261119.md:25 |
| add | D1 사진(git 추적 pairing/answers.txt 포함) | 1 | docs/collaboration/D1_TESTSET_PLAN_20261103.md:21,25 (ax+새 intake, 봉인 뒤 개발·선택·임계·원인분석 금지); artifacts/ebay-intake-20261103-{ax,az,ba..bd}/HOLDOUT.md:1 |
| add | D1 사진 | 4 | docs/collaboration/D1_TESTSET_PLAN_20261103.md:21,25 (ax+새 intake, 봉인 뒤 개발·선택·임계·원인분석 금지); artifacts/ebay-intake-20261103-{ax,az,ba..bd}/HOLDOUT.md:1 |
| add | D1 정답 원본(git 추적 답 8개) | 1 | artifacts/d1-testset-20261103/SEALED.json 키 label_file_sha256 = edge/cor/sur/obs/cen-answers.txt (키 이름만 확인) → 실제 파일은 artifacts/d1-labels-20261103/ (git 추적 8개) |
| add | 468장 정상 점검 사람 응답 | 1 | docs/collaboration/reports/label-provenance-correction-20261126.md:27-28,44 (468 정상 점검 응답·재시험 응답); cohort2-normal-label-check-prereg-20261124.md:9,86 |
| add | 468장 재시험 응답 | 1 | docs/collaboration/reports/label-provenance-correction-20261126.md:27-28,44 (468 정상 점검 응답·재시험 응답); cohort2-normal-label-check-prereg-20261124.md:9,86 |
| add | 350장 출처·식별자 | 1 | docs/collaboration/reports/corner-independent-d3-first-trial-analysis-20261123.md:51 |
| add | 468장 예비분 목록 | 1 | docs/collaboration/plans/corner-cohort2-prep-20261123.md:5,7 |
| add | D1 평가 행(답 포함 가능) | 1 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1 평가 행 | 4 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1 사용 시나리오 | 1 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1 평가 기록(reference.json=정답) | 1 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1 평가 기록 | 2 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1 엣지 구역 평가 기록 | 1 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | D1b 표면 평가 기록 | 1 | docs/collaboration/CLAUDE_HANDOFF_20261104.md:14,25,44 (D2 1회 평가, E2·F1에 D1 사용, D1 소비) |
| add | 350장 평가 기록(independent-result.json) | 1 | corner-independent-d3-first-trial-analysis-20261123.md (1차 시험); 파일 이름만 확인 |
| unknown | 소진 보류 + 학습 편입 기록 | 7 | performance-top3-consensus-20261030.md:483 (y·z·aa·ad·ae·af 를 후보 B 학습에 사용); CLAUDE_HANDOFF_20261103.md:53 (C5 aj~ao 후보 F 학습 편입) → 막으면 기존 학습 입력과 충돌 가능 |
| unknown | 10월 독립 검증(평가 완료) | 8 | docs/history/CHIEUT_INDEPENDENT_VALIDATION_20261012.md, INDEPENDENT_SIX_NORMAL_VALIDATION_20261011.md (10월 독립 검증, 평가 완료); 정책 확인 필요: 소진된 옛 보류를 계속 막을지(HOLDOUT.md는 학습·튜닝 금지, 일부는 학습 편입 기록 있음) |
| unknown | 소진 보류 평가 행·화면 | 7 | docs/collaboration/CLAUDE_HANDOFF_20261103.md:53, CLAUDE_HANDOFF_20261104.md:44 (소비된 보류, 재사용 금지); 정책 확인 필요: 소진된 옛 보류를 계속 막을지(HOLDOUT.md는 학습·튜닝 금지, 일부는 학습 편입 기록 있음) |
| unknown | 소진 보류(C5 ap~aw) | 3 | docs/collaboration/CLAUDE_HANDOFF_20261103.md:53, CLAUDE_HANDOFF_20261104.md:44 (소비된 보류, 재사용 금지); 정책 확인 필요: 소진된 옛 보류를 계속 막을지(HOLDOUT.md는 학습·튜닝 금지, 일부는 학습 편입 기록 있음) |
| unknown | 이름의 independent는 판정자 독립 뜻, 사진 172장 출처 미확인 | 1 | docs/collaboration/reports/independent-judgment-pilot-result-20261113.md:37 |
| unknown | C4 보류 ID 목록(정답 아님), C4 보류 사진의 실제 위치 미확인 | 1 | artifacts/c4-expansion-20261103/MANIFEST.json 키 rule: holdout은 측정기 동결 전 개발 사용 금지; CLAUDE_HANDOFF_20261104.md:7 (C4 포기 → 보류 미사용) |
| unknown | 소진 보류(§62) + 후보 B 학습 편입, HOLDOUT.md 없음 | 1 | performance-top3-consensus-20261030.md:483 (y·z·aa·ad·ae·af 를 후보 B 학습에 사용); CLAUDE_HANDOFF_20261103.md:53 (C5 aj~ao 후보 F 학습 편입) |
| unknown | 소진 보류(§62) + 후보 B 학습 편입 | 2 | performance-top3-consensus-20261030.md:483 (y·z·aa·ad·ae·af 를 후보 B 학습에 사용); CLAUDE_HANDOFF_20261103.md:53 (C5 aj~ao 후보 F 학습 편입) |
| unknown | 소진 보류(§65), HOLDOUT.md 없음 | 1 | performance-top3-consensus-20261030.md:494,501 |
| unknown | 소진 보류(§25), HOLDOUT.md 미추적 | 1 | performance-top3-consensus-20261030.md:218; HOLDOUT.md:1 |
| unknown | 소진 보류(§26) | 2 | performance-top3-consensus-20261030.md:227 |
| unknown | 소진 보류 + 후보 B 학습 편입 | 2 | performance-top3-consensus-20261030.md:483 (y·z·aa·ad·ae·af 를 후보 B 학습에 사용); CLAUDE_HANDOFF_20261103.md:53 (C5 aj~ao 후보 F 학습 편입) |
| unknown | HOLDOUT.md만 있음(수집 중단, 비어 있음) | 1 | docs/collaboration/CLAUDE_HANDOFF_20261103.md:51 |
| unknown | 모든 보류 평가 기록에 정답 사본이 들어감(전수 미확인) | 1 | AGENTS.md 실험 공통 기록: worker가 CARD_CONDITION_EXPERIMENT_REFERENCE 정답을 읽음 |
| unknown | 이름에 sealed, 용도 미확인 | 1 | 파일 이름만 확인 |
| unknown | 10월 독립 검증 라벨 | 1 | docs/history/CHIEUT_INDEPENDENT_VALIDATION_20261012.md, INDEPENDENT_SIX_NORMAL_VALIDATION_20261011.md (10월 독립 검증, 평가 완료) |
| unknown | 소진 보류 p·q·r 파생 | 1 | docs/collaboration/CLAUDE_HANDOFF_20261103.md:53, CLAUDE_HANDOFF_20261104.md:44 (소비된 보류, 재사용 금지) |
| unknown | 옛 worktree 압축본, 내용 미확인 | 1 | 파일 이름만 확인 |
| remove | 봉인 아님(개발 라벨을 재판정 중 가린 것) | 1 | performance-top3-consensus-20261030.md:384 (개발 라벨이 있던 사진 12장, 개발 라벨을 보여주지 않고(봉인)) |
| remove | 봉인 아님(설계 문서 BRIEF·FINAL·compare.py) | 1 | 파일 이름만 확인, 사진 0 |
| remove | 봉인 아님(NEXT_PROMPT.md 1개) | 1 | 파일 이름만 확인 |
| remove | 봉인 아님(worker.py 1개) | 1 | 파일 이름만 확인 |
| remove | 봉인 아님(plan·worker만) | 1 | 파일 이름만 확인 |

## 한계·미확인

- **같은 macOS 사용자의 sandbox 밖 프로세스**(Codex·대화형 Claude·사용자 셸)는 여전히 봉인 자료를 읽을 수 있다(OS 사용자 분리 D-7 범위).
- **sandbox 밖에서 미리 만든 하드 링크**는 목록 밖 이름으로 sandbox 안에서도 읽힌다(scratchpad 실측). sandbox 안에서 새로 만드는 하드 링크는 거절된다. stage_inputs는 링크 수 2 이상을 원래대로 거절한다.
- **목록 완전성 미확인.** 추적 파일 이름만 봤다. 기본 checkout의 추적 안 되는(gitignore) 자료 중 같은 이름 규칙에 걸리는 후보가 65개 더 있다(이름만 확인, 예: `artifacts/cohort-seal-20261123`, `artifacts/cohort2-seal-20261123`, `artifacts/chieut-independent-20261012`, `artifacts/ebay-independent-20261119-*`, `artifacts/corner-rank-independent-*`). 목록에 넣지 않았다. 후보 이름 목록: scratchpad `seal-read/untracked-main-candidates.json`(79개 중 추적 목록 밖 65개).
- 이름 규칙에 안 걸리는 봉인 자료(예: 봉인 350·468장이 다른 이름 폴더에 있다면)는 목록에 없다.
- `tools/experiments/*holdout*/`의 `plan.json`·`worker.py`는 코드로 보고 뺐다(봉인 자료 여부 사용자 확인 필요).
- sandbox 규칙은 경로(실제 경로) 기준이다. 이 macOS에서 대소문자·NFD 변형 경로도 거절됨을 실측했다. 목록 항목이 나중에 생긴 경로면 그때 실제 경로로 다시 계산된다(프로필은 실행마다 만든다).
- **git 사용 제한 — 기존 어댑터와 충돌(아래 "(나) 적용"으로 해결, 5f8f220).** 아래는 해결 전 기록이다. sandbox 안 executor는 저장소·`HARNESS_SOURCE_ROOT`의 git 폴더를 읽을 수 없어 그 저장소에서 `git`이 실패한다. "실제 executor는 git을 쓰지 않는다"는 전제는 틀렸다: 실험 어댑터 `harness/experiment_exec.py:110`이 sandbox 안에서 `dedupe.verify_code(task, workdir)`(git rev-parse·status·ls-files)로 code_sha를 다시 대조한다. 그래서 `6c564d4` 뒤 어댑터는 모든 실험을 `refused`(code_sha를 판별할 수 없다)로 거절하고(fail-closed, 실행 안 함), 기존 시험 2개가 실패한다(아래 전체 시험 2회차). runner는 sandbox 밖에서 같은 대조를 실행 직전에 이미 한다(`harness/runner.py:108`).
  - 고르는 길(사용자·메인 결정): (가) 어댑터 안 재대조를 빼고 runner 대조만 믿는다(sandbox가 저장소 쓰기를 막으므로 남는 틈은 sandbox 밖 같은 사용자 프로세스 = D-7 범위. 어댑터 재대조 시험의 기대도 바뀐다). (나) runner가 sandbox 밖에서 구한 대조 결과를 넘기고 어댑터는 그것만 확인한다. (다) git 폴더 거절을 되돌린다(`git revert 6c564d4`, git show 우회가 다시 열린다). git 폴더 읽기를 일부만 허용하는 방법은 없다(봉인 파일이 추적되어 있어 객체에 내용이 들어 있다).
  - 나중에 실제 `./experiment`·worker를 sandbox 안에서 연결할 때도 그 안에서 git을 쓰면 막힌다: 연결 전에 git 호출 여부를 확인한다.
- git 폴더는 저장소와 `HARNESS_SOURCE_ROOT` 기준만 막는다. 같은 저장소의 다른 복제본(다른 위치의 clone·백업, 다른 git 폴더를 가진 checkout)은 막지 않는다. `.git` 파일이 가리키는 폴더를 따라가므로 worktree는 막힌다.
- stage_inputs의 (장치, inode) 비교는 목록 항목이 지금 있는 경우에만 걸린다(없는 경로는 읽을 것도 없다).
- 실제 runner로 실험 executor를 돌린 확인은 하지 않았다(합성 executor만).

## 사용자 확인 필요

1. 목록 44개 확인·수정(특히 빠진 추적 안 된 자료 65개 후보와 이름 규칙에 안 걸리는 봉인 자료 위치). 확인 뒤 `status`를 바꾼다.
2. `tools/experiments/*holdout*/` 같은 코드 폴더를 목록에 넣을지.

## 롤백

`git revert 6c564d4 2e7c583 cbe25fe 740c90f f13531d`(task 문서 커밋 `b9e9ba3`·`e99ae14`와 이 문서 갱신 커밋도 함께 되돌리려면 그 SHA 추가). 일부만 되돌리면 해당 결함이 다시 열린다(6c564d4: git 우회, cbe25fe: 대소문자 우회). 모두 되돌리면 sandbox는 봉인 경로를 다시 읽을 수 있다(이전 상태).
