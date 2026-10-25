# 자료 확보 후속 준비 (기준 예제·대조 규칙·동의서)

- task_id: data-acquisition-followup-20261025
- owner: Claude
- status: ready_for_review
- base_sha: 3b498c61fe4e5aab5abb087794828260dcd74baf (data-acquisition-strategy-20261025의 인계 커밋. 그 다음에 이어서 통합해야 함)
- branch: claude/data-acquisition-followup-20261025
- 배정 경위: 사용자가 이 세션에서 직접 요청했다. 이전 task 브랜치에는 커밋을 추가하지 않고 새 task로 분리했다. 새 파일만 추가한다.
- goal: 파일럿을 시작하기 전에 필요한 문서 3개를 사용자 입력 없이 준비한다. 기준 예제 후보, 2인 응답 대조 규칙, 협력자 동의서 초안이다.

## allowed_files (모두 신규)

- docs/collaboration/tasks/data-acquisition-followup-20261025.md
- docs/collaboration/reports/gold-example-candidates-20261025.md
- docs/collaboration/reports/pilot-comparison-rules-20261025.md
- docs/collaboration/reports/collaborator-consent-draft-20261025.md
- docs/collaboration/reports/data-acquisition-followup-20261025.html
- ignored: 자기 worktree의 `artifacts/data-acquisition-followup-20261025/gold-example-candidates.json`

## forbidden

이전 task의 문서, 모델·worker·card_condition/·tests/·tools/, 라벨·manifest·ADOPTION, 진척 기준, 검토 UI, 의존성. 학습·추론·외부 AI 호출, D1 탐색, 연락 발송, main 통합·push.

## structure

코드 변경 없음. 후보 선별 스크립트는 세션 scratchpad에만 두었다(함수 정의 0개, 단일 스크립트). 규칙은 기준 예제 문서에 적었다.

## handoff

- 입력(읽기 전용): `artifacts/development-manifest-20261025d/coverage.json` SHA256 `143164a4e04bfe3aaabea4fe852a985a671e587b8471cf996d70a15108c5060d`, manifest `ad021468…`. `card_condition/review.py`(사본별 box 저장), `card_condition/data_coverage.py`(단위 투영 규칙).
- 결과:
  - 기준 예제 후보 34개, 실물 22개, 모두 train.
  - 후보가 2개 미만인 셀 4개: 모서리 정상 앞뒤 0, 엣지 앞 정상 1, 관찰제한 앞 양성 1. 모서리 정상 단위 24개는 모두 box 미확인이다.
  - ignored 후보 JSON SHA256: `11b5a36ddddc69824d1f9728d5bcc1e21f1493339753452b64ba061299b62915`
- 실제 확보량: 사진 0, 사람 정답 0, 실물 0. 진척 30/100 유지.

### checks

| 검사 | 결과 |
|---|---|
| 기준 예제 표 34행과 ignored JSON 대조 | 34/34 일치. 실물 22, val 0건, truth_changed=false, model_scores_used=false |
| 모서리 정상 단위의 box 상태 재집계 | 24개(train 앞13·뒤5, val 앞4·뒤2) 모두 box_reviewed=false |
| HTML 정적 검사 | 태그 짝 오류 0, script 0, 외부 링크 0 |
| 추적 문서의 홈·임시 경로 | 0 |
| `git diff --cached --check` | 통과 |
| 기본 checkout | 수정 없음 |
| HTML 렌더 | headless Chrome 1100px 스크린샷으로 확인: 제목·KPI·표·절 모두 표시. 500px(headless 최소 폭)에서 이전 task HTML 포함 두 파일 모두 scrollWidth=innerWidth로 가로 넘침 없음. 390px 실기 폭은 미확인 |
| HTML 열기 | macOS `open` 요청(아래 커밋 후 실행) |

미실행: 대조 규칙 구현, 파일럿 실행, 사용자 예제 승인, 동의서 발송.

리스크: 예제 대부분이 판매 사진이라 사진 파일을 외부로 전달하면 안 된다. 대조 규칙은 main의 `coverage_report` 동작에 의존한다.

롤백: 미통합이면 반영하지 않는다. 통합 후라면 `git revert`. 데이터 복구는 필요 없다.
