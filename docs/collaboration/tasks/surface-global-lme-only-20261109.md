# surface-global-lme-only-20261109 — α=0 구현·합성 검증 계약

## 배정과 권한

- task_id: surface-global-lme-only-20261109
- owner: 사용자가 별도 대화에서 시작할 구현 세션(모델명과 무관). 사용자에게 전달하는 계약이며 이 문서 생성만으로 실행 세션을 시작하지 않는다.
- status: assigned
- base_sha: e52e4e7d669d553b549daef7b94e8226ed142cfa (검증된 과학/실행 소스 기준)
- checkout_base: 이 계약과 전달 프롬프트를 처음 추가한 커밋. `git log -1 --diff-filter=A --format=%H -- docs/collaboration/prompts/surface-global-lme-only-20261109.md`로 유일하게 확인한다. 실제 전체 SHA는 전달 시 별도로 제공한다. base_sha 이후 checkout_base까지는 두 배정 문서만 추가하며 Python 소스 차이는0이다.
- branch: codex/surface-global-lme-only-20261109
- worktree: 위 브랜치의 신규 전용 checkout. 실제 로컬 절대경로는 커밋하지 않고 현재 메인 세션이 사용자에게 별도로 전달한다. 기본 checkout 및 기존 타인 worktree를 사용하지 않는다.
- main_owner: 이 계약을 만든 현재 Codex 대화. 실제 학습/모델 비교/사진 추론/라벨 기록/모델 채택/main 통합/원격 push는 이 세션에서만 담당한다. 이 배정은 메인 역할 이양이 아니다.
- approval_scope: α=0 수정안 구현과 합성 fixture 검증, 작업 브랜치 커밋까지만 승인. 실제 실험의 실행 승인은 포함하지 않는다. 구현 결과를 수령한 현재 메인이 검토·통합하고, 실험은 별도 승인·사전 계획이 있을 때 기본 checkout에서만 수행한다.
- goal: 고정 α=0의 전체쌍 LME 단독 목적함수와 그 성분 기록이 일치하고, 기존 출력·학습 보호·평가 계약을 보존함을 데이터 없는 합성 검사로 입증해 ready_for_review 상태의 커밋을 전달한다.

## 파일 소유권

구현 세션 전용 쓰기 허용 파일(모두 신규 격리 경로):

1. `tools/experiments/surface-global-lme-only-20261109/objective.py`
2. `tools/experiments/surface-global-lme-only-20261109/worker.py`
3. `tools/experiments/surface-global-lme-only-20261109/armijo_direction.py`
4. `tools/experiments/surface-global-lme-only-20261109/metrics.py`
5. `tools/experiments/surface-global-lme-only-20261109/checks.py`
6. `tools/experiments/surface-global-lme-only-20261109/checks_components.py`
7. `docs/collaboration/reports/surface-global-lme-only-20261109.md`
8. 이 task 문서의 status/checks 실행 결과/handoff 부분만 갱신·추가 가능. 변수·기준·허용 파일·권한은 임의 변경하지 않는다.

읽기 기준은 `tools/experiments/surface-globalmix-gradient-recording-20261108/`의 동명6개 파일이다. 이 기준과 과거 실험 소스는 수정하지 않는다. `armijo_direction.py`, `metrics.py`는 기준과 바이트 동일하게 신규 경로로 복사한다. 현재 메인은 구현 세션의 tip을 받은 뒤까지 위 소유 파일에 병행 쓰기하지 않는다. 병행하는 다른 작업에도 이 파일들을 배정하지 않는다.

구현 worktree 안의 ignored 산출물만 허용:

- `artifacts/surface-global-lme-only-20261109/checks.log`
- `artifacts/surface-global-lme-only-20261109/checks-components.log`
- `artifacts/surface-global-lme-only-20261109/checks.json`
- `artifacts/surface-global-lme-only-20261109/report.html`
- `artifacts/surface-global-lme-only-20261109/opening-status.txt`
- 합성 fit이 만드는 진단/trace는 자기 worktree 환경의 임시 디렉터리에만 작성한다. 실제 `artifacts/experiments/` 기록은 만들지 않는다.

