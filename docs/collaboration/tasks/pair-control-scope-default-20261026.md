# pair-control 허용 범위 기본값 — Claude 배정

- task_id: `pair-control-scope-default-20261026`
- owner: Claude
- status: handoff (코드 커밋 `fa183e96598ce2f7573c0704181963af8b7892c7`)
- base_sha: `b58e244` (claude/pair-control, 미커밋 변경 없음 확인)
- 실행 Node: v24.21.0(nvm)

## 배경

사용자가 "3. 어디를 고쳐도 되나요?"를 매번 채우기 어렵고 디렉터리 제한이 필요 없다고 제안했다. 허용 범위는 실행 중 쓰기를 막는 장치가 아니라(사후 diff 검사뿐) 세 가지 일을 한다: 병렬 작업의 겹침 감지·직렬화, 데이터·라벨·산출물 보호, 범위 밖 변경의 사후 표시. PAIR_CODING.md는 "작업별 소유 파일 분리"와 "허용 파일 대조"를 요구하므로 범위 자체를 없애지는 않고, **비워 두면 기본 범위를 적용**해 사람이 채울 필요를 없앤다.

## 목표

- `allowedFiles`가 비어 있으면 기본 범위 "코드·테스트·문서"(`card_condition/`, `tests/`, `tools/experiments/`, `docs/collaboration/`)를 적용한다. 데이터·라벨·산출물·공용 설정은 기본 범위에 없고, 직접 적어도 금지 경로 규칙은 그대로 막는다. 정리되지 않은 경로(`./` 등) 거부도 그대로다.
- 폼 3번 칸을 "선택"으로 바꾸고 문구·미리보기에 기본 적용 여부를 보여 준다. 좁히려면 직접 적는다(병렬 실행은 범위가 겹치지 않을 때만 가능하다는 안내 포함).

## allowed_files

1. `tools/pair-control/src/executor/prepare.ts` (비었을 때 기본 범위 적용·`scopeDefault` 표시)
2. `tools/pair-control/src/ui/**` (3번 칸 문구·미리보기)
3. `tools/pair-control/test/prepare.test.ts`, `tools/pair-control/test/scope.test.ts`
4. `tools/pair-control/README.md`, 이 문서, `docs/collaboration/reports/pair-control-scope-default-20261026.html`

## forbidden

위 밖 전부. 금지 경로·`./` 거부·충돌 검사·사후 허용 파일 검사의 동작은 바꾸지 않는다. 이미 배정된 작업은 건드리지 않는다.

## 구조 기준

`prepare.ts`는 기존 파일(함수 수 변경 없음, 분기 추가만). UI 모듈 함수 7개 이하 유지.

## checks

1. `npm run typecheck`, `npm test`. 기존 "빈 범위는 실패" 검사는 의도된 동작 변경이므로 "빈 범위는 기본 범위 적용·금지는 여전히 거부"로 바꾼다.
2. 신규: 빈 범위 → ok·기본 4개·`scopeDefault`; 빈 범위로 만든 두 작업은 겹침 경고; 직접 적은 금지 경로·`./`는 여전히 거부.
3. 브라우저(4111, 읽기 전용): 3번 칸·미리보기 문구.
4. 성과·진척 HTML 생성·열기, `git diff --check`, 최종 깨끗한 트리.

## 결과

- 코드 커밋 `fa183e96598ce2f7573c0704181963af8b7892c7` (검사는 같은 작업 트리에서 실행).
- 변경: `planTask`가 허용 파일이 비면 기본 범위 4개를 적용하고 `scopeDefault`를 돌려준다. 폼 3번 칸은 선택으로 바뀌었고 미리보기에 "기본 범위" 표시. 중복이 된 프리셋 버튼·`/pair/api/scope`의 preset 분기는 제거(추출은 유지). 함수 수는 늘지 않았다(prepare.ts 분기 추가, form-scope.js 1개).
- checks: typecheck 통과, `npm test` 75/75(기존 74 + 신규 1). 기존 "빈 범위는 실패" 검사는 의도된 동작 변경이라 "빈 범위는 기본 범위 적용"으로 바꿨다.
- 신규 검사: 빈 범위 → ok·기본 4개·`scopeDefault`·기본 범위끼리 `conflicts()`가 files 겹침으로 판정 / 직접 적은 범위는 그대로 / 금지 경로·`./`는 여전히 거부.
- 실서버(4111, 소스 변경 반영): `POST /pair/api/plan`에 빈 범위 → ok·기본 4개·env python. 브라우저 폼: 목표만 입력 → 미리보기 "기본 범위" 표시·준비 버튼 활성, 콘솔 오류 0.
- 미확인: 폼을 끝까지 제출해 실제 작업을 만드는 흐름(실제 worktree 생성이라 하지 않음).
- 알려진 한계: 기본 범위에는 `card_condition/`가 있어 빈 범위로 만든 작업은 항상 `./develop` 잠금과 자체 `.venv`가 필요하다(준비 단계). 기본 범위끼리는 직렬화된다.
- 롤백: 코드·문서 커밋 `git revert`. 이미 배정된 작업은 바뀌지 않는다.
