---
name: pair-coding
description: Codex·Claude 병렬 페어코딩 절차. 사용자가 "pair-coding 열기/시작/이어하기/통합/인수"를 부를 때만 사용한다. 작업 계약을 open으로 올리고, refs/claims로 선점하고, 체크포인트로 이어받고, 메인이 대화 기록과 대조해 통합한다. 일반 개발 요청에는 쓰지 않는다.
---

# pair-coding (초안 — 비활성)

> 이 파일은 초안이다. `docs/collaboration/plans/`에 있어 어느 에이전트도 자동으로 불러오지 않는다. 사용자가 PAIR_CODING.md 개정(승인 3곳)과 `docs/AGENT_START.md` 스킬 선택표 추가를 승인한 뒤에만 `.agents/skills/pair-coding/SKILL.md`로 옮기고 `.claude/skills/pair-coding`을 연결한다.

## 0. 시작 전 관문 (모든 모드 공통)

1. AGENTS.md 전체와 PAIR_CODING.md 전체를 읽는다. 이 스킬은 권한을 새로 주지 않는다. 충돌하면 AGENTS.md → PAIR_CODING.md → 이 스킬 순으로 따른다.
2. `grep -n 'refs/claims' PAIR_CODING.md`가 아무것도 찾지 못하면 개정이 적용되지 않은 것이다. **진행하지 말고** "pair-coding 규칙 미승인"이라고 보고하고 끝낸다.
3. **신원은 실행 환경이 준 값만 쓴다.** `AG`는 자기 종류(`claude`|`codex`), 세션 ID `SID`는 아래 한 줄로 **환경 변수에서만** 얻는다. ID 값을 직접 적거나, 다른 값으로 대신하거나, 환경 변수를 덮어쓰지 않는다. 비어 있으면 중단하고 보고한다.

   ```sh
   AG=<claude|codex>; case "$AG" in codex) SID=${CODEX_THREAD_ID:-};; claude) SID=${CLAUDE_CODE_SESSION_ID:-};; *) SID=;; esac; [ -n "$SID" ] || { echo "세션 ID 환경 변수 없음 — 중단"; false; }
   ```

   이 줄은 아래 모든 선점 명령 앞에 같은 명령으로 붙여 실행한다(셸 상태가 명령 사이에 이어지지 않을 수 있다). `;`로 이어 붙이면 이 줄이 실패해도 다음 명령이 실행되므로, 선점 명령 자체가 `[ -n "$SID" ] &&`로 다시 확인한다(2026-11-23 시험에서 확인). `AG`는 자기 신고지만, 메인이 대화 기록 위치(`~/.codex/sessions` / `~/.claude/projects`)로 대조한다(§4).
4. 지금 메인이 누구인지는 PAIR_CODING.md §7과 최신 인계 기록으로 확인한다. 모르면 추정하지 말고 묻는다.
5. 사용자가 부른 모드만 수행한다. 모드가 없으면 "열기/시작/이어하기/통합/인수 중 무엇인지"를 묻는다.

claim 내용 형식(모든 모드 공통, 스킬 명령만 만든다):

```text
branch=<agent>/<task-id>[-r<N>]
agent=<claude|codex>
session=<SID>
```

claim 목록 보기:

```sh
git for-each-ref --format='%(refname:strip=2) %(objectname)' refs/claims/ | while read id oid; do echo "== $id"; git cat-file -p "$oid"; done
```

## 1. 열기 — 메인만 (`pair-coding 열기 <목표>`)

1. `git fetch origin main` 후 검증된 최신 main 위에서 작업을 연다(PAIR_CODING.md 137행). 계약의 `base_sha`는 비워 둔다 — 계약 커밋보다 앞선 SHA로 시작하면 worktree에 계약 문서가 없기 때문이다(2026-11-23 대조군에서 확인). 시작하는 에이전트가 계약이 들어 있는 main tip을 기록한다.
2. 목표를 독립 작업으로 나눈다. **동시에 open인 모든 작업끼리 allowed_files가 한 줄도 겹치지 않아야 한다.** 이미 open이거나 선점된 작업의 파일과도 겹치면 안 된다. 겹치면 `depends_on`으로 직렬화하거나 한 작업으로 합친다.
3. 작업마다 `docs/collaboration/tasks/<task-id>.md`를 아래 형식으로 쓴다(PAIR_CODING.md §3 + 추가 필드).

   ```text
   task_id:
   owner: (시작하는 에이전트가 기록)
   status: open
   depends_on: []
   base_sha: (시작하는 에이전트가 worktree를 만든 main SHA를 기록)
   branch: (시작하는 에이전트가 <agent>/<task-id>로 기록)
   goal:
   allowed_files:
   - <경로, 한 줄에 하나>
   forbidden_files:
   contract:
   structure:
   checks:
   experiment:
   done: []
   next: (첫 할 일)
   unrecovered: []
   handoff:
   ```

