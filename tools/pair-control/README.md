# pair-control — Codex·Claude 병렬 개발 관제 (로컬, mock 기본)

사람이 작업 배정·시작·중단·검토·통합 승인을 제어하는 로컬 도구다. 관리용 LLM은 없다. 모든 단계는 결정적인 workflow 단계와 실행기 함수다.

| 구성 | 역할 |
|---|---|
| Mastra Workflow `prepare-task` | `plan → create-worktree → register(계약 커밋)` |
| Mastra Workflow `pair-task` (`src/workflow.ts`) | `launch → await-exit → collect(Git 계약 검사) → review-gate(작업 테스트·리뷰·사람 승인) → integrate-gate(통합·통합 후 검사)` 단계·분기(bail)·suspend/resume·실행 기록(LibSQL) |
| Node 실행기 (`src/executor/`) | 계약 검증, 충돌·중복 차단(O_EXCL 잠금), detached 감독 프로세스, 취소, 재시작 복구, Git 검사, `./develop` 안 cherry-pick |
| Mastra Studio (`/`) | workflow 그래프·실행 목록·trace (Mastra 기본 기능 그대로 사용) |
| 관제 화면 (`/pair`) | Studio에 없는 작업 배정·프로세스 제어·결과 검토·통합 승인만 담당하는 단일 HTML |

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

## 새 작업 만들기 (자동 준비)

사람은 **담당(Claude/Codex) · 목표 · 고칠 파일**만 고른다. 나머지는 Mastra `prepare-task` workflow(`plan → create-worktree → register`, 관리용 LLM 없음)가 채운다.

| 값 | 자동 규칙 |
|---|---|
| task ID | `task-<MMDD>-<n>` (겹치지 않는 번호) |
| 브랜치 | `<담당>/<task ID>` — 이미 있으면 거절(덮어쓰지 않음) |
| 기준 SHA | 통합 브랜치(`integration.branch`) 최신 커밋 |
| worktree | `<worktreeRoot>/<저장소 폴더명>-<담당>-<task ID>`, `git worktree add -b`로 생성. `worktreeRoot`를 비우면 저장소의 상위 폴더 |
| 고칠 파일 | 기준 커밋의 추적 파일·폴더 목록에서 체크. 진행 중 작업이 쓰는 경로는 "사용 중", 데이터·산출물·비밀 경로는 "금지"로 표시 |

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

## 독립 리뷰 작업

검토 단계에서 고정 SHA의 계약·diff·검사 결과를 리뷰 묶음(`.state/reviews/<id>/`)으로 만들고, 구현과 **다른 에이전트**의 별도 CLI 프로세스를 그 폴더에서 실행한다. 구현 worktree 경로는 전달하지 않으며, 실행 전후 worktree가 바뀌면 결과를 버린다. 판정은 `approve`·`changes_requested`·`insufficient_evidence`만 인정하고, 형식 오류("통과" 문구 등)·다른 SHA·실패는 판정 없음으로 표시한다. 판정은 승인 기록에 감사용으로 남을 뿐 사람 승인·통합을 대신하지 않는다. 이 화면은 현재 Codex 앱 대화로 메시지를 보내지 않는다. 지금은 fake 리뷰 CLI(`mock/fake-reviewer.mjs`)로만 검증했고 실제 리뷰 CLI는 차단 조건 해결 전까지 거절된다.

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

## 무료 전용 가드

유료 전환 신호가 보이면 서비스(이 실행기의 `mastra dev` 프로세스 그룹과 그 자식 실행)를 종료하고 macOS 알림 + 콘솔 + `.state/alerts/paid-risk.json`으로 알린다. 알림을 `npm run guard:ack`로 확인하기 전에는 다시 시작하지 않는다.

- 시작 시 환경변수 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `GEMINI_API_KEY`, `MASTRA_CLOUD_ACCESS_TOKEN` 등(`src/executor/paidSignals.mjs`)이 있으면 시작 거부. 값은 기록하지 않는다.
- 실행 로그에서 `credit balance`, `insufficient_quota`, `billing`, `extra usage`, `upgrade to pro/max` 등 문구 감지 → 모든 실행 중단 후 서버 종료.
- 자식 프로세스 환경은 허용 목록(PATH/HOME 등)만 전달하고 위 키를 항상 제거. `MASTRA_TELEMETRY_DISABLED=1`.
- real 모드는 `allowRealModelCalls=true`와 `confirmedSubscriptionAuth=true`(사용자가 CLI가 API 키가 아닌 기존 구독 로그인임을 직접 확인)가 모두 있어야 시작.
- `mastra deploy`/`server`/`auth`/`connect` 등 클라우드 명령은 호출하지 않는다.

