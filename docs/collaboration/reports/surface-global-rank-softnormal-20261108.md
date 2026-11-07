# 정상 순위항 tau0.1 정규화 log-sum-exp · 단일 실험

개발 진척 **78/100(v1.13) 유지**. 5fold 모두 수렴했고 같은 개발 평가에서 누락·오탐·AUC가 개선됐지만 사전 성능 기준 전체는 미통과했다. 운영 미채택, 추가 재시도0.

## 실행 상태와 판정

- 검증 소스 `87b0cc5`.
- record: `artifacts/experiments/20261107T151448-1bcde981/record.json`, **status=completed**. 실행 실패가 아니다.
- result.acceptance_passed=false, evaluation.criterion_met=false. 기준 미달 결과를 성공으로 바꾸지 않았다.
- 벽시계 32.20분, CPU 특징 추출/5fold 학습/평가 포함.
- 수렴: 5/5fold. 최종 gradient 범위5.5770e-8~8.2343e-8, 기존1e-5 기준 통과.
- fold별 반복/실제평가: [(90, 93), (94, 101), (94, 101), (95, 97), (88, 94)]. 모두1000회/1250평가 이내. 초기평가 포함, 추가최종평가 없음.

## 같은 확정1776구역 성능

정답 결함370·정상1406, 사진그룹204, threshold0.5. 기존 완료 실험의 revised모델을 같은 정답/ID/분모로 비교했다.

|지표|기존모델|후보|변화|사전기준|판정|
|---|---|---|---|---|---|
|누락률|67/370=18.11%|56/370=15.14%|**-2.97%p**,11개감소|FN<=67|통과|
|오탐률|201/1406=14.30%|188/1406=13.37%|**-0.92%p**,13개감소|FP<=112(7.97%)|미통과|
|AUC|0.91665065|0.92517973|**+0.00852908**|증가>=0.03|미통과|
|AUC차95%구간|—|[0.00440684,0.01327528]|사진그룹pairedbootstrap2000회|하한>0|통과|

총평균은 좋아졌지만 오탐은 상한보다76개 많고 AUC증가량은0.03에 못 미쳤다. 신규누락4개·신규오탐19개도 발생했고, 기존오류47개를 회복했다(총오류268→244). `no_new_errors=false`를 사전에 유지했으며 새오류를 숨기지 않는다. 상세 ID는 result comparison 및 HTML에 표시한다.

별도 원라벨 보조평가(같은ID,179결함/1597정상): FN44→38,FP369→361,AUC0.84899410→0.86246559,差+0.01347149. 이는 다른정답 분모의 보조결과라 위 확정정답 지표와 섞어 개선량을 주장하지 않는다.

반복 개발CV/모델선택 자료이며 독립시험이 아니다. 일부 사람재판정은 과거모델점수로 선택돼 선택편향이 있다. 독립 일반화/운영 품질 개선 미확인. 학습과 각fold 평가의 그룹/사진해시 분리검사는 기존 worker로 수행했다. D1/보충시험셋의 성능을 새로 평가하거나 튜닝하지 않았다.

## 변경 내용과 검증

신규 `tools/experiments/surface-global-rank-softnormal-20261108/objective.py`: 순위항 정상logit만 `0.1*(logsumexp(valid_logits/0.1)-log(valid_count))`로 변경했다. 결함 순위logit의hardmax,기존 bag loss,최종출력prior.sw.score의hardmax,라벨·분할·mask·mass·L2·영초기값·seed·백본·threshold는 유지했다. tau0.1/계수1 고정,검색0.

worker.py는새가설/경로,armijo_direction.py와metrics.py는이전바이트그대로,checks.py는새목적/마스크/정규화/gradient연속성 검증. task/본보고서 추가. 이전실험/원답/운영모델/진척기준 수정0.

합성검사: 새정상집계를별도구역별수식과autograd로대조,유효1/2/3패치의영점/동일점수정규화,무효paddinggradient0,정상최대패치교체경계gradient연속성,결함hardmax보존. 기존35방향/history20,smoothfixture수렴,Armijo,중복차단,1250평가fixture,상대곡률/정렬초기화 경계도통과. py_compile/AST함수수/diff-check 통과.

실제소스SHA와plan실제import모듈/입력SHA 불변,1776정답/점수정렬,fold별trial수+초기1=실제평가수검산. 전체회귀/독립시험/외부AI호출/추가실험0.

구조: objective3/direction1/metrics4/worker0/checks3함수로 각각7이하. worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss **4전이**, worker→fit→direction **2전이** 유지. 정상집계는inline tensor연산,새callback없음.

## 원인 해석·리스크·롤백

정상 순위항만 smooth하게 바꾼 뒤5fold 모두 기존 gradient 기준에 수렴했다. 앞선 optimizer-only 후보들의실패와구분되는 결과지만, 모든실패원인이한정상구역이었다거나독립품질이개선됐다는증명은아니다. 정상 hardmax를 추적하는 기존 active_patch 로그는 이제 정상 순위항gradient의불연속을직접뜻하지않는다.

남은문제는 이번에는 수렴실패가 아니라 **오탐상한/AUC최소개선량 미충족**이다. 마스킹정규화는정상국소강신호를희석할수있고 학습집계와최종출력집계가다르다. 이위험은사전기준을완화할근거가아니다. 후보 운영채택/최종전체학습/독립평가/threshold변경없음.

롤백: 신규소스/문서커밋만revert후일반push. 실험record/snapshot/모델·점수/로그보존. 운영모델·라벨복구불필요.

runner반환후latest.json은과거20261024handoff를계속가리켰고이번handoff/next_steps/token_report생성없음. 과거기록을이번결과로대체하지않았다.

HTML `artifacts/surface-global-rank-softnormal-20261108/report.html`: 실제204사진/1776구역의사람정답·기존/후보점수·누락/오탐·변화및사전기준표시. 모델선택용개발CV임을명시. 열기·렌더확인별도기록.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
