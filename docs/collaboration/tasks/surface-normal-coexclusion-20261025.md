task_id: surface-normal-coexclusion-20261025
owner: Claude (진단·계약), 구현은 Codex 계약 검토 후 배정, 실행은 Codex(기본 checkout)
status: assigned (계약안, 구현·실행 전)
base_sha: 92a85e89d03554c3256a0b36f93fdc263b8bfc62 (검증된 origin/main, 2026-10-25 fetch 확인)
branch: claude/surface-normal-coexclusion-contract-20261025 (이 문서만)
assignment: 사용자가 joint holdout 결과 진단과 다음 실험 1개 계약안을 요청했다(읽기 전용). 구현·학습·실행은 하지 않았다.

## 1. 확인된 사실 (artifacts/experiments/20261025T122011-647b0e9c, 읽기 전용 집계)

- 실행 무결성: completed, return_code 0. 정본·미러 worker SHA 5db79c3d…가 같다. worker가 현재 후보 재생(2e-5), proposal SHA, fold 재계산, 원본·디코딩 누수 검사를 통과한 뒤 학습했다. fold 4개 모두 converged, max_gradient ≤3.02e-6.
- 학습 코드 대조: fold 학습의 가중치와 호출(`1/실물 행 수`, 양성 질량을 정상 질량에 맞춤, `fit_detail_head(..., penalty=1., normal_reduction='max_bound')`)은 단독 제외 head를 만든 artifacts/surface-dino-front-rgb-20261024/worker.py 41행과 같은 식이다. `fit_detail_head`는 중심화 후 `intercept=bias-center@coef`로 원 좌표 절편을 돌려준다(card_condition/detail_bag.py). 단독 제외와 joint의 적용식 `x@coef+bias`도 같다. 같은 코드로 단독 제외 head를 다시 만들어 보는 재현 검사는 아직 없다(아래 실험의 대조에 포함).
- 앞면 91행의 감독 구조는 실물 단위로 거의 분리돼 있다.

| 출처(파일·해상도) | 실물 | 감독 |
|---|---|---|
| img*.png 388–675px 폭 | b, c, ㄴ | 정상 9구역씩 |
| img*.png 388–449px 폭 | ㅋ-2, ㅋ-3, ㅋ-7, ㅋ-8, ㅋ-10 | 사람 클릭 점만 |
| Screenshot 748–958px 폭 | u, x, z, v | 약한 구역 양성(카드 전체 8–9구역), v는 정상 1구역 추가 |
| Screenshot | a(정상 9), k(정상 1) | 정상 |
| eBay jpg 690–1297px | 7efc, 9f1c, a20c, d22b, (훈련 전용 ff69) | 클릭·정상 일부 |

  ID의 normal 문자열은 행 유형 이름일 뿐이다. 실제 target은 정상 40행, 약한 양성 33행(ID에 normal 포함), 클릭 18행이다. 약한 양성은 Screenshot에만 있고, img 출처의 양성은 클릭뿐이다. 즉 출처와 감독 방식이 섞여 있다(교란).
- 새 FP 9개는 모두 img 정상 카드에서 나왔다: c 5(fold 3), ㄴ 2(fold 3), b 2(fold 4). 복구 5개 중 a 2(Screenshot 정상)가 있다. 정상 카드별 평균 최대 logit(단독 제외 → joint): a −0.67→−1.15, b −0.51→−0.51, c −0.80→+0.05, ㄴ +0.30→+0.55. FP 수는 a 2→0, b 1→2, c 1→6, ㄴ 4→5다.
- 새 FN 5개: v 3(fold 4), z 1(fold 1)은 Screenshot 약한 양성이고, ㅋ-2 1(fold 4)은 img 클릭이다. 클릭 18행의 구역 수준 오류는 단독 제외 0, joint 1이다. typed 점 FN(9→10/18)은 점 토큰 점수라 구역 최대 점수와 다른 지표다.
- fold 안 순위(임계값 없는 AUROC, 같은 held 행, 단독 제외 → joint)와 감독 유형별 평균 logit 이동:
  - fold 1 (u, z 등 제외; 학습 약한 양성 실물 2개뿐): AUROC .881 → .881. 약한 양성 logit 1.06 → 0.38, 오류 5 → 6.
  - fold 2: AUROC .833 → .958. 정상 −0.45 → −0.85.
  - fold 3 (c와 ㄴ 함께 제외): AUROC .917 → .931. 정상 −0.25 → +0.30, 클릭 1.77 → 2.40. 모든 점수가 함께 올라갔다. 절편은 −2.461로 fold 중 가장 높다(다른 fold −2.88 ~ −3.54, 단독 제외 a/b/c/ㄴ −2.48 ~ −2.89). 단, 절편은 coef·중심화와 함께 봐야 한다.
  - fold 4 (b, v 제외): AUROC .82 → .67. 순위가 실제로 나빠졌다.

