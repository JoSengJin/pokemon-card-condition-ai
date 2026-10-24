# pair-control 실사용 준비 — 인계 보고

- task: `pair-control-readiness-20261025` (계약: `docs/collaboration/tasks/pair-control-readiness-20261025.md`)
- branch: `claude/pair-control`, 시작 `4194bf54d3af8901741cabc653e8f58a0cea068b`
- 실행 환경: Node v24.21.0(nvm). 로그인 셸 기본 Node 18.20.5는 사용하지 않음.

## 커밋 순서 (전체 SHA ← 부모)

| # | 커밋 | 부모 | 내용 |
|---|---|---|---|
| 1 | `145bba96d3f1d81eb33cdfc17d5881310d7e0b8d` | `4194bf54d3af8901741cabc653e8f58a0cea068b` | 작업 계약 고정 |
| 2 | `b568bcbaa9e2a71d6772bf4abdde5ecc58e66d09` | `145bba96…` | 연결 상태·실제 실행 차단 원인, 과금 가드 표현, Node 가드 |
| 3 | `69b7f7f724271fea8cedc13297471fafca79a487` | `b568bcba…` | 계약 파일 커밋·실행 기준·재시도 멱등 |
| 4 | `16224c5aaceea24646aa48317d1ff1453cfc4b3d` | `69b7f7f7…` | 실행 준비(.venv·import·모듈) 검사 |
| 5 | `ed68b89c3eb12f1809f8bc9281408dfd9d2dcb1b` | `16224c5a…` | Git 계약 검사·작업 테스트·통합 후 검사 분리 |
| 6 | `72266565f00a8b09b66b85f93383c72fa07cba38` | `ed68b89c…` | 별도 리뷰 작업(fake CLI) |
| 7 | `67d38f37cd0fc4175be8373d681470c592a01dac` | `72266565…` | 단계별 UI, E2E 회귀 |
| 8 | `c152ace5c4b26aba5e3b73c82f60b78aaa5c334e` | `67d38f37…` | 도구 README 갱신 |
| 9 | (이 보고서·task 결과 커밋) | `c152ace5…` | 인계 기록 |

## 변경 파일

`docs/collaboration/tasks/pair-control-readiness-20261025.md`, 이 보고서, `tools/pair-control/**` 23개(신규: `contractFile.ts`, `envcheck.ts`, `mock/fake-reviewer.mjs`, `.nvmrc`, `.npmrc`, 테스트 5개). allowed_files 밖 변경 없음(`git diff --name-only 4194bf5..HEAD`로 확인). Python 코드·데이터·라벨·모델·진척률·루트 문서 미변경.

## 핵심 diff

- `executor.ts`: 실행을 `kind`(agent/check/review)로 구분하는 `spawnSupervised` 하나로 통합. `runChecks`→`startNextCheck`→`onAuxEnd`가 작업 테스트를 순서대로 실행하고, 재시작 후 관찰된 종료는 `interrupted`로 끝내 남은 검사를 실행하지 않음. `approve`는 Git 계약 검사 + 같은 SHA·계약의 작업 테스트 `passed`를 요구. `integrate`는 계약 해시·작업 테스트 SHA를 재확인하고 통합 후 검사를 `./develop` 안에서 실행해 실패 시 `integrated_check_failed`와 `preHead`/`newHead`를 기록. `startReviewJob`/`onReviewEnd`가 리뷰 묶음·worktree 지문·판정 형식을 검사.
- `contractFile.ts`: 계약 렌더(개인 경로 제외)·작업 브랜치 커밋·동일 내용 재사용·다른 내용 거절·커밋별 계약 해시.
- `envcheck.ts`: none/python/python-project별 자체 `.venv` 검사(symlink 금지, `-I` prefix·import 경로, `find_spec`), 해결 명령만 안내.
- `contract.ts`: `CheckSpec`(git·node·`.venv/bin/python`만, 학습·실험·자동 검토 진입점 거절), `doneCriteria`·`checks`·`postChecks`·`env`·`requiredModules`.
- `adapters.ts`/`runtime.ts`: 실제 실행 차단 원인(`cli_missing`·`cli_error`·`flags_unverified`·`real_calls_disabled`·`subscription_unconfirmed`)과 해결 조건, 연결 상태(데모/실제/미설정).
- `page.html`: 상단 연결 상태, "과금 신호 감지 없음"(보장 아님), 실제 모드 비활성+사유, 계약→0 실행 준비→1 Git 계약 검사→2 작업 테스트→3 독립 리뷰→4 승인·통합→5 통합 후 검사.

