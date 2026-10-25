task_id: surface-normal-coexclusion-20261025
owner: Claude (후속 worker·plan·합성 검사 구현), Codex (이번 계약 수정·재검토·통합; 기본 checkout 실행 담당)
status: assigned (Codex 수정·재검토로 계약 승인; 후속 구현 미착수·실험 미실행)
base_sha: 92a85e89d03554c3256a0b36f93fdc263b8bfc62 (검증된 origin/main, 2026-10-25 fetch 확인)
branch: claude/surface-normal-coexclusion-implementation-20261025
source_contract_branch: claude/surface-normal-coexclusion-contract-20261025 (973456b → 332f264)
assignment: 사용자 요청으로 이번 계약 수정 반영은 Codex가 대신 수행했다. Codex가 기존 기록을 검산하고 사전 판정 규칙·기록 계약을 수정해 승인했다. 이 승인은 후속 구현의 계약 확정이며 실제 학습·추론·실험 실행 승인이 아니다. 이번 변경은 이 문서뿐이다.

## 1. 확인된 사실 (artifacts/experiments/20261025T122011-647b0e9c, 읽기 전용 집계)

- 실행 무결성: completed, return_code 0. 정본·미러 worker SHA 5db79c3d…가 같다. worker가 현재 후보 재생(2e-5), proposal SHA, fold 재계산, 원본·디코딩 누수 검사를 통과한 뒤 학습했다. fold 4개 모두 converged, max_gradient ≤3.02e-6.
- 학습 코드 대조: fold 학습의 가중치와 호출(`1/실물 행 수`, 양성 질량을 정상 질량에 맞춤, `fit_detail_head(..., penalty=1., normal_reduction='max_bound')`)은 단독 제외 head를 만든 artifacts/surface-dino-front-rgb-20261024/worker.py 41행과 같은 식이다. `fit_detail_head`는 중심화 후 `intercept=bias-center@coef`로 원 좌표 절편을 돌려준다(card_condition/detail_bag.py). 단독 제외와 joint의 적용식 `x@coef+bias`도 같다. 같은 코드로 단독 제외 head를 다시 만들어 보는 재현 검사는 아직 없다(아래 실험의 대조에 포함).
- 앞면 91행의 감독 구조는 실물 단위로 거의 분리돼 있다.

| 출처(파일·해상도) | 실물 | 감독 |
|---|---|---|
| img*.png 388–675px 폭 | b, c, ㄴ | 정상 9구역씩 |
| img*.png 388–449px 폭 | ㅋ-2, ㅋ-3, ㅋ-7, ㅋ-8, ㅋ-10 | 사람 클릭 점만 |
| Screenshot 748–936px 폭 | u, x, z, v | 약한 구역 양성 u 8·x 9·z 9·v 7구역, v는 정상 1구역 추가 |
| Screenshot | a(정상 9), k(정상 1) | 정상 |
| eBay jpg 690–1297px | 7efc, 9f1c, a20c, d22b, (훈련 전용 ff69) | 클릭·정상 일부 |

  ID의 normal 문자열은 행 유형 이름일 뿐이다. 실제 target은 정상 40행, 약한 양성 33행(ID에 normal 포함), 클릭 18행이다. 약한 양성은 Screenshot에만 있고, img 출처의 양성은 클릭뿐이다. 즉 출처와 감독 방식이 섞여 있다(교란).
- 새 FP 9개는 모두 img 정상 카드에서 나왔다: c 5(fold 3), ㄴ 2(fold 3), b 2(fold 4). 복구 5개 중 a 2(Screenshot 정상)가 있다. 정상 카드별 평균 최대 logit(단독 제외 → joint): a −0.67→−1.15, b −0.51→−0.51, c −0.80→+0.05, ㄴ +0.30→+0.55. FP 수는 a 2→0, b 1→2, c 1→6, ㄴ 4→5다.
- 새 FN 5개: v 3(fold 4), z 1(fold 1)은 Screenshot 약한 양성이고, ㅋ-2 1(fold 4)은 img 클릭이다. 클릭 18행의 구역 수준 오류는 단독 제외 0, joint 1이다. typed 점 FN(9→10/18)은 점 토큰 점수라 구역 최대 점수와 다른 지표다.
- fold 안 순위(임계값 없는 AUROC, 같은 held 행, 단독 제외 → joint)와 감독 유형별 평균 logit 이동:
  - fold 1 (u, z 등 제외; 학습 약한 양성 실물 2개뿐): AUROC .881 → .881. 약한 양성 logit 1.06 → 0.38, 오류 5 → 6.
  - fold 2: AUROC .833 → .958. 정상 −0.45 → −0.85.
  - fold 3 (c와 ㄴ 함께 제외): AUROC .917 → .931. 정상 −0.25 → +0.30, 클릭 1.77 → 2.40. 26행 중 22행은 상승하고 4행은 하락했다. 정상·클릭 두 감독군의 평균 logit은 모두 상승했다. 이는 개별 행 전체의 공통 이동이나 순위 불변을 뜻하지 않는다. 절편은 −2.461로 fold 중 가장 높다(다른 fold −2.88 ~ −3.54, 단독 제외 a/b/c/ㄴ −2.48 ~ −2.89). 단, 절편은 coef·중심화와 함께 봐야 한다.
  - fold 4 (b, v 제외): AUROC .82 → .67. 순위가 실제로 나빠졌다.

