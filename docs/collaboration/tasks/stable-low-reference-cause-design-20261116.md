# stable-low-reference-cause-design-20261116

task_id: stable-low-reference-cause-design-20261116
owner: Codex (페어코딩 설계 담당)
status: assigned
base_sha: 3cbf778e6ebb8f237684989177896f4367ebd140
branch: codex/stable-low-reference-cause-design-20261116
worktree: 별도 관리 worktree, 절대경로는 세션에서만 전달

goal: 동결 기록에서 혼입12곳/혼합사진 적용29·거부89의 설명 가능 범위를 감사하고 다음 검증 하나의 사전 설계 또는 식별 불가 결론을 제출한다. 실행하지 않는다.

## 소유권

allowed_files:
- docs/collaboration/tasks/stable-low-reference-cause-design-20261116.md
- docs/collaboration/reports/stable-low-reference-cause-design-20261116.md

forbidden_files: 위 두 문서 이외 전부. 기본 checkout, .claude/, D-LOC 및 다른 worktree, 원본 artifacts, 라벨/점수/사진/모델/worker/실행기/PokeCollector/비밀 설정 보존. D1 봉인·표면 보충시험·폐기105·예약보류9그룹 열람 금지.

contract: PROMPT.txt/HANDOFF.md와 manifest38개를 읽기 전용 입력으로 사용. packet_path/SHA38/38 일치 확인 후 진행. 누락/불일치 시 기대·실제·경로 기록 후 중단하며 재분석 복구 금지. 허용 계산은 저장 연결·개수·교차표·기록값 검산뿐이다. 과거 worker/selector import·실행 금지. 원본 라벨·점수·사진·로컬 JSON·홈 절대경로 커밋 금지. 보고서에는 감사 파생표와 상대 근거 경로/키만 기록한다.

structure: 문서만 변경, 소스 함수 수/호출 경로 변경 없음(해당 없음).

## 작업 순서와 checks

- [x] 인계 계약/manifest와 현재 HEAD/status/worktree 확인. HEAD 일치, 기본 checkout 기존 미추적 .claude/ 보존.
- [x] manifest packet_path 38/38 SHA-256 일치, 불일치0.
- [ ] 이 task 계약을 먼저 로컬 커밋하여 소유권 고정.
- [ ] 저장 scored rows/photos, sealed references, B0와 snapshot의 정확한 키/값/분모/봉인 순서 대조. 혼입12행, 대조군, 거부 교차표 작성.
- [ ] systematic-debugging의 원인 추적/대조, brainstorming의 가설·대안 비교, writing-plans의 단일 사전 설계/반례 점검을 설계 범위에 적용.
- [ ] verification-before-completion: 근거 해시 재확인, 문서 요구사항/허용 경로/금지 내용/git diff --check 검사 후 로컬 최종 커밋.

experiment: 불필요/실행 금지. 신규 학습·추론·검증·사람 판정 요청·외부 AI 호출0. main 통합/push 금지. 구현용 설치·단위/모델 테스트는 수행하지 않는다. 이번은 설계 문서2개만 허용되므로 HTML 생성/열기/렌더는 하지 않으며 HTML_REPORTING.md의 지침/설계 준비 범위로 기록한다.

고정 조건: 진척78/100 유지(점수 재산정 없음), 제품 FN≤67/370·FP≤112/1406·AUC +0.03·사진그룹 bootstrap 하한>0·유효5fold 유지. D-LOC12/22·결정표④·후속 과제 선정 보류 유지.

## handoff

작성 중. 최종 설계 제출 후 종료하며 후속 실행은 하지 않는다. 리스크: 개발 자료 반복 관찰 편향과 관찰조건/라벨 출처 미확인. 롤백: 이 전용 브랜치의 두 문서 변경만 되돌린다. 원본 기록/기존 worktree는 복원·삭제하지 않는다.
