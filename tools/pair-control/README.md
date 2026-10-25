# pair-control — Codex·Claude 병렬 개발 관제 (로컬, mock 기본)

사람이 작업 배정·시작·중단·검토·통합 승인을 제어하는 로컬 도구다. 관리용 LLM은 없다. 모든 단계는 결정적인 workflow 단계와 실행기 함수다.

| 구성 | 역할 |
|---|---|
| Mastra Workflow `prepare-task` | `plan → create-worktree → register(계약 커밋)` |
| Mastra Workflow `pair-task` (`src/workflow.ts`) | `launch → await-exit → collect(Git 계약 검사) → review-gate(작업 테스트·리뷰·사람 승인) → integrate-gate(통합·통합 후 검사)` 단계·분기(bail)·suspend/resume·실행 기록(LibSQL) |
| Node 실행기 (`src/executor/`) | 계약 검증, 충돌·중복 차단(O_EXCL 잠금), detached 감독 프로세스, 취소, 재시작 복구, Git 검사, `./develop` 안 cherry-pick |
| Mastra Studio (`/`) | workflow 그래프·실행 목록·trace (Mastra 기본 기능 그대로 사용) |
| 관제 화면 (`/pair`) | Studio에 없는 작업 배정·프로세스 제어·결과 검토·통합 승인만 담당. `src/ui/page.html`(마크업·스타일) + `src/ui/js/*.js` 모듈(`/pair/static/<이름>.js`로만 제공) |

## 실행

Node 22 이상이 필요하다(`.nvmrc`=24, `engine-strict`). 로그인 셸 기본 Node가 18이면 `nvm use 24` 후 실행한다. `npm start`도 Node 버전을 검사해 거부한다.

```sh
cd tools/pair-control
npm ci
npm test                      # mock 프로세스 검증(모델 요청 없음)
npm run demo:fixture          # .demo/에 합성 저장소·worktree 생성
npm start -- --demo           # http://127.0.0.1:4111/pair , Studio http://127.0.0.1:4111/
```

실제 저장소에 쓰려면 `config.example.json`을 `config.local.json`(Git 제외)으로 복사해 절대경로를 넣고 `npm start`. 상태·로그·Mastra DB는 `.state/`(Git 제외)에 저장된다. `npm install` 시 npm 11 기본 정책으로 esbuild/fsevents install script가 막히지만 optional 바이너리 패키지로 동작한다(이 환경에서 확인).

## 세 가지 실행 모드

| 모드 | 에이전트는 누가 | 도구가 하는 일 |
|---|---|---|
| **수동(기본)** | 사용자가 Claude/Codex 세션을 해당 worktree에서 직접 실행 | 소유권 잠금(파일 겹침 방지), 시작 프롬프트 생성, "작업 완료" 후 검사·인계·승인·통합·푸시. 프로세스를 띄우지 않으므로 구독 로그인만 쓰는 경로 |
| 실제 CLI | 도구가 `claude`/`codex` CLI를 실행(구독 로그인) | 위 + 프로세스 감독·중단. **무과금 가드를 모두 통과해야 시작** |
| 연습(mock) | 가짜 스크립트 | 도구 동작 확인용. 코드 품질 검증이 아님 |

## 새 작업 만들기 (자동 준비)

사람은 **담당(Claude/Codex) · 목표 · 고칠 파일**만 정한다. 완료 조건·작업 테스트·실행 환경·충돌 그룹 같은 나머지는 기본값이 있고 "고급 설정"에 접혀 있다. 나머지는 Mastra `prepare-task` workflow(`plan → create-worktree → register`, 관리용 LLM 없음)가 채운다.

