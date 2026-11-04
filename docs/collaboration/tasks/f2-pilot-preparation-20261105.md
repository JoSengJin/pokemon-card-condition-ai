task_id: f2-pilot-preparation-20261105
owner: Codex
status: implementing (계획/준비 상태 감사만, 실제 사용 경로 선택 대기)
base_sha: ecd21b3452f9ce6318f0c0d571ed532ae400b95d
branch: main (직렬 문서 준비/통합)
goal: 실제 소비경로 후보와 F1 선행 수용검사/F2 계측 공백을 근거로 정리하고 사용자 결정 두 가지만 분리한다.

## allowed_files
- F2_PILOT_PREPARATION.md
- docs/collaboration/tasks/f2-pilot-preparation-20261105.md
- docs/collaboration/reports/f2-pilot-preparation-20261105.html
- ignored artifacts/f2-pilot-preparation-20261105/ (read-only inventory/합성 테스트 로그/열기/동기화 기록)

## contract
- 코드/모델/라벨/실험/기준/진척 JSON/PokeCollector 불변.
- 독립 CLI를 F1 소비경로로 인정하지 않은 기존 사용자 결정 유지.
- 이번은 계획 준비. 실제 브라우저 앱 구현/서버 시작/시범/사진 추론/외부 AI 호출/수집/새 라벨 요청/설치/릴리스 재빌드 없음.
- F1·F2 pending, v1.13 78점 유지. 선택 질문은 사용 경로 및 후면 지원 범위에 맞는 기준안 준비 여부다. 새 수치/배점/범위를 이번에 바꾸지 않는다.
- 기존 릴리스 SHA 검사/현재 wheel 존재 여부/사용 기록 스키마를 읽고, source 코드·합성 테스트·과거 검증을 구별한다.

## structure / checks
- Python 변경 0, 함수/호출 경로 변경 없음.
- read_release로 기존 0.6.0 파일 무결성 확인(모델 로드/사진 추론 없음). 0.6.1은 현재 설치 0.6.0과 버전 불일치 상태로 기록.
- .venv/bin/python -m unittest discover -s tests -p 'test_back_triage_*.py': 12 tests / 0.695s / OK (합성·mock 회귀, artifacts/f2-pilot-preparation-20261105/tests.log).
- 전체 테스트·깨끗한 설치·실제 롤백/시범 미실행. git diff --check/계획 조건과 코드·criteria 내용 대조.
- HTML: docs/collaboration/reports/f2-pilot-preparation-20261105.html. 계획/현황 보고이며 구현 성과·모델 성능으로 표시하지 않음. 열기 요청/렌더 여부를 기록.

## handoff / risk / rollback
- F2_PILOT_PREPARATION.md에 변경 목록/근거/실측/미검증/선행 검사/결정/위험/롤백 기록.
- 새 화면·기준 개정·F1 성공은 사용자 방향 결정 뒤 별도 구현·검증해야 한다.
- rollback: 이번 문서 커밋만 ./develop -- git revert <SHA>, 기준/코드/데이터 복구 불필요.
