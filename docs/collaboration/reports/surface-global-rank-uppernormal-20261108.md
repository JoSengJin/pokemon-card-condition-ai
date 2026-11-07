# 정상 순위항 패치 수 정규화 제거 · 단일 실험 결과

개발 진척 **78/100(v1.13) 유지**. 5fold 수렴과 같은 개발 평가의 일부 개선은 확인했지만 사전 성능 기준 전체는 미통과했다. 운영 미채택, 추가 재시도0.

## 실행 상태

- 검증 소스 `989d618`.
- record: `artifacts/experiments/20261107T155555-84dbfe36/record.json`, **status=completed**. 실행 실패가 아니다.
- result.acceptance_passed=false, evaluation.criterion_met=false.
- 벽시계 25.72분, CPU 특징 추출/5fold 학습/평가 포함.
- 5/5fold 수렴. 최대 gradient 범위3.5975e-8~9.0595e-8, 기존1e-5 기준 통과.
- fold별 반복/실제평가: [(96, 103), (96, 99), (102, 107), (113, 118), (96, 102)]. 모두1000회/1250평가 이내, 초기평가 포함/최종 추가평가 없음.

## 기존 동결 모델 대비 동일1776구역 성능

결함370·정상1406, 사진그룹204, threshold0.5. 원래 completed revised 모델의 저장 출력과 같은 정답/ID/분모로 비교했다.

|지표|기존모델|후보|변화|사전기준|판정|
|---|---|---|---|---|---|
|누락률|67/370=18.11%|55/370=14.86%|**-3.24%p**,12개감소|FN<=67|통과|
|오탐률|201/1406=14.30%|177/1406=12.59%|**-1.71%p**,24개감소|FP<=112(7.97%)|미통과|
|AUC|0.91665065|0.92570067|**+0.00905002**|증가>=0.03|미통과|
|AUC차95%구간|—|[0.00452131,0.01392209]|사진그룹pairedbootstrap2000회|하한>0|통과|

오탐은 상한보다65개 많고 AUC증가량은0.03에0.02095 못 미쳤다. 즉 실패 사유는 이번에도 수렴/계산 문제가 아니라 **오탐 상한·AUC 최소 개선량 미충족**이다. 신규 누락4개·신규오탐15개 발생, 기존오류55개 회복(총오류268→232). 새오류를 숨기지 않으며 result comparison과사진별HTML에 표시한다.

## 직전 정규화 후보와의 맥락 비교

같은 확정1776구역에서 직전 정규화 후보 FN56/FP188/AUC0.92517973 대비 이번은 FN55/FP177/AUC0.92570067이다. 누락-0.27%p,오탐-0.78%p,AUC+0.00052093의 추가 변화였다. 이 후보끼리의 차이에는 별도 신뢰구간을 계산하지 않았으므로 통계적으로 확정된 개선으로 주장하지 않는다.

직전후보와 비교하면 누락6개를 회복했지만5개가 새로 누락됐고,오탐19개를 회복했지만8개가 새로 생겼다. 따라서 정규화 제거가 모든 오류를 일관되게 고친 것은 아니다. 정상 압력을 강화하는 가설과 오탐 순감소는 정합적이지만,패치별 학습/출력 gap을 저장하지 않아 개별 오탐의 인과는 미확인이다. 남은 구분력 부족을 threshold/기준 완화로 숨기지 않았다.

별도 원라벨 보조평가(같은ID,179결함/1597정상): FN44→37,FP369→350,AUC0.84899410→0.86409924,差+0.01510514. 다른 정답 분모이므로 확정정답 지표와 혼합 비교하지 않는다.

반복 개발CV/모델선택 자료이며 독립시험이 아니다. 과거모델 점수로 일부재판정이 선택된 편향이 있다. 독립 일반화/운영 품질 개선 미확인. 기존 worker의 fold별그룹/사진해시분리검사를 유지했다. D1/보충시험셋 성능 새평가/튜닝 없음.

## 변경·검증·구조

신규 `tools/experiments/surface-global-rank-uppernormal-20261108/objective.py`의 정상 순위항에서 **-tau*log(valid_count)만 제거**했다. `normal_z=0.1*logsumexp(valid_logits/0.1)`이다. tau0.1/계수1 고정. 결함 순위hardmax,최종출력prior.sw.score의hardmax,기존bag loss/라벨/분할/mask/mass/L2/영초기값/seed/백본/threshold0.5는 그대로다.

worker.py는새가설/경로,armijo_direction.py·metrics.py는이전바이트그대로,checks.py는새목적/상한/정규화제거 차이 검증. task/본보고서추가. 이전실험/원답/운영모델/진척기준 수정0.

합성검사: 별도구역별수식/autograd로새목적대조,masked smooth upper-max상한과정확tau*logcount차이,유효1/2/3패치동점값,무효paddinggradient0,정상switchgradient연속성,결함hardmax보존. 기존35방향/history20,smoothfixture수렴,Armijo엄격감소,중복차단,1250평가fixture,상대곡률/정렬초기화상태검사도통과. py_compile/AST함수수/diff-check통과.

실제검산: record소스SHA와plan실제import모듈/입력SHA불변,1776정답/점수정렬,fold별trial수+초기1=평가수검산. 실제실험1회,추가재시도0. 전체회귀/독립시험/외부AI0.

구조 objective3/direction1/metrics4/worker0/checks3함수로각각7이하. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss **4전이**, worker→fit→direction **2전이** 유지. 새callback/재귀없음。

## 리스크·롤백

정규화 제거는 유효패치수가많은bag에더큰정상순위값을부여한다. 더강한정상압력이누락을늘릴수있고학습상한집계와최종max출력은여전히다르다. 이번에는수렴과일부지표개선은확인했지만사전게이트를통과하지못했으므로운영채택하지않는다. 최종gradient1e-5/내부목표1e-7·1000회/1250평가·FN/FP/AUC기준 변경0。

롤백: 신규소스/문서커밋만revert후일반push. record/snapshot/모델·점수/로그보존. 운영모델·라벨복구불필요。

runner반환후latest.json은과거20261024handoff를계속가리켰고이번handoff/next_steps/token_report생성없음. 과거기록으로이번결과를대체하지않음。

HTML `artifacts/surface-global-rank-uppernormal-20261108/report.html`: 실제204사진/1776구역의사람정답·기존/후보점수·누락/오탐·변화·사전판정표시. 개발CV임을명시. 열기·렌더별도기록。

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
