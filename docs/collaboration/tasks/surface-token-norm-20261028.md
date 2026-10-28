# 앞면 표면 토큰 방향 보존 정규화 — 2026-10-28

- task_id: surface-token-norm-20261028
- owner: Codex
- status: implementing
- base_sha: 5857f9e177227d361129908b2cd774395e85e1f1
- branch: codex/surface-token-norm-20261028
- worktree: 로컬 전용
- goal: 기존 확정train의 앞면 DINO token별norm 차이만 제거한 후보를 원래147/51/11cohort에서 한 번 비교한다. 품질통과 때만 채택을 검토한다.

## 근거·가정

102607 고정head진단에서 training오류가거의0이고원형+잔차가더낮은학습목적을얻어도held 실제점/오탐이악화했다. 070550에서는공통성분과잔차가오탐상승에함께기여했다. 사진출처·내용·특징크기가교란돼원인을확정하지않는다. crop평균제거·차원확대·중간층·손실분리와다르게,이번에는같은최종층384차원feature의방향을유지한채크기만고정하는가설이다. 성능향상은미확인이다.

## 소유 파일·금지

allowed_files:
- tools/experiments/surface-token-norm-20261028/transform.py
- tools/experiments/surface-token-norm-20261028/worker.py
- tools/experiments/surface-token-norm-20261028/plan.json
- tests/test_surface_token_norm.py
- docs/collaboration/tasks/surface-token-norm-20261028.md
- docs/collaboration/reports/surface-token-norm-20261028.md
- docs/collaboration/reports/surface-token-norm-20261028.html

ignored: artifacts/surface-token-norm-20261028/ 의신규mirror/검산/HTML,공통실험신규폴더만쓴다. Claude 모든checkout/수집·검토/새사진/라벨/live/미채택manifest/val/봉인test/기존cache·head/운영모델/card_condition/PokeCollector/Gemini fallback/진척점수·기준은수정하지않는다. 새데이터채택/라벨요청/외부AI/새backbone0.

## 한 변수·고정 기준

앞면97행 valid token마다 x→sqrt(384)*x/||x||2. held통계/정답/다른token/다른사진의값을쓰지않는다. dtype/384차원/validmask/point토큰/행순서/사진box/최종층/RGB224는유지하고패딩은불변이다. valid norm0 또는비유한입력은실패로중단한다. sqrtD는차원의상수이며평가를보고scale을고르지않는다. 방향보존이어도norm에담긴유용한손상신호를버리며기존L2와상호작용하는리스크가있다.

원래153cache·147구역(양성94/정상53)/typed51·11cohort/학습전용ff69의6행·4frontfold/실물/raw/decoded분리·첫실제점/weak bag/max_bound/class-group mass/L2=1/zero init/LBFGS100/gradient<=1e-5/threshold.5/뒷면map을보존한다. 이전실패후보와결합하지않는다. training validtoken norm분포는기록만하고후보/scale선택에쓰지않는다.

고유가설ID surface-front-token-direction-20261028. 동일baseline122011 대조에서FN<=16/94,FP<=18/53,새오답0,최소1기존복구,typed51새누락0,원래11cohort전체수용을성공조건으로고정한다. 개선없음/보호위반은미채택,수렴/SHA/분리오류는failed/성능미측정이다. scale·L2·gradient·iteration·seed탐색/실패재시도는하지않는다.

## 구조·검사·기록

transform1함수/worker1/검사2개,각7이하. moduleguard→fit_detail_head→closure→detail_bag_loss→point_bag_loss 최대4전이. 기존finish/render·balanced를읽기전용재사용하며운영호출자는없다. 합성검사는validnorm고정/양의스케일불변/방향보존·패딩/행독립·zero/비유한거절만2개로검산하고기존관련검사를함께실행한다.