4. 계약 문서만 커밋한다(`docs(pair): open <task-id>...`). 기존 push 승인 범위에 따라 origin/main에 반영한다. 계약을 확정할 수 없으면 open으로 올리지 않는다.
5. 보고: 연 작업 목록, 병렬 가능한 묶음, 사용자가 각 창에 넣을 한 줄(`pair-coding 시작`).

## 2. 시작 — 구현 담당 (`pair-coding 시작`)

같은 세션이 하던 작업이 있으면 이어서 하고, 없으면 새 작업 하나를 맡아 시작한다. **다른 세션의 작업은 같은 종류라도 건드리지 않는다**(그건 §3 이어하기).

1. **같은 세션 재개:** claim 목록에서 `agent=$AG`이고 `session=$SID`(내 환경 변수 값과 정확히 같음)인 claim을 찾는다. 그 브랜치 tip의 계약이 `ready_for_review`가 아니면 그 worktree에서 `next`부터 이어간다. `next`가 "실행 중이었음/결과 불명"이면 다시 실행하지 말고 확인부터 한다(PAIR_CODING.md 118행).
2. **새 작업 맡기:** main의 `docs/collaboration/tasks/`에서 `status: open`이고, claim이 없고, `depends_on`이 전부 main에서 `status: integrated`인 작업 중 task_id가 가장 앞선 것을 고른다. 파일 겹침은 계산하지 않는다(메인이 열 때 보장).
3. **선점 + worktree (한 명령, 승인 1회):** §0의 신원 줄 뒤에 이어서 한 번에 실행한다.

   ```sh
   ID=<task-id>; BASE=$(git rev-parse main);  # 끝의 ; 필수: 여러 줄을 한 줄로 합쳐도 값이 비지 않게
   [ -n "$SID" ] && [ -n "$ID" ] && git update-ref "refs/claims/$ID" "$(printf 'branch=%s\nagent=%s\nsession=%s\n' "$AG/$ID" "$AG" "$SID" | git hash-object -w --stdin)" 0000000000000000000000000000000000000000 \
     && git worktree add -b "$AG/$ID" "../pokemon-card-condition-$AG-$ID" "$BASE"
   ```

   - `reference already exists`로 실패 → 다른 쪽이 먼저 잡았다. 2로 돌아가 다음 후보.
   - 선점은 됐는데 worktree 생성이 실패 → claim을 지우지 말고 멈추고 보고한다.
   - Codex: 선점·worktree 생성 명령과, 이후 worktree의 각 체크포인트·완료 커밋은 Git 메타데이터(`.git`) 쓰기라 샌드박스에서 막힌다(`index.lock: Operation not permitted`, 2026-11-22·11-28 실측). 해당 명령마다 권한 상승을 요청한다. 이는 규칙 회피가 아니다(150행의 금지는 검사·규칙을 건너뛰는 상승).
   - 첫 체크포인트에서 계약의 `owner`, `branch`, `base_sha`(= 위 `BASE`), `status: implementing`을 채운다.
4. 새 worktree에서 PAIR_CODING.md §4(66–74행)대로 자체 `.venv`를 준비하고, 모델·worker 수정은 `./develop -- <명령>` 안에서 한다.
5. **체크포인트:** 의미 단위가 끝날 때마다 **한 커밋에** 코드 + 계약의 `done`(이번 단위 추가)·`next`(다음 할 일 하나)를 함께 넣는다. 제목 `checkpoint(<task-id>): <끝낸 단위>`. 커밋 전 `git diff --check`, `git diff --name-only <base_sha>`가 allowed_files + 계약 문서 안인지 확인한다.
6. **완료:** 마지막 커밋은 `feat|fix|test(scope): …` 형식으로 `status: ready_for_review`와 handoff(SHA, 변경 파일, 구조 기준, 검사 결과, 미검증, 리스크, 롤백)를 함께 기록한다. 이후 이 브랜치에 커밋하지 않는다.
7. 보고는 한 줄. 상대 에이전트에게 SHA나 내용을 전달해 달라고 요청하지 않는다.
8. 집을 작업이 없으면 이유(의존 미통합 / 모두 선점됨 / open 없음)를 보고하고 끝낸다. 다른 세션의 내 종류 미완료 claim이 있으면 "`pair-coding 이어하기`로 이어받을 수 있음"을 함께 알린다.

## 3. 이어하기 — 구현 담당, 사용자가 부를 때만 (`pair-coding 이어하기`)

