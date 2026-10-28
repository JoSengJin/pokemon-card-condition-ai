# 원형 특징 보존·점/존재 분리·작은 비선형 head: 세 개 독립 비교

- task_id: surface-preserved-heads-20261028
- owner: Codex
- status: integrated
- base_sha: b4874c38de2625386b9eb80091306eec21d9d424
- branch: codex/surface-preserved-heads-20261028
- worktree: 로컬 전용
- goal: 사용자 승인 세 방향을 서로 결합하지 않고 동일 기준선/4fold/147·51·11cohort에서 각각 한 번 비교한다. 5시간 계정 한도 안에서 새 근거가 있는 개발을 지속하며 반복 학습·토큰 소진 목적 작업은 하지 않는다.

## 소유 파일

allowed_files:
- tools/experiments/surface-preserved-heads-20261028/worker-layer8.py
- tools/experiments/surface-preserved-heads-20261028/plan-layer8.json
- tests/test_surface_layer8.py
- tools/experiments/surface-preserved-heads-20261028/audit.py
- tools/experiments/surface-preserved-heads-20261028/worker-audit.py
- tools/experiments/surface-preserved-heads-20261028/plan-audit.json
- tools/experiments/surface-preserved-heads-20261028/features.py
- tools/experiments/surface-preserved-heads-20261028/nonlinear.py
- tools/experiments/surface-preserved-heads-20261028/worker.py
- tools/experiments/surface-preserved-heads-20261028/plan-preserved.json
- tools/experiments/surface-preserved-heads-20261028/plan-separated.json
- tools/experiments/surface-preserved-heads-20261028/plan-nonlinear.json
- tools/experiments/surface-preserved-heads-20261028/plan-nonlinear-storage-fix.json
- tests/test_surface_preserved_heads.py
- docs/collaboration/tasks/surface-preserved-heads-20261028.md
- docs/collaboration/reports/surface-preserved-heads-20261028.md
- docs/collaboration/reports/surface-preserved-heads-20261028.html

