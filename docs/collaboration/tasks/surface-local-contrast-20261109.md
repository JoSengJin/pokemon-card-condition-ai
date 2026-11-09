# 국소 대비 특징 단일 가설 — 2026-11-09

- task_id: surface-local-contrast-20261109
- owner: 현재 메인 Codex 단독, 기본 checkout main; 병렬 구현 없음.
- status: implementing
- base_sha: a888aa758079c56fe376fc995ef0ba4d598792f9
- approval: 사용자가 국소 대비 특징 추가 단일 가설 설명 뒤 “진행해”로 구현·검증·공통 실행기 단일 실험을 승인.
- goal: 원본384차원과 주변3×3 유효토큰 평균에서의 절대잔차384차원을 연결한 입력만 바꾸어 동일1776구역 개발CV의 순위 분리력을 검증.
- allowed_files: 신규 tools/experiments/surface-local-contrast-20261109/{worker.py,features.py,checks.py}, 이 task, docs/collaboration/reports/surface-local-contrast-20261109.md.
- ignored_outputs: artifacts/surface-local-contrast-20261109/{plan.json,worker.py,features.py,objective.py,metrics.py,armijo_direction.py,checks.log,preflight.json,console.log,analysis.json,postflight.json,report.html,comparison.csv,opening-status.txt}, 공통 실행기 신규 artifacts/experiments/<ID>/.
- forbidden_files: 기존 모델·worker·소스·사진·라벨·캐시·과거기록·기준·다른 worktree·비소유 .claude/. 기존 파일 덮어쓰기/삭제 없음.
- scientific_change: x → concat(x,abs(x-valid_local_mean3x3)). 32×32 patch grid, 자기 자신 포함, grid 밖과 mask=false는 이웃 평균 제외. 원본384차원 그대로 보존, invalid 위치의 추가특징은0. 추가 정규화/스케일 조정 없음. 768차원 선형 head; 백본 동결.
- control: alpha0/normal weight1/defect weight1, artifacts/experiments/20261108T215307-941b3aaa/ (FN57/370 FP167/1406 AUC0.931924954826804). 같은 α0 objective/direction와 기존 metrics를 그대로 호출. 최신 정상계수2는 대조 학습식으로 사용하지 않음.
- fixed_contract: N+D+G+L2, α0·L2=1·tau0.1·mass/center·maskedmax/sigmoid·threshold0.5·라벨/마스크/1776행·사진그룹fold·seed20261031·CPU·영초기화·1000반복/1250평가·gradient1e-5/내부1e-7 모두 불변. 차원 증가에 따른 파라미터수/정규화 기하 변화는 입력표현 변경의 일부로 기록.
- hypothesis_id: surface-frozen-global-lme-local-contrast-20261109
- rationale: 계수2는α0 대비FP167→92/FN57→105/AUC하락. 순위 손실계수 조정 중단. 주변 대비 절대잔차가 추가 분리 정보를 제공할 수 있다는 가설이며 선형 특징 한계/조명원인은 증명되지 않음. 과거 crop 평균 제거는 FN증가: 원본을 제거하지 않고 공간적3×3 절대잔차를 추가.
- preregistered_gate: 직접α0 대비AUC차>0 AND paired photo bootstrap95%하한>0을 표현 개선 근거로 요구. 운영채택은 기존 AND 기준 FN≤67/370 AND FP≤112/1406 AND 원래 reference AUC0.9166506478028527 대비증가≥0.03 AND 원래대비paired95%하한>0 AND 5fold수렴·근거유효를 모두 요구. 결과뒤 기준변경 없음.
- experiment: ./experiment --plan artifacts/surface-local-contrast-20261109/plan.json -- .venv/bin/python artifacts/surface-local-contrast-20261109/worker.py 단1회. PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1, 외부AI/자동review0. 실패/중단/불명 자동재시도0. 원래reference 유지, α0별도 frozen OOF 대조. 독립평가 봉인자료 접근/학습편입 없음.
- structure: 신규 features1함수,worker0함수,checks≤7함수. 특징경로 worker→augment_local_contrast 1전이; 학습 worker→fit_detail_head→loss_and_grad→detail_bag_loss→point_bag_loss 최대4전이, direction2전이. 기존 objective3/direction1/metrics4 불변.
- checks: 독립 loop oracle과 masked3×3·경계·padding·행분리·상수/단일유효·원본보존·비유한거절·768D합성fit/기존objective일치·AST/diff·입력/소스SHA·사진/그룹train/eval분리. 합성검증을 성능으로 표시하지 않음.
- reporting: 실제record/status/gates, 같은분모FN/FP/%p/AUC와직접대조CI, 768계수/훈련행/mass/mask/target/최종성분합 대조. 새 OOF 오류로학습 선별/가중하지 않음. 진척78/100 v1.13 유지(보고전 고정기준 재확인).
- HTML: artifacts/surface-local-contrast-20261109/report.html에 사진 위구역별사람정답/대조/후보점수·누락/오탐분모·%p·개발CV표시·변경/검증/리스크/롤백. 로컬열기 시도와렌더를별도기록. 외부서버/터널/업로드 없음.
- risks: 인쇄/반사 대비 강조로오탐증가, 768차원과메모리/수렴부담 증가. 개발CV 반복이며 독립일반화미확인. 실패시추가설정탐색 없음.
- rollback: 격리후보이며운영모델/fallback불변; 미채택시근거보존. 코드복원필요시본작업SHA만 ./develop -- git revert <SHA> 후일반push. 과거snapshot덮어쓰기/force/reset없음.
- handoff: 구현·검사·실험·HTML 및 SHA를 완료후 갱신. 기존다른세션 worktree/증거 보존; 이번작업 신규 worktree 없음.


