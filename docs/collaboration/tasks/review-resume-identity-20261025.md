# 같은 근거의 자동 검토 재개

- task_id: `review-resume-identity-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `ee8a983` (main)
- branch: `codex/review-resume-identity-20261025`
- goal: 저장된 Codex·Gemini 응답을 재요청하지 않고 6fbd 검토의 NVIDIA 심판부터 재개.
- allowed_files: `card_condition/cross_review_manual.py`, `tests/test_cross_review_resume_identity.py`, 이 문서.
- forbidden_files: 모델·worker·평가·라벨·비밀 설정·기존 검토/캐시 원문.
- contract: 근거 ID의 파일 path/SHA와 다른 자료는 새 검토로 유지. 같은 SHA의 budget_truncated 코드 발췌 길이 변동만 식별값에서 제외. Gemini 응답이 저장된 `critique_recorded` 검토를 빈 최신 폴더보다 우선 선택. 호출/중복 방지·롤백은 변경하지 않는다.
- structure: `cross_review_manual.py` 함수 정의 7→7. 테스트 파일 신규 함수 1개. `review → review_identity` 호출 경로·깊이 변화 없음.
- checks: 저장된 6fbd·a5e packet의 식별값 일치. 소스 SHA 차이/잘리지 않은 코드 차이 분리와 선택 순서 포함 mock 35개 통과.
- experiment: 없음. AI 호출 없이 먼저 검사.
- handoff: 변경은 식별값의 잘린 excerpt만 제외한다. 롤백 시 이 커밋을 되돌리면 기존 식별 규칙으로 복원된다. 기본 checkout의 통합·실제 재개 결과는 별도 기록한다.