| 값 | 자동 규칙 |
|---|---|
| task ID | `task-<MMDD>-<n>` (겹치지 않는 번호) |
| 브랜치 | `<담당>/<task ID>` — 이미 있으면 거절(덮어쓰지 않음) |
| 기준 SHA | 통합 브랜치(`integration.branch`) 최신 커밋 |
| worktree | `<worktreeRoot>/<저장소 폴더명>-<담당>-<task ID>`, `git worktree add -b`로 생성. `worktreeRoot`를 비우면 저장소의 상위 폴더 |
| 고칠 파일 | 한 칸에 한 줄씩 직접 입력(진행률 항목을 고르면 증거 중 코드 파일이 제안으로 채워짐). 데이터·산출물·비밀 경로와 다른 작업이 쓰는 경로는 미리보기가 알려 줌 |

입력할 때마다 부작용 없는 미리보기(`/pair/api/plan`)로 위 값과 검사 결과·겹침 경고를 보여 주고, **준비하고 배정**을 눌러야 폴더·브랜치를 만든다. 고급 설정에서 task ID·기준 SHA·기존 worktree·충돌 그룹을 직접 지정할 수 있다. 도구는 worktree·브랜치를 만들기만 하고 지우지 않는다.

## 작업 계약 (실행의 기준)

목표·완료 조건·허용 파일·작업 테스트·통합 후 검사·실행 환경·상세 지시를 하나의 계약으로 `docs/collaboration/tasks/<task-id>.md`에 렌더링해 **작업 브랜치에만** 커밋한다(main·통합 checkout 거절, 개인 절대경로 미기록). 이 커밋 SHA(`contractSha`)와 내용 해시가 기준이다.

- Git 계약 검사는 계약 커밋 이후 변경만 보고, 계약 파일이 그대로인지 확인한다. 에이전트가 계약을 바꾸면 실패.
- 재시도: 등록 전에 멈춘 준비는 같은 worktree·계약 커밋을 재사용한다. 같은 ID에 다른 내용의 계약이 있으면 거절.
- 실제 CLI 인자에는 계약 경로만 넘긴다(긴 지시는 파일).
- 승인에 계약 해시를 기록하고 통합 직전에 다시 확인한다.
- 작업 테스트 명령은 `{executable: git | node | .venv/bin/python, args[], cwd}`만 받고 셸을 쓰지 않는다. `{base}`·`{contract}`·`{head}` 자리표시자만 치환한다. 학습·실험 기록·자동 교차 검토 진입점은 거절한다.

- 배정 거절: glob·`..`·절대경로, `data/`·`artifacts/`·라벨·비밀 설정 경로, 담당과 다른 브랜치 접두어, `requiresExperiment=true`(학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토는 기본 checkout 단일 담당자 소관).
- 시작 거절: 저장소 worktree 목록에 없는 경로, 기본/통합 checkout, 브랜치 불일치, 기준 SHA가 HEAD의 조상이 아님, Git 진행 중 작업, `.venv` 심볼릭 링크(가상환경 공유), 무료 가드 발동.
- 동시 실행 직렬화: 진행 중(실행·검토 대기·통합 대기 포함) 작업과 허용 파일이 겹치거나, 충돌 그룹(API 계약 등)이 같거나, 공용 설정(`pyproject.toml`, `AGENTS.md` 등 → 암묵 그룹 `shared-config`)을 함께 허용하거나, worktree/브랜치가 같으면 시작하지 않는다.
- 중복 시작: 같은 프로세스 안에서는 동기 구간에서 상태 검사+잠금 획득, 프로세스·재시작을 넘어서는 `task:`/`worktree:`/`branch:` O_EXCL 잠금 파일. 잠금은 종료 확인 또는 사용자의 결과 불명 확정 때만 해제한다.
- `card_condition/`·`tools/experiments/`를 허용한 작업은 해당 worktree의 `./develop -- <CLI>`로 실행해 기존 잠금을 따른다.

## 실행 준비 (worktree 생성 ≠ 실행 가능)

계약 `env`(자동: Python 파일·`card_condition/`·`tests/`·`.venv` 검사가 있으면 python)와 `./develop` 사용 여부로 필요한 환경을 정한다.