## 2. 진단 (인과 결론 아님)

- 구현 오류: 재생·분할·누수·수렴 검사를 통과했고, 학습식이 기존과 같으며, fold마다 변화 방향이 다르다(fold 2는 개선). 이 검사들만으로 구현 오류를 배제할 수 없다. fold별 방향 차이도 구현 오류의 반증은 아니다. 같은 코드의 단독 제외 재현은 미검증이다.
- FP 증가(+12.50%p)는 fold 3·4의 img 정상 카드에 몰려 있다. fold 3의 AUROC는 .917→.931이고 정상·클릭 감독군 평균 logit이 상승했다(개별 22행 상승·4행 하락). 순위 불변이나 전체 점수의 순수 offset 이동은 확인하지 않았다. 원인은 다음 경쟁 설명으로 남는다.
  - H1 추가 정상 제외 민감 패턴: 같은 img 대상에서 정상 카드 h의 출처와 무관하게 추가 공동 제외 후 FP가 증가한다. 양성 점수·계수 분해를 검사하지 않으므로 전체 offset 변화라고 확정하지 않는다.
  - H2 출처와 연관된 공동 제외 민감 패턴(지름길 원인 미확인): img 출처의 학습 자료에서 정상(b, c, ㄴ) 대 양성(ㅋ 클릭) 균형이 바뀔 때만 img 정상에서 FP가 오른다. 저해상도 이미지의 외형을 정상 신호로 일부 쓰고 있을 가능성이다.
  - H3 상호 카드 쌍 민감 패턴: c와 ㄴ의 상호 공동 제외에서 기준선 대비 추가 FP가 생기고 b 공동 제외에서는 거의 변하지 않는다. ㄴ은 기존에도 FP 4/9이므로 정상 인식을 상실한 것으로 해석하지 않는다. 출처와 무관한 원인이라고 확정하지 않는다.
- FN 증가(+7.84%p)는 Screenshot 약한 양성에 몰려 있고, fold 1에서 학습 약한 양성 실물이 2개뿐인 구성과 겹친다. 그러나 약한 양성은 출처·라벨 방식(카드 전체 구역)·실물이 모두 묶여 있어 현재 자료로는 원인을 식별할 수 없다(미확인).
- 기존 진단과의 관계:
  - 101432 공간 감사는 정상 초과 반응의 경계·위치 집중을 지지하지 않았다. 출처나 offset 설명과 충돌하지 않는다.
  - 103800은 분할 가능성만 검증했다. 이번 결과가 그 분할을 무효로 만들지 않는다.
  - 063443의 frozen 삭제는 재학습이 아니라서, 학습 구성을 바꿨을 때의 offset 변화는 본 적이 없다.
- 미확인: 표현력과 선형 head의 한계, 촬영 조건과 인쇄 디자인의 분리, 약한 양성 FN의 원인, 일반화. 앞면 정상 카드는 4장(9구역)뿐이고 fold들은 학습 자료를 공유한다. 모든 수치는 반복 개발 자료의 기술 통계다.

## 3. 다음 실험 (정확히 1개): 정상 카드 쌍 공동 제외 재학습 진단

goal: img 정상 카드의 FP 증가가 H1(구성), H2(출처 조건), H3(카드 쌍) 중 어느 형태와 맞는지, 함께 제외하는 정상 카드 하나만 바꿔 구별한다. 같은 코드로 단독 제외 head를 재현하는 구현 대조도 함께 한다.

