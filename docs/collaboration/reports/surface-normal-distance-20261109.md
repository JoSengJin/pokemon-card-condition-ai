# 정상 분포 거리 단일 가설 결과 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 정상분포거리1개를추가한385차원표현은 **AUC개선근거없음 / 운영미채택**이다. 손실가중치·대조군·성공기준을유지하고단일가설을1회평가했다.

## 실행과 고정 계약

- 검증/실행소스 `878eeb45e3d647576e7e695d3d81f6f4e809b231`. 계약커밋dfa1f24,최종구현878eeb4. 이보고서커밋과실행소스를구별한다.
- 공통기록 `artifacts/experiments/20261109T115137-dab89dcc/record.json`: **completed/exit0**,5fold완료. 2026-11-09 20:51:37→21:15:11 KST. worker경과1412.37초(23.54분),통제속도비교아님.
- 계획 `artifacts/surface-normal-distance-20261109/plan.json` SHA256 `a3f1362f796f0b2e5b34154ddce5af6904ddc25cfb390e4a653604ea0dfcf957`.
- 명령 `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-normal-distance-20261109/plan.json -- .venv/bin/python artifacts/surface-normal-distance-20261109/worker.py`. 고유console noclobber,실행1회/재시도0/추가가설0/자동review·Gemini·Codex호출0.
- 유일변수: x→concat(x,d),d=sqrt(mean_j((x_j-mu_j)^2/max(var_j,1e-6))). 원본384차원을보존하고거리1개만추가,invalid추가거리0. float64통계·거리계산뒤입력float32에추가. 선형head385계수+bias. 추가거리scale/분산하한/거리식탐색없음.
- mu/var는각outer학습fold의명시적target0구역/valid토큰으로만추정. 기존training group/class질량을정상끼리재정규화,각구역valid토큰평균/2차moment의가중합. var=E[x²]−mu²에고정1e-6floor. 평가/다른fold통계사용0. 원본통계/정상ID/group/photoSHA/질량/mask해시를normal-statistics-foldN.json에저장했다.
- 직접대조α0=`20261108T215307-941b3aaa` (정상bag1/결함bag1). 원래품질reference=`20261106T210640-0eb1bdc0`. 실패한최근국소대비/정상계수2로대조군을교체하지않았다.
- N+D+G+L2,α0/정상bag1/결함bag1/L2=1/정상upperLSE tau0.1/결함·출력max/sigmoid/threshold0.5/라벨/mask/1776행/5fold/seed20261031/CPU백본/zero초기값/mass/center정의고정.1000반복1250평가·최종gradient1e-5/내부1e-7불변. 기존streamed alpha0 objective/direction/metrics는바이트동일재사용.

## 같은1776구역 실측

|대조|FN/370|누락률|FP/1406|오탐률|AUC|
|---|---:|---:|---:|---:|---:|
|원래 품질 대조|67|18.1081%|201|14.2959%|0.916650648|
|직접 α0 대조|57|15.4054%|167|11.8777%|0.931924955|
|정상 거리 후보|56|15.1351%|174|12.3755%|0.931325209|
|후보−α0|−1|−0.2703%p|+7|+0.4979%p|−0.000599746|

직접α0 대비paired photo-group bootstrap95% **[-0.002628454,+0.001217494]**(2000회/seed20261107). 차이/하한이양수여야하는표현개선gate미충족. 구간이0을포함하므로개선미확인이며,악화나동등성을통계적으로확정하지않는다.

원래품질reference대비 FN−11(−2.9730%p),FP−27(−1.9203%p),AUC+0.014674561,paired95%[0.008121193,0.021992782]. 이를직접α0 대비개선으로바꾸지않는다.

|기존 채택 AND 기준|실측|판정|
|---|---|---|
|FN≤67/370|56|통과|
|FP≤112/1406|174|미달|
|원래AUC대비증가≥0.03|+0.014674561|미달|
|원래대비paired95%하한>0|+0.008121193|통과|
|5fold수렴·누수/근거유효|모두내부목표1e-7|통과|

직접α0 대비신규누락5·회복6/신규오탐15·회복8. 전체ID는analysis.json/error_changes와1776행comparison.csv. OOF오류ID로학습선별·가중·라벨변경0. 관찰제한누락/오탐은미평가. 원라벨179/1597 보조평가는evaluation.json에분리했고확정정답370/1406과혼합하지않는다.

## 학습fold 한정과 합성/실행 검증

|fold|통계정상구역|정상사진group|평가group/사진겹침|반복/평가수|최종gradient|
|---|---:|---:|---:|---|---:|
|0|1162|158|0/0|108/117|9.3712e-8|
|1|1116|157|0/0|141/152|8.4139e-8|
|2|1099|157|0/0|121/128|7.6659e-8|
|3|1132|158|0/0|129/138|6.2373e-8|
|4|1115|158|0/0|130/145|8.9479e-8|