한계: 실제 청구 여부는 provider 계정에서만 알 수 있다. 이 가드는 신호 기반 차단이며, 신호 없이 과금되는 경로(예: 구독 플랜 자체의 초과 사용 정책)는 감지하지 못한다. `billing` 같은 단어가 정상 코드 출력에 나와도 중단한다(오탐 쪽으로 보수적).

## 보안

`127.0.0.1`에만 바인딩. 모든 요청의 Host는 `127.0.0.1/localhost:<port>`만 허용(DNS rebinding 차단). 상태 변경 요청은 같은 출처 Origin만, `/pair/api/*` POST는 추가로 `X-Pair-Control: 1` 헤더와 Origin이 필수. CORS도 같은 출처로 제한. 임의 셸 명령 API는 없다: 실행 파일은 mock 스크립트, `--help`로 확인한 codex/claude, `./develop`, `git`뿐이며 모두 execFile/spawn 인자 배열이다. 감독 프로세스는 출력의 `sk-…`, `ghp_…`, `Bearer …` 등을 가린 뒤 로그에 쓴다.

Mastra Studio의 workflow 실행(`/api/workflows/...`)도 같은 결정적 단계를 거치므로 등록된 task만 시작할 수 있다. Mastra 서버 자체 API(에이전트·도구 등)는 이 도구에서 정의하지 않았다.

## 실제 CLI 어댑터 상태

`codex`·`claude` 실행 파일을 PATH 또는 설정에서 찾고 `--version`과 `--help`(codex는 `exec --help`)만 실행해 `--cd`/`--sandbox`, `--print`/`--permission-mode` 옵션 이름을 확인한다. 옵션 **값**(`workspace-write`, `acceptEdits`)과 인증 방식은 확인하지 않았다. 이 개발 환경에는 두 CLI 모두 설치되어 있지 않아(호스트 PATH 없음, Claude 앱 내장 바이너리는 Linux용) 화면에 "미설치"로 표시된다. 실제 모델 호출 연동은 별도 승인 작업이다.

## 검증 (2026-10-25, mock)

`npm test` 31개 통과(Node 24.21.0). 실사용 준비 작업에서 추가: 계약 커밋·불변·재시도 멱등, 환경 준비(symlink·import 경로·모듈·통합 checkout), 작업 테스트(CLI 0·테스트 실패 승인 차단, 실행 파일 제한, SHA·계약 변경 무효화, 중단·중복·재시작·불명), 통합 후 검사 실패 표시, fake 리뷰(판정 3종·형식 오류·다른 SHA·worktree 변경·중단·실제 모드 차단), E2E(준비→통합 후 검사, 다른 작업·미커밋 파일·비밀값 보존). 그 전 13개: 병렬 실행 2개, 파일·API 그룹·공용 설정 충돌과 동시 중복 시작, 손자 프로세스 포함 취소(외부 프로세스 생존 확인), 서버 재시작 3종(살아 있음·종료됨·결과 불명) 무재실행, 승인 SHA/기준 브랜치 변경 시 통합 거절 → 재검토 → 통합(`-x` 기록), 통합 충돌 abort와 `./develop` 잠금 사용 중 대기, 실패·범위 밖 변경 표시, 계약 검증, `./develop` 잠금 경유 실행, 무료 가드. `./develop`은 이 저장소의 `card_condition/workspace_lock.py` 복사본을 합성 저장소에서 실행한다.

브라우저(`/pair`)에서 담당·목표·폴더 선택만으로 자동 준비(worktree·브랜치 생성) → 시작 → 검토 대기, 배정 → 병렬 시작 → 충돌 시작 거절 → 중단 → (dev 서버 hot reload로 인한 실제 재시작 후) 관찰 상태 → 결과 반영 → diff → 승인 → 통합, 기준 브랜치 이동 후 승인 무효화 → 재검토 → 통합, 과금 문구로 서비스 종료·재시작 거부까지 확인했다. mock 성공은 실제 에이전트 연동 성공이 아니다.

## 롤백

도구는 `tools/pair-control/` 아래에 독립되어 있다. `git revert <커밋>`으로 도구와 루트 README 링크를 함께 되돌린다. 로컬 산출물은 `tools/pair-control/{node_modules,.state,.mastra,.demo,config.local.json}`을 지우면 된다. 다른 Python 코드·데이터·잠금 파일은 변경하지 않는다.
