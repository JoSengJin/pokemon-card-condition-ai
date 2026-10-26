# pair-control 준비 단계 "환경 만들기" — Claude 배정

- task_id: `pair-control-create-venv-20261027`
- owner: Claude
- status: handoff (코드 커밋 `771ec49322eaf5ba9a525c1927c5353ad3794a9d`)
- base_sha: `0808ac7` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 배경

기본 허용 범위에 `card_condition/`가 있어 작업은 항상 `./develop` 잠금과 자체 `.venv`가 필요하다. 새 worktree에는 `.venv`가 없어서(git이 추적하지 않음) 준비 단계가 매번 막힌다(task-1026-2, task-1027-1). 지금은 사용자가 터미널에서 명령을 직접 실행해야 한다.

## 목표

준비 단계에 **"환경 만들기"** 버튼을 둔다(1회 클릭, 확인창 포함). 실행하는 일은 고정 명령 하나뿐이다: 이 작업의 등록된 worktree에서 `python3 -m venv .venv`(셸 없음, 패키지 설치 없음, 네트워크 없음). 끝나면 실행 준비를 다시 확인한다.

- 거부 조건: 기본 checkout, 등록되지 않은 폴더, 실행·검토 중인 작업, 이미 `.venv`(심볼릭 링크 포함)가 있는 경우. 다른 checkout의 `.venv`를 공유하지 않는다.
- `python-project`(프로젝트 설치가 필요한 환경)는 `.venv`만 만들고 `pip install`은 하지 않는다. 남은 안내는 그대로 보여 준다.
- 준비 단계의 대표 버튼을 `.venv`가 없을 때 "환경 만들기"로 바꿔 지금 눌러야 할 것을 한눈에 보이게 한다.

## allowed_files

1. `tools/pair-control/src/executor/taskControl.ts` (함수 1개 추가)
2. `tools/pair-control/src/mastra/index.ts` (경로 1개)
3. `tools/pair-control/src/ui/**`
4. `tools/pair-control/test/task-control.test.ts`, `tools/pair-control/test/ui-stages.test.ts`
5. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-create-venv-20261027.html`

## forbidden

위 밖 전부. 환경 검사(`envcheck.ts`)의 판정 규칙과 "설치하지 않음" 원칙은 그대로다(패키지 설치·모델 다운로드 없음). 사용자의 실제 작업 폴더(task-1027-1 등)에서 이 버튼을 실행하지 않는다.

## 구조 기준

`taskControl.ts` 함수 7개 이하, 호출 전이 4회 이하: `route → createVenv → G.run`, `createVenv → recheckEnv → checkVenv`.

## checks

1. `npm run typecheck`, `npm test`(기존 75 + 신규).
2. 신규: `.venv` 없는 worktree에서 `createVenv` → 준비됨·`pyvenv.cfg` 생성·재호출 거부; 기본 checkout 경로·진행 중 작업·`.venv` 링크 거부; 대표 버튼 판정(ui-stages).
3. 브라우저(4111): 새 경로는 없는 task ID로만 호출, 버튼은 렌더 확인만(실제 작업에 실행하지 않음).
4. 성과·진척 HTML 생성·열기, `git diff --check`, 최종 깨끗한 트리.

## 결과

- 코드 커밋 `771ec49322eaf5ba9a525c1927c5353ad3794a9d` (검사는 같은 작업 트리에서 실행).
- 함수 수: `taskControl.ts` 4(record·withdrawApproval·setArchived·createVenv), `stages.js` 7(venvMissing 추가), `actions.js` 7(표·분기만 추가), `panels-work.js` 5. 호출 경로: `route → createVenv → G.run` / `createVenv → recheckEnv → checkVenv`(전이 2~3).
- 동작: 준비 패널·"지금 단계" 상자에 "환경 만들기"(`.venv`가 없어 막힌 경우에만 대표 버튼). 확인창에 고정 명령을 보여 주고, 서버는 등록된 worktree에서 `python3 -m venv .venv`만 실행한 뒤 준비를 다시 확인한다. 기본 checkout·등록되지 않은 폴더·시작 전이 아닌 작업·이미 있는 `.venv`는 거부. `python-project`는 `.venv`만 만들고 `pip install`은 하지 않는다.
- checks: typecheck 통과, `npm test` 77/77(기존 75 + 신규 2: 환경 만들기 / 대표 버튼 판정).
- 실행 확인(합성 데모 서버, 실제 저장소 아님): 기본 범위로 작업을 만들면 사용자 화면과 같은 "실행 환경 준비 필요 · 자체 .venv 없음"이 재현되고, 대표 버튼이 "환경 만들기"로 나온다. 클릭 → 확인창(고정 명령 표시) → ".venv를 만들었고 실행 준비가 끝났습니다" → 대표 버튼이 "작업 시작"으로 바뀌고 시작 버튼 활성. 콘솔 오류 0. 확인 후 데모 서버를 종료했다.
- 미확인: 사용자의 실제 저장소 작업(task-1027-1 등)에서 같은 버튼을 눌러 보는 흐름. 확인 시점에 4111 서버가 꺼져 있었고(사용자 서버는 시작·종료하지 않음), 실제 worktree를 바꾸는 일이라 하지 않았다. 새 코드를 쓰려면 사용자가 서버를 다시 시작해야 한다.
- 알려진 한계: `python3`이 시스템 기본(이 환경 3.9.6)이다. 다른 버전이 필요하면 직접 만든다. 도구는 `.venv`를 지우지 않는다.
- 롤백: 코드·문서 커밋 `git revert`. 만들어진 `.venv`는 각 worktree 안에 있고 git이 추적하지 않는다.
