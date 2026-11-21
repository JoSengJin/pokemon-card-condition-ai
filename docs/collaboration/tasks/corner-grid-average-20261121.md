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

## 후속 배정 · 저장 근거와 독립 평가 준비

- 현재 담당 Codex. 후속 검산 기준 SHA `201b031aeaa52291bf21cd7e9f25b30cbbf4bccc`, 기본 checkout. 이전 실험의 기준 SHA와 상태는 위 기록에 귀속한다.
- 허용 파일은 이 절, [후속 평가 계약](../reports/corner-grid-average-independent-20261121.md), Git 제외 `artifacts/corner-grid-average-audit-20261121/`이다. 새 수집·학습·사진 추론·외부 모델 호출·점수 기준 변경은 이번 준비 실행에 포함하지 않는다. D1/D2에서 겹침 조회용 ID와 해시만 사용한다.
- [x] 보존 기록의 파일 SHA와 기준 행을 먼저 확인한다. 942개 행·256개 실물·94번 네 행 제외가 맞고, 저장 결과의 두 비교에서 오류 집합을 재구성한 경우 카드별 근거를 남긴다.
- [x] 단일 후보 E의 출처·모델 SHA를 확인하고, 네 배치 후보의 단일 head 생성 절차·공통 입력·판정 계약을 확정한다. 신규 head 수렴·저장·재로딩 및 평가 코드 봉인은 후속 실행 조건이다.
- [x] D3 작동점과 Wilson 상한을 원문과 대조하고 표본 수·짝비교·보조 임계·지연 계측 절차를 고정한다. 스코어 공개 전에 모델과 독립 표본을 봉인한다는 조건을 둔다.
- [x] 남은 오류로부터 자료 구성 가설 하나를 제안한다. 다음 실험의 실행 승인은 별도다. 반증 사례와 미확인 위치를 기록하고 입수 보류를 유지한다.
- checks/handoff: 기준 SHA, 기록·입력 SHA, E checkpoint, 판정과 통계 계산 로그 및 HTML 열기/렌더 상태는 후속 평가 계약과 로컬 산출물에 남긴다. 적용 스킬은 writing-plans, verification-before-completion 및 직접 대조에 한정한 requesting-code-review다.

## 후속 실행 · 단일 head 생성과 평가 코드 봉인

- 배정은 현재 사용자 요청 「설계대로 진행해」, 담당 Codex, 기본 checkout, 기준 SHA `3601101266c9f64bcb876665de7cefdb2293e8a8`. 단일 head 생성 1회와 평가 코드·합성 검증·로컬 인계에 한정한다. 독립 사진 수집/평가·D1/D2 점수·운영 변경·자동 모델 호출은 범위 밖이다.
- 허용 경로는 `tools/experiments/corner-rank-full-development-head-v1/`, 이 task, 독립 평가 계약 및 ignored `artifacts/corner-rank-full-development-head-v1/`와 새 공통 실행 폴더다. 사전 계약의 946구역·257장, 모델·손실·임계·4배치 고정. 개발 적합은 한 번만 하고 실패는 기록한다.
- 가설 `corner-rank-full-development-head-v1`. 위 계획의 fold 적합 레시피를 고정 개발 전체에 한 번 적용하면 독립 평가용 단일 head를 수렴시켜 재로딩할 수 있다. 대조 E는 기존 SHA의 단일 head, 변경은 배정된 후보의 fold별 계수 대신 단일 개발 전체 계수 사용이다. 성공은 입력 해시·분모 확인, 유한한 최대 기울기 ≤1e−5, float32 계수/bias 정확 재로딩, 합성 점수 차이 ≤2e−6 및 경계 동일. 성능 판정은 별도 독립 평가에서 한다.
- checks: 공통 실행 로그·대상 소스 SHA, 두 head와 데이터·백본·평가 코드 SHA, 같은 입력/정답 검증, 합성 경계·동점·보류·계측 실행 수 검사. 현 task 소유권에서 verification-before-completion과 직접 기준 diff 검토 적용.
