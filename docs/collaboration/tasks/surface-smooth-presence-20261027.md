task_id: surface-smooth-presence-20261027
owner: Codex
status: implementing
base_sha: 4f5c4b03afb78d53c27e4057f52435cada369234
branch: codex/surface-smooth-presence-20261027

goal: 정확점 없는 앞면 양성 bag의 반응 집계 하나만 hard max에서 고정 temperature0.1 log-mean-exp로 바꿔, 동일4-fold의 실제 누락/오탐 개선 여부를 한 번 측정한다.

allowed_files:
- tools/experiments/surface-smooth-presence-20261027/objective.py
- tools/experiments/surface-smooth-presence-20261027/worker.py
- tools/experiments/surface-smooth-presence-20261027/plan.json
- tests/test_smooth_presence_objective.py
- docs/collaboration/tasks/surface-smooth-presence-20261027.md
- docs/collaboration/reports/surface-smooth-presence-20261027.md
- docs/collaboration/reports/surface-smooth-presence-20261027.html
ignored: artifacts/surface-smooth-presence-20261027/ 실행미러·검사로그, 새 artifacts/experiments/<id>/실행기록·head·사진HTML만.
forbidden: card_condition/*, Claude 모든checkout/데이터보완·새라벨·새사진,기존캐시/heads/실험기록/worker/기준·진척수정,PokeCollector,운영모델/배포,외부AI호출. 실제학습은기본checkout에서공통실행기로직렬1회.

근거: 062258 완료진단의rgb153 실제점누락20개에서 presence항의국소기울기가15개를낮추는방향이었다. 비선형hard max의비볼록증거도저장됐다. 062428 양성가중치절반변경은 FN12→16/94·FP13→10/53 및새누락4로미채택. 따라서가중치조정은반복하지않고약한양성토큰집계라는다른변수만비교한다. 이근거는국소/반복개발진단이며원인·일반화확정아님.

변경식: 정확점없는target1에서 softplus(-max(z_valid)) → softplus(-0.1*(logsumexp(z_valid/0.1)-log(N_valid))). count정규화로모든토큰값이같을때기존손실과동일하며많은토큰자체에양성보너스를주지않는다. 토큰전체를결함정답으로바꾸지않고bag존재감독을유지한다. .1은기존정상max_bound의고정평활상수재사용이며탐색하지않는다.

보존: 정확점양성/정상손실은기존detail_bag_loss와값·gradient동일. 양성/정상·실물가중치, RGB153특징/마스크/토큰, L2=1,LBFGS설정/100반복/gradient<=1e-5,고정4fold,뒷면저장maps,threshold.5,11required_cohort 모두그대로. 실패한normal-group-objective의재시도가아니며그파일/계획은변경하지않는다.

사전성공: 참조122011의동일147구역 FN<=16/94·FP<=18/53,새오답0,적어도1오류복구,typed51신규누락0,기존11cohort전부통과. 수치변화없음/보호미통과는미채택. 수렴/분리/SHA/출력실패는failed이며성능으로추정하지않는다. 온도/반복수/허용gradient변경·자동재시도금지. 개선이있어도독립일반화/운영채택아님.

구조: objective3함수(집계,fit,closure),worker2함수(loader,finish),검사4함수이하예정. 모듈guard에서fit직접호출. fit→closure→smooth_presence_loss→detail_bag_loss→point_bag_loss=4전이. baseline과동일한LBFGS에명시적closure를전달하므로콜백대상은알려져있으며새추상화/래퍼계층은없다. finish→기존render→side_image→prepared_image=3전이.

checks: 정상/정확점loss·gradient동일,동일토큰weakloss동일·유효토큰gradient분산·masked불변,weak양성없는fit동치/합성수렴. 합성확인뒤main통합하고입력SHA/11cohort/원본·decoded분리/기준선재생대조후 ./experiment --plan ... -- .venv/bin/python artifacts/.../worker.py 로1회. 실제실패시gradient/objective를기록하되성능값생성안함.
HTML: 새실험index.html에실제사진위구역정답/점수/누락·오탐분모/%p,반복개발/독립아님표시. 추적reports HTML에는공개가능집계와진척30/100,실행record·상태·수용판정·파일·검사·위험·롤백. 열기요청/렌더구분.
rollback: 운영/기존모델소스수정없음. 미채택은전용연구파일/실험기록으로보존하고운영경로에연결하지않는다. 코드제거는통합SHA를 ./develop -- git revert 후관련검사/일반push. 실제기록은실패포함보존.

## 구현 인계

- ready_for_review: objective3/worker2/검사4함수(AST실측),새소스호출전이최대4. fitter본문diff는손실호출2곳과실패gradient/objective메시지뿐이며optimizer/초기화/중심화/가중치/수렴기준동일.
- 정상/실제점손실과gradient는bitwise동일,weak없는fit의coef/bias2e-6·목적값1e-8동치. weak동일토큰loss불변,유효토큰gradient분산·masked0·합성수렴과기존worker회귀합계13검사OK(1.070초). diff검사통과.
- 이검사는성능증거가아니며main검사후실제4fold를1회실행한다. 기존4fold제안/원본·decoded분리와147/11cohort재생은기존공통검증을재사용한다. 현재실패가설은재시도하지않는다.
- 실제수렴실패가생기면새실험failure-diagnostics.json에fold/gradient/objective/완료fold수를남기고raise하여공통record.failed를보존한다. 누락률/오탐률을만들지않는다.
