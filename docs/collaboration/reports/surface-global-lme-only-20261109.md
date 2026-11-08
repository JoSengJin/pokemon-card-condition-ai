# α=0 전체쌍 LME 구현·합성 검증 인계 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 고정 α=0의 `B + G` 구현과 합성 검증을 완료했다. 상태 `ready_for_review`. 실제 모델 성능·일반화 개선은 미평가이며 운영 미채택이다.

## 기준·권한

- source base: `e52e4e7d669d553b549daef7b94e8226ed142cfa`
- checkout base: `00f6372e8912d9145972caa3951c0919042e077e` (전달 프롬프트 최종 커밋과 일치).
- branch: `codex/surface-global-lme-only-20261109`.
- 검증 시점: 위 checkout base 위의 신규 6개 Python 미커밋 상태. 아래 파일별 SHA256이 실제 검사 소스를 고정한다. 최종 tip 전체SHA는 완료 응답으로 전달하며, 이 보고서를 포함한 단일 구현 커밋의 `git log -1 --format=%H`로 확인한다(자기 커밋 SHA의 본문 순환 참조는 하지 않는다).
- 시작 작업 트리 clean, source→checkout 차이는 배정 task/전달 프롬프트 2개뿐(Python 차이0). 구현 세션이며 main 역할 인수 없음.
- 실제 실험/worker 실행/사진 추론/캐시 replay/라벨 수정/외부AI/하위CLI/main 통합/push/PR 각각0. 다른 checkout 데이터·환경·비밀 설정을 가져오지 않았다.
- 진척 근거 `PROGRESS_CRITERIA.md`, `development-progress.json`을 읽었고 점수·배점·기준·history는 수정하지 않았다.

## 변경 파일·핵심 diff

신규 경로 `tools/experiments/surface-global-lme-only-20261109/`의 6개 Python 및 이 보고서, 배정 task의 status/checks/handoff만 변경했다.

|파일|변경|
|---|---|
|`objective.py`|기준 복사본의 `loss_and_grad`에서 `alpha=0.0` 고정. total `B+alpha*M+(1-alpha)*G`, 성분도 동일 계수. 연결된 산술0 유지. 나머지 fit/optimizer/기록 코드는 동일.|
|`worker.py`|가설ID만 `surface-frozen-global-region-rank-global-lme-only-20261109`로 교체. 학습·평가·특징추출 블록 바이트 보존. 실제 실행/import 없음.|
|`armijo_direction.py`, `metrics.py`|기준과 바이트 동일 복사.|
|`checks.py`|기존 optimizer·mask·hardmax 보호 유지. oracle을 G-only로 변경, 50:50/floor 기대 제거. moderate 전체쌍 양의 기여, 극단 underflow0·유한/비음수 확인.|
|`checks_components.py`|독립 G 항등식·autograd·유한차분. 같은 theta의 bag/L2 보존. 새 fit 수렴/기록·scorer AST 단독 검사. 50:50 fit 결과 bit동일 요구 제거.|
|task 문서|status와 checks/handoff만 갱신.|

총 순위계수1, 전체쌍 flatten LME, tau0.1, 결함max, L2=1, mask/점수 API/threshold0.5/seed/optimizer/수렴/예산을 유지했다. 일반 alpha 옵션·epsilon·clipping·추상화·새 의존성 없음.

## 실행 환경·명령·결과

자기 `.venv` Python3.12.15, torch2.14.1, numpy2.5.3. 저장소 `requirements-tested.txt` 고정 버전만 설치하고 `pip install --no-deps --no-build-isolation -e .`로 자기 checkout을 연결했다. `card_condition.__file__` 자기 worktree 일치, 독립 venv 확인. 모델 다운로드/provider 초기화 없음.

준비 중 기본 `python3`가3.9.6인 것을 확인해 새로 만든 빈 환경을 Python3.12로 재생성했다. 최초 합성 실행2건은 editable 설치 전 `ModuleNotFoundError: card_condition`로 종료했고, 자기 checkout editable 설치로 해결했다. 모델 코드/의존성 기준을 우회하지 않았다.

최종 실제 실행(모두 exit0):