## 2. 진단 (인과 결론 아님)

- 구현 오류: 재생·분할·누수·수렴 검사를 통과했고, 학습식이 기존과 같으며, fold마다 변화 방향이 다르다(fold 2는 개선). 구현 오류 하나로 설명되는 패턴이 아니다. 같은 코드의 단독 제외 재현은 미검증이다.
- FP 증가(+12.50%p)는 fold 3·4의 img 정상 카드에 몰려 있다. fold 3은 held 순위가 유지된 채 점수 전체가 오른 형태다. 이는 결정 경계의 위치(offset)가 학습 구성에 민감하다는 신호로 읽힐 뿐이며, 원인은 다음 경쟁 설명으로 남는다.
  - H1 전체 정상 구성: 9구역 정상 카드가 2장 빠지면 출처와 상관없이 offset이 오른다.
  - H2 출처 조건 지름길: img 출처의 학습 자료에서 정상(b, c, ㄴ) 대 양성(ㅋ 클릭) 균형이 바뀔 때만 img 정상에서 FP가 오른다. 저해상도 이미지의 외형을 정상 신호로 일부 쓰고 있을 가능성이다.
  - H3 카드 쌍 특이성: c는 ㄴ이 학습에 있을 때만 정상으로 보인다(같은 출처라는 이유와 무관한 개별 유사성).
- FN 증가(+7.84%p)는 Screenshot 약한 양성에 몰려 있고, fold 1에서 학습 약한 양성 실물이 2개뿐인 구성과 겹친다. 그러나 약한 양성은 출처·라벨 방식(카드 전체 구역)·실물이 모두 묶여 있어 현재 자료로는 원인을 식별할 수 없다(미확인).
- 기존 진단과의 관계:
  - 101432 공간 감사는 정상 초과 반응의 경계·위치 집중을 지지하지 않았다. 출처나 offset 설명과 충돌하지 않는다.
  - 103800은 분할 가능성만 검증했다. 이번 결과가 그 분할을 무효로 만들지 않는다.
  - 063443의 frozen 삭제는 재학습이 아니라서, 학습 구성을 바꿨을 때의 offset 변화는 본 적이 없다.
- 미확인: 표현력과 선형 head의 한계, 촬영 조건과 인쇄 디자인의 분리, 약한 양성 FN의 원인, 일반화. 앞면 정상 카드는 4장(9구역)뿐이고 fold들은 학습 자료를 공유한다. 모든 수치는 반복 개발 자료의 기술 통계다.

## 3. 다음 실험 (정확히 1개): 정상 카드 쌍 공동 제외 재학습 진단

goal: img 정상 카드의 FP 증가가 H1(구성), H2(출처 조건), H3(카드 쌍) 중 어느 형태와 맞는지, 함께 제외하는 정상 카드 하나만 바꿔 구별한다. 같은 코드로 단독 제외 head를 재현하는 구현 대조도 함께 한다.

