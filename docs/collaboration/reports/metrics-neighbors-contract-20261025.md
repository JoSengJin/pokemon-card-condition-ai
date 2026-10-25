# 평가 지표 이웃 모듈 계약 검증 — 2026-10-25

task `metrics-neighbors-contract-20261025`, base `21809d54cf4d0f7d24ddcec1566ef48a407412cb`(main). Codex가 토큰 한도로 쉬는 동안 Claude가 오프라인으로만 수행했다. 모델 학습·추론·성능 평가는 하지 않았다. 진척률 30/100은 그대로다.

## 커밋 순서

1. `c2ddddb4582dcb2902befa49fb361f295c75998a` test: 임계값 스윕·실물 가중·쌍별 누락 전이 손계산 계약
2. `a29943b02a2a35c9e6b608e78596ec4ade38db70` test: 다른 종류 false positive가 섞이지 않음을 reference 쪽까지 확인
3. 이 문서 커밋: 작업 계약·Codex 복귀 프롬프트·보고서·HTML

## 손계산 근거

임계값 스윕: 행 `(실물, 면, 정답, 점수)` = g1 앞 1 .9 / g1 앞 0 .4 / g2 뒤 1 .35 / g2 뒤 0 .05 / g3 뒤 정답없음 .99.

| 임계값 | tp | fp | tn | fn |
|---|---:|---:|---:|---:|
| .1 .2 .3 | 2 | 1 | 1 | 0 |
| .4 | 1 | 1 | 1 | 1 |
| .5 – .9 | 1 | 0 | 2 | 1 |

- 정답 없는 행은 어떤 칸에도 들어가지 않는다. 양성 2 / 정상 2는 임계값과 무관하게 고정된다.
- 실물 단위: g1은 어느 쪽 오류도 없고 g2는 유일한 결함을 놓친다. 정답이 없는 g3은 어디에도 세지 않아 음성 실물 2, 양성 실물 2, 평균 오탐률 0, 평균 누락률 .5다.
- 같은 비중: 실물 A(정상 4개 중 1 오탐 = .25), B(정상 1개 중 1 오탐 = 1), 빈 실물 D 제외 → 평균 오탐률 (.25 + 1) / 2 = .625, 합산 비율 2/5와 다르다.
- 쌍별 전이: 기준 오류 {a, b} → 후보 {b, c}이면 새 누락 [c], 회복 [a], 지속 [b]. 새 누락 + 지속 = 후보 누락 수, 회복 + 지속 = 기준 누락 수. 회복이 있고 새 누락이 없고 false positive가 늘지 않을 때만 개선이다.

## 검사 결과

- `PYTHONPATH=tests .venv/bin/python -m unittest test_threshold_contract test_paired_miss_contract test_region_thresholds test_defect_regressions -v` → 12개 통과(신규 7, 기존 5), 종료코드 0.
- mutation(임시 복사본) 8개: 임계값 `>`, 정답 없음을 정상으로, 합산 비율, 없는 종류를 0으로, 누락/회복 뒤바꿈, false positive 종류 무시, 개선 판정에서 false positive 무시, 새 누락 무시. 7개는 바로 검출, 1개(종류 무시)는 reference 쪽 false positive를 넣어 보강한 뒤 검출.
- 함수 정의 수: 신규 테스트 5·5(7 이하), 소스 변경 없음.

## 미검증·리스크·롤백

- 미검증: `listing_readiness`(torch 필요), 실제 평가 결과, 기존 ML 의존 통합 검사.
- 리스크: 합성 입력의 계약 검증이며 모델 성능을 말하지 않는다. 결함이 없었다는 결과는 이 입력 범위에서만 유효하다.
- 롤백: 테스트·문서만 추가했다. 통합 시 이 브랜치 커밋을 revert하면 된다.


## Codex 인수 결과

검증 SHA 318362a81aacda4a2966b7a7039f656b3d7b4df1. 기본 checkout status/worktree/main 이력을 지정 순서로 확인하고, 고정 c872e964…의 프롬프트6/6-1/6-2절과 보고서·HTML을 읽었다. base21809d5 이후7커밋을 cherry-pick -x로 로컬 main에 통합했다. 브랜치/manifest에 rebase/reset은 하지 않았다. 이번 인수에서는 원격 push 금지 지시를 우선하여 push하지 않는다.

- 직접 실행: 지정 지표 검사12개 통과, listing_readiness5개 통과. 근거 artifacts/codex-resume-20261025/metrics-tests.log 및 listing-tests.log. 신규 테스트 정의5/5, source diff0, git diff --check 통과. Claude의 mutation8개는 재실행하지 않았다. 기존 전체 통합 검사나 실제 모델 평가는 이번에 실행하지 않았다.
- 잠금: 파일의 PID4844는 실행 중이 아니고 확인 시 flock은 비어 있었다. lsof의 읽기 FD는 배타 잠금 소유를 뜻하지 않는다. 잠금 파일을 삭제하지 않았다.
- latest.json은 completed인 과거060608 기록을 가리키며, 더 최근103800 completed 기록과 다르다. handoff는 ai_calls_forbidden이다. 최신 실험을 과거 성공으로 대체하거나 자동 review/실험을 재개하지 않았다.
- 기존 Claude 브랜치 patch 대조: 이번 metrics7커밋 외에는 pair-control18패치만 main 미반영이었다. pair-control은 변경하지 않았다.
- 현재 채택본 SHA4604d1ef… 및 직전5b2f3f9e…/원본d971dbca…를 대조했다. 저장된 coverage는 수량충족2/20이며 train 표면뒤52단위/20실물·표면앞52/13·엣지뒤72/30이다. 새 추론 없이 기존 기록을 읽은 값이며 전범위 A3/품질 충족이 아니다.
- candidate3 두 파일은 z만 다르고 front region_labels가9개/0개이며 box는 동일하다. 사용자 복원·채택 결정이 아직 없으므로 채택본/ADOPTION/원본은 변경하지 않았다. 저장되지 않은 정상 판단25개는 미확인으로 유지하고 재질문하지 않는다.

열린 항목 판단: 결과0600권한은 기존 Codex 수용 결정을 유지한다. ABA snapshot 구조나 sidecar/A3 정책의 새 구현·기준 변경은 이번 인수에서 시작하지 않는다. listing_readiness는 위5개 합성 계약 검사 범위에 한해 미검증을 해소했으며 실사용 전범위 E2나 실제 모델 성능을 증명하지 않는다.

진척30/100 유지. 학습·모델 추론·외부 AI0회. HTML에 이 결과와 채택 결정 대기를 표시했다. 열기는 브라우저에 요청하되 렌더 확인과 구분해 최종 인계한다.

롤백은 이번 인수 문서 커밋과 통합318362a,780f5c2,61090f6,b1c98ab,6beb408,dfd7917,a75ca29를 최신→과거 순서로 revert한다. 데이터/모델은 변경하지 않았다. 실제 채택은 사용자 결정 전까지 보류다.
