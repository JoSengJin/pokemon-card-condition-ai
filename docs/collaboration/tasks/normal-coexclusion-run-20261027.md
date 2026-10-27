task_id: normal-coexclusion-run-20261027
owner: Codex
status: implementing
base_sha: e1414c76cb44c4996d9c6d85fc3172b74bc329cb
source_branch: claude/task-1026-1
source_commits: 1fec3d7e64eb71608adb7528f752581b25fc0015, a3508669bedfe54c6c4cc5eb16e85726df0d54b5

목표: 검토 완료된 정상 공동 제외 진단을 main에 통합하고 공통 실행기로 한 번 실행하여 정상4실물의 오탐 민감 패턴을 실제 측정한다. 같은 입력 재학습 반복 대신 미실행된 단일 정상 제외 가설만 검증한다.

범위: 위 두 커밋의 worker/plan/합성검사/기존 task 문서4파일, 이 계약, docs/collaboration/reports/normal-coexclusion-run-20261027.md 및 .html. ignored 실행미러 artifacts/surface-normal-coexclusion-20261025/worker.py, 새 artifacts/experiments/<new-id> 기록·사진 HTML, artifacts/normal-coexclusion-run-20261027/ 실행·격리 증거만 허용한다.

금지: Claude 데이터 보완 checkout·신규 라벨/사진/manifest·coverage 코드·consumer·운영 모델·기존 실험/캐시 수정, 외부 AI 호출. 실제 실행은 기본 checkout 하나에서 직렬로만 수행. Claude의 미추적 초안은 보존한다.

근거: artifacts/surface-normal-coexclusion-implementation-review-20261027/REPORT.md에서 소스/11입력SHA/11cohort/기준선 재생과6합성검사를 확인했다. 기존 joint holdout은 앞면 FN14/51·FP15/40으로 악화했다. 이번은 양성53행/토큰/손실/가중치식/threshold.5 고정, 정상 h 정체만 바꾼다.

실행 전: source diff/현재 main 및 origin SHA/잠금/미커밋 검사. main 통합6합성검사, 입력SHA11개, 기존 계약 H1/H2/H3 사전기준 보존과 단독제외4+공동제외12확인. 추적worker와 신규미러 바이트 동일 확인. ./experiment --plan tools/experiments/surface-normal-coexclusion-20261025/plan.json -- .venv/bin/python artifacts/surface-normal-coexclusion-20261025/worker.py 로1회만 실행. 재현/수렴/누수 실패면 해석/재시도 금지.

구조: 전달worker7함수, 검사7함수. fit_excluding→fit_detail_head→closure→detail_bag_loss→point_bag_loss=4전이(원계약의 LBFGS 내부 프레임 제외만 적용). 새 모델 코드 추가 없음.

완료 판정: record 실제상태와 H1/H2/H3 또는 미구별, 각g의 FP/9·단독대비%p·logit, 재현최대차·16fit수렴,11cohort 보호를 기록. 공통acceptance는 재생기준선 보호 판정이며 진단모델 성능통과로 쓰지 않는다. 독립평가/운영채택 아님, 진척30/100 유지.

HTML: 실제 사진구역별 사람정답/점수는 새 실험 index.html. 추적 성과 HTML은 개인사진/이름/홈 경로 없이 집계·실제명령·변경·위험·롤백·진척을 기재한다. 둘 다 열기 요청하고 실제렌더 여부를 구분한다.

롤백: 모델/라벨 변경 없으므로 복구 불필요. 통합코드 커밋은 ./develop -- git revert 후 관련검사/일반push. 실험기록은 실패 포함 보존. 검증 후 origin/main 일반push, 정리규칙에 따라 통합확인된clean작업만 정리하고 최신1개 유지. Claude 데이터/미통합/사용중은 보존한다.
