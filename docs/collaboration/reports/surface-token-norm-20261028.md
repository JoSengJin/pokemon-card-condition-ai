# 앞면 특징 크기 제한·뒷면 기존 실제점 활용 — 2026-10-28

**개발 진척률 30/100(+0%p). 기존 자료만으로 뒷면 실제점 누락을 11→9/33으로 줄였다. 전체 구역 누락·오탐과 새 오답은 그대로지만, 전체 수용 기준은 미달이어서 운영 미채택이다.** Claude 수집·검토 데이터와 정답·평가·봉인 자료는 변경하지 않았다.

## 같은 자료의 실제 결과

threshold0.5, 기존147구역(결함94·정상53), 올바른 종류 실제점51과 원래11필수cohort를 유지했다. 반복 개발·모델선택 자료이며 독립시험이 아니다. 두 후보는 각각 원래 대조와 비교했고 서로 결합하지 않았다.

| 모델 | 결함 누락 | 정상 오탐 | 실제점 누락 |
|---|---|---|---|
| 기존 대조 |16/94 (17.02%)|18/53 (33.96%)|21/51 (41.18%)|
| 앞면 방향 보존 정규화 |17/94 (18.09%, +1.06%p)|19/53 (35.85%, +1.89%p)|23/51 (45.10%, +3.92%p)|
| 뒷면 기존 전체점 활용 |16/94 (17.02%, 0%p)|18/53 (33.96%, 0%p)|19/51 (37.25%, −3.92%p)|

뒷면 후보의 실제점만 분리하면11/33(33.33%)→9/33(27.27%), −6.06%p다. 기존 검출점의 새 누락0, 새 구역누락0·새 오탐0이다. 복구된2점은 **같은1실물**이므로2개의독립실물개선이아니다. 점반응누락을계산한것이며정상점/전체손상범위가없어위치정확도·IoU를주장하지않는다. 관찰제한 성능과 속도는 이번에 평가하지 않았다.

## 원인 확인과 실제 개발

앞선 고정head진단에서 training오류가거의0이어도held오류가커서,첫후보는용량증가대신입력제한을시험했다. 앞면97행의유효token만 `sqrt(384)*x/||x||2`로바꿔방향을보존하고패딩/384차원/RGB224/마스크/좌표/원래손실·L2·4fold·뒷면map을유지했다. 다른token/사진/held통계는쓰지않는다. training norm범위36.46~54.00,중앙값45.61~45.97이었다. 고정반경19.60은사전수식이며결과를보고scale을고르지않았다. 네fold모두수렴(최대gradient5.68e-7)했지만새누락2·새오탐3·복구3으로미채택이다. norm이유용한신호를담을수있고고정L2와의상호작용도있어사진조명만의원인으로해석하지않는다.

다음원인을원래필수cohort에서확인했다. legacy51 전체누락기준은5이하인데고정뒷면만12/33누락이었다. 앞면만고쳐서는전체수용에도달할수없다. typed51의뒷면도11/33누락인데구역최대누락은2/43으로낮아,구역의어딘가반응과사람이찍은위치반응을분리해다뤘다. legacy51과typed51은서로다른좌표라수치를섞지않았다. 보호기준을바꾸지않았으며앞면도별도미달이므로뒷면하나만고쳐전체완료라고하지않는다.

후속후보는기존뒷면33양성bag에이미있던46개고유surface점token을사용했다. 변경은양성점손실의첫점→모든고유점의평균하나다. 같은고정manifest의올바른종류점만사용하고,미클릭영역을정상으로바꾸지않았다. 원래21개뒷면실물제외head의train_ids·raw/decoded사진분리를재검증했다. 원래첫점center/정상·weak손실/class-group mass/L2=1/zero init/LBFGS100/gradient<=1e-5/.5를유지했다. 앞면은원래baseline map그대로이고실패한정규화와결합하지않았다.

21fit모두수렴(최대gradient3.03e-6). typed51의점누락21→19,legacy51도별도분모에서22→20으로줄었고각코호트새점누락0이다. 두점의응답은각각0.4911→0.5548,0.4541→0.5185였다. 해당실물/사진은각head학습에서제외됐다. 국소진척사전기준은통과했지만typed51 maxFN18 및legacy51 maxFN5 등전체필수기준에는미달이다. **primary_acceptance_passed=true는전체147 보호통과이고acceptance_passed=false는전체품질미달**이다. 기존연구checkpoint만보존하며운영경로로연결하지않았다.

## 실행·검증 근거

검증source main **1fd6dc6**, 정규화실행source **3a862bd**. 보고서는후속문서커밋이며실행snapshot과구분한다. 실제학습은canonical checkout에서만아래공통실행기로직렬1회씩실행했다. 새backbone forward0·새라벨0·Claude신규자료사용0·외부AI0이다.

