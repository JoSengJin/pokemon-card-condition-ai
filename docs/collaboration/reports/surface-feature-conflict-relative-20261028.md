# 세 작업 실행: 특징 혼동·손실 충돌·상대 입력 — 2026-10-28

**개발 진척률 30/100(+0%p). 세 작업을 실제 실행했다. 두 진단은 수식/출처 검산을 통과했고, 상대 입력은 누락이 늘어 미채택이다.** 운영 모델·정답·평가 기준·Claude 데이터 확보 작업은 변경하지 않았다.

## 작업별 실제 결과

| 요청 | 수행 | 결과/한계 |
|---|---|---|
| 반복 오탐 특징 혼동 | 91앞면구역의 평균/잔차/peak 분해,오탐2·복구4의training-only 최근접 실제점/정상 token 비교 | 두오탐의공통성분기여58.8%/77.6%. 다만 절편을포함하며 사진조명/무늬원인확정아님 |
| 사진 안 상대적 입력 | 각crop의valid DINO token평균만제거,원래손실로고정4fold학습 | 누락20/94·오탐17/53·실제점누락22/51. 기존보호위반으로미채택 |
| 추가 클릭 손실 충돌 | 4fold×기존first/기존all/후보all의3저장상태에서점·구역양성·정상·L2 gradient분해 | 손실gradient합검산통과. 오탐별추가점국소방향이달라한항만원인으로단정불가 |

## 1. 특징 혼동: 확인한 것과 확정하지 않은 것

기존baseline122011과다중점후보222515의같은특징/4fold를고정했다. 각crop에서 `maxlogit=mean_feature·w+bias+max((x-mean_feature)·w)`로정확히분해한다. 기존peak에서의계수변화와peak이동도분리했다.

| 고정 사례 | 평균특징 변화 | 절편 변화 | 평균+절편 공통성분 | 잔차 변화 | peak이동 | 총logit변화 |
|---|---:|---:|---:|---:|---:|---:|
| 9 | +0.054764 | +0.268541 | +0.323304 | +0.226650 | +0.000000 | +0.549954 |
| 21 | +0.217512 | -0.132252 | +0.085261 | -0.047947 | +0.072501 | +0.109815 |

평균+절편의합이총상승의58.8%/77.6%다. b9는절편변화가크고c21은평균특징의양의변화가음의절편과상쇄된다. 이분해를사진색/조명만의영향이나특정학습실물의인과기여라고해석하지않는다. 91구역최대가산오차 1.05e-15다.

최근접raw특징에서 b9는사람점pool35개최고cos0.2652,명시적정상pool6368개최고0.3301이었다. c21은각15개/4832개에서0.4759/0.6364였다. 두경우모두최근접정상토큰도존재한다. 그러나pool크기가크게달라그차이로분류정확도·완전분리·혼동원인을증명하지않는다. query와최근접token은각heldfold의training실물/사진만대조했고held정답을학습자료로옮기지않았다. 상대특징의최근접결과도별도로보존했다.

공통성분양수이면서총logit상승의50%이상인사례가하나이상이면입력실험으로진행한다는사전gate를두사례가모두통과했다. 이는실험진행근거이며성능향상을보장하지않는다.

## 3. 손실 충돌: 국소 미분의 해석 범위

각foldtraining의기존class/group mass와원래첫점center를사용했다. 기존head에서first-point손실과all-point손실을각각계산하고,다중점후보head에서도all-point손실을계산했다. point/presence/normal/L2를따로나눠같은loss의합과전체autograd를검산했다. 최대gradient합오차 7.46e-17다.

4fold의baseline-all에서point/normal gradient cosine은-0.1457~-0.3857,point/presence는-0.0495~-0.1626였다. 반대정답을같은계수로학습하므로이런반대방향자체는자연스러울수있고손실의오류나새loss필요성을증명하지않는다.

