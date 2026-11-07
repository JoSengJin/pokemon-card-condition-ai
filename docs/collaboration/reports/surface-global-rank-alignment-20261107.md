# 정렬도0.01 보호 조건 · 단일 실험 결과

개발 진척 **78/100(v1.13) 유지**. 방향 보호 조건은 정상 작동했으나 수렴하지 못해 실패했다. 추가 재시도0. 결과 정리일2026-11-08(KST), 실험 시작일2026-11-07(KST).

## 실제 실행 결과

- 검증 소스 `20379e7`.
- record: `artifacts/experiments/20261107T140438-a4c05402/record.json`, status=failed, error_kind=child_exit.
- 벽시계 58.68분(CPU 특징 추출/학습 포함).
- 첫 fold **469회차**, 채택 이동468회. **실제 평가1250/1250**, 최대 반복1000 유지.
- 종료 사유 **evaluation_budget**. 완료 fold0/5, observations/result/models/후보OOF 없음.
- 최종 채택 상태 loss **0.5433133925980731**, 최대 gradient **0.0014407593330947113**, 기존1e-5 기준의 **144.08배**.
- 실제 실패 checkpoint가 저장됐고 gradient·평가수·유한성을 검산했다.

## 사전 성능 기준과 판정

|지표|기존 동결 모델|후보·변화|사전 기준|
|---|---|---|---|
|누락률|67/370 = 18.11%|산출 불가|FN<=67|
|오탐률|201/1406 = 14.30%|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|증가>=0.03 AND 사진그룹bootstrap95%하한>0|

실행·수렴 기준 미통과、성능 기준 미평가. 실패를 모델성능0/악화로 해석하지 않는다. 독립 일반화 미확인. 학습 loss를 정확도 향상으로 보고하지 않는다.

## 보호 조건과 실패 원인

보호 조건은 **114·246·365·368회차의4회** 작동했다. 초기 정렬도0.00811957/0.00753948/0.00906921/0.00755805를 약1로 복구했고, 곡률 history를0으로 만들었다. 이후 현재gradient/새방향/실제채택step으로 새 곡률 갱신이 이어졌다.

|초기화 회차|해당 탐색 평가수|채택 step|채택 후 최대gradient|
|---|---:|---:|---:|
|114|14|0.0001220703125|0.00183049|
|246|18|7.62939453125e-6|0.00223138|
|365|27|1.4901161193847656e-8|0.00128664|
|368|28|7.450580596923828e-9|0.00125073|

초기화로 방향 정렬은 개선됐지만, 음의gradient 방향도 최대 패치 전환이 있는 목적에서 큰step으로 내려가지 못해 backtracking으로 축소됐다. 이4회 채택 각각에서 최대패치1구역이 바뀌었다. 방향을 바꾸기만 하면 gradient 기준을 만족한다는 가설은 이번 결과에서 지지되지 않았다.

최종 정렬도는0.05937194734216733으로0.01보다 크므로 마지막469회차에는 초기화하지 않았다. 마지막trial들은 패치3~4구역이 바뀌며 loss가 증가해 거절됐고 평가예산이 끝났다. 더작은step이 나중에 성공했을지나 다른threshold가 유효한지는 시험하지 않았다.

trial1249개는 모두 서로 다른 파라미터이고 중복 차단0. 채택468·거절781. 채택441회에서 최대패치가 바뀌었다. 채택 상태의 최소 gradient도0.000997633021642701로 기준의99.76배였다. 따라서 거의직각방향 차단은 작동했으나 패치 전환·gradient정체 자체는 해소되지 않았다. 더 깊은 수학적 원인/수렴가능성은 미확인이다.

## 구현과 검증

신규 `tools/experiments/surface-global-rank-alignment-20261107/`:
- `armijo_direction.py`: 정렬도<0.01일 때만 history/scale/이전step 초기화와 d=-g 적용. 다음 갱신을 위해 현재gradient와 실제사용방향 저장. 전후정렬도/reset/history/H_diag 로그.
- `objective.py`: 이전 평평한 Armijo 구현 그대로. 진단값을 기존trace에서 기록하며 새평가0.
- `worker.py`: 새가설ID/경로. 동일 입력/분할/대조군.
- `metrics.py`: 이전 바이트 그대로.
- `checks.py`: 기존 합성검사와 보호조건/일관된재시작상태 검증.

함수 수 objective3/direction1/metrics4/worker0/checks3 각각7이하. `worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss` **4전이**, `worker→fit→lbfgs_direction` **2전이** 유지. 새callback/재귀없음.

합성 검증 통과:0.0099초기화/0.0101기존방향보존,history/scale/stale step삭제,현재gradient/방향저장,다음실제step으로fresh곡률갱신. 기존loss/gradient일치, smoothfixture35방향/history20검증,작은fixture수렴,Armijo엄격감소,동일파라미터차단,1250평가fixture,상대곡률경계사례,정밀로그/checkpoint도통과. py_compile/AST함수수/diff-check통과.

실제 검산: record실행소스SHA와plan실제import소스/입력SHA불변,1776reference/FN67/FP201동일,trial1249+초기1=1250,checkpointgradient/평가수검산. 실제모델실험1회,추가재시도0. 전체회귀/독립시험/외부AI0.

## 조건 유지·리스크·롤백

최종gradient<=1e-5/내부목표1e-7, 최대1000회/총평가1250회, 기존상대곡률/Armijo/중복차단/loss/label/fold/mass/L2/영초기값/amax/백본/seed/threshold0.5 및 FN/FP/AUC 기준을 유지했다. 유일한 최적화 변수변경은 고정0.01방향보호조건이며threshold탐색없음. 운영모델/fallback/원답/진척기준수정0. 후보운영채택0.

리스크: 음의gradient방향도 비매끄러운구간에서 backtracking예산을소모했다. 이번 보호조건은 수렴/일반화 개선 근거가 없다. 실패 후 추가 소스수정/성능재실험은 하지 않았다.

롤백은 신규소스/문서커밋만revert후일반push,record/snapshot/log/checkpoint보존. 운영모델·라벨복구불필요.

runner반환후latest.json은과거20261024handoff를계속가리켰다. 이번handoff/next_steps/token_report없으며과거기록으로실패대체하지않았다.

HTML `artifacts/surface-global-rank-alignment-20261107/report.html`:실제진단/사전기준과명시적으로표시한기존대조군32사진저장출력. 후보출력없음. 열기·렌더별도기록.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
