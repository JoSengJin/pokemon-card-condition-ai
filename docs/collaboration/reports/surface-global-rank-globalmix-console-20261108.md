# 고유 콘솔 로그 보존 · 전쌍 LME 후보 단일 실험 결과 — 2026-11-08

개발 진척 **78/100(v1.13) 유지**. PYTHONUNBUFFERED=1·고유console.log 보존을 합성·실제실행에서확인했다. 실제실험1회가정상완료됐고5fold모두수렴했지만 **오탐상한·AUC최소증가량은미달**이다. 추가재시도0, 운영미채택.

## 실제 실행과 로그

- 검증소스 `b6f4f6cc8ac10f49e06246d8b633cef1e5a47143`.
- record: `artifacts/experiments/20261108T133726-586d9cdd/record.json`, **completed / return_code0 / stagefinished**.
- `result.acceptance_passed=false`, `evaluation.criterion_met=false`. 실행실패/중단과품질기준미달을구분한다.
- 실제로그: `artifacts/surface-global-rank-globalmix-console-20261108/execution-63ea2bb6ae2d/console.log`. 환경변수PYTHONUNBUFFERED=1, shellnoclobber로새경로에stdout/stderr를함께저장했다. worker특징추출/5개fit완료/평가메시지와실행기최종완료메시지를확인했다. 최종SHA/크기는outcome.json에기록했다.
- 실행: `PYTHONUNBUFFERED=1 ./experiment --plan artifacts/surface-global-rank-globalmix-console-20261108/plan.json -- .venv/bin/python artifacts/surface-global-rank-globalmix-console-20261108/worker.py > artifacts/surface-global-rank-globalmix-console-20261108/execution-63ea2bb6ae2d/console.log 2>&1` (실행shell의 `set -C` 적용).
- CPU 특징추출, 평가포함벽시계1939.54초(32.33분). 로깅에따른속도/정확도효과를주장하지않는다.
- 이전 `20261108T002449-6e4ad830`의interrupted기록은보존했다. 이번은사용자가새로승인한1회이며같은턴에서자동재시도하지않았다.

## 기존 동결 모델 대비 동일1776구역 결과

확정결함370/정상1406, 204사진그룹, threshold0.5. 기준은 `20261106T210640-0eb1bdc0` completed revised모델. 라벨/ID/사진/분할/평가순서를유지했다.

|지표|기존 모델|이번 후보|변화|사전기준|판정|
|---|---:|---:|---:|---|---|
|누락률|67/370=18.1081%|51/370=13.7838%|−4.3243%p(16개감소)|FN≤67|통과|
|오탐률|201/1406=14.2959%|179/1406=12.7312%|−1.5647%p(22개감소)|FP≤112(7.9659%)|**미통과**|
|AUC|0.916650648|0.930927300|+0.014276652|증가≥0.03|**미통과**|
|AUC차95%구간|—|[0.007979489,0.021023437]|사진그룹pairedbootstrap2000회|하한>0|통과|

오탐은상한보다 **67개많고**, AUC증가량은요구0.03보다 **0.015723348부족**하다. 모든조건AND라전체미통과다. 누락·오탐의순감소나AUC양의구간만으로통과시키지않는다. bootstrap2000회는기존평가지표재표집수이며 optimizer목적함수평가1250회한도와다르다.

## 품질 미달의 근거와 범위

- 모델수렴/계산한도 문제가아니다. 5/5fold가최대gradient2.4065e-8~9.6791e-8로최종기준1e-5와기존내부목표1e-7을충족했다.
- 기준모델대비기존누락21개/오탐45개회복, 신규누락5개/신규오탐23개발생. 총오류268→230(38개감소). 전체집합의라벨/분모를바꾸지않았다.
- 이전산술/LME/50:50후보의공통오탐160개중 **158개가이번에도오탐**이다. 전쌍LME의약한결함강조가새오탐없이기존정상반응을충분히분리했다는증거는없다. 해당집합을학습선별/가중치에쓰지않았다.
- 직전행별LME50:50후보는FN57/FP176/AUC0.929197263이었다. 이번은FN51/FP179/AUC0.930927300: 누락6개감소,오탐3개증가,AUC+0.001730037. 후보간별도신뢰구간을계산하지않았으므로유의한개선이라고단정하지않는다.
- 직전의신규누락6개중654/695는회복하고155/311/574/1509는남았다. 이번에는870이기준모델대비신규누락으로추가됐다. 직전신규오탐17개중15개가남았다. 이는이전가설과일치하는절충양상이지만개별학습쌍gradient의인과분해는하지않았다.
- 이번은전쌍LME후보의첫완료성능측정이다. 로깅은같은모델의출력을보존하는설정이며**성능변화를로깅때문이라고해석하지않는다**. 새patchlogit/결함시각원인분석이나추가후보탐색은실행하지않았다.

신규누락원본인덱스: **155,311,574,870,1509**.

신규오탐원본인덱스: **12,52,71,97,123,245,276,300,408,444,560,596,666,752,793,943,951,1364,1438,1441,1469,1723,1724**.

