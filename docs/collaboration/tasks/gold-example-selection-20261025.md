# 기준 예제 선택 결과 기록

- task_id: gold-example-selection-20261025
- owner: Claude
- status: ready_for_review
- base_sha: c8315fff4668dae573e0de41c75556db55ea8e38 (data-acquisition-followup 인계 커밋 다음에 통합)
- branch: claude/gold-example-selection-20261025
- 배정 경위: 사용자가 선택 페이지에서 저장한 결과를 기록하도록 이 세션에서 요청했다. 인계한 이전 브랜치에는 커밋하지 않았다.
- goal: 사용자의 예제 사용·제외 선택을 검증해 기록하고, 비어 있는 예제 칸과 확인이 필요한 항목을 명시한다.

## allowed_files (신규)
- docs/collaboration/tasks/gold-example-selection-20261025.md
- docs/collaboration/reports/gold-example-selection-20261025.md
- docs/collaboration/reports/gold-example-selection-20261025.html
- ignored: artifacts/gold-example-selection-20261025/{gold-example-selection-20261025.json, gold-example-candidates.json}

## forbidden
라벨·manifest·정답 수정, 이전 task 문서, 코드, 진척 기준. 학습·추론·외부 AI 호출.

## handoff / checks

| 검사 | 결과 |
|---|---|
| 선택 파일 SHA256 | `10855cf9018ff1c936300300cc18004693b65b29d1b79dfef03a5aa5ae3255f4` |
| 후보 목록과 식별값 대조 | 34/34 일치, 미결정 0 |
| 집계 | 사용 25, 제외 9. 질문×면×정답 20칸 중 2개 칸 10, 1개 칸 5, 0개 칸 5 (스크립트 재집계) |
| 확인 필요 | #1 "사용" 선택인데 이유 칸에 "결함 안 보여". 예제에서 보류하고, 정답은 수정하지 않음 |
| 정답 변경 | 없음 |
| HTML 정적 검사·렌더 | script 0·외부 링크 0·홈 경로 0. headless Chrome 1100px 렌더 확인(표 10행·확인 필요 박스 표시). `open` 요청 |

롤백: 미통합이면 반영하지 않는다. 통합 후라면 `git revert`.