| env | 확인 |
|---|---|
| none | 없음 |
| python | 자체 `.venv`(symlink 금지), `pyvenv.cfg`, `.venv/bin/python -I`의 prefix가 이 worktree의 `.venv` |
| python-project | 위 + `-I`로 `card_condition`이 이 worktree에서 import되는지, 필요 모듈 `find_spec` |

미준비면 시작·작업 테스트를 막고 직접 실행할 명령만 보여 준다(가상환경 생성·설치·다운로드 자동 실행 없음). 통합 checkout도 `./develop`용 `.venv`가 없으면 통합하지 않는다.

## 세 가지 검사

| 단계 | 무엇 | 통과 의미 |
|---|---|---|
| 1. Git 계약 검사 | 종료코드·브랜치 HEAD·계약 커밋 위 작업·계약 불변·커밋 존재·미커밋 없음·허용 파일 | 계약 형식을 지켰다. 코드가 맞다는 뜻이 아니다 |
| 2. 작업 테스트 | 사용자가 확인 후 실행기가 감독 프로세스로 계약의 검사를 차례로 실행 | 그 SHA·계약에서 명령이 0으로 끝났다. 미실행·실패·중단·결과 불명·재시작 중단은 통과가 아니다 |
| 3. 통합 후 검사 | 통합 checkout에서 `./develop -- <검사>` | 실패 시 `integrated_check_failed`, 통합 전/후 SHA 기록, 자동 되돌림 없음 |

검사마다 SHA·명령·종료코드·로그·시각을 남긴다. 코드 SHA나 계약이 바뀌면 이전 결과는 "이전 SHA 결과"로 표시되고 승인에 쓰이지 않는다. 서버 재시작 시 끝난 검사의 결과는 기록하지만 남은 검사를 이어서 실행하지 않는다.

## 누구 차례 · 시작 프롬프트 · 메인 인계

- **누구 차례**(사용자/구현 에이전트/메인 에이전트/도구)를 작업 상태에서 파생해 표시한다. 에이전트를 자동으로 부를 수 없으므로 전환은 사용자가 버튼으로 한다("작업 완료", "메인에게 인계", "메인 확인 완료").
- **시작 프롬프트**: 작업 위치(worktree 절대경로)·브랜치·시작 HEAD·기준 SHA·읽을 문서(AGENTS.md, PAIR_CODING.md, 계약, 추가 문서)·목표·완료 조건·허용 파일 수와 목록·검사·진행 방식·금지·인계 형식을 규칙으로 조립한다(LLM 없음). 경로는 복사할 때만 만들고 어떤 파일에도 커밋하지 않는다. `무인 실행` 옵션은 사람 정답 추정·재요청 금지 문구를 추가한다. 추가 문서는 시작 HEAD에 있는 저장소 상대경로만 허용한다.
- **메인 인계**: 커밋이 없거나, 미커밋 변경이 있거나, Git 검사 이후 SHA가 바뀌었으면 거절한다. 인계 문서(전체 SHA와 부모, 변경 파일, 검사·작업 테스트·리뷰 상태, 미검증, 롤백)는 **작업 브랜치에 커밋하지 않고** 상태 폴더에 저장해 복사용으로 보여 준다(PAIR_CODING §4: 완료 후 추가 커밋 금지, SHA 고정). 코드 SHA가 바뀌면 인계는 낡은 것으로 표시되고, 잘못 누른 인계는 승인 전까지 취소할 수 있다. 메인 확인 시각은 승인 기록에 남지만 승인의 필수 조건은 아니다.

## 진행률 항목으로 계약 초안 만들기