- 정규화: `artifacts/experiments/20261028T130920-50860931/record.json`, status=completed, primary=false/전체false.
- 뒷면기존점: `artifacts/experiments/20261028T131334-3c85d76b/record.json`, status=completed, primary=true/전체false.
- 명령: `./experiment --plan tools/experiments/surface-token-norm-20261028/plan.json -- .venv/bin/python artifacts/surface-token-norm-20261028/worker.py` 및 `plan-back.json`/`worker-back.py`. 결과후scale/반복수/수렴/평가기준변경과재시도0.
- 관련단위검사: 정규화와기존회귀13개 격리OK(4.063초)/mainOK(0.885초), 뒷면기존점과기존회귀12개 격리OK(0.894초)/mainOK(0.788초). 검사묶음이겹치므로25개의고유검사로합산하지않는다.
- `postcheck.json`: 두record.files SHA전체·plan고정입력SHA·147저장점수/observations/result재생오차0·11cohort·정규화의뒷면56map/뒷면후보의앞면91map불변을확인했다. 저장4+21head를다시투영해map재생오차0을검증했고추가학습/새backbone은없다. 실제점새누락0·복구2점/1실물도검산했다.
- 구조: transform1/worker1/worker-back3함수,각7이하. 주요손실경로fitter→closure→all_point_loss→detail_bag_loss→point_bag_loss 최대4전이. 기존objective/평가경로를읽기전용재사용하고운영호출자변경0.
- 다른세션의development-cycle/latest는ai_calls_forbidden이고이번실험자동인계가아니다. 기존handoff를읽었으며새provider실행·자동변경은없었다. 독립시험/소비프로젝트통합/실사용속도검사는이번에실행하지않았다.

## 변경 파일·리스크·롤백

- `tools/experiments/surface-token-norm-20261028/transform.py`: token방향보존·고정반경변환1함수.
- 같은폴더 `worker.py`, `plan.json`: 앞면정규화대조와기존147/51/11cohort재생.
- 같은폴더 `worker-back.py`, `plan-back.json`: 원래21뒷면제외학습·기존전체점감독·앞면map보호·뒷면56사진렌더.
- `tests/test_surface_token_norm.py`: 방향/스케일불변·패딩/행독립·유효성거절2검사. 기존all-point검사는재사용했다.
- 작업task/이MD/동명HTML: 사전계약·추가근거·실측·미채택·복구절차. `card_condition`·소비서비스·Claude파일·진척점수변경0.

리스크: 같은개발자료반복으로선택편향이있고두복구점이같은실물이다. 실제점반응개선이독립일반화·다른촬영조건개선을증명하지않는다. 원래전체기준미달이며정규화는실제로악화했다. 더많은독립실물의정상/결함정답은계속필요하다. 기존정답/분모/기준을완화하지않았다.

롤백은실행중인작업없음을확인한뒤 `./develop -- git revert --no-edit 1fd6dc6 fdd8986 3a862bd c78d390` 후관련검사/일반push. 운영checkpoint/정답은바꾸지않아복구불필요. 새연구head와실험기록은삭제하지않는다.

## 사진 보고와 인계

정규화91구역사진: 정규화실험폴더index.html. 뒷면56구역사진: 뒷면실험폴더index.html. 빨강은typed사람점,파랑은모델peak다. 뒷면각사람점의기존/후보점수·누락여부와전체147/51분모·%p도표시한다. 실자료는Git제외artifacts에만보존한다. 종합페이지는 `artifacts/surface-token-norm-20261028/index.html`이다. HTML열기응답/렌더미확인·원격일치/이전checkout정리는확인후덧붙인다.

에튜 포인트: 구역최대가양성이어도실제손상위치가양성이라는뜻은아니다. 이번에는한구역의첫점만학습하던손실을기존모든고유점평균으로바꿔여러위치에반응을요구했다. 예를들어두점이면 `mean(softplus(-z1),softplus(-z2))`이고bag가중치는그대로여서클릭수가많은실물이자동으로더큰가중치를얻지않는다.


실자료종합·뒷면·정규화3개HTML열기요청은모두queued,실제렌더미확인이다. git diff --check 및허용파일대조통과. 독립시험·운영채택없음.


## 원격·checkout·열기 확인

검증코드/보고서 main과origin/main 92af098 일치를 확인했다. 최신Codex 작업checkout53500cf를롤백용으로유지하고이전preserved-heads checkout d81e484만main대응·clean·Git작업없음·비차단flock·고유lock SHA1개보존후일반remove했다. Claude/미통합/사용중checkout과브랜치/이력은보존했다. 감사: artifacts/surface-token-norm-20261028/worktree-cleanup/audit.json. 공개HTML까지4개열기요청queued이며실제렌더미확인이다. 후속문서도일반push한다.