기존head/기존최대반응token에서추가클릭에의한점손실차이만내려가는국소logit방향은b9=-0.089158(하락),c21=+0.005798(상승)이었다. b9의실제재학습후점수는상승했으므로추가클릭항의한스텝방향을최종재학습원인으로단정할수없다. 손실계수·gradient projection·임계값을추가조정하지않았다.

## 2. 상대 입력 실제 비교와 미채택

`x_relative[i,k]=x[i,k]-mean(x[i,valid[i]])`를앞면97행에만적용했다. 다른crop/사진/라벨/held통계는참조하지않고384차원·행순서·마스크/point를보존했다. 패딩token은변경하지않는다. 이는DINO특징공간의crop내평균제거이며사진전체색상보정·조명분리나픽셀전처리가아니다.

원래단일점/구역양성/max_bound손실·class/group mass·L2=1·zero초기값·100iteration·gradient<=1e-5·4fold·.5·뒷면map·기존147/실제점51/11cohort기준을그대로썼다. 다중점loss와ranking을동시에추가하지않았다.

| 같은 평가 자료 | 기존baseline | 상대 입력 후보 | 변화 |
|---|---:|---:|---:|
| 결함누락 |16/94(17.02%)|20/94(21.28%)|+4.26%p|
| 정상오탐 |18/53(33.96%)|17/53(32.08%)|-1.89%p|
| 올바른종류실제점누락 |21/51(41.18%)|22/51(43.14%)|+1.96%p|

새누락6·새오탐6·기존오답복구9다. primary_acceptance_passed=false,acceptance_passed=false다. 오탐1개감소를전체성능개선으로보고하지않는다. 실제점누락도증가해미채택이며독립일반화개선미확인이다. crop의공통특징을통째로제거하는방법은이자료에서유용한손상신호도버릴수있다는한계를보였다. 사진속무늬/조명에대한의미상원인은여전히미확정이다.

## 실제 실행 기록·검증

- source **c3d6e7b**, 후속상대입력계획 **747d968**. 구현브랜치92a6265,후속계획042713a. 실행source는모든단계에서동일하며최초공통실험의after snapshot을후속baseline으로byte동일하게참조했다. 공통실행기기록을우회하지않았다.
- 진단 record: **artifacts/experiments/20261028T070550-da6d6dad/record.json**,status=completed,학습0·새backbone0. primarytrue는기존147/11cohort재생보호이고전체품질acceptancefalse/정확도개선아님.
- 모델비교 record: **artifacts/experiments/20261028T070837-27da5a1b/record.json**,status=completed,4fit수렴(최대gradient7.86e-6),primaryfalse/전체false. 실패·중단실행의수치를추정한것은아니다.
- 명령은각각 `./experiment --plan tools/experiments/surface-feature-conflict-relative-20261028/plan-diagnostic.json -- .venv/bin/python artifacts/surface-feature-conflict-relative-20261028/worker.py`,같은worker에 `plan-relative.json`을전달한후속1회다. 새가설ID로진단→입력실험을직렬실행했다. 재시도/기준완화0.
- `PYTHONPATH=tests .venv/bin/python -m unittest test_surface_feature_conflict_relative test_surface_all_human_points test_ranking_regression_cause`: 격리10개OK(3.448초),main10개OK(0.837초). 평균제거의shift불변/valid평균0·패딩보존/row독립·가산분해·gradient합/finite difference·최근접pool출처를검산했다.
- 함수수analysis4/transform1/worker3/test4,주요diagnose→gradients→all_point_loss→detail_bag_loss→point_bag_loss최대4전이. git diff --check통과. 기존소스복제수정이나새범용프레임워크는추가하지않았다.
- 상대입력valid평균절대오차최대 2.46e-06(float32,원본최대특징22.33대비1.10e-7로dtype epsilon1.19e-7이내);뒷면56map은원본과같고,저장map147개점수와observations의최대차0이다. 원본사진/manifest/cache/사람응답/이전head·code snapshot과두record.files SHA를최종대조했다. postcheck는추가fit/headforward0이다.
- 실제계산은기본checkout/CPU2threads,구현checkout은합성검사만수행했다. Claude의새수집사진/val/검토결과는사용/수정하지않았다. 사람정답·geometry·평가분모/기준·split·진척/배점수정0,새라벨0,provider호출0,운영채택0이다.
- development-review session_id가현재세션과달라새자동handoff/next_steps/token_report는생성되지않았다. 이전latest.json의ai_calls_forbidden기록을이번결과로대체하지않았다.