`development-progress.json`(통합 브랜치에 커밋된 내용을 `git show`로 읽음)의 **미완료 항목**을 고르면, 완료 조건·현재 평가 원문을 인용한 상세 지시와 목표·완료 조건 초안을 채운다. 증거 파일 중 기준 커밋에 실제 있고 금지 경로가 아닌 코드만 "제안 파일"로 보여 주며 자동 선택하지 않는다. 초안에는 "학습·모델 비교·사진 추론·성능 평가는 기본 checkout의 단일 담당자, 점수·진척률 변경 금지"가 들어간다. 어느 항목을 할지와 허용 파일은 사람이 정한다.

## 독립 리뷰 작업

검토 단계에서 고정 SHA의 계약·diff·검사 결과를 리뷰 묶음(`.state/reviews/<id>/`)으로 만들고, 구현과 **다른 에이전트**의 별도 CLI 프로세스를 그 폴더에서 실행한다. 구현 worktree 경로는 전달하지 않으며, 실행 전후 worktree가 바뀌면 결과를 버린다. 판정은 `approve`·`changes_requested`·`insufficient_evidence`만 인정하고, 형식 오류("통과" 문구 등)·다른 SHA·실패는 판정 없음으로 표시한다. 판정은 승인 기록에 감사용으로 남을 뿐 사람 승인·통합을 대신하지 않는다. 이 화면은 현재 Codex 앱 대화로 메시지를 보내지 않는다. 지금은 fake 리뷰 CLI(`mock/fake-reviewer.mjs`)로만 검증했고 실제 리뷰 CLI는 차단 조건 해결 전까지 거절된다.

## 파이프라인 화면

작업마다 단계 노드 10개를 ArgoCD처럼 한 줄로 보여 준다: 준비 → 구현 → Git 검사 → 작업 테스트 → 리뷰(선택) → 메인 인계 → 사람 승인 → 통합 → 통합 후 검사 → 푸시. 단계 상태(완료·진행 중·할 일·주의·실패·대기·건너뜀)는 작업 상태·검사·인계·승인·통합·푸시 기록에서 화면이 파생할 뿐 저장하지 않는다(`src/ui/js/stages.js`, 단위 검사 `test/ui-stages.test.ts`).

- 위쪽 **지금 단계** 줄: 지금 단계, 차례(누구를 기다리는지), 사람이 누를 대표 버튼 하나.
- 노드를 누르면 그 단계의 설명·담당·상세·버튼이 아래에 열린다. 노드를 누르는 것은 작업 상태를 바꾸지 않는다.
- 왼쪽 작업 카드는 같은 단계를 작은 막대 줄로 보여 준다.
- Mastra 실행 ID·프로세스·계약·로그는 "실행 정보 · 계약 · 로그"에 접어 둔다.

## 되돌리기 · 보관

- **승인 취소**: 승인됨(통합 전) 작업을 같은 SHA로 검토 단계로 되돌린다. 에이전트는 다시 실행하지 않고, 같은 SHA·계약의 작업 테스트 결과는 유효하다. 이전 workflow 실행은 `integrate-gate`에서 `withdraw`로 끝나고 재검토 실행이 이어받는다(`src/executor/taskControl.ts`).
- **보관**: 끝났거나 시작 전인 작업만 목록에서 숨긴다(진행 중·검토·승인 대기 작업은 거부). 기록·worktree·브랜치는 지우지 않으며 "보관된 작업"에서 해제한다.
- 통합 후 되돌리기는 도구가 하지 않는다(reset 없음). 푸시 후에는 푸시 단계의 "되돌림 커밋 준비"를 쓴다.

## 상태 의미

