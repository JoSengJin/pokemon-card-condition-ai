# 정상 bag 계수2 단일 후보 계약 — 2026-11-09

- task_id: surface-normal-bag-weight2-20261109
- owner: 현재 메인 Codex 단독, 기본 checkout main. 병렬 에이전트/별도 구현 세션 없음.
- status: integrated / completed / quality_failed / not_adopted
- base_sha: a3beb55860f8d3f9e559d84b4c5f4d170d14ab4d
- approval: α0 실제 결과 뒤 사용자가 정상 bag 손실 가중치만 높이는 후보 제안에 “진행해”로 구현·검증을 승인했다. 이번 고정값1→2 후보1회이며 탐색·재시도·외부AI 호출 승인 아님.
- goal: α0의 출력·threshold0.5·라벨·분할·기준을 유지하며 정상 bag 계수만1→2로 바꾼 격리 후보를 합성 검증하고 공통 실행기로1회 평가한다.
- allowed_files: 신규 tools/experiments/surface-normal-bag-weight2-20261109/{objective.py,worker.py,armijo_direction.py,metrics.py,checks.py,checks_components.py}, 이 task, 신규 docs/collaboration/reports/surface-normal-bag-weight2-20261109.md.
- ignored_outputs: artifacts/surface-normal-bag-weight2-20261109/의 runtime mirror4개·plan.json·preflight.json·합성검사로그/JSON·console.log·analysis.json·postflight.json·report.html·comparison.csv·opening-status.txt, 공통실행기의 신규 artifacts/experiments/<ID>/ 기록/snapshot/model/trace/gradient.
- forbidden_files: 기존 소스·모델·사진·캐시·라벨·기록·평가 기준·다른 worktree/소유파일·비소유.claude/·기존 초안/보고서. 삭제·덮어쓰기 없음.
- scientific_change: objective의 정상 bag 기여에만 normal_bag_weight=2.0을 적용. L=2N+D+G+L2, alpha0 유지. mass·center·class balance·pair 가중/쌍선택·L2를 재정규화하지 않는다. 기록된 normal_bag 성분도 정확히2N이다. 기존 B+G와 raw scale이 달라지는 것이 의도한 단일 변수다.
- fixed_contract: maskedmax→sigmoid·threshold0.5·동일1776행(결함370/정상1406)·mask/fold/seed/CPU백본·정답·bag 수식·전체쌍LME·초기화·정규화mass·L2=1·optimizer 유지. 최종gradient≤1e-5/내부1e-7,1000반복·초기포함1250평가. 산술 성분은 연결된0이며 cosine=None.
- structure: objective 함수3→3, worker0→0, direction1→1, metrics4→4, checks3→3, checks_components6→6. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss 최대4전이, direction2전이. 테스트 wrapper/동적교체도 검토.
- checks: 같은theta에서 α0 대비 total차=N, gradient차=gradN; 정상성분2배·나머지성분 동일; 독립수식14·중심유한차분24·합성fit3·385D0산술·성분합/최종theta/mass해시·초기수렴·거절trial제외·중복/예산·덮어쓰기거절·출력식/평가블록동일·AST 함수수·diff검사. 사진/실제캐시를 합성fixture로 쓰지 않는다.
- hypothesis_id: surface-frozen-global-lme-normal-bag-weight2-20261109
- rationale: α0에서는 정상bag loss가5fold 모두 증가했고 bag합↔순위합이 모두음수였다. 정상bag 계수증가로 해당훈련목표압력을높여 정상구역 경계초과를 줄이는지 시험한다. 최종점 gradient는 국소근거로서 OOF인과/개선보장 아님. 2는 결과전 정한 단일배수이며 탐색최적값 아님.
- controls: 직접 α0=artifacts/experiments/20261108T215307-941b3aaa/ (FN57 FP167 AUC0.931924954826804); 최신50:50=20261108T145825-59681012 (FN51 FP179 AUC0.9309272999884665). 품질 reference=20261106T210640-0eb1bdc0 (FN67 FP201 AUC0.9166506478028527). 동일분모만비교.
- preregistered_gate: FN≤67/370 AND FP≤112/1406 AND 원래 AUC대비증가≥0.03 AND paired photo bootstrap95%하한>0 AND 수렴·근거유효 모두통과. FP≥167이면 의도한오탐감소 방향 반증. FP감소해도 게이트미달이면미채택. 결과후기준변경없음.
- experiment: 원래reference·최신2대조·동결입력SHA·검증소스SHA·CPU·신규mirror4개 baseline=null을 최종계획에 고정. ./experiment --plan <plan> -- .venv/bin/python <mirror worker> 단1회. PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1. 자동review/Gemini/Codex0. 실패/중단/불명이어도재시도없음.
- reporting: 반환후 실제record·development-cycle pointer/해당handoff대조, 학습5fold 행/mask/target/mass·성분합/최종theta·계수제거 gradient·동일평가 FN/FP/%p/AUC비교. OOF오류ID를학습선별/가중/라벨수정에사용안함. 반복CV는독립일반화아님. 진척78/100 v1.13 유지.
- HTML: artifacts/surface-normal-bag-weight2-20261109/report.html에 실제사진·구역별사람정답/저장점수·분모/%p/대조군/근거/리스크/롤백. 기존 file: 정책거절을우회·재시도하지않고정적대조/열기·렌더미확인기록.
- risks: 정상억제로 FN증가·AUC악화·수렴부담 가능. 단일seed개발CV이며선형특징한계/개별patch원인미확인. 가중gradient증가자체를개선으로부르지않음.
- rollback: 격리후보·운영미변경. 미채택시기존운영경로유지하고증거보존. 통합코드복원필요시현재메인에서 ./develop -- git revert <후보SHA> 후일반push. force/reset/실험증거삭제없음.
- handoff: 구현/검사/단일실행후 실제SHA·결과·HTML정적검증/렌더미확인·미검증을갱신한다. 기존 다른세션 checkout은정리하지않는다.

## 구현·합성 확인

신규 Python6개만 추가했다. objective는 정상bag 기여1→2 한 변수, worker는가설ID만 변경, direction/metrics는α0와바이트동일. 독립수식14·유한차분24·합성fit3 및 총19 PASS그룹 통과. 독립loss/gradient최대오차8.882e-16, 함수수6/0/4/3/3/1·호출4전이 유지. 컴파일 통과. 근거: artifacts/surface-normal-bag-weight2-20261109/{checks.log,checks-components.log,synthetic-checks.json}. 실제실험은아직0회이며이후최종계획과소스SHA를고정해1회만실행한다.

## 실제 실행 인계

소스67847d7716ba1cc54613aa090cb5e0dccad5a179·계획SHA fb61212fc89b2ed623ccfa0123710966b8a818f024d7276a269390af95db0a16을 동결했다. 공통기록 artifacts/experiments/20261109T093529-05b9f35a/record.json은 completed/exit0. 1회·재시도0·추가소스수정0·탐색0·자동후속0. FN105/370 FP92/1406 AUC0.9305313136749837, α0 대비 FN+48(+12.9730%p) FP−75(−5.3343%p) AUC−0.001393641. 누락·AUC 기준미달로 미채택. 5fold 내부gradient1e-7·188입력·204사진·실제학습행/mass/target/mask·성분합/최종theta검증통과. 근거는 결과보고서와 analysis/postflight/HTML/CSV. HTML 정적검증만 수행, 기존 정책차단 때문에 열기·렌더미확인. 진척78/100유지. 기존모델/자료·다른worktree/소유파일·.claude/보존.
