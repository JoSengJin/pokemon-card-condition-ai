task_id: surface-ranking-warm-start-20261028
owner: Codex
status: implementing
base_sha: aa116ff7da474a33c78d0de3da07ffa6fdb95bce
branch: codex/surface-ranking-warm-start-20261028

goal: 고정same-photo ranking의초기값하나만zero→기존fold모델로변경해새FN2/FP2를없애면서원래평가기준을통과하는지1회측정.
allowed_files:
- tools/experiments/surface-ranking-warm-start-20261028/objective.py
- tools/experiments/surface-ranking-warm-start-20261028/worker.py
- tools/experiments/surface-ranking-warm-start-20261028/plan.json
- tests/test_ranking_warm_start.py
- docs/collaboration/tasks/surface-ranking-warm-start-20261028.md
- docs/collaboration/reports/surface-ranking-warm-start-20261028.md
- docs/collaboration/reports/surface-ranking-warm-start-20261028.html
ignored: artifacts/surface-ranking-warm-start-20261028/미러·검사,새실험폴더record/head/사진HTML만.
forbidden: card_condition/*,Claude데이터/사진/라벨·모든checkout,기존worker/실험/head/cache,평가기준/진척JSON/PokeCollector/운영fallback,외부AI. canonical공통실행기1회만실행.

근거: 진단211902는기존/후보cache再生오차0,4오류모두係数만으로flip,局所ranking方向은3/4에서최종변화와반대라단일쌍원인을확정할수없다. 기존학습쌍11노출의margin은모두1충족(3.2807~5.2731)이나softplus힘은남아있다. firstfold의동일augmented목적은기존모델≈0.2700849, cold후보0.2714127로기존모델이더낮다. 따라서loss/계수/margin/온도값을재탐색하지않고기존모델에서출발하는새최적화가설을시험한다.비볼록경로/일반화개선은미확정.

변경변수: 각fold의같은train_ids로학습된122011저장coef/rawbias를초기값으로쓴다. 현재train센터좌표로bias복원하여rawlogit초기재생<=1e-8. ranking/base전체손실·mass·정규화·margin1/계수1/T.1·153RGB/mask/point·L2=1·LBFGS100/gradient<=1e-5·4fold·뒷면map·threshold.5/11cohort는보존. 추가teacherregularization이나현재holdoutlabel을쓴모델선택없음. 학습전후동일목적값비증가<=1e-8검사.

사전성공: 기존122011동일147구역 FN<=16/94·FP<=18/53,새오답0,최소1오류복구,typed51새누락0,기존11cohort전부통과. 현재cold15/94·FP18/53및4신규오류의전후도별도로보고하되새기준으로대체하지않음. 변화없음/보호미통과미채택. 수렴/분리/SHA/초기재생/목적비증가실패는failed,수치성과추정/임계·반복수완화/초기값추가탐색/자동재시도없음.

구조: helper4함수,worker2함수유지. 모듈guard직접fit→closure→base/detail→point=3전이,rank경로2. 기존명시closure/LBFGS동일. 검사<=7함수. zero와기존fold두수준외seed/初期値탐색안함.
checks: 입력초기head보존/센터복원logit동치/같은목적함수의정지점재시작동치/손실함수·gradient동일/invalid초기shape拒否. main합성후입력SHA/학습fold教師train_ids/3쌍·2실물/11cohort검증후commonrunner1회.
HTML: 실험index.html의실제사람정답/전후score·누락오탐分母/%p,전4신규오류와全91구역. sourceSHA/30점/검사/리스크/롤백·독립아님·열기/렌더구분.
rollback: 기존모델/정답은안바꿈. 신규연구source는미채택으로보존하거나통합SHA를 ./develop -- git revert 후검사/일반push. 실제기록/사진은실패포함보존,운영채택0.