새 세션에서 같은 종류의 이전 세션 작업을 넘겨받는다. 사용자는 작업 ID를 몰라도 된다.

1. claim 목록에서 `agent=$AG`이고 `session`이 `$SID`와 **다르며**, 브랜치 tip 계약이 `ready_for_review`가 아닌 claim을 모은다.
2. 0개면 "이어받을 작업 없음"을 보고하고 끝낸다. **2개 이상이면 목록(task_id, 브랜치, 마지막 체크포인트 제목, next)을 보여 주고 사용자가 고를 때까지 진행하지 않는다.** 1개면 그것으로 진행한다.
3. 이전 세션이 아직 살아 있을 수 있으므로 **이전 worktree에 이어 쓰지 않는다.** §5 인수와 같은 명령으로 새 브랜치 `$AG/$ID-r<N>`·새 worktree를 만들고 claim을 이전 값 일치 시만 교체한다.
4. 첫 커밋 제목 `checkpoint(<task-id>): resume from <이전 브랜치>@<TIP 앞 12자리>`, 계약에 `resumed_by: pair-coding 이어하기 (사용자 명령)`, `unrecovered`(이전 worktree의 미커밋 경로 목록), `next`를 기록한다. 이후는 시작 5–7.

## 4. 통합 — 메인만 (`pair-coding 통합`)

1. `git for-each-ref --format='%(refname:short) %(objectname)' refs/heads/claude/ refs/heads/codex/`로 브랜치를 훑고, tip 계약이 `ready_for_review`인 것을 찾는다(`git show <브랜치>:docs/collaboration/tasks/<id>.md`).
2. **통합 검사 (구현 담당이 아닌 메인이 직접, 하나라도 실패하면 통합하지 않고 보고):**
   - `refs/claims/<id>`의 `branch=`가 이 브랜치다. 아니면(인수·이어하기로 바뀐 옛 브랜치 등) 통합하지 않는다.
   - `BASE=$(git merge-base main <tip>)`가 브랜치 계약의 `base_sha`와 같다.
   - `git diff --name-only "$BASE" <tip>` ⊆ **main 쪽 계약**의 allowed_files + 계약 문서. (통합 전 main 계약 사본을 보관해 두고 대조한다 — 통합 후에는 브랜치가 고친 계약이 main에 들어온다.)
   - 인수 브랜치면 takeover 커밋에 사용자 지시 인용, 이어하기 브랜치면 `resumed_by`가 있다.
   - done/next·handoff가 채워져 있다.
3. **신원 대조 (에이전트가 아니라 실행 프로그램이 남긴 대화 기록 기준):** 이 작업의 claim에 적힌 **모든** 세션(현재 값 + 인수·이어하기 전 값은 각 takeover/resume 커밋과 이전 브랜치 claim 기록에서)에 대해:
   - 대화 기록 파일을 찾는다. `agent=codex`: `find ~/.codex/sessions -name "*-<session>.jsonl"`, `agent=claude`: `ls ~/.claude/projects/*/<session>.jsonl`. **정확히 1개**여야 하고, 찾은 위치가 `agent`와 맞아야 한다.
   - 그 기록에 `refs/claims/<id>`를 바꾼 명령이 있고, 그 명령이 이 스킬의 형식(생성 `0000…`, 교체 `"$OLD"`)이며 세션 ID를 글자로 적지 않고 `$SID`로 펼쳤다.
   - 그 기록에 다음이 **없다**: `CODEX_THREAD_ID=`·`CLAUDE_CODE_SESSION_ID=` 대입, 스킬 형식 밖의 `update-ref refs/claims`, `--no-verify`, `reset --hard`, `push`, 다른 브랜치·worktree 정리.
   - 기록을 찾을 수 없거나 비어 있으면 **"신원 검증 불가"로 통합하지 않는다**(`--ephemeral` 실행 포함).
   - `git config --get core.logAllRefUpdates`가 `always`면 `git reflog show refs/claims/<id>`의 변경 수가 기록 속 claim 명령 수와 같아야 한다. 아니면 "reflog 미사용"으로 적는다.
4. 기존 PAIR_CODING.md §6(92–101행) 절차로 통합한다. cherry-pick은 범위로 한 번: `./develop -- git cherry-pick -x "$BASE"..<tip>`. squash 금지(145행 대응 확인 보존). 충돌은 93행대로. 검사는 메인이 통합한 코드에서 **직접 다시 실행**한다(구현 담당의 "통과" 보고를 근거로 쓰지 않는다, 94행).
5. main 계약 `status: integrated` 커밋 → claim 삭제(이전 값 일치 시만):

   ```sh
   ID=<task-id>; OLD=$(git rev-parse "refs/claims/$ID") && git update-ref -d "refs/claims/$ID" "$OLD"
   ```