그 밖의 파일, 특히 기존 `card_condition/`·기존 tools 실험·다른 task/보고서·본 작업 전달 프롬프트·AGENTS/PAIR_CODING·의존성 명세·진척 기준·운영 설정은 쓰기 금지다. `.claude/`, 실제 사진/라벨/모델/캐시/실험 기록, `.backups`, provider 비밀 설정은 보존하고 구현 worktree로 복사·연결하지 않는다. 실자료를 가져와 검증하지 않는다.

## 변경 변수 하나

현재 목적함수는 `B + 0.5*M + 0.5*G`다.

- B: 기존 정상/결함 bag loss + 기존 L2. 전부 유지한다.
- M: 학습fold 모든 결함×정상 쌍의 `softplus(normal_z-defect_z)` 산술평균.
- G: 같은 pair loss 전체를 flatten한 `logsumexp(pair_loss)-log(pair_count)`.
- 수정식: `B + alpha*M + (1-alpha)*G`, **alpha=0.0 고정**, 총 순위계수1 유지.

일반화된 설정 시스템·CLI 인자·비율 탐색·환경변수 override·새 helper/옵션을 추가하지 않는다. 기존 `loss_and_grad` 안에 고정값/식을 적용하는 최소 변경으로 구현한다. G를 결함별 row-LME 평균으로 바꾸지 않는다. 모든 학습쌍은 그대로 입력하며 OOF 오류ID별 선별/추가가중/라벨변경을 하지 않는다.

`objective.py`의 최적화 loss와 `components`의 계수를 반드시 함께 맞춘다. 기존 key/schema5개를 유지하고 `arithmetic_rank=alpha*arithmetic`, `global_pair_lme=(1-alpha)*lme`가 되게 한다. 산술항은 값0·385차원 gradient0의 **연결된 tensor**로 남겨 최종 `autograd.grad`와 합 검증이 동작하게 한다. Python 정수0으로 대체해 graph를 끊거나 성분을 숨기지 않는다. zero-gradient의 cosine은 정의되지 않으므로 비교가 필요하면 unavailable/None으로 표시하고 유사도0 또는1로 꾸미지 않는다.

worker는 기준 파일을 새 경로에 복사한 뒤 가설 식별자만 `surface-frozen-global-region-rank-global-lme-only-20261109`로 바꾼다. 실제 실행·특징 추출·fit/score·학습행 기록·평가 블록은 유지한다. `__main__` worker를 실행하거나 실제 모델로 import 경로를 시험하지 않는다.

## 반드시 유지할 계약

- 출력 masked max→sigmoid, threshold0.5, 출력 API/scorer, mask/사람 정답/분할/평가1776행(결함370/정상1406), 사진·그룹 분리.
- 정상 patch tau0.1 비정규화 LSE, 결함 patch max, LME 암묵온도1, bag mass/사진그룹·class 균형, L2=1, 백본·seed·초기화·CPU fit/float64.
- L-BFGS/Armijo/relative curvature/alignment0.01/중복 trial 차단, 최종 gradient≤1e-5·내부목표1e-7, fit당최대1000반복/초기평가 포함1250평가.
- 최종 채택 상태의 5성분 gradient 기록, 학습행 근거, theta/mask/mass/target 해시·합오차≤1e-10·exclusive-create 보존·추가 목적함수 평가0.
- 향후 품질 게이트 FN≤67/370, FP≤112/1406, **원래 기준** AUC0.9166506478028527 대비 증가≥0.03, paired photo bootstrap 하한>0. 이 기준은 합성 테스트로 충족됐다고 보고할 수 없다.
- 최신 실측 후보는 record `20261108T145825-59681012`: FN51/370,FP179/1406,AUC0.9309272999884665, 운영 미채택. 기록 파일은 기본 checkout 소유이며 구현 세션에 전달하지 않는다. 아래 tracked 보고서의 수치만 근거로 사용한다.