source수정은별도checkout ./develop 안에서,실제학습/추론은기본checkout ./experiment --plan … -- … 안에서직렬1회. 원래모델source는변경하지않고code_changes 신규2파일은baseline=null로등록한다. 입력/소스SHA·snapshot·plan은실험전고정한다. 기록상completed와품질수용을구분하며독립일반화개선을주장하지않는다.

전체진척PROGRESS_CRITERIA.md/development-progress.json의30/100유지. 실자료사진91구역·147/51분모·이전대비%p·관찰제한미평가·record.json실제상태/판정·검사/리스크/롤백·검증sourceSHA를동명MD/HTML에보고하고연다. 열기응답과렌더미확인은구분한다.

원격은검증후일반push로main동기화. 최신완료Codex checkout1개유지·이전완료checkout만main대응/clean/flock/고유증거SHA보존후일반remove. Claude/미통합checkout은보존한다. 롤백은실행중작업없을때통합source/plan SHA를 ./develop -- git revert 후관련검사/일반push. 기존운영모델/정답복구불필요,실험기록보존.


## 정규화 실측 뒤 후속 범위 — 뒷면의 기존 모든 실제점

130920-50860931은수렴/completed이나FN17/94,FP19/53,typed23/51로미채택이다. 결과의필수cohort를면별집계하니원래legacy51보호maxFN5에대해고정뒷면만12/33누락이다. 앞면만개선해도이전체기준을통과할수없다. 기존typed51뒷면은11/33누락이며구역뒷면FN2/43과차이가크다. 기준완화없이뒷면위치반응을다음개선대상으로삼는다. 앞면도기준미달이므로뒷면하나의개선만으로운영품질을통과한다고하지않는다.

추가allowed_files: tools/experiments/surface-token-norm-20261028/worker-back.py, 같은폴더plan-back.json. 기존objective.py(surface-all-human-points-20261028)는읽기전용재사용. 앞면모든점실험은실패했으나이번은고정뒷면21실물제외head의33bag/46고유점토큰으로다른범위의별도가설이다. 같은자료반복front실험이나앞뒤후보혼합아니다.

고유ID surface-back-all-existing-points-20261028. 원래53firstpoint/기존typedtraincache/원본고정manifest의surface점만사용하고,변경은뒷면양성bag손실의첫토큰→모든기존고유surface점평균하나다. 정상/weak/L2=1/class-group mass/firstcenter/zero/LBFGS100/gradient<=1e-5/threshold.5/실물rawdecoded분리·21기존train_ids·앞면기준map은불변. 원래147/legacy51/typed51/11cohort정답과기준유지. 정규화후보와결합0.

성공판정은원래전체수용으로유지하고,전체미달이어도국소진척여부를별도로보고한다. 국소전진은같은147 FN<=16 FP<=18,새오답0,typed51기존검출누락0,뒷면typedFN<11을모두만족한경우만표시한다. 전체수용미달이면운영미채택이며학습조건/평가분모는결과후변경하지않는다. failed는완전성능미측정/재시도0이다.

worker-back은load/render/finish최대3함수. fit_all_point_head→closure→all_point_loss→detail_bag_loss→point_bag_loss 최대4전이. 기존allpoint검사를재사용하고기존21train_ids대조·held그룹/rawdecoded완전제외·frontmap불변·원래head재생을실행전검사한다. 렌더는뒷면56구역과typed원래점좌표/모델peak를구분해표시한다. 직접추론/새라벨없고공통실행기단일실행. 모든Claude자료·진척/기준·운영코드금지는유지한다.


## 실행 인계

130920정규화completed/전체false,131334뒷면completed/primarytrue·전체false.후보결합0.typed51 21→19,새누락0·구역FN16/FP18불변,복구2점은같은1실물.검증source1fd6dc6,main13/12검사OK,postcheck25head재생·입력/recordSHA·기존보호통과.진척30/100,운영미채택.상세MD/HTML·위험·롤백은동명reports,사진은각실험index.원격/열기/정리는후속확인.