사진별기존/후보출력은HTML, 전체1776행은comparison.csv, 실제전체실패ID/점수는공통result.json에있다. 오류로선택한일부사진만의비율을전체누락/오탐률로쓰지않았다.

## 변경파일·핵심diff·보존계약

신규 `tools/experiments/surface-global-rank-globalmix-console-20261108/{worker,objective,metrics,armijo_direction,checks,checks_logging}.py`, task와이보고서. ignored계획/console/검사결과/HTML/CSV/outcome을추가했다. 과거소스/기록은그대로다.

실제모델 objective/direction/metrics는이전globalmix와**바이트동일**이다. worker는새가설ID만다르다. 핵심보완은실행환경 `PYTHONUNBUFFERED=1`과부모/worker가상속하는동일stdout/stderr파일,고유경로/noclobber다. 모델함수나콜백층을추가하지않았다.

산술0.5/전체학습쌍LME0.5/총순위계수1, 모든학습쌍, 정상patch tau0.1upperLSE·결함/출력max·sigmoid·threshold0.5·기존bagloss/mass/L2/seed/init/backbone/CPU·그룹분할/독립평가봉인을유지했다. 이전수렴보호(relativecurvature/alignment0.01/Armijo/duplicateguard)와수치기준을바꾸지않았다.

함수정의수 worker0/objective3/direction1/metrics4/checks3/loggingchecks0. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss **4전이**,worker→fit→direction2. 기존출력API/사람정답/분할/운영모델변경0.

## 실제 검증

- `checks_logging.py` 통과: 합성부모/자식의stdout/stderr·UNBUFFERED=1을동일고유파일에서종료전부터확인. 기존로그배타생성검사통과.
- `checks.py` 통과: 전체쌍LME독립수식/autograd·정확50:50값/gradient/모든쌍기여바닥·양축순열·반복정규화/singleton/extreme유한성. 기존35방향/history20·합성수렴·엄격Armijo·중복차단·1250budgetfixture·상대곡률/정렬·normalmask/tau0.1/결함hardmax검사통과.
- 기존선택unittest2개통과: `test_supervisor_sigterm_persists_interruption`, `test_newest_failed_or_running_record_blocks_stale_success` (합성임시root,실제모델아님).
- compile/AST함수수/byteparity/CPU환경/diff검사통과. 계획입력hash100개불변,공통record등록파일hash검증. 결과행1776/정답370·1406/기준점수정렬유지. 기존worker의그룹/사진해시학습평가분리검사유지.
- fold별trial로그수+초기평가1=실제평가수검산. 추가최종closure호출없음. 실제기록은아래와같다.

|fold|기록반복값|실제평가수(초기포함)|최종maxgradient|기준통과|
|---|---:|---:|---:|---|
|0|102|109|9.67908464e-8|통과|
|1|108|114|6.89738091e-8|통과|
|2|116|122|9.21398950e-8|통과|
|3|107|111|2.40648243e-8|통과|
|4|119|128|4.47194733e-8|통과|

각fold1000반복/1250평가한도내다. 반복값은종료조건확인을포함하는기존n_iter기록방식그대로다.

## HTML·진척·인계

`artifacts/surface-global-rank-globalmix-console-20261108/report.html`: 실제204사진/1776사람정답구역과기준/후보점수,누락/오탐·분모·%p·AUC·판정을표시한다. 구역box는기존사람구역이며모델이새로찾은결함좌표가아니다. 일반화개선미확인인반복개발CV/모델선택자료임을표시한다.

HTML생성/내용대조/사진참조존재는검증했다. 현재CUA미제공·이전로컬file프로토콜정책차단을존중하여열기/렌더는미실행,우회/외부서버/업로드0이다. 로컬링크를제공한다.

고정진척 PROGRESS_CRITERIA.md/development-progress.json v1.13의78/100유지. 새완료항목이나운영준비를선언하지않는다. runner반환후latest.json은과거20261024handoff/ai_calls_forbidden을가리키며이번handoff/token_report/next_steps는생성되지않았다. 과거결과로이번실험을대체하지않았다.

## 리스크·롤백

로깅은외부턴취소를막지않으며강제종료직전의OS버퍼까지보장하지않는다. 이번에는stdout/stderr와정상종료를보존했으나실제취소상황의로그유실방지까지시험한것은아니다. 모델은오탐/AUC기준미달,반복개발평가/일부점수선택재판정편향이있고독립일반화미확인이다.

롤백: 신규격리소스커밋 `b6f4f6c`와이번문서커밋만revert해일반push. 운영모델/라벨/분할은변경없어복원불필요. 고유console·공통record/snapshot/가중치/trace/HTML/CSV는증거로보존한다. 후보는운영채택하지않았으며기준미달뒤추가재시도0. `.claude/`는비소유항목으로그대로다.

에튜 포인트: stdout/stderr는부모프로세스의파일descriptor를자식이상속하므로,최상위공통명령에서한번리다이렉트하면양쪽로그를모을수있다. PYTHONUNBUFFERED=1은Python출력버퍼링을줄여중간상태를남기지만모델계산식이나외부취소의의미를바꾸지는않는다.