```sh
.venv/bin/python tools/experiments/surface-global-lme-only-20261109/checks.py
.venv/bin/python tools/experiments/surface-global-lme-only-20261109/checks_components.py
.venv/bin/python -m py_compile tools/experiments/surface-global-lme-only-20261109/*.py
.venv/bin/python -m pip check
git diff --check
```

최종 로그는 아래 경로에 저장했다. 컴파일은 검사 보존 스크립트에서도 `py_compile.compile(..., doraise=True)`로6개 확인했다.

- 독립 목적함수14건(두 normal reduction, 385차원 포함), 성분20+total4 중심 유한차분. 독립 성분 loss/gradient 최대오차 각각 `8.881784197001252e-16`.
- G-only softmax 도함수, row-LME와 구별되는 비대칭 fixture, 쌍 순열/반복/동일값/단일쌍 정규화, 극단값 유한 gradient 통과. 독립 oracle은 `softplus(LSE(normal)-log N + LSE(-defect)-log D)` 항등식으로 전체쌍 G를 재구성하여 production의 flatten 구현과 독립 대조했다.
- 같은 theta/입력의 정상bag·결함bag·L2 값/gradient는 기준과 정확히 동일. 전체 total·gradient·학습계수/점수/trace의 이전50:50 동일성은 요구하지 않았다.
- 산술 성분 loss/gradient/norm/bias 정확히0(385차원 gradient 포함). 5성분합 오차≤1e-10, 최종theta/target/mass/mask SHA 일치. 성분 추출의 추가 목적함수평가/step0. cosine을 계산·수치 채움하지 않았으며 zero-gradient cosine은 unavailable/None이다.
- 실제 합성 fit 3건: 반복/평가 `11/11`, `11/11`, `6/6`; 최종 gradient Linf `9.955717805709696e-09`, `1.7465215496059727e-08`, `6.427308685275079e-10`. fixture는 작은 분리 가능한 tensor이며 실제 데이터 수렴의 증거가 아니다.
- 초기수렴(평가1·trace없음), 실제 채택 상태, 거절된 zero-gradient trial 제외, 1e-7~1e-5 종료 경계, exclusive-create 기존 sidecar 보존, corrupt sum/실패 때 성공 sidecar 부재 통과.
- 방향35step/history20 PyTorch 대조, strict Armijo, relative curvature/scale, alignment0.0099 reset·0.0101 보존, 중복trial 차단, 초기평가 포함1250 상한 통과.
- worker는 전체 문자열을 가설ID 치환한 기준과 대조. 학습행 sidecar AST 한 블록만 가짜 ID2개로 실행해 순서·fold·target·덮어쓰기 방지 확인. worker 전체 미실행.
- 출력은 tracked `tools/experiments/edge-back-source-weight-20261030/worker.py`의 `score` 함수 AST만 고정 파라미터·합성 tensor로 실행해 list API/maskedmax→sigmoid/0.5 경계 확인. worker 모듈은 실행하지 않았다.

## 구조 확인

|파일|기준 함수수→신규 함수수|
|---|---:|
|objective|3→3|
|worker|0→0|
|armijo_direction|1→1|
|metrics|4→4|
|checks|3→3|
|checks_components|6→6|

AST는 def/async def/lambda/중첩을 포함해 계산했다. 아래 프로젝트 함수 경로는 파일/객체 경계를 넘겨 직접 확인했다.

- `worker → fit_detail_head → loss_and_grad → detail_bag_loss → point_bag_loss`:4전이.
- `worker → fit_detail_head → lbfgs_direction`:2전이.
- 테스트 `fit_case → fit_detail_head → loss_and_grad → detail_bag_loss → point_bag_loss`:4전이.
- 거절/오염 mock은 fit_case를 거치지 않고 직접 fit 호출: `fit_detail_head → rejected_trial/corrupt_terms → loss_and_grad → detail_bag_loss → point_bag_loss`:4전이.
- `fit_case → fit_detail_head → boundary_direction → lbfgs_direction`:3전이.
- optimizer의 유일한 테스트 callback은 `torch.optim.LBFGS.step → quadratic`; quadratic 내부는 PyTorch 연산뿐, 프로젝트 helper 호출 없음. 동적 패치 대상은 테스트에서 명시한 위3개 함수로 고정되고 finally로 복원된다. autograd 성분 추출은 추가 fit/forward callback을 등록하지 않는다. worker의 향후 fit dispatch는 대입 대상 `objective.fit_detail_head`로 정적으로 대조했으며 실제 worker 동작은 미검증이다.

