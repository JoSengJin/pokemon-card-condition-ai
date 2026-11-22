# 후면 모서리 애매 구역 학습 제외 실험

> **정정 2026-11-22:** 이 문서가 쓰는 재판정 답의 판정 주체는 사람이 아니거나 미확인이다. [label-provenance-correction-20261122.md](label-provenance-correction-20261122.md) 참고.

**개발 진척 78/100(v1.14, 0%p) · 공통 실행 1회 완료 · 사전 성공 기준 미달.**
합의 구역 AUC는 거의 같았고, 같은 카드 오탐 4건에서 누락이 9건에서 11건으로 늘었다. 후보 E 유지. 일반화 개선 미확인.

## 사전 기준과 결과

| 항목 | 후보 E | 애매 제외 | 변화 및 판정 |
|---|---:|---:|---|
| 합의 167구역 AUC | 0.93868 | 0.93926 | +0.00058, +0.01 기준 미달 |
| 합의 AUC 차이 95% 구간 | — | [-0.02207, +0.02141] | 하한 > 0 기준 미달, 같은 그룹 짝지은 부트스트랩 2,000회 |
| 합의 카드 누락 | 9/62 (14.52%) | 11/62 (17.74%) | +3.23%p, 대조 이하 기준 미달 |
| 합의 카드 오탐 | 4/69 (5.80%) | 4/69 (5.80%) | 0.00%p |
| 합의 구역 누락 | 14/74 (18.92%) | 15/74 (20.27%) | +1.35%p |
| 합의 구역 오탐 | 4/93 (4.30%) | 6/93 (6.45%) | +2.15%p |
| 전체 946구역 AUC | 0.85648 | 0.86083 | +0.00435, 하락 ≤ 0.01 기준 충족 |

합의 167곳(결함 74, 정상 93)에서 후보 E 점수 0.60의 카드 오탐 4건을 예산으로 썼다. 두 모델의 카드 오탐 4건에 대응하는 비교 임계는 0.54564와 0.64946이다. 누락은 합의 결함 모서리 전부가 해당 임계 미만인 카드 수이며, 카드 오탐은 합의 결함이 없는 카드에서 합의 정상 모서리 중 하나 이상이 임계 이상인 카드 수다. 이 임계는 개발 비교 값이다.

애매 193곳은 재판정 360곳의 53.61%, 전체 946곳의 20.40%였다. 미판정 586곳은 상태를 유지했고, 학습에는 해당 구역의 기존 라벨을 사용했다. 원 라벨과 재판정 답은 보존했다.

## 변경과 검증

- `tools/experiments/corner-consensus-experiment-20261121/worker.py`와 `plan.json`을 추가했다. 후보 E의 5개 사진 그룹 fold, 448px DINOv2 특징, 선형 head, λ=1.0과 LBFGS에서 학습 행 선택만 변경했다. 평가 행 946개와 후보 E 대조 점수는 공통 기록에 동결했다. 합의 상태 SHA256은 `68417c98d740ce1466c870c406241d915d2d03267523b8684b5ba5b09f808d50`다.
- 사전 검사 종료 0. 각 구역의 평가 배정 1회, 각 비애매 구역의 학습 배정 4회, 각 애매 구역의 학습 배정 0회, 사진 원본·디코딩 해시와 카드 그룹의 fold 내 교차 0건을 확인했다. 후보 E 점수와 대조 기록 일치를 검사했다.
- `./experiment --plan tools/experiments/corner-consensus-experiment-20261121/plan.json -- .venv/bin/python artifacts/corner-consensus-experiment-20261121/worker.py` 종료 0. 샌드박스 밖 MPS에서 후보 E와 동일 장치 유형을 사용했고 5/5 fold가 수렴했다(최대 기울기 1.15e-6). Gemini 및 기타 외부 AI 호출 0건, D1·D2 입력 사용 0건. 자동 개발 인계는 이번 실행에서 생성되지 않았다.
- `artifacts/experiments/20261121T001341-b2e94833/record.json`은 `completed`. 공통 실행기의 `result.json.acceptance_passed=true`는 0.5 구역 FN/FP 기록용 상한 결과다. 사전 성능 판정은 `evaluation.json.criterion_met=false`다.
- 사후 검산 종료 0. 동결 입력·snapshot SHA, 원본 행과 점수 946개, 순위합 방식으로 독립 계산한 AUC 및 부트스트랩 2,000회, 같은 임계의 FN/FP 일치를 확인했다. 검증 worker SHA256은 `205b5a0c9336993cf28b72728f2a9d16f4ca2bcb0b2a90e80aed3f74fda8f573`, 평가 파일 SHA256은 `366b777e30c776a3b92b863bd389042519348f19b062949f63f9d1a9fa2658b8`다.
- `artifacts/corner-consensus-experiment-20261121/report.html`에 원 라벨·재판정 상태·두 모델 점수를 사진 257장과 946개 구역으로 표시했다. 로컬 `open` 종료 0. Chrome 헤드리스 스크린샷에서 첫 화면의 지표, 사진과 구역 오버레이를 확인했다. `preflight.log`, `run.log`, `verification.log`는 같은 폴더에 보존한다.
- 코드 검토는 task의 base SHA `35c0ac40db6d87f2f2cdfa6a18ebb146b8403431` 기준으로 직접 수행했다. Ponytail, verification-before-completion, requesting-code-review의 본문을 읽었고, 저장소의 호출 제한에 따라 외부 검토 요청 없이 직접 대조했다. 고정 진척 정본 합계는 78점으로 확인했다.

## 근거, 리스크, 롤백

필독 원문은 `AGENTS.md`, `docs/AGENT_START.md`, `PAIR_CODING.md`, `COMMON_EXPERIMENT_RECORDS.md`, `OBSERVATION_CONSENSUS_20261011.md`, `LABELING_PROTOCOL.md`, `PROGRESS_CRITERIA.md`, `development-progress.json`, `docs/collaboration/HTML_REPORTING.md`, [설계서](../../superpowers/specs/2026-11-21-corner-label-definition-design.md), [재판정 보고](corner-blind-rejudge-20261121.md), [실행 계약](../tasks/corner-consensus-experiment-20261121.md)이다.

이 결과는 한 사람의 재판정이 포함된 개발 OOF 비교다. 후보 E 대조는 과거 저장 점수이므로 실행 환경의 시간차 효과를 분리하지 못한다. 독립 사진 수집은 보류 결정으로 기록했다. 합의 구역 200곳을 확보하려면 카드 약 150장·판정 약 1,200회가 필요하다는 인계 추정이다.

코드와 문서는 해당 커밋을 역순으로 `./develop -- git revert <SHA>`하고, 검증 후 일반 push로 되돌릴 수 있다. 실행 기록과 사진은 Git 제외 산출물로 보존한다.
