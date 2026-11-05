# NVIDIA 심판 입력 예산 복구

- task_id: `review-judge-budget-20261025`
- owner: Codex
- status: ready_for_review
- base_sha: `8949761` (main)
- branch: `codex/review-judge-budget-20261025`
- goal: 저장된 Codex·Gemini 응답을 다시 호출하지 않고 NVIDIA 독립 심판 단계의 32KB 입력 검사 통과.
- allowed_files: `card_condition/cross_review_flow.py`, `card_condition/cross_review_judge_projection.py`, `tests/test_cross_review_judge_projection.py`, 이 문서.
- forbidden_files: 모델·worker·평가·라벨·비밀 설정·기존 검토 기록.
- contract: 현재 평가 수치·사람점·사전 기준·실패 이유·코드 인용·원본 path/SHA는 유지한다. 과거 실패의 코호트별 반복 수치 목록만 실패 ID/오류 건수로 요약한다. NVIDIA 무료 검증·호출/토큰 상한과 개발 승인 게이트는 변경하지 않는다. 저장된 앞 단계 응답을 재사용한다.
- structure: `cross_review_flow.py` 함수 정의 6→6(중첩 포함). 신규 projection 파일 1함수. 신규 테스트 1함수. 주요 경로 `run_codex_first → judge_review`, 입력 projection 경유 1전이 추가; 동적 judge callback 이후 깊이는 기존과 동일하며 프레임워크 호출 경로는 테스트로 검증한다.
- checks: 저장된 6fbd 입력을 재구성해 30,924/32,000 bytes. 같은 평가 수치·실패 가설 목록 동일, 원본 미변경. projection+auto mock 19개 통과. high_fixes 포함 56개 중 24개는 구현 worktree에 Git 제외 `nemotron-review.json`이 없어 setup 실패했으므로 기본 checkout 통합 후 재검사.
- experiment: 없음. 실제 모델 실험은 심판·개발 게이트 승인 후 공통 실행기로만.
- handoff: 기존 6fbd는 `judge_unavailable`이며 저장된 Codex 2회·Gemini 1회를 재사용해 같은 폴더에서 NVIDIA부터 재개할 수 있다. 실제 NVIDIA 응답·개발 효과는 아직 미검증. 판정 입력은 오래된 코호트 세부값을 요약하므로 과거 오류 위치별 해석에는 원본 path/SHA 확인이 필요하다. 롤백은 통합 커밋 revert; 기존 검토 폴더는 보존.