변경 변수 하나: 대상 정상 카드 g와 함께 학습에서 빼는 정상 카드 h의 정체(동일한 정상 정답 수 9구역을 가진 카드 중 하나). 같은 물리적 카드 크기나 원본 픽셀 해상도를 뜻하지 않는다.
- 대상 T = {a, b, c, ㄴ} (앞면 9구역 정상 카드 전부). 각 g에 대해 h ∈ T\{g}마다 1회 학습한다(12회). 양성 행과 나머지 정상은 전부 유지하므로 학습 양성 구성은 단독 제외와 같다.
- 대조(재현) 4회: g만 제외하고 다시 학습해 저장된 단독 제외 head(093945 local-heads.pt의 front g)의 g 9구역 점수와 비교한다. 모든 g의 9구역에서 최대 확률 절대차 ≤1e-4이고 threshold 0.5 판정이 저장값과 모두 같으면 이 대조의 수치 재현을 통과한 것으로 본다. 구현 전체의 동일성을 증명하지 않는다. 4개 재현 대조를 먼저 모두 확인하고, 하나라도 실패하면 공동 제외 fit을 시작하지 않으며 실험을 failed로 기록하고 해석하지 않는다. 자동 재시도하지 않는다.
- 고정: 특징 캐시 typed-training-tokens.pt(features·masks와 앞면 point_tokens는 legacy와 동일 확인; 수정된 뒷면 point_tokens는 typed 정본 보존), 153행 중 앞면 전 행, 사람 점 토큰, 실물·클래스 균형 가중치, max_bound, L2=1, threshold 0.5, fit_detail_head. 뒷면은 학습하지 않는다.
- 평가 단위: g의 정상 9구역 최대 점수(FP 수, 평균 최대 logit). 다른 행은 평가에 쓰지 않는다.
- 출처 속성은 사전 고정이다(정답이 아닌 파일 메타데이터): img = 파일명이 img로 시작(b, c, ㄴ), screenshot = a.

경쟁 설명별 예상 결과 (기준은 단독 제외 저장값 FP_L(g): a 2, b 1, c 1, ㄴ 4):
- H1: 세 img 대상 각각에서 h가 a든 img든 FP 증가가 비슷하다.
- H2: img 대상은 같은 출처 h(다른 img 카드)를 뺄 때만 FP·logit이 오르고, h=a일 때는 거의 그대로다. a 대상은 어떤 img h를 빼도 그대로다.
- H3: c는 h=ㄴ일 때, ㄴ은 h=c일 때 기준선 대비 추가 FP가 생기고, 같은 출처의 b를 뺄 때는 거의 변하지 않는다. 한 방향만 반응하면 아래의 상호 H3 판정으로는 미구별이다.

사전 판정 규칙 (결과를 보기 전 고정, 진단용, 채택 기준 아님):
- Δ(g,h) = FP(g,h) − FP_L(g). 같은 출처 평균 Δ_same(g)는 img h 2개의 평균, Δ_cross(g)=Δ(g,a). L(g,h)는 g의 정상9구역 각각의 valid_mask 내부 최대 pre-sigmoid logit의 평균이며 L_L(g)는 저장된 단독 제외 구역 최대 확률의 logit 평균이다. δL(g,h)=L(g,h)−L_L(g), δL_same은 같은 출처 h 2개의 평균, δL_cross=δL(g,a)로 정의한다. 사용 값은 유한해야 하며 임의 clipping으로 판정하지 않는다.
- H2 일치: img 대상 3개 중 2개 이상에서 Δ_same≥2, |Δ_cross|≤1, Δ_same−Δ_cross≥2, δL_same≥0.3, δL_same−δL_cross≥0.3을 모두 만족한다. 동시에 a 대상의 모든 h에서 |Δ(a,h)|≤1이다. 출처 연관 패턴일 뿐 해상도·감독 방식·인쇄·촬영자 중 원인을 식별하지 않는다.
- H1 일치: img 대상 3개 중 2개 이상에서 Δ_cross≥2이고 같은 출처 h 2개 각각에 대해 |Δ(g,h)−Δ_cross|≤1이다. 평균으로 서로 반대인 쌍 효과를 상쇄하지 않는다. 이 판정은 img 대상의 추가 정상 제외 민감 패턴이며 전체 점수의 순수 offset 이동이나 보정법 채택 근거가 아니다.
- H3 일치: FP(c,ㄴ)−FP(c,b)≥3, FP(ㄴ,c)−FP(ㄴ,b)≥3, Δ(c,ㄴ)≥2, Δ(ㄴ,c)≥2, |Δ(c,b)|≤1, |Δ(ㄴ,b)|≤1을 모두 만족한다. 이는 상호 쌍 민감 패턴의 기술적 판정이다.
- 둘 이상 동시 충족이나 모두 미충족이면 "미구별"로 기록한다. 각 원시 조건의 true/false도 보존한다. 미구별·미충족은 가설 반증이나 효과 없음이 아니며, 재현 통과 여부와 혼동하지 않는다. 미구별이면 현재 head·threshold·정책을 유지하고 추가 실행 없이 부족한 대조를 인계한다. 기준을 사후 조정하지 않는다.
- 표본 한계: 대상 카드 4장, 각 9구역의 기술 통계다. 유의성·일반화 주장은 하지 않는다.