ignored artifacts/surface-preserved-heads-20261028/ (mirror/검사·감사), 공통 실행기의 각 새 artifacts/experiments/<run>/record·head·HTML. Claude 모든 checkout·수집/검토/신규사진·라벨·manifest,미추적 DATA_INVENTORY_20261028.md,기존실험/worker/cache/모델,card_condition/*,PokeCollector,운영fallback,기준/점수는 읽기 전용. 외부AI/네트워크 수집/의존성 설치0.

## 공통 불변

base122011의같은153RGB DINO token/마스크/기존53학습점·147구역/typed51·11cohort,원래4frontfold·그룹/raw/decoded분리·threshold.5·뒷면map·L2계수1·zero초기출력·LBFGS100·수렴gradient<=1e-5·class/group mass보존. 후보들은각각동일기준선과비교하며승자fold혼합/후보결합/기준수정없다. 새라벨·val/봉인test편입·backbone추론0.

성공은FN<=16/94,FP<=18/53,새오답0,최소1기존복구,typed51새누락0와기존11cohort전체수용이다. 수렴/누수/SHA오류는failed로종료해후보성능을추정하지않는다. 수치/품질보호미통과는미채택. 계수/폭/seed/threshold/반복수탐색·자동재시도0. 기준을충족하지못한연구head는운영에연결하지않는다.

## H1 원형+crop잔차 정보 보존

앞면만 [x, x-mean(valid x)]로확장한다. 원래384차원이그대로포함되므로기존coef를[w,0]로임베딩해logit을재생할수있다. 패딩잔차는0,mask와사진기하불변. 차원768로증가해용량과L2유도편향도바뀌므로단순히정보보존만의인과효과라고주장하지않는다. 원래단일점/weak/max_bound손실과fitter는그대로다. 평균만삭제한070837실패의재시도가아니라공통정보를보존하는별도입력가설이다.

## H2 실제점/존재 감독 두 경로

pointhead: 기존정확점양성bag+명시적정상bag만학습,좌표없는양성은빼고정상으로바꾸지않는다. presencehead: 같은모든원래bag target으로학습하되양성은위치없는presence손실(tokens=-1)을사용한다. 각역할의선정된training집합에서동일group/class균형규칙을적용한다. 원래head100iteration/gradientguard그대로각각수렴해야한다. 최종logit은두head rawlogit의고정1/2평균(sigmoid전)이며가중치/교정탐색없다. 두경로분리/모델용량변화가함께포함되는구조가설이고기울기충돌자체를손실오류로단정하지않는다.

## H3 작은 비선형 head

원래384차원과원래training center,bag손실그대로8-unit tanhMLP로분류기만바꾼다. hidden weight는로컬CPU Generator(seed0)정규분포/sqrt384,hiddenbias/outputcoef/outputbias는0. 초기출력0을baseline과맞추며모든층0의학습정지를피한다. L2=.5*(W_hidden²+W_output²).sum,모든bias미벌점,계수1고정. LBFGS100/tolerances와gradient<=1e-5동일. 폭/활성/seed탐색없고수렴실패시종료한다. 제한된실물에서과적합가능성이커같은학습loss감소를개선으로세지않는다. 다른과거edge모델의비선형결과와현재DINO앞면을동일평가로섞지않는다.

## 구조·검사·실행

features1함수,nonlinear최대4(closure포함),worker최대4,새test최대7. fit_fold→fitter→closure→detail_bag_loss→point_bag_loss최대4전이. 단위검사는원형임베딩logit동치·패딩/변환지역성,역할별선정/라벨보존과logit평균식,MLP초기출력/gradient·학습/평가forward재생을검산한다. 실제실험은기본checkout ./experiment에서3개를직렬1회씩실행하며소스수정/통합은 ./develop 안에서만한다.

진척은PROGRESS_CRITERIA.md/development-progress.json의30/100 유지,완료조건을실제충족한증거만가산한다. 사진위사람정답/모델출력·같은분모FN/FP/%p·실제점51·record상태/전체수용·미검증/리스크·sourceSHA·열기요청/렌더확인을동명MD/HTML에적는다. 기록기준통과와독립일반화는구분한다.

롤백은통합source/plan커밋을 ./develop -- git revert 후검사/일반push,기존모델/정답복구불필요. 실험head/기록은보존한다. 원격동기화후최근완료checkout1개만유지하며이전Codex완료checkout은lock·고유증거SHA확인후정리,Claude/미통합/사용중checkout은보존한다.


## 비선형 실행 오류 보완 계약

최초비선형실행101414-6b20743e는첫fold학습결과를float32map에넣을때float64확률로RuntimeError가발생해failed다. 관찰결과/품질수치는생성되지않았고가설성능미평가다. dtype오류라는구체구현근거를수정하며폭/seed/L2/손실/수렴기준/임계값을바꾸지않는다.

fit_fold의반환확률을모든후보에서기존base map의float32에맞춘다. rawMLP학습/저장head는float64그대로다. float64feature->float32map대입회귀1개를추가하고기존4검사도유지한다. 실패snapshot을baseline으로등록한plan-nonlinear-storage-fix.json의고유ID surface-nonlinear-head-storage-fix-20261028로검증후한번실행한다. 이전실패plan/record/worker mirror는덮어쓰지않고수정본은ignored storage-fix/하위별도mirror에둔다. 자동재시도나모델가설튜닝이아니라판정이없었던실행오류의수정이며실패기록도함께보고한다.


## 완료 후보의 training/held 원인 분리 진단

H1의4fold학습목적은0.215~0.226으로원래0.265~0.271보다낮지만held오탐/실제점누락이늘었다. H2는오탐9/53으로줄었으나누락28/94로늘었다. MLP수정실행은3번째fold에서gradient1.1174e-5로수렴미달(2fold만완료)이므로전체성능미측정/재시도0이다.

추가학습대신audit.py(최대5함수)/worker-audit.py(최대2)/plan-audit.json으로한번진단한다. 원래4fold별같은training rows와heldrows에서원래head/H1/H2고정head의구역최대·기존실제점응답을계산한다. H2 point/presence 개별경로도보되후보선택/혼합비율튜닝에사용하지않는다. training행은fold사이반복되므로합산정확도·독립표본으로세지않는다.

H1은같은확장입력에서[w_original,0] 임베딩목적값을실제계산해원래기록과2e-5내재생,새head목적과비교한다. 저장heldmap재생<=2e-5·모든그룹/raw/decoded분리·원래147/11cohort실제checkpoint재생·inputSHA보존이진단성공기준이다. 학습과held간차이가확인돼도데이터부족/과적합을원인으로단정하지않고,표현/정규화/감독구조가함께변한한계도명시한다. 이진단은new fit0이고기존모델품질통과/score상승아님. 결과보고서에원래MLP실패2건을모두보존한다.


## 다음 표현 가설: 앞면 표면·224의 고정 block8 (사용자 지속 개발 승인 범위)

진단102607은원래head가training구역을거의맞추고H1이네fold모두더낮은학습목적을얻어도held실제점/오탐은악화함을확인했다. 같은분류기를반복학습/확대하는대신표현층변경하나를시험한다. 과거143432/170601 block8은다른뒷면edge74bags·448입력에서실패했다. 그실패는보존하고이번앞면surface97bags·224를독립가설로등록한다. 효과는미확인이고이후다른층/혼합계수탐색은하지않는다.

worker-layer8.py(최대2함수)는이미설치된pinnedDINOv2 VITS14의같은weights를CPU2threads/eval/frozen으로읽고각앞면crop에서n=[7,11],norm=True로block8/최종층을한번에뽑는다. 새CNN학습/다운로드/외부AI0,실제backbone forward97회는이후가설의명시적예외이며원래세후보는forward0그대로다.

동일RGB/224/EXIF/padding/정규화·모든원래사진/box/mask/실제점보존. 먼저최종층CPU대기존cache feature최대차<=1e-3,고정원래head와11cohort의score재생<=2e-5/판정동일을모든앞면에서확인한다. 이control이실패하면candidate학습전failed로종료하고비교를추정하지않는다. 통과하면앞면특징만block8로교체해원래point/weak/max_bound·L2=1·zero init·LBFGS100·gradient1e-5·4fold·뒷면map불변을보존해1회비교한다. H1/H2변경을동시에쓰지않는다.

성공/실패품질기준은기존147/51/11cohort그대로,노출된개발평가이며독립일반화아니다. layer_pair API선택/순서·shape오류를synthetic2개검사(test_surface_layer8.py)로검산한다. code_changes에새worker baseline=null과pinnedweight/vendorSHA를명시하고,각crop의두층cache와control오차를새record폴더에보존한다. CPU2만사용하며Claude자료확보/검토파일·정답/박스/운영코드변경0.


## 실행 인계 — 2026-10-28

상태: 구현·canonical실험·회귀검사 완료, 모델미채택. 검증main source2a4a7a0, 격리sourcefeafb69. H1/H2 completed이나전체수용false, MLP원실행/저장dtype보완/중간층 모두failed로완전성능미측정. 고정head진단completed이나품질pass아님. main/격리관련17검사각OK, 6record SHA/기존입력/뒷면map/147score/11cohort 대조통과. 변경소스함수1/3/4/5/1/2개, 주요프로젝트손실경로4전이, 운영소스변경0. 상세상태/분모/%p/리스크/롤백은동명reports MD/HTML 및 ignored 요약index.html. 실자료HTML3개열기요청queued/렌더미확인. 원격/정리는후속확인. Claude수집·정답·평가·봉인·운영fallback변경0.


최종통합확인: main/origin aff8869일치후 이전042713a Codex checkout만safe remove, 최신435eed1 Codex checkout 보존. 감사SHA/열기queued·file URL차단/렌더미확인은동명reports최종항목. 모델수용0,진척30/100불변.