## 합성 검사 완료 조건

1. `checks.py`를 새 경로에서 실행 가능하게 옮기고 기존 방향/history20·Armijo·relative curvature·alignment·중복 trial·1250평가·mask·hardmax 보호 fixture를 유지한다.
2. 목적함수 oracle을 **독립적인 전체쌍 G 단독 식**으로 갱신하고, 값·autograd·중심 유한차분을 대조한다. row-LME로 잘못 구현하면 실패하는 fixture를 포함한다. 단일쌍/동일값/순열/반복쌍 정규화·유한성도 확인한다.
3. α=0은 기존 산술 혼합의 gradient floor `0.5/pair_count`를 제거한다. 이전 floor 기대값을 그대로 두거나, 이를 통과시키려고 epsilon 산술항/clipping/가중치 하한을 추가하지 않는다. 적당한 합성 값에서는 전체쌍의 양의 기여를, 극단값에서는 유한·비음수 gradient를 확인한다. 수치 underflow와 쌍 선별을 혼동하지 않는다.
4. 정상/결함 bag와L2의 값·gradient는 **같은 theta/합성 입력**에서 기준 구현과 같다. 총loss/gradient와 재학습된 계수·점수·전체 trace는 의도적으로 달라질 수 있으므로 기준50:50과 bit동일을 요구하는 이전 테스트는 새 수식 검증으로 교체한다. 유지 대상은 scorer의 식/API이지 학습 후 예측값 동일성이 아니다.
5. 산술 성분의 loss/gradient/norm/bias가 정확히0, G 성분은 전체G의 gradient, 5성분 합은 새 total과≤1e-10, 최종theta 해시는 fit 진단과 일치해야 한다. 초기수렴·실제채택trial·거절trial 제외·기존 sidecar 보존·실패 때 성공sidecar 부재를 검사한다. 성분 추출 때문에 forward/목적함수 평가/optimizer step을 추가하지 않는다.
6. 합성 fit의 수렴·예산·실제 평가 횟수와 trace를 확인한다. fixture가 어렵다고 optimizer/수렴 기준을 완화하지 않는다. 필요하면 합성 fixture의 가정을 명시하고 원인을 보고한다. 실제 데이터·사진·캐시를 쓰지 않는다.
7. worker 가설ID·새 import 경로·기준 평가 블록 동일성·metrics/direction 바이트 동일성을 정적으로 대조한다. 신규 학습행 sidecar 블록을 검증할 때는 AST 해당 블록만 가짜 행으로 실행하며 worker 전체는 실행하지 않는다.
8. `git diff --check`, 허용파일 대조, py_compile, AST 함수수, 파일을 넘는 실제 호출 경로를 확인한다. 테스트 wrapper까지 포함해 제한을 넘기지 않는다.

구조 목표(기준 복사본 대비): objective3→3, worker0→0, direction1→1, metrics4→4, checks3→≤7, checks_components6→≤7. 주요 실행 경로 `worker→fit_detail_head→loss_and_grad→detail_bag_loss→point_bag_loss`4전이, `worker→fit→lbfgs_direction`2전이 유지. 프레임워크 callback으로 깊이를 숨기지 않는다.

## 환경·실행 위치

신규 worktree는 자기 `.venv`를 생성해야 한다. 기본 checkout의 `.venv`·artifacts·data·비밀 설정을 공유하거나 symlink하지 않는다. Python≥3.11 및 `requirements-tested.txt`를 읽고 합성 검사에 필요한 기존 고정 의존성만 설치한다. 모델 weights/백본 다운로드·provider 초기화·새 라이브러리/업그레이드·명세 변경은 하지 않는다. 실행 환경이 없으면 상태를 먼저 확인하고 부족분을 기록하며 다른 checkout의 실행 환경으로 우회하지 않는다.

