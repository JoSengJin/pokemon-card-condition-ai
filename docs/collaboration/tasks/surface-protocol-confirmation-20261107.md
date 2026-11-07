# surface-protocol-confirmation-20261107

owner: Codex
status: ready_for_review
base_sha: f2042733c322db7d2d5f1931fb9f235c3dbc16fd
branch: main
goal: 사용자5배치 HTML 적용 확인을946개에만 반영하고 남은570개 ID/근거를 목록화한다.

allowed_files:
- docs/collaboration/tasks/surface-protocol-confirmation-20261107.md
- docs/collaboration/reports/surface-protocol-confirmation-20261107.md
- docs/collaboration/reports/surface-protocol-confirmation-20261107.html
- ignored artifacts/surface-protocol-confirmation-20261107/ 신규 산출물
- ignored artifacts/surface-protocol-scope-20261107/latest-confirmation.json 신규 포인터

forbidden_files: 기존 원답·라벨값·사진·모델·실험·운영소스·소비 프로젝트·fallback·진척기준·다른 작업 파일. 새 학습/실험/추론/AI호출/자동review 금지.

contract: 이번 직접 확인 범위 ad/ae/af/ag/ah만 적용. 기존 미확정946개 제외, 이미 제외된275개 불변, 다른4배치570개 불변. 원답/§93/§97 및 원판정 선택 불변. 남은 목록에 신규 확정946개를 다시 포함하지 않는다. 완료 라벨/기준 재질문 없음.

structure: 신규 추적 소스0. ignored apply_confirmation.py 함수2개, 주요 자체 경로 main→apply_confirmation1전이. 기존 실행기/모델 호출경로 변경0.

checks: 합성5경로 assert·실자료1791 전후 ID/라벨/box/기존선택 일치·946개 외 ledger행 완전불변·분할946/570/275 및 ID중복0·기존120입력/이전ledger 해시 보존·신규experiment record0·570개 CSV/HTML 대조·diff-check·열기상태/렌더 미확인 구분.

experiment: 금지. 일관성 확보 전 재학습하지 않는다. training-gate.json은 사용자 지시 인계이며 새 강제차단 구현으로 주장하지 않는다.

handoff: 목록 작성 완료, 규약 일관성은 미완료. 남은 y130/z139/aa125/ai176, 원답만474/§93일치83/불일치13. 불일치13개도 원판정 선택 유지. 사진HTML artifacts/surface-protocol-confirmation-20261107/report.html에 남은 목록/사진만 표시, 새 모델 출력 없음. 원격·열기 확인은 후속 기록.

rollback: 이번 신규 문서 커밋만 revert 후 일반push. 새 사용자 확인/이전근거는 보존, 원답/모델 복구 불필요.

최종: CSV/JSON/HTML570 ID 완전일치, 이전121입력 SHA불변,946개 외845행 완전불변 확인. HTML 열기 요청 queued, 실제 렌더 미확인. 새 학습/추론/실험/AI호출0.
