# pair-control 작업 화면을 파이프라인 방식으로 — Claude 배정

- task_id: `pair-control-pipeline-ui-20261025`
- owner: Claude
- status: implementing
- base_sha: `e7883780c3ca735ed3a3bb6d76117b0378d282c8` (시작 HEAD, 미커밋 변경 없음 확인)
- branch: `claude/pair-control`
- 실행 Node: v24.21.0(nvm)

## 목표

작업 상세 화면을 ArgoCD처럼 **단계 노드가 이어진 파이프라인**으로 바꿔, 처음 보는 사람도 "지금 어느 단계이고, 누구 차례이며, 다음에 무엇을 누르는지"를 알 수 있게 한다. 단계별 상세·버튼은 해당 노드를 눌렀을 때만 보인다. 서버 동작(실행기·workflow·API 의미)은 바꾸지 않는다.

## allowed_files

1. `tools/pair-control/src/ui/**` (page.html, 새 `js/*.js` 모듈)
2. `tools/pair-control/src/mastra/index.ts` (화면 모듈 정적 제공 경로 1개 추가만)
3. `tools/pair-control/test/ui-stages.test.ts` (신규: 단계 판정 단위 검사)
4. `tools/pair-control/README.md` (화면 설명)
5. `docs/collaboration/tasks/pair-control-pipeline-ui-20261025.md` (이 문서)
6. `docs/collaboration/reports/pair-control-pipeline-ui-20261025.html` (HTML_REPORTING 성과·진척 보고, 공개 가능한 내용·상대경로만)

## forbidden_files

위 목록 밖 전부. 실행기(`src/executor/**`), workflow, 다른 테스트의 동작, Python 코드·데이터·진척률, AGENTS.md·PAIR_CODING.md는 바꾸지 않는다. 사용자가 실행 중인 4111 서버를 종료·재시작하지 않는다(화면 확인은 읽기 전용 동작만).

## 구조 기준 (PAIR_CODING: 파일당 함수 정의 최대 7개, 호출 전이 최대 4회)

- 해석(미확정 시 리뷰어 확인 필요): 이름 있는 함수(함수 선언, 이름에 대입한 화살표/함수 식, 객체 메서드)를 센다. `map`/`forEach`/이벤트 등록에 인라인으로 넘기는 익명 콜백은 별도 함수로 세지 않되, 그 안에서 다른 함수를 호출하면 호출 경로에 포함한다.
- 변경 전: `src/ui/page.html` 인라인 스크립트 36개(제한 초과), `src/mastra/index.ts` 5개.
- 변경 후 목표: `page.html`은 마크업·스타일만(0개), 화면 로직은 `src/ui/js/*.js` 모듈로 나눠 파일마다 7개 이하. `index.ts`는 6개 이하.
- 호출 시작점: 주기 갱신(`refresh`), 로그 갱신(`pollLog`), 클릭·입력 위임 처리기, 폼 입력 처리기. 각 시작점에서 전이 4회 이하로 설계한다. 다시 그리기는 `setTimeout(refresh)` 또는 `ui.rerender`(함수 참조)로 별도 시작점에서 실행되므로 정적으로 이어지지 않는다 — 이 동적 경로는 인계 문서에 적는다.
- 실행기·workflow 등 이번에 바꾸지 않는 기존 파일의 함수 수 초과는 이 작업 범위 밖이며 인계에 남는 부채로 기록한다.

## 단계(노드)

준비 → 구현 → Git 검사 → 작업 테스트 → 리뷰(선택) → 메인 인계 → 사람 승인 → 통합 → 통합 후 검사 → 푸시. 상태: 완료·진행 중·내 차례(행동 필요)·실패·주의·대기·건너뜀(선택). 각 단계는 작업 상태·검사 결과·인계·승인·통합·푸시 기록에서 파생하며 저장하지 않는다.

## checks

1. `npm run typecheck`, `npm test`(기존 60 + 단계 판정 단위 검사).
2. 새 파일별 함수 수와 주요 호출 경로 전이 수를 계산해 인계에 기록.
3. 브라우저에서 데모(합성) 저장소로 파이프라인 노드 클릭·다음 행동 버튼·단계 상세 확인. 사용자의 4111 서버에서는 화면 읽기 전용 확인만.
4. 성과·진척 HTML 생성·내용 대조·열기(열기 요청 성공과 렌더 확인을 구분해 보고).
5. `git diff --check`, allowed_files 대조, 개인 절대경로·비밀값 미포함, 최종 `git status --short` 깨끗함.

## 결과

(인계 시 갱신)