변경 변수 하나: 대상 정상 카드 g와 함께 학습에서 빼는 정상 카드 h의 정체(같은 크기 9구역 정상 카드 중 하나).
- 대상 T = {a, b, c, ㄴ} (앞면 9구역 정상 카드 전부). 각 g에 대해 h ∈ T\{g}마다 1회 학습한다(12회). 양성 행과 나머지 정상은 전부 유지하므로 학습 양성 구성은 단독 제외와 같다.
- 대조(재현) 4회: g만 제외하고 다시 학습해 저장된 단독 제외 head(093945 local-heads.pt의 front g)의 g 9구역 점수와 비교한다. 최대 절대차 ≤1e-4이면 구현 동일로 본다. 넘으면 이 실험을 해석하지 않고 실패로 기록한다.
- 고정: 특징 캐시 typed-training-tokens.pt(legacy와 동일 확인), 153행 중 앞면 전 행, 사람 점 토큰, 실물·클래스 균형 가중치, max_bound, L2=1, threshold 0.5, fit_detail_head. 뒷면은 학습하지 않는다.
- 평가 단위: g의 정상 9구역 최대 점수(FP 수, 평균 최대 logit). 다른 행은 평가에 쓰지 않는다.
- 출처 속성은 사전 고정이다(정답이 아닌 파일 메타데이터): img = 파일명이 img로 시작(b, c, ㄴ), screenshot = a.

경쟁 설명별 예상 결과 (기준은 단독 제외 저장값 FP_L(g): a 2, b 1, c 1, ㄴ 4):
- H1: 세 img 대상 각각에서 h가 a든 img든 FP 증가가 비슷하다.
- H2: img 대상은 같은 출처 h(다른 img 카드)를 뺄 때만 FP·logit이 오르고, h=a일 때는 거의 그대로다. a 대상은 어떤 img h를 빼도 그대로다.
- H3: c는 h=ㄴ일 때만, ㄴ은 h=c일 때만 오르고, 같은 출처의 b를 뺄 때는 오르지 않는다.

사전 판정 규칙 (결과를 보기 전 고정, 진단용, 채택 기준 아님):
- Δ(g,h) = FP(g,h) − FP_L(g). 같은 출처 평균 Δ_same(g)는 img h 2개의 평균, Δ_cross(g)=Δ(g,a). logit도 같은 방식으로 정의한다.
- H2 지지: img 대상 3개 중 2개 이상에서 Δ_same ≥ Δ_cross + 2구역 그리고 logit 차 ≥ 0.3. 동시에 a 대상의 모든 h에서 |Δ| ≤ 1.
- H1 지지: img 대상 3개 중 2개 이상에서 Δ_cross ≥ 2 그리고 |Δ_same − Δ_cross| ≤ 1.
- H3 지지: FP(c,ㄴ) − FP(c,b) ≥ 3 그리고 FP(ㄴ,c) − FP(ㄴ,b) ≥ 3.
- 둘 이상 동시 충족이나 모두 미충족이면 "미구별"로 기록한다. 미구별도 정당한 결과이며 기준을 사후 조정하지 않는다.
- 표본 한계: 대상 카드 4장, 각 9구역의 기술 통계다. 유의성·일반화 주장은 하지 않는다.

이 실험이 다음 판단을 바꾸는 방식:
- H2 → 모델 가중치 조정보다 출처 균형이 먼저다. A3 수집에서 img·Screenshot 각각에 정상과 양성을 함께 확보하고, 해상도 정규화 같은 입력 단일 변수 실험을 우선한다.
- H1 → 그룹 균형 가중치나 offset 추정(중첩 그룹 교차검증 기반)이 다음 모델 쪽 단일 변수 후보가 된다.
- H3 → 일반 수정 대상이 아니다. 정상 카드 다양성(자료)이 우선이다.
- 재현 실패 → 성능 해석을 중단하고 학습 경로 차이부터 조사한다.

공통 실행기 출력 계약:
- experiment_kind=diagnostic.
- 주 평가 147행 점수는 122011 fold-heads.pt의 maps를 재생해 제출한다(재학습 아님, 2e-5 일치 검사). reference_result=artifacts/experiments/20261025T122011-647b0e9c/result.json.
- acceptance는 기준선 재생 동일성 확인용으로 max_fn 16, max_fp 18, no_new_errors true, require_actual_point_guard false이다. required_cohorts는 122011과 같은 11개·같은 기준을 그대로 두며 기존대로 미통과가 예상된다. 진단 결과는 diagnostic_evidence(4000바이트 이하)와 diagnostics.json에 둔다. 모델·threshold 채택은 없다.

