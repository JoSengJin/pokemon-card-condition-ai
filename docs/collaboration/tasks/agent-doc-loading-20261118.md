# 에이전트 문서 로딩 개선 · 설계와 실행 계획

task_id: agent-doc-loading-20261118
owner: Codex
status: implementing
base_sha: 574775949b0e2a931247ad5bb9d320fc89f9ec5a
branch: codex/agent-doc-loading-20261118

## 승인과 목표

사용자 요청: 추천 순서대로 개선하고 기존 지침·승인 범위를 빠뜨리지 않으며 Codex와 Claude 모두 필요한 문서를 읽도록 정리하고 오류·부작용을 테스트한다. 이 요청은 문서·로딩 코드·mock 회귀 검증의 승인이다. 새 실험·실제 AI 호출·모델/라벨/기준 변경을 승인하지 않는다.

## 설계

문장 prefix 대신 8개 고정 review-rule ID 블록을 읽는다. 반환값은 기존과 동일한 규칙 본문 문자열이며 ID 누락·중복·빈 본문·잘못된 경계는 오류로 중단한다. AGENTS가 없는 합성 프로젝트의 기존 빈 문자열 동작은 유지한다. 새로운 문서가 있는 실제 저장소는 8개 ID를 필수로 한다. 모든 기존 지침을 원문 대조하고 진척 버전 참조만 정본 연결로 고친다.

README의 과거 전체 내용은 보관하고 루트는 현재 안내·정본·작업별 필독 경로로 축소한다. 실험 계약의 자동 검토 상세를 별도 필독 문서로 분리하되 모든 문장을 보존한다. PROGRESS_CRITERIA.md·development-progress.json·PAIR_CODING.md·라벨 규약은 변경하지 않는다. CLAUDE.md는 @AGENTS.md만 가져와 두 개의 규칙 정본을 만들지 않는다. AGENT_START는 현재 상태의 정본을 찾는 안내이며 날짜별 인계를 현재 승인으로 만들지 않는다.

## 접근 비교

- 문장 prefix 유지 + 문서만 정리: 문구 변경 누락을 해결하지 못하므로 제외.
- 모든 문서 자동 import: 불필요한 컨텍스트·하위 검토 예산 증가로 제외.
- 채택: 고정 ID + 짧은 공통 입구 + 작업별 필독 문서. 사용자가 승인한 추천 순서를 그대로 적용한다.

## allowed_files

- AGENTS.md
- CLAUDE.md
- README.md
- COMMON_EXPERIMENT_RECORDS.md
- CLAUDE_HANDOFF_20261024.md
- docs/AGENT_START.md
- docs/agent/AUTO_REVIEW_CONTRACT.md
- docs/history/README_BEFORE_AGENT_GUIDE_20261118.md
- docs/history/README.md
- card_condition/cross_review_auto_sources.py
- tests/test_agent_review_rules.py
- tests/test_agent_document_routes.py
- tests/test_cross_review_high_fixes.py
- docs/collaboration/tasks/agent-doc-loading-20261118.md
- docs/collaboration/reports/agent-doc-loading-20261118.md
- ignored artifacts/agent-doc-loading-20261118/ (검증 로그·보존 대조·HTML)

## 구조·입출력

cross_review_auto_sources.py 함수 정의 6→6, review_rules(path)→str 인터페이스 보존. review_context→review_rules는 1회 전이이고 파싱에서 다른 사용자 정의 함수를 호출하지 않는다. 새 테스트 파일도 정의 수 각각 최대 7개. 실행기·격리·프롬프트 32,000 byte 상한·승인 가드는 유지한다.

## 실행 계획 (writing-plans / inline)

- [ ] 1. 새 고정 ID·문구 변경·누락/중복·빈 본문·프롬프트 호환 테스트를 먼저 실패시킨다.
- [ ] 2. review_rules를 최소 변경하고 기존 8개 본문과 일치·문구 변경 후 유지·잘못된 규칙 거부를 확인한다.
- [ ] 3. 기존 지침·승인 원문을 대조하며 README 이력 분리·현재 정본 연결·작업별 읽기 입구·Claude import를 적용한다.
- [ ] 4. 문서 경로·지침 보존·바이트 예산·기존 mock 교차 검토와 전체 unittest를 검사한다. 실제 provider 호출·학습/사진 추론은 하지 않는다.
- [ ] 5. 변경 파일·핵심 diff·실제 검증·미검증·리스크·롤백을 보고서/HTML에 기록하고 기본 checkout에서 통합 검증 후 origin/main에 일반 push한다.

## checks / handoff

HTML: artifacts/agent-doc-loading-20261118/index.html. 내용 대조·열기·렌더 확인은 각각 실제 결과를 기록한다. 지침 누락 보호는 시작 커밋의 모든 AGENTS bullet과 보관 README·분리한 실험 계약을 대조한다. 롤백은 최종 통합 커밋의 git revert 후 검사·일반 push. 기존 untracked .claude/와 다른 worktree는 수정하지 않는다.