- `.venv/bin/python tools/experiments/surface-normal-distance-20261109/checks.py`: 독립손계산mu4.25/var1.9375,결함/패딩값변경불변,평가입력변경에도고정통계보존,거리독립수식/원본보존/floor/singleton/잘못된라벨·질량거절,worker통계함수에x[tr]만전달하는경계검사,추가거리계수0의기존loss/gradient일치,385D합성fit/성분감사통과. 실제사진·실제모델학습은사용하지않은합성검사다.
- `postflight.json`: 공통record파일해시·동결입력215개·사진204장SHA,동일1776행/라벨·5fold훈련행/mass/mask/target의α0일치,유한385계수모델5개·최종thetaSHA/fit성분감사일치검증통과.
- 각normal통계사용ID/group/photoSHA가그fold의훈련정상행과정확히일치. 정상질량을동일float32 group질량에서float64로재구성하여저장값/SHA일치. 평가group목록과사진분리확인,모든fold에서평가통계사용false. 다른학습fold의통계를재사용하지않았다. 최종검증은사진추가추론/통계재fit없이저장근거로수행했다.
- gradient성분합최대오차6.94e-16,loss성분합7.78e-16. 산술rankloss/gradient정확히0. 실제분산최솟값약0.8589~0.8683으로분산floor활성차원0. 거리계수는5fold 0.002110/0.003506/0.002353/0.001654/0.002658. 계수크기만으로정보부재/개별OOF오류원인을단정하거나scale탐색을하지않았다.
- AST 함수수 신규features2/worker0/checks1,모두7이하. 기존objective3/streamed2/direction1/metrics4불변. 통계/거리호출각1전이,학습bag경로 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4전이,streamed custom autograd경로4전이. 새callback/재귀없음.
- 공통실행기반환뒤development-cycle/latest.json을확인했다. 별도20261024 ai_calls_forbidden pointer를이번인계/판정으로주장하지않고보존했다. 이번record에development_handoff/token_report없음. 실제평가/채택은이번record·evaluation기준. 자동변경·운영채택0.

## 변경 파일·HTML·리스크·롤백

변경파일5개: 신규 tools/experiments/surface-normal-distance-20261109/{features.py,worker.py,checks.py},신규task MD/이결과MD. 핵심diff는훈련정상moment추정/385D거리추가와fold별출처저장뿐이다. 기존모델/손실소스/worker/라벨/사진/캐시/평가기준을수정하지않았다. 기존청크계산은바이트동일runtime mirror로등록,새mirror만baseline=null이며공통snapshot에보존했다.

`artifacts/surface-normal-distance-20261109/report.html`: 사진204장위구역1776개의사람정답·α0/후보점수/출력/FNFP·분모/%p,정상통계출처,개발CV구분,리스크/롤백을표시. HTML파싱/개수/경로/저장점수대조통과,CSV1776행. macOS open exit0와브라우저목록의보고서제목/URL은확인했다. 콘텐츠관찰은 **file: 프로토콜 브라우저URL보안정책 차단**,네이티브는Mac잠금/자동해제실패여서 **실제render미확인**. 차단을우회하지않았고외부서버/터널/업로드0. 구역박스만표시하고최고반응patch/사람결함점을만들지않았다.

리스크/미검증: 희귀정상인쇄/반사·정상다봉분포를대각분산하나로표현하는한계는남는다. 개별시각원인/인과분해/독립일반화/관찰제한/통제속도·peakmemory는미검증. 반복개발CV·부분재판정·단일seed로일반화주장불가. 통계도훈련자료에적합된표현이며정상거리를결함정답으로간주하지않았다. 합성통과/수렴/누락1감소를전체진척/품질개선으로바꾸지않았다. PROGRESS_CRITERIA.md/development-progress.json의78/100v1.13유지.

운영미채택이므로복원할운영모델/fallback변경없음. 코드롤백필요시후속의존/실행잠금을확인하고후보878eeb4를일반gitrevert하여관련검증후일반push한다. 문서충돌은검토하며force/reset/증거삭제/과거snapshot일괄덮어쓰기없음. 비소유.claude/와다른세션worktree/브랜치/미통합·고유근거보존. 새worktree없음,기존최근통합rollback checkout1개와다른미통합작업보존. 후속가설·계수/threshold/scale탐색0.

에튜 포인트: 평균/분산을구하는통계전처리도자료에적합하는학습이다. 평가사진으로분산을계산하면평가분포를미리본표현이된다. 이번에는학습정상의mu/var만고정해평가에적용했고,예를들어fold0은학습정상1162구역만사용하고평가41group은배제했다.