| 화면 표시 | 의미 |
|---|---|
| CLI 실행 중 (workflow `await-exit`) | 실제 프로세스 실행 중. workflow는 종료를 기다릴 뿐 사람 승인 대기가 아니다. **CLI 일시정지는 지원하지 않는다**(중단만). |
| 사람 승인 대기 (`review-gate`/`integrate-gate`) | CLI는 종료됨. 사람이 diff를 열어 본 뒤에만 승인 버튼이 활성화된다. |
| 재시작 전 프로세스 실행 중 | 서버 재시작 후 이전 실행이 살아 있음. 관찰만 하며 재실행하지 않는다. |
| 재시작 후 종료 관찰 · 확인 필요 | 서버가 없는 동안 끝난 실행. 자동 반영하지 않고 "결과 반영"으로만 `await-exit`를 재개한다. |
| 결과 불명 | 감독 프로세스와 종료 기록이 모두 없음. 완료로 보지 않으며 잠금 유지. "결과 불명 확정"은 그룹 종료를 확인한 뒤 잠금만 해제(abandoned). |
| ⚠ 불일치 | 실행기 상태와 Mastra 실행 기록의 기대 관계가 다름. |

중단은 실행기가 만든 감독 프로세스 그룹에만 `SIGTERM`(3초 후 남으면 `SIGKILL`)을 보낸다. 리더 PID는 `ps`의 PGID와 명령행의 spec 경로로 소유를 확인한다(PID 재사용 방지). 다른 세션·서버·에이전트는 대상이 아니다.

## 통합

1. 결과는 전체 HEAD SHA로 고정. Git 계약 검사 통과 + 같은 SHA·계약의 작업 테스트 통과 + diff 확인이 있어야 승인 버튼이 켜진다.
2. 승인 시 SHA·기준 브랜치 HEAD·관련 파일 목록 해시·계약 해시를 기록. 통합 직전 하나라도 바뀌거나 작업 테스트가 승인 SHA와 다르면 승인 무효화(`integration_refused`) → "재검토"(에이전트 재실행 없음).
3. 통합은 `integration` O_EXCL 잠금 + 통합 checkout의 `./develop -- git cherry-pick -x <커밋…>`. checkout이 깨끗하지 않거나 `./develop` 잠금 사용 중이면 승인 유지 후 같은 단계에서 대기.
4. 충돌 시 충돌 파일을 기록하고 `./develop -- git cherry-pick --abort`만 수행. ours/theirs 자동 선택·`reset --hard`·push·force push·브랜치 삭제는 구현하지 않았다.

## 실제 CLI 무과금 조건

실제 CLI 모드는 **구독 로그인으로만** 시작한다(`src/executor/nocharge.ts`, `adapters.ts`). 아래 중 하나라도 있으면 시작하지 않고 원인 코드와 해결 조건을 표시한다. 값은 읽지 않고 이름만 본다.

| 검사 | 근거 |
|---|---|
| API 키·클라우드 토큰 환경변수 | `ANTHROPIC_API_KEY` 등이 있으면 API 요금(Claude Code 문서) |
| Claude 설정의 `apiKeyHelper`, `env`에 API 키 이름, `forceLoginMethod`가 `claudeai`가 아님 | 설정 키 목록은 Claude Code 설정 문서의 색인 기준. 사용자·프로젝트(`.claude/settings(.local).json`) 설정 검사. `forceLoginMethod`의 값 이름은 문서 색인에 없어 보수적으로 차단 |
| 인자의 `--bare`, `--max-budget-usd`, `--betas` | `--bare`는 구독 로그인을 쓰지 않고 API 키를 요구(문서). 문서가 `-p`의 기본값이 bare가 될 예정이라고 해서 CLI 업데이트 때 재확인 필요 |
| `confirmedSubscriptionAuth` ≠ true | 두 CLI 모두 로그인 방식을 코드로 확인하는 명령을 문서에서 찾지 못함 → 사용자가 구독 로그인과 추가 크레딧 꺼짐을 직접 확인했다는 표시가 마지막 방어선 |
| `--help`에서 필요한 옵션 미확인 | claude: `--print`, `--permission-mode`, `--allowedTools` / codex: `exec`의 `--cd`, `--sandbox` |

