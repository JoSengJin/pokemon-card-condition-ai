# 원형 특징 보존·점/존재 분리·작은 비선형 head: 세 개 독립 비교

- task_id: surface-preserved-heads-20261028
- owner: Codex
- status: implementing
- base_sha: b4874c38de2625386b9eb80091306eec21d9d424
- branch: codex/surface-preserved-heads-20261028
- worktree: 로컬 전용
- goal: 사용자 승인 세 방향을 서로 결합하지 않고 동일 기준선/4fold/147·51·11cohort에서 각각 한 번 비교한다. 5시간 계정 한도 안에서 새 근거가 있는 개발을 지속하며 반복 학습·토큰 소진 목적 작업은 하지 않는다.

## 소유 파일

allowed_files:
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

features1함수,nonlinear최대4(closure포함),worker최대4,새test최대5. fit_fold→fitter→closure→detail_bag_loss→point_bag_loss최대4전이. 단위검사는원형임베딩logit동치·패딩/변환지역성,역할별선정/라벨보존과logit평균식,MLP초기출력/gradient·학습/평가forward재생을검산한다. 실제실험은기본checkout ./experiment에서3개를직렬1회씩실행하며소스수정/통합은 ./develop 안에서만한다.

진척은PROGRESS_CRITERIA.md/development-progress.json의30/100 유지,완료조건을실제충족한증거만가산한다. 사진위사람정답/모델출력·같은분모FN/FP/%p·실제점51·record상태/전체수용·미검증/리스크·sourceSHA·열기요청/렌더확인을동명MD/HTML에적는다. 기록기준통과와독립일반화는구분한다.

롤백은통합source/plan커밋을 ./develop -- git revert 후검사/일반push,기존모델/정답복구불필요. 실험head/기록은보존한다. 원격동기화후최근완료checkout1개만유지하며이전Codex완료checkout은lock·고유증거SHA확인후정리,Claude/미통합/사용중checkout은보존한다.


## 비선형 실행 오류 보완 계약

최초비선형실행101414-6b20743e는첫fold학습결과를float32map에넣을때float64확률로RuntimeError가발생해failed다. 관찰결과/품질수치는생성되지않았고가설성능미평가다. dtype오류라는구체구현근거를수정하며폭/seed/L2/손실/수렴기준/임계값을바꾸지않는다.

fit_fold의반환확률을모든후보에서기존base map의float32에맞춘다. rawMLP학습/저장head는float64그대로다. float64feature->float32map대입회귀1개를추가하고기존4검사도유지한다. 실패snapshot을baseline으로등록한plan-nonlinear-storage-fix.json의고유ID surface-nonlinear-head-storage-fix-20261028로검증후한번실행한다. 이전실패plan/record/worker mirror는덮어쓰지않고수정본은ignored storage-fix/하위별도mirror에둔다. 자동재시도나모델가설튜닝이아니라판정이없었던실행오류의수정이며실패기록도함께보고한다.