## 증거·HTML

ignored 산출물은 자기 worktree의 `artifacts/surface-global-lme-only-20261109/`에 보존한다. 합성 진단/trace는 tempfile에만 작성 후 정리되며 요약·해시는 로그/JSON에 남는다. 실제 experiments 폴더의 record는 생성하지 않았다.

- `checks.log`, `checks-components.log`: 실제 최종 stdout/stderr.
- `checks.json`: 결과·소스해시·함수수·경로·환경·권한범위.
- `report.html`: source/checkout SHA, 실제 결과, 진척78/100, 변경·리스크·롤백. 외부 리소스/실사진/모델점수 없음.
- `opening-status.txt`: `open artifacts/surface-global-lme-only-20261109/report.html` exit0로 로컬 기본앱 열기 요청 성공. 별도 브라우저 렌더 확인은 **file: 프로토콜 보안정책 차단**, 실제 화면 렌더 미확인. 차단 후 우회·서버·터널·외부업로드 없음. HTML 정적 내용/결과 대조는 통과.

|산출물|SHA256|
|---|---|
|`checks-components.log`|`10e446244bdb7853cfc027918bb93eeeea95f94108cc8800c530f994de0784e8`|
|`checks.json`|`1e7e517383c07f39c1e7858385bc91772495563a57da12e9f6e19aa8e8e0b7c3`|
|`checks.log`|`bf2e06614de73c77cd412e2e1ddae086f79834da932bdeb6dc544fa514311b1e`|
|`opening-status.txt`|`ac53f6631cdd069158f2398eba4caa34b52c077a9045796943f2d97096886983`|
|`report.html`|`50db2692325156a0d9a9c35fa736f47b9010c256b0579de7bdfcd3c53e94a665`|

검증 소스:

|신규 Python|SHA256|
|---|---|
|`armijo_direction.py`|`789269c2bf2b50c032b8c7aeece26ec76a91bcfbce3bdafe68f1ac013e9d6a32`|
|`checks.py`|`62fe3deddbec685006f6df4f4c81dc235dc5e6f5a47d14793813798ec52e37d5`|
|`checks_components.py`|`1d43c30245cc38c85817bd95d7d29ea3cb3b7f82cddf35b7ade95933e230dc9f`|
|`metrics.py`|`b6322300e2e17226c5508f22580af6399ff57e07948f10af68a3f0ac044f698b`|
|`objective.py`|`1f7043f4579b88b188655975aa3446afdd59ec1f333f5843ad86d706ae18ea93`|
|`worker.py`|`445a96260b059fe198fbd8e5c0b51d13685d72e954390b5f56fd60945c30fd80`|

## 미검증·리스크·롤백

실제1776행 평가·FN/FP/AUC/paired bootstrap·독립 일반화·실데이터 수렴/예산/메모리/속도·운영 채택은 미검증이다. 이번 합성 검사는 품질 게이트 충족을 뜻하지 않는다. 가설 근거는 기존 gradient 실행 보고서의 최종점 국소 관계이며 인과관계나 성능 개선 보장이 아니다.

α=0으로 기존 산술 gradient floor가 사라져 극단의 쉬운 쌍은 부동소수 underflow로 기여0이 될 수 있다. 이를 쌍 선별로 해석하지 않으며 epsilon/clipping/하한은 넣지 않았다. 최종 계수·점수·trace 변화는 의도된 목적함수 변경의 영향이다. 실제 품질은 원래 메인 세션의 별도 승인 실험으로만 판단한다.

롤백: 아직 미통합이므로 원래 메인이 후보를 채택하지 않고 기존50:50 소스를 유지하면 된다. 이후 통합된 경우 원래 메인만 통합 커밋을 `./develop -- git revert <통합SHA>`로 되돌린다. 데이터/모델/라벨 변경이나 복원은 없다. 브랜치·worktree·증거를 삭제하지 않는다.

에튜 포인트: `0.0 * arithmetic`은 값은0이어도 autograd graph 연결을 유지한다. 그래서 5성분 기록을 그대로 미분하면 0 vector가 나온다. Python 정수0으로 바꾸면 미분할 graph가 없어 동일한 기록 API가 깨진다.
