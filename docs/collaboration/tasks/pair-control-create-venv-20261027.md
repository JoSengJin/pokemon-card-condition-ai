# pair-control 준비 단계 "환경 만들기" — Claude 배정

- task_id: `pair-control-create-venv-20261027`
- owner: Claude
- status: implementing
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

(인계 시 갱신)
