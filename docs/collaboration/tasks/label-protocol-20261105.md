task_id: label-protocol-20261105
owner: Codex
status: implementing
base_sha: 643382cd159453924cdb394f296e5ab5b6cf27f6
branch: main (serialized implementation/integration; no parallel worker)
goal: 新しく生成する表面案内の誤った除外文をなくし、既存の人の判断と種類別の範囲を一致させる。

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
