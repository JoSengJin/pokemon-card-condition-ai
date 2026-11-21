# Codex 인계: 모서리 애매 구역 학습 제외 실험 (2026-11-21)

````text
목표: 후면 모서리 후보 E 레시피에서 "애매" 구역만 학습에서 빼는 단일 변경 실험을 ./experiment로 1회 실행하고, 합의 구역 기준으로 판정·보고한다. 정확도 우선(사용자 2026-11-21). 답은 한국어, 결론 먼저, 에튜 1~3개.

먼저 읽기: AGENTS.md → docs/AGENT_START.md → PAIR_CODING.md(함수 ≤7/파일, 호출 깊이 ≤4) → COMMON_EXPERIMENT_RECORDS.md → docs/superpowers/specs/2026-11-21-corner-label-definition-design.md(특히 "합의 정의와 다음 실험") → docs/collaboration/reports/corner-blind-rejudge-20261121.md.

확인된 상태(원문 재확인 후 사용):
- 합의 상태: artifacts/corner-rejudge-20261121/consensus-status.json (Git 제외, 생성기 tools/diagnostics/corner-consensus-20261121/build_consensus.py). 946구역 중 합의 167(결함74/정상93), 애매 193(106/87), 미판정 586(225/361).
- 대조: 후보 E 저장 OOF artifacts/experiments/20261102T140143-82781117/observations.json (전체 AUC 0.8565, 합의 0.939, 애매 0.743, 미판정 0.865).
- 템플릿: tools/experiments/corner-mlp-head-20261121/{worker.py,head.py,plan.json}(대조 저장 점수 비교·card_miss·부트스트랩 구현), tools/experiments/corner-same-photo-pair-cv-20261102/worker.py(oof, pair.fit_pair).

실험(결과 전 고정, 설계서와 같음):
- 변경 변수 하나: 학습 fold에서 status=='ambiguous' 구역만 제외. 미판정·합의는 그대로. 평가 fold는 946 전부 점수화. fold·특징·λ=1.0·LBFGS·head 불변.
- 주 판정: 합의 구역만의 OOF 풀링 AUC 차이 ≥ +0.01이고 사진 그룹 짝지은 부트스트랩(2000) 하한 > 0, 그리고 합의 구역으로 계산한 카드 단위 누락(대조의 v1.14 오탐 ≥0.60 건수로 맞춘 임계)이 대조보다 많지 않음. 보조: 전체 946 AUC 하락 ≤ 0.01.
- 수렴 실패·실행 오류는 failed, 재시도·설정 변경 금지. 결과 본 뒤 기준 변경 금지.
- 합의 상태 파일 SHA를 plan.input_sha256에 고정한다.

규칙: 소스는 ./develop -- <명령>(먼저 ./develop --check). 실험은 ./experiment --plan <plan.json> -- <명령>. Gemini 0, 운영 코드·동결 임계·진척 기준 변경 금지, D1 봉인·D2 사용 금지. 사람 라벨 변경·재요청 금지, 미판정을 정상/결함으로 채우지 않는다. 개발 OOF는 "개발 개선, 일반화 미확인". 평가 턴은 구역별 사람 정답·모델 출력·분모 HTML을 만든다.

보고: 첫 줄 진척(변화 없으면 78/100)과 성과. 합의 구역 분모의 누락·오탐·AUC와 대조 대비 %p, record.json 경로·상태·판정, 변경 파일·검증·리스크·롤백. 검증 후 기능별 커밋, ./develop -- git push origin main(force 금지).

남은 사용자 결정(이 실험과 무관, 묻지 말고 기록만): 독립 평가용 새 사진 수집(합의율 약 1/3 → 합의 구역 200곳에 카드 약 150장·판정 약 1200회 추정).
````

## 실행 계약

- task_id: corner-consensus-experiment-20261121
- owner: Codex
- status: integrated
- base_sha: 35c0ac40db6d87f2f2cdfa6a18ebb146b8403431
- branch: main (기본 checkout 단독·직렬 실행)
- allowed_files: 이 task, `tools/experiments/corner-consensus-experiment-20261121/{worker.py,plan.json}`, `docs/collaboration/reports/corner-consensus-experiment-20261121.md`.
- 산출물: Git 제외 `artifacts/corner-consensus-experiment-20261121/`의 실행용 worker 복사본·검사 로그·`report.html` 및 공통 실행기의 고유 실험 폴더.
- 금지: 원 라벨·입력·운영 코드·진척 기준 수정, D1·D2 열람 및 사용, 외부 AI 호출, 실패 재실행.
- 구조: worker.py 신규 함수 4개. 새 경로는 run → folds → 기존 check_separation, run → evaluate → 기존 paired_bootstrap → 기존 auc 및 run → 기존 pair.fit_pair 호출이다. 학습 함수를 새 래퍼로 감싸지 않는다. 기존 최적화의 Torch 콜백은 코드 변경 범위 밖이다.
- checks: 고정 SHA와 대조 점수·행 일치, 기존 접기 및 제외 범위·사진/그룹 분리, 고정 수치 판정 합성 검사, 지정 공통 실행 1회, 기록 검산, HTML 내용/열기, Git diff/원격 확인.
- handoff: 실행 기록과 검사 결과는 같은 이름의 reports 문서에 남긴다. 독립 평가 선행 결정으로 합의 200곳 확보에 카드 약 150장·판정 약 1200회가 필요하다는 추정을 기록한다.

## 실행 결과

- 공통 실행 기록 `artifacts/experiments/20261121T001341-b2e94833/record.json`, 상태 `completed`, 종료 0, 사전 기준 `criterion_met=false`.
- [결과 및 검증 보고](../reports/corner-consensus-experiment-20261121.md)에 변경, 수치, 검사, 리스크와 롤백을 남겼다.
- 산출물 `artifacts/corner-consensus-experiment-20261121/report.html`. 브라우저 열기 요청 성공 및 Chrome 헤드리스에서 지표·대표 사진 오버레이 렌더 확인.
