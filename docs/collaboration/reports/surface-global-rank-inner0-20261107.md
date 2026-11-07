# 내부 line search 허용치0 단일 재실험

개발 진척78/100(v1.13) 유지. 첫fold 평가예산 소진 실패, 후보 미채택, 추가재시도0.

검증 소스 ddbac13. record: artifacts/experiments/20261107T094656-f5f8ae4d/record.json, status=failed/error_kind=child_exit. 벽시계34.08분(CPU 특징추출/학습 포함). fold0/5완료. 후보OOF/observations/result/models 없음.

## 실제 진단과 원인

내부/외부 tolerance_change0 적용. 첫fold의159회차 line search에서 총 closure 평가1250/1250을 소진했고 1251번째 호출은 계산 전에 guard가 차단했다. max_iter1000은유지. line-search-fold0.count.json restored=true로 원래PyTorch함수복원확인. 설치패키지/운영함수변경0.

159회차시작: 누적평가195, loss0.5471336347003728, 초기방향미분-1.0402513823586052e-8,남은평가1055. 이line search가1055회trial평가를사용하고반환하지못했다. 마지막trial loss0.5471336346992776,방향미분-1.0400286452522117e-8. 마지막1034개trial은loss와방향미분이동일했다. step은tensor(0.0001)로표시되지만tensor repr은반올림되므로정확한step값까지모두동일하다고단정하지않는다.

최종trial의 |g_new·d|/|g_start·d|=0.9997858814607979. strong Wolfe의곡률기준은<=0.9이므로미충족. 내부구간종료1e-9를없앤뒤에도 방향미분이충분히줄지않는trial을반복해예산소진했다. 단순히내부허용치가커서만멈춘문제라는설명으로는해결되지않았다. 비매끄러운max의gradient전환/부동소수점구간정체등의세부원인은구간양끝/정밀step이없어미확정.

예외진단 coefficient_gradient0.0010474943004439817/bias_gradient5.680759900459492e-6는마지막trial의유한gradient이며채택된최종모델gradient가아니다. 진단objective/final_loss의문자열nan은예외handler가넣은미확정placeholder이지실제loss가NaN이었다는뜻이아니다. 실제trial loss는유한했다. optimizer.state.func_evals195는진행중line search가반환하지않아미갱신인값이며실제평가수는별도counter1250과trial1249개+초기closure1개로검산한다.

## 성능/판정

|지표|기존모델|후보/변화|기존기준|
|---|---|---|---|
|누락률|67/370=18.11%|산출불가|FN<=67|
|오탐률|201/1406=14.30%|산출불가|FP<=112|
|AUC|0.91665065|산출불가|差>=0.03 AND 사진bootstrap95%하한>0|

실행/수렴기준미통과,성능기준미평가. 기존최종gradient<=1e-5/tolerance_grad1e-7/1000회/1250평가/손실계수/amax/라벨/분할/seed/mass/L2/초기값/백본/threshold불변. 독립일반화미확인. 실패를모델성능0/악화로추정하지않음.

## 변경/검증/리스크/롤백

신규tools/experiments/surface-global-rank-inner0-20261107/objective.py: 실험프로세스에서만 내부strong_wolfe허용치0적용,trial/start/return로그,finally복원,총closure1250guard. worker.py는새가설ID/경로,metrics.py는기존바이트복사. task/본보고서추가. 이전소스/라벨/운영모델변경0. logging은기존trial결과를읽고추가평가0.

검사: 합성fixture의수렴/로그-평가횟수일치/허용치0/원함수복원/함수수검사통과,py_compile/diff-check통과. 공통record소스SHA/1776reference/FN67/FP201검산,trial1249+initial1=1250검산. 실제실험1회실패,추가재시도0/외부AI0. 전체회귀/독립시험/후보성능비교미실행.

구조: objective6함수(closure/두tracecallback포함),metrics4,worker1lambda. 모델손실경로closure→detail_bag_loss→point_bag_loss2전이유지. tracewrapper가프레임워크callback경로에전이2개추가. 전체optimizer/callback경로는4전이를초과하므로구조기준완전충족으로보고하지않는다. task에해당한계를기록. 이실험worker를운영에통합/채택하지않음.

runner반환후latest.json은과거20261024handoff를계속가리킴,이번handoff/next_steps/token_report없음. 이전기록으로이번실패를대체하지않음.

HTML artifacts/surface-global-rank-inner0-20261107/report.html:실패진단/사전기준과기존대조군32사진저장출력만표시,후보출력없음. 열기/렌더별도기록.

리스크:내부허용치0은이상태에서예산을소모하며수렴을해결하지못했다. privateAPI연결은격리worker에한정하고복원확인. 롤백은신규소스/문서커밋만revert후일반push,record/snapshot/trial로그보존. 운영모델/라벨복구불필요. 추가재실험없음.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