소스 편집 전에 자기 `.venv/bin/python -c 'import card_condition; print(card_condition.__file__)'`가 현재 worktree를 가리키는지 확인한다. 수정은 모두 해당 worktree의 `./develop -- <수정 명령>` 안에서 수행한다. `--check` 뒤 별도 쓰기나 기본 checkout 편집은 금지다. checkout 잠금은 전역 잠금이 아니므로 별도 실제 실험을 시작할 권한이 되지 않는다.

## 근거·해석·HTML

필수 읽기: AGENTS.md, PAIR_CODING.md, docs/collaboration/HTML_REPORTING.md, 이 계약, `docs/collaboration/reports/surface-globalmix-gradient-execution-20261108.md`, 기준6개 소스. 필요할 때 관련 호출자를 읽기 전용으로 확인한다.

실제5fold에서 N↔산술은−0.594~−0.517, N↔LME는+0.521~+0.647, 산술↔LME는−0.317~−0.081이었다. 이는 α=0의 근거인 **국소적 가설**이다. 현재최종점에서의 1차 방향은 정상bag 감소와 결함bag 증가 위험을 함께 보였다. 과거 row-LME 단독과 새 전체쌍LME 단독을 구분한다. 코드/합성 검사 완료를 오탐 감소·일반화 개선·운영 채택으로 보고하지 않는다.

자기 worktree의 `artifacts/surface-global-lme-only-20261109/report.html`에 source SHA·실제합성검사·변경/리스크/롤백·진척78/100(v1.13 유지)를 표시한다. 실자료 사진/점수 그래프는 만들지 않는다. 사용 가능한 허용 도구로 열고 실제 열기/렌더 결과를 구분해서 기록한다. 보안정책 차단은 우회하지 않으며 외부 서버·터널·업로드를 시작하지 않는다. 현재 메인 chat에서는 file: 브라우저 열기가 차단된 이력이 있다.

## 금지·완료·전달

`./experiment`, 실제 worker, 재학습/모델비교/사진추론/라벨수정/실제캐시 replay, `./review --auto`/외부AI·하위CLI 호출, 비율·threshold·하이퍼파라미터 탐색, main checkout/merge/cherry-pick/push, 다른 branch/worktree 변경·정리, force/history rewrite는 구현 세션에서 금지다. 같은 로컬 저장소의 작업 브랜치 커밋까지만 수행하고 branch push/PR 생성도 하지 않는다.

완료 시 본문 범위를 바꾸지 말고 status를 ready_for_review로 바꾸고 다음을 handoff에 기록한다: 실제 source base/checkout-base/tip 전체SHA, 자기 branch, 변경 파일과 핵심 diff, 함수수/주요 호출 전이, 실행한 명령·exit code·로그/HTML 경로·열기/렌더 결과, 미검증·리스크·롤백. 허용파일만 선택 stage/commit하고 `git status --short`를 확인한다. ignored 로그는 worktree에 보존하고 report에 SHA256/요약을 남긴다. 새 파일 baseline=null과 공통계획 작성/실행은 이후 현재 메인 담당이며 구현 세션은 실행 계획을 만들거나 실행하지 않는다.

tip을 전달한 뒤 같은 브랜치에 추가 커밋하지 않고 현재 메인의 검토를 기다린다. worktree는 제거하지 않는다. 이 전달은 코드 구현 인계일 뿐 메인 통합·실험 승인이나 상시 실행을 뜻하지 않는다.

## checks / handoff (구현 세션이 채울 부분)

- 아직 구현·합성 검사 미실행. 위 검증 항목을 실제 실행한 뒤에만 결과를 채운다.
- 롤백: 미통합 후보는 현재 메인이 채택하지 않고 기존50:50 소스를 유지한다. 통합된 경우 현재 메인만 후보 통합커밋을 일반 revert/push한다. 기존 데이터/모델 복원이나 증거 삭제는 필요하지 않다.
