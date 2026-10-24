# 面 근거 메타데이터 계약 검토

- task_id: `side-evidence-contract-20261025`
- owner: Claude
- status: assigned
- base_sha: `c7c4b8de9d6eeb751743367424729734c00e4b73`
- branch: `claude/side-evidence-contract-20261025`
- worktree: Codex 전달 메시지에서만 로컬 경로 제공

## 목표와 계약

직전 출처 보고서의 side_evidence 제안을 구현 전에 검토한다. 원본 inventory/side/target/수량을 바꾸지 않는 별도 sidecar의 최소 JSON 예시와 수용 조건을 보고서 한 개로 제시한다. 실제 도구 구현이나 채택은 이번 범위가 아니다.

검토할 문제: human_statement/review_slot_only/missing_source/codex_anchor_eligibility는 서로 배타적인가? 아직 조사하지 않은 행과 원본이 누락된 행을 어떻게 구분하는가? 파일 SHA와 JSON 필드/행 식별자로 근거를 연결하고, 파생 기록 중복을 독립 증거로 세지 않는가? 면 근거와 결함 정답·좌표·3x3 구역 증거를 구별하는가? sidecar가 다른 inventory 버전에 잘못 적용되는 것을 어떻게 거절할 것인가?

기존 보고서에서 확인된 photo-1/photo-3/photo-4, eevee Y, raichu 사례를 합성 ID로 예시화한다. 확인되지 않은 면·날짜·사람 정답은 생성하지 않는다. 구현용 성공/거절 사례를 작은 표로 제시하고 결정이 필요한 항목을 명시한다. 보고서 한 개로 계약을 확정할 수 없으면 미해결로 남긴다.

## allowed_files

- `docs/collaboration/tasks/side-evidence-contract-20261025.md`
- `docs/collaboration/reports/side-evidence-contract-20261025.md` (신규)

그 외 파일은 읽기 전용이다. Python/테스트/원본 inventory/라벨/사진/모델/진척률/관제 UI/다른 worktree 변경 금지. Codex는 감사 보고서 출력의 실패 안전성을 별도 파일 범위에서 수정한다.

## checks

- AGENTS.md, PAIR_CODING.md와 직전 두 provenance 보고서를 읽는다. 기존 추적 보고서만으로 검토하며 원본 snapshot의 재해석이 필요하면 누락 근거를 적는다.
- 표준 라이브러리로 보고서 JSON 예시의 문법과 거절/보존 조건의 내부 일관성을 확인한다. 의존성 설치·사진 열람·모델 추론·학습·외부 AI·review 실행 없음.
- `git diff --check`; base 이후 변경이 allowed_files 2개뿐인지 대조한다. 홈 절대경로·비밀값·사람 원문 전체 인용 금지.
- side_evidence가 면 확인 여부나 정답 변경을 자동으로 뜻하지 않음을 명시한다. 조사 안 함을 missing_source로 채우지 않는다.

## 인계

status ready_for_review, 전체 SHA·부모·파일·검사·미해결·리스크·롤백을 전달한다. 커밋 `docs(provenance): 면 근거 sidecar 계약 검토`. main 통합/push 금지. 롤백은 미통합 또는 문서 커밋 revert. 실험/성능 변화 없음.
