task_id: f2-pilot-preparation-20261105
owner: Codex
status: integrated (준비 문서 검토/통합; 실제 경로·기준안 방향은 사용자 선택 대기)
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

## 실제 준비 결과
- 0.6.0 무결성 확인, 0.6.1은 설치 버전 불일치(예상 보류), checkout 내 0.6.x wheel 미발견. 합성 12 tests OK/0.695초.
- 실제 소비경로/F1 선행 6조건, 현행 F2와 후면 순위 도구의 불일치, 계측 공백/자료 분모/실행 순서를 F2_PILOT_PREPARATION.md에 명시. 새 코드/기준/시범 없음.
- 사용자 질문 2개 제출: PC 브라우저 독립 도구 vs 기존 별도 도구 연결, 후면 지원 기준안 준비 vs 현행 F2 완료 보류. 답변 전 제안안을 승인된 경로/기준으로 표시하지 않음.

- HTML: Codex 브라우저 패널 queued(요청 접수), 정적 파싱/내용 대조 통과. 실제 렌더·클릭 미확인.
- 최종 체크: 제품/도구/테스트/진척 기준 JSON/Markdown diff 0, 78점·v1.13·F1/F2 pending 보존, diff-check 통과.

## 후속 사용자 선호 반영 (2026-11-05)
- 사용자: “카드 검토는 모바일 앱 원격에서 하고싶어”. 실제 사용 경로를 모바일 앱→원격 분석 서비스→모바일 검토/기록으로 준비안 갱신. 이전 PC 브라우저 제안은 대체됨.
- 미결: Android/iPhone, 시범 때 현재 PC를 켜는 호스트 방식/상시 서버. F2 기준안 방향 선택은 여전히 별개. 모바일 웹으로 임의 대체하지 않음.
- F1 설치/호환 버전/실제 원격 전송/통신 단절·재시작·재전송/수동 복귀·복구 조건 및 서버 시간과 사용자 대기시간 구분을 명시.
- 이번 검사는 문서/HTML/기준 불변 대조와 diff 검사. 실제 앱/원격 API/통신 테스트·서버 설치·외부 접속 개방 없음.

- 갱신 HTML 정적 파싱/모바일 사용 방향·78점·미구현 상태 대조 완료. 열기 결과는 html-open.json 및 최종 인계 참조. 실제 렌더/통신 미검증.

## 플랫폼·호스트 결정 반영 (2026-11-05)
- 사용자: “안드로이드야 원격pc는 계속 실행중”. Android 설치 앱 + 현재 상주 PC 분석 서비스로 확정. OS/호스트 재질문 불필요.
- 준비안에 F1 세로 흐름(사진/상자→원격 분석→정확한 사진 위 구역→검토 저장), 원격 실패/재전송/버전 호환·복구 순서를 추가. F2 기준안 방향은 별개이며 기준/시범 시작은 미승인 상태 유지.
- SDK/ADB와 OpenJDK 바이너리 실행 확인. 기본 Java 탐지는 실패했지만 별도 JDK 실행 성공. Android 프로젝트/APK 빌드/폰 연결/원격 통신/서버는 미구현·미검증.
- 문서/HTML 검증만 수행, 기존 합성 12테스트 결과를 새 실행으로 재사용하지 않음. 코드/기준/라벨 변경 없음.

## 사용자 뜻 최종 정정 — Codex 모바일 앱 (2026-11-05)
- 사용자: “코덱스 앱에서 하겠다는건더...?”와 현재 Codex 모바일 채팅 캡처. 의미는 기존 Codex 앱/이 채팅에서 PC 작업·사진/결과/답을 주고받는 경로다.
- 위의 새 Android 설치 앱/APK/원격 분석 API 개발 확정 문구는 Codex의 오해였으며 철회한다. 원래 답변은 새 앱 개발 승인이 아니었다. 기존 Codex 앱의 원격 경로를 사용하는 최소 입력/결과 표시/답 저장 보완으로 F1 준비 범위를 정정.
- F2_PILOT_PREPARATION.md의 현행 본문과 HTML에서 잘못 확장한 구현 계획 제거. SDK/JDK 확인은 경로의 필수조건 아님. 새 앱/서버 구현·설치 변경 자체가 없었으므로 제거할 실행 코드 없음.
- 실제 모바일 카드 검토 왕복·이미지 표시·답 저장은 미검증, F1/F2 pending·78점·기준 불변. 로컬 file 링크가 폰에서 열린다는 약속 없음. 원래 CLI 단독 소비경로 불인정도 유지.
- OpenAI Docs 스킬로 공식 원격 연결 문서 검색·열기 후 지원되는 채팅 계속/응답·결과/스크린샷·호스트 로컬 도구 사용 범위를 확인. 기기 재연결/새 원격계정/포트 개방은 하지 않음.
