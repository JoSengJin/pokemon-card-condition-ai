# pair-control 허용 파일 자동 추출·프리셋·"./" 거부 — Claude 배정

- task_id: `pair-control-scope-extract-20261026`
- owner: Claude
- status: implementing
- base_sha: `98712e8` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 배경

task-1026-1이 허용 파일 `./`로 배정되어 Git 검사의 허용 파일 범위가 전부 실패했다. `isAllowed`는 `./`로 시작하는 경로와만 비교해 어떤 파일도 맞지 않았고, 금지 경로 검사(`isForbidden`)와 충돌 검사(`pathsOverlap`)도 `./`를 통과시켰다. 사용자는 전달받은 프롬프트로 작업할 때 범위를 몰라 저장소 전체를 넣으려 했다.

## 목표

1. 정리되지 않은 허용 경로(`./`, `.`, `./docs/`, `a//b`, `a/./b`, 끝이 `/.`)를 계약 검증에서 거부한다. 저장소 전체를 허용하는 표기는 어떤 형태로도 받지 않는다. 폼 미리보기("계약 규칙")와 `assign`(API 직접 호출) 모두에서 같은 규칙이 걸린다.
2. 전달받은 프롬프트에서 "허용 파일" 목록을 글자 그대로 추출한다(언어 모델 없음, 추측 없음). 찾지 못하면 아무것도 채우지 않고 알린다. 금지 경로·절대경로·glob·저장소 전체 표기는 제외하고 이유를 보여 준다. 붙여 넣은 프롬프트는 저장·커밋하지 않는다(개인 절대경로가 들어 있을 수 있음).
3. 프리셋 "코드·테스트·문서": `card_condition/`, `tests/`, `tools/experiments/`, `docs/collaboration/`. 데이터·라벨·산출물·공용 설정은 포함하지 않는다.

## allowed_files

1. `tools/pair-control/src/executor/contract.ts` (허용 경로 규칙)
2. `tools/pair-control/src/executor/scope.ts` (신규: 추출·프리셋)
3. `tools/pair-control/src/mastra/index.ts` (경로 1개)
4. `tools/pair-control/src/ui/**` (폼 칸·버튼, 신규 `js/form-scope.js`)
5. `tools/pair-control/test/scope.test.ts` (신규), 기존 테스트에 `./` 거부 1건 추가 가능
6. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-scope-extract-20261026.html`

## forbidden

위 밖 전부. 이미 배정된 작업(task-1026-1 포함)의 계약·상태는 바꾸지 않는다. 사용자의 4111 서버를 재시작하지 않는다. 실제 작업에 버튼을 실행하지 않는다.

## 구조 기준

- `scope.ts`·`form-scope.js` 함수 7개 이하. 호출 전이 4회 이하. 폼 클릭 `onScopeClick → api`, 서버 `route → extractScope → gather → pathsIn → checkPath`.

## checks

1. `npm run typecheck`, `npm test`(기존 69 + 신규).
2. 신규 검사: `./`·`.`·`./docs/`·`a//b` 거부, 정상 경로 유지; 추출(inline·목록·번호 목록·못 찾음·금지/절대/glob 제외·중복 제거·`./a.py` 정리); 프리셋 4개 경로 + 계약 통과 + 금지 경로 없음; planTask·assign 모두 `./` 거부.
3. 브라우저(4111, 읽기 전용): 새 칸·버튼 렌더. 서버는 재시작하지 않으므로 새 경로는 별도 포트 데모 없이 테스트로 검증하고 그 한계를 보고서에 적는다.
4. 성과·진척 HTML 생성·열기, `git diff --check`, 최종 깨끗한 트리.

## 결과

(인계 시 갱신)
