task_id: surface-same-photo-ranking-20261027
owner: Codex
status: implementing
base_sha: c25d622a3ded94ade80acb33bc4d4917d6a041e4
branch: codex/surface-same-photo-ranking-20261027

goal: 기존 사람 실제점과 같은 사진의 명시적 표면 정상 bag만 사용한 상대순위 감독을 한 항 추가해 같은4-fold의 누락/오탐을 실제 비교한다.
allowed_files:
- tools/experiments/surface-same-photo-ranking-20261027/objective.py
- tools/experiments/surface-same-photo-ranking-20261027/worker.py
- tools/experiments/surface-same-photo-ranking-20261027/plan.json
- tests/test_same_photo_surface_ranking.py
- docs/collaboration/tasks/surface-same-photo-ranking-20261027.md
- docs/collaboration/reports/surface-same-photo-ranking-20261027.md
- docs/collaboration/reports/surface-same-photo-ranking-20261027.html
ignored: artifacts/surface-same-photo-ranking-20261027/미러·검사로그,새실험폴더기록/head/사진HTML만.
forbidden: card_condition/*,Claude모든checkout·데이터보완/새정답/사진,기존캐시·실험·failedworker·정답/기준/점수,PokeCollector,운영연결,외부AI호출. 기본checkout공통실행기에서만직렬1회.

근거: 061542/062258은같은사진에서실제점반응과정상최대반응의순위위반을읽기만했다. 표면상대순위감독실험은없다. 고정RGB153캐시에앞면실제점–명시적같은사진정상3쌍/2실물이존재한다. ff69정상행reason은과거미확인설명을유지하지만human-response.json의직접사람정답0과정확box/photo SHA를대조해확인했으며고치지않는다. 실제점2개도기존human_evidence만사용한다. unknown을정상으로바꾸지않는다.

변경변수: 기존손실에각실제점의기존mass * mean_same_photo_normal softplus(1 + 0.1*logsumexp(normal_valid_logits/0.1) - actual_point_logit)를추가한다. 계수1·margin1은사전고정,기존정상max_bound의T.1재사용. 같은group/image인명시적정상과실제점만,point는정상box밖이어야한다. 기존loss·가중치·L2=1·optimizer100/gradient<=1e-5·특징/마스크/토큰153·4fold·뒷면maps·.5threshold는보존. smooth-presence와normal-group-objective를반복/결합하지않고원래hard-max약한양성baseline에서시작한다.

사전성공: 같은147구역의122011 기준 FN<=16/94·FP<=18/53,새오답0,적어도1오류복구,typed51새누락0,기존11cohort전부통과. paired 감독은training fold에만구성,held실물/원본·decoded SHA누수0. 4fit수렴/입력SHA보존.변화없음/보호미통과는미채택. 수렴/분리/출처/유한성실패는failed,성능추정/파라미터변경/자동재시도금지.

구조: helper4함수이하(쌍구성,rankingloss,fit,closure),worker기존loader/finish2함수재사용. fit→closure→detail_bag_loss→point_bag_loss=3전이,fit→closure→rankingloss=2. 모듈guard직접fit. LBFGS/closure는baseline그대로이며knowncallback. 테스트4함수이하.
checks: 같은사진/실물/정확종류/직접normal만쌍구성·held제외·contradictorybox차단,쌍없는fitbaseline동치,rankgradient가point상승/normal하강,작은합성fit수렴. 실제고정입력SHA/기준선147·11cohort재생검사뒤공통실행기로1회. 연구산출물만추가,실제모델/라벨변경없음.
HTML: 새실험index.html실제사진의정답/점수/누락오탐·분모/%p/반복개발·독립아님,추적동명reports HTML의실제성과/30점/검사/위험/롤백. 열기와렌더확인구분.
리스크: 3쌍/2실물뿐이며다른crop맥락차이가있다. source조건을줄이는감독가설이지새실물일반화나위치IoU보장이아니다. 수치미달시운영채택0.
rollback: 운영source미변경. 미채택연구코드와실험은보존하고운영경로미연결. 코드제거는통합SHA를 ./develop -- git revert 후관련검사/일반push. 기존/새실험기록은삭제하지않는다.