## 실제 실행한 검사

- `npm run typecheck`(tsc 7.0.2): 오류 없음.
- `npm test`(Node 24.21.0): **31 통과 / 0 실패**, 약 98초.
- `git diff --check`: 통과. 개인 절대경로·비밀값: 커밋 대상에서 검색 결과 없음.
- 브라우저(데모 저장소, `http://127.0.0.1:4111/pair`): 담당·목표·완료 조건·`src_b/` 선택 → 미리보기(자동 ID·브랜치·폴더·기준 SHA·env·검사·계약 파일) → 준비하고 배정 → 에이전트 시작 → 검토 단계(작업 테스트 전 승인 비활성 확인) → 작업 테스트 통과 → fake Codex 리뷰 "승인 의견" → diff → 승인 → 통합 → "통합 후 검사 미지정(미실행)" 표시. `card_condition/` 작업은 "준비 안 됨"·준비 명령 표시·시작 비활성 확인. 확인 대화상자는 자동화에서 수락 처리했다.

## mock 검증 vs 실제 연결 미검증

| 구분 | 항목 |
|---|---|
| mock/fake로 검증 | 위 31개 테스트와 브라우저 흐름. 에이전트=mock 스크립트, 리뷰=fake 리뷰 CLI, 저장소=합성 저장소(실제 `workspace_lock.py` 복사본 + 자체 `.venv`) |
| 실제 연결: 준비 상태·차단까지만 | codex·claude CLI 미설치(PATH 없음)로 "차단 3"과 해결 조건 표시, 실제 리뷰·실행 요청은 차단 사유와 함께 거절 |
| 미검증 | 실제 Codex/Claude 실행·리뷰, 실제 CLI 옵션 값(`workspace-write`, `acceptEdits`, `read-only`, `plan`), 실제 리뷰 CLI 출력 형식, 실제 프로젝트 저장소에서 worktree·계약 커밋·통합, `python-project`의 실제 의존성(합성 `.pth`로만 확인), macOS 알림 표시 |

## 남은 결정

1. **작업 브랜치 준비 주체**: `PAIR_CODING.md`는 Codex가 브랜치·계약을 준비한다고 정한다. 이 도구는 사용자가 화면에서 누를 때 worktree·브랜치·계약 커밋을 만든다. 실제 저장소 사용 전 역할 분담을 정해야 한다(문서 변경은 이번 범위 밖).
2. **리뷰를 승인 조건으로 둘지**: 현재 리뷰는 감사 기록일 뿐 승인 조건이 아니다(사람 판단 우선). 필수로 할지는 사용자 결정.
3. **통합 대상**: 실제 `main` 통합은 Codex 담당. `config.integration`을 어디로 둘지 결정 필요.
4. **실제 CLI 연동**: 설치·구독 로그인 확인·옵션 값 검증은 별도 승인 작업.

## 리스크

- 허용 파일은 사후 diff로만 검사한다. 실행 중 쓰기를 막지 않는다.
- 작업 테스트·통합 후 검사 명령은 사용자 확인 후 실행된다. `node -e`·`python -c`처럼 임의 코드가 가능한 형태는 실행 파일 제한만으로 막지 못하므로 확인 대화상자가 마지막 방어선이다.
- 통합 후 검사는 동기 실행(최대 10분)이며 그동안 통합 잠금을 잡는다. 도중 서버 종료는 `unknown`으로 남고 통합 checkout을 사람이 확인해야 한다.
- 통합 커밋에 작업 계약 파일이 포함된다(PAIR_CODING의 task 문서 커밋 관례와 일치하지만 통합 담당이 원치 않으면 조정 필요).
- 도구는 worktree·브랜치를 만들기만 하고 정리하지 않는다.

## 롤백

`git revert c152ace 67d38f3 7226656 ed68b89 16224c5 69b7f7f b568bcb 145bba9`(최신부터) 또는 브랜치를 `4194bf5`로 되돌리는 것은 Codex 통합 판단에 맡긴다. 로컬 산출물은 `tools/pair-control/{.state,.demo,.mastra,node_modules}` 삭제. 이미 만든 데모 worktree는 `.demo/` 아래에만 있다.

## 작업 트리

인계 커밋 후 `git status --short` 결과를 task 문서 "결과"에 기록한다.
