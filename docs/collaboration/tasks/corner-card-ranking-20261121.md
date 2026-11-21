# 후면 모서리 카드 단위 순위 손실 실험

- task_id: corner-card-ranking-20261121
- owner: Codex
- status: integrated
- base_sha: 9500116cf7f4d3a02b20e858acfe1bb04d4cf0d2
- branch: main, 기본 checkout에서 잠금과 단일 실행
- allowed_files: 이 문서, `tools/experiments/corner-card-ranking-20261121/{head.py,worker.py,plan.json}`, `tests/test_corner_card_ranking.py`, `docs/collaboration/reports/corner-card-ranking-20261121.md`
- ignored 산출물: `artifacts/corner-card-ranking-20261121/`(미러, 검사 로그, report.html), 공통 실행 폴더. D1/D2·운영·기존 실험 코드/자료·라벨·임계 변경 금지. Gemini 0.
- 재현: 후보 E/MLP/애매 제외의 저장 점수 946행 대조에서 오탐 10/81을 맞췄을 때 카드 누락 50/176, 63/176, 63/176. 구역 AUC 상승만으로 정상 카드 상위 점수와 결함 카드 점수의 겹침을 줄이지 못했다.
- 가설·단일 변수: 후보 E의 동일 사진 쌍 손실과 기존 bag/class/정규화에 카드 사이 쌍 순위 손실 계수 1.0을 추가. 결함 카드의 결함 구역들, 정상 카드의 전체 구역들에서 각각 log-mean-exp(T=0.1)로 카드 점수를 계산하고 결함 카드 점수가 정상보다 높도록 softplus 쌍 손실을 평균한다. 원래 특징·마스크·데이터·선형 head·fold·최적화·추론식 보존. 정답은 학습 fold에서만 카드 집계에 사용.
- 사전 AND 기준: 후보 E 오탐 예산 10/81에서 카드 누락 50/176 → 45 이하, 후보 E 누락 예산 50/176에서 카드 오탐 10/81 → 9 이하. 동결 v1.14 비교 작동점에서 누락 7/176 → 6 이하 및 오탐 10/81 → 9 이하. 같은 사진 AUC 하락 ≤0.01. 개발 결과로 기록하고 독립 채택은 별도.
- checks: TDD로 쌍 방향, 혼합 카드 정상구역 제외, 구역 반복 수 정규화, 계수 0에서 대조 fit 동등성을 확인. 대상 worker·head SHA와 사진/그룹 분리 검증, 공통 실행 1회, 결과 독립 검산, HTML 생성·내용대조·열기. 비수렴·실행 오류는 failed, 재시도하지 않는다.
- 구조: head.py 5개(카드 인덱스, 집계, 손실, 학습 및 중첩 closure), worker.py 4개 이하, 테스트 5개 이하. 주요 새 경로 worker.run → head.fit → closure → card_pair_loss → card_scores(4회).

## 결과

- 공통 실행 `artifacts/experiments/20261121T003253-08af1d09/record.json` completed/0, `evaluation.json.criterion_met=false`.
- [원인 진단과 실행·검증 기록](../reports/corner-card-ranking-20261121.md). 후보 E 유지.
- `artifacts/corner-card-ranking-20261121/report.html` 열기 성공, Chrome 헤드리스에서 지표·사진·오버레이 렌더 확인.
