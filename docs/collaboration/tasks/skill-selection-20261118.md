# Superpowers 스킬 선택표 반영 · 계약과 인계

task_id: skill-selection-20261118
owner: Claude (사용자 직접 요청, 메인 계약 선행 없음 — 통합 전 Codex 확인 필요)
status: ready_for_review
base_sha: 1e0debcb3b5048c9615e229d918135fb8607a112
branch: claude/skill-selection-20261118

## 목표

Codex·Claude가 같은 개발 절차 스킬 선택표를 따르게 한다. 새 승인·권한은 부여하지 않는다. 모델 정확도 개선·토큰 절감은 주장하지 않는다(미측정).

## 근거

- Codex 자문(스킬 본문 대조): 선별 도입, 프로젝트 승인·잠금·역할·통합 규칙 우선.
- 스킬 15개 판정: 기본 4, 조건부 5, 제외 6. 미검토였던 4개(dispatching-parallel-agents, receiving-code-review, diagnosing-superpowers, writing-skills)는 본문을 읽고 판정했다. writing-skills는 앞 60행과 키워드 검색만 했다(부분 열람).
- 실제 사용 흔적: docs/collaboration/reports/blind-observation-packet-20261117.md 34행.

## allowed_files

- AGENTS.md (새 `- ` 줄 1개 추가, 기존 줄 변경 없음)
- docs/AGENT_START.md (선택표 섹션 추가)
- docs/collaboration/tasks/skill-selection-20261118.md (이 파일)

## forbidden_files

데이터·라벨·비밀 설정, review-rule 블록, 코드, 다른 task 소유 파일(진행 중 `codex/agent-input-limit-clarity-20261118`은 이 두 문서를 수정하지 않음을 `git diff --stat main...`로 확인).

## structure

코드 변경 없음. 함수 수·호출 경로 해당 없음.

## checks (실제 실행)

환경: worktree 전용 .venv(Python 3.12.14, 의존성 미설치). PIL·torch·numpy·httpx 등 무거운 의존성은 스크래치패드의 임시 대역(MagicMock)으로 채웠다. 대역은 저장소에 없다.

- `git diff --stat`: 2 files, 21 insertions, 삭제 0줄. `git diff --check` 통과.
- AGENTS.md 14,507 → 14,801바이트(한도 16,384 미만).
- tests/test_agent_document_routes.py 5개 통과(수정 전도 통과).
- tests/test_agent_review_rules.py 6개 통과(수정 전도 통과).
- tests/test_cross_review_high_fixes.py: 수정 전·후 모두 27 오류. 원인은 worktree에 없는 ignored `nemotron-review.json`과 미설치 `langgraph`이며 이번 변경과 무관.
- 전체 suite, 학습, 추론, 라벨 접근, 외부 모델 호출, 사람 판정 요청, main 통합, push는 미실행.

## 미이행·리스크

- 의존성 대역을 쓴 실행이라 기본 checkout에서 실제 환경으로 위 두 테스트를 다시 돌려야 한다.
- 선택표의 "기본 사용" 판정은 스킬 본문 일부 열람과 Codex 자문에 근거한다. 준수율·토큰 효과는 미측정이다.
- HTML_REPORTING.md의 성과·진척 HTML은 이번 문서 변경에 만들지 않았다(진척률·성능 수치 변동 없음). 통합 담당이 필요하다고 판단하면 별도로 생성한다.
- 선택표는 Codex의 기존 Superpowers 사용 습관도 제한한다. Codex 확인 필요.

## 롤백

`git revert <이 브랜치 커밋 SHA>` 또는 브랜치 폐기. 기본 checkout은 변경하지 않았다.
