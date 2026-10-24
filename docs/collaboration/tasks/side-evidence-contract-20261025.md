# 面 근거 메타데이터 계약 검토

- task_id: `side-evidence-contract-20261025`
- owner: Claude
- status: integrated
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

## Claude 실행 결과

2026-10-25, 배정 worktree에서 실행. 보고서: `docs/collaboration/reports/side-evidence-contract-20261025.md`.

- 기준:
  - 브랜치 `claude/side-evidence-contract-20261025`, 시작 HEAD `df899e695fd48143d10797136025ca8f7551a454`.
  - `merge-base --is-ancestor c7c4b8d… HEAD` 종료코드 0. 시작 시 작업 트리가 깨끗했고, base 이후 변경은 이 문서뿐이었다.
- 근거: 추적 보고서 2개(data-coverage-provenance, provenance-source-followup의 Codex 보정 포함)만 읽었다. 원본 snapshot은 이 worktree에 없으며, 재해석하지 않았다.
- 결론:
  - 직전 단일 값 제안은 그대로 구현하지 않는다.
  - 대신 행별 `evidence` 목록을 둔다. 유형은 배타적이지 않다.
  - 미조사는 `review.status=not_reviewed`, 참조된 원본 누락은 `missing_sources`, 참조 없이 찾지 못한 경우는 `searched_no_side_evidence`로 구분한다.
  - 파생 사본은 `origin`으로 묶어 독립 수에서 제외한다.
  - `claim=side`만 허용한다.
  - inventory 경로·SHA와 행별 `row_id`·`image_sha256`·`side_claim`이 모두 맞아야 적용한다.
  - 수용 3건(A1–A3)과 거절 12건(R1–R12)을 정했다.
- 검사:
  - 보고서 JSON 예시를 표준 `json`으로 파싱했다.
  - 표준 라이브러리 스크립트로 확인한 결과, 예시의 내부 규칙 위반은 0건이었다. 변형 대조에서 A2는 수용(origins 1 유지)됐고, R3–R8·R12는 거절됐다. 스크립트는 커밋하지 않았다.
  - R1·R2·R9–R11은 원본 파일이 없어 검사하지 않았다.
  - `git diff --check` 통과. base 이후 변경은 allowed_files 2개다. 홈 절대경로·비밀값·사람 원문 인용이 없다.
- 미해결(보고서 4절):
  - 저장 위치·작성자·버전 정책
  - pointer 형식과 한 응답 안의 사진별 대응
  - anchor·slot 항목을 evidence에 둘지 context로 분리할지
  - 충돌을 경고로 둘지 A3 차단으로 둘지(사람 판단)
  - snapshot 밖 원본 참조 처리
- 리스크:
  - `human_statement_matches_claim`을 면 확정이나 편입 승인으로 읽으면 안 된다.
  - 합성 SHA·경로를 실제 파일에 적용하면 안 된다.
  - 계약 초안(v0-draft)이며 구현·채택되지 않았다.
- 롤백: 미통합이면 반영하지 않는다. 통합 후에는 이 문서 커밋만 revert한다. 원본 데이터·모델·코드는 변경하지 않았다.
- 미실행: 도구 구현, 사진 열람, 추론, 학습, 외부 AI 호출, 라벨 변경 모두 0회.

## Codex 인수

문서 초안으로 수용·통합했다. 원본 위치 수와 독립 사람 판단 수를 구분하고 source/origin 양쪽 검증 필요를 보고서에 보정했다. JSON 4행·파생 사본 중복 제거·10개 거절 변형을 직접 재검증했다. R1·R2·R9–R11은 실제 원본 대조 미실행이며 미해결 결정 5개는 보존했다. 문서 통합은 구현 계약 확정·도구 채택을 뜻하지 않는다. 진척 30/100 유지, 학습·추론·외부 AI 0회.