- Claude 실행은 `--permission-mode acceptEdits`와 `--allowedTools`(Read, Edit, Write, `git status/diff/log/add/commit`)만 쓴다. 그 밖의 Bash는 `-p` 모드에서 자동 거부된다. Codex의 `--sandbox workspace-write` 값은 미검증이다.
- **한도 도달은 정지 신호**다: 한도 문구가 나오면 실행 중인 작업을 멈추고 실제 CLI 시작을 거부하며 서비스는 유지한다. 재시도·크레딧 구매는 하지 않고, 사용자가 풀렸음을 확인해야 해제된다. 한도 안내문에 섞인 "extra usage" 같은 권유 문구는 과금으로 보지 않는다. 반대로 `credit balance` 같은 확실한 과금 문구는 서비스를 종료한다. 한도 문구 목록은 CLI 버전마다 달라질 수 있어 목록에 없는 문구는 일반 실패로 끝난다(자동 재시도·구매는 어느 경우에도 없음).
- 로그인 정보 파일(`auth.json`, 키체인)은 열지 않는다.

## 푸시 · 되돌림

통합된 브랜치를 원격에 올리는 단계다. **푸시는 취소할 수 없으므로** 단계별로 막는다. 실수는 `git revert`로 바로잡는다(force push·`reset --hard` 없음).

1. **점검**(읽기 접속·전송 없음): 통합 checkout 브랜치·깨끗함, `git fetch`, fast-forward 가능 여부, 푸시될 커밋(전체 SHA ← 부모)·변경 파일, 이 범위의 작업 중 통합 후 검사 실패 상태가 있는지, **커밋마다** 금지 경로·5MB 초과 파일·알려진 비밀 패턴(`sk-…`, GitHub 토큰, AWS 키, 개인 키, Slack/Google 키), `git push --dry-run`. 중간 커밋에 들어갔다 지워진 값도 이력에 남으므로 최종 diff가 아니라 커밋별로 본다.
2. **확인 입력**: 대상 SHA 앞 12자를 직접 입력해야 푸시 버튼이 켜지고, 푸시 직전에 다시 점검한다. 점검 이후 로컬이나 원격이 바뀌면 거절한다.
3. **푸시**: 확인한 SHA를 지정한 일반 push(`<sha>:refs/heads/<branch>`), 통합 잠금 안에서 하나만. 실패해도 자동 재시도하지 않는다.
4. **사후 확인**: `ls-remote`로 원격 SHA가 대상과 같은지 확인해 `pushed_verified` / `push_failed` / `push_unverified`(결과 불명) / `remote_mismatch`로 기록한다. "원격 다시 확인"으로 읽기 전용 재확인.
5. **되돌림**: 확인된 푸시에서 "되돌림 커밋 준비"를 누르면 푸시한 커밋마다 revert 커밋을 로컬에 만들고(`./develop` 잠금, 충돌 시 `revert --abort`만), **푸시 전 트리와 같은지** 확인한다. 로컬·원격이 모두 푸시한 SHA 그대로일 때만 가능하다. 그다음 1~4를 그대로 거쳐 올린다. 원래 커밋은 이력에 남는다.

비밀 패턴 오탐(예: 테스트용 가짜 키)은 **커밋·파일·줄 단위로** 사용자가 확인하면 경고로 바뀌고 기록이 남는다. 금지 경로·큰 파일은 확인으로 넘길 수 없다. 이 점검은 알려진 모양만 잡으며 모든 비밀을 보장하지 않는다. 자격 증명은 도구가 다루지 않고 git의 기존 credential helper를 프롬프트 없이 쓴다. 실제 GitHub 푸시는 검증하지 않았다(로컬 bare 원격으로만 검증).

## 메인 역할

