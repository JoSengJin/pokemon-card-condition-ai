# 관제도구 핵심 실계정 교대 확인

- task_id: pair-control-native-smoke-20261107
- owner: Codex
- status: implementing
- base_sha: a4ad9eb2b9e420507d07b792ed9e5da8f48c1a8e
- branch: codex/pair-control-native-smoke-20261107
- goal: 기존 회귀를 반복하지 않고 새 메인 양방향 인수2회와 교대 뒤 연속 통합2회만 확인한다.
- authorization: 직전 최대4개 CLI/구독·추가 사용 꺼짐 확인 요청에 사용자가 “응 진행하는데 테스트 처리할게ㅣ 너무 많아 중요한것만 추려서 해”라고 진행 승인. 무료 원칙 유지, 이 시험 이외 실제 모델 호출 금지.
- allowed_files: 이 계약, docs/collaboration/reports/pair-control-native-smoke-20261107.html, Git 제외 artifacts/pair-control-native-smoke-20261107/ 증거.
- forbidden_files: 제품 소스/테스트/설정/운영 상태/다른 세션 서버/.claude/사진/라벨/모델/학습/추론. 운영 Git push는 시험에서 금지하며 검증 문서 main 일반 push는 기존 승인 범위다.
- execution: 기본 checkout에서 독립 임시 Git·bare 원격·합성 파일만 사용. 기존 준비 절차 재사용, 실제 HOME과 무료 가드·로그인·설정 검사 유지. 실제 CLI 작업 총 최대4(내부 공급자 API 요청 수4회 뜻 아님). push_main 승인 없음.
- stop: 과금/한도/권한/응답 오류·결과 불명이면 중단, 재요청/구매/유료 전환 없음. 이미 요청한 CLI는 같은 시험에서 재실행하지 않는다.
- checks: source SHA/잠금/.claude 해시 → 무료 사전 조건 → 인수/연속 처리 최대4CLI → 실제 종료/응답/상태/Git 근거 확인 → HTML 렌더·증거 보존. 소스 무변경이면 전체320회귀/typecheck/구조 검사를 반복하지 않음(직전 검증 재사용으로 표시).
- structure: 제품 소스 변경0, 문서 함수0. 직전270파일/783정의/최대7/전이4 결과를 재사용, 이번 실행으로 새 검사 통과 주장 금지.
- rollback: 운영 변경 없음. 시험 fixture/결과 불명 증거 보존. 문서만 필요 시 git revert, force/reset/다른 프로세스 종료 금지.
