# surface-protocol-finalization-20261107

owner: Codex
status: integrated
base_sha: b2a6bd5e729e612092dada3f4f844257149ce10e
branch: main
goal: 남은570개에 직접 확인을 반영해 규약 적용/답 선택 미확정0과 제외15를 검산하고 재학습 보류를 유지한다.

allowed_files:
- docs/collaboration/tasks/surface-protocol-finalization-20261107.md
- docs/collaboration/reports/surface-protocol-finalization-20261107.md
- docs/collaboration/reports/surface-protocol-finalization-20261107.html
- ignored artifacts/surface-protocol-finalization-20261107/ 신규 산출물
- ignored artifacts/surface-protocol-scope-20261107/latest-confirmation.json 최신 포인터
- ignored artifacts/surface-protocol-confirmation-20261107/latest-finalization.json 신규 포인터

forbidden_files: 모든 기존 라벨값/원답/사진/모델/실험/worker/운영/PokeCollector/fallback/진척기준 및 다른 작업 파일. 새 재학습/추론/모델호출/자동review 금지.

contract: y/z/aa/ai570개만 규약 상태 확정, 기존1221행 불변. 규약 미확정0·선택 미확정0·판정1776(결함370/정상1406)·불가15제외. §93 불일치39원답 선택 유지, 오류/완벽한 반복일치/정확도100%로 주장하지 않음. 완료 후에도 사용자 새 지시 전 재학습 금지.

structure: 신규 추적 소스0. ignored finalize.py 함수3개, 주요 자체 경로 main→finalize_row/effective_decision1전이. 모델/실행기 호출경로 변경0.

checks: 합성6경로·전후1791라벨/box/선택불변·570개밖1221행 완전동일·1776+15분리/미확정0·39기존선택 보존·입력SHA·과거실험정답값과 차이0(행만대조, 점수재평가없음)·신규experiment0·JSON/CSV/HTML1791ID 및pending0 검산·diff-check·열기/렌더 구분.

experiment: 금지. 사용자 명시 보류를 규약 완료로 자동 해제하지 않음.

handoff: 요청 범위의 규약 적용/답 선택 정리 완료, 독립 라벨 정확도/일반화 검증 아님.1776답·15불가 보존, 새 학습/추론0. HTML artifacts/surface-protocol-finalization-20261107/report.html은 사람 선택/근거만 표시. 원격/열기 확인은 후속 기록.

rollback: 이번 신규 문서 커밋만 revert 후 일반push. 사용자 답/감사이력 보존, 기존모델 복구 불필요. 최신포인터는 보존한 이전ledger로 복원 가능.

최종검증: CSV/JSON/HTML1791ID 일치, pending JSON/CSV0행, 122입력SHA 불변, 이전1221행 완전동일. HTML 파일 열기 queued, 실제 표시/렌더 미확인. 재학습 보류는 규약 완료 후에도 false 유지. 일반push 및 원격SHA 확인은 최종 인계/sync.json에 기록.