## 변경 파일·핵심 diff

- `tools/experiments/surface-feature-conflict-relative-20261028/analysis.py`:91구역평균/잔차분해·최근접실제점/정상pool·4손실gradient의진단4함수.
- 같은폴더 `transform.py`:valid token의crop평균만빼는독립변환1함수. 기존card_condition소스는변경하지않았다.
- 같은폴더 `worker.py`:공통실행기의고정context/4fold를검증하고진단/상대입력branch를분리실행,기존11cohort/사진HTML기록.
- 같은폴더 `plan-diagnostic.json`,`plan-relative.json`:사전검산/성공·실패조건·입력SHA·진단gate·원래147/51/11cohort보호와신규/동일Python snapshot계약.
- `tests/test_surface_feature_conflict_relative.py`:상대입력/분해/gradient/최근접pool의4검산. 검사통과를모델진척으로계산하지않는다.
- `docs/collaboration/tasks/surface-feature-conflict-relative-20261028.md`,이MD/동명HTML:세작업범위/실측/미채택/위험/롤백.

## 사진·HTML·리스크·롤백

- 핵심특징/실제training최근접token사진:진단폴더 `overview.html`. 전체91분해/손실수치:같은폴더 `index.html`.
- 상대입력앞면91구역의사람정답/출력·누락/오탐분모·%p:후속실험폴더 `index.html`. 전체147/실제점51분모를상단에명시했다. 모델peak와사람점/최근접특징token을구분한다.
- MD/HTML 본문·수치·record/source SHA를 검증했다. 특징 overview·상대 입력 결과·공개 보고서의 열기 요청은 모두 queued였고, 최근접 token PNG 1개는 직접 확인했다. 실제 HTML 렌더는 미확인이다.
- 위험:최근접pool크기가다르고실물이적어유사도/gradient를인과나일반화로확정할수없다. 평균제거는도움되는공통특징도제거하며후보가실제로누락을늘렸다. 임계값/L2/계수조정으로결과를맞추지않았고기존정답을바꾸지않았다. 원래연구모델의품질미달과새training실물대조자료의존은남아있다.
- 롤백은 `./develop -- git revert --no-edit 747d968 c3d6e7b` 후관련10검사와일반push. 747d968은실험계획,구현은c3d6e7b다. 운영모델/기존소스·정답변경0이므로모델/라벨복구는불필요하다. 공통기록/미채택head는삭제하지않는다.

## 원격·정리·에튜 포인트

검증코드main/origin747d968일치후이전Codex디코딩checkout만main대응·clean·진행Git없음·비차단잠금확인후일반remove했다. 고유snapshot4개와lock증거총5개는SHA로보존했다. 브랜치/이력과실험은보존하고최신codex/surface-feature-conflict-relative-20261028 checkout042713a를롤백용으로유지했다. Claude/미통합/사용중checkout은변경하지않았다. 감사: artifacts/surface-feature-conflict-relative-20261028/worktree-cleanup/audit.json. 문서는후속커밋일반push로공유한다.

국소기울기는현재계수에서한작은변화의방향이다. 예를들어b9의추가점항은현재점수를내리는방향인데실제전체재학습후에는점수가올랐다. 다른손실과최적화경로가함께작용하므로한항의미분만으로최종오류원인을확정하지않았다. 평균특징제거도선택적인조명분리가아니라DINO공통성분전체를버리는변환이라,수학적으로간단해도성능은실측해야한다.