누수 보호: 각 학습에서 g와 h의 모든 행을 제외하고 원본 SHA·디코딩 해시 교차가 없음을 확인한다. 훈련 전용 6행(ff69)은 g, h와 겹치지 않음을 확인한다. 평가에는 g의 행만 쓴다. 단독 제외 저장값과 joint 기준선은 읽기만 하며 덮어쓰지 않는다.

실행 의존:
- (1) Codex 계약 검토
- (2) 구조 규칙: 이 worker도 fit_detail_head(LBFGS closure)를 부른다. PyTorch 내부 프레임까지 세면 4회를 넘는다. C task의 계산 예외는 다른 작업에 확대하지 말라고 했으므로, 이 task에 같은 계산 방식을 허용할지 사용자 결정이 필요하다. 허용하지 않으면 card_condition을 바꾸지 않는 한 구현할 수 없다.
- (3) 구현 worktree 배정
- (4) 기본 checkout에서 실행

## 4. 구현 계약 (승인 후)

allowed_files:
- tools/experiments/surface-normal-coexclusion-20261025/worker.py (신규 정본)
- tools/experiments/surface-normal-coexclusion-20261025/plan.json (신규)
- tests/test_normal_coexclusion_worker.py (신규, 합성 fit만)
- 이 task 문서
- ignored: artifacts/surface-normal-coexclusion-20261025/worker.py(실행 미러, SHA 동일), artifacts/surface-normal-coexclusion-contract-20261025/index.html(이번 진단 보고)

forbidden_files: card_condition/* 전부, 기존 실험 폴더·캐시·heads, 라벨·사람 정답, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, 운영 Gemini 경로, 다른 task 소유 파일.

structure (계획):
- worker 함수 ≤7개(sha, pair_plan, fit_excluding, target_scores, replay_baseline, render, finish 예정).
- 학습 경로: 모듈 guard → fit_excluding → fit_detail_head → closure → detail_bag_loss. worker 정의 함수 기준 전이는 C와 같은 형태이다. 라이브러리 내부 프레임 계산은 위 실행 의존 (2)의 결정을 따른다.

checks:
- 합성 테스트: 쌍 목록 12개와 재현 4개 생성, g·h 제외 누수 거절, 평가 행이 g만인지, Δ 판정 규칙의 경계값(정확히 2, 1, 3).
- 계획 정적 검사: 러너 검사를 읽기 전용으로 재현하고, required_cohorts 11개 보존을 확인한다.
- 실행 후 확인: 재현 4개 최대 절대차, fit 16개 수렴, 판정 규칙 결과와 원시 FP·logit 표, 주 평가 재생 동일성.

HTML 산출물:
- 이번 진단: artifacts/surface-normal-coexclusion-contract-20261025/index.html (Claude worktree, ignored, 새 추론 없음, 기존 기록 집계만)
- 실행 후: 실험 폴더 index.html. g별 사진 위에 9구역 사람 정답(정상)과 h별 점수를 표시한다. FP 분모 9, 단독 제외 대비 변화도 넣는다. 반복 개발 자료이며 독립 시험이 아님을 표시한다.

risks:
- 정상 카드가 4장뿐이라 판정 규칙의 결과가 한두 구역에 좌우된다.
- 출처 속성이 해상도·인쇄·촬영자를 함께 묶고 있어, H2가 지지돼도 "해상도" 하나로 특정할 수 없다.
- 단독 제외 head 재현이 1e-4를 넘으면 실험 전체를 해석할 수 없다.
- fit 16회는 같은 학습 자료를 크게 공유한다.

rollback: 이 브랜치의 문서 커밋을 revert한다. 구현 후에는 tools·tests 신규 파일 revert, 실험 폴더는 기록으로 보존한다. 모델·라벨·기준 변경 없음. 진척 30/100, F1·E2·C3 pending 유지.
