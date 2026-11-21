# 후면 모서리 오탐 16장 최고점 패치 재현

- task_id: corner-fp-patch-replay-20261121
- owner: Codex
- status: integrated
- base_sha: 33f35e15e73f77f2996e9747f5c9a5e7ed312248
- branch: main, 기본 checkout 단독 실행
- 범위: 이 task, 결과 보고, `tools/diagnostics/corner-fp-patch-replay-20261121/{worker.py,plan.json}`, ignored 실험/검토 자료. 라벨, 임계, 원본, D1/D2 및 운영 설정 보존. 외부 AI 0.
- 실행: 카드 순위 후보를 고정 5개 fold에서 재현하고 저장 점수 946개 대비 최대 절대 차이 ≤2e-6 및 오탐 ID 16/16 일치 검증. 새 오탐 6장 우선, 16장 전부의 정상 구역 패치 점수를 저장. 재현 실패 시 원실행 패치로 보고 금지. 실제 개선 실험은 공통 원인에 대한 영상과 대조 개입 근거가 생긴 경우에만 별도 계획을 고정한다.
- 구조: worker 2개 함수. run → 기존 fit 및 run → 기존 입력 해시 검사 호출. 입출력과 계획은 공통 실행기 계약을 따른다.
- checks: 두 이전 completed 기록 SHA, 비교 행·정답·실물·분모 일치, 재현 점수, 실제 원본-입력-패치 역좌표 검산, 사용자용 HTML 열기·렌더와 근거 한계 기록.

## 한 패치가 만든 오탐 확인 후 추가한 실험 계약

- 재현 결과: 원 점수 946/946 완전 일치. 신규 오탐 6장 중 5장, 기존 오탐 10장 중 3장은 결함 표시 기준을 넘은 패치가 카드 전체에 한 칸뿐이었다. 이 한 칸의 점수가 카드 결함 표시를 결정했다.
- 가설 ID: corner-second-patch-20261121. 학습된 head와 입력은 재현과 동일. 유일 변경은 각 구역에서 유효 패치 최고점 대신 두 번째 고득점 사용. 동결 카드 작동점과 기존 라벨 동일.
- 사전 AND: 정상 카드 오탐 16/81 → 8/81 이하, 결함 카드 누락 8/176 이하이면서 새 누락 카드 0장, 같은 사진 AUC 하락 ≤0.01. 비교 대조는 카드 순위 후보. 개발 결과만 보고하고 운영 후보 E와의 대조를 병기한다.
- 추가 허용 파일: `tools/experiments/corner-second-patch-20261121/{worker.py,plan.json}`, `artifacts/corner-second-patch-20261121/`, 공통 기록. worker 2함수. 채택은 별도이며 기준 미달이나 실행 실패 시 재실행하지 않는다.

## 완료

- [16장 확대 대조와 단일 집계 실험 결과](../reports/corner-fp-patch-replay-20261121.md).
- `artifacts/corner-fp-patch-replay-20261121/report.html` 열기 완료 및 Chrome 렌더 확인. 재현·후속 실험 모두 completed, 후속 사전 기준 미달. 후보 E 유지.
