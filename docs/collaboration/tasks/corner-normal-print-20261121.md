# 모서리 결함 구역 내부의 확인된 정상 인쇄면 학습

- task_id: corner-normal-print-20261121
- owner: Codex
- status: integrated
- base_sha: 852be2217afd505237b68318e58d95c4c95fb057
- 실행: 기본 checkout 전용, 94번을 포함하는 기존 평가 묶음 하나. 후보는 기존 카드 순위 학습에 정상 인쇄면 항 하나만 추가하고 대조는 동일 fold의 복원된 기존 head 및 저장 점수. 94번 전체 카드와 평가 묶음 전체는 학습에서 제외한다.
- 근거: 이전 표면 정상 응답으로 확정된 동일 사진·구역·상자, 같은 카드의 모서리 target=1. 양쪽 구역 교집합 안쪽 인쇄면만 채택. 동일 실물/사진 해시 분리. 위치 확인에서 17·23 제외. 94번 녹색 4곳은 스크린샷에 맞춘 셀 범위, A/B는 이전에 고정한 백화 후보 상자다. 사용자 기존 모서리/표면 라벨은 수정하지 않는다.
- 단일 변수: 정상 인쇄면에 완전히 포함되는 패치의 점수에 `softplus(logit)` 페널티를 더한다. 행별 평균 후 지도 있는 행만 평균, 계수 1.0. 특징·기존 목적함수·초기화·LBFGS·집계·고정 작동점 동일.
- 사전 AND 기준: 94번 녹색 네 곳 최고점 평균 5점 이상 감소, 백화 후보 A/B 각 최고점 감소 5점 이내, 고정 작동점의 카드 오탐/누락 둘 모두 증가 없음. 독립 일반화나 배포 채택과 분리. 이 fold는 이전 개발 자료로 94번도 이전 진단에 열람했다.
- 범위: `tools/experiments/corner-normal-print-20261121/{head.py,worker.py,plan.json}`, 이 task 및 결과 보고, 로컬 ignored 검증 자료. D1·D2·Gemini·라벨 변경 0.
- 검사: 정상 출처 ledger/행·사진/box 일치, 시각 인쇄면 경계 확인, train/eval 사진 하드 해시 분리, 정상 영역만 낮추는 합성 gradient와 대상 수, 이전 점수 재현, 공통 실행 1회, 녹색/A·B 지도 및 카드 FN/FP 검산, HTML 열기. head 함수 3개, worker 함수 5개 이내. 주요 경로 worker.run→head.fit→closure→print_penalty(3회).

## 완료

- [94번과 동일 검증 묶음의 결과](../reports/corner-normal-print-20261121.md).
- `artifacts/experiments/20261121T014152-5479595c/record.json` completed/0, 사전 기준 미달, 운영 모델 유지.
- `artifacts/corner-normal-print-20261121/report.html` 열기 성공 및 Chrome 헤드리스 지표·지도 렌더 확인.