이 실험이 다음 판단을 바꾸는 방식:
- H2 일치 → 출처 연관성을 교란된 기술 결과로 기록한다. 추가 자료 확보나 해상도 대조는 후속 검토 후보로만 제안하며, 이 결과만으로 수집·라벨 요청·입력 변경을 시작하지 않는다.
- H1 일치 → 추가 정상 제외 민감성으로 기록한다. 가중치·offset 변경은 후속 단일 변수 후보로 검토하되 순수 offset 효과라고 가정하거나 현재 평가 자료로 threshold를 조정하지 않는다.
- H3 일치 → 상호 쌍 민감성을 기록하고 일반적인 수정법 채택은 보류한다. 카드 다양성 보강은 별도 승인할 후속 후보이며 자동으로 실행하지 않는다.
- 재현 실패 → 성능 해석을 중단하고 학습 경로 차이부터 조사한다.

공통 실행기 출력 계약:
- experiment_kind=diagnostic.
- 주 평가 147행 점수는 122011 fold-heads.pt의 maps를 재생해 제출한다(재학습 아님, 2e-5 일치 검사). reference_result=artifacts/experiments/20261025T122011-647b0e9c/result.json.
- acceptance는 기준선 재생 동일성 확인용으로 max_fn 16, max_fp 18, no_new_errors true, require_actual_point_guard false이다. required_cohorts는 122011 plan의 11개·동일 순서·원래 reference_result·동일 acceptance를 그대로 선언한다. worker는 122011 observations의 각 cohort rows/scores/point_ids/point_scores를 동일하게 제출하고, 새 CARD_CONDITION_EXPERIMENT_REFERENCE의 rows/point_ids와 대조한다. legacy51과 typed51을 서로 대체하지 않는다. 주 평가 maps 최대값은 122011 scores와 2e-5 이내여야 하고 threshold0.5 판정도 같아야 한다. reference_result가 122011이므로 러너는 각 cohort 비교 기준점수를 122011 scores/point_scores로 갱신하지만 기존 절대 FN/FP 기준을 보존한다. 정확히 재생하면 primary_acceptance_passed=true, 전체 acceptance_passed=false(기존 11개 모두 절대 기준 미달)가 예상된다. primary 통과는 기준선 재생일 뿐 새 진단 head의 품질 통과가 아니다. 진단 결과는 diagnostic_evidence와 diagnostics.json에 둔다. diagnostic_evidence는 dict이며 len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))≤4000을 검사한다. 모델·threshold 채택은 없다.

누수 보호: 각 학습에서 g와 h의 모든 행을 제외하고 원본 SHA·디코딩 해시 교차가 없음을 확인한다. 훈련 전용 6행(ff69)은 g, h와 겹치지 않음을 확인한다. 평가에는 g의 행만 쓴다. 단독 제외 저장값과 joint 기준선은 읽기만 하며 덮어쓰지 않는다.

실행 의존:
- (1) Codex 계약 검토: 사전 규칙·공통 기록·범위 수정 후 승인. 이번 단계에서 학습·추론·실험은 실행하지 않았다.
- (2) 구조 규칙: 해결됨. 2026-10-25 사용자 채팅 승인: "surface-normal-coexclusion-20261025 task에 한해 C와 같은 계산(라이브러리 내부 프레임 제외, LBFGS closure 1회)을 승인한다." 이 task에만 적용하며 다른 작업으로 확대하지 않는다. worker 정의 함수 기준 전이는 여전히 4회 이하여야 한다.
- (3) 구현 worktree: 위 branch를 승인된 최종 문서 통합 main에서 생성한다. 실제 경로와 시작 SHA는 세션 인계에만 기록한다. 소스 기준 base_sha는 위 92a85e8이며 그 뒤 통합은 이 계약 문서뿐이다.
- (4) 구현 후 Codex 검토·관련 합성 검사 통과와 실제 실행 승인을 확인한 뒤 기본 checkout에서만 실행한다.

