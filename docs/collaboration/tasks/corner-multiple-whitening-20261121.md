# 같은 모서리 안의 떨어진 밝은 자국과 AI 점수 비교

- task_id: corner-multiple-whitening-20261121
- owner: Codex
- status: integrated
- base_sha: 5f7f6df60e7d80f362e51eacb52f60f69189f108
- branch: main 기본 checkout, 공통 실행기
- 범위: 이 task, 결과 문서, `tools/diagnostics/corner-multiple-whitening-20261121/{worker.py,plan.json}`, ignored 로컬 사진·비교 좌표·보고서와 진단 실행 기록. 기존 라벨·모델·동결 임계 변경 0, D1/D2·외부 AI 0.
- 선택: 기존 사람 라벨이 결함인 구역에서 SHA256 순으로 카드별 한 곳, 96장. AI 점수 가린 화면에서 떨어진 흰 자국 후보가 두 군데 보이는 4장을 골라 보기 좌표와 주변 비교 칸을 고정했다. 사람이 확인한 개별 결함 위치로 취급하지 않는다. 둥근 끝과 인접한 테두리가 포함된 모서리 크롭이다.
- 검사: 동일 체크포인트·448 입력·fold의 네 구역 저장 최고점을 2e-6 이내로 재현. 두 자국 위치에서 각각 영역 최고점과 미리 고른 인접 영역 최고점을 비교. 5점(0.05) 이상 높으면 탐색용 국소 반응으로 기록. 20점(0.20)은 기존 카드 누락 집계의 낮은 점수 기준을 참고로 겹친다. 개별 자국 검출 정답 기준은 없다.
- 판정: 2곳 국소 반응, 1곳 반응, 0곳 반응으로 나누고 두 자국의 절대 점수 및 전 구역 최고점 위치를 함께 제시한다. 주변 대비 반응과 절대 기준을 구분한다. 패치 점수는 주변 문맥도 반영하며 인과·빈도·전체 성능을 판정하지 않는다.
- 구조: worker 3개 함수. worker.run → inspect_marks/peak 및 기존 feature, 실행 결과 해시·좌표·검산 후 HTML로 설명하고 연다.

## 결과

- [진단 결과](../reports/corner-multiple-whitening-20261121.md). 공통 실행 `artifacts/experiments/20261121T012135-1a63edd8/record.json` completed/0.
- 지도에서 두 자국 모두 주변보다 높음 2장, 한 자국만 두드러짐 2장. `artifacts/corner-multiple-whitening-20261121/report.html` 열기와 Chrome 렌더 확인.
