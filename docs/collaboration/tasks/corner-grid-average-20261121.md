# 모서리 카드 판정의 격자 이동 평균 실험

- task_id: corner-grid-average-20261121
- owner: Codex
- status: integrated
- base_sha: eb6c86e46c302ea36ad6477060e7dfe143dc529c
- branch: main 기본 checkout, 단일 공통 실행
- 허용 파일: 이 task, 결과 문서, `tools/experiments/corner-grid-average-20261121/{worker.py,plan.json}`, ignored 보고서·기록. 운영/진척/라벨/동결 기준 변경 금지. Gemini/D1/D2 0.
- 범위: 94번 카드 그룹을 추론 및 비교에서 제외한다. 기존 카드 순위 후보의 사진 그룹별 저장 계수로 256장의 개발 사진을 점수화한다. 94번에 대한 추가 분석이나 재학습은 없다.
- 근거: 기존 오탐 카드 16장 중 8장은 단일 패치만 60점 이상이었다. 두 번째 패치를 쓰면 정상 오탐은 감소했지만 실제 결함 놓침이 늘었다. 서로 다른 입력 격자에서 모서리 전체 점수가 안정적인지를 비교한다.
- 변경 하나: 기존 448 입력의 무이동 점수 + 오른쪽 7px + 아래 7px + 오른쪽/아래 각 7px 점수의 산술 평균. 이동은 같은 회색 배경과 마스크를 사용한다. 재학습, 후보 점수에 맞춘 이동 조정, 임계 변경 없음.
- 사전 AND: 고정 작동점 오탐 3장 이상 감소, 새 누락 카드 0장, 같은 오탐 10/81에서 누락 대조 이하, 같은 사진 AUC 하락 0.01 이내. 후보 E는 동일 분모에서 참고 대조. 기준 미달 시 채택하지 않는다.
- checks: 실제 사진 raw/decoded 해시와 replay 체크포인트 해시, 전체 무이동 점수 오차 ≤2e-6, 94 제외와 기존 그룹 fold의 일치, 카드 오류 동일 분모 검산, 실제 사진/구역 점수 HTML 생성·열기·렌더. worker 5개 함수 이내.

## 완료

- [개발 평가와 검산 결과](../reports/corner-grid-average-20261121.md). 공통 기록 `artifacts/experiments/20261121T050740-8588eeb0/record.json` completed/0, 사전 기준 통과.
- `artifacts/corner-grid-average-20261121/report.html` 기본 브라우저 열기 및 Chrome 헤드리스 지표·사진 렌더 확인. 독립 평가와 운영 채택은 미확정.