## 4. 승인한 구현 계약 (미착수)

allowed_files:
- tools/experiments/surface-normal-coexclusion-20261025/worker.py (신규 정본)
- tools/experiments/surface-normal-coexclusion-20261025/plan.json (신규)
- tests/test_normal_coexclusion_worker.py (신규, 합성 fit만)
- 이 task 문서
- ignored: artifacts/surface-normal-coexclusion-20261025/worker.py(실행 미러, SHA 동일), artifacts/surface-normal-coexclusion-contract-20261025/index.html(이번 진단 보고), CARD_CONDITION_EXPERIMENT_DIR/{observations.json,diagnostics.json,index.html,images/,diagnostic-heads.pt}(새 실험 기록 폴더 내부 worker 산출물만)

forbidden_files: card_condition/* 전부, 기존 실험 폴더·캐시·heads, 라벨·사람 정답, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, 운영 Gemini 경로, 다른 task 소유 파일.

structure (계획):
- worker 함수 ≤7개(sha, pair_plan, fit_excluding, target_scores, replay_baseline, render, finish 예정).
- 학습 경로: 모듈 guard는 함수로 세지 않는다. fit_excluding → fit_detail_head → closure → detail_bag_loss → point_bag_loss = 4전이이다. fit_excluding을 다른 worker 함수 안에서 호출하면 5전이가 되므로 모듈 guard에서 직접 호출한다. 이 task에 승인된 LBFGS 내부 프레임 제외 예외만 적용한다. worker 전체 정의 함수는 중첩·메서드 포함 7개 이하이며 구현 인계 때 실제 AST와 파일 경계를 넘는 호출 경로를 대조한다.

checks:
- 합성 테스트: 쌍 목록 12개와 재현 4개 생성, g·h 제외 누수 거절, 평가 행이 g만인지, Δ 판정 규칙의 경계값(정확히 2, 1, 3)과 logit 0.3, 각 경계 바로 아래·위, 중복 충족·전부 미충족을 검사한다.
- 계획 정적 검사: 러너 검사를 읽기 전용으로 재현하고, required_cohorts 11개 보존을 확인한다.
- 실행 후 확인: 재현 4개 최대 절대차·판정 동일성, fit16개 수렴, 판정 규칙 결과와 원시 FP·logit 표, 주 평가·11개 cohort 재생 동일성. 12개 방향쌍은 학습 집합으로는 6개뿐이며 독립 반복으로 집계하지 않는다. 합성 검사에는 H2의 cross 악화 반례와 H3의 기존 FP 회복 반례를 포함한다.

HTML 산출물:
- 이번 진단: artifacts/surface-normal-coexclusion-contract-20261025/index.html (Claude worktree, ignored, 새 추론 없음, 기존 기록 집계만)
- 실행 후: 실험 폴더 index.html. g별 사진 위에 9구역 사람 정답(정상)과 h별 점수를 표시한다. FP 분모 9, 단독 제외 대비 변화도 넣는다. 반복 개발 자료이며 독립 시험이 아님을 표시한다.

risks:
- 정상 카드가 4장뿐이라 판정 규칙의 결과가 한두 구역에 좌우된다.
- 출처 속성이 해상도·인쇄·촬영자를 함께 묶고 있어, H2가 지지돼도 "해상도" 하나로 특정할 수 없다.
- 단독 제외 head 재현이 1e-4를 넘으면 실험 전체를 해석할 수 없다.
- fit 16회는 같은 학습 자료를 크게 공유한다.

rollback: Codex가 main에 통합한 이 계약의 문서 커밋들을 역순으로 revert한다(정확한 SHA는 최종 인계 기록). 구현 후에는 tools·tests 신규 파일 revert, 실험 폴더는 기록으로 보존한다. 모델·라벨·기준 변경 없음. 진척 30/100, F1·E2·C3 pending 유지.

## Codex 계약 검토에서 추가한 사전 제한

- 새 plan에 gemini_calls_allowed=0, independent=false, production_adopted=false를 고정한다. code_changes는 artifacts/surface-normal-coexclusion-20261025/worker.py, baseline=null로 선언하고 tools 정본과 byte SHA 일치를 실행 전에 확인한다. 과거 snapshot·worker는 덮어쓰지 않는다.
- 원본·디코딩 해시 교차는 모든 retained front 학습 행과 g+h 전체 제외 집합 사이에서 검사한다. 제외되는 h를 평가하지 않더라도 학습에서 그 실물/사진이 다른 ID로 남는 것을 거절한다. 훈련 전용 ff69 6행은 서로 다른 원본 사진 2개를 포함하므로 행 순서·ID·실물·target·box·point_tokens와 원본/디코딩 SHA를 정본에서 대조한다.
- 단독 제외 재현은 train88행(정상35·양성53), 공동 제외는 train79행(정상26·양성53)이다. 양성53행(약한33·클릭20), 토큰·행 순서와 가중치 식을 보존한다. 추가 제외 h에 의해 정상 가중치가 재분배되는 것은 고정 가중치 식의 결과이지 별도 손실 변경이 아니다.
- 원본 크기: a958×1330, b388×500, c428×585, ㄴ675×930. 카드 영역 픽셀 크기도 각각 약877×1237,350×478,401×560,655×899로 다르다. 출처와 크기·디자인·기존 FP 난이도가 교란돼 있으며 정상 대조 Screenshot은 a 한 장뿐이다. 2/9(22.22%p),3/9(33.33%p),logit0.3은 사전 기술 분류 문턱이고 통계 검정/동등성 한계로 해석하지 않는다.
- 새 실험에서 fit/재현/유한성/출처/분리/재생 검사 중 하나라도 실패하면 failed로 종료하고 진단을 해석하지 않는다. threshold나 규칙을 고쳐 같은 실험을 자동 재시도하지 않는다.
- Codex가 2026-10-25 수정 반영본을 재검토해 계약을 승인했다. 수정 전 보고서의 통합 보류는 이 수정본에 대해서 해소됐다. 구현·실제 학습·실험은 아직 수행하지 않았다. 구현 브랜치와 worktree 생성 여부·시작 SHA는 최종 인계 기록을 따른다.

## Codex 승인 및 후속 구현 인계 (2026-10-25)

- 검토한 원본 SHA: 973456b6a3422dab29046d67268ce721d8a5a562 → 332f2646498db64a69361704e61702bd11addd4f. 검토 후 문서 수정은 Codex가 이번에만 대신 수행했다.
- H1/H2/H3 수치 문턱과 미구별·재현 실패 시 행동은 위 본문으로 고정했다. 새 정상 쌍 fit 결과를 보기 전에 확정했으며, 결과를 본 뒤 조정하지 않는다.
- 구현 owner는 Claude이며 allowed_files는 위 정확한 목록뿐이다. 기본 checkout의 실자료·환경·비밀 설정을 구현 worktree와 공유하거나 그곳에서 실제 모델 계산을 하지 않는다. 환경 생성·설치는 이번 계약 통합에서 수행하지 않았다.
- 실행 담당: Codex, 기본 checkout. 구현 검토와 실제 실행 승인 후 사용할 명령 형식은 아래와 같다. 아래 명령은 이번에 실행하지 않았다.

```sh
# 파일 복사는 ./develop -- 안에서 수행하고, 기존 미러가 있으면 임의 덮어쓰지 않는다.
./develop -- cp tools/experiments/surface-normal-coexclusion-20261025/worker.py artifacts/surface-normal-coexclusion-20261025/worker.py
shasum -a 256 tools/experiments/surface-normal-coexclusion-20261025/worker.py artifacts/surface-normal-coexclusion-20261025/worker.py
./experiment --plan tools/experiments/surface-normal-coexclusion-20261025/plan.json -- .venv/bin/python artifacts/surface-normal-coexclusion-20261025/worker.py
```

- 실행 미러의 부모 폴더는 복사 전에 생성한다. 실행 전에 두 worker SHA256이 같아야 한다.
- 공통 실행기 전체 status/acceptance와 별개로 진단 자체의 재현·수렴·원시표·규칙 충족을 보고한다. 기준선 primary 통과를 진단 head 품질 통과라고 보고하지 않는다.
- HTML을 생성·내용 대조·열기 요청하고 열기/렌더 확인을 구분한다. 현재 고정 진척은30/100, F1·E2·C3 pending이며 이 계약 통합으로 점수를 올리지 않는다.