6. 기존 push·worktree 정리 절차(130–152행)를 따른다.

## 5. 인수 — 사용자가 지시할 때만 (`pair-coding 인수 <task-id>`)

다른 종류 에이전트의 작업을 넘겨받는다(예: Codex 할당량 소진 → Claude).

1. 사용자의 지시 문장을 그대로 기록해 둔다. 지시 없이 스스로 인수하지 않는다.
2. 전임 worktree에서 쓰기 명령을 하지 않는다. 확인은 `git --no-optional-locks -C <전임 경로> status --porcelain`만.
3. §0의 신원 줄 뒤에 이어서, 전임 브랜치 tip에서 새 브랜치·worktree, 그리고 claim 교체(이전 값 일치 시만):

   ```sh
   ID=<task-id>; N=<인수 차수>; OLD=$(git rev-parse "refs/claims/$ID"); TIP=$(git rev-parse <전임 브랜치>);  # 끝의 ; 필수
   [ -n "$SID" ] && [ -n "$OLD" ] && git update-ref "refs/claims/$ID" "$(printf 'branch=%s\nagent=%s\nsession=%s\n' "$AG/$ID-r$N" "$AG" "$SID" | git hash-object -w --stdin)" "$OLD" \
     && git worktree add -b "$AG/$ID-r$N" "../pokemon-card-condition-$AG-$ID-r$N" "$TIP"
   ```

   첫 줄이 실패하면(값이 이미 바뀜) 멈추고 보고한다.
4. 첫 커밋 `checkpoint(<task-id>): takeover from <전임 브랜치>@<TIP 앞 12자리>`에 사용자 지시 인용, 이전 claim 내용(`git cat-file -p "$OLD"`), `unrecovered`(전임 미커밋 경로 목록, 내용·절대경로 없음), `next`를 기록한다. 이후는 시작 5–7.

## 6. 금지 행동 (모든 모드)

- 세션 ID·claim 내용을 직접 적거나 지어내지 않는다. `CODEX_THREAD_ID`·`CLAUDE_CODE_SESSION_ID`를 대입·덮어쓰지 않는다. 환경 변수가 없으면 중단한다.
- `refs/claims/*`는 이 스킬의 명령으로만 만든다·바꾼다. 남의 claim을 지우거나 바꾸지 않는다(통합 후 메인 삭제, 사용자 지시 인수, 사용자가 부른 이어하기만 예외).
- 선점에 실패한 작업을 진행하지 않는다.
- 다른 세션의 worktree에 쓰지 않는다(같은 종류라도).
- allowed_files 밖 파일을 고치지 않는다. 이 스킬·AGENTS.md·PAIR_CODING.md도 고치지 않는다. 범위가 부족하면 멈추고 메인에게 계약 갱신을 요청하는 내용을 `next`에 적는다.
- 대화 기록 파일(`~/.codex/sessions`, `~/.claude/projects`)과 Git 설정·reflog를 고치거나 지우지 않는다.
- 막히면 우회하지 않는다(검사 건너뛰기, 강제 옵션, 권한 상승으로 규칙 회피, 다른 브랜치·worktree 정리 금지). 멈추고 보고한다.
- 실제 학습·모델 비교·사진 추론·라벨 수정·자동 검토는 구현 worktree에서 실행하지 않는다(PAIR_CODING.md 12–14행).
- 상대 에이전트를 자동으로 실행하거나 깨우지 않는다(86행). 세션 시작은 사용자 몫이다.
- 완료 불명인 실행·push는 확인 전 재실행하지 않는다(119행).

## 7. 남는 한계

- 마지막 체크포인트 이후 미커밋 작업은 인수·이어하기로 회수하지 않는다(경로만 `unrecovered`).
- 이 스킬은 절차 안내이며 강제 장치가 아니다. 위반은 메인의 통합 검사·신원 대조에서 **드러날 뿐 막히지는 않는다.** 대화 기록·reflog도 로컬 파일이라 고칠 수 있다(흔적은 남김, 위조 불가능은 아님). Codex는 샌드박스에서 홈 폴더 쓰기가 막혀 고치려면 권한 상승 기록이 남는다.
- 대화 기록이 있는 같은 컴퓨터에서만 신원 대조가 된다.
- `CLAUDE_CODE_SESSION_ID`가 앱 재시작·재개 후에도 같은지는 미확인이다. 바뀌면 같은 세션 자동 재개가 안 되고 `이어하기`가 필요할 뿐, 가로채기는 생기지 않는다.
