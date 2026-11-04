task_id: label-protocol-20261105
owner: Codex
status: integrated (직렬 main 구현/검증 완료; 일반 push·원격 SHA 확인은 최종 인계 참조)
base_sha: 643382cd159453924cdb394f296e5ab5b6cf27f6
branch: main (serialized implementation/integration; no parallel worker)
goal: 앞으로 생성하는 표면 안내에서 잘못된 제외 문구를 없애고 기존 사람 판단·종류별 범위를 일치시킨다.

## allowed_files
- LABELING_PROTOCOL.md
- card_condition/label_instructions.py
- tools/mobile_surface_label_pages.py
- tools/mobile_surface_label_pages_v2.py
- tools/relabel_consistency_page.py
- tools/relabel_zone_pages.py
- PROGRESS_CRITERIA.md (정정 범위 사용자 답변 전 기준본문 수정 금지)
- development-progress.json (정정 범위 사용자 답변 전 기준본문 수정 금지)
- docs/collaboration/reports/performance-top3-consensus-20261030.md (과거 본문 보존, 정정 부록만)
- docs/collaboration/tasks/label-protocol-20261105.md
- docs/collaboration/reports/label-protocol-20261105.md
- docs/collaboration/reports/label-protocol-20261105.html
- ignored artifacts/label-protocol-20261105/ (합성 화면·검증 로그·과거 파일 해시)

## contract
- 기존 라벨/답/selection/실험 worker·plan·기록·가중치·과거 HTML 불변. PokeCollector/운영/학습/새 라벨 요청 없음.
- 사용자 기록 §97 재정정과 3종 실제 과거 HTML, mobile 엣지/모서리 도구의 위치별 구분을 근거로 정리.
- 미확인/판단불가를 정상으로 바꾸지 않음. 기존 상태값/복사 형식/버튼 동작·사진 해상도/좌표/선택 규칙 불변.
- 기록으로 확정되지 않은 과거 라벨 의미/성능 영향은 미확인. 점수/배점/수치/모델 채택 변경 없음.

## structure
- 신규 label_instructions.py: 함수 0개(표면 안내 상수 한 개).
- mobile_surface_label_pages.py 및 v2: 함수 4→4.
- relabel_consistency_page.py 및 relabel_zone_pages.py: 함수 5→5.
- 기존 호출 경로 불변. mobile main→article→photo=2전이, consistency main→page→article→photo=3전이, zone main→page→article→crop=3전이(외부 PIL 경로 최대 인증과 구별). 새 호출 계층 없음.

## checks / experiment / HTML
- 실제 과거 3종 HTML의 안내 추출, 사전 해시; source AST 함수 수와 기존 JS/응답 형식 불변 대조.
- 4종 generator 합성 입력/빈 페이지 생성 및 공통 안내 포함 확인, direct CLI import 확인; 관련 테스트 필요 여부는 변경 범위로 판단.
- 새 실험/추론/외부 AI 0. 점수 78/100 v1.12 기준에서 작업 시작.
- 성과·진척 HTML: docs/collaboration/reports/label-protocol-20261105.html. 생성/내용 대조/열기 실제 결과를 handoff에 기록.
- rollback: 작업 커밋 git revert, 과거 자료는 불변이라 데이터 복구 불필요.

## handoff
- 검증 소스 de3ce08, 4종 합성 생성/문단 외 byte 불변/JS 동일/함수 수 확인, 과거 104파일 해시 불변, direct CLI 1면 생성/py_compile/diff-check 성공.
- 상세 변경·미검증·위험·롤백: docs/collaboration/reports/label-protocol-20261105.md.
- 성과·진척 HTML: docs/collaboration/reports/label-protocol-20261105.html. 실제 열기 결과는 아래에 기록.
- 사람 의존 해결: 사용자 선택대로 과거 평가 영향을 먼저 감사한 뒤 v1.13 설명 정정. 128개 기존 안내에는 오류 문구 없음, 후속 16개에만 존재/기존 점수 입력 편입 없음. 손상 세부유형의 부재로 개별 화이트닝 수치 영향은 미확인. 새 학습/추론/실라벨 저장 없음.

## 사용자 선택 반영·허용 산출물 추가
- 사용자: “과거 평가 영향까지 확인한 뒤 확정”. 안내 128개/후속 16개, 고정 평가 plan·입력 SHA·답 스키마를 읽기 전용 감사한 뒤 정정. 새 학습/평가/라벨 요청 없음.
- 추가 ignored 산출물: artifacts/progress-baseline-20261105/criteria-v1.13.json (신규 정정 관리 snapshot, v1.12 불변). 배점·수치/earned/status/기존 증거 전부 보존, C3 설명만 정정.

- 최종 검증: v1.12 snapshot 해시 재현/v1.13 해시 대조, C3 설명·assessment 외 모든 milestone 동일, 기존 104파일 해시 불변, 학습/C3/D2 4개 cohort의 모든 그룹이 검사한 안내 HTML에 포함됨 확인. 기존 안내 128개 오류 문구 0, 후속 재판정 16개 오류 문구 16.
- HTML 열기: Codex 브라우저 패널 queued(요청 접수), 정적 내용 검사 통과. 실제 렌더/클릭은 미확인. 새 모델 성능 검증/전체 테스트 재실행 없음.
