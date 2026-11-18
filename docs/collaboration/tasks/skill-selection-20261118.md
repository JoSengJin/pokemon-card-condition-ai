# Superpowers 스킬 선택표 반영 · 계약과 인계

task_id: skill-selection-20261118
owner: Claude (사용자 직접 요청, 메인 계약 선행 없음 — 통합 전 Codex 확인 필요)
status: integrated
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


## Codex main 통합 검증 — 2026-11-18

- 전달 SHA `937570d7f00d2a34247583cf837fe7b4311a2de0`를 `./develop -- git cherry-pick -x`로 통합했다. 통합 SHA `df5dcd1add6eefee8d275a4ac2b1de62682c9093`. 원본 Claude 브랜치/checkout은 수정하지 않았다.
- 기본 checkout 실제 Python 3.12.14/설치 의존성으로 통합 전·후 document_routes 5개, review_rules 6개, high_fixes 26개 모두 통과. 추가 모듈 대역·설치 없음. 검사 대상 SHA와 명령·종료 코드·로그·파일 SHA-256은 ignored `artifacts/skill-selection-integration-20261118/{baseline.json,baseline-high-fixes-isolated-lock.json,integrated.json}`에 보존했다.
- 최초 high_fixes 실행은 상속한 기본 checkout 잠금 FD가 임시 fixture root와 달라 실패했다. 부모 잠금은 유지하고 임시 root 검사 자식의 상속 FD만 제거한 재검사에서 통과했다. 코드·잠금 가드 변경 없음. 최초 실패 로그도 보존했다. Claude의 worktree 오류 27건과 이번 실제 검사 26개를 같은 결과로 비교하지 않는다.
- AGENTS.md 14,801bytes, review-rule 8블록과 기존 지침 보존. 지침21줄+task53줄=총74줄 추가를 대조했다. main 대비 입력 한도 브랜치의 변경에는 두 지침 파일이 없었고 cherry-pick 충돌 없음.
- 선택표의 격리 확인 조건, task base_sha, task checks 우선 보정을 수용했다. 이번 적용: receiving-code-review/verification-before-completion 원문 전체 및 읽기 전용 ponytail-review 원문 전체. RED/GREEN 기능 추가는 해당 없음(문서 통합); 회귀 검사는 baseline/integrated로 분리했다. writing-skills는 앞65행만 추가 확인했으며 전체 검토라고 주장하지 않는다.
- HTML 산출물: ignored `artifacts/skill-selection-integration-20261118/index.html`. 정적 내용 대조 완료. macOS open은 호환 앱 부재(-10661)로 실패했고 Codex 브라우저 열기 요청은 queued다. 실제 열기·렌더는 미확인. 상세 `opening.json`.
- 개발 진척은 `usable-card-analysis-v1.13` 78/100 유지. 전체 suite·실카드 학습/추론·라벨/사진 열람·외부 모델 호출은 미실행. 준수율·토큰 효과·모델 정확도 개선은 미측정.
- 통합 결과 코드·지침 변경은 원본과 같고 이 절과 status만 main 인계 기록으로 추가했다. 원격 동기화 결과와 worktree 보존 판단은 ignored 통합 기록에 남긴다. 롤백 시 인계 기록 커밋 다음 통합 SHA를 역순으로 `./develop -- git revert`하고 관련 검사 후 일반 push한다.