"메인"은 통합·푸시·실험의 단일 담당이다. 상단에서 현재 메인을 보고 이양할 수 있다. **표시와 기록만** 하며 권한을 강제하지 못한다(누가 클릭하는지 도구가 모름). 프로세스·통합·푸시·결과 불명 푸시·`./develop` 잠금이 있으면 이양을 거절하고, 이양하면 이력과 인계 메모(진행 중 작업, 새 메인에게 다시 전달할 인계, 최근 푸시)를 남긴다. PAIR_CODING.md·AGENTS.md는 main 통합을 Codex로 정해 두었고 이 도구는 그 규칙을 바꾸지 않는다. 토큰 잔량은 읽지 못하므로 이양은 항상 사용자가 누른다.

## 무료 전용 가드

유료 전환 신호가 보이면 서비스(이 실행기의 `mastra dev` 프로세스 그룹과 그 자식 실행)를 종료하고 macOS 알림 + 콘솔 + `.state/alerts/paid-risk.json`으로 알린다. 알림을 `npm run guard:ack`로 확인하기 전에는 다시 시작하지 않는다.

- 시작 시 환경변수 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `GEMINI_API_KEY`, `MASTRA_CLOUD_ACCESS_TOKEN` 등(`src/executor/paidSignals.mjs`)이 있으면 시작 거부. 값은 기록하지 않는다.
- 실행 로그에서 확실한 과금 문구(`credit balance`, `insufficient_quota`, `payment required` 등) 또는 권유성 문구(`billing`, `extra usage`, `upgrade to …`)를 감지하면 모든 실행을 중단하고 서버를 종료한다. 단 구독 한도 도달 문구와 함께 나온 권유성 문구는 정지로만 처리한다(위 "실제 CLI 무과금 조건").
- 자식 프로세스 환경은 허용 목록(PATH/HOME 등)만 전달하고 위 키를 항상 제거. `MASTRA_TELEMETRY_DISABLED=1`.
- real 모드는 `allowRealModelCalls=true`, `confirmedSubscriptionAuth=true`와 위 무과금 검사를 모두 통과해야 시작.
- `mastra deploy`/`server`/`auth`/`connect` 등 클라우드 명령은 호출하지 않는다.

한계: 실제 청구 여부는 provider 계정에서만 알 수 있다. 이 가드는 신호 기반 차단이며, 신호 없이 과금되는 경로(예: 구독 플랜 자체의 초과 사용 정책)는 감지하지 못한다. `billing` 같은 단어가 정상 코드 출력에 나와도 중단한다(오탐 쪽으로 보수적).

## 보안

`127.0.0.1`에만 바인딩. 모든 요청의 Host는 `127.0.0.1/localhost:<port>`만 허용(DNS rebinding 차단). 상태 변경 요청은 같은 출처 Origin만, `/pair/api/*` POST는 추가로 `X-Pair-Control: 1` 헤더와 Origin이 필수. CORS도 같은 출처로 제한. 임의 셸 명령 API는 없다: 실행 파일은 mock 스크립트, `--help`로 확인한 codex/claude, `./develop`, `git`뿐이며 모두 execFile/spawn 인자 배열이다. 감독 프로세스는 출력의 `sk-…`, `ghp_…`, `Bearer …` 등을 가린 뒤 로그에 쓴다.

Mastra Studio의 workflow 실행(`/api/workflows/...`)도 같은 결정적 단계를 거치므로 등록된 task만 시작할 수 있다. Mastra 서버 자체 API(에이전트·도구 등)는 이 도구에서 정의하지 않았다.

## 실제 CLI 어댑터 상태

