# 자료 확보 병목 해소 준비

- task_id: data-acquisition-strategy-20261025
- owner: Claude
- status: ready_for_review
- base_sha: de33cab25aeb78ee2596343ab6d69c95dcf6d398
- branch: claude/data-acquisition-strategy-20261025
- worktree: 세션에서만 전달(로컬 경로는 커밋하지 않음)
- 배정 경위: Codex가 사전 배정한 계약이 없다. 사용자가 이 세션에 직접 요청했다. 새 파일만 추가하므로 다른 task의 소유 파일과 겹치지 않는다. A3 수집 task(`a3-data-intake-batch-20261025`)와는 결과를 연결만 하고, 그 task의 파일은 수정하지 않는다.
- goal: 사용자 전수 라벨링을 줄이는 자료 확보 방법을 근거로 좁히고, 바로 시작할 수 있는 다음 검증 1개의 계획·측정표·지침 초안을 준비한다.

## allowed_files (모두 신규)

- docs/collaboration/tasks/data-acquisition-strategy-20261025.md
- docs/collaboration/reports/data-acquisition-strategy-20261025.md
- docs/collaboration/reports/data-acquisition-strategy-20261025.html
- docs/collaboration/reports/data-acquisition-sources-20261025.md
- docs/collaboration/reports/card-photo-labeling-guide-draft-20261025.md
- docs/collaboration/reports/data-acquisition-pilot-plan-20261025.md
- docs/collaboration/reports/data-acquisition-pilot-sheet-20261025.csv

## forbidden

모델·worker·card_condition/·tests/·tools/·기존 라벨·manifest·ADOPTION·진척 기준과 점수·검토 UI·의존성·운영 코드·다른 task 문서. 학습·사진 추론·Gemini/Codex 호출·자동 검토·실험, 독립 시험 자료 탐색, 다운로드·로그인·연락 발송, main 통합과 push.

## structure

코드 변경이 없어 함수 수와 호출 깊이는 해당 없음. 검사용 임시 스크립트는 세션 scratchpad에만 두었고 커밋하지 않았다.

## experiment

없음. 파일럿은 계획만 했다. 실행에는 사용자 승인과 협력자 확보가 필요하다. 파일럿은 모델 실험이 아니므로 `./experiment` 대상이 아니다. 이 판단은 계획 문서에 적었다.

## handoff

- 입력 근거(읽기 전용): `artifacts/development-manifest-20261025d/ADOPTION.json`, `DECISION.md`, `coverage.json`(SHA256 `143164a4e04bfe3aaabea4fe852a985a671e587b8471cf996d70a15108c5060d`), `combined-reviewed.jsonl`(SHA256 `ad021468b3cd4483b6b335f3b170e452343b6001808725e9faedc4f6635aa935`, ADOPTION과 일치). A3 task 브랜치 tip `6c0d7ba`의 round2 `acquisition.json`, round2-live 응답 없음(바이트 동일).
- 요청서와의 차이: 출발점으로 지정된 c 대신 최신 채택본 d를 기준으로 삼았다. main은 785e21f에서 de33cab로 진행됐다(자료와 무관한 커밋).
- 실제 확보량: 사진 0, 사람 정답 0, 실물 0, 연락 0, 다운로드 0.
- 진척: 30/100(v1.0) 유지. A3·D1 pending.
- 검사 결과: 커밋 직전 실행 결과를 아래에 기록한다.

### checks

| 검사 | 결과 |
|---|---|
| 보고서 부족표 20행과 d `coverage.json` 대조(스크립트) | 20/20 일치. 수량 충족 val 0·train 2 |
| d manifest SHA와 ADOPTION.json 대조 | 일치(`ad021468…`) |
| round2 응답 저장 여부(`labels-review.jsonl` 대 `.before`) | 바이트 동일 → 응답 없음 |
| HTML 정적 검사 | 태그 짝 오류 0, `<script>` 0, 외부 src/href 0, 홈 절대경로 0 |
| 추적 문서 7개의 홈 절대경로 | 0 |
| CSV 열 수 일관성 | 22열 일치 |
| `git diff --cached --check` | 통과(커밋 직전) |
| 기본 checkout 상태 | 수정 없음(`git status` clean) |
| HTML 열기 | macOS `open` exit 0, Claude 앱 미리보기 창에 로드됨. 화면 캡처 도구가 로컬 파일을 지원하지 않고 Playwright는 다른 세션이 사용 중이어서 **렌더는 도구로 확인하지 못함** |

미실행: coverage 재계산, 외부 다운로드, 학습·추론·Gemini·Codex 호출, 사람 라벨 요청, 협력자 연락, 모바일 폭 렌더 확인.

리스크: 공개 썸네일 표본이 작다(첫 화면 12장, 파일명 50개). 파일럿 기준값은 사전 근거가 없는 제안값이다. 협력자를 아직 확보하지 못했다. 독립 판정 단계에서는 사용자의 "hi 후보 미리 표시" 선호를 적용하지 않으므로 사용자 확인이 필요하다.

롤백: 미통합이면 반영하지 않는다. 통합 후라면 `git revert <SHA>`. 데이터·모델·manifest 복구는 필요 없다.
