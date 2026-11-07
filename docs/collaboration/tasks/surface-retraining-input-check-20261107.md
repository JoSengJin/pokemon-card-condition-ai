# surface-retraining-input-check-20261107

owner: Codex
status: integrated
base_sha: 50ce9635ba39b7417c49610bf2031a3292c10d40
branch: main
goal: 최종 확정 라벨과 직전 실제 실행 후보 학습 입력을 대조해 동일 시 재학습을 생략한다.

allowed_files:
- docs/collaboration/reports/surface-retraining-input-check-20261107.md
- docs/collaboration/reports/surface-retraining-input-check-20261107.html
- docs/collaboration/tasks/surface-retraining-input-check-20261107.md
- ignored artifacts/surface-retraining-input-check-20261107/ 신규 비교 산출물
- ignored artifacts/surface-protocol-finalization-20261107/latest-retraining-check.json 신규 포인터

forbidden_files: 기존 라벨/답/사진/모델/실험/worker/운영/PokeCollector/fallback/진척기준/다른 작업 파일. 동일 입력인데 새 학습/실험/추론/AI호출/자동review 실행 금지.

contract: 사용자 새 요청은 조건부 승인이다. 직전 최신 surface record 상태를 먼저 확인하고 실행 snapshot으로 후보/대조 실제 라벨을 복원한다. 확정1776/370양성/1406정상·15제외·group/box/사진해시/순서/fold 동일이면 보고하고 종료. 설명/규약 근거만 바뀐 것을 새 학습 라벨로 취급하지 않는다.

structure: 신규 추적 소스0, ignored compare.py 함수4, 주요 자체 경로 main→compare_rows/read_json/fingerprint1전이. 기존 모델/최적화 호출경로 변경0.

checks: 합성5경로·실행 record/files/input/source SHA·snapshot label_rows 복원과observations/reference 동일·현재 후보/대조행 완전동일·제외15 ID동일·5fold10집합동일·실사진해시·D1/보류2비중복·신규experiment0·JSON/HTML1791ID 및 diff-check·열기/렌더 구분.

experiment: 입력 동일로 생략. 새 plan/record/학습/추론/모델호출0. 기존 completed/기준미충족 판정 보존.

handoff: comparison.json/decision.json에 skip_identical_training_input. 직전 기록 artifacts/experiments/20261106T210640-0eb1bdc0/record.json. 동일 후보1776행 SHA 077650973caaf77d832ef33f38bffff2f6d157266ad701f01519a2f903e1f656. 전체진척78유지·새 성능 변화 미평가. HTML artifacts/surface-retraining-input-check-20261107/report.html은 사람 라벨/입력만 표시. 원격/열기 확인은 후속 기록.

rollback: 신규 문서 커밋만 revert 후 일반push. 기존 입력/모델 복구 불필요, 감사 근거는 보존.

최종:277개입력SHA 불변·전체/10개fold fingerprint 일치·HTML1791ID 확인. HTML 파일 열기 queued, 실제 렌더 미확인. 소스/라벨/모델 변경 없음. 신규 문서3개 일반push 및 원격SHA 확인은 최종 인계/sync.json에 기록.