`codex`·`claude` 실행 파일을 PATH 또는 설정에서 찾고 `--version`과 `--help`(codex는 `exec --help`)만 실행해 옵션 이름(`--print`/`--permission-mode`/`--allowedTools`, `--cd`/`--sandbox`)을 확인한다. **이 개발 환경에는 두 CLI가 설치되어 있지 않고(호스트 PATH 없음, Claude 앱 내장 바이너리는 Linux용) 설치·로그인·모델 호출을 하지 않았다.** 실제 경로는 가짜 `claude`/`codex` 실행 파일(`test/fake-cli/`)로 인자·환경변수·한도·과금 문구 처리를 검증했다. 검증되지 않은 것: 실제 CLI의 출력 형식과 한도 문구, `--permission-mode acceptEdits`·`--allowedTools` 동작(문서의 옵션 이름은 확인), Codex `--sandbox workspace-write` 값, 두 CLI의 로그인 방식 확인(코드로 확인할 방법을 문서에서 찾지 못함). `codex mcp-server`는 문서상 제거되었고 `claude mcp serve`는 문서에서 확인하지 못해 MCP 경로는 쓰지 않는다.

## 검증 (2026-10-25, mock·fake CLI·로컬 bare 원격)

`npm test` 69개 통과(Node 24.21.0, 파이프라인 화면 단계 판정 7개·승인 취소/보관 2개 포함) — 실제 CLI 경로 작업에서 추가: 무과금 가드(환경변수·Claude 설정 키 이름·금지 옵션·한도·과금 문구), 가짜 claude/codex 실행, 수동 모드, 시작 프롬프트, 인계, 푸시·되돌림(성공·거절·실패·이력 점검·오탐 확인), 진행률 초안, 메인 이양. 브라우저에서 진행률 항목 선택 → 수동 작업 → 시작 프롬프트 → 작업 완료 → 작업 테스트 → 인계·확인 → 승인 → 통합 → 푸시 → 되돌림 푸시를 화면 버튼으로 진행했고 원격(로컬 bare) 상태를 별도로 확인했다. 아래는 이전 단계 검증 기록이다.

`npm test` 31개 통과(Node 24.21.0). 실사용 준비 작업에서 추가: 계약 커밋·불변·재시도 멱등, 환경 준비(symlink·import 경로·모듈·통합 checkout), 작업 테스트(CLI 0·테스트 실패 승인 차단, 실행 파일 제한, SHA·계약 변경 무효화, 중단·중복·재시작·불명), 통합 후 검사 실패 표시, fake 리뷰(판정 3종·형식 오류·다른 SHA·worktree 변경·중단·실제 모드 차단), E2E(준비→통합 후 검사, 다른 작업·미커밋 파일·비밀값 보존). 그 전 13개: 병렬 실행 2개, 파일·API 그룹·공용 설정 충돌과 동시 중복 시작, 손자 프로세스 포함 취소(외부 프로세스 생존 확인), 서버 재시작 3종(살아 있음·종료됨·결과 불명) 무재실행, 승인 SHA/기준 브랜치 변경 시 통합 거절 → 재검토 → 통합(`-x` 기록), 통합 충돌 abort와 `./develop` 잠금 사용 중 대기, 실패·범위 밖 변경 표시, 계약 검증, `./develop` 잠금 경유 실행, 무료 가드. `./develop`은 이 저장소의 `card_condition/workspace_lock.py` 복사본을 합성 저장소에서 실행한다.

브라우저(`/pair`)에서 담당·목표·폴더 선택만으로 자동 준비(worktree·브랜치 생성) → 시작 → 검토 대기, 배정 → 병렬 시작 → 충돌 시작 거절 → 중단 → (dev 서버 hot reload로 인한 실제 재시작 후) 관찰 상태 → 결과 반영 → diff → 승인 → 통합, 기준 브랜치 이동 후 승인 무효화 → 재검토 → 통합, 과금 문구로 서비스 종료·재시작 거부까지 확인했다. mock 성공은 실제 에이전트 연동 성공이 아니다.

## 롤백

도구는 `tools/pair-control/` 아래에 독립되어 있다. `git revert <커밋>`으로 도구와 루트 README 링크를 함께 되돌린다. 로컬 산출물은 `tools/pair-control/{node_modules,.state,.mastra,.demo,config.local.json}`을 지우면 된다. 다른 Python 코드·데이터·잠금 파일은 변경하지 않는다.