## 실행 자원 보완 (첫 실행 후, 성능 결과 없음)

첫 공통기록20261109T103853-3fa5c0b6은 interrupted/-15. 특징 변환1776×1024×768 완료 후 첫fold 로그 전에16GiB RAM/시스템swap44272.75MiB 확인, 사용자 Mac 부담을 줄이기 위해 Codex가 worker에SIGTERM. OOM/성능실패로 추정하지 않는다. 기존 코드와 기록은 공통 snapshot/최초 runtime mirror에 보존.

사용자의 “진행해” 구현·검증 범위에서 입력/가설/손실/기준을 바꾸지 않고 메모리 구현만 보완한다. 앞선 계약의 단1회/재시도0은 Codex가 정한 실행계획이며 사용자가 별도로 요구한 제한이 아니다. 성능결과가 없는 자원중단을 해결하기 위한 추가1회 시도만 허용(총시도2회), 자동반복/설정탐색 없음. 수치 판정 기준은 불변.

추가 allowed_files: 같은폴더 objective.py(기존α0 수식 그대로, dtype확장·center빼기만8bag 청크), streamed_linear.py(custom autograd forward/backward3함수), checks_streamed.py(≤7함수). 기존worker/feature/check는 유지. 새 runtime artifacts/surface-local-contrast-streamed-20261109/{worker.py,features.py,objective.py,streamed_linear.py,armijo_direction.py,metrics.py,plan.json,preflight.json,checks.log,console.log,postflight.json,analysis.json,report.html,comparison.csv,opening-status.txt}; 최종보고는 이 경로 사용.

float64 투영/gradient를 청크별로 계산하고 원본float32특징을 저장한다. 원래와 같은theta·center에서 logits/전체loss/gradient/성분gradient·합성fit을 대조하며 합계순서의 부동소수 오차만 허용한다. subset/center 요약의 dtype은 기존float64와 동일. 전체float64특징 복제·positive mass전체재복제 제거; 수식·mass·center정의·dtype·출력·최대반복·정지기준불변. 프로젝트호출 depth: worker→fit→loss_and_grad→StreamedLinear.apply→forward/backward의 custom autograd 경로는 framework 경계를포함4전이. 기존bag경로4전이. 새objective3함수/streamed2메서드.
