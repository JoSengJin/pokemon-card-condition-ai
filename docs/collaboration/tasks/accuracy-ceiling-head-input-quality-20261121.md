# 정확도 개선 인계 프롬프트 — 라벨 상한 → head 구조 → 입력 품질 (2026-11-21)

다른 세션에 그대로 붙여 넣는다. 설계: `docs/superpowers/specs/2026-11-21-accuracy-ceiling-head-input-quality-design.md`.

````text
목표: 후면 점검 모델의 정확도(같은 자료·같은 분모의 누락·오탐·AUC)를 올린다. 진척률 점수 작업(F1·D3 작동점)이나 작동점·정의를 바꿔 수치를 낮추는 일은 하지 않는다(사용자 결정 2026-11-21).
답은 한국어, 결론부터 짧게. 코드·경로·명령은 원문. 마지막에 에튜 1~3개. 이 프롬프트를 포함한 이전 결론은 원본 파일·로그로 재확인하고, 모르면 "미확인"으로 적는다.

## 먼저 읽기
AGENTS.md 전체 → docs/AGENT_START.md → PAIR_CODING.md(함수 ≤7/파일, 호출 깊이 ≤4) → COMMON_EXPERIMENT_RECORDS.md → 설계 docs/superpowers/specs/2026-11-21-accuracy-ceiling-head-input-quality-design.md → docs/collaboration/reports/corner-d3-diagnosis-20261121.md. 스킬은 AGENT_START 선택표만(verification-before-completion 기본, writing-plans는 계획서 단계).

## 순서와 관문
W1 라벨 상한(읽기 전용) → 관문 → W2 head 구조(실험 1회) → W3 입력 품질(진단 → 규칙 실험). W1 결과로 W2 진행 여부가 갈린다.

W1. 같은 사람이 같은 칸·구역을 두 번 이상 답한 기존 기록으로 칸별 일치율·Cohen kappa·분모, 라벨 뒤집힘 가정의 관찰 AUC 상한(가정 명시)을 구한다. 새 라벨 요청 없음.
- 출발 근거: label-reliability-20261111.md(재판정 40곳 kappa 0.472, TN 숨은 결함율 41~50% — 어느 칸·기준인지 원문 확인), label-boundary-criteria-20261112.md, normal-rejudge-20261112.md, E2 재요청 4장(12문항 중 10 일치: artifacts/e2-scenario-20261104/walkthrough*.txt ↔ artifacts/e2-scenario-20261120/answers-*.txt), 미리 채움 격리 u·v. 기준 문구가 다른 판정끼리 섞지 않는다.
- 관문(결과 전 고정): 칸 분모 <30구역이면 "미측정" + 소규모 블라인드 재판정을 사용자에게 제안만. 상한 ≤ 현 AUC+0.03이면 W2 보류하고 라벨·target 정의 선택지를 사용자에게 올린다. 그 외 W2 진행.

W2. 모서리 후보 E 레시피(946구역, 같은 사진 쌍 순위 항 λ=1.0, artifacts/corner-same-photo-pair-cv-20261102/worker.py, head confounder_head.py)에서 토큰 점수기 선형 → 은닉 1층 MLP(폭 64) 하나만 바꾼다.
- 사전 기준: 풀링 AUC +0.02 이상·부트스트랩 하한 >0, 같은 사진 AUC 하락 없음, 오탐을 맞춘 카드 단위 누락이 대조보다 많지 않음. 대조 = 기록 artifacts/experiments/20261102T140143-82781117의 저장 점수(AUC 0.8565, 같은 사진 0.796, v1.14 작동점 누락 7/176·오탐 10/81은 참고).
- 수렴 실패는 failed로 두고 설정을 바꿔 재시도하지 않는다.

W3. 자동 품질 지표(원본 가로 px, 크롭 px, 라플라시안 분산, 포화 픽셀 비율)별 누락·오탐과 위험-범위 곡선을 먼저 진단한다. 슬리브 판별은 눈 확인 표본으로 검증한 뒤에만 쓴다. 규칙 실험은 결과 전에 정한 단일 지표·임계로, 보류 ≤20%에서 남은 카드의 누락·오탐 감소를 본다. 보류는 범위 축소로 따로 보고한다.

## 규칙
- 소스는 `./develop -- <명령>` 안에서만(먼저 `./develop --check`). 실험은 `./experiment --plan <plan.json> -- <명령>`만. 결과를 본 뒤 기준을 바꾸지 않는다. 공유 코드 복사 확장은 동등성 테스트 먼저.
- 학습·평가 사진 그룹 분리. D1 봉인·D2 시험 자료 사용 금지. Gemini 0, 운영 코드·운영 fallback·동결 임계·진척 기준 변경 금지.
- 사람 정답을 모델 오답 때문에 바꾸지 않고, 완료 라벨을 재요청하지 않으며, 미확인을 정상/결함으로 채우지 않는다.
- 비교는 오탐을 맞춘 누락과 AUC로. 절대 임계 고정 건수만으로 개선을 말하지 않는다(보정 이동 혼입).
- 개발 OOF 결과는 "개발 개선, 일반화 미확인". 성능을 평가한 턴은 구역별 사람 정답·모델 출력·분모 HTML을 갱신해 연다.
- 검증된 변경은 기능별 커밋 후 `./develop -- git push origin main`(SHA별 사용자 직접 승인 뒤, 사람이 직접 연 메인 세션만). force push 금지. 커밋 끝에 현재 세션 지침의 Co-Authored-By 줄.

## 보고
첫 줄: 개발 진척률(변화 없으면 78/100 불변)과 이번 성과. 이어서 같은 분모의 누락·오탐·AUC와 이전 대비 %p, record.json 경로·상태·판정, 변경 파일·실행/미실행 검증·리스크·롤백. 사용자 결정이 필요하면 근거 수치와 함께 하나씩 묻는다.
````
